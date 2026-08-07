'use strict';

const { markStatusAsViewed, resolveStatusContext, normalizeStatusParticipantJid } = require('./statusView');
const { sendStatusReaction } = require('./statusReact');

// وظيفة التأخير البشري
function randomDelay(min, max) {
  return new Promise((resolve) => setTimeout(resolve, Math.floor(Math.random() * (max - min + 1) + min)));
}

async function externalStatusHandler(sock, msg, context = {}) {
  // التأكد من أن الرسالة هي حالة (Status)
  if (msg.key.remoteJid !== 'status@broadcast') return false;

  const logger = context.logger || console;
  const resolved = resolveStatusContext(msg);
  const participant = normalizeStatusParticipantJid(context.participant || resolved.participant);
  const messageId = String(context.messageId || resolved.messageId || msg?.key?.id || '').trim();

  if (!participant || !messageId) return false;

  try {
    // 1. الحل الجذري: تأخير عشوائي لمحاكاة قراءة الحالة (7-15 ثانية)
    await randomDelay(1000, 2000);

    // 2. تحديث الحضور لجعل البوت يبدو "متصلاً" للطرف الآخر
    await sock.sendPresenceUpdate('available', msg.key.remoteJid);
    await randomDelay(500, 1000);

    // 3. المشاهدة (Read Status)
    const readResult = await markStatusAsViewed(sock, msg, { logger, participant, messageId });
    
    if (readResult.ok) {
      console.log('تمت المشاهدة بنجاح (بشكل بشري)');
    }

    // 4. الإعجاب (Reaction)
    const reactResult = await sendStatusReaction(sock, msg, {
      logger,
      participant,
      messageId,
      reactionEmoji: '❤️'
    });

    if (reactResult.ok) {
      console.log('تمت المشاهدة والإعجاب بنجاح');
    }

    return true;
  } catch (err) {
    console.error('فشل في المعالجة:', err);
    return false;
  }
}

module.exports = externalStatusHandler;
