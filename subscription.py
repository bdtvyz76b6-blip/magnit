# subscription.py

import base64
import logging
import os
import threading
import time
from typing import Optional

import requests
from dotenv import load_dotenv

from config import (
    AUTO_SYNC_ENABLED,
    AUTO_SYNC_INTERVAL,
    GITHUB_BRANCH,
    GITHUB_OWNER,
    GITHUB_REPO,
    GITHUB_TOKEN,
    HIDE_SETTINGS,
    NO_SERVERS_FILE,
    PROFILE_TITLE,
    PROFILE_UPDATE_INTERVAL,
    SERVERS_FILE,
    TRAFFIC_DOWNLOAD,
    TRAFFIC_TOTAL,
    TRAFFIC_UPLOAD,
)
from database import (
    build_subscription_link,
    get_all_users,
    get_user,
    save_subscription_content,
    save_subscription_link,
)

load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================
# GITHUB
# ============================================================

GITHUB_API = (
    f"https://api.github.com/repos/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}/contents"
)


def github_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "MAGNIT-VPN",
    }

    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    return headers


def github_file_url(filename: str) -> str:
    return (
        f"{GITHUB_API}/{filename}"
        f"?ref={GITHUB_BRANCH}"
    )


# ============================================================
# ЗАГРУЗКА SERVERS.TXT
# ============================================================

def load_github_file(filename: str) -> str:
    """
    Загружает файл из GitHub.

    Если GitHub недоступен или файл не найден,
    возвращает пустую строку.
    """

    try:
        response = requests.get(
            github_file_url(filename),
            headers=github_headers(),
            timeout=20,
        )

        if response.status_code != 200:
            logger.error(
                "GitHub: не удалось получить %s: HTTP %s",
                filename,
                response.status_code,
            )
            return ""

        data = response.json()

        content = data.get("content", "")

        if not content:
            return ""

        # GitHub отдаёт Base64
        content = content.replace("\n", "")

        try:
            decoded = base64.b64decode(
                content
            ).decode("utf-8")

            return decoded.strip()

        except Exception:
            logger.exception(
                "Ошибка Base64 при загрузке %s",
                filename,
            )
            return ""

    except requests.RequestException:
        logger.exception(
            "Ошибка соединения с GitHub при загрузке %s",
            filename,
        )
        return ""

    except Exception:
        logger.exception(
            "Неожиданная ошибка загрузки %s",
            filename,
        )
        return ""


# ============================================================
# ПОЛУЧЕНИЕ СЕРВЕРОВ
# ============================================================

def load_servers() -> str:
    """
    Загружает основной список серверов.

    servers.txt должен содержать VLESS-ссылки.
    """

    content = load_github_file(SERVERS_FILE)

    if content:
        return content.strip()

    logger.warning(
        "Основной %s пустой, пробуем %s",
        SERVERS_FILE,
        NO_SERVERS_FILE,
    )

    fallback = load_github_file(
        NO_SERVERS_FILE
    )

    return fallback.strip()


def clean_servers(content: str) -> list[str]:
    """
    Оставляет только реальные VLESS-ссылки.
    """

    result = []

    for line in content.splitlines():

        line = line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        if line.startswith("vless://"):
            result.append(line)

    return result


# ============================================================
# HAPP HEADERS
# ============================================================

