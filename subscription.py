import os
import base64
import threading
import time
import requests

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# CONFIG
# ============================================================

GITHUB_API = "https://api.github.com"

GITHUB_TOKEN = os.getenv(
    "GITHUB_TOKEN",
    "",
)

GITHUB_OWNER = os.getenv(
    "GITHUB_OWNER",
    "bdtvyz76b6-blip",
)

GITHUB_REPO = os.getenv(
    "GITHUB_REPO",
    "magnit",
)

GITHUB_BRANCH = os.getenv(
    "GITHUB_BRANCH",
    "main",
)

GITHUB_USERS_PATH = os.getenv(
    "GITHUB_USERS_PATH",
    "users",
).strip("/")

SERVERS_FILE = os.getenv(
    "SERVERS_FILE",
    "servers.txt",
)

NO_SERVERS_FILE = os.getenv(
    "NO_SERVERS_FILE",
    "",
)

AUTO_SYNC_ENABLED = (
    os.getenv(
        "AUTO_SYNC_ENABLED",
        "true",
    ).lower()
    in ("1", "true", "yes", "on")
)

try:
    AUTO_SYNC_INTERVAL = int(
        os.getenv(
            "AUTO_SYNC_INTERVAL",
            "600",
        )
    )
except ValueError:
    AUTO_SYNC_INTERVAL = 600


PROFILE_TITLE = os.getenv(
    "PROFILE_TITLE",
    "Магнит VPN",
)

try:
    PROFILE_UPDATE_INTERVAL = int(
        os.getenv(
            "PROFILE_UPDATE_INTERVAL",
            "6",
        )
    )
except ValueError:
    PROFILE_UPDATE_INTERVAL = 6


try:
    TRAFFIC_TOTAL = int(
        os.getenv(
            "TRAFFIC_TOTAL",
            "0",
        )
    )
except ValueError:
    TRAFFIC_TOTAL = 0


try:
    TRAFFIC_UPLOAD = int(
        os.getenv(
            "TRAFFIC_UPLOAD",
            "0",
        )
    )
except ValueError:
    TRAFFIC_UPLOAD = 0


try:
    TRAFFIC_DOWNLOAD = int(
        os.getenv(
            "TRAFFIC_DOWNLOAD",
            "0",
        )
    )
except ValueError:
    TRAFFIC_DOWNLOAD = 0


HIDE_SETTINGS = (
    os.getenv(
        "HIDE_SETTINGS",
        "true",
    ).lower()
    in ("1", "true", "yes", "on")
)


USER_AGENT = "magnit-vpn/1.0"


# ============================================================
# DATABASE
# ============================================================

from database import (
    get_user,
    get_all_users,
    save_subscription_content,
    save_subscription_link,
    build_subscription_link,
    get_nodes,
)


# ============================================================
# ASCII
# ============================================================

def safe_ascii(value):

    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .encode(
            "ascii",
            "ignore",
        )
        .decode("ascii")
    )


# ============================================================
# GITHUB HEADERS
# ============================================================

def github_headers():

    headers = {
        "Accept": (
            "application/vnd.github+json"
        ),
        "X-GitHub-Api-Version":
            "2022-11-28",
        "User-Agent":
            USER_AGENT,
    }

    token = safe_ascii(
        GITHUB_TOKEN
    )

    token = token.strip(
        "\"' "
    )

    if token:
        headers["Authorization"] = (
            f"Bearer {token}"
        )

    return headers


# ============================================================
# GITHUB PATH
# ============================================================

def github_file_path(
    user_id,
):
    return (
        f"{GITHUB_USERS_PATH}/"
        f"{int(user_id)}.txt"
    )


def github_file_url(
    path,
):
    path = str(path).strip().lstrip("/")

    return (
        f"{GITHUB_API}/repos/"
        f"{GITHUB_OWNER}/"
        f"{GITHUB_REPO}/contents/"
        f"{path}"
        f"?ref={GITHUB_BRANCH}"
    )


# ============================================================
# LOAD GITHUB FILE
# ============================================================

