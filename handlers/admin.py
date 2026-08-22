import asyncio
from datetime import datetime

from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from config import ADMIN_IDS

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class Broadcast(StatesGroup):
    waiting_text = State()


class Poll(StatesGroup):
    waiting_question = State()
    waiting_options = State()


def reservation_kb(reservation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Видалити", callback_data=f"del_res:{reservation_id}")]
        ]
    )


def format_reservation(row) -> str:
    rid, name, phone, guests, date, time, comment, status = row
    return (
        f"#{rid} | {status}\n"
        f"{name}, {phone}\n"
        f"{date} {time}, гостей: {guests}\n"
        f"Коментар: {comment}"
    )


@router.message(Command("admin"))
async def cmd_admin_help(message: Message):
    if not is_admin(message.from_user.id):
        return
    count = await db.count_users()
    await message.answer(
        "🛠 Адмін-панель\n\n"
        f"Користувачів у базі: {count}\n\n"
        "/broadcast — розіслати новину/повідомлення всім\n"
        "/poll — створити та розіслати опитування\n"
        "/reservations — останні бронювання столиків (з кнопкою видалення)\n"
        "/clear_past — видалити всі прострочені бронювання одним махом\n"
        "/cancel — скасувати поточну дію"
    )


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(Broadcast.waiting_text)
    await message.answer(
        "Надішліть повідомлення для розсилки — можна текст, фото або відео з підписом.\n"
        "Воно буде розіслано всім користувачам бота.\n\n"
        "Для скасування — /cancel"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if await state.get_state() is None:
        await message.answer("Немає чого скасовувати.")
        return
    await state.clear()
    await message.answer("Скасовано.")


@router.message(Broadcast.waiting_text)
async def do_broadcast(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_ids = await db.get_all_user_ids()
    sent, failed = 0, 0
    status = await message.answer(f"Починаю розсилку на {len(user_ids)} користувачів...")

    for uid in user_ids:
        try:
            await message.copy_to(chat_id=uid)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # щоб не впертися в ліміти Telegram

    await status.edit_text(f"✅ Розсилку завершено.\nНадіслано: {sent}\nНе доставлено: {failed}")


@router.message(Command("poll"))
async def cmd_poll(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(Poll.waiting_question)
    await message.answer("Введіть текст запитання для опитування.\n\nДля скасування — /cancel")


@router.message(Poll.waiting_question)
async def poll_question(message: Message, state: FSMContext):
    await state.update_data(question=message.text)
    await state.set_state(Poll.waiting_options)
    await message.answer(
        "Тепер введіть варіанти відповіді через кому (від 2 до 10).\n"
        "Наприклад: Так, Ні, Ще не вирішив(ла)"
    )


@router.message(Poll.waiting_options)
async def poll_options(message: Message, state: FSMContext, bot: Bot):
    options = [o.strip() for o in message.text.split(",") if o.strip()]
    if len(options) < 2:
        await message.answer("Потрібно щонайменше 2 варіанти відповіді. Спробуйте ще раз.")
        return
    options = options[:10]

    data = await state.get_data()
    question = data["question"]
    await state.clear()

    user_ids = await db.get_all_user_ids()
    sent, failed = 0, 0
    status = await message.answer(f"Розсилаю опитування {len(user_ids)} користувачам...")

    for uid in user_ids:
        try:
            await bot.send_poll(chat_id=uid, question=question, options=options, is_anonymous=True)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await status.edit_text(f"✅ Опитування розіслано.\nНадіслано: {sent}\nНе доставлено: {failed}")


@router.message(Command("reservations"))
async def cmd_reservations(message: Message):
    if not is_admin(message.from_user.id):
        return
    rows = await db.get_reservations(limit=15)
    if not rows:
        await message.answer("Бронювань поки немає.")
        return

    await message.answer("📋 Останні бронювання (натисніть 🗑, щоб видалити):")
    for row in rows:
        rid = row[0]
        await message.answer(format_reservation(row), reply_markup=reservation_kb(rid))


@router.callback_query(F.data.startswith("del_res:"))
async def cb_delete_reservation(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас немає прав для цієї дії.", show_alert=True)
        return

    reservation_id = int(callback.data.split(":", 1)[1])
    deleted = await db.delete_reservation(reservation_id)

    if deleted:
        await callback.message.edit_text(
            callback.message.text + "\n\n🗑 Видалено", reply_markup=None
        )
        await callback.answer("Бронювання видалено")
    else:
        await callback.answer("Це бронювання вже видалено раніше.", show_alert=True)


@router.message(Command("clear_past"))
async def cmd_clear_past(message: Message):
    if not is_admin(message.from_user.id):
        return

    rows = await db.get_reservation_dates()
    today = datetime.now().date()
    ids_to_delete = []

    for reservation_id, date_text in rows:
        try:
            res_date = datetime.strptime(date_text, "%d.%m.%Y").date()
        except (ValueError, TypeError):
            continue
        if res_date < today:
            ids_to_delete.append(reservation_id)

    count = await db.delete_reservations_by_ids(ids_to_delete)

    if count:
        await message.answer(f"🗑 Видалено прострочених бронювань: {count}")
    else:
        await message.answer("Прострочених бронювань не знайдено — все чисто ✨")
