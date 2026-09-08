import sqlite3
import secrets
import string
import uuid

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import DATABASE_PATH


# ============================================================
# TIMEZONE
# ============================================================

MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def now_moscow():
    """
    Текущее время по Москве.
    Возвращает timezone-aware datetime.
    """
    return datetime.now(MOSCOW_TZ)


def now_moscow_iso():
    """
    Текущее московское время в ISO формате.
    """
    return now_moscow().isoformat()


def parse_datetime(value):
    """
    Безопасно преобразует дату из БД в datetime.

    Поддерживает:
    - старые даты без timezone;
    - новые даты с timezone;
    - datetime;
    - пустые значения.
    """

    if not value:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value))
        except Exception:
            return None

    # Старые даты из БД могли быть без timezone.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MOSCOW_TZ)

    return dt.astimezone(MOSCOW_TZ)


# ============================================================
# CONNECTION
# ============================================================

def connect():
    db = sqlite3.connect(
        DATABASE_PATH,
        check_same_thread=False,
        timeout=30,
    )

    db.row_factory = sqlite3.Row

    # SQLite будет ждать освобождения БД.
    db.execute("PRAGMA busy_timeout = 30000")

    return db


# ============================================================
# INIT / MIGRATION
# ============================================================

def column_exists(db, table, column):
    cur = db.cursor()

    cur.execute(
        f"PRAGMA table_info({table})"
    )

    columns = [
        row["name"]
        for row in cur.fetchall()
    ]

    return column in columns


def add_column_if_missing(
    db,
    table,
    column,
    definition,
):
    if not column_exists(
        db,
        table,
        column,
    ):
        db.execute(
            f"ALTER TABLE {table} "
            f"ADD COLUMN {column} {definition}"
        )


