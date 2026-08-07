// lib/sessionManager.js
// ============================================================
//  Multi-Session Manager — عزل الأرقام في مجلدات مستقلة
// ============================================================
//  السبب الجذري لمشكلة "ربط رقم يفصل الرقم السابق" هو وجود
//  Singleton (socket/qr/creds) واحد فقط. هنا نعزل كل رقم في
//  كائن مستقل داخل Map بمفتاح الرقم:
//
//   • مسار جلسة خاص:   sessions/<phone>/
//   • حالته الخاصة (state/qr/registered/ownerId/...)
//   • مؤقت إعادة اتصال مستقل
//   • دورة حياة معزولة (logout/disconnect/reconnect)
// ============================================================

'use strict';

const fs = require('fs');
const path = require('path');
const { EventEmitter } = require('events');
const { SESSION_ROOT } = require('./storagePaths');


function ensureDir(dirPath) {
    if (!fs.existsSync(dirPath)) fs.mkdirSync(dirPath, { recursive: true });
    return dirPath;
}

function normalizePhone(value = '') {
    return String(value || '').replace(/\D/g, '').trim();
}

function getPhoneSessionDir(phone) {
    const normalized = normalizePhone(phone);
    return ensureDir(path.join(SESSION_ROOT, normalized || '__default__'));
}

const SESSION_INDEX_FILE = path.join(SESSION_ROOT, 'index.json');

function readIndex() {
    try {
        const raw = fs.readFileSync(SESSION_INDEX_FILE, 'utf8');
        const data = JSON.parse(raw);
        return (data && typeof data === 'object' && data.sessions) ? data : { sessions: {} };
    } catch (_) { return { sessions: {} }; }
}

function writeIndex(index) {
    ensureDir(SESSION_ROOT);
    fs.writeFileSync(SESSION_INDEX_FILE, JSON.stringify(index, null, 2));
}

function listPersistedPhones() {
    const fromIndex = Object.keys(readIndex().sessions || {});
    let onDisk = [];
    try {
        onDisk = fs.readdirSync(SESSION_ROOT, { withFileTypes: true })
            .filter((e) => e.isDirectory() && /^\d+/.test(e.name))
            .map((e) => e.name);
    } catch (_) {}
    return Array.from(new Set([...fromIndex, ...onDisk].map(normalizePhone))).filter(Boolean);
}

const expectedPhones = new Map();      // phone -> { phone, registered, ownerId, updatedAt }
const sessionBus = new EventEmitter();
sessionBus.setMaxListeners(0);

function markExpected(phone, metadata = {}) {
    const normalized = normalizePhone(phone);
    if (!normalized) return null;
    const existing = expectedPhones.get(normalized) || {};
    const merged = {
        ...existing,
        ...metadata,
        phone: normalized,
        updatedAt: new Date().toISOString()
    };
    expectedPhones.set(normalized, merged);

    const index = readIndex();
    index.sessions = index.sessions || {};
    index.sessions[normalized] = {
        ...(index.sessions[normalized] || {}),
        ...merged
    };
    writeIndex(index);

    sessionBus.emit('expected:upsert', normalized, merged);
    return merged;
}

function unmarkExpected(phone) {
    const normalized = normalizePhone(phone);
    if (!normalized) return false;
    const existed = expectedPhones.delete(normalized);
    const index = readIndex();
    if (index.sessions && index.sessions[normalized]) {
        index.sessions[normalized] = {
            ...index.sessions[normalized],
            registered: false,
            updatedAt: new Date().toISOString()
        };
        writeIndex(index);
    }
    sessionBus.emit('expected:remove', normalized);
    return existed;
}

function setActive(phone, metadata = {}) {
    const normalized = normalizePhone(phone);
    if (!normalized) return;
    markExpected(normalized, { ...metadata, lastConnectedAt: new Date().toISOString() });
    sessionBus.emit('active:set', normalized, metadata);
}

function clearActive(phone) {
    const normalized = normalizePhone(phone);
    if (!normalized) return;
    sessionBus.emit('active:clear', normalized);
}

function deletePhoneSessionFolder(phone) {
    const normalized = normalizePhone(phone);
    if (!normalized) return false;
    const dir = path.join(SESSION_ROOT, normalized);
    try { fs.rmSync(dir, { recursive: true, force: true }); } catch (_) {}
    unmarkExpected(normalized);
    sessionBus.emit('folder:deleted', normalized);
    return true;
}

module.exports = {
    SESSION_ROOT,
    normalizePhone,
    getPhoneSessionDir,
    listPersistedPhones,
    readIndex,
    writeIndex,
    markExpected,
    unmarkExpected,
    setActive,
    clearActive,
    deletePhoneSessionFolder,
    bus: sessionBus
};
