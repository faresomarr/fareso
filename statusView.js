'use strict';

function normalizePhone(value) {
  return String(value || '').replace(/\D/g, '');
}

function normalizeWhatsAppJid(jid) {
  const raw = String(jid || '').trim();
  if (!raw) return '';

  const cleaned = raw.replace(/[\u200e\u200f\u202a-\u202e\s]/g, '');
  const withoutDevice = cleaned
    .replace(/@c\.us$/i, '@s.whatsapp.net')
    .replace(/:\d+(?=@)/g, '');

  if (!withoutDevice) return '';
  if (withoutDevice === 'status@broadcast') return withoutDevice;

  if (/^[^@]+@(?:s\.whatsapp\.net|g\.us|broadcast|newsletter|lid)$/i.test(withoutDevice)) {
    return withoutDevice;
  }

  if (/^\d+$/.test(withoutDevice)) {
    return `${withoutDevice}@s.whatsapp.net`;
  }

  const localPart = withoutDevice.split('@')[0] || '';
  const numericLocalPart = localPart.split(':')[0] || '';
  if (/^\d+$/.test(localPart)) return `${localPart}@s.whatsapp.net`;
  if (/^\d+$/.test(numericLocalPart)) return `${numericLocalPart}@s.whatsapp.net`;

  return withoutDevice;
}

function normalizeStatusParticipantJid(jid) {
  const normalized = normalizeWhatsAppJid(jid);
  if (!normalized || normalized === 'status@broadcast' || normalized.endsWith('@g.us')) {
    return '';
  }

  if (normalized.endsWith('@s.whatsapp.net')) {
    return normalized;
  }

  const numericId = normalizePhone(normalized);
  if (numericId) {
    return `${numericId}@s.whatsapp.net`;
  }

  return normalized;
}

function unwrapMessageContent(message) {
  let current = message || {};
  while (current) {
    if (current.ephemeralMessage?.message) {
      current = current.ephemeralMessage.message;
      continue;
    }
    if (current.viewOnceMessage?.message) {
      current = current.viewOnceMessage.message;
      continue;
    }
    if (current.viewOnceMessageV2?.message) {
      current = current.viewOnceMessageV2.message;
      continue;
    }
    if (current.viewOnceMessageV2Extension?.message) {
      current = current.viewOnceMessageV2Extension.message;
      continue;
    }
    if (current.documentWithCaptionMessage?.message) {
      current = current.documentWithCaptionMessage.message;
      continue;
    }
    break;
  }
  return current || {};
}

function looksLikePersonalJid(value) {
  const normalized = normalizeStatusParticipantJid(value);
  return Boolean(normalized);
}

function collectCandidateParticipants(node, bucket, depth = 0, seen = new Set()) {
  if (!node || depth > 8) return;
  if (typeof node === 'string') {
    const normalized = normalizeStatusParticipantJid(node);
    if (normalized) bucket.add(normalized);
    return;
  }

  if (typeof node !== 'object') return;
  if (seen.has(node)) return;
  seen.add(node);

  if (Array.isArray(node)) {
    for (const item of node) collectCandidateParticipants(item, bucket, depth + 1, seen);
    return;
  }

  const hotKeys = [
    'participant',
    'remoteJid',
    'from',
    'to',
    'author',
    'sender',
    'userJid',
    'senderJid',
    'ownerJid',
    'chatId',
    'broadcastParticipant',
    'statusSourceType',
    'statusJidList'
  ];

  for (const key of hotKeys) {
    if (!(key in node)) continue;
    const value = node[key];
    if (Array.isArray(value)) {
      for (const item of value) {
        const normalized = normalizeStatusParticipantJid(item);
        if (normalized) bucket.add(normalized);
      }
    } else if (typeof value === 'string') {
      const normalized = normalizeStatusParticipantJid(value);
      if (normalized) bucket.add(normalized);
    }
  }

  for (const [key, value] of Object.entries(node)) {
    if (typeof value === 'string') {
      if (/participant|author|sender|jid|remote/i.test(key) || looksLikePersonalJid(value)) {
        const normalized = normalizeStatusParticipantJid(value);
        if (normalized) bucket.add(normalized);
      }
      continue;
    }
    if (value && typeof value === 'object') {
      collectCandidateParticipants(value, bucket, depth + 1, seen);
    }
  }
}

function collectCandidateMessageIds(msg, content) {
  const candidates = [
    msg?.key?.id,
    msg?.message?.messageContextInfo?.stanzaId,
    content?.messageContextInfo?.stanzaId,
    content?.extendedTextMessage?.contextInfo?.stanzaId,
    content?.imageMessage?.contextInfo?.stanzaId,
    content?.videoMessage?.contextInfo?.stanzaId,
    content?.documentMessage?.contextInfo?.stanzaId,
    content?.protocolMessage?.key?.id,
    content?.reactionMessage?.key?.id
  ];

  const nested = [msg, msg?.message, content];
  for (const node of nested) {
    if (!node || typeof node !== 'object') continue;
    const queue = [node];
    const seen = new Set();
    while (queue.length) {
      const current = queue.shift();
      if (!current || typeof current !== 'object' || seen.has(current)) continue;
      seen.add(current);
      if (typeof current.id === 'string') candidates.push(current.id);
      if (typeof current.stanzaId === 'string') candidates.push(current.stanzaId);
      for (const value of Object.values(current)) {
        if (value && typeof value === 'object') queue.push(value);
      }
    }
  }

  return candidates
    .map((item) => String(item || '').trim())
    .filter(Boolean);
}

