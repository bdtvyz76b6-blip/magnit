import os
import base64
import threading
import time
import requests

from config import (
    GITHUB_TOKEN,
    GITHUB_OWNER,
    GITHUB_REPO,
    GITHUB_BRANCH,
    SERVERS_FILE,
    NO_SERVERS_FILE,
    AUTO_SYNC_ENABLED,
    AUTO_SYNC_INTERVAL,
    PROFILE_TITLE,
    PROFILE_UPDATE_INTERVAL,
    TRAFFIC_TOTAL,
    TRAFFIC_UPLOAD,
    TRAFFIC_DOWNLOAD,
    HIDE_SETTINGS,
)

from database import (
    get_user,
    get_all_users,
    save_subscription_content,
    save_subscription_link,
    build_subscription_link,
)


# ============================================================
# GITHUB
# ============================================================

def github_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    return headers


def github_file_url(filename):
    return (
        f"https://api.github.com/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}/contents/{filename}"
        f"?ref={GITHUB_BRANCH}"
    )


def load_github_file(filename):
    """
    Загружает файл из GitHub и возвращает обычный текст.
    """

    url = github_file_url(filename)

    response = requests.get(
        url,
        headers=github_headers(),
        timeout=20,
    )

    if response.status_code == 404:
        return ""

    response.raise_for_status()

    data = response.json()
    encoded = data.get("content", "")

    if not encoded:
        return ""

    encoded = encoded.replace("\n", "").replace("\r", "")

    try:
        return base64.b64decode(encoded).decode("utf-8")
    except Exception:
        return ""


# ============================================================
# SERVERS
# ============================================================

def clean_servers(content):
    """
    Оставляем только реальные VLESS-ссылки.

    Важно для Happ:
    subscription endpoint должен отдавать
    обычный текст, а не JSON/HTML/служебные строки.
    """

    if not content:
        return []

    result = []

    for raw_line in content.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if not line.startswith("vless://"):
            continue

        # Убираем случайные пробелы вокруг ссылки
        line = line.strip()

        result.append(line)

    return result


def load_servers():
    """
    Загружает servers.txt.
    Если он недоступен/пустой — пробует no_servers.txt.
    """

    content = load_github_file(SERVERS_FILE)
    servers = clean_servers(content)

    if servers:
        return servers

    fallback = load_github_file(NO_SERVERS_FILE)
    return clean_servers(fallback)


# ============================================================
# HAPP HEADERS
# ============================================================

def build_happ_headers(user=None):
    """
    Формируем корректные subscription headers.

    Никакого JSON.
    Никакого HTML.
    Никаких device-параметров.
    """

    headers = []

    title = PROFILE_TITLE.strip()

    if title:
        headers.append(f"#profile-title: {title}")

    headers.append(
        f"#profile-update-interval: {int(PROFILE_UPDATE_INTERVAL)}"
    )

    headers.append(
        "#subscription-userinfo: "
        f"upload={int(TRAFFIC_UPLOAD)};"
        f"download={int(TRAFFIC_DOWNLOAD)};"
        f"total={int(TRAFFIC_TOTAL)}"
    )

    if HIDE_SETTINGS:
        headers.append("#profile-web-page-url: ")
        headers.append("#profile-profile-web-page-url: ")

    return headers


# ============================================================
# BUILD SUBSCRIPTION
# ============================================================

def build_subscription_content(user=None):
    """
    Финальный текст подписки.

    Формат:

    #profile-title: ...
    #profile-update-interval: ...
    #subscription-userinfo: ...

    vless://...
    vless://...
    vless://...

    Именно такой plain-text endpoint должен получать VPN-клиент.
    """

    servers = load_servers()

    headers = build_happ_headers(user)

    lines = []

    for header in headers:
        lines.append(header)

    if servers:
        lines.append("")

        for server in servers:
            lines.append(server)

    return "\n".join(lines).strip() + "\n"


# ============================================================
# USER SYNC
# ============================================================

def sync_user(user_id):
    """
    Перегенерирует персональную подписку пользователя.
    """

    user = get_user(user_id)

    if not user:
        return None

    token = user.get("token")

    if not token:
        return None

    content = build_subscription_content(user)

    if not content.strip():
        return None

    link = build_subscription_link(token)

    save_subscription_content(user_id, content)
    save_subscription_link(user_id, link)

    return {
        "user_id": user_id,
        "token": token,
        "link": link,
        "content": content,
    }


def ensure_subscription(user_id):
    """
    Гарантирует наличие персональной ссылки и содержимого.
    """

    user = get_user(user_id)

    if not user:
        return ""

    token = user.get("token")

    if not token:
        return ""

    link = user.get("subscription_link") or build_subscription_link(token)
    content = user.get("subscription_content") or ""

    if not content.strip():
        content = build_subscription_content(user)

    save_subscription_link(user_id, link)
    save_subscription_content(user_id, content)

    return link


# ============================================================
# SYNC ALL
# ============================================================

def sync_all_users():
    users = get_all_users()

    success = 0

    for user in users:
        try:
            user_id = int(user["user_id"])

            result = sync_user(user_id)

            if result:
                success += 1

        except Exception as e:
            print(
                f"[SUBSCRIPTION] sync error "
                f"user={user.get('user_id')}: {e}"
            )

    return success


def sync_all_active_users():
    """
    Оставлено для совместимости с остальным проектом.
    Сейчас синхронизируются все пользователи.
    """

    return sync_all_users()


def force_sync():
    return sync_all_users()


# ============================================================
# GITHUB CHECK
# ============================================================

def check_github_connection():
    try:
        url = (
            f"https://api.github.com/repos/"
            f"{GITHUB_OWNER}/{GITHUB_REPO}"
        )

        response = requests.get(
            url,
            headers=github_headers(),
            timeout=15,
        )

        if response.status_code == 200:
            return True

        print(
            f"[GITHUB] HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

        return False

    except Exception as e:
        print(f"[GITHUB] connection error: {e}")
        return False


def get_servers_info():
    servers = load_servers()

    return {
        "count": len(servers),
        "servers": servers,
    }


# ============================================================
# AUTO SYNC
# ============================================================

_sync_thread = None


def _auto_sync_worker():
    print(
        f"[SUBSCRIPTION] auto sync started, "
        f"interval={AUTO_SYNC_INTERVAL}s"
    )

    while True:
        try:
            sync_all_users()
        except Exception as e:
            print(f"[SUBSCRIPTION] auto sync error: {e}")

        time.sleep(max(60, int(AUTO_SYNC_INTERVAL)))


def start_auto_sync():
    global _sync_thread

    if not AUTO_SYNC_ENABLED:
        print("[SUBSCRIPTION] auto sync disabled")
        return

    if _sync_thread and _sync_thread.is_alive():
        return

    _sync_thread = threading.Thread(
        target=_auto_sync_worker,
        daemon=True,
        name="subscription-sync",
    )

    _sync_thread.start()