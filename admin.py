import asyncio
import html
import os
from datetime import datetime

from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import (
    ADMIN_ID,
    SERVICE_NAME,
)

from database import (
    get_user,
    get_all_users,
    get_stats,
    get_nodes,
    add_node,
    delete_node,
    create_promo,
    extend_subscription,
    block_user,
    get_devices,
    delete_device,
    set_device_limit,
)

from subscription import (
    sync_all_active_users,
    sync_servers_update,
)


# ============================================================
# НАСТРОЙКИ
# ============================================================

ADMIN_IDS = set()

try:
    if ADMIN_ID:
        ADMIN_IDS.add(int(ADMIN_ID))
except Exception:
    pass

# Можно добавить несколько админов через .env:
#
# ADMIN_IDS=123456789,987654321
#
env_admin_ids = os.getenv(
    "ADMIN_IDS",
    "",
).strip()

if env_admin_ids:

    for value in env_admin_ids.split(","):

        value = value.strip()

        if not value:
            continue

        try:
            ADMIN_IDS.add(int(value))
        except ValueError:
            pass


# ============================================================
# ADMIN CHECK
# ============================================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ============================================================
# HELPERS
# ============================================================

def format_date(value):

    if not value:
        return "—"

    try:

        dt = datetime.fromisoformat(
            str(value)
        )

        return dt.strftime(
            "%d.%m.%Y %H:%M"
        )

    except Exception:

        return str(value)


def safe(value):

    if value is None:
        return ""

    return html.escape(
        str(value)
    )


def admin_menu():

    kb = InlineKeyboardBuilder()

    kb.button(
        text="📊 Статистика",
        callback_data="adm:stats",
    )

    kb.button(
        text="👥 Пользователи",
        callback_data="adm:users",
    )

    kb.button(
        text="🔎 Найти пользователя",
        callback_data="adm:find",
    )

    kb.button(
        text="💳 Платежи",
        callback_data="adm:payments",
    )

    kb.button(
        text="🎟 Промокоды",
        callback_data="adm:promo",
    )

    kb.button(
        text="📡 Серверы",
        callback_data="adm:nodes",
    )

    kb.button(
        text="📱 Устройства",
        callback_data="adm:devices",
    )

    kb.button(
        text="🚫 Блокировка",
        callback_data="adm:block",
    )

    kb.button(
        text="🎁 Выдать подписку",
        callback_data="adm:give",
    )

    kb.button(
        text="📢 Рассылка",
        callback_data="adm:broadcast",
    )

    kb.button(
        text="🔄 Синхронизация",
        callback_data="adm:sync",
    )

    kb.button(
        text="⚙️ Настройки",
        callback_data="adm:settings",
    )

    kb.adjust(
        2,
        2,
        2,
        2,
        2,
        2,
    )

    return kb.as_markup()


def back_admin_keyboard():

    kb = InlineKeyboardBuilder()

    kb.button(
        text="⬅️ Админ-панель",
        callback_data="adm:home",
    )

    return kb.as_markup()


# ============================================================
# ADMIN HOME
# ============================================================

