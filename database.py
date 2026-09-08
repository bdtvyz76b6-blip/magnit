import os
import sqlite3
import secrets
import uuid as uuid_lib

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# НАСТРОЙКИ
# ============================================================

DB_PATH = os.getenv("DB_PATH", "/data/users.db")

MOSCOW_TZ = ZoneInfo("Europe/Moscow")


# ============================================================
# ВРЕМЯ
# ============================================================

def now_moscow():
    """Текущее время по Москве."""
    return datetime.now(MOSCOW_TZ)


def now_moscow_iso():
    """Текущее московское время в ISO формате."""
    return now_moscow().isoformat()


def parse_datetime(value):
    """
    Преобразует строку/дату в timezone-aware datetime.
    Старые даты без timezone считаются московскими.
    """
    if not value:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value))
        except (ValueError, TypeError):
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MOSCOW_TZ)

    return dt


# ============================================================
# ПОДКЛЮЧЕНИЕ К БД
# ============================================================

def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    db = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False,
    )

    db.row_factory = sqlite3.Row

    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=30000")
    except Exception:
        pass

    return db


# ============================================================
# ГЕНЕРАЦИЯ
# ============================================================

def generate_token(length=32):
    return secrets.token_urlsafe(length)


def generate_uuid():
    return str(uuid_lib.uuid4())


# ============================================================
# PUBLIC URL
# ============================================================

def get_public_url():
    try:
        from config import PUBLIC_URL

        if PUBLIC_URL:
            return PUBLIC_URL.rstrip("/")
    except Exception:
        pass

    return os.getenv(
        "PUBLIC_URL",
        "https://orelvpnrailoh-1.onrender.com"
    ).rstrip("/")


def build_subscription_link(token):
    """
    Основная ссылка пользователя.
    """

    public_url = get_public_url()

    return f"{public_url}/sub/{token}"


# ============================================================
# ИНИЦИАЛИЗАЦИЯ БД
# ============================================================

def init_db():

    with connect() as db:

        # ----------------------------------------------------
        # USERS
        # ----------------------------------------------------

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',

                token TEXT DEFAULT '',
                uuid TEXT DEFAULT '',

                subscription TEXT DEFAULT 'none',
                subscription_until TEXT DEFAULT '',

                subscription_link TEXT DEFAULT '',

                device_limit INTEGER DEFAULT 1,

                trial_used INTEGER DEFAULT 0,

                blocked INTEGER DEFAULT 0,

                notify INTEGER DEFAULT 1,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # ----------------------------------------------------
        # PAYMENTS
        # ----------------------------------------------------

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER,

                tariff TEXT DEFAULT '',
                stars INTEGER DEFAULT 0,
                days INTEGER DEFAULT 0,

                telegram_charge_id TEXT DEFAULT '',

                status TEXT DEFAULT 'pending',

                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # ----------------------------------------------------
        # PROMOCODES
        # ----------------------------------------------------

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,

                days INTEGER DEFAULT 0,

                uses INTEGER DEFAULT 0,

                max_uses INTEGER DEFAULT 1,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # ----------------------------------------------------
        # NODES
        # ----------------------------------------------------

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                name TEXT NOT NULL,

                vless_link TEXT NOT NULL,

                enabled INTEGER DEFAULT 1,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # ----------------------------------------------------
        # DEVICES
        # ----------------------------------------------------

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                device_id TEXT NOT NULL,

                device_name TEXT DEFAULT '',

                last_seen TEXT DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(user_id, device_id)
            )
            """
        )

        db.commit()

        # ====================================================
        # МИГРАЦИЯ СТАРОЙ БД
        # ====================================================

        columns = {
            row["name"]
            for row in db.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        }

        migrations = {
            "token": "ALTER TABLE users ADD COLUMN token TEXT DEFAULT ''",
            "uuid": "ALTER TABLE users ADD COLUMN uuid TEXT DEFAULT ''",
            "subscription_link": (
                "ALTER TABLE users "
                "ADD COLUMN subscription_link TEXT DEFAULT ''"
            ),
            "device_limit": (
                "ALTER TABLE users "
                "ADD COLUMN device_limit INTEGER DEFAULT 1"
            ),
            "blocked": (
                "ALTER TABLE users "
                "ADD COLUMN blocked INTEGER DEFAULT 0"
            ),
            "notify": (
                "ALTER TABLE users "
                "ADD COLUMN notify INTEGER DEFAULT 1"
            ),
        }

        for column, sql in migrations.items():

            if column not in columns:

                try:
                    db.execute(sql)
                except sqlite3.OperationalError:
                    pass

        # ----------------------------------------------------
        # MIGRATION PAYMENTS
        # ----------------------------------------------------

        payment_columns = {
            row["name"]
            for row in db.execute(
                "PRAGMA table_info(payments)"
            ).fetchall()
        }

        payment_migrations = {
            "tariff": (
                "ALTER TABLE payments "
                "ADD COLUMN tariff TEXT DEFAULT ''"
            ),
            "stars": (
                "ALTER TABLE payments "
                "ADD COLUMN stars INTEGER DEFAULT 0"
            ),
            "days": (
                "ALTER TABLE payments "
                "ADD COLUMN days INTEGER DEFAULT 0"
            ),
            "telegram_charge_id": (
                "ALTER TABLE payments "
                "ADD COLUMN telegram_charge_id TEXT DEFAULT ''"
            ),
            "status": (
                "ALTER TABLE payments "
                "ADD COLUMN status TEXT DEFAULT 'pending'"
            ),
        }

        for column, sql in payment_migrations.items():

            if column not in payment_columns:

                try:
                    db.execute(sql)
                except sqlite3.OperationalError:
                    pass

        # ====================================================
        # ВОССТАНОВЛЕНИЕ ДАННЫХ
        # ====================================================

        users = db.execute(
            "SELECT * FROM users"
        ).fetchall()

        for user in users:

            user_id = user["user_id"]

            # ------------------------------------------------
            # TOKEN
            # ------------------------------------------------

            token = user["token"]

            if not token:

                new_token = generate_token()

                # Проверяем уникальность
                while db.execute(
                    "SELECT 1 FROM users WHERE token = ?",
                    (new_token,)
                ).fetchone():

                    new_token = generate_token()

                db.execute(
                    """
                    UPDATE users
                    SET token = ?
                    WHERE user_id = ?
                    """,
                    (new_token, user_id)
                )

                token = new_token

            # ------------------------------------------------
            # UUID
            # ------------------------------------------------

            if not user["uuid"]:

                db.execute(
                    """
                    UPDATE users
                    SET uuid = ?
                    WHERE user_id = ?
                    """,
                    (
                        generate_uuid(),
                        user_id
                    )
                )

            # ------------------------------------------------
            # SUBSCRIPTION LINK
            # ------------------------------------------------

            link = user["subscription_link"]

            if not link:

                link = build_subscription_link(token)

                db.execute(
                    """
                    UPDATE users
                    SET subscription_link = ?
                    WHERE user_id = ?
                    """,
                    (
                        link,
                        user_id
                    )
                )

            # ------------------------------------------------
            # DEVICE LIMIT
            # ------------------------------------------------

            try:
                if user["device_limit"] is None:
                    db.execute(
                        """
                        UPDATE users
                        SET device_limit = 1
                        WHERE user_id = ?
                        """,
                        (user_id,)
                    )
            except Exception:
                pass

        db.commit()


# ============================================================
# USERS
# ============================================================

def create_user(
    user_id,
    username="",
    first_name=""
):

    existing = get_user(user_id)

    if existing:
        return existing

    token = generate_token()

    # Проверка уникальности токена
    while True:

        with connect() as db:

            exists = db.execute(
                "SELECT 1 FROM users WHERE token = ?",
                (token,)
            ).fetchone()

        if not exists:
            break

        token = generate_token()

    user_uuid = generate_uuid()

    subscription_link = build_subscription_link(token)

    with connect() as db:

        db.execute(
            """
            INSERT INTO users (
                user_id,
                username,
                first_name,
                token,
                uuid,
                subscription,
                subscription_until,
                subscription_link,
                device_limit,
                trial_used,
                blocked,
                notify,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username or "",
                first_name or "",
                token,
                user_uuid,
                "none",
                "",
                subscription_link,
                1,
                0,
                0,
                1,
                now_moscow_iso(),
            )
        )

        db.commit()

    return get_user(user_id)


def get_user(user_id):

    with connect() as db:

        row = db.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()

    if not row:
        return None

    return dict(row)


def get_user_by_token(token):

    if not token:
        return None

    with connect() as db:

        row = db.execute(
            """
            SELECT *
            FROM users
            WHERE token = ?
            """,
            (token,)
        ).fetchone()

    if not row:
        return None

    return dict(row)


