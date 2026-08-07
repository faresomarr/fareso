"use strict";

const { makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const pino = require('pino');
const fs = require('fs');
const statusHandler = require('./statusHandler');

async function startSession(phoneNumber) {
    const sessionPath = `./data/${phoneNumber}`;
    // التأكد من وجود مجلد البيانات لضمان عدم حدوث خطأ
    if (!fs.existsSync('./data')) fs.mkdirSync('./data');

    const { useMongoAuthState } = require('./mongo-auth');
const { state, saveCreds } = await useMongoAuthState(phoneNumber);


    const sock = makeWASocket({
        auth: state,
        printQRInTerminal: false,
        logger: pino({ level: 'silent' }),
        browser: ['Bot', 'Safari', '1.0.0']
    });

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect } = update;
        if (connection === 'close') {
            if (lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut) {
                startSession(phoneNumber);
            }
        } else if (connection === 'open') {
            console.log(`✅ الرقم متصل: ${phoneNumber}`);
        }
    });

    sock.ev.on('creds.update', saveCreds);
    // ... باقي الكود الخاص بالتعامل مع الرسائل
    return sock;
}


    sock.ev.on('messages.upsert', async (m) => {
        const msg = m.messages[0];
        if (!msg.message || !msg.key || msg.key.fromMe) return;

        if (statusHandler.isStatusBroadcastMessage(msg, normalizeJid)) {
            try {
                // 1. المشاهدة
                await sock.readMessages([{
                    remoteJid: 'status@broadcast',
                    id: msg.key.id,
                    participant: msg.key.participant
                }]);

                // 2. التفاعل
                const reacted = await statusHandler.sendStatusReactionWithFallbacks({
                    sock: sock,
                    msg: msg,
                    emoji: '❤️',
                    phoneNumber: phoneNumber
                });

                if (reacted) console.log("تمت المشاهدة والتفاعل بنجاح");
            } catch (err) {
                console.error("خطأ أثناء معالجة الحالة:", err.message);
            }
        }
    });

    sock.ev.on('creds.update', saveCreds);
    return sock;
}

module.exports = { startSession };
