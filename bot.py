# bot.py
# ============================================================
# МАГНИТ VPN — MAIN BOT
# ============================================================

import asyncio
import os
import threading
import logging
from html import escape

import uvicorn

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    LabeledPrice,
    PreCheckoutQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import (
    BOT_TOKEN,
    ADMIN_IDS,
    SERVICE_NAME,
    PUBLIC_URL,
    TELEGRAM_USERNAME,
    TARIFFS,
    TRIAL_DAYS,
)

from database import (
    init_db,
    create_user,
    get_user,
    extend_subscription,
    use_trial,
    use_promo,
    create_payment,
    complete_payment,
    expire_old_subscriptions,
    format_date,
)

from subscription import (
    ensure_subscription,
    start_auto_sync,
)

from web import app

from admin import router as admin_router


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("magnit-vpn")


# ============================================================
# BOT
# ============================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не найден в .env"
    )


bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML,
    ),
)

dp = Dispatcher()


# ============================================================
# HELPERS
# ============================================================

def subscription_link(user: dict) -> str:
    token = user.get("token", "")

    return (
        f"{PUBLIC_URL.rstrip('/')}/sub/{token}"
    )


def personal_page(user: dict) -> str:
    token = user.get("token", "")

    return (
        f"{PUBLIC_URL.rstrip('/')}/s/{token}"
    )


def is_active(user: dict) -> bool:
    if not user:
        return False

    if user.get("blocked"):
        return False

    until = user.get("subscription_until")

    if not until:
        return False

    try:
        from database import parse_datetime
        from datetime import datetime, timezone

        dt = parse_datetime(until)

        if not dt:
            return False

        return dt > datetime.now(timezone.utc)

    except Exception:
        return False


def is_blocked(user_id: int) -> bool:
    user = get_user(user_id)

    return bool(
        user and user.get("blocked")
    )


def tariff_by_days(days: int):
    for key, tariff in TARIFFS.items():
        if tariff["days"] == days:
            return key, tariff

    return None, None


# ============================================================
# USER KEYBOARD
# ============================================================

