# bot.py

import asyncio
import logging
import os
from datetime import datetime, timezone
from html import escape

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    LabeledPrice,
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
    get_user_by_token,
    extend_subscription,
    use_trial,
    use_promo,
    create_payment,
    expire_old_subscriptions,
    get_promo,
    format_date,
)

from subscription import (
    ensure_subscription,
    start_auto_sync,
    github_raw_url,
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"
    ),
)

logger = logging.getLogger(
    "magnit-bot"
)


# ============================================================
# BOT
# ============================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не указан в переменных окружения"
    )

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    ),
)

dp = Dispatcher()
router = Router()


# ============================================================
# STATES
# ============================================================

class PromoState(StatesGroup):
    waiting_code = State()


# ============================================================
# HELPERS
# ============================================================

def is_admin(user_id: int) -> bool:
    return int(user_id) in ADMIN_IDS


def get_raw_link(user_id: int) -> str:
    """
    Возвращает постоянную RAW-ссылку пользователя.
    """
    try:
        user = get_user(user_id)

        if user:
            saved = (
                user.get(
                    "subscription_link",
                    "",
                )
                or ""
            ).strip()

            if saved:
                return saved

    except Exception as exc:
        logger.error(
            "get_raw_link error: %s",
            exc,
        )

    return github_raw_url(
        user_id
    )


def get_cabinet_link(user_id: int) -> str:
    user = get_user(user_id)

    if not user:
        return (
            f"{PUBLIC_URL}"
        )

    token = (
        user.get(
            "token",
            "",
        )
        or ""
    ).strip()

    if not token:
        return (
            f"{PUBLIC_URL}"
        )

    return (
        f"{PUBLIC_URL}/s/{token}"
    )


def subscription_status(user) -> str:

    if not user:
        return "⚪ Не активна"

    if int(
        user.get(
            "blocked",
            0,
        )
        or 0
    ):
        return "🔴 Заблокирована"

    until = (
        user.get(
            "subscription_until",
            "",
        )
        or ""
    ).strip()

    if not until:
        return "⚪ Не активна"

    try:

        expire = datetime.fromisoformat(
            until.replace(
                "Z",
                "+00:00",
            )
        )

        if expire.tzinfo is None:
            expire = expire.replace(
                tzinfo=timezone.utc
            )

        if expire > datetime.now(
            timezone.utc
        ):
            return "🟢 Активна"

    except Exception:
        pass

    return "⚪ Не активна"


def cabinet_text(user_id: int) -> str:

    user = get_user(
        user_id
    )

    if not user:
        return (
            "❌ Пользователь не найден."
        )

    status = subscription_status(
        user
    )

    subscription = (
        user.get(
            "subscription",
            "none",
        )
        or "none"
    )

    until = (
        user.get(
            "subscription_until",
            "",
        )
        or ""
    )

    if until:
        try:
            until_text = format_date(
                until
            )
        except Exception:
            until_text = until
    else:
        until_text = "—"

    raw = get_raw_link(
        user_id
    )

    cabinet = get_cabinet_link(
        user_id
    )

    return (
        f"🧲 <b>{escape(SERVICE_NAME)}</b>\n\n"

        f"👤 <b>Личный кабинет</b>\n\n"

        f"Статус: {status}\n"
        f"Тариф: <b>{escape(str(subscription))}</b>\n"
        f"До: <b>{escape(str(until_text))}</b>\n\n"

        f"🔗 <b>Подписка</b>\n"
        f"<code>{escape(raw)}</code>\n\n"

        f"🌐 <b>Кабинет:</b>\n"
        f"<code>{escape(cabinet)}</code>"
    )


# ============================================================
# KEYBOARDS
# ============================================================

def main_menu(
    user_id: int,
) -> InlineKeyboardMarkup:

    buttons = [
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
            ),
            InlineKeyboardButton(
                text="🎁 Пробный период",
                callback_data="user:trial",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🎟 Промокод",
                callback_data="user:promo",
            ),
            InlineKeyboardButton(
                text="🆘 Поддержка",
                callback_data="user:support",
            ),
        ],
    ]

    if is_admin(user_id):
        buttons.append(
            [
                InlineKeyboardButton(
                    text="⚙️ Админ-панель",
                    callback_data="admin:menu",
                )
            ]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


def cabinet_keyboard(
    user_id: int,
) -> InlineKeyboardMarkup:

    raw = get_raw_link(
        user_id
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Скопировать ссылку",
                    copy_text={
                        "text": raw
                    },
                )
            ],
            [
                InlineKeyboardButton(
                    text="🌐 Открыть кабинет",
                    url=get_cabinet_link(
                        user_id
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🧲 Открыть подписку",
                    url=raw,
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


def buy_keyboard() -> InlineKeyboardMarkup:

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="1 месяц — ⭐ 70",
                    callback_data="buy:1_month",
                )
            ],
            [
                InlineKeyboardButton(
                    text="3 месяца — ⭐ 190",
                    callback_data="buy:3_months",
                )
            ],
            [
                InlineKeyboardButton(
                    text="6 месяцев — ⭐ 350",
                    callback_data="buy:6_months",
                )
            ],
            [
                InlineKeyboardButton(
                    text="12 месяцев — ⭐ 700",
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


def payment_keyboard(
    payment_id: int,
) -> InlineKeyboardMarkup:

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⭐ Оплатить",
                    callback_data=(
                        f"pay:{payment_id}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="user:buy",
                )
            ],
        ]
    )


# ============================================================
# START
# ============================================================

@router.message(
    CommandStart()
)
async def cmd_start(
    message: Message,
):

    user_id = int(
        message.from_user.id
    )

    username = (
        message.from_user.username
        or ""
    )

    first_name = (
        message.from_user.first_name
        or "Пользователь"
    )

    try:

        create_user(
            user_id=user_id,
            username=username,
            first_name=first_name,
        )

    except TypeError:
        try:
            create_user(
                user_id,
                username,
                first_name,
            )
        except Exception as exc:
            logger.error(
                "create_user error: %s",
                exc,
            )

    except Exception as exc:
        logger.error(
            "create_user error: %s",
            exc,
        )

    try:
        ensure_subscription(
            user_id
        )
    except Exception as exc:
        logger.error(
            "ensure_subscription error: %s",
            exc,
        )

    await message.answer(
        f"🧲 <b>{escape(SERVICE_NAME)}</b>\n\n"
        f"Привет, "
        f"<b>{escape(first_name)}</b>!\n\n"
        f"Здесь ты можешь управлять "
        f"своей VPN-подпиской.\n\n"
        f"Выбери нужный раздел ниже 👇",
        reply_markup=main_menu(
            user_id
        ),
    )


# ============================================================
# MAIN MENU
# ============================================================

@router.callback_query(
    F.data == "user:menu"
)
async def user_menu(
    callback: CallbackQuery,
):

    await callback.answer()

    user_id = int(
        callback.from_user.id
    )

    await callback.message.edit_text(
        f"🧲 <b>{escape(SERVICE_NAME)}</b>\n\n"
        f"Главное меню 👇",
        reply_markup=main_menu(
            user_id
        ),
    )


# ============================================================
# CABINET
# ============================================================

@router.callback_query(
    F.data == "user:cabinet"
)
async def user_cabinet(
    callback: CallbackQuery,
):

    await callback.answer()

    user_id = int(
        callback.from_user.id
    )

    try:
        ensure_subscription(
            user_id
        )
    except Exception as exc:
        logger.error(
            "cabinet sync error: %s",
            exc,
        )

    await callback.message.edit_text(
        cabinet_text(
            user_id
        ),
        reply_markup=cabinet_keyboard(
            user_id
        ),
    )


# ============================================================
# BUY
# ============================================================

@router.callback_query(
    F.data == "user:buy"
)
async def user_buy(
    callback: CallbackQuery,
):

    await callback.answer()

    await callback.message.edit_text(
        "💳 <b>Купить подписку</b>\n\n"
        "Выбери срок подписки:",
        reply_markup=buy_keyboard(),
    )


# ============================================================
# CREATE PAYMENT
# ============================================================

