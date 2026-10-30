"""Kirish nuqtasi.

  python -m lovebot          # botni ishga tushirish
  python -m lovebot check    # sozlama va kontentni tekshirish (bot ishga tushmaydi)
"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from .config import ConfigError, Settings, load_settings
from .content import Content, load_content
from .db import Database
from .handlers import build_router
from .middlewares import WhitelistMiddleware
from .scheduler import build_scheduler

log = logging.getLogger("lovebot")

BOT_COMMANDS = [
    BotCommand(command="start", description="Boshlash"),
    BotCommand(command="help", description="Nimalar bor"),
    BotCommand(command="timer", description="Birga bo'lganimizga qancha bo'ldi"),
    BotCommand(command="quiz", description="Viktorina"),
    BotCommand(command="sudo", description="sudo <buyruq>"),
    BotCommand(command="git_log", description="Bizning commit tariximiz"),
]


def _print_report(settings: Settings | None, content: Content, errors: list[str]) -> int:
    print("── LoveBot tekshiruvi ──")
    if settings is not None:
        print(f"✅ .env       MY_ID={settings.my_id} HER_ID={settings.her_id or '(setup rejimi)'} TZ={settings.tz.key}")
        print(f"             birga: {settings.together_since:%Y-%m-%d %H:%M}, sabab {settings.reason_time[0]:02d}:{settings.reason_time[1]:02d}, kayfiyat {settings.mood_time[0]:02d}:{settings.mood_time[1]:02d}")
        print(f"             joylashuv: {'bor' if settings.has_gift_location else 'YO‘Q'}")
    print(f"{'✅' if content.letters else '❌'} xatlar     {len(content.letters)} ta: " + ", ".join(l.slug for l in content.letters))
    print(f"{'✅' if content.reasons else '❌'} sabablar   {len(content.reasons)} ta")
    print(f"{'✅' if content.comfort else '❌'} dalda      {len(content.comfort)} ta")
    print(f"{'✅' if content.coupons else '❌'} kuponlar   {len(content.coupons)} ta")
    print(f"{'✅' if content.quiz else '❌'} viktorina  {len(content.quiz)} ta savol")
    if settings is not None:
        (sh, sm), (eh, em) = settings.love_window
        print(f"{'✅' if content.hourly else '❌'} soatlik    {len(content.hourly)} ta xabar, har {settings.love_interval} daqiqada, {sh:02d}:{sm:02d}–{eh:02d}:{em:02d}")
    else:
        print(f"{'✅' if content.hourly else '❌'} soatlik    {len(content.hourly)} ta xabar")
    print(f"{'✅' if content.game else '❌'} ikkalamiz  {len(content.game)} ta savol")
    print(f"{'✅' if content.days else '❌'} kalendar   {len(content.days)} kun")
    with_photo = sum(1 for l in content.letters + content.days if l.photo)
    print(f"{'✅' if content.gallery else '⚪'} rasmlar    galereya {len(content.gallery)} ta, start rasmi {'bor' if content.start_photo else 'yo‘q'}, rasmli xatlar {with_photo} ta")
    for p in content.problems:
        print(f"⚠️  {p}")
    for e in errors:
        print(f"❌ {e}")
    if errors:
        print("\nAvval xatolarni to'g'rilang.")
        return 1
    print("\nHammasi joyida. Ishga tushirish: python -m lovebot")
    return 0


def check() -> int:
    errors: list[str] = []
    settings: Settings | None = None
    try:
        settings = load_settings()
    except ConfigError as exc:
        errors.append(str(exc))
    content = load_content()
    return _print_report(settings, content, errors)


async def run() -> None:
    settings = load_settings()
    content = load_content()
    for problem in content.problems:
        log.warning("Kontent: %s", problem)
    if settings.setup_mode:
        log.warning("HER_ID=0 — SETUP REJIMI. Bot faqat ID ko'rsatadi; kunlik xabarlar o'chiq.")

    db = Database(settings.db_path)
    await db.connect()

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp["settings"] = settings
    dp["content"] = content
    dp["db"] = db
    dp.update.outer_middleware(WhitelistMiddleware(settings))
    dp.include_router(build_router())

    scheduler = build_scheduler(bot, db, content, settings)

    try:
        me = await bot.get_me()
        log.info("Bot ishga tushdi: @%s", me.username)
        await bot.set_my_commands(BOT_COMMANDS)
        scheduler.start()
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        await db.close()
        await bot.session.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "check":
        sys.exit(check())
    if cmd != "run":
        print(__doc__)
        sys.exit(2)
    try:
        asyncio.run(run())
    except ConfigError as exc:
        log.error("Sozlama xatosi: %s", exc)
        sys.exit(1)
    except (KeyboardInterrupt, SystemExit):
        log.info("To'xtatildi")


if __name__ == "__main__":
    main()
