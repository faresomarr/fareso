require('dotenv').config();

const { getMongoCollection } = require('../lib/mongoClient');

const COLLECTION_NAME = String(process.env.MONGODB_USER_CONFIG_COLLECTION || 'user_configs').trim() || 'user_configs';

function normalizeJid(value = '') {
  return String(value || '').trim();
}

function normalizeUpdateDocument(update = {}) {
  if (!update || typeof update !== 'object') {
    return { $set: {} };
  }

  const hasOperator = Object.keys(update).some((key) => key.startsWith('$'));
  return hasOperator ? update : { $set: update };
}

async function getCollection() {
  const collection = await getMongoCollection(COLLECTION_NAME);
  await collection.createIndex({ jid: 1 }, { unique: true });
  return collection;
}

module.exports = {
  async findOne(query = {}) {
    const jid = normalizeJid(query.jid);
    if (!jid) return null;
    const collection = await getCollection();
    return collection.findOne({ jid });
  },

  async findOneAndUpdate(query = {}, update = {}, options = {}) {
    const jid = normalizeJid(query.jid);
    if (!jid) {
      throw new Error('jid is required');
    }

    const collection = await getCollection();
    const updateDoc = normalizeUpdateDocument(update);
    const now = new Date();

    updateDoc.$set = {
      ...(updateDoc.$set || {}),
      jid,
      updatedAt: now,
    };
    updateDoc.$setOnInsert = {
      emoji: '💤',
      createdAt: now,
      ...(updateDoc.$setOnInsert || {}),
    };

    const result = await collection.findOneAndUpdate(
      { jid },
      updateDoc,
      {
        upsert: options.upsert === true,
        returnDocument: 'after',
      }
    );

    return result?.value || collection.findOne({ jid });
  },
};
