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
    PROFILE_TITLE,
    PROFILE_UPDATE_INTERVAL,
    TRAFFIC_TOTAL,
    TRAFFIC_UPLOAD,
    TRAFFIC_DOWNLOAD,
    HIDE_SETTINGS,
    AUTO_SYNC_ENABLED,
    AUTO_SYNC_INTERVAL,
    PUBLIC_URL,
)

from database import (
    get_user,
    get_all_users,
    get_subscription_content,
    save_subscription_content,
)


# ============================================================
# CONFIG
# ============================================================

GITHUB_API = "https://api.github.com"

GITHUB_USERS_PATH = "users"

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
}

_sync_lock = threading.Lock()
_auto_sync_started = False


# ============================================================
# URL
# ============================================================

def github_file_path(user_id: int) -> str:
    return f"{GITHUB_USERS_PATH}/{user_id}.txt"


def github_raw_url(user_id: int) -> str:
    return (
        f"https://raw.githubusercontent.com/"
        f"{GITHUB_OWNER}/"
        f"{GITHUB_REPO}/"
        f"{GITHUB_BRANCH}/"
        f"{github_file_path(user_id)}"
    )


def subscription_url(user_id: int) -> str:
    return github_raw_url(user_id)


# ============================================================
# FILES
# ============================================================

def read_server_file(filename: str) -> list[str]:
    """
    Читает servers.txt / no_servers.txt.

    Пустые строки и строки с # игнорируются.
    Дубликаты удаляются с сохранением порядка.
    """

    if not filename:
        return []

    if not os.path.exists(filename):
        return []

    result = []
    seen = set()

    try:
        with open(
            filename,
            "r",
            encoding="utf-8",
        ) as file:

            for raw in file:
                line = raw.strip()

                if not line:
                    continue

                if line.startswith("#"):
                    continue

                if line in seen:
                    continue

                seen.add(line)
                result.append(line)

    except Exception as exc:
        print(
            f"[SUBSCRIPTION] Ошибка чтения "
            f"{filename}: {exc}"
        )

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

def is_user_active(user) -> bool:
    """
    Проверяет, действует ли подписка.
    """

    if not user:
        return False

    if int(
        user.get("blocked", 0) or 0
    ):
        return False

    value = (
        user.get(
            "subscription_until",
            "",
        )
        or ""
    ).strip()

    if not value:
        return False

    try:
        from database import parse_datetime, now_utc

        expire = parse_datetime(value)

        if not expire:
            return False

        return expire > now_utc()

    except Exception:
        return False


# ============================================================
# SUBSCRIPTION CONTENT
# ============================================================

def build_subscription_content(
    user_id: int,
) -> str:
    """
    Формирует содержимое подписки.

    Активный пользователь:
        servers.txt

    Неактивный / заблокированный:
        no_servers.txt
    """

    user = get_user(user_id)

    if not user:
        return ""

    if is_user_active(user):
        servers = get_active_servers()
    else:
        servers = get_inactive_servers()

    valid_links = []

    for link in servers:

        link = link.strip()

        if not link:
            continue

        if not link.startswith(
            "vless://"
        ):
            continue

        valid_links.append(link)

    return "\n".join(
        valid_links
    )


# ============================================================
# GITHUB GET
# ============================================================

def github_get_file(
    user_id: int,
) -> tuple[Optional[str], Optional[str]]:

    url = (
        f"{GITHUB_API}/repos/"
        f"{GITHUB_OWNER}/"
        f"{GITHUB_REPO}/contents/"
        f"{github_file_path(user_id)}"
    )

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params={
                "ref": GITHUB_BRANCH,
            },
            timeout=20,
        )

        if response.status_code == 404:
            return None, None

        response.raise_for_status()

        data = response.json()

        encoded = data.get(
            "content",
            "",
        )

        sha = data.get("sha")

        if not encoded:
            return "", sha

        encoded = encoded.replace(
            "\n",
            "",
        )

        content = base64.b64decode(
            encoded
        ).decode(
            "utf-8"
        )

        return content, sha

    except Exception as exc:

        print(
            f"[GITHUB GET] user={user_id}: "
            f"{exc}"
        )

        return None, None


# ============================================================
# GITHUB PUT
# ============================================================

def github_put_file(
    user_id: int,
    content: str,
    sha: Optional[str] = None,
) -> bool:

    url = (
        f"{GITHUB_API}/repos/"
        f"{GITHUB_OWNER}/"
        f"{GITHUB_REPO}/contents/"
        f"{github_file_path(user_id)}"
    )

    encoded = base64.b64encode(
        content.encode("utf-8")
    ).decode("ascii")

    payload = {
        "message": (
            f"Update subscription "
            f"{user_id}"
        ),
        "content": encoded,
        "branch": GITHUB_BRANCH,
    }

    if sha:
        payload["sha"] = sha

    try:
        response = requests.put(
            url,
            headers=HEADERS,
            json=payload,
            timeout=30,
        )

        if response.status_code == 409:
            # SHA устарел — перечитываем
            current, current_sha = (
                github_get_file(user_id)
            )

            if current_sha:
                payload["sha"] = current_sha

                response = requests.put(
                    url,
                    headers=HEADERS,
                    json=payload,
                    timeout=30,
                )

        response.raise_for_status()

        return True

    except Exception as exc:

        print(
            f"[GITHUB PUT] user={user_id}: "
            f"{exc}"
        )

        return False


# ============================================================
# SYNC USER
# ============================================================

