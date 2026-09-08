import os
import html
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse

from database import (
    get_user,
    get_user_by_token,
    get_subscription_content,
    save_subscription_content,
)

try:
    from subscription import ensure_subscription
except Exception:
    ensure_subscription = None


# ============================================================
# НАСТРОЙКИ
# ============================================================

SERVICE_NAME = os.getenv(
    "SERVICE_NAME",
    "МАГНИТ VPN",
).strip()

PUBLIC_URL = os.getenv(
    "PUBLIC_SITE_URL",
    "https://orelvpnrailoh-1.onrender.com",
).rstrip("/")

TELEGRAM_USERNAME = os.getenv(
    "TELEGRAM_USERNAME",
    "Magvpnobot",
).strip().lstrip("@")

TELEGRAM_URL = os.getenv(
    "TELEGRAM_URL",
    "https://t.me/Magvpnobot",
).strip()

PROFILE_TITLE = os.getenv(
    "PROFILE_TITLE",
    "𝗦𝗨𝗕 - 𝗠𝗔𝗚𝗡𝗜𝗧 𝗩𝗣𝗡 🧲",
).strip()

APP_VERSION = "magnit-2026.09.08"

GITHUB_OWNER = os.getenv(
    "GITHUB_OWNER",
    "bdtvyz76b6-blip",
).strip()

GITHUB_REPO = os.getenv(
    "GITHUB_REPO",
    "magnit",
).strip()

GITHUB_BRANCH = os.getenv(
    "GITHUB_BRANCH",
    "main",
).strip()

GITHUB_USERS_PATH = os.getenv(
    "GITHUB_USERS_PATH",
    "users",
).strip().strip("/")


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title=SERVICE_NAME,
    docs_url=None,
    redoc_url=None,
)


# ============================================================
# HEADERS
# ============================================================

NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


# ============================================================
# HELPERS
# ============================================================

def escape(value, default="—"):
    if value is None:
        return default

    value = str(value).strip()

    if not value:
        return default

    return html.escape(value)


def parse_datetime(value):
    if not value:
        return None

    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt

    except Exception:
        return None


def is_subscription_active(value):
    dt = parse_datetime(value)

    if not dt:
        return False

    return dt > datetime.now(timezone.utc)


def get_days_left(value):
    dt = parse_datetime(value)

    if not dt:
        return 0

    seconds = (
        dt - datetime.now(timezone.utc)
    ).total_seconds()

    if seconds <= 0:
        return 0

    return max(
        1,
        int(seconds / 86400),
    )


def format_date(value):
    dt = parse_datetime(value)

    if not dt:
        return "—"

    return dt.strftime("%d.%m.%Y")


# ============================================================
# GITHUB RAW URL
# ============================================================

def build_github_subscription_url(user_id):
    """
    Ссылка на персональный файл:

    users/{user_id}.txt

    Пример:

    https://raw.githubusercontent.com/
    bdtvyz76b6-blip/magnit/main/users/123456789.txt
    """

    return (
        "https://raw.githubusercontent.com/"
        f"{quote(GITHUB_OWNER, safe='')}/"
        f"{quote(GITHUB_REPO, safe='')}/"
        f"{quote(GITHUB_BRANCH, safe='')}/"
        f"{quote(GITHUB_USERS_PATH, safe='')}/"
        f"{quote(str(user_id), safe='')}.txt"
    )


# ============================================================
# HTTPS ССЫЛКА ПОДПИСКИ
# ============================================================

def build_subscription_url(token):
    """
    Серверная ссылка подписки.

    Используется как fallback:

    https://orelvpnrailoh-1.onrender.com/sub/TOKEN
    """

    return (
        f"{PUBLIC_URL}/sub/"
        f"{quote(str(token), safe='')}"
    )


# ============================================================
# HAPP
# ============================================================

def build_happ_url(subscription_url):
    """
    Импорт подписки в Happ.
    """

    return (
        "happ://add/"
        + quote(
            subscription_url,
            safe=":/?=&",
        )
    )


# ============================================================
# ПОЛУЧЕНИЕ АКТУАЛЬНОЙ ССЫЛКИ
# ============================================================

def get_user_subscription_url(user):
    """
    Приоритет:

    1. GitHub raw users/{user_id}.txt
    2. subscription_link из БД
    3. серверная /sub/{token}
    """

    user_id = user.get("user_id")

    if user_id:
        github_url = build_github_subscription_url(
            user_id
        )

        return github_url

    saved_url = (
        user.get("subscription_link")
        or ""
    ).strip()

    if saved_url:
        return saved_url

    token = (
        user.get("token")
        or ""
    ).strip()

    if token:
        return build_subscription_url(token)

    return ""


