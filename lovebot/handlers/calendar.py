"""📅 30 kunlik kalendar — har kuni bitta yangi xat; kelajakdagilari qulf."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from ..config import Settings
from ..content import Content
from ..db import Database
from ..keyboards import Btn, DayCb, days_kb
from ..services import current_day, day_text, send_day_letter

router = Router(name="calendar")


@router.message(F.text == Btn.CALENDAR)
async def calendar_menu(message: Message, content: Content, db: Database, settings: Settings) -> None:
    if not content.days:
        await message.answer("Kalendar hali tayyor emas 🛠")
        return
    number = await current_day(db, content, settings)
    total = len(content.days)
    await send_day_letter(message.bot, message.chat.id, number, content)
    await db.set_calendar_last_sent(number)  # ertalabki job bugun qayta yubormasin
    await message.answer(
        f"Ochilgan kunlar: <b>{number}/{total}</b>. Oldingilarini qayta o'qisang bo'ladi, keyingisi ertaga ochiladi.",
        reply_markup=days_kb(number, total),
    )


@router.callback_query(DayCb.filter())
async def open_day(query: CallbackQuery, callback_data: DayCb, content: Content, db: Database, settings: Settings) -> None:
    number = await current_day(db, content, settings)
    if callback_data.day > number:
        left = callback_data.day - number
        await query.answer(f"🔒 Bu xat {left} kundan keyin ochiladi. Sal sabr — bu ham sovg'aning bir qismi.", show_alert=True)
        return
    letter = content.day(callback_data.day)
    if letter is None:
        await query.answer("Topilmadi", show_alert=True)
        return
    await query.answer()
    if query.message:
        await query.message.answer(day_text(callback_data.day, len(content.days), letter))