def main_keyboard(user_id: int) -> InlineKeyboardMarkup:

    rows = [
        [
            InlineKeyboardButton(
                text="👤 Личный кабинет",
                callback_data="user:cabinet",
            )
        ],
        [
            InlineKeyboardButton(
                text="💳 Купить подписку",
                callback_data="user:buy",
            )
        ],
        [
            InlineKeyboardButton(
                text="🎁 Пробный период",
                callback_data="user:trial",
            )
        ],
        [
            InlineKeyboardButton(
                text="🎟 Промокод",
                callback_data="user:promo",
            )
        ],
        [
            InlineKeyboardButton(
                text="🆘 Поддержка",
                callback_data="user:support",
            )
        ],
    ]

    if user_id in ADMIN_IDS:
        rows.append(
            [
                InlineKeyboardButton(
                    text="⚙️ Админ-панель",
                    callback_data="admin:menu",
                )
            ]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def back_to_menu_keyboard(
    user_id: int,
) -> InlineKeyboardMarkup:

    rows = [
        [
            InlineKeyboardButton(
                text="⬅️ Главное меню",
                callback_data="user:menu",
            )
        ]
    ]

    if user_id in ADMIN_IDS:
        rows.append(
            [
                InlineKeyboardButton(
                    text="⚙️ Админ-панель",
                    callback_data="admin:menu",
                )
            ]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


# ============================================================
# START
# ============================================================

@dp.message(CommandStart())
async def start_handler(
    message: Message,
):

    user_id = message.from_user.id

    if is_blocked(user_id):
        await message.answer(
            "🚫 <b>Доступ заблокирован.</b>\n\n"
            "Обратитесь в поддержку.",
        )
        return

    user = create_user(
        user_id=user_id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or "",
    )

    # Всегда гарантируем наличие ссылки.
    try:
        ensure_subscription(user_id)
        user = get_user(user_id) or user
    except Exception as e:
        logger.exception(
            "Ошибка создания подписки: %s",
            e,
        )

    await message.answer(
        f"🧲 <b>{SERVICE_NAME}</b>\n\n"
        f"Добро пожаловать, "
        f"<b>{escape(message.from_user.first_name or 'пользователь')}</b>!\n\n"
        f"Здесь можно управлять подпиской, "
        f"купить тариф или активировать пробный период.",
        reply_markup=main_keyboard(user_id),
    )


# ============================================================
# MAIN MENU
# ============================================================

@dp.callback_query(
    F.data == "user:menu"
)
async def user_menu(
    callback: CallbackQuery,
):

    if is_blocked(callback.from_user.id):

        await callback.answer(
            "Доступ заблокирован",
            show_alert=True,
        )

        return

    await callback.message.edit_text(
        f"🧲 <b>{SERVICE_NAME}</b>\n\n"
        f"Выберите действие:",
        reply_markup=main_keyboard(
            callback.from_user.id
        ),
    )

    await callback.answer()


# ============================================================
# CABINET
# ============================================================

@dp.callback_query(
    F.data == "user:cabinet"
)
async def cabinet(
    callback: CallbackQuery,
):

    user_id = callback.from_user.id

    if is_blocked(user_id):

        await callback.answer(
            "Доступ заблокирован",
            show_alert=True,
        )

        return

    user = get_user(user_id)

    if not user:
        user = create_user(
            user_id,
            callback.from_user.username or "",
            callback.from_user.first_name or "",
        )

    try:
        ensure_subscription(user_id)
        user = get_user(user_id) or user
    except Exception:
        pass

    active = is_active(user)

    if active:
        status = "🟢 Активна"
    else:
        status = "🔴 Неактивна"

    until = user.get(
        "subscription_until"
    )

    if until:
        try:
            expires = format_date(until)
        except Exception:
            expires = str(until)
    else:
        expires = "—"

    tariff = (
        user.get("subscription")
        or "Нет"
    )

    link = subscription_link(user)
    page = personal_page(user)

    text = (
        f"👤 <b>ЛИЧНЫЙ КАБИНЕТ</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n\n"
        f"📦 Тариф: <b>{escape(str(tariff))}</b>\n"
        f"📊 Статус: <b>{status}</b>\n"
        f"📅 Действует до: <b>{expires}</b>\n\n"
        f"🔗 <b>Ссылка подписки:</b>\n"
        f"<code>{escape(link)}</code>"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Скопировать ссылку",
                    copy_text=None,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚀 Открыть подписку",
                    url=page,
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Купить / продлить",
                    callback_data="user:buy",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="user:menu",
                )
            ],
        ]
    )

    # Telegram Bot API не позволяет обычной
    # InlineKeyboardButton копировать произвольный текст
    # во всех версиях aiogram одинаково.
    # Поэтому используем отдельную кнопку-ссылку
    # на персональную страницу.

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Открыть личную страницу",
                    url=page,
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Купить / продлить",
                    callback_data="user:buy",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="user:menu",
                )
            ],
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
    )

    await callback.answer()


# ============================================================
# BUY MENU
# ============================================================

@dp.callback_query(
    F.data == "user:buy"
)
async def buy_menu(
    callback: CallbackQuery,
):

    if is_blocked(callback.from_user.id):

        await callback.answer(
            "Доступ заблокирован",
            show_alert=True,
        )

        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="1 месяц — ⭐70",
                    callback_data="buy:1_month",
                )
            ],
            [
                InlineKeyboardButton(
                    text="3 месяца — ⭐190",
                    callback_data="buy:3_months",
                )
            ],
            [
                InlineKeyboardButton(
                    text="6 месяцев — ⭐350",
                    callback_data="buy:6_months",
                )
            ],
            [
                InlineKeyboardButton(
                    text="12 месяцев — ⭐700",
                    callback_data="buy:12_months",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="user:menu",
                )
            ],
        ]
    )

    await callback.message.edit_text(
        "💳 <b>ПОДПИСКА</b>\n\n"
        "Выберите тариф:\n\n"
        "⭐ Оплата производится "
        "через Telegram Stars.",
        reply_markup=keyboard,
    )

    await callback.answer()


