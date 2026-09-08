# database.py

import os
import secrets
import sqlite3

from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# CONFIG
# ============================================================

DB_PATH = os.getenv(
    "DB_PATH",
    "./data/users.db",
).strip()

try:
    DEFAULT_DEVICE_LIMIT = int(
        os.getenv(
            "DEFAULT_DEVICE_LIMIT",
            "3",
        )
    )
except (TypeError, ValueError):
    DEFAULT_DEVICE_LIMIT = 3

if DEFAULT_DEVICE_LIMIT < 1:
    DEFAULT_DEVICE_LIMIT = 1


UTC = timezone.utc


# ============================================================
# TIME
# ============================================================

def now_utc() -> datetime:
    return datetime.now(UTC)


def now_iso() -> str:
    return now_utc().isoformat()


def parse_datetime(value) -> Optional[datetime]:

    if not value:
        return None

    if isinstance(value, datetime):

        if value.tzinfo is None:
            return value.replace(
                tzinfo=UTC
            )

        return value.astimezone(UTC)

    value = str(value).strip()

    if not value:
        return None

    try:

        result = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

        if result.tzinfo is None:
            result = result.replace(
                tzinfo=UTC
            )

        return result.astimezone(UTC)

    except (ValueError, TypeError):

        return None


def format_date(value) -> str:

    dt = parse_datetime(value)

    if not dt:
        return "—"

    return dt.astimezone(UTC).strftime(
        "%d.%m.%Y %H:%M"
    )


# ============================================================
# DATABASE
# ============================================================

def ensure_db_directory():

    directory = os.path.dirname(
        os.path.abspath(DB_PATH)
    )

    os.makedirs(
        directory,
        exist_ok=True,
    )


def get_db():

    ensure_db_directory()

    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False,
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA journal_mode=WAL"
    )

    conn.execute(
        "PRAGMA busy_timeout=30000"
    )

    conn.execute(
        "PRAGMA foreign_keys=ON"
    )

    return conn


def row_to_dict(row):

    if row is None:
        return None

    return dict(row)


# ============================================================
# INIT
# ============================================================

