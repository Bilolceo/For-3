"""⏳ Taymer — birga bo'lganimizga qancha bo'ldi + keyingi uchrashuvgacha countdown."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from ..config import Settings
from ..keyboards import Btn
from ..services import format_timer

router = Router(name="timer")


@router.message(F.text == Btn.TIMER)
@router.message(Command("timer", "taymer"))
async def show_timer(message: Message, settings: Settings) -> None:
    await message.answer(
        format_timer(settings.now(), settings.together_since, settings.next_date, settings.next_date_title)
    )
