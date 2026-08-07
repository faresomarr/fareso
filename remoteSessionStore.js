require('dotenv').config();

const zlib = require('zlib');
const { getMongoCollection, DEFAULT_MONGODB_URI } = require('./mongoClient');

const DEFAULT_REMOTE_SESSION_STORE_URI = DEFAULT_MONGODB_URI;
const ENABLE_REMOTE_SESSION_STORE = ['1', 'true', 'yes', 'on'].includes(String(process.env.ENABLE_REMOTE_SESSION_STORE || 'true').trim().toLowerCase());
const SESSION_COLLECTION_NAME = String(process.env.MONGODB_SESSIONS_COLLECTION || 'whatsapp_sessions').trim() || 'whatsapp_sessions';
const SESSION_COMPRESSION_MIN_BYTES = Math.max(256, Number(process.env.SESSION_COMPRESSION_MIN_BYTES || 512));
const SESSION_PRUNE_ENABLED = ['1', 'true', 'yes', 'on'].includes(String(process.env.SESSION_PRUNE_ENABLED || 'true').trim().toLowerCase());
const SESSION_STORE_MAX_BYTES = Math.max(256 * 1024, Number(process.env.SESSION_STORE_MAX_BYTES || (4 * 1024 * 1024)));
const SESSION_MAX_PRE_KEYS = Math.max(20, Number(process.env.SESSION_STORE_MAX_PRE_KEYS || 250));
const SESSION_MAX_SIGNAL_SESSIONS = Math.max(20, Number(process.env.SESSION_STORE_MAX_SIGNAL_SESSIONS || 200));
const SESSION_MAX_SENDER_KEYS = Math.max(20, Number(process.env.SESSION_STORE_MAX_SENDER_KEYS || 150));


function normalizePhone(phone = '') {
  return String(phone || '').replace(/\D/g, '').trim();
}

function isRemoteSessionStoreEnabled() {
  return ENABLE_REMOTE_SESSION_STORE && Boolean(DEFAULT_REMOTE_SESSION_STORE_URI || process.env.MONGODB_URI || process.env.MONGO_URL);
}

function encodeStoredFile(rawContent = '') {
  if (typeof rawContent !== 'string') return null;
  const buffer = Buffer.from(rawContent, 'utf8');
  if (!buffer.length) {
    return '';
  }

  if (buffer.length < SESSION_COMPRESSION_MIN_BYTES) {
    return rawContent;
  }

  try {
    const compressed = zlib.gzipSync(buffer, { level: 9 });
    if (compressed.length >= buffer.length) {
      return rawContent;
    }
    return {
      encoding: 'gzip-base64',
      data: compressed.toString('base64'),
      size: buffer.length,
      compressedSize: compressed.length,
    };
  } catch (_) {
    return rawContent;
  }
}

function decodeStoredFile(value) {
  if (typeof value === 'string') {
    return value;
  }
  if (!value || typeof value !== 'object') {
    return '';
  }
  if (value.encoding === 'gzip-base64' && typeof value.data === 'string') {
    try {
      return zlib.gunzipSync(Buffer.from(value.data, 'base64')).toString('utf8');
    } catch (_) {
      return '';
    }
  }
  if (typeof value.content === 'string') {
    return value.content;
  }
  return '';
}

function categorizeSessionFile(fileName = '') {
  const safeName = String(fileName || '').trim();
  if (!safeName.endsWith('.json')) return 'other';
  if (safeName === 'creds.json') return 'creds';
  if (safeName === 'session-meta.json') return 'meta';
  if (safeName.startsWith('app-state-sync-')) return 'app-state';
  if (safeName.startsWith('pre-key-')) return 'prekey';
  if (safeName.startsWith('sender-key-')) return 'sender';
  if (safeName.startsWith('session-')) return 'session';
  return 'other';
}

function sortFileNamesForRetention(fileNames = []) {
  return [...fileNames].sort((left, right) => {
    const l = String(left || '');
    const r = String(right || '');
    const lMatch = l.match(/(\d+)/g);
    const rMatch = r.match(/(\d+)/g);
    const lScore = lMatch ? Number(lMatch[lMatch.length - 1]) || 0 : 0;
    const rScore = rMatch ? Number(rMatch[rMatch.length - 1]) || 0 : 0;
    if (lScore !== rScore) return rScore - lScore;
    return r.localeCompare(l);
  });
}