# ============================================================
# CREATE INVOICE
# ============================================================

@dp.callback_query(
    F.data.startswith("buy:")
)
async def buy_tariff(
    callback: CallbackQuery,
):

    user_id = callback.from_user.id

    if is_blocked(user_id):

        await callback.answer(
            "Доступ заблокирован",
            show_alert=True,
        )

        return

    tariff_key = callback.data.split(
        ":",
        1,
    )[1]

    tariff = TARIFFS.get(
        tariff_key
    )

    if not tariff:

        await callback.answer(
            "Тариф не найден",
            show_alert=True,
        )

        return

    payment = create_payment(
        user_id=user_id,
        tariff=tariff_key,
        days=tariff["days"],
        stars=tariff["stars"],
    )

    if not payment:

        await callback.answer(
            "Не удалось создать платёж",
            show_alert=True,
        )

        return

    payment_id = payment["id"]

    payload = (
        f"magnit:{payment_id}:{tariff_key}"
    )

    try:

        await bot.send_invoice(
            chat_id=user_id,
            title=(
                f"{SERVICE_NAME} — "
                f"{tariff['title']}"
            ),
            description=(
                f"Подписка {SERVICE_NAME} "
                f"на {tariff['days']} дней."
            ),
            payload=payload,
            currency="XTR",
            prices=[
                LabeledPrice(
                    label=tariff["title"],
                    amount=tariff["stars"],
                )
            ],
        )

        await callback.answer()

    except Exception as e:

        logger.exception(
            "Ошибка send_invoice: %s",
            e,
        )

        await callback.answer(
            "Не удалось создать счёт",
            show_alert=True,
        )


# ============================================================
# PRE CHECKOUT
# ============================================================

@dp.pre_checkout_query()
async def pre_checkout(
    query: PreCheckoutQuery,
):

    try:

        await query.answer(
            ok=True,
        )

    except Exception as e:

        logger.exception(
            "PreCheckout error: %s",
            e,
        )


# ============================================================
# SUCCESSFUL PAYMENT
# ============================================================

@dp.message(
    F.successful_payment
)
async def successful_payment(
    message: Message,
):

    payment = message.successful_payment

    payload = payment.invoice_payload

    if not payload.startswith(
        "magnit:"
    ):
        return

    parts = payload.split(":")

    if len(parts) != 3:
        return

    try:
        payment_id = int(parts[1])
    except ValueError:
        return

    tariff_key = parts[2]

    tariff = TARIFFS.get(
        tariff_key
    )

    if not tariff:
        return

    telegram_charge_id = (
        payment.telegram_payment_charge_id
    )

    completed = complete_payment(
        payment_id=payment_id,
        telegram_payment_charge_id=telegram_charge_id,
    )

    if not completed:

        await message.answer(
            "⚠️ Платёж уже обработан "
            "или не найден."
        )

        return

    user = extend_subscription(
        user_id=message.from_user.id,
        days=tariff["days"],
        tariff=tariff["title"],
    )

    if not user:

        await message.answer(
            "⚠️ Платёж получен, "
            "но подписку не удалось обновить.\n\n"
            "Обратитесь в поддержку."
        )

        return

    try:
        ensure_subscription(
            message.from_user.id
        )
    except Exception:
        logger.exception(
            "Subscription sync error"
        )

    until = user.get(
        "subscription_until",
        "—",
    )

    try:
        expires = format_date(until)
    except Exception:
        expires = str(until)

    link = subscription_link(user)

    await message.answer(
        "🎉 <b>ОПЛАТА УСПЕШНА!</b>\n\n"
        f"📦 Тариф: <b>{tariff['title']}</b>\n"
        f"📅 Действует до: <b>{expires}</b>\n\n"
        f"🔗 <b>Ваша подписка:</b>\n"
        f"<code>{escape(link)}</code>\n\n"
        f"Добавьте эту ссылку в Happ.",
        reply_markup=main_keyboard(
            message.from_user.id
        ),
    )


