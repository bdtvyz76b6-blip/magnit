# subscription.py

import base64
import os
import threading
import time
from typing import Optional

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
)

from database import (
    get_user,
    get_all_users,
    get_subscription_content,
    save_subscription_content,
    get_subscription_link,
    save_subscription_link,
    is_subscription_active,
)


# ============================================================
# CONFIG
# ============================================================

GITHUB_API = "https://api.github.com"

USERS_DIR = "users"

SYNC_TIMEOUT = 30

_sync_lock = threading.Lock()
_auto_sync_started = False


# ============================================================
# GITHUB
# ============================================================

def github_headers():

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if GITHUB_TOKEN:
        headers["Authorization"] = (
            f"Bearer {GITHUB_TOKEN}"
        )

    return headers


def github_file_path(
    user_id: int,
) -> str:

    return (
        f"{USERS_DIR}/"
        f"{int(user_id)}.txt"
    )


def github_raw_url(
    user_id: int,
) -> str:

    return (
        f"https://raw.githubusercontent.com/"
        f"{GITHUB_OWNER}/"
        f"{GITHUB_REPO}/"
        f"{GITHUB_BRANCH}/"
        f"{github_file_path(user_id)}"
    )


# ============================================================
# LOCAL SERVER FILES
# ============================================================

def read_server_file(
    filename: str,
) -> list[str]:

    if not os.path.exists(filename):
        return []

    try:

        with open(
            filename,
            "r",
            encoding="utf-8",
        ) as file:

            lines = file.read().splitlines()

    except OSError:

        return []

    result = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        if not line.startswith(
            "vless://"
        ):
            continue

        result.append(line)

    return result


def get_active_servers() -> list[str]:

    return read_server_file(
        SERVERS_FILE
    )


def get_inactive_servers() -> list[str]:

    return read_server_file(
        NO_SERVERS_FILE
    )


# ============================================================
# USER STATUS
# ============================================================

def is_user_active(
    user_id: int,
) -> bool:

    try:
        return is_subscription_active(
            user_id
        )

    except Exception:

        user = get_user(user_id)

        if not user:
            return False

        if int(
            user.get(
                "blocked",
                0,
            )
            or 0
        ):
            return False

        return False


# ============================================================
# SUBSCRIPTION CONTENT
# ============================================================

def build_subscription_content(
    user_id: int,
) -> str:

    if is_user_active(user_id):

        servers = get_active_servers()

    else:

        servers = get_inactive_servers()

    if not servers:
        return ""

    return "\n".join(
        servers
    ) + "\n"


# ============================================================
# GITHUB GET
# ============================================================

def github_get_file(
    path: str,
):

    url = (
        f"{GITHUB_API}/repos/"
        f"{GITHUB_OWNER}/"
        f"{GITHUB_REPO}/contents/"
        f"{path}"
    )

    try:

        response = requests.get(
            url,
            headers=github_headers(),
            params={
                "ref": GITHUB_BRANCH,
            },
            timeout=SYNC_TIMEOUT,
        )

    except requests.RequestException as exc:

        raise RuntimeError(
            f"GitHub GET error: {exc}"
        )

    if response.status_code == 404:
        return None, None

    if response.status_code != 200:

        raise RuntimeError(
            "GitHub GET failed: "
            f"{response.status_code} "
            f"{response.text[:300]}"
        )

    data = response.json()

    encoded = data.get(
        "content",
        "",
    )

    sha = data.get(
        "sha"
    )

    if encoded:

        try:

            content = base64.b64decode(
                encoded.replace(
                    "\n",
                    "",
                )
            ).decode(
                "utf-8"
            )

        except Exception as exc:

            raise RuntimeError(
                f"GitHub decode error: {exc}"
            )

    else:

        content = ""

    return content, sha


# ============================================================
# GITHUB PUT
# ============================================================

def github_put_file(
    path: str,
    content: str,
    sha: Optional[str] = None,
    message: str = "",
):

    if not GITHUB_TOKEN:

        raise RuntimeError(
            "GITHUB_TOKEN не задан"
        )

    url = (
        f"{GITHUB_API}/repos/"
        f"{GITHUB_OWNER}/"
        f"{GITHUB_REPO}/contents/"
        f"{path}"
    )

    encoded = base64.b64encode(
        content.encode(
            "utf-8"
        )
    ).decode(
        "ascii"
    )

    payload = {
        "message": (
            message
            or f"Update {path}"
        ),
        "content": encoded,
        "branch": GITHUB_BRANCH,
    }

    if sha:
        payload["sha"] = sha

    try:

        response = requests.put(
            url,
            headers=github_headers(),
            json=payload,
            timeout=SYNC_TIMEOUT,
        )

    except requests.RequestException as exc:

        raise RuntimeError(
            f"GitHub PUT error: {exc}"
        )

    if response.status_code not in (
        200,
        201,
    ):

        raise RuntimeError(
            "GitHub PUT failed: "
            f"{response.status_code} "
            f"{response.text[:500]}"
        )

    return response.json()


# ============================================================
# SAVE RAW URL
# ============================================================

def ensure_raw_url(
    user_id: int,
) -> str:

    link = get_subscription_link(
        user_id
    )

    expected = github_raw_url(
        user_id
    )

    # Всегда используем постоянную
    # GitHub RAW-ссылку.
    if link != expected:

        save_subscription_link(
            user_id,
            expected,
        )

        return expected

    return link


