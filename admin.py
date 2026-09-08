# admin.py

import math

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
)

from config import (
    ADMIN_IDS,
    TARIFFS,
    SERVICE_NAME,
)

from database import (
    get_user,
    get_all_users,
    get_stats,
    extend_subscription,
    revoke_subscription,
    set_blocked,
    create_promo,
    format_date,
)

from subscription import (
    force_sync,
    github_raw_url,
)


# ============================================================
# ROUTER
# ============================================================

router = Router(
    name="admin"
)


# ============================================================
# STATE
# ============================================================

admin_states = {}


# ============================================================
# AUTH
# ============================================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_only(callback: CallbackQuery) -> bool:
    return is_admin(
        callback.from_user.id
    )


def admin_message_only(message: Message) -> bool:
    return is_admin(
        message.from_user.id
    )


# ============================================================
# KEYBOARD
# ============================================================

def admin_menu() -> InlineKeyboardMarkup:

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="admin:stats",
                ),
                InlineKeyboardButton(
                    text="👥 Пользователи",
                    callback_data="admin:users:0",
                ),
            ],

            [
                InlineKeyboardButton(
                    text="🔎 Найти пользователя",
                    callback_data="admin:find",
                ),
            ],

            [
                InlineKeyboardButton(
                    text="➕ Выдать подписку",
                    callback_data="admin:give",
                ),
                InlineKeyboardButton(
                    text="🚫 Отозвать",
                    callback_data="admin:revoke",
                ),
            ],

            [
                InlineKeyboardButton(
                    text="⛔ Блокировки",
                    callback_data="admin:block",
                ),
                InlineKeyboardButton(
                    text="🎟 Промокоды",
                    callback_data="admin:promos",
                ),
            ],

            [
                InlineKeyboardButton(
                    text="📢 Рассылка",
                    callback_data="admin:broadcast",
                ),
            ],

            [
                InlineKeyboardButton(
                    text="🔄 Обновить серверы",
                    callback_data="admin:sync",
                ),
            ],
        ]
    )


# ============================================================
# BACK
# ============================================================

def back_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="admin:menu",
                )
            ]
        ]
    )


# ============================================================
# /admin
# ============================================================

@router.message(
    F.text == "/admin"
)
async def admin_command(
    message: Message,
):

    if not admin_message_only(
        message
    ):
        return

    await message.answer(
        f"🛠 <b>{SERVICE_NAME}</b>\n\n"
        "Админ-панель:",
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


# ============================================================
# ADMIN MENU
# ============================================================

@router.callback_query(
    F.data == "admin:menu"
)
async def admin_menu_callback(
    callback: CallbackQuery,
):

    if not admin_only(callback):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        f"🛠 <b>{SERVICE_NAME}</b>\n\n"
        "Админ-панель:",
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# SYNC SERVERS
# ============================================================

@router.callback_query(
    F.data == "admin:sync"
)
async def admin_sync(
    callback: CallbackQuery,
):

    if not admin_only(callback):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    await callback.answer(
        "🔄 Обновляю серверы..."
    )

    try:

        result = force_sync()

        if not result.get(
            "success"
        ):

            error = result.get(
                "error",
                "Неизвестная ошибка",
            )

            await callback.message.edit_text(
                "❌ <b>Обновление не выполнено</b>\n\n"
                f"{error}",
                reply_markup=back_keyboard(),
                parse_mode="HTML",
            )

            return

        total = result.get(
            "total",
            0,
        )

        updated = result.get(
            "updated",
            0,
        )

        skipped = result.get(
            "skipped",
            0,
        )

        failed = result.get(
            "failed",
            0,
        )

        active_servers = result.get(
            "active_servers",
            0,
        )

        inactive_servers = result.get(
            "inactive_servers",
            0,
        )

        text = (
            "✅ <b>Серверы обновлены!</b>\n\n"
            f"🌐 Рабочих серверов: "
            f"<b>{active_servers}</b>\n"
            f"🔒 Неактивных: "
            f"<b>{inactive_servers}</b>\n\n"
            f"👥 Пользователей: "
            f"<b>{total}</b>\n"
            f"🔄 Обновлено файлов: "
            f"<b>{updated}</b>\n"
            f"⏭ Без изменений: "
            f"<b>{skipped}</b>\n"
            f"❌ Ошибок: "
            f"<b>{failed}</b>"
        )

        await callback.message.edit_text(
            text,
            reply_markup=back_keyboard(),
            parse_mode="HTML",
        )

    except Exception as exc:

        await callback.message.edit_text(
            "❌ <b>Ошибка обновления</b>\n\n"
            f"<code>{str(exc)}</code>",
            reply_markup=back_keyboard(),
            parse_mode="HTML",
        )


# ============================================================
# STATS
# ============================================================

@router.callback_query(
    F.data == "admin:stats"
)
async def admin_stats(
    callback: CallbackQuery,
):

    if not admin_only(callback):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    stats = get_stats()

    text = (
        "📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: "
        f"<b>{stats.get('users', 0)}</b>\n"
        f"🟢 Активных: "
        f"<b>{stats.get('active', 0)}</b>\n"
        f"💳 Платежей: "
        f"<b>{stats.get('payments', 0)}</b>\n"
        f"⭐ Stars: "
        f"<b>{stats.get('revenue', 0)}</b>\n"
        f"🌐 Серверов: "
        f"<b>{stats.get('nodes', 0)}</b>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# USERS
# ============================================================

USERS_PER_PAGE = 8


def users_keyboard(
    page: int,
    total: int,
):

    pages = max(
        1,
        math.ceil(
            total / USERS_PER_PAGE
        ),
    )

    buttons = []

    if page > 0:
        buttons.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=(
                    f"admin:users:{page - 1}"
                ),
            )
        )

    buttons.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{pages}",
            callback_data="admin:noop",
        )
    )

    if page < pages - 1:
        buttons.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=(
                    f"admin:users:{page + 1}"
                ),
            )
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            buttons,
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="admin:menu",
                )
            ],
        ]
    )