@dp.message(Command("admin"))
async def admin_command(
    message: Message,
):

    if not is_admin(
        message.from_user.id
    ):
        return

    await message.answer(
        f"👑 <b>{safe(SERVICE_NAME)}</b>\n\n"
        "Админ-панель\n\n"
        "Выбери раздел:",
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "adm:home")
async def admin_home(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    await call.message.edit_text(
        f"👑 <b>{safe(SERVICE_NAME)}</b>\n\n"
        "Админ-панель\n\n"
        "Выбери раздел:",
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )

    await call.answer()


# ============================================================
# STATISTICS
# ============================================================

@dp.callback_query(F.data == "adm:stats")
async def admin_stats(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    try:

        stats = get_stats()

        users = stats.get(
            "users",
            0,
        )

        active = stats.get(
            "active",
            0,
        )

        payments = stats.get(
            "payments",
            0,
        )

        stars = stats.get(
            "stars",
            0,
        )

        text = (
            "📊 <b>СТАТИСТИКА</b>\n\n"
            f"👥 Пользователей: "
            f"<b>{users}</b>\n"
            f"🟢 Активных: "
            f"<b>{active}</b>\n"
            f"💳 Платежей: "
            f"<b>{payments}</b>\n"
            f"⭐ Получено Stars: "
            f"<b>{stars}</b>\n"
        )

    except Exception as e:

        text = (
            "❌ <b>Ошибка статистики</b>\n\n"
            f"<code>{safe(e)}</code>"
        )

    await call.message.edit_text(
        text,
        reply_markup=back_admin_keyboard(),
        parse_mode="HTML",
    )

    await call.answer()


# ============================================================
# USERS
# ============================================================

@dp.callback_query(F.data == "adm:users")
async def admin_users(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    try:

        users = get_all_users()

    except Exception as e:

        await call.message.edit_text(
            f"❌ Ошибка:\n<code>{safe(e)}</code>",
            reply_markup=back_admin_keyboard(),
            parse_mode="HTML",
        )

        await call.answer()

        return

    text = (
        "👥 <b>ПОЛЬЗОВАТЕЛИ</b>\n\n"
        f"Всего: <b>{len(users)}</b>\n\n"
    )

    for user in users[:30]:

        user_id = user.get(
            "user_id",
            "—",
        )

        username = (
            user.get("username")
            or user.get("first_name")
            or "Без имени"
        )

        subscription = (
            user.get("subscription")
            or "none"
        )

        until = format_date(
            user.get(
                "subscription_until"
            )
        )

        text += (
            f"👤 <b>{safe(username)}</b>\n"
            f"🆔 <code>{user_id}</code>\n"
            f"📦 {safe(subscription)}\n"
            f"📅 {until}\n\n"
        )

    if len(users) > 30:

        text += (
            f"… и ещё "
            f"{len(users) - 30} пользователей."
        )

    await call.message.edit_text(
        text,
        reply_markup=back_admin_keyboard(),
        parse_mode="HTML",
    )

    await call.answer()


# ============================================================
# FIND USER
# ============================================================

@dp.callback_query(F.data == "adm:find")
async def admin_find_help(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    await call.message.answer(
        "🔎 <b>Поиск пользователя</b>\n\n"
        "Используй команду:\n"
        "<code>/user USER_ID</code>\n\n"
        "Например:\n"
        "<code>/user 123456789</code>",
        parse_mode="HTML",
    )

    await call.answer()


@dp.message(Command("user"))
async def admin_user(
    message: Message,
):

    if not is_admin(
        message.from_user.id
    ):
        return

    parts = message.text.split()

    if len(parts) != 2:

        await message.answer(
            "Использование:\n"
            "<code>/user USER_ID</code>",
            parse_mode="HTML",
        )

        return

    try:

        user_id = int(
            parts[1]
        )

    except ValueError:

        await message.answer(
            "❌ ID должен быть числом."
        )

        return

    user = get_user(
        user_id
    )

    if not user:

        await message.answer(
            "❌ Пользователь не найден."
        )

        return

    devices = get_devices(
        user_id
    )

    username = (
        user.get("username")
        or "—"
    )

    first_name = (
        user.get("first_name")
        or "—"
    )

    text = (
        "👤 <b>ПОЛЬЗОВАТЕЛЬ</b>\n\n"
        f"🆔 ID: "
        f"<code>{user_id}</code>\n"
        f"👤 Username: "
        f"<b>{safe(username)}</b>\n"
        f"📛 Имя: "
        f"{safe(first_name)}\n\n"
        f"📦 Подписка: "
        f"<b>{safe(user.get('subscription', 'none'))}</b>\n"
        f"📅 До: "
        f"<b>{format_date(user.get('subscription_until'))}</b>\n"
        f"📱 Устройства: "
        f"<b>{len(devices)}</b>/"
        f"<b>{user.get('device_limit', 1)}</b>\n"
        f"🚫 Заблокирован: "
        f"<b>{'Да' if user.get('blocked') else 'Нет'}</b>\n"
    )

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🎁 +30 дней",
        callback_data=f"adm:give30:{user_id}",
    )

    kb.button(
        text="🎁 +90 дней",
        callback_data=f"adm:give90:{user_id}",
    )

    kb.button(
        text="🚫 Заблокировать",
        callback_data=f"adm:blockuser:{user_id}",
    )

    kb.button(
        text="🔓 Разблокировать",
        callback_data=f"adm:unblockuser:{user_id}",
    )

    kb.button(
        text="📱 Устройства",
        callback_data=f"adm:userdevices:{user_id}",
    )

    kb.button(
        text="⬅️ Админ-панель",
        callback_data="adm:home",
    )

    kb.adjust(2, 2, 1, 1)

    await message.answer(
        text,
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )


# ============================================================
# GIVE SUBSCRIPTION
# ============================================================

@dp.callback_query(
    F.data.startswith("adm:give")
)
async def admin_give_buttons(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    parts = call.data.split(":")

    if len(parts) != 3:

        await call.answer(
            "Ошибка",
            show_alert=True,
        )

        return

    action = parts[1]

    try:

        user_id = int(parts[2])

    except ValueError:

        await call.answer(
            "Неверный ID",
            show_alert=True,
        )

        return

    if action == "give30":

        days = 30

    elif action == "give90":

        days = 90

    else:

        await call.answer(
            "Неизвестная команда",
            show_alert=True,
        )

        return

    user = get_user(
        user_id
    )

    if not user:

        await call.answer(
            "Пользователь не найден",
            show_alert=True,
        )

        return

    try:

        date = extend_subscription(
            user_id,
            days,
            "admin",
        )

        await call.answer(
            f"Выдано {days} дней",
        )

        await call.message.answer(
            "✅ <b>Подписка выдана</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"➕ Дней: <b>{days}</b>\n"
            f"📅 До: "
            f"<b>{format_date(date.isoformat())}</b>",
            parse_mode="HTML",
        )

    except Exception as e:

        await call.answer(
            "Ошибка",
            show_alert=True,
        )

        await call.message.answer(
            f"❌ <code>{safe(e)}</code>",
            parse_mode="HTML",
        )


@dp.callback_query(F.data == "adm:give")
async def admin_give_help(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    await call.message.answer(
        "🎁 <b>Выдать подписку</b>\n\n"
        "Команда:\n"
        "<code>/give USER_ID DAYS</code>\n\n"
        "Например:\n"
        "<code>/give 123456789 30</code>",
        parse_mode="HTML",
    )

    await call.answer()


@dp.message(Command("give"))
async def admin_give_command(
    message: Message,
):

    if not is_admin(
        message.from_user.id
    ):
        return

    parts = message.text.split()

    if len(parts) != 3:

        await message.answer(
            "Использование:\n"
            "<code>/give USER_ID DAYS</code>",
            parse_mode="HTML",
        )

        return

    try:

        user_id = int(parts[1])
        days = int(parts[2])

    except ValueError:

        await message.answer(
            "❌ ID и дни должны быть числами."
        )

        return

    if days <= 0:

        await message.answer(
            "❌ Количество дней должно быть больше 0."
        )

        return

    user = get_user(
        user_id
    )

    if not user:

        await message.answer(
            "❌ Пользователь не найден."
        )

        return

    try:

        date = extend_subscription(
            user_id,
            days,
            "admin",
        )

        await message.answer(
            "✅ <b>Подписка выдана</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"➕ Дней: <b>{days}</b>\n"
            f"📅 До: "
            f"<b>{format_date(date.isoformat())}</b>",
            parse_mode="HTML",
        )

    except Exception as e:

        await message.answer(
            f"❌ Ошибка:\n"
            f"<code>{safe(e)}</code>",
            parse_mode="HTML",
        )


# ============================================================
# BLOCK / UNBLOCK
# ============================================================

@dp.callback_query(F.data == "adm:block")
async def admin_block_help(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    await call.message.answer(
        "🚫 <b>Блокировка</b>\n\n"
        "<code>/block USER_ID</code>\n"
        "<code>/unblock USER_ID</code>",
        parse_mode="HTML",
    )

    await call.answer()


@dp.message(Command("block"))
async def admin_block_command(
    message: Message,
):

    if not is_admin(
        message.from_user.id
    ):
        return

    parts = message.text.split()

    if len(parts) != 2:

        await message.answer(
            "<code>/block USER_ID</code>",
            parse_mode="HTML",
        )

        return

    try:

        user_id = int(parts[1])

    except ValueError:

        await message.answer(
            "❌ Неверный ID."
        )

        return

    try:

        block_user(
            user_id,
            True,
        )

        await message.answer(
            f"🚫 Пользователь "
            f"<code>{user_id}</code> "
            f"заблокирован.",
            parse_mode="HTML",
        )

    except Exception as e:

        await message.answer(
            f"❌ <code>{safe(e)}</code>",
            parse_mode="HTML",
        )


@dp.message(Command("unblock"))
async def admin_unblock_command(
    message: Message,
):

    if not is_admin(
        message.from_user.id
    ):
        return

    parts = message.text.split()

    if len(parts) != 2:

        await message.answer(
            "<code>/unblock USER_ID</code>",
            parse_mode="HTML",
        )

        return

    try:

        user_id = int(parts[1])

    except ValueError:

        await message.answer(
            "❌ Неверный ID."
        )

        return

    try:

        block_user(
            user_id,
            False,
        )

        await message.answer(
            f"🔓 Пользователь "
            f"<code>{user_id}</code> "
            f"разблокирован.",
            parse_mode="HTML",
        )

    except Exception as e:

        await message.answer(
            f"❌ <code>{safe(e)}</code>",
            parse_mode="HTML",
        )


# ============================================================
# BLOCK USER BUTTON
# ============================================================

@dp.callback_query(
    F.data.startswith("adm:blockuser:")
)
async def admin_block_user_button(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    try:

        user_id = int(
            call.data.split(":")[-1]
        )

        block_user(
            user_id,
            True,
        )

        await call.answer(
            "Пользователь заблокирован",
            show_alert=True,
        )

    except Exception as e:

        await call.answer(
            f"Ошибка: {str(e)[:100]}",
            show_alert=True,
        )


@dp.callback_query(
    F.data.startswith("adm:unblockuser:")
)
async def admin_unblock_user_button(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    try:

        user_id = int(
            call.data.split(":")[-1]
        )

        block_user(
            user_id,
            False,
        )

        await call.answer(
            "Пользователь разблокирован",
            show_alert=True,
        )

    except Exception as e:

        await call.answer(
            f"Ошибка: {str(e)[:100]}",
            show_alert=True,
        )


# ============================================================
# SERVERS
# ============================================================

@dp.callback_query(F.data == "adm:nodes")
async def admin_nodes(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    try:

        nodes = get_nodes()

    except Exception as e:

        await call.message.edit_text(
            f"❌ Ошибка:\n"
            f"<code>{safe(e)}</code>",
            reply_markup=back_admin_keyboard(),
            parse_mode="HTML",
        )

        await call.answer()

        return

    text = (
        "📡 <b>VPN СЕРВЕРЫ</b>\n\n"
    )

    if not nodes:

        text += (
            "Серверов пока нет.\n\n"
        )

    for node in nodes:

        text += (
            f"🖥 <b>#{node['id']} "
            f"{safe(node['name'])}</b>\n"
            f"<code>{safe(node['vless_link'])}</code>\n\n"
        )

    text += (
        "➕ Добавить:\n"
        "<code>/addnode Название|VLESS</code>\n\n"
        "🗑 Удалить:\n"
        "<code>/delnode ID</code>"
    )

    await call.message.edit_text(
        text,
        reply_markup=back_admin_keyboard(),
        parse_mode="HTML",
    )

    await call.answer()


@dp.message(Command("addnode"))
async def admin_add_node(
    message: Message,
):

    if not is_admin(
        message.from_user.id
    ):
        return

    value = message.text[
        len("/addnode"):
    ].strip()

    if "|" not in value:

        await message.answer(
            "Формат:\n"
            "<code>/addnode Название|VLESS-ссылка</code>",
            parse_mode="HTML",
        )

        return

    name, link = value.split(
        "|",
        1,
    )

    name = name.strip()
    link = link.strip()

    if not name or not link:

        await message.answer(
            "❌ Название и VLESS-ссылка обязательны."
        )

        return

    try:

        node_id = add_node(
            name,
            link,
        )

        await message.answer(
            f"✅ Сервер добавлен.\n\n"
            f"🆔 ID: <code>{node_id}</code>\n"
            f"📡 {safe(name)}",
            parse_mode="HTML",
        )

    except Exception as e:

        await message.answer(
            f"❌ Ошибка:\n"
            f"<code>{safe(e)}</code>",
            parse_mode="HTML",
        )


@dp.message(Command("delnode"))
async def admin_delete_node(
    message: Message,
):

    if not is_admin(
        message.from_user.id
    ):
        return

    value = message.text[
        len("/delnode"):
    ].strip()

    try:

        node_id = int(value)

    except ValueError:

        await message.answer(
            "Использование:\n"
            "<code>/delnode ID</code>",
            parse_mode="HTML",
        )

        return

    try:

        delete_node(
            node_id
        )

        await message.answer(
            f"✅ Сервер "
            f"<code>{node_id}</code> удалён.",
            parse_mode="HTML",
        )

    except Exception as e:

        await message.answer(
            f"❌ Ошибка:\n"
            f"<code>{safe(e)}</code>",
            parse_mode="HTML",
        )


# ============================================================
# PROMOCODES
# ============================================================

@dp.callback_query(F.data == "adm:promo")
async def admin_promo(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    await call.message.edit_text(
        "🎟 <b>ПРОМОКОДЫ</b>\n\n"
        "Создание промокода:\n\n"
        "<code>/promo КОД ДНИ МАКС_АКТИВАЦИЙ</code>\n\n"
        "Пример:\n"
        "<code>/promo MAGNIT100 30 10</code>\n\n"
        "Где:\n"
        "• MAGNIT100 — код\n"
        "• 30 — дней\n"
        "• 10 — максимум активаций",
        reply_markup=back_admin_keyboard(),
        parse_mode="HTML",
    )

    await call.answer()


@dp.message(Command("promo"))
async def admin_create_promo(
    message: Message,
):

    if not is_admin(
        message.from_user.id
    ):
        return

    parts = message.text.split()

    if len(parts) != 4:

        await message.answer(
            "Формат:\n"
            "<code>/promo КОД ДНИ МАКС_АКТИВАЦИЙ</code>",
            parse_mode="HTML",
        )

        return

    _, code, days, max_uses = parts

    try:

        days = int(days)
        max_uses = int(max_uses)

    except ValueError:

        await message.answer(
            "❌ Дни и количество активаций "
            "должны быть числами."
        )

        return

    if days <= 0 or max_uses <= 0:

        await message.answer(
            "❌ Значения должны быть больше 0."
        )

        return

    try:

        success = create_promo(
            code.upper(),
            days,
            max_uses,
        )

        if success:

            await message.answer(
                "✅ <b>Промокод создан!</b>\n\n"
                f"🎟 Код: "
                f"<code>{safe(code.upper())}</code>\n"
                f"➕ Дней: <b>{days}</b>\n"
                f"🔢 Активаций: <b>{max_uses}</b>",
                parse_mode="HTML",
            )

        else:

            await message.answer(
                "❌ Такой промокод уже существует."
            )

    except Exception as e:

        await message.answer(
            f"❌ Ошибка:\n"
            f"<code>{safe(e)}</code>",
            parse_mode="HTML",
        )


# ============================================================
# DEVICES
# ============================================================

@dp.callback_query(F.data == "adm:devices")
async def admin_devices(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    users = get_all_users()

    total_devices = 0

    users_with_devices = 0

    for user in users:

        try:

            items = get_devices(
                user["user_id"]
            )

            if items:

                users_with_devices += 1
                total_devices += len(items)

        except Exception:
            pass

    text = (
        "📱 <b>УСТРОЙСТВА</b>\n\n"
        f"👥 Пользователей: "
        f"<b>{len(users)}</b>\n"
        f"📱 Всего устройств: "
        f"<b>{total_devices}</b>\n"
        f"👤 С устройствами: "
        f"<b>{users_with_devices}</b>\n\n"
        "Для просмотра устройств пользователя:\n"
        "<code>/user USER_ID</code>"
    )

    await call.message.edit_text(
        text,
        reply_markup=back_admin_keyboard(),
        parse_mode="HTML",
    )

    await call.answer()


# ============================================================
# USER DEVICES
# ============================================================

@dp.callback_query(
    F.data.startswith("adm:userdevices:")
)
async def admin_user_devices(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    try:

        user_id = int(
            call.data.split(":")[-1]
        )

    except ValueError:

        await call.answer(
            "Неверный ID",
            show_alert=True,
        )

        return

    try:

        items = get_devices(
            user_id
        )

    except Exception as e:

        await call.answer(
            "Ошибка",
            show_alert=True,
        )

        await call.message.answer(
            f"❌ <code>{safe(e)}</code>",
            parse_mode="HTML",
        )

        return

    text = (
        "📱 <b>УСТРОЙСТВА</b>\n\n"
        f"🆔 Пользователь: "
        f"<code>{user_id}</code>\n"
        f"Количество: <b>{len(items)}</b>\n\n"
    )

    if not items:

        text += "Устройств нет."

    else:

        for index, device in enumerate(
            items,
            start=1,
        ):

            text += (
                f"{index}. "
                f"<b>{safe(device.get('device_name') or 'Устройство')}</b>\n"
                f"ID: <code>{safe(device.get('device_id'))}</code>\n\n"
            )

    kb = InlineKeyboardBuilder()

    for device in items:

        device_id = device.get(
            "device_id"
        )

        kb.button(
            text=(
                f"❌ {str(device_id)[:12]}"
            ),
            callback_data=(
                f"adm:deldevice:"
                f"{user_id}:"
                f"{device_id}"
            ),
        )

    kb.button(
        text="⬅️ Назад",
        callback_data="adm:home",
    )

    kb.adjust(1)

    await call.message.answer(
        text,
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )

    await call.answer()


@dp.callback_query(
    F.data.startswith("adm:deldevice:")
)
async def admin_delete_device(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    parts = call.data.split(
        ":",
        3,
    )

    if len(parts) != 4:

        await call.answer(
            "Ошибка",
            show_alert=True,
        )

        return

    try:

        user_id = int(parts[2])

    except ValueError:

        await call.answer(
            "Неверный ID",
            show_alert=True,
        )

        return

    device_id = parts[3]

    try:

        delete_device(
            user_id,
            device_id,
        )

        await call.answer(
            "Устройство удалено",
            show_alert=True,
        )

    except Exception as e:

        await call.answer(
            f"Ошибка: {str(e)[:80]}",
            show_alert=True,
        )


# ============================================================
# PAYMENTS
# ============================================================

@dp.callback_query(F.data == "adm:payments")
async def admin_payments(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    try:

        stats = get_stats()

        text = (
            "💳 <b>ПЛАТЕЖИ</b>\n\n"
            f"💳 Всего платежей: "
            f"<b>{stats.get('payments', 0)}</b>\n"
            f"⭐ Получено Stars: "
            f"<b>{stats.get('stars', 0)}</b>\n\n"
            "Подробные платежи доступны "
            "через базу данных.\n\n"
            "В следующей версии сюда можно "
            "добавить полноценный журнал "
            "платежей с фильтрами."
        )

    except Exception as e:

        text = (
            "❌ Ошибка:\n"
            f"<code>{safe(e)}</code>"
        )

    await call.message.edit_text(
        text,
        reply_markup=back_admin_keyboard(),
        parse_mode="HTML",
    )

    await call.answer()


# ============================================================
# SYNCHRONIZATION
# ============================================================

@dp.callback_query(F.data == "adm:sync")
async def admin_sync(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    kb = InlineKeyboardBuilder()

    kb.button(
        text="🔄 Синхронизировать подписки",
        callback_data="adm:sync_subs",
    )

    kb.button(
        text="📡 Обновить серверы",
        callback_data="adm:sync_servers",
    )

    kb.button(
        text="⬅️ Назад",
        callback_data="adm:home",
    )

    kb.adjust(1)

    await call.message.edit_text(
        "🔄 <b>СИНХРОНИЗАЦИЯ</b>\n\n"
        "Выбери действие:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )

    await call.answer()


@dp.callback_query(F.data == "adm:sync_subs")
async def admin_sync_subscriptions(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    await call.answer(
        "Синхронизация запущена..."
    )

    try:

        result = await asyncio.to_thread(
            sync_all_active_users
        )

        await call.message.answer(
            "✅ <b>Синхронизация завершена</b>\n\n"
            f"🟢 Обновлено: "
            f"<b>{result.get('updated', 0)}</b>\n"
            f"🔴 Истекло: "
            f"<b>{result.get('expired', 0)}</b>\n"
            f"⚪ Пропущено: "
            f"<b>{result.get('skipped', 0)}</b>\n"
            f"❌ Ошибок: "
            f"<b>{result.get('errors', 0)}</b>",
            parse_mode="HTML",
        )

    except Exception as e:

        await call.message.answer(
            "❌ <b>Ошибка синхронизации</b>\n\n"
            f"<code>{safe(e)}</code>",
            parse_mode="HTML",
        )


@dp.callback_query(F.data == "adm:sync_servers")
async def admin_sync_servers(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    await call.answer(
        "Обновление серверов..."
    )

    try:

        result = await asyncio.to_thread(
            sync_servers_update
        )

        await call.message.answer(
            "✅ <b>Серверы обновлены</b>\n\n"
            f"🟢 Обновлено: "
            f"<b>{result.get('updated', 0)}</b>\n"
            f"🔴 Истекло: "
            f"<b>{result.get('expired', 0)}</b>\n"
            f"⚪ Пропущено: "
            f"<b>{result.get('skipped', 0)}</b>\n"
            f"❌ Ошибок: "
            f"<b>{result.get('errors', 0)}</b>",
            parse_mode="HTML",
        )

    except Exception as e:

        await call.message.answer(
            "❌ <b>Ошибка</b>\n\n"
            f"<code>{safe(e)}</code>",
            parse_mode="HTML",
        )


# ============================================================
# SETTINGS
# ============================================================

@dp.callback_query(F.data == "adm:settings")
async def admin_settings(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    admin_list = ", ".join(
        str(x)
        for x in sorted(ADMIN_IDS)
    )

    text = (
        "⚙️ <b>НАСТРОЙКИ</b>\n\n"
        f"🧲 Сервис: "
        f"<b>{safe(SERVICE_NAME)}</b>\n"
        f"👑 Admin ID: "
        f"<code>{safe(admin_list)}</code>\n\n"
        "Секретные данные не отображаются.\n"
        "Токены и ключи должны находиться "
        "в .env."
    )

    await call.message.edit_text(
        text,
        reply_markup=back_admin_keyboard(),
        parse_mode="HTML",
    )

    await call.answer()


# ============================================================
# BROADCAST
# ============================================================

@dp.callback_query(F.data == "adm:broadcast")
async def admin_broadcast(
    call: CallbackQuery,
):

    if not is_admin(
        call.from_user.id
    ):
        return

    await call.message.answer(
        "📢 <b>РАССЫЛКА</b>\n\n"
        "Использование:\n"
        "<code>/broadcast Текст сообщения</code>\n\n"
        "Сообщение будет отправлено "
        "всем пользователям из базы.",
        parse_mode="HTML",
    )

    await call.answer()


@dp.message(Command("broadcast"))
async def admin_broadcast_command(
    message: Message,
):

    if not is_admin(
        message.from_user.id
    ):
        return

    text = message.text[
        len("/broadcast"):
    ].strip()

    if not text:

        await message.answer(
            "❌ Напиши текст после команды.\n\n"
            "<code>/broadcast Привет!</code>",
            parse_mode="HTML",
        )

        return

    try:

        users = get_all_users()

    except Exception as e:

        await message.answer(
            f"❌ Ошибка базы:\n"
            f"<code>{safe(e)}</code>",
            parse_mode="HTML",
        )

        return

    sent = 0
    failed = 0

    status = await message.answer(
        "📢 Рассылка запущена...\n"
        "⏳ Подготавливаю пользователей."
    )

    for user in users:

        user_id = user.get(
            "user_id"
        )

        if not user_id:
            continue

        try:

            await message.bot.send_message(
                chat_id=user_id,
                text=text,
            )

            sent += 1

        except Exception:

            failed += 1

        await asyncio.sleep(
            0.05
        )

    await status.edit_text(
        "📢 <b>Рассылка завершена</b>\n\n"
        f"✅ Отправлено: <b>{sent}</b>\n"
        f"❌ Ошибок: <b>{failed}</b>",
        parse_mode="HTML",
    )


# ============================================================
# COMMAND: ADMIN HELP
# ============================================================

@dp.message(Command("adminhelp"))
async def admin_help(
    message: Message,
):

    if not is_admin(
        message.from_user.id
    ):
        return

    await message.answer(
        "👑 <b>КОМАНДЫ АДМИНИСТРАТОРА</b>\n\n"
        "🏠 <code>/admin</code> — панель\n"
        "👤 <code>/user ID</code> — пользователь\n"
        "🎁 <code>/give ID DAYS</code> — выдать дни\n"
        "🚫 <code>/block ID</code> — блокировка\n"
        "🔓 <code>/unblock ID</code> — разблокировка\n"
        "📡 <code>/addnode NAME|VLESS</code> — сервер\n"
        "🗑 <code>/delnode ID</code> — удалить сервер\n"
        "🎟 <code>/promo CODE DAYS USES</code> — промокод\n"
        "📢 <code>/broadcast TEXT</code> — рассылка\n\n"
        "Все остальные функции находятся "
        "в кнопочной админ-панели.",
        parse_mode="HTML",
    )