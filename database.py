import os
import sqlite3
import secrets
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# CONFIG
# ============================================================

DB_PATH = os.getenv(
    "DB_PATH",
    "./data/users.db",
)

try:
    DEFAULT_DEVICE_LIMIT = int(
        os.getenv(
            "DEFAULT_DEVICE_LIMIT",
            "3",
        )
    )
except ValueError:
    DEFAULT_DEVICE_LIMIT = 3


UTC = timezone.utc


# ============================================================
# TIME
# ============================================================

def now_utc():
    return datetime.now(UTC)


def now_iso():
    return now_utc().isoformat()


def parse_datetime(value):
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(str(value))

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

        return dt.astimezone(UTC)

    except Exception:
        return None


def format_date(value):
    dt = parse_datetime(value)

    if not dt:
        return "—"

    return dt.astimezone(UTC).strftime(
        "%d.%m.%Y %H:%M"
    )


# ============================================================
# DATABASE
# ============================================================

def connect():
    directory = os.path.dirname(
        os.path.abspath(DB_PATH)
    )

    if directory:
        os.makedirs(
            directory,
            exist_ok=True,
        )

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


def _columns(conn, table):
    rows = conn.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    return {
        row["name"]
        for row in rows
    }


def _add_column_if_missing(
    conn,
    table,
    column,
    definition,
):
    columns = _columns(
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


# ============================================================
# INIT
# ============================================================

def init_db():

    conn = connect()

    try:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',

                token TEXT UNIQUE,

                subscription TEXT DEFAULT 'none',
                subscription_until TEXT DEFAULT '',

                subscription_link TEXT DEFAULT '',
                subscription_content TEXT DEFAULT '',

                trial_used INTEGER DEFAULT 0,

                blocked INTEGER DEFAULT 0,
                notify INTEGER DEFAULT 1,
                accepted_terms INTEGER DEFAULT 0,

                device_limit INTEGER DEFAULT 3,

                created_at TEXT DEFAULT ''
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                tariff TEXT DEFAULT '',
                days INTEGER DEFAULT 0,
                stars INTEGER DEFAULT 0,

                telegram_payment_charge_id TEXT DEFAULT '',

                status TEXT DEFAULT 'pending',

                created_at TEXT DEFAULT '',
                completed_at TEXT DEFAULT ''
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                days INTEGER DEFAULT 0,
                uses_left INTEGER DEFAULT 0,
                created_at TEXT DEFAULT ''
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT DEFAULT '',
                vless_link TEXT DEFAULT '',
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT ''
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                device_id TEXT NOT NULL,
                device_name TEXT DEFAULT '',

                created_at TEXT DEFAULT '',
                last_seen TEXT DEFAULT '',

                UNIQUE(user_id, device_id),

                FOREIGN KEY(user_id)
                    REFERENCES users(user_id)
                    ON DELETE CASCADE
            )
        """)

        # ====================================================
        # MIGRATIONS
        # ====================================================

        _add_column_if_missing(
            conn,
            "users",
            "token",
            "TEXT",
        )

        _add_column_if_missing(
            conn,
            "users",
            "subscription_content",
            "TEXT DEFAULT ''",
        )

        _add_column_if_missing(
            conn,
            "users",
            "blocked",
            "INTEGER DEFAULT 0",
        )

        _add_column_if_missing(
            conn,
            "users",
            "notify",
            "INTEGER DEFAULT 1",
        )

        _add_column_if_missing(
            conn,
            "users",
            "accepted_terms",
            "INTEGER DEFAULT 0",
        )

        _add_column_if_missing(
            conn,
            "users",
            "device_limit",
            f"INTEGER DEFAULT {DEFAULT_DEVICE_LIMIT}",
        )

        # ====================================================
        # TOKENS
        # ====================================================

        rows = conn.execute("""
            SELECT user_id
            FROM users
            WHERE token IS NULL
               OR token = ''
        """).fetchall()

        for row in rows:

            token = secrets.token_urlsafe(32)

            while conn.execute(
                """
                SELECT 1
                FROM users
                WHERE token = ?
                """,
                (token,),
            ).fetchone():

                token = secrets.token_urlsafe(32)

            conn.execute("""
                UPDATE users
                SET token = ?
                WHERE user_id = ?
            """, (
                token,
                row["user_id"],
            ))

        # ====================================================
        # DEFAULT DEVICE LIMIT
        # ====================================================

        conn.execute("""
            UPDATE users
            SET device_limit = ?
            WHERE device_limit IS NULL
               OR device_limit <= 0
        """, (
            DEFAULT_DEVICE_LIMIT,
        ))

        conn.commit()

    finally:
        conn.close()


# ============================================================
# USERS
# ============================================================

def create_user(
    user_id,
    username="",
    first_name="",
):
    conn = connect()

    try:

        user = conn.execute("""
            SELECT *
            FROM users
            WHERE user_id = ?
        """, (
            int(user_id),
        )).fetchone()

        if user:

            conn.execute("""
                UPDATE users
                SET username = ?,
                    first_name = ?
                WHERE user_id = ?
            """, (
                username or "",
                first_name or "",
                int(user_id),
            ))

        else:

            token = secrets.token_urlsafe(32)

            while conn.execute(
                """
                SELECT 1
                FROM users
                WHERE token = ?
                """,
                (token,),
            ).fetchone():

                token = secrets.token_urlsafe(32)

            conn.execute("""
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
                    device_limit,
                    created_at
                )
                VALUES (
                    ?, ?, ?, ?, 'none', '', '', '',
                    0, 0, 1, 0, ?, ?
                )
            """, (
                int(user_id),
                username or "",
                first_name or "",
                token,
                DEFAULT_DEVICE_LIMIT,
                now_iso(),
            ))

        conn.commit()

        return get_user(user_id)

    finally:
        conn.close()


def get_user(user_id):

    conn = connect()

    try:

        row = conn.execute("""
            SELECT *
            FROM users
            WHERE user_id = ?
        """, (
            int(user_id),
        )).fetchone()

        return dict(row) if row else None

    finally:
        conn.close()


def get_user_by_token(token):

    if not token:
        return None

    conn = connect()

    try:

        row = conn.execute("""
            SELECT *
            FROM users
            WHERE token = ?
        """, (
            token,
        )).fetchone()

        return dict(row) if row else None

    finally:
        conn.close()


def get_all_users():

    conn = connect()

    try:

        rows = conn.execute("""
            SELECT *
            FROM users
            ORDER BY created_at DESC
        """).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        conn.close()


# ============================================================
# SUBSCRIPTION LINKS
# ============================================================

def build_subscription_link(token):

    public_url = os.getenv(
        "PUBLIC_SITE_URL",
        "",
    ).rstrip("/")

    return f"{public_url}/sub/{token}"


def save_subscription_link(
    user_id,
    link,
):
    conn = connect()

    try:

        conn.execute("""
            UPDATE users
            SET subscription_link = ?
            WHERE user_id = ?
        """, (
            link or "",
            int(user_id),
        ))

        conn.commit()

    finally:
        conn.close()


def get_subscription_link(user_id):

    user = get_user(user_id)

    if not user:
        return ""

    return (
        user.get(
            "subscription_link",
            "",
        )
        or ""
    )


def save_subscription_content(
    user_id,
    content,
):
    conn = connect()

    try:

        conn.execute("""
            UPDATE users
            SET subscription_content = ?
            WHERE user_id = ?
        """, (
            content or "",
            int(user_id),
        ))

        conn.commit()

    finally:
        conn.close()


def get_subscription_content(user_id):

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
# SUBSCRIPTIONS
# ============================================================

def extend_subscription(
    user_id,
    days,
    tariff="",
):
    days = int(days)

    conn = connect()

    try:

        row = conn.execute("""
            SELECT subscription_until
            FROM users
            WHERE user_id = ?
        """, (
            int(user_id),
        )).fetchone()

        if not row:
            return None

        current = parse_datetime(
            row["subscription_until"]
        )

        now = now_utc()

        if current and current > now:
            base = current
        else:
            base = now

        new_expire = (
            base +
            timedelta(days=days)
        )

        conn.execute("""
            UPDATE users
            SET subscription = ?,
                subscription_until = ?
            WHERE user_id = ?
        """, (
            tariff or "active",
            new_expire.isoformat(),
            int(user_id),
        ))

        conn.commit()

        return get_user(user_id)

    finally:
        conn.close()


def revoke_subscription(user_id):

    conn = connect()

    try:

        conn.execute("""
            UPDATE users
            SET subscription = 'none',
                subscription_until = ''
            WHERE user_id = ?
        """, (
            int(user_id),
        ))

        conn.commit()

    finally:
        conn.close()


def expire_old_subscriptions():

    conn = connect()

    try:

        rows = conn.execute("""
            SELECT user_id,
                   subscription_until
            FROM users
            WHERE subscription_until != ''
        """).fetchall()

        expired = 0
        now = now_utc()

        for row in rows:

            expire = parse_datetime(
                row["subscription_until"]
            )

            if expire and expire <= now:

                conn.execute("""
                    UPDATE users
                    SET subscription = 'expired'
                    WHERE user_id = ?
                """, (
                    row["user_id"],
                ))

                expired += 1

        conn.commit()

        return expired

    finally:
        conn.close()


# ============================================================
# TRIAL
# ============================================================

def use_trial(
    user_id,
    days,
):
    conn = connect()

    try:

        row = conn.execute("""
            SELECT trial_used
            FROM users
            WHERE user_id = ?
        """, (
            int(user_id),
        )).fetchone()

        if not row:
            return None

        if int(row["trial_used"] or 0):
            return None

        expire = (
            now_utc() +
            timedelta(days=int(days))
        )

        conn.execute("""
            UPDATE users
            SET trial_used = 1,
                subscription = 'trial',
                subscription_until = ?
            WHERE user_id = ?
        """, (
            expire.isoformat(),
            int(user_id),
        ))

        conn.commit()

        return get_user(user_id)

    finally:
        conn.close()


# ============================================================
# BLOCK
# ============================================================

def set_blocked(
    user_id,
    blocked,
):
    conn = connect()

    try:

        cursor = conn.execute("""
            UPDATE users
            SET blocked = ?
            WHERE user_id = ?
        """, (
            1 if blocked else 0,
            int(user_id),
        ))

        conn.commit()

        return cursor.rowcount > 0

    finally:
        conn.close()


def block_user(user_id):
    return set_blocked(
        user_id,
        True,
    )


def unblock_user(user_id):
    return set_blocked(
        user_id,
        False,
    )


# ============================================================
# PAYMENTS
# ============================================================

def create_payment(
    user_id,
    tariff,
    days,
    stars,
):
    conn = connect()

    try:

        cursor = conn.execute("""
            INSERT INTO payments (
                user_id,
                tariff,
                days,
                stars,
                status,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, 'pending', ?
            )
        """, (
            int(user_id),
            tariff or "",
            int(days),
            int(stars),
            now_iso(),
        ))

        conn.commit()

        payment_id = cursor.lastrowid

        row = conn.execute("""
            SELECT *
            FROM payments
            WHERE id = ?
        """, (
            payment_id,
        )).fetchone()

        return dict(row)

    finally:
        conn.close()


def get_payment(payment_id):

    conn = connect()

    try:

        row = conn.execute("""
            SELECT *
            FROM payments
            WHERE id = ?
        """, (
            int(payment_id),
        )).fetchone()

        return dict(row) if row else None

    finally:
        conn.close()


def complete_payment(
    payment_id,
    charge_id="",
):

    conn = connect()

    try:

        cursor = conn.execute("""
            UPDATE payments
            SET status = 'completed',
                telegram_payment_charge_id = ?,
                completed_at = ?
            WHERE id = ?
              AND status = 'pending'
        """, (
            charge_id or "",
            now_iso(),
            int(payment_id),
        ))

        conn.commit()

        if cursor.rowcount != 1:
            return None

        row = conn.execute("""
            SELECT *
            FROM payments
            WHERE id = ?
        """, (
            int(payment_id),
        )).fetchone()

        return dict(row) if row else None

    finally:
        conn.close()


# ============================================================
# PROMOCODES
# ============================================================

def create_promo(
    code,
    days,
    uses_left=0,
):
    code = str(
        code
    ).strip().upper()

    conn = connect()

    try:

        conn.execute("""
            INSERT OR REPLACE INTO promocodes (
                code,
                days,
                uses_left,
                created_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            code,
            int(days),
            int(uses_left),
            now_iso(),
        ))

        conn.commit()

    finally:
        conn.close()