@router.callback_query(
    F.data.startswith("admin:users:")
)
async def admin_users(
    callback: CallbackQuery,
):

    if not admin_only(callback):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    page = int(
        callback.data.split(":")[-1]
    )

    users = get_all_users()

    total = len(users)

    start = (
        page * USERS_PER_PAGE
    )

    current = users[
        start:start + USERS_PER_PAGE
    ]

    lines = [
        "👥 <b>Пользователи</b>\n"
    ]

    buttons = []

    for user in current:

        user_id = int(
            user["user_id"]
        )

        name = (
            user.get(
                "first_name"
            )
            or user.get(
                "username"
            )
            or str(user_id)
        )

        lines.append(
            f"👤 <b>{name}</b> "
            f"<code>{user_id}</code>"
        )

        buttons.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"👤 {name[:25]}"
                    ),
                    callback_data=(
                        f"admin:user:{user_id}"
                    ),
                )
            ]
        )

    markup = users_keyboard(
        page,
        total,
    )

    buttons.extend(
        markup.inline_keyboard
    )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# USER PROFILE
# ============================================================

@router.callback_query(
    F.data.startswith("admin:user:")
)
async def admin_user(
    callback: CallbackQuery,
):

    if not admin_only(callback):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    user_id = int(
        callback.data.split(":")[-1]
    )

    user = get_user(user_id)

    if not user:

        await callback.answer(
            "Пользователь не найден",
            show_alert=True,
        )
        return

    username = (
        user.get("username")
        or "нет"
    )

    first_name = (
        user.get("first_name")
        or "нет"
    )

    subscription = (
        user.get(
            "subscription",
            "none",
        )
        or "none"
    )

    expire = (
        user.get(
            "subscription_until",
            "",
        )
        or ""
    )

    blocked = int(
        user.get(
            "blocked",
            0,
        )
        or 0
    )

    device_limit = int(
        user.get(
            "device_limit",
            3,
        )
        or 3
    )

    raw_url = github_raw_url(
        user_id
    )

    text = (
        "👤 <b>Пользователь</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Имя: <b>{first_name}</b>\n"
        f"🔹 Username: "
        f"<b>{username}</b>\n\n"
        f"📦 Тариф: "
        f"<b>{subscription}</b>\n"
        f"📅 До: "
        f"<b>{format_date(expire) if expire else 'нет'}</b>\n"
        f"📱 Лимит устройств: "
        f"<b>{device_limit}</b>\n"
        f"🚫 Заблокирован: "
        f"<b>{'да' if blocked else 'нет'}</b>\n\n"
        f"🔗 RAW:\n"
        f"<code>{raw_url}</code>"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="➕ 30 дней",
                    callback_data=(
                        f"admin:add:{user_id}:30"
                    ),
                ),
                InlineKeyboardButton(
                    text="➕ 90 дней",
                    callback_data=(
                        f"admin:add:{user_id}:90"
                    ),
                ),
            ],

            [
                InlineKeyboardButton(
                    text="➕ 180 дней",
                    callback_data=(
                        f"admin:add:{user_id}:180"
                    ),
                ),
                InlineKeyboardButton(
                    text="➕ 365 дней",
                    callback_data=(
                        f"admin:add:{user_id}:365"
                    ),
                ),
            ],

            [
                InlineKeyboardButton(
                    text="🚫 Отозвать",
                    callback_data=(
                        f"admin:revoke_user:{user_id}"
                    ),
                ),
            ],

            [
                InlineKeyboardButton(
                    text=(
                        "🔓 Разблокировать"
                        if blocked
                        else "⛔ Заблокировать"
                    ),
                    callback_data=(
                        f"admin:unblock:{user_id}"
                        if blocked
                        else f"admin:block_user:{user_id}"
                    ),
                )
            ],

            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="admin:users:0",
                )
            ],
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=markup,
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# ADD SUBSCRIPTION
# ============================================================

