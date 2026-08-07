// worker.js
// ============================================================
//  Multi-Session Worker
// ------------------------------------------------------------
//  يدير كل رقم مربوط بعزل تام:
//    • مجلد جلسة مستقل
//    • كائن سوكيت مستقل
//    • مؤقت إعادة اتصال مستقل
//    • Keep-Alive مستقل بدون لوب كل ثانية
//    • Owner Guard مستقل
//  لا يوجد أي متغير شائع على مستوى العملية يمكن أن يكسر
//  رقماً أثناء ربط آخر.
// ============================================================

'use strict';

const fs = require('fs');
const fsp = fs.promises;
const path = require('path');
const pino = require('pino');
const { EventEmitter } = require('events');
const NodeCache = require('node-cache');

const {
  makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  Browsers,
} = require('@whiskeysockets/baileys');

const {
  normalizePhone,
  getPhoneSessionDir,
  SESSION_ROOT,
  bus: sessionBus,
} = require('./lib/sessionManager');

const { SessionKeepAlive } = require('./lib/keepAlive');
const { createBoundedLogger } = require('./lib/logThrottle');
const { IndexWriteThrottle } = require('./lib/indexWriteThrottle');
const ownerGuard = require('./lib/ownerGuard');

const workerBus = new EventEmitter();
workerBus.setMaxListeners(0);

// كتالوج الأرقام النشطة — كل رقم له كائن مستقل بالكامل.
const activeClients = new Map();   // phone -> ClientEntry
const pairingQueue = new Map();    // phone -> Promise (قفل في مستوى الرقم)

// كاتب الفهرس — debounced لتقليل عمليات القرص.
const SESSION_INDEX_FILE = path.join(SESSION_ROOT, 'index.json');
const indexWriter = new IndexWriteThrottle(SESSION_INDEX_FILE, { delayMs: 800, maxDelayMs: 3000 });

const globalLogger = createBoundedLogger('worker');

let remoteStoreModule = null;
try { remoteStoreModule = require('./lib/remoteSessionStore'); } catch (_) { remoteStoreModule = null; }

class ClientEntry {
  constructor(phone) {
    this.phone = normalizePhone(phone);
    this.sock = null;
    this.state = 'idle';           // idle | connecting | open | closed | logged_out
    this.connectPromise = null;
    this.reconnectTimer = null;
    this.keepAlive = null;
    this.lastDisconnect = null;
    this.lastConnectedAt = null;
    this.ownerId = null;
    this.ownerJid = null;
    this.logger = createBoundedLogger(`bot:${this.phone}`);
    this._messageQueue = [];
    this._processingQueue = false;
    this._closed = false;
  }

  async init() {
    const sessionDir = getPhoneSessionDir(this.phone);
    // تحميل auth state محلياً
    const { state, saveCreds, removeCreds } = await useMultiFileAuthState(sessionDir);
    this.saveCreds = saveCreds;
    this.removeCreds = removeCreds;
    this.authState = state;
  }

  buildSock() {
    const sessionDir = getPhoneSessionDir(this.phone);
    const sock = makeWASocket({
      auth: this.authState,
      printQRInTerminal: false,
      logger: pino({ level: 'silent' }),
      browser: Browsers.macOS('Desktop'),
      generateHighQualityLinkPreview: false,
      markOnlineOnConnect: false,
      // أوقف الـ events التي تستهلك موارد وتسبب إغراق السجلات
      emitOwnEvents: false,
      fireInitQueries: true,
    });

    sock.ev.on('creds.update', async () => {
      try { await this.saveCreds(); } catch (_) {}
    });

    sock.ev.on('connection.update', async (update) => {
      await this._handleConnectionUpdate(update);
    });

    this.sock = sock;
    return sock;
  }

