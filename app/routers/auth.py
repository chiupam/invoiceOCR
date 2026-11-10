"""Authentication routes: setup, login (+MFA), logout, password, MFA manage."""
from __future__ import annotations

import base64
import io
import logging
import re
from datetime import datetime

import qrcode
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import security
from ..database import get_db
from ..deps import (SESSION_MAX_AGE_DEFAULT, SESSION_MAX_AGE_REMEMBER,
                    flash, get_current_user, require_user, verify_csrf)
from ..jinja import render
from ..models import User

logger = logging.getLogger("invoiceocr.auth")

router = APIRouter(prefix="/auth")

PASSWORD_MIN_LEN = 8


def _validate_password(password: str) -> list[str]:
    errors = []
    if len(password) < PASSWORD_MIN_LEN:
        errors.append("密码长度至少8位")
    if not re.search(r"[A-Za-z]", password):
        errors.append("密码必须包含至少一个字母")
    if not re.search(r"[0-9]", password):
        errors.append("密码必须包含至少一个数字")
    return errors


def _login_response(user: User, remember: bool, next_url: str) -> RedirectResponse:
    max_age = SESSION_MAX_AGE_REMEMBER if remember else SESSION_MAX_AGE_DEFAULT
    resp = RedirectResponse(next_url, status_code=303)
    resp.set_cookie(
        security.SESSION_COOKIE, security.dumps_session(user.id),
        max_age=max_age, httponly=True, samesite="lax",
    )
    resp.delete_cookie(security.MFA_COOKIE)
    return resp


def _safe_next(next_url: str | None) -> str:
    if next_url and next_url.startswith("/"):
        return next_url
    return "/"


