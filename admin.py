import asyncio
import os
from datetime import datetime

from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_ID, SERVICE_NAME

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

from subscription import sync_all_active_users


# ============================================================
# ADMIN IDS
# ============================================================

ADMIN_IDS = set()

try:
    if ADMIN_ID:
        ADMIN_IDS.add(int(ADMIN_ID))
except Exception:
    pass

for value in os.getenv("ADMIN_IDS", "").split(","):
    value = value.strip()

    if value:
        try:
            ADMIN_IDS.add(int(value))
        except ValueError:
            pass


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ============================================================
# HELPERS
# ============================================================

def value(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)

    try:
        return obj[key]
    except Exception:
        return default


def fmt_date(value_):
    if not value_:
        return "—"

    try:
        return datetime.fromisoformat(
            str(value_)
        ).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(value_)


def admin_keyboard():

    kb = InlineKeyboardBuilder()

    kb.button(
        text="📊 Статистика",
        callback_data="admin:stats",
    )

    kb.button(
        text="👥 Пользователи",
        callback_data="admin:users",
    )

    kb.button(
        text="🔎 Найти пользователя",
        callback_data="admin:find",
    )

    kb.button(
        text="🎁 Выдать подписку",
        callback_data="admin:give",
    )

    kb.button(
        text="📱 Устройства",
        callback_data="admin:devices",
    )

    kb.button(
        text="📡 Серверы",
        callback_data="admin:nodes",
    )

    kb.button(
        text="🎟 Промокоды",
        callback_data="admin:promo",
    )

    kb.button(
        text="🚫 Блокировка",
        callback_data="admin:block",
    )

    kb.button(
        text="📢 Рассылка",
        callback_data="admin:broadcast",
    )

    kb.button(
        text="🔄 Синхронизация",
        callback_data="admin:sync",
    )

    kb.adjust(
        2,
        2,
        2,
        2,
        2,
        1,
    )

    return kb.as_markup()


def back_keyboard():

    kb = InlineKeyboardBuilder()

    kb.button(
        text="⬅️ Админ-панель",
        callback_data="admin:home",
    )

    return kb.as_markup()


# ============================================================
# REGISTER
# ============================================================

