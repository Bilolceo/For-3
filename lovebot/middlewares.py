"""Whitelist: botdan faqat ikki kishi foydalana oladi."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update, User

from .config import Settings

log = logging.getLogger(__name__)

FORBIDDEN = (
    "<code>403 Forbidden</code>\n"
    "Bu yurak band. 🔒\n\n"
    "<i>Bu bot ikki kishi uchun. Sen ulardan emassan.</i>"
)


class WhitelistMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None:
            return None  # kanal postlari va h.k. — bizga kerak emas

        if user.id in self.settings.allowed_ids:
            data["is_admin"] = user.id == self.settings.my_id
            return await handler(event, data)

        # Setup rejimi: HER_ID hali yo'q — kim yozsa o'z ID sini ko'rsin
        if self.settings.setup_mode and isinstance(event, Update) and event.message:
            await event.message.answer(
                "⚙️ <b>Setup rejimi</b>\n"
                f"Sizning Telegram ID: <code>{user.id}</code>\n\n"
                "Shu raqamni <code>.env</code> dagi <code>HER_ID</code> ga yozib, botni qayta ishga tushir."
            )
            return None

        log.info("Begona foydalanuvchi rad etildi: id=%s username=%s", user.id, user.username)
        if isinstance(event, Update):
            if event.message:
                await event.message.answer(FORBIDDEN)
            elif event.callback_query:
                await event.callback_query.answer("403 Forbidden 🔒", show_alert=True)
        return None