def load_github_file(
    filename,
):

    url = github_file_url(
        filename
    )

    try:

        response = requests.get(
            url,
            headers=github_headers(),
            timeout=20,
        )

    except requests.RequestException as e:

        print(
            f"[GITHUB] request error: {e}"
        )

        return ""


    if response.status_code == 404:

        print(
            f"[GITHUB] {filename}: 404"
        )

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

        print(
            f"[GITHUB] JSON error: {e}"
        )

        return ""


    content = data.get(
        "content",
        "",
    )

    if not content:
        return ""


    try:

        content = (
            content
            .replace("\n", "")
            .replace("\r", "")
        )

        decoded = base64.b64decode(
            content
        )

        return decoded.decode(
            "utf-8"
        )

    except Exception as e:

        print(
            f"[GITHUB] decode error: {e}"
        )

        return ""


# ============================================================
# LOAD SERVERS
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

        if not line.startswith(
            "vless://"
        ):
            continue

        if line in seen:
            continue

        seen.add(line)

        result.append(line)

    return result


def load_servers():

    content = load_github_file(
        SERVERS_FILE
    )

    servers = clean_servers(
        content
    )

    if servers:
        return servers


    if NO_SERVERS_FILE:

        print(
            f"[SUBSCRIPTION] "
            f"{SERVERS_FILE} empty, "
            f"trying {NO_SERVERS_FILE}"
        )

        fallback = load_github_file(
            NO_SERVERS_FILE
        )

        return clean_servers(
            fallback
        )

    return []


# ============================================================
# HAPP HEADERS
# ============================================================

def build_happ_headers(
    user=None,
):

    headers = []

    if PROFILE_TITLE:

        headers.append(
            f"#profile-title: "
            f"{PROFILE_TITLE}"
        )


    headers.append(
        "#profile-update-interval: "
        f"{PROFILE_UPDATE_INTERVAL}"
    )


    upload = TRAFFIC_UPLOAD
    download = TRAFFIC_DOWNLOAD
    total = TRAFFIC_TOTAL


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

def build_subscription_content(
    user=None,
):

    servers = load_servers()

    lines = []

    lines.extend(
        build_happ_headers(user)
    )

    if servers:

        lines.append("")

        lines.extend(
            servers
        )

    content = "\n".join(
        lines
    ).strip()

    if not content:
        return ""

    return content + "\n"


# ============================================================
# GITHUB UPDATE / CREATE
# ============================================================

def upload_user_subscription(
    user_id,
    content,
):

    if not GITHUB_TOKEN:

        print(
            "[GITHUB] "
            "GITHUB_TOKEN is missing"
        )

        return False


    path = github_file_path(
        user_id
    )

    url = github_file_url(
        path
    )


    encoded = base64.b64encode(
        content.encode("utf-8")
    ).decode("ascii")


    sha = None


    # ========================================================
    # GET EXISTING FILE
    # ========================================================

    try:

        response = requests.get(
            url,
            headers=github_headers(),
            timeout=20,
        )

    except requests.RequestException as e:

        print(
            f"[GITHUB] GET error "
            f"user={user_id}: {e}"
        )

        return False


    if response.status_code == 200:

        try:

            data = response.json()

            sha = data.get(
                "sha"
            )

        except Exception as e:

            print(
                f"[GITHUB] "
                f"SHA error: {e}"
            )

            return False


    elif response.status_code != 404:

        print(
            f"[GITHUB] "
            f"GET user={user_id}: "
            f"HTTP {response.status_code} "
            f"{response.text[:500]}"
        )

        return False


    # ========================================================
    # PUT
    # ========================================================

    payload = {
        "message":
            f"Update subscription "
            f"for {user_id}",

        "content":
            encoded,

        "branch":
            GITHUB_BRANCH,
    }


    if sha:
        payload["sha"] = sha


    try:

        response = requests.put(
            url,
            headers=github_headers(),
            json=payload,
            timeout=30,
        )

    except requests.RequestException as e:

        print(
            f"[GITHUB] PUT error "
            f"user={user_id}: {e}"
        )

        return False


    if response.status_code not in (
        200,
        201,
    ):

        print(
            f"[GITHUB] PUT user={user_id}: "
            f"HTTP {response.status_code} "
            f"{response.text[:1000]}"
        )

        return False


    print(
        f"[GITHUB] "
        f"users/{user_id}.txt updated"
    )

    return True


