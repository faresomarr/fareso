const express = require('express');
const fs = require('fs-extra');
const path = require('path');
const pino = require('pino');
const { MongoClient } = require('mongodb');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  makeCacheableSignalKeyStore,
  fetchLatestBaileysVersion,
  Browsers,
  DisconnectReason,
  delay,
} = require('@whiskeysockets/baileys');
const { pairingBridge } = require('./lib/pairingBridge');
const { SESSION_ROOT } = require('./lib/storagePaths');

const app = express();
app.use(express.json({ limit: '2mb' }));

const PORT = Number(process.env.COMPANION_PORT || process.env.PAIRING_SERVER_PORT || 3100);
const SESSION_INDEX_FILE = path.join(SESSION_ROOT, 'index.json');
const logger = pino({ level: process.env.LOG_LEVEL || 'silent' });
const sockets = new Map();
const startPromises = new Map();
const reconnectTimers = new Map();
const heartbeatTimers = new Map();
const pairingRequests = new Map();
const RECONNECT_DELAY_MS = Math.max(1000, Number(process.env.RECONNECT_DELAY_MS || 1000));
const PAIRING_CODE_CACHE_MS = Math.max(30000, Number(process.env.PAIRING_CODE_CACHE_MS || 55000));
const SESSION_HEARTBEAT_INTERVAL_MS = Math.max(1000, Number(process.env.SESSION_HEARTBEAT_INTERVAL_MS || 1000));
const SESSION_COLLECTION_NAME = String(process.env.MONGODB_SESSIONS_COLLECTION || 'whatsapp_sessions').trim() || 'whatsapp_sessions';
const MONGODB_DB_NAME = String(process.env.MONGODB_DB_NAME || 'whatsapp_pairing_api').trim() || 'whatsapp_pairing_api';
const SESSION_STORE_TIMEOUT_MS = Math.max(5000, Number(process.env.SESSION_STORAGE_TIMEOUT_MS || 20000));
const MONGODB_URI = String(process.env.MONGODB_URI || process.env.MONGO_URL || '').trim();
let mongoCollectionPromise = null;

function normalizePhone(raw = '') {
  return String(raw || '').replace(/\D/g, '').trim();
}

function getSessionDir(phone) {
  return path.join(SESSION_ROOT, normalizePhone(phone));
}

function pickPhone(req) {
  const body = req.body || {};
  const query = req.query || {};
  return normalizePhone(body.num || body.phone || body.number || body.phoneNumber || query.num || query.phone || query.number || query.phoneNumber);
}

function getBrowserProfile() {
  try { return Browsers.ubuntu('Chrome'); } catch (_) {}
  try { return Browsers.windows('Chrome'); } catch (_) {}
  try { return Browsers.macOS('Safari'); } catch (_) {}
  return ['Ubuntu', 'Chrome', '22.04'];
}

function isRemoteStoreEnabled() {
  return Boolean(MONGODB_URI);
}

async function ensureSessionRoot() {
  await fs.ensureDir(SESSION_ROOT);
}

async function readSessionIndex() {
  await ensureSessionRoot();
  try {
    const data = await fs.readJson(SESSION_INDEX_FILE);
    return data && typeof data === 'object' ? data : { sessions: {} };
  } catch (_) {
    return { sessions: {} };
  }
}

async function writeSessionIndex(index) {
  await ensureSessionRoot();
  await fs.writeJson(SESSION_INDEX_FILE, index, { spaces: 2 });
}

async function updateSessionIndex(phone, patch = {}) {
  const normalized = normalizePhone(phone);
  if (!normalized) return null;
  const index = await readSessionIndex();
  const existing = index.sessions?.[normalized] || {};
  index.sessions = index.sessions || {};
  index.sessions[normalized] = {
    phone: normalized,
    sessionId: normalized,
    updatedAt: new Date().toISOString(),
    ...existing,
    ...patch,
  };
  await writeSessionIndex(index);
  return index.sessions[normalized];
}