def init_db():

    db = connect()
    cur = db.cursor()

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',

            token TEXT UNIQUE,
            uuid TEXT UNIQUE,

            subscription TEXT DEFAULT 'none',
            subscription_until TEXT DEFAULT '',

            subscription_link TEXT DEFAULT '',

            device_limit INTEGER DEFAULT 2,

            trial_used INTEGER DEFAULT 0,
            blocked INTEGER DEFAULT 0,

            notify INTEGER DEFAULT 1,

            created_at TEXT DEFAULT ''
        )
    """)

    # --------------------------------------------------------
    # PAYMENTS
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            tariff TEXT,
            stars INTEGER,
            days INTEGER,
            telegram_charge_id TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT ''
        )
    """)

    # --------------------------------------------------------
    # PROMOCODES
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY,
            days INTEGER DEFAULT 0,
            uses INTEGER DEFAULT 0,
            max_uses INTEGER DEFAULT 1,
            created_at TEXT DEFAULT ''
        )
    """)

    # --------------------------------------------------------
    # NODES
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            vless_link TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT ''
        )
    """)

    # --------------------------------------------------------
    # DEVICES
    # --------------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            device_id TEXT,
            device_name TEXT DEFAULT '',
            last_seen TEXT DEFAULT '',

            UNIQUE(user_id, device_id)
        )
    """)

    # ========================================================
    # МИГРАЦИЯ СТАРОЙ БД
    # ========================================================

    # USERS
    add_column_if_missing(
        db,
        "users",
        "subscription_link",
        "TEXT DEFAULT ''",
    )

    add_column_if_missing(
        db,
        "users",
        "device_limit",
        "INTEGER DEFAULT 2",
    )

    add_column_if_missing(
        db,
        "users",
        "blocked",
        "INTEGER DEFAULT 0",
    )

    add_column_if_missing(
        db,
        "users",
        "notify",
        "INTEGER DEFAULT 1",
    )

    add_column_if_missing(
        db,
        "users",
        "token",
        "TEXT",
    )

    add_column_if_missing(
        db,
        "users",
        "uuid",
        "TEXT",
    )

    # PAYMENTS
    add_column_if_missing(
        db,
        "payments",
        "tariff",
        "TEXT",
    )

    add_column_if_missing(
        db,
        "payments",
        "stars",
        "INTEGER DEFAULT 0",
    )

    add_column_if_missing(
        db,
        "payments",
        "days",
        "INTEGER DEFAULT 0",
    )

    add_column_if_missing(
        db,
        "payments",
        "telegram_charge_id",
        "TEXT DEFAULT ''",
    )

    add_column_if_missing(
        db,
        "payments",
        "status",
        "TEXT DEFAULT 'pending'",
    )

    # ========================================================
    # ЗАПОЛНЯЕМ ДАТЫ ДЛЯ СТАРЫХ ЗАПИСЕЙ
    # ========================================================

    cur.execute("""
        UPDATE users
        SET created_at=?
        WHERE created_at IS NULL
           OR created_at=''
    """, (
        now_moscow_iso(),
    ))

    cur.execute("""
        UPDATE payments
        SET created_at=?
        WHERE created_at IS NULL
           OR created_at=''
    """, (
        now_moscow_iso(),
    ))

    cur.execute("""
        UPDATE promocodes
        SET created_at=?
        WHERE created_at IS NULL
           OR created_at=''
    """, (
        now_moscow_iso(),
    ))

    cur.execute("""
        UPDATE nodes
        SET created_at=?
        WHERE created_at IS NULL
           OR created_at=''
    """, (
        now_moscow_iso(),
    ))

    cur.execute("""
        UPDATE devices
        SET last_seen=?
        WHERE last_seen IS NULL
           OR last_seen=''
    """, (
        now_moscow_iso(),
    ))

    # ========================================================
    # ГЕНЕРИРУЕМ TOKEN / UUID СТАРЫМ ПОЛЬЗОВАТЕЛЯМ
    # ========================================================

    cur.execute("""
        SELECT user_id
        FROM users
        WHERE token IS NULL
           OR token=''
    """)

    users_without_token = cur.fetchall()

    for row in users_without_token:

        token = generate_token()

        # Защита от редкого совпадения.
        while True:

            cur.execute(
                "SELECT 1 FROM users WHERE token=?",
                (token,)
            )

            if not cur.fetchone():
                break

            token = generate_token()

        cur.execute("""
            UPDATE users
            SET token=?
            WHERE user_id=?
        """, (
            token,
            row["user_id"],
        ))

    cur.execute("""
        SELECT user_id
        FROM users
        WHERE uuid IS NULL
           OR uuid=''
    """)

    users_without_uuid = cur.fetchall()

    for row in users_without_uuid:

        user_uuid = generate_uuid()

        cur.execute("""
            UPDATE users
            SET uuid=?
            WHERE user_id=?
        """, (
            user_uuid,
            row["user_id"],
        ))

    # ========================================================
    # СОЗДАЁМ ССЫЛКИ СУЩЕСТВУЮЩИМ ПОЛЬЗОВАТЕЛЯМ
    # ========================================================

    try:
        from config import PUBLIC_URL

        public_url = str(
            PUBLIC_URL
        ).rstrip("/")

        cur.execute("""
            SELECT user_id, token
            FROM users
            WHERE subscription_link IS NULL
               OR subscription_link=''
        """)

        users_without_link = cur.fetchall()

        for row in users_without_link:

            if row["token"]:

                link = (
                    f"{public_url}/sub/"
                    f"{row['token']}"
                )

                cur.execute("""
                    UPDATE users
                    SET subscription_link=?
                    WHERE user_id=?
                """, (
                    link,
                    row["user_id"],
                ))

    except Exception as e:

        print(
            "Subscription link migration error:",
            e,
        )

    db.commit()
    db.close()


# ============================================================
# USER
# ============================================================

def generate_token(length=40):

    chars = (
        string.ascii_letters
        + string.digits
    )

    return "".join(
        secrets.choice(chars)
        for _ in range(length)
    )


def generate_uuid():

    return str(
        uuid.uuid4()
    )


def create_user(
    user_id,
    username="",
    first_name="",
):

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
            SET
                username=?,
                first_name=?
            WHERE user_id=?
        """, (
            username or "",
            first_name or "",
            user_id,
        ))

        db.commit()

        cur.execute(
            "SELECT * FROM users WHERE user_id=?",
            (user_id,)
        )

        user = cur.fetchone()

        db.close()

        return dict(user)

    # --------------------------------------------------------
    # НОВЫЙ ПОЛЬЗОВАТЕЛЬ
    # --------------------------------------------------------

    token = generate_token()
    user_uuid = generate_uuid()

    # Получаем PUBLIC_URL.
    try:

        from config import PUBLIC_URL

        public_url = str(
            PUBLIC_URL
        ).rstrip("/")

    except Exception:

        public_url = ""

    subscription_link = ""

    if public_url:

        subscription_link = (
            f"{public_url}/sub/{token}"
        )

    cur.execute("""
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
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """, (
        user_id,
        username or "",
        first_name or "",
        token,
        user_uuid,
        "none",
        "",
        subscription_link,
        2,
        0,
        0,
        1,
        now_moscow_iso(),
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

    return (
        dict(row)
        if row
        else None
    )


def get_user_by_token(token):

    db = connect()
    cur = db.cursor()

    cur.execute(
        "SELECT * FROM users WHERE token=?",
        (token,)
    )

    row = cur.fetchone()

    db.close()

    return (
        dict(row)
        if row
        else None
    )


def get_all_users():

    db = connect()
    cur = db.cursor()

    cur.execute("""
        SELECT *
        FROM users
        ORDER BY created_at DESC
    """)

    rows = cur.fetchall()

    db.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# SUBSCRIPTION
# ============================================================

def extend_subscription(
    user_id,
    days,
    tariff=None,
):

    db = connect()
    cur = db.cursor()

    cur.execute(
        """
        SELECT subscription_until
        FROM users
        WHERE user_id=?
        """,
        (user_id,)
    )

    row = cur.fetchone()

    now = now_moscow()

    current = None

    if row and row["subscription_until"]:

        current = parse_datetime(
            row["subscription_until"]
        )

    if not current or current < now:

        current = now

    new_date = (
        current
        + timedelta(days=days)
    )

    new_date = new_date.astimezone(
        MOSCOW_TZ
    )

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
        user_id,
    ))

    db.commit()
    db.close()

    return new_date