# ============================================================
# АВТОСОЗДАНИЕ ПОДПИСКИ
# ============================================================

def ensure_user_subscription(user_id):
    """
    Создаёт/обновляет персональную подписку
    через subscription.py.

    subscription.py:
        - получает сервера
        - формирует Happ subscription
        - создаёт users/{user_id}.txt
        - возвращает raw GitHub URL
        - сохраняет ссылку в БД
    """

    try:
        content = get_subscription_content(
            user_id
        )
    except Exception:
        content = ""

    # --------------------------------------------------------
    # Пытаемся синхронизировать
    # --------------------------------------------------------

    if ensure_subscription is not None:

        try:

            result = ensure_subscription(
                user_id
            )

            if isinstance(result, str):

                result = result.strip()

                if result:
                    # Если это raw URL,
                    # content брать не нужно.
                    if result.startswith(
                        "http://"
                    ) or result.startswith(
                        "https://"
                    ):
                        return result

                    content = result

            elif isinstance(result, dict):

                link = (
                    result.get("url")
                    or result.get("link")
                    or result.get("subscription_link")
                    or ""
                ).strip()

                if link:
                    return link

                new_content = (
                    result.get("content")
                    or result.get(
                        "subscription_content"
                    )
                    or ""
                )

                if new_content:
                    content = new_content.strip()

        except Exception as e:

            print(
                f"[WEB] ensure_subscription "
                f"error for {user_id}: {e}"
            )

    # --------------------------------------------------------
    # БД
    # --------------------------------------------------------

    if not content:

        try:
            content = get_subscription_content(
                user_id
            )
        except Exception:
            content = ""

    if content:

        try:

            save_subscription_content(
                user_id,
                content,
            )

        except Exception as e:

            print(
                "[WEB] "
                "save_subscription_content "
                f"error: {e}"
            )

    # --------------------------------------------------------
    # ВАЖНО
    #
    # Даже если subscription.py вернул content,
    # основной URL пользователя — GitHub raw.
    # --------------------------------------------------------

    return build_github_subscription_url(
        user_id
    )


# ============================================================
# ГЛАВНАЯ
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
async def index():

    return f"""
<!doctype html>

<html lang="ru">

<head>

<meta charset="utf-8">

<meta
    name="viewport"
    content="
        width=device-width,
        initial-scale=1,
        maximum-scale=1,
        viewport-fit=cover
    "
>

<meta
    name="theme-color"
    content="#050505"
>

<title>
    {html.escape(SERVICE_NAME)}
</title>

<style>

* {{
    box-sizing: border-box;
    -webkit-tap-highlight-color: transparent;
}}

html,
body {{
    margin: 0;
    min-height: 100%;
}}

body {{

    min-height: 100vh;

    background:
        radial-gradient(
            circle at 50% -10%,
            rgba(255,255,255,.13),
            transparent 34%
        ),
        radial-gradient(
            circle at 100% 45%,
            rgba(255,255,255,.04),
            transparent 30%
        ),
        linear-gradient(
            180deg,
            #090909,
            #050505 58%,
            #020202
        );

    color: #f5f5f7;

    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "SF Pro Display",
        "SF Pro Text",
        Inter,
        Arial,
        sans-serif;

    display: grid;
    place-items: center;
}}

.card {{

    width: min(92%, 520px);

    padding: 35px;

    border-radius: 28px;

    background:
        rgba(18,18,20,.78);

    border:
        1px solid rgba(255,255,255,.08);

    box-shadow:
        0 25px 80px rgba(0,0,0,.45);

    text-align: center;

    backdrop-filter: blur(20px);
}}

.logo {{

    width: 76px;
    height: 76px;

    margin: 0 auto 20px;

    border-radius: 24px;

    display: grid;
    place-items: center;

    font-size: 32px;
    font-weight: 900;

    background:
        linear-gradient(
            145deg,
            #292929,
            #0c0c0c
        );

    border:
        1px solid rgba(255,255,255,.1);
}}

h1 {{

    margin: 0;

    font-size: 34px;
    font-weight: 850;
}}

p {{

    color: #929298;

    line-height: 1.5;
}}

.button {{

    display: block;

    margin-top: 25px;

    padding: 17px 20px;

    border-radius: 17px;

    background: #fff;

    color: #000;

    text-decoration: none;

    font-weight: 800;
}}

</style>

</head>

<body>

<div class="card">

    <div class="logo">
        🧲
    </div>

    <h1>
        {html.escape(SERVICE_NAME)}
    </h1>

    <p>
        Быстрый и защищённый VPN
        без лишних настроек.
    </p>

    <a
        class="button"
        href="{html.escape(TELEGRAM_URL, quote=True)}"
    >
        Открыть Telegram
    </a>

</div>

</body>

</html>
"""


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health():

    return JSONResponse(
        content={
            "service": SERVICE_NAME,
            "status": "ok",
            "version": APP_VERSION,
        },
        headers=NO_CACHE_HEADERS,
    )