function getDisconnectStatusCode(lastDisconnect = null) {
  return Number(lastDisconnect?.error?.output?.statusCode || lastDisconnect?.error?.statusCode || 0);
}

function isPermanentDisconnect(lastDisconnect = null) {
  const statusCode = getDisconnectStatusCode(lastDisconnect);
  const rawMessage = String(
    lastDisconnect?.error?.data ||
    lastDisconnect?.error?.message ||
    lastDisconnect?.error?.output?.payload?.message ||
    ''
  ).toLowerCase();
  if (statusCode === Number(DisconnectReason.loggedOut)) return true;
  if ([401, 403, 405, 500].includes(statusCode)) return true;
  return /(logged\s*out|device\s*removed|forbidden|banned|blocked|not-authorized|not authorized|session\s*expired|bad\s*session)/i.test(rawMessage);
}

function listSessionFiles(phone) {
  const normalized = normalizePhone(phone);
  const sessionDir = getSessionDir(normalized);
  if (!normalized || !fs.existsSync(sessionDir)) return [];
  return fs.readdirSync(sessionDir)
    .filter((name) => name && name.endsWith('.json'))
    .sort();
}

function hasLocalAuthFiles(phone) {
  return listSessionFiles(phone).some((fileName) => fileName === 'creds.json' || fileName.startsWith('app-state-sync-') || fileName.startsWith('pre-key-') || fileName.startsWith('sender-key-') || fileName.startsWith('session-'));
}

async function removeSessionDir(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized) return;
  await fs.remove(getSessionDir(normalized));
}

async function collectSessionFiles(phone) {
  const normalized = normalizePhone(phone);
  const files = {};
  for (const fileName of listSessionFiles(normalized)) {
    const filePath = path.join(getSessionDir(normalized), fileName);
    try {
      files[fileName] = await fs.readFile(filePath, 'utf8');
    } catch (error) {
      console.error('Failed to read session file', fileName, error?.message || error);
    }
  }
  return files;
}

async function writeSessionFiles(phone, files = {}) {
  const normalized = normalizePhone(phone);
  if (!normalized) return false;
  const sessionDir = getSessionDir(normalized);
  await fs.ensureDir(sessionDir);

  const allowed = new Set(Object.keys(files || {}).filter((name) => name.endsWith('.json')));
  for (const existingFile of listSessionFiles(normalized)) {
    if (!allowed.has(existingFile)) {
      try { await fs.remove(path.join(sessionDir, existingFile)); } catch (_) {}
    }
  }

  for (const [fileName, content] of Object.entries(files || {})) {
    if (!fileName || !fileName.endsWith('.json')) continue;
    await fs.writeFile(path.join(sessionDir, fileName), String(content || ''), 'utf8');
  }
  return true;
}

async function getSessionCollection() {
  if (!isRemoteStoreEnabled()) return null;
  if (!mongoCollectionPromise) {
    mongoCollectionPromise = (async () => {
      const client = new MongoClient(MONGODB_URI, {
        appName: 'local-whatsapp-pairing-server',
        serverSelectionTimeoutMS: SESSION_STORE_TIMEOUT_MS,
        connectTimeoutMS: SESSION_STORE_TIMEOUT_MS,
        maxPoolSize: 5,
        retryWrites: true,
      });
      await client.connect();
      const collection = client.db(MONGODB_DB_NAME).collection(SESSION_COLLECTION_NAME);
      await Promise.allSettled([
        collection.createIndex({ phone: 1 }, { unique: true }),
        collection.createIndex({ updatedAt: -1 }),
      ]);
      return collection;
    })().catch((error) => {
      mongoCollectionPromise = null;
      throw error;
    });
  }
  return mongoCollectionPromise;
}

