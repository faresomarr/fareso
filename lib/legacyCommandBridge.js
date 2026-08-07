const fs = require('fs');
const path = require('path');

const legacyHandlers = require('../main');
const legacySettings = require('../settings');

function safeRequire(modulePath) {
    try {
        return require(modulePath);
    } catch (error) {
        console.error(`[legacy-command-bridge] failed to require ${modulePath}:`, error.message || error);
        return null;
    }
}

const extraCommandHandlers = {
    pair: safeRequire('../commands/pair'),
    gif: safeRequire('../commands/gif'),
    'sticker-alt': safeRequire('../commands/sticker-alt')
};

const legacyDispatchQueues = new Map();

function normalizePhone(phone) {
    return String(phone || '').replace(/\D/g, '');
}

function extractTextFromMessage(msg = {}) {
    return String(
        msg?.message?.conversation ||
        msg?.message?.extendedTextMessage?.text ||
        msg?.message?.imageMessage?.caption ||
        msg?.message?.videoMessage?.caption ||
        msg?.message?.buttonsResponseMessage?.selectedButtonId ||
        ''
    ).trim();
}

function withLegacyDispatchLock(phoneNumber, task) {
    const queueKey = normalizePhone(phoneNumber) || 'global';
    const previous = legacyDispatchQueues.get(queueKey) || Promise.resolve();
    const execution = previous.then(() => task());
    const tracked = execution.catch(() => undefined);
    legacyDispatchQueues.set(queueKey, tracked);
    return execution.finally(() => {
        const current = legacyDispatchQueues.get(queueKey);
        if (current === tracked || !current) {
            legacyDispatchQueues.delete(queueKey);
        }
    });
}

async function withScopedLegacySettings(phoneNumber, task) {
    const normalizedPhone = normalizePhone(phoneNumber);
    const runWithContext = typeof legacySettings.__runWithContext === 'function'
        ? legacySettings.__runWithContext.bind(legacySettings)
        : async (_context, scopedTask) => scopedTask();

    const context = {
        ownerNumber: normalizedPhone || legacySettings.ownerNumber,
        botOwner: String(legacySettings.botOwner || normalizedPhone || '').trim() || normalizedPhone || legacySettings.ownerNumber
    };

    return runWithContext(context, task);
}

async function dispatchExtraCommandIfNeeded(sock, phoneNumber, msg) {
    const text = extractTextFromMessage(msg);
    if (!text.startsWith('.')) return false;

    const [rawCommand, ...rest] = text.split(/\s+/);
    const command = rawCommand.replace(/^\./, '').toLowerCase();
    const chatId = msg?.key?.remoteJid;

    if (!chatId) return false;

    if (command === 'pair' && typeof extraCommandHandlers.pair === 'function') {
        await withScopedLegacySettings(phoneNumber, async () => {
            await extraCommandHandlers.pair(sock, chatId, msg, rest.join(' '));
        });
        return true;
    }

    if (command === 'gif' && typeof extraCommandHandlers.gif === 'function') {
        await withScopedLegacySettings(phoneNumber, async () => {
            await extraCommandHandlers.gif(sock, chatId, rest.join(' '));
        });
        return true;
    }

    if (['stickeralt', 'sticker-alt', 's2', 'sticker2'].includes(command) && typeof extraCommandHandlers['sticker-alt'] === 'function') {
        await withScopedLegacySettings(phoneNumber, async () => {
            await extraCommandHandlers['sticker-alt'](sock, chatId, msg);
        });
        return true;
    }

    return false;
}

async function dispatchLegacyMessage(sock, phoneNumber, msg) {
    return withLegacyDispatchLock(phoneNumber, async () => {
        const handledExtraCommand = await dispatchExtraCommandIfNeeded(sock, phoneNumber, msg);
        if (handledExtraCommand) {
            return true;
        }

        await withScopedLegacySettings(phoneNumber, async () => {
            await legacyHandlers.handleMessages(sock, {
                messages: [msg],
                type: 'notify'
            }, false);
        });

        return true;
    });
}

async function dispatchLegacyGroupParticipantsUpdate(sock, phoneNumber, update) {
    return withLegacyDispatchLock(phoneNumber, async () => {
        await withScopedLegacySettings(phoneNumber, async () => {
            await legacyHandlers.handleGroupParticipantUpdate(sock, update);
        });
        return true;
    });
}

function preloadDirectoryModules(directoryPath, skipFiles = new Set()) {
    if (!fs.existsSync(directoryPath)) return [];

    const loaded = [];
    for (const entry of fs.readdirSync(directoryPath)) {
        if (!entry.endsWith('.js')) continue;
        if (skipFiles.has(entry)) continue;

        const modulePath = path.join(directoryPath, entry);
        try {
            require(modulePath);
            loaded.push(modulePath);
        } catch (error) {
            console.error(`[legacy-command-bridge] preload failed for ${modulePath}:`, error.message || error);
        }
    }

    return loaded;
}

function preloadLegacyProjectModules() {
    const projectRoot = path.join(__dirname, '..');
    const loadedCommands = preloadDirectoryModules(path.join(projectRoot, 'commands'));
    const loadedLibs = preloadDirectoryModules(path.join(projectRoot, 'lib'), new Set(['legacyCommandBridge.js']));
    return {
        commands: loadedCommands,
        libs: loadedLibs
    };
}

module.exports = {
    dispatchLegacyMessage,
    dispatchLegacyGroupParticipantsUpdate,
    preloadLegacyProjectModules,
    extractTextFromMessage
};
