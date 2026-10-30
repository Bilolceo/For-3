from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from lovebot.config import ConfigError, load_settings
from lovebot.content import LoveMessage
from lovebot.scheduler import _love_trigger
from lovebot.services import day_number, format_timer, pick_love, pick_reason

TZ = ZoneInfo("Asia/Tashkent")


def test_timer_counts_days_hours_minutes():
    since = datetime(2025, 2, 14, 19, 30, tzinfo=TZ)
    now = since + timedelta(days=100, hours=5, minutes=42, seconds=10)
    text = format_timer(now, since, None, "x")
    assert "100 kun, 5 soat, 42 daqiqa, 10 soniya" in text
    assert "14.02.2025 dan beri" in text
    assert "📅" not in text


def test_timer_real_date_2026_03_26():
    since = datetime(2026, 3, 26, tzinfo=TZ)
    now = datetime(2026, 10, 30, 22, 0, 22, tzinfo=TZ)
    assert "218 kun, 22 soat, 0 daqiqa, 22 soniya" in format_timer(now, since, None, "x")


def test_timer_countdown_to_next_date():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=TZ)
    nxt = now + timedelta(days=2, hours=1)
    text = format_timer(now, now - timedelta(days=1), nxt, "Uchrashuv <3")
    assert "2 kun, 1 soat, 0 daqiqa, 0 soniya" in text
    assert "Uchrashuv &lt;3" in text  # HTML-escape


def test_timer_next_date_today():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=TZ)
    text = format_timer(now, now - timedelta(days=1), now - timedelta(minutes=1), "Bugun")
    assert "bugun" in text.lower()


def test_timer_before_start():
    now = datetime(2026, 1, 1, tzinfo=TZ)
    text = format_timer(now, now + timedelta(days=1), None, "x")
    assert "Hali boshlanmagan" in text


def test_pick_reason_sequential_then_random():
    reasons = ["a", "b"]
    text, cur, exhausted = pick_reason(reasons, 0)
    assert (text, cur, exhausted) == ("a", 1, False)
    text, cur, exhausted = pick_reason(reasons, 1)
    assert (text, cur, exhausted) == ("b", 2, False)
    text, cur, exhausted = pick_reason(reasons, 2)
    assert text in reasons and cur == 2 and exhausted


def test_pick_reason_empty():
    assert pick_reason([], 0) == ("", 0, True)


def test_pick_love_no_repeat_until_exhausted():
    msgs = [LoveMessage("sevgi", f"m{i}") for i in range(5)]
    bag: list[int] = []
    seen = []
    for _ in range(5):
        m, bag = pick_love(msgs, bag)
        seen.append(m.text)
    assert sorted(seen) == sorted(x.text for x in msgs)  # har biri bir marta
    assert bag == []
    m, bag = pick_love(msgs, bag)  # qayta aralashadi
    assert m is not None and len(bag) == 4


def test_pick_love_ignores_stale_indices():
    msgs = [LoveMessage("sevgi", "a")]
    m, bag = pick_love(msgs, [7, 9])  # kontent qisqargan — eski indekslar tashlanadi
    assert m.text == "a" and bag == []


def test_pick_love_empty():
    assert pick_love([], [1]) == (None, [])


def test_day_number():
    start = date(2026, 11, 1)
    assert day_number(start, date(2026, 11, 1), 30) == 1
    assert day_number(start, date(2026, 11, 15), 30) == 15
    assert day_number(start, date(2026, 11, 30), 30) == 30
    assert day_number(start, date(2027, 1, 1), 30) == 30  # tugagach oxirgi kunda qoladi
    assert day_number(start, date(2026, 10, 20), 30) == 1  # soat o'zgarsa ham 1 dan past emas


def _settings(interval: int, window: str):
    import os

    env = {
        "BOT_TOKEN": "x", "MY_ID": "1", "HER_ID": "2", "TOGETHER_SINCE": "2025-01-01",
        "LOVE_INTERVAL_MINUTES": str(interval), "LOVE_WINDOW": window,
    }
    old = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        return load_settings()
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_love_window():
    s = _settings(60, "09:00-23:00")
    assert s.in_love_window(datetime(2026, 1, 1, 9, 0, tzinfo=TZ))
    assert s.in_love_window(datetime(2026, 1, 1, 22, 59, tzinfo=TZ))
    assert not s.in_love_window(datetime(2026, 1, 1, 23, 0, tzinfo=TZ))
    assert not s.in_love_window(datetime(2026, 1, 1, 3, 30, tzinfo=TZ))


def test_love_trigger_hourly_fires_only_in_window():
    s = _settings(60, "09:00-23:00")
    trig = _love_trigger(s)
    start = datetime(2026, 1, 1, 0, 0, tzinfo=TZ)
    fires = []
    t = start
    for _ in range(14):
        t = trig.get_next_fire_time(None, t + timedelta(seconds=1))
        fires.append(t)
    assert fires[0].hour == 9 and fires[0].minute == 0
    assert fires[13].hour == 22
    assert all(f.minute == 0 for f in fires)
    assert trig.get_next_fire_time(None, fires[13] + timedelta(seconds=1)).day == 2  # keyingisi ertaga 09:00


def test_love_trigger_every_30_min_and_every_2h():
    s = _settings(30, "10:00-12:00")
    t = _love_trigger(s).get_next_fire_time(None, datetime(2026, 1, 1, 10, 0, 1, tzinfo=TZ))
    assert (t.hour, t.minute) == (10, 30)
    s = _settings(120, "09:00-23:00")
    t = _love_trigger(s).get_next_fire_time(None, datetime(2026, 1, 1, 9, 0, 1, tzinfo=TZ))
    assert (t.hour, t.minute) == (11, 0)


def test_invalid_love_settings():
    with pytest.raises(ConfigError):
        _settings(7, "09:00-23:00")
    with pytest.raises(ConfigError):
        _settings(60, "23:00-09:00")
