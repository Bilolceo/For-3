"""/start, /help, /id va dasturchicha hazillar."""

from __future__ import annotations

import html
import logging
import random

from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import FSInputFile, Message

from ..config import Settings
from ..content import Content
from ..db import Database
from ..keyboards import MAIN_MENU
from ..services import ensure_calendar_started, send_day_letter

router = Router(name="start")
log = logging.getLogger(__name__)

FAKE_COMMITS = [
    "feat: seni birinchi marta ko'rdim",
    "fix: yuragim tez urishini to'g'irlolmadim (wontfix)",
    "refactor: hayotimni sen atrofida qayta qurdim",
    "feat: har kuni seni o'ylash (cron: * * * * *)",
    "chore: bo'sh vaqtimni sen bilan almashtirdim",
    "perf: sen bilan kunlar tezroq o'tadi",
    "docs: seni yaxshi ko'rish sabablari ro'yxati yangilandi",
    "feat!: BREAKING CHANGE — sen mening eng muhim release'imsan",
]


@router.message(CommandStart())
async def cmd_start(message: Message, settings: Settings, db: Database, content: Content, is_admin: bool) -> None:
    name = html.escape(settings.my_name if is_admin else settings.her_name)
    if content.start_photo is not None:
        try:
            await message.answer_photo(FSInputFile(content.start_photo))
        except Exception:  # noqa: BLE001 — rasm ketmasa ham salom ketsin
            log.exception("Start rasmi yuborilmadi")
    await message.answer(
        f"Salom, {name} 🤍\n\n"
        "Bu bot faqat ikki kishi uchun — sen va men.\n"
        "Pastdagi tugmalardan boshla. Adashib qolsang: /help",
        reply_markup=MAIN_MENU,
    )
    # U birinchi marta /start bosgan kun — kalendarning 1-kuni
    if message.from_user and message.from_user.id == settings.her_id and content.days:
        if await db.calendar_start() is None:
            await ensure_calendar_started(db, settings)
            await message.answer("📅 Bugundan boshlab har kuni ertalab senga bitta yangi xat ochiladi — 30 kun. Birinchisi — hozir:")
            await send_day_letter(message.bot, message.chat.id, 1, content)
            await db.set_calendar_last_sent(1)


@router.message(Command("help", "menu"))
async def cmd_help(message: Message, is_admin: bool) -> None:
    text = (
        "<b>Nimalar bor:</b>\n"
        "📅 Bugungi kun — 30 kun, har kuni yangi xat\n"
        "📸 Bizning rasmlar — xotiralar albomi\n"
        "💌 Xatlar — kere paytda ochiladigan xatlar\n"
        "💝 Bugungi sabab — har kuni bittadan\n"
        "🎟 Kuponlar — ishlatsang menga xabar keladi\n"
        "⏳ Taymer — qachondan beri gaplashamiz\n"
        "🎮 Viktorina — oxirida sovg'a 😉\n"
        "🌤 Kayfiyat — bugun qanaqa o'tdi\n"
        "💬 Ikkalamiz — ikkalamizga bitta savol, javoblar birga ochiladi\n"
        "🎬 Kino kechasi — birga kino, kameralar yonida\n\n"
        "Har 2 soatda — kichik eslatma: seni yaxshi ko'raman 🤍\n\n"
        "<b>Yashirin buyruqlar:</b>\n"
        "<code>/sudo</code>, <code>/git_log</code>, <code>/ping</code>, <code>/whoami</code>"
    )
    if is_admin:
        text += "\n\n<b>Admin:</b> /stats, /send_reason, /send_mood, /send_love, /send_day, /preview_letters"
    await message.answer(text, reply_markup=MAIN_MENU)


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(f"Sizning ID: <code>{message.from_user.id}</code>" if message.from_user else "?")


@router.message(Command("sudo"))
async def cmd_sudo(message: Message, command: CommandObject, settings: Settings, is_admin: bool) -> None:
    arg = (command.args or "").strip()
    if is_admin:
        await message.answer("<code>$ sudo</code> — sen allaqachon root'san, bro 🙃")
        return
    if not arg:
        await message.answer("<code>usage: sudo &lt;buyruq&gt;</code>\nMasalan: <code>/sudo sev_meni</code>")
        return
    await message.answer(
        f"<code>[sudo] password for {html.escape(settings.her_name.lower())}: ********</code>\n"
        f"<code>$ {html.escape(arg)}</code>\n\n"
        "✅ <b>Permission granted.</b> Senga hammasi mumkin. ❤️"
    )


@router.message(Command("git_log", "git"))
async def cmd_git_log(message: Message, settings: Settings) -> None:
    lines = ["<code>$ git log --oneline --author=\"" + html.escape(settings.my_name) + "\"</code>", ""]
    for commit in FAKE_COMMITS:
        sha = "".join(random.choices("0123456789abcdef", k=7))
        lines.append(f"<code>{sha}</code> {html.escape(commit)}")
    await message.answer("\n".join(lines))


@router.message(Command("ping"))
async def cmd_ping(message: Message) -> None:
    await message.answer("pong 🏓 — men shettaman, doim.")


@router.message(Command("whoami"))
async def cmd_whoami(message: Message, settings: Settings, is_admin: bool) -> None:
    if is_admin:
        await message.answer("root — bu tizimning egasi.")
    else:
        await message.answer(f"{html.escape(settings.her_name)} — bu botning yagona sababi. 🤍")