def init_db():

    conn = get_db()

    try:

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',

                token TEXT UNIQUE DEFAULT '',

                subscription TEXT DEFAULT 'none',
                subscription_until TEXT DEFAULT '',
                subscription_link TEXT DEFAULT '',
                subscription_content TEXT DEFAULT '',

                trial_used INTEGER DEFAULT 0,
                blocked INTEGER DEFAULT 0,

                notify INTEGER DEFAULT 1,
                accepted_terms INTEGER DEFAULT 0,

                device_limit INTEGER DEFAULT 3,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );


            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                tariff TEXT DEFAULT '',
                days INTEGER DEFAULT 0,
                stars INTEGER DEFAULT 0,

                telegram_payment_charge_id TEXT DEFAULT '',

                status TEXT DEFAULT 'pending',

                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT DEFAULT ''
            );


            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,

                days INTEGER NOT NULL,

                uses_left INTEGER DEFAULT -1,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );


            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                name TEXT DEFAULT '',
                vless_link TEXT DEFAULT '',

                active INTEGER DEFAULT 1,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );


            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                device_id TEXT NOT NULL,
                device_name TEXT DEFAULT '',

                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(user_id, device_id),

                FOREIGN KEY(user_id)
                    REFERENCES users(user_id)
                    ON DELETE CASCADE
            );


            CREATE INDEX IF NOT EXISTS
                idx_users_token
            ON users(token);


            CREATE INDEX IF NOT EXISTS
                idx_users_subscription_until
            ON users(subscription_until);


            CREATE INDEX IF NOT EXISTS
                idx_devices_user
            ON devices(user_id);
            """
        )

        conn.commit()

        migrate_db(conn)

    finally:

        conn.close()


# ============================================================
# MIGRATIONS
# ============================================================

def get_columns(
    conn,
    table: str,
):

    rows = conn.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    return {
        row["name"]
        for row in rows
    }


def add_column_if_missing(
    conn,
    table: str,
    column: str,
    definition: str,
):

    columns = get_columns(
        conn,
        table,
    )

    if column not in columns:

        conn.execute(
            f"""
            ALTER TABLE {table}
            ADD COLUMN {column} {definition}
            """
        )


def migrate_db(conn):

    add_column_if_missing(
        conn,
        "users",
        "token",
        "TEXT DEFAULT ''",
    )

    add_column_if_missing(
        conn,
        "users",
        "subscription_content",
        "TEXT DEFAULT ''",
    )

    add_column_if_missing(
        conn,
        "users",
        "blocked",
        "INTEGER DEFAULT 0",
    )

    add_column_if_missing(
        conn,
        "users",
        "notify",
        "INTEGER DEFAULT 1",
    )

    add_column_if_missing(
        conn,
        "users",
        "accepted_terms",
        "INTEGER DEFAULT 0",
    )

    add_column_if_missing(
        conn,
        "users",
        "device_limit",
        f"INTEGER DEFAULT {DEFAULT_DEVICE_LIMIT}",
    )

    add_column_if_missing(
        conn,
        "users",
        "subscription_link",
        "TEXT DEFAULT ''",
    )

    add_column_if_missing(
        conn,
        "users",
        "subscription",
        "TEXT DEFAULT 'none'",
    )

    # Старым пользователям выдаём токены.
    rows = conn.execute(
        """
        SELECT user_id
        FROM users
        WHERE token IS NULL
           OR token = ''
        """
    ).fetchall()

    for row in rows:

        token = secrets.token_urlsafe(
            32
        )

        conn.execute(
            """
            UPDATE users
            SET token = ?
            WHERE user_id = ?
            """,
            (
                token,
                row["user_id"],
            ),
        )

    # Исправляем пустые device_limit.
    conn.execute(
        """
        UPDATE users
        SET device_limit = ?
        WHERE device_limit IS NULL
           OR device_limit <= 0
        """,
        (
            DEFAULT_DEVICE_LIMIT,
        ),
    )

    conn.commit()


# ============================================================
# USERS
# ============================================================

def create_user(
    user_id: int,
    username: str = "",
    first_name: str = "",
):

    conn = get_db()

    try:

        existing = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (
                user_id,
            ),
        ).fetchone()

        if existing:

            conn.execute(
                """
                UPDATE users
                SET username = ?,
                    first_name = ?
                WHERE user_id = ?
                """,
                (
                    username or "",
                    first_name or "",
                    user_id,
                ),
            )

            conn.commit()

            return row_to_dict(
                conn.execute(
                    """
                    SELECT *
                    FROM users
                    WHERE user_id = ?
                    """,
                    (user_id,),
                ).fetchone()
            )

        token = secrets.token_urlsafe(
            32
        )

        conn.execute(
            """
            INSERT INTO users (
                user_id,
                username,
                first_name,
                token,
                subscription,
                subscription_until,
                subscription_link,
                subscription_content,
                trial_used,
                blocked,
                notify,
                accepted_terms,
                device_limit
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username or "",
                first_name or "",
                token,
                "none",
                "",
                "",
                "",
                0,
                0,
                1,
                0,
                DEFAULT_DEVICE_LIMIT,
            ),
        )

        conn.commit()

        return row_to_dict(
            conn.execute(
                """
                SELECT *
                FROM users
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        )

    finally:

        conn.close()


def get_user(
    user_id: int,
):

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (
                user_id,
            ),
        ).fetchone()

        return row_to_dict(row)

    finally:

        conn.close()


def get_user_by_token(
    token: str,
):

    if not token:
        return None

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE token = ?
            """,
            (
                token,
            ),
        ).fetchone()

        return row_to_dict(row)

    finally:

        conn.close()


def get_all_users():

    conn = get_db()

    try:

        rows = conn.execute(
            """
            SELECT *
            FROM users
            ORDER BY created_at DESC
            """
        ).fetchall()

        return [
            row_to_dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# TOKEN / SUBSCRIPTION LINK
# ============================================================

def build_subscription_link(
    user_id: int,
):

    user = get_user(user_id)

    if not user:
        return ""

    token = user.get(
        "token",
        "",
    )

    if not token:
        return ""

    from config import PUBLIC_URL

    return (
        f"{PUBLIC_URL}/sub/{token}"
    )


def save_subscription_link(
    user_id: int,
    link: str,
):

    conn = get_db()

    try:

        conn.execute(
            """
            UPDATE users
            SET subscription_link = ?
            WHERE user_id = ?
            """,
            (
                link or "",
                user_id,
            ),
        )

        conn.commit()

    finally:

        conn.close()


def get_subscription_link(
    user_id: int,
):

    user = get_user(user_id)

    if not user:
        return ""

    link = (
        user.get(
            "subscription_link",
            "",
        )
        or ""
    )

    if link:
        return link

    link = build_subscription_link(
        user_id
    )

    if link:
        save_subscription_link(
            user_id,
            link,
        )

    return link


# ============================================================
# SUBSCRIPTION CONTENT
# ============================================================

def save_subscription_content(
    user_id: int,
    content: str,
):

    conn = get_db()

    try:

        conn.execute(
            """
            UPDATE users
            SET subscription_content = ?
            WHERE user_id = ?
            """,
            (
                content or "",
                user_id,
            ),
        )

        conn.commit()

    finally:

        conn.close()


def get_subscription_content(
    user_id: int,
):

    user = get_user(user_id)

    if not user:
        return ""

    return (
        user.get(
            "subscription_content",
            "",
        )
        or ""
    )


# ============================================================
# SUBSCRIPTION
# ============================================================

def extend_subscription(
    user_id: int,
    days: int,
    subscription: str = "paid",
):

    days = int(days)

    if days <= 0:
        return False

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT subscription_until
            FROM users
            WHERE user_id = ?
            """,
            (
                user_id,
            ),
        ).fetchone()

        if not row:
            return False

        current = parse_datetime(
            row["subscription_until"]
        )

        now = now_utc()

        if current and current > now:
            start = current
        else:
            start = now

        expire = (
            start
            + timedelta(days=days)
        )

        conn.execute(
            """
            UPDATE users
            SET subscription = ?,
                subscription_until = ?,
                blocked = 0
            WHERE user_id = ?
            """,
            (
                subscription or "paid",
                expire.isoformat(),
                user_id,
            ),
        )

        conn.commit()

        return True

    finally:

        conn.close()


def revoke_subscription(
    user_id: int,
):

    conn = get_db()

    try:

        conn.execute(
            """
            UPDATE users
            SET subscription = 'none',
                subscription_until = ''
            WHERE user_id = ?
            """,
            (
                user_id,
            ),
        )

        conn.commit()

        return True

    finally:

        conn.close()


def is_subscription_active(
    user_id: int,
):

    user = get_user(user_id)

    if not user:
        return False

    if int(
        user.get(
            "blocked",
            0,
        )
        or 0
    ):
        return False

    expire = parse_datetime(
        user.get(
            "subscription_until",
            "",
        )
    )

    if not expire:
        return False

    return expire > now_utc()


def expire_old_subscriptions():

    conn = get_db()

    try:

        now = now_utc().isoformat()

        cursor = conn.execute(
            """
            UPDATE users
            SET subscription = 'none'
            WHERE subscription_until IS NOT NULL
              AND subscription_until != ''
              AND subscription_until <= ?
              AND subscription != 'none'
            """,
            (
                now,
            ),
        )

        conn.commit()

        return cursor.rowcount

    finally:

        conn.close()


# ============================================================
# TRIAL
# ============================================================

def use_trial(
    user_id: int,
    days: int = 3,
):

    days = int(days)

    if days <= 0:
        return False

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (
                user_id,
            ),
        ).fetchone()

        if not row:
            return False

        if int(
            row["trial_used"] or 0
        ):
            return False

        current = parse_datetime(
            row["subscription_until"]
        )

        now = now_utc()

        # Не позволяем пробнику заменить
        # уже действующую платную подписку.
        if current and current > now:
            return False

        expire = (
            now
            + timedelta(days=days)
        )

        conn.execute(
            """
            UPDATE users
            SET trial_used = 1,
                subscription = 'trial',
                subscription_until = ?,
                blocked = 0
            WHERE user_id = ?
            """,
            (
                expire.isoformat(),
                user_id,
            ),
        )

        conn.commit()

        return True

    finally:

        conn.close()


# ============================================================
# BLOCK
# ============================================================

def set_blocked(
    user_id: int,
    blocked: bool,
):

    conn = get_db()

    try:

        conn.execute(
            """
            UPDATE users
            SET blocked = ?
            WHERE user_id = ?
            """,
            (
                1 if blocked else 0,
                user_id,
            ),
        )

        conn.commit()

        return True

    finally:

        conn.close()


def is_blocked(
    user_id: int,
):

    user = get_user(user_id)

    if not user:
        return False

    return bool(
        int(
            user.get(
                "blocked",
                0,
            )
            or 0
        )
    )


# ============================================================
# NOTIFICATIONS / TERMS
# ============================================================

def set_notify(
    user_id: int,
    enabled: bool,
):

    conn = get_db()

    try:

        conn.execute(
            """
            UPDATE users
            SET notify = ?
            WHERE user_id = ?
            """,
            (
                1 if enabled else 0,
                user_id,
            ),
        )

        conn.commit()

    finally:

        conn.close()


def set_accepted_terms(
    user_id: int,
    accepted: bool = True,
):

    conn = get_db()

    try:

        conn.execute(
            """
            UPDATE users
            SET accepted_terms = ?
            WHERE user_id = ?
            """,
            (
                1 if accepted else 0,
                user_id,
            ),
        )

        conn.commit()

    finally:

        conn.close()


# ============================================================
# PAYMENTS
# ============================================================

def create_payment(
    user_id: int,
    tariff: str,
    days: int,
    stars: int,
):

    conn = get_db()

    try:

        cursor = conn.execute(
            """
            INSERT INTO payments (
                user_id,
                tariff,
                days,
                stars,
                status
            )
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (
                user_id,
                tariff or "",
                int(days),
                int(stars),
            ),
        )

        conn.commit()

        return cursor.lastrowid

    finally:

        conn.close()


def complete_payment(
    payment_id: int,
    charge_id: str = "",
):

    conn = get_db()

    try:

        cursor = conn.execute(
            """
            UPDATE payments
            SET status = 'completed',
                telegram_payment_charge_id = ?,
                completed_at = ?
            WHERE id = ?
              AND status != 'completed'
            """,
            (
                charge_id or "",
                now_iso(),
                payment_id,
            ),
        )

        conn.commit()

        return cursor.rowcount > 0

    finally:

        conn.close()


def get_payment(
    payment_id: int,
):

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT *
            FROM payments
            WHERE id = ?
            """,
            (
                payment_id,
            ),
        ).fetchone()

        return row_to_dict(row)

    finally:

        conn.close()


def get_all_payments():

    conn = get_db()

    try:

        rows = conn.execute(
            """
            SELECT *
            FROM payments
            ORDER BY id DESC
            """
        ).fetchall()

        return [
            row_to_dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# PROMOCODES
# ============================================================

def create_promo(
    code: str,
    days: int,
    uses_left: int = -1,
):

    code = (
        str(code or "")
        .strip()
        .upper()
    )

    days = int(days)

    if not code or days <= 0:
        return False

    conn = get_db()

    try:

        try:

            conn.execute(
                """
                INSERT INTO promocodes (
                    code,
                    days,
                    uses_left
                )
                VALUES (?, ?, ?)
                """,
                (
                    code,
                    days,
                    uses_left,
                ),
            )

            conn.commit()

            return True

        except sqlite3.IntegrityError:

            return False

    finally:

        conn.close()


def get_promo(
    code: str,
):

    code = (
        str(code or "")
        .strip()
        .upper()
    )

    if not code:
        return None

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT *
            FROM promocodes
            WHERE code = ?
            """,
            (
                code,
            ),
        ).fetchone()

        return row_to_dict(row)

    finally:

        conn.close()


