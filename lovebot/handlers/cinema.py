"""🎬 Kino kechasi — Mini App havolasi (Telegram ichida yoki brauzerda) va ikkinchi tomonga chaqiruv."""

from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from ..config import Settings
from ..keyboards import Btn
from ..web.auth import make_token

router = Router(name="cinema")


def cinema_kb(settings: Settings, uid: int) -> InlineKeyboardMarkup:
    rows = []
    if settings.public_url.startswith("https://"):  # Telegram web_app faqat https ni qabul qiladi
        rows.append([InlineKeyboardButton(text="🎬 Telegram'da ochish", web_app=WebAppInfo(url=f"{settings.public_url}/app/"))])
    rows.append(
        [InlineKeyboardButton(text="🌐 Brauzerda ochish", url=f"{settings.public_url}/app/?t={make_token(uid, settings.bot_token)}")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text == Btn.CINEMA)
async def cinema(message: Message, settings: Settings, is_admin: bool) -> None:
    if not settings.cinema_enabled:
        await message.answer("🎬 Kino xonasi hali sozlanmagan (PUBLIC_URL yo'q).")
        return
    if not message.from_user:
        return
    uid = message.from_user.id
    await message.answer(
        "🎬 <b>Kino kechasi</b>\n\n"
        "Ikkalamiz bitta xonaga kiramiz: kino sinxron ketadi (biri bossa — ikkinchisida ham), "
        "yonida kameralar.\n\n"
        "Havola 12 soat ishlaydi. Telegram ichida kamera ochilmasa — <b>Brauzerda ochish</b>ni bos "
        "(kompyuterda eng yaxshi ishlaydi).",
        reply_markup=cinema_kb(settings, uid),
    )
    other = settings.her_id if is_admin else settings.my_id
    if other and other != uid:
        try:
            await message.bot.send_message(
                other,
                f"🍿 <b>{html.escape(settings.name_of(uid))} kinoga chaqiryapti!</b>\nKir — xonada kutyapti.",
                reply_markup=cinema_kb(settings, other),
            )
        except Exception:  # noqa: BLE001 — ikkinchi tomon botni ochmagan bo'lishi mumkin
            await message.answer("Ikkinchi tomonga xabar yetmadi — u hali botga /start bosmagan bo'lishi mumkin.")
