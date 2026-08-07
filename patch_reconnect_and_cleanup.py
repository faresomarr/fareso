from pathlib import Path
import re

path = Path('/home/user/whatsapp-pairing-api/index.js')
text = path.read_text(encoding='utf-8')


def replace_once(old, new):
    global text
    if old not in text:
        raise SystemExit(f'Anchor not found:\n{old[:240]}')
    text = text.replace(old, new, 1)

# 1) add runtime state map
replace_once(
    "const sessionStartPromises = new Map();\nconst recentStatusEvents = new Map();\nconst pendingContactSyncs = new Map();",
    "const sessionStartPromises = new Map();\nconst recentStatusEvents = new Map();\nconst pendingContactSyncs = new Map();\nconst phoneSessionRuntimeState = new Map();"
)

# 2) helper functions after analytics boot marker
replace_once(
    "function markAnalyticsBoot() {\n    const db = getAnalyticsDB();\n    db.lastBootAt = new Date().toISOString();\n    db.updatedAt = db.lastBootAt;\n    queueAnalyticsSave();\n}\n\nfunction getSettings() {",
    "function markAnalyticsBoot() {\n    const db = getAnalyticsDB();\n    db.lastBootAt = new Date().toISOString();\n    db.updatedAt = db.lastBootAt;\n    queueAnalyticsSave();\n}\n\nfunction getDefaultPhoneSessionRuntimeMetrics() {\n    return {\n        reconnectAttempts: 0,\n        reconnectSchedules: 0,\n        sessionStartsSinceConnect: 0,\n        lastRuntimeResetAt: '',\n        connectedAt: '',\n        ownerId: '',\n        lastReconnectScheduledAt: '',\n        lastSessionReplacementAt: '',\n        lastSessionReplacementReason: '',\n        lastMaintenanceAt: ''\n    };\n}\n\nfunction getPhoneSessionRuntimeMetrics(phone) {\n    const normalizedPhone = normalizePhone(phone);\n    const base = getDefaultPhoneSessionRuntimeMetrics();\n    if (!normalizedPhone) return { ...base };\n    return { ...base, ...(phoneSessionRuntimeState.get(normalizedPhone) || {}) };\n}\n\nfunction setPhoneSessionRuntimeMetrics(phone, patch = {}, options = {}) {\n    const normalizedPhone = normalizePhone(phone);\n    const base = options.reset === true ? getDefaultPhoneSessionRuntimeMetrics() : getPhoneSessionRuntimeMetrics(normalizedPhone);\n    if (!normalizedPhone) return { ...base, ...(patch || {}) };\n    const next = { ...base, ...(patch || {}) };\n    phoneSessionRuntimeState.set(normalizedPhone, next);\n    return next;\n}\n\nfunction resetPhoneSessionRuntimeMetrics(phone, patch = {}) {\n    const nowIso = new Date().toISOString();\n    return setPhoneSessionRuntimeMetrics(phone, {\n        reconnectAttempts: 0,\n        reconnectSchedules: 0,\n        sessionStartsSinceConnect: 0,\n        lastRuntimeResetAt: nowIso,\n        connectedAt: patch.connectedAt || '',\n        ...patch\n    }, { reset: true });\n}\n\nfunction notePhoneReconnectScheduled(phone, attemptNumber = 0) {\n    const current = getPhoneSessionRuntimeMetrics(phone);\n    return setPhoneSessionRuntimeMetrics(phone, {\n        reconnectAttempts: Math.max(0, Number(attemptNumber) || 0),\n        reconnectSchedules: Math.max(0, Number(current.reconnectSchedules || 0) + 1),\n        lastReconnectScheduledAt: new Date().toISOString()\n    });\n}\n\nfunction notePhoneSessionReplacement(phone, ownerId = '', reason = 'manual') {\n    const current = getPhoneSessionRuntimeMetrics(phone);\n    return setPhoneSessionRuntimeMetrics(phone, {\n        ownerId: String(ownerId || current.ownerId || getPhoneOwner(phone) || '').trim(),\n        reconnectAttempts: 0,\n        lastSessionReplacementAt: new Date().toISOString(),\n        lastSessionReplacementReason: String(reason || 'manual').trim() || 'manual'\n    });\n}\n\nfunction notePhoneSuccessfulConnection(phone, ownerId = '') {\n    const current = getPhoneSessionRuntimeMetrics(phone);\n    return resetPhoneSessionRuntimeMetrics(phone, {\n        ownerId: String(ownerId || current.ownerId || getPhoneOwner(phone) || '').trim(),\n        connectedAt: new Date().toISOString(),\n        lastSessionReplacementAt: current.lastSessionReplacementAt || '',\n        lastSessionReplacementReason: current.lastSessionReplacementReason || '',\n        lastMaintenanceAt: current.lastMaintenanceAt || ''\n    });\n}\n\nfunction clearExpiredPhoneSettingsAuthSessions() {\n    const now = Date.now();\n    for (const [key, value] of Array.from(phoneSettingsAuthSessions.entries())) {\n        if (Number(value?.expiresAt || 0) <= now) {\n            phoneSettingsAuthSessions.delete(key);\n        }\n    }\n}\n\nfunction pruneOrphanSessionDirectories() {\n    try {\n        ensureDir(SESSIONS_DIR);\n        const linkedPhones = new Set(getAllLinkedPhones().map((phone) => normalizePhone(phone)).filter(Boolean));\n        const storedPhones = new Set(Object.keys(getSessionStoreDB().sessions || {}).map((phone) => normalizePhone(phone)).filter(Boolean));\n        const activePhones = new Set([\n            ...Array.from(waClients.keys()),\n            ...Array.from(sessionStartPromises.keys()),\n            ...Array.from(pairingRequests.keys())\n        ].map((phone) => normalizePhone(phone)).filter(Boolean));\n\n        let removed = 0;\n        for (const entry of fs.readdirSync(SESSIONS_DIR, { withFileTypes: true })) {\n            if (!entry.isDirectory()) continue;\n            if (entry.name === '__web_qr__') continue;\n            const phone = normalizePhone(entry.name);\n            if (!phone) continue;\n            if (linkedPhones.has(phone) || storedPhones.has(phone) || activePhones.has(phone) || getPhoneOwner(phone)) {\n                continue;\n            }\n            try { fs.rmSync(path.join(SESSIONS_DIR, entry.name), { recursive: true, force: true }); } catch (_) {}\n            try { deleteSessionStoreRecordLocal(phone); } catch (_) {}\n            try { deletePhoneProfileDirectory(phone); } catch (_) {}\n            phoneSessionRuntimeState.delete(phone);\n            removed += 1;\n        }\n        return removed;\n    } catch (_) {\n        return 0;\n    }\n}\n\nfunction runRuntimeMaintenance(options = {}) {\n    try {\n        clearExpiredPhoneSettingsAuthSessions();\n        pruneExpiredStatusBackups();\n        pruneStatusArchive();\n        pruneUploadsDir();\n        pruneProblematicRuntimeFiles();\n        pruneOrphanSessionDirectories();\n        if (typeof global.gc === 'function') {\n            try { global.gc(); } catch (_) {}\n        }\n        const phone = normalizePhone(options.phone || '');\n        if (phone) {\n            setPhoneSessionRuntimeMetrics(phone, { lastMaintenanceAt: new Date().toISOString() });\n        }\n        return true;\n    } catch (error) {\n        console.error('Runtime Maintenance Warning:', error?.message || error);\n        return false;\n    }\n}\n\nfunction getSettings() {"
)

