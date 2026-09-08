import os
import time
import threading
import requests

from datetime import datetime, timedelta

from dotenv import load_dotenv

from database import (
    save_subscription_link,
    save_subscription_content,
    get_all_users,
)

# ============================================================
# .ENV
# ============================================================

load_dotenv()

# ============================================================
# НАСТРОЙКИ
# ============================================================

PUBLIC_SITE_URL = os.getenv(
    "PUBLIC_SITE_URL",
    "https://orelvpnrailoh-1.onrender.com",
).rstrip("/")

SUBSCRIPTION_PREFIX = os.getenv(
    "SUBSCRIPTION_PREFIX",
    "2ix847xy",
).strip()

# Telegram
TELEGRAM_USERNAME = os.getenv(
    "TELEGRAM_USERNAME",
    "orelvpntopbot",
).strip().lstrip("@")

TELEGRAM_URL = os.getenv(
    "TELEGRAM_URL",
    f"https://t.me/{TELEGRAM_USERNAME}",
).strip()

# ============================================================
# НАЗВАНИЕ МАГНИТ VPN
# ============================================================

PROFILE_TITLE = os.getenv(
    "PROFILE_TITLE",
    "𝗦𝗨𝗕 - 𝗠𝗔𝗚𝗡𝗜𝗧 𝗩𝗣𝗡 🧲",
).strip()

PROFILE_UPDATE_INTERVAL = int(
    os.getenv(
        "PROFILE_UPDATE_INTERVAL",
        "1",
    )
)

# ============================================================
# HAPP — ТРАФИК
# ============================================================

# 0 = безлимит
TRAFFIC_TOTAL = int(
    os.getenv(
        "TRAFFIC_TOTAL",
        "0",
    )
)

TRAFFIC_UPLOAD = int(
    os.getenv(
        "TRAFFIC_UPLOAD",
        "0",
    )
)

TRAFFIC_DOWNLOAD = int(
    os.getenv(
        "TRAFFIC_DOWNLOAD",
        "0",
    )
)

# ============================================================
# HAPP — СКРЫТИЕ НАСТРОЕК
# ============================================================

HIDE_SETTINGS = os.getenv(
    "HIDE_SETTINGS",
    "1",
).strip() == "1"

# ============================================================
# АВТОСИНХРОНИЗАЦИЯ
# ============================================================

AUTO_SYNC_ENABLED = os.getenv(
    "AUTO_SYNC_ENABLED",
    "1",
).strip() == "1"

try:
    AUTO_SYNC_INTERVAL = int(
        os.getenv(
            "AUTO_SYNC_INTERVAL",
            "600",
        )
    )
except Exception:
    AUTO_SYNC_INTERVAL = 600

# ============================================================
# GITHUB
# ============================================================

GITHUB_TOKEN = os.getenv(
    "GITHUB_TOKEN",
    "",
).strip()

OWNER = os.getenv(
    "GITHUB_OWNER",
    "bdtvyz76b6-blip",
).strip()

REPO = os.getenv(
    "GITHUB_REPO",
    "vpn-sub",
).strip()

BRANCH = os.getenv(
    "GITHUB_BRANCH",
    "main",
).strip()

# ============================================================
# ФАЙЛЫ СЕРВЕРОВ
# ============================================================

SERVERS_FILE = os.getenv(
    "SERVERS_FILE",
    "servers.txt",
).strip()

NO_SERVERS_FILE = os.getenv(
    "NO_SERVERS_FILE",
    "no_servers.txt",
).strip()

# ============================================================
# RAW GITHUB
# ============================================================

def raw_url(filename):
    return (
        f"https://raw.githubusercontent.com/"
        f"{OWNER}/{REPO}/{BRANCH}/{filename}"
    )


# ============================================================
# ЗАГРУЗКА ФАЙЛА GITHUB
# ============================================================

def load_github_file(filename):
    response = requests.get(
        raw_url(filename),
        timeout=20,
    )

    if response.status_code != 200:
        raise Exception(
            f"Не удалось загрузить {filename}: "
            f"HTTP {response.status_code}"
        )

    content = response.text.strip()

    if not content:
        raise Exception(
            f"Файл {filename} пустой"
        )

    return content


# ============================================================
# АКТИВНЫЕ СЕРВЕРЫ
# ============================================================

def load_servers():
    return load_github_file(
        SERVERS_FILE
    )


# ============================================================
# СЕРВЕРЫ ДЛЯ НЕАКТИВНОЙ ПОДПИСКИ
# ============================================================