def build_happ_headers(
    user: Optional[dict] = None,
) -> list[str]:

    headers = [
        f"#profile-title: {PROFILE_TITLE}",
        (
            "#profile-update-interval: "
            f"{PROFILE_UPDATE_INTERVAL}"
        ),
        (
            "#subscription-userinfo: "
            f"upload={TRAFFIC_UPLOAD};"
            f"download={TRAFFIC_DOWNLOAD};"
            f"total={TRAFFIC_TOTAL}"
        ),
    ]

    if HIDE_SETTINGS:

        headers.extend(
            [
                "#hide-settings: true",
                "#happ-hide-settings: true",
                "#hide_server_settings: true",
                "#hidesettings: true",
            ]
        )

    if user:

        username = user.get(
            "username",
            "",
        )

        first_name = user.get(
            "first_name",
            "",
        )

        user_id = user.get(
            "user_id",
            "",
        )

        if username:
            announce = (
                f"🧲 МАГНИТ VPN | "
                f"@{username}"
            )

        elif first_name:
            announce = (
                f"🧲 МАГНИТ VPN | "
                f"{first_name}"
            )

        else:
            announce = (
                f"🧲 МАГНИТ VPN | "
                f"ID {user_id}"
            )

        headers.append(
            f"#announce: {announce}"
        )

    else:
        headers.append(
            "#announce: 🧲 МАГНИТ VPN"
        )

    return headers


# ============================================================
# ГЕНЕРАЦИЯ ПОДПИСКИ
# ============================================================

def build_subscription_content(
    user: Optional[dict] = None,
) -> str:
    """
    Создаёт содержимое подписки Happ.

    Формат:

    #profile-title: ...
    #profile-update-interval: ...
    #subscription-userinfo: ...
    ...
    vless://...
    """

    servers_content = load_servers()

    servers = clean_servers(
        servers_content
    )

    headers = build_happ_headers(
        user
    )

    lines = []

    lines.extend(headers)

    if servers:
        lines.append("")
        lines.extend(servers)

    return "\n".join(lines).strip() + "\n"


# ============================================================
# СОХРАНЕНИЕ ПОДПИСКИ
# ============================================================

def sync_user(
    user_id: int,
) -> bool:
    """
    Пересобирает подписку конкретного пользователя.
    """

    user = get_user(user_id)

    if not user:
        logger.warning(
            "sync_user: пользователь %s не найден",
            user_id,
        )
        return False

    try:
        token = user.get(
            "token",
            "",
        )

        if not token:
            logger.error(
                "У пользователя %s отсутствует token",
                user_id,
            )
            return False

        content = build_subscription_content(
            user
        )

        if not content:
            logger.error(
                "Пустое содержимое подписки "
                "для пользователя %s",
                user_id,
            )
            return False

        link = build_subscription_link(
            token
        )

        save_subscription_content(
            user_id,
            content,
        )

        save_subscription_link(
            user_id,
            link,
        )

        logger.info(
            "Подписка пользователя %s синхронизирована",
            user_id,
        )

        return True

    except Exception:
        logger.exception(
            "Ошибка синхронизации пользователя %s",
            user_id,
        )
        return False


# ============================================================
# СОЗДАНИЕ ПОДПИСКИ ПРИ СОЗДАНИИ USER
# ============================================================

def ensure_subscription(
    user_id: int,
) -> Optional[str]:
    """
    Гарантирует наличие ссылки и содержимого подписки.

    Возвращает ссылку.
    """

    user = get_user(user_id)

    if not user:
        return None

    token = user.get(
        "token",
        "",
    )

    if not token:
        return None

    link = user.get(
        "subscription_link",
        "",
    )

    content = user.get(
        "subscription_content",
        "",
    )

    if not link:
        link = build_subscription_link(
            token
        )

        save_subscription_link(
            user_id,
            link,
        )

    if not content:
        sync_user(
            user_id
        )

    return link


# ============================================================
# СИНХРОНИЗАЦИЯ ВСЕХ ПОЛЬЗОВАТЕЛЕЙ
# ============================================================

def sync_all_users() -> dict:
    """
    Пересобирает подписки всех пользователей.
    """

    users = get_all_users()

    success = 0
    failed = 0
    skipped = 0

    for user in users:

        user_id = user.get(
            "user_id"
        )

        if not user_id:
            skipped += 1
            continue

        if sync_user(user_id):
            success += 1
        else:
            failed += 1

    result = {
        "total": len(users),
        "success": success,
        "failed": failed,
        "skipped": skipped,
    }

    logger.info(
        "Полная синхронизация: %s",
        result,
    )

    return result


# ============================================================
# СИНХРОНИЗАЦИЯ АКТИВНЫХ
# ============================================================

