# web.py

import html
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse

from config import (
    SERVICE_NAME,
    PROFILE_TITLE,
    PROFILE_UPDATE_INTERVAL,
    TELEGRAM_USERNAME,
)

from database import (
    get_user,
    get_user_by_token,
    get_subscription_content,
    save_subscription_content,
)

from subscription import (
    ensure_subscription,
    build_subscription_content,
    github_raw_url,
)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title=SERVICE_NAME,
    docs_url=None,
    redoc_url=None,
)


# ============================================================
# NO CACHE
# ============================================================

NO_CACHE_HEADERS = {
    "Cache-Control": (
        "no-store, no-cache, must-revalidate, "
        "proxy-revalidate, max-age=0"
    ),
    "Pragma": "no-cache",
    "Expires": "0",
}


# ============================================================
# HELPERS
# ============================================================

def get_user_or_404(
    token: str,
):

    user = get_user_by_token(
        token
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    return user


def get_subscription_for_user(
    user_id: int,
) -> str:

    # Сначала пытаемся убедиться,
    # что GitHub-файл существует
    # и соответствует текущему статусу.
    try:

        ensure_subscription(
            user_id
        )

    except Exception as exc:

        print(
            f"[WEB] ensure_subscription "
            f"failed for {user_id}: {exc}"
        )

    # Берём актуальный контент из БД.
    content = get_subscription_content(
        user_id
    )

    # Если в БД пусто — строим напрямую
    # из servers.txt / no_servers.txt.
    if not content:

        content = build_subscription_content(
            user_id
        )

        if content:

            try:

                save_subscription_content(
                    user_id,
                    content,
                )

            except Exception as exc:

                print(
                    f"[WEB] save content failed "
                    f"for {user_id}: {exc}"
                )

    return content


# ============================================================
# SUBSCRIPTION
# ============================================================

@app.get(
    "/sub/{token}",
    response_class=PlainTextResponse,
)
async def subscription(
    token: str,
):

    user = get_user_or_404(
        token
    )

    user_id = int(
        user["user_id"]
    )

    content = get_subscription_for_user(
        user_id
    )

    if not content:

        content = (
            "# МАГНИТ VPN\n"
            "# Серверы временно недоступны\n"
        )

    headers = {
        **NO_CACHE_HEADERS,
        "profile-title": PROFILE_TITLE,
        "profile-update-interval": str(
            PROFILE_UPDATE_INTERVAL
        ),
        "content-disposition": (
            'inline; filename="magnit.txt"'
        ),
    }

    return PlainTextResponse(
        content=content,
        media_type="text/plain",
        headers=headers,
    )


# ============================================================
# SUBSCRIPTION JSON
# ============================================================

@app.get(
    "/sub/{token}/json"
)
async def subscription_json(
    token: str,
):

    user = get_user_or_404(
        token
    )

    user_id = int(
        user["user_id"]
    )

    content = get_subscription_for_user(
        user_id
    )

    servers = []

    for line in content.splitlines():

        line = line.strip()

        if not line:
            continue

        if not line.startswith(
            "vless://"
        ):
            continue

        name = ""

        if "#" in line:

            try:
                name = line.split(
                    "#",
                    1,
                )[1]
            except Exception:
                name = ""

        servers.append(
            {
                "name": name,
                "url": line,
            }
        )

    return {
        "name": SERVICE_NAME,
        "profile_title": PROFILE_TITLE,
        "user": {
            "id": user_id,
            "subscription": user.get(
                "subscription",
                "none",
            ),
            "subscription_until": user.get(
                "subscription_until",
                "",
            ),
            "blocked": bool(
                int(
                    user.get(
                        "blocked",
                        0,
                    )
                    or 0
                )
            ),
            "device_limit": int(
                user.get(
                    "device_limit",
                    3,
                )
                or 3
            ),
        },
        "servers": servers,
    }


# ============================================================
# RAW LINK
# ============================================================

@app.get(
    "/raw/{token}",
)
async def raw_link(
    token: str,
):

    user = get_user_or_404(
        token
    )

    user_id = int(
        user["user_id"]
    )

    return {
        "url": github_raw_url(
            user_id
        )
    }


# ============================================================
# PERSONAL CABINET
# ============================================================

@app.get(
    "/s/{token}",
    response_class=HTMLResponse,
)
async def cabinet(
    token: str,
):

    user = get_user_or_404(
        token
    )

    user_id = int(
        user["user_id"]
    )

    username = html.escape(
        str(
            user.get(
                "username",
                "",
            )
            or ""
        )
    )

    first_name = html.escape(
        str(
            user.get(
                "first_name",
                "Пользователь",
            )
            or "Пользователь"
        )
    )

    subscription = html.escape(
        str(
            user.get(
                "subscription",
                "none",
            )
            or "none"
        )
    )

    subscription_until = html.escape(
        str(
            user.get(
                "subscription_until",
                "",
            )
            or ""
        )
    )

    raw_url = github_raw_url(
        user_id
    )

    safe_raw_url = html.escape(
        raw_url,
        quote=True,
    )

    bot_username = (
        TELEGRAM_USERNAME
        or ""
    ).lstrip("@")

    bot_url = (
        f"https://t.me/{bot_username}"
        if bot_username
        else "#"
    )

    safe_bot_url = html.escape(
        bot_url,
        quote=True,
    )

    safe_service = html.escape(
        SERVICE_NAME
    )

    safe_profile = html.escape(
        PROFILE_TITLE
    )

    return f"""
<!DOCTYPE html>
<html lang="ru">
<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width,
    initial-scale=1.0,
    maximum-scale=1.0,
    user-scalable=no"
>

<meta
    name="theme-color"
    content="#111111"
>

<title>
    {safe_service}
</title>

<style>

* {{
    box-sizing: border-box;
}}

html,
body {{
    margin: 0;
    padding: 0;
    min-height: 100%;

    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;

    background:
        radial-gradient(
            circle at top,
            #242424 0%,
            #111111 45%,
            #070707 100%
        );

    color: #ffffff;
}}

body {{
    padding: 20px;
}}

.container {{
    width: 100%;
    max-width: 520px;
    margin: 0 auto;
}}

.card {{
    background: rgba(
        255,
        255,
        255,
        0.07
    );

    border: 1px solid rgba(
        255,
        255,
        255,
        0.10
    );

    border-radius: 24px;

    padding: 24px;

    backdrop-filter:
        blur(20px);

    -webkit-backdrop-filter:
        blur(20px);

    box-shadow:
        0 20px 60px
        rgba(0,0,0,.35);
}}

.logo {{
    width: 72px;
    height: 72px;

    margin: 0 auto 16px;

    border-radius: 22px;

    display: flex;
    align-items: center;
    justify-content: center;

    background:
        linear-gradient(
            135deg,
            #ffffff,
            #777777
        );

    color: #111111;

    font-size: 36px;
    font-weight: 900;

    box-shadow:
        0 10px 35px
        rgba(255,255,255,.15);
}}

h1 {{
    text-align: center;
    margin: 0;

    font-size: 25px;
}}

.subtitle {{
    text-align: center;

    margin-top: 8px;

    color: #999999;

    font-size: 14px;
}}

.user {{
    margin-top: 24px;

    padding: 16px;

    border-radius: 18px;

    background:
        rgba(
            255,
            255,
            255,
            0.05
        );
}}

.row {{
    display: flex;
    justify-content: space-between;
    gap: 15px;

    padding: 9px 0;
}}

.label {{
    color: #999999;
}}

.value {{
    text-align: right;
    font-weight: 600;
    word-break: break-word;
}}

.active {{
    color: #62ff9a;
}}

.inactive {{
    color: #ff6b6b;
}}

.link-box {{
    margin-top: 18px;
}}

.link {{
    width: 100%;

    padding: 13px;

    border-radius: 14px;

    background: #080808;

    border: 1px solid
        rgba(255,255,255,.08);

    color: #aaa;

    font-size: 12px;

    word-break: break-all;
}}

button,
.button {{
    width: 100%;

    border: 0;

    border-radius: 15px;

    padding: 15px;

    margin-top: 12px;

    font-size: 15px;

    font-weight: 700;

    cursor: pointer;

    text-decoration: none;

    display: block;

    text-align: center;
}}

.copy {{
    background: #ffffff;
    color: #111111;
}}

.happ {{
    background: #262626;
    color: #ffffff;
}}

.telegram {{
    background: #262626;
    color: #ffffff;
}}

.small {{
    text-align: center;

    margin-top: 20px;

    color: #666666;

    font-size: 12px;
}}

</style>

</head>

<body>

<div class="container">

<div class="card">

<div class="logo">
    🧲
</div>

<h1>
    {safe_service}
</h1>

<div class="subtitle">
    {safe_profile}
</div>

<div class="user">

<div class="row">
    <span class="label">
        Пользователь
    </span>

    <span class="value">
        {first_name}
    </span>
</div>

<div class="row">
    <span class="label">
        ID
    </span>

    <span class="value">
        {user_id}
    </span>
</div>

<div class="row">
    <span class="label">
        Статус
    </span>

    <span class="value active">
        {subscription}
    </span>
</div>

<div class="row">
    <span class="label">
        До
    </span>

    <span class="value">
        {subscription_until or "—"}
    </span>
</div>

</div>

<div class="link-box">

<div class="label">
    Ваша подписка
</div>

<div
    class="link"
    id="subscriptionLink"
>
    {safe_raw_url}
</div>

<button
    class="copy"
    onclick="copySubscription()"
>
    📋 Скопировать ссылку
</button>

<a
    class="button happ"
    href="happ://subscribe/{safe_raw_url}"
>
    🚀 Открыть в Happ
</a>

<a
    class="button telegram"
    href="{safe_bot_url}"
>
    🤖 Открыть бота
</a>

</div>

<div class="small">
    {safe_service} • Личный кабинет
</div>

</div>

</div>

<script>

async function copySubscription() {{

    const link =
        document
        .getElementById(
            "subscriptionLink"
        )
        .innerText
        .trim();

    try {{

        await navigator.clipboard.writeText(
            link
        );

        alert(
            "Ссылка скопирована!"
        );

    }} catch (e) {{

        const area =
            document.createElement(
                "textarea"
            );

        area.value = link;

        document.body.appendChild(
            area
        );

        area.select();

        document.execCommand(
            "copy"
        );

        area.remove();

        alert(
            "Ссылка скопирована!"
        );
    }}
}}

</script>

</body>
</html>
"""


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():

    return {
        "service": SERVICE_NAME,
        "status": "online",
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health():

    return {
        "status": "ok"
    }


# ============================================================
# RUN DIRECTLY
# ============================================================

if __name__ == "__main__":

    import uvicorn

    port = int(
        os.getenv(
            "PORT",
            "8080",
        )
    )

    uvicorn.run(
        "web:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )