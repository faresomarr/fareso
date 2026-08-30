#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
بوت تيليجرام لتنزيل فيديوهات تيك توك وإنستجرام مع لوحة مطور، إذاعة، واشتراك إجباري.

أهم التحسينات في هذه النسخة:
- تقليل الضغط على الاستضافة المجانية: البوت لا يحمل فيديو المعاينة محلياً لكل طلب.
- محاولة إرسال روابط الفيديو/الصوت مباشرة عبر تيليجرام أولاً لتخفيف استهلاك الرام والمعالج.
- دعم تنزيل فيديوهات إنستجرام (Reels / Posts) بدون الاعتماد الإجباري على RapidAPI مع بدائل احتياطية.
- حصر التحميل المحلي الثقيل داخل Semaphore لتجنب توقف البوت عند الضغط على HD.
- إعادة تشغيل تلقائية عند حدوث خطأ قاتل أثناء التشغيل.
- حفظ الإعدادات والمستخدمين في ملفات JSON.
- لوحة مطور داخل البوت:
  * تغيير رسالة /start
  * إذاعة للمشتركين
  * تفعيل/تعطيل الاشتراك الإجباري
  * عرض الإحصائيات
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


# ==============================
# Bootstrap dependencies
# ==============================
def _ensure_package(import_name: str, pip_name: str) -> None:
    try:
        importlib.import_module(import_name)
        return
    except ImportError:
        print(f"[bootstrap] Installing missing package: {pip_name}", flush=True)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--no-cache-dir", pip_name]
        )
        importlib.import_module(import_name)


for _import_name, _pip_name in (
    ("requests", "requests>=2.31.0"),
    ("bs4", "beautifulsoup4>=4.12.0"),
    ("telegram", 'python-telegram-bot[webhooks]==21.6'),
    ("urllib3", "urllib3>=2.0.0"),
    ("yt_dlp", "yt-dlp>=2025.1.15"),
):
    _ensure_package(_import_name, _pip_name)


import requests
import yt_dlp
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.error import BadRequest, Forbidden, NetworkError, TimedOut
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from urllib3.util.retry import Retry


# ==============================
# الإعدادات الأساسية
# ==============================
BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "8487375085:AAGdJdtFSgdT8YUFS7L3vuQh5deQwhThQSg",
).strip()
DEVELOPER_ID = int(os.getenv("DEVELOPER_ID", "7231690686") or "7231690686")

SOURCE_PREFIX = "tiktokio.com"
SOURCE_SITE = "https://tiktokio.com/"
SOURCE_API = "https://tiktokio.com/api/v1/tk/html"
DEFAULT_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/135.0 Safari/537.36"
)

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "").strip()
INSTAGRAM_RAPIDAPI_HOST = os.getenv(
    "INSTAGRAM_RAPIDAPI_HOST",
    "instagram-reels-downloader-api.p.rapidapi.com",
).strip() or "instagram-reels-downloader-api.p.rapidapi.com"
INSTAGRAM_RAPIDAPI_ENDPOINT = os.getenv(
    "INSTAGRAM_RAPIDAPI_ENDPOINT",
    "https://instagram-reels-downloader-api.p.rapidapi.com/download",
).strip() or "https://instagram-reels-downloader-api.p.rapidapi.com/download"
INSTAGRAM_SESSIONID = os.getenv("INSTAGRAM_SESSIONID", "").strip()
INSTAGRAM_COOKIES = os.getenv("INSTAGRAM_COOKIES", "").strip()
INSTAGRAM_COOKIES_FILE = os.getenv("INSTAGRAM_COOKIES_FILE", "").strip()
INSTAGRAM_COOKIES_FROM_BROWSER = os.getenv("INSTAGRAM_COOKIES_FROM_BROWSER", "").strip()
INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID", "936619743392459").strip() or "936619743392459"

HOST = os.getenv("HOST", "0.0.0.0").strip() or "0.0.0.0"
PORT = int(os.getenv("PORT", "8080"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN", "").strip()
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/telegram").strip() or "/telegram"
USE_WEBHOOK = os.getenv("USE_WEBHOOK", "").strip().lower() in {"1", "true", "yes", "on"}

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "25"))
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "60"))
MAX_DOWNLOAD_MB = int(os.getenv("MAX_DOWNLOAD_MB", "48"))
MAX_LOCAL_UPLOAD_MB = int(os.getenv("MAX_LOCAL_UPLOAD_MB", "18"))
DOWNLOAD_STORE_TTL = int(os.getenv("DOWNLOAD_STORE_TTL", "7200"))
LOCAL_DOWNLOAD_CONCURRENCY = int(os.getenv("LOCAL_DOWNLOAD_CONCURRENCY", "1"))
LOW_QUALITY_MAX_WIDTH = int(os.getenv("LOW_QUALITY_MAX_WIDTH", "640"))
LOW_QUALITY_VIDEO_BITRATE_K = int(os.getenv("LOW_QUALITY_VIDEO_BITRATE_K", "650"))
LOW_QUALITY_AUDIO_BITRATE_K = int(os.getenv("LOW_QUALITY_AUDIO_BITRATE_K", "96"))
LOW_QUALITY_FPS = int(os.getenv("LOW_QUALITY_FPS", "24"))
LOW_QUALITY_CRF = int(os.getenv("LOW_QUALITY_CRF", "30"))
FETCH_CACHE_TTL = int(os.getenv("FETCH_CACHE_TTL", "900"))
WARMUP_INTERVAL_SECONDS = int(os.getenv("WARMUP_INTERVAL_SECONDS", "900"))
RESTART_DELAY_SECONDS = int(os.getenv("RESTART_DELAY_SECONDS", "8"))

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", ".bot_storage")).resolve()
USERS_FILE = STORAGE_DIR / "users.json"
SETTINGS_FILE = STORAGE_DIR / "settings.json"

START_MESSAGE_DEFAULT = (
    "أهلاً بيك 👋\n\n"
    "ابعت رابط تيك توك أو إنستجرام وأنا هجهزهولك فوراً.\n\n"
    "المتاح حالياً:\n"
    "• TikTok: تحميل فيديو بأعلى جودة متاحة HD\n"
    "• TikTok: تحميل الملف الصوتي MP3\n"
    "• Instagram: تحميل الفيديو مباشرة حتى لو لم يتم ضبط RapidAPI\n\n"
    "لو واجهت رابط لا يعمل، ابعته مرة ثانية وسأحاول من جديد."
)

FORCE_SUB_TEXT_DEFAULT = (
    "لازم تشترك أولاً في القناة/القناة المطلوبة ثم اضغط تحقق ✅"
)

RAW_COOKIES = [
    {
        "name": "__eoi",
        "value": "ID=6ff0e30c63a9450a:T=1777480916:RT=1777480916:S=AA-AfjZWlh1Lu7Eg1qpsevX14nDR",
        "domain": ".tiktokio.com",
        "path": "/",
    },
    {
        "name": "__gads",
        "value": "ID=72bd49fdd6164587:T=1777480916:RT=1777480916:S=ALNI_MbRi_jU4Hahc7-PGbYeovxzpo_bBg",
        "domain": ".tiktokio.com",
        "path": "/",
    },
    {
        "name": "__gpi",
        "value": "UID=000013da5adbd05c:T=1777480916:RT=1777480916:S=ALNI_MZr0VQ2NF5j3GmcXX8CP3aGd9jCtw",
        "domain": ".tiktokio.com",
        "path": "/",
    },
    {
        "name": "cf_clearance",
        "value": "wrNXzToPK1vQlgJsAO_zVXepi8tTzuo9n1yR3XP2n.o-1777480913-1.2.1.1-YOXPlWx0KxagD8jUvT0KKqyj8K9nM6fRxfBeUUKNo4DhEXKsppwMgL4zXC2uXFzM6ulFquFgwHmyx5CMzRIUZSp438eXnVhp83ICInYHWELNB94.U.9TQ8wBC9NUOjxCluvXI9RcbG2atD8V8EUkmMEjEALEPD6O8nVWR6w3kTPat1d8zGSsr0Wn306hxeazkMhKmCcgWiy3uhbS4YVDB8QLNg3yVQ2xpeK3g.dGXWHKCiTFzI7hgP5F4csOfHKXFOawgG2vmWvEKGckbZJjC2Br7_.YvHnAlYXmICVQzUKTY9BCU8rP43vZwOKefC_x0XzwwYllWDq.DWWuWeW4Yg",
        "domain": ".tiktokio.com",
        "path": "/",
    },
]


# ==============================
# السجل العام
# ==============================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("tiktok_store_bot")
APP_START_TIME = time.time()
JSON_LOCK = threading.Lock()
TIKTOK_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:vt\.tiktok\.com|vm\.tiktok\.com|m\.tiktok\.com|tiktok\.com)/\S+",
    re.IGNORECASE,
)
INSTAGRAM_URL_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:reel|reels|p|tv)/\S+",
    re.IGNORECASE,
)


# ==============================
# أدوات مساعدة عامة
# ==============================
def _should_use_webhook() -> bool:
    return bool(WEBHOOK_URL) or USE_WEBHOOK


def _normalize_webhook_path(path: str) -> str:
    path = (path or "/telegram").strip()
    if not path.startswith("/"):
        path = "/" + path
    return path


def _truncate(text: str, limit: int = 3900) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _notify_developer_sync(text: str) -> None:
    if not BOT_TOKEN or not DEVELOPER_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": DEVELOPER_ID, "text": _truncate(text)},
            timeout=20,
        )
    except Exception:
        logger.exception("Could not notify developer via direct API call")


def ensure_storage() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        USERS_FILE.write_text("{}", encoding="utf-8")
    if not SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text(
            json.dumps(
                {
                    "start_message": START_MESSAGE_DEFAULT,
                    "force_sub_enabled": False,
                    "force_sub_chat_id": "",
                    "force_sub_url": "",
                    "force_sub_text": FORCE_SUB_TEXT_DEFAULT,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def _load_json(path: Path, default: Any) -> Any:
    try:
        with JSON_LOCK:
            if not path.exists():
                return default
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Could not load JSON file: %s", path)
        return default


def _save_json(path: Path, data: Any) -> None:
    with JSON_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)


def get_settings(context: ContextTypes.DEFAULT_TYPE | None = None) -> dict[str, Any]:
    if context and "settings" in context.bot_data:
        return context.bot_data["settings"]
    ensure_storage()
    return _load_json(
        SETTINGS_FILE,
        {
            "start_message": START_MESSAGE_DEFAULT,
            "force_sub_enabled": False,
            "force_sub_chat_id": "",
            "force_sub_url": "",
            "force_sub_text": FORCE_SUB_TEXT_DEFAULT,
        },
    )


def save_settings(context: ContextTypes.DEFAULT_TYPE, settings: dict[str, Any]) -> None:
    context.bot_data["settings"] = settings
    _save_json(SETTINGS_FILE, settings)


def get_users() -> dict[str, Any]:
    ensure_storage()
    return _load_json(USERS_FILE, {})


def save_users(data: dict[str, Any]) -> None:
    _save_json(USERS_FILE, data)


def is_developer(user_id: int | None) -> bool:
    return bool(user_id and DEVELOPER_ID and user_id == DEVELOPER_ID)


def format_uptime(seconds: int) -> str:
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}ي")
    if hours:
        parts.append(f"{hours}س")
    if minutes:
        parts.append(f"{minutes}د")
    parts.append(f"{secs}ث")
    return " ".join(parts)


def register_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    users = context.bot_data.setdefault("users", get_users())
    key = str(user.id)
    users[key] = {
        "id": user.id,
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "full_name": user.full_name,
        "username": user.username or "",
        "is_bot": bool(user.is_bot),
        "last_seen": int(time.time()),
    }
    save_users(users)


def _cleanup_expired_results(context: ContextTypes.DEFAULT_TYPE) -> None:
    store = context.bot_data.setdefault("downloads", {})
    now = time.time()
    expired_keys = [
        key for key, value in store.items() if now - float(value.get("created_at", now)) > DOWNLOAD_STORE_TTL
    ]
    for key in expired_keys:
        store.pop(key, None)


# ==============================
# TikTok استخراج
# ==============================
@dataclass
class TikTokResult:
    source_url: str
    title: str
    cover_url: str | None
    preview_video_url: str | None
    no_watermark_url: str | None
    hd_url: str | None
    mp3_url: str | None
    watermark_url: str | None
    raw_links: dict[str, str]


@dataclass
class MediaProbe:
    final_url: str
    content_type: str
    content_length: int | None


class TikTokIOClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_lock = threading.Lock()
        self._warmup_lock = threading.Lock()
        self._last_warmup = 0.0
        self._reset_session()

    def _reset_session(self) -> None:
        retry = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=1,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("HEAD", "GET", "POST"),
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self.session.headers.clear()
        self.session.headers.update(
            {
                "User-Agent": DEFAULT_BROWSER_UA,
                "Origin": SOURCE_SITE.rstrip("/"),
                "Referer": SOURCE_SITE,
                "Accept": "text/plain, text/html, application/json, */*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Connection": "keep-alive",
            }
        )
        self.session.cookies.clear()
        self._load_cookies(RAW_COOKIES)
        self._load_instagram_runtime_cookies()

    def _load_cookies(self, cookies: list[dict[str, Any]]) -> None:
        for cookie in cookies:
            self.session.cookies.set(
                name=cookie["name"],
                value=str(cookie["value"]),
                domain=cookie.get("domain", ".tiktokio.com"),
                path=cookie.get("path", "/"),
            )

    @staticmethod
    def _parse_cookie_header(cookie_header: str) -> dict[str, str]:
        parsed: dict[str, str] = {}
        for part in (cookie_header or "").split(";"):
            if "=" not in part:
                continue
            name, value = part.split("=", 1)
            name = name.strip()
            value = value.strip()
            if name and value:
                parsed[name] = value
        return parsed

    @classmethod
    def _read_instagram_cookie_file(cls, cookie_file: str) -> dict[str, str]:
        path = Path(cookie_file).expanduser()
        if not path.exists():
            return {}

        text = path.read_text(encoding="utf-8", errors="ignore")
        if "\t" not in text and "sessionid=" in text:
            return cls._parse_cookie_header(text)

        parsed: dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            domain, _include_subdomains, _path, _secure, _expires, name, value = parts[:7]
            if "instagram.com" not in domain.lower():
                continue
            if name and value:
                parsed[name] = value
        return parsed

    def _load_instagram_runtime_cookies(self) -> None:
        cookie_map: dict[str, str] = {}

        if INSTAGRAM_COOKIES_FILE:
            try:
                cookie_map.update(self._read_instagram_cookie_file(INSTAGRAM_COOKIES_FILE))
            except Exception as exc:
                logger.warning("Could not load Instagram cookie file: %s", exc)

        if INSTAGRAM_COOKIES:
            cookie_map.update(self._parse_cookie_header(INSTAGRAM_COOKIES))

        if INSTAGRAM_SESSIONID and "sessionid" not in cookie_map:
            cookie_map["sessionid"] = INSTAGRAM_SESSIONID

        for name, value in cookie_map.items():
            if not name or not value:
                continue
            self.session.cookies.set(
                name=name,
                value=str(value),
                domain=".instagram.com",
                path="/",
            )

    def _create_instagram_cookiefile_for_ytdlp(self) -> str | None:
        persistent_cookie_path = Path(INSTAGRAM_COOKIES_FILE).expanduser() if INSTAGRAM_COOKIES_FILE else None
        if persistent_cookie_path and persistent_cookie_path.exists():
            return str(persistent_cookie_path)

        instagram_cookies = [
            cookie
            for cookie in self.session.cookies
            if "instagram.com" in (cookie.domain or "").lower()
        ]
        if not instagram_cookies:
            return None

        fd, temp_path = tempfile.mkstemp(prefix="instagram_cookie_", suffix=".txt")
        os.close(fd)
        cookie_file = Path(temp_path)
        with cookie_file.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("# Netscape HTTP Cookie File\n")
            for cookie in instagram_cookies:
                domain = cookie.domain or ".instagram.com"
                include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
                secure = "TRUE" if bool(getattr(cookie, "secure", False)) else "FALSE"
                expires = str(int(cookie.expires or 0))
                handle.write(
                    "\t".join(
                        [
                            domain,
                            include_subdomains,
                            cookie.path or "/",
                            secure,
                            expires,
                            cookie.name,
                            cookie.value,
                        ]
                    )
                    + "\n"
                )
        return str(cookie_file)

    def _warmup(self, *, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_warmup < WARMUP_INTERVAL_SECONDS:
            return

        with self._warmup_lock:
            now = time.time()
            if not force and now - self._last_warmup < WARMUP_INTERVAL_SECONDS:
                return
            try:
                self.session.get(SOURCE_SITE, timeout=12)
                self._last_warmup = now
            except Exception:
                logger.debug("Warmup request failed", exc_info=True)

    def _get_cached_result(self, tiktok_url: str) -> TikTokResult | None:
        with self._cache_lock:
            cached = self._cache.get(tiktok_url)
            if not cached:
                return None
            if time.time() - float(cached.get("saved_at", 0)) > FETCH_CACHE_TTL:
                self._cache.pop(tiktok_url, None)
                return None
            result = cached.get("result")
            return result if isinstance(result, TikTokResult) else None

    def _set_cached_result(self, tiktok_url: str, result: TikTokResult) -> None:
        with self._cache_lock:
            self._cache[tiktok_url] = {"saved_at": time.time(), "result": result}
            expired = [
                key
                for key, value in self._cache.items()
                if time.time() - float(value.get("saved_at", 0)) > FETCH_CACHE_TTL
            ]
            for key in expired:
                self._cache.pop(key, None)

    def probe_media(self, url: str) -> MediaProbe:
        content_type = ""
        content_length: int | None = None
        final_url = url

        try:
            response = self.session.head(
                url,
                allow_redirects=True,
                timeout=min(15, DOWNLOAD_TIMEOUT),
                headers=self._build_request_headers(url),
            )
            response.raise_for_status()
            final_url = response.url or url
            content_type = (response.headers.get("Content-Type") or "").lower()
            header = (response.headers.get("Content-Length") or "").strip()
            if header.isdigit():
                content_length = int(header)
        except Exception:
            logger.debug("HEAD probe failed for media url", exc_info=True)

        if content_length is None or not content_type or "text/html" in content_type:
            try:
                response = self.session.get(
                    final_url,
                    stream=True,
                    allow_redirects=True,
                    timeout=min(20, DOWNLOAD_TIMEOUT),
                    headers=self._build_request_headers(final_url, {"Range": "bytes=0-0"}),
                )
                response.raise_for_status()
                final_url = response.url or final_url
                content_type = (response.headers.get("Content-Type") or content_type or "").lower()
                content_range = response.headers.get("Content-Range") or ""
                if "/" in content_range:
                    total = content_range.rsplit("/", 1)[-1].strip()
                    if total.isdigit():
                        content_length = int(total)
                if content_length is None:
                    header = (response.headers.get("Content-Length") or "").strip()
                    if header.isdigit():
                        content_length = int(header)
                response.close()
            except Exception:
                logger.debug("Range probe failed for media url", exc_info=True)

        return MediaProbe(final_url=final_url, content_type=content_type, content_length=content_length)

    @staticmethod
    def _extract_html_payload(response_text: str) -> str:
        raw_text = (response_text or "").strip()
        if not raw_text:
            return ""

        if raw_text.startswith("{") and raw_text.endswith("}"):
            try:
                data = json.loads(raw_text)
                if isinstance(data, dict):
                    direct_message = data.get("message") or data.get("error")
                    for key in ("html", "data", "result", "content"):
                        value = data.get(key)
                        if isinstance(value, str) and value.strip():
                            return value.strip()
                        if isinstance(value, dict):
                            for inner_key in ("html", "content", "result"):
                                inner_value = value.get(inner_key)
                                if isinstance(inner_value, str) and inner_value.strip():
                                    return inner_value.strip()
                    if direct_message:
                        raise RuntimeError(str(direct_message))
            except json.JSONDecodeError:
                pass
        return raw_text

    @staticmethod
    def _extract_text_error(html: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")
        for selector in (".tk-error", ".alert-danger", ".error", ".text-danger"):
            err = soup.select_one(selector)
            if err:
                message = err.get_text(" ", strip=True)
                if message:
                    return message
        return None

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join((text or "").split())

    @staticmethod
    def _absolute_url(url: str | None) -> str | None:
        if not url:
            return None
        url = url.strip()
        if not url:
            return None
        if url.startswith("//"):
            return "https:" + url
        return requests.compat.urljoin(SOURCE_SITE, url)

    @staticmethod
    def _canonical_instagram_url(url: str) -> str:
        raw = (url or "").strip()
        if not raw:
            return ""
        parts = urlsplit(raw)
        cleaned_path = parts.path.rstrip("/") + "/"
        return urlunsplit((parts.scheme or "https", parts.netloc, cleaned_path, "", ""))

    @staticmethod
    def _build_request_headers(
        url: str,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        lowered = (url or "").lower()
        headers = {
            "User-Agent": DEFAULT_BROWSER_UA,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Connection": "keep-alive",
        }
        if any(host in lowered for host in ("instagram.com", "cdninstagram.com", "fbcdn.net")):
            headers["Referer"] = "https://www.instagram.com/"
            headers["Origin"] = "https://www.instagram.com"
            # إضافة رؤوس إضافية لتجاوز حماية 403 في بعض روابط CDN
            headers["Sec-Fetch-Dest"] = "video"
            headers["Sec-Fetch-Mode"] = "no-cors"
            headers["Sec-Fetch-Site"] = "cross-site"
        else:
            headers["Referer"] = SOURCE_SITE
            headers["Origin"] = SOURCE_SITE.rstrip("/")
        if extra_headers:
            headers.update(extra_headers)
        return headers

    @staticmethod
    def _decode_escaped_url(value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            return ""
        cleaned = cleaned.replace(r"\/", "/").replace(r"\u0026", "&").replace("&amp;", "&")
        try:
            return json.loads(f'"{cleaned}"')
        except Exception:
            return cleaned

    def fetch(self, tiktok_url: str) -> TikTokResult:
        cleaned_url = tiktok_url.strip()
        cached = self._get_cached_result(cleaned_url)
        if cached:
            return cached

        last_error: Exception | None = None

        for attempt in range(1, 4):
            try:
                self._warmup()
                response = self.session.post(
                    SOURCE_API,
                    json={"vid": cleaned_url, "prefix": SOURCE_PREFIX},
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()

                html = self._extract_html_payload(response.text)
                if not html:
                    raise RuntimeError("الموقع أعاد نتيجة فارغة. غالباً الجلسة أو الكوكيز تحتاج تحديث.")

                if "tk-error" in html.lower():
                    raise RuntimeError(self._extract_text_error(html) or "تعذر جلب بيانات الرابط من المصدر.")

                result = self._parse_html(cleaned_url, html)
                if not any([result.no_watermark_url, result.hd_url, result.mp3_url]):
                    raise RuntimeError("تمت قراءة الصفحة لكن لم يتم العثور على روابط تنزيل صالحة.")
                self._set_cached_result(cleaned_url, result)
                return result
            except Exception as exc:
                last_error = exc
                logger.warning("Fetch attempt %s/3 failed: %s", attempt, exc)
                if attempt < 3:
                    time.sleep(attempt)
                    self._reset_session()

        raise RuntimeError(f"فشل جلب روابط التحميل بعد عدة محاولات: {last_error}")

    def _parse_html(self, source_url: str, html: str) -> TikTokResult:
        soup = BeautifulSoup(html, "html.parser")

        title = "مقطع تيك توك"
        for selector in ("h1", "h2", "h3", "title", 'meta[property="og:title"]'):
            node = soup.select_one(selector)
            if not node:
                continue
            value = node.get("content") if node.name == "meta" else node.get_text(" ", strip=True)
            if value:
                title = self._normalize_text(value) or title
                break

        cover_url = None
        for selector in ('meta[property="og:image"]', "img", "video[poster]"):
            node = soup.select_one(selector)
            if not node:
                continue
            if node.name == "meta":
                cover_url = self._absolute_url(node.get("content"))
            else:
                cover_url = self._absolute_url(node.get("src") or node.get("poster"))
            if cover_url:
                break

        preview_video_url = None
        for selector in ("video", "video source", 'meta[property="og:video"]'):
            node = soup.select_one(selector)
            if not node:
                continue
            if node.name == "meta":
                preview_video_url = self._absolute_url(node.get("content"))
            else:
                preview_video_url = self._absolute_url(node.get("src"))
            if preview_video_url:
                break

        raw_links: dict[str, str] = {}
        for a in soup.find_all("a", href=True):
            href = self._absolute_url(a.get("href"))
            if not href or href.lower().startswith("javascript:"):
                continue

            label_parts = [
                a.get_text(" ", strip=True),
                a.get("title", ""),
                a.get("aria-label", ""),
                a.get("download", ""),
                " ".join(a.get("class", [])),
            ]
            label = self._normalize_text(" ".join(part for part in label_parts if part))
            if not label:
                label = href
            raw_links[label] = href

        def pick_link(
            required_any: tuple[str, ...] = (),
            required_all: tuple[str, ...] = (),
            excluded: tuple[str, ...] = (),
            href_suffixes: tuple[str, ...] = (),
        ) -> str | None:
            for label, href in raw_links.items():
                lowered = label.lower()
                if required_any and not any(token in lowered for token in required_any):
                    continue
                if required_all and not all(token in lowered for token in required_all):
                    continue
                if excluded and any(token in lowered for token in excluded):
                    continue
                if href_suffixes and not href.lower().split("?", 1)[0].endswith(href_suffixes):
                    continue
                return href
            return None

        mp3_url = pick_link(
            required_any=("mp3", "audio", "music"),
            excluded=("mp4", "video"),
        ) or pick_link(href_suffixes=(".mp3",))

        hd_url = pick_link(
            required_any=("hd", "high quality", "high-quality", "original"),
            excluded=("mp3", "audio"),
        )

        no_watermark_url = pick_link(
            required_any=("without watermark", "no watermark", "download without watermark"),
            excluded=("mp3", "audio"),
        )

        watermark_url = pick_link(
            required_any=("with watermark", "watermark"),
            excluded=("without",),
        )

        if hd_url and no_watermark_url == hd_url:
            alt_no_watermark = pick_link(
                required_any=("without watermark", "no watermark", "download without watermark"),
                excluded=("hd", "high quality", "mp3", "audio"),
            )
            if alt_no_watermark:
                no_watermark_url = alt_no_watermark

        if not no_watermark_url and hd_url:
            no_watermark_url = hd_url

        if not preview_video_url:
            preview_video_url = no_watermark_url or hd_url or watermark_url

        return TikTokResult(
            source_url=source_url,
            title=title,
            cover_url=cover_url,
            preview_video_url=preview_video_url,
            no_watermark_url=no_watermark_url,
            hd_url=hd_url,
            mp3_url=mp3_url,
            watermark_url=watermark_url,
            raw_links=raw_links,
        )

    @staticmethod
    def _safe_string(value: Any, default: str = "") -> str:
        if value is None:
            return default
        text = str(value).strip()
        return text or default

    def _format_has_video(self, fmt: dict[str, Any]) -> bool:
        vcodec = self._safe_string(fmt.get("vcodec")).lower()
        return vcodec not in {"", "none"}

    def _format_has_audio(self, fmt: dict[str, Any]) -> bool:
        acodec = self._safe_string(fmt.get("acodec")).lower()
        return acodec not in {"", "none"}

    def _score_instagram_video_format(self, fmt: dict[str, Any], *, default_base: int = 0) -> int:
        fmt_url = self._safe_string(fmt.get("url"))
        if not fmt_url:
            return -10**9

        ext = self._safe_string(fmt.get("ext")).lower()
        protocol = self._safe_string(fmt.get("protocol")).lower()
        height = fmt.get("height") if isinstance(fmt.get("height"), int) else 0
        has_video = self._format_has_video(fmt)
        has_audio = self._format_has_audio(fmt)

        score = default_base + int(height or 0)
        if has_video:
            score += 400
        if has_audio:
            score += 260
        if has_video and has_audio:
            score += 500
        if ext == "mp4" or fmt_url.lower().split("?", 1)[0].endswith(".mp4"):
            score += 150
        if protocol in {"https", "http"}:
            score += 40
        if protocol.startswith("m3u8"):
            score -= 120
        if not has_video:
            score -= 1000
        elif not has_audio:
            score -= 450
        return score

    def _pick_first_video_entry(self, payload: Any) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None

        nested_entries = payload.get("entries")
        if isinstance(nested_entries, list):
            for entry in nested_entries:
                picked = self._pick_first_video_entry(entry)
                if picked:
                    return picked

        direct_url = self._safe_string(payload.get("url"))
        if direct_url and direct_url.lower().split("?", 1)[0].endswith(".mp4"):
            return payload

        formats = payload.get("formats")
        if isinstance(formats, list):
            for fmt in formats:
                if not isinstance(fmt, dict):
                    continue
                fmt_url = self._safe_string(fmt.get("url"))
                ext = self._safe_string(fmt.get("ext")).lower()
                vcodec = self._safe_string(fmt.get("vcodec")).lower()
                if fmt_url and (ext == "mp4" or fmt_url.lower().split("?", 1)[0].endswith(".mp4") or vcodec not in {"", "none"}):
                    return payload
        return None

    def _extract_instagram_result_from_ytdlp(self, source_url: str, info: Any) -> TikTokResult:
        entry = self._pick_first_video_entry(info)
        if not entry:
            raise RuntimeError("yt-dlp لم يجد فيديو داخل رابط Instagram.")

        raw_links: dict[str, str] = {}
        ranked_formats: list[tuple[int, str]] = []
        seen_urls: set[str] = set()

        def add_candidate(label: str, fmt: dict[str, Any], *, default_base: int = 0) -> None:
            candidate_url = self._safe_string(fmt.get("url"))
            if not candidate_url or candidate_url in seen_urls:
                return
            score = self._score_instagram_video_format(fmt, default_base=default_base)
            if score <= -10**8:
                return
            seen_urls.add(candidate_url)
            raw_links[label] = candidate_url
            ranked_formats.append((score, candidate_url))

        direct_url = self._safe_string(entry.get("url"))
        if direct_url:
            add_candidate(
                "instagram_direct",
                {
                    "url": direct_url,
                    "ext": entry.get("ext"),
                    "height": entry.get("height"),
                    "protocol": entry.get("protocol"),
                    "vcodec": entry.get("vcodec"),
                    "acodec": entry.get("acodec"),
                },
                default_base=200,
            )

        requested_formats = entry.get("requested_formats")
        if isinstance(requested_formats, list):
            for index, fmt in enumerate(requested_formats, start=1):
                if not isinstance(fmt, dict):
                    continue
                add_candidate(f"instagram_requested_{index}", fmt, default_base=120)

        formats = entry.get("formats")
        if isinstance(formats, list):
            for index, fmt in enumerate(formats, start=1):
                if not isinstance(fmt, dict):
                    continue
                add_candidate(f"instagram_format_{index}", fmt)

        video_url = max(ranked_formats, key=lambda item: item[0])[1] if ranked_formats else ""
        if not video_url:
            raise RuntimeError("yt-dlp لم يرجع رابط فيديو مباشر صالح.")

        cover_url = self._safe_string(entry.get("thumbnail"))
        thumbnails = entry.get("thumbnails")
        if not cover_url and isinstance(thumbnails, list):
            for thumb in reversed(thumbnails):
                if not isinstance(thumb, dict):
                    continue
                candidate_thumb = self._safe_string(thumb.get("url"))
                if candidate_thumb:
                    cover_url = candidate_thumb
                    break

        title = self._normalize_text(
            self._safe_string(
                entry.get("title")
                or entry.get("description")
                or (info.get("title") if isinstance(info, dict) else "")
                or (info.get("description") if isinstance(info, dict) else "")
                or "Instagram Download"
            )
        ) or "Instagram Download"

        return TikTokResult(
            source_url=source_url,
            title=title,
            cover_url=cover_url or None,
            preview_video_url=video_url,
            no_watermark_url=video_url,
            hd_url=video_url,
            mp3_url=None,
            watermark_url=None,
            raw_links=raw_links,
        )

    def _build_instagram_headers(
        self,
        url: str,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        headers = self._build_request_headers(
            url,
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "X-IG-App-ID": INSTAGRAM_APP_ID,
                "X-ASBD-ID": "129477",
            },
        )
        if extra_headers:
            headers.update(extra_headers)
        return headers

    @staticmethod
    def _looks_like_video_url(url: str) -> bool:
        lowered = (url or "").lower()
        return lowered.startswith("http") and any(
            token in lowered
            for token in (
                ".mp4",
                ".m4v",
                ".mov",
                ".webm",
                "mime_type=video_mp4",
                "video_dashinit",
                "cdninstagram.com",
                "fbcdn.net",
            )
        )

    def _extract_direct_video_urls_from_text(self, text: str) -> list[str]:
        normalized = (text or "").replace(r"\/", "/").replace(r"\u0026", "&").replace("&amp;", "&")
        found: list[str] = []
        for raw_url in re.findall(r'https?://[^"\'\s<>]+', normalized):
            candidate = raw_url.strip("'\" ")
            if self._looks_like_video_url(candidate):
                found.append(candidate)
        return found

    def _collect_instagram_video_urls_from_payload(self, payload: Any, collected: list[str] | None = None) -> list[str]:
        results = collected or []
        if isinstance(payload, dict):
            for key, value in payload.items():
                key_lower = str(key).lower()
                if isinstance(value, str):
                    decoded = self._decode_escaped_url(value)
                    if self._looks_like_video_url(decoded) and (
                        key_lower in {"url", "video_url", "contenturl", "src", "playback_url"}
                        or "video" in key_lower
                    ):
                        results.append(decoded)
                    results.extend(self._extract_direct_video_urls_from_text(decoded))
                else:
                    self._collect_instagram_video_urls_from_payload(value, results)
        elif isinstance(payload, list):
            for item in payload:
                self._collect_instagram_video_urls_from_payload(item, results)
        return results

    @staticmethod
    def _rank_direct_video_url(url: str) -> int:
        lowered = (url or "").lower()
        score = 0
        if ".mp4" in lowered or "mime_type=video_mp4" in lowered:
            score += 200
        if "fbcdn.net" in lowered or "cdninstagram.com" in lowered:
            score += 150
        if ".m3u8" in lowered:
            score -= 180
        score += min(len(url or ""), 220)
        return score

    def _pick_best_direct_video_url(self, urls: list[str]) -> str:
        deduped: list[str] = []
        seen: set[str] = set()
        for url in urls:
            candidate = self._decode_escaped_url(url).strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            deduped.append(candidate)
        return max(deduped, key=self._rank_direct_video_url) if deduped else ""

    def _build_instagram_result_from_video_url(
        self,
        source_url: str,
        video_url: str,
        *,
        title: str = "Instagram Download",
        cover_url: str | None = None,
        raw_links: dict[str, str] | None = None,
    ) -> TikTokResult:
        final_title = self._normalize_text(title) or "Instagram Download"
        return TikTokResult(
            source_url=source_url,
            title=final_title,
            cover_url=cover_url or None,
            preview_video_url=video_url,
            no_watermark_url=video_url,
            hd_url=video_url,
            mp3_url=None,
            watermark_url=None,
            raw_links=raw_links or {"instagram_video": video_url},
        )

    def _fetch_instagram_via_ytdlp(self, instagram_url: str) -> TikTokResult:
        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": False,
            "extract_flat": False,
            "socket_timeout": DOWNLOAD_TIMEOUT,
            "http_headers": self._build_instagram_headers(instagram_url),
        }

        cookiefile_path = None
        persistent_cookiefile = str(Path(INSTAGRAM_COOKIES_FILE).expanduser()) if INSTAGRAM_COOKIES_FILE else ""
        try:
            cookiefile_path = self._create_instagram_cookiefile_for_ytdlp()
            if cookiefile_path:
                options["cookiefile"] = cookiefile_path

            browser_name = (INSTAGRAM_COOKIES_FROM_BROWSER or "").split(":", 1)[0].strip().lower()
            if browser_name and not cookiefile_path:
                options["cookiesfrombrowser"] = (browser_name,)

            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(instagram_url, download=False)
            return self._extract_instagram_result_from_ytdlp(instagram_url, info)
        finally:
            if cookiefile_path:
                try:
                    resolved_temp = str(Path(cookiefile_path).expanduser().resolve())
                    resolved_persistent = str(Path(persistent_cookiefile).expanduser().resolve()) if persistent_cookiefile else ""
                    if not resolved_persistent or resolved_temp != resolved_persistent:
                        Path(cookiefile_path).unlink(missing_ok=True)
                except Exception:
                    logger.debug("Could not remove temporary Instagram cookie file", exc_info=True)

    def _extract_instagram_meta_content(self, soup: BeautifulSoup, *selectors: str) -> str:
        for selector in selectors:
            node = soup.select_one(selector)
            if not node:
                continue
            value = self._safe_string(node.get("content") or node.get("href") or node.get_text(" ", strip=True))
            if value:
                return value
        return ""

    def _fetch_instagram_via_webpage(self, instagram_url: str) -> TikTokResult:
        response = self.session.get(
            instagram_url,
            headers=self._build_instagram_headers(
                instagram_url,
                {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            ),
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()

        content_type = (response.headers.get("Content-Type") or "").lower()
        if "video/" in content_type and response.url:
            return self._build_instagram_result_from_video_url(
                instagram_url,
                response.url,
                raw_links={"instagram_response_video": response.url},
            )

        html = response.text or ""
        soup = BeautifulSoup(html, "html.parser")

        title = self._extract_instagram_meta_content(
            soup,
            'meta[property="og:title"]',
            'meta[name="twitter:title"]',
            "title",
        ) or "Instagram Download"
        cover_url = self._extract_instagram_meta_content(
            soup,
            'meta[property="og:image"]',
            'meta[property="og:image:secure_url"]',
            'meta[name="twitter:image"]',
        )
        video_url = self._extract_instagram_meta_content(
            soup,
            'meta[property="og:video"]',
            'meta[property="og:video:secure_url"]',
            'meta[name="twitter:player:stream"]',
        )

        if not video_url:
            for pattern in (
                r'"video_url":"([^"]+)"',
                r'"contentUrl":"([^"]+)"',
                r'"video_versions":\\[\\{\"type\":[^\\]]*\"url\":\"([^\"]+)\"',
            ):
                match = re.search(pattern, html)
                if match:
                    video_url = self._decode_escaped_url(match.group(1))
                    if video_url:
                        break

        if not video_url:
            video_url = self._pick_best_direct_video_url(self._extract_direct_video_urls_from_text(html))

        if not video_url:
            raise RuntimeError("تعذر استخراج رابط الفيديو من صفحة Instagram مباشرة.")

        return self._build_instagram_result_from_video_url(
            instagram_url,
            video_url,
            title=title,
            cover_url=cover_url or None,
            raw_links={"instagram_meta_video": video_url},
        )

    def _fetch_instagram_via_embed_json(self, instagram_url: str) -> TikTokResult:
        endpoints = [
            f"{instagram_url}?__a=1&__d=dis",
            requests.compat.urljoin(instagram_url, "embed/captioned/"),
        ]
        last_error: Exception | None = None

        for endpoint in endpoints:
            try:
                response = self.session.get(
                    endpoint,
                    headers=self._build_instagram_headers(
                        endpoint,
                        {"Accept": "application/json,text/plain,*/*"},
                    ),
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=True,
                )
                response.raise_for_status()
                raw_text = response.text or ""
                payload_text = raw_text.split("\n", 1)[-1] if raw_text.startswith("for (;;);") else raw_text

                parsed_payload: Any = None
                if payload_text.strip().startswith(("{", "[")):
                    try:
                        parsed_payload = json.loads(payload_text)
                    except Exception:
                        parsed_payload = None

                title = "Instagram Download"
                cover_url = None
                video_url = ""
                raw_links: dict[str, str] = {"instagram_embed_endpoint": endpoint}

                if parsed_payload is not None:
                    candidates = self._collect_instagram_video_urls_from_payload(parsed_payload)
                    video_url = self._pick_best_direct_video_url(candidates)
                    if video_url:
                        raw_links["instagram_embed_video"] = video_url

                if not video_url:
                    soup = BeautifulSoup(raw_text, "html.parser")
                    title = self._extract_instagram_meta_content(
                        soup,
                        'meta[property="og:title"]',
                        'meta[name="twitter:title"]',
                        "title",
                    ) or title
                    cover_url = self._extract_instagram_meta_content(
                        soup,
                        'meta[property="og:image"]',
                        'meta[property="og:image:secure_url"]',
                        'meta[name="twitter:image"]',
                    ) or None
                    video_url = self._extract_instagram_meta_content(
                        soup,
                        'meta[property="og:video"]',
                        'meta[property="og:video:secure_url"]',
                        'meta[name="twitter:player:stream"]',
                    )
                    if not video_url:
                        video_url = self._pick_best_direct_video_url(self._extract_direct_video_urls_from_text(raw_text))
                    if video_url:
                        raw_links["instagram_embed_video"] = video_url

                if video_url:
                    return self._build_instagram_result_from_video_url(
                        instagram_url,
                        video_url,
                        title=title,
                        cover_url=cover_url,
                        raw_links=raw_links,
                    )
            except Exception as exc:
                last_error = exc

        raise RuntimeError(f"تعذر استخراج فيديو Instagram من واجهة JSON/Embed: {last_error}")

    def _fetch_instagram_via_instafix(self, instagram_url: str) -> TikTokResult:
        path_parts = urlsplit(instagram_url)
        normalized_path = (path_parts.path.rstrip("/") or "/") + "/"
        candidate_urls = [
            urlunsplit(("https", host, normalized_path, "", ""))
            for host in ("www.ddinstagram.com", "ddinstagram.com", "d.ddinstagram.com")
        ]

        last_error: Exception | None = None
        for candidate_url in candidate_urls:
            try:
                response = self.session.get(
                    candidate_url,
                    headers=self._build_request_headers(
                        candidate_url,
                        {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
                    ),
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=True,
                )
                response.raise_for_status()

                content_type = (response.headers.get("Content-Type") or "").lower()
                if "video/" in content_type and response.url:
                    return self._build_instagram_result_from_video_url(
                        instagram_url,
                        response.url,
                        raw_links={"instafix_direct": response.url, "instafix_page": candidate_url},
                    )

                html = response.text or ""
                soup = BeautifulSoup(html, "html.parser")
                title = self._extract_instagram_meta_content(
                    soup,
                    'meta[property="og:title"]',
                    'meta[name="twitter:title"]',
                    "title",
                ) or "Instagram Download"
                cover_url = self._extract_instagram_meta_content(
                    soup,
                    'meta[property="og:image"]',
                    'meta[property="og:image:secure_url"]',
                    'meta[name="twitter:image"]',
                ) or None
                video_url = self._extract_instagram_meta_content(
                    soup,
                    'meta[property="og:video"]',
                    'meta[property="og:video:secure_url"]',
                    'meta[name="twitter:player:stream"]',
                )
                if not video_url:
                    video_url = self._pick_best_direct_video_url(self._extract_direct_video_urls_from_text(html))

                if video_url:
                    return self._build_instagram_result_from_video_url(
                        instagram_url,
                        video_url,
                        title=title,
                        cover_url=cover_url,
                        raw_links={
                            "instafix_page": candidate_url,
                            "instafix_video": video_url,
                        },
                    )
            except Exception as exc:
                last_error = exc

        raise RuntimeError(f"تعذر استخراج فيديو Instagram عبر ddinstagram/InstaFix: {last_error}")

    def _extract_instagram_result(self, source_url: str, payload: Any) -> TikTokResult:
        if not isinstance(payload, dict):
            raise RuntimeError("استجابة Instagram API غير صالحة.")

        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        medias = data.get("medias") if isinstance(data, dict) else None
        if not isinstance(medias, list) or not medias:
            raise RuntimeError("لم يتم العثور على أي وسائط داخل استجابة Instagram API.")

        media_url = None
        cover_url = None
        raw_links: dict[str, str] = {}

        for index, media in enumerate(medias, start=1):
            if not isinstance(media, dict):
                continue
            candidate_url = self._safe_string(media.get("url"))
            candidate_cover = self._safe_string(
                media.get("thumbnail") or media.get("thumb") or media.get("cover") or media.get("image")
            )
            media_type = self._safe_string(media.get("type") or media.get("media_type")).lower()

            if candidate_url:
                raw_links[f"instagram_media_{index}"] = candidate_url
            if candidate_cover and not cover_url:
                cover_url = candidate_cover
            if candidate_url and (
                media_type in {"video", "reel", "mp4"}
                or candidate_url.lower().split("?", 1)[0].endswith((".mp4", ".m4v", ".mov", ".webm"))
            ):
                media_url = candidate_url
                break

        if not media_url:
            raise RuntimeError("لم يتم استخراج رابط فيديو صالح من Instagram API.")

        title = self._safe_string(
            data.get("caption") if isinstance(data, dict) else "",
            default="Instagram Download",
        )
        title = self._normalize_text(title) or "Instagram Download"

        return TikTokResult(
            source_url=source_url,
            title=title,
            cover_url=cover_url,
            preview_video_url=media_url,
            no_watermark_url=media_url,
            hd_url=media_url,
            mp3_url=None,
            watermark_url=None,
            raw_links=raw_links,
        )

    def _fetch_instagram_via_rapidapi(self, instagram_url: str) -> TikTokResult:
        if not RAPIDAPI_KEY:
            raise RuntimeError("RAPIDAPI_KEY غير مضبوط.")

        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = requests.get(
                    INSTAGRAM_RAPIDAPI_ENDPOINT,
                    params={"url": instagram_url},
                    headers={
                        "x-rapidapi-key": RAPIDAPI_KEY,
                        "x-rapidapi-host": INSTAGRAM_RAPIDAPI_HOST,
                    },
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                return self._extract_instagram_result(instagram_url, response.json())
            except Exception as exc:
                last_error = exc
                logger.warning("Instagram RapidAPI attempt %s/3 failed: %s", attempt, exc)
                if attempt < 3:
                    time.sleep(attempt)

        raise RuntimeError(f"RapidAPI فشل بعد عدة محاولات: {last_error}")

    def fetch_instagram(self, instagram_url: str) -> TikTokResult:
        cleaned_url = self._canonical_instagram_url(instagram_url)
        cache_key = f"instagram::{cleaned_url}"
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached

        has_instagram_auth = any(
            (
                INSTAGRAM_SESSIONID,
                INSTAGRAM_COOKIES,
                INSTAGRAM_COOKIES_FILE,
                INSTAGRAM_COOKIES_FROM_BROWSER,
            )
        )

        attempts: list[tuple[str, Any]] = []
        if has_instagram_auth:
            attempts.append(("yt-dlp-auth", self._fetch_instagram_via_ytdlp))

        attempts.extend(
            [
                ("webpage", self._fetch_instagram_via_webpage),
                ("embed/json", self._fetch_instagram_via_embed_json),
                ("instafix", self._fetch_instagram_via_instafix),
            ]
        )

        if not has_instagram_auth:
            attempts.append(("yt-dlp", self._fetch_instagram_via_ytdlp))

        if RAPIDAPI_KEY:
            attempts.append(("rapidapi", self._fetch_instagram_via_rapidapi))

        errors: list[str] = []
        for method_name, method in attempts:
            try:
                result = method(cleaned_url)
                self._set_cached_result(cache_key, result)
                return result
            except Exception as exc:
                logger.warning("Instagram fetch via %s failed: %s", method_name, exc)
                errors.append(f"{method_name}: {exc}")

        joined_errors = " | ".join(errors) if errors else "لا توجد تفاصيل إضافية."
        raise RuntimeError(
            "تعذر تجهيز فيديو Instagram بهذا الرابط. تأكد أنه Reel/Post عام وغير خاص، ثم جرّب مرة ثانية.\n"
            "إذا استمر الخطأ على بعض الروابط، أضف كوكيز إنستجرام عبر المتغيرات INSTAGRAM_SESSIONID أو INSTAGRAM_COOKIES أو INSTAGRAM_COOKIES_FILE.\n"
            f"تفاصيل المحاولات: {joined_errors}"
        )

    def download_file(self, url: str, suffix: str) -> Path:
        response = self.session.get(
            url,
            stream=True,
            allow_redirects=True,
            timeout=DOWNLOAD_TIMEOUT,
            headers=self._build_request_headers(url),
        )
        response.raise_for_status()

        content_length_header = (response.headers.get("Content-Length") or "0").strip()
        if content_length_header.isdigit():
            size_mb = int(content_length_header) / (1024 * 1024)
            if size_mb > MAX_DOWNLOAD_MB:
                raise RuntimeError(
                    f"حجم الملف كبير جداً ({size_mb:.1f}MB) والحد المحلي الحالي {MAX_DOWNLOAD_MB}MB."
                )

        content_type = (response.headers.get("Content-Type") or "").lower()
        # السماح ببعض المرونة لروابط إنستجرام لأنها قد تعيد HTML في حالة الخطأ، لكننا نريد محاولة القراءة أولاً
        if "text/html" in content_type and not any(h in url.lower() for h in ("instagram.com", "cdninstagram.com")):
            preview = response.text[:500]
            raise RuntimeError(f"الرابط أعاد HTML بدل الملف: {preview}")

        fd, temp_path = tempfile.mkstemp(prefix="tiktok_store_", suffix=suffix)
        os.close(fd)
        path = Path(temp_path)

        total_bytes = 0
        try:
            with path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 64):
                    if not chunk:
                        continue
                    total_bytes += len(chunk)
                    if total_bytes > MAX_DOWNLOAD_MB * 1024 * 1024:
                        raise RuntimeError(f"تم إيقاف التحميل لأن الملف تجاوز {MAX_DOWNLOAD_MB}MB.")
                    f.write(chunk)

            if total_bytes == 0:
                raise RuntimeError("تم إنشاء ملف فارغ. رابط التنزيل غير صالح أو انتهت صلاحيته.")
            return path
        except Exception:
            path.unlink(missing_ok=True)
            raise


    def convert_video_to_low_quality(self, input_path: Path) -> Path:
        if not input_path.exists():
            raise RuntimeError("ملف الفيديو المؤقت غير موجود.")

        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            raise RuntimeError("تعذر تجهيز النسخة الأقل دقة لأن ffmpeg غير متوفر على الخادم.")

        fd, temp_path = tempfile.mkstemp(prefix="tiktok_store_low_", suffix=".mp4")
        os.close(fd)
        output_path = Path(temp_path)

        scale_filter = f"scale='min({max(240, LOW_QUALITY_MAX_WIDTH)},iw)':-2,fps={max(12, LOW_QUALITY_FPS)}"
        command = [
            ffmpeg_path,
            "-y",
            "-i",
            str(input_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-vf",
            scale_filter,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            str(max(20, LOW_QUALITY_CRF)),
            "-maxrate",
            f"{max(250, LOW_QUALITY_VIDEO_BITRATE_K)}k",
            "-bufsize",
            f"{max(500, LOW_QUALITY_VIDEO_BITRATE_K * 2)}k",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            f"{max(48, LOW_QUALITY_AUDIO_BITRATE_K)}k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if completed.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
            output_path.unlink(missing_ok=True)
            details = (completed.stderr or completed.stdout or "").strip()
            details = details[-700:] if details else "لا توجد تفاصيل إضافية."
            raise RuntimeError(f"فشل ضغط الفيديو للجودة الأقل. {details}")

        return output_path


client = TikTokIOClient()
LOCAL_DOWNLOAD_SEMAPHORE: asyncio.Semaphore | None = None


# ==============================
# واجهات تيليجرام
# ==============================
def build_choice_keyboard(result: TikTokResult, ref_id: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if result.mp3_url:
        rows.append([InlineKeyboardButton("تحميل MP3", callback_data=f"dl:mp3:{ref_id}")])

    if result.hd_url or result.no_watermark_url:
        rows.append(
            [
                InlineKeyboardButton("تحميل أقل دقة", callback_data=f"dl:low:{ref_id}"),
                InlineKeyboardButton("تحميل أعلى دقة HD", callback_data=f"dl:hd:{ref_id}"),
            ]
        )

    rows.append([InlineKeyboardButton("إعادة التحضير", callback_data=f"dl:refresh:{ref_id}")])
    return InlineKeyboardMarkup(rows)


def build_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("تغيير رسالة /start", callback_data="admin:set_start")],
            [InlineKeyboardButton("إذاعة للمستخدمين", callback_data="admin:broadcast")],
            [InlineKeyboardButton("إعداد الاشتراك الإجباري", callback_data="admin:force_sub")],
            [InlineKeyboardButton("تعطيل الاشتراك الإجباري", callback_data="admin:disable_force_sub")],
            [InlineKeyboardButton("الإحصائيات", callback_data="admin:stats")],
            [InlineKeyboardButton("عرض رسالة /start الحالية", callback_data="admin:view_start")],
        ]
    )


def build_subscription_keyboard(settings: dict[str, Any]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    join_url = (settings.get("force_sub_url") or "").strip()
    if join_url:
        rows.append([InlineKeyboardButton("اشترك الآن", url=join_url)])
    rows.append([InlineKeyboardButton("تحقق من الاشتراك", callback_data="sub:verify")])
    return InlineKeyboardMarkup(rows)


def save_result(context: ContextTypes.DEFAULT_TYPE, user_id: int, result: TikTokResult) -> str:
    _cleanup_expired_results(context)
    store = context.bot_data.setdefault("downloads", {})
    ref_id = uuid.uuid4().hex[:12]
    store[ref_id] = {
        "user_id": user_id,
        "title": result.title,
        "source_url": result.source_url,
        "cover_url": result.cover_url,
        "preview_video_url": result.preview_video_url,
        "no_watermark_url": result.no_watermark_url,
        "hd_url": result.hd_url,
        "mp3_url": result.mp3_url,
        "watermark_url": result.watermark_url,
        "created_at": time.time(),
    }
    return ref_id


async def enforce_force_subscription(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    prompt: bool = True,
) -> bool:
    user = update.effective_user
    if not user or is_developer(user.id):
        return True

    settings = get_settings(context)
    if not settings.get("force_sub_enabled"):
        return True

    target_chat = str(settings.get("force_sub_chat_id") or "").strip()
    if not target_chat:
        return True

    try:
        member = await context.bot.get_chat_member(chat_id=target_chat, user_id=user.id)
        if member.status in {"member", "administrator", "creator"}:
            return True
    except Exception as exc:
        logger.warning("Force subscription check failed: %s", exc)
        # لو فحص العضوية فشل بسبب إعدادات القناة، لا نمنع المستخدم حتى لا يتعطل البوت بالكامل.
        return True

    if prompt:
        text = settings.get("force_sub_text") or FORCE_SUB_TEXT_DEFAULT
        keyboard = build_subscription_keyboard(settings)
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.reply_text(text, reply_markup=keyboard)
        elif update.effective_message:
            await update.effective_message.reply_text(text, reply_markup=keyboard)
    return False


async def send_start_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return

    settings = get_settings(context)
    text = settings.get("start_message") or START_MESSAGE_DEFAULT

    if update.effective_user and is_developer(update.effective_user.id):
        text += (
            "\n\n━━━━━━━━━━\n"
            "أوامر المطور:\n"
            "/admin - لوحة المطور\n"
            "/stats - الإحصائيات\n"
            "/ping - فحص حالة البوت\n"
            "/cancel - إلغاء العملية الحالية\n"
        )
        await update.effective_message.reply_text(text, reply_markup=build_admin_keyboard())
    else:
        await update.effective_message.reply_text(text)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    register_user(update, context)
    if not await enforce_force_subscription(update, context):
        return
    await send_start_message(update, context)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    register_user(update, context)
    if not await enforce_force_subscription(update, context):
        return
    await update.effective_message.reply_text(
        "ابعت أي رابط TikTok مباشر أو مختصر، والبوت هيطلعلك خيارات التحميل المتاحة."
    )


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("pending_action", None)
    if update.effective_message:
        await update.effective_message.reply_text("تم إلغاء العملية الحالية.")


async def ping_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user:
        return
    if not is_developer(update.effective_user.id):
        await update.effective_message.reply_text("هذا الأمر للمطور فقط.")
        return

    store = context.bot_data.get("downloads", {})
    users = context.bot_data.setdefault("users", get_users())
    mode = "Webhook" if _should_use_webhook() else "Polling"
    await update.effective_message.reply_text(
        "البوت شغال ✅\n"
        f"الوضع: {mode}\n"
        f"عدد المستخدمين: {len(users)}\n"
        f"العناصر المؤقتة: {len(store)}\n"
        f"المنفذ: {PORT}\n"
        f"مدة التشغيل: {format_uptime(int(time.time() - APP_START_TIME))}"
    )


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user:
        return
    if not is_developer(update.effective_user.id):
        await update.effective_message.reply_text("هذا الأمر للمطور فقط.")
        return

    users = context.bot_data.setdefault("users", get_users())
    settings = get_settings(context)
    store = context.bot_data.get("downloads", {})
    mode = "Webhook" if _should_use_webhook() else "Polling"
    force_sub = "مفعل" if settings.get("force_sub_enabled") else "معطل"
    force_sub_target = settings.get("force_sub_chat_id") or "غير محدد"

    await update.effective_message.reply_text(
        "إحصائيات البوت 📊\n\n"
        f"المستخدمون المسجلون: {len(users)}\n"
        f"الطلبات المؤقتة: {len(store)}\n"
        f"الاشتراك الإجباري: {force_sub}\n"
        f"القناة/المعرف: {force_sub_target}\n"
        f"الوضع: {mode}\n"
        f"مدة التشغيل: {format_uptime(int(time.time() - APP_START_TIME))}"
    )


async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user:
        return
    if not is_developer(update.effective_user.id):
        await update.effective_message.reply_text("هذا الأمر للمطور فقط.")
        return
    await update.effective_message.reply_text("لوحة المطور", reply_markup=build_admin_keyboard())


async def process_admin_pending_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    user = update.effective_user
    message = update.effective_message
    if not user or not message or not is_developer(user.id):
        return False

    pending = context.user_data.get("pending_action")
    if not pending:
        return False

    settings = get_settings(context)

    if pending == "set_start_message":
        settings["start_message"] = text.strip() or START_MESSAGE_DEFAULT
        save_settings(context, settings)
        context.user_data.pop("pending_action", None)
        await message.reply_text("تم حفظ رسالة /start الجديدة ✅", reply_markup=build_admin_keyboard())
        return True

    if pending == "set_force_sub":
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            await message.reply_text(
                "الصيغة غير صحيحة.\nأرسل في السطر الأول معرف القناة أو يوزر القناة مثل @channel\n"
                "وفي السطر الثاني رابط الانضمام إن وجد."
            )
            return True

        chat_id_value = lines[0]
        join_url = lines[1] if len(lines) > 1 else ""
        custom_text = "\n".join(lines[2:]).strip() if len(lines) > 2 else ""

        settings["force_sub_enabled"] = True
        settings["force_sub_chat_id"] = chat_id_value
        settings["force_sub_url"] = join_url
        if custom_text:
            settings["force_sub_text"] = custom_text
        save_settings(context, settings)
        context.user_data.pop("pending_action", None)
        await message.reply_text(
            "تم حفظ إعدادات الاشتراك الإجباري ✅\n"
            f"المعرف/القناة: {chat_id_value}\n"
            f"الرابط: {join_url or 'غير مضاف'}",
            reply_markup=build_admin_keyboard(),
        )
        return True

    if pending == "broadcast_message":
        context.user_data.pop("pending_action", None)
        users = context.bot_data.setdefault("users", get_users())
        total = 0
        success = 0
        failed = 0

        progress = await message.reply_text("بدأت الإذاعة... انتظر حتى تنتهي.")

        for user_id in list(users.keys()):
            total += 1
            try:
                await context.bot.send_message(chat_id=int(user_id), text=text)
                success += 1
            except Exception:
                failed += 1
            if total % 25 == 0:
                try:
                    await progress.edit_text(
                        f"جاري الإذاعة...\nتمت المحاولة: {total}\nنجح: {success}\nفشل: {failed}"
                    )
                except Exception:
                    pass
                await asyncio.sleep(0.1)

        await progress.edit_text(
            "انتهت الإذاعة ✅\n"
            f"إجمالي المحاولات: {total}\n"
            f"نجح: {success}\n"
            f"فشل: {failed}"
        )
        return True

    return False


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user or not update.effective_chat:
        return

    register_user(update, context)

    text = (update.effective_message.text or "").strip()
    if await process_admin_pending_text(update, context, text):
        return

    if not await enforce_force_subscription(update, context):
        return

    instagram_match = INSTAGRAM_URL_RE.search(text)
    tiktok_match = TIKTOK_URL_RE.search(text)

    if instagram_match:
        source_label = "Instagram"
        target_url = instagram_match.group(0)
        fetcher = client.fetch_instagram
    elif tiktok_match:
        source_label = "TikTok"
        target_url = tiktok_match.group(0)
        fetcher = client.fetch
    else:
        await update.effective_message.reply_text(
            "ابعت رابط TikTok أو Instagram صحيح علشان أقدر أجهز التحميل."
        )
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    status = await update.effective_message.reply_text(f"جاري تجهيز رابط {source_label}، انتظر لحظة...")

    try:
        result = await asyncio.to_thread(fetcher, target_url)
    except Exception as exc:
        logger.exception("Failed to fetch media link from %s", source_label)
        await status.edit_text(f"حصل خطأ أثناء معالجة رابط {source_label}:\n{exc}")
        return

    ref_id = save_result(context, update.effective_user.id, result)
    keyboard = build_choice_keyboard(result, ref_id)
    caption = result.title if len(result.title) <= 900 else result.title[:900] + "..."

    try:
        await status.delete()
    except Exception:
        logger.debug("Could not delete status message", exc_info=True)

    if result.cover_url:
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)
            await update.effective_message.reply_photo(
                photo=result.cover_url,
                caption=f"{caption}\n\nاختر طريقة التحميل من الأزرار بالأسفل:",
                reply_markup=keyboard,
            )
            return
        except Exception as exc:
            logger.warning("Remote preview photo send failed: %s", exc)

    await update.effective_message.reply_text(
        f"تم تجهيز رابط {source_label}: {caption}\n\nاختر طريقة التحميل:",
        reply_markup=keyboard,
    )


def _format_size_mb(byte_count: int | None) -> str:
    if not byte_count or byte_count <= 0:
        return "غير معروف"
    return f"{byte_count / (1024 * 1024):.1f}MB"


def _is_instagram_media_like_url(url: str) -> bool:
    lowered = (url or "").lower()
    return any(
        token in lowered
        for token in (
            "instagram.com",
            "cdninstagram.com",
            "fbcdn.net",
            "scontent",
        )
    )


async def deliver_remote_or_local(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    direct_url: str,
    kind: str,
    title: str,
    force_local_processing: bool = False,
    output_label: str | None = None,
) -> None:
    message = update.callback_query.message if update.callback_query else update.effective_message
    if not message:
        raise RuntimeError("تعذر الوصول للرسالة الحالية.")

    target_filename = output_label or ("tiktok_low.mp4" if kind == "low" else "tiktok_hd.mp4")

    # المحاولة الأولى: إرسال مباشر من الرابط لتخفيف الحمل على الاستضافة.
    if kind == "mp3":
        try:
            await message.reply_audio(
                audio=direct_url,
                caption=title,
                title=(title[:64] if title else "TikTok Audio"),
                performer="TikTok",
            )
            return
        except Exception as exc:
            logger.warning("Direct remote audio send failed: %s", exc)
    else:
        # ملاحظة: تيليجرام أحياناً يرفض روابط Instagram المباشرة بسبب حماية Hotlinking
        # لذا سنحاول الإرسال المباشر، وإذا فشل سننتقل فوراً للتحميل المحلي
        if not force_local_processing:
            try:
                await message.reply_video(video=direct_url, caption=title, supports_streaming=True)
                return
            except Exception as exc:
                logger.warning("Direct remote video send failed: %s", exc)
                if not _is_instagram_media_like_url(direct_url):
                    try:
                        await message.reply_document(document=direct_url, caption=title, filename=target_filename)
                        return
                    except Exception as doc_exc:
                        logger.warning("Direct remote document send failed: %s", doc_exc)

    # المحاولة الثانية: فحص خفيف للرابط قبل أي تحميل محلي ثقيل.
    probe = await asyncio.to_thread(client.probe_media, direct_url)
    if "text/html" in probe.content_type and not _is_instagram_media_like_url(direct_url):
        raise RuntimeError("رابط التنزيل أعاد صفحة HTML بدل ملف وسائط صالح.")

    local_limit_bytes = MAX_LOCAL_UPLOAD_MB * 1024 * 1024
    download_limit_bytes = MAX_DOWNLOAD_MB * 1024 * 1024
    if probe.content_length and probe.content_length > local_limit_bytes and not force_local_processing:
        await message.reply_text(
            "الفيديو أكبر من الحد الآمن للرفع المحلي على الاستضافة الحالية، "
            "لذلك أوقفت التحميل المحلي حتى لا يتوقف البوت.\n\n"
            f"الحجم التقريبي: {_format_size_mb(probe.content_length)}\n"
            f"رابط مباشر: {probe.final_url or direct_url}"
        )
        return

    if force_local_processing and probe.content_length and probe.content_length > download_limit_bytes:
        raise RuntimeError(
            "تعذر تجهيز النسخة الأقل دقة لأن الملف الأصلي أكبر من الحد المتاح للتنزيل المحلي على الاستضافة الحالية. "
            f"الحجم التقريبي: {_format_size_mb(probe.content_length)}"
        )

    allow_unknown_size_local = kind != "mp3" and (
        probe.content_type.startswith("video/")
        or _is_instagram_media_like_url(probe.final_url or direct_url)
    )
    if kind != "mp3" and probe.content_length is None and not allow_unknown_size_local:
        await message.reply_text(
            "تعذر التأكد من حجم الفيديو بشكل آمن على الاستضافة الحالية، "
            "لذلك أرسلت لك الرابط المباشر بدل التحميل المحلي حتى لا يتعطل البوت.\n\n"
            f"رابط مباشر: {probe.final_url or direct_url}"
        )
        return

    semaphore = context.bot_data.get("local_download_semaphore")
    if semaphore is None:
        semaphore = asyncio.Semaphore(max(1, LOCAL_DOWNLOAD_CONCURRENCY))
        context.bot_data["local_download_semaphore"] = semaphore

    suffix = ".mp3" if kind == "mp3" else ".mp4"
    action = ChatAction.UPLOAD_AUDIO if kind == "mp3" else ChatAction.UPLOAD_VIDEO

    async with semaphore:
        file_path: Path | None = None
        try:
            await context.bot.send_chat_action(chat_id=message.chat_id, action=action)
            file_path = await asyncio.to_thread(client.download_file, probe.final_url or direct_url, suffix)
            if kind == "mp3":
                with file_path.open("rb") as audio_file:
                    await message.reply_audio(
                        audio=audio_file,
                        caption=title,
                        title=(title[:64] if title else "TikTok Audio"),
                        performer="TikTok",
                    )
            else:
                upload_path = file_path
                if force_local_processing:
                    upload_path = await asyncio.to_thread(client.convert_video_to_low_quality, file_path)

                try:
                    with upload_path.open("rb") as video_file:
                        await message.reply_video(
                            video=video_file,
                            caption=title,
                            supports_streaming=True,
                        )
                except Exception:
                    with upload_path.open("rb") as doc_file:
                        await message.reply_document(
                            document=doc_file,
                            caption=title,
                            filename=target_filename,
                        )
                finally:
                    if upload_path != file_path and upload_path.exists():
                        upload_path.unlink(missing_ok=True)
        finally:
            if file_path and file_path.exists():
                file_path.unlink(missing_ok=True)


async def download_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        return

    await query.answer()

    if not await enforce_force_subscription(update, context, prompt=True):
        return

    parts = (query.data or "").split(":", 2)
    if len(parts) != 3 or parts[0] != "dl":
        await query.answer("الطلب غير صالح.", show_alert=True)
        return

    kind, ref_id = parts[1], parts[2]
    payload = context.bot_data.get("downloads", {}).get(ref_id)
    if not payload:
        await query.message.reply_text("انتهت صلاحية هذا الطلب. ابعت الرابط مرة ثانية.")
        return

    if payload.get("user_id") != update.effective_user.id and not is_developer(update.effective_user.id):
        await query.answer("هذا الزر ليس تابعاً لطلبك.", show_alert=True)
        return

    if kind == "refresh":
        await query.message.reply_text("ابعت الرابط مرة ثانية وأنا هجهزه من جديد.")
        return

    force_local_processing = False
    output_label = None

    if kind == "mp3":
        direct_url = payload.get("mp3_url")
        label = "الملف الصوتي"
    elif kind == "low":
        direct_url = (
            payload.get("no_watermark_url")
            or payload.get("hd_url")
            or payload.get("preview_video_url")
            or payload.get("watermark_url")
        )
        label = "الفيديو الأقل دقة"
        force_local_processing = True
        output_label = "tiktok_low.mp4"
    elif kind == "hd":
        direct_url = payload.get("hd_url") or payload.get("no_watermark_url")
        label = "الفيديو بأعلى دقة"
        output_label = "tiktok_hd.mp4"
    else:
        await query.answer("الخيار غير معروف.", show_alert=True)
        return

    if not direct_url:
        await query.answer("هذا الخيار غير متاح لهذا الرابط.", show_alert=True)
        return

    waiting = await query.message.reply_text(f"جاري تجهيز {label}...")
    try:
        title = payload.get("title") or "TikTok Download"
        await deliver_remote_or_local(
            update,
            context,
            direct_url=direct_url,
            kind=kind,
            title=title,
            force_local_processing=force_local_processing,
            output_label=output_label,
        )
        try:
            await waiting.delete()
        except Exception:
            pass
    except Exception as exc:
        logger.exception("Download callback failed")
        try:
            await waiting.delete()
        except Exception:
            pass
        await query.message.reply_text(
            f"حصل خطأ أثناء تجهيز {label}.\n"
            f"الرسالة: {exc}\n\n"
            f"رابط بديل مباشر:\n{direct_url}"
        )


async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return

    await query.answer()
    if not is_developer(user.id):
        await query.answer("هذا القسم للمطور فقط.", show_alert=True)
        return

    action = (query.data or "").split(":", 1)[1]
    settings = get_settings(context)

    if action == "set_start":
        context.user_data["pending_action"] = "set_start_message"
        await query.message.reply_text(
            "أرسل الآن رسالة /start الجديدة كاملة.\nاكتب /cancel للإلغاء.",
            reply_markup=build_admin_keyboard(),
        )
        return

    if action == "broadcast":
        context.user_data["pending_action"] = "broadcast_message"
        await query.message.reply_text(
            "أرسل الآن نص الإذاعة الذي تريد إرساله لكل المستخدمين.\nاكتب /cancel للإلغاء.",
            reply_markup=build_admin_keyboard(),
        )
        return

    if action == "force_sub":
        context.user_data["pending_action"] = "set_force_sub"
        await query.message.reply_text(
            "أرسل إعدادات الاشتراك الإجباري بهذا الشكل:\n\n"
            "السطر الأول: معرف القناة أو اليوزر مثل @channel\n"
            "السطر الثاني: رابط الانضمام (اختياري)\n"
            "من السطر الثالث وما بعده: رسالة الاشتراك الإجباري (اختياري)\n\n"
            "مثال:\n"
            "@mychannel\n"
            "https://t.me/mychannel\n"
            "اشترك بالقناة ثم اضغط تحقق ✅",
            reply_markup=build_admin_keyboard(),
        )
        return

    if action == "disable_force_sub":
        settings["force_sub_enabled"] = False
        save_settings(context, settings)
        await query.message.reply_text("تم تعطيل الاشتراك الإجباري ✅", reply_markup=build_admin_keyboard())
        return

    if action == "stats":
        users = context.bot_data.setdefault("users", get_users())
        force_sub = "مفعل" if settings.get("force_sub_enabled") else "معطل"
        await query.message.reply_text(
            "إحصائيات البوت 📊\n\n"
            f"عدد المستخدمين: {len(users)}\n"
            f"الاشتراك الإجباري: {force_sub}\n"
            f"القناة/المعرف: {settings.get('force_sub_chat_id') or 'غير محدد'}\n"
            f"مدة التشغيل: {format_uptime(int(time.time() - APP_START_TIME))}",
            reply_markup=build_admin_keyboard(),
        )
        return

    if action == "view_start":
        await query.message.reply_text(
            "رسالة /start الحالية:\n\n" + (settings.get("start_message") or START_MESSAGE_DEFAULT),
            reply_markup=build_admin_keyboard(),
        )
        return


async def subscription_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    await query.answer()
    ok = await enforce_force_subscription(update, context, prompt=False)
    if ok:
        await query.message.reply_text("تم التحقق بنجاح ✅ يمكنك الآن استخدام البوت.")
    else:
        settings = get_settings(context)
        await query.message.reply_text(
            settings.get("force_sub_text") or FORCE_SUB_TEXT_DEFAULT,
            reply_markup=build_subscription_keyboard(settings),
        )


async def post_init(application: Application) -> None:
    ensure_storage()
    application.bot_data["settings"] = get_settings(None)
    application.bot_data["users"] = get_users()
    application.bot_data["downloads"] = {}
    application.bot_data["local_download_semaphore"] = asyncio.Semaphore(
        max(1, LOCAL_DOWNLOAD_CONCURRENCY)
    )

    try:
        await application.bot.set_my_commands(
            [
                ("start", "تشغيل البوت"),
                ("help", "المساعدة"),
                ("ping", "فحص البوت"),
                ("stats", "إحصائيات المطور"),
                ("admin", "لوحة المطور"),
                ("cancel", "إلغاء العملية الحالية"),
            ]
        )
    except Exception:
        logger.exception("Could not set bot commands")

    mode = "Webhook" if _should_use_webhook() else "Polling"
    extra = ""
    if _should_use_webhook():
        public_webhook = WEBHOOK_URL.rstrip("/") + _normalize_webhook_path(WEBHOOK_PATH)
        extra = f"\nWebhook: {public_webhook}"

    try:
        if DEVELOPER_ID:
            await application.bot.send_message(
                chat_id=DEVELOPER_ID,
                text=(
                    "تم تشغيل بوت تنزيل فيديوهات تيك توك وإنستجرام بنجاح ✅\n"
                    f"الوضع: {mode}\n"
                    f"Python: {sys.version.split()[0]}\n"
                    f"Port: {PORT}{extra}"
                ),
            )
    except Exception:
        logger.exception("Could not send startup notification to developer")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error_text = "".join(
        traceback.format_exception(
            None,
            context.error,
            context.error.__traceback__ if context.error else None,
        )
    )
    logger.error("Unhandled exception: %s", error_text)

    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "حصل خطأ داخلي غير متوقع. جرب مرة ثانية بعد لحظات."
            )
    except Exception:
        logger.debug("Could not reply to user with error message", exc_info=True)

    try:
        if DEVELOPER_ID:
            await context.bot.send_message(
                chat_id=DEVELOPER_ID,
                text=_truncate(f"⚠️ خطأ داخلي داخل البوت:\n{error_text}"),
            )
    except Exception:
        logger.exception("Could not send error report to developer")


def build_app() -> Application:
    builder = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .concurrent_updates(True)
    )
    app = builder.build()

    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("cancel", cancel_handler))
    app.add_handler(CommandHandler("ping", ping_handler))
    app.add_handler(CommandHandler("stats", stats_handler))
    app.add_handler(CommandHandler("admin", admin_handler))
    app.add_handler(CallbackQueryHandler(download_callback_handler, pattern=r"^dl:"))
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern=r"^admin:"))
    app.add_handler(CallbackQueryHandler(subscription_callback_handler, pattern=r"^sub:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    return app


def validate_configuration() -> None:
    ensure_storage()
    if not BOT_TOKEN or ":" not in BOT_TOKEN:
        raise RuntimeError("قيمة BOT_TOKEN غير صالحة أو غير موجودة.")
    if DEVELOPER_ID <= 0:
        raise RuntimeError("قيمة DEVELOPER_ID غير صالحة.")
    if PORT <= 0:
        raise RuntimeError("قيمة PORT غير صالحة.")
    if _should_use_webhook() and not WEBHOOK_URL.startswith(("http://", "https://")):
        raise RuntimeError("لازم WEBHOOK_URL يكون رابط كامل يبدأ بـ http:// أو https://")


def run_app(application: Application) -> None:
    if _should_use_webhook():
        webhook_path = _normalize_webhook_path(WEBHOOK_PATH)
        public_webhook = WEBHOOK_URL.rstrip("/") + webhook_path
        logger.info(
            "Running in webhook mode | listen=%s | port=%s | path=%s | public=%s",
            HOST,
            PORT,
            webhook_path,
            public_webhook,
        )
        application.run_webhook(
            listen=HOST,
            port=PORT,
            url_path=webhook_path.lstrip("/"),
            webhook_url=public_webhook,
            secret_token=WEBHOOK_SECRET_TOKEN or None,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,
            close_loop=False,
        )
    else:
        logger.info("Running in polling mode")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,
            close_loop=False,
        )


if __name__ == "__main__":
    while True:
        try:
            logger.info("Starting TikTok/Instagram Store bot...")
            validate_configuration()
            application = build_app()
            run_app(application)
            break
        except KeyboardInterrupt:
            logger.info("Bot stopped by keyboard interrupt")
            break
        except Exception as exc:
            logger.exception("Fatal startup/runtime error")
            _notify_developer_sync(
                "❌ تعطل بوت تنزيل فيديوهات تيك توك/إنستجرام وسيتم محاولة إعادة تشغيله\n"
                f"السبب: {exc}\n"
                f"Python: {sys.version.split()[0]}\n"
                f"الوضع: {'Webhook' if _should_use_webhook() else 'Polling'}\n"
                f"PORT: {PORT}\n"
                f"إعادة المحاولة بعد {RESTART_DELAY_SECONDS} ثوانٍ"
            )
            time.sleep(max(3, RESTART_DELAY_SECONDS))
