"""📸 Bizning rasmlar — content/gallery/ dagi rasmlar albom bo'lib yuboriladi."""

from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.types import FSInputFile, InputMediaPhoto, Message

from ..content import Content
from ..keyboards import Btn

router = Router(name="gallery")
log = logging.getLogger(__name__)
ALBUM_SIZE = 10  # Telegram: bitta albomda ko'pi bilan 10 ta


@router.message(F.text == Btn.GALLERY)
async def show_gallery(message: Message, content: Content) -> None:
    if not content.gallery:
        await message.answer("📸 Rasmlar hali qo'yilmagan… tez orada bo'ladi.")
        return
    await message.answer(f"📸 <b>Bizning rasmlar</b> — {len(content.gallery)} ta. Har biri — bitta xotira.")
    photos = content.gallery
    for i in range(0, len(photos), ALBUM_SIZE):
        chunk = photos[i : i + ALBUM_SIZE]
        media = [
            InputMediaPhoto(media=FSInputFile(p.path), caption=html.escape(p.caption) if p.caption else None)
            for p in chunk
        ]
        try:
            await message.answer_media_group(media)
        except Exception:  # noqa: BLE001 — bitta buzuq fayl butun albomni to'xtatmasin
            log.exception("Albom yuborilmadi (%s-%s)", i + 1, i + len(chunk))
            await message.answer("Bu albomni yuborolmadim — rasm fayllarini tekshirish kerak.")
