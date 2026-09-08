# database.py

import os
import sqlite3
import secrets

from datetime import datetime, timedelta, timezone


# ============================================================
# НАСТРОЙКИ
# ============================================================

DB_PATH = os.getenv(
    "DB_PATH",
    "./data/users.db",
)


# ============================================================
# ВРЕМЯ
# ============================================================

UTC = timezone.utc


def now_utc() -> datetime:
    return datetime.now(UTC)


def now_iso() -> str:
    return now_utc().isoformat()


def parse_datetime(value):
    if not value:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    return dt.astimezone(UTC)


def format_date(value) -> str:
    dt = parse_datetime(value)

    if not dt:
        return "—"

    return dt.strftime("%d.%m.%Y")


# ============================================================
# СОЕДИНЕНИЕ
# ============================================================

def connect():
    path = os.path.abspath(DB_PATH)

    directory = os.path.dirname(path)

    if directory:
        os.makedirs(directory, exist_ok=True)

    connection = sqlite3.connect(
        path,
        timeout=30,
        check_same_thread=False,
    )

    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("PRAGMA foreign_keys=ON")

    return connection


# ============================================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================================

def init_db():
    with connect() as db:

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,

                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',

                token TEXT UNIQUE NOT NULL,

                subscription TEXT DEFAULT 'none',

                subscription_until TEXT DEFAULT '',

                subscription_link TEXT DEFAULT '',

                subscription_content TEXT DEFAULT '',

                trial_used INTEGER DEFAULT 0,

                blocked INTEGER DEFAULT 0,

                notify INTEGER DEFAULT 1,

                accepted_terms INTEGER DEFAULT 0,

                created_at TEXT DEFAULT ''
            )
            """
        )

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                tariff TEXT DEFAULT '',

                days INTEGER DEFAULT 0,

                stars INTEGER DEFAULT 0,

                telegram_payment_charge_id TEXT DEFAULT '',

                status TEXT DEFAULT 'pending',

                created_at TEXT DEFAULT '',

                completed_at TEXT DEFAULT '',

                FOREIGN KEY(user_id)
                    REFERENCES users(user_id)
                    ON DELETE CASCADE
            )
            """
        )

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,

                days INTEGER NOT NULL,

                uses_left INTEGER DEFAULT 0,

                created_at TEXT DEFAULT ''
            )
            """
        )

        # ----------------------------------------------------
        # МИГРАЦИИ СТАРОЙ БАЗЫ
        # ----------------------------------------------------

        columns = {
            row["name"]
            for row in db.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        }

        migrations = {
            "token": "ALTER TABLE users ADD COLUMN token TEXT",
            "subscription_content": (
                "ALTER TABLE users "
                "ADD COLUMN subscription_content TEXT DEFAULT ''"
            ),
            "blocked": (
                "ALTER TABLE users "
                "ADD COLUMN blocked INTEGER DEFAULT 0"
            ),
            "notify": (
                "ALTER TABLE users "
                "ADD COLUMN notify INTEGER DEFAULT 1"
            ),
            "accepted_terms": (
                "ALTER TABLE users "
                "ADD COLUMN accepted_terms INTEGER DEFAULT 0"
            ),
        }

        for column, sql in migrations.items():

            if column not in columns:

                try:
                    db.execute(sql)
                except sqlite3.OperationalError:
                    pass

        # Заполняем token существующим пользователям
        rows = db.execute(
            """
            SELECT user_id
            FROM users
            WHERE token IS NULL
               OR token = ''
            """
        ).fetchall()

        for row in rows:

            token = secrets.token_urlsafe(32)

            db.execute(
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

        db.commit()


# ============================================================
# ПОЛЬЗОВАТЕЛИ
# ============================================================

def create_user(
    user_id: int,
    username: str = "",
    first_name: str = "",
):
    with connect() as db:

        existing = db.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if existing:

            db.execute(
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

            db.commit()

            return get_user(user_id)

        token = secrets.token_urlsafe(32)

        db.execute(
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
                created_at
            )
            VALUES (?, ?, ?, ?, 'none', '', '', '', 0, 0, 1, 0, ?)
            """,
            (
                user_id,
                username or "",
                first_name or "",
                token,
                now_iso(),
            ),
        )

        db.commit()

    return get_user(user_id)


def get_user(user_id: int):
    with connect() as db:

        row = db.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    return dict(row) if row else None


def get_user_by_token(token: str):
    with connect() as db:

        row = db.execute(
            """
            SELECT *
            FROM users
            WHERE token = ?
            """,
            (token,),
        ).fetchone()

    return dict(row) if row else None


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
# ПОДПИСКА
# ============================================================

def build_subscription_link(token: str):
    from config import PUBLIC_URL

    return f"{PUBLIC_URL}/sub/{token}"


def save_subscription_link(
    user_id: int,
    link: str,
):
    with connect() as db:

        db.execute(
            """
            UPDATE users
            SET subscription_link = ?
            WHERE user_id = ?
            """,
            (
                link,
                user_id,
            ),
        )

        db.commit()


def get_subscription_link(user_id: int):
    user = get_user(user_id)

    if not user:
        return ""

    return user.get("subscription_link", "")


def save_subscription_content(
    user_id: int,
    content: str,
):
    with connect() as db:

        db.execute(
            """
            UPDATE users
            SET subscription_content = ?
            WHERE user_id = ?
            """,
            (
                content,
                user_id,
            ),
        )

        db.commit()


