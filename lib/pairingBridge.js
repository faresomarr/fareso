// lib/pairingBridge.js
// ============================================================
//  Pairing Bridge — مُعدّل لضمان عزل الأرقام (Multi-Session)
// ============================================================
//  المنطق الأوّلي كان يحتفظ بـ primarySocket واحد (آخر سوكيت
//  مُمرَّر)، وهذا يعني أن ربط رقم جديد يستبدل المرجع — وهو
//  بالضبط الفصل الذي يشتكي منه المستخدم. هنا:
//
//   • لا يوجد "primarySocket": أي عملية تطلب سوكيت لرقم معيّن
//     تحصل عليه فقط، وأي رقم آخر يتأثر بصفر.
//   • getSocket(phone) صار يرفض افتراض وجود سوكيت افتراضي ويطلب
//     رقمًا صريحًا؛ أما getAnySocket() فيبقى للأغراض العامة فقط.
//   • setSocket يرفض التسجيل بدون رقم صريح.
//   • عند تكرار setSocket لنفس الرقم، نُغلق السوكيت السابق بهدوء
//     (لا نُلغي سوكيتات الأرقام الأخرى).
// ============================================================

const { EventEmitter } = require('events');

const emitter = new EventEmitter();
emitter.setMaxListeners(0);

const socketMap = new Map();   // phone -> socket (مفتاح = الرقم نفسه)
const metaMap = new Map();      // phone -> metadata
let connectionState = 'idle';
let lastUpdatedAt = new Date().toISOString();

function touch() { lastUpdatedAt = new Date().toISOString(); }
function normalizePhone(phone = '') {
    return String(phone || '').replace(/\D/g, '').trim();
}

function setConnectionState(state) {
    connectionState = state || 'unknown';
    touch();
    return connectionState;
}
function getConnectionState() { return connectionState; }

function setSocket(phoneOrSocket, maybeSocket, metadata = {}) {
    const hasExplicitPhone = typeof phoneOrSocket === 'string' || typeof phoneOrSocket === 'number';
    const normalizedPhone = hasExplicitPhone ? normalizePhone(phoneOrSocket) : '';

    // REFUSAL: لا نقبل التسجيل بدون رقم — يمنع استبدال سوكيت رقم نشط بآخر.
    if (!hasExplicitPhone || !normalizedPhone) {
        console.warn('[pairingBridge] setSocket مرفوض بدون رقم صريح — كل سوكيت ينتمي لرقم.');
        return null;
    }

    const socket = maybeSocket || null;
    const key = normalizedPhone;

    if (!socket) {
        const existed = socketMap.delete(key);
        metaMap.delete(key);
        if (existed) {
            setImmediate(() => { try { emitter.emit('phone.released', normalizedPhone); } catch (_) {} });
        }
        if (socketMap.size === 0) setConnectionState('idle');
        touch();
        return null;
    }

    // إذا كان هناك سوكيت سابق لنفس الرقم فقط، نُغلقه بهدوء (لا يمس الأرقام الأخرى).
    const previous = socketMap.get(key);
    if (previous && previous !== socket) {
        try { previous.ws?.close?.(); } catch (_) {}
        try { previous.end?.(); } catch (_) {}
    }

    socketMap.set(key, socket);
    metaMap.set(key, {
        ...(metaMap.get(key) || {}),
        ...(metadata || {}),
        phone: normalizedPhone,
        registered: metadata?.registered !== false,
    });

    setConnectionState('open');
    touch();

    setImmediate(() => {
        try { emitter.emit('phone.activated', normalizedPhone, socket, metaMap.get(key) || {}); } catch (_) {}
    });
    return socket;
}

function releaseSocket(phone = '') {
    const normalizedPhone = normalizePhone(phone);
    if (!normalizedPhone) return false;
    const existed = socketMap.delete(normalizedPhone);
    metaMap.delete(normalizedPhone);
    if (socketMap.size === 0) setConnectionState('idle');
    touch();
    if (existed) {
        setImmediate(() => { try { emitter.emit('phone.released', normalizedPhone); } catch (_) {} });
    }
    return existed;
}

function getSocket(phone = '') {
    const normalizedPhone = normalizePhone(phone);
    if (!normalizedPhone) return null;
    return socketMap.get(normalizedPhone) || null;
}

function getAnySocket() {
    // فقط للأغراض العامة (status panel). لا تستخدمه لتوجيه رسالة لرقم محدد.
    return socketMap.values().next().value || null;
}

function getPhoneMeta(phone = '') {
    const normalizedPhone = normalizePhone(phone);
    if (!normalizedPhone) return null;
    return metaMap.get(normalizedPhone) || null;
}

function listActivePhones() {
    return Array.from(socketMap.keys());
}

function getBridgeState() {
    return {
        connectionState,
        socketCount: socketMap.size,
        activePhones: listActivePhones(),
        lastUpdatedAt,
        socketMapSize: socketMap.size,
    };
}

async function waitForPhone(phone, { timeoutMs = 6000 } = {}) {
    const normalizedPhone = normalizePhone(phone);
    if (!normalizedPhone) return null;
    const existing = socketMap.get(normalizedPhone);
    if (existing) return existing;
    return new Promise((resolve) => {
        const onActivated = (activatedPhone, socket) => {
            if (normalizePhone(activatedPhone) === normalizedPhone) {
                cleanup();
                resolve(socket);
            }
        };
        const timer = setTimeout(() => {
            cleanup();
            resolve(socketMap.get(normalizedPhone) || null);
        }, Math.max(250, Number(timeoutMs) || 6000));
        if (typeof timer.unref === 'function') timer.unref();
        const cleanup = () => {
            emitter.off('phone.activated', onActivated);
            clearTimeout(timer);
        };
        emitter.on('phone.activated', onActivated);
    });
}

const pairingBridge = {
    setSocket, releaseSocket,
    getSocket, getAnySocket, getPhoneMeta,
    listActivePhones, getBridgeState,
    setConnectionState, getConnectionState,
    waitForPhone, emitter,
};

module.exports = {
    pairingBridge,
    setSocket, releaseSocket,
    getSocket, getAnySocket, getPhoneMeta,
    listActivePhones, getBridgeState,
    setConnectionState, getConnectionState,
    waitForPhone, emitter,
};
