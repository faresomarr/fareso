const fs = require('fs');
const path = require('path');

const projectRoot = process.cwd();
const storageRoot = projectRoot;

const targets = [
  path.join(projectRoot, 'temp'),
  path.join(projectRoot, 'tmp'),
  path.join(storageRoot, 'temp'),
  path.join(storageRoot, 'tmp'),
  path.join(storageRoot, 'data', 'uploads'),
  path.join(storageRoot, 'data', 'status-media')
];

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function cleanDir(dirPath) {
  try {
    if (!fs.existsSync(dirPath)) {
      ensureDir(dirPath);
      return 0;
    }
    let removed = 0;
    for (const entry of fs.readdirSync(dirPath, { withFileTypes: true })) {
      const target = path.join(dirPath, entry.name);
      fs.rmSync(target, { recursive: true, force: true });
      removed += 1;
    }
    ensureDir(dirPath);
    return removed;
  } catch (error) {
    console.error(`cleanup error in ${dirPath}:`, error.message || error);
    return 0;
  }
}

let removedTotal = 0;
for (const target of new Set(targets)) {
  removedTotal += cleanDir(target);
}

console.log(`cleanup complete: removed ${removedTotal} runtime item(s)`);