def use_promo(
    user_id,
    code,
):
    code = str(
        code
    ).strip().upper()

    conn = connect()

    try:

        row = conn.execute("""
            SELECT *
            FROM promocodes
            WHERE code = ?
        """, (
            code,
        )).fetchone()

        if not row:
            return 0

        uses_left = int(
            row["uses_left"] or 0
        )

        # 0 = unlimited
        if uses_left > 0:

            cursor = conn.execute("""
                UPDATE promocodes
                SET uses_left = uses_left - 1
                WHERE code = ?
                  AND uses_left > 0
            """, (
                code,
            ))

            if cursor.rowcount != 1:
                return 0

        conn.commit()

        return int(
            row["days"] or 0
        )

    finally:
        conn.close()


# ============================================================
# NODES
# ============================================================

def add_node(
    name,
    vless_link,
):
    conn = connect()

    try:

        cursor = conn.execute("""
            INSERT INTO nodes (
                name,
                vless_link,
                active,
                created_at
            )
            VALUES (?, ?, 1, ?)
        """, (
            name or "",
            vless_link or "",
            now_iso(),
        ))

        conn.commit()

        return cursor.lastrowid

    finally:
        conn.close()


def update_node(
    node_id,
    name=None,
    vless_link=None,
    active=None,
):
    conn = connect()

    try:

        fields = []
        values = []

        if name is not None:
            fields.append(
                "name = ?"
            )
            values.append(name)

        if vless_link is not None:
            fields.append(
                "vless_link = ?"
            )
            values.append(vless_link)

        if active is not None:
            fields.append(
                "active = ?"
            )
            values.append(
                int(bool(active))
            )

        if not fields:
            return False

        values.append(
            int(node_id)
        )

        cursor = conn.execute(
            f"""
            UPDATE nodes
            SET {", ".join(fields)}
            WHERE id = ?
            """,
            tuple(values),
        )

        conn.commit()

        return cursor.rowcount > 0

    finally:
        conn.close()


