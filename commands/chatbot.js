const fs = require('fs');
const path = require('path');
const fetch = require('node-fetch');

const USER_GROUP_DATA = path.join(__dirname, '../data/userGroupData.json');

const chatMemory = {
  messages: new Map(),
  userInfo: new Map()
};

function loadUserGroupData() {
  try {
    return JSON.parse(fs.readFileSync(USER_GROUP_DATA));
  } catch (error) {
    console.error('❌ Error loading user group data:', error.message);
    return { groups: [], chatbot: {} };
  }
}

function saveUserGroupData(data) {
  try {
    fs.writeFileSync(USER_GROUP_DATA, JSON.stringify(data, null, 2));
  } catch (error) {
    console.error('❌ Error saving user group data:', error.message);
  }
}

function getRandomDelay() {
  return Math.floor(Math.random() * 1200) + 800;
}

async function showTyping(sock, chatId) {
  try {
    await sock.presenceSubscribe(chatId);
    await sock.sendPresenceUpdate('composing', chatId);
    await new Promise(resolve => setTimeout(resolve, getRandomDelay()));
  } catch (error) {
    console.error('Typing indicator error:', error);
  }
}

function extractUserInfo(message) {
  const info = {};
  const text = String(message || '');

  if (/my name is/i.test(text)) {
    info.name = text.split(/my name is/i)[1]?.trim()?.split(' ')?.[0];
  }

  if (/i am/i.test(text) && /years old/i.test(text)) {
    info.age = text.match(/\d+/)?.[0];
  }

  if (/i live in/i.test(text) || /i am from/i.test(text)) {
    info.location = text.split(/(?:i live in|i am from)/i)[1]?.trim()?.split(/[.,!?]/)?.[0];
  }

  return info;
}

async function handleChatbotCommand(sock, chatId, message, match) {
  if (!match) {
    await showTyping(sock, chatId);
    return sock.sendMessage(chatId, {
      text: '*إعدادات الشات بوت*\n\n*.chatbot on*\nتشغيل الشات بوت\n\n*.chatbot off*\nإيقاف الشات بوت في هذه المجموعة'
    }, { quoted: message });
  }

  const data = loadUserGroupData();
  const botNumber = sock.user.id.split(':')[0] + '@s.whatsapp.net';
  const senderId = message.key.participant || message.participant || message.pushName || message.key.remoteJid;
  const isOwner = senderId === botNumber;

  if (isOwner) {
    if (match === 'on') {
      await showTyping(sock, chatId);
      if (data.chatbot[chatId]) {
        return sock.sendMessage(chatId, { text: '*الشات بوت مفعل بالفعل في هذه المجموعة*' }, { quoted: message });
      }
      data.chatbot[chatId] = true;
      saveUserGroupData(data);
      return sock.sendMessage(chatId, { text: '*تم تفعيل الشات بوت في هذه المجموعة*' }, { quoted: message });
    }

    if (match === 'off') {
      await showTyping(sock, chatId);
      if (!data.chatbot[chatId]) {
        return sock.sendMessage(chatId, { text: '*الشات بوت متوقف بالفعل في هذه المجموعة*' }, { quoted: message });
      }
      delete data.chatbot[chatId];
      saveUserGroupData(data);
      return sock.sendMessage(chatId, { text: '*تم إيقاف الشات بوت في هذه المجموعة*' }, { quoted: message });
    }
  }

  let isAdmin = false;
  if (chatId.endsWith('@g.us')) {
    try {
      const groupMetadata = await sock.groupMetadata(chatId);
      isAdmin = groupMetadata.participants.some(p => p.id === senderId && (p.admin === 'admin' || p.admin === 'superadmin'));
    } catch (e) {
      console.warn('⚠️ Could not fetch group metadata. Bot might not be admin.');
    }
  }

  if (!isAdmin && !isOwner) {
    await showTyping(sock, chatId);
    return sock.sendMessage(chatId, {
      text: '❌ هذا الأمر متاح فقط لمشرفي المجموعة أو مالك البوت.'
    }, { quoted: message });
  }

  if (match === 'on') {
    await showTyping(sock, chatId);
    if (data.chatbot[chatId]) {
      return sock.sendMessage(chatId, { text: '*الشات بوت مفعل بالفعل في هذه المجموعة*' }, { quoted: message });
    }
    data.chatbot[chatId] = true;
    saveUserGroupData(data);
    return sock.sendMessage(chatId, { text: '*تم تفعيل الشات بوت في هذه المجموعة*' }, { quoted: message });
  }

  if (match === 'off') {
    await showTyping(sock, chatId);
    if (!data.chatbot[chatId]) {
      return sock.sendMessage(chatId, { text: '*الشات بوت متوقف بالفعل في هذه المجموعة*' }, { quoted: message });
    }
    delete data.chatbot[chatId];
    saveUserGroupData(data);
    return sock.sendMessage(chatId, { text: '*تم إيقاف الشات بوت في هذه المجموعة*' }, { quoted: message });
  }

  await showTyping(sock, chatId);
  return sock.sendMessage(chatId, {
    text: '*أمر غير صحيح. استخدم .chatbot لعرض طريقة الاستخدام*'
  }, { quoted: message });
}

