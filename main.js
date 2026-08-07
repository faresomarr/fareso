// 🧹 Fix for ENOSPC / temp overflow in hosted panels
const fs = require('fs');
const path = require('path');

// Redirect temp storage away from system /tmp
const customTemp = path.join(process.cwd(), 'temp');
if (!fs.existsSync(customTemp)) fs.mkdirSync(customTemp, { recursive: true });
process.env.TMPDIR = customTemp;
process.env.TEMP = customTemp;
process.env.TMP = customTemp;

// Auto-cleaner every 3 hours
setInterval(() => {
    fs.readdir(customTemp, (err, files) => {
        if (err) return;
        for (const file of files) {
            const filePath = path.join(customTemp, file);
            fs.stat(filePath, (err, stats) => {
                if (!err && Date.now() - stats.mtimeMs > 3 * 60 * 60 * 1000) {
                    fs.unlink(filePath, () => { });
                }
            });
        }
    });
    console.log('🧹 Temp folder auto-cleaned');
}, 3 * 60 * 60 * 1000);

const settings = require('./settings');
require('./config.js');
const { isBanned } = require('./lib/isBanned');
const yts = require('yt-search');
const { fetchBuffer } = require('./lib/myfunc');
const fetch = require('node-fetch');
const ytdl = require('ytdl-core');
const axios = require('axios');
const ffmpeg = require('fluent-ffmpeg');
const { isSudo } = require('./lib/index');
const isOwnerOrSudo = require('./lib/isOwner');
const { autotypingCommand, isAutotypingEnabled, handleAutotypingForMessage, handleAutotypingForCommand, showTypingAfterCommand } = require('./commands/autotyping');
const { autoreadCommand, isAutoreadEnabled, handleAutoread } = require('./commands/autoread');

// Command imports
const tagAllCommand = require('./commands/tagall');
const helpCommand = require('./commands/help');
const banCommand = require('./commands/ban');
const { promoteCommand } = require('./commands/promote');
const { demoteCommand } = require('./commands/demote');
const muteCommand = require('./commands/mute');
const unmuteCommand = require('./commands/unmute');
const stickerCommand = require('./commands/sticker');
const isAdmin = require('./lib/isAdmin');
const warnCommand = require('./commands/warn');
const warningsCommand = require('./commands/warnings');
const ttsCommand = require('./commands/tts');
const { tictactoeCommand, handleTicTacToeMove } = require('./commands/tictactoe');
const { incrementMessageCount, topMembers } = require('./commands/topmembers');
const ownerCommand = require('./commands/owner');
const deleteCommand = require('./commands/delete');
const { handleAntilinkCommand, handleLinkDetection } = require('./commands/antilink');
const { handleAntitagCommand, handleTagDetection } = require('./commands/antitag');
const { Antilink } = require('./lib/antilink');
const { handleMentionDetection, mentionToggleCommand, setMentionCommand } = require('./commands/mention');
const memeCommand = require('./commands/meme');
const tagCommand = require('./commands/tag');
const tagNotAdminCommand = require('./commands/tagnotadmin');
const hideTagCommand = require('./commands/hidetag');
const jokeCommand = require('./commands/joke');
const quoteCommand = require('./commands/quote');
const factCommand = require('./commands/fact');
const weatherCommand = require('./commands/weather');
const newsCommand = require('./commands/news');
const kickCommand = require('./commands/kick');
const simageCommand = require('./commands/simage');
const attpCommand = require('./commands/attp');
const { startHangman, guessLetter } = require('./commands/hangman');
const { startTrivia, answerTrivia } = require('./commands/trivia');
const { complimentCommand } = require('./commands/compliment');
const { insultCommand } = require('./commands/insult');
const { eightBallCommand } = require('./commands/eightball');
const { lyricsCommand } = require('./commands/lyrics');
const { dareCommand } = require('./commands/dare');
const { truthCommand } = require('./commands/truth');
const { clearCommand } = require('./commands/clear');
const pingCommand = require('./commands/ping');
const aliveCommand = require('./commands/alive');
const blurCommand = require('./commands/img-blur');
const { welcomeCommand, handleJoinEvent } = require('./commands/welcome');
const { goodbyeCommand, handleLeaveEvent } = require('./commands/goodbye');
const githubCommand = require('./commands/github');
const { handleAntiBadwordCommand, handleBadwordDetection } = require('./lib/antibadword');
const antibadwordCommand = require('./commands/antibadword');
const { handleChatbotCommand, handleChatbotResponse } = require('./commands/chatbot');
const takeCommand = require('./commands/take');
const { flirtCommand } = require('./commands/flirt');
const characterCommand = require('./commands/character');
const wastedCommand = require('./commands/wasted');
const shipCommand = require('./commands/ship');
const groupInfoCommand = require('./commands/groupinfo');
const resetlinkCommand = require('./commands/resetlink');
const staffCommand = require('./commands/staff');
const unbanCommand = require('./commands/unban');
const emojimixCommand = require('./commands/emojimix');
const { handlePromotionEvent } = require('./commands/promote');
const { handleDemotionEvent } = require('./commands/demote');
const viewOnceCommand = require('./commands/viewonce');
const clearSessionCommand = require('./commands/clearsession');
const { autoStatusCommand, handleStatusUpdate } = require('./commands/autostatus');
const { simpCommand } = require('./commands/simp');
const { stupidCommand } = require('./commands/stupid');
const stickerTelegramCommand = require('./commands/stickertelegram');
const textmakerCommand = require('./commands/textmaker');
const { handleAntideleteCommand, handleMessageRevocation, storeMessage } = require('./commands/antidelete');
const clearTmpCommand = require('./commands/cleartmp');
const setProfilePicture = require('./commands/setpp');
const { setGroupDescription, setGroupName, setGroupPhoto } = require('./commands/groupmanage');
const instagramCommand = require('./commands/instagram');
const facebookCommand = require('./commands/facebook');
const spotifyCommand = require('./commands/spotify');
const playCommand = require('./commands/play');
const tiktokCommand = require('./commands/tiktok');
const songCommand = require('./commands/song');
const aiCommand = require('./commands/ai');
const urlCommand = require('./commands/url');
const { handleTranslateCommand } = require('./commands/translate');
const { handleSsCommand } = require('./commands/ss');
const { addCommandReaction, handleAreactCommand } = require('./lib/reactions');
const { goodnightCommand } = require('./commands/goodnight');
const { shayariCommand } = require('./commands/shayari');
const { rosedayCommand } = require('./commands/roseday');
const imagineCommand = require('./commands/imagine');
const videoCommand = require('./commands/video');
const sudoCommand = require('./commands/sudo');
const { miscCommand, handleHeart } = require('./commands/misc');
const { animeCommand } = require('./commands/anime');
const { piesCommand, piesAlias } = require('./commands/pies');
const stickercropCommand = require('./commands/stickercrop');
const updateCommand = require('./commands/update');
const removebgCommand = require('./commands/removebg');
const { reminiCommand } = require('./commands/remini');
const { igsCommand } = require('./commands/igs');
const { anticallCommand, readState: readAnticallState } = require('./commands/anticall');
const { pmblockerCommand, readState: readPmBlockerState } = require('./commands/pmblocker');
const settingsCommand = require('./commands/settings');
const soraCommand = require('./commands/sora');
const translateGoogle = (() => {
    try {
        return require('translate-google-api');
    } catch (_) {
        return null;
    }
})();

// Global settings
global.packname = settings.packname;
global.author = settings.author;
global.channelLink = settings.channelLink || "https://whatsapp.com/channel/0029Vb8jjfWCRs1sVz0x1w3v";
global.repoUrl = settings.repoUrl || "https://t.me/Faresw_bot";
global.ytch = settings.botOwner || "Knight Bot";

const channelInfo = {};