def get_all_users():

    with connect() as db:

        rows = db.execute(
            """
            SELECT *
            FROM users
            ORDER BY created_at DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


# ============================================================
# SUBSCRIPTION LINK
# ============================================================

def save_subscription_link(user_id, link):

    with connect() as db:

        db.execute(
            """
            UPDATE users
            SET subscription_link = ?
            WHERE user_id = ?
            """,
            (
                link,
                user_id
            )
        )

        db.commit()


def get_subscription_link(user_id):

    user = get_user(user_id)

    if not user:
        return ""

    link = user.get("subscription_link")

    if link:
        return link

    token = user.get("token")

    if token:

        link = build_subscription_link(token)

        save_subscription_link(
            user_id,
            link
        )

        return link

    return ""


# ============================================================
# SUBSCRIPTION
# ============================================================

def extend_subscription(
    user_id,
    days,
    subscription="vip"
):

    user = get_user(user_id)

    if not user:
        return None

    now = now_moscow()

    current_until = parse_datetime(
        user.get("subscription_until")
    )

    if current_until and current_until > now:
        start = current_until
    else:
        start = now

    from datetime import timedelta

    new_until = start + timedelta(days=int(days))

    with connect() as db:

        db.execute(
            """
            UPDATE users
            SET
                subscription = ?,
                subscription_until = ?
            WHERE user_id = ?
            """,
            (
                subscription,
                new_until.isoformat(),
                user_id
            )
        )

        db.commit()

    return get_user(user_id)


def expire_old_subscriptions():

    now = now_moscow()

    expired_count = 0

    users = get_all_users()

    for user in users:

        subscription = user.get("subscription")

        if subscription in (
            "none",
            "",
            None
        ):
            continue

        until = parse_datetime(
            user.get("subscription_until")
        )

        if not until:
            continue

        if until <= now:

            with connect() as db:

                db.execute(
                    """
                    UPDATE users
                    SET
                        subscription = 'none',
                        subscription_until = ''
                    WHERE user_id = ?
                    """,
                    (
                        user["user_id"],
                    )
                )

                db.commit()

            expired_count += 1

    return expired_count


# ============================================================
# DEVICE LIMIT
# ============================================================

def set_device_limit(
    user_id,
    limit
):

    limit = max(1, int(limit))

    with connect() as db:

        db.execute(
            """
            UPDATE users
            SET device_limit = ?
            WHERE user_id = ?
            """,
            (
                limit,
                user_id
            )
        )

        db.commit()

    return get_user(user_id)


# ============================================================
# BLOCK
# ============================================================

def block_user(
    user_id,
    blocked=True
):

    with connect() as db:

        db.execute(
            """
            UPDATE users
            SET blocked = ?
            WHERE user_id = ?
            """,
            (
                1 if blocked else 0,
                user_id
            )
        )

        db.commit()

    return get_user(user_id)


# ============================================================
# TRIAL
# ============================================================

def use_trial(user_id):

    user = get_user(user_id)

    if not user:
        return False

    if user.get("trial_used"):
        return False

    with connect() as db:

        db.execute(
            """
            UPDATE users
            SET trial_used = 1
            WHERE user_id = ?
            """,
            (user_id,)
        )

        db.commit()

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

    with connect() as db:

        cursor = db.execute(
            """
            INSERT INTO payments (
                user_id,
                tariff,
                stars,
                days,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                tariff,
                int(stars),
                int(days),
                "pending",
                now_moscow_iso(),
            )
        )

        db.commit()

        return cursor.lastrowid


def complete_payment(
    payment_id,
    telegram_charge_id=""
):

    with connect() as db:

        payment = db.execute(
            """
            SELECT *
            FROM payments
            WHERE id = ?
            """,
            (payment_id,)
        ).fetchone()

        if not payment:
            return None

        # Защита от повторной оплаты
        if payment["status"] == "paid":
            return dict(payment)

        db.execute(
            """
            UPDATE payments
            SET
                status = 'paid',
                telegram_charge_id = ?
            WHERE id = ?
            """,
            (
                telegram_charge_id or "",
                payment_id
            )
        )

        db.commit()

        payment = db.execute(
            """
            SELECT *
            FROM payments
            WHERE id = ?
            """,
            (payment_id,)
        ).fetchone()

    return dict(payment) if payment else None


# ============================================================
# PROMOCODES
# ============================================================