function normalizeStoredSession(phone, payload = {}) {
  const normalized = normalizePhone(phone || payload.phone || payload.sessionId || payload._id || '');
  if (!normalized) return null;
  const files = {};
  for (const [fileName, content] of Object.entries(payload.files || {})) {
    const safeName = path.basename(String(fileName || '').trim());
    if (!safeName || !safeName.endsWith('.json')) continue;
    if (typeof content !== 'string') continue;
    files[safeName] = content;
  }
  return {
    _id: normalized,
    phone: normalized,
    sessionId: normalized,
    registered: payload.registered === true,
    connected: payload.connected === true,
    lastConnectedAt: payload.lastConnectedAt || null,
    lastDisconnectAt: payload.lastDisconnectAt || null,
    activatedAt: payload.activatedAt || null,
    updatedAt: payload.updatedAt || new Date().toISOString(),
    files,
    fileCount: Object.keys(files).length,
  };
}

async function listStoredSessions() {
  if (!isRemoteStoreEnabled()) return [];
  try {
    const collection = await getSessionCollection();
    const docs = await collection.find({}, { projection: { files: 0 } }).toArray();
    return docs.map((doc) => normalizeStoredSession(doc.phone || doc.sessionId || doc._id, doc)).filter(Boolean);
  } catch (error) {
    console.error('Failed to list stored sessions:', error?.message || error);
    return [];
  }
}

async function fetchStoredSession(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized || !isRemoteStoreEnabled()) return null;
  try {
    const collection = await getSessionCollection();
    const doc = await collection.findOne({ _id: normalized });
    return normalizeStoredSession(normalized, doc || {});
  } catch (error) {
    console.error('Failed to fetch stored session:', error?.message || error);
    return null;
  }
}

async function upsertStoredSession(phone, payload = {}) {
  const normalized = normalizePhone(phone);
  const doc = normalizeStoredSession(normalized, payload || {});
  if (!doc || !isRemoteStoreEnabled()) return doc;
  try {
    const collection = await getSessionCollection();
    await collection.updateOne({ _id: normalized }, { $set: doc }, { upsert: true });
  } catch (error) {
    console.error('Failed to upsert stored session:', error?.message || error);
  }
  return doc;
}

async function deleteStoredSession(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized || !isRemoteStoreEnabled()) return false;
  try {
    const collection = await getSessionCollection();
    await collection.deleteOne({ _id: normalized });
    return true;
  } catch (error) {
    console.error('Failed to delete stored session:', error?.message || error);
    return false;
  }
}

async function syncSessionToStore(phone, metadata = {}) {
  const normalized = normalizePhone(phone);
  if (!normalized) return false;
  const files = await collectSessionFiles(normalized);
  const snapshot = await upsertStoredSession(normalized, {
    ...metadata,
    phone: normalized,
    sessionId: normalized,
    files,
    updatedAt: new Date().toISOString(),
  });
  await updateSessionIndex(normalized, {
    registered: snapshot?.registered === true,
    connected: metadata.connected === true,
    lastConnectedAt: snapshot?.lastConnectedAt || null,
    activatedAt: snapshot?.activatedAt || null,
    remoteBackedUpAt: new Date().toISOString(),
    fileCount: snapshot?.fileCount || Object.keys(files).length,
  });
  return true;
}

async function restoreSessionFromStore(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized || hasLocalAuthFiles(normalized)) return false;
  const stored = await fetchStoredSession(normalized);
  if (!stored || !Object.keys(stored.files || {}).length) return false;
  await writeSessionFiles(normalized, stored.files || {});
  await updateSessionIndex(normalized, {
    registered: stored.registered === true,
    connected: false,
    restoredFromDatabaseAt: new Date().toISOString(),
    lastConnectedAt: stored.lastConnectedAt || null,
    fileCount: stored.fileCount || Object.keys(stored.files || {}).length,
  });
  return true;
}

function clearReconnect(phone) {
  const normalized = normalizePhone(phone);
  const timer = reconnectTimers.get(normalized);
  if (timer) {
    clearTimeout(timer);
    reconnectTimers.delete(normalized);
  }
}

function clearHeartbeat(phone) {
  const normalized = normalizePhone(phone);
  const timer = heartbeatTimers.get(normalized);
  if (timer) {
    clearInterval(timer);
    heartbeatTimers.delete(normalized);
  }
}

function startHeartbeat(sock, phone) {
  const normalized = normalizePhone(phone);
  if (!sock || !normalized) return;
  clearHeartbeat(normalized);
  const timer = setInterval(async () => {
    try {
      if (Number(sock.ws?.readyState) !== 1) return;
      if (typeof sock.ws?.ping === 'function') {
        try { sock.ws.ping(); } catch (_) {}
      }
      if (typeof sock.sendPresenceUpdate === 'function') {
        try { await sock.sendPresenceUpdate('available'); } catch (_) {}
      }
      await updateSessionIndex(normalized, {
        connected: true,
        registered: sock?.authState?.creds?.registered === true || Boolean(sock?.user),
        lastConnectedAt: new Date().toISOString(),
      });
    } catch (_) {}
  }, SESSION_HEARTBEAT_INTERVAL_MS);
  if (typeof timer.unref === 'function') timer.unref();
  heartbeatTimers.set(normalized, timer);
}

async function destroySocket(phone) {
  const normalized = normalizePhone(phone);
  const existing = sockets.get(normalized);
  clearHeartbeat(normalized);
  if (!existing) return;
  sockets.delete(normalized);
  try { existing.ws?.close?.(); } catch (_) {}
  try { existing.end?.(); } catch (_) {}
  try { pairingBridge.releaseSocket(normalized); } catch (_) {}
}

async function purgeSession(phone, { removeRemote = true } = {}) {
  const normalized = normalizePhone(phone);
  if (!normalized) return false;
  pairingRequests.delete(normalized);
  clearReconnect(normalized);
  await destroySocket(normalized);
  await removeSessionDir(normalized);
  if (removeRemote) {
    await deleteStoredSession(normalized);
  }
  await updateSessionIndex(normalized, {
    connected: false,
    registered: false,
    pendingPairing: false,
    lastPurgedAt: new Date().toISOString(),
  });
  return true;
}

function scheduleReconnect(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized || reconnectTimers.has(normalized)) return;
  const timer = setTimeout(async () => {
    reconnectTimers.delete(normalized);
    try {
      await createSocket(normalized, { bootRestore: true });
    } catch (error) {
      console.error('Reconnect failed for', normalized, error?.message || error);
      scheduleReconnect(normalized);
    }
  }, RECONNECT_DELAY_MS);
  reconnectTimers.set(normalized, timer);
}

function waitForPairingWindow(sock, phone, timeoutMs = 20000) {
  const normalized = normalizePhone(phone);
  if (!sock) return Promise.reject(new Error('Socket is required'));
  if (sock?.authState?.creds?.registered === true || sock?.user) {
    return Promise.resolve('registered');
  }

  return new Promise((resolve, reject) => {
    let settled = false;
    const cleanup = () => {
      clearTimeout(timer);
      try {
        if (typeof sock.ev.off === 'function') sock.ev.off('connection.update', onUpdate);
        else if (typeof sock.ev.removeListener === 'function') sock.ev.removeListener('connection.update', onUpdate);
      } catch (_) {}
    };
    const finishResolve = (reason) => {
      if (settled) return;
      settled = true;
      cleanup();
      updateSessionIndex(normalized, {
        pendingPairing: true,
        pairingWindowReadyAt: new Date().toISOString(),
        pairingWindowReason: String(reason || 'unknown'),
      }).catch(() => {});
      resolve(String(reason || 'ready'));
    };
    const finishReject = (error) => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(error instanceof Error ? error : new Error(String(error)));
    };
    const onUpdate = (update = {}) => {
      const connection = String(update.connection || '').trim();
      if (connection === 'connecting' || connection === 'open' || update.qr) {
        finishResolve(update.qr ? 'qr' : (connection || 'connecting'));
        return;
      }
      if (connection === 'close' && isPermanentDisconnect(update.lastDisconnect)) {
        finishReject(new Error(`Session closed before pairing (${getDisconnectStatusCode(update.lastDisconnect) || 'unknown'})`));
      }
    };
    const timer = setTimeout(() => finishResolve('timeout'), timeoutMs);
    try {
      sock.ev.on('connection.update', onUpdate);
    } catch (error) {
      finishReject(error);
    }
  });
}

