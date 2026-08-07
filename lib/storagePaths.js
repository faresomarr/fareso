'use strict';

const path = require('path');

const ENABLE_PERSISTENT_LOCAL_STORAGE = ['1', 'true', 'yes', 'on'].includes(
  String(process.env.ENABLE_PERSISTENT_LOCAL_STORAGE || 'true').trim().toLowerCase()
);

function computeStorageRoot() {
  const projectRoot = process.cwd();
  const runtimeRoot = path.join(projectRoot, '.runtime');
  const candidates = [
    process.env.BOT_STORAGE_ROOT,
    process.env.RAILWAY_VOLUME_MOUNT_PATH,
    process.env.RAILWAY_PERSISTENT_DIR,
    process.env.RENDER_DISK_MOUNT_PATH,
    projectRoot,
    runtimeRoot,
  ].map((item) => String(item || '').trim()).filter(Boolean);

  if (!ENABLE_PERSISTENT_LOCAL_STORAGE) {
    return candidates[candidates.length - 1] || runtimeRoot;
  }

  return candidates[0] || projectRoot;
}

const STORAGE_ROOT = computeStorageRoot();
const DATA_DIR = path.join(STORAGE_ROOT, 'data');
const SESSION_ROOT = path.join(STORAGE_ROOT, 'sessions');

module.exports = {
  ENABLE_PERSISTENT_LOCAL_STORAGE,
  STORAGE_ROOT,
  DATA_DIR,
  SESSION_ROOT,
};