def register_admin_handlers(dp):

    # ========================================================
    # ADMIN
    # ========================================================

    @dp.message(Command("admin"))
    async def admin_command(message: Message):

        if not is_admin(message.from_user.id):
            return

        await message.answer(
            f"👑 <b>{SERVICE_NAME}</b>\n\n"
            "Админ-панель\n\n"
            "Выберите раздел:",
            reply_markup=admin_keyboard(),
            parse_mode="HTML",
        )


    # ========================================================
    # HOME
    # ========================================================

    @dp.callback_query(F.data == "admin:home")
    async def admin_home(call: CallbackQuery):

        if not is_admin(call.from_user.id):
            return

        await call.message.edit_text(
            f"👑 <b>{SERVICE_NAME}</b>\n\n"
            "Админ-панель\n\n"
            "Выберите раздел:",
            reply_markup=admin_keyboard(),
            parse_mode="HTML",
        )

        await call.answer()


    # ========================================================
    # STATS
    # ========================================================

    @dp.callback_query(F.data == "admin:stats")
    async def admin_stats(call: CallbackQuery):

        if not is_admin(call.from_user.id):
            return

        try:
            stats = get_stats()

            if isinstance(stats, dict):

                text = (
                    "📊 <b>СТАТИСТИКА</b>\n\n"
                    f"👥 Пользователей: "
                    f"<b>{stats.get('users', 0)}</b>\n"
                    f"🟢 Активных: "
                    f"<b>{stats.get('active', 0)}</b>\n"
                    f"💳 Платежей: "
                    f"<b>{stats.get('payments', 0)}</b>\n"
                    f"⭐ Stars: "
                    f"<b>{stats.get('stars', 0)}</b>"
                )

            else:

                text = (
                    "📊 <b>СТАТИСТИКА</b>\n\n"
                    f"<code>{stats}</code>"
                )

        except Exception as e:

            text = (
                "❌ Ошибка статистики:\n\n"
                f"<code>{e}</code>"
            )

        await call.message.edit_text(
            text,
            reply_markup=back_keyboard(),
            parse_mode="HTML",
        )

        await call.answer()


    # ========================================================
    # USERS
    # ========================================================

    @dp.callback_query(F.data == "admin:users")
    async def admin_users(call: CallbackQuery):

        if not is_admin(call.from_user.id):
            return

        try:
            users = get_all_users()

            text = (
                "👥 <b>ПОЛЬЗОВАТЕЛИ</b>\n\n"
                f"Всего: <b>{len(users)}</b>\n\n"
            )

            for user in users[:30]:

                user_id = value(
                    user,
                    "user_id",
                    "—",
                )

                username = (
                    value(
                        user,
                        "username",
                        None,
                    )
                    or value(
                        user,
                        "first_name",
                        None,
                    )
                    or "Без имени"
                )

                subscription = value(
                    user,
                    "subscription",
                    "none",
                )

                until = value(
                    user,
                    "subscription_until",
                    "",
                )

                text += (
                    f"👤 <b>{username}</b>\n"
                    f"🆔 <code>{user_id}</code>\n"
                    f"📦 {subscription}\n"
                    f"📅 {fmt_date(until)}\n\n"
                )

            if len(users) > 30:
                text += (
                    f"Показаны первые 30 "
                    f"из {len(users)}."
                )

        except Exception as e:

            text = (
                "❌ Ошибка:\n"
                f"<code>{e}</code>"
            )

        await call.message.edit_text(
            text,
            reply_markup=back_keyboard(),
            parse_mode="HTML",
        )

        await call.answer()


    # ========================================================
    # FIND USER
    # ========================================================

    @dp.callback_query(F.data == "admin:find")
    async def admin_find(call: CallbackQuery):

        if not is_admin(call.from_user.id):
            return

        await call.message.answer(
            "🔎 <b>Поиск пользователя</b>\n\n"
            "Используйте:\n"
            "<code>/user ID</code>\n\n"
            "Например:\n"
            "<code>/user 123456789</code>",
            parse_mode="HTML",
        )

        await call.answer()


    @dp.message(Command("user"))
    async def admin_user(message: Message):

        if not is_admin(message.from_user.id):
            return

        parts = message.text.split()

        if len(parts) != 2:

            await message.answer(
                "Использование:\n"
                "<code>/user ID</code>",
                parse_mode="HTML",
            )

            return

        try:
            user_id = int(parts[1])
        except ValueError:

            await message.answer(
                "❌ ID должен быть числом."
            )

            return

        user = get_user(user_id)

        if not user:

            await message.answer(
                "❌ Пользователь не найден."
            )

            return

        devices = get_devices(user_id)

        username = (
            value(user, "username")
            or "—"
        )

        first_name = (
            value(user, "first_name")
            or "—"
        )

        subscription = value(
            user,
            "subscription",
            "none",
        )

        until = value(
            user,
            "subscription_until",
            "",
        )

        device_limit = value(
            user,
            "device_limit",
            1,
        )

        text = (
            "👤 <b>ПОЛЬЗОВАТЕЛЬ</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"👤 Username: <b>{username}</b>\n"
            f"📛 Имя: {first_name}\n\n"
            f"📦 Подписка: <b>{subscription}</b>\n"
            f"📅 До: <b>{fmt_date(until)}</b>\n"
            f"📱 Устройства: "
            f"<b>{len(devices)}</b>/"
            f"<b>{device_limit}</b>"
        )

        kb = InlineKeyboardBuilder()

        kb.button(
            text="🎁 +30 дней",
            callback_data=f"admin:give30:{user_id}",
        )

        kb.button(
            text="🎁 +90 дней",
            callback_data=f"admin:give90:{user_id}",
        )

        kb.button(
            text="📱 Устройства",
            callback_data=f"admin:userdevices:{user_id}",
        )

        kb.button(
            text="⬅️ Админ-панель",
            callback_data="admin:home",
        )

        kb.adjust(2, 1, 1)

        await message.answer(
            text,
            reply_markup=kb.as_markup(),
            parse_mode="HTML",
        )


    # ========================================================
    # GIVE
    # ========================================================

    @dp.callback_query(F.data == "admin:give")
    async def admin_give(call: CallbackQuery):

        if not is_admin(call.from_user.id):
            return

        await call.message.answer(
            "🎁 <b>Выдача подписки</b>\n\n"
            "Используйте:\n"
            "<code>/give ID DAYS</code>\n\n"
            "Например:\n"
            "<code>/give 123456789 30</code>",
            parse_mode="HTML",
        )

        await call.answer()


    @dp.message(Command("give"))
    async def give_command(message: Message):

        if not is_admin(message.from_user.id):
            return

        parts = message.text.split()

        if len(parts) != 3:

            await message.answer(
                "Использование:\n"
                "<code>/give ID DAYS</code>",
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

        user = get_user(user_id)

        if not user:

            await message.answer(
                "❌ Пользователь не найден."
            )

            return

        try:

            new_date = extend_subscription(
                user_id,
                days,
                "admin",
            )

            await message.answer(
                "✅ <b>Подписка выдана</b>\n\n"
                f"🆔 <code>{user_id}</code>\n"
                f"➕ Дней: <b>{days}</b>\n"
                f"📅 До: "
                f"<b>{fmt_date(new_date)}</b>",
                parse_mode="HTML",
            )

        except Exception as e:

            await message.answer(
                f"❌ Ошибка:\n"
                f"<code>{e}</code>",
                parse_mode="HTML",
            )


    @dp.callback_query(
        F.data.startswith("admin:give30:")
    )
    async def give30(call: CallbackQuery):

        if not is_admin(call.from_user.id):
            return

        user_id = int(
            call.data.split(":")[-1]
        )

        try:

            new_date = extend_subscription(
                user_id,
                30,
                "admin",
            )

            await call.answer(
                "✅ Выдано 30 дней",
                show_alert=True,
            )

            await call.message.answer(
                f"🎁 Пользователю "
                f"<code>{user_id}</code> "
                f"выдано <b>30 дней</b>.\n"
                f"📅 До: "
                f"<b>{fmt_date(new_date)}</b>",
                parse_mode="HTML",
            )

        except Exception as e:

            await call.answer(
                f"Ошибка: {str(e)[:100]}",
                show_alert=True,
            )


    @dp.callback_query(
        F.data.startswith("admin:give90:")
    )
    async def give90(call: CallbackQuery):

        if not is_admin(call.from_user.id):
            return

        user_id = int(
            call.data.split(":")[-1]
        )

        try:

            new_date = extend_subscription(
                user_id,
                90,
                "admin",
            )

            await call.answer(
                "✅ Выдано 90 дней",
                show_alert=True,
            )

            await call.message.answer(
                f"🎁 Пользователю "
                f"<code>{user_id}</code> "
                f"выдано <b>90 дней</b>.\n"
                f"📅 До: "
                f"<b>{fmt_date(new_date)}</b>",
                parse_mode="HTML",
            )

        except Exception as e:

            await call.answer(
                f"Ошибка: {str(e)[:100]}",
                show_alert=True,
            )


    # ========================================================
    # DEVICES
    # ========================================================

    @dp.callback_query(F.data == "admin:devices")
    async def admin_devices(call: CallbackQuery):

        if not is_admin(call.from_user.id):
            return

        try:

            users = get_all_users()

            total = 0

            with_devices = 0

            for user in users:

                user_id = value(
                    user,
                    "user_id",
                )

                if not user_id:
                    continue

                try:

                    items = get_devices(
                        user_id
                    )

                    if items:
                        with_devices += 1
                        total += len(items)

                except Exception:
                    pass

            text = (
                "📱 <b>УСТРОЙСТВА</b>\n\n"
                f"📱 Всего устройств: "
                f"<b>{total}</b>\n"
                f"👥 Пользователей с устройствами: "
                f"<b>{with_devices}</b>\n\n"
                "Для конкретного пользователя:\n"
                "<code>/user ID</code>"
            )

        except Exception as e:

            text = (
                f"❌ Ошибка:\n"
                f"<code>{e}</code>"
            )

        await call.message.edit_text(
            text,
            reply_markup=back_keyboard(),
            parse_mode="HTML",
        )

        await call.answer()


    # ========================================================
    # USER DEVICES
    # ========================================================

    @dp.callback_query(
        F.data.startswith("admin:userdevices:")
    )
    async def user_devices(call: CallbackQuery):

        if not is_admin(call.from_user.id):
            return

        user_id = int(
            call.data.split(":")[-1]
        )

        try:

            items = get_devices(
                user_id
            )

            text = (
                "📱 <b>УСТРОЙСТВА</b>\n\n"
                f"🆔 Пользователь: "
                f"<code>{user_id}</code>\n"
                f"Количество: "
                f"<b>{len(items)}</b>\n\n"
            )

            if not items:

                text += "Устройств нет."

            else:

                for i, device in enumerate(
                    items,
                    1,
                ):

                    name = value(
                        device,
                        "device_name",
                        "Устройство",
                    )

                    device_id = value(
                        device,
                        "device_id",
                        "",
                    )

                    text += (
                        f"{i}. <b>{name}</b>\n"
                        f"ID: <code>{device_id}</code>\n\n"
                    )

            kb = InlineKeyboardBuilder()

            for device in items:

                device_id = value(
                    device,
                    "device_id",
                    "",
                )

                kb.button(
                    text=f"❌ {str(device_id)[:10]}",
                    callback_data=(
                        f"admin:deldevice:"
                        f"{user_id}:"
                        f"{device_id}"
                    ),
                )

            kb.button(
                text="⬅️ Назад",
                callback_data="admin:home",
            )

            kb.adjust(1)

            await call.message.answer(
                text,
                reply_markup=kb.as_markup(),
                parse_mode="HTML",
            )

        except Exception as e:

            await call.message.answer(
                f"❌ Ошибка:\n"
                f"<code>{e}</code>",
                parse_mode="HTML",
            )

        await call.answer()


    # ========================================================
    # DELETE DEVICE
    # ========================================================

    @dp.callback_query(
        F.data.startswith("admin:deldevice:")
    )
    async def admin_delete_device(
        call: CallbackQuery,
    ):

        if not is_admin(call.from_user.id):
            return

        parts = call.data.split(":", 3)

        if len(parts) != 4:
            await call.answer("Ошибка")
            return

        user_id = int(parts[2])
        device_id = parts[3]

        try:

            delete_device(
                user_id,
                device_id,
            )

            await call.answer(
                "✅ Устройство удалено",
                show_alert=True,
            )

        except Exception as e:

            await call.answer(
                f"Ошибка: {str(e)[:100]}",
                show_alert=True,
            )


    # ========================================================
    # SERVERS
    # ========================================================

    @dp.callback_query(F.data == "admin:nodes")
    async def admin_nodes(call: CallbackQuery):

        if not is_admin(call.from_user.id):
            return

        try:

            nodes = get_nodes()

            text = (
                "📡 <b>VPN СЕРВЕРЫ</b>\n\n"
            )

            if not nodes:

                text += "Серверов нет."

            else:

                for node in nodes:

                    node_id = value(
                        node,
                        "id",
                        "—",
                    )

                    name = value(
                        node,
                        "name",
                        "Без названия",
                    )

                    text += (
                        f"🖥 <b>#{node_id} "
                        f"{name}</b>\n"
                        f"<code>"
                        f"{value(node, 'vless_link', '')}"
                        f"</code>\n\n"
                    )

            text += (
                "\n➕ Добавить:\n"
                "<code>/addnode Название|VLESS</code>\n\n"
                "🗑 Удалить:\n"
                "<code>/delnode ID</code>"
            )

        except Exception as e:

            text = (
                f"❌ Ошибка:\n"
                f"<code>{e}</code>"
            )

        await call.message.edit_text(
            text,
            reply_markup=back_keyboard(),
            parse_mode="HTML",
        )

        await call.answer()


    @dp.message(Command("addnode"))
    async def admin_addnode(
        message: Message,
    ):

        if not is_admin(message.from_user.id):
            return

        data = message.text[
            len("/addnode"):
        ].strip()

        if "|" not in data:

            await message.answer(
                "Формат:\n"
                "<code>/addnode Название|VLESS</code>",
                parse_mode="HTML",
            )

            return

        name, link = data.split(
            "|",
            1,
        )

        try:

            node_id = add_node(
                name.strip(),
                link.strip(),
            )

            await message.answer(
                "✅ <b>Сервер добавлен</b>\n\n"
                f"🆔 ID: <code>{node_id}</code>\n"
                f"📡 {name.strip()}",
                parse_mode="HTML",
            )

        except Exception as e:

            await message.answer(
                f"❌ Ошибка:\n"
                f"<code>{e}</code>",
                parse_mode="HTML",
            )


    @dp.message(Command("delnode"))
    async def admin_delnode(
        message: Message,
    ):

        if not is_admin(message.from_user.id):
            return

        data = message.text[
            len("/delnode"):
        ].strip()

        try:

            node_id = int(data)

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
                f"<code>{e}</code>",
                parse_mode="HTML",
            )


    # ========================================================
    # PROMO
    # ========================================================

    @dp.callback_query(F.data == "admin:promo")
    async def admin_promo(call: CallbackQuery):

        if not is_admin(call.from_user.id):
            return

        await call.message.edit_text(
            "🎟 <b>ПРОМОКОДЫ</b>\n\n"
            "Создать:\n"
            "<code>/promo КОД ДНИ</code>\n\n"
            "Пример:\n"
            "<code>/promo MAGNIT100 30</code>",
            reply_markup=back_keyboard(),
            parse_mode="HTML",
        )

        await call.answer()


    @dp.message(Command("promo"))
    async def admin_promo_command(
        message: Message,
    ):

        if not is_admin(message.from_user.id):
            return

        parts = message.text.split()

        if len(parts) != 3:

            await message.answer(
                "Формат:\n"
                "<code>/promo КОД ДНИ</code>",
                parse_mode="HTML",
            )

            return

        code = parts[1].upper()

        try:
            days = int(parts[2])
        except ValueError:

            await message.answer(
                "❌ Дни должны быть числом."
            )

            return

        try:

            result = create_promo(
                code,
                days,
            )

            await message.answer(
                "🎟 <b>Промокод создан</b>\n\n"
                f"Код: <code>{code}</code>\n"
                f"Дней: <b>{days}</b>\n\n"
                f"Результат: <code>{result}</code>",
                parse_mode="HTML",
            )

        except Exception as e:

            await message.answer(
                f"❌ Ошибка:\n"
                f"<code>{e}</code>",
                parse_mode="HTML",
            )


    # ========================================================
    # BLOCK
    # ========================================================

    @dp.callback_query(F.data == "admin:block")
    async def admin_block_help(
        call: CallbackQuery,
    ):

        if not is_admin(call.from_user.id):
            return

        await call.message.answer(
            "🚫 <b>Блокировка</b>\n\n"
            "<code>/block ID</code> — заблокировать\n"
            "<code>/unblock ID</code> — разблокировать",
            parse_mode="HTML",
        )

        await call.answer()


    @dp.message(Command("block"))
    async def admin_block_command(
        message: Message,
    ):

        if not is_admin(message.from_user.id):
            return

        parts = message.text.split()

        if len(parts) != 2:

            await message.answer(
                "<code>/block ID</code>",
                parse_mode="HTML",
            )

            return

        try:

            user_id = int(parts[1])

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
                f"❌ Ошибка:\n"
                f"<code>{e}</code>",
                parse_mode="HTML",
            )


    @dp.message(Command("unblock"))
    async def admin_unblock_command(
        message: Message,
    ):

        if not is_admin(message.from_user.id):
            return

        parts = message.text.split()

        if len(parts) != 2:

            await message.answer(
                "<code>/unblock ID</code>",
                parse_mode="HTML",
            )

            return

        try:

            user_id = int(parts[1])

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
                f"❌ Ошибка:\n"
                f"<code>{e}</code>",
                parse_mode="HTML",
            )


    # ========================================================
    # BROADCAST
    # ========================================================

    @dp.callback_query(F.data == "admin:broadcast")
    async def admin_broadcast(
        call: CallbackQuery,
    ):

        if not is_admin(call.from_user.id):
            return

        await call.message.answer(
            "📢 <b>РАССЫЛКА</b>\n\n"
            "Используйте:\n"
            "<code>/broadcast Текст</code>",
            parse_mode="HTML",
        )

        await call.answer()


    @dp.message(Command("broadcast"))
    async def broadcast_command(
        message: Message,
    ):

        if not is_admin(message.from_user.id):
            return

        text = message.text[
            len("/broadcast"):
        ].strip()

        if not text:

            await message.answer(
                "❌ Укажите текст."
            )

            return

        users = get_all_users()

        sent = 0
        failed = 0

        status = await message.answer(
            "📢 Рассылка запущена..."
        )

        for user in users:

            user_id = value(
                user,
                "user_id",
            )

            if not user_id:
                continue

            try:

                await message.bot.send_message(
                    user_id,
                    text,
                )

                sent += 1

            except Exception:

                failed += 1

            await asyncio.sleep(0.05)

        await status.edit_text(
            "📢 <b>Рассылка завершена</b>\n\n"
            f"✅ Отправлено: <b>{sent}</b>\n"
            f"❌ Ошибок: <b>{failed}</b>",
            parse_mode="HTML",
        )


    # ========================================================
    # SYNC
    # ========================================================

    @dp.callback_query(F.data == "admin:sync")
    async def admin_sync(call: CallbackQuery):

        if not is_admin(call.from_user.id):
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
                f"⚪ Неактивно: "
                f"<b>{result.get('skipped', 0)}</b>\n"
                f"❌ Ошибок: "
                f"<b>{result.get('errors', 0)}</b>",
                parse_mode="HTML",
            )

        except Exception as e:

            await call.message.answer(
                f"❌ Ошибка:\n"
                f"<code>{e}</code>",
                parse_mode="HTML",
            )