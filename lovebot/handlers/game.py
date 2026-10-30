"""💬 "Ikkalamiz" — ikkalangizga bitta savol; ikkalangiz javob bergandan keyingina javoblar ochiladi."""

from __future__ import annotations

import html
import logging
import random

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

from ..config import Settings
from ..content import Content
from ..db import Database
from ..keyboards import Btn, GameCb, game_new_kb, game_skip_kb

router = Router(name="game")
log = logging.getLogger(__name__)

INTRO = (
    "💬 <b>Ikkalamiz</b>\n\n"
    "Qoida oddiy: bot ikkalamizga bitta savol yuboradi. Har birimiz javob yozamiz — "
    "lekin javoblar faqat <b>ikkalamiz</b> yozgandan keyin ochiladi. Ko'chirib bo'mmaydi 😄"
)


def _pick_question(content: Content, asked: list[str]) -> str:
    """Avval hali so'ralmaganlardan; hammasi so'ralgan bo'lsa — istalganidan."""
    pool = [q for q in content.game if q not in asked] or content.game
    return random.choice(pool)


async def _broadcast(bot: Bot, settings: Settings, text: str, reply_markup=None) -> None:
    for uid in settings.allowed_ids:
        try:
            await bot.send_message(uid, text, reply_markup=reply_markup)
        except Exception:  # noqa: BLE001 — biri botni bloklagan bo'lsa ham ikkinchisiga ketsin
            log.exception("O'yin xabari yuborilmadi: %s", uid)


async def _start_round(bot: Bot, db: Database, content: Content, settings: Settings) -> None:
    question = _pick_question(content, await db.asked_questions())
    await db.start_round(question)
    await _broadcast(
        bot,
        settings,
        f"❓ <b>Savol:</b>\n{html.escape(question)}\n\n<i>Javobingni shunchaki yozib yubor.</i>",
        reply_markup=game_skip_kb(),
    )


async def _reveal(bot: Bot, db: Database, settings: Settings, round_id: int, question: str) -> None:
    answers = await db.round_answers(round_id)
    await db.finish_round(round_id)
    lines = [f"❓ <b>{html.escape(question)}</b>", ""]
    for uid in settings.allowed_ids:
        if uid in answers:
            lines.append(f"<b>{html.escape(settings.name_of(uid))}:</b> {html.escape(answers[uid])}")
    lines.append("\n🤍 Javoblar ochildi!")
    await _broadcast(bot, settings, "\n".join(lines), reply_markup=game_new_kb())


@router.message(F.text == Btn.GAME)
async def game_menu(message: Message, content: Content, db: Database, settings: Settings) -> None:
    if not content.game:
        await message.answer("Savollar hali yo'q 🛠")
        return
    active = await db.active_round()
    if active is None:
        await message.answer(INTRO)
        await _start_round(message.bot, db, content, settings)
        return
    round_id, question = active
    answers = await db.round_answers(round_id)
    if message.from_user and message.from_user.id in answers:
        await message.answer("⏳ Sen javob berding. Ikkinchisini kutamiz…", reply_markup=game_skip_kb())
    else:
        await message.answer(
            f"❓ <b>Savol:</b>\n{html.escape(question)}\n\n<i>Javobingni shunchaki yozib yubor.</i>",
            reply_markup=game_skip_kb(),
        )


@router.callback_query(GameCb.filter(F.action == "new"))
async def game_new(query: CallbackQuery, content: Content, db: Database, settings: Settings) -> None:
    await query.answer()
    if await db.active_round() is not None:
        await query.answer("Hozirgi savol hali tugamadi-ku 🙂", show_alert=True)
        return
    await _start_round(query.bot, db, content, settings)


@router.callback_query(GameCb.filter(F.action == "skip"))
async def game_skip(query: CallbackQuery, db: Database, settings: Settings) -> None:
    await query.answer()
    active = await db.active_round()
    if active is None:
        return
    round_id, _ = active
    await db.finish_round(round_id)
    who = settings.name_of(query.from_user.id)
    await _broadcast(query.bot, settings, f"⏭ {html.escape(who)} bu savolni o'tkazib yubordi.", reply_markup=game_new_kb())


@router.message(F.text, ~F.text.startswith("/"))
async def game_answer(message: Message, db: Database, settings: Settings) -> None:
    """Faol savol bo'lsa — oddiy matn javob sifatida qabul qilinadi."""
    active = await db.active_round()
    if active is None or not message.from_user:
        await message.answer("Tushunmadim 🙂 Pastdagi tugmalarni bos yoki /help")
        return
    round_id, question = active
    uid = message.from_user.id
    answers = await db.round_answers(round_id)
    if uid in answers:
        await message.answer("Sen allaqachon javob bergansan — ikkinchisini kutamiz ⏳")
        return
    await db.answer_round(round_id, uid, message.text or "")
    answers[uid] = message.text or ""
    if settings.allowed_ids <= set(answers):
        await _reveal(message.bot, db, settings, round_id, question)
        return
    await message.answer("✅ Javobing qabul qilindi. Ikkinchisi yozishini kutamiz…")
    other = next((u for u in settings.allowed_ids if u not in answers), None)
    if other is not None:
        try:
            await message.bot.send_message(
                other, f"👀 {html.escape(settings.name_of(uid))} javob berdi. Navbat senda!", reply_markup=game_skip_kb()
            )
        except Exception:  # noqa: BLE001
            log.exception("Eslatma yuborilmadi: %s", other)
