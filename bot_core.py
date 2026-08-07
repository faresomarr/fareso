import asyncio
import html
import json
import logging
import os
import re
import subprocess
import threading
import time
import atexit
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse
import importlib.util
import shutil
import sys


def ensure_python_package(module_name: str, pip_name: Optional[str] = None) -> None:
    if importlib.util.find_spec(module_name) is not None:
        return
    package_name = pip_name or module_name
    print(f"Installing missing Python dependency: {package_name}", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", package_name])


ensure_python_package("requests", "requests>=2.31.0")
ensure_python_package("telegram", "python-telegram-bot>=20,<23")
ensure_python_package("pymongo", "pymongo[srv]>=4.6.0")

import requests
from pymongo import MongoClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import Conflict
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
    force=True,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
EMBEDDED_COMPANION_DIR = Path(os.getenv("EMBEDDED_COMPANION_DIR") or str(BASE_DIR / "_embedded_pairing_runtime")).resolve()
ENV_PATH = BASE_DIR / ".env"
SETTINGS_PATH = BASE_DIR / "bot_settings.json"
USERS_PATH = BASE_DIR / "bot_users.json"
USER_EMOJI_SETTINGS_PATH = BASE_DIR / "user_emoji_settings.json"
LINKED_WHATSAPP_USERS_PATH = BASE_DIR / "linked_whatsapp_users.json"
PENDING_PAIRINGS_PATH = BASE_DIR / "pending_pairings.json"
AUTO_REPLY_LOG_PATH = BASE_DIR / "auto_reply_log.json"
DEFAULT_BOT_TOKEN = "8631941557:AAH-d476_Rrtvvgc5aOba8SPzMJnno5sG4o"
DEFAULT_ADMIN_ID = 7231690686
DEFAULT_START_MESSAGE_TEMPLATE = "{emoji}"
START_MESSAGE_AUTO_LINE_PATTERNS = [
    (re.compile(r"^[^\S\r\n]*(?:\S+\s*)?الإيموجي الحالي\s*:\s*.*$", re.MULTILINE), "{emoji} الإيموجي الحالي: {emoji}"),
    (re.compile(r"^[^\S\r\n]*\{?auto_reply_status\}?[^\S\r\n]*$", re.MULTILINE), ""),
    (re.compile(r"^[^\S\r\n]*(?:\S+\s*)?المطور الأساسي\s*:\s*.*$", re.MULTILINE), "{admin_text}"),
    (re.compile(r"^[^\S\r\n]*(?:\S+\s*)?المطور الاساسي\s*:\s*.*$", re.MULTILINE), "{admin_text}"),
]
DEFAULT_AUTO_REPLY_CHANNEL_URL = "https://whatsapp-pairing-api-production-639f.up.railway.app/"
DEFAULT_CONTACT_NUMBER = "967773987296"
DEFAULT_SITE_BRAND_NAME = "بوت الربط بايثون"
DEFAULT_SITE_FOOTER = "بوت الربط بايثون"
DEFAULT_SITE_INFO_TEXT = (
    f"🔗 القناة الرسمية: {DEFAULT_AUTO_REPLY_CHANNEL_URL}\n"
    f"📞 رقم التواصل: {DEFAULT_CONTACT_NUMBER}"
)
DEFAULT_AUTO_REPLY_MESSAGE_TEMPLATE = (
    "🔗 هذا رابط القناة الخاصة بنا\n"
    "{channel_url}\n\n"
    f"📞 رقم التواصل: {DEFAULT_CONTACT_NUMBER}"
)
DEFAULT_WHATSAPP_ALIVE_MESSAGE = "✅ *Golden Queen is active now*\n\n👑 *Owner:* Golden Queen\n🤖 *Status:* Ready"
DEFAULT_WHATSAPP_BOT_MESSAGE = '✅ *كود الاقتران الجديد*\n\n🔑 *الكود:* {code}\n\n📱 *طريقة الربط:*\n1️⃣ افتح واتساب.\n2️⃣ ادخل إلى الأجهزة المرتبطة.\n3️⃣ اختر ربط جهاز.\n4️⃣ أدخل الكود أعلاه مباشرة باعلى سرعة (يفضل خلال 30 ثانية من استخراج الكود).\n\n⚠️ *هام جدًا:* استخدم آخر كود فقط. إذا ظهر *جار تسجيل الدخول* لمدة تزيد عن دقيقة واحدة أو توقف لمتصفح واتساب، اطلب كودًا جديدًا فورًا وأعد المحاولة فوراً، لا تنسخ قديما.'
DEVELOPER_CONTACT_MESSAGE = "التواصل معى المطور على الواتس من خلال الرقم التالي\n967773987296\nاو لتواصل مع المطور من خلال التليجرام عبر اليوزر التالي\n@P_n_ij"
DEFAULT_WHATSAPP_SETTINGS_MESSAGE = "⚙️ رسالة الإعدادات"
LEGACY_WHATSAPP_BOT_MESSAGES = ('👑 *GQUEEN-MINI VERIFICATION*\n\n🔑 Your Link Code: *{code}*\n\n----------------------------\n📱 *How to Link Your Device:*\n\n1️⃣ Open *WhatsApp* on your phone.\n2️⃣ Tap *Menu* (⋮) or *Settings* (⚙️).\n3️⃣ Select *Linked Devices*.\n4️⃣ Tap *Link a Device*.\n5️⃣ Point your phone to the screen to scan the QR or use this code if prompted.',)
LEGACY_WHATSAPP_ALIVE_MESSAGES = ("*👋⃝⃘̉̉̉━⋆─⋆──❂*\n*┊ ┊ ┊ ┊ ┊*\n*┊ ┊ ✫ ˚㋛ ⋆｡ ❀*\n*┊ ☠︎︎*\n*✧  ◥ ツفارس 🇾🇪ツ ◤𓂃✍︎𝄞*\n*┏━━━━━━━━━━━━━❥❥❥*\n*┃* *👋 I AM ALIVE NOW*\n*┗━━━━━━━━━━━━━❥❥❥*\n*┏━━━━━━━━━━━━━❥❥❥*\n*┃*𝙾𝚆𝙽𝙴𝚁* - Golden Queen\n*┃* *𝙿𝚁𝙴𝙵𝙸𝚇* - [ undefined ] \n*┃* *𝚆𝙴𝙱* - 'www.goldenqueen.store'\n*┗━━━━━━━━━━━━━❥❥❥*\n\n𝙲𝙾𝙽𝙽𝙴𝙲𝚃 𝙽𝙴𝚆 𝙱𝙾𝚃 ✅\nwww.goldenqueen.store/wa-bot/\n©𝗣𝗢𝗪𝗘𝗥𝗘𝗗 𝗕𝗬 Golden Queen Bot",)
LEGACY_WHATSAPP_BOT_SNIPPETS = ('لربط بوتك انتقل هنا', 'https://t.me/Safum99bot', '𝙲𝙾𝙽𝙽𝙴𝙲𝚃 𝙽𝙴𝚆 𝙱𝙾𝚃', 'www.goldenqueen.store/wa-bot/', '@𝐏𝐎𝐖𝐄𝐑𝐄𝐃 𝐁𝐘 fares',)
LEGACY_WHATSAPP_ALIVE_SNIPPETS = ('𝙲𝙾𝙽𝙽𝙴𝙲𝚃 𝙽𝙴𝚆 𝙱𝙾𝚃 ✅', 'www.goldenqueen.store/wa-bot/', '©𝗣𝗢𝗪𝗘𝗥𝗘𝗗 𝗕𝗬 Golden Queen Bot', "*┃* *𝚆𝙴𝙱* - 'www.goldenqueen.store'",)


def normalize_whatsapp_template_value(value: Any, default_value: str, legacy_exact_values: tuple[str, ...] = (), legacy_snippets: tuple[str, ...] = ()) -> str:
    normalized_value = str(value or "").replace("\r\n", "\n").strip()
    if not normalized_value:
        return default_value
    if normalized_value in legacy_exact_values:
        return default_value
    if legacy_snippets and any(snippet in normalized_value for snippet in legacy_snippets):
        return default_value
    return normalized_value

PASSWORD_DISCOVERY_COMMAND = ".settings"
PASSWORD_DISCOVERY_ATTEMPT_DELAYS = (15, 45, 60)
PASSWORD_DISCOVERY_RESPONSE_WAIT_SECONDS = 12
START_MANUAL_LOGIN_HINT = ""
BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()
SESSION_RECONCILE_INTERVAL_SECONDS = max(20, int((os.getenv("SESSION_RECONCILE_INTERVAL_SECONDS") or "60").strip() or "60"))
SESSION_MISSING_GRACE_CHECKS = max(1, int((os.getenv("SESSION_MISSING_GRACE_CHECKS") or "2").strip() or "2"))
SESSION_RECONCILE_MISS_COUNTS: dict[str, int] = {}
ARABIC_DIGIT_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
TELEGRAM_APP = None
TELEGRAM_LOOP = None
BOT_LINK_CACHE = {"url": ""}
PAIRING_RUNTIME_DISABLED_REASON = ""
EMBEDDED_COMPANION_LOG_PATH = BASE_DIR / "embedded_companion.log"
EMBEDDED_COMPANION_LOG_HANDLE = None
DEFAULT_LINKED_MESSAGE_IMAGE_URL = "https://www.genspark.ai/api/files/s/18UAzOdi"
SITE_SETTINGS_SYNC_INTERVAL_SECONDS = max(20, int((os.getenv("SITE_SETTINGS_SYNC_INTERVAL_SECONDS") or "45").strip() or "45"))

DEFAULT_MONGODB_URI = "mongodb+srv://faresomar79:faresaltmimi99@cluster0.0tb0uf9.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
MONGODB_URI = (os.getenv("MONGODB_URI") or os.getenv("MONGO_URL") or DEFAULT_MONGODB_URI).strip()
MONGODB_DB_NAME = (os.getenv("MONGODB_DB_NAME") or "whatsapp_pairing_api").strip() or "whatsapp_pairing_api"
MONGODB_STATE_COLLECTION = (os.getenv("MONGODB_STATE_COLLECTION") or "telegram_bot_state").strip() or "telegram_bot_state"
MONGODB_SESSIONS_COLLECTION = (os.getenv("MONGODB_SESSIONS_COLLECTION") or "whatsapp_sessions").strip() or "whatsapp_sessions"
MONGODB_TIMEOUT_MS = max(5000, int((os.getenv("MONGODB_TIMEOUT_MS") or os.getenv("SESSION_STORAGE_TIMEOUT_MS") or "20000").strip() or "20000"))
_MONGO_CLIENT: Optional[MongoClient] = None
_MONGO_DB = None


def get_mongo_database():
    global _MONGO_CLIENT, _MONGO_DB
    if not MONGODB_URI:
        return None
    if _MONGO_DB is not None:
        return _MONGO_DB
    try:
        _MONGO_CLIENT = MongoClient(
            MONGODB_URI,
            appname="whatsapp_pairing_telegram_bot",
            serverSelectionTimeoutMS=MONGODB_TIMEOUT_MS,
            connectTimeoutMS=MONGODB_TIMEOUT_MS,
            maxPoolSize=10,
            retryWrites=True,
        )
        _MONGO_CLIENT.admin.command("ping")
        _MONGO_DB = _MONGO_CLIENT[MONGODB_DB_NAME]
        return _MONGO_DB
    except Exception:
        logger.exception("Failed to connect to MongoDB")
        _MONGO_CLIENT = None
        _MONGO_DB = None
        return None


def load_state_from_mongo(state_key: str, default: Any = None) -> Any:
    database = get_mongo_database()
    if database is None:
        return default
    try:
        collection = database[MONGODB_STATE_COLLECTION]
        document = collection.find_one({"_id": state_key})
        if isinstance(document, dict) and "payload" in document:
            return document.get("payload")
    except Exception:
        logger.exception("Failed to load %s from MongoDB", state_key)
    return default


def save_state_to_mongo(state_key: str, payload: Any) -> None:
    database = get_mongo_database()
    if database is None:
        return
    try:
        database[MONGODB_STATE_COLLECTION].update_one(
            {"_id": state_key},
            {"$set": {"payload": payload, "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
    except Exception:
        logger.exception("Failed to save %s into MongoDB", state_key)


def hydrate_local_state_from_mongo() -> None:
    state_files = {
        "settings": SETTINGS_PATH,
        "registered_users": USERS_PATH,
        "user_emoji_settings": USER_EMOJI_SETTINGS_PATH,
        "linked_whatsapp_users": LINKED_WHATSAPP_USERS_PATH,
        "pending_pairings": PENDING_PAIRINGS_PATH,
        "auto_reply_log": AUTO_REPLY_LOG_PATH,
    }
    restored_any = False
    for state_key, file_path in state_files.items():
        payload = load_state_from_mongo(state_key, None)
        if payload is None:
            continue
        try:
            file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            restored_any = True
        except Exception:
            logger.exception("Failed to restore %s from MongoDB", state_key)
    if not restored_any:
        return

    global SETTINGS, USER_EMOJI_SETTINGS, LINKED_WHATSAPP_USERS, PENDING_PAIRINGS, AUTO_REPLY_EVENT_LOG
    SETTINGS = load_settings()
    USER_EMOJI_SETTINGS = load_user_emoji_settings()
    LINKED_WHATSAPP_USERS = load_linked_whatsapp_users()
    PENDING_PAIRINGS = load_pending_pairings()
    AUTO_REPLY_EVENT_LOG = load_auto_reply_log()
    BOT_STATS["total_users"] = load_registered_users()


def sync_all_local_state_to_mongo() -> None:
    save_state_to_mongo("settings", SETTINGS)
    save_state_to_mongo("registered_users", sorted(BOT_STATS.get("total_users", set())))
    save_state_to_mongo("user_emoji_settings", {str(user_id): emoji for user_id, emoji in USER_EMOJI_SETTINGS.items() if emoji})
    save_state_to_mongo("linked_whatsapp_users", LINKED_WHATSAPP_USERS)
    save_state_to_mongo("pending_pairings", PENDING_PAIRINGS)
    save_state_to_mongo("auto_reply_log", AUTO_REPLY_EVENT_LOG)

USER_EMOJI_TRIGGERS = {
    "تغيير ايموجي الحاله",
    "تغيير إيموجي الحاله",
    "تغيير ايموجي الحالة",
    "تغيير إيموجي الحالة",
    "غير الايموجي",
    "غيّر الايموجي",
    "غير الإيموجي",
    "غيّر الإيموجي",
}
DRF_TEXT_TRIGGERS = {
    "اعدادات الموقع",
    "إعدادات الموقع",
    "اعدادات الموقع /drf",
    "إعدادات الموقع /drf",
    "drf",
    "/drf",
}

SITE_SETTINGS_FIELD_LABELS = {
    "name": "اسم البوت",
    "ownerNumber": "رقم التواصل",
    "ownername": "اسم المالك",
    "description": "المعلومات التعريفية",
    "from": "الموقع",
    "age": "العمر",
    "prefix": "البادئة",
    "footer2": "الفوتر",
    "mode": "الوضع",
    "antiBad": "مكافحة الكلمات السيئة",
    "antiLink": "مكافحة الروابط",
    "autoRecording": "تسجيل تلقائي",
    "autoTyping": "كتابة تلقائية",
    "alwaysOnline": "دائمًا أونلاين",
    "autoStatusRead": "مشاهدة الحالة تلقائيًا",
    "autoStatusReact": "التفاعل مع الحالة تلقائيًا",
    "autoRead": "قراءة تلقائية",
    "autoBlock": "حظر تلقائي",
    "autoReact": "تفاعل تلقائي",
    "autoVoice": "صوت تلقائي",
    "antiDelete": "مكافحة الحذف",
    "sendDeleteTo": "إرسال المحذوف إلى",
    "statusMsgSend": "إرسال رسالة على الحالة",
    "statusMsgType": "نوع رسالة الحالة",
    "customMsg": "رسالة الحالة المخصصة",
    "menu": DEFAULT_LINKED_MESSAGE_IMAGE_URL,
    "alive": DEFAULT_LINKED_MESSAGE_IMAGE_URL,
    "owner": DEFAULT_LINKED_MESSAGE_IMAGE_URL,
    "statusCustomReact": "رموز تعبيرية للحالة (10 كحد أقصى)",
    "antiBug": "مكافحة البق",
    "antiBot": "مكافحة البوت",
    "antiBotAction": "إجراء مكافحة البوت",
    "gaGroupJid": "معرف الجروب",
    "gaTimezone": "المنطقة الزمنية",
    "gaCloseTime": "وقت الإغلاق",
    "gaOpenTime": "وقت الفتح",
}
DRF_FIELDS_PER_PAGE = 8
DEFAULT_SITE_SETTINGS_PAYLOAD = {
    "name": DEFAULT_SITE_BRAND_NAME,
    "from": "Yemen",
    "age": "24",
    "prefix": ".",
    "footer2": DEFAULT_SITE_FOOTER,
    "mode": "private",
    "antiBad": "off",
    "antiLink": "off",
    "autoRecording": "off",
    "autoTyping": "off",
    "alwaysOnline": "off",
    "autoStatusRead": "on",
    "autoStatusReact": "on",
    "autoRead": "off",
    "autoBlock": "off",
    "autoReact": "off",
    "autoVoice": "off",
    "antiDelete": "off",
    "sendDeleteTo": "owner",
    "antiCall": "off",
    "excludeCallNumbers": "",
    "statusMsgSend": "off",
    "statusMsgType": "default",
    "customMsg": DEFAULT_SITE_INFO_TEXT,
    "ownerNumber": DEFAULT_CONTACT_NUMBER,
    "ownername": DEFAULT_SITE_BRAND_NAME,
    "description": DEFAULT_SITE_INFO_TEXT,
    "gaGroupJid": "",
    "gaTimezone": "Asia/Colombo",
    "gaCloseTime": "15:00",
    "gaOpenTime": "05:00",
    "menu": "https://i.ibb.co/DfXkGJM1/77963b2740a0.jpg",
    "alive": "https://i.ibb.co/DfXkGJM1/77963b2740a0.jpg",
    "owner": "https://i.ibb.co/DfXkGJM1/77963b2740a0.jpg",
    "statusCustomReact": "",
    "antiBug": "off",
    "antiBot": "off",
    "antiBotAction": "delete",
}


PROJECT_SOURCE_DIR = Path(os.getenv("PROJECT_SOURCE_DIR", str(BASE_DIR))).resolve()
PROJECT_DATA_DIR = PROJECT_SOURCE_DIR / "data"
PROJECT_SNAPSHOT_PATH = BASE_DIR / "project_snapshot.json"
PROJECT_JSON_SOURCES = {
    "settings_root": PROJECT_SOURCE_DIR / "settings.json",
    "phone_settings_root": PROJECT_SOURCE_DIR / "phone-settings.json",
    "users_root": PROJECT_SOURCE_DIR / "users.json",
    "message_count": PROJECT_DATA_DIR / "messageCount.json",
    "owner_data": PROJECT_DATA_DIR / "owner.json",
    "premium_data": PROJECT_DATA_DIR / "premium.json",
}


def _safe_read_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8") or "{}")
            return payload if isinstance(payload, dict) else {}
    except Exception:
        logger.exception("Failed to read project json file: %s", path)
    return {}


def _extract_project_defaults() -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "project_source_dir": str(PROJECT_SOURCE_DIR),
        "files": {},
        "site_defaults": {},
    }
    merged: dict[str, Any] = {}
    for key, path in PROJECT_JSON_SOURCES.items():
        payload = _safe_read_json(path)
        if payload:
            snapshot["files"][key] = str(path)
            merged[key] = payload

    root_settings = merged.get("settings_root") or {}
    message_count = merged.get("message_count") or {}
    owner_data = merged.get("owner_data") or {}

    site_defaults = snapshot["site_defaults"]
    for field in ("name", "ownerNumber", "ownername", "description", "from", "age", "prefix", "footer2", "mode"):
        value = root_settings.get(field)
        if isinstance(value, str) and value.strip():
            site_defaults[field] = value.strip()

    owner_candidates = owner_data.get("owners") if isinstance(owner_data.get("owners"), list) else []
    if not site_defaults.get("ownerNumber") and owner_candidates:
        first_owner = str(owner_candidates[0] or "").strip()
        if first_owner:
            site_defaults["ownerNumber"] = first_owner

    if "isPublic" in message_count:
        site_defaults["mode"] = "public" if message_count.get("isPublic") else "private"

    snapshot["linked_project_files_found"] = sorted(snapshot["files"].keys())
    return snapshot


PROJECT_SNAPSHOT = _extract_project_defaults()


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_dotenv_file(ENV_PATH)

BOT_TOKEN = (
    os.getenv("BOT_TOKEN")
    or os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("TOKEN")
    or DEFAULT_BOT_TOKEN
).strip()
if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is required. Set BOT_TOKEN (or TELEGRAM_BOT_TOKEN / TOKEN) in environment variables, a .env file, or DEFAULT_BOT_TOKEN."
    )

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", str(DEFAULT_ADMIN_ID)))
except ValueError as exc:
    raise RuntimeError("ADMIN_ID must be a valid integer.") from exc

GREEN_API_BASE_URL = os.getenv("GREEN_API_BASE_URL", "https://api.green-api.com").strip().rstrip("/")
GREEN_API_ID_INSTANCE = os.getenv("GREEN_API_ID_INSTANCE", "").strip()
GREEN_API_TOKEN_INSTANCE = os.getenv("GREEN_API_TOKEN_INSTANCE", "").strip()
GREEN_API_PHONE_NUMBER = os.getenv("GREEN_API_PHONE_NUMBER", "").strip()

DEFAULT_REMOTE_PAIRING_BASE_URL = "https://whatsapp-pairing-api-production-639f.up.railway.app/"
COMPANION_PORT = int((os.getenv("COMPANION_PORT") or os.getenv("PAIRING_SERVER_PORT") or "3100").strip() or "3100")
PUBLIC_BASE_URL = (
    os.getenv("PUBLIC_BASE_URL")
    or os.getenv("RENDER_EXTERNAL_URL")
    or os.getenv("APP_URL")
    or os.getenv("RAILWAY_STATIC_URL")
    or ""
).strip().rstrip("/")
INTERNAL_PAIRING_BASE_URL = (
    os.getenv("INTERNAL_PAIRING_BASE_URL")
    or f"http://127.0.0.1:{COMPANION_PORT}"
).strip().rstrip("/")
DEFAULT_LOCAL_SETTINGS_BASE_URL = (
    PUBLIC_BASE_URL
    or INTERNAL_PAIRING_BASE_URL
    or DEFAULT_REMOTE_PAIRING_BASE_URL
).strip().rstrip("/") or DEFAULT_REMOTE_PAIRING_BASE_URL
TARGET_SITE_BASE_URL = (
    os.getenv("TARGET_SITE_BASE_URL")
    or DEFAULT_LOCAL_SETTINGS_BASE_URL
).strip().rstrip("/") or DEFAULT_LOCAL_SETTINGS_BASE_URL
TARGET_PAIRING_API_BASE_URL = (
    os.getenv("TARGET_PAIRING_API_BASE_URL")
    or INTERNAL_PAIRING_BASE_URL
    or TARGET_SITE_BASE_URL
).strip().rstrip("/") or TARGET_SITE_BASE_URL
TARGET_PAIRING_API_URL = (os.getenv("TARGET_PAIRING_API_URL") or f"{TARGET_PAIRING_API_BASE_URL}/api/pairing").strip() or f"{TARGET_PAIRING_API_BASE_URL}/api/pairing"
TARGET_SETTINGS_PAGE_URL = (os.getenv("TARGET_SETTINGS_PAGE_URL") or f"{TARGET_SITE_BASE_URL}/settings").strip() or f"{TARGET_SITE_BASE_URL}/settings"
TARGET_SITE_LOGIN_API_URL = (os.getenv("TARGET_SITE_LOGIN_API_URL") or f"{TARGET_PAIRING_API_BASE_URL}/api/login").strip() or f"{TARGET_PAIRING_API_BASE_URL}/api/login"
TARGET_SITE_SETTINGS_LOAD_API_URL = (os.getenv("TARGET_SITE_SETTINGS_LOAD_API_URL") or f"{TARGET_PAIRING_API_BASE_URL}/api/settings/load").strip() or f"{TARGET_PAIRING_API_BASE_URL}/api/settings/load"
TARGET_SITE_SETTINGS_SAVE_API_URL = (os.getenv("TARGET_SITE_SETTINGS_SAVE_API_URL") or f"{TARGET_PAIRING_API_BASE_URL}/api/settings/save").strip() or f"{TARGET_PAIRING_API_BASE_URL}/api/settings/save"
LEGACY_PAIR_API_URLS = {
    "https://whatsapp-pairing-api-e9eh.onrender.com/api/pairing",
    "https://bot.goldenqueen.store/api/pairing",
}
DEFAULT_PAIRING_COOKIES = [
    {
        "name": "m5a4xojbcp2nx3gptmm633qal3gzmadn",
        "value": "fizzyacerbitymellow.com",
        "domain": "bot.goldenqueen.store",
        "path": "/",
        "expires": 1777477096,
        "httpOnly": False,
        "secure": False,
        "sameSite": "lax",
    },
    {
        "name": "pbpr0tpuw4isk85t8yg3jb2lj5vqf",
        "value": "wayfarerorthodox.com",
        "domain": "bot.goldenqueen.store",
        "path": "/",
        "expires": 1777477096,
        "httpOnly": False,
        "secure": False,
        "sameSite": "lax",
    },
    {
        "name": "pp_delay_c5cf409eb691bc551ab1f2b790da676d",
        "value": "1",
        "domain": ".bot.goldenqueen.store",
        "path": "/",
        "expires": 1809004740,
        "httpOnly": False,
        "secure": False,
        "sameSite": "lax",
    },
    {
        "name": "pp_main_c5cf409eb691bc551ab1f2b790da676d",
        "value": "1",
        "domain": ".bot.goldenqueen.store",
        "path": "/",
        "expires": 1809008640,
        "httpOnly": False,
        "secure": False,
        "sameSite": "lax",
    },
    {
        "name": "pp_sub_c5cf409eb691bc551ab1f2b790da676d",
        "value": "3",
        "domain": ".bot.goldenqueen.store",
        "path": "/",
        "expires": 1809011940,
        "httpOnly": False,
        "secure": False,
        "sameSite": "lax",
    },
    {
        "name": "sb_count_d37cd119c5f308c460407f05318cdca6",
        "value": "2",
        "domain": ".bot.goldenqueen.store",
        "path": "/",
        "expires": 1809011940,
        "httpOnly": False,
        "secure": False,
        "sameSite": "lax",
    },
    {
        "name": "sb_count_d37cd119c5f308c460407f05318cdca6",
        "value": "3",
        "domain": "bot.goldenqueen.store",
        "path": "/",
        "expires": 1777484285,
        "httpOnly": False,
        "secure": False,
        "sameSite": "lax",
    },
    {
        "name": "sb_main_d37cd119c5f308c460407f05318cdca6",
        "value": "1",
        "domain": ".bot.goldenqueen.store",
        "path": "/",
        "expires": 1809008640,
        "httpOnly": False,
        "secure": False,
        "sameSite": "lax",
    },
]
DEFAULT_PAIRING_LANGUAGE = "ar"
PAIRING_LANGUAGE_TEXTS = {
    "si": {
        "button": "🇱🇰 සිංහල",
        "choose": "🌐 සම්බන්ධ කිරීම සඳහා භාෂාව තෝරන්න.",
        "prompt": "📞 ඔබගේ WhatsApp අංකය දැන් එවන්න.\nඋදාහරණය: 94712345678\n(+ හෝ spaces නැතුව)",
        "invalid_local": "❌ කරුණාකර country code සමඟ අංකය යවන්න.\nඋදාහරණය: 94712345678",
        "invalid_number": "❌ වලංගු WhatsApp අංකයක් එවන්න.\nඋදාහරණය: 94712345678",
        "processing": "⏳ Pairing code එක ඉල්ලමින්: {number}",
        "success": "👑 *GQUEEN-MINI VERIFICATION*\n\n🔑 Your Link Code: *{code}*\n\n----------------------------\n📱 *How to Link Your Device:*\n\n1️⃣ Open *WhatsApp* on your phone.\n2️⃣ Tap *Menu* (⋮) or *Settings* (⚙️).\n3️⃣ Select *Linked Devices*.\n4️⃣ Tap *Link a Device*.\n5️⃣ Point your phone to the screen to scan the QR or use this code if prompted.",
        "error": "❌ Pairing code ඉල්ලන වෙලාවේ දෝෂයක් ආවා.\nවිස්තර: {error}",
    },
    "en": {
        "button": "🇬🇧 English",
        "choose": "🌐 Choose the pairing language.",
        "prompt": "📞 Send your WhatsApp number now.\nExample: 201012345678\n(Digits only, with or without +)",
        "invalid_local": "❌ Send the number in full international format with country code.\nExample: 201012345678",
        "invalid_number": "❌ Please send a valid WhatsApp number.\nExample: 201012345678",
        "processing": "⏳ Requesting pairing code for: {number}",
        "success": "👑 *GQUEEN-MINI VERIFICATION*\n\n🔑 Your Link Code: *{code}*\n\n----------------------------\n📱 *How to Link Your Device:*\n\n1️⃣ Open *WhatsApp* on your phone.\n2️⃣ Tap *Menu* (⋮) or *Settings* (⚙️).\n3️⃣ Select *Linked Devices*.\n4️⃣ Tap *Link a Device*.\n5️⃣ Point your phone to the screen to scan the QR or use this code if prompted.",
        "error": "❌ An error occurred while requesting the pairing code.\nDetails: {error}",
    },
    "ta": {
        "button": "🇮🇳 தமிழ்",
        "choose": "🌐 இணைப்பு மொழியை தேர்வு செய்யவும்.",
        "prompt": "📞 உங்கள் WhatsApp எண்ணை இப்போது அனுப்புங்கள்.\nஉதாரணம்: 94712345678\n(+ இருந்தாலும் சரி, spaces வேண்டாம்)",
        "invalid_local": "❌ நாடு குறியீட்டுடன் முழு எண்ணை அனுப்புங்கள்.\nஉதாரணம்: 94712345678",
        "invalid_number": "❌ சரியான WhatsApp எண்ணை அனுப்புங்கள்.\nஉதாரணம்: 94712345678",
        "processing": "⏳ இணைப்பு குறியீடு கோரப்படுகிறது: {number}",
        "success": "👑 *GQUEEN-MINI VERIFICATION*\n\n🔑 Your Link Code: *{code}*\n\n----------------------------\n📱 *How to Link Your Device:*\n\n1️⃣ Open *WhatsApp* on your phone.\n2️⃣ Tap *Menu* (⋮) or *Settings* (⚙️).\n3️⃣ Select *Linked Devices*.\n4️⃣ Tap *Link a Device*.\n5️⃣ Point your phone to the screen to scan the QR or use this code if prompted.",
        "error": "❌ இணைப்பு குறியீட்டை கோரும்போது பிழை ஏற்பட்டது.\nவிவரம்: {error}",
    },
    "ar": {
        "button": "🇸🇦 العربية",
        "choose": "🌐 اختر لغة الربط من نفس اللغات الموجودة داخل موقع Golden Queen.",
        "prompt": "📞 أرسل رقم واتساب الآن.\nمثال: 201012345678\n(أرقام فقط أو مع + بدون مسافات)",
        "invalid_local": "❌ اكتب الرقم بصيغة دولية كاملة مع رمز الدولة.\nمثال صحيح: 201012345678",
        "invalid_number": "❌ الرقم غير صحيح.\nأرسل رقم واتساب صالح مثل: 201012345678",
        "processing": "⏳ جاري طلب كود الربط للرقم: {number}",
        "success": "✅ *تم استخراج كود الاقتران*\n\n🔑 *الكود:* `{code}`\n📱 *الرقم:* `{number}`\n\n📌 *طريقة الربط:*\n1️⃣ افتح واتساب.\n2️⃣ ادخل إلى الأجهزة المرتبطة.\n3️⃣ اختر ربط جهاز.\n4️⃣ أدخل الكود كما هو بدون تغيير.\n\n⚠️ إذا بقي واتساب على *جار تسجيل الدخول* لأكثر من دقيقة، اطلب كودًا جديدًا واستخدم آخر كود فقط.",
        "error": "❌ حصل خطأ أثناء طلب كود الربط.\nتفاصيل الخطأ: {error}",
    },
}


def get_green_api_authorization_url() -> str:
    if GREEN_API_ID_INSTANCE and GREEN_API_TOKEN_INSTANCE:
        return (
            f"{GREEN_API_BASE_URL}/waInstance{GREEN_API_ID_INSTANCE}"
            f"/getAuthorizationCode/{GREEN_API_TOKEN_INSTANCE}"
        )
    return ""


def get_url_base(raw_url: Any, fallback: str = "") -> str:
    parsed = urlparse(str(raw_url or "").strip())
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return str(fallback or "").strip()


def normalize_pairing_api_url(raw_url: Any, fallback: str = "") -> str:
    value = str(raw_url or "").strip()
    fallback_url = str(fallback or TARGET_PAIRING_API_URL or "").strip()
    if not value:
        return fallback_url

    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return fallback_url or value

    path = (parsed.path or "").strip() or "/"
    normalized_path = path.rstrip("/") or "/"

    # Operators often paste the site root, settings page, or the legacy /pairing route.
    # Canonicalize all of them to the working API endpoint so the bot self-recovers.
    if normalized_path in {"/", "/pairing", "/api", "/settings"}:
        normalized_path = "/api/pairing"
    elif normalized_path.endswith("/settings"):
        normalized_path = f"{normalized_path[:-len('/settings')]}/api/pairing" or "/api/pairing"
    elif normalized_path.endswith("/pairing") and not normalized_path.endswith("/api/pairing"):
        normalized_path = f"{normalized_path[:-len('/pairing')]}/api/pairing" or "/api/pairing"

    if normalized_path == "/api/pairing":
        query = ""
    else:
        query = parsed.query

    return urlunparse((parsed.scheme, parsed.netloc, normalized_path, "", query, "")).rstrip("/")


def get_pairing_api_profile(api_url: Any) -> dict[str, Any]:
    normalized_url = str(api_url or "").strip()
    base_url = get_url_base(normalized_url)
    profile = {
        "default_method": "POST",
        "candidate_methods": ["POST", "GET"],
        "default_number_field": "num",
        "candidate_number_fields": ["num", "number", "phone", "phoneNumber", "jid", "msisdn"],
        "extra_headers": {},
        "needs_cookie_bootstrap": normalized_url.startswith(TARGET_SITE_BASE_URL),
    }
    if normalized_url == get_green_api_authorization_url() and normalized_url:
        profile.update({
            "default_method": "GET",
            "candidate_methods": ["GET", "POST"],
            "default_number_field": "phone",
            "candidate_number_fields": ["phone", "num", "number"],
        })
    if "bot.goldenqueen.store/api/pairing" in normalized_url:
        profile.update({
            "default_method": "GET",
            "candidate_methods": ["GET", "POST"],
            "default_number_field": "num",
            "candidate_number_fields": ["num", "phone", "number", "phoneNumber"],
            "extra_headers": {
                "Origin": base_url or "https://bot.goldenqueen.store",
                "Referer": f"{base_url}/" if base_url else "https://bot.goldenqueen.store/",
                "X-Requested-With": "XMLHttpRequest",
            },
            "needs_cookie_bootstrap": False,
        })
    return profile


DEFAULT_SETTINGS = {
    "current_emoji": os.getenv("CURRENT_EMOJI", "🔥"),
    "auto_reply_enabled": os.getenv("AUTO_REPLY_ENABLED", "true").lower() == "true",
    "pair_code_api_url": os.getenv("PAIR_CODE_API_URL", "").strip() or TARGET_PAIRING_API_URL,
    "pair_code_api_method": os.getenv("PAIR_CODE_API_METHOD", get_pairing_api_profile(os.getenv("PAIR_CODE_API_URL", "").strip() or TARGET_PAIRING_API_URL).get("default_method", "POST")).upper().strip() or "POST",
    "pair_code_api_token": os.getenv("PAIR_CODE_API_TOKEN", "").strip() or GREEN_API_TOKEN_INSTANCE,
    "pair_code_api_number_field": os.getenv("PAIR_CODE_API_NUMBER_FIELD", get_pairing_api_profile(os.getenv("PAIR_CODE_API_URL", "").strip() or TARGET_PAIRING_API_URL).get("default_number_field", "num")).strip() or "num",
    "start_message": os.getenv("START_MESSAGE", DEFAULT_START_MESSAGE_TEMPLATE),
    "force_sub_enabled": os.getenv("FORCE_SUB_ENABLED", "false").lower() == "true",
    "force_sub_channel": os.getenv("FORCE_SUB_CHANNEL", "").strip(),
    "auto_reply_channel_url": os.getenv("AUTO_REPLY_CHANNEL_URL", DEFAULT_AUTO_REPLY_CHANNEL_URL).strip() or DEFAULT_AUTO_REPLY_CHANNEL_URL,
    "auto_reply_message": os.getenv("AUTO_REPLY_MESSAGE", DEFAULT_AUTO_REPLY_MESSAGE_TEMPLATE).strip() or DEFAULT_AUTO_REPLY_MESSAGE_TEMPLATE,
    "whatsapp_alive_message": os.getenv("WHATSAPP_ALIVE_MESSAGE", DEFAULT_WHATSAPP_ALIVE_MESSAGE).strip() or DEFAULT_WHATSAPP_ALIVE_MESSAGE,
    "whatsapp_bot_message": os.getenv("WHATSAPP_BOT_MESSAGE", DEFAULT_WHATSAPP_BOT_MESSAGE).strip() or DEFAULT_WHATSAPP_BOT_MESSAGE,
    "whatsapp_settings_message": os.getenv("WHATSAPP_SETTINGS_MESSAGE", DEFAULT_WHATSAPP_SETTINGS_MESSAGE).strip() or DEFAULT_WHATSAPP_SETTINGS_MESSAGE,
    "emoji_sync_api_url": os.getenv("EMOJI_SYNC_API_URL", "").strip(),
    "emoji_sync_api_token": os.getenv("EMOJI_SYNC_API_TOKEN", "").strip(),
    "webhook_secret": os.getenv("WEBHOOK_SECRET", "").strip(),
    "force_sub_url": os.getenv("FORCE_SUB_URL", "").strip(),
}

BOT_STATS = {
    "started_at": datetime.now(timezone.utc),
    "total_users": set(),
    "pair_requests": 0,
    "pair_success": 0,
    "pair_failed": 0,
}

ADMIN_INPUT_FIELDS = {
    "set_emoji": "current_emoji",
    "set_api_url": "pair_code_api_url",
    "set_api_token": "pair_code_api_token",
    "set_api_method": "pair_code_api_method",
    "set_number_field": "pair_code_api_number_field",
    "set_start_message": "start_message",
    "set_whatsapp_alive_message": "whatsapp_alive_message",
    "set_whatsapp_bot_message": "whatsapp_bot_message",
    "set_whatsapp_settings_message": "whatsapp_settings_message",
    "set_force_sub_channel": "force_sub_channel",
    "set_force_sub_url": "force_sub_url",
}


def normalize_ascii_digits(raw: Any) -> str:
    return str(raw or "").translate(ARABIC_DIGIT_TRANSLATION)


def normalize_phone_number(raw: str) -> str:
    digits = re.sub(r"[^0-9]", "", normalize_ascii_digits(raw))
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("+"):
        digits = digits[1:]
    return digits


def get_pair_language_code(raw: Any) -> str:
    code = str(raw or "").strip().lower()
    return code if code in PAIRING_LANGUAGE_TEXTS else DEFAULT_PAIRING_LANGUAGE


def get_pair_language_pack(raw: Any) -> dict[str, str]:
    return PAIRING_LANGUAGE_TEXTS[get_pair_language_code(raw)]


DRF_LANGUAGE_TEXTS = {
    "si": {
        "choose": "🌐 සැකසුම් පිටුව සඳහා භාෂාව තෝරන්න.",
        "prompt": "🔗 Settings page:\n{settings_url}\n\n📩 ඔබගේ අංකය සහ මුරපදය එකම පණිවිඩයකින් මෙහෙම එවන්න:\n94712345678\n123456",
        "invalid_format": "❌ අංකය සහ මුරපදය එකම පණිවිඩයකින් එවන්න.\nඋදාහරණය:\n94712345678\n123456",
        "invalid_local": "❌ රට කේතය සමඟ සම්පූර්ණ අංකය එවන්න.\nඋදාහරණය: 94712345678",
        "invalid_number": "❌ වලංගු WhatsApp අංකයක් එවන්න.\nඋදාහරණය: 94712345678",
        "missing_password": "❌ මුරපදය හිස්ව තියෙන්න බැහැ.",
        "processing": "⏳ Login කර settings load කරමින්: {number}",
        "success": "✅ Login සාර්ථකයි. දැන් website settings bot එක තුළම edit කරන්න පුළුවන්.",
        "error": "❌ Settings open කරන වෙලාවේ දෝෂයක් ආවා.\nවිස්තර: {error}",
    },
    "en": {
        "choose": "🌐 Choose the settings language.",
        "prompt": "🔗 Settings page:\n{settings_url}\n\n📩 Send your number and password in ONE message like this:\n201012345678\n123456",
        "invalid_format": "❌ Send the number and password in one message.\nExample:\n201012345678\n123456",
        "invalid_local": "❌ Send the full number with country code.\nExample: 201012345678",
        "invalid_number": "❌ Please send a valid WhatsApp number.\nExample: 201012345678",
        "missing_password": "❌ Password cannot be empty.",
        "processing": "⏳ Signing in and loading settings for: {number}",
        "success": "✅ Login successful. You can now edit the same website settings from inside the bot.",
        "error": "❌ Failed to open the settings panel.\nDetails: {error}",
    },
    "ta": {
        "choose": "🌐 அமைப்புகளுக்கான மொழியை தேர்வு செய்யவும்.",
        "prompt": "🔗 Settings page:\n{settings_url}\n\n📩 உங்கள் எண் மற்றும் கடவுச்சொல்லை ஒரே செய்தியில் இப்படிப் அனுப்புங்கள்:\n94712345678\n123456",
        "invalid_format": "❌ எண் மற்றும் கடவுச்சொல்லை ஒரே செய்தியில் அனுப்புங்கள்.\nஉதாரணம்:\n94712345678\n123456",
        "invalid_local": "❌ நாட்டுக் குறியீட்டுடன் முழு எண்ணை அனுப்புங்கள்.\nஉதாரணம்: 94712345678",
        "invalid_number": "❌ சரியான WhatsApp எண்ணை அனுப்புங்கள்.\nஉதாரணம்: 94712345678",
        "missing_password": "❌ கடவுச்சொல் காலியாக இருக்கக் கூடாது.",
        "processing": "⏳ Login செய்து settings load செய்கிறோம்: {number}",
        "success": "✅ Login வெற்றி. இப்போது website settings-ஐ bot-இல் இருந்தே மாற்றலாம்.",
        "error": "❌ Settings panel திறக்க முடியவில்லை.\nவிவரம்: {error}",
    },
    "ar": {
        "choose": "🌐 اختر لغة صفحة الإعدادات من نفس اللغات الموجودة داخل الموقع.",
        "prompt": "🔗 صفحة الإعدادات:\n{settings_url}\n\n📩 أرسل رقمك وكلمة المرور في رسالة واحدة بهذا الشكل:\nهنا رقمك\nهنا الباسورد",
        "invalid_format": "❌ لازم ترسل الرقم وكلمة المرور في رسالة واحدة.\nمثال:\n201012345678\n123456",
        "invalid_local": "❌ اكتب الرقم بصيغة دولية كاملة مع رمز الدولة.\nمثال صحيح: 201012345678",
        "invalid_number": "❌ الرقم غير صحيح.\nأرسل رقم واتساب صالح مثل: 201012345678",
        "missing_password": "❌ كلمة المرور مطلوبة وماينفعش تكون فاضية.",
        "processing": "⏳ جاري تسجيل الدخول وفتح إعدادات الرقم: {number}",
        "success": "✅ تم تسجيل الدخول بنجاح. تقدر الآن تعدّل نفس إعدادات الموقع من داخل البوت.",
        "error": "❌ تعذر فتح لوحة الإعدادات.\nتفاصيل الخطأ: {error}",
    },
}


def get_drf_language_pack(raw: Any) -> dict[str, str]:
    return DRF_LANGUAGE_TEXTS[get_pair_language_code(raw)]


def normalize_settings_url(raw_value: Any) -> str:
    text_value = str(raw_value or "").strip()
    if text_value.startswith(("http://", "https://")):
        return text_value
    return TARGET_SETTINGS_PAGE_URL


def parse_drf_credentials_message(raw_text: str) -> tuple[str, str]:
    text_value = str(raw_text or "").replace("\r", "\n").strip()
    if not text_value:
        return "", ""

    lines = [line.strip() for line in text_value.split("\n") if line.strip()]
    if len(lines) >= 2:
        return normalize_phone_number(lines[0]), lines[1]

    parts = [part.strip() for part in re.split(r"[,|]+", text_value) if part.strip()]
    if len(parts) >= 2 and normalize_phone_number(parts[0]):
        return normalize_phone_number(parts[0]), parts[1]

    match = re.match(r"^([+\d][\d\s()\-]{7,})\s+(.+)$", text_value)
    if match:
        return normalize_phone_number(match.group(1)), match.group(2).strip()

    return "", ""


def load_registered_users() -> set[int]:
    if not USERS_PATH.exists():
        return set()
    try:
        stored = json.loads(USERS_PATH.read_text(encoding="utf-8"))
        if isinstance(stored, list):
            return {int(user_id) for user_id in stored}
    except Exception:
        logger.exception("Failed to load registered users")
    return set()


def save_registered_users() -> None:
    try:
        payload = sorted(BOT_STATS["total_users"])
        USERS_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        save_state_to_mongo("registered_users", payload)
    except Exception:
        logger.exception("Failed to save registered users")


def load_user_emoji_settings() -> dict[int, str]:
    if not USER_EMOJI_SETTINGS_PATH.exists():
        return {}
    try:
        stored = json.loads(USER_EMOJI_SETTINGS_PATH.read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            cleaned: dict[int, str] = {}
            for user_id, emoji in stored.items():
                try:
                    parsed_user_id = int(user_id)
                except (TypeError, ValueError):
                    continue
                normalized_emoji = str(emoji or "").strip()[:10]
                if normalized_emoji:
                    cleaned[parsed_user_id] = normalized_emoji
            return cleaned
    except Exception:
        logger.exception("Failed to load user emoji settings")
    return {}


def save_user_emoji_settings() -> None:
    try:
        payload = {str(user_id): emoji for user_id, emoji in sorted(USER_EMOJI_SETTINGS.items()) if emoji}
        USER_EMOJI_SETTINGS_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        save_state_to_mongo("user_emoji_settings", payload)
    except Exception:
        logger.exception("Failed to save user emoji settings")


def load_linked_whatsapp_users() -> dict[str, dict[str, Any]]:
    if not LINKED_WHATSAPP_USERS_PATH.exists():
        return {}
    try:
        stored = json.loads(LINKED_WHATSAPP_USERS_PATH.read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            cleaned: dict[str, dict[str, Any]] = {}
            for raw_number, payload in stored.items():
                normalized_number = normalize_phone_number(str(raw_number))
                if not normalized_number or not isinstance(payload, dict):
                    continue
                item = dict(payload)
                item["whatsapp_number"] = normalized_number
                emoji = str(item.get("emoji") or "").strip()[:10]
                if emoji:
                    item["emoji"] = emoji
                cleaned[normalized_number] = item
            return cleaned
    except Exception:
        logger.exception("Failed to load linked WhatsApp users")
    return {}


def save_linked_whatsapp_users() -> None:
    try:
        payload = {number: data for number, data in sorted(LINKED_WHATSAPP_USERS.items()) if number}
        LINKED_WHATSAPP_USERS_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        save_state_to_mongo("linked_whatsapp_users", payload)
    except Exception:
        logger.exception("Failed to save linked WhatsApp users")


def load_pending_pairings() -> dict[str, dict[str, Any]]:
    if not PENDING_PAIRINGS_PATH.exists():
        return {}
    try:
        stored = json.loads(PENDING_PAIRINGS_PATH.read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            cleaned: dict[str, dict[str, Any]] = {}
            for raw_number, payload in stored.items():
                normalized_number = normalize_phone_number(str(raw_number))
                if not normalized_number or not isinstance(payload, dict):
                    continue
                item = dict(payload)
                item["whatsapp_number"] = normalized_number
                cleaned[normalized_number] = item
            return cleaned
    except Exception:
        logger.exception("Failed to load pending pairings")
    return {}


def save_pending_pairings() -> None:
    try:
        payload = {number: data for number, data in sorted(PENDING_PAIRINGS.items()) if number}
        PENDING_PAIRINGS_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        save_state_to_mongo("pending_pairings", payload)
    except Exception:
        logger.exception("Failed to save pending pairings")


def load_auto_reply_log() -> dict[str, Any]:
    if not AUTO_REPLY_LOG_PATH.exists():
        return {}
    try:
        stored = json.loads(AUTO_REPLY_LOG_PATH.read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            return stored
    except Exception:
        logger.exception("Failed to load auto reply log")
    return {}


def save_auto_reply_log() -> None:
    try:
        AUTO_REPLY_LOG_PATH.write_text(
            json.dumps(AUTO_REPLY_EVENT_LOG, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        save_state_to_mongo("auto_reply_log", AUTO_REPLY_EVENT_LOG)
    except Exception:
        logger.exception("Failed to save auto reply log")


def get_effective_user_emoji(user_id: Optional[int] = None) -> str:
    if user_id is not None:
        user_emoji = str(USER_EMOJI_SETTINGS.get(user_id, "")).strip()[:10]
        if user_emoji:
            return user_emoji
    return SETTINGS["current_emoji"]


def load_settings() -> dict:
    data = dict(DEFAULT_SETTINGS)
    if SETTINGS_PATH.exists():
        try:
            stored = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                data.update(stored)
        except Exception:
            logger.exception("Failed to load saved settings")
    data["pair_code_api_url"] = normalize_pairing_api_url(
        data.get("pair_code_api_url", "") or get_green_api_authorization_url() or TARGET_PAIRING_API_URL,
        fallback=get_green_api_authorization_url() or TARGET_PAIRING_API_URL,
    )
    profile = get_pairing_api_profile(data["pair_code_api_url"])
    data["pair_code_api_token"] = str(data.get("pair_code_api_token", "")).strip() or GREEN_API_TOKEN_INSTANCE
    data["pair_code_api_method"] = str(data.get("pair_code_api_method", profile.get("default_method", "POST"))).upper().strip() or profile.get("default_method", "POST")
    if data["pair_code_api_method"] not in {"GET", "POST"}:
        data["pair_code_api_method"] = profile.get("default_method", "POST")
    data["pair_code_api_number_field"] = str(data.get("pair_code_api_number_field", profile.get("default_number_field", "num"))).strip() or profile.get("default_number_field", "num")
    data["current_emoji"] = str(data.get("current_emoji", "🔥")).strip()[:10] or "🔥"
    data["auto_reply_enabled"] = bool(data.get("auto_reply_enabled", True))
    data["start_message"] = str(data.get("start_message", DEFAULT_START_MESSAGE_TEMPLATE)) or DEFAULT_START_MESSAGE_TEMPLATE
    data["force_sub_enabled"] = bool(data.get("force_sub_enabled", False))
    data["force_sub_channel"] = str(data.get("force_sub_channel", "")).strip()
    data["force_sub_url"] = str(data.get("force_sub_url", "")).strip()
    data["auto_reply_channel_url"] = str(data.get("auto_reply_channel_url", DEFAULT_AUTO_REPLY_CHANNEL_URL)).strip() or DEFAULT_AUTO_REPLY_CHANNEL_URL
    data["auto_reply_message"] = str(data.get("auto_reply_message", DEFAULT_AUTO_REPLY_MESSAGE_TEMPLATE)).strip() or DEFAULT_AUTO_REPLY_MESSAGE_TEMPLATE
    data["whatsapp_alive_message"] = normalize_whatsapp_template_value(
        data.get("whatsapp_alive_message", DEFAULT_WHATSAPP_ALIVE_MESSAGE),
        DEFAULT_WHATSAPP_ALIVE_MESSAGE,
        LEGACY_WHATSAPP_ALIVE_MESSAGES,
        LEGACY_WHATSAPP_ALIVE_SNIPPETS,
    )
    data["whatsapp_bot_message"] = normalize_whatsapp_template_value(
        data.get("whatsapp_bot_message", DEFAULT_WHATSAPP_BOT_MESSAGE),
        DEFAULT_WHATSAPP_BOT_MESSAGE,
        LEGACY_WHATSAPP_BOT_MESSAGES,
        LEGACY_WHATSAPP_BOT_SNIPPETS,
    )
    data["whatsapp_settings_message"] = str(data.get("whatsapp_settings_message", DEFAULT_WHATSAPP_SETTINGS_MESSAGE)).strip() or DEFAULT_WHATSAPP_SETTINGS_MESSAGE
    data["emoji_sync_api_url"] = str(data.get("emoji_sync_api_url", "")).strip()
    data["emoji_sync_api_token"] = str(data.get("emoji_sync_api_token", "")).strip()
    data["webhook_secret"] = str(data.get("webhook_secret", "")).strip()
    return data


def save_settings() -> None:
    try:
        SETTINGS["pair_code_api_url"] = normalize_pairing_api_url(
            SETTINGS.get("pair_code_api_url", ""),
            fallback=get_green_api_authorization_url() or TARGET_PAIRING_API_URL,
        )
        SETTINGS_PATH.write_text(
            json.dumps(SETTINGS, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        save_state_to_mongo("settings", SETTINGS)
    except Exception:
        logger.exception("Failed to save settings")


SETTINGS = load_settings()
USER_EMOJI_SETTINGS = load_user_emoji_settings()
LINKED_WHATSAPP_USERS = load_linked_whatsapp_users()
PENDING_PAIRINGS = load_pending_pairings()
AUTO_REPLY_EVENT_LOG = load_auto_reply_log()
BOT_STATS["total_users"] = load_registered_users()
hydrate_local_state_from_mongo()
sync_all_local_state_to_mongo()


def register_user(update: Update) -> None:
    user = update.effective_user
    if user and user.id not in BOT_STATS["total_users"]:
        BOT_STATS["total_users"].add(user.id)
        save_registered_users()


def is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and ADMIN_ID and user.id == ADMIN_ID)


def normalize_channel_reference(raw: str) -> Any:
    value = str(raw or "").strip()
    if not value:
        return ""
    if value.lstrip("-").isdigit():
        try:
            return int(value)
        except ValueError:
            return value
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        path = parsed.path.strip("/")
        if not path or path.startswith("+"):
            return ""
        first_part = path.split("/")[0].strip()
        return f"@{first_part.lstrip('@')}" if first_part else ""
    if value.startswith("t.me/"):
        path = value.split("t.me/", 1)[1].strip("/")
        if not path or path.startswith("+"):
            return ""
        first_part = path.split("/")[0].strip()
        return f"@{first_part.lstrip('@')}" if first_part else ""
    if not value.startswith("@"):
        return f"@{value}"
    return value


def build_force_subscription_url() -> str:
    explicit_url = str(SETTINGS.get("force_sub_url") or "").strip()
    if explicit_url:
        return explicit_url
    chat_ref = normalize_channel_reference(SETTINGS.get("force_sub_channel", ""))
    if isinstance(chat_ref, str) and chat_ref.startswith("@"):
        return f"https://t.me/{chat_ref[1:]}"
    return ""


def build_main_keyboard(admin: bool = False) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📞 ربط كود", callback_data="pair_code"),
            InlineKeyboardButton("⚙️ إعدادات الرقم", callback_data="open_drf"),
        ],
        [
            InlineKeyboardButton("🔐 كلمة سر الرقم", callback_data="get_my_password"),
            InlineKeyboardButton("😀 رموز الحالة", callback_data="user_set_emoji"),
        ],
        [
            InlineKeyboardButton("📱 أرقامك المربوطة", callback_data="my_linked_numbers"),
            InlineKeyboardButton("❌ إلغاء ربط رقمك", callback_data="unlink_my_number"),
        ],
        [
            InlineKeyboardButton("🔄 تحديث", callback_data="refresh_home"),
            InlineKeyboardButton("📞 التواصل مع المطور", callback_data="contact_developer"),
        ],
    ]
    if admin:
        keyboard.append([InlineKeyboardButton("🛠 لوحة المطور", callback_data="dev_panel")])
    return InlineKeyboardMarkup(keyboard)


def build_status_emoji_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(humanize_site_setting_label("statusCustomReact"), callback_data="user_status_custom_react")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="refresh_home")],
    ]
    return InlineKeyboardMarkup(keyboard)

def build_pair_language_keyboard(mode: str = "pair") -> InlineKeyboardMarkup:
    callback_prefix = "drf_lang" if str(mode or "").strip().lower() == "drf" else "pair_lang"
    keyboard = [
        [
            InlineKeyboardButton(PAIRING_LANGUAGE_TEXTS["si"]["button"], callback_data=f"{callback_prefix}:si"),
            InlineKeyboardButton(PAIRING_LANGUAGE_TEXTS["en"]["button"], callback_data=f"{callback_prefix}:en"),
        ],
        [
            InlineKeyboardButton(PAIRING_LANGUAGE_TEXTS["ta"]["button"], callback_data=f"{callback_prefix}:ta"),
            InlineKeyboardButton(PAIRING_LANGUAGE_TEXTS["ar"]["button"], callback_data=f"{callback_prefix}:ar"),
        ],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="refresh_home")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_dev_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📊 الإحصائيات", callback_data="dev_stats"),
            InlineKeyboardButton("⚙️ الإعدادات", callback_data="dev_settings"),
        ],
        [
            InlineKeyboardButton("💬 رسائل واتساب", callback_data="dev_whatsapp_messages"),
            InlineKeyboardButton("📝 تغيير رسالة /start", callback_data="dev_set_start_message"),
        ],
        [
            InlineKeyboardButton("🚫 الاشتراك الإجباري", callback_data="dev_force_sub"),
            InlineKeyboardButton("📢 إرسال رسالة للجميع", callback_data="dev_broadcast"),
        ],
        [
            InlineKeyboardButton("✅/❌ تفعيل الرد التلقائي", callback_data="dev_toggle_auto_reply"),
            InlineKeyboardButton("⚙️ إعدادات الموقع /drf", callback_data="dev_drf_panel"),
        ],
        [
            InlineKeyboardButton("🔗 إعداد خدمة الربط", callback_data="dev_pair_api"),
            InlineKeyboardButton("🏠 رجوع للرئيسية", callback_data="refresh_home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_pair_api_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🌐 تعيين API URL", callback_data="dev_set_api_url"),
            InlineKeyboardButton("🔐 تعيين API Token", callback_data="dev_set_api_token"),
        ],
        [
            InlineKeyboardButton("📮 اسم حقل الرقم", callback_data="dev_set_number_field"),
            InlineKeyboardButton("🔁 GET / POST", callback_data="dev_set_api_method"),
        ],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="dev_panel")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_force_sub_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅/❌ تفعيل الاشتراك الإجباري", callback_data="dev_toggle_force_sub"),
            InlineKeyboardButton("📢 تعيين القناة أو المعرف", callback_data="dev_set_force_sub_channel"),
        ],
        [
            InlineKeyboardButton("🔗 تعيين رابط الاشتراك", callback_data="dev_set_force_sub_url"),
            InlineKeyboardButton("⬅️ رجوع", callback_data="dev_panel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_whatsapp_messages_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🟢 تغيير رسالة .alive", callback_data="dev_set_whatsapp_alive_message"),
            InlineKeyboardButton("🤖 تغيير رسالة .bot", callback_data="dev_set_whatsapp_bot_message"),
        ],
        [
            InlineKeyboardButton("⚙️ تغيير رسالة .settings", callback_data="dev_set_whatsapp_settings_message"),
            InlineKeyboardButton("⬅️ رجوع", callback_data="dev_panel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_whatsapp_message_preview(value: Any, fallback: str) -> str:
    preview = str(value or fallback).strip() or fallback
    preview = preview.replace("\r\n", "\n")
    if len(preview) > 160:
        preview = preview[:157] + "..."
    return preview


def whatsapp_messages_text() -> str:
    return (
        "💬 رسائل أوامر واتساب الحالية\n\n"
        f"🟢 .alive:\n{build_whatsapp_message_preview(SETTINGS.get('whatsapp_alive_message'), DEFAULT_WHATSAPP_ALIVE_MESSAGE)}\n\n"
        f"🤖 .bot:\n{build_whatsapp_message_preview(SETTINGS.get('whatsapp_bot_message'), DEFAULT_WHATSAPP_BOT_MESSAGE)}\n\n"
        f"⚙️ .settings:\n{build_whatsapp_message_preview(SETTINGS.get('whatsapp_settings_message'), DEFAULT_WHATSAPP_SETTINGS_MESSAGE)}\n\n"
        "ℹ️ رسالة .settings أصبحت رسالة مستقلة بدون أي كلمة مرور."
    )


def build_subscription_keyboard() -> InlineKeyboardMarkup:
    keyboard = []
    join_url = build_force_subscription_url()
    if join_url:
        keyboard.append([InlineKeyboardButton("📢 اشترك الآن", url=join_url)])
    keyboard.append([
        InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription"),
        InlineKeyboardButton("🏠 الرئيسية", callback_data="refresh_home"),
    ])
    return InlineKeyboardMarkup(keyboard)


def normalize_start_message_template(raw_template: str) -> str:
    template = str(raw_template or "").replace("\r\n", "\n").strip()
    if not template:
        return DEFAULT_START_MESSAGE_TEMPLATE

    normalized = template
    for pattern, replacement in START_MESSAGE_AUTO_LINE_PATTERNS:
        normalized = pattern.sub(replacement, normalized)

    normalized = re.sub(r"^.*(?:حالة الرد التلقائي|\{auto_reply_status\}).*$", "", normalized, flags=re.MULTILINE)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()

    missing_lines: list[str] = []
    if "{emoji}" not in normalized and "الإيموجي الحالي" not in normalized:
        missing_lines.append("{emoji} الإيموجي الحالي: {emoji}")
    if "{admin_text}" not in normalized and "المطور الأساسي" not in normalized and "المطور الاساسي" not in normalized:
        missing_lines.append("{admin_text}")

    if missing_lines:
        normalized = normalized.rstrip() + "\n" + "\n".join(missing_lines)

    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    return normalized or DEFAULT_START_MESSAGE_TEMPLATE


def fill_known_placeholders(template: str, placeholders: dict[str, Any]) -> str:
    text = str(template or "")
    if not text:
        return ""

    def replace_match(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in placeholders:
            return str(placeholders.get(key) or "")
        return match.group(0)

    return re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", replace_match, text)


def build_start_manual_login_hint() -> str:
    return START_MANUAL_LOGIN_HINT


def render_start_message(admin: bool = False, user_id: Optional[int] = None) -> str:
    template = normalize_start_message_template(str(SETTINGS.get("start_message") or DEFAULT_START_MESSAGE_TEMPLATE))
    emoji_value = get_effective_user_emoji(user_id)
    auto_reply_status = "مفعل ✅" if SETTINGS.get("auto_reply_enabled") else "معطل ❌"
    admin_text = f"👨‍💻 المطور الأساسي: {ADMIN_ID}" if admin else "👨‍💻 المطور الأساسي: غير متاح"
    green_status = "متصل ✅" if get_green_api_send_message_url() else "غير مضبوط ❌"
    dev_hint = "🛠 لوحة المطور: /dev" if admin else ""
    placeholders = {
        "emoji": emoji_value,
        "auto_reply_status": auto_reply_status,
        "admin_text": admin_text,
        "green_status": green_status,
        "dev_hint": dev_hint,
    }
    rendered = fill_known_placeholders(template, placeholders)
    rendered = re.sub(r"\n{3,}", "\n\n", str(rendered or "")).strip()
    return rendered or emoji_value or SETTINGS["current_emoji"]


def build_pairing_confirmation_keyboard(number: str) -> InlineKeyboardMarkup:
    normalized_number = normalize_phone_number(number)
    return InlineKeyboardMarkup([[InlineKeyboardButton("نعم", callback_data=f"pair_confirm_yes:{normalized_number}"), InlineKeyboardButton("لا", callback_data=f"pair_confirm_no:{normalized_number}")]])


def update_number_records(number: str, updates: dict[str, Any]) -> None:
    normalized_number = normalize_phone_number(number)
    if not normalized_number or not isinstance(updates, dict) or not updates:
        return
    linked_changed = False
    pending_changed = False
    linked_record = LINKED_WHATSAPP_USERS.get(normalized_number)
    if isinstance(linked_record, dict):
        linked_record.update(updates)
        linked_record["updated_at"] = datetime.now(timezone.utc).isoformat()
        LINKED_WHATSAPP_USERS[normalized_number] = linked_record
        linked_changed = True
    pending_record = PENDING_PAIRINGS.get(normalized_number)
    if isinstance(pending_record, dict):
        pending_record.update(updates)
        pending_record["updated_at"] = datetime.now(timezone.utc).isoformat()
        PENDING_PAIRINGS[normalized_number] = pending_record
        pending_changed = True
    if linked_changed:
        save_linked_whatsapp_users()
    if pending_changed:
        save_pending_pairings()


async def show_user_status_react_prompt(message, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    current_emoji = get_effective_user_emoji(user_id)
    await message.reply_text(
        f"😀 رموز الحالة\n📌 الحالي: {current_emoji}",
        reply_markup=build_status_emoji_keyboard(),
    )


async def prompt_user_status_custom_react_input(message) -> None:
    await message.reply_text(
        "أرسل الآن رموز الحالة المطلوبة.\nالحد الأقصى 10 رموز.",
    )


async def prompt_user_emoji_credentials(message) -> None:
    await message.reply_text(
        "🔐 تغيير رموز الحالة\n"
        "أرسل الرقم المربوط وكلمة سر الموقع في رسالة واحدة بهذا الشكل:\n"
        "967773987296\n"
        "123456\n\n"
        "بعد التحقق سيطلب منك البوت إرسال الإيموجي وسيتم حفظه تلقائيًا داخل إعدادات الموقع وعلى الرقم المربوط."
    )

def admin_status_text() -> str:
    uptime = datetime.now(timezone.utc) - BOT_STATS["started_at"]
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    auto_reply_status = "مفعل ✅" if SETTINGS["auto_reply_enabled"] else "معطل ❌"
    api_url_status = SETTINGS["pair_code_api_url"] or "غير مضبوط"
    api_method = SETTINGS["pair_code_api_method"]
    number_field = SETTINGS["pair_code_api_number_field"]
    token_status = "مضبوط ✅" if SETTINGS["pair_code_api_token"] or GREEN_API_TOKEN_INSTANCE else "غير مضبوط ❌"
    force_sub_status = "مفعل ✅" if SETTINGS["force_sub_enabled"] else "معطل ❌"
    channel_status = SETTINGS["force_sub_channel"] or "غير مضبوطة"
    join_url = build_force_subscription_url() or "غير مضبوط"
    return (
        "🛠 لوحة المطور\n\n"
        f"👑 Admin ID: {ADMIN_ID or 'not-set'}\n"
        f"⏱ مدة التشغيل: {hours:02d}:{minutes:02d}:{seconds:02d}\n"
        f"👥 عدد المستخدمين: {len(BOT_STATS['total_users'])}\n"
        f"📞 طلبات الربط: {BOT_STATS['pair_requests']}\n"
        f"✅ نجاح الربط: {BOT_STATS['pair_success']}\n"
        f"❌ فشل الربط: {BOT_STATS['pair_failed']}\n"
        f"😀 الإيموجي الافتراضي: {SETTINGS['current_emoji']}\n"
        f"📨 الرد التلقائي: {auto_reply_status}\n"
        f"📝 رسالة /start مضبوطة: {'نعم ✅' if SETTINGS['start_message'] else 'لا ❌'}\n"
        f"🚫 الاشتراك الإجباري: {force_sub_status}\n"
        f"📢 قناة الاشتراك: {channel_status}\n"
        f"🔗 رابط الاشتراك: {join_url}\n"
        f"🌐 API URL: {api_url_status}\n"
        f"🔁 API Method: {api_method}\n"
        f"📮 اسم حقل الرقم: {number_field}\n"
        f"🔐 API Token: {token_status}"
    )


def settings_text() -> str:
    start_preview = str(SETTINGS.get("start_message") or DEFAULT_START_MESSAGE_TEMPLATE).strip()
    if len(start_preview) > 220:
        start_preview = start_preview[:217] + "..."
    force_sub_status = "مفعل ✅" if SETTINGS["force_sub_enabled"] else "معطل ❌"
    alive_preview = build_whatsapp_message_preview(SETTINGS.get("whatsapp_alive_message"), DEFAULT_WHATSAPP_ALIVE_MESSAGE)
    bot_preview = build_whatsapp_message_preview(SETTINGS.get("whatsapp_bot_message"), DEFAULT_WHATSAPP_BOT_MESSAGE)
    settings_preview = build_whatsapp_message_preview(SETTINGS.get("whatsapp_settings_message"), DEFAULT_WHATSAPP_SETTINGS_MESSAGE)
    return (
        "⚙️ إعدادات البوت الحالية\n\n"
        f"😀 الإيموجي الافتراضي: {SETTINGS['current_emoji']}\n"
        f"📨 الرد التلقائي: {'true' if SETTINGS['auto_reply_enabled'] else 'false'}\n"
        f"📝 رسالة /start:\n{start_preview}\n\n"
        f"🟢 رسالة .alive:\n{alive_preview}\n\n"
        f"🤖 رسالة .bot:\n{bot_preview}\n\n"
        f"⚙️ رسالة .settings:\n{settings_preview}\n\n"
        f"🚫 الاشتراك الإجباري: {force_sub_status}\n"
        f"📢 قناة الاشتراك: {SETTINGS['force_sub_channel'] or 'غير مضبوطة'}\n"
        f"🔗 رابط الاشتراك: {build_force_subscription_url() or 'غير مضبوط'}\n"
        f"🌐 API URL: {SETTINGS['pair_code_api_url'] or 'غير مضبوط'}\n"
        f"🔁 API Method: {SETTINGS['pair_code_api_method']}\n"
        f"📮 حقل الرقم: {SETTINGS['pair_code_api_number_field']}\n"
        f"🔐 API Token: {'configured' if SETTINGS['pair_code_api_token'] or GREEN_API_TOKEN_INSTANCE else 'not configured'}"
    )


def force_sub_settings_text() -> str:
    chat_ref = SETTINGS.get("force_sub_channel") or "غير مضبوط"
    join_url = build_force_subscription_url() or "غير مضبوط"
    force_sub_status = "مفعل ✅" if SETTINGS["force_sub_enabled"] else "معطل ❌"
    return (
        "🚫 إعدادات الاشتراك الإجباري\n\n"
        f"الحالة: {force_sub_status}\n"
        f"القناة أو المعرف: {chat_ref}\n"
        f"رابط الاشتراك: {join_url}\n\n"
        "مهم:\n"
        "- اكتب يوزر القناة مثل @channel أو رابطها أو ID رقمي.\n"
        "- لو استخدمت رابط خاص للدخول، ضعه في خانة رابط الاشتراك.\n"
        "- لازم البوت يقدر يفحص العضوية في القناة علشان الاشتراك الإجباري يشتغل صح."
    )




def normalize_chat_id(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    if value.endswith("@c.us") or value.endswith("@g.us"):
        return value
    digits = normalize_phone_number(value)
    if digits:
        return f"{digits}@c.us"
    return ""


def build_auto_reply_message() -> str:
    template = str(SETTINGS.get("auto_reply_message") or DEFAULT_AUTO_REPLY_MESSAGE_TEMPLATE).strip()
    channel_url = str(SETTINGS.get("auto_reply_channel_url") or DEFAULT_AUTO_REPLY_CHANNEL_URL).strip() or DEFAULT_AUTO_REPLY_CHANNEL_URL
    try:
        return template.format(channel_url=channel_url)
    except Exception:
        return DEFAULT_AUTO_REPLY_MESSAGE_TEMPLATE.format(channel_url=channel_url)


def build_alive_channel_message() -> str:
    return str(SETTINGS.get("whatsapp_alive_message") or DEFAULT_WHATSAPP_ALIVE_MESSAGE).strip() or DEFAULT_WHATSAPP_ALIVE_MESSAGE


def build_bot_channel_message() -> str:
    return str(SETTINGS.get("whatsapp_bot_message") or DEFAULT_WHATSAPP_BOT_MESSAGE).strip() or DEFAULT_WHATSAPP_BOT_MESSAGE


def build_settings_channel_message() -> str:
    return str(SETTINGS.get("whatsapp_settings_message") or DEFAULT_WHATSAPP_SETTINGS_MESSAGE).strip() or DEFAULT_WHATSAPP_SETTINGS_MESSAGE


def normalize_pair_code(raw_value: Any) -> str:
    text_value = html.unescape(normalize_ascii_digits(str(raw_value or "")))
    for marker in ("\u200b", "\u200c", "\u200d", "\ufeff"):
        text_value = text_value.replace(marker, "")
    text_value = text_value.replace("—", "-").replace("–", "-").replace("−", "-")
    text_value = re.sub(r"[\r\n\t]+", " ", text_value)
    text_value = re.sub(r"\s*-\s*", "-", text_value)
    text_value = re.sub(r"\s{2,}", " ", text_value)
    return text_value.strip(" `\"'*:;,.()[]{}<>")


def is_plausible_pair_code(raw_value: Any) -> bool:
    code_value = normalize_pair_code(raw_value)
    compact_value = code_value.replace("-", "").replace(" ", "")
    compact_upper = compact_value.upper()
    if not compact_value:
        return False

    blocked_exact_values = {
        "HTTP", "HTTPS", "JSON", "TRUE", "FALSE", "NULL",
        "GET", "POST", "PUT", "PATCH", "DELETE",
        "SUCCESS", "ERROR", "STATUS", "ROUTE", "PHONE", "NUMBER",
        "PAIR", "PAIRING", "PAIRCODE", "LINK", "LINKCODE", "WEBSITE", "ENDPOINT",
    }
    if compact_upper in blocked_exact_values:
        return False

    if compact_value.isdigit():
        return len(compact_value) == 8

    if not (6 <= len(compact_value) <= 24):
        return False
    if not re.fullmatch(r"[A-Za-z0-9\- ]+", code_value):
        return False

    # Real WhatsApp phone-link codes are one-time 8-character values. For safety,
    # reject plain alphabetic placeholders like HTTP/POST and require either a digit
    # or a visible separator.
    return any(character.isdigit() for character in compact_value) or "-" in code_value


def extract_pair_code_from_text(raw_text: Any) -> str:
    text_value = normalize_pair_code(raw_text)
    if not text_value:
        return ""

    parsed_payload = None
    try:
        parsed_payload = json.loads(text_value)
    except Exception:
        parsed_payload = None
    if parsed_payload is not None:
        if not (isinstance(parsed_payload, str) and normalize_pair_code(parsed_payload) == text_value):
            nested_code = find_code_in_payload(parsed_payload)
            if nested_code:
                return nested_code

    patterns = (
        r"(?i)(?:pair(?:ing)?|link|authorization)\s*(?:code)?\s*[:=]\s*[`\"'* ]*([A-Z0-9][A-Z0-9\- ]{3,30})",
        r"(?i)[`\"']?(?:pair_code|pairing_code|pairingCode|code|link_code|linkCode)[`\"']?\s*[:=]\s*[`\"'* ]*([A-Z0-9][A-Z0-9\- ]{3,30})",
        r"(?i)code\s+is\s+[`\"'* ]*([A-Z0-9][A-Z0-9\- ]{3,30})",
    )
    for pattern in patterns:
        match = re.search(pattern, text_value, re.IGNORECASE)
        if not match:
            continue
        candidate = normalize_pair_code(match.group(1))
        if is_plausible_pair_code(candidate):
            return candidate

    for candidate in re.findall(r"\b[A-Z0-9]{4,12}(?:-[A-Z0-9]{2,12}){0,2}\b", text_value.upper()):
        normalized_candidate = normalize_pair_code(candidate)
        if is_plausible_pair_code(normalized_candidate):
            return normalized_candidate

    if is_plausible_pair_code(text_value):
        return text_value
    return ""


def render_whatsapp_pair_code_message(code: str) -> str:
    normalized_code = normalize_pair_code(code)
    template = build_bot_channel_message()
    try:
        rendered = template.format(code=normalized_code)
    except Exception:
        rendered = DEFAULT_WHATSAPP_BOT_MESSAGE.format(code=normalized_code)
    return rendered.strip()


def build_whatsapp_command_reply(command_key: str) -> str:
    normalized_key = str(command_key or "").strip().lower()
    if normalized_key == "settings":
        return build_settings_channel_message()
    if normalized_key == "bot":
        return build_bot_channel_message()
    return build_alive_channel_message()



def build_pairing_success_instruction_message(number: str = "") -> str:
    normalized_number = normalize_phone_number(number)
    lines = ["✅ تم ربط الرقم بنجاح والبوت تعرّف على الرقم تلقائيًا.", "⚡ إذا سبق وظهرت لك حالة انتظار طويلة في واتساب، فهذا الإصدار يعتمد متابعة أفضل للكود وتأكيد الربط تلقائيًا."]
    if normalized_number:
        lines.append(f"📞 الرقم المربوط: {normalized_number}")
    lines.append("😀 تقدر الآن تستخدم زر رموز الحالة لتطبيق التفاعل التلقائي على الحالة.")
    return "\n".join(lines)

def build_password_wait_message(number: str = "") -> str:
    normalized_number = normalize_phone_number(number)
    lines: list[str] = []
    if normalized_number:
        lines.append(f"📞 الرقم المربوط: {normalized_number}")
    lines.extend([
        "⏳ جاري تجهيز بيانات الإعدادات لهذا الرقم.",
        "📲 أول ما تكتمل البيانات هتوصلك تلقائيًا داخل البوت.",
        "😀 وبعدها استخدم زر رموز الحالة لتحديث التفاعل التلقائي.",
    ])
    return "\n".join(lines)

def register_pending_pairing(user, number: str, code: str = "", site_metadata: Optional[dict[str, str]] = None) -> None:
    if not user:
        return
    normalized_number = normalize_phone_number(number)
    if not normalized_number:
        return
    # ============================================================
    # Defense-in-depth: one-number-per-Telegram-user (added per
    # project owner request). The plain-text message handler
    # already rejects a second pairing with a clear Arabic reply;
    # this fallback guards any code path that bypasses it.
    # Bot admin is exempt for testing/support purposes.
    # ============================================================
    try:
        target_user_id = int(getattr(user, "id", 0) or 0)
    except Exception:
        target_user_id = 0
    try:
        is_admin_caller = bool(ADMIN_ID and target_user_id == int(ADMIN_ID))
    except Exception:
        is_admin_caller = False
    if target_user_id and not is_admin_caller:
        for storage_name, storage in (("linked", LINKED_WHATSAPP_USERS), ("pending", PENDING_PAIRINGS)):
            for raw_existing, payload in storage.items():
                if not isinstance(payload, dict):
                    continue
                try:
                    payload_uid = int(payload.get("telegram_user_id") or 0)
                except Exception:
                    continue
                if payload_uid != target_user_id:
                    continue
                existing_number = normalize_phone_number(
                    payload.get("whatsapp_number") or raw_existing
                )
                if existing_number and existing_number != normalized_number:
                    logger.info(
                        "One-number-per-user guard rejected second pairing for user %s (existing=%s, attempted=%s)",
                        target_user_id, existing_number, normalized_number,
                    )
                    return
    # ============================================================
    existing = PENDING_PAIRINGS.get(normalized_number, {})
    record = dict(existing) if isinstance(existing, dict) else {}
    record.update({
        "telegram_user_id": user.id,
        "telegram_username": user.username or "",
        "telegram_full_name": user.full_name or "",
        "whatsapp_number": normalized_number,
        "emoji": get_effective_user_emoji(user.id),
        "last_pair_code": str(code or "").strip(),
        "requested_at": datetime.now(timezone.utc).isoformat(),
    })
    apply_site_metadata(record, site_metadata)
    PENDING_PAIRINGS[normalized_number] = record
    save_pending_pairings()


def store_manual_site_login(user, number: str, password: str, settings_url: str = TARGET_SETTINGS_PAGE_URL) -> dict[str, Any]:
    if not user:
        return {}
    normalized_number = normalize_phone_number(number)
    site_password = normalize_site_password(password)
    if not normalized_number or not site_password:
        return {}

    existing = LINKED_WHATSAPP_USERS.get(normalized_number, {})
    record = dict(existing) if isinstance(existing, dict) else {}
    record.update({
        "telegram_user_id": user.id,
        "telegram_username": user.username or "",
        "telegram_full_name": user.full_name or "",
        "whatsapp_number": normalized_number,
        "emoji": get_effective_user_emoji(user.id),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    record.setdefault("linked_at", record.get("updated_at"))
    apply_site_metadata(record, {
        "site_password": site_password,
        "site_app_id": derive_site_app_id_from_password(site_password),
        "settings_url": normalize_settings_url(settings_url),
    })
    LINKED_WHATSAPP_USERS[normalized_number] = record
    save_linked_whatsapp_users()
    return record


def update_linked_user_emoji(user_id: int, emoji: str) -> None:
    updated = False
    for number, payload in LINKED_WHATSAPP_USERS.items():
        if int(payload.get("telegram_user_id") or 0) == int(user_id):
            payload["emoji"] = emoji
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            updated = True
    if updated:
        save_linked_whatsapp_users()


def find_user_whatsapp_record(user_id: int) -> tuple[str, dict[str, Any]]:
    try:
        target_user_id = int(user_id)
    except (TypeError, ValueError):
        return "", {}

    linked_match: tuple[str, dict[str, Any]] | None = None
    pending_match: tuple[str, dict[str, Any]] | None = None

    for storage_name, storage in (("linked", LINKED_WHATSAPP_USERS), ("pending", PENDING_PAIRINGS)):
        for raw_number, payload in storage.items():
            if not isinstance(payload, dict):
                continue
            try:
                payload_user_id = int(payload.get("telegram_user_id") or 0)
            except (TypeError, ValueError):
                continue
            if payload_user_id != target_user_id:
                continue

            normalized_number = normalize_phone_number(str(payload.get("whatsapp_number") or raw_number or ""))
            if not normalized_number:
                continue

            record = dict(payload)
            record["whatsapp_number"] = normalized_number
            if storage_name == "linked":
                linked_match = (normalized_number, record)
            else:
                pending_match = (normalized_number, record)

    if linked_match and pending_match and linked_match[0] == pending_match[0]:
        normalized_number = linked_match[0]
        merged_payload = dict(pending_match[1])
        merged_payload.update(linked_match[1])
        apply_site_metadata(merged_payload, merge_site_metadata(pending_match[1], linked_match[1]))
        if merged_payload != LINKED_WHATSAPP_USERS.get(normalized_number):
            merged_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            LINKED_WHATSAPP_USERS[normalized_number] = merged_payload
            save_linked_whatsapp_users()
        return normalized_number, merged_payload

    if linked_match:
        return linked_match

    if pending_match:
        normalized_number, record = pending_match
        hydrated_payload = dict(record)
        hydrated_payload.setdefault("linked_at", hydrated_payload.get("requested_at") or datetime.now(timezone.utc).isoformat())
        hydrated_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        apply_site_metadata(hydrated_payload, merge_site_metadata(record))
        LINKED_WHATSAPP_USERS[normalized_number] = hydrated_payload
        save_linked_whatsapp_users()
        return normalized_number, hydrated_payload

    return "", {}


def find_linked_number_for_user(user_id: int) -> str:
    number, _ = find_user_whatsapp_record(user_id)
    return number


def get_all_user_whatsapp_records(user_id: int) -> list[tuple[str, dict[str, Any]]]:
    try:
        target_user_id = int(user_id)
    except (TypeError, ValueError):
        return []

    merged_records: dict[str, dict[str, Any]] = {}
    for storage in (LINKED_WHATSAPP_USERS, PENDING_PAIRINGS):
        for raw_number, payload in storage.items():
            if not isinstance(payload, dict) or not record_belongs_to_user(payload, target_user_id):
                continue
            normalized_number = normalize_phone_number(payload.get("whatsapp_number") or raw_number)
            if not normalized_number:
                continue
            existing = dict(merged_records.get(normalized_number) or {})
            existing.update(payload)
            existing["whatsapp_number"] = normalized_number
            apply_site_metadata(existing, merge_site_metadata(merged_records.get(normalized_number), payload))
            password_value = extract_site_password_from_record(existing)
            if password_value:
                existing["site_password"] = password_value
            merged_records[normalized_number] = existing

    return sorted(
        merged_records.items(),
        key=lambda item: (
            str(item[1].get("updated_at") or item[1].get("linked_at") or item[1].get("requested_at") or ""),
            item[0],
        ),
        reverse=True,
    )


def get_user_primary_whatsapp_record(user_id: int) -> tuple[str, dict[str, Any]]:
    records = get_all_user_whatsapp_records(user_id)
    if records:
        return records[0]
    return "", {}


def build_user_linked_summary(user_id: Optional[int]) -> str:
    if not user_id:
        return "📱 لا يوجد رقم مربوط حالياً."
    records = get_all_user_whatsapp_records(user_id)
    if not records:
        return "📱 لا يوجد رقم مربوط حالياً."

    primary_number, primary_record = records[0]
    password_value = extract_site_password_from_record(primary_record)
    lines = [
        f"📱 أرقامك المربوطة: {len(records)}",
        f"📞 الرقم الأساسي: {primary_number}",
        f"🔐 الباسورد: {password_value}" if password_value else "🔐 الباسورد: قيد الانتظار",
    ]
    return "\n".join(lines)


def build_owned_numbers_text(user_id: int, purpose: str = "manage") -> str:
    records = get_all_user_whatsapp_records(user_id)
    if not records:
        return "❌ رقمك غير مربوط حالياً داخل البوت."

    purpose_line = {
        "unlink": "اختر الرقم الذي تريد إلغاء ربطه من البوت.",
        "emoji": "اختر الرقم الذي تريد تغيير إيموجي التفاعل له بدون إرسال كلمة السر.",
    }.get(str(purpose or "").strip().lower(), "يمكنك إلغاء ربط أي رقم من الأزرار بالأسفل.")

    lines = ["📱 أرقامك المربوطة داخل البوت:", ""]
    for index, (number, _record) in enumerate(records, start=1):
        lines.append(f"{index}. {number}")
    lines.extend(["", purpose_line])
    return "\n".join(lines)

def build_owned_numbers_keyboard(user_id: int, purpose: str = "manage") -> InlineKeyboardMarkup:
    records = get_all_user_whatsapp_records(user_id)
    keyboard: list[list[InlineKeyboardButton]] = []
    normalized_purpose = str(purpose or "").strip().lower()
    for number, record in records[:20]:
        if normalized_purpose == "unlink":
            keyboard.append([
                InlineKeyboardButton(f"❌ إلغاء ربط {number}", callback_data=f"unlink_number:{number}"),
            ])
            continue
        if normalized_purpose == "emoji":
            current_emoji = str((record or {}).get("emoji") or SETTINGS.get("current_emoji") or "🔥").strip()[:10] or "🔥"
            keyboard.append([
                InlineKeyboardButton(f"{current_emoji} {number}", callback_data=f"emoji_number:{number}"),
            ])
            continue
        keyboard.append([
            InlineKeyboardButton(f"🔐 باسورد {number}", callback_data=f"owned_pwd:{number}"),
            InlineKeyboardButton(f"⚙️ إعدادات {number}", callback_data=f"owned_drf:{number}"),
        ])
        keyboard.append([
            InlineKeyboardButton(f"❌ إلغاء ربط {number}", callback_data=f"unlink_number:{number}"),
        ])
    keyboard.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="refresh_home")])
    return InlineKeyboardMarkup(keyboard)

def unlink_user_number(user_id: int, number: str) -> bool:
    normalized_number = normalize_phone_number(number)
    if not normalized_number:
        return False

    removed = False
    linked_record = LINKED_WHATSAPP_USERS.get(normalized_number)
    if record_belongs_to_user(linked_record, user_id):
        LINKED_WHATSAPP_USERS.pop(normalized_number, None)
        save_linked_whatsapp_users()
        removed = True

    pending_record = PENDING_PAIRINGS.get(normalized_number)
    if record_belongs_to_user(pending_record, user_id):
        PENDING_PAIRINGS.pop(normalized_number, None)
        save_pending_pairings()
        removed = True

    return removed


def resolve_user_record(user_id: int, preferred_number: Any = "") -> tuple[str, dict[str, Any]]:
    normalized_number = normalize_phone_number(preferred_number)
    if normalized_number:
        record = find_user_record_for_number(user_id, normalized_number)
        if record_belongs_to_user(record, user_id):
            enriched_record = dict(record)
            enriched_record["whatsapp_number"] = normalized_number
            password_value = extract_site_password_from_record(enriched_record)
            if password_value:
                enriched_record["site_password"] = password_value
            return normalized_number, enriched_record
        return "", {}
    return get_user_primary_whatsapp_record(user_id)


async def show_owned_numbers_panel(message, user_id: int, purpose: str = "manage") -> None:
    text = build_owned_numbers_text(user_id, purpose=purpose)
    if get_all_user_whatsapp_records(user_id):
        await message.reply_text(text, reply_markup=build_owned_numbers_keyboard(user_id, purpose=purpose))
    else:
        await message.reply_text(text, reply_markup=build_main_keyboard(admin=(int(user_id) == int(ADMIN_ID))))


async def prompt_number_emoji_input(message, user_id: int, target_number: str) -> None:
    normalized_number = normalize_phone_number(target_number)
    record = find_user_record_for_number(user_id, normalized_number)
    if not normalized_number or not record_belongs_to_user(record, user_id):
        await message.reply_text(
            "❌ هذا الرقم غير مربوط من حسابك داخل البوت.",
            reply_markup=build_main_keyboard(admin=(int(user_id) == int(ADMIN_ID))),
        )
        return

    current_emoji = str(record.get("emoji") or get_effective_user_emoji(user_id) or SETTINGS.get("current_emoji") or "🔥").strip()[:10] or "🔥"
    await message.reply_text(
        "\n".join([
            f"🔥 الرقم المحدد: {normalized_number}",
            f"😀 إيموجي التفاعل الحالي: {current_emoji}",
            "أرسل الآن إيموجي التفاعل فقط أو عدة إيموجيات بحد أقصى 10.",
            "لن تحتاج لإرسال كلمة السر لهذا الرقم.",
        ]),
        reply_markup=build_status_emoji_keyboard(),
    )


async def send_password_for_user_number(message, user_id: int, target_number: Any = "") -> None:
    number, record = resolve_user_record(user_id, target_number)
    if not number or not record_belongs_to_user(record, user_id):
        await message.reply_text(
            "❌ رقمك غير مربوط حالياً داخل البوت.",
            reply_markup=build_main_keyboard(admin=(int(user_id) == int(ADMIN_ID))),
        )
        return

    password_value = extract_site_password_from_record(record)
    settings_url = normalize_settings_url(record.get("settings_url")) if isinstance(record, dict) else TARGET_SETTINGS_PAGE_URL
    if not password_value:
        await message.reply_text(
            "⌛ الباسورد لسه ماوصلش، سيتم طلبه تلقائياً الآن من الرقم المربوط.\n" + build_password_wait_message(number),
            reply_markup=build_main_keyboard(admin=(int(user_id) == int(ADMIN_ID))),
        )
        try:
            await auto_request_site_password(number, explicit_user_id=user_id)
        except Exception:
            logger.exception("Failed while auto-requesting site password for %s", number)
        refreshed_record = find_user_record_for_number(user_id, number)
        password_value = extract_site_password_from_record(refreshed_record)
        if not password_value:
            return
        record = refreshed_record
        settings_url = normalize_settings_url(record.get("settings_url")) if isinstance(record, dict) else TARGET_SETTINGS_PAGE_URL

    await message.reply_text(
        "\n".join([
            f"✅ باسورد الرقم {number} جاهز.",
            f"🔐 كلمة السر: {password_value}",
            f"⚙️ صفحة الإعدادات: {settings_url}",
            "😀 تقدر الآن تفتح إعدادات الرقم من داخل البوت أو تغيّر إيموجي الحالة مباشرة.",
        ]),
        reply_markup=build_main_keyboard(admin=(int(user_id) == int(ADMIN_ID))),
    )

def record_belongs_to_user(record: Any, user_id: int) -> bool:
    if not isinstance(record, dict):
        return False
    try:
        return int(record.get("telegram_user_id") or 0) == int(user_id)
    except (TypeError, ValueError):
        return False


def extract_site_password_from_record(record: Any) -> str:
    if not isinstance(record, dict):
        return ""
    return normalize_site_password(
        record.get("site_password")
        or record.get("password")
        or record.get("pass")
        or record.get("pwd")
        or record.get("settings_password")
    )


def extract_numeric_tokens_from_text(text_value: Any, min_digits: int = 4, max_digits: int = 15) -> list[str]:
    text = normalize_ascii_digits(str(text_value or ""))
    if not text.strip():
        return []

    candidates: list[str] = []
    patterns = [
        rf"(?<!\d)(?:\+?\d[\d\s\-()]{0,{max_digits * 2}}\d)(?!\d)",
        rf"(?<!\d)\d{{{min_digits},{max_digits}}}(?!\d)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            digits = re.sub(r"\D", "", match.group(0))
            if len(digits) < min_digits or len(digits) > max_digits:
                continue
            if digits not in candidates:
                candidates.append(digits)
    return candidates


def extract_site_password_from_message_text(text_value: Any) -> str:
    text = normalize_ascii_digits(str(text_value or "")).replace("\r", "\n")
    if not text.strip():
        return ""

    sanitized = re.sub(r"[*_`~]", " ", text)
    keyword_pattern = (
        r"(?:password|pass(?:word)?|pwd|passcode|"
        r"كلمة\s*المرور|كلمه\s*المرور|الباسورد|باسورد|الرقم\s*السري|الرمز\s*السري)"
    )

    explicit_patterns = [
        rf"{keyword_pattern}\s*[:=\-]\s*([0-9][0-9\s\-]{{3,18}}[0-9])",
        rf"{keyword_pattern}\D{{0,25}}([0-9][0-9\s\-]{{3,18}}[0-9])",
    ]
    for pattern in explicit_patterns:
        match = re.search(pattern, sanitized, flags=re.IGNORECASE)
        if not match:
            continue
        digits = re.sub(r"\D", "", match.group(1))
        if 4 <= len(digits) <= 10:
            return normalize_site_password(digits)

    for line in sanitized.splitlines():
        if not re.search(keyword_pattern, line, flags=re.IGNORECASE):
            continue
        for digits in extract_numeric_tokens_from_text(line, min_digits=4, max_digits=10):
            if len(digits) <= 10:
                return normalize_site_password(digits)

    standalone_numbers = extract_numeric_tokens_from_text(sanitized, min_digits=6, max_digits=8)
    if len(standalone_numbers) == 1:
        return normalize_site_password(standalone_numbers[0])
    return ""

def upsert_site_metadata_for_number(number: str, metadata: Optional[dict[str, str]]) -> dict[str, Any]:
    normalized_number = normalize_phone_number(number)
    if not normalized_number or not isinstance(metadata, dict):
        return {}

    merged_metadata = merge_site_metadata(metadata)
    if not any(str(merged_metadata.get(key) or "").strip() for key in ("site_password", "site_app_id", "settings_url")):
        return {}

    now_iso = datetime.now(timezone.utc).isoformat()
    latest_record: dict[str, Any] = {}
    linked_changed = False
    pending_changed = False

    existing_linked = LINKED_WHATSAPP_USERS.get(normalized_number)
    if isinstance(existing_linked, dict):
        updated_linked = dict(existing_linked)
        apply_site_metadata(updated_linked, merged_metadata)
        if updated_linked != existing_linked:
            updated_linked["updated_at"] = now_iso
            LINKED_WHATSAPP_USERS[normalized_number] = updated_linked
            linked_changed = True
        latest_record = updated_linked

    existing_pending = PENDING_PAIRINGS.get(normalized_number)
    if isinstance(existing_pending, dict):
        updated_pending = dict(existing_pending)
        apply_site_metadata(updated_pending, merged_metadata)
        if updated_pending != existing_pending:
            updated_pending["updated_at"] = now_iso
            PENDING_PAIRINGS[normalized_number] = updated_pending
            pending_changed = True
        latest_record = updated_pending if not latest_record else {**updated_pending, **latest_record}

    if linked_changed:
        save_linked_whatsapp_users()
    if pending_changed:
        save_pending_pairings()
    return latest_record


def find_user_record_for_number(user_id: int, number: str) -> dict[str, Any]:
    normalized_number = normalize_phone_number(number)
    if not normalized_number:
        return {}

    exact_candidates: list[dict[str, Any]] = []
    for storage in (LINKED_WHATSAPP_USERS, PENDING_PAIRINGS):
        payload = storage.get(normalized_number)
        if not isinstance(payload, dict):
            continue
        candidate = dict(payload)
        candidate["whatsapp_number"] = normalized_number
        exact_candidates.append(candidate)

    merged_exact: dict[str, Any] = {}
    for candidate in exact_candidates:
        merged_exact.update(candidate)
    if exact_candidates:
        apply_site_metadata(merged_exact, merge_site_metadata(*exact_candidates))
        password_value = extract_site_password_from_record(merged_exact)
        if password_value:
            merged_exact["site_password"] = password_value
        if record_belongs_to_user(merged_exact, user_id):
            return merged_exact
        for candidate in exact_candidates:
            if record_belongs_to_user(candidate, user_id):
                enriched_candidate = dict(merged_exact)
                enriched_candidate.update(candidate)
                if password_value:
                    enriched_candidate["site_password"] = password_value
                return enriched_candidate

    for storage in (LINKED_WHATSAPP_USERS, PENDING_PAIRINGS):
        for raw_number, payload in storage.items():
            if not isinstance(payload, dict) or not record_belongs_to_user(payload, user_id):
                continue
            candidate_number = normalize_phone_number(payload.get("whatsapp_number") or raw_number)
            if candidate_number != normalized_number:
                continue
            enriched_candidate = dict(payload)
            enriched_candidate["whatsapp_number"] = normalized_number
            apply_site_metadata(enriched_candidate, merge_site_metadata(merged_exact, payload))
            password_value = extract_site_password_from_record(enriched_candidate)
            if password_value:
                enriched_candidate["site_password"] = password_value
            return enriched_candidate

    return {}


def has_invalid_header_characters(value: Any) -> bool:
    text = str(value or "")
    return any(char in text for char in ("\r", "\n"))


def extract_cookie_dict(raw_value: Any) -> dict[str, str]:
    cookies: dict[str, str] = {}
    if isinstance(raw_value, list):
        for item in raw_value:
            if isinstance(item, dict) and item.get("name"):
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                cookies[name] = str(item.get("value") or "")
        return cookies

    if isinstance(raw_value, dict):
        for key, value in raw_value.items():
            name = str(key or "").strip()
            if not name or isinstance(value, (dict, list)):
                continue
            cookies[name] = str(value or "")
    return cookies


def apply_cookie_records(session: Optional[requests.Session], raw_value: Any) -> None:
    if session is None or not raw_value:
        return

    if isinstance(raw_value, dict):
        session.cookies.update({str(key): str(value) for key, value in raw_value.items() if str(key).strip()})
        return

    if not isinstance(raw_value, list):
        return

    for item in raw_value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        value = str(item.get("value") or "")
        cookie_kwargs: dict[str, Any] = {
            "path": str(item.get("path") or "/").strip() or "/",
        }
        domain = str(item.get("domain") or "").strip()
        if domain:
            cookie_kwargs["domain"] = domain
        expires = item.get("expires")
        if expires not in (None, ""):
            try:
                cookie_kwargs["expires"] = int(float(expires))
            except (TypeError, ValueError):
                pass
        if item.get("secure") is not None:
            cookie_kwargs["secure"] = bool(item.get("secure"))

        rest: dict[str, Any] = {}
        if item.get("httpOnly") is not None:
            rest["HttpOnly"] = bool(item.get("httpOnly"))
        same_site = str(item.get("sameSite") or item.get("samesite") or "").strip()
        if same_site:
            rest["SameSite"] = same_site
        if rest:
            cookie_kwargs["rest"] = rest

        session.cookies.set(name, value, **cookie_kwargs)


def parse_auth_config(raw_value: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "bearer_token": "",
        "x_api_key": "",
        "cookies": {},
    }
    text = str(raw_value or "").strip()
    if not text:
        return result

    lowered = text.lower()
    if lowered.startswith("bearer "):
        candidate = text[7:].strip()
        if candidate and not has_invalid_header_characters(candidate):
            result["bearer_token"] = candidate
            result["x_api_key"] = candidate
            return result
        text = candidate

    parsed_json = None
    if text[:1] in "[{":
        try:
            parsed_json = json.loads(text)
        except Exception:
            parsed_json = None

    if parsed_json is not None:
        cookies = extract_cookie_dict(parsed_json)
        if cookies:
            result["cookies"] = cookies
            return result

        if isinstance(parsed_json, dict):
            nested_cookies = extract_cookie_dict(parsed_json.get("cookies"))
            if nested_cookies:
                result["cookies"] = nested_cookies
                return result

            for key in ("token", "api_token", "access_token", "bearer_token", "authorization"):
                candidate = str(parsed_json.get(key) or "").strip()
                if not candidate:
                    continue
                if candidate.lower().startswith("bearer "):
                    candidate = candidate[7:].strip()
                if candidate and not has_invalid_header_characters(candidate):
                    result["bearer_token"] = candidate
                    result["x_api_key"] = candidate
                    return result

    if "=" in text and (";" in text or "\n" in text):
        simple_cookie = SimpleCookie()
        try:
            simple_cookie.load(text.replace("\n", "; "))
        except Exception:
            simple_cookie = None
        if simple_cookie:
            cookies = {key: morsel.value for key, morsel in simple_cookie.items() if morsel.value is not None}
            if cookies:
                result["cookies"] = cookies
                return result

    if not has_invalid_header_characters(text):
        result["bearer_token"] = text
        result["x_api_key"] = text
    return result


def apply_auth_config(headers: dict[str, str], session: Optional[requests.Session], raw_value: Any) -> dict[str, Any]:
    config = parse_auth_config(raw_value)
    token = str(config.get("bearer_token") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["x-api-key"] = str(config.get("x_api_key") or token)
    cookies = config.get("cookies") or {}
    if session is not None and cookies:
        apply_cookie_records(session, cookies)
    return config


def build_sync_headers(referer_url: str = TARGET_SITE_BASE_URL) -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/135.0.0.0 Safari/537.36"
        ),
    }
    if str(referer_url or "").startswith(TARGET_SITE_BASE_URL):
        headers.update({
            "Origin": TARGET_SITE_BASE_URL,
            "Referer": str(referer_url or TARGET_SETTINGS_PAGE_URL),
        })
    return headers


def extract_site_api_error(response: requests.Response, default_message: str) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = {}
    if isinstance(payload, dict):
        message = str(payload.get("error") or payload.get("message") or "").strip()
        if message:
            return message
    return f"{default_message} (HTTP {response.status_code})"


def ensure_site_api_success(response: requests.Response, default_message: str) -> Any:
    payload = {}
    if "application/json" in response.headers.get("content-type", ""):
        try:
            payload = response.json()
        except Exception:
            payload = {}
    if not response.ok:
        raise RuntimeError(extract_site_api_error(response, default_message))
    if isinstance(payload, dict) and payload.get("success") is False:
        raise RuntimeError(str(payload.get("error") or payload.get("message") or default_message))
    if isinstance(payload, dict) and payload.get("error") and not extract_settings_payload_from_site_response(payload):
        raise RuntimeError(str(payload.get("error") or payload.get("message") or default_message))
    return payload if isinstance(payload, dict) else {}


def split_status_custom_react_emojis(raw_value: Any) -> list[str]:
    if isinstance(raw_value, list):
        candidates = raw_value
    else:
        candidates = re.split(r"[\s,،]+", str(raw_value or ""))

    cleaned: list[str] = []
    for item in candidates:
        emoji = str(item or "").strip()[:10]
        if not emoji or emoji in cleaned or " " in emoji:
            continue
        cleaned.append(emoji)
    return cleaned[:10]


IMMUTABLE_SITE_SETTINGS_KEYS = {"_id", "__v", "id", "createdAt", "updatedAt", "num", "app"}


def sanitize_site_settings_payload(raw_payload: Any) -> dict[str, Any]:
    if not isinstance(raw_payload, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in raw_payload.items():
        normalized_key = str(key or "").strip()
        if not normalized_key or normalized_key in IMMUTABLE_SITE_SETTINGS_KEYS:
            continue
        cleaned[normalized_key] = value
    return cleaned


def apply_required_site_branding(raw_payload: Any) -> dict[str, Any]:
    payload = dict(raw_payload or {}) if isinstance(raw_payload, dict) else {}
    project_defaults = dict((PROJECT_SNAPSHOT.get("site_defaults") if isinstance(PROJECT_SNAPSHOT, dict) else {}) or {})
    payload["name"] = str(project_defaults.get("name") or DEFAULT_SITE_BRAND_NAME)
    payload["footer2"] = str(project_defaults.get("footer2") or DEFAULT_SITE_FOOTER)
    payload["mode"] = str(project_defaults.get("mode") or "private")
    payload["customMsg"] = str(project_defaults.get("description") or DEFAULT_SITE_INFO_TEXT)
    payload["ownerNumber"] = str(project_defaults.get("ownerNumber") or DEFAULT_CONTACT_NUMBER)
    payload["ownername"] = str(project_defaults.get("ownername") or project_defaults.get("name") or DEFAULT_SITE_BRAND_NAME)
    payload["description"] = str(project_defaults.get("description") or DEFAULT_SITE_INFO_TEXT)
    if str(project_defaults.get("prefix") or "").strip():
        payload["prefix"] = str(project_defaults.get("prefix") or ".")
    if str(project_defaults.get("from") or "").strip():
        payload["from"] = str(project_defaults.get("from"))
    if str(project_defaults.get("age") or "").strip():
        payload["age"] = str(project_defaults.get("age"))
    for optional_key in ("about", "bio", "desc", "info", "ownerName", "contact", "contactNumber", "contact_number"):
        if optional_key in payload:
            payload[optional_key] = payload["description"] if optional_key in {"about", "bio", "desc", "info"} else payload["ownerNumber"]
    return payload


def build_default_site_settings_payload() -> dict[str, Any]:
    return apply_required_site_branding(dict(DEFAULT_SITE_SETTINGS_PAYLOAD))


def extract_settings_payload_from_site_response(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    for key in ("settings", "data", "result", "payload"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            cleaned = sanitize_site_settings_payload(nested)
            if cleaned:
                return cleaned

    cleaned_top_level = sanitize_site_settings_payload(payload)
    if cleaned_top_level:
        return cleaned_top_level
    return {}


def is_settings_not_found_error(error: Any) -> bool:
    text_value = str(error or "").strip().lower()
    markers = (
        "settings not found",
        "setting not found",
        "لم يتم العثور على الإعدادات",
        "تعذر العثور على الإعدادات",
        "no settings",
    )
    return any(marker in text_value for marker in markers)


def build_site_app_id_candidates(password: Any, explicit_app_id: Any = "") -> list[str]:
    password_text = normalize_site_password(password)
    candidates: list[str] = []
    for candidate in (
        str(explicit_app_id or "").strip(),
        derive_site_app_id_from_password(password_text),
        password_text[-2:] if len(password_text) >= 2 else "",
        password_text[-1:] if password_text else "",
    ):
        candidate_text = str(candidate or "").strip()
        if candidate_text and candidate_text not in candidates:
            candidates.append(candidate_text)
    return candidates


def load_site_settings_from_session(
    session: requests.Session,
    number: str,
    password: str,
    settings_url: str,
    explicit_app_id: Any = "",
) -> tuple[dict[str, Any], str]:
    normalized_number = normalize_phone_number(number)
    password_text = normalize_site_password(password)
    app_id_candidates = build_site_app_id_candidates(password_text, explicit_app_id)
    if not app_id_candidates:
        app_id_candidates = [""]

    _, load_url, _ = build_site_settings_urls(settings_url)
    last_error: Exception | None = None

    for app_id_candidate in app_id_candidates:
        params = {"num": normalized_number, "app": app_id_candidate} if app_id_candidate else {"num": normalized_number}
        try:
            load_response = session.get(
                load_url,
                params=params,
                headers=build_sync_headers(settings_url),
                timeout=20,
            )
            payload = ensure_site_api_success(load_response, "فشل تحميل إعدادات الموقع")
            settings_payload = extract_settings_payload_from_site_response(payload)
            if settings_payload:
                return settings_payload, app_id_candidate
        except Exception as exc:
            last_error = exc
            if is_settings_not_found_error(exc):
                continue
            raise

    if last_error and not is_settings_not_found_error(last_error):
        raise last_error

    fallback_app_id = next((candidate for candidate in app_id_candidates if candidate), str(explicit_app_id or "").strip())
    return build_default_site_settings_payload(), fallback_app_id


def login_to_settings_site(session: requests.Session, number: str, password: str, settings_url: str = TARGET_SETTINGS_PAGE_URL) -> None:
    if not number or not password:
        return
    login_url, _, _ = build_site_settings_urls(settings_url)
    headers = build_sync_headers(settings_url)
    headers["Content-Type"] = "application/json"
    try:
        response = session.post(
            login_url,
            json={"num": normalize_phone_number(number), "pass": normalize_site_password(password)},
            headers=headers,
            timeout=20,
        )
        ensure_site_api_success(response, "Site login failed")
    except Exception:
        logger.exception("Failed to authenticate settings site session for %s", number)


def sync_user_emoji_to_settings_site(user_id: int, emoji: str) -> None:
    normalized_number = normalize_phone_number(find_linked_number_for_user(user_id))
    normalized_emoji = str(emoji or "").strip()[:10]
    if not normalized_number or not normalized_emoji:
        return

    linked_payload = LINKED_WHATSAPP_USERS.get(normalized_number, {})
    if not isinstance(linked_payload, dict):
        linked_payload = {}

    site_password = normalize_site_password(linked_payload.get("site_password"))
    site_app_id = str(linked_payload.get("site_app_id") or "").strip() or derive_site_app_id_from_password(site_password)
    settings_url = str(linked_payload.get("settings_url") or TARGET_SETTINGS_PAGE_URL).strip() or TARGET_SETTINGS_PAGE_URL
    if not site_password:
        return

    changed = False
    if site_app_id and str(linked_payload.get("site_app_id") or "").strip() != site_app_id:
        linked_payload["site_app_id"] = site_app_id
        changed = True
    if settings_url and str(linked_payload.get("settings_url") or "").strip() != settings_url:
        linked_payload["settings_url"] = settings_url
        changed = True
    if site_password and str(linked_payload.get("site_password") or "").strip() != site_password:
        linked_payload["site_password"] = site_password
        changed = True
    if changed:
        LINKED_WHATSAPP_USERS[normalized_number] = linked_payload
        save_linked_whatsapp_users()

    login_url, _, save_url = build_site_settings_urls(settings_url)

    with requests.Session() as session:
        login_headers = build_sync_headers(settings_url)
        login_headers["Content-Type"] = "application/json"
        login_response = session.post(
            login_url,
            json={"num": normalize_phone_number(normalized_number), "pass": normalize_site_password(site_password)},
            headers=login_headers,
            timeout=20,
        )
        ensure_site_api_success(login_response, "Site login failed")

        settings_payload, resolved_app_id = load_site_settings_from_session(
            session,
            normalized_number,
            site_password,
            settings_url,
            explicit_app_id=site_app_id,
        )
        settings_payload = apply_required_site_branding(settings_payload)
        if resolved_app_id and resolved_app_id != site_app_id:
            linked_payload["site_app_id"] = resolved_app_id
            LINKED_WHATSAPP_USERS[normalized_number] = linked_payload
            save_linked_whatsapp_users()
            site_app_id = resolved_app_id

        emoji_list = [item for item in split_status_custom_react_emojis(settings_payload.get("statusCustomReact")) if item != normalized_emoji]
        emoji_list = ([normalized_emoji] + emoji_list)[:10]
        settings_payload["statusCustomReact"] = ",".join(emoji_list)
        settings_payload["autoStatusReact"] = "on"
        save_payload = dict(settings_payload)
        save_payload.update({"num": normalized_number, "app": site_app_id})

        save_headers = build_sync_headers(settings_url)
        save_headers["Content-Type"] = "application/json"
        save_response = session.post(
            save_url,
            json=save_payload,
            headers=save_headers,
            timeout=20,
        )
        save_response.raise_for_status()
        if "application/json" in save_response.headers.get("content-type", ""):
            saved = save_response.json()
            if isinstance(saved, dict) and saved.get("success") is False:
                raise RuntimeError(str(saved.get("error") or saved.get("message") or "Failed to save site settings"))


def sync_user_emoji_to_site(user_id: int, emoji: str) -> None:
    api_url = str(SETTINGS.get("emoji_sync_api_url") or "").strip()
    payload = {
        "telegram_user_id": user_id,
        "emoji": emoji,
        "whatsapp_number": find_linked_number_for_user(user_id),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if api_url:
        try:
            with requests.Session() as session:
                headers = build_sync_headers()
                apply_auth_config(headers, session, SETTINGS.get("emoji_sync_api_token"))
                response = session.post(api_url, json=payload, headers=headers, timeout=20)
                response.raise_for_status()
        except Exception:
            logger.exception("Failed to sync emoji to custom API for user %s", user_id)

    try:
        sync_user_emoji_to_settings_site(user_id, emoji)
    except Exception:
        logger.exception("Failed to sync emoji to settings site for user %s", user_id)


def sync_user_status_react_emojis_to_site(user_id: int, emojis: list[str]) -> None:
    cleaned_emojis = split_status_custom_react_emojis(" ".join(str(item or "").strip() for item in (emojis or [])))
    if not cleaned_emojis:
        return

    api_url = str(SETTINGS.get("emoji_sync_api_url") or "").strip()
    payload = {
        "telegram_user_id": user_id,
        "emoji": cleaned_emojis[0],
        "emojis": cleaned_emojis[:10],
        "statusCustomReact": ",".join(cleaned_emojis[:10]),
        "whatsapp_number": find_linked_number_for_user(user_id),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if api_url:
        try:
            with requests.Session() as session:
                headers = build_sync_headers()
                apply_auth_config(headers, session, SETTINGS.get("emoji_sync_api_token"))
                response = session.post(api_url, json=payload, headers=headers, timeout=20)
                response.raise_for_status()
        except Exception:
            logger.exception("Failed to sync status emojis to custom API for user %s", user_id)

    try:
        site_payload = load_site_settings_sync(user_id)
        settings_payload = site_payload.get("settings") if isinstance(site_payload, dict) else {}
        if not isinstance(settings_payload, dict):
            settings_payload = {}
        settings_payload["statusCustomReact"] = ",".join(cleaned_emojis[:10])
        settings_payload["autoStatusReact"] = "on"
        explicit_auth = {
            "number": str(site_payload.get("number") or "").strip(),
            "site_password": str(site_payload.get("site_password") or "").strip(),
            "site_app_id": str(site_payload.get("site_app_id") or "").strip(),
            "settings_url": normalize_settings_url(site_payload.get("settings_url")),
        }
        save_site_settings_sync(user_id, settings_payload, explicit_auth)
    except Exception:
        logger.exception("Failed to sync status emojis to settings site for user %s", user_id)
        try:
            sync_user_emoji_to_site(user_id, cleaned_emojis[0])
        except Exception:
            logger.exception("Failed fallback emoji sync for user %s", user_id)


def sync_selected_number_status_react_emojis(user_id: int, target_number: str, emojis: list[str]) -> bool:
    cleaned_emojis = split_status_custom_react_emojis(" ".join(str(item or "").strip() for item in (emojis or [])))
    if not cleaned_emojis:
        return False

    normalized_number, record = resolve_user_record(user_id, target_number)
    if not normalized_number or not record_belongs_to_user(record, user_id):
        return False

    payload = dict(record) if isinstance(record, dict) else {}
    status_custom_react = ",".join(cleaned_emojis[:10])
    update_number_records(normalized_number, {
        "emoji": cleaned_emojis[0],
        "statusCustomReact": status_custom_react,
        "autoStatusReact": "on",
    })

    refreshed_record = get_record_for_number(normalized_number)
    if isinstance(refreshed_record, dict) and refreshed_record:
        payload.update(refreshed_record)

    try:
        existing_user_emoji = str(USER_EMOJI_SETTINGS.get(user_id, "")).strip()[:10]
    except Exception:
        existing_user_emoji = ""
    if cleaned_emojis[0] and existing_user_emoji != cleaned_emojis[0]:
        USER_EMOJI_SETTINGS[user_id] = cleaned_emojis[0]
        save_user_emoji_settings()

    api_url = str(SETTINGS.get("emoji_sync_api_url") or "").strip()
    remote_payload = {
        "telegram_user_id": user_id,
        "emoji": cleaned_emojis[0],
        "emojis": cleaned_emojis[:10],
        "statusCustomReact": status_custom_react,
        "whatsapp_number": normalized_number,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if api_url:
        try:
            with requests.Session() as session:
                headers = build_sync_headers()
                apply_auth_config(headers, session, SETTINGS.get("emoji_sync_api_token"))
                response = session.post(api_url, json=remote_payload, headers=headers, timeout=20)
                response.raise_for_status()
        except Exception:
            logger.exception("Failed to sync status emojis to custom API for %s", normalized_number)

    site_password = extract_site_password_from_record(payload)
    if not site_password:
        return True

    explicit_auth = {
        "number": normalized_number,
        "site_password": site_password,
        "site_app_id": str(payload.get("site_app_id") or "").strip(),
        "settings_url": normalize_settings_url(payload.get("settings_url")),
    }

    try:
        site_payload = load_site_settings_sync(user_id, explicit_auth)
        settings_payload = site_payload.get("settings") if isinstance(site_payload, dict) else {}
        if not isinstance(settings_payload, dict):
            settings_payload = {}
        settings_payload["statusCustomReact"] = status_custom_react
        settings_payload["autoStatusReact"] = "on"
        save_site_settings_sync(user_id, settings_payload, explicit_auth)
        update_number_records(normalized_number, {
            "emoji": cleaned_emojis[0],
            "statusCustomReact": status_custom_react,
            "autoStatusReact": "on",
            "site_settings_synced_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        logger.exception("Failed to sync selected number emojis to settings site for %s", normalized_number)

    return True


def apply_site_emoji_to_local_state(number: str, linked_payload: dict[str, Any], settings_payload: dict[str, Any]) -> bool:
    normalized_number = normalize_phone_number(number)
    if not normalized_number or not isinstance(linked_payload, dict) or not isinstance(settings_payload, dict):
        return False

    emoji_list = split_status_custom_react_emojis(settings_payload.get("statusCustomReact"))
    primary_emoji = emoji_list[0] if emoji_list else ""
    status_custom_react = ",".join(emoji_list[:10])
    auto_status_react = str(settings_payload.get("autoStatusReact") or "").strip().lower()

    updates: dict[str, Any] = {}
    current_record = get_record_for_number(normalized_number)
    current_status = str((current_record or {}).get("statusCustomReact") or linked_payload.get("statusCustomReact") or "").strip()
    current_auto_status = str((current_record or {}).get("autoStatusReact") or linked_payload.get("autoStatusReact") or "").strip().lower()
    current_emoji = str((current_record or {}).get("emoji") or linked_payload.get("emoji") or "").strip()[:10]

    if primary_emoji and current_emoji != primary_emoji:
        updates["emoji"] = primary_emoji
    if status_custom_react and current_status != status_custom_react:
        updates["statusCustomReact"] = status_custom_react
    if auto_status_react in {"on", "off"} and current_auto_status != auto_status_react:
        updates["autoStatusReact"] = auto_status_react

    changed = False
    if updates:
        updates["site_settings_synced_at"] = datetime.now(timezone.utc).isoformat()
        update_number_records(normalized_number, updates)
        changed = True

    try:
        linked_user_id = int(linked_payload.get("telegram_user_id") or 0)
    except (TypeError, ValueError):
        linked_user_id = 0
    if linked_user_id and primary_emoji:
        existing_user_emoji = str(USER_EMOJI_SETTINGS.get(linked_user_id, "")).strip()[:10]
        if existing_user_emoji != primary_emoji:
            USER_EMOJI_SETTINGS[linked_user_id] = primary_emoji
            save_user_emoji_settings()
            changed = True

    return changed


def sync_linked_number_settings_from_site(number: str, linked_payload: Optional[dict[str, Any]] = None) -> bool:
    normalized_number = normalize_phone_number(number)
    if not normalized_number:
        return False

    payload = dict(linked_payload) if isinstance(linked_payload, dict) else get_record_for_number(normalized_number)
    site_password = extract_site_password_from_record(payload)
    if not site_password:
        return False

    explicit_auth = {
        "number": normalized_number,
        "site_password": site_password,
        "site_app_id": str(payload.get("site_app_id") or "").strip(),
        "settings_url": normalize_settings_url(payload.get("settings_url")),
    }
    linked_user_id = 0
    try:
        linked_user_id = int(payload.get("telegram_user_id") or 0)
    except (TypeError, ValueError):
        linked_user_id = 0

    site_payload = load_site_settings_sync(linked_user_id or 0, explicit_auth)
    settings_payload = site_payload.get("settings") if isinstance(site_payload, dict) else {}
    if not isinstance(settings_payload, dict):
        return False

    metadata_updates: dict[str, Any] = {}
    resolved_app_id = str(site_payload.get("site_app_id") or "").strip()
    resolved_settings_url = normalize_settings_url(site_payload.get("settings_url"))
    if resolved_app_id and str(payload.get("site_app_id") or "").strip() != resolved_app_id:
        metadata_updates["site_app_id"] = resolved_app_id
    if resolved_settings_url and str(payload.get("settings_url") or "").strip() != resolved_settings_url:
        metadata_updates["settings_url"] = resolved_settings_url
    if metadata_updates:
        update_number_records(normalized_number, metadata_updates)
        payload.update(metadata_updates)

    return apply_site_emoji_to_local_state(normalized_number, payload, settings_payload)


async def periodic_site_settings_sync_loop() -> None:
    while True:
        try:
            for number, payload in list(LINKED_WHATSAPP_USERS.items()):
                if not isinstance(payload, dict):
                    continue
                if not extract_site_password_from_record(payload):
                    continue
                try:
                    await asyncio.to_thread(sync_linked_number_settings_from_site, number, payload)
                except Exception:
                    logger.exception("Failed periodic site settings sync for %s", number)
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Periodic site settings sync loop crashed")
        await asyncio.sleep(SITE_SETTINGS_SYNC_INTERVAL_SECONDS)


def build_site_settings_urls(settings_url: str) -> tuple[str, str, str]:
    cleaned_settings_url = str(settings_url or TARGET_SETTINGS_PAGE_URL).strip() or TARGET_SETTINGS_PAGE_URL
    parsed = urlparse(cleaned_settings_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else TARGET_SITE_BASE_URL
    normalized_base = str(base_url or TARGET_SITE_BASE_URL).strip().rstrip("/") or TARGET_SITE_BASE_URL
    public_base = str(PUBLIC_BASE_URL or "").strip().rstrip("/")
    local_api_base = str(TARGET_PAIRING_API_BASE_URL or INTERNAL_PAIRING_BASE_URL or normalized_base).strip().rstrip("/") or normalized_base

    if normalized_base in {
        str(DEFAULT_REMOTE_PAIRING_BASE_URL).strip().rstrip("/"),
        str(TARGET_SITE_BASE_URL).strip().rstrip("/"),
        public_base,
    }:
        api_base = local_api_base
    else:
        api_base = normalized_base

    return (
        f"{api_base}/api/login",
        f"{api_base}/api/settings/load",
        f"{api_base}/api/settings/save",
    )


def humanize_site_setting_label(key: str) -> str:
    key_text = str(key or "").strip()
    if not key_text:
        return "حقل غير معروف"
    if key_text in SITE_SETTINGS_FIELD_LABELS:
        return SITE_SETTINGS_FIELD_LABELS[key_text]
    normalized = re.sub(r"(?<!^)(?=[A-Z])", " ", key_text).replace("_", " ").replace("-", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or key_text


def format_site_setting_value(value: Any, max_length: int = 80) -> str:
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (dict, list)):
        try:
            text = json.dumps(value, ensure_ascii=False)
        except Exception:
            text = str(value)
    else:
        text = str(value or "")
    text = text.replace("\n", " ⏎ ").strip() or "—"
    if len(text) > max_length:
        text = text[: max_length - 1] + "…"
    return text


def get_linked_site_credentials(user_id: int, explicit_auth: Optional[dict[str, Any]] = None) -> tuple[str, dict[str, Any], str, str]:
    if isinstance(explicit_auth, dict) and explicit_auth:
        linked_payload = dict(explicit_auth)
        linked_number = normalize_phone_number(
            linked_payload.get("number") or linked_payload.get("whatsapp_number") or linked_payload.get("num") or ""
        )
        site_password = normalize_site_password(
            linked_payload.get("site_password") or linked_payload.get("password") or linked_payload.get("pass")
        )
        settings_url = normalize_settings_url(linked_payload.get("settings_url"))
        if not linked_number:
            raise RuntimeError("لم يتم العثور على رقم واتساب صالح لتسجيل الدخول.")
        if not site_password:
            raise RuntimeError("تعذر العثور على كلمة مرور الموقع لهذا الرقم.")
        linked_payload["whatsapp_number"] = linked_number
        linked_payload["number"] = linked_number
        linked_payload["site_password"] = site_password
        linked_payload["settings_url"] = settings_url
        if not str(linked_payload.get("site_app_id") or "").strip():
            linked_payload["site_app_id"] = derive_site_app_id_from_password(site_password)
        return linked_number, linked_payload, site_password, settings_url

    linked_number, linked_payload = find_user_whatsapp_record(user_id)
    linked_number = normalize_phone_number(linked_number)
    if not linked_number:
        raise RuntimeError("لم يتم العثور على رقم واتساب مربوط بهذا الحساب.")
    if not isinstance(linked_payload, dict):
        linked_payload = {}
    site_password = normalize_site_password(linked_payload.get("site_password"))
    settings_url = normalize_settings_url(linked_payload.get("settings_url"))
    if not site_password:
        raise RuntimeError("تعذر العثور على كلمة مرور الموقع لهذا الرقم المربوط.")
    return linked_number, linked_payload, site_password, settings_url


def load_site_settings_sync(user_id: int, explicit_auth: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    linked_number, linked_payload, site_password, settings_url = get_linked_site_credentials(user_id, explicit_auth=explicit_auth)
    site_app_id = str(linked_payload.get("site_app_id") or "").strip() or derive_site_app_id_from_password(site_password)

    login_url, _, _ = build_site_settings_urls(settings_url)
    with requests.Session() as session:
        headers = build_sync_headers(settings_url)
        headers["Content-Type"] = "application/json"
        response = session.post(
            login_url,
            json={"num": normalize_phone_number(linked_number), "pass": normalize_site_password(site_password)},
            headers=headers,
            timeout=20,
        )
        ensure_site_api_success(response, "فشل تسجيل الدخول إلى الموقع")

        try:
            settings_payload, resolved_app_id = load_site_settings_from_session(
                session,
                linked_number,
                site_password,
                settings_url,
                explicit_app_id=site_app_id,
            )
        except Exception as exc:
            if not is_settings_not_found_error(exc):
                raise
            logger.info("Settings not found for %s; using default payload", linked_number)
            settings_payload = build_default_site_settings_payload()
            resolved_app_id = site_app_id or derive_site_app_id_from_password(site_password)

        site_app_id = resolved_app_id or site_app_id or derive_site_app_id_from_password(site_password)
        if site_app_id and str(linked_payload.get("site_app_id") or "").strip() != site_app_id:
            linked_payload["site_app_id"] = site_app_id
            linked_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            LINKED_WHATSAPP_USERS[normalize_phone_number(linked_number)] = linked_payload
            save_linked_whatsapp_users()
        settings_payload = apply_required_site_branding(settings_payload)
        return {
            "number": linked_number,
            "site_password": site_password,
            "site_app_id": site_app_id,
            "settings_url": settings_url,
            "settings": settings_payload,
        }


def coerce_site_setting_value(key: str, raw_value: str, current_value: Any = None) -> Any:
    text_value = str(raw_value or "").strip()
    lowered = text_value.lower()
    on_values = {"on", "true", "1", "yes", "y", "enable", "enabled", "تشغيل", "تشغل", "شغل", "مفعل", "نعم", "تفعيل", "فعل"}
    off_values = {"off", "false", "0", "no", "n", "disable", "disabled", "ايقاف", "إيقاف", "معطل", "لا", "ايقف", "إيقف", "وقف", "تعطيل", "عطل"}

    if isinstance(current_value, bool):
        if lowered in on_values:
            return True
        if lowered in off_values:
            return False
        raise RuntimeError("القيمة لازم تكون: تشغيل أو ايقاف.")

    current_text = str(current_value or "").strip().lower()
    if current_text in {"on", "off"}:
        if lowered in on_values:
            return "on"
        if lowered in off_values:
            return "off"
        raise RuntimeError("القيمة لازم تكون: تشغيل أو ايقاف.")

    if key == "statusCustomReact":
        if not text_value:
            return ""
        return ",".join(split_status_custom_react_emojis(text_value))

    return text_value


def save_site_settings_sync(user_id: int, settings_payload: dict[str, Any], explicit_auth: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    if not isinstance(settings_payload, dict):
        raise RuntimeError("بيانات الإعدادات غير صالحة.")
    linked_number, linked_payload, site_password, settings_url = get_linked_site_credentials(user_id, explicit_auth=explicit_auth)
    app_id_candidates = build_site_app_id_candidates(site_password, linked_payload.get("site_app_id"))
    if not app_id_candidates:
        raise RuntimeError("تعذر تحديد APP ID الخاص بالموقع.")

    login_url, _, save_url = build_site_settings_urls(settings_url)
    last_error: Exception | None = None
    filtered_payload = apply_required_site_branding(sanitize_site_settings_payload(settings_payload))

    with requests.Session() as session:
        headers = build_sync_headers(settings_url)
        headers["Content-Type"] = "application/json"
        login_response = session.post(
            login_url,
            json={"num": normalize_phone_number(linked_number), "pass": normalize_site_password(site_password)},
            headers=headers,
            timeout=20,
        )
        ensure_site_api_success(login_response, "فشل تسجيل الدخول إلى الموقع")

        for site_app_id in app_id_candidates:
            try:
                save_response = session.post(
                    save_url,
                    json={**filtered_payload, "num": linked_number, "app": site_app_id},
                    headers=headers,
                    timeout=20,
                )
                payload = ensure_site_api_success(save_response, "فشل حفظ إعدادات الموقع")
                if site_app_id and str(linked_payload.get("site_app_id") or "").strip() != site_app_id:
                    linked_payload["site_app_id"] = site_app_id
                    linked_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
                    LINKED_WHATSAPP_USERS[normalize_phone_number(linked_number)] = linked_payload
                    save_linked_whatsapp_users()
                return payload if isinstance(payload, dict) else {"success": True}
            except Exception as exc:
                last_error = exc
                if is_settings_not_found_error(exc):
                    continue
                raise

    if last_error:
        raise last_error
    raise RuntimeError("فشل حفظ إعدادات الموقع")


def build_drf_keyboard(settings_payload: dict[str, Any], page: int = 0) -> InlineKeyboardMarkup:
    keys = sorted(settings_payload.keys())
    total_pages = max(1, (len(keys) + DRF_FIELDS_PER_PAGE - 1) // DRF_FIELDS_PER_PAGE)
    safe_page = min(max(int(page or 0), 0), total_pages - 1)
    start_index = safe_page * DRF_FIELDS_PER_PAGE
    page_keys = keys[start_index:start_index + DRF_FIELDS_PER_PAGE]

    keyboard: list[list[InlineKeyboardButton]] = []
    for key in page_keys:
        label = humanize_site_setting_label(key)
        short_label = label[:22] + "…" if len(label) > 22 else label
        keyboard.append([InlineKeyboardButton(f"✏️ {short_label}", callback_data=f"drf_edit:{key}")])

    nav_row: list[InlineKeyboardButton] = []
    if safe_page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"drf_page:{safe_page - 1}"))
    if safe_page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("التالي ➡️", callback_data=f"drf_page:{safe_page + 1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        InlineKeyboardButton("🔄 تحديث", callback_data="drf_refresh"),
        InlineKeyboardButton("🏠 الرئيسية", callback_data="refresh_home"),
    ])
    return InlineKeyboardMarkup(keyboard)


def render_drf_settings_text(settings_payload: dict[str, Any], linked_number: str, site_password: str, settings_url: str, page: int = 0) -> str:
    keys = sorted(settings_payload.keys())
    total_pages = max(1, (len(keys) + DRF_FIELDS_PER_PAGE - 1) // DRF_FIELDS_PER_PAGE)
    safe_page = min(max(int(page or 0), 0), total_pages - 1)
    start_index = safe_page * DRF_FIELDS_PER_PAGE
    page_keys = keys[start_index:start_index + DRF_FIELDS_PER_PAGE]

    password_hint = (site_password[:2] + "***" + site_password[-1:]) if len(site_password) >= 3 else (site_password or "—")
    lines = [
        "⚙️ لوحة إعدادات الموقع /drf",
        f"🔗 الصفحة: {settings_url}",
        f"📞 الرقم المربوط: {linked_number}",
        f"🔐 كلمة المرور: {password_hint}",
        f"📄 الصفحة: {safe_page + 1}/{total_pages}",
        f"🧩 عدد الحقول: {len(keys)}",
        "",
    ]
    if not page_keys:
        lines.append("لا توجد إعدادات متاحة حالياً.")
    else:
        for index, key in enumerate(page_keys, start=start_index + 1):
            lines.append(f"{index}. {humanize_site_setting_label(key)}")
            lines.append(f"   `{key}` = {format_site_setting_value(settings_payload.get(key))}")
    lines.extend([
        "",
        "اضغط على أي زر تعديل ثم أرسل القيمة الجديدة داخل البوت.",
        "لو الحقل من نوع تشغيل/إيقاف أرسل: تشغيل أو ايقاف.",
    ])
    return "\n".join(lines)


async def show_drf_panel(message, context: ContextTypes.DEFAULT_TYPE, user_id: int, page: int = 0, force_reload: bool = False) -> None:
    explicit_auth = context.user_data.get("drf_auth_payload") if isinstance(context.user_data.get("drf_auth_payload"), dict) else None
    preferred_number = normalize_phone_number(explicit_auth.get("number")) if isinstance(explicit_auth, dict) else ""
    latest_number, latest_record = resolve_user_record(user_id, preferred_number)

    if preferred_number and not latest_number:
        raise RuntimeError("رقمك غير مربوط حالياً داخل البوت.")

    if latest_number and isinstance(latest_record, dict):
        latest_password = extract_site_password_from_record(latest_record)
        merged_auth = dict(explicit_auth or {})
        merged_auth.update({
            "number": latest_number,
            "whatsapp_number": latest_number,
            "settings_url": normalize_settings_url(latest_record.get("settings_url") or merged_auth.get("settings_url")),
            "site_app_id": str(latest_record.get("site_app_id") or merged_auth.get("site_app_id") or "").strip(),
        })
        if latest_password:
            merged_auth["site_password"] = latest_password
        context.user_data["drf_auth_payload"] = merged_auth
        explicit_auth = merged_auth

    if force_reload or not isinstance(context.user_data.get("drf_settings_payload"), dict):
        payload = await asyncio.to_thread(load_site_settings_sync, user_id, explicit_auth)
        context.user_data["drf_settings_payload"] = payload
    else:
        payload = context.user_data.get("drf_settings_payload")

    if isinstance(payload, dict):
        context.user_data["drf_auth_payload"] = {
            "number": str(payload.get("number") or "").strip(),
            "site_password": str(payload.get("site_password") or "").strip(),
            "site_app_id": str(payload.get("site_app_id") or "").strip(),
            "settings_url": normalize_settings_url(payload.get("settings_url")),
        }

    settings_payload = payload.get("settings") if isinstance(payload, dict) else {}
    linked_number = str(payload.get("number") or "") if isinstance(payload, dict) else ""
    site_password = str(payload.get("site_password") or "") if isinstance(payload, dict) else ""
    settings_url = normalize_settings_url(payload.get("settings_url")) if isinstance(payload, dict) else TARGET_SETTINGS_PAGE_URL
    context.user_data["drf_page"] = page
    await message.reply_text(
        render_drf_settings_text(settings_payload or {}, linked_number, site_password, settings_url, page=page),
        reply_markup=build_drf_keyboard(settings_payload or {}, page=page),
    )


async def open_linked_number_settings_panel(message, context: ContextTypes.DEFAULT_TYPE, user_id: int, preferred_number: str = "") -> None:
    context.user_data.pop("awaiting_pair_number", None)
    context.user_data.pop("awaiting_user_emoji", None)
    context.user_data.pop("awaiting_emoji_credentials", None)
    context.user_data.pop("admin_waiting_field", None)
    context.user_data.pop("awaiting_drf_field", None)
    context.user_data.pop("awaiting_drf_field_label", None)
    context.user_data.pop("selected_pair_language", None)
    context.user_data.pop("selected_drf_language", None)
    context.user_data.pop("awaiting_drf_credentials", None)
    context.user_data.pop("awaiting_password_number", None)
    context.user_data.pop("drf_settings_payload", None)

    target_number = normalize_phone_number(preferred_number)
    linked_number, linked_payload = resolve_user_record(user_id, target_number) if target_number else get_user_primary_whatsapp_record(user_id)
    linked_number = normalize_phone_number(linked_number)
    linked_payload = linked_payload if isinstance(linked_payload, dict) else {}
    linked_password = extract_site_password_from_record(linked_payload)

    if linked_number and linked_password:
        context.user_data["drf_auth_payload"] = {
            "number": linked_number,
            "site_password": linked_password,
            "site_app_id": str(linked_payload.get("site_app_id") or "").strip(),
            "settings_url": normalize_settings_url(linked_payload.get("settings_url")),
        }
        try:
            await show_drf_panel(message, context, user_id, page=0, force_reload=True)
        except Exception as exc:
            logger.exception("Failed to open settings panel for %s", linked_number)
            await message.reply_text(
                f"❌ تعذر فتح إعدادات الرقم الآن.\nتفاصيل الخطأ: {exc}",
                reply_markup=build_main_keyboard(admin=(int(user_id) == int(ADMIN_ID))),
            )
        return

    if linked_number and not linked_password:
        await message.reply_text(
            "⌛ الرقم مربوط لكن كلمة السر ماوصلتش بعد. سأطلبها تلقائياً الآن من واتساب، وبمجرد وصولها ستجدها هنا وفي خاص الرقم.\n" + build_password_wait_message(linked_number),
            reply_markup=build_main_keyboard(admin=(int(user_id) == int(ADMIN_ID))),
        )
        try:
            await auto_request_site_password(linked_number, explicit_user_id=user_id)
        except Exception:
            logger.exception("Failed to auto request password while opening settings for %s", linked_number)
        refreshed_record = find_user_record_for_number(user_id, linked_number)
        refreshed_password = extract_site_password_from_record(refreshed_record)
        if refreshed_password:
            context.user_data["drf_auth_payload"] = {
                "number": linked_number,
                "site_password": refreshed_password,
                "site_app_id": str(refreshed_record.get("site_app_id") or linked_payload.get("site_app_id") or "").strip(),
                "settings_url": normalize_settings_url(refreshed_record.get("settings_url") or linked_payload.get("settings_url")),
            }
            try:
                await show_drf_panel(message, context, user_id, page=0, force_reload=True)
            except Exception as exc:
                logger.exception("Failed to reopen settings panel after password refresh for %s", linked_number)
                await message.reply_text(
                    f"❌ تم العثور على كلمة المرور لكن تعذر تحميل الإعدادات.\nتفاصيل الخطأ: {exc}",
                    reply_markup=build_main_keyboard(admin=(int(user_id) == int(ADMIN_ID))),
                )
            return

    manual_lines = [
        "⚙️ فتح إعدادات الرقم من داخل البوت.",
        "إذا كان الباسورد محفوظاً سيتم فتح اللوحة مباشرة.",
        "إذا لم يكن محفوظاً، اختر لغة الصفحة ثم أرسل الرقم الدولي + كلمة المرور في رسالة واحدة.",
    ]
    if linked_number:
        manual_lines.append(f"📞 رقمك المربوط الحالي: {linked_number}")
    else:
        manual_lines.append("ℹ️ لا يوجد رقم مربوط حالياً، يمكنك الدخول يدوياً إذا كان لديك الرقم وكلمة السر.")

    context.user_data.pop("drf_auth_payload", None)
    await message.reply_text(
        "\n".join(manual_lines),
        reply_markup=build_pair_language_keyboard(mode="drf"),
    )


async def drf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update)
    if not await ensure_subscription(update, context):
        return
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return
    await open_linked_number_settings_panel(message, context, user.id)

def get_green_api_send_message_url() -> str:
    if GREEN_API_ID_INSTANCE and GREEN_API_TOKEN_INSTANCE:
        return (
            f"{GREEN_API_BASE_URL}/waInstance{GREEN_API_ID_INSTANCE}"
            f"/sendMessage/{GREEN_API_TOKEN_INSTANCE}"
        )
    return ""


def send_whatsapp_message_sync(chat_id: str, message: str) -> dict[str, Any]:
    endpoint = get_green_api_send_message_url()
    if not endpoint:
        raise RuntimeError("Green API sendMessage is not configured.")
    normalized_chat_id = normalize_chat_id(chat_id)
    if not normalized_chat_id.endswith("@c.us"):
        raise RuntimeError("Invalid WhatsApp chat id.")
    response = requests.post(
        endpoint,
        json={"chatId": normalized_chat_id, "message": message, "linkPreview": True},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    if "application/json" in response.headers.get("content-type", ""):
        return response.json()
    return {"response": response.text}


async def send_whatsapp_message(chat_id: str, message: str) -> dict[str, Any]:
    return await asyncio.to_thread(send_whatsapp_message_sync, chat_id, message)


def get_green_api_send_file_url() -> str:
    if GREEN_API_ID_INSTANCE and GREEN_API_TOKEN_INSTANCE:
        return (
            f"{GREEN_API_BASE_URL}/waInstance{GREEN_API_ID_INSTANCE}"
            f"/sendFileByUrl/{GREEN_API_TOKEN_INSTANCE}"
        )
    return ""


def send_whatsapp_image_by_url_sync(chat_id: str, file_url: str, caption: str = "") -> dict[str, Any]:
    endpoint = get_green_api_send_file_url()
    if not endpoint:
        raise RuntimeError("Green API sendFileByUrl is not configured.")
    normalized_chat_id = normalize_chat_id(chat_id)
    if not normalized_chat_id.endswith("@c.us"):
        raise RuntimeError("Invalid WhatsApp chat id.")
    response = requests.post(
        endpoint,
        json={
            "chatId": normalized_chat_id,
            "urlFile": str(file_url or "").strip(),
            "fileName": "goldenqueen-link.png",
            "caption": caption,
        },
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    if "application/json" in response.headers.get("content-type", ""):
        return response.json()
    return {"response": response.text}


async def send_whatsapp_image_by_url(chat_id: str, file_url: str, caption: str = "") -> dict[str, Any]:
    return await asyncio.to_thread(send_whatsapp_image_by_url_sync, chat_id, file_url, caption)


def build_linked_number_private_message(number: str = "", site_password: str = "", bot_link: str = "") -> str:
    normalized_number = normalize_phone_number(number)
    lines = ["✅ تم ربط الرقم بنجاح من داخل البوت بدون أي موقع خارجي أو صفحة ربط."]
    if normalized_number:
        lines.append(f"📞 الرقم المربوط: {normalized_number}")
    lines.append("💾 جلسة هذا الرقم محفوظة داخل البوت نفسه وقاعدة البيانات.")
    lines.append("♻️ سيبقى الرقم شغالاً مادام بوت الربط شغال.")
    lines.append("🗑️ إذا حذفت الجلسة من البوت سيتم تسجيل خروجها من واتساب وحذفها من قاعدة البيانات تلقائياً.")
    lines.append("🔄 وإذا خرجت الجلسة من واتساب فسيتم حذفها من البوت وقاعدة البيانات تلقائياً.")
    if site_password:
        lines.append(f"🔐 كلمة سر إعدادات الرقم: {site_password}")
    else:
        lines.append("⏳ جارِ تجهيز كلمة سر إعدادات الرقم، وستصلك تلقائيًا عند توفرها.")
    if bot_link:
        lines.append(f"🤖 إدارة الرقم من داخل البوت: {bot_link}")
    lines.append("😀 هذه الرسالة خاصة بهذا الرقم فقط.")
    return "\n".join(lines)


async def deliver_linked_number_private_bundle(number: str, site_password: str = "", bot_link: str = "") -> bool:
    normalized_number = normalize_phone_number(number)
    if not normalized_number:
        return False

    linked_payload = LINKED_WHATSAPP_USERS.get(normalized_number, {})
    if not isinstance(linked_payload, dict):
        linked_payload = {}

    updated = False
    image_url = str(DEFAULT_LINKED_MESSAGE_IMAGE_URL or "").strip()
    image_signature = image_url or "no-image"
    if image_url and linked_payload.get("whatsapp_linked_image_signature") != image_signature:
        try:
            await send_whatsapp_image_by_url(normalized_number, image_url, "✅ تم الربط بنجاح")
            linked_payload["whatsapp_linked_image_signature"] = image_signature
            linked_payload["whatsapp_linked_image_sent_at"] = datetime.now(timezone.utc).isoformat()
            updated = True
        except Exception:
            logger.exception("Failed to send linked image to WhatsApp number %s", normalized_number)

    message_signature = json.dumps({
        "password": str(site_password or "").strip(),
        "bot_link": str(bot_link or "").strip(),
    }, ensure_ascii=False, sort_keys=True)
    if linked_payload.get("whatsapp_private_bundle_signature") == message_signature:
        if updated:
            linked_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            LINKED_WHATSAPP_USERS[normalized_number] = linked_payload
            save_linked_whatsapp_users()
        return True

    await send_whatsapp_message(normalized_number, build_linked_number_private_message(normalized_number, site_password, bot_link))
    linked_payload["whatsapp_private_bundle_signature"] = message_signature
    linked_payload["whatsapp_private_bundle_sent_at"] = datetime.now(timezone.utc).isoformat()
    linked_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    LINKED_WHATSAPP_USERS[normalized_number] = linked_payload
    save_linked_whatsapp_users()
    return True


def get_green_api_logout_url() -> str:
    if GREEN_API_ID_INSTANCE and GREEN_API_TOKEN_INSTANCE:
        return (
            f"{GREEN_API_BASE_URL}/waInstance{GREEN_API_ID_INSTANCE}"
            f"/logout/{GREEN_API_TOKEN_INSTANCE}"
        )
    return ""


def logout_whatsapp_instance_sync() -> dict[str, Any]:
    endpoint = get_green_api_logout_url()
    if not endpoint:
        raise RuntimeError("Green API logout is not configured.")
    response = requests.get(endpoint, timeout=30)
    response.raise_for_status()
    if "application/json" in response.headers.get("content-type", ""):
        return response.json()
    return {"response": response.text}


async def logout_whatsapp_instance() -> dict[str, Any]:
    return await asyncio.to_thread(logout_whatsapp_instance_sync)


def delete_pairing_session_sync(number: str) -> dict[str, Any]:
    normalized_number = normalize_phone_number(number)
    if not normalized_number:
        return {"success": False, "error": "invalid phone"}

    candidate_bases: list[str] = []
    for base in (INTERNAL_PAIRING_BASE_URL, get_url_base(resolve_pair_code_api_url(), INTERNAL_PAIRING_BASE_URL)):
        cleaned_base = str(base or "").strip().rstrip("/")
        if cleaned_base and cleaned_base not in candidate_bases:
            candidate_bases.append(cleaned_base)

    last_error: Optional[Exception] = None
    for base in candidate_bases:
        try:
            response = requests.delete(f"{base}/api/session/{normalized_number}", timeout=25)
            if response.status_code in {200, 202, 204, 404}:
                if "application/json" in response.headers.get("content-type", ""):
                    return response.json()
                return {"success": response.status_code != 404, "status_code": response.status_code}
        except Exception as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    return {"success": False}


async def delete_pairing_session(number: str) -> dict[str, Any]:
    return await asyncio.to_thread(delete_pairing_session_sync, number)


def remove_local_number_records(number: str) -> bool:
    normalized_number = normalize_phone_number(number)
    if not normalized_number:
        return False

    removed = False
    if normalized_number in LINKED_WHATSAPP_USERS:
        LINKED_WHATSAPP_USERS.pop(normalized_number, None)
        save_linked_whatsapp_users()
        removed = True
    if normalized_number in PENDING_PAIRINGS:
        PENDING_PAIRINGS.pop(normalized_number, None)
        save_pending_pairings()
        removed = True
    SESSION_RECONCILE_MISS_COUNTS.pop(normalized_number, None)
    return removed


def is_delete_pairing_result_successful(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("success") is True or result.get("deleted") is True:
        return True
    status_code_raw = str(result.get("status_code") or "").strip()
    status_code = int(status_code_raw) if status_code_raw.isdigit() else 0
    if status_code in {200, 202, 204, 404}:
        return True
    error_text = str(result.get("error") or result.get("message") or "").strip().lower()
    return error_text in {"not found", "session not found", "already missing"}


async def unlink_number_everywhere(user_id: int, number: str) -> tuple[bool, str]:
    normalized_number = normalize_phone_number(number)
    if not normalized_number:
        return False, "❌ تعذر تحديد الرقم المطلوب."

    record = find_user_record_for_number(user_id, normalized_number)
    if not record_belongs_to_user(record, user_id):
        record = get_record_for_number(normalized_number)
    if not record_belongs_to_user(record, user_id):
        return False, "❌ هذا الرقم غير مربوط من حسابك داخل البوت."

    try:
        delete_result = await delete_pairing_session(normalized_number)
    except Exception as exc:
        logger.exception("Failed to delete pairing session for %s", normalized_number)
        return False, f"❌ تعذر حذف جلسة الرقم من واتساب وقاعدة البيانات تلقائياً: {exc}"

    if not is_delete_pairing_result_successful(delete_result):
        return False, "❌ تعذر إنهاء جلسة الرقم من واتساب وقاعدة البيانات، لذلك لم يتم حذفها من البوت حفاظاً على التزامن."

    remove_local_number_records(normalized_number)
    return True, f"✅ تم إلغاء ربط الرقم {normalized_number} وحذف جلسته من واتساب والبوت وقاعدة البيانات تلقائياً."


def track_background_task(task: asyncio.Task[Any]) -> None:
    BACKGROUND_TASKS.add(task)
    task.add_done_callback(lambda finished_task: BACKGROUND_TASKS.discard(finished_task))


def get_record_for_number(number: str) -> dict[str, Any]:
    normalized_number = normalize_phone_number(number)
    if not normalized_number:
        return {}
    merged: dict[str, Any] = {"whatsapp_number": normalized_number}
    linked_payload = LINKED_WHATSAPP_USERS.get(normalized_number)
    pending_payload = PENDING_PAIRINGS.get(normalized_number)
    if isinstance(pending_payload, dict):
        merged.update(pending_payload)
    if isinstance(linked_payload, dict):
        merged.update(linked_payload)
    apply_site_metadata(merged, merge_site_metadata(pending_payload, linked_payload))
    password_value = extract_site_password_from_record(merged)
    if password_value:
        merged["site_password"] = password_value
    return merged


def build_auto_stop_prefix_value(raw_prefix: Any) -> str:
    prefix_value = str(raw_prefix or "").strip()
    if prefix_value == "ايقاف تلقائي":
        return prefix_value
    if not prefix_value:
        return "ايقاف تلقائي"
    if "." not in prefix_value:
        return prefix_value
    updated_prefix = prefix_value.replace(".", "ايقاف تلقائي")
    updated_prefix = re.sub(r"\s{2,}", " ", updated_prefix).strip()
    return updated_prefix or "ايقاف تلقائي"


async def schedule_pairing_confirmation_prompt(number: str, explicit_user_id: Optional[int] = None, delay_seconds: int = 30) -> None:
    normalized_number = normalize_phone_number(number)
    if not normalized_number:
        return
    await asyncio.sleep(max(int(delay_seconds or 0), 0))
    latest_record = get_record_for_number(normalized_number)
    user_id = explicit_user_id or int(latest_record.get("telegram_user_id") or 0) or None
    if not user_id or TELEGRAM_APP is None:
        return
    if latest_record.get("telegram_pairing_confirmation_prompt_sent"):
        return
    try:
        await TELEGRAM_APP.bot.send_message(
            chat_id=user_id,
            text=f"❓ هل تم ربط حسابك بنجاح للرقم {normalized_number}?",
            reply_markup=build_pairing_confirmation_keyboard(normalized_number),
        )
        update_number_records(normalized_number, {
            "telegram_pairing_confirmation_prompt_sent": True,
            "telegram_pairing_confirmation_prompt_sent_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        logger.exception("Failed to send pairing confirmation prompt for %s", normalized_number)


async def apply_confirmed_pairing_updates(user_id: int, number: str) -> tuple[bool, str]:
    normalized_number = normalize_phone_number(number)
    if not normalized_number:
        return False, "❌ تعذر تحديد الرقم المطلوب."

    record = find_user_record_for_number(user_id, normalized_number)
    if not record_belongs_to_user(record, user_id):
        record = get_record_for_number(normalized_number)
    if not record_belongs_to_user(record, user_id):
        return False, "❌ هذا الرقم غير مربوط من حسابك داخل البوت."

    password_value = extract_site_password_from_record(record)
    if not password_value:
        await auto_request_site_password(normalized_number, explicit_user_id=user_id)
        refreshed_record = find_user_record_for_number(user_id, normalized_number)
        record = refreshed_record if isinstance(refreshed_record, dict) else get_record_for_number(normalized_number)
        password_value = extract_site_password_from_record(record)

    if not password_value:
        return False, "⌛ تم تأكيد الربط، لكن لسه ماقدرتش أقرأ بيانات الرقم كاملة تلقائيًا. جرّب بعد شوية."

    explicit_auth = {
        "number": normalized_number,
        "site_password": password_value,
        "site_app_id": str(record.get("site_app_id") or "").strip(),
        "settings_url": normalize_settings_url(record.get("settings_url")),
    }
    payload = await asyncio.to_thread(load_site_settings_sync, user_id, explicit_auth)
    settings_payload = payload.get("settings") if isinstance(payload, dict) else {}
    if not isinstance(settings_payload, dict):
        settings_payload = {}

    old_prefix = str(settings_payload.get("prefix") or "").strip()
    new_prefix = build_auto_stop_prefix_value(old_prefix)
    settings_payload["prefix"] = new_prefix
    settings_payload["autoStatusReact"] = "on"

    selected_emoji = str(record.get("emoji") or get_effective_user_emoji(user_id)).strip()[:10]
    emoji_list = [item for item in split_status_custom_react_emojis(settings_payload.get("statusCustomReact")) if item != selected_emoji]
    if selected_emoji:
        settings_payload["statusCustomReact"] = ",".join(([selected_emoji] + emoji_list)[:10])

    await asyncio.to_thread(save_site_settings_sync, user_id, settings_payload, explicit_auth)
    update_number_records(normalized_number, {
        "telegram_pairing_confirmation_answer": "yes",
        "telegram_pairing_confirmation_answered_at": datetime.now(timezone.utc).isoformat(),
        "post_link_prefix_updated": True,
        "post_link_prefix_updated_at": datetime.now(timezone.utc).isoformat(),
    })

    if old_prefix != new_prefix:
        return True, (
            f"✅ تم تأكيد ربط الرقم {normalized_number}.\n"
            f"🔁 تم تفعيل التفاعل التلقائي بالحالة.\n"
            f"📝 تم استبدال البادئة من {old_prefix or 'فارغ'} إلى {new_prefix}."
        )
    return True, (
        f"✅ تم تأكيد ربط الرقم {normalized_number}.\n"
        f"🔁 تم تفعيل التفاعل التلقائي بالحالة.\n"
        f"📝 البادئة الحالية: {new_prefix}."
    )


async def process_pairing_confirmation_yes(user_id: int, number: str) -> None:
    try:
        _success, message = await apply_confirmed_pairing_updates(user_id, number)
    except Exception as exc:
        logger.exception("Failed to process confirmed pairing updates for %s", number)
        message = f"❌ تعذر قراءة معلومات الرقم أو تحديث البادئة تلقائيًا: {exc}"

    if TELEGRAM_APP is None:
        return
    try:
        await TELEGRAM_APP.bot.send_message(
            chat_id=user_id,
            text=message,
            reply_markup=build_main_keyboard(admin=(int(user_id) == int(ADMIN_ID))),
        )
    except Exception:
        logger.exception("Failed to deliver confirmed pairing result to user %s", user_id)

async def auto_request_site_password(number: str, explicit_user_id: Optional[int] = None) -> None:
    normalized_number = normalize_phone_number(number)
    if not normalized_number or not get_green_api_send_message_url():
        return

    try:
        for delay in PASSWORD_DISCOVERY_ATTEMPT_DELAYS:
            if delay > 0:
                await asyncio.sleep(delay)

            current_record = get_record_for_number(normalized_number)
            current_password = extract_site_password_from_record(current_record)
            if current_password:
                await notify_site_password_detected(
                    normalized_number,
                    explicit_user_id=explicit_user_id,
                    site_metadata=current_record,
                )
                return

            try:
                await send_whatsapp_message(normalized_number, PASSWORD_DISCOVERY_COMMAND)
            except Exception:
                logger.exception("Failed to auto-request site password for %s", normalized_number)
                continue

            await asyncio.sleep(PASSWORD_DISCOVERY_RESPONSE_WAIT_SECONDS)
            refreshed_record = get_record_for_number(normalized_number)
            refreshed_password = extract_site_password_from_record(refreshed_record)
            if refreshed_password:
                await notify_site_password_detected(
                    normalized_number,
                    explicit_user_id=explicit_user_id,
                    site_metadata=refreshed_record,
                )
                return
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Automatic site password discovery failed for %s", normalized_number)


def iter_nested_values(payload: Any):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from iter_nested_values(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from iter_nested_values(item)


def extract_scalar_from_payload(payload: Any, candidate_keys: set[str]) -> str:
    for key, value in iter_nested_values(payload):
        normalized_key = str(key).lower().replace("-", "_").replace(" ", "_")
        if normalized_key not in candidate_keys:
            continue
        if isinstance(value, (dict, list)):
            continue
        text_value = str(value or "").strip()
        if text_value:
            return text_value
    return ""


def normalize_site_password(raw_value: Any) -> str:
    return normalize_ascii_digits(str(raw_value or "").strip())


def derive_site_app_id_from_password(password: Any) -> str:
    password_text = normalize_site_password(password)
    if len(password_text) == 6:
        return password_text[-1:]
    if len(password_text) == 7:
        return password_text[-2:]
    return ""


def extract_pairing_site_metadata(payload: Any) -> dict[str, str]:
    if not isinstance(payload, (dict, list)):
        return {}

    message_text = extract_incoming_message_text(payload) if isinstance(payload, dict) else ""
    password = normalize_site_password(
        extract_scalar_from_payload(payload, {"password", "pass", "pwd", "site_password", "settings_password", "owner_password", "ownerpass", "owner_pass"})
    )
    if not password:
        password = extract_site_password_from_message_text(message_text)

    app_id = str(
        extract_scalar_from_payload(
            payload,
            {"app", "app_id", "appid", "site_app", "settings_app", "site_app_id", "settings_app_id"},
        )
        or ""
    ).strip()
    settings_url = str(
        extract_scalar_from_payload(
            payload,
            {"settings_url", "settingsurl", "site_settings_url", "panel_url", "dashboard_url"},
        )
        or ""
    ).strip()

    if not app_id and password:
        app_id = derive_site_app_id_from_password(password)
    if settings_url and not settings_url.startswith("http"):
        settings_url = ""
    if not settings_url:
        settings_url = TARGET_SETTINGS_PAGE_URL

    return {
        "site_password": password,
        "site_app_id": app_id,
        "settings_url": settings_url,
    }


def merge_site_metadata(*sources: Any) -> dict[str, str]:
    merged = {"settings_url": TARGET_SETTINGS_PAGE_URL}
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in ("site_password", "site_app_id", "settings_url"):
            value = str(source.get(key) or "").strip()
            if value:
                merged[key] = value

    if not merged.get("site_app_id") and merged.get("site_password"):
        merged["site_app_id"] = derive_site_app_id_from_password(merged["site_password"])
    if not merged.get("settings_url"):
        merged["settings_url"] = TARGET_SETTINGS_PAGE_URL
    return merged


def apply_site_metadata(target: dict[str, Any], metadata: Optional[dict[str, str]]) -> None:
    if not isinstance(target, dict) or not metadata:
        return
    for key in ("site_password", "site_app_id", "settings_url"):
        value = str(metadata.get(key) or "").strip()
        if value:
            target[key] = value
    if not str(target.get("site_app_id") or "").strip() and str(target.get("site_password") or "").strip():
        target["site_app_id"] = derive_site_app_id_from_password(target.get("site_password"))
    if not str(target.get("settings_url") or "").strip():
        target["settings_url"] = TARGET_SETTINGS_PAGE_URL


def build_pair_code_result(code: str, source_payload: Any = None) -> dict[str, str]:
    resolved_code = normalize_pair_code(code)
    extracted_code = find_code_in_payload(source_payload)
    if extracted_code:
        resolved_code = extracted_code
    result = {"code": resolved_code}
    result.update(extract_pairing_site_metadata(source_payload))
    if not result.get("settings_url"):
        result["settings_url"] = TARGET_SETTINGS_PAGE_URL
    return result


def extract_telegram_user_id(payload: Any) -> Optional[int]:
    candidate_keys = {
        "telegram_user_id", "telegramuserid", "telegramid", "tg_user_id",
        "user_id", "userid", "telegram_chat_id", "chat_id"
    }
    for key, value in iter_nested_values(payload):
        normalized_key = str(key).lower().replace("-", "_").replace(" ", "_")
        if normalized_key in candidate_keys:
            try:
                return int(str(value).strip())
            except (TypeError, ValueError):
                continue
    return None


def extract_number_from_payload(payload: Any) -> str:
    candidates: list[str] = []

    def add_candidate(raw_value: Any) -> None:
        if raw_value in (None, ""):
            return
        if isinstance(raw_value, str):
            for token in extract_numeric_tokens_from_text(raw_value, min_digits=8, max_digits=15):
                if token not in candidates:
                    candidates.append(token)
            normalized = normalize_phone_number(raw_value)
            if 8 <= len(normalized) <= 15 and normalized not in candidates:
                candidates.append(normalized)
            return
        normalized = normalize_phone_number(str(raw_value or ""))
        if 8 <= len(normalized) <= 15 and normalized not in candidates:
            candidates.append(normalized)

    if isinstance(payload, dict):
        instance_data = payload.get("instanceData") if isinstance(payload.get("instanceData"), dict) else {}
        sender_data = payload.get("senderData") if isinstance(payload.get("senderData"), dict) else {}
        message_text = extract_incoming_message_text(payload)

        priority_values = [
            payload.get("whatsapp_number"),
            payload.get("phone"),
            payload.get("phoneNumber"),
            payload.get("number"),
            instance_data.get("wid"),
            payload.get("wid"),
            payload.get("viewer"),
            payload.get("viewerChatId"),
            payload.get("chatId"),
            sender_data.get("chatId"),
            payload.get("sender"),
            sender_data.get("sender"),
            payload.get("jid"),
            payload.get("participant"),
            payload.get("contactId"),
            message_text,
        ]
        for value in priority_values:
            add_candidate(value)

        for _, value in iter_nested_values(payload):
            if isinstance(value, (dict, list)):
                continue
            add_candidate(value)
    elif isinstance(payload, list):
        for item in payload:
            candidate = extract_number_from_payload(item)
            if candidate and candidate not in candidates:
                candidates.append(candidate)
    else:
        add_candidate(payload)

    for candidate in candidates:
        if candidate in PENDING_PAIRINGS or candidate in LINKED_WHATSAPP_USERS:
            return candidate
    return candidates[0] if candidates else ""


def resolve_pairing_target_number(payload: Any) -> str:
    number = extract_number_from_payload(payload)
    if number:
        return number

    extracted_code = normalize_pair_code(find_code_in_payload(payload) or extract_pair_code_from_text(payload))
    if extracted_code:
        for pending_number, pending_payload in PENDING_PAIRINGS.items():
            stored_code = normalize_pair_code((pending_payload or {}).get("last_pair_code") or "")
            if stored_code and stored_code == extracted_code:
                return pending_number

    if len(PENDING_PAIRINGS) == 1:
        lowered = json.dumps(payload, ensure_ascii=False).lower()
        if any(flag in lowered for flag in ("authorized", "authorised", "connected", "online", "success", "pair", "link", "instance")):
            return next(iter(PENDING_PAIRINGS.keys()))
    return ""


def payload_indicates_pairing_success(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False

    number = extract_number_from_payload(payload)
    webhook_type = str(payload.get("typeWebhook") or "").lower().strip()
    state_instance = str(payload.get("stateInstance") or "").lower().strip()
    status_instance = str(payload.get("statusInstance") or "").lower().strip()
    status_value = str(payload.get("status") or payload.get("instanceStatus") or payload.get("connectionStatus") or "").lower().strip()
    sender_data = payload.get("senderData") if isinstance(payload.get("senderData"), dict) else {}

    success_flags = (
        payload.get("success"),
        payload.get("paired"),
        payload.get("linked"),
        payload.get("authorized"),
        payload.get("authorised"),
        payload.get("connected"),
        payload.get("isAuthorized"),
        payload.get("isConnected"),
        payload.get("isLoggedIn"),
        payload.get("loggedIn"),
    )
    if any(flag is True for flag in success_flags) and number:
        return True
    if webhook_type == "stateinstancechanged" and state_instance in {"authorized", "authorised", "connected", "online"} and number:
        return True
    if webhook_type == "statusinstancechanged" and status_instance in {"authorized", "authorised", "connected", "online"} and number and number in PENDING_PAIRINGS:
        return True
    if (
        webhook_type == "incomingmessagereceived"
        and number
        and number in PENDING_PAIRINGS
        and not bool(payload.get("fromMe"))
        and not bool(sender_data.get("fromMe"))
    ):
        return True

    lowered = json.dumps(payload, ensure_ascii=False).lower()
    positive_markers = (
        "paired", "linked", "authorized", "authorised", "connected",
        "success", "logged in", "login successful", "device connected",
        "stateinstancechanged", '"authorized"', '"online"'
    )
    pairing_markers = (
        "pair", "link", "authorize", "authorise", "connect", "instance",
        "stateinstancechanged", "statusinstancechanged", "whatsapp"
    )
    if number and status_value in {"authorized", "authorised", "connected", "online", "success", "logged_in", "logged in"}:
        has_context = any(marker in lowered for marker in pairing_markers)
        if has_context:
            return True

    has_positive = any(marker in lowered for marker in positive_markers)
    has_context = any(marker in lowered for marker in pairing_markers)
    return has_positive and has_context and bool(number)


def extract_viewer_chat_id(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""

    candidate_paths = [
        payload.get("viewerChatId"),
        payload.get("viewer"),
        payload.get("chatId"),
        payload.get("sender"),
        payload.get("participant"),
        payload.get("contactId"),
        (payload.get("senderData") or {}).get("chatId") if isinstance(payload.get("senderData"), dict) else None,
        (payload.get("senderData") or {}).get("sender") if isinstance(payload.get("senderData"), dict) else None,
    ]

    for raw in candidate_paths:
        chat_id = normalize_chat_id(raw)
        if chat_id.endswith("@c.us"):
            return chat_id

    for _, value in iter_nested_values(payload):
        chat_id = normalize_chat_id(value)
        if chat_id.endswith("@c.us"):
            return chat_id
    return ""


def extract_incoming_message_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""

    candidate_keys = {
        "text", "body", "message", "textmessage", "extendedtextmessage", "caption",
        "conversation", "selectedbuttonid", "selectedbuttontext", "selectedrowid", "selectedrowtitle",
    }
    for key, value in iter_nested_values(payload):
        normalized_key = str(key).lower().replace("-", "_").replace(" ", "_")
        if normalized_key not in candidate_keys:
            continue
        if isinstance(value, (dict, list)):
            continue
        text_value = str(value or "").strip()
        if text_value:
            return text_value
    return ""


def extract_private_whatsapp_command(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""

    webhook_type = str(payload.get("typeWebhook") or "").lower()
    if webhook_type and webhook_type != "incomingmessagereceived":
        return ""

    if bool(payload.get("fromMe")):
        return ""
    sender_data = payload.get("senderData") if isinstance(payload.get("senderData"), dict) else {}
    if bool(sender_data.get("fromMe")):
        return ""

    chat_id = extract_viewer_chat_id(payload)
    if not chat_id.endswith("@c.us"):
        return ""

    lowered_payload = json.dumps(payload, ensure_ascii=False).lower()
    if "status@broadcast" in lowered_payload or "newsletter" in lowered_payload or "channel" in lowered_payload:
        return ""

    message_text = extract_incoming_message_text(payload).strip()
    if not message_text:
        return ""

    normalized_text = message_text.lower().strip()
    first_token = normalized_text.split()[0]
    if first_token[:1] in {".", "/", "!", "#"}:
        first_token = first_token[1:]

    command_map = {
        "alive": "alive",
        "ping": "alive",
        "bot": "bot",
        "menu": "bot",
        "help": "bot",
        "start": "bot",
        "owner": "bot",
        "status": "bot",
        "settings": "settings",
    }
    return command_map.get(first_token, "")


def payload_indicates_status_interaction(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    lowered = json.dumps(payload, ensure_ascii=False).lower()
    markers = ("status", "story", "view", "viewer", "reaction", "react", "reply")
    webhook_type = str(payload.get("typeWebhook") or "").lower()
    return any(marker in lowered for marker in markers) or webhook_type == "incomingmessagestatus"


def mark_event_processed(event_key: str) -> bool:
    if not event_key:
        return False
    if event_key in AUTO_REPLY_EVENT_LOG:
        return False
    AUTO_REPLY_EVENT_LOG[event_key] = datetime.now(timezone.utc).isoformat()
    if len(AUTO_REPLY_EVENT_LOG) > 5000:
        for key in list(sorted(AUTO_REPLY_EVENT_LOG.keys()))[:-3000]:
            AUTO_REPLY_EVENT_LOG.pop(key, None)
    save_auto_reply_log()
    return True


async def notify_site_password_detected(number: str, explicit_user_id: Optional[int] = None, site_metadata: Optional[dict[str, str]] = None) -> bool:
    normalized_number = normalize_phone_number(number)
    if not normalized_number:
        return False

    linked_payload = LINKED_WHATSAPP_USERS.get(normalized_number, {})
    pending_payload = PENDING_PAIRINGS.get(normalized_number, {})
    if not isinstance(linked_payload, dict):
        linked_payload = {}
    if not isinstance(pending_payload, dict):
        pending_payload = {}

    merged_site_metadata = merge_site_metadata(pending_payload, linked_payload, site_metadata or {})
    site_password = normalize_site_password(merged_site_metadata.get("site_password"))
    if not site_password:
        return False

    settings_url = str(merged_site_metadata.get("settings_url") or linked_payload.get("settings_url") or TARGET_SETTINGS_PAGE_URL).strip() or TARGET_SETTINGS_PAGE_URL
    user_id = explicit_user_id or int(linked_payload.get("telegram_user_id") or pending_payload.get("telegram_user_id") or 0) or None

    updated = False
    if linked_payload:
        before_payload = dict(linked_payload)
        apply_site_metadata(linked_payload, merged_site_metadata)
        if linked_payload != before_payload:
            linked_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            LINKED_WHATSAPP_USERS[normalized_number] = linked_payload
            updated = True
    if pending_payload:
        before_pending = dict(pending_payload)
        apply_site_metadata(pending_payload, merged_site_metadata)
        if pending_payload != before_pending:
            pending_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            PENDING_PAIRINGS[normalized_number] = pending_payload
            save_pending_pairings()

    if not user_id or TELEGRAM_APP is None:
        if updated:
            save_linked_whatsapp_users()
        return False

    if linked_payload.get("telegram_password_sent_for_value") == site_password:
        if updated:
            save_linked_whatsapp_users()
        return True

    bot_link = str(BOT_LINK_CACHE.get("url") or "").strip()
    message_lines = [
        f"✅ تم اكتشاف كلمة سر الرقم {normalized_number} بنجاح.",
        f"🔐 كلمة سر الإعدادات: {site_password}",
        f"⚙️ صفحة الإعدادات: {TARGET_SETTINGS_PAGE_URL}",
        "📌 تم حفظ البيانات داخل البوت لهذا الرقم، ويمكنك الآن فتح الإعدادات أو تغيير إيموجي الحالة.",
    ]

    try:
        await TELEGRAM_APP.bot.send_message(
            chat_id=user_id,
            text="\n".join(message_lines),
            reply_markup=build_main_keyboard(admin=(int(user_id) == int(ADMIN_ID))),
        )
        await deliver_linked_number_private_bundle(normalized_number, site_password, bot_link)
        linked_payload.setdefault("telegram_user_id", user_id)
        linked_payload.setdefault("whatsapp_number", normalized_number)
        apply_site_metadata(linked_payload, merged_site_metadata)
        linked_payload["telegram_password_sent_for_value"] = site_password
        linked_payload["telegram_password_message_sent_at"] = datetime.now(timezone.utc).isoformat()
        linked_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        LINKED_WHATSAPP_USERS[normalized_number] = linked_payload
        save_linked_whatsapp_users()
        return True
    except Exception:
        logger.exception("Failed to notify Telegram user %s about detected password", user_id)
        if updated:
            save_linked_whatsapp_users()
        return False


async def notify_successful_pairing(number: str, explicit_user_id: Optional[int] = None, site_metadata: Optional[dict[str, str]] = None) -> bool:
    normalized_number = normalize_phone_number(number)
    if not normalized_number:
        return False

    pending = PENDING_PAIRINGS.get(normalized_number, {})
    user_id = explicit_user_id or int(pending.get("telegram_user_id") or 0) or None
    if not user_id:
        for payload in PENDING_PAIRINGS.values():
            if normalize_phone_number(payload.get("whatsapp_number", "")) == normalized_number:
                user_id = int(payload.get("telegram_user_id") or 0) or None
                pending = payload
                break

    linked_payload = LINKED_WHATSAPP_USERS.get(normalized_number, {})
    if not isinstance(linked_payload, dict):
        linked_payload = {}

    merged_site_metadata = merge_site_metadata(pending, linked_payload, site_metadata or {})
    linked_payload.update({
        "telegram_user_id": user_id or linked_payload.get("telegram_user_id"),
        "telegram_username": pending.get("telegram_username") or linked_payload.get("telegram_username", ""),
        "telegram_full_name": pending.get("telegram_full_name") or linked_payload.get("telegram_full_name", ""),
        "whatsapp_number": normalized_number,
        "emoji": pending.get("emoji") or linked_payload.get("emoji") or (get_effective_user_emoji(user_id) if user_id else SETTINGS["current_emoji"]),
        "linked_at": linked_payload.get("linked_at") or datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "pairing_notified": True,
    })
    apply_site_metadata(linked_payload, merged_site_metadata)
    LINKED_WHATSAPP_USERS[normalized_number] = linked_payload
    save_linked_whatsapp_users()
    PENDING_PAIRINGS.pop(normalized_number, None)
    save_pending_pairings()

    if user_id and linked_payload.get("emoji"):
        try:
            await asyncio.to_thread(sync_user_emoji_to_site, user_id, str(linked_payload.get("emoji") or ""))
        except Exception:
            logger.exception("Failed to sync emoji after successful pairing for user %s", user_id)

    site_password = normalize_site_password(linked_payload.get("site_password"))
    bot_link = str(BOT_LINK_CACHE.get("url") or "").strip()
    try:
        await deliver_linked_number_private_bundle(normalized_number, site_password, bot_link)
        linked_payload["whatsapp_pairing_instruction_sent"] = True
        linked_payload["whatsapp_pairing_instruction_sent_at"] = datetime.now(timezone.utc).isoformat()
        linked_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        LINKED_WHATSAPP_USERS[normalized_number] = linked_payload
        save_linked_whatsapp_users()
    except Exception:
        logger.exception("Failed to send WhatsApp linked bundle to %s", normalized_number)

    if not user_id or TELEGRAM_APP is None or TELEGRAM_LOOP is None:
        return False

    if linked_payload.get("telegram_success_message_sent"):
        return True

    message_lines = [
        f"✅ تم ربط الرقم {normalized_number} بنجاح من داخل البوت.",
        "🤖 لا تحتاج أي موقع خارجي أو صفحة ربط لإدارة الرقم.",
        "💾 الجلسة محفوظة داخل البوت نفسه وقاعدة البيانات.",
        "♻️ سيبقى الرقم شغالاً مادام بوت الربط شغال.",
        "🗑️ إذا حذفت الجلسة من البوت فسيتم تسجيل خروجها من واتساب وحذفها من قاعدة البيانات تلقائياً.",
        "🔄 وإذا خرجت الجلسة من واتساب فسيتم حذفها من البوت وقاعدة البيانات تلقائياً.",
    ]
    if site_password:
        message_lines.extend(["", f"🔐 كلمة سر الإعدادات: {site_password}", "😀 يمكنك الآن فتح إعدادات الرقم من داخل البوت أو تغيير إيموجي الحالة."])
    else:
        message_lines.extend(["", build_password_wait_message(normalized_number)])

    try:
        await TELEGRAM_APP.bot.send_message(
            chat_id=user_id,
            text="\n".join(message_lines),
            reply_markup=build_main_keyboard(admin=(user_id == ADMIN_ID)),
        )
        linked_payload["telegram_success_message_sent"] = True
        linked_payload["telegram_success_message_sent_at"] = datetime.now(timezone.utc).isoformat()
        linked_payload["auto_settings_probe_started_at"] = linked_payload.get("auto_settings_probe_started_at") or datetime.now(timezone.utc).isoformat()
        save_linked_whatsapp_users()
        if not site_password and TELEGRAM_LOOP is not None and get_green_api_send_message_url():
            track_background_task(asyncio.create_task(auto_request_site_password(normalized_number, explicit_user_id=user_id)))
        return True
    except Exception:
        logger.exception("Failed to notify Telegram user %s about successful pairing", user_id)
        return False


async def process_external_webhook(payload: dict[str, Any]) -> None:
    try:
        payload_number = resolve_pairing_target_number(payload)
        extracted_site_metadata = extract_pairing_site_metadata(payload)
        has_site_metadata = any(str(extracted_site_metadata.get(key) or "").strip() for key in ("site_password", "site_app_id", "settings_url"))
        if payload_number and has_site_metadata:
            upsert_site_metadata_for_number(payload_number, extracted_site_metadata)

        if payload_indicates_pairing_success(payload):
            number = payload_number or resolve_pairing_target_number(payload)
            if number:
                await notify_successful_pairing(
                    number,
                    explicit_user_id=extract_telegram_user_id(payload),
                    site_metadata=extracted_site_metadata,
                )

        if payload_number and str(extracted_site_metadata.get("site_password") or "").strip():
            await notify_site_password_detected(
                payload_number,
                explicit_user_id=extract_telegram_user_id(payload),
                site_metadata=extracted_site_metadata,
            )

        command_key = extract_private_whatsapp_command(payload)
        if command_key:
            viewer_chat_id = extract_viewer_chat_id(payload)
            if viewer_chat_id:
                event_key = f"cmd:{command_key}:{payload.get('idMessage') or payload.get('timestamp') or viewer_chat_id}:{viewer_chat_id}"
                if mark_event_processed(event_key):
                    try:
                        await send_whatsapp_message(viewer_chat_id, build_whatsapp_command_reply(command_key))
                    except Exception:
                        logger.exception("Failed to send WhatsApp command reply to %s", viewer_chat_id)

        if SETTINGS.get("auto_reply_enabled") and payload_indicates_status_interaction(payload):
            viewer_chat_id = extract_viewer_chat_id(payload)
            if viewer_chat_id:
                event_key = f"{payload.get('typeWebhook') or 'status'}:{payload.get('idMessage') or payload.get('timestamp') or viewer_chat_id}:{viewer_chat_id}"
                if mark_event_processed(event_key):
                    try:
                        await send_whatsapp_message(viewer_chat_id, build_auto_reply_message())
                    except Exception:
                        logger.exception("Failed to send WhatsApp auto reply to %s", viewer_chat_id)
    except Exception:
        logger.exception("Failed to process external webhook payload")


def build_number_variants(raw: str) -> list[str]:
    normalized = normalize_phone_number(raw)
    variants = []
    if normalized:
        variants.append(normalized)
        variants.append(f"+{normalized}")
    deduped = []
    for item in variants:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def find_code_in_payload(payload: Any) -> Optional[str]:
    keys_priority = [
        "pair_code",
        "pairing_code",
        "pairingCode",
        "code",
        "link_code",
        "linkCode",
    ]

    if isinstance(payload, dict):
        for key in keys_priority:
            value = payload.get(key)
            if value in (None, ""):
                continue
            if isinstance(value, (dict, list)):
                found_nested = find_code_in_payload(value)
                if found_nested:
                    return found_nested
                continue
            candidate = extract_pair_code_from_text(value) if isinstance(value, str) else normalize_pair_code(value)
            if is_plausible_pair_code(candidate):
                return candidate
        for nested_key, value in payload.items():
            if str(nested_key) in keys_priority:
                continue
            found = find_code_in_payload(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = find_code_in_payload(item)
            if found:
                return found
    elif isinstance(payload, str):
        extracted = extract_pair_code_from_text(payload)
        if extracted:
            return extracted
    return None


def resolve_pair_code_api_url() -> str:
    internal_url = normalize_pairing_api_url(
        f"{INTERNAL_PAIRING_BASE_URL}/api/pairing",
        fallback=f"{INTERNAL_PAIRING_BASE_URL}/api/pairing",
    )
    if SETTINGS.get("pair_code_api_url") != internal_url:
        SETTINGS["pair_code_api_url"] = internal_url
        save_settings()
    return internal_url


def start_healthcheck_server() -> Optional[ThreadingHTTPServer]:
    # Accept PORT from common hosting envs; fall back to a default so the host
    # never kills the worker for "no bind". Free hosts (Render/Railway/Koyeb/
    # Hugging Face/etc.) require an HTTP listener on $PORT or they SIGTERM us.
    raw_ports: list[str] = []
    for key in ("PORT", "HTTP_PORT", "APP_PORT", "WEB_PORT", "SERVER_PORT"):
        value = (os.getenv(key) or "").strip()
        if value:
            raw_ports.append(value)
    if not raw_ports:
        raw_ports.append("8080")

    port = 8080
    for raw in raw_ports:
        try:
            port = int(raw)
            break
        except ValueError:
            logger.warning("Ignoring invalid PORT value: %s", raw)

    started_at = time.time()

    class HealthHandler(BaseHTTPRequestHandler):
        server_version = "TelegramBotWebhook/1.0"

        def _send_json(self, payload: dict[str, Any], status_code: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                self.wfile.write(body)
            except Exception:
                pass

        def _read_json_body(self) -> dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0") or 0)
            raw_body = self.rfile.read(content_length) if content_length else b"{}"
            if not raw_body:
                return {}
            try:
                parsed = json.loads(raw_body.decode("utf-8"))
                return parsed if isinstance(parsed, dict) else {"payload": parsed}
            except Exception as exc:
                raise ValueError("Invalid JSON body") from exc

        def _is_secret_valid(self) -> bool:
            expected_secret = str(SETTINGS.get("webhook_secret") or "").strip()
            if not expected_secret:
                return True
            provided_secret = (
                self.headers.get("X-Webhook-Secret")
                or self.headers.get("X-API-Key")
                or self.headers.get("Authorization", "").removeprefix("Bearer ")
            )
            return str(provided_secret or "").strip() == expected_secret

        def do_GET(self):
            uptime = int(time.time() - started_at)
            payload: dict[str, Any]
            if self.path in ("/", "/healthz", "/health", "/ping", "/alive", "/keepalive"):
                payload = {
                    "status": "ok",
                    "service": "telegram-bot",
                    "uptime_seconds": uptime,
                    "time": datetime.now(timezone.utc).isoformat(),
                    "bot_token_valid": bool(re.fullmatch(r"\d{6,}:[A-Za-z0-9_-]{20,}", BOT_TOKEN or "")),
                    "webhook_paths": ["/webhook", "/green-api/webhook", "/pairing/webhook"],
                }
                self._send_json(payload, 200)
                return
            if self.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            self._send_json({
                "status": "ok",
                "service": "telegram-bot",
                "message": "Telegram bot is running. Use POST /webhook or POST /green-api/webhook for Green API events.",
                "uptime_seconds": uptime,
                "webhook_paths": ["/webhook", "/green-api/webhook", "/pairing/webhook"],
            })

        def do_POST(self):
            if self.path in ("/", "/healthz", "/health", "/ping", "/alive", "/keepalive"):
                self._send_json({"status": "ok"}, 200)
                return
            if self.path not in {"/webhook", "/green-api/webhook", "/pairing/webhook"}:
                self._send_json({"status": "error", "message": "Not Found"}, 404)
                return

            if not self._is_secret_valid():
                self._send_json({"status": "error", "message": "Unauthorized"}, 401)
                return

            try:
                payload = self._read_json_body()
            except ValueError:
                self._send_json({"status": "error", "message": "Invalid JSON"}, 400)
                return

            if TELEGRAM_LOOP is not None:
                asyncio.run_coroutine_threadsafe(process_external_webhook(payload), TELEGRAM_LOOP)
            self._send_json({"status": "accepted"}, 202)

        def log_message(self, format: str, *args) -> None:
            return  # keep hosting logs clean


    class ReusableThreadingHTTPServer(ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    try:
        server = ReusableThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    except OSError as exc:
        logger.warning("Could not bind health server on port %s (%s), retrying on 8080", port, exc)
        try:
            server = ReusableThreadingHTTPServer(("0.0.0.0", 8080), HealthHandler)
        except OSError as exc2:
            logger.error("Could not bind health server on fallback port 8080 either: %s", exc2)
            return None

    thread = threading.Thread(target=server.serve_forever, name="health-server", daemon=True)
    thread.start()
    logger.info("Healthcheck/Webhook server started on port %s", server.server_address[1])
    print(
        f"[keep-alive] HTTP server listening on 0.0.0.0:{server.server_address[1]} - bot is alive",
        flush=True,
    )
    return server


def build_pairing_headers(api_url: str) -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.4 Safari/605.1.15"
        ),
        "X-Requested-With": "XMLHttpRequest",
    }
    profile = get_pairing_api_profile(api_url)
    headers.update({
        key: str(value)
        for key, value in (profile.get("extra_headers") or {}).items()
        if value is not None and str(value).strip()
    })
    api_base_url = get_url_base(api_url)
    if api_url.startswith(TARGET_SITE_BASE_URL):
        headers.update(
            {
                "Origin": TARGET_SITE_BASE_URL,
                "Referer": f"{TARGET_SITE_BASE_URL}/",
            }
        )
    elif api_base_url and "Origin" not in headers:
        headers.update(
            {
                "Origin": api_base_url,
                "Referer": f"{api_base_url}/",
            }
        )
    return headers


def build_pairing_attempts(api_url: str, configured_method: str, configured_field: str) -> list[tuple[str, str]]:
    profile = get_pairing_api_profile(api_url)
    methods: list[str] = []
    for candidate in [configured_method, profile.get("default_method"), *(profile.get("candidate_methods") or []), "GET", "POST"]:
        normalized_method = str(candidate or "").upper().strip()
        if normalized_method in {"GET", "POST"} and normalized_method not in methods:
            methods.append(normalized_method)
    fields: list[str] = []
    for candidate in [configured_field, profile.get("default_number_field"), *(profile.get("candidate_number_fields") or []), "phone", "num", "number", "phoneNumber"]:
        normalized_field = str(candidate or "").strip()
        if normalized_field and normalized_field not in fields:
            fields.append(normalized_field)
    return [(method, field) for method in methods for field in fields]


# Persistent session file so cookies (including any cached pairing-session tokens)
# survive between restarts of the Telegram bot.
_PAIR_API_SESSION_PATH = BASE_DIR / ".pair_api_session.json"


def _load_pair_api_session() -> dict[str, Any]:
    if not _PAIR_API_SESSION_PATH.exists():
        return {}
    try:
        return json.loads(_PAIR_API_SESSION_PATH.read_text(encoding="utf-8") or "{}") or {}
    except Exception:
        return {}


def _save_pair_api_session(payload: dict[str, Any]) -> None:
    try:
        _PAIR_API_SESSION_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception:
        logger.exception("Failed to persist pair API session state")


def _try_apply_persisted_cookies(session: requests.Session, api_url: str) -> None:
    """Rehydrate cookies from disk so Render-spun-down instances inherit our session."""
    state = _load_pair_api_session()
    cookies = state.get("cookies") or []
    if not cookies:
        return
    parsed = urlparse(api_url)
    target_host = parsed.hostname or ""

    if isinstance(cookies, dict):
        cookies = [{"name": key, "value": value, "domain": target_host, "path": "/"} for key, value in cookies.items()]

    if not isinstance(cookies, list):
        return

    for item in cookies:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        value = item.get("value")
        if not name or value is None:
            continue
        try:
            cookie_kwargs: dict[str, Any] = {"path": str(item.get("path") or "/").strip() or "/"}
            domain = str(item.get("domain") or target_host or "").strip()
            if domain:
                cookie_kwargs["domain"] = domain
            expires = item.get("expires")
            if expires not in (None, ""):
                try:
                    cookie_kwargs["expires"] = int(float(expires))
                except (TypeError, ValueError):
                    pass
            secure = item.get("secure")
            if secure is not None:
                cookie_kwargs["secure"] = bool(secure)
            session.cookies.set(name, str(value), **cookie_kwargs)
        except Exception:
            continue


def _persist_session_cookies(session: requests.Session) -> None:
    try:
        cookie_records: list[dict[str, Any]] = []
        for cookie in session.cookies:
            if not getattr(cookie, "name", None):
                continue
            cookie_records.append({
                "name": str(cookie.name),
                "value": str(cookie.value),
                "domain": str(cookie.domain or ""),
                "path": str(cookie.path or "/"),
                "expires": cookie.expires,
                "secure": bool(cookie.secure),
            })
        if not cookie_records:
            return
        _save_pair_api_session({"cookies": cookie_records, "updated_at": datetime.now(timezone.utc).isoformat()})
    except Exception:
        logger.exception("Failed to serialize session cookies")


def _build_repeatable_session(api_url: str) -> requests.Session:
    """Single persistent Session: retains cookies + auth across number-variant attempts,
    which keeps the server's Baileys state keyed to the same browser fingerprint and
    lets the login side finish writing creds before our retry timer expires."""
    session = requests.Session()
    # Match the browser profile used in build_pairing_headers for request fingerprint symmetry.
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.4 Safari/605.1.15"
        ),
    })
    profile = get_pairing_api_profile(api_url)
    headers_extra = profile.get("extra_headers") or {}
    for key, value in headers_extra.items():
        if value is not None and str(value).strip():
            session.headers[str(key)] = str(value)

    api_base_url = get_url_base(api_url)
    if api_url.startswith(TARGET_SITE_BASE_URL):
        session.headers["Origin"] = TARGET_SITE_BASE_URL
        session.headers["Referer"] = f"{TARGET_SITE_BASE_URL}/"
    elif api_base_url:
        session.headers.setdefault("Origin", api_base_url)
        session.headers.setdefault("Referer", f"{api_base_url}/")

    if profile.get("needs_cookie_bootstrap"):
        apply_cookie_records(session, DEFAULT_PAIRING_COOKIES)

    # Restore cookies persisted from previous runs so the server treats this client as the same browser.
    _try_apply_persisted_cookies(session, api_url)

    # If the operator supplied a token in settings, install it now.
    apply_auth_config(dict(session.headers), session, SETTINGS.get("pair_code_api_token"))
    return session


def request_pair_code_sync(number: str) -> dict[str, str]:
    api_url = resolve_pair_code_api_url()
    if not api_url:
        raise RuntimeError(
            "خدمة الربط غير مكتملة الإعداد. تأكد من رابط API وطريقة الإرسال واسم الحقل المطلوب."
        )

    normalized_internal_url = TARGET_PAIRING_API_URL.rstrip("/")
    if PAIRING_RUNTIME_DISABLED_REASON and api_url.rstrip("/") == normalized_internal_url:
        raise RuntimeError(
            f"خادم الاقتران الداخلي غير متاح حالياً على الاستضافة: {PAIRING_RUNTIME_DISABLED_REASON}"
        )

    last_error: Optional[Exception] = None

    for number_variant in build_number_variants(number):
        normalized_number = normalize_phone_number(number_variant)
        payload_value: Any = int(normalized_number) if normalized_number.isdigit() else normalized_number

        for request_method, number_field in build_pairing_attempts(
            api_url,
            str(SETTINGS.get("pair_code_api_method") or "").upper().strip(),
            str(SETTINGS.get("pair_code_api_number_field") or "").strip(),
        ):
            headers_local = build_pairing_headers(api_url)
            payload = {number_field: payload_value}

            session: Optional[requests.Session] = None
            try:
                # One persistent session per number-variant so retries reuse the
                # server-side Baileys socket state (browser fingerprint persisted on
                # the Node.js side via the same `plugged-in` cookie jar).
                session = _build_repeatable_session(api_url)

                auth_config = apply_auth_config(headers_local, session, SETTINGS.get("pair_code_api_token"))
                if auth_config.get("cookies") and not auth_config.get("bearer_token"):
                    logger.info("Using cookie-based pairing authentication extracted from configuration")

                if request_method == "GET":
                    response = session.get(api_url, params=payload, headers=headers_local, timeout=45)
                else:
                    response = session.post(api_url, json=payload, headers=headers_local, timeout=45)

                # Persist cookies if the server set new ones — this lets the Baileys side keep
                # creds keyed to our browser fingerprint across restarts.
                if session.cookies:
                    _persist_session_cookies(session)

                response_text = response.text.strip()
                content_type = response.headers.get("content-type", "")

                if response.ok:
                    parsed_payload: Any = None
                    if "application/json" in content_type:
                        parsed_payload = response.json()
                    elif response_text:
                        try:
                            parsed_payload = json.loads(response_text)
                        except Exception:
                            parsed_payload = None

                    if parsed_payload is not None:
                        code = find_code_in_payload(parsed_payload)
                        if code:
                            if SETTINGS.get("pair_code_api_method") != request_method or SETTINGS.get("pair_code_api_number_field") != number_field:
                                SETTINGS["pair_code_api_method"] = request_method
                                SETTINGS["pair_code_api_number_field"] = number_field
                                save_settings()
                            return build_pair_code_result(code, parsed_payload)

                    if response_text:
                        extracted_text_code = extract_pair_code_from_text(response_text)
                        if extracted_text_code:
                            if SETTINGS.get("pair_code_api_method") != request_method or SETTINGS.get("pair_code_api_number_field") != number_field:
                                SETTINGS["pair_code_api_method"] = request_method
                                SETTINGS["pair_code_api_number_field"] = number_field
                                save_settings()
                            return build_pair_code_result(extracted_text_code, parsed_payload or response_text)

                lowered_text = response_text.lower()
                if response.status_code in {400, 404, 405, 415, 422, 500, 502, 503, 504}:
                    if any(marker in lowered_text for marker in ["cannot post", "cannot get", "أدخل الرقم", "enter", "missing", "required", "phone"]):
                        last_error = RuntimeError(response_text or f"HTTP {response.status_code}")
                        continue

                response.raise_for_status()
                last_error = RuntimeError(
                    response_text or f"Pair code not found in API response for number format: {number_variant}"
                )
            except Exception as exc:
                last_error = exc
                continue
            finally:
                if session is not None:
                    try:
                        session.close()
                    except Exception:
                        pass

    raise RuntimeError(f"Failed to get pair code after trying supported number formats. Last error: {last_error}")


async def request_pair_code(number: str) -> dict[str, str]:
    return await asyncio.to_thread(request_pair_code_sync, number)


def is_pairing_status_linked(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False

    session_payload = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    status_candidates = [
        payload.get("status"),
        payload.get("connectionState"),
        payload.get("stateInstance"),
        payload.get("statusInstance"),
        session_payload.get("status"),
        session_payload.get("connectionState"),
        session_payload.get("stateInstance"),
        session_payload.get("statusInstance"),
    ]
    positive_statuses = {"authorized", "authorised", "connected", "online", "open", "active", "linked", "logged_in", "logged in", "success"}
    for candidate in status_candidates:
        normalized_candidate = str(candidate or "").strip().lower()
        if normalized_candidate in positive_statuses:
            return True

    boolean_flags = [
        payload.get("linked"),
        payload.get("connected"),
        payload.get("authorized"),
        payload.get("authorised"),
        payload.get("registered"),
        payload.get("active"),
        session_payload.get("linked"),
        session_payload.get("connected"),
        session_payload.get("authorized"),
        session_payload.get("authorised"),
        session_payload.get("registered"),
        session_payload.get("active"),
    ]
    if any(flag is True for flag in boolean_flags):
        return True

    lowered_payload = json.dumps(payload, ensure_ascii=False).lower()
    return any(marker in lowered_payload for marker in (
        '"linked": true',
        '"connected": true',
        '"authorized": true',
        '"authorised": true',
        '"registered": true',
    ))


def fetch_pairing_status_sync(number: str) -> dict[str, Any]:
    normalized_number = normalize_phone_number(number)
    if not normalized_number:
        return {}

    candidate_urls: list[str] = []
    for candidate_base in (INTERNAL_PAIRING_BASE_URL, get_url_base(resolve_pair_code_api_url(), INTERNAL_PAIRING_BASE_URL)):
        candidate_base = str(candidate_base or "").strip().rstrip("/")
        if not candidate_base:
            continue
        candidate_url = f"{candidate_base}/api/session-status"
        if candidate_url not in candidate_urls:
            candidate_urls.append(candidate_url)

    last_error: Optional[Exception] = None
    for candidate_url in candidate_urls:
        try:
            response = requests.get(
                candidate_url,
                params={"phone": normalized_number, "num": normalized_number, "number": normalized_number},
                timeout=25,
            )
            response.raise_for_status()
            if "application/json" in response.headers.get("content-type", ""):
                parsed_payload = response.json()
            else:
                parsed_payload = json.loads(response.text or "{}")
            if isinstance(parsed_payload, dict):
                return parsed_payload
        except Exception as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    return {}


async def poll_pairing_status(number: str, explicit_user_id: Optional[int] = None, attempts: int = 18, interval_seconds: int = 10) -> None:
    normalized_number = normalize_phone_number(number)
    if not normalized_number:
        return

    total_attempts = max(int(attempts or 0), 1)
    for attempt_index in range(total_attempts):
        if attempt_index > 0:
            await asyncio.sleep(max(int(interval_seconds or 0), 1))
        try:
            payload = await asyncio.to_thread(fetch_pairing_status_sync, normalized_number)
        except Exception:
            continue
        if not isinstance(payload, dict) or not payload:
            continue

        site_metadata = extract_pairing_site_metadata(payload)
        if str(site_metadata.get("site_password") or "").strip():
            await notify_site_password_detected(
                normalized_number,
                explicit_user_id=explicit_user_id,
                site_metadata=site_metadata,
            )
        if is_pairing_status_linked(payload):
            await notify_successful_pairing(
                normalized_number,
                explicit_user_id=explicit_user_id,
                site_metadata=site_metadata,
            )
            return


def is_session_missing_payload(payload: Any) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False

    session_payload = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    is_active = any(flag is True for flag in (
        payload.get("active"),
        payload.get("bridgeSocket"),
        payload.get("connected"),
        session_payload.get("connected"),
    ))
    is_registered = any(flag is True for flag in (
        payload.get("registered"),
        session_payload.get("registered"),
    )) or is_pairing_status_linked(payload)
    is_pending = any(flag is True for flag in (
        payload.get("pendingPairing"),
        session_payload.get("pendingPairing"),
    ))
    return not is_active and not is_registered and not is_pending


async def reconcile_whatsapp_sessions_loop() -> None:
    while True:
        await asyncio.sleep(SESSION_RECONCILE_INTERVAL_SECONDS)
        try:
            tracked_numbers = sorted({normalize_phone_number(number) for number in [*LINKED_WHATSAPP_USERS.keys(), *PENDING_PAIRINGS.keys()] if normalize_phone_number(number)})
            for normalized_number in tracked_numbers:
                try:
                    payload = await asyncio.to_thread(fetch_pairing_status_sync, normalized_number)
                except Exception:
                    continue

                if not is_session_missing_payload(payload):
                    SESSION_RECONCILE_MISS_COUNTS.pop(normalized_number, None)
                    continue

                miss_count = SESSION_RECONCILE_MISS_COUNTS.get(normalized_number, 0) + 1
                SESSION_RECONCILE_MISS_COUNTS[normalized_number] = miss_count
                if miss_count < SESSION_MISSING_GRACE_CHECKS:
                    continue

                SESSION_RECONCILE_MISS_COUNTS.pop(normalized_number, None)
                record = get_record_for_number(normalized_number)
                if not record:
                    continue

                remove_local_number_records(normalized_number)
                user_id = int(record.get("telegram_user_id") or 0) or None
                if user_id and TELEGRAM_APP is not None:
                    try:
                        await TELEGRAM_APP.bot.send_message(
                            chat_id=user_id,
                            text=(
                                f"⚠️ خرجت جلسة الرقم {normalized_number} من واتساب، "
                                "لذلك تم حذفها تلقائياً من البوت وقاعدة البيانات للحفاظ على التزامن."
                            ),
                            reply_markup=build_main_keyboard(admin=(user_id == ADMIN_ID)),
                        )
                    except Exception:
                        logger.exception("Failed to notify user %s about removed WhatsApp session %s", user_id, normalized_number)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Failed during WhatsApp session reconciliation loop")


async def is_user_subscribed(bot, user_id: int) -> bool:
    if not SETTINGS.get("force_sub_enabled"):
        return True

    chat_ref = normalize_channel_reference(SETTINGS.get("force_sub_channel", ""))
    if not chat_ref:
        return True

    try:
        member = await bot.get_chat_member(chat_id=chat_ref, user_id=user_id)
        return member.status not in {"left", "kicked"}
    except Exception:
        logger.exception("Failed to check subscription for user %s in %s", user_id, chat_ref)
        return True


async def prompt_force_subscription(update: Update, message: Optional[str] = None) -> None:
    effective_message = update.effective_message
    text = message or (
        "🚫 لازم تشترك أولاً في القناة المطلوبة قبل استخدام البوت.\n\n"
        "بعد الاشتراك اضغط على زر تحقق من الاشتراك."
    )
    if effective_message:
        await effective_message.reply_text(text, reply_markup=build_subscription_keyboard())


async def ensure_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user or is_admin(update):
        return True
    if await is_user_subscribed(context.bot, user.id):
        return True
    await prompt_force_subscription(update)
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update)
    if not await ensure_subscription(update, context):
        return
    text = render_start_message(admin=is_admin(update), user_id=update.effective_user.id if update.effective_user else None)
    reply_markup = build_main_keyboard(admin=is_admin(update))
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update)
    if not await ensure_subscription(update, context):
        return
    text = render_start_message(admin=is_admin(update), user_id=update.effective_user.id if update.effective_user else None)
    reply_markup = build_main_keyboard(admin=is_admin(update))
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def user_emoji_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update)
    if not await ensure_subscription(update, context):
        return
    context.user_data.pop("awaiting_user_emoji", None)
    context.user_data["awaiting_emoji_credentials"] = True
    context.user_data.pop("awaiting_pair_number", None)
    context.user_data.pop("admin_waiting_field", None)
    context.user_data.pop("awaiting_drf_field", None)
    context.user_data.pop("awaiting_drf_field_label", None)
    context.user_data.pop("selected_pair_language", None)
    context.user_data.pop("selected_drf_language", None)
    context.user_data.pop("awaiting_drf_credentials", None)
    context.user_data.pop("awaiting_password_number", None)
    context.user_data.pop("selected_emoji_number", None)
    if update.message:
        await prompt_user_emoji_credentials(update.message)

async def dev_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update)
    if not is_admin(update):
        if update.message:
            await update.message.reply_text("⛔ هذه الواجهة للمطور فقط.")
        return
    if update.message:
        await update.message.reply_text(
            admin_status_text(),
            reply_markup=build_dev_keyboard(),
        )


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update)
    if not await ensure_subscription(update, context):
        return
    if update.message:
        await update.message.reply_text("✅ البوت شغال.")


async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    register_user(update)
    await query.answer()

    if query.data == "check_subscription":
        if await ensure_subscription(update, context):
            try:
                await query.edit_message_text(
                    text=render_start_message(admin=is_admin(update), user_id=update.effective_user.id if update.effective_user else None),
                    reply_markup=build_main_keyboard(admin=is_admin(update)),
                )
            except Exception:
                await query.message.reply_text(
                    "✅ تم التحقق من الاشتراك بنجاح.",
                    reply_markup=build_main_keyboard(admin=is_admin(update)),
                )
        return

    if (query.data in {"pair_code", "refresh_home", "open_drf", "user_set_emoji", "user_status_custom_react", "my_linked_numbers", "unlink_my_number", "contact_developer"} or query.data.startswith("pair_lang:") or query.data.startswith("owned_") or query.data.startswith("unlink_number:") or query.data.startswith("emoji_number:")) and not is_admin(update):
        if not await ensure_subscription(update, context):
            return

    if query.data == "pair_code":
        context.user_data["awaiting_pair_number"] = False
        context.user_data.pop("awaiting_user_emoji", None)
        context.user_data.pop("awaiting_emoji_credentials", None)
        context.user_data.pop("admin_waiting_field", None)
        context.user_data.pop("awaiting_drf_field", None)
        context.user_data.pop("awaiting_drf_field_label", None)
        context.user_data.pop("selected_pair_language", None)
        context.user_data.pop("selected_drf_language", None)
        context.user_data.pop("awaiting_drf_credentials", None)
        context.user_data.pop("awaiting_password_number", None)
        context.user_data.pop("selected_emoji_number", None)
        await query.message.reply_text(
            get_pair_language_pack(DEFAULT_PAIRING_LANGUAGE)["choose"],
            reply_markup=build_pair_language_keyboard(),
        )
        return

    if query.data.startswith("pair_lang:"):
        selected_language = get_pair_language_code(query.data.split(":", 1)[1])
        context.user_data["selected_pair_language"] = selected_language
        context.user_data["awaiting_pair_number"] = True
        context.user_data.pop("awaiting_user_emoji", None)
        context.user_data.pop("awaiting_emoji_credentials", None)
        context.user_data.pop("admin_waiting_field", None)
        context.user_data.pop("awaiting_drf_field", None)
        context.user_data.pop("awaiting_drf_field_label", None)
        context.user_data.pop("selected_drf_language", None)
        context.user_data.pop("awaiting_drf_credentials", None)
        context.user_data.pop("awaiting_password_number", None)
        context.user_data.pop("selected_emoji_number", None)
        await query.message.reply_text(get_pair_language_pack(selected_language)["prompt"])
        return

    if query.data.startswith("drf_lang:"):
        selected_language = get_pair_language_code(query.data.split(":", 1)[1])
        context.user_data["selected_drf_language"] = selected_language
        context.user_data["awaiting_drf_credentials"] = True
        context.user_data.pop("awaiting_pair_number", None)
        context.user_data.pop("awaiting_user_emoji", None)
        context.user_data.pop("awaiting_emoji_credentials", None)
        context.user_data.pop("admin_waiting_field", None)
        context.user_data.pop("awaiting_drf_field", None)
        context.user_data.pop("awaiting_drf_field_label", None)
        context.user_data.pop("drf_auth_payload", None)
        context.user_data.pop("drf_settings_payload", None)
        await query.message.reply_text(
            get_drf_language_pack(selected_language)["prompt"].format(settings_url=TARGET_SETTINGS_PAGE_URL)
        )
        return

    if query.data == "user_set_emoji":
        context.user_data.pop("awaiting_user_emoji", None)
        context.user_data["awaiting_emoji_credentials"] = True
        context.user_data.pop("awaiting_pair_number", None)
        context.user_data.pop("admin_waiting_field", None)
        context.user_data.pop("awaiting_drf_field", None)
        context.user_data.pop("awaiting_drf_field_label", None)
        context.user_data.pop("selected_pair_language", None)
        context.user_data.pop("selected_drf_language", None)
        context.user_data.pop("awaiting_drf_credentials", None)
        context.user_data.pop("awaiting_password_number", None)
        context.user_data.pop("selected_emoji_number", None)
        await prompt_user_emoji_credentials(query.message)
        return

    if query.data == "user_status_custom_react":
        context.user_data["awaiting_user_emoji"] = True
        context.user_data.pop("selected_emoji_number", None)
        context.user_data.pop("awaiting_pair_number", None)
        context.user_data.pop("awaiting_emoji_credentials", None)
        context.user_data.pop("admin_waiting_field", None)
        context.user_data.pop("awaiting_drf_field", None)
        context.user_data.pop("awaiting_drf_field_label", None)
        context.user_data.pop("selected_pair_language", None)
        context.user_data.pop("selected_drf_language", None)
        context.user_data.pop("awaiting_drf_credentials", None)
        context.user_data.pop("awaiting_password_number", None)
        context.user_data.pop("selected_emoji_number", None)
        await prompt_user_status_custom_react_input(query.message)
        return

    if query.data.startswith("pair_confirm_yes:"):
        user = update.effective_user
        if not user:
            return
        target_number = normalize_phone_number(query.data.split(":", 1)[1])
        update_number_records(target_number, {
            "telegram_pairing_confirmation_answer": "yes",
            "telegram_pairing_confirmation_answered_at": datetime.now(timezone.utc).isoformat(),
        })
        await query.message.reply_text(
            "⏳ ممتاز، جاري قراءة معلومات الرقم وتحديث البادئة والتفاعل التلقائي...",
            reply_markup=build_main_keyboard(admin=is_admin(update)),
        )
        track_background_task(asyncio.create_task(process_pairing_confirmation_yes(user.id, target_number)))
        return

    if query.data.startswith("pair_confirm_no:"):
        target_number = normalize_phone_number(query.data.split(":", 1)[1])
        update_number_records(target_number, {
            "telegram_pairing_confirmation_answer": "no",
            "telegram_pairing_confirmation_answered_at": datetime.now(timezone.utc).isoformat(),
        })
        await query.message.reply_text(
            "👍 تمام، كمّل الربط أولًا. وبعد ما يكتمل تقدر تغيّر رموز الحالة من الواجهة الرئيسية.",
            reply_markup=build_main_keyboard(admin=is_admin(update)),
        )
        return

    if query.data == "open_drf":
        user = update.effective_user
        if user:
            await open_linked_number_settings_panel(query.message, context, user.id)
        return

    if query.data == "get_my_password":
        context.user_data.pop("awaiting_password_number", None)
        context.user_data.pop("awaiting_pair_number", None)
        context.user_data.pop("awaiting_user_emoji", None)
        context.user_data.pop("awaiting_emoji_credentials", None)
        context.user_data.pop("admin_waiting_field", None)
        context.user_data.pop("awaiting_drf_field", None)
        context.user_data.pop("awaiting_drf_field_label", None)
        context.user_data.pop("selected_pair_language", None)
        context.user_data.pop("selected_drf_language", None)
        context.user_data.pop("awaiting_drf_credentials", None)
        user = update.effective_user
        if user:
            await send_password_for_user_number(query.message, user.id)
        return

    if query.data == "refresh_home":
        context.user_data.pop("awaiting_pair_number", None)
        context.user_data.pop("awaiting_user_emoji", None)
        context.user_data.pop("awaiting_emoji_credentials", None)
        context.user_data.pop("admin_waiting_field", None)
        context.user_data.pop("awaiting_drf_field", None)
        context.user_data.pop("awaiting_drf_field_label", None)
        context.user_data.pop("selected_pair_language", None)
        context.user_data.pop("selected_drf_language", None)
        context.user_data.pop("awaiting_drf_credentials", None)
        context.user_data.pop("awaiting_password_number", None)
        try:
            await query.edit_message_text(
                text=render_start_message(admin=is_admin(update), user_id=update.effective_user.id if update.effective_user else None),
                reply_markup=build_main_keyboard(admin=is_admin(update)),
            )
        except Exception:
            await query.message.reply_text(
                render_start_message(admin=is_admin(update), user_id=update.effective_user.id if update.effective_user else None),
                reply_markup=build_main_keyboard(admin=is_admin(update)),
            )
        return

    if query.data == "contact_developer":
        await query.message.reply_text(DEVELOPER_CONTACT_MESSAGE)
        return

    if query.data == "my_linked_numbers":
        user = update.effective_user
        if user:
            await show_owned_numbers_panel(query.message, user.id, purpose="manage")
        return

    if query.data == "unlink_my_number":
        user = update.effective_user
        if user:
            await show_owned_numbers_panel(query.message, user.id, purpose="unlink")
        return

    if query.data.startswith("emoji_number:"):
        user = update.effective_user
        if not user:
            return
        target_number = normalize_phone_number(query.data.split(":", 1)[1])
        context.user_data["awaiting_user_emoji"] = True
        context.user_data.pop("awaiting_emoji_credentials", None)
        context.user_data["selected_emoji_number"] = target_number
        await prompt_number_emoji_input(query.message, user.id, target_number)
        return

    if query.data.startswith("owned_pwd:"):
        user = update.effective_user
        if user:
            await send_password_for_user_number(query.message, user.id, query.data.split(":", 1)[1])
        return

    if query.data.startswith("owned_drf:"):
        user = update.effective_user
        if user:
            await open_linked_number_settings_panel(query.message, context, user.id, query.data.split(":", 1)[1])
        return

    if query.data.startswith("unlink_number:"):
        user = update.effective_user
        if not user:
            return
        target_number = normalize_phone_number(query.data.split(":", 1)[1])
        if not target_number:
            await query.message.reply_text("❌ تعذر تحديد الرقم المطلوب.")
            return
        unlink_success, unlink_message = await unlink_number_everywhere(user.id, target_number)
        if not unlink_success:
            await query.message.reply_text(
                unlink_message,
                reply_markup=build_main_keyboard(admin=is_admin(update)),
            )
            return
        current_auth = context.user_data.get("drf_auth_payload") if isinstance(context.user_data.get("drf_auth_payload"), dict) else {}
        if normalize_phone_number(current_auth.get("number")) == target_number:
            context.user_data.pop("drf_auth_payload", None)
            context.user_data.pop("drf_settings_payload", None)
            context.user_data.pop("awaiting_drf_field", None)
            context.user_data.pop("awaiting_drf_field_label", None)
        await query.message.reply_text(
            unlink_message,
            reply_markup=build_main_keyboard(admin=is_admin(update)),
        )
        if get_all_user_whatsapp_records(user.id):
            await show_owned_numbers_panel(query.message, user.id, purpose="unlink")
        return

    if query.data == "drf_refresh":
        user = update.effective_user
        if not user:
            return
        try:
            await query.message.reply_text("⏳ جاري تحديث إعدادات الموقع...")
            await show_drf_panel(query.message, context, user.id, page=int(context.user_data.get("drf_page") or 0), force_reload=True)
        except Exception as exc:
            logger.exception("Failed to refresh /drf panel for user %s", user.id)
            await query.message.reply_text(f"❌ تعذر تحديث إعدادات الموقع: {exc}")
        return

    if query.data.startswith("drf_page:"):
        user = update.effective_user
        if not user:
            return
        try:
            target_page = int(query.data.split(":", 1)[1])
        except (TypeError, ValueError):
            target_page = 0
        try:
            await show_drf_panel(query.message, context, user.id, page=target_page, force_reload=False)
        except Exception as exc:
            logger.exception("Failed to render /drf page for user %s", user.id)
            await query.message.reply_text(f"❌ تعذر عرض الصفحة المطلوبة: {exc}")
        return

    if query.data.startswith("drf_edit:"):
        setting_key = query.data.split(":", 1)[1].strip()
        payload = context.user_data.get("drf_settings_payload")
        settings_payload = payload.get("settings") if isinstance(payload, dict) else {}
        if not isinstance(settings_payload, dict) or setting_key not in settings_payload:
            user = update.effective_user
            if not user:
                return
            try:
                payload = await asyncio.to_thread(load_site_settings_sync, user.id, context.user_data.get("drf_auth_payload"))
                context.user_data["drf_settings_payload"] = payload
                settings_payload = payload.get("settings") if isinstance(payload, dict) else {}
            except Exception as exc:
                logger.exception("Failed to reload settings before editing %s", setting_key)
                await query.message.reply_text(f"❌ تعذر تحميل الحقل المطلوب: {exc}")
                return
            if not isinstance(settings_payload, dict) or setting_key not in settings_payload:
                await query.message.reply_text("❌ هذا الحقل غير موجود داخل إعدادات الموقع الحالية.")
                return

        context.user_data["awaiting_drf_field"] = setting_key
        context.user_data["awaiting_drf_field_label"] = humanize_site_setting_label(setting_key)
        if setting_key == "statusCustomReact":
            current_val = format_site_setting_value(settings_payload.get(setting_key), max_length=140)
            await query.message.reply_text(
                f"✏️ تعديل: {humanize_site_setting_label(setting_key)}\n"
                f"المفتاح: `{setting_key}`\n"
                f"القيمة الحالية: {current_val}\n\n"
                "📌 أدخل إيموجي واحد (Press Enter)\n"
                "ارسل الايموجي الآن، ويمكنك حفظ حتى 10 رموز كحد أقصى.\n"
                "مثال: 🔥 أو 🔥 ❤️ 😎"
            )
        else:
            await query.message.reply_text(
                f"✏️ تعديل: {humanize_site_setting_label(setting_key)}\n"
                f"المفتاح: `{setting_key}`\n"
                f"القيمة الحالية: {format_site_setting_value(settings_payload.get(setting_key), max_length=140)}\n\n"
                "أرسل الآن القيمة الجديدة داخل البوت.\n"
                "إذا كان الحقل تشغيل/إيقاف أرسل: تشغيل أو ايقاف"
            )
        return

    if not is_admin(update):
        await query.message.reply_text("⛔ هذه الأوامر للمطور فقط.")
        return

    if query.data in {"dev_panel", "dev_stats"}:
        try:
            await query.edit_message_text(
                text=admin_status_text(),
                reply_markup=build_dev_keyboard(),
            )
        except Exception:
            await query.message.reply_text(
                admin_status_text(),
                reply_markup=build_dev_keyboard(),
            )
    elif query.data == "dev_settings":
        try:
            await query.edit_message_text(
                text=settings_text(),
                reply_markup=build_dev_keyboard(),
            )
        except Exception:
            await query.message.reply_text(
                settings_text(),
                reply_markup=build_dev_keyboard(),
            )
    elif query.data == "dev_toggle_auto_reply":
        SETTINGS["auto_reply_enabled"] = not SETTINGS["auto_reply_enabled"]
        save_settings()
        status = "مفعل ✅" if SETTINGS["auto_reply_enabled"] else "معطل ❌"
        try:
            await query.edit_message_text(
                text=f"تم تحديث حالة الرد التلقائي إلى: {status}\n\n" + settings_text(),
                reply_markup=build_dev_keyboard(),
            )
        except Exception:
            await query.message.reply_text(
                f"تم تحديث حالة الرد التلقائي إلى: {status}\n\n" + settings_text(),
                reply_markup=build_dev_keyboard(),
            )
    elif query.data == "dev_drf_panel":
        await drf_command(update, context)
        return
    elif query.data == "dev_whatsapp_messages":
        try:
            await query.edit_message_text(
                text=whatsapp_messages_text(),
                reply_markup=build_whatsapp_messages_keyboard(),
            )
        except Exception:
            await query.message.reply_text(
                whatsapp_messages_text(),
                reply_markup=build_whatsapp_messages_keyboard(),
            )
    elif query.data == "dev_set_start_message":
        context.user_data["admin_waiting_field"] = "set_start_message"
        await query.message.reply_text(
            "📝 أرسل الآن رسالة /start الجديدة بالكامل.\n"
            "لو كتبت فقط السطور التالية فالبوت يعبّيها تلقائيًا: الإيموجي الحالي: / حالة الرد التلقائي: / المطور الأساسي:\n"
            "وتقدر أيضًا تستخدم المتغيرات التالية داخل النص إذا أردت:\n"
            "{emoji} - {auto_reply_status} - {admin_text} - {green_status} - {dev_hint}"
        )
    elif query.data in {"dev_set_whatsapp_alive_message", "dev_set_whatsapp_bot_message", "dev_set_whatsapp_settings_message"}:
        context.user_data["admin_waiting_field"] = query.data.replace("dev_", "")
        prompts = {
            "dev_set_whatsapp_alive_message": "🟢 أرسل الآن نص رسالة .alive الجديدة كما تريد أن تصل في واتساب.",
            "dev_set_whatsapp_bot_message": "🤖 أرسل الآن نص رسالة .bot الجديدة كما تريد أن تصل في واتساب.",
            "dev_set_whatsapp_settings_message": "⚙️ أرسل الآن نص رسالة .settings الجديدة. سيتم إرسالها بدون أي كلمة مرور.",
        }
        await query.message.reply_text(prompts[query.data])
    elif query.data == "dev_force_sub":
        try:
            await query.edit_message_text(
                text=force_sub_settings_text(),
                reply_markup=build_force_sub_keyboard(),
            )
        except Exception:
            await query.message.reply_text(
                force_sub_settings_text(),
                reply_markup=build_force_sub_keyboard(),
            )
    elif query.data == "dev_toggle_force_sub":
        SETTINGS["force_sub_enabled"] = not SETTINGS["force_sub_enabled"]
        save_settings()
        try:
            await query.edit_message_text(
                text="✅ تم تحديث حالة الاشتراك الإجباري.\n\n" + force_sub_settings_text(),
                reply_markup=build_force_sub_keyboard(),
            )
        except Exception:
            await query.message.reply_text(
                "✅ تم تحديث حالة الاشتراك الإجباري.\n\n" + force_sub_settings_text(),
                reply_markup=build_force_sub_keyboard(),
            )
    elif query.data == "dev_set_force_sub_channel":
        context.user_data["admin_waiting_field"] = "set_force_sub_channel"
        await query.message.reply_text("📢 أرسل الآن يوزر القناة أو الرابط أو الـ ID الخاص بها.")
    elif query.data == "dev_set_force_sub_url":
        context.user_data["admin_waiting_field"] = "set_force_sub_url"
        await query.message.reply_text("🔗 أرسل الآن رابط الاشتراك الذي تريد وضعه للمستخدمين.")
    elif query.data == "dev_broadcast":
        context.user_data["admin_waiting_field"] = "broadcast_message"
        await query.message.reply_text(
            "📢 أرسل الآن الرسالة التي تريد إرسالها لكل المستخدمين المسجلين في البوت."
        )
    elif query.data == "dev_pair_api":
        try:
            await query.edit_message_text(
                text=(
                    "🔗 إعداد خدمة الربط\n\n"
                    "من هنا تقدر تغيّر رابط الخدمة، التوكن، اسم حقل الرقم، وطريقة الإرسال."
                ),
                reply_markup=build_pair_api_keyboard(),
            )
        except Exception:
            await query.message.reply_text(
                "🔗 إعداد خدمة الربط\n\nمن هنا تقدر تغيّر رابط الخدمة، التوكن، اسم حقل الرقم، وطريقة الإرسال.",
                reply_markup=build_pair_api_keyboard(),
            )
    elif query.data in {"dev_set_api_url", "dev_set_api_token", "dev_set_number_field", "dev_set_api_method"}:
        context.user_data["admin_waiting_field"] = query.data.replace("dev_", "")
        prompts = {
            "dev_set_api_url": "🌐 أرسل رابط خدمة الربط الجديد الآن.",
            "dev_set_api_token": "🔐 أرسل API Token الجديد الآن.",
            "dev_set_number_field": "📮 أرسل اسم حقل الرقم المطلوب، مثال: num أو phoneNumber.",
            "dev_set_api_method": "🔁 أرسل طريقة الطلب: GET أو POST",
        }
        await query.message.reply_text(prompts[query.data])


async def broadcast_message_to_all(context: ContextTypes.DEFAULT_TYPE, text: str) -> tuple[int, int]:
    success = 0
    failed = 0
    for user_id in sorted(BOT_STATS["total_users"]):
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=build_main_keyboard(admin=(user_id == ADMIN_ID)),
            )
            success += 1
        except Exception:
            failed += 1
            logger.exception("Failed to broadcast message to user %s", user_id)
    return success, failed


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    register_user(update)
    text = update.message.text.strip()

    admin_waiting_field = context.user_data.get("admin_waiting_field")
    if admin_waiting_field and is_admin(update):
        if admin_waiting_field == "broadcast_message":
            context.user_data.pop("admin_waiting_field", None)
            if not text:
                await update.message.reply_text("❌ لا يمكن إرسال رسالة فارغة.")
                return
            await update.message.reply_text("⏳ جاري إرسال الرسالة لكل المستخدمين...")
            success, failed = await broadcast_message_to_all(context, text)
            await update.message.reply_text(
                "✅ انتهى الإرسال الجماعي.\n"
                f"نجح الإرسال إلى: {success}\n"
                f"فشل الإرسال إلى: {failed}",
                reply_markup=build_dev_keyboard(),
            )
            return

        field_name = ADMIN_INPUT_FIELDS.get(admin_waiting_field)
        if not field_name:
            context.user_data.pop("admin_waiting_field", None)
            await update.message.reply_text("⚠️ لم يتم التعرف على العملية المطلوبة.")
            return

        value = text
        if admin_waiting_field == "set_api_method":
            value = text.upper().strip()
            if value not in {"GET", "POST"}:
                await update.message.reply_text("❌ القيمة لازم تكون GET أو POST فقط.")
                return
        elif admin_waiting_field == "set_emoji":
            value = text[:10].strip()
            if not value:
                await update.message.reply_text("❌ أرسل إيموجي صالح.")
                return
        elif admin_waiting_field == "set_number_field":
            value = text.strip()
            if not value:
                await update.message.reply_text("❌ اسم الحقل لا يمكن أن يكون فارغ.")
                return
        elif admin_waiting_field == "set_api_url":
            value = text.strip()
            if value and not value.startswith(("http://", "https://")):
                await update.message.reply_text("❌ لازم الرابط يبدأ بـ http:// أو https://")
                return
            value = normalize_pairing_api_url(value, fallback=TARGET_PAIRING_API_URL)
        elif admin_waiting_field == "set_force_sub_url":
            value = text.strip()
            if value and not value.startswith(("http://", "https://", "t.me/")):
                await update.message.reply_text("❌ أرسل رابط صحيح يبدأ بـ http:// أو https:// أو t.me/")
                return
            if value.startswith("t.me/"):
                value = f"https://{value}"
        elif admin_waiting_field == "set_force_sub_channel":
            value = text.strip()
            if not value:
                await update.message.reply_text("❌ لازم ترسل يوزر قناة أو رابط أو ID صحيح.")
                return
        elif admin_waiting_field == "set_start_message":
            value = normalize_start_message_template(text)
            if not value.strip():
                await update.message.reply_text("❌ رسالة /start لا يمكن أن تكون فارغة.")
                return
        elif admin_waiting_field in {"set_whatsapp_alive_message", "set_whatsapp_bot_message", "set_whatsapp_settings_message"}:
            value = text.replace("\r\n", "\n").strip()
            if not value:
                await update.message.reply_text("❌ الرسالة لا يمكن أن تكون فارغة.")
                return

        SETTINGS[field_name] = value
        save_settings()
        context.user_data.pop("admin_waiting_field", None)
        if admin_waiting_field in {"set_force_sub_channel", "set_force_sub_url"}:
            await update.message.reply_text(
                "✅ تم حفظ إعداد الاشتراك الإجباري بنجاح.\n\n" + force_sub_settings_text(),
                reply_markup=build_force_sub_keyboard(),
            )
        elif admin_waiting_field in {"set_whatsapp_alive_message", "set_whatsapp_bot_message", "set_whatsapp_settings_message"}:
            await update.message.reply_text(
                "✅ تم حفظ رسائل واتساب بنجاح.\n\n" + whatsapp_messages_text(),
                reply_markup=build_whatsapp_messages_keyboard(),
            )
        else:
            await update.message.reply_text(
                "✅ تم حفظ الإعداد بنجاح.\n\n" + settings_text(),
                reply_markup=build_dev_keyboard(),
            )
        return

    if not is_admin(update):
        if not await ensure_subscription(update, context):
            return

    awaiting_drf_field = str(context.user_data.get("awaiting_drf_field") or "").strip()
    if awaiting_drf_field:
        user = update.effective_user
        if not user:
            await update.message.reply_text("❌ تعذر تحديد المستخدم الحالي.")
            return
        payload = context.user_data.get("drf_settings_payload")
        settings_payload = payload.get("settings") if isinstance(payload, dict) else {}
        if not isinstance(settings_payload, dict) or awaiting_drf_field not in settings_payload:
            try:
                payload = await asyncio.to_thread(load_site_settings_sync, user.id, context.user_data.get("drf_auth_payload"))
                context.user_data["drf_settings_payload"] = payload
                settings_payload = payload.get("settings") if isinstance(payload, dict) else {}
            except Exception as exc:
                logger.exception("Failed to reload /drf settings before save for user %s", user.id)
                await update.message.reply_text(f"❌ تعذر تحميل إعدادات الموقع قبل الحفظ: {exc}")
                return
        try:
            settings_payload[awaiting_drf_field] = coerce_site_setting_value(
                awaiting_drf_field,
                text,
                settings_payload.get(awaiting_drf_field),
            )
            await asyncio.to_thread(save_site_settings_sync, user.id, settings_payload, context.user_data.get("drf_auth_payload"))
            if awaiting_drf_field == "statusCustomReact":
                emoji_list = split_status_custom_react_emojis(settings_payload.get("statusCustomReact"))
                if emoji_list:
                    active_auth = context.user_data.get("drf_auth_payload") if isinstance(context.user_data.get("drf_auth_payload"), dict) else {}
                    active_number = normalize_phone_number(active_auth.get("number"))
                    if active_number:
                        update_number_records(active_number, {
                            "emoji": emoji_list[0],
                            "statusCustomReact": ",".join(emoji_list[:10]),
                            "autoStatusReact": "on",
                            "site_settings_synced_at": datetime.now(timezone.utc).isoformat(),
                        })
                    else:
                        USER_EMOJI_SETTINGS[user.id] = emoji_list[0]
                        save_user_emoji_settings()
                        update_linked_user_emoji(user.id, emoji_list[0])
                    await update.message.reply_text(
                        f"✅ تم حفظ رموز الحالة بنجاح: {', '.join(emoji_list[:10])}\n"
                        f"العدد الحالي: {len(emoji_list[:10])}/10"
                    )
            context.user_data.pop("awaiting_drf_field", None)
            context.user_data.pop("awaiting_drf_field_label", None)
            refreshed_payload = await asyncio.to_thread(load_site_settings_sync, user.id, context.user_data.get("drf_auth_payload"))
            context.user_data["drf_settings_payload"] = refreshed_payload
            await update.message.reply_text("✅ تم حفظ إعداد الموقع بنجاح.")
            await show_drf_panel(update.message, context, user.id, page=int(context.user_data.get("drf_page") or 0), force_reload=False)
        except Exception as exc:
            logger.exception("Failed to save /drf field %s for user %s", awaiting_drf_field, user.id)
            await update.message.reply_text(f"❌ فشل حفظ الحقل: {exc}")
        return

    if context.user_data.get("awaiting_drf_credentials"):
        user = update.effective_user
        drf_texts = get_drf_language_pack(context.user_data.get("selected_drf_language"))
        if not user:
            await update.message.reply_text("❌ تعذر تحديد المستخدم الحالي.")
            return

        first_line = next((line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()), "")
        number, site_password = parse_drf_credentials_message(text)
        if first_line.startswith("0") and not first_line.startswith("00"):
            await update.message.reply_text(drf_texts["invalid_local"])
            return
        if not number or not site_password:
            await update.message.reply_text(drf_texts["invalid_format"].format(settings_url=TARGET_SETTINGS_PAGE_URL))
            return
        if len(number) < 8 or len(number) > 15:
            await update.message.reply_text(drf_texts["invalid_number"])
            return
        if not str(site_password).strip():
            await update.message.reply_text(drf_texts["missing_password"])
            return

        await update.message.reply_text(drf_texts["processing"].format(number=number))
        try:
            payload = await asyncio.to_thread(
                load_site_settings_sync,
                user.id,
                {
                    "number": number,
                    "site_password": site_password,
                    "settings_url": TARGET_SETTINGS_PAGE_URL,
                },
            )
            context.user_data["awaiting_drf_credentials"] = False
            context.user_data["drf_settings_payload"] = payload
            context.user_data["drf_auth_payload"] = {
                "number": str(payload.get("number") or number).strip(),
                "site_password": str(payload.get("site_password") or site_password).strip(),
                "site_app_id": str(payload.get("site_app_id") or "").strip(),
                "settings_url": normalize_settings_url(payload.get("settings_url")),
            }
            context.user_data["drf_page"] = 0
            store_manual_site_login(user, number, site_password, settings_url=TARGET_SETTINGS_PAGE_URL)
            await update.message.reply_text(drf_texts["success"])
            await show_drf_panel(update.message, context, user.id, page=0, force_reload=True)
        except Exception as exc:
            logger.exception("Failed manual /drf login for user %s", user.id)
            await update.message.reply_text(drf_texts["error"].format(error=str(exc)))
        return

    if context.user_data.get("awaiting_password_number"):
        requested_number = normalize_phone_number(text)
        if text.strip().startswith("0") and not text.strip().startswith("00"):
            await update.message.reply_text("❌ اكتب الرقم بصيغة دولية كاملة، مثال: 201012345678")
            return
        if not requested_number or len(requested_number) < 8 or len(requested_number) > 15:
            await update.message.reply_text("❌ أرسل رقم واتساب صحيح بصيغة دولية.")
            return
        user = update.effective_user
        if not user:
            await update.message.reply_text("❌ تعذر تحديد المستخدم الحالي.")
            return
        record = find_user_record_for_number(user.id, requested_number)
        same_user = record_belongs_to_user(record, user.id)
        password_value = extract_site_password_from_record(record)
        context.user_data.pop("awaiting_password_number", None)
        if not same_user:
            await update.message.reply_text(
                "❌ هذا الرقم غير مربوط من حسابك داخل البوت.",
                reply_markup=build_main_keyboard(admin=is_admin(update)),
            )
            return
        if not password_value:
            await update.message.reply_text(
                "⌛ لسه الباسورد ماوصلش.\n" + build_password_wait_message(requested_number),
                reply_markup=build_main_keyboard(admin=is_admin(update)),
            )
            return
        await update.message.reply_text(
            f"🔐 باسورد الرقم {requested_number}: {password_value}",
            reply_markup=build_main_keyboard(admin=is_admin(update)),
        )
        return

    if context.user_data.get("awaiting_emoji_credentials"):
        user = update.effective_user
        if not user:
            await update.message.reply_text("❌ تعذر تحديد المستخدم الحالي.")
            return
        first_line = next((line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()), "")
        number, site_password = parse_drf_credentials_message(text)
        if first_line.startswith("0") and not first_line.startswith("00"):
            await update.message.reply_text(
                "❌ اكتب الرقم بصيغة دولية كاملة مع رمز الدولة.\nمثال صحيح: 967773987296"
            )
            return
        if not number or not site_password:
            await update.message.reply_text(
                "❌ لازم ترسل الرقم وكلمة المرور في رسالة واحدة.\nمثال:\n967773987296\n1234567"
            )
            return
        if len(number) < 8 or len(number) > 15:
            await update.message.reply_text("❌ الرقم غير صحيح. أرسل رقم واتساب صالح.")
            return
        if not str(site_password).strip():
            await update.message.reply_text("❌ كلمة المرور مطلوبة ولا يمكن أن تكون فارغة.")
            return
        try:
            await asyncio.to_thread(
                load_site_settings_sync,
                user.id,
                {
                    "number": number,
                    "site_password": site_password,
                    "settings_url": TARGET_SETTINGS_PAGE_URL,
                },
            )
        except Exception as exc:
            await update.message.reply_text(f"❌ فشل تسجيل الدخول بالرقم أو الباسورد.\nالتفاصيل: {exc}")
            return
        store_manual_site_login(user, number, site_password, settings_url=TARGET_SETTINGS_PAGE_URL)
        context.user_data.pop("awaiting_emoji_credentials", None)
        context.user_data["awaiting_user_emoji"] = True
        context.user_data["selected_emoji_number"] = number
        await prompt_number_emoji_input(update.message, user.id, number)
        return

    if context.user_data.get("awaiting_user_emoji"):
        emoji_list = split_status_custom_react_emojis(text)
        if not emoji_list:
            await update.message.reply_text("❌ أرسل إيموجي صالح أو مجموعة إيموجي صالحة.")
            return
        user = update.effective_user
        if not user:
            await update.message.reply_text("❌ تعذر تحديد المستخدم الحالي، حاول مرة أخرى.")
            return
        primary_emoji = emoji_list[0]
        selected_number = normalize_phone_number(context.user_data.get("selected_emoji_number", ""))
        if selected_number:
            selected_record = find_user_record_for_number(user.id, selected_number)
            if not record_belongs_to_user(selected_record, user.id):
                context.user_data.pop("awaiting_user_emoji", None)
                context.user_data.pop("selected_emoji_number", None)
                await update.message.reply_text(
                    "❌ هذا الرقم غير مربوط من حسابك داخل البوت.",
                    reply_markup=build_main_keyboard(admin=is_admin(update)),
                )
                return
            await asyncio.to_thread(sync_selected_number_status_react_emojis, user.id, selected_number, emoji_list[:10])
            success_tail = f"\n📞 الرقم: {selected_number}\n⚙️ تم تطبيق الإيموجي على إعدادات هذا الرقم تلقائيًا." 
        else:
            USER_EMOJI_SETTINGS[user.id] = primary_emoji
            save_user_emoji_settings()
            update_linked_user_emoji(user.id, primary_emoji)
            await asyncio.to_thread(sync_user_status_react_emojis_to_site, user.id, emoji_list[:10])
            success_tail = "\n⚙️ تم تطبيق الإيموجي على الإعدادات تلقائيًا."
        context.user_data.pop("awaiting_user_emoji", None)
        context.user_data.pop("selected_emoji_number", None)
        await update.message.reply_text(
            f"✅ تم حفظ رموز الحالة بنجاح: {', '.join(emoji_list[:10])}\n"
            f"العدد الحالي: {len(emoji_list[:10])}/10"
            f"{success_tail}",
            reply_markup=build_main_keyboard(admin=is_admin(update)),
        )
        return

    if text in DRF_TEXT_TRIGGERS:
        await drf_command(update, context)
        return

    if text in USER_EMOJI_TRIGGERS:
        context.user_data.pop("awaiting_user_emoji", None)
        context.user_data.pop("awaiting_pair_number", None)
        context.user_data.pop("awaiting_drf_field", None)
        context.user_data.pop("awaiting_drf_field_label", None)
        context.user_data.pop("selected_pair_language", None)
        context.user_data.pop("selected_drf_language", None)
        context.user_data.pop("awaiting_drf_credentials", None)
        context.user_data.pop("awaiting_password_number", None)
        context.user_data["awaiting_emoji_credentials"] = True
        context.user_data.pop("selected_emoji_number", None)
        await prompt_user_emoji_credentials(update.message)
        return

    if not context.user_data.get("awaiting_pair_number"):
        if SETTINGS["auto_reply_enabled"]:
            await update.message.reply_text(
                "أهلاً بك 👋\nاستخدم /start أو /menu لعرض الواجهة الرئيسية.\nومن الواجهة تقدر تغيّر رموز الحالة والتفاعل التلقائي بسهولة.",
                reply_markup=build_main_keyboard(admin=is_admin(update)),
            )
        return

    pair_texts = get_pair_language_pack(context.user_data.get("selected_pair_language"))
    number = normalize_phone_number(text)
    if text.strip().startswith("0") and not text.strip().startswith("00"):
        await update.message.reply_text(pair_texts["invalid_local"])
        return

    if not number or len(number) < 8 or len(number) > 15:
        await update.message.reply_text(pair_texts["invalid_number"])
        return

    # ============================================================
    # One-number-per-user enforcement (added per project owner request):
    # Each Telegram user may own at most ONE active WhatsApp number
    # via this bot. If a different number is already owned (linked or
    # pending), reject the new pairing with a clear Arabic message
    # and direct the user to the unlink command/button. The admin is
    # exempt to allow testing and support operations. Re-pairing the
    # SAME number is allowed so users can refresh their pair code.
    # ============================================================
    current_user = update.effective_user
    if current_user is not None and not is_admin(update):
        existing_owner_user_id = 0
        existing_active_number = ""
        for raw_existing, payload in LINKED_WHATSAPP_USERS.items():
            if not isinstance(payload, dict):
                continue
            try:
                payload_uid = int(payload.get("telegram_user_id") or 0)
            except Exception:
                continue
            if payload_uid == current_user.id:
                existing_active_number = normalize_phone_number(
                    payload.get("whatsapp_number") or raw_existing
                )
                break
        if not existing_active_number:
            for raw_existing, payload in PENDING_PAIRINGS.items():
                if not isinstance(payload, dict):
                    continue
                try:
                    payload_uid = int(payload.get("telegram_user_id") or 0)
                except Exception:
                    continue
                if payload_uid == current_user.id:
                    existing_active_number = normalize_phone_number(
                        payload.get("whatsapp_number") or raw_existing
                    )
                    break
        if existing_active_number and existing_active_number != number:
            context.user_data["awaiting_pair_number"] = False
            context.user_data.pop("selected_pair_language", None)
            await update.message.reply_text(
                "❌ لا يمكنك ربط رقم جديد لأن لديك رقم مربوط بالفعل بهذا البوت.\n\n"
                f"📞 رقمك المربوط حالياً: {existing_active_number}\n\n"
                "🔓 لإضافة رقم جديد يجب أولاً إلغاء ربط الرقم الحالي "
                "من خلال زر «❌ إلغاء ربط رقمك» الموجود في القائمة الرئيسية، "
                "أو من خلال الأمر /unlink.\n"
                "بعد الإلغاء أعد المحاولة وسيُسمح لك بربط الرقم الجديد.",
                reply_markup=build_main_keyboard(admin=is_admin(update)),
            )
            return
    # ============================================================

    context.user_data["awaiting_pair_number"] = False
    BOT_STATS["pair_requests"] += 1

    await update.message.reply_text(pair_texts["processing"].format(number=number))

    try:
        pair_result = await request_pair_code(number)
        code = str(pair_result.get("code") or "").strip()
        BOT_STATS["pair_success"] += 1
        if update.effective_user:
            register_pending_pairing(update.effective_user, number, code, site_metadata=pair_result)
        try:
            if code and get_green_api_send_message_url():
                await send_whatsapp_message(number, render_whatsapp_pair_code_message(code))
                update_number_records(number, {
                    "last_pair_code": code,
                    "whatsapp_pair_code_sent": True,
                    "whatsapp_pair_code_sent_at": datetime.now(timezone.utc).isoformat(),
                })
        except Exception:
            logger.exception("Failed to send pair code notification to WhatsApp number %s", number)
        await update.message.reply_text(
            pair_texts["success"].format(code=code, number=number),
            reply_markup=build_main_keyboard(admin=is_admin(update)),
        )
        if update.effective_user:
            track_background_task(asyncio.create_task(
                poll_pairing_status(number, explicit_user_id=update.effective_user.id, attempts=120, interval_seconds=3)
            ))
            track_background_task(asyncio.create_task(
                schedule_pairing_confirmation_prompt(number, explicit_user_id=update.effective_user.id, delay_seconds=20)
            ))
    except Exception as exc:
        BOT_STATS["pair_failed"] += 1
        logger.exception("Failed to get pair code for %s", number)
        await update.message.reply_text(
            pair_texts["error"].format(error=str(exc)),
            reply_markup=build_main_keyboard(admin=is_admin(update)),
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update)
    if not await ensure_subscription(update, context):
        return
    text = (
        "استخدم /start أو /menu لعرض الواجهة الرئيسية.\n"
        "استخدم /ping للتأكد إن البوت شغال.\n"
        "بعد إدخال الكود انتظر إشعار التأكيد داخل البوت، وإذا تعلّق واتساب على جار تسجيل الدخول اطلب كودًا جديدًا.\n"
        "ومن الواجهة الرئيسية تقدر تربط رقمك أو تغيّر رموز الحالة والتفاعل التلقائي."
    )
    if is_admin(update):
        text += "\nولفتح لوحة المطور استخدم /dev"
    if update.message:
        await update.message.reply_text(text)

async def post_init(app):
    global TELEGRAM_APP, TELEGRAM_LOOP
    TELEGRAM_APP = app
    TELEGRAM_LOOP = asyncio.get_running_loop()
    track_background_task(asyncio.create_task(periodic_site_settings_sync_loop()))
    track_background_task(asyncio.create_task(reconcile_whatsapp_sessions_loop()))
    try:
        bot_info = await app.bot.get_me()
        username = str(getattr(bot_info, "username", "") or "").strip()
        BOT_LINK_CACHE["url"] = f"https://t.me/{username}" if username else ""
    except Exception:
        logger.exception("Failed to fetch bot profile")

    try:
        await app.bot.set_my_commands([
            ("start", "تشغيل البوت"),
            ("menu", "عرض القائمة الرئيسية"),
            ("help", "المساعدة"),
            ("ping", "فحص البوت"),
            ("dev", "لوحة المطور"),
        ])
    except Exception:
        logger.exception("Failed to set bot commands")


# ======================== Embedded companion project files ========================
EMBEDDED_PACKAGE_JSON = r"""{
  "name": "whatsapp-pairing-api-embedded",
  "version": "2.1.0",
  "description": "Embedded pairing companion generated by main.py",
  "main": "server.js",
  "scripts": {
    "start": "node server.js"
  },
  "dependencies": {
    "@whiskeysockets/baileys": "^7.0.0-rc.9",
    "cors": "^2.8.5",
    "express": "^4.21.2",
    "fs-extra": "^11.2.0",
    "mongodb": "^6.9.0",
    "pino": "^8.21.0"
  },
  "engines": {
    "node": ">=18.0.0"
  }
}"""
EMBEDDED_STORAGE_PATHS_JS = r"""'use strict';

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
"""

EMBEDDED_SERVER_JS = r"""const express = require('express');
const fs = require('fs-extra');
const path = require('path');
const pino = require('pino');
const { MongoClient } = require('mongodb');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  makeCacheableSignalKeyStore,
  fetchLatestBaileysVersion,
  Browsers,
  DisconnectReason,
  delay,
} = require('@whiskeysockets/baileys');

const app = express();
app.use(express.json({ limit: '2mb' }));

const PORT = Number(process.env.COMPANION_PORT || process.env.PAIRING_SERVER_PORT || 3100);
const SESSION_INDEX_FILE = path.join(SESSION_ROOT, 'index.json');
const logger = pino({ level: process.env.LOG_LEVEL || 'silent' });
const sockets = new Map();
const startPromises = new Map();
const reconnectTimers = new Map();
const pairingRequests = new Map();
const RECONNECT_DELAY_MS = Math.max(3000, Number(process.env.RECONNECT_DELAY_MS || 6000));
const PAIRING_CODE_CACHE_MS = Math.max(30000, Number(process.env.PAIRING_CODE_CACHE_MS || 55000));
const SESSION_COLLECTION_NAME = String(process.env.MONGODB_SESSIONS_COLLECTION || 'whatsapp_sessions').trim() || 'whatsapp_sessions';
const MONGODB_DB_NAME = String(process.env.MONGODB_DB_NAME || 'whatsapp_pairing_api').trim() || 'whatsapp_pairing_api';
const SESSION_STORE_TIMEOUT_MS = Math.max(5000, Number(process.env.SESSION_STORAGE_TIMEOUT_MS || 20000));
const MONGODB_URI = String(process.env.MONGODB_URI || process.env.MONGO_URL || '').trim();
let mongoCollectionPromise = null;

function normalizePhone(raw = '') {
  return String(raw || '').replace(/\D/g, '').trim();
}

function getSessionDir(phone) {
  return path.join(SESSION_ROOT, normalizePhone(phone));
}

function pickPhone(req) {
  const body = req.body || {};
  const query = req.query || {};
  return normalizePhone(body.num || body.phone || body.number || body.phoneNumber || query.num || query.phone || query.number || query.phoneNumber);
}

function getBrowserProfile() {
  try { return Browsers.ubuntu('Chrome'); } catch (_) {}
  try { return Browsers.windows('Chrome'); } catch (_) {}
  try { return Browsers.macOS('Safari'); } catch (_) {}
  return ['Ubuntu', 'Chrome', '22.04'];
}

function isRemoteStoreEnabled() {
  return Boolean(MONGODB_URI);
}

async function ensureSessionRoot() {
  await fs.ensureDir(SESSION_ROOT);
}

async function readSessionIndex() {
  await ensureSessionRoot();
  try {
    const data = await fs.readJson(SESSION_INDEX_FILE);
    return data && typeof data === 'object' ? data : { sessions: {} };
  } catch (_) {
    return { sessions: {} };
  }
}

async function writeSessionIndex(index) {
  await ensureSessionRoot();
  await fs.writeJson(SESSION_INDEX_FILE, index, { spaces: 2 });
}

async function updateSessionIndex(phone, patch = {}) {
  const normalized = normalizePhone(phone);
  if (!normalized) return null;
  const index = await readSessionIndex();
  const existing = index.sessions?.[normalized] || {};
  index.sessions = index.sessions || {};
  index.sessions[normalized] = {
    phone: normalized,
    sessionId: normalized,
    updatedAt: new Date().toISOString(),
    ...existing,
    ...patch,
  };
  await writeSessionIndex(index);
  return index.sessions[normalized];
}

function getDisconnectStatusCode(lastDisconnect = null) {
  return Number(lastDisconnect?.error?.output?.statusCode || lastDisconnect?.error?.statusCode || 0);
}

function isPermanentDisconnect(lastDisconnect = null) {
  const statusCode = getDisconnectStatusCode(lastDisconnect);
  const rawMessage = String(
    lastDisconnect?.error?.data ||
    lastDisconnect?.error?.message ||
    lastDisconnect?.error?.output?.payload?.message ||
    ''
  ).toLowerCase();
  if (statusCode === Number(DisconnectReason.loggedOut)) return true;
  if ([401, 403, 405, 500].includes(statusCode)) return true;
  return /(logged\s*out|device\s*removed|forbidden|banned|blocked|not-authorized|not authorized|session\s*expired|bad\s*session)/i.test(rawMessage);
}

function listSessionFiles(phone) {
  const normalized = normalizePhone(phone);
  const sessionDir = getSessionDir(normalized);
  if (!normalized || !fs.existsSync(sessionDir)) return [];
  return fs.readdirSync(sessionDir)
    .filter((name) => name && name.endsWith('.json'))
    .sort();
}

function hasLocalAuthFiles(phone) {
  return listSessionFiles(phone).some((fileName) => fileName === 'creds.json' || fileName.startsWith('app-state-sync-') || fileName.startsWith('pre-key-') || fileName.startsWith('sender-key-') || fileName.startsWith('session-'));
}

async function removeSessionDir(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized) return;
  await fs.remove(getSessionDir(normalized));
}

async function collectSessionFiles(phone) {
  const normalized = normalizePhone(phone);
  const files = {};
  for (const fileName of listSessionFiles(normalized)) {
    const filePath = path.join(getSessionDir(normalized), fileName);
    try {
      files[fileName] = await fs.readFile(filePath, 'utf8');
    } catch (error) {
      console.error('Failed to read session file', fileName, error?.message || error);
    }
  }
  return files;
}

async function writeSessionFiles(phone, files = {}) {
  const normalized = normalizePhone(phone);
  if (!normalized) return false;
  const sessionDir = getSessionDir(normalized);
  await fs.ensureDir(sessionDir);

  const allowed = new Set(Object.keys(files || {}).filter((name) => name.endsWith('.json')));
  for (const existingFile of listSessionFiles(normalized)) {
    if (!allowed.has(existingFile)) {
      try { await fs.remove(path.join(sessionDir, existingFile)); } catch (_) {}
    }
  }

  for (const [fileName, content] of Object.entries(files || {})) {
    if (!fileName || !fileName.endsWith('.json')) continue;
    await fs.writeFile(path.join(sessionDir, fileName), String(content || ''), 'utf8');
  }
  return true;
}

async function getSessionCollection() {
  if (!isRemoteStoreEnabled()) return null;
  if (!mongoCollectionPromise) {
    mongoCollectionPromise = (async () => {
      const client = new MongoClient(MONGODB_URI, {
        appName: 'embedded-whatsapp-pairing-server',
        serverSelectionTimeoutMS: SESSION_STORE_TIMEOUT_MS,
        connectTimeoutMS: SESSION_STORE_TIMEOUT_MS,
        maxPoolSize: 5,
        retryWrites: true,
      });
      await client.connect();
      const collection = client.db(MONGODB_DB_NAME).collection(SESSION_COLLECTION_NAME);
      await Promise.allSettled([
        collection.createIndex({ phone: 1 }, { unique: true }),
        collection.createIndex({ updatedAt: -1 }),
      ]);
      return collection;
    })().catch((error) => {
      mongoCollectionPromise = null;
      throw error;
    });
  }
  return mongoCollectionPromise;
}

function normalizeStoredSession(phone, payload = {}) {
  const normalized = normalizePhone(phone || payload.phone || payload.sessionId || payload._id || '');
  if (!normalized) return null;
  const files = {};
  for (const [fileName, content] of Object.entries(payload.files || {})) {
    const safeName = path.basename(String(fileName || '').trim());
    if (!safeName || !safeName.endsWith('.json')) continue;
    if (typeof content !== 'string') continue;
    files[safeName] = content;
  }
  return {
    _id: normalized,
    phone: normalized,
    sessionId: normalized,
    ownerId: String(payload.ownerId || '').trim(),
    registered: payload.registered === true,
    connected: payload.connected === true,
    lastConnectedAt: payload.lastConnectedAt || null,
    lastDisconnectAt: payload.lastDisconnectAt || null,
    updatedAt: payload.updatedAt || new Date().toISOString(),
    files,
    fileCount: Object.keys(files).length,
  };
}

async function listStoredSessions() {
  if (!isRemoteStoreEnabled()) return [];
  try {
    const collection = await getSessionCollection();
    const docs = await collection.find({}, { projection: { files: 0 } }).toArray();
    return docs.map((doc) => normalizeStoredSession(doc.phone || doc.sessionId || doc._id, doc)).filter(Boolean);
  } catch (error) {
    console.error('Failed to list stored sessions:', error?.message || error);
    return [];
  }
}

async function fetchStoredSession(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized || !isRemoteStoreEnabled()) return null;
  try {
    const collection = await getSessionCollection();
    const doc = await collection.findOne({ _id: normalized });
    return normalizeStoredSession(normalized, doc || {});
  } catch (error) {
    console.error('Failed to fetch stored session:', error?.message || error);
    return null;
  }
}

async function upsertStoredSession(phone, payload = {}) {
  const normalized = normalizePhone(phone);
  const doc = normalizeStoredSession(normalized, payload || {});
  if (!doc || !isRemoteStoreEnabled()) return doc;
  try {
    const collection = await getSessionCollection();
    await collection.updateOne({ _id: normalized }, { $set: doc }, { upsert: true });
  } catch (error) {
    console.error('Failed to upsert stored session:', error?.message || error);
  }
  return doc;
}

async function deleteStoredSession(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized || !isRemoteStoreEnabled()) return false;
  try {
    const collection = await getSessionCollection();
    await collection.deleteOne({ _id: normalized });
    return true;
  } catch (error) {
    console.error('Failed to delete stored session:', error?.message || error);
    return false;
  }
}

async function syncSessionToStore(phone, metadata = {}) {
  const normalized = normalizePhone(phone);
  if (!normalized) return false;
  const files = await collectSessionFiles(normalized);
  const snapshot = await upsertStoredSession(normalized, {
    ...metadata,
    phone: normalized,
    sessionId: normalized,
    files,
    updatedAt: new Date().toISOString(),
  });
  await updateSessionIndex(normalized, {
    ownerId: snapshot?.ownerId || '',
    registered: snapshot?.registered === true,
    connected: metadata.connected === true,
    lastConnectedAt: snapshot?.lastConnectedAt || null,
    remoteBackedUpAt: new Date().toISOString(),
    fileCount: snapshot?.fileCount || Object.keys(files).length,
  });
  return true;
}

async function restoreSessionFromStore(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized || hasLocalAuthFiles(normalized)) return false;
  const stored = await fetchStoredSession(normalized);
  if (!stored || !Object.keys(stored.files || {}).length) return false;
  await writeSessionFiles(normalized, stored.files || {});
  await updateSessionIndex(normalized, {
    registered: stored.registered === true,
    connected: false,
    restoredFromDatabaseAt: new Date().toISOString(),
    lastConnectedAt: stored.lastConnectedAt || null,
    fileCount: stored.fileCount || Object.keys(stored.files || {}).length,
  });
  return true;
}

function clearReconnect(phone) {
  const normalized = normalizePhone(phone);
  const timer = reconnectTimers.get(normalized);
  if (timer) {
    clearTimeout(timer);
    reconnectTimers.delete(normalized);
  }
}

async function destroySocket(phone) {
  const normalized = normalizePhone(phone);
  const existing = sockets.get(normalized);
  if (!existing) return;
  sockets.delete(normalized);
  try { existing.ws?.close?.(); } catch (_) {}
  try { existing.end?.(); } catch (_) {}
}

async function purgeSession(phone, { removeRemote = true } = {}) {
  const normalized = normalizePhone(phone);
  if (!normalized) return false;
  pairingRequests.delete(normalized);
  clearReconnect(normalized);
  await destroySocket(normalized);
  await removeSessionDir(normalized);
  if (removeRemote) {
    await deleteStoredSession(normalized);
  }
  await updateSessionIndex(normalized, {
    connected: false,
    registered: false,
    pendingPairing: false,
    lastPurgedAt: new Date().toISOString(),
  });
  return true;
}

function scheduleReconnect(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized || reconnectTimers.has(normalized)) return;
  const timer = setTimeout(async () => {
    reconnectTimers.delete(normalized);
    try {
      await createSocket(normalized, { bootRestore: true });
    } catch (error) {
      console.error('Reconnect failed for', normalized, error?.message || error);
      scheduleReconnect(normalized);
    }
  }, RECONNECT_DELAY_MS);
  reconnectTimers.set(normalized, timer);
}

function waitForPairingWindow(sock, phone, timeoutMs = 20000) {
  const normalized = normalizePhone(phone);
  if (!sock) return Promise.reject(new Error('Socket is required'));
  if (sock?.authState?.creds?.registered === true || sock?.user) {
    return Promise.resolve('registered');
  }

  return new Promise((resolve, reject) => {
    let settled = false;
    const cleanup = () => {
      clearTimeout(timer);
      try {
        if (typeof sock.ev.off === 'function') sock.ev.off('connection.update', onUpdate);
        else if (typeof sock.ev.removeListener === 'function') sock.ev.removeListener('connection.update', onUpdate);
      } catch (_) {}
    };
    const finishResolve = (reason) => {
      if (settled) return;
      settled = true;
      cleanup();
      updateSessionIndex(normalized, {
        pendingPairing: true,
        pairingWindowReadyAt: new Date().toISOString(),
        pairingWindowReason: String(reason || 'unknown'),
      }).catch(() => {});
      resolve(String(reason || 'ready'));
    };
    const finishReject = (error) => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(error instanceof Error ? error : new Error(String(error)));
    };
    const onUpdate = (update = {}) => {
      const connection = String(update.connection || '').trim();
      if (connection === 'connecting' || connection === 'open' || update.qr) {
        finishResolve(update.qr ? 'qr' : (connection || 'connecting'));
        return;
      }
      if (connection === 'close' && isPermanentDisconnect(update.lastDisconnect)) {
        finishReject(new Error(`Session closed before pairing (${getDisconnectStatusCode(update.lastDisconnect) || 'unknown'})`));
      }
    };
    const timer = setTimeout(() => finishResolve('timeout'), timeoutMs);
    try {
      sock.ev.on('connection.update', onUpdate);
    } catch (error) {
      finishReject(error);
    }
  });
}

async function requestPairingCodeWithRetry(sock, phone) {
  const normalized = normalizePhone(phone);
  const cached = pairingRequests.get(normalized);
  if (cached && cached.code && (Date.now() - Number(cached.requestedAt || 0) < PAIRING_CODE_CACHE_MS)) {
    return String(cached.code);
  }

  await waitForPairingWindow(sock, normalized);
  if (sock?.authState?.creds?.registered === true || sock?.user) {
    throw new Error('الرقم مربوط بالفعل والجلسة جاهزة.');
  }

  const waits = [1200, 2500, 4500, 7000];
  let lastError = new Error('Pairing code request failed');
  for (const waitMs of waits) {
    try {
      await delay(waitMs);
      const code = String(await sock.requestPairingCode(normalized) || '').trim();
      if (code) {
        pairingRequests.set(normalized, { code, requestedAt: Date.now() });
        return code;
      }
      lastError = new Error('Empty pairing code response');
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
    }
  }
  throw lastError;
}

async function createSocket(phone, options = {}) {
  const normalized = normalizePhone(phone);
  if (!normalized) throw new Error('Phone is required');
  if (sockets.has(normalized)) return sockets.get(normalized);
  if (startPromises.has(normalized)) return startPromises.get(normalized);

  const startPromise = (async () => {
    clearReconnect(normalized);

    if (!hasLocalAuthFiles(normalized)) {
      await restoreSessionFromStore(normalized);
    }

    await ensureSessionRoot();
    const sessionDir = getSessionDir(normalized);
    await fs.ensureDir(sessionDir);
    const helper = await useMultiFileAuthState(sessionDir);
    const state = helper.state;
    const { version } = await fetchLatestBaileysVersion();
    const sock = makeWASocket({
      version,
      browser: getBrowserProfile(),
      logger,
      printQRInTerminal: false,
      auth: {
        creds: state.creds,
        keys: makeCacheableSignalKeyStore(state.keys, logger),
      },
      markOnlineOnConnect: false,
      syncFullHistory: false,
      defaultQueryTimeoutMs: 0,
      connectTimeoutMs: 60000,
      keepAliveIntervalMs: 15000,
      fireInitQueries: true,
      emitOwnEvents: false,
      generateHighQualityLinkPreview: false,
    });

    sock.__sessionState = state;
    sockets.set(normalized, sock);

    const persistState = async (extra = {}) => {
      try {
        await helper.saveCreds();
      } catch (error) {
        console.error('Failed to save creds for', normalized, error?.message || error);
      }
      await syncSessionToStore(normalized, {
        registered: extra.registered === true || state?.creds?.registered === true,
        connected: extra.connected === true,
        lastConnectedAt: extra.lastConnectedAt || null,
        lastDisconnectAt: extra.lastDisconnectAt || null,
      });
    };

    sock.ev.on('creds.update', async () => {
      await updateSessionIndex(normalized, {
        registered: state?.creds?.registered === true,
        lastCredsSaveAt: new Date().toISOString(),
      });
      await persistState({ registered: state?.creds?.registered === true });
    });

    sock.ev.on('connection.update', async (update = {}) => {
      const connection = update.connection || '';
      if (connection === 'connecting' || update.qr) {
        await updateSessionIndex(normalized, {
          connected: false,
          registered: state?.creds?.registered === true,
          pendingPairing: state?.creds?.registered !== true,
          lastPairingWindowAt: new Date().toISOString(),
          lastError: '',
        });
      }

      if (connection === 'open') {
        pairingRequests.delete(normalized);
        clearReconnect(normalized);
        await updateSessionIndex(normalized, {
          registered: true,
          connected: true,
          pendingPairing: false,
          lastConnectedAt: new Date().toISOString(),
          meId: sock.user?.id || '',
          lastError: '',
        });
        await persistState({ registered: true, connected: true, lastConnectedAt: new Date().toISOString() });
        return;
      }

      if (connection === 'close') {
        sockets.delete(normalized);
        const statusCode = getDisconnectStatusCode(update.lastDisconnect);
        const permanent = isPermanentDisconnect(update.lastDisconnect);
        const restartRequired = statusCode === Number(DisconnectReason.restartRequired);
        await updateSessionIndex(normalized, {
          connected: false,
          registered: state?.creds?.registered === true,
          pendingPairing: state?.creds?.registered !== true,
          lastDisconnectAt: new Date().toISOString(),
          lastDisconnectReason: String(update.lastDisconnect?.error?.message || statusCode || ''),
        });
        if (permanent) {
          await purgeSession(normalized, { removeRemote: true });
          return;
        }
        if (restartRequired) {
          await destroySocket(normalized);
        }
        scheduleReconnect(normalized);
      }
    });

    await updateSessionIndex(normalized, {
      registered: state?.creds?.registered === true,
      connected: false,
      sessionDir,
      startedAt: new Date().toISOString(),
    });

    if (state?.creds?.registered === true) {
      await persistState({ registered: true, connected: false });
    }
    return sock;
  })().finally(() => {
    startPromises.delete(normalized);
  });

  startPromises.set(normalized, startPromise);
  return startPromise;
}

async function listLocalSessionPhones() {
  await ensureSessionRoot();
  const entries = await fs.readdir(SESSION_ROOT).catch(() => []);
  return entries
    .filter((name) => name !== 'index.json')
    .map((name) => normalizePhone(name))
    .filter(Boolean);
}

async function restoreAllSessionsOnBoot() {
  const localPhones = await listLocalSessionPhones();
  const remotePhones = (await listStoredSessions())
    .map((item) => normalizePhone(item.phone || item.sessionId || item._id || ''))
    .filter(Boolean);
  const phones = Array.from(new Set([...localPhones, ...remotePhones]));
  for (const phone of phones) {
    try {
      await createSocket(phone, { bootRestore: true });
      await delay(350);
    } catch (error) {
      console.error('Boot restore failed for', phone, error?.message || error);
    }
  }
}

app.get('/', async (_req, res) => {
  const index = await readSessionIndex();
  res.json({ status: 'ok', service: 'embedded-pairing-server', sessions: Object.keys(index.sessions || {}).length, time: new Date().toISOString() });
});

app.get('/health', async (_req, res) => {
  const index = await readSessionIndex();
  res.json({ status: 'ok', sessions: index.sessions || {}, activeSockets: Array.from(sockets.keys()) });
});

app.get('/api/session-status', async (req, res) => {
  const phone = pickPhone(req);
  if (!phone) return res.status(400).json({ success: false, error: 'phone is required' });
  const index = await readSessionIndex();
  return res.json({ success: true, session: index.sessions?.[phone] || null, active: sockets.has(phone) });
});

app.all('/api/pairing', async (req, res) => {
  const phone = pickPhone(req);
  if (!phone) return res.status(400).json({ success: false, error: 'أدخل الرقم أولاً' });

  try {
    const index = await readSessionIndex();
    const existingRecord = index.sessions?.[phone] || {};
    if (existingRecord.registered === true || hasLocalAuthFiles(phone)) {
      const restoredSock = await createSocket(phone, { bootRestore: true });
      if (restoredSock?.user || existingRecord.registered === true || restoredSock?.__sessionState?.creds?.registered === true) {
        await updateSessionIndex(phone, {
          registered: true,
          connected: true,
          alreadyLinked: true,
          pendingPairing: false,
          lastPairingCheckAt: new Date().toISOString(),
        });
        return res.json({ success: true, linked: true, alreadyLinked: true, number: phone, message: 'الرقم مربوط بالفعل والجلسة محفوظة.' });
      }
    }

    await purgeSession(phone, { removeRemote: true });
    const sock = await createSocket(phone, { bootRestore: false });
    if (sock?.authState?.creds?.registered === true || sock?.user) {
      await updateSessionIndex(phone, {
        registered: true,
        connected: true,
        alreadyLinked: true,
        pendingPairing: false,
        lastPairingCheckAt: new Date().toISOString(),
      });
      return res.json({ success: true, linked: true, alreadyLinked: true, number: phone, message: 'الرقم مربوط بالفعل والجلسة محفوظة.' });
    }
    const code = await requestPairingCodeWithRetry(sock, phone);
    await updateSessionIndex(phone, {
      registered: false,
      connected: false,
      pendingPairing: true,
      lastPairCodeRequestedAt: new Date().toISOString(),
      lastError: '',
    });
    await syncSessionToStore(phone, { registered: false, connected: false });
    return res.json({ success: true, linked: false, number: phone, code, pairingCode: code });
  } catch (error) {
    await updateSessionIndex(phone, {
      registered: false,
      connected: false,
      pendingPairing: false,
      lastError: error?.message || String(error),
      lastErrorAt: new Date().toISOString(),
    });
    console.error('Pairing failure for', phone, error?.stack || error?.message || error);
    return res.status(500).json({ success: false, error: error?.message || 'فشل توليد الكود، حاول مجدداً' });
  }
});

app.delete('/api/session/:phone', async (req, res) => {
  const phone = normalizePhone(req.params?.phone || '');
  if (!phone) return res.status(400).json({ success: false, error: 'phone is required' });
  await purgeSession(phone, { removeRemote: true });
  return res.json({ success: true, deleted: true, phone });
});

process.on('SIGINT', async () => {
  for (const timer of reconnectTimers.values()) clearTimeout(timer);
  for (const phone of Array.from(sockets.keys())) await destroySocket(phone);
  process.exit(0);
});

process.on('SIGTERM', async () => {
  for (const timer of reconnectTimers.values()) clearTimeout(timer);
  for (const phone of Array.from(sockets.keys())) await destroySocket(phone);
  process.exit(0);
});

app.listen(PORT, '0.0.0.0', async () => {
  await ensureSessionRoot();
  await restoreAllSessionsOnBoot();
  console.log(`Embedded pairing server listening on ${PORT}`);
});
"""
EMBEDDED_INDEX_HTML = '''<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WhatsApp Pairing</title>
    <style>
        body { margin:0; min-height:100vh; display:flex; justify-content:center; align-items:center; background:#0b0f14; font-family:Arial,sans-serif; color:#fff; }
        .card { width:min(92vw,420px); background:#111827; border:1px solid #1f2937; border-radius:22px; padding:28px; box-shadow:0 20px 45px rgba(0,0,0,.35); text-align:center; }
        input, button { width:100%; border-radius:14px; padding:14px 16px; border:0; font-size:16px; box-sizing:border-box; }
        input { margin:14px 0; background:#1f2937; color:#fff; }
        button { background:#16a34a; color:#fff; cursor:pointer; font-weight:700; }
        button:disabled { opacity:.7; cursor:not-allowed; }
        .code { margin-top:18px; font-size:28px; font-weight:700; letter-spacing:3px; background:#fff; color:#000; border-radius:14px; padding:14px; display:none; }
        .hint, .error, .loader { margin-top:12px; font-size:14px; }
        .hint { color:#93c5fd; }
        .error { color:#fca5a5; }
        .loader { color:#86efac; display:none; }
    </style>
</head>
<body>
    <div class="card">
        <h2>WhatsApp Pairing</h2>
        <p>أدخل رقم الواتساب مع رمز الدولة</p>
        <input type="text" id="number" placeholder="مثال: 96777xxxxxxx">
        <button id="submitBtn" onclick="sendPairingRequest()">الحصول على الكود</button>
        <div id="loader" class="loader">جاري طلب الكود...</div>
        <div id="code" class="code"></div>
        <div class="hint">الأجهزة المرتبطة ← ربط جهاز ← الربط برقم الهاتف</div>
        <div id="error" class="error"></div>
    </div>

    <script>
        async function sendPairingRequest() {
            const numberInput = document.getElementById('number');
            const btn = document.getElementById('submitBtn');
            const loader = document.getElementById('loader');
            const codeBox = document.getElementById('code');
            const errorBox = document.getElementById('error');

            const number = numberInput.value.replace(/[^0-9]/g, '');
            if (!number || number.length < 8) {
                errorBox.innerText = 'يرجى إدخال رقم صحيح مع رمز الدولة';
                return;
            }

            errorBox.innerText = '';
            codeBox.style.display = 'none';
            btn.disabled = true;
            loader.style.display = 'block';

            try {
                const response = await fetch(`/api/pairing?num=${encodeURIComponent(number)}`, {
                    method: 'GET',
                    headers: { 'Accept': 'application/json' }
                });
                const data = await response.json();
                if (!response.ok || !data.code) {
                    throw new Error(data.error || data.message || 'فشل توليد الكود');
                }
                codeBox.innerText = data.code;
                codeBox.style.display = 'block';
            } catch (error) {
                errorBox.innerText = error.message || 'تعذر الاتصال بالسيرفر';
            } finally {
                loader.style.display = 'none';
                btn.disabled = false;
            }
        }
    </script>
</body>
</html>
'''

EMBEDDED_PACKAGE_JSON = r'''{
  "name": "whatsapp-pairing-api-local",
  "version": "1.0.0",
  "private": true,
  "main": "server.js",
  "scripts": {
    "start": "node server.js"
  },
  "engines": {
    "node": ">=18.0.0"
  },
  "dependencies": {
    "@whiskeysockets/baileys": "^7.0.0-rc.9",
    "express": "^4.21.2",
    "fs-extra": "^11.2.0",
    "mongodb": "^6.0.0",
    "pino": "^8.21.0"
  }
}'''

EMBEDDED_PAIRING_BRIDGE_JS = r'''const { EventEmitter } = require('events');

const emitter = new EventEmitter();
emitter.setMaxListeners(0);
const socketMap = new Map();
const metaMap = new Map();
let connectionState = 'idle';
let lastUpdatedAt = new Date().toISOString();

function touch() { lastUpdatedAt = new Date().toISOString(); }

function setConnectionState(state) {
  connectionState = state || 'unknown';
  touch();
  return connectionState;
}

function getConnectionState() { return connectionState; }

function setSocket(phone, socket, metadata = {}) {
  if (!phone) return null;
  const normalizedPhone = String(phone).replace(/\D/g, '');
  if (!normalizedPhone) return null;

  socketMap.set(normalizedPhone, socket);
  metaMap.set(normalizedPhone, { ...(metaMap.get(normalizedPhone) || {}), ...metadata, phone: normalizedPhone, registered: metadata?.registered !== false });
  touch();
  setConnectionState('open');

  setImmediate(() => {
    try { emitter.emit('phone.activated', normalizedPhone, socket, metaMap.get(normalizedPhone) || {}); } catch (_) {}
  });

  return socket;
}

function releaseSocket(phone) {
  if (!phone) return false;
  const normalizedPhone = String(phone).replace(/\D/g, '');
  if (!normalizedPhone) return false;
  const existed = socketMap.delete(normalizedPhone);
  metaMap.delete(normalizedPhone);
  if (socketMap.size === 0) setConnectionState('idle');
  touch();
  if (existed) {
    setImmediate(() => {
      try { emitter.emit('phone.released', normalizedPhone); } catch (_) {}
    });
  }
  return existed;
}

function getSocket(phone = '') {
  const normalizedPhone = String(phone || '').replace(/\D/g, '');
  return socketMap.get(normalizedPhone) || null;
}

function getPhoneMeta(phone = '') {
  const normalizedPhone = String(phone || '').replace(/\D/g, '');
  return metaMap.get(normalizedPhone) || null;
}

function listActivePhones() {
  return Array.from(socketMap.keys());
}

function getBridgeState() {
  return {
    connectionState,
    hasSocket: socketMap.size > 0,
    activePhones: listActivePhones(),
    lastUpdatedAt,
    socketCount: socketMap.size,
  };
}

async function waitForPhone(phone, { timeoutMs = 6000 } = {}) {
  const normalizedPhone = String(phone || '').replace(/\D/g, '');
  if (!normalizedPhone) return null;
  const existing = socketMap.get(normalizedPhone);
  if (existing) return existing;

  return new Promise((resolve) => {
    const onActivated = (activatedPhone, socket) => {
      if (String(activatedPhone).replace(/\D/g, '') === normalizedPhone) {
        cleanup();
        resolve(socket);
      }
    };
    const timer = setTimeout(() => {
      cleanup();
      resolve(socketMap.get(normalizedPhone) || null);
    }, Math.max(250, Number(timeoutMs) || 6000));
    const cleanup = () => {
      emitter.off('phone.activated', onActivated);
      clearTimeout(timer);
    };
    emitter.on('phone.activated', onActivated);
  });
}

module.exports = {
  pairingBridge: {
    setSocket,
    releaseSocket,
    getSocket,
    getPhoneMeta,
    listActivePhones,
    getBridgeState,
    setConnectionState,
    getConnectionState,
    waitForPhone,
    emitter,
  },
};
'''

EMBEDDED_SERVER_JS = r'''const express = require('express');
const fs = require('fs-extra');
const path = require('path');
const pino = require('pino');
const { MongoClient } = require('mongodb');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  makeCacheableSignalKeyStore,
  fetchLatestBaileysVersion,
  Browsers,
  DisconnectReason,
  delay,
} = require('@whiskeysockets/baileys');
const { pairingBridge } = require('./lib/pairingBridge');
const { SESSION_ROOT } = require('./lib/storagePaths');

const app = express();
app.use(express.json({ limit: '2mb' }));

const PORT = Number(process.env.COMPANION_PORT || process.env.PAIRING_SERVER_PORT || 3100);
const SESSION_INDEX_FILE = path.join(SESSION_ROOT, 'index.json');
const logger = pino({ level: process.env.LOG_LEVEL || 'silent' });
const sockets = new Map();
const startPromises = new Map();
const reconnectTimers = new Map();
const pairingRequests = new Map();
const RECONNECT_DELAY_MS = Math.max(2500, Number(process.env.RECONNECT_DELAY_MS || 5000));
const PAIRING_CODE_CACHE_MS = Math.max(30000, Number(process.env.PAIRING_CODE_CACHE_MS || 55000));
const SESSION_COLLECTION_NAME = String(process.env.MONGODB_SESSIONS_COLLECTION || 'whatsapp_sessions').trim() || 'whatsapp_sessions';
const MONGODB_DB_NAME = String(process.env.MONGODB_DB_NAME || 'whatsapp_pairing_api').trim() || 'whatsapp_pairing_api';
const SESSION_STORE_TIMEOUT_MS = Math.max(5000, Number(process.env.SESSION_STORAGE_TIMEOUT_MS || 20000));
const MONGODB_URI = String(process.env.MONGODB_URI || process.env.MONGO_URL || '').trim();
let mongoCollectionPromise = null;

function normalizePhone(raw = '') {
  return String(raw || '').replace(/\D/g, '').trim();
}

function getSessionDir(phone) {
  return path.join(SESSION_ROOT, normalizePhone(phone));
}

function pickPhone(req) {
  const body = req.body || {};
  const query = req.query || {};
  return normalizePhone(body.num || body.phone || body.number || body.phoneNumber || query.num || query.phone || query.number || query.phoneNumber);
}

function getBrowserProfile() {
  try { return Browsers.ubuntu('Chrome'); } catch (_) {}
  try { return Browsers.windows('Chrome'); } catch (_) {}
  try { return Browsers.macOS('Safari'); } catch (_) {}
  return ['Ubuntu', 'Chrome', '22.04'];
}

function isRemoteStoreEnabled() {
  return Boolean(MONGODB_URI);
}

async function ensureSessionRoot() {
  await fs.ensureDir(SESSION_ROOT);
}

async function readSessionIndex() {
  await ensureSessionRoot();
  try {
    const data = await fs.readJson(SESSION_INDEX_FILE);
    return data && typeof data === 'object' ? data : { sessions: {} };
  } catch (_) {
    return { sessions: {} };
  }
}

async function writeSessionIndex(index) {
  await ensureSessionRoot();
  await fs.writeJson(SESSION_INDEX_FILE, index, { spaces: 2 });
}

async function updateSessionIndex(phone, patch = {}) {
  const normalized = normalizePhone(phone);
  if (!normalized) return null;
  const index = await readSessionIndex();
  const existing = index.sessions?.[normalized] || {};
  index.sessions = index.sessions || {};
  index.sessions[normalized] = {
    phone: normalized,
    sessionId: normalized,
    updatedAt: new Date().toISOString(),
    ...existing,
    ...patch,
  };
  await writeSessionIndex(index);
  return index.sessions[normalized];
}

function getDisconnectStatusCode(lastDisconnect = null) {
  return Number(lastDisconnect?.error?.output?.statusCode || lastDisconnect?.error?.statusCode || 0);
}

function isPermanentDisconnect(lastDisconnect = null) {
  const statusCode = getDisconnectStatusCode(lastDisconnect);
  const rawMessage = String(
    lastDisconnect?.error?.data ||
    lastDisconnect?.error?.message ||
    lastDisconnect?.error?.output?.payload?.message ||
    ''
  ).toLowerCase();
  if (statusCode === Number(DisconnectReason.loggedOut)) return true;
  if ([401, 403, 405, 500].includes(statusCode)) return true;
  return /(logged\s*out|device\s*removed|forbidden|banned|blocked|not-authorized|not authorized|session\s*expired|bad\s*session)/i.test(rawMessage);
}

function listSessionFiles(phone) {
  const normalized = normalizePhone(phone);
  const sessionDir = getSessionDir(normalized);
  if (!normalized || !fs.existsSync(sessionDir)) return [];
  return fs.readdirSync(sessionDir)
    .filter((name) => name && name.endsWith('.json'))
    .sort();
}

function hasLocalAuthFiles(phone) {
  return listSessionFiles(phone).some((fileName) => fileName === 'creds.json' || fileName.startsWith('app-state-sync-') || fileName.startsWith('pre-key-') || fileName.startsWith('sender-key-') || fileName.startsWith('session-'));
}

async function removeSessionDir(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized) return;
  await fs.remove(getSessionDir(normalized));
}

async function collectSessionFiles(phone) {
  const normalized = normalizePhone(phone);
  const files = {};
  for (const fileName of listSessionFiles(normalized)) {
    const filePath = path.join(getSessionDir(normalized), fileName);
    try {
      files[fileName] = await fs.readFile(filePath, 'utf8');
    } catch (error) {
      console.error('Failed to read session file', fileName, error?.message || error);
    }
  }
  return files;
}

async function writeSessionFiles(phone, files = {}) {
  const normalized = normalizePhone(phone);
  if (!normalized) return false;
  const sessionDir = getSessionDir(normalized);
  await fs.ensureDir(sessionDir);

  const allowed = new Set(Object.keys(files || {}).filter((name) => name.endsWith('.json')));
  for (const existingFile of listSessionFiles(normalized)) {
    if (!allowed.has(existingFile)) {
      try { await fs.remove(path.join(sessionDir, existingFile)); } catch (_) {}
    }
  }

  for (const [fileName, content] of Object.entries(files || {})) {
    if (!fileName || !fileName.endsWith('.json')) continue;
    await fs.writeFile(path.join(sessionDir, fileName), String(content || ''), 'utf8');
  }
  return true;
}

async function getSessionCollection() {
  if (!isRemoteStoreEnabled()) return null;
  if (!mongoCollectionPromise) {
    mongoCollectionPromise = (async () => {
      const client = new MongoClient(MONGODB_URI, {
        appName: 'local-whatsapp-pairing-server',
        serverSelectionTimeoutMS: SESSION_STORE_TIMEOUT_MS,
        connectTimeoutMS: SESSION_STORE_TIMEOUT_MS,
        maxPoolSize: 5,
        retryWrites: true,
      });
      await client.connect();
      const collection = client.db(MONGODB_DB_NAME).collection(SESSION_COLLECTION_NAME);
      await Promise.allSettled([
        collection.createIndex({ phone: 1 }, { unique: true }),
        collection.createIndex({ updatedAt: -1 }),
      ]);
      return collection;
    })().catch((error) => {
      mongoCollectionPromise = null;
      throw error;
    });
  }
  return mongoCollectionPromise;
}

function normalizeStoredSession(phone, payload = {}) {
  const normalized = normalizePhone(phone || payload.phone || payload.sessionId || payload._id || '');
  if (!normalized) return null;
  const files = {};
  for (const [fileName, content] of Object.entries(payload.files || {})) {
    const safeName = path.basename(String(fileName || '').trim());
    if (!safeName || !safeName.endsWith('.json')) continue;
    if (typeof content !== 'string') continue;
    files[safeName] = content;
  }
  return {
    _id: normalized,
    phone: normalized,
    sessionId: normalized,
    registered: payload.registered === true,
    connected: payload.connected === true,
    lastConnectedAt: payload.lastConnectedAt || null,
    lastDisconnectAt: payload.lastDisconnectAt || null,
    activatedAt: payload.activatedAt || null,
    updatedAt: payload.updatedAt || new Date().toISOString(),
    files,
    fileCount: Object.keys(files).length,
  };
}

async function listStoredSessions() {
  if (!isRemoteStoreEnabled()) return [];
  try {
    const collection = await getSessionCollection();
    const docs = await collection.find({}, { projection: { files: 0 } }).toArray();
    return docs.map((doc) => normalizeStoredSession(doc.phone || doc.sessionId || doc._id, doc)).filter(Boolean);
  } catch (error) {
    console.error('Failed to list stored sessions:', error?.message || error);
    return [];
  }
}

async function fetchStoredSession(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized || !isRemoteStoreEnabled()) return null;
  try {
    const collection = await getSessionCollection();
    const doc = await collection.findOne({ _id: normalized });
    return normalizeStoredSession(normalized, doc || {});
  } catch (error) {
    console.error('Failed to fetch stored session:', error?.message || error);
    return null;
  }
}

async function upsertStoredSession(phone, payload = {}) {
  const normalized = normalizePhone(phone);
  const doc = normalizeStoredSession(normalized, payload || {});
  if (!doc || !isRemoteStoreEnabled()) return doc;
  try {
    const collection = await getSessionCollection();
    await collection.updateOne({ _id: normalized }, { $set: doc }, { upsert: true });
  } catch (error) {
    console.error('Failed to upsert stored session:', error?.message || error);
  }
  return doc;
}

async function deleteStoredSession(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized || !isRemoteStoreEnabled()) return false;
  try {
    const collection = await getSessionCollection();
    await collection.deleteOne({ _id: normalized });
    return true;
  } catch (error) {
    console.error('Failed to delete stored session:', error?.message || error);
    return false;
  }
}

async function syncSessionToStore(phone, metadata = {}) {
  const normalized = normalizePhone(phone);
  if (!normalized) return false;
  const files = await collectSessionFiles(normalized);
  const snapshot = await upsertStoredSession(normalized, {
    ...metadata,
    phone: normalized,
    sessionId: normalized,
    files,
    updatedAt: new Date().toISOString(),
  });
  await updateSessionIndex(normalized, {
    registered: snapshot?.registered === true,
    connected: metadata.connected === true,
    lastConnectedAt: snapshot?.lastConnectedAt || null,
    activatedAt: snapshot?.activatedAt || null,
    remoteBackedUpAt: new Date().toISOString(),
    fileCount: snapshot?.fileCount || Object.keys(files).length,
  });
  return true;
}

async function restoreSessionFromStore(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized || hasLocalAuthFiles(normalized)) return false;
  const stored = await fetchStoredSession(normalized);
  if (!stored || !Object.keys(stored.files || {}).length) return false;
  await writeSessionFiles(normalized, stored.files || {});
  await updateSessionIndex(normalized, {
    registered: stored.registered === true,
    connected: false,
    restoredFromDatabaseAt: new Date().toISOString(),
    lastConnectedAt: stored.lastConnectedAt || null,
    fileCount: stored.fileCount || Object.keys(stored.files || {}).length,
  });
  return true;
}

function clearReconnect(phone) {
  const normalized = normalizePhone(phone);
  const timer = reconnectTimers.get(normalized);
  if (timer) {
    clearTimeout(timer);
    reconnectTimers.delete(normalized);
  }
}

async function destroySocket(phone) {
  const normalized = normalizePhone(phone);
  const existing = sockets.get(normalized);
  if (!existing) return;
  sockets.delete(normalized);
  try { existing.ws?.close?.(); } catch (_) {}
  try { existing.end?.(); } catch (_) {}
  try { pairingBridge.releaseSocket(normalized); } catch (_) {}
}

async function purgeSession(phone, { removeRemote = true } = {}) {
  const normalized = normalizePhone(phone);
  if (!normalized) return false;
  pairingRequests.delete(normalized);
  clearReconnect(normalized);
  await destroySocket(normalized);
  await removeSessionDir(normalized);
  if (removeRemote) {
    await deleteStoredSession(normalized);
  }
  await updateSessionIndex(normalized, {
    connected: false,
    registered: false,
    pendingPairing: false,
    lastPurgedAt: new Date().toISOString(),
  });
  return true;
}

function scheduleReconnect(phone) {
  const normalized = normalizePhone(phone);
  if (!normalized || reconnectTimers.has(normalized)) return;
  const timer = setTimeout(async () => {
    reconnectTimers.delete(normalized);
    try {
      await createSocket(normalized, { bootRestore: true });
    } catch (error) {
      console.error('Reconnect failed for', normalized, error?.message || error);
      scheduleReconnect(normalized);
    }
  }, RECONNECT_DELAY_MS);
  reconnectTimers.set(normalized, timer);
}

function waitForPairingWindow(sock, phone, timeoutMs = 20000) {
  const normalized = normalizePhone(phone);
  if (!sock) return Promise.reject(new Error('Socket is required'));
  if (sock?.authState?.creds?.registered === true || sock?.user) {
    return Promise.resolve('registered');
  }

  return new Promise((resolve, reject) => {
    let settled = false;
    const cleanup = () => {
      clearTimeout(timer);
      try {
        if (typeof sock.ev.off === 'function') sock.ev.off('connection.update', onUpdate);
        else if (typeof sock.ev.removeListener === 'function') sock.ev.removeListener('connection.update', onUpdate);
      } catch (_) {}
    };
    const finishResolve = (reason) => {
      if (settled) return;
      settled = true;
      cleanup();
      updateSessionIndex(normalized, {
        pendingPairing: true,
        pairingWindowReadyAt: new Date().toISOString(),
        pairingWindowReason: String(reason || 'unknown'),
      }).catch(() => {});
      resolve(String(reason || 'ready'));
    };
    const finishReject = (error) => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(error instanceof Error ? error : new Error(String(error)));
    };
    const onUpdate = (update = {}) => {
      const connection = String(update.connection || '').trim();
      if (connection === 'connecting' || connection === 'open' || update.qr) {
        finishResolve(update.qr ? 'qr' : (connection || 'connecting'));
        return;
      }
      if (connection === 'close' && isPermanentDisconnect(update.lastDisconnect)) {
        finishReject(new Error(`Session closed before pairing (${getDisconnectStatusCode(update.lastDisconnect) || 'unknown'})`));
      }
    };
    const timer = setTimeout(() => finishResolve('timeout'), timeoutMs);
    try {
      sock.ev.on('connection.update', onUpdate);
    } catch (error) {
      finishReject(error);
    }
  });
}

async function requestPairingCodeWithRetry(sock, phone) {
  const normalized = normalizePhone(phone);
  const cached = pairingRequests.get(normalized);
  if (cached && cached.code && (Date.now() - Number(cached.requestedAt || 0) < PAIRING_CODE_CACHE_MS)) {
    return String(cached.code);
  }

  await waitForPairingWindow(sock, normalized);
  if (sock?.authState?.creds?.registered === true || sock?.user) {
    throw new Error('الرقم مربوط بالفعل والجلسة جاهزة.');
  }

  const waits = [1200, 2500, 4500, 7000];
  let lastError = new Error('Pairing code request failed');
  for (const waitMs of waits) {
    try {
      await delay(waitMs);
      const code = String(await sock.requestPairingCode(normalized) || '').trim();
      if (code) {
        pairingRequests.set(normalized, { code, requestedAt: Date.now() });
        return code;
      }
      lastError = new Error('Empty pairing code response');
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
    }
  }
  throw lastError;
}

async function handleConnectionOpened(sock, phone, state) {
  const normalized = normalizePhone(phone);
  const nowIso = new Date().toISOString();
  pairingRequests.delete(normalized);
  clearReconnect(normalized);

  await updateSessionIndex(normalized, {
    registered: true,
    connected: true,
    pendingPairing: false,
    lastConnectedAt: nowIso,
    meId: sock.user?.id || '',
    lastError: '',
  });

  try { await syncSessionToStore(normalized, { registered: true, connected: true, lastConnectedAt: nowIso }); } catch (_) {}
  try {
    pairingBridge.setSocket(normalized, sock, {
      phone: normalized,
      registered: true,
      meId: sock.user?.id || '',
      connectedAt: nowIso,
    });
  } catch (_) {}
}

async function createSocket(phone, options = {}) {
  const normalized = normalizePhone(phone);
  if (!normalized) throw new Error('Phone is required');
  if (sockets.has(normalized)) return sockets.get(normalized);
  if (startPromises.has(normalized)) return startPromises.get(normalized);

  const startPromise = (async () => {
    clearReconnect(normalized);

    if (!hasLocalAuthFiles(normalized)) {
      await restoreSessionFromStore(normalized);
    }

    await ensureSessionRoot();
    const sessionDir = getSessionDir(normalized);
    await fs.ensureDir(sessionDir);
    const helper = await useMultiFileAuthState(sessionDir);
    const state = helper.state;
    const { version } = await fetchLatestBaileysVersion().catch(() => ({ version: undefined }));
    const sock = makeWASocket({
      version,
      browser: getBrowserProfile(),
      logger,
      printQRInTerminal: false,
      auth: {
        creds: state.creds,
        keys: makeCacheableSignalKeyStore(state.keys, logger),
      },
      markOnlineOnConnect: true,
      syncFullHistory: false,
      defaultQueryTimeoutMs: 0,
      connectTimeoutMs: 60000,
      keepAliveIntervalMs: 15000,
      fireInitQueries: true,
      emitOwnEvents: false,
      generateHighQualityLinkPreview: false,
    });

    sock.__sessionState = state;
    sockets.set(normalized, sock);

    const persistState = async (extra = {}) => {
      try { await helper.saveCreds(); } catch (error) { console.error('Failed to save creds for', normalized, error?.message || error); }
      await syncSessionToStore(normalized, {
        registered: extra.registered === true || state?.creds?.registered === true,
        connected: extra.connected === true,
        lastConnectedAt: extra.lastConnectedAt || null,
        lastDisconnectAt: extra.lastDisconnectAt || null,
      });
    };

    sock.ev.on('creds.update', async () => {
      await updateSessionIndex(normalized, {
        registered: state?.creds?.registered === true,
        lastCredsSaveAt: new Date().toISOString(),
      });
      await persistState({ registered: state?.creds?.registered === true });
    });

    sock.ev.on('connection.update', async (update = {}) => {
      const connection = update.connection || '';
      if (connection === 'connecting' || update.qr) {
        await updateSessionIndex(normalized, {
          connected: false,
          registered: state?.creds?.registered === true,
          pendingPairing: state?.creds?.registered !== true,
          lastPairingWindowAt: new Date().toISOString(),
          lastError: '',
        });
      }

      if (connection === 'open') {
        await handleConnectionOpened(sock, normalized, state);
        return;
      }

      if (connection === 'close') {
        sockets.delete(normalized);
        const statusCode = getDisconnectStatusCode(update.lastDisconnect);
        const permanent = isPermanentDisconnect(update.lastDisconnect);
        const restartRequired = statusCode === Number(DisconnectReason.restartRequired);
        await updateSessionIndex(normalized, {
          connected: false,
          registered: state?.creds?.registered === true,
          pendingPairing: state?.creds?.registered !== true,
          lastDisconnectAt: new Date().toISOString(),
          lastDisconnectReason: String(update.lastDisconnect?.error?.message || statusCode || ''),
        });
        if (permanent) {
          await purgeSession(normalized, { removeRemote: true });
          return;
        }
        if (restartRequired) {
          await destroySocket(normalized);
        }
        scheduleReconnect(normalized);
      }
    });

    await updateSessionIndex(normalized, {
      registered: state?.creds?.registered === true,
      connected: false,
      sessionDir,
      startedAt: new Date().toISOString(),
    });

    if (state?.creds?.registered === true) {
      try { pairingBridge.setSocket(normalized, sock, { phone: normalized, registered: true }); } catch (_) {}
      await persistState({ registered: true, connected: false });
    }
    return sock;
  })().finally(() => {
    startPromises.delete(normalized);
  });

  startPromises.set(normalized, startPromise);
  return startPromise;
}

async function listLocalSessionPhones() {
  await ensureSessionRoot();
  const entries = await fs.readdir(SESSION_ROOT).catch(() => []);
  return entries.filter((name) => name !== 'index.json').map((name) => normalizePhone(name)).filter(Boolean);
}

async function restoreAllSessionsOnBoot() {
  const localPhones = await listLocalSessionPhones();
  const remotePhones = (await listStoredSessions()).map((item) => normalizePhone(item.phone || item.sessionId || item._id || '')).filter(Boolean);
  const phones = Array.from(new Set([...localPhones, ...remotePhones]));
  for (const phone of phones) {
    try {
      await createSocket(phone, { bootRestore: true });
      await delay(350);
    } catch (error) {
      console.error('Boot restore failed for', phone, error?.message || error);
    }
  }
}

app.get('/', async (_req, res) => {
  const index = await readSessionIndex();
  res.json({ status: 'ok', service: 'local-whatsapp-pairing-server', sessions: Object.keys(index.sessions || {}).length, time: new Date().toISOString() });
});

app.get('/health', async (_req, res) => {
  const index = await readSessionIndex();
  res.json({ status: 'ok', sessions: index.sessions || {}, activeSockets: Array.from(sockets.keys()) });
});

app.get('/api/session-status', async (req, res) => {
  const phone = pickPhone(req);
  if (!phone) return res.status(400).json({ success: false, error: 'phone is required' });
  const index = await readSessionIndex();
  return res.json({ success: true, session: index.sessions?.[phone] || null, active: sockets.has(phone), bridgeSocket: !!pairingBridge.getSocket(phone) });
});

app.all('/api/pairing', async (req, res) => {
  const phone = pickPhone(req);
  if (!phone) return res.status(400).json({ success: false, error: 'أدخل الرقم أولاً' });

  try {
    const index = await readSessionIndex();
    const existingRecord = index.sessions?.[phone] || {};
    if (existingRecord.registered === true || hasLocalAuthFiles(phone)) {
      const restoredSock = await createSocket(phone, { bootRestore: true });
      if (restoredSock?.user || existingRecord.registered === true || restoredSock?.__sessionState?.creds?.registered === true) {
        await updateSessionIndex(phone, {
          registered: true,
          connected: true,
          alreadyLinked: true,
          pendingPairing: false,
          lastPairingCheckAt: new Date().toISOString(),
        });
        try { await handleConnectionOpened(restoredSock, phone, restoredSock.__sessionState); } catch (_) {}
        return res.json({ success: true, linked: true, alreadyLinked: true, number: phone, message: 'الرقم مربوط بالفعل والجلسة محفوظة.' });
      }
    }

    await purgeSession(phone, { removeRemote: true });
    const sock = await createSocket(phone, { bootRestore: false });
    if (sock?.authState?.creds?.registered === true || sock?.user) {
      await updateSessionIndex(phone, {
        registered: true,
        connected: true,
        alreadyLinked: true,
        pendingPairing: false,
        lastPairingCheckAt: new Date().toISOString(),
      });
      try { await handleConnectionOpened(sock, phone, sock.__sessionState); } catch (_) {}
      return res.json({ success: true, linked: true, alreadyLinked: true, number: phone, message: 'الرقم مربوط بالفعل والجلسة محفوظة.' });
    }

    const code = await requestPairingCodeWithRetry(sock, phone);
    await updateSessionIndex(phone, {
      registered: false,
      connected: false,
      pendingPairing: true,
      lastPairCodeRequestedAt: new Date().toISOString(),
      lastError: '',
    });
    await syncSessionToStore(phone, { registered: false, connected: false });
    return res.json({ success: true, linked: false, number: phone, code, pairingCode: code, expiresInSeconds: Math.round(PAIRING_CODE_CACHE_MS / 1000) });
  } catch (error) {
    await updateSessionIndex(phone, {
      registered: false,
      connected: false,
      pendingPairing: false,
      lastError: error?.message || String(error),
      lastErrorAt: new Date().toISOString(),
    });
    console.error('Pairing failure for', phone, error?.stack || error?.message || error);
    return res.status(500).json({ success: false, error: error?.message || 'فشل توليد الكود، حاول مجدداً' });
  }
});

app.delete('/api/session/:phone', async (req, res) => {
  const phone = normalizePhone(req.params?.phone || '');
  if (!phone) return res.status(400).json({ success: false, error: 'phone is required' });
  await purgeSession(phone, { removeRemote: true });
  return res.json({ success: true, deleted: true, phone });
});

process.on('SIGINT', async () => {
  for (const timer of reconnectTimers.values()) clearTimeout(timer);
  for (const phone of Array.from(sockets.keys())) await destroySocket(phone);
  process.exit(0);
});

process.on('SIGTERM', async () => {
  for (const timer of reconnectTimers.values()) clearTimeout(timer);
  for (const phone of Array.from(sockets.keys())) await destroySocket(phone);
  process.exit(0);
});

app.listen(PORT, '0.0.0.0', async () => {
  await ensureSessionRoot();
  await restoreAllSessionsOnBoot();
  console.log(`Local pairing server listening on ${PORT}`);
});
'''

def ensure_embedded_companion_files(base_dir: Optional[Path] = None) -> dict[str, Path]:
    target_dir = Path(base_dir) if base_dir else EMBEDDED_COMPANION_DIR
    embedded_files = {
        "package.json": EMBEDDED_PACKAGE_JSON,
        "server.js": EMBEDDED_SERVER_JS,
        "index.html": EMBEDDED_INDEX_HTML,
        "lib/pairingBridge.js": EMBEDDED_PAIRING_BRIDGE_JS,
        "lib/storagePaths.js": EMBEDDED_STORAGE_PATHS_JS,
    }
    protected_existing_files: set[str] = set()
    written_files: dict[str, Path] = {}
    for filename, content in embedded_files.items():
        file_path = target_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        existing_content = None
        if file_path.exists():
            try:
                existing_content = file_path.read_text(encoding="utf-8")
            except Exception:
                existing_content = None
        if existing_content != content:
            file_path.write_text(content, encoding="utf-8")
        written_files[filename] = file_path

    snapshot_path = target_dir / PROJECT_SNAPSHOT_PATH.name
    try:
        snapshot_payload = dict(PROJECT_SNAPSHOT if isinstance(PROJECT_SNAPSHOT, dict) else {})
        snapshot_payload["generated_at"] = datetime.now(timezone.utc).isoformat()
        snapshot_payload["target_site_base_url"] = TARGET_SITE_BASE_URL
        snapshot_path.write_text(json.dumps(snapshot_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written_files[snapshot_path.name] = snapshot_path
    except Exception:
        logger.exception("Failed to write project snapshot companion file")
    return written_files

EMBEDDED_COMPANION_PROCESS: Optional[subprocess.Popen[Any]] = None


def wait_for_embedded_companion(timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Optional[Exception] = None
    while time.time() < deadline:
        process = EMBEDDED_COMPANION_PROCESS
        if process is not None and process.poll() is not None:
            raise RuntimeError("تعذر تشغيل خادم الاقتران الداخلي: process exited unexpectedly")
        try:
            response = requests.get(f"{INTERNAL_PAIRING_BASE_URL}/health", timeout=3)
            if response.ok:
                return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(1.0)
    if last_error is not None:
        raise RuntimeError(f"تعذر تشغيل خادم الاقتران الداخلي: {last_error}") from last_error
    raise RuntimeError("تعذر تشغيل خادم الاقتران الداخلي خلال المهلة المحددة")


def stop_embedded_companion_process() -> None:
    global EMBEDDED_COMPANION_PROCESS, EMBEDDED_COMPANION_LOG_HANDLE
    process = EMBEDDED_COMPANION_PROCESS
    EMBEDDED_COMPANION_PROCESS = None
    if process is not None and process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=15)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass
    if EMBEDDED_COMPANION_LOG_HANDLE is not None:
        try:
            EMBEDDED_COMPANION_LOG_HANDLE.close()
        except Exception:
            pass
        EMBEDDED_COMPANION_LOG_HANDLE = None


def ensure_project_runtime_dependencies() -> None:
    if shutil.which("node") is None:
        raise RuntimeError("Node.js غير متوفر على الاستضافة، لذلك محرك واتساب المحلي لن يعمل.")

    project_index_file = BASE_DIR / "index.js"
    if not project_index_file.exists():
        raise RuntimeError("تعذر العثور على index.js داخل المشروع الرئيسي.")

    required_paths = [
        BASE_DIR / "node_modules" / "express",
        BASE_DIR / "node_modules" / "fs-extra",
        BASE_DIR / "node_modules" / "pino",
        BASE_DIR / "node_modules" / "mongodb",
        BASE_DIR / "node_modules" / "@whiskeysockets" / "baileys",
    ]
    if all(path.exists() for path in required_paths):
        return

    if shutil.which("npm") is None:
        raise RuntimeError("npm غير متوفر على الاستضافة، لذلك لا يمكن تثبيت مكتبات محرك واتساب.")

    logger.info("Installing main project npm dependencies...")
    subprocess.check_call(
        ["npm", "install", "--omit=dev", "--legacy-peer-deps", "--no-audit", "--no-fund"],
        cwd=str(BASE_DIR),
    )


def ensure_embedded_companion_dependencies() -> None:
    if shutil.which("node") is None:
        raise RuntimeError("Node.js غير متوفر على الاستضافة، لذلك خادم الاقتران الداخلي لن يعمل.")
    if shutil.which("npm") is None:
        raise RuntimeError("npm غير متوفر على الاستضافة، لذلك لا يمكن تثبيت مكتبات خادم الاقتران.")

    ensure_embedded_companion_files(EMBEDDED_COMPANION_DIR)

    embedded_node_modules = EMBEDDED_COMPANION_DIR / "node_modules"
    root_node_modules = BASE_DIR / "node_modules"
    if not embedded_node_modules.exists() and root_node_modules.exists():
        try:
            os.symlink(root_node_modules, embedded_node_modules, target_is_directory=True)
        except FileExistsError:
            pass
        except Exception:
            logger.exception("Failed to link root node_modules into embedded runtime")

    required_paths = [
        EMBEDDED_COMPANION_DIR / "node_modules" / "express",
        EMBEDDED_COMPANION_DIR / "node_modules" / "fs-extra",
        EMBEDDED_COMPANION_DIR / "node_modules" / "pino",
        EMBEDDED_COMPANION_DIR / "node_modules" / "mongodb",
        EMBEDDED_COMPANION_DIR / "node_modules" / "@whiskeysockets" / "baileys",
    ]
    if all(path.exists() for path in required_paths):
        return

    logger.info("Installing embedded companion npm dependencies...")
    subprocess.check_call(
        ["npm", "install", "--omit=dev", "--no-audit", "--no-fund"],
        cwd=str(EMBEDDED_COMPANION_DIR),
    )



def start_embedded_companion_process() -> bool:
    global EMBEDDED_COMPANION_PROCESS, PAIRING_RUNTIME_DISABLED_REASON, EMBEDDED_COMPANION_LOG_HANDLE
    if EMBEDDED_COMPANION_PROCESS is not None and EMBEDDED_COMPANION_PROCESS.poll() is None:
        return True

    ensure_embedded_companion_files(EMBEDDED_COMPANION_DIR)

    base_env = os.environ.copy()
    base_env["PAIRING_SERVER_PORT"] = str(COMPANION_PORT)
    base_env["COMPANION_PORT"] = str(COMPANION_PORT)
    base_env["APP_PORT"] = str(COMPANION_PORT)
    base_env["PORT"] = str(COMPANION_PORT)
    base_env.setdefault("LOG_LEVEL", base_env.get("LOG_LEVEL", "silent"))
    base_env.setdefault("MONGODB_URI", MONGODB_URI)
    base_env.setdefault("MONGO_URL", MONGODB_URI)
    base_env.setdefault("MONGODB_DB_NAME", MONGODB_DB_NAME)
    base_env.setdefault("MONGODB_SESSIONS_COLLECTION", MONGODB_SESSIONS_COLLECTION)

    launch_targets = [
        {
            "label": "main-project-runtime",
            "command": ["node", "index.js"],
            "cwd": BASE_DIR,
            "prepare": ensure_project_runtime_dependencies,
            "drop_telegram_token": True,
        },
        {
            "label": "embedded-runtime",
            "command": ["node", "server.js"],
            "cwd": EMBEDDED_COMPANION_DIR,
            "prepare": ensure_embedded_companion_dependencies,
            "drop_telegram_token": False,
        },
    ]

    last_error: Optional[Exception] = None
    for target in launch_targets:
        stop_embedded_companion_process()
        try:
            target["prepare"]()
            env = dict(base_env)
            if target.get("drop_telegram_token"):
                env["BOT_TOKEN"] = ""
                env["TELEGRAM_BOT_TOKEN"] = ""
                env["ENABLE_TELEGRAM_PAIR_BOT"] = "false"
                env["DISABLE_TELEGRAM_BOT"] = "true"
            EMBEDDED_COMPANION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            EMBEDDED_COMPANION_LOG_HANDLE = open(EMBEDDED_COMPANION_LOG_PATH, "ab")
            EMBEDDED_COMPANION_PROCESS = subprocess.Popen(
                target["command"],
                cwd=str(target["cwd"]),
                env=env,
                stdout=EMBEDDED_COMPANION_LOG_HANDLE,
                stderr=subprocess.STDOUT,
            )
            wait_for_embedded_companion()
            PAIRING_RUNTIME_DISABLED_REASON = ""
            logger.info("Started local WhatsApp runtime using %s", target["label"])
            return True
        except Exception as exc:
            last_error = exc
            PAIRING_RUNTIME_DISABLED_REASON = f"{target['label']}: {exc}"
            logger.exception("Failed to start %s", target["label"])
            stop_embedded_companion_process()

    if last_error is not None:
        PAIRING_RUNTIME_DISABLED_REASON = str(last_error)
    return False


atexit.register(stop_embedded_companion_process)


def main():
    global PAIRING_RUNTIME_DISABLED_REASON
    logger.info("Starting Telegram bot")
    print("[boot] Starting Telegram bot...", flush=True)

    if not re.fullmatch(r"\d{6,}:[A-Za-z0-9_-]{20,}", BOT_TOKEN):
        raise RuntimeError("BOT_TOKEN format looks invalid. Please verify the token value.")

    SETTINGS["pair_code_api_url"] = resolve_pair_code_api_url().rstrip("/")
    save_settings()
    ensure_embedded_companion_files(EMBEDDED_COMPANION_DIR)
    embedded_companion_started = start_embedded_companion_process()
    if not embedded_companion_started:
        raise RuntimeError(
            "تعذر تشغيل محرك واتساب المحلي داخل نفس المشروع. تأكد أن الاستضافة تدعم Node.js و npm مع Python وأن npm install تم بنجاح أثناء البناء.\n"
            f"سبب الخطأ: {PAIRING_RUNTIME_DISABLED_REASON or 'unknown error'}"
        )

    PAIRING_RUNTIME_DISABLED_REASON = ""
    health_server = start_healthcheck_server()
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("emoji", user_emoji_command))
    app.add_handler(CommandHandler("drf", drf_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("dev", dev_command))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    try:
        app.run_polling(drop_pending_updates=True)
    except Conflict:
        logger.error(
            "Another instance is already running for this token. Stop the old process/server before starting this one."
        )
        raise SystemExit(1)
    finally:
        stop_embedded_companion_process()
        if health_server is not None:
            health_server.shutdown()
            health_server.server_close()


if __name__ == "__main__":
    main()
