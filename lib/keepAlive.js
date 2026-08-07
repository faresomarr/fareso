// lib/keepAlive.js
// ============================================================
//  Keep-Alive بدون لوب كل ثانية (مستقر وموفر للسجلات)
// ============================================================
//  - عند فتح السوكيت: نبضة واحدة فورية للقاعدة.
//  - heartbeat خفيف كل 30 ثانية (يكفي لإبقاء السوكيت نشطاً
//    عند مزودي الاستضافة ولا يسبّب فصل من واتساب).
//  - كل شيء يتم في الخلفية بدون طباعة ملايين السجلات.
// ============================================================

'use strict';

const DEFAULT_HEARTBEAT_MS = 30_000;        // نبضة كل 30 ثانية
const IMMEDIATE_PULSE_DELAY_MS = 1_500;     // نبضة بعد الفتح مباشرة
const MAX_HEARTBEAT_MS = 5 * 60_000;        // سقف أعلى: 5 دقائق

class SessionKeepAlive {
  constructor(opts = {}) {
    this.phone = opts.phone || 'unknown';
    this.heartbeatMs = clampPositive(opts.heartbeatMs, DEFAULT_HEARTBEAT_MS, 5_000, MAX_HEARTBEAT_MS);
    this.onPulse = typeof opts.onPulse === 'function' ? opts.onPulse : () => {};
    this.onHealthCheck = typeof opts.onHealthCheck === 'function' ? opts.onHealthCheck : () => {};
    this._timer = null;
    this._immediateTimer = null;
    this._stopped = false;
  }

  /**
   * تشغيل Keep-Alive لسوكيت مفتوح.
   * يستقبل الـ sock ليتم تحديث presence + الكتابة للقاعدة عند النبض.
   */
  start(sock) {
    this.stop();
    this._stopped = false;
    const phone = this.phone;

    // نبضة فورية بعد الفتح بقليل (ليست كل ثانية؛ مرة واحدة فقط)
    this._immediateTimer = setTimeout(() => {
      if (this._stopped) return;
      try {
        if (sock && typeof sock.sendPresenceUpdate === 'function') {
          // presence "available" خفيف — لا يسبّب فصل من واتساب
          sock.sendPresenceUpdate('available').catch(() => {});
        }
      } catch (_) { /* ignore */ }
      safeInvoke(this.onPulse, sock, phone);
      safeInvoke(this.onHealthCheck, sock, phone);
    }, IMMEDIATE_PULSE_DELAY_MS);

    this._timer = setInterval(() => {
      if (this._stopped) return;
      try {
        if (sock && typeof sock.sendPresenceUpdate === 'function') {
          sock.sendPresenceUpdate('available').catch(() => {});
        }
      } catch (_) { /* ignore */ }
      safeInvoke(this.onPulse, sock, phone);
      safeInvoke(this.onHealthCheck, sock, phone);
    }, this.heartbeatMs);

    // ضمان عدم إبقاء العملية حيّة لهذا المؤقّت فقط
    if (this._timer && typeof this._timer.unref === 'function') this._timer.unref();
    if (this._immediateTimer && typeof this._immediateTimer.unref === 'function') this._immediateTimer.unref();
  }

  stop() {
    this._stopped = true;
    if (this._timer) { clearInterval(this._timer); this._timer = null; }
    if (this._immediateTimer) { clearTimeout(this._immediateTimer); this._immediateTimer = null; }
  }

  isActive() {
    return !this._stopped && Boolean(this._timer || this._immediateTimer);
  }
}

function safeInvoke(fn, ...args) {
  try { fn(...args); } catch (_) { /* swallow — keep-alive لا يجب أن يكسر السوكيت */ }
}

function clampPositive(value, fallback, min, max) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return fallback;
  return Math.min(Math.max(n, min), max);
}

module.exports = {
  SessionKeepAlive,
  DEFAULT_HEARTBEAT_MS,
  IMMEDIATE_PULSE_DELAY_MS,
};
