# admin.py

import asyncio
import html
import math

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import (
    ADMIN_IDS,
    SERVICE_NAME,
    TARIFFS,
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
    sync_user,
    github_raw_url,
)


router = Router(name="admin")


# ============================================================
# SETTINGS
# ============================================================

USERS_PER_PAGE = 8

admin_states = {}


# ============================================================
# HELPERS
# ============================================================

def is_admin(user_id: int) -> bool:
    return int(user_id) in ADMIN_IDS


def esc(value) -> str:
    return html.escape(
        str(value or "")
    )


def user_name(user) -> str:
    return (
        user.get("first_name")
        or user.get("username")
        or str(user.get("user_id", ""))
    )


def status_text(user) -> str:
    if int(user.get("blocked", 0) or 0):
        return "⛔ Заблокирован"

    until = user.get(
        "subscription_until",
        "",
    ) or ""

    if not until:
        return "🔴 Неактивна"

    from database import parse_datetime, now_utc

    expire = parse_datetime(until)

    if not expire:
        return "🔴 Неактивна"

    if expire <= now_utc():
        return "🔴 Истекла"

    return "🟢 Активна"


# ============================================================
# MAIN MENU
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


def back_keyboard() -> InlineKeyboardMarkup:

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

@router.message(F.text == "/admin")
async def admin_command(message: Message):

    if not is_admin(
        message.from_user.id
    ):
        return

    await message.answer(
        f"🛠 <b>{esc(SERVICE_NAME)}</b>\n\n"
        "Добро пожаловать в панель администратора.",
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


# ============================================================
# MENU
# ============================================================

@router.callback_query(F.data == "admin:menu")
async def admin_menu_handler(
    callback: CallbackQuery,
):

    if not is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        f"🛠 <b>{esc(SERVICE_NAME)}</b>\n\n"
        "Админ-панель:",
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# STATS
# ============================================================

@router.callback_query(F.data == "admin:stats")
async def admin_stats(
    callback: CallbackQuery,
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    stats = get_stats()

    await callback.message.edit_text(
        "📊 <b>Статистика МАГНИТ VPN</b>\n\n"
        f"👥 Пользователей: "
        f"<b>{stats.get('users', 0)}</b>\n"
        f"🟢 Активных: "
        f"<b>{stats.get('active', 0)}</b>\n"
        f"💳 Платежей: "
        f"<b>{stats.get('payments', 0)}</b>\n"
        f"⭐ Получено Stars: "
        f"<b>{stats.get('revenue', 0)}</b>\n"
        f"🌐 Серверов: "
        f"<b>{stats.get('nodes', 0)}</b>",
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# USERS
# ============================================================

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

    rows = []

    navigation = []

    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=(
                    f"admin:users:{page - 1}"
                ),
            )
        )

    navigation.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{pages}",
            callback_data="admin:noop",
        )
    )

    if page < pages - 1:
        navigation.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=(
                    f"admin:users:{page + 1}"
                ),
            )
        )

    rows.append(navigation)

    rows.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="admin:menu",
        )
    ])

    return rows