const COMMAND_ALIASES = {
    help: ['الاوامر', 'الأوامر', 'اوامر', 'مساعدة', 'قائمة', 'منيو'],
    menu: ['المنيو'],
    alive: ['حي', 'شغال', 'فحص'],
    ping: ['بنج', 'سرعة'],
    owner: ['المالك', 'مطور', 'المطور'],
    tts: ['تكلم', 'صوت'],
    ban: ['حظر'],
    unban: ['فكالحظر', 'فك_الحظر', 'الغاءالحظر', 'إلغاءالحظر'],
    promote: ['ترقية'],
    demote: ['تنزيل'],
    mute: ['كتم'],
    unmute: ['فكالكتم', 'فك_الكتم'],
    delete: ['حذف'],
    del: ['مسح'],
    sticker: ['ستيكر', 'ملصق'],
    simage: ['صورةالملصق', 'صورة_الملصق'],
    attp: ['ملصقنص', 'ملصق_نص'],
    settings: ['الاعدادات', 'الإعدادات'],
    mode: ['الوضع'],
    anticall: ['منعالاتصال', 'منع_الاتصال'],
    pmblocker: ['منعالخاص', 'منع_الخاص'],
    tagall: ['منشنالكل', 'منشن_الكل'],
    tagnotadmin: ['منشنالاعضاء', 'منشن_الاعضاء'],
    hidetag: ['منشنمخفي', 'منشن_مخفي'],
    tag: ['منشن', 'تاق'],
    antilink: ['منعالروابط', 'منع_الروابط'],
    antitag: ['منعالمنشن', 'منع_المنشن'],
    antibadword: ['منعالسب', 'منع_السب'],
    weather: ['طقس'],
    news: ['اخبار', 'أخبار'],
    tictactoe: ['اكساو', 'اكس_او', 'xo'],
    guess: ['خمن'],
    trivia: ['سؤال'],
    answer: ['اجابة', 'إجابة'],
    warnings: ['تحذيرات'],
    warn: ['تحذير'],
    lyrics: ['كلمات'],
    joke: ['نكتة'],
    quote: ['اقتباس'],
    fact: ['معلومة'],
    kick: ['طرد'],
    groupinfo: ['معلوماتالقروب', 'معلومات_القروب'],
    staff: ['المشرفين', 'الادمنية', 'الأدمنية'],
    chatbot: ['شاتبوت', 'دردشة'],
    resetlink: ['اعادةالرابط', 'إعادةالرابط', 'اعادة_الرابط', 'إعادة_الرابط'],
    welcome: ['ترحيب'],
    goodbye: ['وداع'],
    clear: ['تنظيف'],
    github: ['السورس'],
    git: ['كود'],
    repo: ['المستودع'],
    sc: ['شفرة'],
    take: ['اخذ', 'أخذ'],
    flirt: ['مغازلة'],
    character: ['شخصية'],
    wasted: ['هلاك'],
    ship: ['شيب'],
    url: ['رابط'],
    emojimix: ['دمجايموجي', 'دمج_ايموجي'],
    tgsticker: ['ملصقاتتيليجرام', 'ملصقات_تيليجرام'],
    vv: ['فتح'],
    clearsession: ['تنظيفالجلسات', 'تنظيف_الجلسات'],
    autostatus: ['حالةتلقائية', 'حالة_تلقائية'],
    simp: ['سمب'],
    truth: ['صراحة'],
    dare: ['تحدي'],
    setpp: ['صورةالبوت', 'صورة_البوت'],
    setgdesc: ['وصفالقروب', 'وصف_القروب'],
    setgname: ['اسمالقروب', 'اسم_القروب'],
    setgpp: ['صورةالقروب', 'صورة_القروب'],
    instagram: ['انستا', 'إنستا'],
    igs: ['ستوري'],
    igsc: ['انستاميديا', 'إنستاميديا'],
    facebook: ['فيسبوك'],
    spotify: ['سبوتيفاي'],
    play: ['شغل'],
    song: ['اغنية', 'أغنية'],
    video: ['فيديو'],
    tiktok: ['تيك', 'تيكتوك', 'تيك_توك'],
    ai: ['ذكاء'],
    gpt: ['جيبيتي', 'جي_بي_تي'],
    gemini: ['جيميني'],
    translate: ['ترجمة'],
    trt: ['ترجم'],
    ss: ['صورةموقع', 'صورة_موقع'],
    autoreact: ['تفاعلتلقائي', 'تفاعل_تلقائي'],
    areact: ['تفاعل'],
    sudo: ['سودو'],
    goodnight: ['تصبحتعلىخير', 'تصبح_على_خير'],
    shayari: ['شعر'],
    roseday: ['ورد'],
    imagine: ['تخيل'],
    flux: ['فلوكس'],
    jid: ['معرف'],
    autotyping: ['كتابةتلقائية', 'كتابة_تلقائية'],
    autoread: ['قراءةتلقائية', 'قراءة_تلقائية'],
    update: ['تحديث'],
    removebg: ['شفاف'],
    remini: ['تحسين'],
    sora: ['سورا']
};

const DISPLAY_COMMAND_ALIASES = {
    help: 'الأوامر',
    menu: 'الأوامر',
    bot: 'الأوامر',
    list: 'الأوامر',
    alive: 'حي',
    ping: 'بنج',
    owner: 'المالك',
    tts: 'تكلم',
    ban: 'حظر',
    unban: 'فك_الحظر',
    promote: 'ترقية',
    demote: 'تنزيل',
    mute: 'كتم',
    unmute: 'فك_الكتم',
    delete: 'حذف',
    del: 'حذف',
    sticker: 'ملصق',
    simage: 'صورة_الملصق',
    attp: 'ملصق_نص',
    settings: 'الإعدادات',
    mode: 'الوضع',
    anticall: 'منع_الاتصال',
    pmblocker: 'منع_الخاص',
    tagall: 'منشن_الكل',
    tagnotadmin: 'منشن_الأعضاء',
    hidetag: 'منشن_مخفي',
    tag: 'منشن',
    antilink: 'منع_الروابط',
    antitag: 'منع_المنشن',
    antibadword: 'منع_السب',
    weather: 'طقس',
    news: 'أخبار',
    tictactoe: 'اكس_او',
    ttt: 'اكس_او',
    guess: 'خمن',
    trivia: 'سؤال',
    answer: 'إجابة',
    warnings: 'تحذيرات',
    warn: 'تحذير',
    lyrics: 'كلمات',
    joke: 'نكتة',
    quote: 'اقتباس',
    fact: 'معلومة',
    kick: 'طرد',
    groupinfo: 'معلومات_القروب',
    staff: 'المشرفين',
    admins: 'المشرفين',
    chatbot: 'شاتبوت',
    resetlink: 'إعادة_الرابط',
    welcome: 'ترحيب',
    goodbye: 'وداع',
    clear: 'تنظيف',
    github: 'السورس',
    git: 'السورس',
    repo: 'السورس',
    sc: 'السورس',
    script: 'السورس',
    take: 'أخذ',
    flirt: 'مغازلة',
    character: 'شخصية',
    wasted: 'هلاك',
    waste: 'هلاك',
    ship: 'شيب',
    url: 'رابط',
    tourl: 'رابط',
    emojimix: 'دمج_إيموجي',
    tgsticker: 'ملصقات_تيليجرام',
    vv: 'فتح',
    clearsession: 'تنظيف_الجلسات',
    autostatus: 'حالة_تلقائية',
    truth: 'صراحة',
    dare: 'تحدي',
    setpp: 'صورة_البوت',
    setgdesc: 'وصف_القروب',
    setgname: 'اسم_القروب',
    setgpp: 'صورة_القروب',
    instagram: 'إنستا',
    igs: 'ستوري',
    igsc: 'إنستا_ميديا',
    facebook: 'فيسبوك',
    spotify: 'سبوتيفاي',
    play: 'شغل',
    song: 'أغنية',
    ytmp3: 'أغنية',
    mp3: 'أغنية',
    video: 'فيديو',
    ytmp4: 'يوتيوب_فيديو',
    tiktok: 'تيك_توك',
    tt: 'تيك_توك',
    ai: 'ذكاء',
    gpt: 'ذكاء',
    gemini: 'جيميني',
    translate: 'ترجمة',
    trt: 'ترجمة',
    ss: 'صورة_موقع',
    screenshot: 'صورة_موقع',
    autoreact: 'تفاعل_تلقائي',
    areact: 'تفاعل_تلقائي',
    sudo: 'سودو',
    goodnight: 'تصبح_على_خير',
    shayari: 'شعر',
    roseday: 'ورد',
    imagine: 'تخيل',
    flux: 'فلوكس',
    jid: 'معرف',
    autotyping: 'كتابة_تلقائية',
    autoread: 'قراءة_تلقائية',
    update: 'تحديث',
    removebg: 'شفاف',
    remini: 'تحسين',
    sora: 'سورا'
};

const INCOMING_COMMAND_ALIAS_TO_CANONICAL = Object.create(null);
for (const [canonical, aliases] of Object.entries(COMMAND_ALIASES)) {
    INCOMING_COMMAND_ALIAS_TO_CANONICAL[canonical] = canonical;
    for (const alias of aliases) {
        INCOMING_COMMAND_ALIAS_TO_CANONICAL[normalizeCommandToken(alias)] = canonical;
    }
}

const TEXTLIKE_KEYS = new Set([
    'text', 'caption', 'footer', 'title', 'description', 'displayText',
    'contentText', 'hydratedContentText', 'hydratedFooterText', 'buttonText'
]);
const translationCache = new Map();

function normalizeCommandToken(token = '') {
    return String(token || '')
        .trim()
        .toLowerCase()
        .replace(/[أإآ]/g, 'ا')
        .replace(/ى/g, 'ي')
        .replace(/ؤ/g, 'و')
        .replace(/ئ/g, 'ي')
        .replace(/[ً-ٰٟ]/g, '')
        .replace(/ـ/g, '');
}