def get_subscription_content(user_id: int):
    user = get_user(user_id)

    if not user:
        return ""

    return user.get("subscription_content", "")


# ============================================================
# ПРОДЛЕНИЕ
# ============================================================

def extend_subscription(
    user_id: int,
    days: int,
    tariff: str = "",
):
    user = get_user(user_id)

    if not user:
        return None

    current = parse_datetime(
        user.get("subscription_until")
    )

    now = now_utc()

    if current is None or current < now:
        current = now

    new_until = current + timedelta(days=days)

    with connect() as db:

        db.execute(
            """
            UPDATE users
            SET subscription = ?,
                subscription_until = ?
            WHERE user_id = ?
            """,
            (
                tariff or user.get("subscription") or "active",
                new_until.isoformat(),
                user_id,
            ),
        )

        db.commit()

    return get_user(user_id)


def revoke_subscription(user_id: int):
    with connect() as db:

        db.execute(
            """
            UPDATE users
            SET subscription = 'none',
                subscription_until = ''
            WHERE user_id = ?
            """,
            (user_id,),
        )

        db.commit()

    return get_user(user_id)


def expire_old_subscriptions():
    now = now_utc()

    with connect() as db:

        db.execute(
            """
            UPDATE users
            SET subscription = 'expired'
            WHERE subscription_until != ''
              AND subscription_until IS NOT NULL
              AND subscription_until < ?
              AND subscription NOT IN ('none', 'expired')
            """,
            (now.isoformat(),),
        )

        db.commit()


# ============================================================
# ПРОБНЫЙ ПЕРИОД
# ============================================================

def use_trial(
    user_id: int,
    days: int,
):
    user = get_user(user_id)

    if not user:
        return False

    if user.get("trial_used"):
        return False

    now = now_utc()

    until = now + timedelta(days=days)

    with connect() as db:

        db.execute(
            """
            UPDATE users
            SET trial_used = 1,
                subscription = 'trial',
                subscription_until = ?
            WHERE user_id = ?
            """,
            (
                until.isoformat(),
                user_id,
            ),
        )

        db.commit()

    return True


# ============================================================
# БЛОКИРОВКА
# ============================================================

def set_blocked(
    user_id: int,
    blocked: bool,
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
                user_id,
            ),
        )

        db.commit()

    return get_user(user_id)


def is_blocked(user_id: int):
    user = get_user(user_id)

    if not user:
        return False

    return bool(user.get("blocked"))


# ============================================================
# ПЛАТЕЖИ
# ============================================================

def create_payment(
    user_id: int,
    tariff: str,
    days: int,
    stars: int,
):
    with connect() as db:

        cursor = db.execute(
            """
            INSERT INTO payments (
                user_id,
                tariff,
                days,
                stars,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (
                user_id,
                tariff,
                days,
                stars,
                now_iso(),
            ),
        )

        db.commit()

        return cursor.lastrowid


def get_payment(payment_id: int):
    with connect() as db:

        row = db.execute(
            """
            SELECT *
            FROM payments
            WHERE id = ?
            """,
            (payment_id,),
        ).fetchone()

    return dict(row) if row else None


def complete_payment(
    payment_id: int,
    charge_id: str = "",
):
    with connect() as db:

        db.execute(
            """
            UPDATE payments
            SET status = 'completed',
                telegram_payment_charge_id = ?,
                completed_at = ?
            WHERE id = ?
            """,
            (
                charge_id,
                now_iso(),
                payment_id,
            ),
        )

        db.commit()

    return get_payment(payment_id)


# ============================================================
# ПРОМОКОДЫ
# ============================================================

def create_promo(
    code: str,
    days: int,
    uses_left: int = 0,
):
    code = code.strip().upper()

    with connect() as db:

        db.execute(
            """
            INSERT OR REPLACE INTO promocodes (
                code,
                days,
                uses_left,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                code,
                days,
                uses_left,
                now_iso(),
            ),
        )

        db.commit()


def use_promo(
    user_id: int,
    code: str,
):
    code = code.strip().upper()

    with connect() as db:

        promo = db.execute(
            """
            SELECT *
            FROM promocodes
            WHERE code = ?
            """,
            (code,),
        ).fetchone()

        if not promo:
            return None

        uses_left = promo["uses_left"]

        if uses_left > 0:

            db.execute(
                """
                UPDATE promocodes
                SET uses_left = uses_left - 1
                WHERE code = ?
                """,
                (code,),
            )

        db.commit()

    return int(promo["days"])


# ============================================================
# СТАТИСТИКА
# ============================================================

def get_stats():
    with connect() as db:

        total = db.execute(
            """
            SELECT COUNT(*)
            FROM users
            """
        ).fetchone()[0]

        active = db.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE subscription_until != ''
              AND subscription_until > ?
              AND blocked = 0
            """,
            (now_iso(),),
        ).fetchone()[0]

        blocked = db.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE blocked = 1
            """
        ).fetchone()[0]

        trials = db.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE trial_used = 1
            """
        ).fetchone()[0]

        payments = db.execute(
            """
            SELECT COUNT(*)
            FROM payments
            WHERE status = 'completed'
            """
        ).fetchone()[0]

        stars = db.execute(
            """
            SELECT COALESCE(SUM(stars), 0)
            FROM payments
            WHERE status = 'completed'
            """
        ).fetchone()[0]

    return {
        "total": total,
        "active": active,
        "blocked": blocked,
        "trials": trials,
        "payments": payments,
        "stars": stars,
    }


# ============================================================
# ЗАПУСК
# ============================================================

init_db()