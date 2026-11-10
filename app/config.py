"""Application configuration.

Environment-only settings for infrastructure concerns (DB, paths, secrets).
Business/OCR credentials live in the ``settings`` DB table (see models.py)
and are managed through the settings page; env vars only serve as the
one-time bootstrap.
"""
from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Infrastructure
    secret_key: str = ""
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'invoices.db'}"
    upload_folder: str = str(BASE_DIR / "app" / "static" / "uploads")
    output_dir: str = str(BASE_DIR / "data" / "output")

    # Upload limits
    max_upload_mb: int = 16
    allowed_extensions: frozenset = frozenset({"png", "jpg", "jpeg", "gif", "pdf"})

    # Cookies: set SECURE_COOKIES=true when serving over HTTPS
    secure_cookies: bool = False

    # OCR bootstrap (imported into the settings table on first run)
    tencent_secret_id: str = ""
    tencent_secret_key: str = ""

    model_config_json_schema_extra: dict = {}


@lru_cache
def get_config() -> AppConfig:
    cfg = AppConfig()
    if not cfg.secret_key:
        # Dev convenience: random per-process key. Sessions/CSRF tokens are
        # invalidated on restart — set SECRET_KEY in .env for stable sessions.
        import logging

        logging.getLogger("invoiceocr").warning(
            "SECRET_KEY 未配置，已生成随机密钥（重启后所有会话失效）。"
            "请在 .env 中设置 SECRET_KEY。"
        )
        cfg.secret_key = secrets.token_hex(32)
    Path(cfg.upload_folder).mkdir(parents=True, exist_ok=True)
    Path(cfg.output_dir).mkdir(parents=True, exist_ok=True)
    return cfg