@router.get("/login", name="auth.login")
async def login_page(request: Request,
                     user: User | None = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    if user is not None:
        return RedirectResponse("/", status_code=303)

    owner = User.get_owner(db)
    if owner is None:
        return RedirectResponse("/auth/setup", status_code=303)

    is_locked = owner.is_locked(db)
    lock_remaining = 0
    if is_locked and owner.locked_until:
        delta = owner.locked_until - datetime.now()
        lock_remaining = max(0, int(delta.total_seconds()))

    return render(request, "auth/login.html", {
        "errors": {}, "is_locked": is_locked, "lock_remaining": lock_remaining,
    })


@router.post("/login", dependencies=[Depends(verify_csrf)])
async def login_submit(request: Request,
                       password: str = Form(""),
                       remember: str = Form(""),
                       db: Session = Depends(get_db)):
    owner = User.get_owner(db)
    if owner is None:
        return RedirectResponse("/auth/setup", status_code=303)

    if owner.is_locked(db):
        return RedirectResponse("/auth/login", status_code=303)

    if not owner.check_password(password):
        owner.increment_failed_login(db)
        remaining = User.MAX_FAILED_LOGINS - owner.failed_login_count
        if remaining > 0:
            flash(request, f"密码错误，还剩{remaining}次尝试机会", "danger")
        else:
            flash(request, "密码错误次数过多，账户已锁定15分钟", "danger")
        security_logger = logging.getLogger("security")
        security_logger.warning(
            "登录失败: ip=%s, failed_count=%s",
            request.client.host if request.client else "?",
            owner.failed_login_count,
        )
        return RedirectResponse("/auth/login", status_code=303)

    if owner.mfa_enabled:
        resp = RedirectResponse("/auth/login/mfa", status_code=303)
        resp.set_cookie(
            security.MFA_COOKIE,
            security.dumps_mfa_pending(owner.id, remember=bool(remember)),
            max_age=600, httponly=True, samesite="lax",
        )
        return resp

    owner.record_login(db, request.client.host if request.client else "")
    flash(request, "登录成功", "success")
    next_url = _safe_next(request.query_params.get("next"))
    return _login_response(owner, remember=bool(remember), next_url=next_url)


@router.get("/login/mfa", name="auth.mfa_verify")
async def mfa_verify_page(request: Request,
                          user: User | None = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    if user is not None:
        return RedirectResponse("/", status_code=303)
    pending = security.loads_mfa_pending(request.cookies.get(security.MFA_COOKIE, ""))
    if not pending:
        return RedirectResponse("/auth/login", status_code=303)
    return render(request, "auth/mfa_verify.html", {"errors": {}})


@router.post("/login/mfa", dependencies=[Depends(verify_csrf)])
async def mfa_verify_submit(request: Request,
                            code: str = Form(""),
                            db: Session = Depends(get_db)):
    pending = security.loads_mfa_pending(request.cookies.get(security.MFA_COOKIE, ""))
    if not pending:
        return RedirectResponse("/auth/login", status_code=303)

    user = db.get(User, pending["mfa_uid"])
    if user is None or not user.mfa_enabled:
        resp = RedirectResponse("/auth/login", status_code=303)
        resp.delete_cookie(security.MFA_COOKIE)
        return resp

    if user.verify_mfa_code(code.strip()):
        user.record_login(db, request.client.host if request.client else "")
        flash(request, "登录成功", "success")
        return _login_response(user, remember=bool(pending.get("remember")),
                               next_url="/")

    flash(request, "验证码错误，请重试", "danger")
    return RedirectResponse("/auth/login/mfa", status_code=303)


@router.get("/setup", name="auth.setup")
async def setup_page(request: Request,
                     user: User | None = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    if user is not None:
        return RedirectResponse("/", status_code=303)
    if not User.can_register(db):
        return RedirectResponse("/auth/login", status_code=303)
    return render(request, "auth/setup.html", {"errors": {}})


@router.post("/setup", dependencies=[Depends(verify_csrf)])
async def setup_submit(request: Request,
                       password: str = Form(""),
                       password2: str = Form(""),
                       db: Session = Depends(get_db)):
    if not User.can_register(db):
        return RedirectResponse("/auth/login", status_code=303)

    errors: dict[str, list[str]] = {}
    pwd_errors = _validate_password(password)
    if pwd_errors:
        errors["password"] = pwd_errors
    if password != password2:
        errors["password2"] = ["两次输入的密码不一致"]
    if errors:
        return render(request, "auth/setup.html", {"errors": errors},
                      status_code=400)

    user = User(username="owner", email="owner@invoice-ocr.local", is_admin=True)
    user.set_password(password)
    db.add(user)
    db.commit()

    user.record_login(db, request.client.host if request.client else "")
    flash(request, "账户设置成功，欢迎使用发票OCR系统", "success")
    return _login_response(user, remember=True, next_url="/")


@router.get("/register", name="auth.register")
async def register(db: Session = Depends(get_db)):
    target = "/auth/setup" if User.can_register(db) else "/auth/login"
    return RedirectResponse(target, status_code=303)


@router.get("/logout", name="auth.logout")
async def logout(request: Request):
    flash(request, "已安全退出", "info")
    resp = RedirectResponse("/auth/login", status_code=303)
    resp.delete_cookie(security.SESSION_COOKIE)
    resp.delete_cookie(security.MFA_COOKIE)
    return resp


@router.get("/change-password", name="auth.change_password")
async def change_password_page(request: Request,
                               user: User = Depends(require_user)):
    return render(request, "auth/change_password.html", {"errors": {}})


@router.post("/change-password", dependencies=[Depends(verify_csrf)])
async def change_password_submit(request: Request,
                                 old_password: str = Form(""),
                                 new_password: str = Form(""),
                                 new_password2: str = Form(""),
                                 user: User = Depends(require_user),
                                 db: Session = Depends(get_db)):
    errors: dict[str, list[str]] = {}
    if not user.check_password(old_password):
        errors["old_password"] = ["当前密码错误"]
    pwd_errors = _validate_password(new_password)
    if pwd_errors:
        errors["new_password"] = pwd_errors
    elif user.check_password(new_password):
        errors["new_password"] = ["新密码不能与当前密码相同"]
    if new_password != new_password2:
        errors["new_password2"] = ["两次输入的密码不一致"]
    if errors:
        return render(request, "auth/change_password.html", {"errors": errors},
                      status_code=400)

    user.set_password(new_password)
    db.commit()
    flash(request, "密码修改成功，请重新登录", "success")
    resp = RedirectResponse("/auth/login", status_code=303)
    resp.delete_cookie(security.SESSION_COOKIE)
    return resp


@router.get("/mfa/setup", name="auth.mfa_setup")
async def mfa_setup_page(request: Request,
                         user: User = Depends(require_user),
                         db: Session = Depends(get_db)):
    if user.mfa_enabled:
        return RedirectResponse("/auth/mfa/manage", status_code=303)

    if not user.mfa_secret:
        user.generate_mfa_secret()
        db.commit()

    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(user.get_mfa_uri())
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return render(request, "auth/mfa_setup.html", {
        "errors": {}, "qr_b64": qr_b64, "secret": user.mfa_secret,
    })


@router.post("/mfa/setup", dependencies=[Depends(verify_csrf)])
async def mfa_setup_submit(request: Request,
                           code: str = Form(""),
                           user: User = Depends(require_user),
                           db: Session = Depends(get_db)):
    if user.verify_mfa_code(code.strip()):
        user.mfa_enabled = True
        db.commit()
        flash(request, "两步验证已成功启用", "success")
        resp = RedirectResponse("/auth/mfa/manage?just_enabled=1", status_code=303)
        return resp

    flash(request, "验证码错误，请重试", "danger")
    return RedirectResponse("/auth/mfa/setup", status_code=303)


@router.get("/mfa/manage", name="auth.mfa_manage")
async def mfa_manage_page(request: Request,
                          user: User = Depends(require_user)):
    just_enabled = request.query_params.get("just_enabled") == "1"
    return render(request, "auth/mfa_manage.html", {
        "mfa_enabled": user.mfa_enabled, "just_enabled": just_enabled,
    })


@router.post("/mfa/manage", dependencies=[Depends(verify_csrf)])
async def mfa_manage_submit(request: Request,
                            action: str = Form(""),
                            user: User = Depends(require_user),
                            db: Session = Depends(get_db)):
    if action == "disable":
        user.mfa_enabled = False
        user.mfa_secret = None
        db.commit()
        flash(request, "两步验证已关闭", "info")
    return RedirectResponse("/auth/mfa/manage", status_code=303)


@router.get("/profile", name="auth.profile")
async def profile(request: Request, user: User = Depends(require_user)):
    return render(request, "auth/profile.html", {})
