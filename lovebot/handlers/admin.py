"""Admin (faqat MY_ID): statistika va kunlik xabarlarni qo'lda yuborish."""

from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from ..config import Settings
from ..content import Content
from ..db import Database
from ..keyboards import MOOD_LABELS
from ..services import (
    current_day,
    send_daily_reason,
    send_day_letter,
    send_letter,
    send_love_message,
    send_mood_prompt,
)

router = Router(name="admin")


async def _admin_only(message: Message, is_admin: bool) -> bool:
    return is_admin


# Barcha admin buyruqlari faqat MY_ID uchun; boshqalar uchun router o'tkazib yuboriladi
router.message.filter(_admin_only)


@router.message(Command("stats"))
async def cmd_stats(message: Message, content: Content, db: Database, settings: Settings) -> None:
    opened = await db.letters_opened()
    uses = await db.coupon_uses()
    cursor, last_day = await db.reason_state()
    moods = await db.recent_moods(7)
    quiz_done = await db.quiz_completions()

    lines = [f"📊 <b>Statistika</b> ({html.escape(settings.her_name)})", ""]
    lines.append(f"💌 Xatlar: {len(opened)}/{len(content.letters)} ochilgan")
    for letter in content.letters:
        mark = f"📖 ×{opened[letter.slug]}" if letter.slug in opened else "✉️"
        lines.append(f"   {mark} {html.escape(letter.title)}")
    lines.append(f"\n💝 Sabablar: {cursor}/{len(content.reasons)} yuborilgan (oxirgi: {last_day or '—'})")
    lines.append(f"\n🎟 Kuponlar:")
    for c in content.coupons:
        limit = "∞" if c.limit == 0 else c.limit
        lines.append(f"   {c.emoji} {html.escape(c.title)}: {uses.get(c.id, 0)}/{limit}")
    lines.append(f"\n🎮 Viktorina tugatilgan: {quiz_done} marta")
    bag = await db.love_bag()
    lines.append(f"\n💌 Soatlik xabarlar: {len(content.hourly)} ta, joriy aylanishda {len(bag) if bag else len(content.hourly)} ta qoldi")
    lines.append(f"💬 Ikkalamiz: {await db.rounds_finished()} savol o'ynalgan / {len(content.game)} ta")
    start = await db.calendar_start()
    if start:
        lines.append(f"📅 Kalendar: {start} dan boshlangan, {await current_day(db, content, settings)}/{len(content.days)}-kun")
    else:
        lines.append(f"📅 Kalendar: hali boshlanmagan (u /start bosganda boshlanadi), {len(content.days)} kun tayyor")
    if moods:
        lines.append("\n🌤 Kayfiyat (oxirgi 7 kun):")
        for day, mood in moods:
            lines.append(f"   {day} — {MOOD_LABELS.get(mood, mood)}")
    if content.problems:
        lines.append("\n⚠️ Kontent muammolari:")
        lines.extend(f"   • {html.escape(p)}" for p in content.problems)
    await message.answer("\n".join(lines))


@router.message(Command("send_reason"))
async def cmd_send_reason(message: Message, content: Content, db: Database, settings: Settings) -> None:
    if settings.setup_mode:
        await message.answer("HER_ID hali sozlanmagan.")
        return
    sent = await send_daily_reason(message.bot, db, content, settings, force=True)
    await message.answer("Yuborildi ✅" if sent else "Sabablar ro'yxati bo'sh ❌")


@router.message(Command("send_mood"))
async def cmd_send_mood(message: Message, settings: Settings) -> None:
    if settings.setup_mode:
        await message.answer("HER_ID hali sozlanmagan.")
        return
    await send_mood_prompt(message.bot, settings)
    await message.answer("Kayfiyat so'rovi yuborildi ✅")


@router.message(Command("send_love"))
async def cmd_send_love(message: Message, content: Content, db: Database, settings: Settings) -> None:
    if settings.setup_mode:
        await message.answer("HER_ID hali sozlanmagan.")
        return
    sent = await send_love_message(message.bot, db, content, settings)
    await message.answer("Yuborildi ✅" if sent else "hourly/ bo'sh ❌")


@router.message(Command("send_day"))
async def cmd_send_day(message: Message, command: CommandObject, content: Content, db: Database, settings: Settings) -> None:
    """/send_day — bugungi kunni unga yuboradi; /send_day 7 — 7-kunni o'zingga ko'rsatadi (tekshirish)."""
    if not content.days:
        await message.answer("days/ bo'sh ❌")
        return
    arg = (command.args or "").strip()
    if arg.isdigit():
        ok = await send_day_letter(message.bot, message.chat.id, int(arg), content)
        if not ok:
            await message.answer(f"Bunday kun yo'q (1–{len(content.days)})")
        return
    if settings.setup_mode:
        await message.answer("HER_ID hali sozlanmagan.")
        return
    number = await current_day(db, content, settings)
    await send_day_letter(message.bot, settings.her_id, number, content)
    await db.set_calendar_last_sent(number)
    await message.answer(f"{number}-kun yuborildi ✅")


@router.message(Command("preview_letters"))
async def cmd_preview_letters(message: Message, content: Content) -> None:
    """Hamma xatlarni o'zingga yuboradi — tekshirish uchun."""
    if not content.letters:
        await message.answer("Xatlar yo'q.")
        return
    for letter in content.letters:
        await send_letter(message.bot, message.chat.id, letter)
    await message.answer(f"{len(content.letters)} ta xat ko'rsatildi. Buyruqlar: " + ", ".join(f"/{l.slug}" for l in content.letters))
