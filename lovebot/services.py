"""Handler va scheduler birgalikda ishlatadigan mantiq (toza funksiyalar + yuborish)."""

from __future__ import annotations

import html
import logging
import random
from datetime import date, datetime

from aiogram import Bot
from aiogram.types import FSInputFile

from .config import Settings
from .content import Content, Letter, LoveMessage
from .db import Database
from .keyboards import mood_kb

log = logging.getLogger(__name__)


# ── Taymer ──────────────────────────────────────────────────────────────
def _parts(delta_seconds: int) -> tuple[int, int, int, int]:
    days, rest = divmod(delta_seconds, 86_400)
    hours, rest = divmod(rest, 3_600)
    minutes, seconds = divmod(rest, 60)
    return days, hours, minutes, seconds


def _human(delta_seconds: int) -> str:
    d, h, m, s = _parts(delta_seconds)
    return f"{d} kun, {h} soat, {m} daqiqa, {s} soniya"


def format_timer(now: datetime, since: datetime, next_date: datetime | None, next_title: str) -> str:
    seconds = int((now - since).total_seconds())
    if seconds < 0:
        together = "⏳ Hali boshlanmagan… lekin yaqin qoldi 😉"
    else:
        together = (
            f"💞 {since:%d.%m.%Y} dan beri gaplashamiz:\n<b>{_human(seconds)}</b>"
        )

    lines = [together]
    if next_date is not None:
        left = int((next_date - now).total_seconds())
        if left <= 0:
            lines.append(f"\n🎉 <b>{html.escape(next_title)}</b> — bugun!")
        else:
            lines.append(f"\n📅 {html.escape(next_title)} gacha:\n<b>{_human(left)}</b>")
    return "\n".join(lines)


# ── Kunlik sabab ────────────────────────────────────────────────────────
def pick_reason(reasons: list[str], cursor: int) -> tuple[str, int, bool]:
    """(matn, yangi cursor, ro'yxat tugaganmi). Tugagach tasodifiy tanlanadi."""
    if not reasons:
        return "", cursor, True
    if cursor < len(reasons):
        return reasons[cursor], cursor + 1, False
    return random.choice(reasons), cursor, True


async def send_daily_reason(bot: Bot, db: Database, content: Content, settings: Settings, *, force: bool = False) -> str | None:
    """Bugungi sababni yuboradi. force=False bo'lsa, bugun yuborilgan bo'lsa qaytadan yubormaydi."""
    today = settings.now().date().isoformat()
    cursor, last_day = await db.reason_state()
    if last_day == today and not force:
        return None
    text, new_cursor, exhausted = pick_reason(content.reasons, cursor)
    if not text:
        return None
    number = cursor + 1 if not exhausted else None
    header = f"💝 Seni yaxshi ko'rishimning <b>{number}-sababi</b>" if number else "💝 Seni yaxshi ko'rishimning yana bir sababi"
    message = f"{header}\n\n{html.escape(text)}"
    await bot.send_message(settings.her_id, message)
    await db.set_reason_state(new_cursor, today)
    return message


async def todays_reason(db: Database, content: Content) -> str | None:
    """Bugun yuborilgan sababni (cursor - 1) qaytaradi; yuborilmagan bo'lsa None."""
    cursor, _ = await db.reason_state()
    if cursor == 0 or not content.reasons:
        return None
    index = min(cursor, len(content.reasons)) - 1
    return f"💝 Seni yaxshi ko'rishimning <b>{index + 1}-sababi</b>\n\n{html.escape(content.reasons[index])}"


# ── Xatlar ──────────────────────────────────────────────────────────────
CAPTION_LIMIT = 1024  # Telegram: rasm ostidagi matn chegarasi


async def send_text_with_media(bot: Bot, chat_id: int, text: str, letter: Letter) -> None:
    """Rasm bo'lsa — rasm + matn (sig'sa caption, sig'masa alohida), ovoz bo'lsa — oxirida ovoz."""
    if letter.photo is not None:
        try:
            if len(text) <= CAPTION_LIMIT:
                await bot.send_photo(chat_id, FSInputFile(letter.photo), caption=text)
                text = ""
            else:
                await bot.send_photo(chat_id, FSInputFile(letter.photo))
        except Exception:  # noqa: BLE001 — rasm ketmasa ham matn ketsin
            log.exception("Rasm yuborilmadi: %s", letter.photo)
    if text:
        await bot.send_message(chat_id, text)
    if letter.voice is not None:
        try:
            await bot.send_voice(chat_id, FSInputFile(letter.voice))
        except Exception:  # noqa: BLE001
            log.exception("Ovozli xabar yuborilmadi: %s", letter.voice)