@router.callback_query(
    F.data.startswith("buy:")
)
async def choose_tariff(
    callback: CallbackQuery,
):

    await callback.answer()

    tariff_key = callback.data.split(
        ":",
        1,
    )[1]

    tariff = TARIFFS.get(
        tariff_key
    )

    if not tariff:
        await callback.message.answer(
            "❌ Тариф не найден."
        )
        return

    user_id = int(
        callback.from_user.id
    )

    try:

        payment_id = create_payment(
            user_id=user_id,
            tariff=tariff_key,
            days=int(
                tariff["days"]
            ),
            stars=int(
                tariff["stars"]
            ),
        )

    except TypeError:

        payment_id = create_payment(
            user_id,
            tariff_key,
            int(tariff["days"]),
            int(tariff["stars"]),
        )

    except Exception as exc:

        logger.exception(
            "create_payment error"
        )

        await callback.message.answer(
            "❌ Не удалось создать платёж."
        )
        return

    await callback.message.edit_text(
        "💳 <b>Оплата подписки</b>\n\n"
        f"Тариф: "
        f"<b>{escape(str(tariff['title']))}</b>\n"
        f"Срок: "
        f"<b>{tariff['days']} дней</b>\n"
        f"Стоимость: "
        f"<b>⭐ {tariff['stars']}</b>\n\n"
        f"Нажми кнопку ниже для оплаты.",
        reply_markup=payment_keyboard(
            payment_id
        ),
    )


# ============================================================
# TELEGRAM STARS PAYMENT
# ============================================================

@router.callback_query(
    F.data.startswith("pay:")
)
async def pay_tariff(
    callback: CallbackQuery,
):

    await callback.answer()

    payment_id = int(
        callback.data.split(
            ":",
            1,
        )[1]
    )

    user_id = int(
        callback.from_user.id
    )

    from database import get_payment

    payment = get_payment(
        payment_id
    )

    if not payment:
        await callback.message.answer(
            "❌ Платёж не найден."
        )
        return

    if int(
        payment.get(
            "user_id",
            0,
        )
        or 0
    ) != user_id:
        await callback.message.answer(
            "❌ Этот платёж принадлежит "
            "другому пользователю."
        )
        return

    if payment.get(
        "status"
    ) == "completed":

        await callback.message.answer(
            "✅ Этот платёж уже оплачен."
        )
        return

    tariff_key = payment.get(
        "tariff"
    )

    tariff = TARIFFS.get(
        tariff_key
    )

    if not tariff:
        await callback.message.answer(
            "❌ Тариф не найден."
        )
        return

    prices = [
        LabeledPrice(
            label=str(
                tariff["title"]
            ),
            amount=int(
                tariff["stars"]
            ),
        )
    ]

    payload = (
        f"magnit:"
        f"{payment_id}:"
        f"{tariff_key}"
    )

    await bot.send_invoice(
        chat_id=user_id,
        title=(
            f"{SERVICE_NAME} — "
            f"{tariff['title']}"
        ),
        description=(
            f"VPN-подписка "
            f"на {tariff['days']} дней."
        ),
        payload=payload,
        currency="XTR",
        prices=prices,
    )


# ============================================================
# PRE-CHECKOUT
# ============================================================

@router.pre_checkout_query()
async def process_pre_checkout(
    query,
):

    await query.answer(
        ok=True
    )


# ============================================================
# SUCCESSFUL PAYMENT
# ============================================================