@router.callback_query(
    F.data.startswith("admin:users:")
)
async def admin_users(
    callback: CallbackQuery,
):

    if not is_admin(
        callback.from_user.id
    ):
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

    rows = []

    for user in current:

        uid = int(
            user["user_id"]
        )

        name = user_name(user)

        rows.append([
            InlineKeyboardButton(
                text=(
                    f"{'🟢' if status_text(user) == '🟢 Активна' else '🔴'} "
                    f"{name[:25]}"
                ),
                callback_data=(
                    f"admin:user:{uid}"
                ),
            )
        ])

    rows.extend(
        users_keyboard(
            page,
            total,
        )
    )

    await callback.message.edit_text(
        f"👥 <b>Пользователи</b>\n\n"
        f"Всего: <b>{total}</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=rows
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

    if not is_admin(
        callback.from_user.id
    ):
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

    until = (
        user.get(
            "subscription_until",
            "",
        )
        or ""
    )

    if until:
        until_text = format_date(until)
    else:
        until_text = "нет"

    device_limit = int(
        user.get(
            "device_limit",
            3,
        )
        or 3
    )

    blocked = bool(
        int(
            user.get(
                "blocked",
                0,
            )
            or 0
        )
    )

    raw = github_raw_url(
        user_id
    )

    text = (
        "👤 <b>Профиль пользователя</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Имя: <b>{esc(user_name(user))}</b>\n"
        f"🔹 Username: "
        f"<b>{esc(user.get('username') or 'нет')}</b>\n\n"
        f"📦 Тариф: "
        f"<b>{esc(user.get('subscription') or 'none')}</b>\n"
        f"📅 До: <b>{until_text}</b>\n"
        f"📌 Статус: <b>{status_text(user)}</b>\n"
        f"📱 Лимит устройств: <b>{device_limit}</b>\n"
        f"🚫 Блокировка: "
        f"<b>{'да' if blocked else 'нет'}</b>\n\n"
        f"🔗 <b>RAW подписка:</b>\n"
        f"<code>{raw}</code>"
    )

    rows = [
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
                text="🚫 Отозвать подписку",
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
                text="🔄 Обновить подписку",
                callback_data=(
                    f"admin:sync_user:{user_id}"
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

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=rows
        ),
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

    if not is_admin(
        callback.from_user.id
    ):
        return

    parts = callback.data.split(":")

    user_id = int(parts[2])
    days = int(parts[3])

    user = get_user(user_id)

    if not user:
        await callback.answer(
            "Пользователь не найден",
            show_alert=True,
        )
        return

    extend_subscription(
        user_id,
        days,
        "admin",
    )

    success = sync_user(
        user_id,
        force=True,
    )

    await callback.answer(
        "✅ Подписка продлена"
        if success
        else "⚠️ Продлена, но синхронизация не удалась",
        show_alert=True,
    )

    # Перерисовываем профиль
    await admin_user(callback)


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

    if not is_admin(
        callback.from_user.id
    ):
        return

    user_id = int(
        callback.data.split(":")[-1]
    )

    revoke_subscription(
        user_id
    )

    sync_user(
        user_id,
        force=True,
    )

    await callback.answer(
        "🚫 Подписка отозвана",
        show_alert=True,
    )

    await admin_user(callback)


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

    if not is_admin(
        callback.from_user.id
    ):
        return

    user_id = int(
        callback.data.split(":")[-1]
    )

    set_blocked(
        user_id,
        True,
    )

    sync_user(
        user_id,
        force=True,
    )

    await callback.answer(
        "⛔ Пользователь заблокирован",
        show_alert=True,
    )

    await admin_user(callback)


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

    if not is_admin(
        callback.from_user.id
    ):
        return

    user_id = int(
        callback.data.split(":")[-1]
    )

    set_blocked(
        user_id,
        False,
    )

    sync_user(
        user_id,
        force=True,
    )

    await callback.answer(
        "🔓 Пользователь разблокирован",
        show_alert=True,
    )

    await admin_user(callback)


# ============================================================
# SYNC ONE USER
# ============================================================

@router.callback_query(
    F.data.startswith(
        "admin:sync_user:"
    )
)
async def admin_sync_user(
    callback: CallbackQuery,
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    user_id = int(
        callback.data.split(":")[-1]
    )

    await callback.answer(
        "🔄 Обновляю..."
    )

    success = sync_user(
        user_id,
        force=True,
    )

    if success:
        await callback.answer(
            "✅ Подписка обновлена",
            show_alert=True,
        )
    else:
        await callback.answer(
            "❌ Ошибка синхронизации",
            show_alert=True,
        )

    await admin_user(callback)


# ============================================================
# 🔄 UPDATE ALL SERVERS
# ============================================================

@router.callback_query(
    F.data == "admin:sync"
)
async def admin_sync(
    callback: CallbackQuery,
):

    if not is_admin(
        callback.from_user.id
    ):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    await callback.answer(
        "🔄 Начинаю обновление..."
    )

    try:

        result = await asyncio.to_thread(
            force_sync
        )

        if not result.get(
            "success",
            False,
        ):

            error = result.get(
                "error",
                "Неизвестная ошибка",
            )

            await callback.message.edit_text(
                "❌ <b>Обновление серверов не выполнено</b>\n\n"
                f"<code>{esc(error)}</code>",
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
            f"🔒 Заглушек: "
            f"<b>{inactive_servers}</b>\n\n"
            f"👥 Пользователей: "
            f"<b>{total}</b>\n"
            f"🔄 Обновлено: "
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
            "❌ <b>Ошибка обновления серверов</b>\n\n"
            f"<code>{esc(exc)}</code>",
            reply_markup=back_keyboard(),
            parse_mode="HTML",
        )


# ============================================================
# FIND USER
# ============================================================

@router.callback_query(
    F.data == "admin:find"
)
async def admin_find(
    callback: CallbackQuery,
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    admin_states[
        callback.from_user.id
    ] = {
        "action": "find"
    }

    await callback.message.edit_text(
        "🔎 <b>Поиск пользователя</b>\n\n"
        "Отправь Telegram ID пользователя.",
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# GIVE
# ============================================================

@router.callback_query(
    F.data == "admin:give"
)
async def admin_give(
    callback: CallbackQuery,
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    admin_states[
        callback.from_user.id
    ] = {
        "action": "give"
    }

    await callback.message.edit_text(
        "➕ <b>Выдать подписку</b>\n\n"
        "Отправь сообщение в формате:\n\n"
        "<code>ID ДНИ</code>\n\n"
        "Например:\n"
        "<code>123456789 30</code>",
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# REVOKE
# ============================================================

@router.callback_query(
    F.data == "admin:revoke"
)
async def admin_revoke(
    callback: CallbackQuery,
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    admin_states[
        callback.from_user.id
    ] = {
        "action": "revoke"
    }

    await callback.message.edit_text(
        "🚫 <b>Отозвать подписку</b>\n\n"
        "Отправь Telegram ID.",
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# BLOCK MENU
# ============================================================

@router.callback_query(
    F.data == "admin:block"
)
async def admin_block_menu(
    callback: CallbackQuery,
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    admin_states[
        callback.from_user.id
    ] = {
        "action": "block"
    }

    await callback.message.edit_text(
        "⛔ <b>Блокировка</b>\n\n"
        "Отправь:\n"
        "<code>ID on</code> — заблокировать\n"
        "<code>ID off</code> — разблокировать",
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# PROMOS
# ============================================================

@router.callback_query(
    F.data == "admin:promos"
)
async def admin_promos(
    callback: CallbackQuery,
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    await callback.message.edit_text(
        "🎟 <b>Промокоды</b>\n\n"
        "Создать промокод:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ Создать",
                        callback_data=(
                            "admin:create_promo"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data="admin:menu",
                    )
                ],
            ]
        ),
        parse_mode="HTML",
    )

    await callback.answer()


@router.callback_query(
    F.data == "admin:create_promo"
)
async def admin_create_promo(
    callback: CallbackQuery,
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    admin_states[
        callback.from_user.id
    ] = {
        "action": "promo"
    }

    await callback.message.edit_text(
        "🎟 <b>Создание промокода</b>\n\n"
        "Отправь:\n\n"
        "<code>КОД ДНИ</code>\n\n"
        "Например:\n"
        "<code>MAGNIT30 30</code>",
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# BROADCAST
# ============================================================

@router.callback_query(
    F.data == "admin:broadcast"
)
async def admin_broadcast(
    callback: CallbackQuery,
):

    if not is_admin(
        callback.from_user.id
    ):
        return

    admin_states[
        callback.from_user.id
    ] = {
        "action": "broadcast"
    }

    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Отправь текст сообщения.",
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# BACK / CANCEL
# ============================================================

@router.callback_query(
    F.data == "admin:cancel"
)
async def admin_cancel(
    callback: CallbackQuery,
):

    admin_states.pop(
        callback.from_user.id,
        None,
    )

    await callback.message.edit_text(
        "🛠 <b>Админ-панель</b>",
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )

    await callback.answer()


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
# ADMIN TEXT STATES
# ============================================================

@router.message()
async def admin_text_handler(
    message: Message,
):

    if not is_admin(
        message.from_user.id
    ):
        return

    state = admin_states.get(
        message.from_user.id
    )

    if not state:
        return

    action = state.get(
        "action"
    )

    text = (
        message.text or ""
    ).strip()

    # --------------------------------------------------------
    # FIND
    # --------------------------------------------------------

    if action == "find":

        try:
            user_id = int(text)

        except ValueError:

            await message.answer(
                "❌ ID должен быть числом."
            )
            return

        admin_states.pop(
            message.from_user.id,
            None,
        )

        user = get_user(user_id)

        if not user:

            await message.answer(
                "❌ Пользователь не найден.",
                reply_markup=admin_menu(),
            )
            return

        await message.answer(
            "👤 <b>Пользователь найден</b>\n\n"
            f"ID: <code>{user_id}</code>\n"
            f"Имя: <b>{esc(user_name(user))}</b>\n"
            f"Тариф: <b>"
            f"{esc(user.get('subscription') or 'none')}"
            f"</b>\n"
            f"Статус: <b>{status_text(user)}</b>\n"
            f"До: <b>"
            f"{format_date(user.get('subscription_until')) if user.get('subscription_until') else 'нет'}"
            f"</b>\n\n"
            f"🔗 RAW:\n"
            f"<code>{github_raw_url(user_id)}</code>",
            reply_markup=admin_menu(),
            parse_mode="HTML",
        )

        return

    # --------------------------------------------------------
    # GIVE
    # --------------------------------------------------------

    if action == "give":

        parts = text.split()

        if len(parts) != 2:

            await message.answer(
                "❌ Формат:\n"
                "<code>ID ДНИ</code>",
                parse_mode="HTML",
            )
            return

        try:
            user_id = int(parts[0])
            days = int(parts[1])

        except ValueError:

            await message.answer(
                "❌ ID и дни должны быть числами."
            )
            return

        if not get_user(user_id):

            await message.answer(
                "❌ Пользователь не найден."
            )
            return

        extend_subscription(
            user_id,
            days,
            "admin",
        )

        success = await asyncio.to_thread(
            sync_user,
            user_id,
            True,
        )

        admin_states.pop(
            message.from_user.id,
            None,
        )

        await message.answer(
            "✅ <b>Готово</b>\n\n"
            f"Пользователь: <code>{user_id}</code>\n"
            f"Добавлено: <b>{days} дней</b>\n"
            f"Синхронизация: "
            f"<b>{'OK' if success else 'Ошибка'}</b>",
            reply_markup=admin_menu(),
            parse_mode="HTML",
        )

        return

    # --------------------------------------------------------
    # REVOKE
    # --------------------------------------------------------

    if action == "revoke":

        try:
            user_id = int(text)

        except ValueError:

            await message.answer(
                "❌ Некорректный ID."
            )
            return

        if not get_user(user_id):

            await message.answer(
                "❌ Пользователь не найден."
            )
            return

        revoke_subscription(
            user_id
        )

        await asyncio.to_thread(
            sync_user,
            user_id,
            True,
        )

        admin_states.pop(
            message.from_user.id,
            None,
        )

        await message.answer(
            "🚫 <b>Подписка отозвана.</b>",
            reply_markup=admin_menu(),
            parse_mode="HTML",
        )

        return

    # --------------------------------------------------------
    # BLOCK
    # --------------------------------------------------------

    if action == "block":

        parts = text.split()

        if len(parts) != 2:

            await message.answer(
                "❌ Формат:\n"
                "<code>ID on</code>\n"
                "или\n"
                "<code>ID off</code>",
                parse_mode="HTML",
            )
            return

        try:
            user_id = int(parts[0])

        except ValueError:

            await message.answer(
                "❌ Некорректный ID."
            )
            return

        mode = parts[1].lower()

        if mode not in {
            "on",
            "off",
        }:

            await message.answer(
                "❌ Используй on или off."
            )
            return

        if not get_user(user_id):

            await message.answer(
                "❌ Пользователь не найден."
            )
            return

        set_blocked(
            user_id,
            mode == "on",
        )

        await asyncio.to_thread(
            sync_user,
            user_id,
            True,
        )

        admin_states.pop(
            message.from_user.id,
            None,
        )

        await message.answer(
            (
                "⛔ Пользователь заблокирован."
                if mode == "on"
                else "🔓 Пользователь разблокирован."
            ),
            reply_markup=admin_menu(),
        )

        return

    # --------------------------------------------------------
    # PROMO
    # --------------------------------------------------------

    if action == "promo":

        parts = text.split()

        if len(parts) != 2:

            await message.answer(
                "❌ Формат:\n"
                "<code>КОД ДНИ</code>",
                parse_mode="HTML",
            )
            return

        code = parts[0].strip().upper()

        try:
            days = int(parts[1])

        except ValueError:

            await message.answer(
                "❌ Количество дней должно быть числом."
            )
            return

        if days <= 0:

            await message.answer(
                "❌ Дни должны быть больше нуля."
            )
            return

        success = create_promo(
            code,
            days,
        )

        admin_states.pop(
            message.from_user.id,
            None,
        )

        await message.answer(
            (
                f"✅ Промокод создан.\n\n"
                f"🎟 <code>{esc(code)}</code>\n"
                f"📅 {days} дней"
                if success
                else "❌ Такой промокод уже существует."
            ),
            reply_markup=admin_menu(),
            parse_mode="HTML",
        )

        return

    # --------------------------------------------------------
    # BROADCAST
    # --------------------------------------------------------

    if action == "broadcast":

        admin_states.pop(
            message.from_user.id,
            None,
        )

        users = get_all_users()

        sent = 0
        failed = 0

        await message.answer(
            f"📢 Начинаю рассылку для "
            f"<b>{len(users)}</b> пользователей...",
            parse_mode="HTML",
        )

        for user in users:

            if int(
                user.get(
                    "blocked",
                    0,
                )
                or 0
            ):
                continue

            try:

                await message.bot.send_message(
                    chat_id=int(
                        user["user_id"]
                    ),
                    text=text,
                    parse_mode="HTML",
                )

                sent += 1

                await asyncio.sleep(
                    0.05
                )

            except Exception:

                failed += 1

        await message.answer(
            "📢 <b>Рассылка завершена</b>\n\n"
            f"✅ Отправлено: <b>{sent}</b>\n"
            f"❌ Ошибок: <b>{failed}</b>",
            reply_markup=admin_menu(),
            parse_mode="HTML",
        )

        return