# admin.py
# ============================================================
# МАГНИТ VPN — ADMIN PANEL
# ============================================================

import math
from datetime import datetime

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import ADMIN_IDS, TARIFFS, SERVICE_NAME
from database import (
    get_user,
    get_all_users,
    get_stats,
    extend_subscription,
    revoke_subscription,
    set_blocked,
    create_promo,
)
from subscription import force_sync


router = Router(name="admin")

# Состояния ввода администратора.
# Никаких состояний, связанных с устройствами.
admin_states = {}


# ============================================================
# ACCESS
# ============================================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ============================================================
# HELPERS
# ============================================================

def safe_text(value) -> str:
    if value is None:
        return "—"

    text = str(value)

    if len(text) > 1000:
        text = text[:997] + "..."

    return text


def user_name(user: dict) -> str:
    username = user.get("username")

    if username:
        return f"@{username}"

    first_name = user.get("first_name")

    if first_name:
        return first_name

    return f"ID {user.get('user_id')}"


def user_status(user: dict) -> str:
    if user.get("blocked"):
        return "🚫 Заблокирован"

    until = user.get("subscription_until")

    if not until:
        return "🔴 Нет подписки"

    try:
        dt = datetime.fromisoformat(
            str(until).replace("Z", "+00:00")
        )

        if dt > datetime.now(dt.tzinfo):
            return "🟢 Активна"

    except Exception:
        pass

    return "🔴 Истекла"


def format_user(user: dict) -> str:
    return (
        f"👤 <b>{safe_text(user_name(user))}</b>\n\n"
        f"🆔 ID: <code>{user.get('user_id')}</code>\n"
        f"📦 Тариф: <b>{safe_text(user.get('subscription', 'none'))}</b>\n"
        f"📅 До: <b>{safe_text(user.get('subscription_until'))}</b>\n"
        f"📊 Статус: <b>{user_status(user)}</b>\n"
        f"🎁 Пробник использован: "
        f"<b>{'Да' if user.get('trial_used') else 'Нет'}</b>\n"
        f"🚫 Заблокирован: "
        f"<b>{'Да' if user.get('blocked') else 'Нет'}</b>"
    )


# ============================================================
# MAIN ADMIN MENU
# ============================================================

def admin_keyboard() -> InlineKeyboardMarkup:
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
                    text="➖ Забрать подписку",
                    callback_data="admin:revoke",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Блокировка",
                    callback_data="admin:block",
                ),
            ],
            [
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
                    text="🔄 Синхронизация",
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
# USER PAGINATION
# ============================================================

USERS_PER_PAGE = 8


def users_keyboard(page: int = 0) -> InlineKeyboardMarkup:

    users = get_all_users()

    total_pages = max(
        1,
        math.ceil(len(users) / USERS_PER_PAGE),
    )

    page = max(0, min(page, total_pages - 1))

    start = page * USERS_PER_PAGE
    end = start + USERS_PER_PAGE

    current = users[start:end]

    rows = []

    for user in current:

        uid = user["user_id"]

        name = user_name(user)

        if len(name) > 25:
            name = name[:22] + "..."

        rows.append(
            [
                InlineKeyboardButton(
                    text=f"👤 {name}",
                    callback_data=f"admin:user:{uid}",
                )
            ]
        )

    navigation = []

    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=f"admin:users:{page - 1}",
            )
        )

    navigation.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}",
            callback_data="admin:noop",
        )
    )

    if page < total_pages - 1:
        navigation.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=f"admin:users:{page + 1}",
            )
        )

    rows.append(navigation)

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ В админ-панель",
                callback_data="admin:menu",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


# ============================================================
# USER ACTIONS KEYBOARD
# ============================================================