def sync_all_active_users() -> dict:
    """
    Синхронизирует пользователей,
    у которых есть активная/просроченная подписка.

    ВАЖНО:
    здесь нет никакой проверки устройств.
    """

    users = get_all_users()

    success = 0
    failed = 0
    skipped = 0

    for user in users:

        user_id = user.get(
            "user_id"
        )

        if not user_id:
            skipped += 1
            continue

        subscription_until = user.get(
            "subscription_until",
            "",
        )

        subscription = user.get(
            "subscription",
            "none",
        )

        # Пользователям без подписки
        # синхронизация не обязательна.
        if (
            not subscription_until
            and subscription == "none"
        ):
            skipped += 1
            continue

        if sync_user(user_id):
            success += 1
        else:
            failed += 1

    result = {
        "total": len(users),
        "success": success,
        "failed": failed,
        "skipped": skipped,
    }

    logger.info(
        "Синхронизация активных: %s",
        result,
    )

    return result


# ============================================================
# ФОНОВАЯ АВТОСИНХРОНИЗАЦИЯ
# ============================================================

_sync_thread = None
_sync_started = False


def _auto_sync_loop():
    global _sync_started

    logger.info(
        "Автосинхронизация MAGNIT VPN запущена"
    )

    while True:

        try:
            time.sleep(
                max(
                    AUTO_SYNC_INTERVAL,
                    60,
                )
            )

            logger.info(
                "Запуск автоматической "
                "синхронизации подписок"
            )

            sync_all_active_users()

        except Exception:
            logger.exception(
                "Ошибка фоновой синхронизации"
            )


def start_auto_sync():
    """
    Запускает один фоновый поток.
    """

    global _sync_thread
    global _sync_started

    if not AUTO_SYNC_ENABLED:
        logger.info(
            "AUTO_SYNC_ENABLED отключён"
        )
        return

    if _sync_started:
        logger.warning(
            "Автосинхронизация уже запущена"
        )
        return

    _sync_started = True

    _sync_thread = threading.Thread(
        target=_auto_sync_loop,
        name="magnit-vpn-sync",
        daemon=True,
    )

    _sync_thread.start()


# ============================================================
# ПРИНУДИТЕЛЬНАЯ СИНХРОНИЗАЦИЯ
# ============================================================

def force_sync() -> dict:
    """
    Полная ручная синхронизация.
    Используется кнопкой админ-панели.
    """

    logger.info(
        "Запущена ручная синхронизация"
    )

    return sync_all_users()


# ============================================================
# ПРОВЕРКА КОНФИГУРАЦИИ
# ============================================================

def check_github_connection() -> bool:
    """
    Проверяет доступность servers.txt.
    """

    try:
        response = requests.get(
            github_file_url(SERVERS_FILE),
            headers=github_headers(),
            timeout=15,
        )

        if response.status_code == 200:
            return True

        logger.error(
            "GitHub проверка: HTTP %s",
            response.status_code,
        )

        return False

    except requests.RequestException:
        logger.exception(
            "GitHub проверка завершилась ошибкой"
        )
        return False


# ============================================================
# ИНФОРМАЦИЯ О СЕРВЕРАХ
# ============================================================

def get_servers_info() -> dict:
    """
    Возвращает информацию для админ-панели.
    """

    content = load_servers()

    servers = clean_servers(
        content
    )

    return {
        "count": len(servers),
        "servers": servers,
        "source": (
            f"{GITHUB_OWNER}/"
            f"{GITHUB_REPO}/"
            f"{SERVERS_FILE}"
        ),
    }


# ============================================================
# ТЕСТ
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
    )

    print(
        "🧲 MAGNIT VPN — subscription.py"
    )

    print(
        "GitHub:",
        "OK"
        if check_github_connection()
        else "ERROR",
    )

    info = get_servers_info()

    print(
        "Серверов:",
        info["count"],
    )

    if info["count"]:
        for server in info["servers"]:
            print(server)