"""JWT 与密码哈希单测。"""
import time
from datetime import datetime, timedelta

import jwt

import app.core.security as security
from app.core.errors import AuthError
from app.core.security import create_access_token, decode_token, hash_password, verify_password


def test_create_and_decode_token_roundtrip():
    token = create_access_token(user_id=42)
    assert isinstance(token, str) and len(token) > 0

    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert "iat" in payload and "exp" in payload
    assert int(payload["exp"]) > int(payload["iat"])


def test_decode_token_rejects_garbage():
    try:
        decode_token("not-a-jwt")
    except AuthError as e:
        assert e.code == "AUTH_ERROR"
        assert e.status_code == 401
    else:
        raise AssertionError("expected AuthError for garbage token")


def test_decode_token_rejects_wrong_secret():
    from app.core.config import get_settings
    settings = get_settings()
    bad = jwt.encode(
        {"sub": "1", "iat": int(time.time()), "exp": int(time.time()) + 60},
        "different-secret-that-is-at-least-32-bytes",
        algorithm=settings.jwt_algorithm,
    )
    try:
        decode_token(bad)
    except AuthError:
        return
    raise AssertionError("expected AuthError for wrong-secret token")


def test_decode_token_allows_small_clock_skew(monkeypatch):
    """A freshly issued token remains valid across a small host clock correction."""
    real_datetime = datetime

    class TwoSecondsAhead(datetime):
        @classmethod
        def now(cls, tz=None):
            return real_datetime.now(tz) + timedelta(seconds=2)

    monkeypatch.setattr(security, "datetime", TwoSecondsAhead)
    token = security.create_access_token(user_id=42)
    monkeypatch.setattr(security, "datetime", real_datetime)

    payload = security.decode_token(token)

    assert payload["sub"] == "42"


def test_decode_token_rejects_large_future_iat(monkeypatch):
    """Clock tolerance must not make arbitrary future tokens valid."""
    real_datetime = datetime

    class ThirtySecondsAhead(datetime):
        @classmethod
        def now(cls, tz=None):
            return real_datetime.now(tz) + timedelta(seconds=30)

    monkeypatch.setattr(security, "datetime", ThirtySecondsAhead)
    token = security.create_access_token(user_id=42)
    monkeypatch.setattr(security, "datetime", real_datetime)

    try:
        security.decode_token(token)
    except AuthError:
        return
    raise AssertionError("expected AuthError for token issued too far in the future")


def test_hash_and_verify_password():
    raw = "hunter2#pwd"
    hashed = hash_password(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("wrong", hashed) is False