def use_promo(
    user_id: int,
    code: str,
):

    code = (
        str(code or "")
        .strip()
        .upper()
    )

    if not code:
        return False

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT *
            FROM promocodes
            WHERE code = ?
            """,
            (
                code,
            ),
        ).fetchone()

        if not row:
            return False

        uses_left = int(
            row["uses_left"]
            if row["uses_left"] is not None
            else -1
        )

        if uses_left == 0:
            return False

        # Если лимит использований задан.
        if uses_left > 0:

            conn.execute(
                """
                UPDATE promocodes
                SET uses_left = uses_left - 1
                WHERE code = ?
                """,
                (
                    code,
                ),
            )

        conn.commit()

        # Выдаём дни отдельно,
        # после успешного списания.
        days = int(
            row["days"]
        )

        conn.close()

        return extend_subscription(
            user_id,
            days,
            f"promo:{code}",
        )

    except Exception:

        conn.rollback()
        raise

    finally:

        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# NODES
# ============================================================

def get_nodes(
    active_only: bool = False,
):

    conn = get_db()

    try:

        if active_only:

            rows = conn.execute(
                """
                SELECT *
                FROM nodes
                WHERE active = 1
                ORDER BY id ASC
                """
            ).fetchall()

        else:

            rows = conn.execute(
                """
                SELECT *
                FROM nodes
                ORDER BY id ASC
                """
            ).fetchall()

        return [
            row_to_dict(row)
            for row in rows
        ]

    finally:

        conn.close()


def add_node(
    name: str,
    vless_link: str,
    active: bool = True,
):

    conn = get_db()

    try:

        cursor = conn.execute(
            """
            INSERT INTO nodes (
                name,
                vless_link,
                active
            )
            VALUES (?, ?, ?)
            """,
            (
                name or "",
                vless_link or "",
                1 if active else 0,
            ),
        )

        conn.commit()

        return cursor.lastrowid

    finally:

        conn.close()


def update_node(
    node_id: int,
    name: str,
    vless_link: str,
    active: bool = True,
):

    conn = get_db()

    try:

        cursor = conn.execute(
            """
            UPDATE nodes
            SET name = ?,
                vless_link = ?,
                active = ?
            WHERE id = ?
            """,
            (
                name or "",
                vless_link or "",
                1 if active else 0,
                node_id,
            ),
        )

        conn.commit()

        return cursor.rowcount > 0

    finally:

        conn.close()


def delete_node(
    node_id: int,
):

    conn = get_db()

    try:

        cursor = conn.execute(
            """
            DELETE FROM nodes
            WHERE id = ?
            """,
            (
                node_id,
            ),
        )

        conn.commit()

        return cursor.rowcount > 0

    finally:

        conn.close()


# ============================================================
# DEVICES
# ============================================================

def get_device_limit(
    user_id: int,
):

    user = get_user(user_id)

    if not user:
        return DEFAULT_DEVICE_LIMIT

    try:

        limit = int(
            user.get(
                "device_limit",
                DEFAULT_DEVICE_LIMIT,
            )
            or DEFAULT_DEVICE_LIMIT
        )

    except (TypeError, ValueError):

        limit = DEFAULT_DEVICE_LIMIT

    return max(
        1,
        limit,
    )


def set_device_limit(
    user_id: int,
    limit: int,
):

    limit = int(limit)

    if limit < 1:
        return False

    conn = get_db()

    try:

        cursor = conn.execute(
            """
            UPDATE users
            SET device_limit = ?
            WHERE user_id = ?
            """,
            (
                limit,
                user_id,
            ),
        )

        conn.commit()

        return cursor.rowcount > 0

    finally:

        conn.close()


def get_devices(
    user_id: int,
):

    conn = get_db()

    try:

        rows = conn.execute(
            """
            SELECT *
            FROM devices
            WHERE user_id = ?
            ORDER BY last_seen DESC
            """,
            (
                user_id,
            ),
        ).fetchall()

        return [
            row_to_dict(row)
            for row in rows
        ]

    finally:

        conn.close()


def count_devices(
    user_id: int,
):

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM devices
            WHERE user_id = ?
            """,
            (
                user_id,
            ),
        ).fetchone()

        return int(
            row["count"]
        )

    finally:

        conn.close()