# ============================================================
# SYNC ONE USER
# ============================================================

def sync_user(
    user_id: int,
    force: bool = False,
):

    user = get_user(
        user_id
    )

    if not user:
        return {
            "success": False,
            "status": "not_found",
            "user_id": user_id,
        }

    content = build_subscription_content(
        user_id
    )

    # Сохраняем актуальное содержимое
    # также локально в БД.
    save_subscription_content(
        user_id,
        content,
    )

    raw_url = ensure_raw_url(
        user_id
    )

    path = github_file_path(
        user_id
    )

    old_content, sha = github_get_file(
        path
    )

    # Если файл существует и содержимое
    # одинаковое — PUT не нужен.
    if (
        not force
        and old_content is not None
        and old_content == content
    ):

        return {
            "success": True,
            "status": "skipped",
            "user_id": user_id,
            "url": raw_url,
        }

    # Даже при force не делаем PUT,
    # если содержимое реально не изменилось.
    if (
        old_content is not None
        and old_content == content
    ):

        return {
            "success": True,
            "status": "skipped",
            "user_id": user_id,
            "url": raw_url,
        }

    result = github_put_file(
        path=path,
        content=content,
        sha=sha,
        message=(
            f"Update subscription "
            f"for user {user_id}"
        ),
    )

    return {
        "success": True,
        "status": (
            "created"
            if old_content is None
            else "updated"
        ),
        "user_id": user_id,
        "url": raw_url,
        "github": result,
    }


# ============================================================
# ENSURE SUBSCRIPTION
# ============================================================

def ensure_subscription(
    user_id: int,
):

    user = get_user(
        user_id
    )

    if not user:
        return None

    raw_url = ensure_raw_url(
        user_id
    )

    content = get_subscription_content(
        user_id
    )

    expected = build_subscription_content(
        user_id
    )

    # Если локального содержимого нет
    # или оно устарело — синхронизируем.
    if content != expected:

        try:

            result = sync_user(
                user_id
            )

            return {
                "url": raw_url,
                "result": result,
            }

        except Exception as exc:

            return {
                "url": raw_url,
                "error": str(exc),
            }

    # Если GitHub-файла ещё нет,
    # создаём его.
    try:

        github_content, _ = github_get_file(
            github_file_path(user_id)
        )

        if github_content is None:

            result = sync_user(
                user_id
            )

            return {
                "url": raw_url,
                "result": result,
            }

    except Exception as exc:

        return {
            "url": raw_url,
            "error": str(exc),
        }

    return {
        "url": raw_url,
        "result": {
            "success": True,
            "status": "ok",
        },
    }


# ============================================================
# FORCE SYNC ALL USERS
# ============================================================

def force_sync():

    if not _sync_lock.acquire(
        blocking=False
    ):

        return {
            "success": False,
            "status": "already_running",
            "total": 0,
            "updated": 0,
            "created": 0,
            "skipped": 0,
            "failed": 0,
            "active_servers": len(
                get_active_servers()
            ),
            "inactive_servers": len(
                get_inactive_servers()
            ),
        }

    try:

        active_servers = (
            get_active_servers()
        )

        inactive_servers = (
            get_inactive_servers()
        )

        users = get_all_users()

        updated = 0
        created = 0
        skipped = 0
        failed = 0

        errors = []

        for user in users:

            user_id = int(
                user["user_id"]
            )

            try:

                result = sync_user(
                    user_id,
                    force=False,
                )

                status = result.get(
                    "status"
                )

                if status == "updated":
                    updated += 1

                elif status == "created":
                    created += 1

                elif status == "skipped":
                    skipped += 1

                else:
                    skipped += 1

            except Exception as exc:

                failed += 1

                errors.append(
                    {
                        "user_id": user_id,
                        "error": str(exc),
                    }
                )

        return {
            "success": failed == 0,
            "status": "completed",

            "total": len(users),

            "updated": updated,
            "created": created,
            "skipped": skipped,
            "failed": failed,

            "active_servers": len(
                active_servers
            ),

            "inactive_servers": len(
                inactive_servers
            ),

            "errors": errors,
        }

    finally:

        _sync_lock.release()


# ============================================================
# UPDATE SERVERS
# ============================================================

def update_servers():

    return force_sync()


# ============================================================
# AUTO SYNC
# ============================================================

def auto_sync_loop():

    while True:

        try:

            force_sync()

        except Exception as exc:

            print(
                "[AUTO SYNC] ERROR:",
                exc,
            )

        time.sleep(
            max(
                30,
                int(
                    AUTO_SYNC_INTERVAL
                ),
            )
        )


def start_auto_sync():

    global _auto_sync_started

    if not AUTO_SYNC_ENABLED:
        return None

    if _auto_sync_started:
        return None

    _auto_sync_started = True

    thread = threading.Thread(
        target=auto_sync_loop,
        name="magnit-auto-sync",
        daemon=True,
    )

    thread.start()

    return thread


# ============================================================
# MANUAL USER REFRESH
# ============================================================

def refresh_user_subscription(
    user_id: int,
):

    return sync_user(
        user_id,
        force=False,
    )


# ============================================================
# CHECK SERVER FILES
# ============================================================

def get_server_info():

    active = get_active_servers()
    inactive = get_inactive_servers()

    return {
        "active": active,
        "inactive": inactive,
        "active_count": len(active),
        "inactive_count": len(inactive),
    }