def sync_user(
    user_id: int,
    force: bool = False,
) -> bool:
    """
    Обновляет одного пользователя.

    force=True:
        перепроверяет GitHub и обновляет файл,
        если содержимое изменилось.

    Важно:
        ссылка пользователя не меняется.
    """

    user = get_user(user_id)

    if not user:
        return False

    content = build_subscription_content(
        user_id
    )

    if not content:
        print(
            f"[SYNC] user={user_id}: "
            f"пустая подписка"
        )

    old_content = (
        get_subscription_content(
            user_id
        )
        or ""
    )

    github_content, sha = (
        github_get_file(user_id)
    )

    # Если GitHub уже содержит актуальные данные,
    # ничего не перезаписываем.
    if (
        not force
        and github_content is not None
        and github_content == content
    ):
        save_subscription_content(
            user_id,
            content,
        )
        return True

    # Даже при force не создаём бессмысленный PUT,
    # если содержимое абсолютно такое же.
    if (
        github_content is not None
        and github_content == content
    ):
        save_subscription_content(
            user_id,
            content,
        )
        return True

    success = github_put_file(
        user_id,
        content,
        sha,
    )

    if not success:
        return False

    save_subscription_content(
        user_id,
        content,
    )

    return True


# ============================================================
# ENSURE SUBSCRIPTION
# ============================================================

def ensure_subscription(
    user_id: int,
):
    """
    Гарантирует наличие актуального GitHub RAW-файла.
    """

    user = get_user(user_id)

    if not user:
        return None

    content = build_subscription_content(
        user_id
    )

    current_content, sha = (
        github_get_file(user_id)
    )

    if (
        current_content != content
    ):
        if not github_put_file(
            user_id,
            content,
            sha,
        ):
            return None

    save_subscription_content(
        user_id,
        content,
    )

    return {
        "url": github_raw_url(
            user_id
        ),
        "content": content,
    }


# ============================================================
# FORCE SYNC ALL
# ============================================================

def force_sync() -> dict:
    """
    Полное ручное обновление серверов.

    Вызывается кнопкой:
        🔄 Обновить серверы

    Что происходит:

    1. заново читаются servers.txt
    2. заново читается no_servers.txt
    3. берутся все пользователи
    4. для каждого формируется актуальная подписка
    5. GitHub users/{id}.txt обновляется
    """

    if not GITHUB_TOKEN:
        return {
            "success": False,
            "total": 0,
            "updated": 0,
            "failed": 0,
            "skipped": 0,
            "error": (
                "GITHUB_TOKEN не задан"
            ),
        }

    if not _sync_lock.acquire(
        blocking=False
    ):
        return {
            "success": False,
            "total": 0,
            "updated": 0,
            "failed": 0,
            "skipped": 0,
            "error": (
                "Синхронизация уже выполняется"
            ),
        }

    try:

        # ВАЖНО:
        # перечитываем файлы непосредственно
        # перед обновлением.
        active_servers = (
            get_active_servers()
        )

        inactive_servers = (
            get_inactive_servers()
        )

        users = get_all_users()

        total = len(users)
        updated = 0
        failed = 0
        skipped = 0

        print(
            "[FORCE SYNC] "
            f"Рабочих серверов: "
            f"{len(active_servers)}"
        )

        print(
            "[FORCE SYNC] "
            f"Неактивных серверов: "
            f"{len(inactive_servers)}"
        )

        print(
            "[FORCE SYNC] "
            f"Пользователей: {total}"
        )

        for user in users:

            user_id = int(
                user["user_id"]
            )

            try:

                content = (
                    build_subscription_content(
                        user_id
                    )
                )

                github_content, sha = (
                    github_get_file(
                        user_id
                    )
                )

                # Уже актуально
                if (
                    github_content is not None
                    and github_content == content
                ):

                    save_subscription_content(
                        user_id,
                        content,
                    )

                    skipped += 1
                    continue

                success = github_put_file(
                    user_id,
                    content,
                    sha,
                )

                if success:

                    save_subscription_content(
                        user_id,
                        content,
                    )

                    updated += 1

                else:
                    failed += 1

            except Exception as exc:

                failed += 1

                print(
                    f"[FORCE SYNC] "
                    f"user={user_id}: "
                    f"{exc}"
                )

            # Не спамим GitHub API
            time.sleep(0.05)

        return {
            "success": failed == 0,
            "total": total,
            "updated": updated,
            "failed": failed,
            "skipped": skipped,
            "active_servers": len(
                active_servers
            ),
            "inactive_servers": len(
                inactive_servers
            ),
        }

    finally:
        _sync_lock.release()


# ============================================================
# AUTO SYNC
# ============================================================

def auto_sync_loop():

    print(
        "[AUTO SYNC] запущен"
    )

    while True:

        try:

            force_sync()

        except Exception as exc:

            print(
                f"[AUTO SYNC] ошибка: "
                f"{exc}"
            )

        time.sleep(
            max(
                60,
                AUTO_SYNC_INTERVAL,
            )
        )


def start_auto_sync():

    global _auto_sync_started

    if not AUTO_SYNC_ENABLED:
        print(
            "[AUTO SYNC] отключён"
        )
        return

    if _auto_sync_started:
        return

    _auto_sync_started = True

    thread = threading.Thread(
        target=auto_sync_loop,
        daemon=True,
        name="magnit-auto-sync",
    )

    thread.start()

    print(
        "[AUTO SYNC] поток запущен"
    )


# ============================================================
# MANUAL SERVER UPDATE
# ============================================================

def update_servers() -> dict:
    """
    Алиас для админки.
    """

    return force_sync()