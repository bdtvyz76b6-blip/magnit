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

# subscription.py
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
    "PUBLIC_URL",
    "https://magnit-grcm.onrender.com",
).rstrip("/")

TELEGRAM_USERNAME = os.getenv(
    "TELEGRAM_USERNAME",
    "orelvpntopbot",
).strip().lstrip("@")

PROFILE_TITLE = os.getenv(
    "PROFILE_TITLE",
    "𝗦𝗨𝗕 - 𝗠𝗔𝗚𝗡𝗜𝗧 𝗩𝗣𝗡 🧲",
).strip()

APP_VERSION = "magnit-2026.09.08"


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

    return max(1, int(seconds / 86400))


def format_date(value):
    dt = parse_datetime(value)

    if not dt:
        return "—"

    return dt.strftime("%d.%m.%Y")


# ============================================================
# URL ПОДПИСКИ
# ============================================================

def build_subscription_url(token):
    """
    Обычная HTTPS ссылка подписки.

    Например:
    https://magnit-grcm.onrender.com/sub/ABC123
    """

    return (
        f"{PUBLIC_URL}/sub/"
        f"{quote(str(token), safe='')}"
    )


def build_happ_url(token):
    """
    Прямая ссылка для импорта подписки в Happ.

    Формат:

    happ://add/https://domain/sub/token

    Happ открывается и получает персональную
    ссылку подписки.
    """

    subscription_url = build_subscription_url(token)

    return (
        "happ://add/"
        + quote(subscription_url, safe=":/?=&")
    )


# ============================================================
# АВТОСОЗДАНИЕ ПОДПИСКИ
# ============================================================

def ensure_user_subscription(user_id):
    """
    Если subscription_content уже есть —
    просто возвращаем его.

    Если нет —
    пробуем создать через subscription.py.
    """

    try:
        content = get_subscription_content(user_id)
    except Exception:
        content = ""

    if content:
        return content

    # --------------------------------------------------------
    # Пробуем использовать subscription.py
    # --------------------------------------------------------

    if ensure_subscription is not None:
        try:
            result = ensure_subscription(user_id)

            # ensure_subscription может вернуть:
            # строку
            if isinstance(result, str) and result.strip():
                content = result.strip()

            # или dict
            elif isinstance(result, dict):
                content = (
                    result.get("content")
                    or result.get("subscription_content")
                    or ""
                )

        except Exception as e:
            print(
                f"[WEB] ensure_subscription error "
                f"for {user_id}: {e}"
            )

    # --------------------------------------------------------
    # Проверяем БД ещё раз
    # --------------------------------------------------------

    if not content:
        try:
            content = get_subscription_content(user_id)
        except Exception:
            content = ""

    # --------------------------------------------------------
    # Если получили — сохраняем
    # --------------------------------------------------------

    if content:
        try:
            save_subscription_content(
                user_id,
                content,
            )
        except Exception as e:
            print(
                f"[WEB] save_subscription_content error "
                f"for {user_id}: {e}"
            )

    return content or ""


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
    content="width=device-width,
    initial-scale=1,
    maximum-scale=1,
    viewport-fit=cover"
>

<meta name="theme-color" content="#050505">

<title>{html.escape(SERVICE_NAME)}</title>

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

    background: rgba(18,18,20,.78);

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

    <div class="logo">🧲</div>

    <h1>{html.escape(SERVICE_NAME)}</h1>

    <p>
        Быстрый и защищённый VPN
        без лишних настроек.
    </p>

    <a
        class="button"
        href="https://t.me/{html.escape(TELEGRAM_USERNAME)}"
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

    # --------------------------------------------------------
    # Сначала ищем пользователя по token
    # --------------------------------------------------------

    try:
        user = get_user_by_token(token)
    except Exception as e:
        print(f"[WEB] get_user_by_token error: {e}")
        user = None

    # --------------------------------------------------------
    # Fallback — если функция отсутствует/не сработала
    # --------------------------------------------------------

    if not user:

        try:
            # Некоторые старые БД могли хранить token
            # иначе. Здесь просто сообщаем 404.
            raise HTTPException(
                status_code=404,
                detail="Subscription not found",
            )

        except HTTPException:
            raise

    # --------------------------------------------------------
    # Получаем user_id
    # --------------------------------------------------------

    user_id = user.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=404,
            detail="Subscription user not found",
        )

    # --------------------------------------------------------
    # ВАЖНО:
    #
    # если subscription_content пустой,
    # автоматически создаём его.
    # --------------------------------------------------------

    content = ensure_user_subscription(user_id)

    if not content:
        raise HTTPException(
            status_code=503,
            detail="Subscription could not be generated",
        )

    # --------------------------------------------------------
    # Возвращаем чистую подписку
    # --------------------------------------------------------

    response = PlainTextResponse(
        content=content.strip() + "\n",
        media_type="text/plain",
    )

    for key, value in NO_CACHE_HEADERS.items():
        response.headers[key] = value

    # Чтобы Happ точно воспринимал ответ
    response.headers["Content-Disposition"] = (
        'inline; filename="subscription.txt"'
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
        user = get_user_by_token(token)
    except Exception as e:
        print(f"[WEB] user lookup error: {e}")
        user = None

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Not found",
        )

    user_id = user.get("user_id")

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
        user.get("subscription_until")
        or ""
    )

    active = is_subscription_active(
        subscription_until
    )

    days = get_days_left(
        subscription_until
    )

    subscription_url = build_subscription_url(
        token
    )

    happ_url = build_happ_url(
        token
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
    # Пытаемся создать подписку заранее
    # --------------------------------------------------------

    try:
        ensure_user_subscription(user_id)
    except Exception as e:
        print(
            f"[WEB] pre-generate error: {e}"
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
    content="width=device-width,
    initial-scale=1,
    maximum-scale=1,
    viewport-fit=cover"
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
            {escape(first_name, "Пользователь")}
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
                {format_date(subscription_until)}
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
            href="{html.escape(happ_url, quote=True)}"
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
                value="{html.escape(subscription_url, quote=True)}"
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
            href="https://t.me/{html.escape(TELEGRAM_USERNAME)}"
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
async def not_found(request, exc):

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