async function requestPairingCodeWithRetry(sock, phone) {
  const normalized = normalizePhone(phone);
  const cached = pairingRequests.get(normalized);
  if (cached && cached.code && (Date.now() - Number(cached.requestedAt || 0) < PAIRING_CODE_CACHE_MS)) {
    return String(cached.code);
  }

  await waitForPairingWindow(sock, normalized);
  if (sock?.authState?.creds?.registered === true || sock?.user) {
    throw new Error('الرقم مربوط بالفعل والجلسة جاهزة.');
  }

  const waits = [1200, 2500, 4500, 7000];
  let lastError = new Error('Pairing code request failed');
  for (const waitMs of waits) {
    try {
      await delay(waitMs);
      const code = String(await sock.requestPairingCode(normalized) || '').trim();
      if (code) {
        pairingRequests.set(normalized, { code, requestedAt: Date.now() });
        return code;
      }
      lastError = new Error('Empty pairing code response');
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
    }
  }
  throw lastError;
}

async function handleConnectionOpened(sock, phone, state) {
  const normalized = normalizePhone(phone);
  const nowIso = new Date().toISOString();
  pairingRequests.delete(normalized);
  clearReconnect(normalized);

  await updateSessionIndex(normalized, {
    registered: true,
    connected: true,
    pendingPairing: false,
    lastConnectedAt: nowIso,
    meId: sock.user?.id || '',
    lastError: '',
  });

  startHeartbeat(sock, normalized);

  try { await syncSessionToStore(normalized, { registered: true, connected: true, lastConnectedAt: nowIso }); } catch (_) {}
  try {
    pairingBridge.setSocket(normalized, sock, {
      phone: normalized,
      registered: true,
      meId: sock.user?.id || '',
      connectedAt: nowIso,
    });
  } catch (_) {}
}

