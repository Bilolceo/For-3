from pathlib import Path

import pytest

from lovebot.db import Database


@pytest.fixture
async def db(tmp_path: Path):
    database = Database(tmp_path / "t.db")
    await database.connect()
    yield database
    await database.close()


async def test_letters_open_count(db: Database):
    assert await db.letters_opened() == {}
    await db.mark_letter_opened("a")
    await db.mark_letter_opened("a")
    await db.mark_letter_opened("b")
    assert await db.letters_opened() == {"a": 2, "b": 1}


async def test_reason_state_roundtrip(db: Database):
    assert await db.reason_state() == (0, None)
    await db.set_reason_state(3, "2026-01-01")
    assert await db.reason_state() == (3, "2026-01-01")


async def test_coupon_uses(db: Database):
    assert await db.use_coupon("cafe") == 1
    assert await db.use_coupon("cafe") == 2
    assert await db.coupon_uses() == {"cafe": 2}


async def test_mood_upsert_and_order(db: Database):
    await db.set_mood("2026-01-01", "ok")
    await db.set_mood("2026-01-02", "tired")
    await db.set_mood("2026-01-01", "great")  # xuddi shu kun qayta belgilanadi
    assert await db.recent_moods() == [("2026-01-02", "tired"), ("2026-01-01", "great")]


async def test_game_round_lifecycle(db: Database):
    assert await db.active_round() is None
    rid = await db.start_round("Savol?")
    assert await db.active_round() == (rid, "Savol?")
    await db.answer_round(rid, 1, "a")
    await db.answer_round(rid, 1, "a2")  # qayta yozsa — yangilanadi
    await db.answer_round(rid, 2, "b")
    assert await db.round_answers(rid) == {1: "a2", 2: "b"}
    await db.finish_round(rid)
    assert await db.active_round() is None
    assert await db.rounds_finished() == 1
    assert await db.asked_questions() == ["Savol?"]


async def test_love_bag_roundtrip(db: Database):
    assert await db.love_bag() == []
    await db.set_love_bag([3, 1, 2])
    assert await db.love_bag() == [3, 1, 2]
    await db.set_kv("love_bag", "buzuq")
    assert await db.love_bag() == []


async def test_quiz_results(db: Database):
    assert await db.quiz_completions() == 0
    await db.save_quiz_result(2)
    assert await db.quiz_completions() == 1
