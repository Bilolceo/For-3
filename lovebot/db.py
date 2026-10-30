"""SQLite ustida yupqa qatlam. Bot holatini (xatlar, kuponlar, kayfiyat, viktorina) saqlaydi."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS letters_opened (
    slug       TEXT PRIMARY KEY,
    opened_at  TEXT NOT NULL,
    open_count INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS coupon_uses (
    coupon_id TEXT NOT NULL,
    used_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS moods (
    day        TEXT PRIMARY KEY,
    mood       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quiz_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    finished_at TEXT NOT NULL,
    wrong_tries INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS game_rounds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS game_answers (
    round_id INTEGER NOT NULL REFERENCES game_rounds(id),
    user_id  INTEGER NOT NULL,
    answer   TEXT NOT NULL,
    PRIMARY KEY (round_id, user_id)
);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database.connect() chaqirilmagan")
        return self._conn

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    # ── kv ──────────────────────────────────────────────────────────────
    async def get_kv(self, key: str, default: str | None = None) -> str | None:
        async with self.conn.execute("SELECT value FROM kv WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
        return row["value"] if row else default

    async def set_kv(self, key: str, value: Any) -> None:
        await self.conn.execute(
            "INSERT INTO kv(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        await self.conn.commit()

    # ── xatlar ──────────────────────────────────────────────────────────
    async def mark_letter_opened(self, slug: str) -> None:
        await self.conn.execute(
            "INSERT INTO letters_opened(slug, opened_at) VALUES(?, ?) "
            "ON CONFLICT(slug) DO UPDATE SET open_count = open_count + 1",
            (slug, _utcnow()),
        )
        await self.conn.commit()

    async def letters_opened(self) -> dict[str, int]:
        async with self.conn.execute("SELECT slug, open_count FROM letters_opened") as cur:
            return {row["slug"]: row["open_count"] for row in await cur.fetchall()}

    # ── kunlik sabab ────────────────────────────────────────────────────
    async def reason_state(self) -> tuple[int, str | None]:
        """(keyingi yuboriladigan indeks, oxirgi yuborilgan kun)."""
        cursor = int(await self.get_kv("reason_cursor", "0") or 0)
        last_day = await self.get_kv("reason_last_day")
        return cursor, last_day

    async def set_reason_state(self, cursor: int, day: str) -> None:
        await self.set_kv("reason_cursor", cursor)
        await self.set_kv("reason_last_day", day)

    # ── kuponlar ────────────────────────────────────────────────────────
    async def coupon_uses(self) -> dict[str, int]:
        async with self.conn.execute(
            "SELECT coupon_id, COUNT(*) AS n FROM coupon_uses GROUP BY coupon_id"
        ) as cur:
            return {row["coupon_id"]: row["n"] for row in await cur.fetchall()}

    async def use_coupon(self, coupon_id: str) -> int:
        await self.conn.execute(
            "INSERT INTO coupon_uses(coupon_id, used_at) VALUES(?, ?)", (coupon_id, _utcnow())
        )
        await self.conn.commit()
        return (await self.coupon_uses()).get(coupon_id, 0)

    # ── kayfiyat ────────────────────────────────────────────────────────
    async def set_mood(self, day: str, mood: str) -> None:
        await self.conn.execute(
            "INSERT INTO moods(day, mood, created_at) VALUES(?, ?, ?) "
            "ON CONFLICT(day) DO UPDATE SET mood = excluded.mood, created_at = excluded.created_at",
            (day, mood, _utcnow()),
        )
        await self.conn.commit()

    async def recent_moods(self, limit: int = 7) -> list[tuple[str, str]]:
        async with self.conn.execute(
            "SELECT day, mood FROM moods ORDER BY day DESC LIMIT ?", (limit,)
        ) as cur:
            return [(row["day"], row["mood"]) for row in await cur.fetchall()]

    # ── viktorina ───────────────────────────────────────────────────────
    async def save_quiz_result(self, wrong_tries: int) -> None:
        await self.conn.execute(
            "INSERT INTO quiz_results(finished_at, wrong_tries) VALUES(?, ?)",
            (_utcnow(), wrong_tries),
        )
        await self.conn.commit()

    async def quiz_completions(self) -> int:
        async with self.conn.execute("SELECT COUNT(*) AS n FROM quiz_results") as cur:
            row = await cur.fetchone()
        return int(row["n"]) if row else 0

    # ── kunlik kalendar ─────────────────────────────────────────────────
    async def calendar_start(self) -> str | None:
        """Kalendar boshlangan kun (ISO sana) yoki None."""
        return await self.get_kv("calendar_start")

    async def set_calendar_start(self, day: str) -> None:
        await self.set_kv("calendar_start", day)

    async def calendar_last_sent(self) -> int:
        return int(await self.get_kv("calendar_last_sent", "0") or 0)

    async def set_calendar_last_sent(self, day_number: int) -> None:
        await self.set_kv("calendar_last_sent", day_number)

    # ── soatlik xabarlar: takrorlanmas "xalta" ─────────────────────────
    async def love_bag(self) -> list[int]:
        raw = await self.get_kv("love_bag", "[]")
        try:
            return [int(i) for i in json.loads(raw or "[]")]
        except (ValueError, TypeError):
            return []

    async def set_love_bag(self, bag: list[int]) -> None:
        await self.set_kv("love_bag", json.dumps(bag))

    # ── "Ikkalamiz" o'yini ──────────────────────────────────────────────
    async def active_round(self) -> tuple[int, str] | None:
        async with self.conn.execute(
            "SELECT id, question FROM game_rounds WHERE finished_at IS NULL ORDER BY id DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
        return (int(row["id"]), row["question"]) if row else None

    async def start_round(self, question: str) -> int:
        cur = await self.conn.execute(
            "INSERT INTO game_rounds(question, created_at) VALUES(?, ?)", (question, _utcnow())
        )
        await self.conn.commit()
        return int(cur.lastrowid or 0)

    async def answer_round(self, round_id: int, user_id: int, answer: str) -> None:
        await self.conn.execute(
            "INSERT INTO game_answers(round_id, user_id, answer) VALUES(?, ?, ?) "
            "ON CONFLICT(round_id, user_id) DO UPDATE SET answer = excluded.answer",
            (round_id, user_id, answer),
        )
        await self.conn.commit()

    async def round_answers(self, round_id: int) -> dict[int, str]:
        async with self.conn.execute(
            "SELECT user_id, answer FROM game_answers WHERE round_id = ?", (round_id,)
        ) as cur:
            return {int(row["user_id"]): row["answer"] for row in await cur.fetchall()}

    async def finish_round(self, round_id: int) -> None:
        await self.conn.execute(
            "UPDATE game_rounds SET finished_at = ? WHERE id = ?", (_utcnow(), round_id)
        )
        await self.conn.commit()

    async def asked_questions(self) -> list[str]:
        async with self.conn.execute("SELECT question FROM game_rounds ORDER BY id") as cur:
            return [row["question"] for row in await cur.fetchall()]

    async def rounds_finished(self) -> int:
        async with self.conn.execute(
            "SELECT COUNT(*) AS n FROM game_rounds WHERE finished_at IS NOT NULL"
        ) as cur:
            row = await cur.fetchone()
        return int(row["n"]) if row else 0