async function createSocket(phone, options = {}) {
  const normalized = normalizePhone(phone);
  if (!normalized) throw new Error('Phone is required');
  if (sockets.has(normalized)) return sockets.get(normalized);
  if (startPromises.has(normalized)) return startPromises.get(normalized);

  const startPromise = (async () => {
    clearReconnect(normalized);

    if (!hasLocalAuthFiles(normalized)) {
      await restoreSessionFromStore(normalized);
    }

    await ensureSessionRoot();
    const sessionDir = getSessionDir(normalized);
    await fs.ensureDir(sessionDir);
    const helper = await useMultiFileAuthState(sessionDir);
    const state = helper.state;
    const { version } = await fetchLatestBaileysVersion().catch(() => ({ version: undefined }));
    const sock = makeWASocket({
      version,
      browser: getBrowserProfile(),
      logger,
      printQRInTerminal: false,
      auth: {
        creds: state.creds,
        keys: makeCacheableSignalKeyStore(state.keys, logger),
      },
      markOnlineOnConnect: true,
      syncFullHistory: false,
      defaultQueryTimeoutMs: 0,
      connectTimeoutMs: 60000,
      keepAliveIntervalMs: 1000,
      fireInitQueries: true,
      emitOwnEvents: false,
      generateHighQualityLinkPreview: false,
    });

    sock.__sessionState = state;
    sockets.set(normalized, sock);

    const persistState = async (extra = {}) => {
      try { await helper.saveCreds(); } catch (error) { console.error('Failed to save creds for', normalized, error?.message || error); }
      await syncSessionToStore(normalized, {
        registered: extra.registered === true || state?.creds?.registered === true,
        connected: extra.connected === true,
        lastConnectedAt: extra.lastConnectedAt || null,
        lastDisconnectAt: extra.lastDisconnectAt || null,
      });
    };

    sock.ev.on('creds.update', async () => {
      await updateSessionIndex(normalized, {
        registered: state?.creds?.registered === true,
        lastCredsSaveAt: new Date().toISOString(),
      });
      await persistState({ registered: state?.creds?.registered === true });
    });

    sock.ev.on('connection.update', async (update = {}) => {
      const connection = update.connection || '';
      if (connection === 'connecting' || update.qr) {
        await updateSessionIndex(normalized, {
          connected: false,
          registered: state?.creds?.registered === true,
          pendingPairing: state?.creds?.registered !== true,
          lastPairingWindowAt: new Date().toISOString(),
          lastError: '',
        });
      }

      if (connection === 'open') {
        await handleConnectionOpened(sock, normalized, state);
        return;
      }

      if (connection === 'close') {
        clearHeartbeat(normalized);
        sockets.delete(normalized);
        const statusCode = getDisconnectStatusCode(update.lastDisconnect);
        const permanent = isPermanentDisconnect(update.lastDisconnect);
        const restartRequired = statusCode === Number(DisconnectReason.restartRequired);
        await updateSessionIndex(normalized, {
          connected: false,
          registered: state?.creds?.registered === true,
          pendingPairing: state?.creds?.registered !== true,
          lastDisconnectAt: new Date().toISOString(),
          lastDisconnectReason: String(update.lastDisconnect?.error?.message || statusCode || ''),
        });
        if (permanent) {
          await purgeSession(normalized, { removeRemote: true });
          return;
        }
        if (restartRequired) {
          await destroySocket(normalized);
        }
        scheduleReconnect(normalized);
      }
    });

    await updateSessionIndex(normalized, {
      registered: state?.creds?.registered === true,
      connected: false,
      sessionDir,
      startedAt: new Date().toISOString(),
    });

    if (state?.creds?.registered === true) {
      try { pairingBridge.setSocket(normalized, sock, { phone: normalized, registered: true }); } catch (_) {}
      await persistState({ registered: true, connected: false });
    }
    return sock;
  })().finally(() => {
    startPromises.delete(normalized);
  });

  startPromises.set(normalized, startPromise);
  return startPromise;
}

async function listLocalSessionPhones() {
  await ensureSessionRoot();
  const entries = await fs.readdir(SESSION_ROOT).catch(() => []);
  return entries.filter((name) => name !== 'index.json').map((name) => normalizePhone(name)).filter(Boolean);
}

async function restoreAllSessionsOnBoot() {
  const localPhones = await listLocalSessionPhones();
  const remotePhones = (await listStoredSessions()).map((item) => normalizePhone(item.phone || item.sessionId || item._id || '')).filter(Boolean);
  const phones = Array.from(new Set([...localPhones, ...remotePhones]));
  for (const phone of phones) {
    try {
      await createSocket(phone, { bootRestore: true });
      await delay(350);
    } catch (error) {
      console.error('Boot restore failed for', phone, error?.message || error);
    }
  }
}

app.get('/', async (_req, res) => {
  const index = await readSessionIndex();
  res.json({ status: 'ok', service: 'local-whatsapp-pairing-server', sessions: Object.keys(index.sessions || {}).length, time: new Date().toISOString() });
});

app.get('/health', async (_req, res) => {
  const index = await readSessionIndex();
  res.json({ status: 'ok', sessions: index.sessions || {}, activeSockets: Array.from(sockets.keys()) });
});

