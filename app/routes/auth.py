# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
"""登录、身份选择与注销路由。"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import (
    check_role_password,
    create_login_token,
    debug_prefill_for_role,
    get_login_by_token,
    has_configured_passwords,
    revoke_token,
    should_debug_prefill,
)
from app.helpers import nav_and_page
from app.storage import storage_uses_database

router = APIRouter()

# ── 登录限流：每 IP 5 次失败/分钟 ──
_LOGIN_ATTEMPTS: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60.0  # 秒
_RATE_LIMIT_MAX_FAILS = 5


def _check_rate_limit(client_ip: str) -> bool:
    """返回 True 表示已被限流。"""
    now = time.time()
    attempts = _LOGIN_ATTEMPTS[client_ip]
    # 清理过期记录
    _LOGIN_ATTEMPTS[client_ip] = [t for t in attempts if now - t < _RATE_LIMIT_WINDOW]
    return len(_LOGIN_ATTEMPTS[client_ip]) >= _RATE_LIMIT_MAX_FAILS


def _record_failed_attempt(client_ip: str) -> None:
    _LOGIN_ATTEMPTS[client_ip].append(time.time())


def _clear_attempts(client_ip: str) -> None:
    _LOGIN_ATTEMPTS.pop(client_ip, None)


@router.get("/login", response_class=HTMLResponse)
def login_get(request: Request) -> Any:
    templates = request.app.state.templates
    if request.session.get("role"):
        return RedirectResponse("/", status_code=303)
    if not has_configured_passwords():
        return templates.TemplateResponse(
            request,
            "message.html",
            {
                "title": "暂未配置登录密码",
                "message": "系统尚未设置任何登录密码，请联系管理员处理。",
            },
        )
    prefill = ""
    if should_debug_prefill() and request.session.get("login_temp_role"):
        prefill = debug_prefill_for_role(str(request.session["login_temp_role"]))
    le = request.session.pop("login_error", None)
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "step": "identity" if not request.session.get("login_temp_role") else "password",
            "temp_role": request.session.get("login_temp_role"),
            "debug_prefill": prefill,
            "login_error": le,
        },
    )


@router.post("/login/identity")
def login_identity(
    request: Request,
    role: str = Form(...),
) -> RedirectResponse:
    if role in ("填报人员", "管理员", "产量数据可视化"):
        request.session["login_temp_role"] = role
    return RedirectResponse("/login", status_code=303)


@router.get("/login/reset")
def login_reset(request: Request) -> RedirectResponse:
    # Clear temporary role/password step so user can re-pick identity.
    request.session["login_temp_role"] = None
    request.session["login_error"] = None
    return RedirectResponse("/login", status_code=303)


@router.post("/login/verify")
def login_verify(
    request: Request,
    password: str = Form(""),
) -> RedirectResponse:
    client_ip = request.client.host if request.client else "unknown"
    if _check_rate_limit(client_ip):
        request.session["login_error"] = "登录尝试过于频繁，请稍后再试"
        return RedirectResponse("/login", status_code=303)
    tr = request.session.get("login_temp_role")
    if not tr or not str(password).strip():
        return RedirectResponse("/login", status_code=303)
    if not check_role_password(str(password), tr):
        _record_failed_attempt(client_ip)
        request.session["login_error"] = "密码错误，请重试"
        return RedirectResponse("/login", status_code=303)
    _clear_attempts(client_ip)
    if tr == "填报人员":
        request.session["reporter_pick_pending"] = True
        request.session["login_temp_role"] = None
        return RedirectResponse("/reporter/choose", status_code=303)
    request.session["role"] = tr
    tok = create_login_token(role=tr, reporter_kind=None)
    request.session["auth_token"] = tok
    request.session["login_temp_role"] = None
    return RedirectResponse("/", status_code=303)


@router.get("/reporter/choose", response_class=HTMLResponse)
def reporter_choose(request: Request) -> Any:
    templates = request.app.state.templates
    if not request.session.get("reporter_pick_pending"):
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(request, "reporter_choose.html", {})


@router.post("/reporter/confirm")
def reporter_confirm(
    request: Request,
    kind: str = Form(...),
) -> RedirectResponse:
    if not request.session.get("reporter_pick_pending"):
        return RedirectResponse("/login", status_code=303)
    if kind not in ("actual", "nybb"):
        return RedirectResponse("/reporter/choose", status_code=303)
    rk = "实际产量填报" if kind == "actual" else "能源局口径产销量填报"
    request.session["role"] = "填报人员"
    request.session["reporter_kind"] = rk
    request.session["reporter_pick_pending"] = None
    tok = create_login_token(role="填报人员", reporter_kind=rk)
    request.session["auth_token"] = tok
    return RedirectResponse("/", status_code=303)


@router.get("/logout")
def logout(request: Request) -> RedirectResponse:
    tok = request.session.get("auth_token")
    if tok:
        revoke_token(str(tok))
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
