from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

import database as db
from config import ADMIN_IDS, CAFE_NAME, CAFE_ADDRESS, CAFE_HOURS, CAFE_PHONE

router = Router()

BTN_BOOK = "📅 Забронювати столик"
BTN_ABOUT = "ℹ️ Про кафе"


class Reservation(StatesGroup):
    name = State()
    phone = State()
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


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    await message.answer(
        f"Привіт, {message.from_user.first_name}! 👋\n\n"
        f"Я бот кафе «{CAFE_NAME}».\n"
        "Допоможу забронювати столик, а ще надсилатиму новини та опитування.\n\n"
        "Оберіть дію в меню нижче:",
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
    await message.answer("Як вас звати?", reply_markup=ReplyKeyboardRemove())


@router.message(Command("cancel_booking"), Reservation.name)
@router.message(Command("cancel_booking"), Reservation.phone)
@router.message(Command("cancel_booking"), Reservation.guests)
@router.message(Command("cancel_booking"), Reservation.date)
@router.message(Command("cancel_booking"), Reservation.time)
@router.message(Command("cancel_booking"), Reservation.comment)
async def cancel_booking(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Бронювання скасовано.", reply_markup=main_menu_kb())


@router.message(Reservation.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Reservation.phone)
    await message.answer("Ваш номер телефону? (наприклад, +380001234567)")


@router.message(Reservation.phone)
async def get_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(Reservation.guests)
    await message.answer("Скільки буде гостей?")


@router.message(Reservation.guests)
async def get_guests(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Будь ласка, введіть кількість гостей цифрою.")
        return
    await state.update_data(guests=int(message.text))
    await state.set_state(Reservation.date)
    await message.answer("На яку дату? (наприклад, 25.08.2026)")


@router.message(Reservation.date)
async def get_date(message: Message, state: FSMContext):
    await state.update_data(date=message.text)
    await state.set_state(Reservation.time)
    await message.answer("На який час? (наприклад, 19:30)")


@router.message(Reservation.time)
async def get_time(message: Message, state: FSMContext):
    await state.update_data(time=message.text)
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
        "✅ Бронювання прийнято!\n\n" + summary + "\n\nМи зв'яжемося з вами для підтвердження. Дякуємо! 🙌",
        reply_markup=main_menu_kb(),
    )

    for admin_id in ADMIN_IDS:
        try:
            username = f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id)
            await bot.send_message(admin_id, f"🆕 Нове бронювання від {username}\n\n{summary}")
        except Exception:
            pass
