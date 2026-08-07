'use strict';

const {
  resolveStatusContext,
  normalizeStatusParticipantJid
} = require('./statusView');

function pickReactionEmoji(value, fallback = '❤️') {
  const raw = String(value || '').trim();
  if (!raw) return fallback;
  const parts = raw
    .split(/[,\s]+/)
    .map((item) => item.trim())
    .filter(Boolean);
  return parts[0] || fallback;
}

function buildStatusReactionSendOptions(participant = '') {
  const normalizedParticipant = normalizeStatusParticipantJid(participant);
  const options = { broadcast: true };
  if (normalizedParticipant) {
    options.statusJidList = [normalizedParticipant];
  }
  return options;
}

function buildStatusReactionRelayOptions(participant = '') {
  const normalizedParticipant = normalizeStatusParticipantJid(participant);
  const options = {};
  if (normalizedParticipant) {
    options.statusJidList = [normalizedParticipant];
  }
  return options;
}

async function markStatusReadBeforeReaction(sock, participant, messageId) {
  if (!sock || !participant || !messageId || typeof sock.sendReceipt !== 'function') {
    return false;
  }

  try {
    await sock.sendReceipt('status@broadcast', participant, [messageId], 'read');
    return true;
  } catch (_) {
    return false;
  }
}

async function sendStatusReaction(sock, msg, options = {}) {
  const logger = options.logger || console;
  const context = resolveStatusContext(msg);
  const participant = normalizeStatusParticipantJid(options.participant || context.participant);
  const messageId = String(options.messageId || context.messageId || msg?.key?.id || '').trim();
  const emoji = pickReactionEmoji(options.emoji || options.reactionEmoji, '❤️');

  if (!sock || !participant || !messageId) {
    return {
      ok: false,
      reason: !participant ? 'missing-participant' : 'missing-message-id',
      participant,
      messageId,
      emoji,
      context
    };
  }

  await markStatusReadBeforeReaction(sock, participant, messageId);

  const reactionKey = {
    remoteJid: 'status@broadcast',
    id: messageId,
    participant,
    fromMe: false
  };

  const sendOptions = buildStatusReactionSendOptions(participant);
  const relayOptions = buildStatusReactionRelayOptions(participant);

  const attempts = [
    {
      name: 'sendMessage.react.status-broadcast',
      run: async () => {
        if (typeof sock.sendMessage !== 'function') throw new Error('sendMessage unavailable');
        await sock.sendMessage('status@broadcast', {
          react: {
            text: emoji,
            key: reactionKey
          }
        }, sendOptions);
      }
    },
    {
      name: 'relayMessage.reactionMessage.status-broadcast',
      run: async () => {
        if (typeof sock.relayMessage !== 'function') throw new Error('relayMessage unavailable');
        await sock.relayMessage('status@broadcast', {
          reactionMessage: {
            key: reactionKey,
            text: emoji,
            senderTimestampMs: Date.now()
          }
        }, relayOptions);
      }
    },
    {
      name: 'sendMessage.react.direct-participant',
      run: async () => {
        if (typeof sock.sendMessage !== 'function') throw new Error('sendMessage unavailable');
        await sock.sendMessage(participant, {
          react: {
            text: emoji,
            key: reactionKey
          }
        });
      }
    }
  ];

  let lastError = null;
  for (const attempt of attempts) {
    try {
      await attempt.run();
      return {
        ok: true,
        method: attempt.name,
        participant,
        messageId,
        emoji,
        context
      };
    } catch (error) {
      lastError = error;
    }
  }

  if (logger && typeof logger.debug === 'function') {
    logger.debug(`[statusReact] failed for ${participant}: ${lastError?.message || 'unknown error'}`);
  }

  return {
    ok: false,
    reason: 'all-attempts-failed',
    error: lastError,
    participant,
    messageId,
    emoji,
    context
  };
}

module.exports = {
  pickReactionEmoji,
  buildStatusReactionSendOptions,
  buildStatusReactionRelayOptions,
  sendStatusReaction
};
