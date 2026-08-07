// lib/logThrottle.js
// ============================================================
//  Rate-limited Structured Logging — تقليل فيضان سجلات Railway
// ============================================================
//  - يطبّق خنق (rate limit) لكل نوع حدث: لا يطبع نفس المفتاح
//    أكثر من مرة كل N ميلي ثانية.
//  - يقلّل استهلاك الـ credit على Railway بشكل ملحوظ.
//  - لا يطبع رسائل per-message بشكل افتراضي؛ فقط أهم
//    أحداث الاتصال/الانفصال/الأخطاء.
// ============================================================

'use strict';

const DEFAULT_WINDOW_MS = 60_000; // دقيقة واحدة لكل مفتاح افتراضياً
const DEFAULT_MAX_PER_WINDOW = 5;  // 5 طبعات كحد أقصى لكل دقيقة لكل مفتاح

const lastSeen = new Map();

function throttle(key, payloadFn, opts = {}) {
  const windowMs = Number(opts.windowMs ?? DEFAULT_WINDOW_MS);
  const maxPerWindow = Number(opts.maxPerWindow ?? DEFAULT_MAX_PER_WINDOW);
  const now = Date.now();
  const entry = lastSeen.get(key) || { count: 0, firstAt: now, lastAt: 0, suppressed: 0 };

  // نافذة جديدة
  if (now - entry.firstAt > windowMs) {
    if (entry.suppressed > 0 && typeof opts.onWindowReset === 'function') {
      safeInvoke(opts.onWindowReset, key, entry.suppressed);
    }
    entry.count = 0;
    entry.firstAt = now;
    entry.suppressed = 0;
  }

  if (entry.count >= maxPerWindow) {
    entry.suppressed += 1;
    lastSeen.set(key, entry);
    return false;
  }

  entry.count += 1;
  entry.lastAt = now;
  lastSeen.set(key, entry);

  safeInvoke(payloadFn);
  return true;
}

function reset(key) {
  if (key === undefined) lastSeen.clear();
  else lastSeen.delete(key);
}

function safeInvoke(fn, ...args) {
  try { fn(...args); } catch (_) { /* لا تكسر منطق الخنق */ }
}

/**
 * إنشاء Logger مخصّص للسوكيتات: يطبع فقط أهم الأحداث ولا يغرق Railway.
 */
function createBoundedLogger(prefix = '') {
  const tag = prefix ? `[${prefix}]` : '';
  return {
    info: (key, message, meta) => {
      throttle(`info:${key}`, () => safeLog('info', `${tag} ${message}`, meta), { windowMs: 30_000, maxPerWindow: 8 });
    },
    warn: (key, message, meta) => {
      throttle(`warn:${key}`, () => safeLog('warn', `${tag} ${message}`, meta), { windowMs: 30_000, maxPerWindow: 12 });
    },
    error: (message, meta) => safeLog('error', `${tag} ${message}`, meta), // الأخطاء دائماً تطبع
  };
}

function safeLog(level, message, meta) {
  try {
    if (meta && Object.keys(meta).length) {
      // eslint-disable-next-line no-console
      console[level === 'info' ? 'log' : level](message);
    } else {
      // eslint-disable-next-line no-console
      console[level === 'info' ? 'log' : level](message);
    }
  } catch (_) { /* ignore */ }
}

module.exports = {
  throttle,
  reset,
  createBoundedLogger,
};
