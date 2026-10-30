"""Tugmalar va callback ma'lumotlari."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from .content import Coupon, Letter, QuizQuestion


class Btn:
    LETTERS = "💌 Xatlar"
    REASON = "💝 Bugungi sabab"
    COUPONS = "🎟 Kuponlar"
    TIMER = "⏳ Taymer"
    QUIZ = "🎮 Viktorina"
    MOOD = "🌤 Kayfiyat"
    GAME = "💬 Ikkalamiz"
    CALENDAR = "📅 Bugungi kun"
    GALLERY = "📸 Bizning rasmlar"


MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=Btn.CALENDAR), KeyboardButton(text=Btn.REASON)],
        [KeyboardButton(text=Btn.LETTERS), KeyboardButton(text=Btn.COUPONS)],
        [KeyboardButton(text=Btn.TIMER), KeyboardButton(text=Btn.QUIZ)],
        [KeyboardButton(text=Btn.MOOD), KeyboardButton(text=Btn.GAME)],
        [KeyboardButton(text=Btn.GALLERY)],
    ],
    resize_keyboard=True,
    input_field_placeholder="Tugmalardan birini tanla…",
)


class LetterCb(CallbackData, prefix="letter"):
    slug: str


class CouponCb(CallbackData, prefix="coupon"):
    action: str  # view | use | confirm | back
    id: str = "-"


class QuizCb(CallbackData, prefix="quiz"):
    action: str  # start | answer | stop
    q: int = 0
    opt: int = 0


class MoodCb(CallbackData, prefix="mood"):
    mood: str  # great | ok | tired


class GameCb(CallbackData, prefix="game"):
    action: str  # new | skip


class DayCb(CallbackData, prefix="day"):
    day: int


def days_kb(current: int, total: int, per_row: int = 6) -> InlineKeyboardMarkup:
    """1..total kunlar; current gacha ochiq, qolgani 🔒."""
    buttons = []
    for n in range(1, total + 1):
        if n < current:
            text = f"{n}"
        elif n == current:
            text = f"📖 {n}"
        else:
            text = "🔒"
        buttons.append(InlineKeyboardButton(text=text, callback_data=DayCb(day=n).pack()))
    rows = [buttons[i : i + per_row] for i in range(0, len(buttons), per_row)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def game_new_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🎲 Yana bitta savol", callback_data=GameCb(action="new").pack())]]
    )


def game_skip_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⏭ Bu savolni o'tkazib yuborish", callback_data=GameCb(action="skip").pack())]]
    )


MOOD_LABELS = {
    "great": "☀️ A'lo",
    "ok": "⛅ Oddiy",
    "tired": "🌧 Charchadim",
}


def letters_kb(letters: list[Letter], opened: dict[str, int]) -> InlineKeyboardMarkup:
    rows = []
    for letter in letters:
        mark = "📖" if letter.slug in opened else "✉️"
        rows.append(
            [InlineKeyboardButton(text=f"{mark} {letter.title}", callback_data=LetterCb(slug=letter.slug).pack())]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def coupons_kb(coupons: list[Coupon], uses: dict[str, int]) -> InlineKeyboardMarkup:
    rows = []
    for c in coupons:
        used = uses.get(c.id, 0)
        left = "∞" if c.limit == 0 else max(c.limit - used, 0)
        text = f"{c.emoji} {c.title} · {left}"
        rows.append([InlineKeyboardButton(text=text, callback_data=CouponCb(action="view", id=c.id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def coupon_view_kb(coupon: Coupon, exhausted: bool) -> InlineKeyboardMarkup:
    rows = []
    if not exhausted:
        rows.append([InlineKeyboardButton(text="✅ Ishlatish", callback_data=CouponCb(action="use", id=coupon.id).pack())])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=CouponCb(action="back").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def coupon_confirm_kb(coupon: Coupon) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Ha, ishlataman 🎉", callback_data=CouponCb(action="confirm", id=coupon.id).pack()),
                InlineKeyboardButton(text="Yo'q, keyinroq", callback_data=CouponCb(action="view", id=coupon.id).pack()),
            ]
        ]
    )


def quiz_start_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🚀 Boshlash", callback_data=QuizCb(action="start").pack())]]
    )


def quiz_question_kb(index: int, question: QuizQuestion) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=opt, callback_data=QuizCb(action="answer", q=index, opt=i).pack())]
        for i, opt in enumerate(question.options)
    ]
    rows.append([InlineKeyboardButton(text="✖️ To'xtatish", callback_data=QuizCb(action="stop").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def mood_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=MoodCb(mood=key).pack()) for key, label in MOOD_LABELS.items()]
        ]
    )
