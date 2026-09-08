import asyncio
from datetime import datetime

from aiogram import (
    Bot,
    Dispatcher,
    F,
)
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    LabeledPrice,
)
from aiogram.utils.keyboard import (
    InlineKeyboardBuilder,
)

from config import (
    BOT_TOKEN,
    ADMIN_ID,
    PUBLIC_URL,
    SERVICE_NAME,
    TARIFFS,
    TRIAL_DAYS,
    DEFAULT_DEVICE_LIMIT,
)

from database import (
    create_user,
    get_user,
    get_all_users,
    extend_subscription,
    use_trial,
    create_payment,
    complete_payment,
    create_promo,
    use_promo,
    add_node,
    delete_node,
    get_nodes,
    get_devices,
    delete_device,
    set_device_limit,
    block_user,
    get_stats,
    expire_old_subscriptions,
)


# ============================================================
# BOT
# ============================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is not configured"
    )

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


# ============================================================
# KEYBOARDS
# ============================================================

def main_keyboard():
    kb = InlineKeyboardBuilder()

    kb.button(
        text="👤 Личный кабинет",
        callback_data="cabinet"
    )

    kb.button(
        text="💳 Купить подписку",
        callback_data="buy"
    )

    kb.button(
        text="🎁 Пробный период",
        callback_data="trial"
    )

    kb.button(
        text="🎟 Промокод",
        callback_data="promo"
    )

    kb.adjust(1)

    return kb.as_markup()


def tariff_keyboard():
    kb = InlineKeyboardBuilder()

    for key, tariff in TARIFFS.items():
        kb.button(
            text=(
                f"{tariff['name']} — "
                f"⭐{tariff['stars']}"
            ),
            callback_data=f"tariff:{key}"
        )

    kb.button(
        text="⬅️ Назад",
        callback_data="back"
    )

    kb.adjust(1)

    return kb.as_markup()


def admin_keyboard():
    kb = InlineKeyboardBuilder()

    kb.button(
        text="📊 Статистика",
        callback_data="admin:stats"
    )

    kb.button(
        text="👥 Пользователи",
        callback_data="admin:users"
    )

    kb.button(
        text="🖥 Серверы",
        callback_data="admin:nodes"
    )

    kb.button(
        text="🎟 Создать промокод",
        callback_data="admin:promo"
    )

    kb.adjust(1)

    return kb.as_markup()


# ============================================================
# HELPERS
# ============================================================

def is_admin(user_id):
    return user_id == ADMIN_ID


def subscription_link(user):
    return (
        f"{PUBLIC_URL}/sub/"
        f"{user['token']}"
    )


def format_date(value):
    if not value:
        return "—"

    try:
        dt = datetime.fromisoformat(value)

        return dt.strftime(
            "%d.%m.%Y %H:%M"
        )

    except Exception:
        return value


# ============================================================
# START
# ============================================================

@dp.message(Command("start"))
async def start(message: Message):

    user = create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    await message.answer(
        f"🧲 <b>{SERVICE_NAME}</b>\n\n"
        f"Добро пожаловать!\n\n"
        f"Быстрый и удобный доступ к VPN.\n\n"
        f"Выберите действие:",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )


# ============================================================
# CABINET
# ============================================================

