import base64
import json
from datetime import datetime
from urllib.parse import unquote

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response

from config import API_SECRET, SERVICE_NAME
from database import (
    get_user_by_token,
    get_nodes,
    get_devices,
)


app = FastAPI(
    title="Магнит VPN API"
)


# ============================================================
# CHECK SUBSCRIPTION
# ============================================================

def check_user(token):
    user = get_user_by_token(token)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found"
        )

    if user["blocked"]:
        raise HTTPException(
            status_code=403,
            detail="Subscription blocked"
        )

    if not user["subscription_until"]:
        raise HTTPException(
            status_code=403,
            detail="Subscription inactive"
        )

    try:
        expire = datetime.fromisoformat(
            user["subscription_until"]
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Invalid expiration date"
        )

    if expire < datetime.utcnow():
        raise HTTPException(
            status_code=403,
            detail="Subscription expired"
        )

    return user


# ============================================================
# VLESS → BASE64
# ============================================================

def encode_base64(text):
    return base64.b64encode(
        text.encode()
    ).decode()


# ============================================================
# SUBSCRIPTION
# ============================================================

@app.get("/sub/{token}")
async def subscription(token: str):

    user = check_user(token)
    nodes = get_nodes()

    links = []

    for node in nodes:
        link = node["vless_link"].strip()

        if not link:
            continue

        # Можно оставить ссылку как есть.
        # Сервер просто отдаёт её Happ.
        links.append(link)

    # Если узлов нет — отдаём пустую подписку.
    content = "\n".join(links)

    encoded = encode_base64(content)

    expire = int(
        datetime.fromisoformat(
            user["subscription_until"]
        ).timestamp()
    )

    headers = {
        "subscription-userinfo": (
            f"upload=0;"
            f"download=0;"
            f"total=0;"
            f"expire={expire}"
        ),
        "profile-title": SERVICE_NAME,
        "profile-update-interval": "6",
        "content-disposition":
            'attachment; filename="magnit.txt"',
    }

    return Response(
        content=encoded,
        media_type="text/plain; charset=utf-8",
        headers=headers
    )


# ============================================================
# JSON SUBSCRIPTION
# ============================================================

@app.get("/sub/{token}/json")
async def subscription_json(token: str):

    user = check_user(token)
    nodes = get_nodes()

    servers = []

    for node in nodes:
        servers.append({
            "name": node["name"],
            "url": node["vless_link"],
        })

    expire = int(
        datetime.fromisoformat(
            user["subscription_until"]
        ).timestamp()
    )

    data = {
        "name": SERVICE_NAME,
        "expire": expire,
        "user": {
            "id": user["user_id"],
            "subscription": user["subscription"],
            "device_limit": user["device_limit"],
        },
        "servers": servers,
    }

    return data


# ============================================================
# DEVICES
# ============================================================

@app.post("/api/device/{token}")
async def register_device(
    token: str,
    device_id: str,
    device_name: str = "",
):
    user = check_user(token)

    from database import add_device

    success = add_device(
        user["user_id"],
        device_id,
        device_name
    )

    if not success:
        return {
            "success": False,
            "error": "device_limit"
        }

    return {
        "success": True
    }


@app.get("/api/devices/{token}")
async def devices(token: str):

    user = check_user(token)

    items = get_devices(
        user["user_id"]
    )

    return {
        "success": True,
        "limit": user["device_limit"],
        "devices": items
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/")
async def root():
    return {
        "service": SERVICE_NAME,
        "status": "online"
    }


@app.get("/health")
async def health():
    return {
        "status": "ok"
    }


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8080,
        reload=False
    )