def set_device_limit(
    user_id,
    limit,
):

    db = connect()

    db.execute(
        """
        UPDATE users
        SET device_limit=?
        WHERE user_id=?
        """,
        (
            int(limit),
            user_id,
        )
    )

    db.commit()
    db.close()


def block_user(
    user_id,
    blocked=True,
):

    db = connect()

    db.execute(
        """
        UPDATE users
        SET blocked=?
        WHERE user_id=?
        """,
        (
            1 if blocked else 0,
            user_id,
        )
    )

    db.commit()
    db.close()


def expire_old_subscriptions():

    db = connect()

    now = now_moscow()

    cur = db.cursor()

    cur.execute("""
        SELECT user_id, subscription_until
        FROM users
        WHERE subscription_until != ''
          AND subscription != 'expired'
    """)

    rows = cur.fetchall()

    expired_ids = []

    for row in rows:

        expire_dt = parse_datetime(
            row["subscription_until"]
        )

        if (
            expire_dt
            and expire_dt <= now
        ):

            expired_ids.append(
                row["user_id"]
            )

    if expired_ids:

        cur.executemany(
            """
            UPDATE users
            SET subscription='expired'
            WHERE user_id=?
            """,
            [
                (user_id,)
                for user_id in expired_ids
            ]
        )

    db.commit()
    db.close()

    return len(expired_ids)


# ============================================================
# TRIAL
# ============================================================

