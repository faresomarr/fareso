async function pairCommand(sock, chatId) {
    await sock.sendMessage(chatId, {
        text: `📱 الربط يتم من داخل البوت فقط.

❌ تم تعطيل أي مواقع أو روابط خارجية للربط.
✅ اطلب كود الاقتران من واجهة البوت التي تربط منها رقمك.`,
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