# 3) dashboard stats
replace_once(
    "        autoSave: settings.autoSave || 'on',\n        pointLikePackages: pointLikes.packages,\n        pointLikeCapacity: pointLikes.likes,\n        lastDailyGiftAt: userRecord?.lastDailyGiftAt || null\n    };",
    "        autoSave: settings.autoSave || 'on',\n        pointLikePackages: pointLikes.packages,\n        pointLikeCapacity: pointLikes.likes,\n        lastDailyGiftAt: userRecord?.lastDailyGiftAt || null,\n        runtime: getPhoneSessionRuntimeMetrics(normalizedPhone),\n        currentReconnectAttempts: getReconnectAttempts(normalizedPhone)\n    };"
)

# 4) purge session data reset/delete runtime metrics
replace_once(
    "    if (keepProfile) {\n        clearPhoneSettingsAuthForPhone(normalized);\n        return;\n    }\n    removeLinkedNumber(normalized);\n}",
    "    if (keepProfile) {\n        resetPhoneSessionRuntimeMetrics(normalized, {\n            ownerId: preservedOwnerId,\n            lastSessionReplacementAt: new Date().toISOString(),\n            lastSessionReplacementReason: String(options.reason || 'purge_keep_profile')\n        });\n        clearPhoneSettingsAuthForPhone(normalized);\n        return;\n    }\n    phoneSessionRuntimeState.delete(normalized);\n    removeLinkedNumber(normalized);\n}"
)

# 5) clearReconnectTimer helper insertion
replace_once(
    "function clearReconnectTimer(phone) {\n    const normalized = normalizePhone(phone);\n    const timer = reconnectTimers.get(normalized);\n    if (timer) {\n        clearTimeout(timer);\n        reconnectTimers.delete(normalized);\n    }\n}\n",
    "function clearReconnectTimer(phone) {\n    const normalized = normalizePhone(phone);\n    const timer = reconnectTimers.get(normalized);\n    if (timer) {\n        clearTimeout(timer);\n        reconnectTimers.delete(normalized);\n    }\n}\n\nasync function prepareFreshSessionReplacement(phone, ownerId = '', reason = 'manual_repair') {\n    const normalizedPhone = normalizePhone(phone);\n    if (!normalizedPhone) return false;\n    const preservedOwnerId = String(ownerId || getPhoneOwner(normalizedPhone) || '').trim();\n    const existingSock = waClients.get(normalizedPhone);\n\n    clearReconnectTimer(normalizedPhone);\n    clearPairingRequest(normalizedPhone);\n    clearPresenceTimer(normalizedPhone);\n    clearGhostPendingMessagesForPhone(normalizedPhone);\n    clearSessionSnapshotSyncState(normalizedPhone);\n    stoppedPairings.delete(normalizedPhone);\n    clientActivity.delete(normalizedPhone);\n\n    if (existingSock) {\n        try { await existingSock.logout?.(); } catch (_) {}\n        try { existingSock.ws?.close?.(); } catch (_) {}\n        try { existingSock.end?.(); } catch (_) {}\n        waClients.delete(normalizedPhone);\n    }\n\n    await purgeSessionData(normalizedPhone, {\n        keepProfile: true,\n        ownerId: preservedOwnerId,\n        reason: 'fresh_session_replacement'\n    });\n    ensurePhoneSettingsProfile(normalizedPhone, getActivePhoneAppId(normalizedPhone) || 'default');\n    notePhoneSessionReplacement(normalizedPhone, preservedOwnerId, reason);\n    return true;\n}\n"
)

# 6) reconnect counters sync
replace_once(
    "function resetReconnectAttempts(phone) {\n    const normalized = normalizePhone(phone);\n    if (!normalized) return 0;\n    reconnectAttempts.delete(normalized);\n    return 0;\n}\n",
    "function resetReconnectAttempts(phone) {\n    const normalized = normalizePhone(phone);\n    if (!normalized) return 0;\n    reconnectAttempts.delete(normalized);\n    setPhoneSessionRuntimeMetrics(normalized, { reconnectAttempts: 0 });\n    return 0;\n}\n"
)
replace_once(
    "function bumpReconnectAttempts(phone) {\n    const normalized = normalizePhone(phone);\n    if (!normalized) return 0;\n    const next = getReconnectAttempts(normalized) + 1;\n    reconnectAttempts.set(normalized, next);\n    return next;\n}\n",
    "function bumpReconnectAttempts(phone) {\n    const normalized = normalizePhone(phone);\n    if (!normalized) return 0;\n    const next = getReconnectAttempts(normalized) + 1;\n    reconnectAttempts.set(normalized, next);\n    setPhoneSessionRuntimeMetrics(normalized, { reconnectAttempts: next });\n    return next;\n}\n"
)