# ============================================================
# SUBSCRIPTION
# ============================================================

@app.get(
    "/sub/{token}",
    response_class=PlainTextResponse,
)
async def subscription(token: str):

    if not token:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    try:

        user = get_user_by_token(
            token
        )

    except Exception as e:

        print(
            f"[WEB] get_user_by_token "
            f"error: {e}"
        )

        user = None

    if not user:

        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    user_id = user.get(
        "user_id"
    )

    if not user_id:

        raise HTTPException(
            status_code=404,
            detail="Subscription user not found",
        )

    # --------------------------------------------------------
    # Проверяем срок подписки
    # --------------------------------------------------------

    subscription_until = (
        user.get(
            "subscription_until"
        )
        or ""
    )

    if not is_subscription_active(
        subscription_until
    ):

        raise HTTPException(
            status_code=403,
            detail="Subscription expired",
        )

    # --------------------------------------------------------
    # Получаем содержимое
    # --------------------------------------------------------

    try:

        content = get_subscription_content(
            user_id
        )

    except Exception:

        content = ""

    # --------------------------------------------------------
    # Если пусто — создаём
    # --------------------------------------------------------

    if not content:

        ensure_user_subscription(
            user_id
        )

        try:

            content = get_subscription_content(
                user_id
            )

        except Exception:

            content = ""

    if not content:

        raise HTTPException(
            status_code=503,
            detail="Subscription could not be generated",
        )

    # --------------------------------------------------------
    # Ответ
    # --------------------------------------------------------

    response = PlainTextResponse(
        content=content.strip() + "\n",
        media_type="text/plain",
    )

    for key, value in NO_CACHE_HEADERS.items():
        response.headers[key] = value

    response.headers[
        "Content-Disposition"
    ] = (
        'inline; filename="magnit.txt"'
    )

    response.headers[
        "profile-title"
    ] = PROFILE_TITLE

    response.headers[
        "profile-update-interval"
    ] = os.getenv(
        "PROFILE_UPDATE_INTERVAL",
        "1",
    )

    return response


# ============================================================
# ЛИЧНЫЙ КАБИНЕТ
# ============================================================

