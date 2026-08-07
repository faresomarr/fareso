const { listMongoSessionJsonFiles, clearMongoSessionAuthFiles, deleteMongoSessionSnapshot } = require('../mongo-auth');
const isOwnerOrSudo = require('../lib/isOwner');

const channelInfo = {
    contextInfo: {
        forwardingScore: 999,
        isForwarded: true,
        forwardedNewsletterMessageInfo: {
            newsletterJid: '120363161513685998@newsletter',
            newsletterName: 'KnightBot MD',
            serverMessageId: -1
        }
    }
};

function normalizePhone(value = '') {
    return String(value || '').replace(/\D/g, '').trim();
}

function resolveCurrentSessionPhone(sock) {
    const candidates = [
        sock?.user?.id,
        sock?.authState?.creds?.me?.id,
        sock?.user?.lid,
        sock?.authState?.creds?.me?.lid
    ];

    for (const candidate of candidates) {
        const phone = normalizePhone(candidate);
        if (phone) return phone;
    }

    return '';
}

async function clearSessionCommand(sock, chatId, msg) {
    try {
        const senderId = msg.key.participant || msg.key.remoteJid;
        const isOwner = await isOwnerOrSudo(senderId, sock, chatId);

        if (!msg.key.fromMe && !isOwner) {
            await sock.sendMessage(chatId, {
                text: '❌ This command can only be used by the owner!',
                ...channelInfo
            });
            return;
        }

        const phone = resolveCurrentSessionPhone(sock);
        if (!phone) {
            await sock.sendMessage(chatId, {
                text: '❌ تعذر تحديد رقم الجلسة الحالية من الاتصال النشط.',
                ...channelInfo
            });
            return;
        }

        await sock.sendMessage(chatId, {
            text: `🔍 جاري تنظيف ملفات جلسة MongoDB للرقم ${phone}...`,
            ...channelInfo
        });

        const files = listMongoSessionJsonFiles(phone);
        const appStateSyncCount = files.filter((file) => file.startsWith('app-state-sync-')).length;
        const preKeyCount = files.filter((file) => file.startsWith('pre-key-')).length;
        const senderKeyCount = files.filter((file) => file.startsWith('sender-key-')).length;
        const signalSessionCount = files.filter((file) => file.startsWith('session-')).length;
        const removed = clearMongoSessionAuthFiles(phone, { preserveSessionMeta: false, preservePhoneSettings: false, ownerId: '' });
        const deletedSnapshot = await deleteMongoSessionSnapshot(phone);

        const message = `✅ تم حذف جلسة MongoDB نهائياً!\n\n` +
            `📱 Target session: ${phone}\n` +
            `📊 Statistics:\n` +
            `• Total auth records cleared: ${removed}\n` +
            `• App state sync records found: ${appStateSyncCount}\n` +
            `• Pre-key records found: ${preKeyCount}\n` +
            `• Sender-key records found: ${senderKeyCount}\n` +
            `• Signal session records found: ${signalSessionCount}\n` +
            `• Remote snapshot deleted: ${deletedSnapshot ? 'yes' : 'no / already missing'}\n` +
            `• Storage mode: MongoDB only`;

        await sock.sendMessage(chatId, {
            text: message,
            ...channelInfo
        });
    } catch (error) {
        console.error('Error in clearsession command:', error);
        await sock.sendMessage(chatId, {
            text: '❌ Failed to clear MongoDB session records!',
            ...channelInfo
        });
    }
}

module.exports = clearSessionCommand;
