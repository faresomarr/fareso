// lib/ownerGuard.js
// ============================================================
//  Owner Guard لكل رقم مربوط
// ============================================================
//  كل رقم مربوط له مالك واحد (Telegram ID) تم تسجيله عند عملية
//  الربط الأولى. أي أمر خاص بالبوت على واتساب يستجيب فقط لمالك
//  الرقم الحالي، وأي شخص آخر يتجاهلُه تماماً (مع تجاهل الطباعة
//  لتخفيف الحمل على السجلات).
// ============================================================

'use strict';

const { normalizePhone } = require('./sessionManager');

/**
 * خريطة: phone -> { ownerId, ownerJid, updatedAt }
 * تُملأ في worker.js عند ربط الرقم من البوت، وتُقرأ هنا.
 */
const ownerRegistry = new Map();

function setOwnerForPhone(phone, ownerId, ownerJid = null) {
  const normalized = normalizePhone(phone);
  if (!normalized) return false;
  ownerRegistry.set(normalized, {
    ownerId: String(ownerId || '').trim(),
    ownerJid: (ownerJid ? String(ownerJid).trim() : null),
    updatedAt: new Date().toISOString(),
  });
  return true;
}

function clearOwnerForPhone(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized) return false;
  return ownerRegistry.delete(normalized);
}

function getOwnerForPhone(phone) {
  const normalized = normalizePhone(phone);
  return ownerRegistry.get(normalized) || null;
}

/**
 * يستخرج رقم الـ phone المرتبط بسوكيت معيّن من خلال الـ JID الأساسي.
 */
function phoneFromSocket(sock) {
  if (!sock) return null;
  const candidate = sock.user?.id || sock.authState?.creds?.me?.id || '';
  const cleaned = String(candidate || '').split(':')[0].split('@')[0].replace(/\D/g, '');
  return cleaned || null;
}

/**
 * يحدد إذا كان المُرسِل (JID) هو مالك الرقم الحالي للسوكيت.
 * قواعد القبول:
 *   - مطابقة JID كامل
 *   - مطابقة رقم نظيف
 *   - LID match في المجموعات
 *   - رقم الرقم نفسه (self-message)
 */
function isOwnerForThisBot(senderId, sock) {
  if (!senderId || !sock) return false;

  const phone = phoneFromSocket(sock);
  if (!phone) return false;
  const owner = getOwnerForPhone(phone);
  if (!owner) return false;

  const sender = String(senderId || '');
  const senderClean = sender.split(':')[0].split('@')[0];
  const senderLidNumeric = sender.includes('@lid') ? sender.split('@')[0].split(':')[0] : '';

  // 1) مالك الرقم المسجّل
  const ownerClean = String(owner.ownerId || '').replace(/\D/g, '');
  if (ownerClean && senderClean && ownerClean === senderClean) return true;

  // 2) JID مسجّل يدوياً
  if (owner.ownerJid && sender === owner.ownerJid) return true;

  // 3) الرقم هو نفسه مالك الرقم (self chat)
  const botUserClean = String(sock.user?.id || '').split(':')[0].split('@')[0];
  if (botUserClean && senderClean === botUserClean) return true;

  // 4) LID match
  const botLid = sock.user?.lid || '';
  const botLidNumeric = String(botLid || '').includes(':')
    ? String(botLid).split(':')[0]
    : (String(botLid || '').includes('@') ? String(botLid).split('@')[0] : String(botLid || ''));
  if (senderLidNumeric && botLidNumeric && senderLidNumeric === botLidNumeric) return true;

  return false;
}

module.exports = {
  setOwnerForPhone,
  clearOwnerForPhone,
  getOwnerForPhone,
  phoneFromSocket,
  isOwnerForThisBot,
};
