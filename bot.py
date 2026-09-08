import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, LabeledPrice
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import (
    BOT_TOKEN,
    PUBLIC_URL,
    SERVICE_NAME,
    TARIFFS,
    TRIAL_DAYS,
)

from database import (
    create_user,
    get_user,
    extend_subscription,
    use_trial,
    create_payment,
    complete_payment,
    use_promo,
    get_devices,
    delete_device,
    set_device_limit,
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
        callback_data="cabinet",
    )

    kb.button(
        text="💳 Купить подписку",
        callback_data="buy",
    )

    kb.button(
        text="🎁 Пробный период",
        callback_data="trial",
    )

    kb.button(
        text="🎟 Промокод",
        callback_data="promo",
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
            callback_data=f"tariff:{key}",
        )

    kb.button(
        text="⬅️ Назад",
        callback_data="back",
    )

    kb.adjust(1)

    return kb.as_markup()


# ============================================================
# HELPERS
# ============================================================

def subscription_link(user):
    """
    Получает постоянную ссылку пользователя.

    Если она уже есть в БД — используем её.
    Иначе строим новую.
    """

    if user.get("subscription_link"):
        return user["subscription_link"]

    token = user.get("token")

    if token:
        return (
            f"{PUBLIC_URL}/sub/"
            f"{token}"
        )

    return (
        f"{PUBLIC_URL}/sub/"
        f"{user['user_id']}"
    )


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


# ============================================================
# START
# ============================================================