@app.get(
    "/s/{token}",
    response_class=HTMLResponse,
)
async def subscription_page(token: str):

    if not token:

        raise HTTPException(
            status_code=404,
            detail="Not found",
        )

    try:

        user = get_user_by_token(
            token
        )

    except Exception as e:

        print(
            f"[WEB] user lookup error: {e}"
        )

        user = None

    if not user:

        raise HTTPException(
            status_code=404,
            detail="Not found",
        )

    user_id = user.get(
        "user_id"
    )

    first_name = (
        user.get("first_name")
        or user.get("username")
        or "Пользователь"
    )

    subscription = (
        user.get("subscription")
        or "Не выбран"
    )

    subscription_until = (
        user.get(
            "subscription_until"
        )
        or ""
    )

    active = is_subscription_active(
        subscription_until
    )

    days = get_days_left(
        subscription_until
    )

    # --------------------------------------------------------
    # Генерируем GitHub файл
    # --------------------------------------------------------

    subscription_url = (
        get_user_subscription_url(
            user
        )
    )

    if user_id:

        try:

            github_url = (
                ensure_user_subscription(
                    user_id
                )
            )

            if github_url:

                subscription_url = (
                    github_url
                )

        except Exception as e:

            print(
                f"[WEB] subscription "
                f"generation error: {e}"
            )

    # --------------------------------------------------------
    # Happ
    # --------------------------------------------------------

    happ_url = build_happ_url(
        subscription_url
    )

    status = (
        "Активна"
        if active
        else "Неактивна"
    )

    status_class = (
        "active"
        if active
        else "inactive"
    )

    days_text = (
        f"{days} дн."
        if active
        else "Завершена"
    )

    # --------------------------------------------------------
    # HTML
    # --------------------------------------------------------

    page = f"""
<!doctype html>

<html lang="ru">

<head>

<meta charset="utf-8">

<meta
    name="viewport"
    content="
        width=device-width,
        initial-scale=1,
        maximum-scale=1,
        viewport-fit=cover
    "
>

<meta
    name="theme-color"
    content="#050505"
>

<meta
    name="apple-mobile-web-app-capable"
    content="yes"
>

<title>
    {html.escape(SERVICE_NAME)}
    — Личный кабинет
</title>

<style>

* {{
    box-sizing: border-box;
    -webkit-tap-highlight-color: transparent;
}}

html,
body {{
    margin: 0;
    min-height: 100%;
}}

body {{

    min-height: 100vh;

    color: #f5f5f7;

    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "SF Pro Display",
        "SF Pro Text",
        Inter,
        Arial,
        sans-serif;

    background:

        radial-gradient(
            circle at 50% -10%,
            rgba(255,255,255,.13),
            transparent 34%
        ),

        radial-gradient(
            circle at 100% 45%,
            rgba(255,255,255,.04),
            transparent 30%
        ),

        linear-gradient(
            180deg,
            #090909,
            #050505 58%,
            #020202
        );
}}

.container {{

    width:
        min(
            calc(100% - 32px),
            620px
        );

    margin: auto;

    padding:
        calc(20px + env(safe-area-inset-top))
        0
        calc(30px + env(safe-area-inset-bottom));
}}

.header {{

    display: flex;
    align-items: center;

    gap: 12px;

    margin-bottom: 22px;
}}

.logo {{

    width: 48px;
    height: 48px;

    border-radius: 15px;

    display: grid;
    place-items: center;

    font-size: 22px;

    background:
        linear-gradient(
            145deg,
            #292929,
            #0c0c0c
        );

    border:
        1px solid rgba(255,255,255,.1);

    box-shadow:
        0 14px 35px rgba(0,0,0,.35);
}}

.brand h1 {{

    margin: 0;

    font-size: 20px;
    font-weight: 850;
}}

.brand p {{

    margin: 3px 0 0;

    color: #85858c;

    font-size: 13px;
}}

.card {{

    margin-top: 14px;

    padding: 20px;

    border-radius: 23px;

    background:
        rgba(18,18,20,.76);

    border:
        1px solid rgba(255,255,255,.08);

    box-shadow:
        0 18px 50px rgba(0,0,0,.25);

    backdrop-filter: blur(20px);
}}

.label {{

    color: #85858c;

    font-size: 13px;

    margin-bottom: 7px;
}}

.value {{

    font-size: 20px;

    font-weight: 800;
}}

.status {{

    display: inline-flex;

    align-items: center;

    gap: 7px;

    padding:
        8px
        12px;

    border-radius: 999px;

    font-size: 13px;

    font-weight: 750;
}}

.status.active {{

    color: #d9ffd9;

    background:
        rgba(60,190,80,.13);

    border:
        1px solid rgba(60,190,80,.18);
}}

.status.inactive {{

    color: #ffdede;

    background:
        rgba(255,70,70,.13);

    border:
        1px solid rgba(255,70,70,.18);
}}

.dot {{

    width: 7px;
    height: 7px;

    border-radius: 50%;

    background: currentColor;
}}

.primary {{

    display: block;

    width: 100%;

    padding: 17px 18px;

    margin-top: 15px;

    border-radius: 17px;

    text-align: center;

    text-decoration: none;

    font-weight: 850;

    color: #000;

    background: #fff;

    box-shadow:
        0 12px 35px rgba(0,0,0,.3);
}}

.primary:active {{
    transform: scale(.985);
}}

.secondary {{

    width: 100%;

    padding: 15px 18px;

    margin-top: 10px;

    border-radius: 17px;

    border:
        1px solid rgba(255,255,255,.09);

    background:
        rgba(255,255,255,.05);

    color: #fff;

    font-size: 15px;

    font-weight: 750;
}}

.urlbox {{

    display: flex;

    gap: 8px;

    margin-top: 12px;
}}

.urlbox input {{

    min-width: 0;
    flex: 1;

    height: 48px;

    padding: 0 12px;

    border-radius: 13px;

    border:
        1px solid rgba(255,255,255,.08);

    background:
        rgba(255,255,255,.04);

    color: #aaa;

    font-size: 12px;
}}

.copy {{

    height: 48px;

    padding: 0 14px;

    border: 0;

    border-radius: 13px;

    background: #fff;

    color: #000;

    font-weight: 850;
}}

.notice {{

    display: flex;

    gap: 11px;

    margin-top: 15px;

    padding: 14px;

    border-radius: 16px;

    background:
        rgba(255,255,255,.035);

    border:
        1px solid rgba(255,255,255,.06);
}}

.check {{

    width: 28px;
    height: 28px;

    flex: 0 0 28px;

    display: grid;
    place-items: center;

    border-radius: 50%;

    background:
        rgba(255,255,255,.08);
}}

.notice b {{
    font-size: 13px;
}}

.notice p {{

    margin: 4px 0 0;

    color: #818188;

    font-size: 12px;

    line-height: 1.4;
}}

.footer {{

    margin-top: 22px;

    text-align: center;

    color: #606066;

    font-size: 11px;

    line-height: 1.5;
}}

</style>

</head>

<body>

<div class="container">

    <div class="header">

        <div class="logo">
            🧲
        </div>

        <div class="brand">

            <h1>
                {html.escape(SERVICE_NAME)}
            </h1>

            <p>
                Личный кабинет
            </p>

        </div>

    </div>


    <section class="card">

        <div class="label">
            Пользователь
        </div>

        <div class="value">
            {escape(
                first_name,
                "Пользователь"
            )}
        </div>

    </section>


    <section class="card">

        <div class="label">
            Статус подписки
        </div>

        <div
            class="status {status_class}"
        >

            <span class="dot"></span>

            {status}

        </div>


        <div
            style="
                margin-top:16px;
                display:flex;
                justify-content:space-between;
                gap:20px;
            "
        >

            <div>

                <div class="label">
                    Тариф
                </div>

                <div class="value">
                    {escape(subscription)}
                </div>

            </div>


            <div style="text-align:right">

                <div class="label">
                    Осталось
                </div>

                <div class="value">
                    {days_text}
                </div>

            </div>

        </div>


        <div
            style="
                margin-top:18px;
                padding-top:15px;
                border-top:
                    1px solid
                    rgba(255,255,255,.07);
            "
        >

            <div class="label">
                Действует до
            </div>

            <div class="value">
                {format_date(
                    subscription_until
                )}
            </div>

        </div>

    </section>


    <section class="card">

        <div class="label">
            Подключение
        </div>

        <div class="value">
            Happ VPN
        </div>

        <a
            class="primary"
            href="{html.escape(
                happ_url,
                quote=True
            )}"
        >
            🧲 Подключить через Happ
        </a>

        <button
            class="secondary"
            onclick="copySubscription()"
        >
            📋 Скопировать ссылку
        </button>

    </section>


    <section class="card">

        <div class="label">
            Моя подписка
        </div>

        <div class="urlbox">

            <input
                id="subUrl"
                readonly
                value="{html.escape(
                    subscription_url,
                    quote=True
                )}"
            >

            <button
                class="copy"
                onclick="copySubscription()"
            >
                COPY
            </button>

        </div>


        <div class="notice">

            <div class="check">
                ✓
            </div>

            <div>

                <b>
                    Серверные параметры скрыты
                </b>

                <p>
                    IP, порты, UUID, Reality
                    и другие технические данные
                    не отображаются на странице.
                </p>

            </div>

        </div>

    </section>


    <section class="card">

        <div class="label">
            Поддержка
        </div>

        <div class="value">
            Нужна помощь?
        </div>

        <a
            class="primary"
            href="{html.escape(
                TELEGRAM_URL,
                quote=True
            )}"
        >
            💬 Открыть поддержку
        </a>

    </section>


    <div class="footer">

        {html.escape(SERVICE_NAME)}
        · {APP_VERSION}

        <br>

        Быстро. Приватно. Без лишнего.

    </div>

</div>


<script>

const SUB_URL =
    {subscription_url!r};


async function copySubscription() {{

    try {{

        await navigator.clipboard.writeText(
            SUB_URL
        );

        alert(
            "Ссылка скопирована"
        );

    }} catch (e) {{

        const textarea =
            document.createElement(
                "textarea"
            );

        textarea.value =
            SUB_URL;

        textarea.style.position =
            "fixed";

        textarea.style.opacity =
            "0";

        document.body.appendChild(
            textarea
        );

        textarea.select();

        document.execCommand(
            "copy"
        );

        textarea.remove();

        alert(
            "Ссылка скопирована"
        );
    }}
}}

</script>

</body>

</html>
"""

    response = HTMLResponse(
        content=page,
        headers=NO_CACHE_HEADERS,
    )

    return response


# ============================================================
# 404
# ============================================================

@app.exception_handler(404)
async def not_found(
    request,
    exc,
):

    return JSONResponse(
        status_code=404,
        content={
            "detail": "Not found"
        },
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    import uvicorn

    port = int(
        os.getenv(
            "PORT",
            "10000",
        )
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
    )