function sanitizeSessionFiles(files = {}, { forStorage = false } = {}) {
  const output = {};
  for (const [fileName, rawContent] of Object.entries(files || {})) {
    const safeName = String(fileName || '').trim().replace(/[^a-zA-Z0-9._-]+/g, '_');
    if (!safeName || !safeName.endsWith('.json')) continue;
    const content = forStorage ? encodeStoredFile(rawContent) : decodeStoredFile(rawContent);
    if (typeof content !== 'string' && (!content || typeof content !== 'object')) continue;
    output[safeName] = content;
  }
  return output;
}

function estimateFilesByteLength(files = {}) {
  let total = 0;
  for (const value of Object.values(files || {})) {
    if (typeof value === 'string') {
      total += Buffer.byteLength(value, 'utf8');
      continue;
    }
    if (value?.encoding === 'gzip-base64' && typeof value.data === 'string') {
      total += Buffer.byteLength(value.data, 'utf8');
    }
  }
  return total;
}

function pruneSessionFiles(files = {}) {
  const decoded = sanitizeSessionFiles(files, { forStorage: false });
  if (!SESSION_PRUNE_ENABLED) {
    return { files: decoded, fileBytes: estimateFilesByteLength(decoded) };
  }
  const keep = {};
  const grouped = { prekey: [], session: [], sender: [], other: [] };

  for (const [fileName, content] of Object.entries(decoded)) {
    const category = categorizeSessionFile(fileName);
    if (category === 'creds' || category === 'meta' || category === 'app-state') {
      keep[fileName] = content;
      continue;
    }
    if (!grouped[category]) grouped[category] = [];
    grouped[category].push([fileName, content]);
  }

  const categoryLimits = {
    prekey: SESSION_MAX_PRE_KEYS,
    session: SESSION_MAX_SIGNAL_SESSIONS,
    sender: SESSION_MAX_SENDER_KEYS,
  };

  for (const [category, limit] of Object.entries(categoryLimits)) {
    const ranked = sortFileNamesForRetention(grouped[category].map(([fileName]) => fileName));
    const allowed = new Set(ranked.slice(0, limit));
    for (const [fileName, content] of grouped[category]) {
      if (allowed.has(fileName)) {
        keep[fileName] = content;
      }
    }
  }

  for (const [fileName, content] of grouped.other || []) {
    keep[fileName] = content;
  }

  const trimPriority = ['sender', 'session', 'prekey'];
  const trimmed = { ...keep };
  let totalBytes = estimateFilesByteLength(trimmed);

  if (totalBytes > SESSION_STORE_MAX_BYTES) {
    const rankedByCategory = {
      sender: sortFileNamesForRetention(Object.keys(trimmed).filter((name) => categorizeSessionFile(name) === 'sender')).reverse(),
      session: sortFileNamesForRetention(Object.keys(trimmed).filter((name) => categorizeSessionFile(name) === 'session')).reverse(),
      prekey: sortFileNamesForRetention(Object.keys(trimmed).filter((name) => categorizeSessionFile(name) === 'prekey')).reverse(),
    };

    for (const category of trimPriority) {
      for (const fileName of rankedByCategory[category]) {
        if (totalBytes <= SESSION_STORE_MAX_BYTES) break;
        const content = trimmed[fileName];
        delete trimmed[fileName];
        totalBytes -= estimateFilesByteLength({ [fileName]: content });
      }
      if (totalBytes <= SESSION_STORE_MAX_BYTES) break;
    }
  }

  return { files: trimmed, fileBytes: estimateFilesByteLength(trimmed) };
}

function normalizeSessionDocument(phone, payload = {}, { forStorage = false } = {}) {
  const normalizedPhone = normalizePhone(phone || payload.phone || payload.sessionId || '');
  if (!normalizedPhone) return null;
  const now = new Date().toISOString();
  const pruned = pruneSessionFiles(payload.files || {});
  const files = forStorage ? sanitizeSessionFiles(pruned.files || {}, { forStorage: true }) : sanitizeSessionFiles(pruned.files || {}, { forStorage: false });

  return {
    _id: normalizedPhone,
    phone: normalizedPhone,
    sessionId: normalizedPhone,
    ownerId: String(payload.ownerId || '').trim(),
    registered: payload.registered === true,
    lastConnectedAt: payload.lastConnectedAt || null,
    updatedAt: payload.updatedAt || now,
    files,
    fileCount: Object.keys(files).length,
    fileBytes: forStorage ? estimateFilesByteLength(files) : pruned.fileBytes,
    storageVersion: 3,
  };
}

let collectionPromise = null;

