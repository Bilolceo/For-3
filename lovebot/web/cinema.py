"""Kino xonasi: pleyer holati + ikki ishtirokchi orasida xabar almashish (sync va WebRTC signaling)."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from aiohttp import web

log = logging.getLogger(__name__)

YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "www.youtube.com", "m.youtube.com")


def source_kind(url: str) -> str:
    host = url.split("//", 1)[-1].split("/", 1)[0].lower()
    return "youtube" if host in YOUTUBE_HOSTS else "file"


@dataclass
class PlayerState:
    url: str = ""
    kind: str = "file"
    playing: bool = False
    position: float = 0.0  # soniya, `updated_at` paytidagi
    updated_at: float = 0.0  # server vaqti (epoch, soniya)

    def expected_position(self, now: float | None = None) -> float:
        if not self.playing:
            return self.position
        return self.position + ((now if now is not None else time.time()) - self.updated_at)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Room:
    peers: dict[int, web.WebSocketResponse] = field(default_factory=dict)
    names: dict[int, str] = field(default_factory=dict)
    state: PlayerState = field(default_factory=PlayerState)

    # ── holat ──────────────────────────────────────────────────────────
    def apply(self, event: dict[str, Any], now: float | None = None) -> bool:
        """Mijoz hodisasini holatga tatbiq qiladi. Holat o'zgargan bo'lsa True."""
        now = now if now is not None else time.time()
        kind = event.get("type")
        position = _num(event.get("position"), default=self.state.expected_position(now))
        if kind == "source":
            url = str(event.get("url", "")).strip()
            if not url.startswith(("http://", "https://")):
                return False
            self.state = PlayerState(url=url, kind=source_kind(url), playing=False, position=0.0, updated_at=now)
            return True
        if kind == "play":
            self.state.playing, self.state.position, self.state.updated_at = True, position, now
            return True
        if kind == "pause":
            self.state.playing, self.state.position, self.state.updated_at = False, position, now
            return True
        if kind == "seek":
            self.state.position, self.state.updated_at = position, now
            return True
        return False

    # ── ishtirokchilar ─────────────────────────────────────────────────
    async def join(self, uid: int, name: str, ws: web.WebSocketResponse) -> None:
        old = self.peers.get(uid)
        self.peers[uid] = ws
        self.names[uid] = name
        if old is not None and not old.closed:
            await old.close(code=4000, message=b"replaced")

    def leave(self, uid: int, ws: web.WebSocketResponse) -> None:
        if self.peers.get(uid) is ws:
            self.peers.pop(uid, None)

    def others(self, uid: int) -> list[int]:
        return [p for p in self.peers if p != uid]

    async def send(self, uid: int, message: dict[str, Any]) -> None:
        ws = self.peers.get(uid)
        if ws is None or ws.closed:
            return
        try:
            await ws.send_json(message)
        except Exception:  # noqa: BLE001 — uzilgan ulanish xonani to'xtatmasin
            log.exception("WS yuborishda xato: uid=%s", uid)

    async def broadcast(self, message: dict[str, Any], exclude: int | None = None) -> None:
        for uid in list(self.peers):
            if uid != exclude:
                await self.send(uid, message)


def _num(value: Any, default: float) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default
