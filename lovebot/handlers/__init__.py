from aiogram import Router

from . import admin, calendar, cinema, coupons, gallery, game, letters, mood, quiz, reasons, start, timer


def build_router() -> Router:
    root = Router(name="root")
    # Tartib muhim: letters noma'lum /buyruq larni, game esa oddiy matnni ushlaydi — ikkalasi oxirida
    root.include_routers(
        start.router,
        admin.router,
        calendar.router,
        gallery.router,
        cinema.router,
        reasons.router,
        coupons.router,
        timer.router,
        quiz.router,
        mood.router,
        letters.router,
        game.router,
    )
    return root