  async _handleConnectionUpdate(update) {
    if (this._closed) return;
    const { connection, lastDisconnect } = update || {};
    this.lastDisconnect = lastDisconnect || this.lastDisconnect;

    if (connection === 'open') {
      this.state = 'open';
      this.lastConnectedAt = new Date().toISOString();
      // مالك الرقم — لو لم يُسجَّل بعد، سجّل الرقم نفسه كاحتياط.
      if (!this.ownerId) {
        ownerGuard.setOwnerForPhone(this.phone, this.phone, this.sock?.user?.id || null);
      }
      sessionBus.emit('active:set', this.phone, { phone: this.phone, lastConnectedAt: this.lastConnectedAt });
      workerBus.emit('phone:open', this.phone);
      // بداية Keep-Alive
      this._startKeepAlive();
      // إرسال الرسالة الترحيبية فور الفتح (بدون انتظار)
      this._sendPostPairingWelcome().catch(() => {});
      // تسجيل في الفهرس (debounced)
      indexWriter.schedule(() => ({
        sessions: {
          ...readIndexSafe().sessions,
          [this.phone]: {
            ...((readIndexSafe().sessions || {})[this.phone] || {}),
            phone: this.phone,
            connected: true,
            registered: true,
            lastConnectedAt: this.lastConnectedAt,
            updatedAt: this.lastConnectedAt,
          },
        },
      }));
    } else if (connection === 'close') {
      this.state = 'closed';
      this._stopKeepAlive();
      const statusCode = getStatusCode(lastDisconnect);
      this.logger.warn(`closed:${statusCode}`, `connection.close code=${statusCode}`);
      // تحديث الفهرس — debounced
      indexWriter.schedule(() => {
        const idx = readIndexSafe();
        return {
          sessions: {
            ...(idx.sessions || {}),
            [this.phone]: {
              ...((idx.sessions || {})[this.phone] || {}),
              phone: this.phone,
              connected: false,
              registered: false,
              lastDisconnect: { code: statusCode, at: new Date().toISOString() },
              updatedAt: new Date().toISOString(),
            },
          },
        };
      });
      workerBus.emit('phone:close', this.phone, { code: statusCode });

      if (isPermanent(statusCode)) {
        // Logged out — لا نحاول إعادة الاتصال
        this.state = 'logged_out';
        try { if (typeof this.removeCreds === 'function') await this.removeCreds(); } catch (_) {}
        workerBus.emit('phone:logged_out', this.phone);
        return;
      }
      // إعادة اتصال بخلفية لا تسرّب السجلات
      this._scheduleReconnect();
    } else if (connection === 'connecting') {
      this.state = 'connecting';
    }
  }

  _startKeepAlive() {
    if (this.keepAlive) this.keepAlive.stop();
    this.keepAlive = new SessionKeepAlive({
      phone: this.phone,
      heartbeatMs: 30_000,             // 30 ثانية — يكفي لإبقاء السوكيت نشطاً
      onPulse: () => {
        if (this.state !== 'open') return;
        // كتابة debounced فقط عند النبض
        indexWriter.schedule(() => {
          const idx = readIndexSafe();
          return {
            sessions: {
              ...(idx.sessions || {}),
              [this.phone]: {
                ...((idx.sessions || {})[this.phone] || {}),
                phone: this.phone,
                connected: true,
                lastSeen: new Date().toISOString(),
                updatedAt: new Date().toISOString(),
              },
            },
          };
        });
      },
      onHealthCheck: () => {
        // فحص صامت — لا طباعة
        if (this.sock && this.state === 'open') {
          try { this.sock.sendPresenceUpdate('available').catch(() => {}); } catch (_) {}
        }
      },
    });
    this.keepAlive.start(this.sock);
  }

  _stopKeepAlive() {
    if (this.keepAlive) { this.keepAlive.stop(); this.keepAlive = null; }
  }

  _scheduleReconnect(delayMs = 1500) {
    if (this._closed) return;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    // backoff بسيط بدون إغراق السجلات
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (this._closed) return;
      this.start().catch(() => { /* swallow */ });
    }, delayMs);
    if (typeof this.reconnectTimer.unref === 'function') this.reconnectTimer.unref();
  }

  async _sendPostPairingWelcome() {
    const sock = this.sock;
    if (!sock || this.state !== 'open') return;
    const phone = this.phone;
    const ownJid = sock.user?.id || (phone ? `${phone}@s.whatsapp.net` : null);
    if (!ownJid) return;
    const welcome = [
      '✅ تم ربط الرقم بنجاح!',
      '',
      '🤖 البوت يعمل الآن على هذا الرقم.',
      '',
      '📌 ملاحظة هامة:',
      '— جميع أوامر البوت تستجيب لمالك الرقم فقط.',
      '— أي شخص آخر يرسل أمراً، سيتم تجاهله تلقائياً.',
      '— أنت فقط من يتحكم بهذا الرقم من خلال البوت.',
      '',
      '🚫 الأوامر لن تستجيب لأي مستخدم آخر، حفاظاً على أمان حسابك.',
    ].join('\n');
    try { await sock.sendMessage(ownJid, { text: welcome }); } catch (_) {}
  }

  async start() {
    if (this._closed) return false;
    if (this.state === 'connecting' || this.state === 'open') return true;
    if (!this.authState) await this.init();
    try {
      this.buildSock();
    } catch (e) {
      this.logger.error('start failed', { err: e && e.message });
      this._scheduleReconnect(3000);
      return false;
    }
    return true;
  }

  async close() {
    this._closed = true;
    this._stopKeepAlive();
    if (this.reconnectTimer) { clearTimeout(this.reconnectTimer); this.reconnectTimer = null; }
    try { if (this.sock) await this.sock.logout().catch(() => {}); } catch (_) {}
    try { if (this.sock) await this.sock.end().catch(() => {}); } catch (_) {}
    ownerGuard.clearOwnerForPhone(this.phone);
    workerBus.emit('phone:closed', this.phone);
  }

  /**
   * معالجة الرسائل — مع تطبيق Owner Guard لكل رقم.
   * يستقبل handler(message, context) من main.js.
   */
  async handleMessage(handler) {
    if (!this.sock) return;
    this.sock.ev.on('messages.upsert', async (m) => {
      if (this._closed) return;
      try {
        const messages = Array.isArray(m?.messages) ? m.messages : [];
        const ctx = {
          phone: this.phone,
          sock: this.sock,
          isOwnerForThisBot: (senderJid) => ownerGuard.isOwnerForThisBot(senderJid, this.sock),
          ownerForPhone: () => ownerGuard.getOwnerForPhone(this.phone),
        };
        for (const message of messages) {
          if (!message || message.key?.fromMe) continue;
          await safeInvoke(handler, message, ctx);
        }
      } catch (_) { /* swallow */ }
    });
  }
}

