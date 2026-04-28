# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
# 本文件为「云煤矿业产销量管理系统」的组成部分。
# 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
# 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE。
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Any

from filelock import FileLock

from app.config import get_settings
from app.timeutil import TZ_BEIJING, now_beijing


def _path() -> str:
    return get_settings().login_sessions_json


def _read_sessions() -> dict[str, dict[str, Any]]:
    p = _path()
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return {}
        return {str(k): v for k, v in raw.items() if isinstance(v, dict)}
    except Exception:
        return {}


def _write_sessions(data: dict[str, dict[str, Any]]) -> None:
    p = _path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _purge_expired(data: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    now = now_beijing()
    keep: dict[str, dict[str, Any]] = {}
    for tok, item in data.items():
        exp = item.get("expires_at", "")
        try:
            exp_dt = datetime.fromisoformat(str(exp))
        except Exception:
            continue
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=TZ_BEIJING)
        if exp_dt >= now:
            keep[tok] = item
    return keep


def create_login_token(*, role: str, reporter_kind: str | None, ttl_seconds: int | None = None) -> str:
    s = get_settings()
    sec = ttl_seconds if ttl_seconds is not None else s.session_ttl_seconds
    token = secrets.token_urlsafe(24)
    p = _path()
    lock = FileLock(p + ".lock")
    with lock:
        d = _purge_expired(_read_sessions())
        d[token] = {
            "role": role,
            "reporter_kind": reporter_kind or "",
            "expires_at": (now_beijing() + timedelta(seconds=sec)).isoformat(),
        }
        _write_sessions(d)
    return token


def get_login_by_token(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    p = _path()
    lock = FileLock(p + ".lock")
    with lock:
        d = _purge_expired(_read_sessions())
        item = d.get(token)
        _write_sessions(d)
    if not item:
        return None
    role = str(item.get("role", "")).strip()
    if not role:
        return None
    return {
        "role": role,
        "reporter_kind": str(item.get("reporter_kind", "")).strip() or None,
    }


def revoke_token(token: str) -> None:
    if not token:
        return
    p = _path()
    lock = FileLock(p + ".lock")
    with lock:
        d = _read_sessions()
        d.pop(token, None)
        _write_sessions(d)
