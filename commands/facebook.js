const axios = require('axios');
const fs = require('fs');
const path = require('path');

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

function isFacebookUrl(url = '') {
  return /https?:\/\/(?:www\.)?(?:facebook\.com|fb\.watch|m\.facebook\.com)\//i.test(url);
}

function firstNonEmpty(...values) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
}

function extractFacebookResult(data) {
  if (!data || typeof data !== 'object') return null;
  const roots = [data, data.result, data.data].filter(Boolean);

  for (const root of roots) {
    const fbvid = firstNonEmpty(
      root?.media?.video_hd,
      root?.media?.video_sd,
      root?.video_hd,
      root?.video_sd,
      root?.url,
      root?.download,
      root?.video,
      Array.isArray(root) ? root.find(item => item?.quality === 'HD')?.url : '',
      Array.isArray(root) ? root.find(item => item?.quality === 'SD')?.url : '',
      Array.isArray(root) ? root[0]?.url : ''
    );

    if (fbvid) {
      return {
        videoUrl: fbvid,
        title: firstNonEmpty(root?.info?.title, root?.title, root?.caption, 'Facebook Video')
      };
    }
  }

  return null;
}

async function facebookCommand(sock, chatId, message) {
  try {
    const text = getMessageText(message);
    const url = extractUrl(text);

    if (!url) {
      return await sock.sendMessage(chatId, {
        text: 'أرسل رابط فيديو فيسبوك صحيح، مثال:\n.fb https://www.facebook.com/...'
      }, { quoted: message });
    }

    if (!isFacebookUrl(url)) {
      return await sock.sendMessage(chatId, {
        text: '❌ هذا ليس رابط فيسبوك صحيح.'
      }, { quoted: message });
    }

    await sock.sendMessage(chatId, {
      react: { text: '🔄', key: message.key }
    });

    let resolvedUrl = url;
    try {
      const res = await axios.get(url, {
        timeout: 20000,
        maxRedirects: 10,
        headers: { 'User-Agent': 'Mozilla/5.0' }
      });
      const possible = res?.request?.res?.responseUrl;
      if (possible && typeof possible === 'string') resolvedUrl = possible;
    } catch (_) {}

    const endpoints = [
      `https://api.hanggts.xyz/download/facebook?url=${encodeURIComponent(resolvedUrl)}`,
      `https://api.hanggts.xyz/download/facebook?url=${encodeURIComponent(url)}`
    ];

    let result = null;
    for (const endpoint of endpoints) {
      try {
        const response = await axios.get(endpoint, {
          timeout: 20000,
          headers: {
            accept: '*/*',
            'User-Agent': 'Mozilla/5.0'
          },
          maxRedirects: 5,
          validateStatus: status => status >= 200 && status < 500
        });
        result = extractFacebookResult(response.data);
        if (result?.videoUrl) break;
      } catch (error) {
        console.error('Facebook API failed:', error.message);
      }
    }

    if (!result?.videoUrl) {
      return await sock.sendMessage(chatId, {
        text: '❌ تعذر الحصول على رابط الفيديو من فيسبوك. قد يكون الفيديو خاصاً أو الرابط غير صالح.'
      }, { quoted: message });
    }

    const caption = result.title ? `✅ تم تنزيل فيديو فيسبوك\n\n📝 ${result.title}` : '✅ تم تنزيل فيديو فيسبوك';

    try {
      await sock.sendMessage(chatId, {
        video: { url: result.videoUrl },
        mimetype: 'video/mp4',
        caption
      }, { quoted: message });
      return;
    } catch (urlError) {
      console.error('Facebook URL send failed:', urlError.message);
    }

    const tmpDir = path.join(process.cwd(), 'tmp');
    if (!fs.existsSync(tmpDir)) fs.mkdirSync(tmpDir, { recursive: true });
    const tempFile = path.join(tmpDir, `fb_${Date.now()}.mp4`);

    try {
      const videoResponse = await axios({
        method: 'GET',
        url: result.videoUrl,
        responseType: 'stream',
        timeout: 60000,
        headers: {
          'User-Agent': 'Mozilla/5.0',
          Accept: 'video/mp4,video/*;q=0.9,*/*;q=0.8',
          Referer: 'https://www.facebook.com/'
        }
      });

      const writer = fs.createWriteStream(tempFile);
      videoResponse.data.pipe(writer);
      await new Promise((resolve, reject) => {
        writer.on('finish', resolve);
        writer.on('error', reject);
      });

      await sock.sendMessage(chatId, {
        video: { url: tempFile },
        mimetype: 'video/mp4',
        caption
      }, { quoted: message });
    } finally {
      try { if (fs.existsSync(tempFile)) fs.unlinkSync(tempFile); } catch (_) {}
    }
  } catch (error) {
    console.error('Error in Facebook command:', error);
    await sock.sendMessage(chatId, {
      text: '❌ حدث خطأ أثناء تنزيل فيديو فيسبوك. حاول مرة أخرى.'
    }, { quoted: message });
  }
}

module.exports = facebookCommand;
