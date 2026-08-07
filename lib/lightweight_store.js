const fs = require('fs')
const STORE_FILE = './baileys_store.json'

// [MEM-OPT] Messages storage completely disabled to prevent RAM accumulation
// At 100 linked numbers, storing messages causes memory to grow unboundedly
const MAX_MESSAGES = 0

const store = {
    messages: {},
    contacts: {},
    chats: {},

    readFromFile(filePath = STORE_FILE) {
        try {
            if (fs.existsSync(filePath)) {
                const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'))
                // [MEM-OPT] Only restore contacts and chats, NOT messages
                this.contacts = data.contacts || {}
                this.chats = data.chats || {}
                this.messages = {} // Always start with empty messages
            }
        } catch (e) {
            console.warn('Failed to read store file:', e.message)
        }
    },

    writeToFile(filePath = STORE_FILE) {
        try {
            // [MEM-OPT] Only persist contacts and chats - no messages
            const data = JSON.stringify({
                contacts: this.contacts,
                chats: this.chats,
                messages: {}
            })
            fs.writeFileSync(filePath, data)
        } catch (e) {
            console.warn('Failed to write store file:', e.message)
        }
    },

    cleanupData() {
        // [MEM-OPT] Always clear messages on cleanup
        this.messages = {}
    },

    bind(ev) {
        // [MEM-OPT] messages.upsert: do NOT store messages - only track chats/contacts
        ev.on('messages.upsert', ({ messages }) => {
            // Intentionally empty - no message buffering
        })

        ev.on('contacts.update', (contacts) => {
            contacts.forEach(contact => {
                if (contact.id) {
                    this.contacts[contact.id] = {
                        id: contact.id,
                        name: contact.notify || contact.name || ''
                    }
                }
            })
        })

        ev.on('chats.set', (chats) => {
            this.chats = {}
            chats.forEach(chat => {
                this.chats[chat.id] = { id: chat.id, subject: chat.subject || '' }
            })
        })
    },

    async loadMessage(jid, id) {
        // [MEM-OPT] No messages stored - always returns null
        return null
    },

    getStats() {
        return {
            messages: 0,
            contacts: Object.keys(this.contacts).length,
            chats: Object.keys(this.chats).length,
            maxMessagesPerChat: MAX_MESSAGES
        }
    }
}

module.exports = store