def add_device(
    user_id: int,
    device_id: str,
    device_name: str = "",
):

    device_id = (
        str(device_id or "")
        .strip()
    )

    if not device_id:
        return False

    conn = get_db()

    try:

        existing = conn.execute(
            """
            SELECT id
            FROM devices
            WHERE user_id = ?
              AND device_id = ?
            """,
            (
                user_id,
                device_id,
            ),
        ).fetchone()

        now = now_iso()

        if existing:

            conn.execute(
                """
                UPDATE devices
                SET device_name = ?,
                    last_seen = ?
                WHERE id = ?
                """,
                (
                    device_name or "",
                    now,
                    existing["id"],
                ),
            )

            conn.commit()

            return True

        limit_row = conn.execute(
            """
            SELECT device_limit
            FROM users
            WHERE user_id = ?
            """,
            (
                user_id,
            ),
        ).fetchone()

        if not limit_row:
            return False

        try:

            limit = int(
                limit_row["device_limit"]
                or DEFAULT_DEVICE_LIMIT
            )

        except (TypeError, ValueError):

            limit = DEFAULT_DEVICE_LIMIT

        count_row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM devices
            WHERE user_id = ?
            """,
            (
                user_id,
            ),
        ).fetchone()

        count = int(
            count_row["count"]
        )

        if count >= limit:
            return False

        conn.execute(
            """
            INSERT INTO devices (
                user_id,
                device_id,
                device_name,
                created_at,
                last_seen
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                device_id,
                device_name or "",
                now,
                now,
            ),
        )

        conn.commit()

        return True

    except sqlite3.IntegrityError:

        return False

    finally:

        conn.close()


