'use strict';

function normalizeBasicJid(jid = '') {
    return String(jid || '').replace(/:\d+(?=@)/, '').trim();
}

function unwrapMessageContent(message) {
    let current = message || {};

    while (current?.ephemeralMessage?.message) {
        current = current.ephemeralMessage.message;
    }

    while (current?.viewOnceMessage?.message) {
        current = current.viewOnceMessage.message;
    }

    while (current?.viewOnceMessageV2?.message) {
        current = current.viewOnceMessageV2.message;
    }

    while (current?.viewOnceMessageV2Extension?.message) {
        current = current.viewOnceMessageV2Extension.message;
    }

    while (current?.documentWithCaptionMessage?.message) {
        current = current.documentWithCaptionMessage.message;
    }

    while (current?.editedMessage?.message) {
        current = current.editedMessage.message;
    }

    return current || {};
}

function extractStatusParticipant(msg = {}, extraCandidates = []) {
    const content = unwrapMessageContent(msg?.message);
    const candidates = [
        ...(Array.isArray(extraCandidates) ? extraCandidates : [extraCandidates]),
        msg?.participant,
        msg?.key?.participant,
        msg?.key?.remoteJid,
        msg?.message?.messageContextInfo?.participant,
        content?.messageContextInfo?.participant,
        content?.extendedTextMessage?.contextInfo?.participant,
        content?.imageMessage?.contextInfo?.participant,
        content?.videoMessage?.contextInfo?.participant,
        content?.documentMessage?.contextInfo?.participant,
        content?.reactionMessage?.key?.participant,
        content?.protocolMessage?.key?.participant
    ];

    for (const candidate of candidates) {
        const normalized = normalizeBasicJid(candidate);
        if (normalized && normalized !== 'status@broadcast') {
            return normalized;
        }
    }

    return '';
}

function buildStatusReactionKey(msg = {}, participant = '') {
    return {
        ...(msg?.key || {}),
        remoteJid: 'status@broadcast',
        participant,
        fromMe: false
    };
}

function buildStatusReactionSendOptions(participant = '') {
    const options = { broadcast: true };
    if (participant) {
        options.statusJidList = [participant];
        options.participant = participant;
    }
    return options;
}

async function sendRobustStatusReaction({ sock, msg, emoji, candidates = [], delayFn = null }) {
    if (!sock || !msg?.key?.id || !emoji) {
        return { ok: false, error: 'missing_input' };
    }

    const participant = extractStatusParticipant(msg, candidates);
    if (!participant) {
        return { ok: false, error: 'missing_participant' };
    }

    const reactionKey = buildStatusReactionKey(msg, participant);
    const sendOptions = buildStatusReactionSendOptions(participant);
    const attempts = [
        async () => {
            await sock.sendMessage('status@broadcast', {
                react: {
                    text: emoji,
                    key: reactionKey
                }
            }, sendOptions);
        },
        async () => {
            await sock.sendMessage('status@broadcast', {
                react: {
                    text: emoji,
                    key: {
                        ...reactionKey,
                        remoteJid: 'status@broadcast',
                        participant,
                        fromMe: false
                    }
                }
            }, sendOptions);
        },
        async () => {
            await sock.sendMessage('status@broadcast', {
                react: {
                    text: emoji,
                    key: {
                        id: msg.key.id,
                        remoteJid: 'status@broadcast',
                        participant,
                        fromMe: false
                    }
                }
            }, sendOptions);
        }
    ];

    let lastError = null;

    for (const attempt of attempts) {
        try {
            if (typeof delayFn === 'function') {
                await delayFn(150);
            }
            await attempt();
            return { ok: true, participant };
        } catch (error) {
            lastError = error;
        }
    }

    return { ok: false, error: lastError || 'unknown_error', participant };
}

module.exports = {
    normalizeBasicJid,
    sendRobustStatusReaction,
    extractStatusParticipant,
    unwrapMessageContent
};
