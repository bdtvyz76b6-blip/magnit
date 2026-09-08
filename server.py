# server.py

import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from config import (
    SERVICE_NAME,
    PROFILE_TITLE,
    PROFILE_UPDATE_INTERVAL,
)

from database import (
    get_user_by_token,
    parse_datetime,
    now_utc,
)

from subscription import (
    ensure_subscription,
    build_subscription_content,
)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title=f"{SERVICE_NAME} API",
    docs_url=None,
    redoc_url=None,
)


# ============================================================
# HELPERS
# ============================================================

def check_user(token: str):

    user = get_user_by_token(token)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    if int(
        user.get("blocked", 0) or 0
    ):
        raise HTTPException(
            status_code=403,
            detail="Subscription blocked",
        )

    subscription_until = (
        user.get(
            "subscription_until",
            "",
        )
        or ""
    )

    if not subscription_until:
        raise HTTPException(
            status_code=403,
            detail="Subscription inactive",
        )

    expire = parse_datetime(
        subscription_until
    )

    if not expire:
        raise HTTPException(
            status_code=500,
            detail="Invalid expiration date",
        )

    if expire <= now_utc():
        raise HTTPException(
            status_code=403,
            detail="Subscription expired",
        )

    return user


def get_expire_timestamp(
    user,
) -> int:

    value = (
        user.get(
            "subscription_until",
            "",
        )
        or ""
    )

    expire = parse_datetime(
        value
    )

    if not expire:
        return 0

    return int(
        expire.timestamp()
    )


# ============================================================
# SUBSCRIPTION API
# ============================================================

@app.get(
    "/sub/{token}",
    response_class=PlainTextResponse,
)
async def subscription(
    token: str,
):

    user = check_user(
        token
    )

    user_id = int(
        user["user_id"]
    )

    try:

        ensure_subscription(
            user_id
        )

    except Exception as exc:

        print(
            f"[SERVER] "
            f"ensure_subscription "
            f"error for {user_id}: "
            f"{exc}"
        )

    # Берём серверы непосредственно
    # из servers.txt.
    content = build_subscription_content(
        user_id
    )

    if not content:
        raise HTTPException(
            status_code=503,
            detail="No servers available",
        )

    expire = get_expire_timestamp(
        user
    )

    headers = {
        "Cache-Control": (
            "no-store, "
            "no-cache, "
            "must-revalidate"
        ),
        "Pragma": "no-cache",
        "Expires": "0",

        "profile-title": PROFILE_TITLE,

        "profile-update-interval": str(
            PROFILE_UPDATE_INTERVAL
        ),

        "subscription-userinfo": (
            "upload=0;"
            "download=0;"
            "total=0;"
            f"expire={expire}"
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
# JSON SUBSCRIPTION
# ============================================================

@app.get(
    "/sub/{token}/json"
)
async def subscription_json(
    token: str,
):

    user = check_user(
        token
    )

    user_id = int(
        user["user_id"]
    )

    content = build_subscription_content(
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

            name = line.split(
                "#",
                1,
            )[1]

        servers.append(
            {
                "name": name,
                "url": line,
            }
        )

    expire = get_expire_timestamp(
        user
    )

    return {
        "service": SERVICE_NAME,

        "profile": {
            "title": PROFILE_TITLE,
            "update_interval": (
                PROFILE_UPDATE_INTERVAL
            ),
        },

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
            "expire": expire,
        },

        "servers": servers,
    }


# ============================================================
# CHECK SUBSCRIPTION
# ============================================================

@app.get(
    "/api/check/{token}"
)
async def check_subscription(
    token: str,
):

    user = check_user(
        token
    )

    expire = get_expire_timestamp(
        user
    )

    return {
        "success": True,

        "user_id": int(
            user["user_id"]
        ),

        "active": True,

        "subscription": user.get(
            "subscription",
            "none",
        ),

        "subscription_until": user.get(
            "subscription_until",
            "",
        ),

        "expire": expire,
    }


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
        "status": "ok",
        "service": SERVICE_NAME,
    }


# ============================================================
# RUN
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
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )