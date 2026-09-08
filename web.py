import os
import html
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse

from config import (
    SERVICE_NAME,
    PUBLIC_URL,
    TELEGRAM_USERNAME,
)

from database import (
    get_user,
    get_subscription_content,
)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title=SERVICE_NAME,
    docs_url=None,
    redoc_url=None,
)


APP_VERSION = "magnit-2026.09.08"

PUBLIC_URL = PUBLIC_URL.rstrip("/")
TELEGRAM_USERNAME = TELEGRAM_USERNAME.lstrip("@")

TELEGRAM_URL = f"https://t.me/{TELEGRAM_USERNAME}"


NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


# ============================================================
# HELPERS
# ============================================================

def subscription_url(token: str):
    return f"{PUBLIC_URL}/sub/{quote(str(token), safe='')}"


def personal_url(token: str):
    return f"{PUBLIC_URL}/s/{quote(str(token), safe='')}"


def parse_date(value):
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


def is_active(value):
    dt = parse_date(value)

    if not dt:
        return False

    return dt > datetime.now(timezone.utc)


def days_left(value):
    dt = parse_date(value)

    if not dt:
        return 0

    seconds = (
        dt - datetime.now(timezone.utc)
    ).total_seconds()

    if seconds <= 0:
        return 0

    return max(1, int(seconds // 86400))


def format_date(value):
    dt = parse_date(value)

    if not dt:
        return "—"

    return dt.strftime("%d.%m.%Y")


def safe(value, default="—"):
    if value is None:
        return default

    value = str(value).strip()

    if not value:
        return default

    return html.escape(value)


# ============================================================
# MAIN WEBSITE
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def index():

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

<meta name="theme-color" content="#07070a">

<title>{html.escape(SERVICE_NAME)}</title>

<style>

* {{
    box-sizing:border-box;
    -webkit-tap-highlight-color:transparent;
}}

html,
body {{
    margin:0;
    padding:0;
    min-height:100%;

    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "SF Pro Display",
        "SF Pro Text",
        Inter,
        Arial,
        sans-serif;

    color:#fff;
    background:#07070a;
}}

body {{

    overflow-x:hidden;

    background:
        radial-gradient(
            circle at 50% -10%,
            rgba(255,255,255,.16),
            transparent 34%
        ),
        radial-gradient(
            circle at 0% 55%,
            rgba(255,255,255,.06),
            transparent 28%
        ),
        radial-gradient(
            circle at 100% 70%,
            rgba(255,255,255,.05),
            transparent 30%
        ),
        linear-gradient(
            180deg,
            #0b0b10 0%,
            #07070a 45%,
            #030305 100%
        );
}}

body::before {{

    content:"";

    position:fixed;

    width:420px;
    height:420px;

    left:50%;
    top:50%;

    transform:
        translate(-50%,-50%);

    border-radius:50%;

    background:
        radial-gradient(
            circle,
            rgba(255,255,255,.045),
            transparent 68%
        );

    filter:blur(40px);

    pointer-events:none;
}}

.container {{

    width:min(
        calc(100% - 30px),
        760px
    );

    margin:auto;

    padding:
        calc(20px + env(safe-area-inset-top))
        0
        calc(35px + env(safe-area-inset-bottom));
}}

.header {{

    display:flex;
    align-items:center;
    justify-content:space-between;

    padding:8px 0 20px;
}}

.brand {{

    display:flex;
    align-items:center;
    gap:12px;
}}

.logo {{

    width:46px;
    height:46px;

    border-radius:15px;

    display:grid;
    place-items:center;

    background:
        linear-gradient(
            145deg,
            #29292e,
            #0d0d10
        );

    border:
        1px solid
        rgba(255,255,255,.12);

    box-shadow:
        0 12px 35px
        rgba(0,0,0,.4);
}}

.logo span {{

    font-size:22px;
    font-weight:950;
    letter-spacing:-2px;
}}

.brandName {{

    font-size:20px;
    font-weight:900;

    letter-spacing:-.8px;
}}

.secure {{

    font-size:9px;
    letter-spacing:1.5px;
    color:#777;
    font-weight:800;
}}

.hero {{

    text-align:center;

    padding:
        55px
        0
        35px;
}}

.badge {{

    display:inline-flex;

    align-items:center;
    gap:7px;

    padding:
        8px
        12px;

    border-radius:999px;

    background:
        rgba(255,255,255,.055);

    border:
        1px solid
        rgba(255,255,255,.08);

    color:#a3a3aa;

    font-size:10px;

    font-weight:850;

    letter-spacing:.8px;

    text-transform:uppercase;
}}

.badgeDot {{

    width:6px;
    height:6px;

    border-radius:50%;

    background:#fff;

    box-shadow:
        0 0 14px
        rgba(255,255,255,.9);
}}

.hero h1 {{

    margin:
        22px
        0
        14px;

    font-size:
        clamp(44px,10vw,78px);

    line-height:.95;

    letter-spacing:-5px;

    font-weight:950;
}}

.hero h1 span {{

    color:#8c8c93;
}}

.hero p {{

    margin:0 auto;

    max-width:530px;

    color:#888890;

    font-size:16px;

    line-height:1.6;
}}

.buttons {{

    display:grid;

    grid-template-columns:
        repeat(2,1fr);

    gap:11px;

    margin-top:28px;
}}

.button {{

    min-height:56px;

    display:flex;

    align-items:center;

    justify-content:center;

    border-radius:18px;

    text-decoration:none;

    font-size:14px;

    font-weight:900;

    transition:
        transform .18s,
        opacity .18s;
}}

.button:active {{

    transform:scale(.97);
}}

.primary {{

    background:#fff;
    color:#050507;

    box-shadow:
        0 16px 45px
        rgba(255,255,255,.08);
}}

.secondary {{

    background:
        rgba(255,255,255,.045);

    color:#fff;

    border:
        1px solid
        rgba(255,255,255,.09);
}}

.cards {{

    display:grid;

    grid-template-columns:
        repeat(3,1fr);

    gap:12px;

    margin-top:20px;
}}

.card {{

    padding:22px;

    border-radius:24px;

    background:
        rgba(18,18,21,.72);

    border:
        1px solid
        rgba(255,255,255,.075);

    box-shadow:
        0 18px 60px
        rgba(0,0,0,.22);

    backdrop-filter:
        blur(22px);
}}

.icon {{

    font-size:25px;

    margin-bottom:16px;
}}

.card h3 {{

    margin:
        0 0 7px;

    font-size:15px;
    font-weight:900;
}}

.card p {{

    margin:0;

    color:#77777f;

    font-size:12px;

    line-height:1.5;
}}

.section {{

    margin-top:15px;
}}

.sectionTitle {{

    font-size:12px;

    text-transform:uppercase;

    letter-spacing:1.2px;

    color:#66666d;

    font-weight:900;

    margin:
        25px
        5px
        10px;
}}

.bigCard {{

    padding:26px;

    border-radius:27px;

    background:
        linear-gradient(
            145deg,
            rgba(255,255,255,.075),
            rgba(255,255,255,.025)
        );

    border:
        1px solid
        rgba(255,255,255,.09);

    box-shadow:
        0 22px 70px
        rgba(0,0,0,.28);
}}

.bigCard h2 {{

    margin:0 0 8px;

    font-size:24px;

    letter-spacing:-1px;

    font-weight:950;
}}

.bigCard p {{

    margin:0;

    color:#85858d;

    line-height:1.55;

    font-size:13px;
}}

.steps {{

    display:grid;

    gap:10px;

    margin-top:20px;
}}

.step {{

    display:flex;

    gap:13px;

    align-items:center;

    padding:14px;

    border-radius:17px;

    background:
        rgba(255,255,255,.035);

    border:
        1px solid
        rgba(255,255,255,.05);
}}

.stepNumber {{

    width:32px;
    height:32px;

    flex:0 0 32px;

    display:grid;
    place-items:center;

    border-radius:11px;

    background:#fff;
    color:#000;

    font-size:12px;
    font-weight:950;
}}

.stepText b {{

    display:block;

    font-size:13px;

    margin-bottom:3px;
}}

.stepText span {{

    color:#73737a;

    font-size:11px;
}}

.footer {{

    text-align:center;

    color:#55555b;

    font-size:10px;

    line-height:1.7;

    padding:
        35px
        0
        5px;
}}

@media(max-width:600px) {{

    .cards {{
        grid-template-columns:1fr;
    }}

    .buttons {{
        grid-template-columns:1fr;
    }}

    .hero {{
        padding-top:40px;
    }}

    .hero h1 {{
        letter-spacing:-3px;
    }}

}}

</style>

</head>

<body>

<div class="container">

<header class="header">

    <div class="brand">

        <div class="logo">
            <span>🧲</span>
        </div>

        <div class="brandName">
            МАГНИТ VPN
        </div>

    </div>

    <div class="secure">
        SECURE ACCESS
    </div>

</header>


<section class="hero">

    <div class="badge">
        <span class="badgeDot"></span>
        Сервис работает
    </div>

    <h1>
        МАГНИТ<br>
        <span>VPN</span>
    </h1>

    <p>
        Быстрое подключение без лишних настроек.
        Получите подписку и импортируйте её
        прямо в VPN-клиент.
    </p>

    <div class="buttons">

        <a
            class="button primary"
            href="{TELEGRAM_URL}"
        >
            🚀 Открыть бота
        </a>

        <a
            class="button secondary"
            href="{TELEGRAM_URL}"
        >
            💬 Поддержка
        </a>

    </div>

</section>


<div class="cards">

    <div class="card">

        <div class="icon">⚡</div>

        <h3>
            Быстро
        </h3>

        <p>
            Подключение через
            персональную подписку.
        </p>

    </div>


    <div class="card">

        <div class="icon">🔒</div>

        <h3>
            Защищённо
        </h3>

        <p>
            Данные серверов
            не отображаются
            в личном кабинете.
        </p>

    </div>


    <div class="card">

        <div class="icon">📱</div>

        <h3>
            Удобно
        </h3>

        <p>
            Подписка подходит
            для совместимых
            VPN-клиентов.
        </p>

    </div>

</div>


<section class="section">

<div class="sectionTitle">
    Как подключиться
</div>

<div class="bigCard">

    <h2>
        Три шага — и готово
    </h2>

    <p>
        Управляйте подпиской через
        Telegram-бота.
    </p>


    <div class="steps">

        <div class="step">

            <div class="stepNumber">
                1
            </div>

            <div class="stepText">

                <b>
                    Откройте бота
                </b>

                <span>
                    Перейдите в Telegram
                </span>

            </div>

        </div>


        <div class="step">

            <div class="stepNumber">
                2
            </div>

            <div class="stepText">

                <b>
                    Получите подписку
                </b>

                <span>
                    Выберите подходящий тариф
                </span>

            </div>

        </div>


        <div class="step">

            <div class="stepNumber">
                3
            </div>

            <div class="stepText">

                <b>
                    Подключите VPN
                </b>

                <span>
                    Импортируйте персональную ссылку
                </span>

            </div>

        </div>

    </div>

</div>

</section>


<footer class="footer">

    МАГНИТ VPN · {APP_VERSION}<br>

    Быстро. Приватно. Без лишнего.

</footer>

</div>

</body>

</html>
"""

    return HTMLResponse(
        content=page,
        headers=NO_CACHE_HEADERS,
    )


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health():

    return JSONResponse(
        {
            "service": SERVICE_NAME,
            "status": "ok",
            "version": APP_VERSION,
        },
        headers=NO_CACHE_HEADERS,
    )


# ============================================================
# SUBSCRIPTION RAW ENDPOINT
# ============================================================

@app.get("/sub/{token}")
async def subscription(token: str):

    if not token:
        raise HTTPException(
            status_code=404,
            detail="Not Found",
        )

    # Проверяем существование пользователя.
    user = get_user_by_token_safe(token)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    user_id = user["user_id"]

    content = get_subscription_content(user_id)

    if not content:
        raise HTTPException(
            status_code=404,
            detail="Subscription is empty",
        )

    # ========================================================
    # ВАЖНО:
    #
    # Возвращаем ТОЛЬКО plain text.
    #
    # Никаких:
    # - JSON
    # - HTML
    # - Markdown
    # - crypt4
    # - happ wrapper
    #
    # Это основной endpoint для VPN-клиента.
    # ========================================================

    return PlainTextResponse(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={
            **NO_CACHE_HEADERS,
            "Content-Disposition": "inline",
        },
    )


# ============================================================
# SAFE USER LOOKUP
# ============================================================

def get_user_by_token_safe(token):
    """
    Поддерживает текущую database.py,
    где get_user_by_token(token) возвращает dict.
    """

    try:
        from database import get_user_by_token

        user = get_user_by_token(token)

        if user:
            return user

    except Exception:
        pass

    return None


# ============================================================
# PERSONAL PAGE
# ============================================================

@app.get("/s/{token}", response_class=HTMLResponse)
async def personal_page(token: str):

    user = get_user_by_token_safe(token)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Not Found",
        )

    first_name = safe(
        user.get("first_name")
        or user.get("username")
        or "Пользователь"
    )

    tariff = safe(
        user.get("subscription"),
        "Нет тарифа",
    )

    until = user.get(
        "subscription_until",
        "",
    )

    active = is_active(until)

    remaining = days_left(until)

    expiry = format_date(until)

    sub_url = subscription_url(token)

    if active:

        status = "АКТИВНА"
        status_class = "active"

        days_text = (
            f"{remaining} "
            f"{'день' if remaining == 1 else 'дней'}"
        )

    else:

        status = "НЕАКТИВНА"
        status_class = "inactive"

        days_text = "Завершена"


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
    content="#07070a"
>

<title>
    МАГНИТ VPN — Подписка
</title>

<style>

* {{
    box-sizing:border-box;
    -webkit-tap-highlight-color:transparent;
}}

html,
body {{
    margin:0;
    min-height:100%;

    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "SF Pro Display",
        Inter,
        Arial,
        sans-serif;

    background:#07070a;
    color:#fff;
}}

body {{

    background:
        radial-gradient(
            circle at 50% -10%,
            rgba(255,255,255,.15),
            transparent 35%
        ),
        linear-gradient(
            180deg,
            #0b0b0f,
            #050507
        );
}}

.container {{

    width:
        min(
            calc(100% - 30px),
            620px
        );

    margin:auto;

    padding:
        calc(20px + env(safe-area-inset-top))
        0
        calc(30px + env(safe-area-inset-bottom));
}}

.header {{

    display:flex;

    justify-content:space-between;

    align-items:center;

    margin-bottom:25px;
}}

.brand {{

    display:flex;

    align-items:center;

    gap:10px;
}}

.logo {{

    width:43px;
    height:43px;

    border-radius:14px;

    display:grid;
    place-items:center;

    background:
        linear-gradient(
            145deg,
            #29292e,
            #0d0d10
        );

    border:
        1px solid
        rgba(255,255,255,.1);
}}

.brand b {{

    font-size:18px;
    font-weight:950;
}}

.hero {{

    text-align:center;

    padding:
        25px
        0
        20px;
}}

.hero .small {{

    color:#77777f;

    font-size:12px;

    margin-bottom:8px;
}}

.hero h1 {{

    margin:0;

    font-size:42px;

    letter-spacing:-2.5px;

    font-weight:950;
}}

.hero p {{

    margin:
        10px
        0
        0;

    color:#818189;

    font-size:14px;
}}

.card {{

    margin-top:12px;

    padding:22px;

    border-radius:25px;

    background:
        rgba(18,18,21,.76);

    border:
        1px solid
        rgba(255,255,255,.08);

    box-shadow:
        0 20px 65px
        rgba(0,0,0,.28);

    backdrop-filter:blur(25px);
}}

.statusRow {{

    display:flex;

    justify-content:space-between;

    align-items:center;

    gap:10px;
}}

.label {{

    color:#6f6f76;

    font-size:10px;

    text-transform:uppercase;

    letter-spacing:1px;

    font-weight:900;
}}

.status {{

    padding:
        8px
        11px;

    border-radius:999px;

    background:
        rgba(255,255,255,.055);

    font-size:11px;

    font-weight:900;
}}

.status.active {{

    box-shadow:
        0 0 20px
        rgba(255,255,255,.06);
}}

.big {{

    margin-top:20px;

    font-size:34px;

    font-weight:950;

    letter-spacing:-1.5px;
}}

.grid {{

    display:grid;

    grid-template-columns:
        1fr 1fr;

    gap:10px;

    margin-top:18px;
}}

.stat {{

    padding:15px;

    border-radius:17px;

    background:
        rgba(255,255,255,.035);

    border:
        1px solid
        rgba(255,255,255,.05);
}}

.stat span {{

    display:block;

    color:#68686f;

    font-size:9px;

    text-transform:uppercase;

    letter-spacing:.8px;

    margin-bottom:7px;
}}

.stat b {{

    font-size:15px;

    font-weight:900;
}}

.primary {{

    width:100%;

    min-height:55px;

    display:flex;

    align-items:center;

    justify-content:center;

    margin-top:17px;

    border-radius:17px;

    background:#fff;

    color:#050507;

    text-decoration:none;

    font-size:14px;

    font-weight:950;

    box-shadow:
        0 15px 40px
        rgba(255,255,255,.08);
}}

.actions {{

    display:grid;

    grid-template-columns:
        1fr 1fr;

    gap:9px;

    margin-top:9px;
}}

.action {{

    min-height:49px;

    display:flex;

    align-items:center;

    justify-content:center;

    border-radius:16px;

    background:
        rgba(255,255,255,.045);

    color:#fff;

    border:
        1px solid
        rgba(255,255,255,.08);

    text-decoration:none;

    font-size:12px;

    font-weight:900;
}}

.url {{

    margin-top:13px;

    display:flex;

    align-items:center;

    gap:7px;

    padding:6px;

    border-radius:16px;

    background:#09090b;

    border:
        1px solid
        rgba(255,255,255,.07);
}}

.url input {{

    min-width:0;

    flex:1;

    border:0;

    outline:0;

    background:transparent;

    color:#74747b;

    font-size:10px;

    padding:9px;
}}

.copy {{

    border:0;

    border-radius:11px;

    padding:
        10px
        12px;

    background:#fff;

    color:#000;

    font-size:9px;

    font-weight:950;
}}

.notice {{

    margin-top:13px;

    padding:14px;

    border-radius:17px;

    background:
        rgba(255,255,255,.035);

    border:
        1px solid
        rgba(255,255,255,.05);

    color:#77777e;

    font-size:11px;

    line-height:1.5;
}}

.notice b {{

    color:#aaaab0;
}}

.footer {{

    text-align:center;

    color:#55555b;

    font-size:10px;

    line-height:1.6;

    padding:28px 0 4px;
}}

@media(max-width:430px) {{

    .hero h1 {{
        font-size:37px;
    }}

    .big {{
        font-size:29px;
    }}

}}

</style>

</head>

<body>

<div class="container">

<header class="header">

    <div class="brand">

        <div class="logo">
            🧲
        </div>

        <b>
            МАГНИТ VPN
        </b>

    </div>

</header>


<section class="hero">

    <div class="small">
        ЛИЧНЫЙ КАБИНЕТ
    </div>

    <h1>
        Привет, {first_name}
    </h1>

    <p>
        Ваша персональная подписка
    </p>

</section>


<section class="card">

    <div class="statusRow">

        <div class="label">
            Состояние подписки
        </div>

        <div class="status {status_class}">
            {status}
        </div>

    </div>


    <div class="big">
        {days_text}
    </div>


    <div class="grid">

        <div class="stat">

            <span>
                Тариф
            </span>

            <b>
                {tariff}
            </b>

        </div>


        <div class="stat">

            <span>
                Действует до
            </span>

            <b>
                {expiry}
            </b>

        </div>

    </div>

</section>


<section class="card">

    <div class="label">
        ПОДКЛЮЧЕНИЕ
    </div>

    <div
        style="
        font-size:20px;
        font-weight:950;
        margin-top:8px;
        "
    >
        Подключить VPN
    </div>

    <div
        style="
        color:#77777f;
        font-size:12px;
        line-height:1.5;
        margin-top:5px;
        "
    >
        Используйте персональную
        ссылку подписки в вашем VPN-клиенте.
    </div>


    <a
        class="primary"
        href="{sub_url}"
    >
        🔗 Открыть подписку
    </a>


    <div class="actions">

        <a
            class="action"
            href="{TELEGRAM_URL}"
        >
            💬 Поддержка
        </a>

        <button
            class="action"
            onclick="copySubscription()"
        >
            📋 Скопировать
        </button>

    </div>


    <div class="url">

        <input
            id="subUrl"
            readonly
            value="{html.escape(sub_url, quote=True)}"
        >

        <button
            class="copy"
            onclick="copySubscription()"
        >
            COPY
        </button>

    </div>


    <div class="notice">

        <b>
            🔒 Данные серверов скрыты
        </b>

        <br>

        IP-адреса, порты, UUID и
        технические параметры серверов
        не отображаются на странице.

    </div>

</section>


<footer class="footer">

    МАГНИТ VPN · {APP_VERSION}<br>

    Быстро. Приватно. Без лишнего.

</footer>

</div>


<script>

const SUB_URL =
    {sub_url!r};


async function copySubscription() {{

    try {{

        await navigator.clipboard
            .writeText(SUB_URL);

    }} catch(e) {{

        const textarea =
            document.createElement("textarea");

        textarea.value = SUB_URL;

        textarea.style.position = "fixed";
        textarea.style.opacity = "0";

        document.body.appendChild(
            textarea
        );

        textarea.select();

        document.execCommand("copy");

        textarea.remove();
    }}

    alert(
        "Ссылка подписки скопирована"
    );
}}

</script>

</body>

</html>
"""

    return HTMLResponse(
        content=page,
        headers=NO_CACHE_HEADERS,
    )


# ============================================================
# RUN
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
        "web:app",
        host="0.0.0.0",
        port=port,
    )