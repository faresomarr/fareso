# Multi-Session Fix — Fares Bot

## المشكلة
ربط رقم جديد يفصل الرقم السابق لأن المشروع فيه **singleton واحد فقط** للسوكيت (`pairingBridge.primarySocket`)، و`bot_core.py` يحوي نفس `createSocket` مكررًا مرتين، و`main.js` يستخدم آخر سوكيت فقط، و`start.sh` يشغّل Python فقط دون Node الذي يحمل خريطة المآخذ. كل رقم كان يشارك نفس مجلد الجلسة → أول كتابة تدمّر ما قبلها.

## الحل (Multi-Session حقيقي، كل رقم في مساره الخاص)

### ملفات معدّلة
| الملف | التعديل |
|------|--------|
| `lib/pairingBridge.js` | حُذف `primarySocket`؛ كل سوكيت يُخزَّن بمفتاح رقمه في `socketMap`؛ `setSocket` يرفض التسجيل بدون رقم صريح؛ انتقال رقم لا يمس الأرقام الأخرى |
| `lib/sessionManager.js` | **جديد** — يدير `sessions/<phone>/` و `sessions/index.json`، مع `listPersistedPhones()` التي تُرجع كل الأرقام المخزّنة للاستعادة التلقائية |
| `start.sh` | يُشغّل Node و Python معًا في الخلفية (الـNode يحمل `waClients` Map الـPython يساعد بالمصادقة) |
| `bot_core.py` | حُذفت النسخة المكررة الثانية من `createSocket`/`useMongoAuthState` التي كانت تُلغي النسخة الأولى |
| `bot_core.py.bak` | نسخة احتياطية من الأصلي |

### ملف جديد مرفق: `multi_session.patch`
يحتوي نفس التعديلات بصيغة unified diff ليُطبَّق على فرعك مباشرة.

## خطوات التطبيق على مشروعك
```bash
# 1) نظّف الجلسة القديمة (اختياري لكن موصى به)
rm -rf sessions/

# 2) استبدل الملفات المعدّلة في مستودعك
cp lib/pairingBridge.js   <repo>/lib/pairingBridge.js
cp lib/sessionManager.js   <repo>/lib/sessionManager.js
cp start.sh               <repo>/start.sh
cp bot_core.py            <repo>/bot_core.py
chmod +x start.sh

# 3) اربط كل رقم عبر رقم هاتف مختلف — كل رقم يأخذ مجلده.
```

## كيف يحدث العزل
1. **`lib/pairingBridge.js`** — مفتاح الخريطة = رقم الهاتف؛ أي رقم `waClients.delete(otherPhone)` لا يمس سوابقه.
2. **`lib/sessionManager.js`** — `getPhoneSessionDir(phone)` يرجع `sessions/<digits>/` لبايلز.
3. **`start.sh`** — يضمن بقاء Node (مالك `waClients` و `pairingBridge`) حيًّا مع Python.
4. **`bot_core.py`** — دالة `createSocket` واحدة فقط، لا استبدال صامت.
