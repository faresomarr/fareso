const { igdl } = require('ruhend-scraper');

const processedMessages = new Set();

function getMessageText(message) {
  return (
    message.message?.conversation ||
    message.message?.extendedTextMessage?.text ||
    message.message?.imageMessage?.caption ||
    message.message?.videoMessage?.caption ||
    ''
  ).trim();
}

function extractUrl(text = '') {
  return String(text).match(/https?:\/\/\S+/i)?.[0] || '';
}

function isInstagramUrl(url = '') {
  return /https?:\/\/(?:www\.)?(?:instagram\.com|instagr\.am)\//i.test(url);
}

function extractUniqueMedia(mediaData) {
  const uniqueMedia = [];
  const seenUrls = new Set();
  for (const media of mediaData) {
    if (!media?.url) continue;
    if (seenUrls.has(media.url)) continue;
    seenUrls.add(media.url);
    uniqueMedia.push(media);
  }
  return uniqueMedia;
}

async function instagramCommand(sock, chatId, message) {
  try {
    if (processedMessages.has(message.key.id)) return;
    processedMessages.add(message.key.id);
    setTimeout(() => processedMessages.delete(message.key.id), 5 * 60 * 1000);

    const text = getMessageText(message);
    const url = extractUrl(text);

    if (!url) {
      return await sock.sendMessage(chatId, {
        text: 'أرسل رابط إنستغرام صحيح، مثال:\n.instagram https://www.instagram.com/reel/...'
      }, { quoted: message });
    }

    if (!isInstagramUrl(url)) {
      return await sock.sendMessage(chatId, {
        text: '❌ هذا ليس رابط إنستغرام صحيح.'
      }, { quoted: message });
    }

    await sock.sendMessage(chatId, {
      react: { text: '🔄', key: message.key }
    });

    const downloadData = await igdl(url);
    const mediaData = Array.isArray(downloadData?.data) ? downloadData.data : [];
    if (!mediaData.length) {
      return await sock.sendMessage(chatId, {
        text: '❌ لم يتم العثور على وسائط في الرابط. قد يكون المنشور خاصاً أو الرابط غير صالح.'
      }, { quoted: message });
    }

    const mediaToDownload = extractUniqueMedia(mediaData).slice(0, 20);
    if (!mediaToDownload.length) {
      return await sock.sendMessage(chatId, {
        text: '❌ لم أتمكن من استخراج ملفات قابلة للتنزيل من الرابط.'
      }, { quoted: message });
    }

    for (let i = 0; i < mediaToDownload.length; i++) {
      try {
        const media = mediaToDownload[i];
        const mediaUrl = media.url;
        const isVideo = media.type === 'video' || /\.(mp4|mov|avi|mkv|webm)(\?|$)/i.test(mediaUrl) || /\/reel\//i.test(url) || /\/tv\//i.test(url);

        if (isVideo) {
          await sock.sendMessage(chatId, {
            video: { url: mediaUrl },
            mimetype: 'video/mp4',
            caption: '✅ تم تنزيل المقطع من إنستغرام'
          }, { quoted: message });
        } else {
          await sock.sendMessage(chatId, {
            image: { url: mediaUrl },
            caption: '✅ تم تنزيل الصورة من إنستغرام'
          }, { quoted: message });
        }

        if (i < mediaToDownload.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      } catch (mediaError) {
        console.error(`Error downloading Instagram media ${i + 1}:`, mediaError.message);
      }
    }
  } catch (error) {
    console.error('Error in Instagram command:', error);
    await sock.sendMessage(chatId, {
      text: '❌ حدث خطأ أثناء تنزيل محتوى إنستغرام. حاول مرة أخرى.'
    }, { quoted: message });
  }
}

module.exports = instagramCommand;
