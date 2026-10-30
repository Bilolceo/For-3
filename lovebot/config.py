"""Sozlamalar: .env faylidan o'qiladi va tekshiriladi."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
CONTENT_DIR = BASE_DIR / "content"


class ConfigError(RuntimeError):
    """Noto'g'ri yoki yetishmayotgan sozlama."""


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _required(name: str) -> str:
    value = _env(name)
    if not value:
        raise ConfigError(f"{name} .env faylida ko'rsatilmagan")
    return value


def _int(name: str, default: int = 0) -> int:
    raw = _env(name, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} butun son bo'lishi kerak, hozir: {raw!r}") from exc


def _float_opt(name: str) -> float | None:
    raw = _env(name)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} son bo'lishi kerak, hozir: {raw!r}") from exc


def _datetime(name: str, tz: ZoneInfo, required: bool) -> datetime | None:
    raw = _env(name)
    if not raw:
        if required:
            raise ConfigError(f"{name} .env faylida ko'rsatilmagan")
        return None
    try:
        value = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ConfigError(
            f"{name} formati noto'g'ri ({raw!r}). Misol: 2025-02-14 yoki 2025-02-14 19:30"
        ) from exc
    return value if value.tzinfo else value.replace(tzinfo=tz)


def _time(name: str, default: str) -> tuple[int, int]:
    raw = _env(name, default)
    try:
        hour, minute = (int(part) for part in raw.split(":", 1))
    except ValueError as exc:
        raise ConfigError(f"{name} formati HH:MM bo'lishi kerak, hozir: {raw!r}") from exc
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ConfigError(f"{name} noto'g'ri vaqt: {raw!r}")
    return hour, minute


LOVE_INTERVALS = (5, 10, 15, 20, 30, 60, 120, 180, 240)


def _window(name: str, default: str) -> tuple[tuple[int, int], tuple[int, int]]:
    raw = _env(name, default)
    try:
        start_raw, end_raw = raw.split("-", 1)
        start = tuple(int(p) for p in start_raw.strip().split(":", 1))
        end = tuple(int(p) for p in end_raw.strip().split(":", 1))
    except ValueError as exc:
        raise ConfigError(f"{name} formati HH:MM-HH:MM bo'lishi kerak, hozir: {raw!r}") from exc
    for h, m in (start, end):
        if not (0 <= h <= 24 and 0 <= m < 60):
            raise ConfigError(f"{name} noto'g'ri vaqt: {raw!r}")
    if start >= end:
        raise ConfigError(f"{name}: boshlanish tugashdan oldin bo'lishi kerak ({raw!r})")
    return start, end  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    my_id: int
    her_id: int
    my_name: str
    her_name: str
    together_since: datetime
    next_date: datetime | None
    next_date_title: str
    tz: ZoneInfo
    reason_time: tuple[int, int]
    mood_time: tuple[int, int]
    gift_lat: float | None
    gift_lon: float | None
    gift_title: str
    gift_address: str
    db_path: Path
    love_interval: int  # daqiqa
    love_window: tuple[tuple[int, int], tuple[int, int]]  # (HH,MM) dan (HH,MM) gacha
    calendar_time: tuple[int, int]
    quiz_per_game: int

    def name_of(self, user_id: int) -> str:
        return self.my_name if user_id == self.my_id else self.her_name

    def in_love_window(self, when: datetime) -> bool:
        (sh, sm), (eh, em) = self.love_window
        minutes = when.hour * 60 + when.minute
        return sh * 60 + sm <= minutes < eh * 60 + em

    @property
    def setup_mode(self) -> bool:
        """HER_ID hali kiritilmagan — bot faqat ID ko'rsatib turadi."""
        return self.her_id == 0

    @property
    def allowed_ids(self) -> frozenset[int]:
        return frozenset(i for i in (self.my_id, self.her_id) if i)

    @property
    def has_gift_location(self) -> bool:
        return self.gift_lat is not None and self.gift_lon is not None

    def now(self) -> datetime:
        return datetime.now(self.tz)


def load_settings(env_file: Path | None = None) -> Settings:
    load_dotenv(env_file or BASE_DIR / ".env", override=False)

    tz_name = _env("TZ", "Asia/Tashkent")
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"TZ noma'lum: {tz_name!r}") from exc

    db_path = Path(_env("DB_PATH", "data/lovebot.db"))
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_path

    settings = Settings(
        bot_token=_required("BOT_TOKEN"),
        my_id=_int("MY_ID"),
        her_id=_int("HER_ID"),
        my_name=_env("MY_NAME", "Men"),
        her_name=_env("HER_NAME", "Sen"),
        together_since=_datetime("TOGETHER_SINCE", tz, required=True),  # type: ignore[arg-type]
        next_date=_datetime("NEXT_DATE", tz, required=False),
        next_date_title=_env("NEXT_DATE_TITLE", "Keyingi uchrashuvimiz"),
        tz=tz,
        reason_time=_time("REASON_TIME", "08:30"),
        mood_time=_time("MOOD_TIME", "20:30"),
        gift_lat=_float_opt("GIFT_LAT"),
        gift_lon=_float_opt("GIFT_LON"),
        gift_title=_env("GIFT_TITLE", "Sovg'ang shu yerda 🎁"),
        gift_address=_env("GIFT_ADDRESS", ""),
        db_path=db_path,
        love_interval=_int("LOVE_INTERVAL_MINUTES", 60),
        love_window=_window("LOVE_WINDOW", "09:00-23:00"),
        calendar_time=_time("CALENDAR_TIME", "09:00"),
        quiz_per_game=_int("QUIZ_PER_GAME", 6),
    )

    if settings.quiz_per_game < 1:
        raise ConfigError("QUIZ_PER_GAME kamida 1 bo'lishi kerak")

    if settings.love_interval not in LOVE_INTERVALS:
        raise ConfigError(f"LOVE_INTERVAL_MINUTES quyidagilardan biri bo'lsin: {', '.join(map(str, LOVE_INTERVALS))}")
    if settings.my_id == 0:
        raise ConfigError("MY_ID ko'rsatilmagan — avval o'z Telegram ID ingizni yozing (/id)")
    if (settings.gift_lat is None) != (settings.gift_lon is None):
        raise ConfigError("GIFT_LAT va GIFT_LON ikkalasi ham bo'lishi kerak (yoki ikkalasi ham bo'sh)")
    return settings
