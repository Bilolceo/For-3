"""💝 Bugungi sabab."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from ..config import Settings
from ..content import Content
from ..db import Database
from ..keyboards import Btn
from ..services import send_daily_reason, todays_reason

router = Router(name="reasons")


@router.message(F.text == Btn.REASON)
async def todays_reason_btn(message: Message, content: Content, db: Database, settings: Settings, is_admin: bool) -> None:
    if not content.reasons:
        await message.answer("Ro'yxat hali bo'sh… lekin sabab ko'p. 🤍")
        return
    today = settings.now().date().isoformat()
    _, last_day = await db.reason_state()
    if last_day != today and not is_admin:
        # Bugungi hali yuborilmagan (masalan, bot o'chiq bo'lgan) — hozir yuboramiz
        await send_daily_reason(message.bot, db, content, settings)
        return
    text = await todays_reason(db, content)
    if text is None:
        hour, minute = settings.reason_time
        await message.answer(f"Bugungi sabab {hour:02d}:{minute:02d} da keladi. Sal sabr qil 😉")
        return
    await message.answer(text)