def create_promo(
    code,
    days,
    max_uses=1
):

    code = str(code).strip().upper()

    with connect() as db:

        existing = db.execute(
            """
            SELECT code
            FROM promocodes
            WHERE code = ?
            """,
            (code,)
        ).fetchone()

        if existing:
            return False

        db.execute(
            """
            INSERT INTO promocodes (
                code,
                days,
                uses,
                max_uses,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                code,
                int(days),
                0,
                int(max_uses),
                now_moscow_iso(),
            )
        )

        db.commit()

    return True


def use_promo(
    user_id,
    code
):

    code = str(code).strip().upper()

    with connect() as db:

        promo = db.execute(
            """
            SELECT *
            FROM promocodes
            WHERE code = ?
            """,
            (code,)
        ).fetchone()

        if not promo:
            return False

        if promo["uses"] >= promo["max_uses"]:
            return False

        # Увеличиваем использование
        db.execute(
            """
            UPDATE promocodes
            SET uses = uses + 1
            WHERE code = ?
            """,
            (code,)
        )

        db.commit()

    return int(promo["days"])


# ============================================================
# NODES
# ============================================================

def add_node(
    name,
    vless_link
):

    with connect() as db:

        cursor = db.execute(
            """
            INSERT INTO nodes (
                name,
                vless_link,
                enabled,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                name,
                vless_link,
                1,
                now_moscow_iso(),
            )
        )

        db.commit()

        return cursor.lastrowid


def delete_node(node_id):

    with connect() as db:

        db.execute(
            """
            DELETE FROM nodes
            WHERE id = ?
            """,
            (node_id,)
        )

        db.commit()


def get_nodes(
    enabled_only=False
):

    with connect() as db:

        if enabled_only:

            rows = db.execute(
                """
                SELECT *
                FROM nodes
                WHERE enabled = 1
                ORDER BY id ASC
                """
            ).fetchall()

        else:

            rows = db.execute(
                """
                SELECT *
                FROM nodes
                ORDER BY id ASC
                """
            ).fetchall()

    return [dict(row) for row in rows]


# ============================================================
# DEVICES
# ============================================================

def add_device(
    user_id,
    device_id,
    device_name=""
):

    device_id = str(device_id)

    with connect() as db:

        existing = db.execute(
            """
            SELECT *
            FROM devices
            WHERE user_id = ?
            AND device_id = ?
            """,
            (
                user_id,
                device_id
            )
        ).fetchone()

        if existing:

            db.execute(
                """
                UPDATE devices
                SET
                    device_name = ?,
                    last_seen = ?
                WHERE user_id = ?
                AND device_id = ?
                """,
                (
                    device_name or "",
                    now_moscow_iso(),
                    user_id,
                    device_id
                )
            )

            db.commit()

            return True

        # ----------------------------------------------------
        # Проверка лимита
        # ----------------------------------------------------

        user = db.execute(
            """
            SELECT device_limit
            FROM users
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()

        if not user:
            return False

        limit = user["device_limit"] or 1

        count = db.execute(
            """
            SELECT COUNT(*)
            FROM devices
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()[0]

        if count >= limit:
            return False

        # ----------------------------------------------------
        # Добавляем устройство
        # ----------------------------------------------------

        db.execute(
            """
            INSERT INTO devices (
                user_id,
                device_id,
                device_name,
                last_seen
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                device_id,
                device_name or "",
                now_moscow_iso(),
            )
        )

        db.commit()

    return True


def get_devices(user_id):

    with connect() as db:

        rows = db.execute(
            """
            SELECT *
            FROM devices
            WHERE user_id = ?
            ORDER BY last_seen DESC
            """,
            (user_id,)
        ).fetchall()

    return [dict(row) for row in rows]


def delete_device(
    user_id,
    device_id
):

    with connect() as db:

        db.execute(
            """
            DELETE FROM devices
            WHERE user_id = ?
            AND device_id = ?
            """,
            (
                user_id,
                device_id
            )
        )

        db.commit()

    return True


# ============================================================
# СТАТИСТИКА
# ============================================================

def get_stats():

    with connect() as db:

        users = db.execute(
            """
            SELECT COUNT(*)
            FROM users
            """
        ).fetchone()[0]

        active = db.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE subscription != 'none'
            AND subscription != ''
            AND subscription_until != ''
            """
        ).fetchone()[0]

        blocked = db.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE blocked = 1
            """
        ).fetchone()[0]

        payments = db.execute(
            """
            SELECT COUNT(*)
            FROM payments
            WHERE status = 'paid'
            """
        ).fetchone()[0]

        stars = db.execute(
            """
            SELECT COALESCE(SUM(stars), 0)
            FROM payments
            WHERE status = 'paid'
            """
        ).fetchone()[0]

        devices = db.execute(
            """
            SELECT COUNT(*)
            FROM devices
            """
        ).fetchone()[0]

        promocodes = db.execute(
            """
            SELECT COUNT(*)
            FROM promocodes
            """
        ).fetchone()[0]

    return {
        "users": users,
        "active": active,
        "blocked": blocked,
        "payments": payments,
        "stars": stars,
        "devices": devices,
        "promocodes": promocodes,
    }


# ============================================================
# ЗАПУСК ИНИЦИАЛИЗАЦИИ
# ============================================================

init_db()