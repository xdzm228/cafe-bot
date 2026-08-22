from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import database as db
from config import (
    ADMIN_IDS,
    CAFE_NAME,
    CAFE_ADDRESS,
    CAFE_HOURS,
    CAFE_PHONE,
    CAFE_OPEN_TIME,
    CAFE_CLOSE_TIME,
    MAX_BOOKING_DAYS_AHEAD,
)
from validators import validate_phone, parse_date, parse_time

router = Router()

BTN_BOOK = "📅 Забронювати столик"
BTN_ABOUT = "ℹ️ Про кафе"


class Reservation(StatesGroup):
    name = State()
    phone = State()
    phone_confirm = State()
    guests = State()
    date = State()
    time = State()
    comment = State()


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_BOOK)],
            [KeyboardButton(text=BTN_ABOUT)],
        ],
        resize_keyboard=True,
    )


def phone_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Так, все вірно", callback_data="phone_confirm:yes")],
            [InlineKeyboardButton(text="✏️ Ввести ще раз", callback_data="phone_confirm:no")],
        ]
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    await message.answer(
        f"Привіт, {message.from_user.first_name}! 😊☕\n\n"
        f"Раді бачити вас у боті кафе «{CAFE_NAME}»!\n"
        "Тут можна швидко й зручно забронювати столик, а ще ми ділитимемось "
        "смачними новинами та інколи питатимемо вашу думку в невеличких опитуваннях.\n\n"
        "Що робимо? Обирайте в меню нижче 👇",
        reply_markup=main_menu_kb(),
    )


@router.message(F.text == BTN_ABOUT)
async def about(message: Message):
    await message.answer(
        f"☕ Кафе «{CAFE_NAME}»\n"
        f"Адреса: {CAFE_ADDRESS}\n"
        f"Час роботи: {CAFE_HOURS}\n"
        f"Телефон: {CAFE_PHONE}"
    )


@router.message(F.text == BTN_BOOK)
@router.message(Command("book"))
async def start_booking(message: Message, state: FSMContext):
    await state.set_state(Reservation.name)
    await message.answer(
        "Чудово! Давайте оформимо бронювання 📝\n\nЯк вас звати?",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Command("cancel_booking"), Reservation.name)
