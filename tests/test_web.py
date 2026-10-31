import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode

import pytest
from aiohttp.test_utils import TestClient, TestServer

from lovebot.config import load_settings
from lovebot.db import Database
from lovebot.web.auth import make_token, validate_init_data, verify_token
from lovebot.web.cinema import PlayerState, Room, source_kind
from lovebot.web.server import DB_KEY, build_web_app

TOKEN = "123456:TESTTOKEN"


def _init_data(user: dict, bot_token: str = TOKEN, auth_date: int | None = None) -> str:
    fields = {"auth_date": str(auth_date or int(time.time())), "query_id": "q1", "user": json.dumps(user, separators=(",", ":"))}
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


# ── auth ────────────────────────────────────────────────────────────────
def test_init_data_valid_and_tampered():
    data = _init_data({"id": 42, "first_name": "Aida"})
    assert validate_init_data(data, TOKEN)["id"] == 42
    assert validate_init_data(data, "999:other") is None  # boshqa bot tokeni
    assert validate_init_data(data.replace("Aida", "Eva"), TOKEN) is None  # o'zgartirilgan
    assert validate_init_data("", TOKEN) is None
    assert validate_init_data("a=b", TOKEN) is None  # hash yo'q


def test_init_data_expired():
    data = _init_data({"id": 42}, auth_date=int(time.time()) - 2 * 86400)
    assert validate_init_data(data, TOKEN) is None
    assert validate_init_data(data, TOKEN, max_age=0)["id"] == 42


def test_token_roundtrip_and_expiry():
    t = make_token(777, TOKEN, ttl=60, now=1000)
    assert verify_token(t, TOKEN, now=1030) == 777
    assert verify_token(t, TOKEN, now=1061) is None  # muddati o'tgan
    assert verify_token(t, "other", now=1030) is None
    assert verify_token(t[:-1] + ("0" if t[-1] != "0" else "1"), TOKEN, now=1030) is None
    assert verify_token("garbage", TOKEN) is None


# ── xona holati ─────────────────────────────────────────────────────────
def test_source_kind():
    assert source_kind("https://www.youtube.com/watch?v=abc") == "youtube"
    assert source_kind("https://youtu.be/abc") == "youtube"
    assert source_kind("https://cdn.example.com/film.mp4") == "file"


def test_room_apply_play_pause_seek():
    room = Room()
    assert room.apply({"type": "source", "url": "ftp://x"}) is False
    assert room.apply({"type": "source", "url": "https://x/f.mp4"}, now=100) is True
    assert room.state.kind == "file" and room.state.playing is False
    assert room.apply({"type": "play", "position": 10}, now=100) is True
    assert room.state.expected_position(now=130) == pytest.approx(40)
    assert room.apply({"type": "pause"}, now=130) is True  # position berilmasa — kutilgan joy
    assert room.state.position == pytest.approx(40) and room.state.playing is False
    assert room.apply({"type": "seek", "position": 5}, now=131) is True
    assert room.state.expected_position(now=200) == 5
    assert room.apply({"type": "bogus"}) is False


def test_player_state_dict():
    s = PlayerState(url="u", kind="file", playing=True, position=1, updated_at=2)
    assert s.to_dict()["playing"] is True


# ── HTTP + WebSocket oqimi ──────────────────────────────────────────────
@pytest.fixture
def env(monkeypatch):
    for k, v in {
        "BOT_TOKEN": TOKEN, "MY_ID": "1", "HER_ID": "2", "MY_NAME": "Bilol", "HER_NAME": "Aida",
        "TOGETHER_SINCE": "2026-03-26", "PUBLIC_URL": "https://example.test",
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("GIFT_LAT", raising=False)
    monkeypatch.delenv("GIFT_LON", raising=False)


@pytest.fixture
async def client(env, tmp_path: Path):
    settings = load_settings()
    db = Database(tmp_path / "w.db")
    await db.connect()
    app = build_web_app(settings, db)
    async with TestClient(TestServer(app)) as c:
        yield c
    await db.close()


async def test_session_and_static(client: TestClient):
    r = await client.get("/")
    assert r.status == 200
    r = await client.get("/app/")
    assert r.status == 200 and "Kino kechasi" in await r.text()
    r = await client.post("/api/session", json={"init_data": _init_data({"id": 2, "first_name": "A"})})
    assert r.status == 200
    body = await r.json()
    assert body["uid"] == 2 and body["name"] == "Aida" and body["is_admin"] is False and body["ice_servers"]
    r = await client.post("/api/session", json={"init_data": _init_data({"id": 999})})
    assert r.status == 403  # ro'yxatda yo'q
    r = await client.post("/api/session", json={"token": make_token(1, TOKEN)})
    body = await r.json()
    assert body["is_admin"] is True and body["movies"] == []


async def test_ws_sync_and_signal(client: TestClient):
    t1, t2 = make_token(1, TOKEN), make_token(2, TOKEN)
    r = await client.get("/ws?t=bad")
    assert r.status == 403

    ws1 = await client.ws_connect(f"/ws?t={t1}")
    hello1 = await ws1.receive_json()
    assert hello1["type"] == "hello" and hello1["peers"] == []

    ws2 = await client.ws_connect(f"/ws?t={t2}")
    hello2 = await ws2.receive_json()
    assert [p["uid"] for p in hello2["peers"]] == [1]
    assert (await ws1.receive_json())["type"] == "peer_joined"

    await ws1.send_json({"type": "source", "url": "https://x/f.mp4"})
    s1, s2 = await ws1.receive_json(), await ws2.receive_json()
    assert s1["type"] == "state" and s2["state"]["url"] == "https://x/f.mp4" and s2["by"] == 1

    await ws2.send_json({"type": "play", "position": 12})
    assert (await ws1.receive_json())["state"]["playing"] is True
    assert (await ws2.receive_json())["state"]["position"] == 12

    await ws1.send_json({"type": "signal", "data": {"candidate": "c"}})
    sig = await ws2.receive_json()
    assert sig == {"type": "signal", "from": 1, "data": {"candidate": "c"}}

    # manba qayta ishga tushganda ham eslab qolinadi
    assert await client.server.app[DB_KEY].get_kv("cinema_url") == "https://x/f.mp4"

    await ws2.close()
    assert (await ws1.receive_json())["type"] == "peer_left"
    await ws1.close()
