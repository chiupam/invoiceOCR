#!/usr/bin/env python3
"""Development entry point.

Production runs inside Docker via gunicorn + uvicorn workers
(see Dockerfile / gunicorn.conf.py); this script is for local dev only.
"""
from __future__ import annotations

import os
import pathlib
import sys


def _bootstrap() -> None:
    """Ensure directories exist and import env OCR credentials once."""
    from app.database import init_db
    from app.models import Settings, User
    from app.database import SessionLocal

    pathlib.Path("data/output").mkdir(parents=True, exist_ok=True)

    init_db()

    with SessionLocal() as db:
        if User.can_register(db):
            print("\n" + "=" * 50)
            print("  首次使用：请通过浏览器访问系统完成密码设置")
            print("  访问地址: http://localhost:5001/auth/setup")
            print("=" * 50 + "\n")

    if not Settings.get_value("TENCENT_SECRET_ID") and os.environ.get("TENCENT_SECRET_ID"):
        Settings.set_value("TENCENT_SECRET_ID", os.environ["TENCENT_SECRET_ID"])
        print("已从环境变量导入腾讯云SecretId")
    if not Settings.get_value("TENCENT_SECRET_KEY") and os.environ.get("TENCENT_SECRET_KEY"):
        Settings.set_value("TENCENT_SECRET_KEY", os.environ["TENCENT_SECRET_KEY"])
        print("已从环境变量导入腾讯云SecretKey")


def main() -> None:
    _bootstrap()

    import uvicorn

    reload = os.environ.get("DEV_RELOAD", "1") == "1"
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5001")),
        reload=reload,
    )


if __name__ == "__main__":
    main()