def use_trial(user_id):

    db = connect()

    cur = db.cursor()

    cur.execute(
        """
        SELECT trial_used
        FROM users
        WHERE user_id=?
        """,
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
    """, (
        user_id,
    ))

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
    days,
):

    db = connect()

    cur = db.cursor()

    cur.execute("""
        INSERT INTO payments (
            user_id,
            tariff,
            stars,
            days,
            telegram_charge_id,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        tariff,
        stars,
        days,
        "",
        "pending",
        now_moscow_iso(),
    ))

    payment_id = cur.lastrowid

    db.commit()
    db.close()

    return payment_id


def complete_payment(
    payment_id,
    telegram_charge_id,
):

    db = connect()

    cur = db.cursor()

    # --------------------------------------------------------
    # ВАЖНО:
    # Не даём один платёж провести повторно.
    # --------------------------------------------------------

    cur.execute("""
        SELECT *
        FROM payments
        WHERE id=?
    """, (
        payment_id,
    ))

    existing = cur.fetchone()

    if not existing:

        db.close()

        return None

    if existing["status"] == "paid":

        db.close()

        return None

    # --------------------------------------------------------
    # ОПЛАЧИВАЕМ
    # --------------------------------------------------------

    cur.execute("""
        UPDATE payments
        SET
            status='paid',
            telegram_charge_id=?
        WHERE id=?
          AND status='pending'
    """, (
        telegram_charge_id,
        payment_id,
    ))

    db.commit()

    # --------------------------------------------------------
    # ПОЛУЧАЕМ ОБНОВЛЁННЫЙ ПЛАТЁЖ
    # --------------------------------------------------------

    cur.execute(
        """
        SELECT *
        FROM payments
        WHERE id=?
        """,
        (payment_id,)
    )

    row = cur.fetchone()

    db.close()

    return (
        dict(row)
        if row
        else None
    )


# ============================================================
# PROMOCODES
# ============================================================

def create_promo(
    code,
    days,
    max_uses=1,
):

    db = connect()

    try:

        db.execute("""
            INSERT INTO promocodes (
                code,
                days,
                max_uses,
                uses,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            code.strip().upper(),
            int(days),
            int(max_uses),
            0,
            now_moscow_iso(),
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

    code = (
        code
        .strip()
        .upper()
    )

    cur.execute(
        """
        SELECT *
        FROM promocodes
        WHERE code=?
        """,
        (code,)
    )

    promo = cur.fetchone()

    if not promo:

        db.close()

        return None

    # --------------------------------------------------------
    # ПРОВЕРЯЕМ ЛИМИТ
    # --------------------------------------------------------

    if promo["uses"] >= promo["max_uses"]:

        db.close()

        return None

    # --------------------------------------------------------
    # УВЕЛИЧИВАЕМ USES
    # --------------------------------------------------------

    cur.execute("""
        UPDATE promocodes
        SET uses=uses+1
        WHERE code=?
          AND uses < max_uses
    """, (
        code,
    ))

    if cur.rowcount == 0:

        db.close()

        return None

    db.commit()

    db.close()

    return dict(promo)


# ============================================================
# NODES
# ============================================================

def add_node(
    name,
    vless_link,
):

    db = connect()

    cur = db.cursor()

    cur.execute("""
        INSERT INTO nodes (
            name,
            vless_link,
            enabled,
            created_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        name,
        vless_link,
        1,
        now_moscow_iso(),
    ))

    db.commit()

    node_id = cur.lastrowid

    db.close()

    return node_id