@dp.callback_query(F.data == "cabinet")
async def cabinet(call: CallbackQuery):

    user = get_user(call.from_user.id)

    if not user:
        user = create_user(
            call.from_user.id,
            call.from_user.username,
            call.from_user.first_name
        )

    devices = get_devices(
        call.from_user.id
    )

    link = subscription_link(user)

    if user["subscription_until"]:
        status = (
            "🟢 Активна"
            if (
                user["subscription_until"]
                > datetime.utcnow().isoformat()
            )
            else
            "🔴 Истекла"
        )
    else:
        status = "⚪ Не активна"

    text = (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"📡 Статус: {status}\n"
        f"📅 До: "
        f"<b>{format_date(user['subscription_until'])}</b>\n"
        f"📱 Устройства: "
        f"{len(devices)}/{user['device_limit']}\n\n"
        f"🔗 <b>Ссылка Happ:</b>\n"
        f"<code>{link}</code>"
    )

    kb = InlineKeyboardBuilder()

    kb.button(
        text="📋 Скопировать ссылку",
        callback_data="copy_link"
    )

    kb.button(
        text="📱 Мои устройства",
        callback_data="devices"
    )

    kb.button(
        text="💳 Купить",
        callback_data="buy"
    )

    kb.button(
        text="⬅️ Назад",
        callback_data="back"
    )

    kb.adjust(1)

    await call.message.edit_text(
        text,
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

    await call.answer()


@dp.callback_query(F.data == "copy_link")
async def copy_link(call: CallbackQuery):

    user = get_user(call.from_user.id)

    if not user:
        await call.answer(
            "Сначала нажми /start",
            show_alert=True
        )
        return

    link = subscription_link(user)

    await call.message.answer(
        f"<code>{link}</code>",
        parse_mode="HTML"
    )

    await call.answer(
        "Ссылка отправлена"
    )


# ============================================================
# DEVICES
# ============================================================

@dp.callback_query(F.data == "devices")
async def devices(call: CallbackQuery):

    user = get_user(call.from_user.id)

    items = get_devices(
        call.from_user.id
    )

    text = (
        "📱 <b>Мои устройства</b>\n\n"
        f"Лимит: "
        f"{len(items)}/{user['device_limit']}\n\n"
    )

    if not items:
        text += "Устройств пока нет."

    else:
        for i, device in enumerate(
            items,
            start=1
        ):
            text += (
                f"{i}. "
                f"{device['device_name'] or 'Устройство'}\n"
                f"   ID: <code>"
                f"{device['device_id']}</code>\n"
            )

    kb = InlineKeyboardBuilder()

    for device in items:
        kb.button(
            text=(
                "❌ "
                + (
                    device["device_name"]
                    or device["device_id"][:8]
                )
            ),
            callback_data=(
                f"deldevice:{device['device_id']}"
            )
        )

    kb.button(
        text="⬅️ Кабинет",
        callback_data="cabinet"
    )

    kb.adjust(1)

    await call.message.edit_text(
        text,
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

    await call.answer()


@dp.callback_query(
    F.data.startswith("deldevice:")
)
async def remove_device(call: CallbackQuery):

    device_id = call.data.split(
        ":",
        1
    )[1]

    delete_device(
        call.from_user.id,
        device_id
    )

    await call.answer(
        "Устройство удалено"
    )

    await devices(call)


# ============================================================
# BUY
# ============================================================

@dp.callback_query(F.data == "buy")
async def buy(call: CallbackQuery):

    await call.message.edit_text(
        "💳 <b>Выберите тариф:</b>",
        reply_markup=tariff_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


@dp.callback_query(
    F.data.startswith("tariff:")
)
async def select_tariff(
    call: CallbackQuery
):

    key = call.data.split(
        ":",
        1
    )[1]

    tariff = TARIFFS.get(key)

    if not tariff:
        await call.answer(
            "Тариф не найден",
            show_alert=True
        )
        return

    payment_id = create_payment(
        call.from_user.id,
        key,
        tariff["stars"],
        tariff["days"]
    )

    prices = [
        LabeledPrice(
            label=tariff["name"],
            amount=tariff["stars"]
        )
    ]

    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=f"{SERVICE_NAME} — {tariff['name']}",
        description=(
            f"VPN подписка на "
            f"{tariff['days']} дней"
        ),
        payload=str(payment_id),
        currency="XTR",
        prices=prices,
    )

    await call.answer()


# ============================================================
# PRE CHECKOUT
# ============================================================

@dp.pre_checkout_query()
async def pre_checkout(query):

    await query.answer(
        ok=True
    )


# ============================================================
# SUCCESSFUL PAYMENT
# ============================================================

@dp.message(F.successful_payment)
async def successful_payment(
    message: Message
):

    payment = message.successful_payment

    payment_id = int(
        payment.invoice_payload
    )

    result = complete_payment(
        payment_id,
        payment.telegram_payment_charge_id
    )

    if not result:
        await message.answer(
            "❌ Не удалось обработать платёж."
        )
        return

    tariff_key = result["tariff"]

    tariff = TARIFFS.get(
        tariff_key
    )

    new_date = extend_subscription(
        message.from_user.id,
        result["days"],
        tariff["name"] if tariff else "active"
    )

    if tariff:
        set_device_limit(
            message.from_user.id,
            tariff["device_limit"]
        )

    user = get_user(
        message.from_user.id
    )

    await message.answer(
        f"✅ <b>Оплата прошла!</b>\n\n"
        f"🧲 {SERVICE_NAME}\n"
        f"📦 Тариф: "
        f"<b>{tariff['name']}</b>\n"
        f"📅 Действует до: "
        f"<b>{format_date(new_date.isoformat())}</b>\n\n"
        f"🔗 Ссылка:\n"
        f"<code>{subscription_link(user)}</code>",
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )


# ============================================================
# TRIAL
# ============================================================

@dp.callback_query(F.data == "trial")
async def trial(call: CallbackQuery):

    success = use_trial(
        call.from_user.id
    )

    if not success:
        await call.answer(
            "❌ Вы уже использовали пробный период.",
            show_alert=True
        )
        return

    date = extend_subscription(
        call.from_user.id,
        TRIAL_DAYS,
        "trial"
    )

    user = get_user(
        call.from_user.id
    )

    await call.message.edit_text(
        f"🎁 <b>Пробный период активирован!</b>\n\n"
        f"⏳ Срок: {TRIAL_DAYS} дня\n"
        f"📅 До: {format_date(date.isoformat())}\n\n"
        f"🔗 Ваша ссылка:\n"
        f"<code>{subscription_link(user)}</code>",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


# ============================================================
# PROMO
# ============================================================

@dp.callback_query(F.data == "promo")
async def promo_request(call: CallbackQuery):

    await call.message.answer(
        "🎟 Введите промокод сообщением:"
    )

    # aiogram state здесь намеренно не используется:
    # следующий текст обрабатывается ниже.
    await call.answer()


@dp.message(
    lambda message:
    message.text
    and message.text.upper().startswith("PROMO:")
)
async def promo_message(message: Message):

    code = message.text.split(
        ":",
        1
    )[1].strip()

    promo = use_promo(code)

    if not promo:
        await message.answer(
            "❌ Промокод недействителен."
        )
        return

    date = extend_subscription(
        message.from_user.id,
        promo["days"],
        "promo"
    )

    await message.answer(
        f"🎉 Промокод активирован!\n\n"
        f"➕ {promo['days']} дней\n"
        f"📅 До: {format_date(date.isoformat())}",
        reply_markup=main_keyboard()
    )


# ============================================================
# ADMIN
# ============================================================

@dp.message(Command("admin"))
async def admin(message: Message):

    if not is_admin(
        message.from_user.id
    ):
        return

    await message.answer(
        "👑 <b>Админ-панель</b>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "admin:stats")
async def admin_stats(
    call: CallbackQuery
):

    if not is_admin(
        call.from_user.id
    ):
        return

    stats = get_stats()

    await call.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: "
        f"{stats['users']}\n"
        f"🟢 Активных: "
        f"{stats['active']}\n"
        f"💳 Оплат: "
        f"{stats['payments']}\n"
        f"⭐ Получено Stars: "
        f"{stats['stars']}",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


@dp.callback_query(F.data == "admin:users")
async def admin_users(
    call: CallbackQuery
):

    if not is_admin(
        call.from_user.id
    ):
        return

    users = get_all_users()

    text = (
        f"👥 <b>Пользователи:</b> "
        f"{len(users)}\n\n"
    )

    for user in users[:30]:

        text += (
            f"🆔 <code>{user['user_id']}</code> "
            f"— "
            f"{user['username'] or user['first_name'] or 'без имени'}\n"
            f"📅 "
            f"{format_date(user['subscription_until'])}\n\n"
        )

    await call.message.edit_text(
        text,
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


# ============================================================
# ADMIN NODES
# ============================================================

@dp.callback_query(F.data == "admin:nodes")
async def admin_nodes(
    call: CallbackQuery
):

    if not is_admin(
        call.from_user.id
    ):
        return

    nodes = get_nodes()

    text = "🖥 <b>VPN-ноды</b>\n\n"

    if not nodes:
        text += "Нод пока нет.\n\n"

    for node in nodes:
        text += (
            f"#{node['id']} "
            f"<b>{node['name']}</b>\n"
            f"<code>{node['vless_link']}</code>\n\n"
        )

    text += (
        "Чтобы добавить сервер:\n"
        "<code>/addnode Название|VLESS-ссылка</code>\n\n"
        "Удалить:\n"
        "<code>/delnode ID</code>"
    )

    await call.message.edit_text(
        text,
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


@dp.message(Command("addnode"))
async def admin_add_node(
    message: Message
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
            "/addnode Название|VLESS-ссылка"
        )
        return

    name, link = value.split(
        "|",
        1
    )

    node_id = add_node(
        name.strip(),
        link.strip()
    )

    await message.answer(
        f"✅ Нода добавлена.\n"
        f"ID: {node_id}"
    )


@dp.message(Command("delnode"))
async def admin_delete_node(
    message: Message
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
            "Использование: /delnode ID"
        )
        return

    delete_node(node_id)

    await message.answer(
        "✅ Нода удалена."
    )


# ============================================================
# ADMIN PROMO
# ============================================================

@dp.callback_query(F.data == "admin:promo")
async def admin_promo_help(
    call: CallbackQuery
):

    if not is_admin(
        call.from_user.id
    ):
        return

    await call.message.answer(
        "🎟 Создание промокода:\n\n"
        "<code>/promo MAGNIT100 30 10</code>\n\n"
        "MAGNIT100 — код\n"
        "30 — дней\n"
        "10 — максимальное количество активаций",
        parse_mode="HTML"
    )

    await call.answer()


@dp.message(Command("promo"))
async def admin_create_promo(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    parts = message.text.split()

    if len(parts) != 4:
        await message.answer(
            "Формат:\n"
            "/promo КОД ДНИ МАКС_АКТИВАЦИЙ"
        )
        return

    _, code, days, max_uses = parts

    try:
        days = int(days)
        max_uses = int(max_uses)
    except ValueError:
        await message.answer(
            "Дни и количество активаций "
            "должны быть числами."
        )
        return

    success = create_promo(
        code,
        days,
        max_uses
    )

    if success:
        await message.answer(
            f"✅ Промокод {code.upper()} создан."
        )
    else:
        await message.answer(
            "❌ Такой промокод уже существует."
        )


# ============================================================
# ADMIN USER COMMANDS
# ============================================================

@dp.message(Command("give"))
async def admin_give(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    parts = message.text.split()

    if len(parts) != 3:
        await message.answer(
            "/give USER_ID DAYS"
        )
        return

    try:
        user_id = int(parts[1])
        days = int(parts[2])
    except ValueError:
        await message.answer(
            "ID и дни должны быть числами."
        )
        return

    user = get_user(user_id)

    if not user:
        await message.answer(
            "Пользователь не найден."
        )
        return

    date = extend_subscription(
        user_id,
        days,
        "admin"
    )

    await message.answer(
        f"✅ Выдано {days} дней.\n"
        f"До: {format_date(date.isoformat())}"
    )


@dp.message(Command("block"))
async def admin_block(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    parts = message.text.split()

    if len(parts) != 2:
        await message.answer(
            "/block USER_ID"
        )
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        return

    block_user(
        user_id,
        True
    )

    await message.answer(
        "🚫 Пользователь заблокирован."
    )


@dp.message(Command("unblock"))
async def admin_unblock(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    parts = message.text.split()

    if len(parts) != 2:
        await message.answer(
            "/unblock USER_ID"
        )
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        return

    block_user(
        user_id,
        False
    )

    await message.answer(
        "✅ Пользователь разблокирован."
    )


# ============================================================
# BACK
# ============================================================

@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):

    await call.message.edit_text(
        f"🧲 <b>{SERVICE_NAME}</b>\n\n"
        f"Главное меню:",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )

    await call.answer()


# ============================================================
# AUTO EXPIRATION
# ============================================================

async def expiration_loop():

    while True:

        try:
            expire_old_subscriptions()
        except Exception as e:
            print(
                "Expiration error:",
                e
            )

        await asyncio.sleep(
            60 * 10
        )


# ============================================================
# MAIN
# ============================================================

async def main():

    print(
        f"{SERVICE_NAME} starting..."
    )

    asyncio.create_task(
        expiration_loop()
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":
    asyncio.run(main())