@router.message(
    F.successful_payment
)
async def successful_payment(
    message: Message,
):

    payment = (
        message.successful_payment
    )

    if not payment:
        return

    payload = (
        payment.invoice_payload
        or ""
    )

    parts = payload.split(
        ":"
    )

    if len(parts) < 3:
        logger.error(
            "Invalid payment payload: %s",
            payload,
        )
        return

    try:
        payment_id = int(
            parts[1]
        )
    except ValueError:
        return

    tariff_key = parts[2]

    tariff = TARIFFS.get(
        tariff_key
    )

    if not tariff:
        return

    user_id = int(
        message.from_user.id
    )

    from database import (
        complete_payment,
    )

    try:

        complete_payment(
            payment_id,
            payment.telegram_payment_charge_id,
        )

    except TypeError:

        complete_payment(
            payment_id
        )

    except Exception as exc:

        logger.exception(
            "complete_payment error: %s",
            exc,
        )

    try:

        extend_subscription(
            user_id,
            int(
                tariff["days"]
            ),
            tariff_key,
        )

    except TypeError:

        extend_subscription(
            user_id,
            int(
                tariff["days"]
            ),
        )

    except Exception as exc:

        logger.exception(
            "extend_subscription error"
        )

        await message.answer(
            "⚠️ Оплата прошла, "
            "но произошла ошибка "
            "при активации подписки.\n\n"
            "Администратор уже получил "
            "информацию об ошибке."
        )
        return

    try:

        ensure_subscription(
            user_id
        )

    except Exception as exc:

        logger.error(
            "subscription sync error: %s",
            exc,
        )

    user = get_user(
        user_id
    )

    until = (
        user.get(
            "subscription_until",
            "",
        )
        if user
        else ""
    )

    try:
        until_text = format_date(
            until
        )
    except Exception:
        until_text = until or "—"

    await message.answer(
        "🎉 <b>Оплата прошла успешно!</b>\n\n"
        f"🧲 Тариф: "
        f"<b>{escape(str(tariff['title']))}</b>\n"
        f"📅 Срок: "
        f"<b>{tariff['days']} дней</b>\n"
        f"⏰ Действует до: "
        f"<b>{escape(str(until_text))}</b>\n\n"
        f"🔗 Твоя подписка:\n"
        f"<code>{escape(get_raw_link(user_id))}</code>\n\n"
        f"Можно открыть личный кабинет "
        f"через кнопку ниже.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👤 Личный кабинет",
                        url=get_cabinet_link(
                            user_id
                        ),
                    )
                ]
            ]
        ),
    )


# ============================================================
# TRIAL
# ============================================================

@router.callback_query(
    F.data == "user:trial"
)
async def user_trial(
    callback: CallbackQuery,
):

    await callback.answer()

    user_id = int(
        callback.from_user.id
    )

    try:

        success = use_trial(
            user_id,
            TRIAL_DAYS,
        )

    except TypeError:

        success = use_trial(
            user_id
        )

    except Exception as exc:

        logger.exception(
            "use_trial error"
        )

        await callback.message.answer(
            "❌ Не удалось активировать "
            "пробный период."
        )
        return

    if not success:

        await callback.message.edit_text(
            "❌ <b>Пробный период недоступен.</b>\n\n"
            "Возможно, ты уже использовал "
            "пробный период или у тебя "
            "есть активная подписка.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💳 Купить подписку",
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
            ),
        )
        return

    try:
        ensure_subscription(
            user_id
        )
    except Exception as exc:
        logger.error(
            "trial sync error: %s",
            exc,
        )

    user = get_user(
        user_id
    )

    until = (
        user.get(
            "subscription_until",
            "",
        )
        if user
        else ""
    )

    try:
        until_text = format_date(
            until
        )
    except Exception:
        until_text = until or "—"

    await callback.message.edit_text(
        "🎁 <b>Пробный период активирован!</b>\n\n"
        f"📅 Срок: "
        f"<b>{TRIAL_DAYS} дней</b>\n"
        f"⏰ До: "
        f"<b>{escape(str(until_text))}</b>\n\n"
        f"🔗 Подписка:\n"
        f"<code>{escape(get_raw_link(user_id))}</code>",
        reply_markup=cabinet_keyboard(
            user_id
        ),
    )


# ============================================================
# PROMO
# ============================================================

@router.callback_query(
    F.data == "user:promo"
)
async def user_promo(
    callback: CallbackQuery,
    state: FSMContext,
):

    await callback.answer()

    await state.set_state(
        PromoState.waiting_code
    )

    await callback.message.edit_text(
        "🎟 <b>Промокод</b>\n\n"
        "Отправь промокод одним сообщением:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data="promo:cancel",
                    )
                ]
            ]
        ),
    )


@router.callback_query(
    F.data == "promo:cancel"
)
async def promo_cancel(
    callback: CallbackQuery,
    state: FSMContext,
):

    await state.clear()
    await callback.answer()

    await callback.message.edit_text(
        f"🧲 <b>{escape(SERVICE_NAME)}</b>\n\n"
        "Главное меню 👇",
        reply_markup=main_menu(
            callback.from_user.id
        ),
    )