def delete_node(node_id):

    conn = connect()

    try:

        cursor = conn.execute("""
            DELETE FROM nodes
            WHERE id = ?
        """, (
            int(node_id),
        ))

        conn.commit()

        return cursor.rowcount > 0

    finally:
        conn.close()


def get_nodes(
    active_only=True,
):

    conn = connect()

    try:

        if active_only:

            rows = conn.execute("""
                SELECT *
                FROM nodes
                WHERE active = 1
                ORDER BY id ASC
            """).fetchall()

        else:

            rows = conn.execute("""
                SELECT *
                FROM nodes
                ORDER BY id ASC
            """).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        conn.close()


# ============================================================
# DEVICES
# ============================================================

def get_devices(user_id):

    conn = connect()

    try:

        rows = conn.execute("""
            SELECT *
            FROM devices
            WHERE user_id = ?
            ORDER BY created_at ASC
        """, (
            int(user_id),
        )).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        conn.close()


def add_device(
    user_id,
    device_id,
    device_name="",
):
    user_id = int(user_id)
    device_id = str(
        device_id
    ).strip()

    if not device_id:
        return False

    conn = connect()

    try:

        user = conn.execute("""
            SELECT device_limit
            FROM users
            WHERE user_id = ?
        """, (
            user_id,
        )).fetchone()

        if not user:
            return False

        existing = conn.execute("""
            SELECT id
            FROM devices
            WHERE user_id = ?
              AND device_id = ?
        """, (
            user_id,
            device_id,
        )).fetchone()

        if existing:

            conn.execute("""
                UPDATE devices
                SET device_name = ?,
                    last_seen = ?
                WHERE user_id = ?
                  AND device_id = ?
            """, (
                device_name or "",
                now_iso(),
                user_id,
                device_id,
            ))

            conn.commit()

            return True

        limit = int(
            user["device_limit"]
            or DEFAULT_DEVICE_LIMIT
        )

        count = conn.execute("""
            SELECT COUNT(*)
            FROM devices
            WHERE user_id = ?
        """, (
            user_id,
        )).fetchone()[0]

        if limit > 0 and count >= limit:
            return False

        timestamp = now_iso()

        conn.execute("""
            INSERT INTO devices (
                user_id,
                device_id,
                device_name,
                created_at,
                last_seen
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            device_id,
            device_name or "",
            timestamp,
            timestamp,
        ))

        conn.commit()

        return True

    finally:
        conn.close()


def remove_device(
    user_id,
    device_id,
):

    conn = connect()

    try:

        cursor = conn.execute("""
            DELETE FROM devices
            WHERE user_id = ?
              AND device_id = ?
        """, (
            int(user_id),
            str(device_id),
        ))

        conn.commit()

        return cursor.rowcount > 0

    finally:
        conn.close()


def clear_devices(user_id):

    conn = connect()

    try:

        cursor = conn.execute("""
            DELETE FROM devices
            WHERE user_id = ?
        """, (
            int(user_id),
        ))

        conn.commit()

        return cursor.rowcount

    finally:
        conn.close()


def set_device_limit(
    user_id,
    limit,
):

    conn = connect()

    try:

        conn.execute("""
            UPDATE users
            SET device_limit = ?
            WHERE user_id = ?
        """, (
            max(0, int(limit)),
            int(user_id),
        ))

        conn.commit()

    finally:
        conn.close()


# ============================================================
# STATS
# ============================================================

def get_stats():

    conn = connect()

    try:

        users = conn.execute("""
            SELECT COUNT(*)
            FROM users
        """).fetchone()[0]

        active = conn.execute("""
            SELECT COUNT(*)
            FROM users
            WHERE subscription_until != ''
              AND subscription_until IS NOT NULL
        """).fetchone()[0]

        payments = conn.execute("""
            SELECT COUNT(*)
            FROM payments
            WHERE status = 'completed'
        """).fetchone()[0]

        revenue = conn.execute("""
            SELECT COALESCE(
                SUM(stars),
                0
            )
            FROM payments
            WHERE status = 'completed'
        """).fetchone()[0]

        nodes = conn.execute("""
            SELECT COUNT(*)
            FROM nodes
            WHERE active = 1
        """).fetchone()[0]

        return {
            "users": users,
            "active": active,
            "payments": payments,
            "revenue": revenue,
            "nodes": nodes,
        }

    finally:
        conn.close()


# ============================================================
# START
# ============================================================

init_db()