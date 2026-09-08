from datetime import datetime

from fastapi import (
    FastAPI,
    HTTPException,
)

from fastapi.responses import Response

from database import (
    get_user_by_token,
    get_nodes,
    get_devices,
    add_device,
    parse_datetime,
    now_utc,
)

import os


# ============================================================
# CONFIG
# ============================================================

SERVICE_NAME = os.getenv(
    "SERVICE_NAME",
    "Магнит VPN",
)

API_SECRET = os.getenv(
    "API_SECRET",
    "",
)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Магнит VPN API"
)


# ============================================================
# USER CHECK
# ============================================================

def check_user(token):

    user = get_user_by_token(
        token
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )


    if int(
        user.get("blocked", 0)
        or 0
    ):

        raise HTTPException(
            status_code=403,
            detail="Subscription blocked",
        )


    if not user.get(
        "subscription_until"
    ):

        raise HTTPException(
            status_code=403,
            detail="Subscription inactive",
        )


    expire = parse_datetime(
        user.get(
            "subscription_until"
        )
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


# ============================================================
# SUBSCRIPTION
# ============================================================

@app.get(
    "/sub/{token}"
)
async def subscription(
    token: str,
):

    user = check_user(
        token
    )


    nodes = get_nodes(
        active_only=True
    )


    links = []

    for node in nodes:

        link = (
            node.get(
                "vless_link",
                "",
            )
            or ""
        ).strip()

        if not link:
            continue

        if not link.startswith(
            "vless://"
        ):
            continue

        links.append(
            link
        )


    content = "\n".join(
        links
    )


    encoded = __import__(
        "base64"
    ).b64encode(
        content.encode("utf-8")
    ).decode("ascii")


    expire = int(
        parse_datetime(
            user[
                "subscription_until"
            ]
        ).timestamp()
    )


    headers = {

        "subscription-userinfo":
            "upload=0;"
            "download=0;"
            f"total=0;"
            f"expire={expire}",

        "profile-title":
            SERVICE_NAME,

        "profile-update-interval":
            "6",

        "content-disposition":
            'attachment; '
            'filename="magnit.txt"',
    }


    return Response(
        content=encoded,
        media_type=(
            "text/plain; "
            "charset=utf-8"
        ),
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


    nodes = get_nodes(
        active_only=True
    )


    servers = []


    for node in nodes:

        url = (
            node.get(
                "vless_link",
                "",
            )
            or ""
        ).strip()


        if not url:
            continue


        servers.append({
            "name": node.get(
                "name",
                "",
            ),
            "url": url,
        })


    expire = int(
        parse_datetime(
            user[
                "subscription_until"
            ]
        ).timestamp()
    )


    data = {

        "name":
            SERVICE_NAME,

        "expire":
            expire,

        "user": {

            "id":
                user["user_id"],

            "subscription":
                user.get(
                    "subscription",
                    "none",
                ),

            "device_limit":
                int(
                    user.get(
                        "device_limit",
                        3,
                    )
                    or 3
                ),
        },

        "servers":
            servers,
    }


    return data


# ============================================================
# DEVICE REGISTER
# ============================================================

@app.post(
    "/api/device/{token}"
)
async def register_device(
    token: str,
    device_id: str,
    device_name: str = "",
):

    user = check_user(
        token
    )


    success = add_device(
        user["user_id"],
        device_id,
        device_name,
    )


    if not success:

        return {
            "success": False,
            "error":
                "device_limit",
        }


    return {
        "success": True,
    }


# ============================================================
# DEVICES
# ============================================================

@app.get(
    "/api/devices/{token}"
)
async def devices(
    token: str,
):

    user = check_user(
        token
    )


    items = get_devices(
        user["user_id"]
    )


    return {

        "success":
            True,

        "limit":
            int(
                user.get(
                    "device_limit",
                    3,
                )
                or 3
            ),

        "devices":
            items,
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/")
async def root():

    return {
        "service":
            SERVICE_NAME,

        "status":
            "online",
    }


@app.get("/health")
async def health():

    return {
        "status":
            "ok",
    }


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=int(
            os.getenv(
                "PORT",
                "8080",
            )
        ),
        reload=False,
    )