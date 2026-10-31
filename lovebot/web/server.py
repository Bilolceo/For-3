"""aiohttp ilovasi: /api/session, /ws, /app/ (Mini App statik sahifasi), / (health)."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import aiohttp
from aiohttp import WSMsgType, web

from ..config import Settings
from ..content import Content
from ..db import Database
from .auth import make_token, validate_init_data, verify_token
from .cinema import PlayerState, Room, source_kind

log = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"
CINEMA_URL_KEY = "cinema_url"

SETTINGS_KEY = web.AppKey("settings", Settings)
DB_KEY = web.AppKey("db", Database)
ROOM_KEY = web.AppKey("room", Room)
CONTENT_KEY = web.AppKey("content", Content)
HTTP_KEY = web.AppKey("http", aiohttp.ClientSession)

# Google Drive va shunga o'xshash xostlar brauzerga "virus tekshiruvi" HTML sahifasini beradi,
# serverga esa to'g'ri faylni — shuning uchun katalogdagi kinolar server orqali oqimlanadi.
MEDIA_UA = "Mozilla/5.0 (compatible; LoveBot/1.0)"
MEDIA_PASS_HEADERS = ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "Last-Modified", "ETag")


@web.middleware
async def _no_cache(request: web.Request, handler):
    """Mini App fayllari kichik — brauzer eski app.js ni ushlab qolmasin (har deploy'da yangisi kelsin)."""
    response = await handler(request)
    if request.path.startswith("/app"):
        response.headers["Cache-Control"] = "no-cache"
    return response


def build_web_app(settings: Settings, db: Database, content: Content | None = None) -> web.Application:
    app = web.Application(client_max_size=64 * 1024, middlewares=[_no_cache])
    app[SETTINGS_KEY] = settings
    app[DB_KEY] = db
    app[ROOM_KEY] = Room()
    app[CONTENT_KEY] = content or Content()
    app.on_startup.append(_restore_source)
    app.on_startup.append(_open_http)
    app.on_cleanup.append(_close_http)
    app.add_routes(
        [
            web.get("/", health),
            web.get("/app", app_index),
            web.get("/app/", app_index),
            web.post("/api/session", api_session),
            web.get("/ws", ws_handler),
            web.get("/media/{index}", media_proxy),
            web.static("/app/static", STATIC_DIR),
        ]
    )
    return app


async def _open_http(app: web.Application) -> None:
    app[HTTP_KEY] = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=None, connect=20, sock_read=60),
        headers={"User-Agent": MEDIA_UA},
        cookie_jar=aiohttp.DummyCookieJar(),  # cookie'lar bilan Google boshqa javob beradi
    )


async def _close_http(app: web.Application) -> None:
    await app[HTTP_KEY].close()


async def start_web(app: web.Application, port: int) -> web.AppRunner:
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("Veb-server ishga tushdi: port %s", port)
    return runner


async def _restore_source(app: web.Application) -> None:
    """Qayta ishga tushganda oxirgi kino manbasini eslab qoladi."""
    url = await app[DB_KEY].get_kv(CINEMA_URL_KEY)
    if url:
        app[ROOM_KEY].state = PlayerState(url=url, kind=source_kind(url), updated_at=time.time())


# ── marshrutlar ─────────────────────────────────────────────────────────
async def health(_: web.Request) -> web.Response:
    return web.Response(text="ok")


async def app_index(_: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})


def _user_name(settings: Settings, uid: int) -> str:
    return settings.name_of(uid)


async def api_session(request: web.Request) -> web.Response:
    """Telegram initData → kirish tokeni. Faqat ikki ruxsat etilgan ID uchun."""
    settings: Settings = request.app[SETTINGS_KEY]
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise web.HTTPBadRequest(text="json kutilgan")
    uid: int | None = None
    if init_data := body.get("init_data"):
        user = validate_init_data(str(init_data), settings.bot_token)
        uid = int(user["id"]) if user else None
    elif token := body.get("token"):
        uid = verify_token(str(token), settings.bot_token)
    if uid is None or uid not in settings.allowed_ids:
        raise web.HTTPForbidden(text="403: bu yurak band")
    return web.json_response(
        {
            "token": make_token(uid, settings.bot_token),
            "uid": uid,
            "name": _user_name(settings, uid),
            "is_admin": uid == settings.my_id,
            "ice_servers": settings.ice_servers,
            "public_url": settings.public_url,
            "movies": [
                {**m.to_dict(), "play_url": f"/media/{i}" if m.url else ""}
                for i, m in enumerate(request.app[CONTENT_KEY].movies)
            ],
        }
    )