function readIndexSafe() {
  try {
    const raw = fs.readFileSync(SESSION_INDEX_FILE, 'utf8');
    const data = JSON.parse(raw);
    return (data && typeof data === 'object' && data.sessions) ? data : { sessions: {} };
  } catch (_) { return { sessions: {} }; }
}

function getStatusCode(lastDisconnect) {
  if (!lastDisconnect) return 0;
  const e = lastDisconnect.error || {};
  return Number(e.output?.statusCode || e.statusCode || 0);
}

function isPermanent(code) {
  if (!code) return false;
  const permanent = [
    DisconnectReason.loggedOut,
    DisconnectReason.multideviceMismatch,
    DisconnectReason.forbidden,
    401, 403, 440, 428,
  ];
  return permanent.includes(code);
}

async function safeInvoke(fn, ...args) {
  try { return await fn(...args); } catch (_) { /* ignore */ }
}

/**
 * جلب/إنشاء كائن لسوكيت هذا الرقم (مع قفل في مستوى الرقم).
 */
async function getClient(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized) return null;
  let entry = activeClients.get(normalized);
  if (!entry) {
    entry = new ClientEntry(normalized);
    activeClients.set(normalized, entry);
  }
  if (!entry.authState) await entry.init();
  return entry;
}

async function startPhone(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized) throw new Error('phone required');

  const prev = pairingQueue.get(normalized);
  if (prev) { try { await prev; } catch (_) {} }

  const task = (async () => {
    const client = await getClient(normalized);
    await client.start();
    return client;
  })();
  pairingQueue.set(normalized, task);
  try {
    return await task;
  } finally {
    pairingQueue.delete(normalized);
  }
}

async function stopPhone(phone) {
  const normalized = normalizePhone(phone);
  const entry = activeClients.get(normalized);
  if (!entry) return false;
  await entry.close();
  activeClients.delete(normalized);
  return true;
}

function listActivePhones() {
  return Array.from(activeClients.keys());
}

function setOwner(phone, ownerId, ownerJid = null) {
  return ownerGuard.setOwnerForPhone(phone, ownerId, ownerJid);
}

function isOwnerForSocket(senderJid, sock) {
  return ownerGuard.isOwnerForThisBot(senderJid, sock);
}

// ضمان كتابة آخر تحديثات الفهرس قبل الإغلاق
async function shutdown() {
  // إغلاق جميع السوكيتات
  for (const entry of activeClients.values()) {
    try { await entry.close(); } catch (_) {}
  }
  // كتابة آخر snapshot للفهرس
  indexWriter.flush();
}

// دعم الحوادث الخارجية: استعادة من الفهرس + مسارات الجلسات
async function resumeAllSessions() {
  const result = { resumed: 0, skipped: 0 };
  let phones = [];
  try {
    const dir = await fsp.readdir(SESSION_ROOT, { withFileTypes: true });
    phones = dir
      .filter((e) => e.isDirectory() && /^\d+/.test(e.name))
      .map((e) => e.name);
  } catch (_) { phones = []; }

  const fromIndex = Object.keys(readIndexSafe().sessions || {});
  const all = Array.from(new Set([...phones, ...fromIndex].map(normalizePhone))).filter(Boolean);

  for (const phone of all) {
    try {
      const dir = getPhoneSessionDir(phone);
      const credsExist = fs.existsSync(path.join(dir, 'creds.json'));
      if (!credsExist) { result.skipped += 1; continue; }
      await startPhone(phone);
      result.resumed += 1;
    } catch (_) { result.skipped += 1; }
  }
  return result;
}

module.exports = {
  getClient,
  startPhone,
  stopPhone,
  listActivePhones,
  setOwner,
  isOwnerForSocket,
  resumeAllSessions,
  shutdown,
  bus: workerBus,
};
