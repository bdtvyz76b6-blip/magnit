import sqlite3
import secrets
import string
from datetime import datetime, timedelta

from config import DATABASE_PATH


# ============================================================
# CONNECTION
# ============================================================

def connect():
    db = sqlite3.connect(
        DATABASE_PATH,
        check_same_thread=False
    )
    db.row_factory = sqlite3.Row
    return db


# ============================================================
# INIT
# ============================================================

def init_db():
    db = connect()
    cur = db.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',

            token TEXT UNIQUE,
            uuid TEXT UNIQUE,

            subscription TEXT DEFAULT 'none',
            subscription_until TEXT DEFAULT '',

            device_limit INTEGER DEFAULT 2,

            trial_used INTEGER DEFAULT 0,
            blocked INTEGER DEFAULT 0,

            notify INTEGER DEFAULT 1,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            tariff TEXT,
            stars INTEGER,
            days INTEGER,
            telegram_charge_id TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY,
            days INTEGER DEFAULT 0,
            uses INTEGER DEFAULT 0,
            max_uses INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            vless_link TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            device_id TEXT,
            device_name TEXT DEFAULT '',
            last_seen TEXT DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(user_id, device_id)
        )
    """)

    db.commit()
    db.close()


# ============================================================
# USER
# ============================================================

def generate_token(length=40):
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def generate_uuid():
    import uuid
    return str(uuid.uuid4())


def create_user(user_id, username="", first_name=""):
    db = connect()
    cur = db.cursor()

    cur.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user_id,)
    )

    user = cur.fetchone()

    if user:
        cur.execute("""
            UPDATE users
            SET username=?, first_name=?
            WHERE user_id=?
        """, (
            username or "",
            first_name or "",
            user_id
        ))

        db.commit()

        cur.execute(
            "SELECT * FROM users WHERE user_id=?",
            (user_id,)
        )

        user = cur.fetchone()
        db.close()
        return dict(user)

    token = generate_token()
    user_uuid = generate_uuid()

    cur.execute("""
        INSERT INTO users (
            user_id,
            username,
            first_name,
            token,
            uuid
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        user_id,
        username or "",
        first_name or "",
        token,
        user_uuid
    ))

    db.commit()

    cur.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user_id,)
    )

    user = cur.fetchone()
    db.close()

    return dict(user)


def get_user(user_id):
    db = connect()
    cur = db.cursor()

    cur.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cur.fetchone()
    db.close()

    return dict(row) if row else None


def get_user_by_token(token):
    db = connect()
    cur = db.cursor()

    cur.execute(
        "SELECT * FROM users WHERE token=?",
        (token,)
    )

    row = cur.fetchone()
    db.close()

    return dict(row) if row else None


def get_all_users():
    db = connect()
    cur = db.cursor()

    cur.execute(
        "SELECT * FROM users ORDER BY created_at DESC"
    )

    rows = cur.fetchall()
    db.close()

    return [dict(x) for x in rows]


# ============================================================
# SUBSCRIPTION
# ============================================================