function resolveStatusContext(msg) {
  const content = unwrapMessageContent(msg?.message);
  const participants = new Set();

  const priorityCandidates = [
    msg?.key?.participant,
    msg?.participant,
    msg?.message?.messageContextInfo?.participant,
    content?.messageContextInfo?.participant,
    content?.extendedTextMessage?.contextInfo?.participant,
    content?.imageMessage?.contextInfo?.participant,
    content?.videoMessage?.contextInfo?.participant,
    content?.documentMessage?.contextInfo?.participant,
    content?.reactionMessage?.key?.participant,
    content?.protocolMessage?.key?.participant,
    msg?.pushName,
    msg?.broadcastParticipant
  ];

  for (const candidate of priorityCandidates) {
    const normalized = normalizeStatusParticipantJid(candidate);
    if (normalized) participants.add(normalized);
  }

  collectCandidateParticipants(msg, participants);
  collectCandidateParticipants(content, participants);

  const ids = collectCandidateMessageIds(msg, content);
  const contentKeys = Object.keys(content || {});
  const statusContentKeys = contentKeys.filter(
    (key) => !['messageContextInfo', 'protocolMessage', 'reactionMessage', 'senderKeyDistributionMessage'].includes(key)
  );

  return {
    participant: Array.from(participants)[0] || '',
    participantCandidates: Array.from(participants),
    messageId: ids[0] || '',
    messageIdCandidates: ids,
    hasStatusContent: statusContentKeys.length > 0,
    kind: statusContentKeys[0] || ''
  };
}

function buildStatusReadKeyCandidates(msg, participant = '', messageId = '') {
  const normalizedParticipant = normalizeStatusParticipantJid(participant || msg?.key?.participant || msg?.participant || '');
  const finalMessageId = String(messageId || msg?.key?.id || '').trim();
  const originalRemoteJid = normalizeWhatsAppJid(msg?.key?.remoteJid || '');

  const candidates = [
    {
      remoteJid: 'status@broadcast',
      id: finalMessageId,
      participant: normalizedParticipant,
      fromMe: false
    },
    {
      remoteJid: normalizedParticipant,
      id: finalMessageId,
      participant: normalizedParticipant,
      fromMe: false
    },
    {
      ...(msg?.key || {}),
      remoteJid: 'status@broadcast',
      id: finalMessageId,
      participant: normalizedParticipant,
      fromMe: false
    },
    {
      ...(msg?.key || {}),
      remoteJid: normalizedParticipant || originalRemoteJid,
      id: finalMessageId,
      participant: normalizedParticipant,
      fromMe: false
    }
  ];

  const seen = new Set();
  return candidates.filter((item) => {
    const remoteJid = normalizeWhatsAppJid(item?.remoteJid || '');
    const id = String(item?.id || '').trim();
    const participantValue = normalizeStatusParticipantJid(item?.participant || '');
    if (!remoteJid || !id) return false;
    const signature = `${remoteJid}::${id}::${participantValue}`;
    if (seen.has(signature)) return false;
    seen.add(signature);
    item.remoteJid = remoteJid;
    item.id = id;
    item.participant = participantValue;
    item.fromMe = false;
    return true;
  });
}

async function markStatusAsViewed(sock, msg, options = {}) {
  const logger = options.logger || console;
  const context = resolveStatusContext(msg);
  const participant = normalizeStatusParticipantJid(options.participant || context.participant);
  const messageId = String(options.messageId || context.messageId || msg?.key?.id || '').trim();

  if (!sock || !participant || !messageId) {
    return {
      ok: false,
      reason: !participant ? 'missing-participant' : 'missing-message-id',
      participant,
      messageId,
      context
    };
  }

  const keyCandidates = buildStatusReadKeyCandidates(msg, participant, messageId);
  const readMessageAttempts = keyCandidates.map((key, index) => ({
    name: `readMessages.${index + 1}`,
    run: async () => {
      if (typeof sock.readMessages !== 'function') throw new Error('readMessages unavailable');
      await sock.readMessages([key]);
    }
  }));

  const sendReceiptAttempts = [
    {
      name: 'sendReceipt.read.status-broadcast',
      run: async () => {
        if (typeof sock.sendReceipt !== 'function') throw new Error('sendReceipt unavailable');
        await sock.sendReceipt('status@broadcast', participant, [messageId], 'read');
      }
    },
    {
      name: 'sendReceipt.read.direct-participant',
      run: async () => {
        if (typeof sock.sendReceipt !== 'function') throw new Error('sendReceipt unavailable');
        await sock.sendReceipt(participant, undefined, [messageId], 'read');
      }
    }
  ];

  const attempts = options.preferExplicitReadReceipt
    ? [...sendReceiptAttempts, ...readMessageAttempts]
    : [...readMessageAttempts, ...sendReceiptAttempts];

  let lastError = null;
  for (const attempt of attempts) {
    try {
      await attempt.run();
      return { ok: true, method: attempt.name, participant, messageId, context };
    } catch (error) {
      lastError = error;
    }
  }

  if (logger && typeof logger.debug === 'function') {
    logger.debug(`[statusView] failed for ${participant}: ${lastError?.message || 'unknown error'}`);
  }

  return {
    ok: false,
    reason: 'all-attempts-failed',
    error: lastError,
    participant,
    messageId,
    context
  };
}

module.exports = {
  normalizeWhatsAppJid,
  normalizeStatusParticipantJid,
  unwrapMessageContent,
  resolveStatusContext,
  buildStatusReadKeyCandidates,
  markStatusAsViewed
};
