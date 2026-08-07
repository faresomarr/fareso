const FALLBACK_TELEGRAM_BOT_LINK = 'https://t.me/Faresw_bot';

async function pairCommand(sock, chatId) {
    const telegramBotLink = String(
        process.env.DEFAULT_BOT_LINK ||
        process.env.TELEGRAM_BOT_LINK ||
        FALLBACK_TELEGRAM_BOT_LINK
    ).trim() || FALLBACK_TELEGRAM_BOT_LINK;

    await sock.sendMessage(chatId, {
        text: `❌ تم إيقاف الربط من داخل واتساب.

📱 ربط الأرقام متاح فقط من داخل بوت تيليجرام.
🤖 رابط البوت: ${telegramBotLink}`,
        contextInfo: {
            forwardingScore: 1,
            isForwarded: true,
            forwardedNewsletterMessageInfo: {
                newsletterJid: '120363161513685998@newsletter',
                newsletterName: 'KnightBot MD',
                serverMessageId: -1
            }
        }
    });
}

module.exports = pairCommand;
