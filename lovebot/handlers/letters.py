"""💌 Xatlar — "qachon ochish kerak" xatlari. Tugma orqali yoki /slug buyrug'i bilan."""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from ..config import Settings
from ..content import Content
from ..db import Database
from ..keyboards import Btn, LetterCb, letters_kb
from ..services import notify_admin, send_letter

router = Router(name="letters")
COMMAND_RE = re.compile(r"^/([a-z0-9_]{1,32})(?:@\w+)?$")


@router.message(F.text == Btn.LETTERS)
async def list_letters(message: Message, content: Content, db: Database) -> None:
    if not content.letters:
        await message.answer("Hozircha xat yo'q… lekin tez orada bo'ladi. ✉️")
        return
    opened = await db.letters_opened()
    await message.answer(
        "💌 <b>Xatlar</b>\n\n"
        "Har birini o'sha payt kelganda och. Shoshilma — hech qayerga ketmaydi.\n"
        "✉️ — hali ochilmagan, 📖 — o'qilgan",
        reply_markup=letters_kb(content.letters, opened),
    )


async def _open_letter(slug: str, chat_id: int, content: Content, db: Database, settings: Settings, is_admin: bool, bot) -> bool:
    letter = content.letter(slug)
    if letter is None:
        return False
    await send_letter(bot, chat_id, letter)
    if not is_admin:
        opened = await db.letters_opened()
        await db.mark_letter_opened(slug)
        if slug not in opened:
            await notify_admin(bot, settings, f"💌 {settings.her_name} xatni ochdi: <b>{letter.title}</b>")
    return True


@router.callback_query(LetterCb.filter())
async def open_letter_cb(
    query: CallbackQuery, callback_data: LetterCb, content: Content, db: Database, settings: Settings, is_admin: bool
) -> None:
    ok = await _open_letter(callback_data.slug, query.from_user.id, content, db, settings, is_admin, query.bot)
    await query.answer() if ok else await query.answer("Bu xat topilmadi 🤔", show_alert=True)
    if ok and query.message:
        opened = await db.letters_opened()
        try:
            await query.message.edit_reply_markup(reply_markup=letters_kb(content.letters, opened))
        except Exception:  # noqa: BLE001 — markup o'zgarmagan bo'lsa Telegram xato beradi, muhim emas
            pass


@router.message(F.text.regexp(COMMAND_RE))
async def open_letter_cmd(message: Message, content: Content, db: Database, settings: Settings, is_admin: bool) -> None:
    match = COMMAND_RE.match(message.text or "")
    slug = match.group(1) if match else ""
    ok = await _open_letter(slug, message.chat.id, content, db, settings, is_admin, message.bot)
    if not ok:
        await message.answer("<code>command not found</code> 🙂\nPastdagi tugmalarni bos yoki /help")