@dp.message(Command("start"))
async def start(message: Message):

    user = create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )

    await message.answer(
        f"🧲 <b>{SERVICE_NAME}</b>\n\n"
        "Добро пожаловать!\n\n"
        "Быстрый и удобный доступ к VPN.\n\n"
        "Выберите действие:",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# CABINET
# ============================================================

@dp.callback_query(F.data == "cabinet")
async def cabinet(call: CallbackQuery):

    user = get_user(
        call.from_user.id
    )

    if not user:

        user = create_user(
            call.from_user.id,
            call.from_user.username,
            call.from_user.first_name,
        )

    devices = get_devices(
        call.from_user.id
    )

    link = subscription_link(user)

    subscription_until = (
        user.get("subscription_until")
    )

    if subscription_until:

        try:

            expire_dt = datetime.fromisoformat(
                str(subscription_until)
            )

            if expire_dt > datetime.utcnow():

                status = "🟢 Активна"

            else:

                status = "🔴 Истекла"

        except Exception:

            status = "⚪ Неизвестно"

    else:

        status = "⚪ Не активна"

    device_limit = user.get(
        "device_limit",
        1,
    )

    text = (
        "👤 <b>Личный кабинет</b>\n\n"
        f"🆔 ID: "
        f"<code>{user['user_id']}</code>\n"
        f"📡 Статус: {status}\n"
        f"📅 До: "
        f"<b>{format_date(subscription_until)}</b>\n"
        f"📱 Устройства: "
        f"{len(devices)}/{device_limit}\n\n"
        "🔗 <b>Ссылка подписки:</b>\n"
        f"<code>{link}</code>"
    )

    kb = InlineKeyboardBuilder()

    kb.button(
        text="📋 Скопировать ссылку",
        callback_data="copy_link",
    )

    kb.button(
        text="📱 Мои устройства",
        callback_data="devices",
    )

    kb.button(
        text="💳 Купить",
        callback_data="buy",
    )

    kb.button(
        text="⬅️ Назад",
        callback_data="back",
    )

    kb.adjust(1)

    await call.message.edit_text(
        text,
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )

    await call.answer()


# ============================================================
# COPY LINK
# ============================================================

@dp.callback_query(F.data == "copy_link")
async def copy_link(call: CallbackQuery):

    user = get_user(
        call.from_user.id
    )

    if not user:

        await call.answer(
            "Сначала нажми /start",
            show_alert=True,
        )

        return

    link = subscription_link(user)

    await call.message.answer(
        f"<code>{link}</code>",
        parse_mode="HTML",
    )

    await call.answer(
        "Ссылка отправлена",
    )


# ============================================================
# DEVICES
# ============================================================

@dp.callback_query(F.data == "devices")
async def devices(call: CallbackQuery):

    user = get_user(
        call.from_user.id
    )

    if not user:

        await call.answer(
            "Сначала нажми /start",
            show_alert=True,
        )

        return

    items = get_devices(
        call.from_user.id
    )

    device_limit = user.get(
        "device_limit",
        1,
    )

    text = (
        "📱 <b>Мои устройства</b>\n\n"
        f"Лимит: "
        f"{len(items)}/{device_limit}\n\n"
    )

    if not items:

        text += "Устройств пока нет."

    else:

        for i, device in enumerate(
            items,
            start=1,
        ):

            device_name = (
                device.get("device_name")
                or "Устройство"
            )

            device_id = device.get(
                "device_id",
                "",
            )

            text += (
                f"{i}. {device_name}\n"
                f"   ID: "
                f"<code>{device_id}</code>\n"
            )

    kb = InlineKeyboardBuilder()

    for device in items:

        device_id = device.get(
            "device_id",
            "",
        )

        device_name = (
            device.get("device_name")
            or device_id[:8]
            or "Устройство"
        )

        kb.button(
            text=f"❌ {device_name}",
            callback_data=(
                f"deldevice:{device_id}"
            ),
        )

    kb.button(
        text="⬅️ Кабинет",
        callback_data="cabinet",
    )

    kb.adjust(1)

    await call.message.edit_text(
        text,
        reply_markup=kb.as_markup(),
        parse_mode="HTML",
    )

    await call.answer()


# ============================================================
# DELETE DEVICE
# ============================================================

@dp.callback_query(
    F.data.startswith("deldevice:")
)
async def remove_device(
    call: CallbackQuery
):

    device_id = call.data.split(
        ":",
        1,
    )[1]

    delete_device(
        call.from_user.id,
        device_id,
    )

    await call.answer(
        "Устройство удалено",
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
        parse_mode="HTML",
    )

    await call.answer()


# ============================================================
# SELECT TARIFF
# ============================================================

@dp.callback_query(
    F.data.startswith("tariff:")
)
async def select_tariff(
    call: CallbackQuery
):

    key = call.data.split(
        ":",
        1,
    )[1]

    tariff = TARIFFS.get(
        key
    )

    if not tariff:

        await call.answer(
            "Тариф не найден",
            show_alert=True,
        )

        return

    payment_id = create_payment(
        call.from_user.id,
        key,
        tariff["stars"],
        tariff["days"],
    )

    prices = [
        LabeledPrice(
            label=tariff["name"],
            amount=tariff["stars"],
        )
    ]

    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=(
            f"{SERVICE_NAME} — "
            f"{tariff['name']}"
        ),
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
        payment.telegram_payment_charge_id,
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

    tariff_name = (
        tariff["name"]
        if tariff
        else "active"
    )

    new_date = extend_subscription(
        message.from_user.id,
        result["days"],
        tariff_name,
    )

    if tariff:

        set_device_limit(
            message.from_user.id,
            tariff["device_limit"],
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
        "🔗 Ссылка:\n"
        f"<code>{subscription_link(user)}</code>",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
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
            "❌ Вы уже использовали "
            "пробный период.",
            show_alert=True,
        )

        return

    date = extend_subscription(
        call.from_user.id,
        TRIAL_DAYS,
        "trial",
    )

    user = get_user(
        call.from_user.id
    )

    await call.message.edit_text(
        "🎁 <b>Пробный период "
        "активирован!</b>\n\n"
        f"⏳ Срок: {TRIAL_DAYS} дня\n"
        f"📅 До: "
        f"<b>{format_date(date.isoformat())}</b>\n\n"
        "🔗 Ваша ссылка:\n"
        f"<code>{subscription_link(user)}</code>",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )

    await call.answer()


# ============================================================
# PROMO
# ============================================================

@dp.callback_query(F.data == "promo")
async def promo_request(
    call: CallbackQuery
):

    await call.message.answer(
        "🎟 Введите промокод сообщением.\n\n"
        "Например:\n"
        "<code>PROMO: MAGNIT100</code>",
        parse_mode="HTML",
    )

    await call.answer()


# ============================================================
# PROMO MESSAGE
# ============================================================

@dp.message(
    lambda message:
    message.text
    and message.text.upper().startswith(
        "PROMO:"
    )
)
async def promo_message(
    message: Message
):

    code = message.text.split(
        ":",
        1,
    )[1].strip()

    promo = use_promo(
        code
    )

    if not promo:

        await message.answer(
            "❌ Промокод недействителен."
        )

        return

    date = extend_subscription(
        message.from_user.id,
        promo["days"],
        "promo",
    )

    user = get_user(
        message.from_user.id
    )

    await message.answer(
        "🎉 <b>Промокод активирован!</b>\n\n"
        f"➕ {promo['days']} дней\n"
        f"📅 До: "
        f"<b>{format_date(date.isoformat())}</b>\n\n"
        "🔗 Ваша ссылка:\n"
        f"<code>{subscription_link(user)}</code>",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


# ============================================================
# BACK
# ============================================================

@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):

    await call.message.edit_text(
        f"🧲 <b>{SERVICE_NAME}</b>\n\n"
        "Главное меню:",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )

    await call.answer()


# ============================================================
# АВТОМАТИЧЕСКОЕ ИСТЕЧЕНИЕ
# ============================================================

async def expiration_loop():

    while True:

        try:

            expire_old_subscriptions()

        except Exception as e:

            print(
                "Expiration error:",
                e,
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