"""FastAPI application factory: middleware, routers, static files, errors."""
from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from . import security
from .config import get_config
from .database import init_db
from .deps import CsrfError, LoginRequired, ensure_csrf_cookie
from .jinja import render
from .routers import api, auth, health, pages

logger = logging.getLogger("invoiceocr")

STATIC_DIR = Path(__file__).resolve().parent / "static"


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RequestContextMiddleware(BaseHTTPMiddleware):
    """Request id + timing log + template-visible request state."""

    async def dispatch(self, request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex[:12]
        request.state.flashes = security.loads_flash(
            request.cookies.get(security.FLASH_COOKIE, ""))
        request.state.outgoing_flashes = []
        request.state.user = None  # populated by get_current_user dependency
        request.state.csrf_token = ensure_csrf_cookie(request)
        request.state.csrf_needs_cookie = \
            security.CSRF_COOKIE not in request.cookies

        start = time.monotonic()
        response = await call_next(request)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info("%s %s -> %s (%dms) [%s]",
                    request.method, request.url.path, response.status_code,
                    elapsed_ms, request.state.request_id)

        # Flash cookie: outgoing messages win; otherwise consume incoming.
        if request.state.outgoing_flashes:
            response.set_cookie(
                security.FLASH_COOKIE,
                security.dumps_flash(request.state.outgoing_flashes),
                max_age=60, httponly=True, samesite="lax",
            )
        elif security.FLASH_COOKIE in request.cookies:
            response.delete_cookie(security.FLASH_COOKIE)

        if request.state.csrf_needs_cookie:
            response.set_cookie(security.CSRF_COOKIE, request.state.csrf_token,
                                max_age=30 * 24 * 3600, httponly=False,
                                samesite="lax")
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Small in-memory per-IP sliding-window limiter.

    Strict buckets for credential endpoints; a generous default for
    everything else. /health and static assets are exempt (probe traffic).
    """

    STRICT_RULES = {
        ("POST", "/auth/login"): (20, 60),
        ("POST", "/auth/login/mfa"): (10, 60),
        ("POST", "/auth/setup"): (5, 60),
    }
    DEFAULT_LIMIT, DEFAULT_WINDOW = 300, 3600
    EXEMPT_PREFIXES = ("/health", "/static")

    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[tuple, deque] = defaultdict(deque)

    def _allow(self, key, limit, window) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > window:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith(self.EXEMPT_PREFIXES):
            ip = request.client.host if request.client else "unknown"
            limit, window = self.STRICT_RULES.get(
                (request.method, path), (self.DEFAULT_LIMIT, self.DEFAULT_WINDOW))
            bucket = (ip, request.method, path) if (request.method, path) in \
                self.STRICT_RULES else (ip,)
            if not self._allow(bucket, limit, window):
                if "application/json" in request.headers.get("accept", ""):
                    return JSONResponse({"error": "请求过于频繁，请稍后再试"},
                                        status_code=429)
                return render(request, "errors/429.html", {}, status_code=429)
        return await call_next(request)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    get_config()  # validate + ensure directories
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    security_log = logging.getLogger("security")
    if not security_log.handlers:
        fh = logging.FileHandler(log_dir / "security.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        security_log.addHandler(fh)

    init_db()

    app = FastAPI(title="invoiceOCR", docs_url=None, redoc_url=None,
                  openapi_url=None)

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(RateLimitMiddleware)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(api.router)
    app.include_router(pages.router)

    @app.exception_handler(LoginRequired)
    async def login_required_handler(request: Request, exc: LoginRequired):
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"error": "未登录"}, status_code=401)
        return RedirectResponse(f"/auth/login?next={exc.next_path}",
                                status_code=303)

    @app.exception_handler(CsrfError)
    async def csrf_handler(request: Request, exc: CsrfError):
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"success": False, "message": str(exc)},
                                status_code=403)
        return render(request, "errors/500.html",
                      {"error_message": f"安全校验失败：{exc}"}, status_code=403)

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return render(request, "errors/404.html", {}, status_code=404)

    @app.exception_handler(500)
    async def server_error_handler(request: Request, exc):
        return render(request, "errors/500.html", {}, status_code=500)

    return app


app = create_app()