# 7) reconnect schedule bookkeeping
replace_once(
    "    incrementAnalytics('totalReconnects');\n\n    const timer = setTimeout(async () => {",
    "    notePhoneReconnectScheduled(normalized, attemptNumber);\n    incrementAnalytics('totalReconnects');\n\n    const timer = setTimeout(async () => {"
)

# 8) supervisor maintenance
replace_once(
    "        if (!lastRuntimeCleanupAt || now - lastRuntimeCleanupAt >= RUNTIME_CLEANUP_INTERVAL_MS) {\n            lastRuntimeCleanupAt = now;\n            pruneExpiredStatusBackups();\n            pruneStatusArchive();\n            pruneUploadsDir();\n            pruneProblematicRuntimeFiles();\n        }",
    "        if (!lastRuntimeCleanupAt || now - lastRuntimeCleanupAt >= RUNTIME_CLEANUP_INTERVAL_MS) {\n            lastRuntimeCleanupAt = now;\n            runRuntimeMaintenance({ reason: 'session_supervisor' });\n        }"
)

# 9) startWhatsApp fresh session support
replace_once(
    "async function startWhatsApp(phoneNumber, telegramCtx = null, ownerId = null, pairingNotifier = null, options = {}) {\n    const normalizedPhone = normalizePhone(phoneNumber);\n    const bootRestore = options?.bootRestore === true;\n    if (!normalizedPhone) return null;\n\n    const inflightStart = sessionStartPromises.get(normalizedPhone);\n    if (inflightStart) {\n        return inflightStart;\n    }\n\n    const startPromise = (async () => {\n        clearReconnectTimer(normalizedPhone);\n        stoppedPairings.delete(normalizedPhone);\n\n        const existing = waClients.get(normalizedPhone);\n        if (existing) {\n            touchClient(normalizedPhone);\n            return existing;\n        }\n\n        const sessionPath = getSessionPath(normalizedPhone);\n        const autoRequestPairingCode = options?.autoRequestPairingCode !== false;\n\n        const { state, saveCreds } = await getMongoAuthState(normalizedPhone);\n        const { version } = await getCachedBaileysVersion();\n        const requestedOwnerId = String(ownerId || telegramCtx?.from?.id || getPhoneOwner(normalizedPhone) || '');",
    "async function startWhatsApp(phoneNumber, telegramCtx = null, ownerId = null, pairingNotifier = null, options = {}) {\n    const normalizedPhone = normalizePhone(phoneNumber);\n    const bootRestore = options?.bootRestore === true;\n    const forceFreshSession = options?.forceFreshSession === true;\n    if (!normalizedPhone) return null;\n\n    const requestedOwnerId = String(ownerId || telegramCtx?.from?.id || getPhoneOwner(normalizedPhone) || '');\n    const inflightStart = sessionStartPromises.get(normalizedPhone);\n    if (inflightStart) {\n        if (!forceFreshSession) {\n            return inflightStart;\n        }\n        throw new Error('يوجد تشغيل أو استعادة جاري لهذا الرقم، انتظر قليلاً ثم أعد المحاولة');\n    }\n\n    const startPromise = (async () => {\n        clearReconnectTimer(normalizedPhone);\n        stoppedPairings.delete(normalizedPhone);\n\n        if (forceFreshSession) {\n            await prepareFreshSessionReplacement(normalizedPhone, requestedOwnerId, String(options?.replaceReason || 'fresh_session'));\n        }\n\n        const existing = waClients.get(normalizedPhone);\n        if (existing) {\n            touchClient(normalizedPhone);\n            return existing;\n        }\n\n        const sessionPath = getSessionPath(normalizedPhone);\n        const autoRequestPairingCode = options?.autoRequestPairingCode !== false;\n\n        const { state, saveCreds } = await getMongoAuthState(normalizedPhone);\n        const { version } = await getCachedBaileysVersion();"
)