@router.message(
    PromoState.waiting_code
)
async def process_promo(
    message: Message,
    state: FSMContext,
):

    code = (
        message.text
        or ""
    ).strip()

    if not code:
        await message.answer(
            "❌ Введи промокод текстом."
        )
        return

    user_id = int(
        message.from_user.id
    )

    try:

        result = use_promo(
            user_id,
            code,
        )

    except Exception as exc:

        logger.exception(
            "use_promo error"
        )

        await state.clear()

        await message.answer(
            "❌ Ошибка при применении "
            "промокода."
        )
        return

    await state.clear()

    if not result:

        await message.answer(
            "❌ <b>Промокод недействителен.</b>\n\n"
            "Проверь правильность написания.",
            reply_markup=main_menu(
                user_id
            ),
        )
        return

    if isinstance(
        result,
        dict,
    ):

        days = int(
            result.get(
                "days",
                0,
            )
            or 0
        )

    else:

        try:
            days = int(
                result
            )
        except Exception:
            days = 0

    if days <= 0:

        await message.answer(
            "❌ Промокод не дал дней подписки.",
            reply_markup=main_menu(
                user_id
            ),
        )
        return

    try:

        extend_subscription(
            user_id,
            days,
            "promo",
        )

    except TypeError:

        extend_subscription(
            user_id,
            days,
        )

    try:
        ensure_subscription(
            user_id
        )
    except Exception as exc:
        logger.error(
            "promo sync error: %s",
            exc,
        )

    user = get_user(
        user_id
    )

    until = (
        user.get(
            "subscription_until",
            "",
        )
        if user
        else ""
    )

    try:
        until_text = format_date(
            until
        )
    except Exception:
        until_text = until or "—"

    await message.answer(
        "🎉 <b>Промокод активирован!</b>\n\n"
        f"➕ Начислено: "
        f"<b>{days} дней</b>\n"
        f"⏰ Подписка до: "
        f"<b>{escape(str(until_text))}</b>\n\n"
        f"🔗 Подписка:\n"
        f"<code>{escape(get_raw_link(user_id))}</code>",
        reply_markup=cabinet_keyboard(
            user_id
        ),
    )


# ============================================================
# SUPPORT
# ============================================================

@router.callback_query(
    F.data == "user:support"
)
async def user_support(
    callback: CallbackQuery,
):

    await callback.answer()

    username = TELEGRAM_USERNAME

    if username:
        support_text = (
            f"🆘 <b>Поддержка {escape(SERVICE_NAME)}</b>\n\n"
            f"Если возникли проблемы с VPN, "
            f"напиши администратору.\n\n"
            f"👤 @{escape(username)}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💬 Написать администратору",
                        url=(
                            f"https://t.me/"
                            f"{username}"
                        ),
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

    else:

        support_text = (
            "🆘 <b>Поддержка</b>\n\n"
            "Обратись к администратору."
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data="user:menu",
                    )
                ]
            ]
        )

    await callback.message.edit_text(
        support_text,
        reply_markup=keyboard,
    )


# ============================================================
# EXPIRATION LOOP
# ============================================================

async def expiration_loop():

    while True:

        try:

            expired = (
                expire_old_subscriptions()
            )

            if expired:
                logger.info(
                    "Expired subscriptions: %s",
                    expired,
                )

        except Exception as exc:

            logger.error(
                "expiration loop error: %s",
                exc,
            )

        await asyncio.sleep(
            300
        )


# ============================================================
# STARTUP
# ============================================================

async def on_startup():

    logger.info(
        "Starting %s...",
        SERVICE_NAME,
    )

    init_db()

    try:
        start_auto_sync()
    except Exception as exc:
        logger.error(
            "Auto sync start error: %s",
            exc,
        )

    asyncio.create_task(
        expiration_loop()
    )

    logger.info(
        "%s started successfully",
        SERVICE_NAME,
    )


# ============================================================
# ROUTER
# ============================================================

dp.include_router(
    router
)


# ============================================================
# MAIN
# ============================================================

async def main():

    await on_startup()

    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
    )


if __name__ == "__main__":

    try:
        asyncio.run(
            main()
        )

    except (
        KeyboardInterrupt,
        SystemExit,
    ):
        logger.info(
            "Bot stopped"
        )