def load_no_servers():
    return load_github_file(
        NO_SERVERS_FILE
    )


# ============================================================
# ПЕРСОНАЛЬНАЯ СТРАНИЦА
# ============================================================

def get_subscription_link(user_id):
    return (
        f"{PUBLIC_SITE_URL}/s/"
        f"{SUBSCRIPTION_PREFIX}"
        f"{user_id}"
    )


# ============================================================
# ПРЯМАЯ ССЫЛКА НА ПОДПИСКУ
# ============================================================

def get_subscription_content_url(user_id):
    return (
        f"{PUBLIC_SITE_URL}/sub/"
        f"{SUBSCRIPTION_PREFIX}"
        f"{user_id}"
    )


# ============================================================
# DATE → UNIX
# ============================================================

def date_to_timestamp(date):
    if isinstance(date, datetime):
        return int(date.timestamp())

    value = str(date).strip()

    for fmt in (
        "%Y-%m-%d",
        "%d.%m.%Y",
    ):
        try:
            parsed = datetime.strptime(
                value,
                fmt,
            )

            return int(
                datetime.combine(
                    parsed.date(),
                    datetime.min.time(),
                ).timestamp()
            )

        except Exception:
            pass

    return 0


# ============================================================
# HAPP TRAFFIC
# ============================================================

def build_traffic_header(
    upload=TRAFFIC_UPLOAD,
    download=TRAFFIC_DOWNLOAD,
    total=TRAFFIC_TOTAL,
    expire=0,
):
    return (
        "#subscription-userinfo: "
        f"upload={int(upload)}; "
        f"download={int(download)}; "
        f"total={int(total)}; "
        f"expire={int(expire)}\n"
    )


# ============================================================
# HAPP PROFILE HEADER
# ============================================================

def build_profile_header(
    announce,
    expire=0,
    upload=TRAFFIC_UPLOAD,
    download=TRAFFIC_DOWNLOAD,
    total=TRAFFIC_TOTAL,
):
    hide = "true" if HIDE_SETTINGS else "false"

    return (
        f"#profile-title: {PROFILE_TITLE}\n"
        f"#profile-update-interval: "
        f"{PROFILE_UPDATE_INTERVAL}\n"
        f"#subscription-userinfo: "
        f"upload={int(upload)}; "
        f"download={int(download)}; "
        f"total={int(total)}; "
        f"expire={int(expire)}\n"
        f"#hide-settings: {hide}\n"
        f"#happ-hide-settings: {hide}\n"
        f"#hide_server_settings: {hide}\n"
        f"#hidesettings: {hide}\n"
        f"#announce: {announce}\n\n"
    )


# ============================================================
# СОХРАНЕНИЕ ПОДПИСКИ
# ============================================================

def save_user_subscription(
    user_id,
    content,
):
    link = get_subscription_link(
        user_id
    )

    save_subscription_content(
        user_id,
        content,
    )

    save_subscription_link(
        user_id,
        link,
    )

    return link


# ============================================================
# НОВЫЙ ПОЛЬЗОВАТЕЛЬ
# ============================================================

def get_inactive_announce():
    return (
        "🔒 Подписка не активна • "
        f"Оформите подписку через @{TELEGRAM_USERNAME}"
    )


NEW_USER_TEMPLATE = (
    build_profile_header(
        get_inactive_announce(),
        expire=0,
        upload=0,
        download=0,
        total=0,
    )
    +
    "vless://00000000-0000-0000-0000-000000000000"
    "@expired.invalid:443"
    "?type=tcp"
    "&security=reality"
    "&sni=expired.invalid"
    "&fp=chrome"
    "&pbk=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "&sid="
    "&flow=xtls-rprx-vision"
    "#⛔ Активируйте подписку"
).strip()


# ============================================================
# СОЗДАНИЕ ПОДПИСКИ НОВОМУ ПОЛЬЗОВАТЕЛЮ
# ============================================================

def create_user_subscription(user_id):

    link = save_user_subscription(
        user_id,
        NEW_USER_TEMPLATE,
    )

    print(
        f"🆕 Создана подписка МАГНИТ VPN "
        f"для пользователя {user_id}"
    )

    print(
        f"🔗 Страница: {link}"
    )

    print(
        "🔗 Subscription URL: "
        f"{get_subscription_content_url(user_id)}"
    )

    return link


# ============================================================
# ФОРМАТ ДАТЫ
# ============================================================

