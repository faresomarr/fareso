let started = false;

function startTelegramPairBot() {
  if (started) return true;
  started = true;

  const enabled = String(process.env.ENABLE_TELEGRAM_PAIR_BOT || '').toLowerCase() === 'true';
  if (!enabled) {
    console.log('ℹ️ Telegram pair bot is disabled. Set ENABLE_TELEGRAM_PAIR_BOT=true to enable it.');
    return false;
  }

  const token = process.env.TELEGRAM_BOT_TOKEN;
  const developerId = process.env.TELEGRAM_DEVELOPER_ID;

  if (!token || !developerId) {
    console.log('⚠️ Telegram pair bot not started: missing TELEGRAM_BOT_TOKEN or TELEGRAM_DEVELOPER_ID.');
    return false;
  }

  console.log('✅ Telegram pair bot configuration detected. Service bootstrap completed.');
  console.log('ℹ️ If you need Telegram polling/webhook logic, add it inside lib/telegramPairBot.js.');
  return true;
}

module.exports = {
  startTelegramPairBot,
};