async def media_proxy(request: web.Request) -> web.StreamResponse:
    """Katalogdagi kinoni manbadan Range bilan olib, brauzerga oqim qilib uzatadi."""
    settings: Settings = request.app[SETTINGS_KEY]
    uid = verify_token(request.query.get("t", ""), settings.bot_token)
    if uid is None or uid not in settings.allowed_ids:
        raise web.HTTPForbidden(text="403")
    movies = request.app[CONTENT_KEY].movies
    try:
        movie = movies[int(request.match_info["index"])]
    except (ValueError, IndexError):
        raise web.HTTPNotFound(text="bunday kino yo'q")
    if not movie.url:
        raise web.HTTPNotFound(text="havola yo'q")

    headers = {}
    if rng := request.headers.get("Range"):
        headers["Range"] = rng
    http: aiohttp.ClientSession = request.app[HTTP_KEY]
    try:
        upstream = await http.get(movie.url, headers=headers, allow_redirects=True)
    except aiohttp.ClientError as exc:
        log.warning("Media manba xatosi (%s): %s", movie.title, exc)
        raise web.HTTPBadGateway(text="manba javob bermadi")
    try:
        ctype = upstream.headers.get("Content-Type", "")
        if upstream.status >= 400 or ctype.startswith("text/html"):
            log.warning("Media manba yaroqsiz javob (%s): %s %s", movie.title, upstream.status, ctype)
            raise web.HTTPBadGateway(text="manba video bermadi (HTML/xato qaytardi)")
        response = web.StreamResponse(status=upstream.status)
        for name in MEDIA_PASS_HEADERS:
            if value := upstream.headers.get(name):
                response.headers[name] = value
        response.headers.setdefault("Accept-Ranges", "bytes")
        response.headers["Cache-Control"] = "private, max-age=0"
        await response.prepare(request)
        try:
            async for chunk in upstream.content.iter_chunked(256 * 1024):
                await response.write(chunk)
            await response.write_eof()
        except (ConnectionResetError, aiohttp.ClientPayloadError):
            pass  # tomoshabin seek qildi yoki yopdi — brauzer yangi Range bilan qayta keladi
        return response
    finally:
        upstream.release()


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    settings: Settings = request.app[SETTINGS_KEY]
    room: Room = request.app[ROOM_KEY]
    db: Database = request.app[DB_KEY]

    uid = verify_token(request.query.get("t", ""), settings.bot_token)
    if uid is None or uid not in settings.allowed_ids:
        raise web.HTTPForbidden(text="403")
    name = _user_name(settings, uid)

    ws = web.WebSocketResponse(heartbeat=25)
    await ws.prepare(request)
    await room.join(uid, name, ws)
    await ws.send_json(
        {
            "type": "hello",
            "you": uid,
            "name": name,
            "peers": [{"uid": p, "name": room.names.get(p, "")} for p in room.others(uid)],
            "state": room.state.to_dict(),
            "server_time": time.time(),
        }
    )
    await room.broadcast({"type": "peer_joined", "uid": uid, "name": name}, exclude=uid)
    log.info("Kino: %s kirdi (%s kishi)", name, len(room.peers))

    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                event = json.loads(msg.data)
            except json.JSONDecodeError:
                continue
            kind = event.get("type")
            if kind == "ping":
                await ws.send_json({"type": "pong", "server_time": time.time()})
            elif kind == "signal":
                # WebRTC offer/answer/ice — ikkinchi ishtirokchiga o'zgarishsiz uzatiladi
                for other in room.others(uid):
                    await room.send(other, {"type": "signal", "from": uid, "data": event.get("data")})
            elif kind in ("source", "play", "pause", "seek"):
                if room.apply(event):
                    if kind == "source":
                        await db.set_kv(CINEMA_URL_KEY, room.state.url)
                    await room.broadcast(
                        {"type": "state", "state": room.state.to_dict(), "by": uid, "event": kind, "server_time": time.time()}
                    )
            elif kind == "chat":
                text = str(event.get("text", ""))[:500].strip()
                if text:
                    await room.broadcast({"type": "chat", "from": uid, "name": name, "text": text})
    finally:
        room.leave(uid, ws)
        await room.broadcast({"type": "peer_left", "uid": uid, "name": name}, exclude=uid)
        log.info("Kino: %s chiqdi (%s kishi)", name, len(room.peers))
    return ws
