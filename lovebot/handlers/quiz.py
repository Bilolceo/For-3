"""🎮 Viktorina — savollar bankidan har o'yinda QUIZ_PER_GAME ta tasodifiy savol.

Birinchi g'alaba — sovg'a joylashuvi (xarita). Keyingi g'alabalar — xarita + bonus xabar.
Xato bo'lsa savol qayta so'raladi (hint bilan), to'g'ri javobsiz oldinga o'tib bo'lmaydi.
"""

from __future__ import annotations

import html
import random

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ..config import Settings
from ..content import Content
from ..db import Database
from ..keyboards import Btn, QuizCb, quiz_question_kb, quiz_start_kb
from ..services import notify_admin, pick_love

router = Router(name="quiz")


class Quiz(StatesGroup):
    playing = State()


def _question_text(position: int, total: int, question_text: str) -> str:
    return f"❓ <b>Savol {position + 1}/{total}</b>\n\n{html.escape(question_text)}"


def _pick_order(total_questions: int, per_game: int) -> list[int]:
    count = min(per_game, total_questions)
    return random.sample(range(total_questions), count)


@router.message(F.text == Btn.QUIZ)
@router.message(F.text.in_({"/quiz", "/viktorina"}))
async def quiz_intro(message: Message, content: Content, db: Database, settings: Settings, state: FSMContext) -> None:
    await state.clear()
    if not content.quiz:
        await message.answer("Viktorina hali tayyor emas 🛠")
        return
    done = await db.quiz_completions()
    per_game = min(settings.quiz_per_game, len(content.quiz))
    extra = f"\n\n🏆 Buni {done} marta yutgansan. Savollar har safar boshqacha — yana o'ynab ko'r." if done else ""
    await message.answer(
        f"🎮 <b>Biz haqimizda viktorina</b>\n\n"
        f"{per_game} ta savol — {len(content.quiz)} tadan tasodifiy chiqadi. Hammasiga to'g'ri javob bersang — "
        "rostakam sovg'ang qayerdaligini ko'rsataman. 🎁\n"
        f"Xato qilsang, o'sha savol qayta so'raladi.{extra}",
        reply_markup=quiz_start_kb(),
    )


async def _send_question(message: Message, content: Content, order: list[int], position: int) -> None:
    question = content.quiz[order[position]]
    await message.answer(
        _question_text(position, len(order), question.question),
        reply_markup=quiz_question_kb(position, question),
    )


@router.callback_query(QuizCb.filter(F.action == "start"))
async def quiz_start(query: CallbackQuery, content: Content, settings: Settings, state: FSMContext) -> None:
    order = _pick_order(len(content.quiz), settings.quiz_per_game)
    await state.set_state(Quiz.playing)
    await state.update_data(order=order, position=0, wrong=0)
    await query.answer()
    if query.message:
        await query.message.edit_reply_markup(reply_markup=None)
        await _send_question(query.message, content, order, 0)


@router.callback_query(QuizCb.filter(F.action == "stop"))
async def quiz_stop(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await query.answer()
    if query.message:
        await query.message.edit_text("To'xtatildi. Xohlagan payting qaytadan boshlaysan 🙂")


@router.callback_query(Quiz.playing, QuizCb.filter(F.action == "answer"))
async def quiz_answer(
    query: CallbackQuery,
    callback_data: QuizCb,
    content: Content,
    db: Database,
    settings: Settings,
    state: FSMContext,
    is_admin: bool,
) -> None:
    data = await state.get_data()
    order: list[int] = list(data.get("order", []))
    position = int(data.get("position", 0))
    if callback_data.q != position or position >= len(order) or order[position] >= len(content.quiz):
        await query.answer("Bu eski savol 🙂")
        return

    question = content.quiz[order[position]]
    total = len(order)
    if callback_data.opt != question.answer:
        wrong = int(data.get("wrong", 0)) + 1
        await state.update_data(wrong=wrong)
        hint = f"\n💡 {html.escape(question.hint)}" if question.hint else ""
        await query.answer("❌ Yo'q, yana o'ylab ko'r…")
        if query.message:
            await query.message.edit_text(
                _question_text(position, total, question.question) + f"\n\n❌ <i>Noto'g'ri.</i>{hint}",
                reply_markup=quiz_question_kb(position, question),
            )
        return

    await query.answer("✅ To'g'ri!")
    if query.message:
        await query.message.edit_text(
            _question_text(position, total, question.question)
            + f"\n\n✅ <b>{html.escape(question.options[question.answer])}</b>"
        )

    position += 1
    if position < total:
        await state.update_data(position=position)
        if query.message:
            await _send_question(query.message, content, order, position)
        return

    # Hammasi to'g'ri — yakun
    wrong = int(data.get("wrong", 0))
    await state.clear()
    if not query.message:
        return
    wins_before = await db.quiz_completions()
    if wins_before == 0:
        await query.message.answer(
            "🎉 <b>Tabriklayman!</b>\n\n"
            "Hammasidan o'tding. Bu savollarga faqat sen javob berolarding — "
            "chunki bu bizning hikoyamiz.\n\n"
            "Rostakam sovg'ang mana shetta 👇"
        )
    else:
        await query.message.answer(
            f"🏆 <b>{wins_before + 1}-g'alaba!</b>\n\nBizni yaxshi bilasan — bu tasodif emas. Sovg'a joyi o'sha-o'sha 👇"
        )
    if settings.has_gift_location:
        await query.message.answer_venue(
            latitude=settings.gift_lat,  # type: ignore[arg-type]
            longitude=settings.gift_lon,  # type: ignore[arg-type]
            title=settings.gift_title,
            address=settings.gift_address or "📍",
        )
    else:
        await query.message.answer("📍 Joyini senga o'zim aytaman.")
    if wins_before > 0:
        bonus, _ = pick_love(content.hourly, [])
        if bonus is not None:
            await query.message.answer(f"🎁 Bonus:\n{html.escape(bonus.text)}")

    if not is_admin:
        await db.save_quiz_result(wrong)
        await notify_admin(
            query.bot,
            settings,
            f"🎮 <b>{html.escape(settings.her_name)} viktorinani tugatdi!</b> ({wins_before + 1}-marta)\n"
            f"Xato urinishlar: {wrong}. Joy yuborildi — tayyor bo'l 😉",
        )