async def send_letter(bot: Bot, chat_id: int, letter: Letter) -> None:
    await send_text_with_media(bot, chat_id, f"💌 <b>{html.escape(letter.title)}</b>\n\n{letter.body}", letter)


# ── Kunlik kalendar ─────────────────────────────────────────────────────
def day_number(start: date, today: date, total: int) -> int:
    """Kalendar kuni: 1 dan total gacha (oxirgi kundan keyin ham total qoladi)."""
    return max(1, min((today - start).days + 1, total))


async def ensure_calendar_started(db: Database, settings: Settings) -> date:
    """Kalendar birinchi marta ochilganda bugungi kun 1-kun bo'ladi."""
    raw = await db.calendar_start()
    if raw:
        return date.fromisoformat(raw)
    today = settings.now().date()
    await db.set_calendar_start(today.isoformat())
    return today


async def current_day(db: Database, content: Content, settings: Settings) -> int:
    start = await ensure_calendar_started(db, settings)
    return day_number(start, settings.now().date(), len(content.days))


def day_text(number: int, total: int, letter: Letter) -> str:
    return f"📅 <b>{number}-kun / {total}</b> — <b>{html.escape(letter.title)}</b>\n\n{letter.body}"


async def send_day_letter(bot: Bot, chat_id: int, number: int, content: Content) -> bool:
    letter = content.day(number)
    if letter is None:
        return False
    await send_text_with_media(bot, chat_id, day_text(number, len(content.days), letter), letter)
    return True


async def send_daily_calendar(bot: Bot, db: Database, content: Content, settings: Settings) -> int | None:
    """Ertalabki kalendar: bugungi kun hali yuborilmagan bo'lsa — yuboradi. Qaytaradi: kun raqami."""
    if not content.days or await db.calendar_start() is None:
        return None  # u hali /start bosmagan — kalendar boshlanmagan
    number = await current_day(db, content, settings)
    if number <= await db.calendar_last_sent():
        return None
    await bot.send_message(settings.her_id, f"🌅 Xayrli tong, {html.escape(settings.her_name)}. Bugungi xating ochildi:")
    await send_day_letter(bot, settings.her_id, number, content)
    await db.set_calendar_last_sent(number)
    return number


# ── Kayfiyat ────────────────────────────────────────────────────────────
async def send_mood_prompt(bot: Bot, settings: Settings) -> None:
    await bot.send_message(
        settings.her_id,
        f"Hey, {html.escape(settings.her_name)} 🌙\nBugun kuning qanday o'tdi?",
        reply_markup=mood_kb(),
    )


def comfort_message(content: Content, her_name: str) -> str:
    line = random.choice(content.comfort) if content.comfort else "Men doim yoningdaman. 🤍"
    return f"🤍 {html.escape(line)}"


# ── Soatlik sevgi xabarlari ─────────────────────────────────────────────
THEME_EMOJI = {"sevgi": "❤️", "dalda": "🤍", "birgalikda": "🤝"}


def pick_love(messages: list[LoveMessage], bag: list[int]) -> tuple[LoveMessage | None, list[int]]:
    """Takrorlanmas tanlov: xalta bo'shasa — qayta aralashtiriladi."""
    if not messages:
        return None, []
    valid = [i for i in bag if 0 <= i < len(messages)]
    if not valid:
        valid = list(range(len(messages)))
        random.shuffle(valid)
    index = valid.pop()
    return messages[index], valid


async def send_love_message(bot: Bot, db: Database, content: Content, settings: Settings) -> str | None:
    message, bag = pick_love(content.hourly, await db.love_bag())
    if message is None:
        return None
    emoji = THEME_EMOJI.get(message.theme, "💌")
    text = f"{emoji} {html.escape(message.text)}"
    await bot.send_message(settings.her_id, text)
    await db.set_love_bag(bag)
    return text


async def notify_admin(bot: Bot, settings: Settings, text: str) -> None:
    try:
        await bot.send_message(settings.my_id, text)
    except Exception:  # noqa: BLE001
        log.exception("Adminga xabar yuborilmadi")
