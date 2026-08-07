const { ttdl } = require('ruhend-scraper');
const axios = require('axios');

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

function isTikTokUrl(url = '') {
  return /https?:\/\/(?:www\.)?(?:vt|vm)?\.?tiktok\.com\//i.test(url) || /https?:\/\/www\.tiktok\.com\/@/i.test(url);
}

function firstNonEmpty(...values) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
}

function extractTikTokResult(payload) {
  if (!payload || typeof payload !== 'object') return null;

  const roots = [payload, payload.data, payload.result, payload.data?.data, payload.result?.data].filter(Boolean);

  for (const root of roots) {
    const title = firstNonEmpty(
      root?.title,
      root?.desc,
      root?.metadata?.title,
      root?.author?.nickname,
      root?.music_info?.title,
      'TikTok Video'
    );

    const videoUrl = firstNonEmpty(
      root?.play,
      root?.hdplay,
      root?.hdplay_url,
      root?.no_watermark,
      root?.nowm,
      root?.wmv,
      root?.video,
      root?.video_url,
      root?.download,
      root?.download_url,
      root?.url,
      Array.isArray(root?.urls) ? root.urls[0] : '',
      Array.isArray(root?.video) ? root.video[0] : ''
    );

    const audioUrl = firstNonEmpty(
      root?.music,
      root?.music_url,
      root?.audio,
      root?.audio_url,
      root?.mp3,
      root?.music_info?.play
    );

    if (videoUrl) {
      return { videoUrl, audioUrl, title };
    }
  }

  return null;
}

async function sendVideo(sock, chatId, message, videoUrl, title = '') {
  const caption = title ? `✅ تم تنزيل فيديو تيك توك بدون علامة مائية\n\n📝 ${title}` : '✅ تم تنزيل فيديو تيك توك بدون علامة مائية';

  try {
    await sock.sendMessage(chatId, {
      video: { url: videoUrl },
      mimetype: 'video/mp4',
      caption
    }, { quoted: message });
    return true;
  } catch (urlError) {
    try {
      const videoResponse = await axios.get(videoUrl, {
        responseType: 'arraybuffer',
        timeout: 60000,
        maxContentLength: 100 * 1024 * 1024,
        headers: {
          'User-Agent': 'Mozilla/5.0',
          'Referer': 'https://www.tiktok.com/'
        }
      });

      const videoBuffer = Buffer.from(videoResponse.data || []);
      if (!videoBuffer.length) throw new Error('empty video buffer');

      await sock.sendMessage(chatId, {
        video: videoBuffer,
        mimetype: 'video/mp4',
        caption
      }, { quoted: message });
      return true;
    } catch (bufferError) {
      console.error('TikTok sendVideo failed:', urlError.message, bufferError.message);
      return false;
    }
  }
}

async function fetchTikTokFromApis(url) {
  const endpoints = [
    `https://api.siputzx.my.id/api/d/tiktok?url=${encodeURIComponent(url)}`,
    `https://api.ryzendesu.vip/api/downloader/tiktok?url=${encodeURIComponent(url)}`,
    `https://api.giftedtech.my.id/api/download/tiktok?apikey=gifted&url=${encodeURIComponent(url)}`
  ];

  for (const endpoint of endpoints) {
    try {
      const response = await axios.get(endpoint, {
        timeout: 20000,
        validateStatus: status => status >= 200 && status < 500,
        headers: { 'User-Agent': 'Mozilla/5.0' }
      });

      const extracted = extractTikTokResult(response.data);
      if (extracted?.videoUrl) return extracted;
    } catch (error) {
      console.error('TikTok API failed:', endpoint, error.message);
    }
  }

  return null;
}

async function fetchTikTokFromScraper(url) {
  try {
    const downloadData = await ttdl(url);
    const mediaData = Array.isArray(downloadData?.data) ? downloadData.data : [];
    for (const media of mediaData) {
      const mediaUrl = media?.url || '';
      const isVideo = media?.type === 'video' || /\.(mp4|mov|avi|mkv|webm)(\?|$)/i.test(mediaUrl);
      if (isVideo && mediaUrl) {
        return {
          videoUrl: mediaUrl,
          audioUrl: '',
          title: media?.title || 'TikTok Video'
        };
      }
    }
  } catch (error) {
    console.error('TikTok scraper fallback failed:', error.message);
  }

  return null;
}

async function tiktokCommand(sock, chatId, message) {
  try {
    if (processedMessages.has(message.key.id)) return;
    processedMessages.add(message.key.id);
    setTimeout(() => processedMessages.delete(message.key.id), 5 * 60 * 1000);

    const text = getMessageText(message);
    const url = extractUrl(text);

    if (!url) {
      return await sock.sendMessage(chatId, {
        text: 'أرسل رابط تيك توك صحيح، مثال:\n.tiktok https://vt.tiktok.com/...'
      }, { quoted: message });
    }

    if (!isTikTokUrl(url)) {
      return await sock.sendMessage(chatId, {
        text: '❌ هذا ليس رابط تيك توك صحيح.'
      }, { quoted: message });
    }

    await sock.sendMessage(chatId, {
      react: { text: '🔄', key: message.key }
    });

    const result = await fetchTikTokFromApis(url) || await fetchTikTokFromScraper(url);
    if (!result?.videoUrl) {
      return await sock.sendMessage(chatId, {
        text: '❌ تعذر تنزيل فيديو تيك توك حالياً. جرّب رابطاً آخر أو أعد المحاولة لاحقاً.'
      }, { quoted: message });
    }

    const sent = await sendVideo(sock, chatId, message, result.videoUrl, result.title);
    if (!sent) {
      return await sock.sendMessage(chatId, {
        text: '❌ تم العثور على الفيديو لكن فشل إرساله. حاول مرة أخرى بعد قليل.'
      }, { quoted: message });
    }
  } catch (error) {
    console.error('Error in TikTok command:', error);
    await sock.sendMessage(chatId, {
      text: '❌ حدث خطأ أثناء معالجة رابط تيك توك. حاول مرة أخرى.'
    }, { quoted: message });
  }
}

module.exports = tiktokCommand;