@router.message(Command("cancel_booking"), Reservation.phone)
@router.message(Command("cancel_booking"), Reservation.phone_confirm)
@router.message(Command("cancel_booking"), Reservation.guests)
@router.message(Command("cancel_booking"), Reservation.date)
@router.message(Command("cancel_booking"), Reservation.time)
@router.message(Command("cancel_booking"), Reservation.comment)
async def cancel_booking(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Бронювання скасовано.", reply_markup=main_menu_kb())


@router.message(Reservation.name)
async def get_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Ім'я закоротке 🙂 Введіть, будь ласка, своє ім'я ще раз.")
        return
    await state.update_data(name=name)
    await state.set_state(Reservation.phone)
    await message.answer("Ваш номер телефону? (наприклад, +380501234567)")


@router.message(Reservation.phone)
async def get_phone(message: Message, state: FSMContext):
    phone = validate_phone(message.text)
    if not phone:
        await message.answer(
            "Схоже, номер введено некоректно 🤔\n"
            "Введіть, будь ласка, номер у форматі +380501234567 або 0501234567."
        )
        return
    await state.update_data(phone_pending=phone)
    await state.set_state(Reservation.phone_confirm)
    await message.answer(
        f"Перевірте, будь ласка, номер телефону:\n📱 {phone}\n\nВсе правильно?",
        reply_markup=phone_confirm_kb(),
    )


@router.callback_query(Reservation.phone_confirm, F.data.startswith("phone_confirm:"))
async def confirm_phone(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    answer = callback.data.split(":", 1)[1]

    if answer == "yes":
        data = await state.get_data()
        await state.update_data(phone=data.get("phone_pending"))
        await state.set_state(Reservation.guests)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Скільки буде гостей?")
    else:
        await state.set_state(Reservation.phone)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Добре, введіть номер телефону ще раз:")


@router.message(Reservation.guests)
async def get_guests(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or not (1 <= int(text) <= 50):
        await message.answer("Введіть, будь ласка, кількість гостей цифрою (від 1 до 50).")
        return
    await state.update_data(guests=int(text))
    await state.set_state(Reservation.date)
    await message.answer("На яку дату? (у форматі ДД.ММ.РРРР, наприклад 25.08.2026)")


@router.message(Reservation.date)
async def get_date(message: Message, state: FSMContext):
    date_obj = parse_date(message.text)
    if not date_obj:
        await message.answer(
            "Не вдалося розпізнати дату 🤔\n"
            "Введіть, будь ласка, у форматі ДД.ММ.РРРР, наприклад 25.08.2026."
        )
        return

    today = datetime.now().date()
    if date_obj < today:
        await message.answer(
            "Цю дату вже минуло 🙂 Оберіть, будь ласка, сьогоднішню або майбутню дату."
        )
        return

    max_date = today + timedelta(days=MAX_BOOKING_DAYS_AHEAD)
    if date_obj > max_date:
        await message.answer(
            f"Наразі бронювання приймаємо не більш ніж на {MAX_BOOKING_DAYS_AHEAD} днів наперед. "
            "Оберіть, будь ласка, ближчу дату."
        )
        return

    await state.update_data(date=date_obj.strftime("%d.%m.%Y"), date_iso=date_obj.isoformat())
    await state.set_state(Reservation.time)
    await message.answer(
        f"На який час? Ми працюємо з {CAFE_OPEN_TIME} до {CAFE_CLOSE_TIME}.\n"
        "Наприклад, 19:30"
    )


@router.message(Reservation.time)
async def get_time(message: Message, state: FSMContext):
    time_obj = parse_time(message.text)
    if not time_obj:
        await message.answer(
            "Не вдалося розпізнати час 🤔\n"
            "Введіть, будь ласка, у форматі ГГ:ХХ, наприклад 19:30."
        )
        return

    open_time = parse_time(CAFE_OPEN_TIME)
    close_time = parse_time(CAFE_CLOSE_TIME)
    if not (open_time <= time_obj <= close_time):
        await message.answer(
            f"Ми працюємо з {CAFE_OPEN_TIME} до {CAFE_CLOSE_TIME}. "
            "Оберіть, будь ласка, час у межах робочого часу."
        )
        return

    data = await state.get_data()
    date_iso = data.get("date_iso")
    if date_iso:
        date_obj = datetime.fromisoformat(date_iso).date()
        if date_obj == datetime.now().date() and time_obj < datetime.now().time():
            await message.answer(
                "Цей час на сьогодні вже минув ⏰ Оберіть, будь ласка, пізніший час."
            )
            return

    await state.update_data(time=time_obj.strftime("%H:%M"))
    await state.set_state(Reservation.comment)
    await message.answer("Є побажання чи коментар? Якщо немає — напишіть «-»")


@router.message(Reservation.comment)
async def get_comment(message: Message, state: FSMContext, bot: Bot):
    data = await state.update_data(comment=message.text)
    await db.add_reservation(
        user_id=message.from_user.id,
        name=data["name"],
        phone=data["phone"],
        guests=data["guests"],
        date=data["date"],
        time=data["time"],
        comment=data["comment"],
    )
    await state.clear()

    summary = (
        f"Ім'я: {data['name']}\n"
        f"Телефон: {data['phone']}\n"
        f"Гостей: {data['guests']}\n"
        f"Дата: {data['date']}\n"
        f"Час: {data['time']}\n"
        f"Коментар: {data['comment']}"
    )

    await message.answer(
        "✅ Дякуємо! Бронювання прийнято 🎉\n\n"
        + summary
        + "\n\nМи зв'яжемося з вами для підтвердження. До зустрічі! 🙌",
        reply_markup=main_menu_kb(),
    )

    for admin_id in ADMIN_IDS:
        try:
            username = f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id)
            await bot.send_message(admin_id, f"🆕 Нове бронювання від {username}\n\n{summary}")
        except Exception:
            pass