def delete_node(node_id):

    db = connect()

    db.execute(
        """
        DELETE FROM nodes
        WHERE id=?
        """,
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

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# DEVICES
# ============================================================

def add_device(
    user_id,
    device_id,
    device_name="",
):

    db = connect()

    cur = db.cursor()

    # --------------------------------------------------------
    # ИЩЕМ УЖЕ СУЩЕСТВУЮЩЕЕ УСТРОЙСТВО
    # --------------------------------------------------------

    cur.execute("""
        SELECT *
        FROM devices
        WHERE user_id=?
          AND device_id=?
    """, (
        user_id,
        device_id,
    ))

    existing = cur.fetchone()

    if existing:

        cur.execute("""
            UPDATE devices
            SET
                device_name=?,
                last_seen=?
            WHERE user_id=?
              AND device_id=?
        """, (
            device_name or "",
            now_moscow_iso(),
            user_id,
            device_id,
        ))

        db.commit()
        db.close()

        return True

    # --------------------------------------------------------
    # ПОЛУЧАЕМ ЛИМИТ
    # --------------------------------------------------------

    cur.execute(
        """
        SELECT device_limit
        FROM users
        WHERE user_id=?
        """,
        (user_id,)
    )

    user = cur.fetchone()

    limit = (
        user["device_limit"]
        if user
        else 2
    )

    # --------------------------------------------------------
    # СЧИТАЕМ УСТРОЙСТВА
    # --------------------------------------------------------

    cur.execute("""
        SELECT COUNT(*) AS count
        FROM devices
        WHERE user_id=?
    """, (
        user_id,
    ))

    count = cur.fetchone()["count"]

    if count >= limit:

        db.close()

        return False

    # --------------------------------------------------------
    # ДОБАВЛЯЕМ
    # --------------------------------------------------------

    cur.execute("""
        INSERT INTO devices (
            user_id,
            device_id,
            device_name,
            last_seen
        )
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        device_id,
        device_name or "",
        now_moscow_iso(),
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
    """, (
        user_id,
    ))

    rows = cur.fetchall()

    db.close()

    return [
        dict(row)
        for row in rows
    ]


def delete_device(
    user_id,
    device_id,
):

    db = connect()

    db.execute("""
        DELETE FROM devices
        WHERE user_id=?
          AND device_id=?
    """, (
        user_id,
        device_id,
    ))

    db.commit()
    db.close()


# ============================================================
# STATISTICS
# ============================================================

def get_stats():

    db = connect()
    cur = db.cursor()

    now = now_moscow()

    # --------------------------------------------------------
    # ВСЕ ПОЛЬЗОВАТЕЛИ
    # --------------------------------------------------------

    cur.execute("""
        SELECT COUNT(*) AS c
        FROM users
    """)

    users = cur.fetchone()["c"]

    # --------------------------------------------------------
    # АКТИВНЫЕ
    # --------------------------------------------------------

    cur.execute("""
        SELECT
            user_id,
            subscription_until
        FROM users
        WHERE subscription_until != ''
    """)

    active = 0

    for row in cur.fetchall():

        expire_dt = parse_datetime(
            row["subscription_until"]
        )

        if (
            expire_dt
            and expire_dt > now
        ):
            active += 1

    # --------------------------------------------------------
    # ЗАБЛОКИРОВАННЫЕ
    # --------------------------------------------------------

    cur.execute("""
        SELECT COUNT(*) AS c
        FROM users
        WHERE blocked=1
    """)

    blocked = cur.fetchone()["c"]

    # --------------------------------------------------------
    # ПЛАТЕЖИ
    # --------------------------------------------------------

    cur.execute("""
        SELECT COUNT(*) AS c
        FROM payments
        WHERE status='paid'
    """)

    payments = cur.fetchone()["c"]

    # --------------------------------------------------------
    # STARS
    # --------------------------------------------------------

    cur.execute("""
        SELECT COALESCE(SUM(stars), 0) AS s
        FROM payments
        WHERE status='paid'
    """)

    stars = cur.fetchone()["s"]

    # --------------------------------------------------------
    # УСТРОЙСТВА
    # --------------------------------------------------------

    cur.execute("""
        SELECT COUNT(*) AS c
        FROM devices
    """)

    devices = cur.fetchone()["c"]

    # --------------------------------------------------------
    # ПРОМОКОДЫ
    # --------------------------------------------------------

    cur.execute("""
        SELECT COUNT(*) AS c
        FROM promocodes
    """)

    promocodes = cur.fetchone()["c"]

    db.close()

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
# CURRENT MOSCOW TIME
# ============================================================

def get_moscow_time():
    return now_moscow()


# ============================================================
# INIT DATABASE
# ============================================================

init_db()