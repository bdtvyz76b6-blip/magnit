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
# НАСТРОЙКИ
# ============================================================

GITHUB_API = "https://api.github.com"

# ВАЖНО:
# HTTP-заголовки должны содержать только ASCII.
# Поэтому здесь НЕ используется название сервиса,
# PROFILE_TITLE и любые кириллические символы.
HTTP_USER_AGENT = "magnit-vpn/1.0"


# ============================================================
# БЕЗОПАСНАЯ ОЧИСТКА HTTP ЗАГОЛОВКОВ
# ============================================================

def ascii_header_value(value):
    """
    Приводит значение HTTP-заголовка к безопасному ASCII.

    Это предотвращает:
    UnicodeEncodeError:
    'latin-1' codec can't encode characters
    """

    if value is None:
        return ""

    value = str(value).strip()

    # Удаляем всё, что не является ASCII.
    value = value.encode("ascii", "ignore").decode("ascii")

    return value


# ============================================================
# GITHUB HEADERS
# ============================================================

def github_headers():
    """
    Заголовки GitHub API.

    КРИТИЧНО:
    Никакой кириллицы и эмодзи здесь быть не должно.
    """

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": HTTP_USER_AGENT,
    }

    token = ascii_header_value(GITHUB_TOKEN)

    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


# ============================================================
# GITHUB URL
# ============================================================

def github_file_url(filename):
    filename = str(filename).strip().lstrip("/")

    return (
        f"{GITHUB_API}/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}/contents/{filename}"
        f"?ref={GITHUB_BRANCH}"
    )


# ============================================================
# LOAD GITHUB FILE
# ============================================================

def load_github_file(filename):
    """
    Загружает файл из GitHub.

    Возвращает обычный UTF-8 текст.
    """

    url = github_file_url(filename)

    try:
        response = requests.get(
            url,
            headers=github_headers(),
            timeout=20,
        )

    except requests.RequestException as e:
        print(f"[GITHUB] request error: {e}")
        return ""

    if response.status_code == 404:
        print(f"[GITHUB] file not found: {filename}")
        return ""

    if response.status_code != 200:
        print(
            f"[GITHUB] HTTP {response.status_code} "
            f"for {filename}: {response.text[:500]}"
        )
        return ""

    try:
        data = response.json()
    except Exception as e:
        print(f"[GITHUB] invalid JSON for {filename}: {e}")
        return ""

    encoded = data.get("content", "")

    if not encoded:
        return ""

    encoded = encoded.replace("\n", "").replace("\r", "").strip()

    try:
        decoded = base64.b64decode(encoded)
        return decoded.decode("utf-8")
    except Exception as e:
        print(f"[GITHUB] decode error for {filename}: {e}")
        return ""


# ============================================================
# SERVERS
# ============================================================

