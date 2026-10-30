"""🌤 Kayfiyat — kunlik so'rov; "Charchadim" bo'lsa senga xabar va unga dalda."""

from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from ..config import Settings
from ..content import Content
from ..db import Database
from ..keyboards import MOOD_LABELS, Btn, MoodCb, mood_kb
from ..services import comfort_message, notify_admin

router = Router(name="mood")

REPLIES = {
    "great": "Zo'r! Kuning yaxshi o'tgan bo'lsa — men ham xursandman ☀️",
    "ok": "Oddiy kun ham yaxshi kun. Ertaga yaxshiroq bo'ladi — so'z beraman 🤍",
}


@router.message(F.text == Btn.MOOD)
async def mood_menu(message: Message, db: Database, settings: Settings) -> None:
    history = await db.recent_moods(7)
    lines = ["🌤 <b>Bugun kuning qanday o'tdi?</b>"]
    if history:
        lines.append("\n<b>Oxirgi kunlar:</b>")
        for day, mood in history:
            lines.append(f"{day[5:]} — {MOOD_LABELS.get(mood, mood)}")
    await message.answer("\n".join(lines), reply_markup=mood_kb())


@router.callback_query(MoodCb.filter())
async def mood_answer(
    query: CallbackQuery, callback_data: MoodCb, content: Content, db: Database, settings: Settings, is_admin: bool
) -> None:
    mood = callback_data.mood
    label = MOOD_LABELS.get(mood, mood)
    if not is_admin:
        await db.set_mood(settings.now().date().isoformat(), mood)
    await query.answer("Qabul qilindi 🤍")
    if query.message:
        await query.message.edit_text(f"Bugungi kayfiyat: <b>{label}</b>")

    if mood == "tired":
        if query.message:
            await query.message.answer(comfort_message(content, settings.her_name))
        if not is_admin:
            await notify_admin(
                query.bot,
                settings,
                f"🌧 <b>{html.escape(settings.her_name)} bugun charchagan.</b>\n"
                "Qo'ng'iroq qil yoki shirinlik yubor — bot o'z ishini qildi, qolgani senda 😉",
            )
    elif query.message:
        await query.message.answer(REPLIES.get(mood, "🤍"))