def user_keyboard(user: dict) -> InlineKeyboardMarkup:

    uid = user["user_id"]

    rows = [
        [
            InlineKeyboardButton(
                text="➕ 30 дней",
                callback_data=f"admin:add:{uid}:30",
            ),
            InlineKeyboardButton(
                text="➕ 90 дней",
                callback_data=f"admin:add:{uid}:90",
            ),
        ],
        [
            InlineKeyboardButton(
                text="➕ 180 дней",
                callback_data=f"admin:add:{uid}:180",
            ),
            InlineKeyboardButton(
                text="➕ 365 дней",
                callback_data=f"admin:add:{uid}:365",
            ),
        ],
        [
            InlineKeyboardButton(
                text="➖ Забрать подписку",
                callback_data=f"admin:revoke_user:{uid}",
            )
        ],
    ]

    if user.get("blocked"):
        rows.append(
            [
                InlineKeyboardButton(
                    text="🟢 Разблокировать",
                    callback_data=f"admin:unblock:{uid}",
                )
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🚫 Заблокировать",
                    callback_data=f"admin:block_user:{uid}",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ К пользователям",
                callback_data="admin:users:0",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


# ============================================================
# ADMIN MENU COMMAND
# ============================================================

@router.message(
    F.text.regexp(r"^/admin$")
)
async def admin_command(message: Message):

    if not is_admin(message.from_user.id):
        return

    admin_states.pop(message.from_user.id, None)

    await message.answer(
        f"🧲 <b>{SERVICE_NAME}</b>\n\n"
        f"⚙️ <b>Панель администратора</b>\n\n"
        f"Выберите действие:",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# CALLBACK — MENU
# ============================================================

@router.callback_query(
    F.data == "admin:menu"
)
async def admin_menu(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    admin_states.pop(
        callback.from_user.id,
        None,
    )

    await callback.message.edit_text(
        f"🧲 <b>{SERVICE_NAME}</b>\n\n"
        f"⚙️ <b>Панель администратора</b>\n\n"
        f"Выберите действие:",
        reply_markup=admin_keyboard(),
    )

    await callback.answer()


# ============================================================
# CALLBACK — NOOP
# ============================================================

@router.callback_query(
    F.data == "admin:noop"
)
async def admin_noop(callback: CallbackQuery):

    await callback.answer()


# ============================================================
# STATISTICS
# ============================================================

@router.callback_query(
    F.data == "admin:stats"
)
async def admin_stats(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    stats = get_stats()

    text = (
        f"📊 <b>СТАТИСТИКА {SERVICE_NAME}</b>\n\n"
        f"👥 Всего пользователей: "
        f"<b>{stats.get('total', 0)}</b>\n"
        f"🟢 Активных подписок: "
        f"<b>{stats.get('active', 0)}</b>\n"
        f"🚫 Заблокировано: "
        f"<b>{stats.get('blocked', 0)}</b>\n"
        f"🎁 Использовали пробник: "
        f"<b>{stats.get('trials', 0)}</b>\n\n"
        f"💳 Платежей: "
        f"<b>{stats.get('payments', 0)}</b>\n"
        f"⭐ Получено Stars: "
        f"<b>{stats.get('stars', 0)}</b>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
    )

    await callback.answer()


# ============================================================
# USERS
# ============================================================

@router.callback_query(
    F.data.startswith("admin:users:")
)
async def admin_users(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    try:
        page = int(
            callback.data.split(":")[2]
        )
    except Exception:
        page = 0

    users = get_all_users()

    text = (
        f"👥 <b>ПОЛЬЗОВАТЕЛИ</b>\n\n"
        f"Всего: <b>{len(users)}</b>\n\n"
        f"Выберите пользователя:"
    )

    await callback.message.edit_text(
        text,
        reply_markup=users_keyboard(page),
    )

    await callback.answer()


# ============================================================
# USER PROFILE
# ============================================================

@router.callback_query(
    F.data.startswith("admin:user:")
)
async def admin_user(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    try:
        uid = int(
            callback.data.split(":")[2]
        )
    except Exception:
        await callback.answer(
            "Ошибка ID",
            show_alert=True,
        )
        return

    user = get_user(uid)

    if not user:
        await callback.answer(
            "Пользователь не найден",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        format_user(user),
        reply_markup=user_keyboard(user),
    )

    await callback.answer()


# ============================================================
# ADD SUBSCRIPTION
# ============================================================

@router.callback_query(
    F.data.startswith("admin:add:")
)
async def admin_add_subscription(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    parts = callback.data.split(":")

    try:
        uid = int(parts[2])
        days = int(parts[3])
    except Exception:
        await callback.answer(
            "Ошибка данных",
            show_alert=True,
        )
        return

    user = get_user(uid)

    if not user:
        await callback.answer(
            "Пользователь не найден",
            show_alert=True,
        )
        return

    tariff_name = ""

    for key, tariff in TARIFFS.items():
        if tariff["days"] == days:
            tariff_name = tariff["title"]
            break

    updated = extend_subscription(
        uid,
        days,
        tariff=tariff_name,
    )

    if not updated:
        await callback.answer(
            "Не удалось изменить подписку",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        "✅ <b>Подписка выдана</b>\n\n"
        f"{format_user(updated)}",
        reply_markup=user_keyboard(updated),
    )

    await callback.answer(
        f"+{days} дней",
        show_alert=False,
    )


# ============================================================
# REVOKE FROM USER PROFILE
# ============================================================

@router.callback_query(
    F.data.startswith("admin:revoke_user:")
)
async def admin_revoke_user(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    try:
        uid = int(
            callback.data.split(":")[2]
        )
    except Exception:
        await callback.answer(
            "Ошибка ID",
            show_alert=True,
        )
        return

    user = get_user(uid)

    if not user:
        await callback.answer(
            "Пользователь не найден",
            show_alert=True,
        )
        return

    updated = revoke_subscription(uid)

    await callback.message.edit_text(
        "✅ <b>Подписка забрана</b>\n\n"
        f"{format_user(updated)}",
        reply_markup=user_keyboard(updated),
    )

    await callback.answer(
        "Подписка забрана",
    )


# ============================================================
# REVOKE MENU
# ============================================================

@router.callback_query(
    F.data == "admin:revoke"
)
async def admin_revoke_menu(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        "➖ <b>ЗАБРАТЬ ПОДПИСКУ</b>\n\n"
        "Выберите пользователя:",
        reply_markup=users_keyboard(0),
    )

    await callback.answer()


# ============================================================
# GIVE MENU
# ============================================================

@router.callback_query(
    F.data == "admin:give"
)
async def admin_give_menu(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        "➕ <b>ВЫДАТЬ ПОДПИСКУ</b>\n\n"
        "Выберите пользователя.\n\n"
        "После выбора можно будет "
        "одной кнопкой добавить срок.",
        reply_markup=users_keyboard(0),
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

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        "🚫 <b>БЛОКИРОВКА</b>\n\n"
        "Выберите пользователя:",
        reply_markup=users_keyboard(0),
    )

    await callback.answer()


# ============================================================
# BLOCK USER
# ============================================================

@router.callback_query(
    F.data.startswith("admin:block_user:")
)
async def admin_block_user(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    try:
        uid = int(
            callback.data.split(":")[2]
        )
    except Exception:
        await callback.answer(
            "Ошибка ID",
            show_alert=True,
        )
        return

    updated = set_blocked(
        uid,
        True,
    )

    if not updated:
        await callback.answer(
            "Пользователь не найден",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        "🚫 <b>Пользователь заблокирован</b>\n\n"
        f"{format_user(updated)}",
        reply_markup=user_keyboard(updated),
    )

    await callback.answer(
        "Заблокирован",
    )


# ============================================================
# UNBLOCK USER
# ============================================================

@router.callback_query(
    F.data.startswith("admin:unblock:")
)
async def admin_unblock_user(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    try:
        uid = int(
            callback.data.split(":")[2]
        )
    except Exception:
        await callback.answer(
            "Ошибка ID",
            show_alert=True,
        )
        return

    updated = set_blocked(
        uid,
        False,
    )

    if not updated:
        await callback.answer(
            "Пользователь не найден",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        "🟢 <b>Пользователь разблокирован</b>\n\n"
        f"{format_user(updated)}",
        reply_markup=user_keyboard(updated),
    )

    await callback.answer(
        "Разблокирован",
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

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    admin_states[
        callback.from_user.id
    ] = "find_user"

    await callback.message.edit_text(
        "🔎 <b>ПОИСК ПОЛЬЗОВАТЕЛЯ</b>\n\n"
        "Отправьте Telegram ID пользователя.\n\n"
        "Например:\n"
        "<code>6312016802</code>",
        reply_markup=back_keyboard(),
    )

    await callback.answer()


@router.message()
async def admin_text_handler(
    message: Message,
):

    uid = message.from_user.id

    if not is_admin(uid):
        return

    state = admin_states.get(uid)

    if not state:
        return

    # --------------------------------------------------------
    # FIND USER
    # --------------------------------------------------------

    if state == "find_user":

        text = (message.text or "").strip()

        if not text.isdigit():

            await message.answer(
                "❌ ID должен состоять только из цифр.\n\n"
                "Попробуйте ещё раз."
            )

            return

        target_id = int(text)

        user = get_user(target_id)

        admin_states.pop(uid, None)

        if not user:

            await message.answer(
                "❌ Пользователь не найден.",
                reply_markup=admin_keyboard(),
            )

            return

        await message.answer(
            format_user(user),
            reply_markup=user_keyboard(user),
        )

        return

    # --------------------------------------------------------
    # CREATE PROMO
    # --------------------------------------------------------

    if state == "promo_code":

        code = (
            message.text or ""
        ).strip().upper()

        if not code:

            await message.answer(
                "❌ Код не может быть пустым."
            )

            return

        admin_states[uid] = {
            "type": "promo_days",
            "code": code,
        }

        await message.answer(
            f"🎟 Код: <code>{code}</code>\n\n"
            "Теперь отправьте количество дней "
            "для промокода.\n\n"
            "Например: <code>30</code>"
        )

        return

    # --------------------------------------------------------
    # PROMO DAYS
    # --------------------------------------------------------

    if (
        isinstance(state, dict)
        and state.get("type") == "promo_days"
    ):

        text = (
            message.text or ""
        ).strip()

        if not text.isdigit():

            await message.answer(
                "❌ Количество дней должно быть числом."
            )

            return

        days = int(text)

        if days <= 0:

            await message.answer(
                "❌ Дни должны быть больше нуля."
            )

            return

        code = state["code"]

        try:
            create_promo(
                code,
                days,
                uses_left=0,
            )

            result = (
                "🎟 <b>Промокод создан</b>\n\n"
                f"Код: <code>{code}</code>\n"
                f"Дней: <b>{days}</b>\n"
                f"Использований: <b>∞</b>"
            )

        except Exception as e:

            result = (
                "❌ <b>Не удалось создать промокод</b>\n\n"
                f"<code>{safe_text(e)}</code>"
            )

        admin_states.pop(uid, None)

        await message.answer(
            result,
            reply_markup=admin_keyboard(),
        )

        return

    # --------------------------------------------------------
    # BROADCAST
    # --------------------------------------------------------

    if state == "broadcast":

        broadcast_text = (
            message.text or ""
        ).strip()

        admin_states.pop(uid, None)

        if not broadcast_text:

            await message.answer(
                "❌ Сообщение пустое.",
                reply_markup=admin_keyboard(),
            )

            return

        users = get_all_users()

        success = 0
        failed = 0

        await message.answer(
            f"📢 Начинаю рассылку...\n\n"
            f"Получателей: <b>{len(users)}</b>"
        )

        for user in users:

            target = user.get("user_id")

            if not target:
                continue

            if user.get("blocked"):
                continue

            try:

                await message.bot.send_message(
                    target,
                    broadcast_text,
                )

                success += 1

            except Exception:

                failed += 1

        await message.answer(
            "📢 <b>Рассылка завершена</b>\n\n"
            f"✅ Отправлено: <b>{success}</b>\n"
            f"❌ Ошибок: <b>{failed}</b>",
            reply_markup=admin_keyboard(),
        )

        return


# ============================================================
# PROMOCODES
# ============================================================

@router.callback_query(
    F.data == "admin:promos"
)
async def admin_promos(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Создать промокод",
                    callback_data="admin:create_promo",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="admin:menu",
                )
            ],
        ]
    )

    await callback.message.edit_text(
        "🎟 <b>ПРОМОКОДЫ</b>\n\n"
        "Создайте код и задайте количество дней.\n\n"
        "Например:\n"
        "<code>MAGNIT30</code> → 30 дней",
        reply_markup=keyboard,
    )

    await callback.answer()


# ============================================================
# CREATE PROMO
# ============================================================

@router.callback_query(
    F.data == "admin:create_promo"
)
async def admin_create_promo(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    admin_states[
        callback.from_user.id
    ] = "promo_code"

    await callback.message.edit_text(
        "🎟 <b>СОЗДАНИЕ ПРОМОКОДА</b>\n\n"
        "Отправьте код.\n\n"
        "Например:\n"
        "<code>MAGNIT30</code>",
        reply_markup=back_keyboard(),
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

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    admin_states[
        callback.from_user.id
    ] = "broadcast"

    await callback.message.edit_text(
        "📢 <b>РАССЫЛКА</b>\n\n"
        "Отправьте сообщение, которое нужно "
        "разослать пользователям.\n\n"
        "Поддерживается HTML-разметка Telegram.\n\n"
        "Например:\n"
        "<code>&lt;b&gt;Важная новость&lt;/b&gt;</code>",
        reply_markup=back_keyboard(),
    )

    await callback.answer()


# ============================================================
# SYNC
# ============================================================

@router.callback_query(
    F.data == "admin:sync"
)
async def admin_sync(
    callback: CallbackQuery,
):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Нет доступа",
            show_alert=True,
        )
        return

    await callback.answer(
        "🔄 Синхронизация запущена...",
    )

    try:

        result = force_sync()

        await callback.message.edit_text(
            "✅ <b>СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА</b>\n\n"
            f"Обновлено пользователей: "
            f"<b>{result.get('synced', 0) if isinstance(result, dict) else result}</b>",
            reply_markup=back_keyboard(),
        )

    except Exception as e:

        await callback.message.edit_text(
            "❌ <b>Ошибка синхронизации</b>\n\n"
            f"<code>{safe_text(e)}</code>",
            reply_markup=back_keyboard(),
        )


# ============================================================
# CLEANUP
# ============================================================

def clear_admin_state(user_id: int):
    admin_states.pop(user_id, None)