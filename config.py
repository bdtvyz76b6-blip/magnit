import os

# ============================================================
# МАГНИТ VPN — CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Telegram ID администратора
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Публичный адрес сервера, например:
# https://magnit-vpn.onrender.com
PUBLIC_URL = os.getenv(
    "PUBLIC_URL",
    "http://localhost:8080"
).rstrip("/")

# Секрет для API подписок
API_SECRET = os.getenv(
    "API_SECRET",
    "change-this-secret"
)

# База
DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    "magnit.db"
)

# Пробный период
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "3"))

# Лимит устройств по умолчанию
DEFAULT_DEVICE_LIMIT = int(
    os.getenv("DEFAULT_DEVICE_LIMIT", "2")
)

# ============================================================
# ТАРИФЫ
# ============================================================

TARIFFS = {
    "1": {
        "name": "1 месяц",
        "days": 30,
        "stars": 70,
        "device_limit": 2,
    },
    "3": {
        "name": "3 месяца",
        "days": 90,
        "stars": 190,
        "device_limit": 3,
    },
    "6": {
        "name": "6 месяцев",
        "days": 180,
        "stars": 350,
        "device_limit": 4,
    },
    "12": {
        "name": "12 месяцев",
        "days": 365,
        "stars": 700,
        "device_limit": 5,
    },
}

# Название сервиса
SERVICE_NAME = "🧲 Магнит VPN"

# Время уведомления до окончания
EXPIRY_WARNING_DAYS = 1