app.get('/api/session-status', async (req, res) => {
  const phone = pickPhone(req);
  if (!phone) return res.status(400).json({ success: false, error: 'phone is required' });
  const index = await readSessionIndex();
  return res.json({ success: true, session: index.sessions?.[phone] || null, active: sockets.has(phone), bridgeSocket: !!pairingBridge.getSocket(phone) });
});

app.all('/api/pairing', async (req, res) => {
  const phone = pickPhone(req);
  if (!phone) return res.status(400).json({ success: false, error: 'أدخل الرقم أولاً' });

  try {
    const index = await readSessionIndex();
    const existingRecord = index.sessions?.[phone] || {};
    if (existingRecord.registered === true || hasLocalAuthFiles(phone)) {
      const restoredSock = await createSocket(phone, { bootRestore: true });
      if (restoredSock?.user || existingRecord.registered === true || restoredSock?.__sessionState?.creds?.registered === true) {
        await updateSessionIndex(phone, {
          registered: true,
          connected: true,
          alreadyLinked: true,
          pendingPairing: false,
          lastPairingCheckAt: new Date().toISOString(),
        });
        try { await handleConnectionOpened(restoredSock, phone, restoredSock.__sessionState); } catch (_) {}
        return res.json({ success: true, linked: true, alreadyLinked: true, number: phone, message: 'الرقم مربوط بالفعل والجلسة محفوظة.' });
      }
    }

    await purgeSession(phone, { removeRemote: true });
    const sock = await createSocket(phone, { bootRestore: false });
    if (sock?.authState?.creds?.registered === true || sock?.user) {
      await updateSessionIndex(phone, {
        registered: true,
        connected: true,
        alreadyLinked: true,
        pendingPairing: false,
        lastPairingCheckAt: new Date().toISOString(),
      });
      try { await handleConnectionOpened(sock, phone, sock.__sessionState); } catch (_) {}
      return res.json({ success: true, linked: true, alreadyLinked: true, number: phone, message: 'الرقم مربوط بالفعل والجلسة محفوظة.' });
    }

    const code = await requestPairingCodeWithRetry(sock, phone);
    await updateSessionIndex(phone, {
      registered: false,
      connected: false,
      pendingPairing: true,
      lastPairCodeRequestedAt: new Date().toISOString(),
      lastError: '',
    });
    await syncSessionToStore(phone, { registered: false, connected: false });
    return res.json({ success: true, linked: false, number: phone, code, pairingCode: code, expiresInSeconds: Math.round(PAIRING_CODE_CACHE_MS / 1000) });
  } catch (error) {
    await updateSessionIndex(phone, {
      registered: false,
      connected: false,
      pendingPairing: false,
      lastError: error?.message || String(error),
      lastErrorAt: new Date().toISOString(),
    });
    console.error('Pairing failure for', phone, error?.stack || error?.message || error);
    return res.status(500).json({ success: false, error: error?.message || 'فشل توليد الكود، حاول مجدداً' });
  }
});

app.delete('/api/session/:phone', async (req, res) => {
  const phone = normalizePhone(req.params?.phone || '');
  if (!phone) return res.status(400).json({ success: false, error: 'phone is required' });
  await purgeSession(phone, { removeRemote: true });
  return res.json({ success: true, deleted: true, phone });
});

process.on('SIGINT', async () => {
  for (const timer of reconnectTimers.values()) clearTimeout(timer);
  for (const phone of Array.from(sockets.keys())) await destroySocket(phone);
  process.exit(0);
});

process.on('SIGTERM', async () => {
  for (const timer of reconnectTimers.values()) clearTimeout(timer);
  for (const phone of Array.from(sockets.keys())) await destroySocket(phone);
  process.exit(0);
});

app.listen(PORT, '0.0.0.0', async () => {
  await ensureSessionRoot();
  await restoreAllSessionsOnBoot();
  console.log(`Local pairing server listening on ${PORT}`);
});