def format_subscription_date(date):

    if isinstance(date, datetime):
        return date.strftime(
            "%d.%m.%Y"
        )

    if hasattr(date, "strftime"):
        try:
            return date.strftime(
                "%d.%m.%Y"
            )
        except Exception:
            pass

    value = str(date).strip()

    for fmt in (
        "%Y-%m-%d",
        "%d.%m.%Y",
    ):
        try:
            parsed = datetime.strptime(
                value,
                fmt,
            )

            return parsed.strftime(
                "%d.%m.%Y"
            )

        except Exception:
            pass

    return value


# ============================================================
# СОЗДАНИЕ ПОДПИСКИ НА N ДНЕЙ
# ============================================================

def create_subscription(
    user_id,
    days=30,
):

    days = int(days)

    if days <= 0:
        raise ValueError(
            "Количество дней должно быть больше 0"
        )

    expire_date = (
        datetime.now().date()
        + timedelta(days=days)
    )

    display_date = expire_date.strftime(
        "%d.%m.%Y"
    )

    return activate_subscription_file(
        user_id,
        display_date,
    )


# ============================================================
# АКТИВНАЯ ПОДПИСКА
# ============================================================

def activate_subscription_file(
    user_id,
    date,
):

    servers = load_servers()

    display_date = format_subscription_date(
        date
    )

    expire_timestamp = date_to_timestamp(
        display_date
    )

    announce = (
        f"🟢 МАГНИТ VPN • "
        f"активна до {display_date} • "
        f"🆔 ID: {user_id}"
    )

    content = (
        build_profile_header(
            announce,
            expire=expire_timestamp,
            upload=0,
            download=0,
            total=TRAFFIC_TOTAL,
        )
        + servers
    )

    link = save_user_subscription(
        user_id,
        content,
    )

    print(
        f"🟢 МАГНИТ VPN: "
        f"{user_id} → до {display_date}"
    )

    print(
        "📊 Трафик: ♾️ безлимит"
        if TRAFFIC_TOTAL == 0
        else f"📊 Лимит: {TRAFFIC_TOTAL} байт"
    )

    print(
        f"🔗 Страница: {link}"
    )

    return link


# ============================================================
# АКТИВАЦИЯ
# ============================================================

def activate_user_subscription(
    user_id,
    days,
):
    return create_subscription(
        user_id,
        days,
    )


# ============================================================
# ОБНОВЛЕНИЕ ПО ДАТЕ
# ============================================================

def update_subscription_file(
    user_id,
    date,
):

    display_date = format_subscription_date(
        date
    )

    return activate_subscription_file(
        user_id,
        display_date,
    )


# ============================================================
# ИСТЕЧЕНИЕ ПОДПИСКИ
# ============================================================

def expire_subscription(user_id):

    no_servers = load_no_servers()

    announce = (
        "🔴 МАГНИТ VPN • "
        "Подписка истекла • "
        f"Продлите через @{TELEGRAM_USERNAME}"
    )

    content = (
        build_profile_header(
            announce,
            expire=0,
            upload=0,
            download=0,
            total=0,
        )
        + no_servers
    )

    link = save_user_subscription(
        user_id,
        content,
    )

    print(
        f"🔴 МАГНИТ VPN: "
        f"{user_id} — подписка отключена"
    )

    return link


# ============================================================
# АКТИВНЫЕ ТАРИФЫ
# ============================================================

ACTIVE_SUBSCRIPTIONS = {
    "vip",
    "trial",

    # Совместимость со старыми пользователями
    "👑 Орёл VPN",
    "🎁 Пробный период",
}


# ============================================================
# СИНХРОНИЗАЦИЯ ВСЕХ ПОЛЬЗОВАТЕЛЕЙ
# ============================================================