async function getSessionCollection() {
  if (!isRemoteSessionStoreEnabled()) {
    throw new Error('MongoDB session store is not configured');
  }

  if (!collectionPromise) {
    collectionPromise = (async () => {
      const collection = await getMongoCollection(SESSION_COLLECTION_NAME);
      await Promise.allSettled([
        collection.createIndex({ phone: 1 }, { unique: true }),
        collection.createIndex({ updatedAt: -1 }),
        collection.createIndex({ lastConnectedAt: -1 }),
        collection.createIndex({ fileBytes: -1 }),
      ]);
      return collection;
    })().catch((error) => {
      collectionPromise = null;
      throw error;
    });
  }

  return collectionPromise;
}

function normalizeFetchedSession(doc = {}) {
  if (!doc) return null;
  const normalizedPhone = normalizePhone(doc.phone || doc.sessionId || doc._id || '');
  if (!normalizedPhone) return null;
  const normalized = normalizeSessionDocument(normalizedPhone, doc, { forStorage: false });
  return {
    ...doc,
    phone: normalized.phone,
    sessionId: normalized.sessionId,
    ownerId: String(doc.ownerId || '').trim(),
    registered: doc.registered === true,
    lastConnectedAt: doc.lastConnectedAt || null,
    updatedAt: doc.updatedAt || null,
    files: normalized.files,
    fileCount: normalized.fileCount,
    fileBytes: normalized.fileBytes,
  };
}

async function listRemoteSessions() {
  const collection = await getSessionCollection();
  const sessions = await collection
    .find({}, { projection: { _id: 0, files: 0 } })
    .sort({ lastConnectedAt: -1, updatedAt: -1, phone: 1 })
    .toArray();
  return Array.isArray(sessions) ? sessions.map((item) => normalizeFetchedSession(item)).filter(Boolean) : [];
}

async function fetchRemoteSession(phone) {
  const normalizedPhone = normalizePhone(phone);
  if (!normalizedPhone) return null;
  const collection = await getSessionCollection();
  const session = await collection.findOne({ _id: normalizedPhone }, { projection: { _id: 0 } });
  return normalizeFetchedSession(session || null);
}

async function upsertRemoteSession(phone, session = {}) {
  const normalizedPhone = normalizePhone(phone);
  if (!normalizedPhone) return null;

  const collection = await getSessionCollection();
  const normalized = normalizeSessionDocument(normalizedPhone, session, { forStorage: true });
  if (!normalized) return null;

  await collection.updateOne(
    { _id: normalizedPhone },
    {
      $set: {
        phone: normalized.phone,
        sessionId: normalized.sessionId,
        ownerId: normalized.ownerId,
        registered: normalized.registered,
        lastConnectedAt: normalized.lastConnectedAt,
        updatedAt: normalized.updatedAt,
        files: normalized.files,
        fileCount: normalized.fileCount,
        fileBytes: normalized.fileBytes,
        storageVersion: normalized.storageVersion,
      },
      $setOnInsert: {
        createdAt: new Date().toISOString(),
      },
    },
    { upsert: true }
  );

  return fetchRemoteSession(normalizedPhone);
}

async function deleteRemoteSession(phone) {
  const normalizedPhone = normalizePhone(phone);
  if (!normalizedPhone) return false;
  const collection = await getSessionCollection();
  const result = await collection.deleteOne({ _id: normalizedPhone });
  return result.deletedCount > 0;
}

async function touchRemoteSession(phone, metadata = {}) {
  const normalizedPhone = normalizePhone(phone);
  if (!normalizedPhone) return null;
  const collection = await getSessionCollection();
  const now = new Date().toISOString();

  const setPayload = {
    phone: normalizedPhone,
    sessionId: normalizedPhone,
    updatedAt: now,
  };

  if (String(metadata.ownerId || '').trim()) {
    setPayload.ownerId = String(metadata.ownerId || '').trim();
  }
  if (typeof metadata.registered !== 'undefined') {
    setPayload.registered = metadata.registered === true;
  }
  if (Object.prototype.hasOwnProperty.call(metadata, 'lastConnectedAt')) {
    setPayload.lastConnectedAt = metadata.lastConnectedAt || null;
  }

  await collection.updateOne(
    { _id: normalizedPhone },
    {
      $set: setPayload,
      $setOnInsert: {
        createdAt: now,
        files: {},
        fileCount: 0,
        fileBytes: 0,
        storageVersion: 3,
      },
    },
    { upsert: true }
  );

  return fetchRemoteSession(normalizedPhone);
}

module.exports = {
  isRemoteSessionStoreEnabled,
  listRemoteSessions,
  fetchRemoteSession,
  upsertRemoteSession,
  deleteRemoteSession,
  touchRemoteSession,
};