# ============================================================
# RAW URL
# ============================================================

def build_github_subscription_link(
    user_id,
):

    return (
        "https://raw.githubusercontent.com/"
        f"{GITHUB_OWNER}/"
        f"{GITHUB_REPO}/"
        f"{GITHUB_BRANCH}/"
        f"{github_file_path(user_id)}"
    )


# ============================================================
# SYNC USER
# ============================================================

def sync_user(
    user_id,
):

    user = get_user(
        user_id
    )

    if not user:

        print(
            f"[SUBSCRIPTION] "
            f"user {user_id} not found"
        )

        return None


    token = user.get(
        "token"
    )

    if not token:

        print(
            f"[SUBSCRIPTION] "
            f"user {user_id}: token missing"
        )

        return None


    try:

        content = build_subscription_content(
            user
        )

    except Exception as e:

        print(
            f"[SUBSCRIPTION] "
            f"build error "
            f"user={user_id}: {e}"
        )

        return None


    if not content.strip():

        print(
            f"[SUBSCRIPTION] "
            f"empty subscription "
            f"user={user_id}"
        )

        return None


    # ========================================================
    # GITHUB
    # ========================================================

    github_link = (
        build_github_subscription_link(
            user_id
        )
    )


    if not upload_user_subscription(
        user_id,
        content,
    ):
        return None


    # ========================================================
    # DATABASE
    # ========================================================

    try:

        save_subscription_content(
            user_id,
            content,
        )

        # Для кабинета теперь сохраняем
        # именно прямую GitHub-ссылку.

        save_subscription_link(
            user_id,
            github_link,
        )

    except Exception as e:

        print(
            f"[SUBSCRIPTION] "
            f"database error "
            f"user={user_id}: {e}"
        )

        return None


    return {
        "user_id": user_id,
        "token": token,
        "link": github_link,
        "content": content,
    }


# ============================================================
# ENSURE
# ============================================================

def ensure_subscription(
    user_id,
):

    user = get_user(
        user_id
    )

    if not user:
        return ""


    token = user.get(
        "token"
    )

    if not token:
        return ""


    github_link = (
        build_github_subscription_link(
            user_id
        )
    )


    # Если контент уже есть,
    # всё равно возвращаем GitHub URL.

    content = (
        user.get(
            "subscription_content",
            "",
        )
        or ""
    )


    if content.strip():

        try:

            save_subscription_link(
                user_id,
                github_link,
            )

        except Exception as e:

            print(
                f"[SUBSCRIPTION] "
                f"link save error "
                f"user={user_id}: {e}"
            )

        return github_link


    result = sync_user(
        user_id
    )

    if not result:
        return ""

    return result["link"]


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

            if sync_user(
                user_id
            ):
                success += 1

        except Exception as e:

            print(
                "[SUBSCRIPTION] "
                f"sync error "
                f"user={user.get('user_id')}: {e}"
            )


    print(
        "[SUBSCRIPTION] "
        f"sync complete: "
        f"{success}/{len(users)}"
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
            f"{GITHUB_OWNER}/"
            f"{GITHUB_REPO}"
        )

        response = requests.get(
            url,
            headers=github_headers(),
            timeout=15,
        )

        if response.status_code == 200:
            return True


        print(
            f"[GITHUB] "
            f"HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

        return False

    except requests.RequestException as e:

        print(
            f"[GITHUB] "
            f"connection error: {e}"
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
        "[SUBSCRIPTION] "
        "auto sync started "
        f"interval={AUTO_SYNC_INTERVAL}s"
    )


    while True:

        try:

            sync_all_users()

        except Exception as e:

            print(
                "[SUBSCRIPTION] "
                f"auto sync error: {e}"
            )


        try:

            interval = int(
                AUTO_SYNC_INTERVAL
            )

        except (
            TypeError,
            ValueError,
        ):

            interval = 600


        time.sleep(
            max(
                60,
                interval,
            )
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
        and
        _sync_thread.is_alive()
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