# 10) connection open runtime reset/maintenance
replace_once(
    "                incrementAnalytics('totalSessionsStarted');\n                clearReconnectTimer(normalizedPhone);\n                resetReconnectAttempts(normalizedPhone);\n                startPresenceKeepAlive(sock, normalizedPhone);",
    "                incrementAnalytics('totalSessionsStarted');\n                clearReconnectTimer(normalizedPhone);\n                resetReconnectAttempts(normalizedPhone);\n                notePhoneSuccessfulConnection(normalizedPhone, requestedOwnerId || getPhoneOwner(normalizedPhone) || '');\n                runRuntimeMaintenance({ reason: 'connection_open', phone: normalizedPhone });\n                startPresenceKeepAlive(sock, normalizedPhone);"
)

# 11) pair_wa UI blocks
replace_once(
    "    if (data === 'pair_wa') {\n        const currentPhones = getUserPhones(ctx.from.id);\n        if (currentPhones.length) {\n            return safeReply(ctx, `❌ لايمكنك ربط أكثر من رقم.\\nلحذف الرقم الحالي استخدم زر حذف جلسة أولاً ثم اربط الرقم الآخر.`);\n        }\n        ctx.session = { step: 'wait_phone' };\n        return safeReply(ctx, `📱 أرسل رقم الواتساب بهذه الصيغة: 967771163825\\nبدون + وبدون 00 وبدون مسافات.`);\n    }",
    "    if (data === 'pair_wa') {\n        const currentPhones = getUserPhones(ctx.from.id);\n        if (currentPhones.length > 1) {\n            return safeReply(ctx, `❌ لايمكنك ربط أكثر من رقم.\\nلحذف الرقم الحالي استخدم زر حذف جلسة أولاً ثم اربط الرقم الآخر.`);\n        }\n        ctx.session = { step: 'wait_phone' };\n        const pairHint = currentPhones.length === 1\n            ? `📱 لديك رقم مربوط حالياً: ${currentPhones[0]}\\nأرسل نفس الرقم لتجديد الجلسة واستبدال القديمة، أو احذف الرقم الحالي أولاً إذا أردت رقماً مختلفاً.`\n            : '📱 أرسل رقم الواتساب بهذه الصيغة: 967771163825';\n        return safeReply(ctx, `${pairHint}\\nبدون + وبدون 00 وبدون مسافات.`);\n    }"
)
replace_once(
    "        if (keyboardAction === 'pair_wa') {\n            const currentPhones = getUserPhones(ctx.from.id);\n            if (currentPhones.length) {\n                return safeReply(ctx, `❌ لايمكنك ربط أكثر من رقم.\\nلحذف الرقم الحالي استخدم زر حذف جلسة أولاً ثم اربط الرقم الآخر.`);\n            }\n            ctx.session = { step: 'wait_phone' };\n            return safeReply(ctx, `📱 أرسل رقم الواتساب بهذه الصيغة: 967771163825\\nبدون + وبدون 00 وبدون مسافات.`);\n        }",
    "        if (keyboardAction === 'pair_wa') {\n            const currentPhones = getUserPhones(ctx.from.id);\n            if (currentPhones.length > 1) {\n                return safeReply(ctx, `❌ لايمكنك ربط أكثر من رقم.\\nلحذف الرقم الحالي استخدم زر حذف جلسة أولاً ثم اربط الرقم الآخر.`);\n            }\n            ctx.session = { step: 'wait_phone' };\n            const pairHint = currentPhones.length === 1\n                ? `📱 لديك رقم مربوط حالياً: ${currentPhones[0]}\\nأرسل نفس الرقم لتجديد الجلسة واستبدال القديمة، أو احذف الرقم الحالي أولاً إذا أردت رقماً مختلفاً.`\n                : '📱 أرسل رقم الواتساب بهذه الصيغة: 967771163825';\n            return safeReply(ctx, `${pairHint}\\nبدون + وبدون 00 وبدون مسافات.`);\n        }"
)

