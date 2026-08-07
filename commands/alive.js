const settings = require('../settings');

async function aliveCommand(sock, chatId, message) {
    try {
        const aliveMessage = `*🤖 البوت يعمل بنجاح!*

` +
            `*الإصدار:* ${settings.version}
` +
            `*الحالة:* متصل
` +
            `*الوضع:* عام

` +
            `*✨ المميزات الأساسية:*
` +
            `• إدارة المجموعات
` +
            `• الحماية من الروابط
` +
            `• أوامر متنوعة
` +
            `• والمزيد...

` +
            `اكتب *.الأوامر* لعرض جميع الأوامر العربية`;

        await sock.sendMessage(chatId, { text: aliveMessage }, { quoted: message });
    } catch (error) {
        console.error('Error in alive command:', error);
        await sock.sendMessage(chatId, { text: 'البوت شغال بدون مشاكل.' }, { quoted: message });
    }
}

module.exports = aliveCommand;
