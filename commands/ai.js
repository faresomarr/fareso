const axios = require('axios');

// مفتاح الذكاء الاصطناعي المخصص - يمكنك تغييره من هنا أو عبر متغير البيئة AI_API_KEY
const AI_API_KEY = process.env.AI_API_KEY || 'AQ.Ab8RN6JROQdETCT6qhX9K98QGfe0qGbP-1s6OskfQ_gbpQ_cdQ';
// عنوان نقطة النهاية المخصصة (اتركه فارغًا لاستخدام قائمة النقاط العامة الاحتياطية)
const AI_API_URL = process.env.AI_API_URL || '';
// اسم الموديل المطلوب من البوابة (يمكن تغييره)
const AI_MODEL = process.env.AI_MODEL || 'gemini-2.0-flash';

// خريطة الأوامر المدعومة (بالعربية والإنجليزية)
const SUPPORTED_COMMANDS = {
  '.ذكاء': 'ai',
  '.ai': 'ai',
  '.gpt': 'gpt',
  '.جيميني': 'gemini',
  '.gemini': 'gemini'
};

function getMessageText(message) {
  return (
    message.message?.conversation ||
    message.message?.extendedTextMessage?.text ||
    message.message?.imageMessage?.caption ||
    message.message?.videoMessage?.caption ||
    ''
  ).trim();
}

function buildArabicPrompt(question, mode = 'ai') {
  const role = mode === 'gemini' ? 'Gemini' : mode === 'gpt' ? 'GPT' : 'AI';
  return [
    `أنت مساعد ${role} مفيد داخل واتساب.`,
    'أجب باللغة العربية فقط وبشكل واضح ومباشر ومنظم.',
    'استخدم أسلوباً مهذباً ورسمياً نوعاً ما، وقدّم إجابة مختصرة دون إطالة غير ضرورية.',
    'إذا كان السؤال برمجياً، أعطِ حلاً صحيحاً ومختصراً مع أمثلة عند الحاجة.',
    'تجنب تماماً الرد بأي لغة أخرى غير العربية حتى لو كتب المستخدم السؤال بلغة أخرى.',
    `السؤال: ${question}`,
    'ردّك (بالعربية فقط):'
  ].join('\n');
}

