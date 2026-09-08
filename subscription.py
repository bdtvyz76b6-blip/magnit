import os
import time
import base64
import threading
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from database import (
    get_user,
    save_subscription_link,
    save_subscription_content,
)

load_dotenv()


# ============================================================
# CONFIG
# ============================================================

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "bdtvyz76b6-blip").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "magnit").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()
GITHUB_USERS_PATH = os.getenv("GITHUB_USERS_PATH", "users").strip("/")

SERVERS_FILE = os.getenv("SERVERS_FILE", "servers.txt")
NO_SERVERS_FILE = os.getenv("NO_SERVERS_FILE", "no_servers.txt")

PROFILE_TITLE = os.getenv(
    "PROFILE_TITLE",
    "𝗦𝗨𝗕 - 𝗠𝗔𝗚𝗡𝗜𝗧 𝗩𝗣𝗡 🧲",
)

try:
    PROFILE_UPDATE_INTERVAL = int(
        os.getenv("PROFILE_UPDATE_INTERVAL", "1")
    )
except ValueError:
    PROFILE_UPDATE_INTERVAL = 1

TRAFFIC_TOTAL = os.getenv("TRAFFIC_TOTAL", "0")
TRAFFIC_UPLOAD = os.getenv("TRAFFIC_UPLOAD", "0")
TRAFFIC_DOWNLOAD = os.getenv("TRAFFIC_DOWNLOAD", "0")

HIDE_SETTINGS = os.getenv("HIDE_SETTINGS", "1")

try:
    AUTO_SYNC_ENABLED = int(
        os.getenv("AUTO_SYNC_ENABLED", "1")
    )
except ValueError:
    AUTO_SYNC_ENABLED = 1

try:
    AUTO_SYNC_INTERVAL = int(
        os.getenv("AUTO_SYNC_INTERVAL", "600")
    )
except ValueError:
    AUTO_SYNC_INTERVAL = 600


# ============================================================
# GITHUB
# ============================================================

GITHUB_API = "https://api.github.com"


def github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }


def github_file_path(user_id):
    return f"{GITHUB_USERS_PATH}/{int(user_id)}.txt"


def build_github_subscription_url(user_id):
    return (
        f"https://raw.githubusercontent.com/"
        f"{GITHUB_OWNER}/"
        f"{GITHUB_REPO}/"
        f"{GITHUB_BRANCH}/"
        f"{github_file_path(user_id)}"
    )


# ============================================================
# SERVERS
# ============================================================

def read_lines(filename):
    if not filename:
        return []

    if not os.path.exists(filename):
        return []

    result = []

    try:
        with open(
            filename,
            "r",
            encoding="utf-8",
        ) as file:
            for line in file:
                line = line.strip()

                if not line:
                    continue

                if line.startswith("#"):
                    continue

                result.append(line)

    except Exception as e:
        print(
            f"[SUBSCRIPTION] Ошибка чтения "
            f"{filename}: {e}"
        )

    return result


def get_servers():
    servers = []

    servers.extend(
        read_lines(SERVERS_FILE)
    )

    if NO_SERVERS_FILE:
        servers.extend(
            read_lines(NO_SERVERS_FILE)
        )

    # Убираем дубликаты, сохраняя порядок
    unique = []

    for server in servers:
        if server not in unique:
            unique.append(server)

    return unique


# ============================================================
# SUBSCRIPTION CONTENT
# ============================================================

def build_subscription_content(user_id):
    """
    Создаёт содержимое пользовательской подписки.

    Формат:
    обычные VLESS-ссылки по одной на строку.
    """

    servers = get_servers()

    if not servers:
        print(
            f"[SUBSCRIPTION] Для пользователя "
            f"{user_id} нет серверов."
        )

        return ""

    return "\n".join(servers)


# ============================================================
# GITHUB GET
# ============================================================