async function handleChatbotResponse(sock, chatId, message, userMessage, senderId) {
  const data = loadUserGroupData();
  if (!data.chatbot[chatId]) return;

  try {
    const botId = sock.user.id;
    const botNumber = botId.split(':')[0];
    const botLid = sock.user.lid || '';
    const botJids = [
      botId,
      `${botNumber}@s.whatsapp.net`,
      `${botNumber}@whatsapp.net`,
      `${botNumber}@lid`,
      botLid,
      botLid ? `${botLid.split(':')[0]}@lid` : ''
    ].filter(Boolean);

    let isBotMentioned = false;
    let isReplyToBot = false;

    if (message.message?.extendedTextMessage) {
      const mentionedJid = message.message.extendedTextMessage.contextInfo?.mentionedJid || [];
      const quotedParticipant = message.message.extendedTextMessage.contextInfo?.participant;

      isBotMentioned = mentionedJid.some(jid => {
        const jidNumber = jid.split('@')[0].split(':')[0];
        return botJids.some(botJid => botJid.split('@')[0].split(':')[0] === jidNumber);
      });

      if (quotedParticipant) {
        const cleanQuoted = quotedParticipant.replace(/[:@].*$/, '');
        isReplyToBot = botJids.some(botJid => botJid.replace(/[:@].*$/, '') === cleanQuoted);
      }
    } else if (message.message?.conversation) {
      isBotMentioned = userMessage.includes(`@${botNumber}`);
    }

    if (!isBotMentioned && !isReplyToBot) return;

    let cleanedMessage = userMessage;
    if (isBotMentioned) {
      cleanedMessage = cleanedMessage.replace(new RegExp(`@${botNumber}`, 'g'), '').trim();
    }

    if (!chatMemory.messages.has(senderId)) {
      chatMemory.messages.set(senderId, []);
      chatMemory.userInfo.set(senderId, {});
    }

    const userInfo = extractUserInfo(cleanedMessage);
    if (Object.keys(userInfo).length > 0) {
      chatMemory.userInfo.set(senderId, {
        ...chatMemory.userInfo.get(senderId),
        ...userInfo
      });
    }

    const messages = chatMemory.messages.get(senderId);
    messages.push(cleanedMessage);
    if (messages.length > 20) messages.shift();
    chatMemory.messages.set(senderId, messages);

    await showTyping(sock, chatId);

    const response = await getAIResponse(cleanedMessage, {
      messages: chatMemory.messages.get(senderId),
      userInfo: chatMemory.userInfo.get(senderId)
    });

    if (!response) {
      await sock.sendMessage(chatId, {
        text: '🤔 ما قدرت أرد الآن، جرّب ترسل سؤالك مرة ثانية.'
      }, { quoted: message });
      return;
    }

    await new Promise(resolve => setTimeout(resolve, getRandomDelay()));
    await sock.sendMessage(chatId, { text: response }, { quoted: message });
  } catch (error) {
    console.error('❌ Error in chatbot response:', error.message);
    if (error.message && error.message.includes('No sessions')) return;

    try {
      await sock.sendMessage(chatId, {
        text: '❌ صار خطأ أثناء تجهيز الرد، أرسل رسالتك مرة ثانية.'
      }, { quoted: message });
    } catch (sendError) {
      console.error('Failed to send chatbot error message:', sendError.message);
    }
  }
}

async function getAIResponse(userMessage, userContext) {
  try {
    const prompt = [
      'أنت مساعد ودود داخل واتساب.',
      'أجب باللغة العربية فقط.',
      'اجعل الرد قصيراً ومفيداً وطبيعياً.',
      'إذا كان السؤال تقنياً فأعطِ إجابة واضحة ومباشرة.',
      'لا تكرر التعليمات ولا تذكر أنك تتبع برومبت.',
      '',
      'سياق المحادثة السابق:',
      userContext.messages.join('\n'),
      '',
      'معلومات المستخدم:',
      JSON.stringify(userContext.userInfo, null, 2),
      '',
      `رسالة المستخدم الحالية: ${userMessage}`,
      '',
      'الرد بالعربية:'
    ].join('\n');

    const response = await fetch('https://zellapi.autos/ai/chatbot?text=' + encodeURIComponent(prompt));
    if (!response.ok) throw new Error('API call failed');

    const data = await response.json();
    if (!data.status || !data.result) throw new Error('Invalid API response');

    return String(data.result)
      .replace(/\r/g, '')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  } catch (error) {
    console.error('AI API error:', error);
    return null;
  }
}

module.exports = {
  handleChatbotCommand,
  handleChatbotResponse
};