function normalizeText(value) {
  return String(value || '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/\r/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function extractAnswer(payload) {
  if (!payload) return '';
  if (typeof payload === 'string') return normalizeText(payload);
  if (Array.isArray(payload)) {
    const joined = payload
      .map(item => (typeof item === 'string' ? item : item?.text || item?.content || item?.message || ''))
      .filter(Boolean)
      .join('\n');
    return normalizeText(joined);
  }

  const directCandidates = [
    payload.result,
    payload.answer,
    payload.message,
    payload.response,
    payload.text,
    payload.data?.result,
    payload.data?.answer,
    payload.data?.message,
    payload.data?.response,
    payload.data?.text,
    payload.data?.content,
    payload.data?.choices?.[0]?.message?.content,
    payload.choices?.[0]?.message?.content,
    payload.content,
    payload.candidates?.[0]?.content?.parts?.map?.(part => part?.text || '').join('\n'),
    payload.output?.[0]?.content?.[0]?.text,
    payload.output_text,
    payload.generated_text
  ];

  for (const candidate of directCandidates) {
    const text = extractAnswer(candidate);
    if (text) return text;
  }

  if (payload.data && typeof payload.data === 'object' && !Array.isArray(payload.data)) {
    for (const value of Object.values(payload.data)) {
      const text = extractAnswer(value);
      if (text) return text;
    }
  }

  for (const value of Object.values(payload)) {
    const text = extractAnswer(value);
    if (text) return text;
  }

  return '';
}

function getCommandAndQuery(text) {
  const raw = String(text || '').trim();
  // استخراج الأمر الصحيح بالنظر للأوامر المدعومة (يدعم العربية والإنجليزية)
  let matchedCommand = null;
  for (const cmd of Object.keys(SUPPORTED_COMMANDS)) {
    // تطابق: الأمر في بداية النص متبوعاً بمسافة أو نهاية النص
    const regex = new RegExp(`^${cmd.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(\\s+|$)`, 'u');
    if (regex.test(raw)) {
      matchedCommand = cmd;
      break;
    }
  }

  if (matchedCommand) {
    const query = raw.slice(matchedCommand.length).trim();
    return { command: matchedCommand, query };
  }

  // fallback: الأمر الأول حتى أول مسافة (lowercase للأوامر الإنجليزية)
  const parts = raw.split(/\s+/);
  const command = (parts.shift() || '').toLowerCase();
  const query = parts.join(' ').trim();
  return { command, query };
}

async function callCustomEndpoint(prompt, mode) {
  if (!AI_API_URL) return null;

  // دعم صيغ متعددة (OpenAI-compatible / Gemini / generic)
  try {
    // 1) صيغة OpenAI-compatible
    const isOpenAiCompatible = /\/chat\/completions$|\/v1\//i.test(AI_API_URL);
    if (isOpenAiCompatible) {
      const response = await axios.post(
        AI_API_URL,
        {
          model: AI_MODEL,
          messages: [
            { role: 'system', content: 'أنت مساعد ذكاء اصطناعي مفيد داخل واتساب. أجب باللغة العربية فقط، بشكل واضح ومباشر ومنظم. لا ترد بأي لغة أخرى غير العربية تحت أي ظرف.' },
            { role: 'user', content: prompt }
          ]
        },
        {
          timeout: 30000,
          validateStatus: status => status >= 200 && status < 500,
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${AI_API_KEY}`,
            'User-Agent': 'Mozilla/5.0'
          }
        }
      );
      const answer = extractAnswer(response.data);
      if (answer) return answer;
    }

    // 2) صيغة Gemini (generateContent)
    const isGeminiStyle = /gemini|generativelanguage/i.test(AI_API_URL);
    if (isGeminiStyle) {
      const urlWithKey = AI_API_URL.includes('?')
        ? `${AI_API_URL}&key=${encodeURIComponent(AI_API_KEY)}`
        : `${AI_API_URL}?key=${encodeURIComponent(AI_API_KEY)}`;
      const response = await axios.post(
        urlWithKey,
        {
          contents: [{ parts: [{ text: prompt }] }]
        },
        {
          timeout: 30000,
          validateStatus: status => status >= 200 && status < 500,
          headers: {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0'
          }
        }
      );
      const answer = extractAnswer(response.data);
      if (answer) return answer;
    }

    // 3) Generic POST كاحتياط
    const response = await axios.post(
      AI_API_URL,
      { prompt, question: prompt, text: prompt, message: prompt, model: AI_MODEL },
      {
        timeout: 30000,
        validateStatus: status => status >= 200 && status < 500,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${AI_API_KEY}`,
          'User-Agent': 'Mozilla/5.0'
        }
      }
    );
    const answer = extractAnswer(response.data);
    if (answer) return answer;

    // 4) Generic GET كاحتياط أخير
    const responseGet = await axios.get(
      AI_API_URL,
      {
        timeout: 30000,
        validateStatus: status => status >= 200 && status < 500,
        headers: {
          'Authorization': `Bearer ${AI_API_KEY}`,
          'User-Agent': 'Mozilla/5.0'
        },
        params: { prompt, text: prompt, question: prompt, model: AI_MODEL, key: AI_API_KEY }
      }
    );
    return extractAnswer(responseGet.data);
  } catch (error) {
    console.error('[AI Custom Endpoint] failed:', error?.message || error);
    return null;
  }
}

async function queryAiApis(question, mode) {
  const prompt = buildArabicPrompt(question, mode);

  // 1) محاولة البوابة المخصصة أولاً (تحمل المفتاح AQ. الخاص بك)
  const customAnswer = await callCustomEndpoint(question, mode);
  if (customAnswer) return customAnswer;

  // 2) الاحتياط: النقاط العامة المعروفة
  const endpoints = [
    `https://zellapi.autos/ai/chatbot?text=${encodeURIComponent(prompt)}`,
    `https://api.ryzendesu.vip/api/ai/gemini?text=${encodeURIComponent(prompt)}`,
    `https://api.siputzx.my.id/api/ai/gemini-pro?content=${encodeURIComponent(prompt)}`,
    `https://api.giftedtech.my.id/api/ai/geminiai?apikey=gifted&q=${encodeURIComponent(prompt)}`
  ];

  let lastError = null;

  for (const endpoint of endpoints) {
    try {
      const response = await axios.get(endpoint, {
        timeout: 25000,
        validateStatus: status => status >= 200 && status < 500,
        headers: {
          'User-Agent': 'Mozilla/5.0'
        }
      });

      const answer = extractAnswer(response.data);
      if (answer) return answer;
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError || new Error('All AI endpoints failed');
}

async function aiCommand(sock, chatId, message) {
  try {
    const text = getMessageText(message);
    const { command, query } = getCommandAndQuery(text);
    const mode = SUPPORTED_COMMANDS[command] || SUPPORTED_COMMANDS[command?.toLowerCase?.()] || 'ai';

    if (!query) {
      return await sock.sendMessage(chatId, {
        text: 'اكتب سؤالك بعد الأمر مباشرة.\n\nأمثلة:\n.ذكاء ما هو عاصمة مصر؟\n.ai اشرح لي async await\n.gpt اكتب كود تسجيل دخول بسيط\n.جيميني لخص هذا الموضوع'
      }, { quoted: message });
    }

    await sock.sendMessage(chatId, {
      react: { text: '🤖', key: message.key }
    });

    const answer = await queryAiApis(query, mode);

    await sock.sendMessage(chatId, {
      text: answer || '❌ لم أتمكن من استخراج رد مناسب الآن، جرّب مرة أخرى.'
    }, { quoted: message });
  } catch (error) {
    console.error('AI Command Error:', error);
    await sock.sendMessage(chatId, {
      text: '❌ تعذر الحصول على رد من الذكاء الاصطناعي حالياً. حاول مرة ثانية بعد قليل.'
    }, { quoted: message });
  }
}

module.exports = aiCommand;