def sync_all_active_users():

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🔄 МАГНИТ VPN — синхронизация")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    try:
        servers = load_servers()
        no_servers = load_no_servers()
        users = get_all_users()

    except Exception as e:

        print(
            f"❌ Ошибка загрузки данных: {e}"
        )

        return {
            "updated": 0,
            "skipped": 0,
            "expired": 0,
            "errors": 1,
        }

    updated = 0
    skipped = 0
    expired = 0
    errors = 0

    today = datetime.now().date()

    for user in users:

        user_id = user[0]

        try:

            subscription = user[3]
            subscription_until = user[4]

            # ==================================================
            # НЕАКТИВНА
            # ==================================================

            if subscription not in ACTIVE_SUBSCRIPTIONS:

                content = (
                    build_profile_header(
                        get_inactive_announce(),
                        expire=0,
                        upload=0,
                        download=0,
                        total=0,
                    )
                    + no_servers
                )

                save_user_subscription(
                    user_id,
                    content,
                )

                skipped += 1

                print(
                    f"{user_id} — ⚪ неактивна"
                )

                continue

            # ==================================================
            # НЕТ ДАТЫ
            # ==================================================

            if not subscription_until:

                content = (
                    build_profile_header(
                        get_inactive_announce(),
                        expire=0,
                        upload=0,
                        download=0,
                        total=0,
                    )
                    + no_servers
                )

                save_user_subscription(
                    user_id,
                    content,
                )

                expired += 1

                print(
                    f"{user_id} — 🔴 нет даты"
                )

                continue

            # ==================================================
            # ПАРСИНГ ДАТЫ
            # ==================================================

            try:

                expire_date = datetime.strptime(
                    str(subscription_until),
                    "%Y-%m-%d",
                ).date()

            except Exception:

                print(
                    f"❌ Неверная дата у {user_id}: "
                    f"{subscription_until}"
                )

                content = (
                    build_profile_header(
                        "🔴 Ошибка даты подписки",
                        expire=0,
                        upload=0,
                        download=0,
                        total=0,
                    )
                    + no_servers
                )

                save_user_subscription(
                    user_id,
                    content,
                )

                errors += 1

                continue

            # ==================================================
            # ИСТЕКЛА
            # ==================================================

            if expire_date < today:

                content = (
                    build_profile_header(
                        (
                            "🔴 МАГНИТ VPN • "
                            "Подписка истекла • "
                            f"Продлите через "
                            f"@{TELEGRAM_USERNAME}"
                        ),
                        expire=0,
                        upload=0,
                        download=0,
                        total=0,
                    )
                    + no_servers
                )

                save_user_subscription(
                    user_id,
                    content,
                )

                expired += 1

                print(
                    f"{user_id} — 🔴 истекла"
                )

                continue

            # ==================================================
            # АКТИВНА
            # ==================================================

            display_date = expire_date.strftime(
                "%d.%m.%Y"
            )

            expire_timestamp = int(
                datetime.combine(
                    expire_date,
                    datetime.min.time(),
                ).timestamp()
            )

            announce = (
                f"🟢 МАГНИТ VPN • "
                f"активна до {display_date} • "
                f"🆔 ID: {user_id}"
            )

            content = (
                build_profile_header(
                    announce,
                    expire=expire_timestamp,
                    upload=0,
                    download=0,
                    total=TRAFFIC_TOTAL,
                )
                + servers
            )

            save_user_subscription(
                user_id,
                content,
            )

            updated += 1

            print(
                f"{user_id} — "
                f"🟢 до {display_date}"
            )

        except Exception as e:

            errors += 1

            print(
                f"❌ Ошибка пользователя "
                f"{user_id}: {e}"
            )

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ Синхронизация завершена")
    print(f"🟢 Обновлено: {updated}")
    print(f"🔴 Истекло: {expired}")
    print(f"⚪ Неактивно: {skipped}")
    print(f"❌ Ошибок: {errors}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return {
        "updated": updated,
        "skipped": skipped,
        "expired": expired,
        "errors": errors,
    }


# ============================================================
# ОБНОВЛЕНИЕ СЕРВЕРОВ ИЗ АДМИНКИ
# ============================================================

def sync_servers_update():

    print(
        "🔄 МАГНИТ VPN — "
        "обновление серверов из админки"
    )

    return sync_all_active_users()


# ============================================================
# AUTO SYNC
# ============================================================

def _auto_sync_worker():

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🤖 МАГНИТ VPN — автосинхронизация")
    print(
        f"⏱ Интервал: "
        f"{AUTO_SYNC_INTERVAL} секунд"
    )
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    time.sleep(15)

    while True:

        try:

            sync_all_active_users()

        except Exception as e:

            print(
                f"❌ Ошибка автосинхронизации: {e}"
            )

        time.sleep(
            AUTO_SYNC_INTERVAL
        )


# ============================================================
# ЗАПУСК
# ============================================================

if AUTO_SYNC_ENABLED:

    sync_thread = threading.Thread(
        target=_auto_sync_worker,
        daemon=True,
        name="magnit-vpn-auto-sync",
    )

    sync_thread.start()