"""Jinja2 rendering with the globals the ported templates expect.

Templates were written for Flask (url_for / csrf_token / get_flashed_messages
/ current_user / request). ``render()`` injects compatible shims so the
templates work unmodified.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Expose Python builtins a few templates rely on
templates.env.globals.setdefault("zip", zip)
templates.env.globals.setdefault("str", str)
templates.env.globals.setdefault("int", int)
templates.env.globals.setdefault("len", len)


_URL_MAP: dict[str, str] | None = None


def _url_map() -> dict[str, str]:
    """name → path map built lazily from our routers (Starlette-version-proof)."""
    global _URL_MAP
    if _URL_MAP is None:
        from .routers import api, auth, health, pages
        m = {}
        for router in (auth.router, pages.router, api.router, health.router):
            for route in router.routes:
                if getattr(route, "name", None):
                    m[route.name] = getattr(route, "path_format", None) or route.path
        _URL_MAP = m
    return _URL_MAP


def render(request: Request, name: str, context: dict | None = None,
           status_code: int = 200):
    ctx = dict(context or {})

    def url_for(endpoint: str, **params) -> str:
        if endpoint == "static":
            return "/static/" + params.get("filename", "")
        path = _url_map().get(endpoint)
        if path is None:
            raise KeyError(f"未知路由: {endpoint}")
        remaining = {}
        for key, value in params.items():
            placeholder = "{" + key + "}"
            if placeholder in path:
                path = path.replace(placeholder, str(value))
            else:
                remaining[key] = value
        if remaining:
            from urllib.parse import urlencode
            path += "?" + urlencode(remaining)
        return path

    def get_flashed_messages(with_categories: bool = False):
        flashes = getattr(request.state, "flashes", [])
        if with_categories:
            return [(cat, msg) for cat, msg in flashes]
        return [msg for _, msg in flashes]

    ctx.setdefault("request", request)
    ctx.setdefault("url_for", url_for)
    ctx.setdefault("get_flashed_messages", get_flashed_messages)
    ctx.setdefault("csrf_token", lambda: request.state.csrf_token)
    ctx.setdefault("current_user", getattr(request.state, "user", None))
    ctx.setdefault("current_project_id", None)

    return templates.TemplateResponse(request, name, ctx, status_code=status_code)