def extend_subscription(user_id, days, tariff=None):
    db = connect()
    cur = db.cursor()

    cur.execute(
        "SELECT subscription_until FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cur.fetchone()

    now = datetime.utcnow()

    if row and row["subscription_until"]:
        try:
            current = datetime.fromisoformat(
                row["subscription_until"]
            )
        except Exception:
            current = now
    else:
        current = now

    if current < now:
        current = now

    new_date = current + timedelta(days=days)

    cur.execute("""
        UPDATE users
        SET
            subscription=?,
            subscription_until=?,
            blocked=0
        WHERE user_id=?
    """, (
        tariff or "active",
        new_date.isoformat(),
        user_id
    ))

    db.commit()
    db.close()

    return new_date


def set_device_limit(user_id, limit):
    db = connect()
    db.execute(
        "UPDATE users SET device_limit=? WHERE user_id=?",
        (limit, user_id)
    )
    db.commit()
    db.close()


def block_user(user_id, blocked=True):
    db = connect()
    db.execute(
        "UPDATE users SET blocked=? WHERE user_id=?",
        (1 if blocked else 0, user_id)
    )
    db.commit()
    db.close()


def expire_old_subscriptions():
    db = connect()

    now = datetime.utcnow().isoformat()

    db.execute("""
        UPDATE users
        SET subscription='expired'
        WHERE subscription_until != ''
        AND subscription_until < ?
        AND subscription != 'expired'
    """, (now,))

    db.commit()
    db.close()


# ============================================================
# TRIAL
# ============================================================

def use_trial(user_id):
    db = connect()

    cur = db.cursor()

    cur.execute(
        "SELECT trial_used FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cur.fetchone()

    if not row or row["trial_used"]:
        db.close()
        return False

    cur.execute("""
        UPDATE users
        SET trial_used=1
        WHERE user_id=?
    """, (user_id,))

    db.commit()
    db.close()

    return True


# ============================================================
# PAYMENTS
# ============================================================

def create_payment(
    user_id,
    tariff,
    stars,
    days
):
    db = connect()

    cur = db.cursor()

    cur.execute("""
        INSERT INTO payments (
            user_id,
            tariff,
            stars,
            days
        )
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        tariff,
        stars,
        days
    ))

    payment_id = cur.lastrowid

    db.commit()
    db.close()

    return payment_id


def complete_payment(
    payment_id,
    telegram_charge_id
):
    db = connect()

    cur = db.cursor()

    cur.execute("""
        UPDATE payments
        SET
            status='paid',
            telegram_charge_id=?
        WHERE id=?
    """, (
        telegram_charge_id,
        payment_id
    ))

    db.commit()

    cur.execute(
        "SELECT * FROM payments WHERE id=?",
        (payment_id,)
    )

    row = cur.fetchone()

    db.close()

    return dict(row) if row else None


# ============================================================
# PROMOCODES
# ============================================================

def create_promo(code, days, max_uses=1):
    db = connect()

    try:
        db.execute("""
            INSERT INTO promocodes (
                code,
                days,
                max_uses
            )
            VALUES (?, ?, ?)
        """, (
            code.upper(),
            days,
            max_uses
        ))

        db.commit()
        result = True

    except sqlite3.IntegrityError:
        result = False

    db.close()

    return result


def use_promo(code):
    db = connect()

    cur = db.cursor()

    cur.execute(
        "SELECT * FROM promocodes WHERE code=?",
        (code.upper(),)
    )

    promo = cur.fetchone()

    if not promo:
        db.close()
        return None

    if promo["uses"] >= promo["max_uses"]:
        db.close()
        return None

    cur.execute("""
        UPDATE promocodes
        SET uses=uses+1
        WHERE code=?
    """, (code.upper(),))

    db.commit()
    db.close()

    return dict(promo)


# ============================================================
# NODES
# ============================================================

def add_node(name, vless_link):
    db = connect()

    cur = db.cursor()

    cur.execute("""
        INSERT INTO nodes (
            name,
            vless_link
        )
        VALUES (?, ?)
    """, (
        name,
        vless_link
    ))

    db.commit()
    node_id = cur.lastrowid
    db.close()

    return node_id


def delete_node(node_id):
    db = connect()

    db.execute(
        "DELETE FROM nodes WHERE id=?",
        (node_id,)
    )

    db.commit()
    db.close()


def get_nodes():
    db = connect()

    cur = db.cursor()

    cur.execute("""
        SELECT *
        FROM nodes
        WHERE enabled=1
        ORDER BY id
    """)

    rows = cur.fetchall()
    db.close()

    return [dict(x) for x in rows]


# ============================================================
# DEVICES
# ============================================================

def add_device(user_id, device_id, device_name=""):
    db = connect()

    cur = db.cursor()

    cur.execute("""
        SELECT *
        FROM devices
        WHERE user_id=? AND device_id=?
    """, (
        user_id,
        device_id
    ))

    existing = cur.fetchone()

    if existing:
        cur.execute("""
            UPDATE devices
            SET
                device_name=?,
                last_seen=CURRENT_TIMESTAMP
            WHERE user_id=? AND device_id=?
        """, (
            device_name,
            user_id,
            device_id
        ))

        db.commit()
        db.close()
        return True

    cur.execute(
        "SELECT device_limit FROM users WHERE user_id=?",
        (user_id,)
    )

    user = cur.fetchone()

    limit = user["device_limit"] if user else 2

    cur.execute("""
        SELECT COUNT(*) AS count
        FROM devices
        WHERE user_id=?
    """, (user_id,))

    count = cur.fetchone()["count"]

    if count >= limit:
        db.close()
        return False

    cur.execute("""
        INSERT INTO devices (
            user_id,
            device_id,
            device_name
        )
        VALUES (?, ?, ?)
    """, (
        user_id,
        device_id,
        device_name
    ))

    db.commit()
    db.close()

    return True


def get_devices(user_id):
    db = connect()

    cur = db.cursor()

    cur.execute("""
        SELECT *
        FROM devices
        WHERE user_id=?
        ORDER BY last_seen DESC
    """, (user_id,))

    rows = cur.fetchall()
    db.close()

    return [dict(x) for x in rows]


def delete_device(user_id, device_id):
    db = connect()

    db.execute("""
        DELETE FROM devices
        WHERE user_id=? AND device_id=?
    """, (
        user_id,
        device_id
    ))

    db.commit()
    db.close()


# ============================================================
# STATISTICS
# ============================================================

def get_stats():
    db = connect()
    cur = db.cursor()

    cur.execute(
        "SELECT COUNT(*) AS c FROM users"
    )
    users = cur.fetchone()["c"]

    cur.execute("""
        SELECT COUNT(*) AS c
        FROM users
        WHERE subscription_until != ''
        AND subscription_until > ?
    """, (datetime.utcnow().isoformat(),))

    active = cur.fetchone()["c"]

    cur.execute("""
        SELECT COUNT(*) AS c
        FROM payments
        WHERE status='paid'
    """)

    payments = cur.fetchone()["c"]

    cur.execute("""
        SELECT COALESCE(SUM(stars), 0) AS s
        FROM payments
        WHERE status='paid'
    """)

    stars = cur.fetchone()["s"]

    db.close()

    return {
        "users": users,
        "active": active,
        "payments": payments,
        "stars": stars,
    }


init_db()