"""🎟 Kuponlar — u tugmani bosadi, senga xabar keladi."""

from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from ..config import Settings
from ..content import Content, Coupon
from ..db import Database
from ..keyboards import Btn, CouponCb, coupon_confirm_kb, coupon_view_kb, coupons_kb
from ..services import notify_admin

router = Router(name="coupons")

LIST_TEXT = (
    "🎟 <b>Kuponlar</b>\n\n"
    "Bular rostakam. Xohlagan payting ishlat — bajaraman. Bu mening so'zim.\n"
    "Raqam — necha marta qolgani."
)


def _coupon_text(coupon: Coupon, used: int) -> tuple[str, bool]:
    left_text = "cheksiz" if coupon.limit == 0 else f"{max(coupon.limit - used, 0)} ta qoldi"
    exhausted = coupon.limit != 0 and used >= coupon.limit
    text = f"{coupon.emoji} <b>{html.escape(coupon.title)}</b>\n\n{html.escape(coupon.description)}\n\n<i>{left_text}</i>"
    if exhausted:
        text += "\n\n✅ Bu kupon tugagan."
    return text, exhausted


@router.message(F.text == Btn.COUPONS)
async def list_coupons(message: Message, content: Content, db: Database) -> None:
    if not content.coupons:
        await message.answer("Kuponlar hali tayyor emas 🖨")
        return
    await message.answer(LIST_TEXT, reply_markup=coupons_kb(content.coupons, await db.coupon_uses()))


@router.callback_query(CouponCb.filter(F.action == "back"))
async def back_to_list(query: CallbackQuery, content: Content, db: Database) -> None:
    if query.message:
        await query.message.edit_text(LIST_TEXT, reply_markup=coupons_kb(content.coupons, await db.coupon_uses()))
    await query.answer()


@router.callback_query(CouponCb.filter(F.action == "view"))
async def view_coupon(query: CallbackQuery, callback_data: CouponCb, content: Content, db: Database) -> None:
    coupon = content.coupon(callback_data.id)
    if coupon is None:
        await query.answer("Kupon topilmadi", show_alert=True)
        return
    used = (await db.coupon_uses()).get(coupon.id, 0)
    text, exhausted = _coupon_text(coupon, used)
    if query.message:
        await query.message.edit_text(text, reply_markup=coupon_view_kb(coupon, exhausted))
    await query.answer()


@router.callback_query(CouponCb.filter(F.action == "use"))
async def ask_confirm(query: CallbackQuery, callback_data: CouponCb, content: Content) -> None:
    coupon = content.coupon(callback_data.id)
    if coupon is None:
        await query.answer("Kupon topilmadi", show_alert=True)
        return
    if query.message:
        await query.message.edit_text(
            f"{coupon.emoji} <b>{html.escape(coupon.title)}</b>\n\nRostdan hozir ishlatasanmi?",
            reply_markup=coupon_confirm_kb(coupon),
        )
    await query.answer()


@router.callback_query(CouponCb.filter(F.action == "confirm"))
async def confirm_use(
    query: CallbackQuery, callback_data: CouponCb, content: Content, db: Database, settings: Settings, is_admin: bool
) -> None:
    coupon = content.coupon(callback_data.id)
    if coupon is None:
        await query.answer("Kupon topilmadi", show_alert=True)
        return
    used = (await db.coupon_uses()).get(coupon.id, 0)
    if coupon.limit != 0 and used >= coupon.limit:
        await query.answer("Bu kupon tugagan 🙂", show_alert=True)
        return
    if is_admin:
        await query.answer("Bu kuponlar sen uchun emas, bro 😄", show_alert=True)
        return

    used = await db.use_coupon(coupon.id)
    text, exhausted = _coupon_text(coupon, used)
    if query.message:
        await query.message.edit_text(
            text + "\n\n🎉 <b>Ishlatildi!</b> Menga xabar ketdi — endi bajarish menda.",
            reply_markup=coupon_view_kb(coupon, exhausted),
        )
    await query.answer("Qabul qilindi 🎉")
    await notify_admin(
        query.bot,
        settings,
        f"🎟 <b>{html.escape(settings.her_name)} kupon ishlatdi:</b> {coupon.emoji} {html.escape(coupon.title)}\n"
        f"<i>{html.escape(coupon.description)}</i>",
    )
