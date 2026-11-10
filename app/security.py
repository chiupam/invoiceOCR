"""Session cookies, CSRF tokens, and flash messages.

- Session: itsdangerous-signed cookie holding the user id.
- CSRF: double-submit cookie pattern — a random ``csrf_token`` cookie that
  must be echoed back via the ``X-CSRFToken`` header or a ``csrf_token``
  form field.
- Flash: signed cookie carrying a JSON list of [category, message] pairs,
  consumed by the next rendered page.
"""
from __future__ import annotations

import json
import secrets

from itsdangerous import BadSignature, URLSafeSerializer, URLSafeTimedSerializer

from .config import get_config

SESSION_COOKIE = "invoiceocr_session"
MFA_COOKIE = "invoiceocr_mfa"
FLASH_COOKIE = "invoiceocr_flash"
CSRF_COOKIE = "csrf_token"


def _session_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_config().secret_key, salt="session")


def _flash_serializer() -> URLSafeSerializer:
    return URLSafeSerializer(get_config().secret_key, salt="flash")


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

def dumps_session(user_id: int) -> str:
    return _session_serializer().dumps({"uid": user_id})


def loads_session(value: str, max_age: int) -> int | None:
    try:
        data = _session_serializer().loads(value, max_age=max_age)
        return int(data["uid"])
    except (BadSignature, KeyError, TypeError, ValueError):
        return None


def dumps_mfa_pending(user_id: int, remember: bool) -> str:
    return _session_serializer().dumps({"mfa_uid": user_id, "remember": remember})


def loads_mfa_pending(value: str, max_age: int = 600) -> dict | None:
    try:
        return _session_serializer().loads(value, max_age=max_age)
    except BadSignature:
        return None


# ---------------------------------------------------------------------------
# Flash
# ---------------------------------------------------------------------------

def dumps_flash(messages: list[list[str]]) -> str:
    return _flash_serializer().dumps(messages)


def loads_flash(value: str) -> list[list[str]]:
    try:
        data = _flash_serializer().loads(value)
        return data if isinstance(data, list) else []
    except BadSignature:
        return []


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------

def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)
