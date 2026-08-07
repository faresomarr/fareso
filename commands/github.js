const moment = require('moment-timezone');
const fetch = require('node-fetch');
const fs = require('fs');
const path = require('path');
const settings = require('../settings');

const DEFAULT_PROJECT_URL = 'https://t.me/Faresw_bot';

function getConfiguredProjectUrl() {
  return String(global.repoUrl || settings.repoUrl || DEFAULT_PROJECT_URL).trim() || DEFAULT_PROJECT_URL;
}

function extractIncomingText(message = {}) {
  return String(
    message?.message?.conversation ||
    message?.message?.extendedTextMessage?.text ||
    message?.message?.imageMessage?.caption ||
    message?.message?.videoMessage?.caption ||
    ''
  ).trim().toLowerCase();
}

function isGithubRepoUrl(repoUrl = '') {
  return /github\.com\/[^/]+\/[^/#?]+/i.test(String(repoUrl));
}

function parseRepoInfo(repoUrl = '') {
  const match = String(repoUrl).match(/github\.com\/([^/]+)\/([^/#?]+)/i);
  if (!match) return null;

  return {
    owner: match[1],
    repo: match[2].replace(/\.git$/i, ''),
    htmlUrl: `https://github.com/${match[1]}/${match[2].replace(/\.git$/i, '')}`
  };
}

function buildProjectInfoMessage(projectUrl) {
  let txt = `*📦 معلومات المشروع*

`;
  txt += `*الاسم:* ${settings.botName || 'Knight Bot'}
`;
  txt += `*الوصف:* ${settings.description || 'لا يوجد وصف'}
`;
  txt += `*الإصدار:* ${settings.version || 'غير معروف'}
`;
  txt += `*المطور:* ${settings.botOwner || 'غير معروف'}
`;
  txt += `*الرابط:* ${projectUrl}`;
  return txt;
}

async function sendProjectResponse(sock, chatId, message, text) {
  const imgPath = path.join(__dirname, '../assets/bot_image.jpg');
  if (fs.existsSync(imgPath)) {
    const imgBuffer = fs.readFileSync(imgPath);
    await sock.sendMessage(chatId, { image: imgBuffer, caption: text }, { quoted: message });
    return;
  }

  await sock.sendMessage(chatId, { text }, { quoted: message });
}

async function githubCommand(sock, chatId, message) {
  const projectUrl = getConfiguredProjectUrl();
  const incomingText = extractIncomingText(message);
  const isDirectLinkCommand = ['.git', '.sc', '.script', '.repo'].includes(incomingText);

  try {
    if (isDirectLinkCommand) {
      await sendProjectResponse(sock, chatId, message, `*🔗 رابط المشروع:*
${projectUrl}`);
      return;
    }

    if (!isGithubRepoUrl(projectUrl)) {
      await sendProjectResponse(sock, chatId, message, buildProjectInfoMessage(projectUrl));
      return;
    }

    const repoInfo = parseRepoInfo(projectUrl);
    if (!repoInfo) {
      await sendProjectResponse(sock, chatId, message, buildProjectInfoMessage(projectUrl));
      return;
    }

    const apiUrl = `https://api.github.com/repos/${repoInfo.owner}/${repoInfo.repo}`;
    const res = await fetch(apiUrl, {
      headers: {
        'User-Agent': 'KnightBot-MD'
      }
    });

    if (!res.ok) throw new Error('GitHub API request failed');
    const json = await res.json();

    let txt = `*📦 معلومات المستودع*

`;
    txt += `*الاسم:* ${json.full_name || `${repoInfo.owner}/${repoInfo.repo}`}
`;
    txt += `*الوصف:* ${json.description || 'لا يوجد وصف'}
`;
    txt += `*النجوم:* ${json.stargazers_count ?? 0}
`;
    txt += `*الفوركات:* ${json.forks_count ?? 0}
`;
    txt += `*المشاهدات:* ${json.watchers_count ?? 0}
`;
    txt += `*الحجم:* ${Number.isFinite(json.size) ? (json.size / 1024).toFixed(2) : '0.00'} MB
`;
    txt += `*آخر تحديث:* ${json.updated_at ? moment(json.updated_at).format('DD/MM/YYYY - HH:mm:ss') : 'غير معروف'}
`;
    txt += `*الرابط:* ${projectUrl}`;

    await sendProjectResponse(sock, chatId, message, txt);
  } catch (error) {
    console.error('githubCommand error:', error);
    await sendProjectResponse(sock, chatId, message, buildProjectInfoMessage(projectUrl));
  }
}

module.exports = githubCommand;
