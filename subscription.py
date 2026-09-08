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


GITHUB_API = "https://api.github.com"

# Только ASCII!
USER_AGENT = "magnit-vpn/1.0"


# ============================================================
# HTTP
# ============================================================

def safe_ascii(value):
    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def github_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    }

    token = safe_ascii(GITHUB_TOKEN)

    # Убираем возможные кавычки из переменной Render
    token = token.strip("\"' ")

    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


def github_file_url(filename):
    filename = str(filename).strip().lstrip("/")

    return (
        f"{GITHUB_API}/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}/contents/"
        f"{filename}?ref={GITHUB_BRANCH}"
    )


# ============================================================
# GITHUB FILE
# ============================================================

def load_github_file(filename):
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
        print(f"[GITHUB] {filename}: 404")
        return ""

    if response.status_code != 200:
        print(
            f"[GITHUB] {filename}: "
            f"HTTP {response.status_code} "
            f"{response.text[:300]}"
        )
        return ""

    try:
        data = response.json()
    except Exception as e:
        print(f"[GITHUB] JSON error: {e}")
        return ""

    content = data.get("content", "")

    if not content:
        return ""

    try:
        content = content.replace("\n", "").replace("\r", "")

        decoded = base64.b64decode(content)

        return decoded.decode("utf-8")

    except Exception as e:
        print(f"[GITHUB] decode error: {e}")
        return ""


# ============================================================
# SERVERS
# ============================================================

def clean_servers(content):
    if not content:
        return []

    result = []
    seen = set()

    for raw in content.splitlines():

        line = raw.strip()

        if not line:
            continue

        if not line.startswith("vless://"):
            continue

        # Убираем случайные пробелы
        line = line.strip()

        # Не добавляем дубли
        if line in seen:
            continue

        seen.add(line)
        result.append(line)

    return result


def load_servers():
    content = load_github_file(SERVERS_FILE)

    servers = clean_servers(content)

    if servers:
        return servers

    print(
        f"[SUBSCRIPTION] {SERVERS_FILE} empty, "
        f"trying {NO_SERVERS_FILE}"
    )

    fallback = load_github_file(NO_SERVERS_FILE)

    return clean_servers(fallback)


# ============================================================
# HAPP PROFILE
# ============================================================

def build_happ_headers(user=None):

    headers = []

    title = str(PROFILE_TITLE or "").strip()

    if title:
        headers.append(
            f"#profile-title: {title}"
        )

    try:
        interval = int(PROFILE_UPDATE_INTERVAL)
    except (TypeError, ValueError):
        interval = 1

    headers.append(
        f"#profile-update-interval: {interval}"
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
        headers.append(
            "#profile-web-page-url:"
        )

        headers.append(
            "#profile-profile-web-page-url:"
        )

    return headers


# ============================================================
# SUBSCRIPTION CONTENT
# ============================================================

def build_subscription_content(user=None):

    servers = load_servers()

    lines = []

    # Happ metadata
    lines.extend(
        build_happ_headers(user)
    )

    # VLESS
    if servers:

        lines.append("")

        lines.extend(servers)

    content = "\n".join(lines).strip()

    if not content:
        return ""

    return content + "\n"


# ============================================================
# USER SUBSCRIPTION
# ============================================================

def sync_user(user_id):

    user = get_user(user_id)

    if not user:
        print(
            f"[SUBSCRIPTION] user {user_id} not found"
        )
        return None

    token = user.get("token")

    if not token:
        print(
            f"[SUBSCRIPTION] user {user_id}: "
            f"token missing"
        )
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
            f"[SUBSCRIPTION] empty subscription "
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
            f"[SUBSCRIPTION] database error "
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
# ENSURE
# ============================================================

def ensure_subscription(user_id):

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

    # Уже существует
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

    # Создаём новую
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
            f"[SUBSCRIPTION] ensure save error "
            f"user={user_id}: {e}"
        )

        return ""

    return link


# ============================================================
# SYNC ALL
# ============================================================

def sync_all_users():

    users = get_all_users()

    success = 0

    for user in users:

        try:

            user_id = int(
                user["user_id"]
            )

            if sync_user(user_id):
                success += 1

        except Exception as e:

            print(
                "[SUBSCRIPTION] sync error "
                f"user={user.get('user_id')}: {e}"
            )

    print(
        f"[SUBSCRIPTION] "
        f"sync complete: {success}/{len(users)}"
    )

    return success


def sync_all_active_users():
    return sync_all_users()


def force_sync():
    return sync_all_users()


# ============================================================
# GITHUB CHECK
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
            f"[GITHUB] HTTP "
            f"{response.status_code}: "
            f"{response.text[:500]}"
        )

        return False

    except requests.RequestException as e:

        print(
            f"[GITHUB] connection error: {e}"
        )

        return False


# ============================================================
# SERVER INFO
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
        "[SUBSCRIPTION] auto sync started "
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