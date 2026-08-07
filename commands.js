// commands.js
const UserConfig = require('./models/UserConfig');

module.exports = async (sock, msg, text, senderJid) => {
    const prefix = '!';
    if (!text.startsWith(prefix)) return;

    const args = text.slice(prefix.length).trim().split(/ +/);
    const command = args.shift().toLowerCase();

    if (command === 'setemoji') {
        const newEmoji = args[0];
        if (!newEmoji) {
            return await sock.sendMessage(senderJid, { text: 'الرجاء إرسال إيموجي. مثال: !setemoji 💤' });
        }
        
        await UserConfig.findOneAndUpdate(
            { jid: senderJid },
            { emoji: newEmoji },
            { upsert: true }
        );
        await sock.sendMessage(senderJid, { text: `تم تحديث إيموجي التفاعل إلى: ${newEmoji}` });
    }
};