# 12) wait_phone flow replace existing same number/session
replace_once(
    "        if (userOwnsPhone(ctx.from.id, phone) && waClients.has(phone)) {\n            ctx.session = null;\n            return safeReply(ctx, '✅ هذا الرقم مربوط لديك بالفعل ومفعل حالياً.');\n        }\n\n        await safeReply(ctx, '⏳ جاري إنشاء الجلسة وطلب كود الربط، انتظر قليلاً...');\n        ctx.session = null;\n        await startWhatsApp(phone, ctx, ctx.from.id);\n        return;",
    "        const userAlreadyOwnsPhone = userOwnsPhone(ctx.from.id, phone);\n        const shouldReplaceExistingSession = userAlreadyOwnsPhone || hasPersistedSuccessfulSession(phone) || waClients.has(phone);\n\n        if (userAlreadyOwnsPhone && waClients.has(phone)) {\n            await safeReply(ctx, '♻️ تم التعرف على الرقم كمربوط لديك بالفعل. سيتم حذف الجلسة القديمة والبدء بجلسة جديدة مع الاحتفاظ بجميع إعدادات الرقم الخاصة به.');\n        } else {\n            await safeReply(ctx, '⏳ جاري إنشاء الجلسة وطلب كود الربط، انتظر قليلاً...');\n        }\n        ctx.session = null;\n        await startWhatsApp(phone, ctx, ctx.from.id, null, {\n            forceFreshSession: shouldReplaceExistingSession,\n            replaceReason: userAlreadyOwnsPhone ? 'telegram_repair_same_number' : 'telegram_pair_or_restore'\n        });\n        return;"
)

# 13) admin paircode force fresh
replace_once(
    "        await startWhatsApp(phone, null, ctx.from.id, null, { autoRequestPairingCode: true });",
    "        await startWhatsApp(phone, null, ctx.from.id, null, { autoRequestPairingCode: true, forceFreshSession: true, replaceReason: 'admin_paircode_refresh' });"
)

# 14) pairing API allow replacing existing session
replace_once(
    "        if (hasPersistedSuccessfulSession(phone) || waClients.has(phone)) {\n            await startWhatsApp(phone, null, getPhoneOwner(phone) || null, null, { autoRequestPairingCode: false, bootRestore: true });\n            return res.status(409).json({ success: false, error: 'هذا الرقم مرتبط بالفعل وتوجد له جلسة محفوظة، لذلك لن يتم إنشاء جلسة جديدة أو كود جديد' });\n        }\n        if (pairingRequests.has(phone)) return res.status(409).json({ success: false, error: 'يوجد كود ربط جاري لهذا الرقم، انتظر قليلاً' });\n        await startWhatsApp(phone, null, null, null, { autoRequestPairingCode: true });\n        const code = await waitForPairingCode(phone);",
    "        const replacingExistingSession = hasPersistedSuccessfulSession(phone) || waClients.has(phone);\n        if (pairingRequests.has(phone)) return res.status(409).json({ success: false, error: 'يوجد كود ربط جاري لهذا الرقم، انتظر قليلاً' });\n        await startWhatsApp(phone, null, getPhoneOwner(phone) || null, null, {\n            autoRequestPairingCode: true,\n            forceFreshSession: replacingExistingSession,\n            replaceReason: replacingExistingSession ? 'pairing_api_replace_existing_session' : 'pairing_api_new_session'\n        });\n        const code = await waitForPairingCode(phone);"
)
replace_once(
    "            code,\n            website: SITE_ENDPOINTS.target_site_base_url,\n            settingsPage: SITE_ENDPOINTS.target_settings_page_url\n        });",
    "            code,\n            replacedExistingSession: replacingExistingSession,\n            website: SITE_ENDPOINTS.target_site_base_url,\n            settingsPage: SITE_ENDPOINTS.target_settings_page_url\n        });"
)

# 15) boot maintenance
replace_once(
    "    await resetRuntimePhoneDataOnBoot();\n    await getStoredMongoSessionEntries().catch((error) => {",
    "    await resetRuntimePhoneDataOnBoot();\n    runRuntimeMaintenance({ reason: 'service_boot' });\n    await getStoredMongoSessionEntries().catch((error) => {"
)

path.write_text(text, encoding='utf-8')
print('Patched index.js successfully')
