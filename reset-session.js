require('dotenv').config();

const fs = require('fs');
const path = require('path');
const { listRemoteSessions } = require('./lib/remoteSessionStore');
const { clearMongoSessionAuthFiles } = require('./mongo-auth');

const projectRoot = process.cwd();
const sessionStoreFile = path.join(projectRoot, 'data', 'session-store.json');

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function normalizePhone(value = '') {
  return String(value || '').replace(/\D/g, '').trim();
}

function readJson(filePath, fallback) {
  try {
    if (!fs.existsSync(filePath)) return fallback;
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (_) {
    return fallback;
  }
}

function writeJson(filePath, data) {
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
}

async function main() {
  const requestedPhone = normalizePhone(process.env.PHONE || process.argv[2] || '');
  const db = readJson(sessionStoreFile, { sessions: {} });

  const remoteSessions = await listRemoteSessions().catch(() => []);
  const targets = requestedPhone
    ? [requestedPhone]
    : remoteSessions.map((entry) => normalizePhone(entry?.phone || entry?.sessionId || '')).filter(Boolean);

  let removedTotal = 0;

  for (const phone of targets) {
    removedTotal += clearMongoSessionAuthFiles(phone, {
      preserveSessionMeta: true,
      ownerId: String(db.sessions?.[phone]?.ownerId || '').trim(),
      lastConnectedAt: db.sessions?.[phone]?.lastConnectedAt || null
    });

    const current = db.sessions[phone] || {};
    db.sessions[phone] = {
      ...current,
      phone,
      sessionId: phone,
      registered: false,
      updatedAt: new Date().toISOString(),
      fileCount: 0,
      lastConnectedAt: current.lastConnectedAt || null
    };
  }

  writeJson(sessionStoreFile, db);
  console.log(`session reset complete: removed ${removedTotal} auth record(s) from MongoDB session store`);
}

main().catch((error) => {
  console.error('session reset failed:', error?.message || error);
  process.exit(1);
});