def get_github_file(user_id):
    """
    Получает существующий файл пользователя.

    Возвращает:
        {
            "sha": "...",
            "content": "..."
        }

    или None.
    """

    if not GITHUB_TOKEN:
        print(
            "[GITHUB] GITHUB_TOKEN не задан."
        )
        return None

    path = github_file_path(user_id)

    url = (
        f"{GITHUB_API}/repos/"
        f"{GITHUB_OWNER}/"
        f"{GITHUB_REPO}/"
        f"/contents/{path}"
    )

    params = {
        "ref": GITHUB_BRANCH,
    }

    try:
        response = requests.get(
            url,
            headers=github_headers(),
            params=params,
            timeout=20,
        )

    except Exception as e:
        print(
            f"[GITHUB] Ошибка GET: {e}"
        )
        return None

    if response.status_code == 404:
        return None

    if response.status_code != 200:
        print(
            "[GITHUB] GET ошибка:",
            response.status_code,
            response.text[:500],
        )
        return None

    try:
        data = response.json()

        encoded = data.get("content", "")
        encoded = encoded.replace("\n", "")

        content = base64.b64decode(
            encoded
        ).decode(
            "utf-8",
            errors="replace",
        )

        return {
            "sha": data.get("sha"),
            "content": content,
        }

    except Exception as e:
        print(
            f"[GITHUB] Ошибка обработки файла: {e}"
        )
        return None


# ============================================================
# GITHUB CREATE / UPDATE
# ============================================================

def upload_github_file(user_id, content):
    """
    Реально создаёт или обновляет:

    users/{user_id}.txt

    в GitHub.
    """

    if not GITHUB_TOKEN:
        print(
            "[GITHUB] ОШИБКА: "
            "GITHUB_TOKEN не задан."
        )
        return False

    path = github_file_path(user_id)

    url = (
        f"{GITHUB_API}/repos/"
        f"{GITHUB_OWNER}/"
        f"{GITHUB_REPO}/"
        f"/contents/{path}"
    )

    # --------------------------------------------------------
    # Сначала проверяем, существует ли файл
    # --------------------------------------------------------

    existing = get_github_file(user_id)

    encoded_content = base64.b64encode(
        content.encode("utf-8")
    ).decode("utf-8")

    payload = {
        "message": (
            f"Update subscription "
            f"for user {user_id}"
        ),
        "content": encoded_content,
        "branch": GITHUB_BRANCH,
    }

    # Если файл уже существует —
    # обязательно передаём SHA.
    if existing and existing.get("sha"):
        payload["sha"] = existing["sha"]

    try:
        response = requests.put(
            url,
            headers=github_headers(),
            json=payload,
            timeout=30,
        )

    except Exception as e:
        print(
            f"[GITHUB] Ошибка PUT: {e}"
        )
        return False

    # --------------------------------------------------------
    # Успех
    # --------------------------------------------------------

    if response.status_code in (200, 201):
        print(
            f"[GITHUB] Файл успешно "
            f"{'обновлён' if existing else 'создан'}: "
            f"{path}"
        )

        return True

    # --------------------------------------------------------
    # Если SHA устарел — повторяем запрос
    # --------------------------------------------------------

    if response.status_code == 409:
        print(
            "[GITHUB] Конфликт SHA. "
            "Получаем новый SHA..."
        )

        latest = get_github_file(user_id)

        if latest and latest.get("sha"):
            payload["sha"] = latest["sha"]

            try:
                retry = requests.put(
                    url,
                    headers=github_headers(),
                    json=payload,
                    timeout=30,
                )

                if retry.status_code in (
                    200,
                    201,
                ):
                    print(
                        f"[GITHUB] Файл обновлён "
                        f"после повторной попытки: "
                        f"{path}"
                    )

                    return True

                print(
                    "[GITHUB] Повторный PUT ошибка:",
                    retry.status_code,
                    retry.text[:500],
                )

            except Exception as e:
                print(
                    f"[GITHUB] Ошибка повторного PUT: {e}"
                )

        return False

    print(
        "[GITHUB] PUT ошибка:",
        response.status_code,
        response.text[:1000],
    )

    return False


# ============================================================
# SYNC USER
# ============================================================

def sync_user(user_id):
    """
    Полностью синхронизирует подписку пользователя:

    1. Берёт серверы из servers.txt
    2. Создаёт content
    3. Создаёт/обновляет users/{id}.txt
    4. Сохраняет Raw URL в БД

    Возвращает Raw URL или None.
    """

    user_id = int(user_id)

    user = get_user(user_id)

    if not user:
        print(
            f"[SUBSCRIPTION] Пользователь "
            f"{user_id} не найден."
        )
        return None

    content = build_subscription_content(
        user_id
    )

    if not content:
        print(
            f"[SUBSCRIPTION] Пустая подписка "
            f"для {user_id}. GitHub не обновляем."
        )
        return None

    # --------------------------------------------------------
    # Реальная загрузка в GitHub
    # --------------------------------------------------------

    success = upload_github_file(
        user_id,
        content,
    )

    if not success:
        print(
            f"[SUBSCRIPTION] GitHub sync "
            f"не удался для {user_id}"
        )
        return None

    # --------------------------------------------------------
    # Raw URL
    # --------------------------------------------------------

    raw_url = build_github_subscription_url(
        user_id
    )

    # Сохраняем URL в БД
    save_subscription_link(
        user_id,
        raw_url,
    )

    # Сохраняем содержимое в БД
    save_subscription_content(
        user_id,
        content,
    )

    print(
        f"[SUBSCRIPTION] {user_id} → {raw_url}"
    )

    return raw_url


# ============================================================
# ENSURE SUBSCRIPTION
# ============================================================

def ensure_subscription(user_id):
    """
    Проверяет пользовательскую подписку.

    Если файла нет — создаёт.
    Если есть — оставляет существующий,
    если содержимое актуально.

    Возвращает Raw GitHub URL.
    """

    user_id = int(user_id)

    user = get_user(user_id)

    if not user:
        return None

    raw_url = build_github_subscription_url(
        user_id
    )

    # --------------------------------------------------------
    # Проверяем GitHub
    # --------------------------------------------------------

    existing = get_github_file(user_id)

    if existing:
        github_content = existing.get(
            "content",
            "",
        )

        current_content = (
            build_subscription_content(
                user_id
            )
        )

        # Если содержимое изменилось —
        # обновляем GitHub.
        if (
            current_content
            and github_content.strip()
            != current_content.strip()
        ):
            print(
                f"[SUBSCRIPTION] "
                f"Изменения серверов для {user_id}, "
                f"обновляем GitHub..."
            )

            result = upload_github_file(
                user_id,
                current_content,
            )

            if not result:
                return None

            save_subscription_content(
                user_id,
                current_content,
            )

        else:
            save_subscription_content(
                user_id,
                github_content,
            )

        save_subscription_link(
            user_id,
            raw_url,
        )

        return raw_url

    # --------------------------------------------------------
    # Файла нет → создаём
    # --------------------------------------------------------

    print(
        f"[SUBSCRIPTION] Файла пользователя "
        f"{user_id} нет. Создаём..."
    )

    return sync_user(user_id)


# ============================================================
# AUTO SYNC
# ============================================================

def auto_sync_loop():
    print(
        "[AUTO SYNC] Запущена автоматическая "
        "синхронизация."
    )

    while True:
        try:
            from database import get_all_users

            users = get_all_users()

            for user in users:
                try:
                    user_id = user["user_id"]

                    # Не синхронизируем заблокированных
                    if int(
                        user.get("blocked", 0) or 0
                    ):
                        continue

                    # Только пользователи с подпиской
                    if not user.get(
                        "subscription_until"
                    ):
                        continue

                    sync_user(user_id)

                except Exception as e:
                    print(
                        f"[AUTO SYNC] Ошибка пользователя: "
                        f"{e}"
                    )

        except Exception as e:
            print(
                f"[AUTO SYNC] Общая ошибка: {e}"
            )

        time.sleep(
            max(60, AUTO_SYNC_INTERVAL)
        )


def start_auto_sync():
    if not AUTO_SYNC_ENABLED:
        print(
            "[AUTO SYNC] Отключена."
        )
        return

    thread = threading.Thread(
        target=auto_sync_loop,
        daemon=True,
        name="subscription-auto-sync",
    )

    thread.start()

    print(
        "[AUTO SYNC] Поток запущен."
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    print("====================================")
    print(" MAGNIT VPN SUBSCRIPTION")
    print("====================================")
    print(
        "GitHub:",
        f"{GITHUB_OWNER}/{GITHUB_REPO}",
    )
    print(
        "Branch:",
        GITHUB_BRANCH,
    )
    print(
        "Path:",
        GITHUB_USERS_PATH,
    )
    print(
        "Token:",
        "SET" if GITHUB_TOKEN else "NOT SET",
    )
    print(
        "Servers:",
        len(get_servers()),
    )