def clean_servers(content):
    """
    Оставляет только VLESS-ссылки.
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

        result.append(line)

    return result


def load_servers():
    """
    Сначала загружает servers.txt.

    Если файл пустой или недоступен,
    пробует no_servers.txt.
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
    Заголовки профиля Happ.

    Это НЕ HTTP-заголовки.
    Они находятся внутри содержимого подписки,
    поэтому здесь разрешены Unicode, кириллица и эмодзи.
    """

    headers = []

    title = str(PROFILE_TITLE or "").strip()

    if title:
        headers.append(
            f"#profile-title: {title}"
        )

    try:
        update_interval = int(PROFILE_UPDATE_INTERVAL)
    except (TypeError, ValueError):
        update_interval = 1

    headers.append(
        f"#profile-update-interval: {update_interval}"
    )

    try:
        upload = int(TRAFFIC_UPLOAD)
    except (TypeError, ValueError):
        upload = 0

    try:
        download = int(TRAFFIC_DOWNLOAD)
    except (TypeError, ValueError):
        download = 0

    try:
        total = int(TRAFFIC_TOTAL)
    except (TypeError, ValueError):
        total = 0

    headers.append(
        "#subscription-userinfo: "
        f"upload={upload};"
        f"download={download};"
        f"total={total}"
    )

    if HIDE_SETTINGS:
        headers.append("#profile-web-page-url:")
        headers.append("#profile-profile-web-page-url:")

    return headers


# ============================================================
# BUILD SUBSCRIPTION
# ============================================================

def build_subscription_content(user=None):
    """
    Создаёт обычную текстовую подписку для Happ.

    Формат:

    #profile-title: ...
    #profile-update-interval: ...
    #subscription-userinfo: ...

    vless://...
    vless://...
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
    Полностью пересоздаёт подписку пользователя.
    """

    user = get_user(user_id)

    if not user:
        print(f"[SUBSCRIPTION] user not found: {user_id}")
        return None

    token = user.get("token")

    if not token:
        print(f"[SUBSCRIPTION] token missing: {user_id}")
        return None

    try:
        content = build_subscription_content(user)
    except Exception as e:
        print(
            f"[SUBSCRIPTION] build error "
            f"user={user_id}: {e}"
        )
        return None

    if not content.strip():
        print(
            f"[SUBSCRIPTION] empty content "
            f"user={user_id}"
        )
        return None

    link = build_subscription_link(token)

    try:
        save_subscription_content(
            user_id,
            content,
        )

        save_subscription_link(
            user_id,
            link,
        )

    except Exception as e:
        print(
            f"[SUBSCRIPTION] database save error "
            f"user={user_id}: {e}"
        )
        return None

    return {
        "user_id": user_id,
        "token": token,
        "link": link,
        "content": content,
    }


# ============================================================
# ENSURE SUBSCRIPTION
# ============================================================

def ensure_subscription(user_id):
    """
    Гарантирует наличие ссылки и содержимого подписки.

    Используется web.py.
    """

    user = get_user(user_id)

    if not user:
        return ""

    token = user.get("token")

    if not token:
        return ""

    link = (
        user.get("subscription_link")
        or build_subscription_link(token)
    )

    content = (
        user.get("subscription_content")
        or ""
    )

    # Если подписка уже есть — просто сохраняем ссылку.
    if content.strip():

        try:
            save_subscription_link(
                user_id,
                link,
            )
        except Exception as e:
            print(
                f"[SUBSCRIPTION] link save error "
                f"user={user_id}: {e}"
            )

        return link

    # Если содержимого нет — создаём.
    try:
        content = build_subscription_content(user)
    except Exception as e:
        print(
            f"[SUBSCRIPTION] ensure build error "
            f"user={user_id}: {e}"
        )
        return ""

    if not content.strip():
        return ""

    try:
        save_subscription_link(
            user_id,
            link,
        )

        save_subscription_content(
            user_id,
            content,
        )

    except Exception as e:
        print(
            f"[SUBSCRIPTION] ensure save error "
            f"user={user_id}: {e}"
        )
        return ""

    return link


# ============================================================
# SYNC ALL USERS
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

    print(
        f"[SUBSCRIPTION] sync complete: "
        f"{success}/{len(users)}"
    )

    return success


def sync_all_active_users():
    """
    Совместимость со старым кодом.

    Сейчас синхронизируются все пользователи.
    """

    return sync_all_users()


def force_sync():
    return sync_all_users()


# ============================================================
# GITHUB CONNECTION CHECK
# ============================================================

def check_github_connection():

    try:

        url = (
            f"{GITHUB_API}/repos/"
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

    except requests.RequestException as e:

        print(
            f"[GITHUB] connection error: {e}"
        )

        return False


# ============================================================
# SERVERS INFO
# ============================================================

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
        "[SUBSCRIPTION] auto sync started, "
        f"interval={AUTO_SYNC_INTERVAL}s"
    )

    while True:

        try:

            sync_all_users()

        except Exception as e:

            print(
                f"[SUBSCRIPTION] "
                f"auto sync error: {e}"
            )

        try:

            interval = int(
                AUTO_SYNC_INTERVAL
            )

        except (TypeError, ValueError):

            interval = 600

        time.sleep(
            max(60, interval)
        )


def start_auto_sync():

    global _sync_thread

    if not AUTO_SYNC_ENABLED:

        print(
            "[SUBSCRIPTION] "
            "auto sync disabled"
        )

        return

    if (
        _sync_thread
        and _sync_thread.is_alive()
    ):

        return

    _sync_thread = threading.Thread(
        target=_auto_sync_worker,
        daemon=True,
        name="subscription-sync",
    )

    _sync_thread.start()

    print(
        "[SUBSCRIPTION] "
        "auto sync thread started"
    )