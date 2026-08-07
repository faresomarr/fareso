require('dotenv').config();

const { MongoClient } = require('mongodb');

const DEFAULT_MONGODB_URI = '';
const MONGODB_URI = String(process.env.MONGODB_URI || process.env.MONGO_URL || DEFAULT_MONGODB_URI).trim();
const MONGODB_DB_NAME = String(process.env.MONGODB_DB_NAME || 'whatsapp_pairing_api').trim() || 'whatsapp_pairing_api';
const MONGODB_TIMEOUT_MS = Math.max(5000, Number(process.env.MONGODB_TIMEOUT_MS || process.env.SESSION_STORAGE_TIMEOUT_MS || 20000));

let clientPromise = null;
let dbPromise = null;
const collectionPromises = new Map();

function isMongoConfigured() {
  return Boolean(MONGODB_URI);
}

async function getMongoClient() {
  if (!isMongoConfigured()) {
    throw new Error('MongoDB is not configured');
  }

  if (!clientPromise) {
    clientPromise = (async () => {
      const client = new MongoClient(MONGODB_URI, {
        appName: 'whatsapp-pairing-api',
        serverSelectionTimeoutMS: MONGODB_TIMEOUT_MS,
        connectTimeoutMS: MONGODB_TIMEOUT_MS,
        maxPoolSize: 15,
        retryWrites: true,
      });
      await client.connect();
      return client;
    })().catch((error) => {
      clientPromise = null;
      dbPromise = null;
      collectionPromises.clear();
      throw error;
    });
  }

  return clientPromise;
}

async function getMongoDb() {
  if (!dbPromise) {
    dbPromise = getMongoClient().then((client) => client.db(MONGODB_DB_NAME)).catch((error) => {
      dbPromise = null;
      throw error;
    });
  }
  return dbPromise;
}

async function getMongoCollection(name) {
  const collectionName = String(name || '').trim();
  if (!collectionName) {
    throw new Error('MongoDB collection name is required');
  }

  if (!collectionPromises.has(collectionName)) {
    collectionPromises.set(
      collectionName,
      getMongoDb().then((db) => db.collection(collectionName)).catch((error) => {
        collectionPromises.delete(collectionName);
        throw error;
      })
    );
  }

  return collectionPromises.get(collectionName);
}

module.exports = {
  DEFAULT_MONGODB_URI,
  MONGODB_URI,
  MONGODB_DB_NAME,
  MONGODB_TIMEOUT_MS,
  isMongoConfigured,
  getMongoClient,
  getMongoDb,
  getMongoCollection,
};