# ============================================================
# TRIAL
# ============================================================

@dp.callback_query(
    F.data == "user:trial"
)
async def trial(
    callback: CallbackQuery,
):

    user_id = callback.from_user.id

    if is_blocked(user_id):

        await callback.answer(
            "Доступ заблокирован",
            show_alert=True,
        )

        return

    user = get_user(user_id)

    if not user:

        user = create_user(
            user_id,
            callback.from_user.username or "",
            callback.from_user.first_name or "",
        )

    success = use_trial(
        user_id,
        TRIAL_DAYS,
    )

    if not success:

        await callback.answer(
            "Пробный период уже использован",
            show_alert=True,
        )

        return

    user = get_user(user_id)

    try:
        ensure_subscription(user_id)
    except Exception:
        logger.exception(
            "Trial sync error"
        )

    until = user.get(
        "subscription_until"
    )

    try:
        expires = format_date(until)
    except Exception:
        expires = str(until)

    link = subscription_link(user)

    await callback.message.edit_text(
        "🎁 <b>ПРОБНЫЙ ПЕРИОД АКТИВИРОВАН!</b>\n\n"
        f"⏳ Срок: <b>{TRIAL_DAYS} дня</b>\n"
        f"📅 До: <b>{expires}</b>\n\n"
        f"🔗 Ваша ссылка:\n"
        f"<code>{escape(link)}</code>\n\n"
        "Добавьте её в Happ.",
        reply_markup=back_to_menu_keyboard(
            user_id
        ),
    )

    await callback.answer(
        "Пробный период активирован!",
    )


# ============================================================
# PROMO
# ============================================================

promo_states = {}


@dp.callback_query(
    F.data == "user:promo"
)
async def promo_start(
    callback: CallbackQuery,
):

    user_id = callback.from_user.id

    if is_blocked(user_id):

        await callback.answer(
            "Доступ заблокирован",
            show_alert=True,
        )

        return

    promo_states[user_id] = True

    await callback.message.edit_text(
        "🎟 <b>ПРОМОКОД</b>\n\n"
        "Отправьте промокод сообщением.\n\n"
        "Например:\n"
        "<code>MAGNIT30</code>",
        reply_markup=back_to_menu_keyboard(
            user_id
        ),
    )

    await callback.answer()


@dp.message()
async def user_text_handler(
    message: Message,
):

    user_id = message.from_user.id

    if user_id not in promo_states:
        return

    if is_blocked(user_id):
        promo_states.pop(user_id, None)
        return

    code = (
        message.text or ""
    ).strip().upper()

    promo_states.pop(
        user_id,
        None,
    )

    if not code:

        await message.answer(
            "❌ Промокод пустой."
        )

        return

    days = use_promo(
        code
    )

    if not days:

        await message.answer(
            "❌ <b>Промокод недействителен.</b>\n\n"
            "Проверьте код и попробуйте ещё раз.",
            reply_markup=main_keyboard(
                user_id
            ),
        )

        return

    user = extend_subscription(
        user_id,
        days,
        tariff=f"Промокод {code}",
    )

    if not user:

        await message.answer(
            "❌ Не удалось активировать промокод.",
            reply_markup=main_keyboard(
                user_id
            ),
        )

        return

    try:
        ensure_subscription(user_id)
    except Exception:
        logger.exception(
            "Promo sync error"
        )

    until = user.get(
        "subscription_until"
    )

    try:
        expires = format_date(until)
    except Exception:
        expires = str(until)

    link = subscription_link(user)

    await message.answer(
        "🎉 <b>ПРОМОКОД АКТИВИРОВАН!</b>\n\n"
        f"🎟 Код: <code>{escape(code)}</code>\n"
        f"➕ Добавлено: <b>{days} дней</b>\n"
        f"📅 Действует до: <b>{expires}</b>\n\n"
        f"🔗 Подписка:\n"
        f"<code>{escape(link)}</code>",
        reply_markup=main_keyboard(
            user_id
        ),
    )


