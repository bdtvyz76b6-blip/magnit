# config.py

import os
from dotenv import load_dotenv

load_dotenv()


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "да",
    }


def env_int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# ============================================================
# TELEGRAM
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_ID = env_int("ADMIN_ID", 0)

ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

if ADMIN_ID:
    ADMIN_IDS.add(ADMIN_ID)


# ============================================================
# СЕРВИС
# ============================================================

SERVICE_NAME = os.getenv(
    "SERVICE_NAME",
    "МАГНИТ VPN",
).strip()

PUBLIC_URL = os.getenv(
    "PUBLIC_URL",
    "https://orelvpnrailoh-1.onrender.com",
).rstrip("/")

TELEGRAM_USERNAME = os.getenv(
    "TELEGRAM_USERNAME",
    "orelvpntopbot",
).strip().lstrip("@")


# ============================================================
# ПОДПИСКА
# ============================================================

PROFILE_TITLE = os.getenv(
    "PROFILE_TITLE",
    "𝗦𝗨𝗕 - 𝗠𝗔𝗚𝗡𝗜𝗧 𝗩𝗣𝗡 🧲",
)

PROFILE_UPDATE_INTERVAL = env_int(
    "PROFILE_UPDATE_INTERVAL",
    1,
)

TRAFFIC_TOTAL = env_int(
    "TRAFFIC_TOTAL",
    0,
)

TRAFFIC_UPLOAD = env_int(
    "TRAFFIC_UPLOAD",
    0,
)

TRAFFIC_DOWNLOAD = env_int(
    "TRAFFIC_DOWNLOAD",
    0,
)

HIDE_SETTINGS = env_bool(
    "HIDE_SETTINGS",
    True,
)


# ============================================================
# GITHUB
# ============================================================

GITHUB_TOKEN = os.getenv(
    "GITHUB_TOKEN",
    "",
).strip()

GITHUB_OWNER = os.getenv(
    "GITHUB_OWNER",
    "bdtvyz76b6-blip",
).strip()

GITHUB_REPO = os.getenv(
    "GITHUB_REPO",
    "vpn-sub",
).strip()

GITHUB_BRANCH = os.getenv(
    "GITHUB_BRANCH",
    "main",
).strip()

SERVERS_FILE = os.getenv(
    "SERVERS_FILE",
    "servers.txt",
).strip()

NO_SERVERS_FILE = os.getenv(
    "NO_SERVERS_FILE",
    "no_servers.txt",
).strip()


# ============================================================
# АВТОСИНХРОНИЗАЦИЯ
# ============================================================

AUTO_SYNC_ENABLED = env_bool(
    "AUTO_SYNC_ENABLED",
    True,
)

AUTO_SYNC_INTERVAL = env_int(
    "AUTO_SYNC_INTERVAL",
    600,
)


# ============================================================
# БАЗА
# ============================================================

DB_PATH = os.getenv(
    "DB_PATH",
    "./data/users.db",
).strip()


# ============================================================
# ПРОБНЫЙ ПЕРИОД
# ============================================================

TRIAL_DAYS = env_int(
    "TRIAL_DAYS",
    3,
)


# ============================================================
# ТАРИФЫ
# ============================================================

TARIFFS = {
    "1_month": {
        "title": "1 месяц",
        "days": 30,
        "stars": 70,
    },
    "3_months": {
        "title": "3 месяца",
        "days": 90,
        "stars": 190,
    },
    "6_months": {
        "title": "6 месяцев",
        "days": 180,
        "stars": 350,
    },
    "12_months": {
        "title": "12 месяцев",
        "days": 365,
        "stars": 700,
    },
}


# ============================================================
# ПРОВЕРКА
# ============================================================

if not BOT_TOKEN:
    print("⚠️ ВНИМАНИЕ: BOT_TOKEN не указан в .env")

if not ADMIN_IDS:
    print("⚠️ ВНИМАНИЕ: ADMIN_IDS не указан в .env")