// lib/indexWriteThrottle.js
// ============================================================
//  Debounced Index Writes — تقليل عمليات كتابة sessions/index.json
// ============================================================
//  عند ربط عدة أرقام دفعة واحدة، أو عند تكرار الـ heartbeat،
//  كان الملف يُكتب على القرص عشرات المرات في الثانية. هذا يسبب
//  استهلاك CPU + كتابة متكررة على Railway. هذا الملف يجمّع
//  الكتابة في debounced write واحدة.
// ============================================================

'use strict';

const fs = require('fs');
const path = require('path');

class IndexWriteThrottle {
  constructor(filePath, opts = {}) {
    this.filePath = filePath;
    this.delayMs = Number(opts.delayMs ?? 800);
    this.maxDelayMs = Number(opts.maxDelayMs ?? 3_000);
    this._timer = null;
    this._pendingSnapshot = null;
    this._lastFlushAt = 0;
    this._firstChangeAt = 0;
  }

  /**
   * حدّث الـ snapshot وأجّل الكتابة (debounce).
   */
  schedule(buildSnapshotFn) {
    this._pendingSnapshot = typeof buildSnapshotFn === 'function' ? buildSnapshotFn : this._pendingSnapshot;
    if (this._timer) {
      // مدد المؤقّت إلى الأبد إذا استمرت التحديثات
      this._resetTimer(this.delayMs);
      return;
    }
    this._firstChangeAt = Date.now();
    this._resetTimer(this.delayMs);
  }

  _resetTimer(ms) {
    if (this._timer) clearTimeout(this._timer);
    const cap = Math.max(this.delayMs, Math.min(this.maxDelayMs, this.maxDelayMs));
    const effective = Math.min(ms, cap);
    this._timer = setTimeout(() => this.flush(), effective);
    if (typeof this._timer.unref === 'function') this._timer.unref();
  }

  /**
   * اكتب الآن (flush) — يستدعى عند الإغلاق لتجنّب فقد البيانات.
   */
  flush() {
    if (this._timer) { clearTimeout(this._timer); this._timer = null; }
    if (!this._pendingSnapshot) return;
    try {
      const dir = path.dirname(this.filePath);
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(this.filePath, JSON.stringify(this._pendingSnapshot, null, 2));
      this._lastFlushAt = Date.now();
    } catch (e) {
      try { /* eslint-disable-next-line no-console */ console.warn('indexWriteThrottle flush failed:', e && e.message); } catch (_) {}
    } finally {
      this._pendingSnapshot = null;
      this._firstChangeAt = 0;
    }
  }

  lastFlushAt() {
    return this._lastFlushAt;
  }
}

module.exports = { IndexWriteThrottle };