@router.callback_query(
    F.data.startswith("admin:add:")
)
async def admin_add(
    callback: CallbackQuery,
):

    if not admin_only(callback):
        return

    _, _, user_id, days = (
        callback.data.split(":")
    )

    user_id = int(user_id)
    days = int(days)

    extend_subscription(
        user_id,
        days,
        "admin",
    )

    # Сразу обновляем GitHub,
    # чтобы подписка заработала.
    from subscription import sync_user

    sync_user(
        user_id,
        force=True,
    )

    await callback.answer(
        f"✅ Добавлено {days} дней"
    )

    await admin_user(
        callback
    )


# ============================================================
# REVOKE
# ============================================================

@router.callback_query(
    F.data.startswith(
        "admin:revoke_user:"
    )
)
async def admin_revoke_user(
    callback: CallbackQuery,
):

    if not admin_only(callback):
        return

    user_id = int(
        callback.data.split(":")[-1]
    )

    revoke_subscription(
        user_id
    )

    from subscription import sync_user

    sync_user(
        user_id,
        force=True,
    )

    await callback.answer(
        "🚫 Подписка отозвана"
    )

    await admin_user(
        callback
    )


# ============================================================
# BLOCK
# ============================================================

@router.callback_query(
    F.data.startswith(
        "admin:block_user:"
    )
)
async def admin_block_user(
    callback: CallbackQuery,
):

    if not admin_only(callback):
        return

    user_id = int(
        callback.data.split(":")[-1]
    )

    set_blocked(
        user_id,
        True,
    )

    from subscription import sync_user

    sync_user(
        user_id,
        force=True,
    )

    await callback.answer(
        "⛔ Пользователь заблокирован"
    )

    await admin_user(
        callback
    )


# ============================================================
# UNBLOCK
# ============================================================

@router.callback_query(
    F.data.startswith(
        "admin:unblock:"
    )
)
async def admin_unblock(
    callback: CallbackQuery,
):

    if not admin_only(callback):
        return

    user_id = int(
        callback.data.split(":")[-1]
    )

    set_blocked(
        user_id,
        False,
    )

    from subscription import sync_user

    sync_user(
        user_id,
        force=True,
    )

    await callback.answer(
        "🔓 Пользователь разблокирован"
    )

    await admin_user(
        callback
    )


# ============================================================
# NOOP
# ============================================================

@router.callback_query(
    F.data == "admin:noop"
)
async def admin_noop(
    callback: CallbackQuery,
):

    await callback.answer()


# ============================================================
# FALLBACK MENU
# ============================================================

@router.callback_query(
    F.data == "admin:find"
)
async def admin_find(
    callback: CallbackQuery,
):

    if not admin_only(callback):
        return

    admin_states[
        callback.from_user.id
    ] = "find"

    await callback.message.edit_text(
        "🔎 <b>Поиск пользователя</b>\n\n"
        "Отправь Telegram ID:",
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# TEXT STATE
# ============================================================

@router.message()
async def admin_text_state(
    message: Message,
):

    if not admin_message_only(
        message
    ):
        return

    user_id = message.from_user.id

    state = admin_states.get(
        user_id
    )

    if state != "find":
        return

    try:
        target_id = int(
            message.text.strip()
        )

    except (
        TypeError,
        ValueError,
    ):

        await message.answer(
            "❌ Отправь корректный Telegram ID."
        )
        return

    admin_states.pop(
        user_id,
        None,
    )

    target = get_user(
        target_id
    )

    if not target:

        await message.answer(
            "❌ Пользователь не найден.",
            reply_markup=admin_menu(),
        )
        return

    name = (
        target.get("first_name")
        or target.get("username")
        or str(target_id)
    )

    expire = (
        target.get(
            "subscription_until",
            "",
        )
        or ""
    )

    raw = github_raw_url(
        target_id
    )

    await message.answer(
        "👤 <b>Пользователь найден</b>\n\n"
        f"Имя: <b>{name}</b>\n"
        f"ID: <code>{target_id}</code>\n"
        f"Тариф: <b>"
        f"{target.get('subscription', 'none')}"
        f"</b>\n"
        f"До: <b>"
        f"{format_date(expire) if expire else 'нет'}"
        f"</b>\n\n"
        f"🔗 RAW:\n"
        f"<code>{raw}</code>",
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )