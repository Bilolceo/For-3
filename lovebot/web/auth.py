"""Telegram Mini App initData tekshiruvi va qisqa muddatli kirish tokenlari.

initData: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
Token: "<uid>.<exp>.<hmac>" — bot tokeni bilan imzolanadi, brauzerda ochish havolasi uchun.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

TOKEN_TTL = 12 * 3600


def validate_init_data(init_data: str, bot_token: str, max_age: int = 24 * 3600) -> dict | None:
    """To'g'ri imzolangan bo'lsa Telegram `user` obyektini (id, first_name …) qaytaradi."""
    if not init_data:
        return None
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", None)
    if not received:
        return None
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        return None
    try:
        auth_date = int(pairs.get("auth_date", "0") or 0)
    except ValueError:
        return None
    if max_age and time.time() - auth_date > max_age:
        return None
    try:
        user = json.loads(pairs.get("user", "") or "{}")
    except json.JSONDecodeError:
        return None
    return user if isinstance(user, dict) and user.get("id") else None


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]


def make_token(user_id: int, secret: str, ttl: int = TOKEN_TTL, now: float | None = None) -> str:
    exp = int((now if now is not None else time.time()) + ttl)
    payload = f"{user_id}.{exp}"
    return f"{payload}.{_sign(payload, secret)}"


def verify_token(token: str, secret: str, now: float | None = None) -> int | None:
    try:
        uid_s, exp_s, sig = token.split(".")
        uid, exp = int(uid_s), int(exp_s)
    except (ValueError, AttributeError):
        return None
    if not hmac.compare_digest(_sign(f"{uid}.{exp}", secret), sig):
        return None
    if (now if now is not None else time.time()) > exp:
        return None
    return uid
