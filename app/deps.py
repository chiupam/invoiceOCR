"""Shared FastAPI dependencies: DB session, current user, CSRF, flash."""
from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from . import security
from .config import get_config
from .database import get_db  # noqa: F401 — re-exported for routers
from .models import User

SESSION_MAX_AGE_REMEMBER = 30 * 24 * 3600   # 30 days
SESSION_MAX_AGE_DEFAULT = 7 * 24 * 3600     # 7 days


class LoginRequired(Exception):
    """Raised by require_user; handled in main.py by redirecting to login."""

    def __init__(self, next_path: str = "/"):
        self.next_path = next_path


class CsrfError(Exception):
    pass


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    raw = request.cookies.get(security.SESSION_COOKIE)
    user = None
    if raw:
        uid = security.loads_session(raw, max_age=SESSION_MAX_AGE_REMEMBER)
        if uid is not None:
            candidate = db.get(User, uid)
            if candidate is not None and candidate.is_active:
                user = candidate
    request.state.user = user
    return user


def require_user(request: Request,
                 user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        next_path = request.url.path
        if request.url.query:
            next_path += "?" + request.url.query
        raise LoginRequired(next_path)
    return user


async def verify_csrf(request: Request) -> None:
    """Dependency for state-changing routes: validate the CSRF token.

    Token is taken from the ``X-CSRFToken`` header first (JS/fetch flows),
    falling back to the ``csrf_token`` form field (plain HTML forms). It must
    match the ``csrf_token`` cookie (double-submit pattern).
    """
    cookie_token = request.cookies.get(security.CSRF_COOKIE)
    if not cookie_token:
        raise CsrfError("缺少 CSRF cookie")
    token = request.headers.get("x-csrftoken")
    if not token:
        form = await request.form()
        token = form.get("csrf_token", "")
    if not token or token != cookie_token:
        raise CsrfError("CSRF 校验失败")


def flash(request: Request, message: str, category: str = "info") -> None:
    """Queue a flash message; stored in a cookie by the flash middleware."""
    outgoing = getattr(request.state, "outgoing_flashes", None)
    if outgoing is None:
        outgoing = []
        request.state.outgoing_flashes = outgoing
    outgoing.append([category, message])


def ensure_csrf_cookie(request: Request) -> str:
    """Return the request's CSRF token, generating one if absent."""
    token = request.cookies.get(security.CSRF_COOKIE)
    if not token:
        token = getattr(request.state, "csrf_token", None)
    if not token:
        token = security.new_csrf_token()
        request.state.csrf_token = token
        request.state.csrf_needs_cookie = True
    return token