def remove_device(
    user_id: int,
    device_id: str,
):

    conn = get_db()

    try:

        cursor = conn.execute(
            """
            DELETE FROM devices
            WHERE user_id = ?
              AND device_id = ?
            """,
            (
                user_id,
                device_id,
            ),
        )

        conn.commit()

        return cursor.rowcount > 0

    finally:

        conn.close()


def clear_devices(
    user_id: int,
):

    conn = get_db()

    try:

        cursor = conn.execute(
            """
            DELETE FROM devices
            WHERE user_id = ?
            """,
            (
                user_id,
            ),
        )

        conn.commit()

        return cursor.rowcount

    finally:

        conn.close()


# ============================================================
# STATISTICS
# ============================================================

def get_stats():

    conn = get_db()

    try:

        users = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM users
            """
        ).fetchone()["count"]

        now = now_utc().isoformat()

        active = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM users
            WHERE blocked = 0
              AND subscription_until IS NOT NULL
              AND subscription_until != ''
              AND subscription_until > ?
            """,
            (
                now,
            ),
        ).fetchone()["count"]

        payments = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM payments
            WHERE status = 'completed'
            """
        ).fetchone()["count"]

        revenue = conn.execute(
            """
            SELECT COALESCE(
                SUM(stars),
                0
            ) AS total
            FROM payments
            WHERE status = 'completed'
            """
        ).fetchone()["total"]

        nodes = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM nodes
            WHERE active = 1
            """
        ).fetchone()["count"]

        devices = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM devices
            """
        ).fetchone()["count"]

        return {
            "users": int(users or 0),
            "active": int(active or 0),
            "payments": int(payments or 0),
            "revenue": int(revenue or 0),
            "nodes": int(nodes or 0),
            "devices": int(devices or 0),
        }

    finally:

        conn.close()


# ============================================================
# AUTO INIT
# ============================================================

init_db()