function normalizeIncomingCommand(text = '') {
    const trimmed = String(text || '').replace(/\.\s+/g, '.').trim();
    if (!trimmed.startsWith('.')) return trimmed;
    const parts = trimmed.split(/\s+/);
    const rawCommand = String(parts.shift() || '').slice(1);
    const normalizedCommand = normalizeCommandToken(rawCommand);
    const canonical = INCOMING_COMMAND_ALIAS_TO_CANONICAL[normalizedCommand] || rawCommand.toLowerCase();
    return `.${canonical}${parts.length ? ` ${parts.join(' ')}` : ''}`.trim();
}

function localizeCommandMentions(text = '') {
    return String(text || '').replace(/(^|[\s(])\.([a-z0-9_-]+)/gi, (match, prefix, command) => {
        const replacement = DISPLAY_COMMAND_ALIASES[String(command || '').toLowerCase()];
        return `${prefix}.${replacement || command}`;
    });
}

function isChannelArtifact(text = '') {
    return /whatsapp\.com\/channel\//i.test(String(text || '')) || /عرض\s*القناة/i.test(String(text || ''));
}

function stripChannelPromotionsFromText(text = '') {
    const cleanedLines = String(text || '')
        .split('\n')
        .filter((line) => {
            const sample = String(line || '').trim();
            if (!sample) return true;
            if (/whatsapp\.com\/channel\//i.test(sample)) return false;
            if (/قناة واتساب الرسمية/i.test(sample)) return false;
            if (/عرض\s*القناة/i.test(sample)) return false;
            if (/اضغط.*القناة/i.test(sample)) return false;
            if (/فتح القناة/i.test(sample)) return false;
            return true;
        });
    return cleanedLines.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

function applyFallbackArabicReplacements(text = '') {
    let output = String(text || '');
    const replacements = [
        [/This command can only be used in groups!?/gi, 'هذا الأمر يعمل داخل المجموعات فقط.'],
        [/Please make the bot an admin to use admin commands\.?/gi, 'اجعل البوت مشرفاً لاستخدام أوامر الإدارة.'],
        [/Please make the bot an admin first\.?/gi, 'اجعل البوت مشرفاً أولاً.'],
        [/Sorry, only group admins can use this command\.?/gi, 'هذا الأمر للمشرفين فقط.'],
        [/Only admins or bot owner can use this command/gi, 'هذا الأمر للمشرفين أو مالك البوت فقط.'],
        [/Only bot owner can use this command!?/gi, 'هذا الأمر لمالك البوت فقط.'],
        [/Only owner\/sudo can use .*? in private chat\.?/gi, 'هذا الأمر متاح للمالك أو السودو فقط في الخاص.'],
        [/Only owner\/sudo can use anticall\.?/gi, 'هذا الأمر متاح للمالك أو السودو فقط.'],
        [/Private messages are blocked\. Please contact the owner in groups only\.?/gi, 'الرسائل الخاصة متوقفة. تواصل مع المالك من داخل المجموعات فقط.'],
        [/Please reply to a sticker with the \.simage command to convert it\./gi, 'قم بالرد على ملصق واستخدم أمر .صورة_الملصق لتحويله إلى صورة.'],
        [/Please provide a valid number of minutes or use \.mute with no number to mute immediately\./gi, 'اكتب عدد دقائق صحيح أو استخدم أمر .كتم بدون رقم للكتم مباشرة.'],
        [/Please specify a city, e\.g\.,/gi, 'اكتب اسم المدينة مثل'],
        [/Please provide a valid position number for Tic-Tac-Toe move\./gi, 'اكتب رقم خانة صحيح للعب اكس او.'],
        [/Please guess a letter using \.guess <letter>/gi, 'اكتب حرفاً باستخدام الأمر .خمن <حرف>'],
        [/Please provide an answer using \.answer <answer>/gi, 'اكتب الإجابة باستخدام الأمر .إجابة <نص>'],
        [/Bot must be admin to use this feature/gi, 'يجب أن يكون البوت مشرفاً لاستخدام هذه الميزة.'],
        [/Failed to read bot mode status/gi, 'تعذر قراءة حالة وضع البوت.'],
        [/Failed to update bot access mode/gi, 'تعذر تحديث وضع البوت.'],
        [/Failed to process command!?/gi, 'تعذر تنفيذ الأمر.'],
        [/Current bot mode:\s*\*(public|private)\*/gi, (_, mode) => `وضع البوت الحالي: *${String(mode).toLowerCase() === 'public' ? 'عام' : 'خاص'}*`],
        [/Usage:/gi, 'الاستخدام:'],
        [/Example:/gi, 'مثال:'],
        [/Allow everyone to use bot/gi, 'السماح للجميع باستخدام البوت'],
        [/Restrict to owner only/gi, 'قصر الاستخدام على المالك فقط'],
        [/Bot is now in \*(public|private)\* mode/gi, (_, mode) => `تم تغيير وضع البوت إلى *${String(mode).toLowerCase() === 'public' ? 'عام' : 'خاص'}*`],
        [/Online/gi, 'متصل'],
        [/Public/gi, 'عام'],
        [/Private/gi, 'خاص']
    ];
    for (const [pattern, replacement] of replacements) {
        output = output.replace(pattern, replacement);
    }
    return output;
}

function looksArabicEnough(text = '') {
    const sample = String(text || '');
    const arabicCount = (sample.match(/[؀-ۿ]/g) || []).length;
    const latinCount = (sample.match(/[A-Za-z]/g) || []).length;
    return arabicCount > 0 && latinCount < Math.max(12, arabicCount * 0.4);
}

async function translateOutgoingText(text = '') {
    const original = String(text || '');
    if (!original.trim()) return original;

    let prepared = stripChannelPromotionsFromText(localizeCommandMentions(original));
    prepared = applyFallbackArabicReplacements(prepared);
    if (!prepared.trim()) return '';
    if (looksArabicEnough(prepared) || !/[A-Za-z]{3,}/.test(prepared) || !translateGoogle) {
        return prepared;
    }

    if (translationCache.has(prepared)) {
        return translationCache.get(prepared);
    }

    try {
        const translated = await translateGoogle(prepared, { to: 'ar' });
        const resolved = Array.isArray(translated)
            ? translated.join(' ')
            : (translated?.text || translated?.translation || translated?.translatedText || translated);
        const finalText = String(resolved || prepared).trim() || prepared;
        translationCache.set(prepared, finalText);
        return finalText;
    } catch (_) {
        return prepared;
    }
}

async function sanitizeOutgoingNode(value, parentKey = '') {
    if (value == null) return value;
    if (Buffer.isBuffer(value) || value instanceof Uint8Array) return value;

    if (Array.isArray(value)) {
        const output = [];
        for (const item of value) {
            const sanitized = await sanitizeOutgoingNode(item, parentKey);
            if (sanitized !== null && sanitized !== undefined) {
                output.push(sanitized);
            }
        }
        return output;
    }

    if (typeof value === 'object') {
        if (value.urlButton) {
            const url = String(value.urlButton.url || '');
            const label = String(value.urlButton.displayText || '');
            if (isChannelArtifact(url) || /عرض\s*القناة/i.test(label)) {
                return null;
            }
            return {
                ...value,
                urlButton: {
                    ...value.urlButton,
                    displayText: await translateOutgoingText(label)
                }
            };
        }

        if (value.quickReplyButton) {
            return {
                ...value,
                quickReplyButton: {
                    ...value.quickReplyButton,
                    displayText: await translateOutgoingText(value.quickReplyButton.displayText || '')
                }
            };
        }

        const clone = {};
        for (const [key, entry] of Object.entries(value)) {
            if (key === 'contextInfo') continue;
            if ((key === 'url' || key === 'sourceUrl') && isChannelArtifact(entry)) continue;

            if (TEXTLIKE_KEYS.has(key) && typeof entry === 'string') {
                const localized = await translateOutgoingText(entry);
                if (localized) clone[key] = localized;
                continue;
            }

            const sanitized = await sanitizeOutgoingNode(entry, key);
            if (sanitized === null || sanitized === undefined) continue;
            if (Array.isArray(sanitized) && sanitized.length === 0 && ['templateButtons', 'buttons', 'sections'].includes(key)) continue;
            if (typeof sanitized === 'string' && !sanitized.trim() && ['text', 'caption', 'footer'].includes(key)) continue;
            clone[key] = sanitized;
        }
        return clone;
    }

    if (typeof value === 'string' && TEXTLIKE_KEYS.has(parentKey)) {
        return await translateOutgoingText(value);
    }

    return value;
}

function patchArabicOutgoingSock(sock) {
    if (!sock || sock.__arabicOutgoingPatched) return;
    const originalSendMessage = sock.sendMessage.bind(sock);
    sock.sendMessage = async (jid, content = {}, options = {}) => {
        const sanitizedContent = await sanitizeOutgoingNode(content);
        return originalSendMessage(jid, sanitizedContent, options);
    };
    sock.__arabicOutgoingPatched = true;
}

async function handleMessages(sock, messageUpdate, printLog) {
    try {
        const { messages, type } = messageUpdate;
        if (type !== 'notify') return;

        const message = messages[0];
        if (!message?.message) return;

        // Store message for antidelete feature
        if (message.message) {
            storeMessage(sock, message);
        }

        // Handle message revocation
        if (message.message?.protocolMessage?.type === 0) {
            await handleMessageRevocation(sock, message);
            return;
        }

        const chatId = message.key.remoteJid;
        const senderId = message.key.participant || message.key.remoteJid;
        const isGroup = chatId.endsWith('@g.us');
        const senderIsSudo = await isSudo(senderId);
        const senderIsOwnerOrSudo = await isOwnerOrSudo(senderId, sock, chatId);

        // Early PM blocker check: skip autoread for blocked PMs so single tick stays
        let skipAutoRead = false;
        if (!isGroup && !message.key.fromMe && !senderIsSudo) {
            try {
                const pmStateEarly = readPmBlockerState();
                if (pmStateEarly.enabled) {
                    skipAutoRead = true;
                }
            } catch (e) { }
        }

        // Handle autoread functionality (skip if PM blocker is active)
        if (!skipAutoRead) {
            await handleAutoread(sock, message);
        }
        patchArabicOutgoingSock(sock);

        // Handle button responses
        if (message.message?.buttonsResponseMessage) {
            const buttonId = message.message.buttonsResponseMessage.selectedButtonId;
            const chatId = message.key.remoteJid;

            if (buttonId === 'channel') {
                return;
            } else if (buttonId === 'owner') {
                const ownerCommand = require('./commands/owner');
                await ownerCommand(sock, chatId);
                return;
            } else if (buttonId === 'support') {
                await sock.sendMessage(chatId, {
                    text: `🔗 *Support*\n\nhttps://chat.whatsapp.com/GA4WrOFythU6g3BFVubYM7?mode=wwt`
                }, { quoted: message });
                return;
            }
        }

        const rawIncomingText = message.message?.conversation?.trim() ||
            message.message?.extendedTextMessage?.text?.trim() ||
            message.message?.imageMessage?.caption?.trim() ||
            message.message?.videoMessage?.caption?.trim() ||
            message.message?.buttonsResponseMessage?.selectedButtonId?.trim() ||
            '';

        // Normalize Arabic commands to internal command names while preserving arguments
        const rawText = normalizeIncomingCommand(rawIncomingText);
        const userMessage = rawText.toLowerCase().replace(/\.\s+/g, '.').trim();

        // Only log command usage
        if (userMessage.startsWith('.')) {
            console.log(`📝 Command used in ${isGroup ? 'group' : 'private'}: ${userMessage}`);
        }
        // Read bot mode once; don't early-return so moderation can still run in private mode
        let isPublic = true;
        try {
            const data = JSON.parse(fs.readFileSync('./data/messageCount.json'));
            if (typeof data.isPublic === 'boolean') isPublic = data.isPublic;
        } catch (error) {
            console.error('Error checking access mode:', error);
            // default isPublic=true on error
        }
        const isOwnerOrSudoCheck = message.key.fromMe || senderIsOwnerOrSudo;
        // Check if user is banned (skip ban check for unban command)
        if (isBanned(senderId) && !userMessage.startsWith('.unban')) {
            // Only respond occasionally to avoid spam
            if (Math.random() < 0.1) {
                await sock.sendMessage(chatId, {
                    text: '❌ You are banned from using the bot. Contact an admin to get unbanned.',
                    ...channelInfo
                });
            }
            return;
        }

        // First check if it's a game move
        if (/^[1-9]$/.test(userMessage) || userMessage.toLowerCase() === 'surrender' || userMessage === 'استسلام' || userMessage === 'انسحب') {
            await handleTicTacToeMove(sock, chatId, senderId, ['استسلام', 'انسحب'].includes(userMessage) ? 'surrender' : userMessage);
            return;
        }

        /*  // Basic message response in private chat
          if (!isGroup && (userMessage === 'hi' || userMessage === 'hello' || userMessage === 'bot' || userMessage === 'hlo' || userMessage === 'hey' || userMessage === 'bro')) {
              await sock.sendMessage(chatId, {
                  text: 'Hi, How can I help you?\nYou can use .menu for more info and commands.',
                  ...channelInfo
              });
              return;
          } */

        if (!message.key.fromMe) incrementMessageCount(chatId, senderId);

        // Check for bad words and antilink FIRST, before ANY other processing
        // Always run moderation in groups, regardless of mode
        if (isGroup) {
            if (userMessage) {
                await handleBadwordDetection(sock, chatId, message, userMessage, senderId);
            }
            // Antilink checks message text internally, so run it even if userMessage is empty
            await Antilink(message, sock);
        }

        // PM blocker: forward DMs to owner instead of blocking (no ban, single tick stays)
        if (!isGroup && !message.key.fromMe && !senderIsSudo) {
            try {
                const pmState = readPmBlockerState();
                if (pmState.enabled) {
                    // DO NOT read the message — leave a single tick (✓) at sender
                    // DO NOT block the number — sender can still see the conversation
                    // Forward the message content to the owner (linked number)
                    const ownerJid = settings.ownerNumber + '@s.whatsapp.net';
                    const senderPhone = chatId.split('@')[0];
                    const senderName = message?.pushName || senderPhone;

                    // Build forwarded text with sender info
                    let forwardText = `📨 *رسالة خاصة جديدة*

`; 
                    forwardText += `👤 المرسل: ${senderName}\n`;
                    forwardText += `📱 الرقم: ${senderPhone}\n`;
                    forwardText += `💬 الرسالة: ${rawIncomingText || '(رسالة غير نصية)'}\n`;
                    forwardText += `⏰ الوقت: ${new Date().toLocaleString('ar')}\n`;
                    forwardText += `\n_للرد على المرسل استخدم الأمر: .رد ${senderPhone} <رسالتك>_`;

                    try {
                        await sock.sendMessage(ownerJid, { text: forwardText });
                    } catch (fwdErr) {
                        console.error('PM Blocker forward error:', fwdErr.message);
                    }

                    // Send the warning message to sender (single tick stays, no block)
                    await sock.sendMessage(chatId, { text: pmState.message || 'Private messages are blocked. Please contact the owner in groups only.' });
                    return;
                }
            } catch (e) { }
        }

        // Then check for command prefix
        if (!userMessage.startsWith('.')) {
            // التحميل التلقائي لروابط السوشل ميديا
            if (/https?:\/\/(?:www\.)?(?:vt|vm)?\.?tiktok\.com\//i.test(rawText) || /https?:\/\/www\.tiktok\.com\/@/i.test(rawText)) {
                await tiktokCommand(sock, chatId, message);
                return;
            }

            if (/https?:\/\/(?:www\.)?(?:instagram\.com|instagr\.am)\//i.test(rawText)) {
                await instagramCommand(sock, chatId, message);
                return;
            }

            if (/https?:\/\/(?:www\.)?(?:facebook\.com|fb\.watch|m\.facebook\.com)\//i.test(rawText)) {
                await facebookCommand(sock, chatId, message);
                return;
            }

            // Show typing indicator if autotyping is enabled
            await handleAutotypingForMessage(sock, chatId, userMessage);

            if (isGroup) {
                // Always run moderation features (antitag) regardless of mode
                await handleTagDetection(sock, chatId, message, senderId);
                await handleMentionDetection(sock, chatId, message);

                // Only run chatbot in public mode or for owner/sudo
                if (isPublic || isOwnerOrSudoCheck) {
                    await handleChatbotResponse(sock, chatId, message, userMessage, senderId);
                }
            }
            return;
        }
        // In private mode, only owner/sudo can run commands
        if (!isPublic && !isOwnerOrSudoCheck) {
            return;
        }

        // List of admin commands
        const adminCommands = ['.mute', '.unmute', '.ban', '.unban', '.promote', '.demote', '.kick', '.tagall', '.tagnotadmin', '.hidetag', '.antilink', '.antitag', '.setgdesc', '.setgname', '.setgpp'];
        const isAdminCommand = adminCommands.some(cmd => userMessage.startsWith(cmd));

        // List of owner commands
        const ownerCommands = ['.mode', '.autostatus', '.antidelete', '.cleartmp', '.setpp', '.clearsession', '.areact', '.autoreact', '.autotyping', '.autoread', '.pmblocker'];
        const isOwnerCommand = ownerCommands.some(cmd => userMessage.startsWith(cmd));

        let isSenderAdmin = false;
        let isBotAdmin = false;

        // Check admin status only for admin commands in groups
        if (isGroup && isAdminCommand) {
            const adminStatus = await isAdmin(sock, chatId, senderId);
            isSenderAdmin = adminStatus.isSenderAdmin;
            isBotAdmin = adminStatus.isBotAdmin;

            if (!isBotAdmin) {
                await sock.sendMessage(chatId, { text: 'Please make the bot an admin to use admin commands.', ...channelInfo }, { quoted: message });
                return;
            }

            if (
                userMessage.startsWith('.mute') ||
                userMessage === '.unmute' ||
                userMessage.startsWith('.ban') ||
                userMessage.startsWith('.unban') ||
                userMessage.startsWith('.promote') ||
                userMessage.startsWith('.demote')
            ) {
                if (!isSenderAdmin && !message.key.fromMe) {
                    await sock.sendMessage(chatId, {
                        text: 'Sorry, only group admins can use this command.',
                        ...channelInfo
                    }, { quoted: message });
                    return;
                }
            }
        }

        // Check owner status for owner commands
        if (isOwnerCommand) {
            if (!message.key.fromMe && !senderIsOwnerOrSudo) {
                await sock.sendMessage(chatId, { text: '❌ This command is only available for the owner or sudo!' }, { quoted: message });
                return;
            }
        }

        // Command handlers - Execute commands immediately without waiting for typing indicator
        // We'll show typing indicator after command execution if needed
        let commandExecuted = false;

        // ─── PM Blocker reply command: .رد <number> <message> ───
        if (userMessage.startsWith('.رد ')) {
            if (!message.key.fromMe && !senderIsOwnerOrSudo) {
                await sock.sendMessage(chatId, { text: '❌ هذا الأمر للمالك فقط!' }, { quoted: message });
                return;
            }
            const replyParts = rawText.split(' '); // use rawText to preserve Arabic
            // .رد <number> <message...>
            const targetNumber = replyParts[1];
            const replyMsg = replyParts.slice(2).join(' ').trim();
            if (!targetNumber || !replyMsg) {
                await sock.sendMessage(chatId, { text: 'الاستخدام: .رد <الرقم> <رسالتك>\nمثال: .رد 919876543210 مرحبا' }, { quoted: message });
                return;
            }
            const targetJid = targetNumber.replace(/[^0-9]/g, '') + '@s.whatsapp.net';
            try {
                await sock.sendMessage(targetJid, { text: replyMsg });
                await sock.sendMessage(chatId, { text: `✅ تم إرسال ردك إلى ${targetNumber}` }, { quoted: message });
            } catch (replyErr) {
                await sock.sendMessage(chatId, { text: `❌ فشل إرسال الرد: ${replyErr.message}` }, { quoted: message });
            }
            return;
        }

        switch (true) {
            case userMessage === '.simage': {
                const quotedMessage = message.message?.extendedTextMessage?.contextInfo?.quotedMessage;
                if (quotedMessage?.stickerMessage) {
                    await simageCommand(sock, quotedMessage, chatId);
                } else {
                    await sock.sendMessage(chatId, { text: 'Please reply to a sticker with the .simage command to convert it.', ...channelInfo }, { quoted: message });
                }
                commandExecuted = true;
                break;
            }
            case userMessage.startsWith('.kick'):
                const mentionedJidListKick = message.message.extendedTextMessage?.contextInfo?.mentionedJid || [];
                await kickCommand(sock, chatId, senderId, mentionedJidListKick, message);
                break;
            case userMessage.startsWith('.mute'):
                {
                    const parts = userMessage.trim().split(/\s+/);
                    const muteArg = parts[1];
                    const muteDuration = muteArg !== undefined ? parseInt(muteArg, 10) : undefined;
                    if (muteArg !== undefined && (isNaN(muteDuration) || muteDuration <= 0)) {
                        await sock.sendMessage(chatId, { text: 'Please provide a valid number of minutes or use .mute with no number to mute immediately.', ...channelInfo }, { quoted: message });
                    } else {
                        await muteCommand(sock, chatId, senderId, message, muteDuration);
                    }
                }
                break;
            case userMessage === '.unmute':
                await unmuteCommand(sock, chatId, senderId);
                break;
            case userMessage.startsWith('.ban'):
                if (!isGroup) {
                    if (!message.key.fromMe && !senderIsSudo) {
                        await sock.sendMessage(chatId, { text: 'Only owner/sudo can use .ban in private chat.' }, { quoted: message });
                        break;
                    }
                }
                await banCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.unban'):
                if (!isGroup) {
                    if (!message.key.fromMe && !senderIsSudo) {
                        await sock.sendMessage(chatId, { text: 'Only owner/sudo can use .unban in private chat.' }, { quoted: message });
                        break;
                    }
                }
                await unbanCommand(sock, chatId, message);
                break;
            case userMessage === '.help' || userMessage === '.menu' || userMessage === '.bot' || userMessage === '.list':
                await helpCommand(sock, chatId, message, global.channelLink);
                commandExecuted = true;
                break;
            case userMessage === '.sticker' || userMessage === '.s':
                await stickerCommand(sock, chatId, message);
                commandExecuted = true;
                break;
            case userMessage.startsWith('.warnings'):
                const mentionedJidListWarnings = message.message.extendedTextMessage?.contextInfo?.mentionedJid || [];
                await warningsCommand(sock, chatId, mentionedJidListWarnings);
                break;
            case userMessage.startsWith('.warn'):
                const mentionedJidListWarn = message.message.extendedTextMessage?.contextInfo?.mentionedJid || [];
                await warnCommand(sock, chatId, senderId, mentionedJidListWarn, message);
                break;
            case userMessage.startsWith('.tts'):
                const text = userMessage.slice(4).trim();
                await ttsCommand(sock, chatId, text, message);
                break;
            case userMessage.startsWith('.delete') || userMessage.startsWith('.del'):
                await deleteCommand(sock, chatId, message, senderId);
                break;
            case userMessage.startsWith('.attp'):
                await attpCommand(sock, chatId, message);
                break;

            case userMessage === '.settings':
                await settingsCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.mode'):
                // Check if sender is the owner
                if (!message.key.fromMe && !senderIsOwnerOrSudo) {
                    await sock.sendMessage(chatId, { text: 'Only bot owner can use this command!', ...channelInfo }, { quoted: message });
                    return;
                }
                // Read current data first
                let data;
                try {
                    data = JSON.parse(fs.readFileSync('./data/messageCount.json'));
                } catch (error) {
                    console.error('Error reading access mode:', error);
                    await sock.sendMessage(chatId, { text: 'Failed to read bot mode status', ...channelInfo });
                    return;
                }

                const action = userMessage.split(' ')[1]?.toLowerCase();
                // If no argument provided, show current status
                if (!action) {
                    const currentMode = data.isPublic ? 'public' : 'private';
                    await sock.sendMessage(chatId, {
                        text: `Current bot mode: *${currentMode}*\n\nUsage: .mode public/private\n\nExample:\n.mode public - Allow everyone to use bot\n.mode private - Restrict to owner only`,
                        ...channelInfo
                    }, { quoted: message });
                    return;
                }

                if (action !== 'public' && action !== 'private') {
                    await sock.sendMessage(chatId, {
                        text: 'Usage: .mode public/private\n\nExample:\n.mode public - Allow everyone to use bot\n.mode private - Restrict to owner only',
                        ...channelInfo
                    }, { quoted: message });
                    return;
                }

                try {
                    // Update access mode
                    data.isPublic = action === 'public';

                    // Save updated data
                    fs.writeFileSync('./data/messageCount.json', JSON.stringify(data, null, 2));

                    await sock.sendMessage(chatId, { text: `Bot is now in *${action}* mode`, ...channelInfo });
                } catch (error) {
                    console.error('Error updating access mode:', error);
                    await sock.sendMessage(chatId, { text: 'Failed to update bot access mode', ...channelInfo });
                }
                break;
            case userMessage.startsWith('.anticall'):
                if (!message.key.fromMe && !senderIsOwnerOrSudo) {
                    await sock.sendMessage(chatId, { text: 'Only owner/sudo can use anticall.' }, { quoted: message });
                    break;
                }
                {
                    const args = userMessage.split(' ').slice(1).join(' ');
                    await anticallCommand(sock, chatId, message, args);
                }
                break;
            case userMessage.startsWith('.pmblocker'):
                {
                    const args = userMessage.split(' ').slice(1).join(' ');
                    await pmblockerCommand(sock, chatId, message, args);
                }
                commandExecuted = true;
                break;
            case userMessage === '.owner':
                await ownerCommand(sock, chatId);
                break;
            case userMessage === '.tagall':
                await tagAllCommand(sock, chatId, senderId, message);
                break;
            case userMessage === '.tagnotadmin':
                await tagNotAdminCommand(sock, chatId, senderId, message);
                break;
            case userMessage.startsWith('.hidetag'):
                {
                    const messageText = rawText.slice(8).trim();
                    const replyMessage = message.message?.extendedTextMessage?.contextInfo?.quotedMessage || null;
                    await hideTagCommand(sock, chatId, senderId, messageText, replyMessage, message);
                }
                break;
            case userMessage.startsWith('.tag'):
                const messageText = rawText.slice(4).trim();  // use rawText here, not userMessage
                const replyMessage = message.message?.extendedTextMessage?.contextInfo?.quotedMessage || null;
                await tagCommand(sock, chatId, senderId, messageText, replyMessage, message);
                break;
            case userMessage.startsWith('.antilink'):
                if (!isGroup) {
                    await sock.sendMessage(chatId, {
                        text: 'This command can only be used in groups.',
                        ...channelInfo
                    }, { quoted: message });
                    return;
                }
                if (!isBotAdmin) {
                    await sock.sendMessage(chatId, {
                        text: 'Please make the bot an admin first.',
                        ...channelInfo
                    }, { quoted: message });
                    return;
                }
                await handleAntilinkCommand(sock, chatId, userMessage, senderId, isSenderAdmin, message);
                break;
            case userMessage.startsWith('.antitag'):
                if (!isGroup) {
                    await sock.sendMessage(chatId, {
                        text: 'This command can only be used in groups.',
                        ...channelInfo
                    }, { quoted: message });
                    return;
                }
                if (!isBotAdmin) {
                    await sock.sendMessage(chatId, {
                        text: 'Please make the bot an admin first.',
                        ...channelInfo
                    }, { quoted: message });
                    return;
                }
                await handleAntitagCommand(sock, chatId, userMessage, senderId, isSenderAdmin, message);
                break;
            case userMessage === '.meme':
                await memeCommand(sock, chatId, message);
                break;
            case userMessage === '.joke':
                await jokeCommand(sock, chatId, message);
                break;
            case userMessage === '.quote':
                await quoteCommand(sock, chatId, message);
                break;
            case userMessage === '.fact':
                await factCommand(sock, chatId, message, message);
                break;
            case userMessage.startsWith('.weather'):
                const city = userMessage.slice(9).trim();
                if (city) {
                    await weatherCommand(sock, chatId, message, city);
                } else {
                    await sock.sendMessage(chatId, { text: 'Please specify a city, e.g., .weather London', ...channelInfo }, { quoted: message });
                }
                break;
            case userMessage === '.news':
                await newsCommand(sock, chatId);
                break;
            case userMessage.startsWith('.ttt') || userMessage.startsWith('.tictactoe'):
                const tttText = userMessage.split(' ').slice(1).join(' ');
                await tictactoeCommand(sock, chatId, senderId, tttText);
                break;
            case userMessage.startsWith('.move'):
                const position = parseInt(userMessage.split(' ')[1]);
                if (isNaN(position)) {
                    await sock.sendMessage(chatId, { text: 'Please provide a valid position number for Tic-Tac-Toe move.', ...channelInfo }, { quoted: message });
                } else {
                    tictactoeMove(sock, chatId, senderId, position);
                }
                break;
            case userMessage === '.topmembers':
                topMembers(sock, chatId, isGroup);
                break;
            case userMessage.startsWith('.hangman'):
                startHangman(sock, chatId);
                break;
            case userMessage.startsWith('.guess'):
                const guessedLetter = userMessage.split(' ')[1];
                if (guessedLetter) {
                    guessLetter(sock, chatId, guessedLetter);
                } else {
                    sock.sendMessage(chatId, { text: 'Please guess a letter using .guess <letter>', ...channelInfo }, { quoted: message });
                }
                break;
            case userMessage.startsWith('.trivia'):
                startTrivia(sock, chatId);
                break;
            case userMessage.startsWith('.answer'):
                const answer = userMessage.split(' ').slice(1).join(' ');
                if (answer) {
                    answerTrivia(sock, chatId, answer);
                } else {
                    sock.sendMessage(chatId, { text: 'Please provide an answer using .answer <answer>', ...channelInfo }, { quoted: message });
                }
                break;
            case userMessage.startsWith('.compliment'):
                await complimentCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.insult'):
                await insultCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.8ball'):
                const question = userMessage.split(' ').slice(1).join(' ');
                await eightBallCommand(sock, chatId, question);
                break;
            case userMessage.startsWith('.lyrics'):
                const songTitle = userMessage.split(' ').slice(1).join(' ');
                await lyricsCommand(sock, chatId, songTitle, message);
                break;
            case userMessage.startsWith('.simp'):
                const quotedMsg = message.message?.extendedTextMessage?.contextInfo?.quotedMessage;
                const mentionedJid = message.message?.extendedTextMessage?.contextInfo?.mentionedJid || [];
                await simpCommand(sock, chatId, quotedMsg, mentionedJid, senderId);
                break;
            case userMessage.startsWith('.stupid') || userMessage.startsWith('.itssostupid') || userMessage.startsWith('.iss'):
                const stupidQuotedMsg = message.message?.extendedTextMessage?.contextInfo?.quotedMessage;
                const stupidMentionedJid = message.message?.extendedTextMessage?.contextInfo?.mentionedJid || [];
                const stupidArgs = userMessage.split(' ').slice(1);
                await stupidCommand(sock, chatId, stupidQuotedMsg, stupidMentionedJid, senderId, stupidArgs);
                break;
            case userMessage === '.dare':
                await dareCommand(sock, chatId, message);
                break;
            case userMessage === '.truth':
                await truthCommand(sock, chatId, message);
                break;
            case userMessage === '.clear':
                if (isGroup) await clearCommand(sock, chatId);
                break;
            case userMessage.startsWith('.promote'):
                const mentionedJidListPromote = message.message.extendedTextMessage?.contextInfo?.mentionedJid || [];
                await promoteCommand(sock, chatId, mentionedJidListPromote, message);
                break;
            case userMessage.startsWith('.demote'):
                const mentionedJidListDemote = message.message.extendedTextMessage?.contextInfo?.mentionedJid || [];
                await demoteCommand(sock, chatId, mentionedJidListDemote, message);
                break;
            case userMessage === '.ping':
                await pingCommand(sock, chatId, message);
                break;
            case userMessage === '.alive':
                await aliveCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.mention '):
                {
                    const args = userMessage.split(' ').slice(1).join(' ');
                    const isOwner = message.key.fromMe || senderIsSudo;
                    await mentionToggleCommand(sock, chatId, message, args, isOwner);
                }
                break;
            case userMessage === '.setmention':
                {
                    const isOwner = message.key.fromMe || senderIsSudo;
                    await setMentionCommand(sock, chatId, message, isOwner);
                }
                break;
            case userMessage.startsWith('.blur'):
                const quotedMessage = message.message?.extendedTextMessage?.contextInfo?.quotedMessage;
                await blurCommand(sock, chatId, message, quotedMessage);
                break;
            case userMessage.startsWith('.welcome'):
                if (isGroup) {
                    // Check admin status if not already checked
                    if (!isSenderAdmin) {
                        const adminStatus = await isAdmin(sock, chatId, senderId);
                        isSenderAdmin = adminStatus.isSenderAdmin;
                    }

                    if (isSenderAdmin || message.key.fromMe) {
                        await welcomeCommand(sock, chatId, message);
                    } else {
                        await sock.sendMessage(chatId, { text: 'Sorry, only group admins can use this command.', ...channelInfo }, { quoted: message });
                    }
                } else {
                    await sock.sendMessage(chatId, { text: 'This command can only be used in groups.', ...channelInfo }, { quoted: message });
                }
                break;
            case userMessage.startsWith('.goodbye'):
                if (isGroup) {
                    // Check admin status if not already checked
                    if (!isSenderAdmin) {
                        const adminStatus = await isAdmin(sock, chatId, senderId);
                        isSenderAdmin = adminStatus.isSenderAdmin;
                    }

                    if (isSenderAdmin || message.key.fromMe) {
                        await goodbyeCommand(sock, chatId, message);
                    } else {
                        await sock.sendMessage(chatId, { text: 'Sorry, only group admins can use this command.', ...channelInfo }, { quoted: message });
                    }
                } else {
                    await sock.sendMessage(chatId, { text: 'This command can only be used in groups.', ...channelInfo }, { quoted: message });
                }
                break;
            case userMessage === '.git':
            case userMessage === '.github':
            case userMessage === '.sc':
            case userMessage === '.script':
            case userMessage === '.repo':
                await githubCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.antibadword'):
                if (!isGroup) {
                    await sock.sendMessage(chatId, { text: 'This command can only be used in groups.', ...channelInfo }, { quoted: message });
                    return;
                }

                const adminStatus = await isAdmin(sock, chatId, senderId);
                isSenderAdmin = adminStatus.isSenderAdmin;
                isBotAdmin = adminStatus.isBotAdmin;

                if (!isBotAdmin) {
                    await sock.sendMessage(chatId, { text: '*Bot must be admin to use this feature*', ...channelInfo }, { quoted: message });
                    return;
                }

                await antibadwordCommand(sock, chatId, message, senderId, isSenderAdmin);
                break;
            case userMessage.startsWith('.chatbot'):
                if (!isGroup) {
                    await sock.sendMessage(chatId, { text: 'This command can only be used in groups.', ...channelInfo }, { quoted: message });
                    return;
                }

                // Check if sender is admin or bot owner
                const chatbotAdminStatus = await isAdmin(sock, chatId, senderId);
                if (!chatbotAdminStatus.isSenderAdmin && !message.key.fromMe) {
                    await sock.sendMessage(chatId, { text: '*Only admins or bot owner can use this command*', ...channelInfo }, { quoted: message });
                    return;
                }

                const match = userMessage.slice(8).trim();
                await handleChatbotCommand(sock, chatId, message, match);
                break;
            case userMessage.startsWith('.take') || userMessage.startsWith('.steal'):
                {
                    const isSteal = userMessage.startsWith('.steal');
                    const sliceLen = isSteal ? 6 : 5; // '.steal' vs '.take'
                    const takeArgs = rawText.slice(sliceLen).trim().split(' ');
                    await takeCommand(sock, chatId, message, takeArgs);
                }
                break;
            case userMessage === '.flirt':
                await flirtCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.character'):
                await characterCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.waste'):
                await wastedCommand(sock, chatId, message);
                break;
            case userMessage === '.ship':
                if (!isGroup) {
                    await sock.sendMessage(chatId, { text: 'This command can only be used in groups!', ...channelInfo }, { quoted: message });
                    return;
                }
                await shipCommand(sock, chatId, message);
                break;
            case userMessage === '.groupinfo' || userMessage === '.infogp' || userMessage === '.infogrupo':
                if (!isGroup) {
                    await sock.sendMessage(chatId, { text: 'This command can only be used in groups!', ...channelInfo }, { quoted: message });
                    return;
                }
                await groupInfoCommand(sock, chatId, message);
                break;
            case userMessage === '.resetlink' || userMessage === '.revoke' || userMessage === '.anularlink':
                if (!isGroup) {
                    await sock.sendMessage(chatId, { text: 'This command can only be used in groups!', ...channelInfo }, { quoted: message });
                    return;
                }
                await resetlinkCommand(sock, chatId, senderId);
                break;
            case userMessage === '.staff' || userMessage === '.admins' || userMessage === '.listadmin':
                if (!isGroup) {
                    await sock.sendMessage(chatId, { text: 'This command can only be used in groups!', ...channelInfo }, { quoted: message });
                    return;
                }
                await staffCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.tourl') || userMessage.startsWith('.url'):
                await urlCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.emojimix') || userMessage.startsWith('.emix'):
                await emojimixCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.tg') || userMessage.startsWith('.stickertelegram') || userMessage.startsWith('.tgsticker') || userMessage.startsWith('.telesticker'):
                await stickerTelegramCommand(sock, chatId, message);
                break;

            case userMessage === '.vv':
                await viewOnceCommand(sock, chatId, message);
                break;
            case userMessage === '.clearsession' || userMessage === '.clearsesi':
                await clearSessionCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.autostatus'):
                const autoStatusArgs = userMessage.split(' ').slice(1);
                await autoStatusCommand(sock, chatId, message, autoStatusArgs);
                break;
            case userMessage.startsWith('.simp'):
                await simpCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.metallic'):
                await textmakerCommand(sock, chatId, message, userMessage, 'metallic');
                break;
            case userMessage.startsWith('.ice'):
                await textmakerCommand(sock, chatId, message, userMessage, 'ice');
                break;
            case userMessage.startsWith('.snow'):
                await textmakerCommand(sock, chatId, message, userMessage, 'snow');
                break;
            case userMessage.startsWith('.impressive'):
                await textmakerCommand(sock, chatId, message, userMessage, 'impressive');
                break;
            case userMessage.startsWith('.matrix'):
                await textmakerCommand(sock, chatId, message, userMessage, 'matrix');
                break;
            case userMessage.startsWith('.light'):
                await textmakerCommand(sock, chatId, message, userMessage, 'light');
                break;
            case userMessage.startsWith('.neon'):
                await textmakerCommand(sock, chatId, message, userMessage, 'neon');
                break;
            case userMessage.startsWith('.devil'):
                await textmakerCommand(sock, chatId, message, userMessage, 'devil');
                break;
            case userMessage.startsWith('.purple'):
                await textmakerCommand(sock, chatId, message, userMessage, 'purple');
                break;
            case userMessage.startsWith('.thunder'):
                await textmakerCommand(sock, chatId, message, userMessage, 'thunder');
                break;
            case userMessage.startsWith('.leaves'):
                await textmakerCommand(sock, chatId, message, userMessage, 'leaves');
                break;
            case userMessage.startsWith('.1917'):
                await textmakerCommand(sock, chatId, message, userMessage, '1917');
                break;
            case userMessage.startsWith('.arena'):
                await textmakerCommand(sock, chatId, message, userMessage, 'arena');
                break;
            case userMessage.startsWith('.hacker'):
                await textmakerCommand(sock, chatId, message, userMessage, 'hacker');
                break;
            case userMessage.startsWith('.sand'):
                await textmakerCommand(sock, chatId, message, userMessage, 'sand');
                break;
            case userMessage.startsWith('.blackpink'):
                await textmakerCommand(sock, chatId, message, userMessage, 'blackpink');
                break;
            case userMessage.startsWith('.glitch'):
                await textmakerCommand(sock, chatId, message, userMessage, 'glitch');
                break;
            case userMessage.startsWith('.fire'):
                await textmakerCommand(sock, chatId, message, userMessage, 'fire');
                break;
            case userMessage.startsWith('.antidelete'):
                const antideleteMatch = userMessage.slice(11).trim();
                await handleAntideleteCommand(sock, chatId, message, antideleteMatch);
                break;
            case userMessage === '.surrender' || userMessage === 'استسلام' || userMessage === 'انسحب':
                // Handle surrender command for tictactoe game
                await handleTicTacToeMove(sock, chatId, senderId, 'surrender');
                break;
            case userMessage === '.cleartmp':
                await clearTmpCommand(sock, chatId, message);
                break;
            case userMessage === '.setpp':
                await setProfilePicture(sock, chatId, message);
                break;
            case userMessage.startsWith('.setgdesc'):
                {
                    const text = rawText.slice(9).trim();
                    await setGroupDescription(sock, chatId, senderId, text, message);
                }
                break;
            case userMessage.startsWith('.setgname'):
                {
                    const text = rawText.slice(9).trim();
                    await setGroupName(sock, chatId, senderId, text, message);
                }
                break;
            case userMessage.startsWith('.setgpp'):
                await setGroupPhoto(sock, chatId, senderId, message);
                break;
            case userMessage.startsWith('.instagram') || userMessage.startsWith('.insta') || (userMessage === '.ig' || userMessage.startsWith('.ig ')):
                await instagramCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.igsc'):
                await igsCommand(sock, chatId, message, true);
                break;
            case userMessage.startsWith('.igs'):
                await igsCommand(sock, chatId, message, false);
                break;
            case userMessage.startsWith('.fb') || userMessage.startsWith('.facebook'):
                await facebookCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.music'):
                await playCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.spotify'):
                await spotifyCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.play') || userMessage.startsWith('.mp3') || userMessage.startsWith('.ytmp3') || userMessage.startsWith('.song'):
                await songCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.video') || userMessage.startsWith('.ytmp4'):
                await videoCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.tiktok') || userMessage.startsWith('.tt'):
                await tiktokCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.gpt') || userMessage.startsWith('.gemini') || userMessage.startsWith('.ai'):
                await aiCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.translate') || userMessage.startsWith('.trt'):
                const commandLength = userMessage.startsWith('.translate') ? 10 : 4;
                await handleTranslateCommand(sock, chatId, message, userMessage.slice(commandLength));
                return;
            case userMessage.startsWith('.ss') || userMessage.startsWith('.ssweb') || userMessage.startsWith('.screenshot'):
                const ssCommandLength = userMessage.startsWith('.screenshot') ? 11 : (userMessage.startsWith('.ssweb') ? 6 : 3);
                await handleSsCommand(sock, chatId, message, userMessage.slice(ssCommandLength).trim());
                break;
            case userMessage.startsWith('.areact') || userMessage.startsWith('.autoreact') || userMessage.startsWith('.autoreaction'):
                await handleAreactCommand(sock, chatId, message, isOwnerOrSudoCheck);
                break;
            case userMessage.startsWith('.sudo'):
                await sudoCommand(sock, chatId, message);
                break;
            case userMessage === '.goodnight' || userMessage === '.lovenight' || userMessage === '.gn':
                await goodnightCommand(sock, chatId, message);
                break;
            case userMessage === '.shayari' || userMessage === '.shayri':
                await shayariCommand(sock, chatId, message);
                break;
            case userMessage === '.roseday':
                await rosedayCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.imagine') || userMessage.startsWith('.flux') || userMessage.startsWith('.dalle'): await imagineCommand(sock, chatId, message);
                break;
            case userMessage === '.jid': await groupJidCommand(sock, chatId, message);
                break;
            case userMessage.startsWith('.autotyping'):
                await autotypingCommand(sock, chatId, message);
                commandExecuted = true;
                break;
            case userMessage.startsWith('.autoread'):
                await autoreadCommand(sock, chatId, message);
                commandExecuted = true;
                break;
            case userMessage.startsWith('.heart'):
                await handleHeart(sock, chatId, message);
                break;
            case userMessage.startsWith('.horny'):
                {
                    const parts = userMessage.trim().split(/\s+/);
                    const args = ['horny', ...parts.slice(1)];
                    await miscCommand(sock, chatId, message, args);
                }
                break;
            case userMessage.startsWith('.circle'):
                {
                    const parts = userMessage.trim().split(/\s+/);
                    const args = ['circle', ...parts.slice(1)];
                    await miscCommand(sock, chatId, message, args);
                }
                break;
            case userMessage.startsWith('.lgbt'):
                {
                    const parts = userMessage.trim().split(/\s+/);
                    const args = ['lgbt', ...parts.slice(1)];
                    await miscCommand(sock, chatId, message, args);
                }
                break;
            case userMessage.startsWith('.lolice'):
                {
                    const parts = userMessage.trim().split(/\s+/);
                    const args = ['lolice', ...parts.slice(1)];
                    await miscCommand(sock, chatId, message, args);
                }
                break;
            case userMessage.startsWith('.simpcard'):
                {
                    const parts = userMessage.trim().split(/\s+/);
                    const args = ['simpcard', ...parts.slice(1)];
                    await miscCommand(sock, chatId, message, args);
                }
                break;
            case userMessage.startsWith('.tonikawa'):
                {
                    const parts = userMessage.trim().split(/\s+/);
                    const args = ['tonikawa', ...parts.slice(1)];
                    await miscCommand(sock, chatId, message, args);
                }
                break;
            case userMessage.startsWith('.its-so-stupid'):
                {
                    const parts = userMessage.trim().split(/\s+/);
                    const args = ['its-so-stupid', ...parts.slice(1)];
                    await miscCommand(sock, chatId, message, args);
                }
                break;
            case userMessage.startsWith('.namecard'):
                {
                    const parts = userMessage.trim().split(/\s+/);
                    const args = ['namecard', ...parts.slice(1)];
                    await miscCommand(sock, chatId, message, args);
                }
                break;

            case userMessage.startsWith('.oogway2'):
            case userMessage.startsWith('.oogway'):
                {
                    const parts = userMessage.trim().split(/\s+/);
                    const sub = userMessage.startsWith('.oogway2') ? 'oogway2' : 'oogway';
                    const args = [sub, ...parts.slice(1)];
                    await miscCommand(sock, chatId, message, args);
                }
                break;
            case userMessage.startsWith('.tweet'):
                {
                    const parts = userMessage.trim().split(/\s+/);
                    const args = ['tweet', ...parts.slice(1)];
                    await miscCommand(sock, chatId, message, args);
                }
                break;
            case userMessage.startsWith('.ytcomment'):
                {
                    const parts = userMessage.trim().split(/\s+/);
                    const args = ['youtube-comment', ...parts.slice(1)];
                    await miscCommand(sock, chatId, message, args);
                }
                break;
            case userMessage.startsWith('.comrade'):
            case userMessage.startsWith('.gay'):
            case userMessage.startsWith('.glass'):
            case userMessage.startsWith('.jail'):
            case userMessage.startsWith('.passed'):
            case userMessage.startsWith('.triggered'):
                {
                    const parts = userMessage.trim().split(/\s+/);
                    const sub = userMessage.slice(1).split(/\s+/)[0];
                    const args = [sub, ...parts.slice(1)];
                    await miscCommand(sock, chatId, message, args);
                }
                break;
            case userMessage.startsWith('.animu'):
                {
                    const parts = userMessage.trim().split(/\s+/);
                    const args = parts.slice(1);
                    await animeCommand(sock, chatId, message, args);
                }
                break;
            // animu aliases
            case userMessage.startsWith('.nom'):
            case userMessage.startsWith('.poke'):
            case userMessage.startsWith('.cry'):
            case userMessage.startsWith('.kiss'):
            case userMessage.startsWith('.pat'):
            case userMessage.startsWith('.hug'):
            case userMessage.startsWith('.wink'):
            case userMessage.startsWith('.facepalm'):
            case userMessage.startsWith('.face-palm'):
            case userMessage.startsWith('.animuquote'):
            case userMessage.startsWith('.quote'):
            case userMessage.startsWith('.loli'):
                {
                    const parts = userMessage.trim().split(/\s+/);
                    let sub = parts[0].slice(1);
                    if (sub === 'facepalm') sub = 'face-palm';
                    if (sub === 'quote' || sub === 'animuquote') sub = 'quote';
                    await animeCommand(sock, chatId, message, [sub]);
                }
                break;
            case userMessage === '.crop':
                await stickercropCommand(sock, chatId, message);
                commandExecuted = true;
                break;
            case userMessage.startsWith('.pies'):
                {
                    const parts = rawText.trim().split(/\s+/);
                    const args = parts.slice(1);
                    await piesCommand(sock, chatId, message, args);
                    commandExecuted = true;
                }
                break;
            case userMessage === '.china':
                await piesAlias(sock, chatId, message, 'china');
                commandExecuted = true;
                break;
            case userMessage === '.indonesia':
                await piesAlias(sock, chatId, message, 'indonesia');
                commandExecuted = true;
                break;
            case userMessage === '.japan':
                await piesAlias(sock, chatId, message, 'japan');
                commandExecuted = true;
                break;
            case userMessage === '.korea':
                await piesAlias(sock, chatId, message, 'korea');
                commandExecuted = true;
                break;
            case userMessage === '.india':
                await piesAlias(sock, chatId, message, 'india');
                commandExecuted = true;
                break;
            case userMessage === '.malaysia':
                await piesAlias(sock, chatId, message, 'malaysia');
                commandExecuted = true;
                break;
            case userMessage === '.thailand':
                await piesAlias(sock, chatId, message, 'thailand');
                commandExecuted = true;
                break;
            case userMessage.startsWith('.update'):
                {
                    const parts = rawText.trim().split(/\s+/);
                    const zipArg = parts[1] && parts[1].startsWith('http') ? parts[1] : '';
                    await updateCommand(sock, chatId, message, zipArg);
                }
                commandExecuted = true;
                break;
            case userMessage.startsWith('.removebg') || userMessage.startsWith('.rmbg') || userMessage.startsWith('.nobg'):
                await removebgCommand.exec(sock, message, userMessage.split(' ').slice(1));
                break;
            case userMessage.startsWith('.remini') || userMessage.startsWith('.enhance') || userMessage.startsWith('.upscale'):
                await reminiCommand(sock, chatId, message, userMessage.split(' ').slice(1));
                break;
            case userMessage.startsWith('.sora'):
                await soraCommand(sock, chatId, message);
                break;
            default:
                if (isGroup) {
                    // Handle non-command group messages
                    if (userMessage) {  // Make sure there's a message
                        await handleChatbotResponse(sock, chatId, message, userMessage, senderId);
                    }
                    await handleTagDetection(sock, chatId, message, senderId);
                    await handleMentionDetection(sock, chatId, message);
                }
                commandExecuted = false;
                break;
        }

        // If a command was executed, show typing status after command execution
        if (commandExecuted !== false) {
            // Command was executed, now show typing status after command execution
            await showTypingAfterCommand(sock, chatId);
        }

        // Function to handle .groupjid command
        async function groupJidCommand(sock, chatId, message) {
            const groupJid = message.key.remoteJid;

            if (!groupJid.endsWith('@g.us')) {
                return await sock.sendMessage(chatId, {
                    text: "❌ This command can only be used in a group."
                });
            }

            await sock.sendMessage(chatId, {
                text: `✅ Group JID: ${groupJid}`
            }, {
                quoted: message
            });
        }

        if (userMessage.startsWith('.')) {
            // After command is processed successfully
            await addCommandReaction(sock, message);
        }
    } catch (error) {
        console.error('❌ Error in message handler:', error.message);
        // Only try to send error message if we have a valid chatId
        if (chatId) {
            await sock.sendMessage(chatId, {
                text: '❌ Failed to process command!',
                ...channelInfo
            });
        }
    }
}

async function handleGroupParticipantUpdate(sock, update) {
    try {
        const { id, participants, action, author } = update;

        // Check if it's a group
        if (!id.endsWith('@g.us')) return;

        // Respect bot mode: only announce promote/demote in public mode
        let isPublic = true;
        try {
            const modeData = JSON.parse(fs.readFileSync('./data/messageCount.json'));
            if (typeof modeData.isPublic === 'boolean') isPublic = modeData.isPublic;
        } catch (e) {
            // If reading fails, default to public behavior
        }

        // Handle promotion events
        if (action === 'promote') {
            if (!isPublic) return;
            await handlePromotionEvent(sock, id, participants, author);
            return;
        }

        // Handle demotion events
        if (action === 'demote') {
            if (!isPublic) return;
            await handleDemotionEvent(sock, id, participants, author);
            return;
        }

        // Handle join events
        if (action === 'add') {
            await handleJoinEvent(sock, id, participants);
        }

        // Handle leave events
        if (action === 'remove') {
            await handleLeaveEvent(sock, id, participants);
        }
    } catch (error) {
        console.error('Error in handleGroupParticipantUpdate:', error);
    }
}

// Instead, export the handlers along with handleMessages
module.exports = {
    handleMessages,
    handleGroupParticipantUpdate,
    handleStatus: async (sock, status) => {
        await handleStatusUpdate(sock, status);
    }
};