# ============================================================
# SUPPORT
# ============================================================

@dp.callback_query(
    F.data == "user:support"
)
async def support(
    callback: CallbackQuery,
):

    username = (
        TELEGRAM_USERNAME
        .lstrip("@")
    )

    support_url = (
        f"https://t.me/{username}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Написать в поддержку",
                    url=support_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="user:menu",
                )
            ],
        ]
    )

    await callback.message.edit_text(
        "🆘 <b>ПОДДЕРЖКА</b>\n\n"
        "Если возникли проблемы с подпиской "
        "или подключением — напишите нам.",
        reply_markup=keyboard,
    )

    await callback.answer()


# ============================================================
# BLOCK CHECK FOR TEXT COMMANDS
# ============================================================

@dp.message(
    F.text == "/cabinet"
)
async def cabinet_command(
    message: Message,
):

    if is_blocked(message.from_user.id):

        await message.answer(
            "🚫 Доступ заблокирован."
        )

        return

    user = get_user(
        message.from_user.id
    )

    if not user:

        user = create_user(
            message.from_user.id,
            message.from_user.username or "",
            message.from_user.first_name or "",
        )

    active = is_active(user)

    status = (
        "🟢 Активна"
        if active
        else "🔴 Неактивна"
    )

    until = user.get(
        "subscription_until"
    ) or "—"

    link = subscription_link(user)

    await message.answer(
        f"👤 <b>ЛИЧНЫЙ КАБИНЕТ</b>\n\n"
        f"📊 Статус: <b>{status}</b>\n"
        f"📅 До: <b>{escape(str(until))}</b>\n\n"
        f"🔗 <code>{escape(link)}</code>",
        reply_markup=main_keyboard(
            message.from_user.id
        ),
    )


# ============================================================
# EXPIRATION LOOP
# ============================================================

async def expiration_loop():

    while True:

        try:
            expire_old_subscriptions()

        except Exception as e:

            logger.exception(
                "Expiration loop error: %s",
                e,
            )

        await asyncio.sleep(
            300
        )


# ============================================================
# WEB SERVER
# ============================================================

def run_web_server():

    port = int(
        os.getenv(
            "PORT",
            "10000",
        )
    )

    logger.info(
        "Web server starting on port %s",
        port,
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )


# ============================================================
# STARTUP
# ============================================================

async def main():

    logger.info(
        "Starting %s...",
        SERVICE_NAME,
    )

    # DB
    init_db()

    # Web
    web_thread = threading.Thread(
        target=run_web_server,
        daemon=True,
        name="web-server",
    )

    web_thread.start()

    # Auto subscription sync
    try:
        start_auto_sync()

        logger.info(
            "Auto sync started"
        )

    except Exception as e:

        logger.exception(
            "Auto sync error: %s",
            e,
        )

    # Expiration checker
    asyncio.create_task(
        expiration_loop()
    )

    # Remove old webhook
    try:

        await bot.delete_webhook(
            drop_pending_updates=True
        )

    except Exception as e:

        logger.warning(
            "delete_webhook error: %s",
            e,
        )

    logger.info(
        "Bot polling started"
    )

    await dp.start_polling(
        bot
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    # Admin router должен быть подключён
    # до запуска polling.
    dp.include_router(
        admin_router
    )

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        logger.info(
            "Bot stopped"
        )

    except Exception as e:

        logger.exception(
            "Fatal error: %s",
            e
        )