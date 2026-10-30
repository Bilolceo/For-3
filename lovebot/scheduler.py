"""Kunlik vazifalar: ertalabki sabab va kechki kayfiyat so'rovi."""

from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import Settings
from .content import Content
from .db import Database
from .services import send_daily_calendar, send_daily_reason, send_love_message, send_mood_prompt

log = logging.getLogger(__name__)


async def _calendar_job(bot: Bot, db: Database, content: Content, settings: Settings) -> None:
    try:
        number = await send_daily_calendar(bot, db, content, settings)
        log.info("Kalendar: %s", f"{number}-kun yuborildi" if number else "yuborilmadi (boshlanmagan / bugun bor)")
    except Exception:  # noqa: BLE001
        log.exception("Kalendar xatini yuborishda xato")


async def _love_job(bot: Bot, db: Database, content: Content, settings: Settings) -> None:
    now = settings.now()
    if not settings.in_love_window(now):
        log.debug("Soatlik xabar: %s vaqt oralig'idan tashqarida", now.strftime("%H:%M"))
        return
    try:
        sent = await send_love_message(bot, db, content, settings)
        log.info("Soatlik xabar: %s", "yuborildi" if sent else "ro'yxat bo'sh")
    except Exception:  # noqa: BLE001
        log.exception("Soatlik xabar yuborishda xato")


def _love_trigger(settings: Settings) -> CronTrigger:
    """LOVE_INTERVAL_MINUTES ga mos cron: 60 dan kichik bo'lsa daqiqa, aks holda soat qadam."""
    (sh, _), (eh, em) = settings.love_window
    last_hour = eh if em > 0 else max(eh - 1, sh)  # 23:00 gacha → oxirgi soat 22
    n = settings.love_interval
    if n < 60:
        return CronTrigger(minute=f"*/{n}", hour=f"{sh}-{last_hour}", timezone=settings.tz)
    return CronTrigger(minute=0, hour=f"{sh}-{last_hour}/{n // 60}", timezone=settings.tz)


async def _reason_job(bot: Bot, db: Database, content: Content, settings: Settings) -> None:
    try:
        sent = await send_daily_reason(bot, db, content, settings)
        log.info("Kunlik sabab: %s", "yuborildi" if sent else "o'tkazib yuborildi (bugun bor edi / ro'yxat bo'sh)")
    except Exception:  # noqa: BLE001
        log.exception("Kunlik sabab yuborishda xato")


async def _mood_job(bot: Bot, settings: Settings) -> None:
    try:
        await send_mood_prompt(bot, settings)
        log.info("Kayfiyat so'rovi yuborildi")
    except Exception:  # noqa: BLE001
        log.exception("Kayfiyat so'rovini yuborishda xato")


def build_scheduler(bot: Bot, db: Database, content: Content, settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.tz)
    if settings.setup_mode:
        log.warning("Setup rejimi: HER_ID yo'q, kunlik xabarlar rejalashtirilmadi")
        return scheduler

    rh, rm = settings.reason_time
    mh, mm = settings.mood_time
    scheduler.add_job(
        _reason_job,
        CronTrigger(hour=rh, minute=rm, timezone=settings.tz),
        args=[bot, db, content, settings],
        id="daily_reason",
        misfire_grace_time=3600,  # bot 1 soatgacha kech ishga tushsa ham yuboradi
        coalesce=True,
    )
    scheduler.add_job(
        _mood_job,
        CronTrigger(hour=mh, minute=mm, timezone=settings.tz),
        args=[bot, settings],
        id="daily_mood",
        misfire_grace_time=3600,
        coalesce=True,
    )
    if content.days:
        ch, cm = settings.calendar_time
        scheduler.add_job(
            _calendar_job,
            CronTrigger(hour=ch, minute=cm, timezone=settings.tz),
            args=[bot, db, content, settings],
            id="daily_calendar",
            misfire_grace_time=3600,
            coalesce=True,
        )
    if content.hourly:
        scheduler.add_job(
            _love_job,
            _love_trigger(settings),
            args=[bot, db, content, settings],
            id="love_message",
            misfire_grace_time=300,
            coalesce=True,
        )
    return scheduler
