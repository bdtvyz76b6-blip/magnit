# web.py
# ============================================================
# МАГНИТ VPN — WEB SERVER
# ============================================================

import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse

from config import SERVICE_NAME, PUBLIC_URL
from database import (
    get_user_by_token,
    get_subscription_content,
    format_date,
    parse_datetime,
)


app = FastAPI(
    title=SERVICE_NAME,
    description="Магнит VPN subscription API",
    version="1.0.0",
)


# ============================================================
# HELPERS
# ============================================================

def get_no_servers_content() -> str:
    """
    Возвращает запасной контент для неактивной подписки.
    """
    try:
        from config import NO_SERVERS_FILE

        if os.path.exists(NO_SERVERS_FILE):
            with open(NO_SERVERS_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()

            if content:
                return content
    except Exception:
        pass

    return (
        "#profile-title: 𝗦𝗨𝗕 - 𝗠𝗔𝗚𝗡𝗜𝗧 𝗩𝗣𝗡 🧲\n"
        "#announce: Подписка неактивна 🔴\n"
    )


def is_subscription_active(user: dict) -> bool:
    """
    Проверяет активность подписки.
    """
    if not user:
        return False

    if user.get("blocked"):
        return False

    subscription = str(user.get("subscription") or "").lower()

    if subscription in ("", "none", "expired", "inactive"):
        return False

    until = parse_datetime(user.get("subscription_until"))

    if until is None:
        return False

    return until > datetime.now(timezone.utc)


def get_status_text(user: dict) -> str:
    """
    Человекочитаемый статус.
    """
    if not user:
        return "Пользователь не найден"

    if user.get("blocked"):
        return "Заблокирована 🚫"

    if is_subscription_active(user):
        return "Активна 🟢"

    return "Неактивна 🔴"


# ============================================================
# ROOT
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def index():
    return f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport"
          content="width=device-width, initial-scale=1.0">

    <title>{SERVICE_NAME}</title>

    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;

            background:
                radial-gradient(
                    circle at top,
                    #343434 0,
                    #171717 45%,
                    #0d0d0d 100%
                );

            color: white;
            font-family:
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;
        }}

        .card {{
            width: calc(100% - 32px);
            max-width: 480px;

            padding: 32px;
            border-radius: 28px;

            background: rgba(255,255,255,.08);
            border: 1px solid rgba(255,255,255,.12);

            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);

            text-align: center;
            box-shadow:
                0 25px 80px rgba(0,0,0,.45);
        }}

        .logo {{
            width: 82px;
            height: 82px;

            margin: 0 auto 20px;

            border-radius: 24px;

            display: flex;
            align-items: center;
            justify-content: center;

            background: rgba(255,255,255,.12);

            font-size: 42px;
        }}

        h1 {{
            margin: 0 0 10px;
            font-size: 28px;
        }}

        p {{
            margin: 0;
            color: #aaa;
            line-height: 1.5;
        }}

        .status {{
            margin-top: 24px;
            padding: 14px;
            border-radius: 16px;

            background: rgba(255,255,255,.06);
        }}

        .online {{
            color: #65e38b;
        }}

        .small {{
            margin-top: 20px;
            font-size: 13px;
            color: #777;
        }}
    </style>
</head>

<body>

<div class="card">

    <div class="logo">🧲</div>

    <h1>{SERVICE_NAME}</h1>

    <p>
        Сервер подписок работает нормально.
    </p>

    <div class="status">
        <span class="online">● Онлайн</span>
    </div>

    <div class="small">
        Subscription API is running
    </div>

</div>

</body>
</html>
"""


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "time": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================
# SUBSCRIPTION
# ============================================================

@app.get(
    "/sub/{token}",
    response_class=PlainTextResponse,
)
async def subscription(token: str):
    """
    Основная ссылка подписки для Happ.

    Пример:

    https://example.com/sub/TOKEN
    """

    token = token.strip()

    if not token:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    user = get_user_by_token(token)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    # --------------------------------------------------------
    # Заблокированный пользователь
    # --------------------------------------------------------

    if user.get("blocked"):
        return PlainTextResponse(
            get_no_servers_content(),
            media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-store",
            },
        )

    # --------------------------------------------------------
    # Неактивная подписка
    # --------------------------------------------------------

    if not is_subscription_active(user):
        return PlainTextResponse(
            get_no_servers_content(),
            media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-store",
            },
        )

    # --------------------------------------------------------
    # Получаем сохранённую подписку
    # --------------------------------------------------------

    content = get_subscription_content(user["user_id"])

    if not content:
        return PlainTextResponse(
            get_no_servers_content(),
            media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-store",
            },
        )

    return PlainTextResponse(
        content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


# ============================================================
# PERSONAL SUBSCRIPTION PAGE
# ============================================================

@app.get(
    "/s/{token}",
    response_class=HTMLResponse,
)
async def subscription_page(token: str):
    """
    Красивая веб-страница персональной подписки.
    """

    token = token.strip()

    user = get_user_by_token(token)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    active = is_subscription_active(user)
    status = get_status_text(user)

    until = parse_datetime(
        user.get("subscription_until")
    )

    if until:
        expires = format_date(until)
    else:
        expires = "—"

    subscription_url = (
        f"{PUBLIC_URL.rstrip('/')}/sub/{token}"
    )

    # Безопасные значения для HTML
    username = (
        user.get("username")
        or user.get("first_name")
        or f"ID {user['user_id']}"
    )

    return f"""
<!DOCTYPE html>
<html lang="ru">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<meta name="theme-color"
      content="#111111">

<title>{SERVICE_NAME}</title>

<style>

* {{
    box-sizing: border-box;
}}

html,
body {{
    margin: 0;
    padding: 0;
    min-height: 100%;
}}

body {{
    min-height: 100vh;

    background:
        radial-gradient(
            circle at 50% -10%,
            #454545 0,
            #191919 42%,
            #0b0b0b 100%
        );

    color: #fff;

    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        Roboto,
        sans-serif;

    padding: 24px 16px;
}}

.container {{
    width: 100%;
    max-width: 520px;
    margin: 0 auto;
}}

.header {{
    text-align: center;
    padding: 24px 0 20px;
}}

.logo {{
    width: 86px;
    height: 86px;

    margin: 0 auto 18px;

    display: flex;
    align-items: center;
    justify-content: center;

    border-radius: 26px;

    background:
        linear-gradient(
            145deg,
            rgba(255,255,255,.18),
            rgba(255,255,255,.05)
        );

    border: 1px solid rgba(255,255,255,.14);

    font-size: 44px;

    box-shadow:
        0 20px 60px rgba(0,0,0,.35);
}}

h1 {{
    margin: 0;
    font-size: 30px;
    font-weight: 800;
}}

.subtitle {{
    margin-top: 8px;
    color: #999;
    font-size: 15px;
}}

.card {{
    margin-top: 16px;

    padding: 22px;

    border-radius: 24px;

    background:
        rgba(255,255,255,.075);

    border:
        1px solid rgba(255,255,255,.11);

    box-shadow:
        0 20px 60px rgba(0,0,0,.25);

    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
}}

.user {{
    font-size: 18px;
    font-weight: 700;
    margin-bottom: 18px;
}}

.row {{
    display: flex;
    align-items: center;
    justify-content: space-between;

    padding: 14px 0;

    border-bottom:
        1px solid rgba(255,255,255,.07);
}}

.row:last-child {{
    border-bottom: none;
}}

.label {{
    color: #929292;
    font-size: 14px;
}}

.value {{
    font-weight: 600;
    text-align: right;
}}

.active {{
    color: #61e58a;
}}

.inactive {{
    color: #ff6b6b;
}}

.link {{
    margin-top: 16px;

    padding: 14px;

    border-radius: 15px;

    background: rgba(0,0,0,.25);

    word-break: break-all;

    color: #aaa;

    font-size: 12px;
    line-height: 1.5;
}}

button {{
    width: 100%;

    border: none;

    margin-top: 14px;

    padding: 15px 18px;

    border-radius: 16px;

    background: #fff;
    color: #111;

    font-size: 15px;
    font-weight: 700;

    cursor: pointer;

    transition:
        transform .15s ease,
        opacity .15s ease;
}}

button:active {{
    transform: scale(.98);
}}

button.secondary {{
    background:
        rgba(255,255,255,.09);

    color: #fff;

    border:
        1px solid rgba(255,255,255,.1);
}}

.footer {{
    text-align: center;

    color: #666;

    font-size: 12px;

    padding: 22px 0;
}}

</style>

</head>

<body>

<div class="container">

    <div class="header">

        <div class="logo">
            🧲
        </div>

        <h1>
            {SERVICE_NAME}
        </h1>

        <div class="subtitle">
            Личная подписка
        </div>

    </div>


    <div class="card">

        <div class="user">
            👤 {username}
        </div>


        <div class="row">

            <div class="label">
                Статус
            </div>

            <div class="value {'active' if active else 'inactive'}">
                {status}
            </div>

        </div>


        <div class="row">

            <div class="label">
                Тариф
            </div>

            <div class="value">
                {user.get("subscription") or "Нет"}
            </div>

        </div>


        <div class="row">

            <div class="label">
                Действует до
            </div>

            <div class="value">
                {expires}
            </div>

        </div>


        <div class="link">
            {subscription_url}
        </div>


        <button
            onclick="copyLink()"
        >
            📋 Скопировать ссылку
        </button>


        <button
            class="secondary"
            onclick="openSubscription()"
        >
            🚀 Открыть подписку
        </button>

    </div>


    <div class="footer">
        {SERVICE_NAME} • Subscription
    </div>

</div>


<script>

const subscriptionUrl =
    {subscription_url!r};


async function copyLink() {{

    try {{

        await navigator.clipboard.writeText(
            subscriptionUrl
        );

        alert("Ссылка скопирована!");

    }} catch (error) {{

        const textarea =
            document.createElement("textarea");

        textarea.value =
            subscriptionUrl;

        document.body.appendChild(
            textarea
        );

        textarea.select();

        document.execCommand(
            "copy"
        );

        textarea.remove();

        alert("Ссылка скопирована!");

    }}

}}


function openSubscription() {{

    window.location.href =
        subscriptionUrl;

}}

</script>

</body>

</html>
"""


# ============================================================
# INFO API
# ============================================================

@app.get("/api/sub/{token}")
async def subscription_info(token: str):
    """
    Информация о подписке.
    Не содержит устройств и device_limit.
    """

    token = token.strip()

    user = get_user_by_token(token)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    active = is_subscription_active(user)

    return {
        "success": True,
        "service": SERVICE_NAME,
        "user_id": user["user_id"],
        "username": user.get("username", ""),
        "subscription": user.get("subscription", "none"),
        "subscription_until": user.get(
            "subscription_until",
            "",
        ),
        "active": active,
        "blocked": bool(
            user.get("blocked", 0)
        ),
        "subscription_url": (
            f"{PUBLIC_URL.rstrip('/')}/sub/{token}"
        ),
        "web_url": (
            f"{PUBLIC_URL.rstrip('/')}/s/{token}"
        ),
    }


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.exception_handler(404)
async def not_found(request, exc):
    return PlainTextResponse(
        "Not Found",
        status_code=404,
    )


# ============================================================
# LOCAL START
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