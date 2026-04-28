# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
# 本文件为「云煤矿业产销量管理系统」的组成部分。
# 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
# 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE。
from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any

import tomllib
from filelock import FileLock

from app.config import get_settings

_RUNTIME_JSON = "app_passwords.json"
_KEYS = ("admin", "reporter", "viewer")
_DEFAULT_VIEWER_PASSWORD = "ymky6666"


def _read_toml_passwords() -> dict[str, str]:
    s = get_settings()
    p = s.optional_secrets_toml
    if not p or not p.is_file():
        return {k: "" for k in _KEYS}
    try:
        with open(p, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return {k: "" for k in _KEYS}
    pw = data.get("passwords", {}) or {}
    if not isinstance(pw, dict):
        return {k: "" for k in _KEYS}
    return {k: str(pw.get(k) or "").strip() for k in _KEYS}


def _read_env_passwords() -> dict[str, str]:
    return {
        "admin": (os.environ.get("YMKY_PASSWORD_ADMIN") or os.environ.get("YMKY_ADMIN") or "").strip(),
        "reporter": (os.environ.get("YMKY_PASSWORD_REPORTER") or os.environ.get("YMKY_REPORTER") or "").strip(),
        "viewer": (os.environ.get("YMKY_PASSWORD_VIEWER") or os.environ.get("YMKY_VIEWER") or "").strip(),
    }


def _read_secrets_block() -> dict[str, str]:
    base = {k: "" for k in _KEYS}
    for k, v in _read_toml_passwords().items():
        if k in base:
            base[k] = v
    envb = _read_env_passwords()
    for k in _KEYS:
        if envb.get(k):
            base[k] = envb[k]  # env overrides toml
    return base


def _read_runtime_overrides() -> dict[str, str]:
    try:
        path = get_settings().app_passwords_json
    except Exception:
        return {}
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            raw: Any = json.load(f)
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k in _KEYS:
        v = raw.get(k)
        if isinstance(v, str) and v:
            out[k] = v
    return out


def load_effective_passwords() -> dict[str, str]:
    base = _read_secrets_block()
    over = _read_runtime_overrides()
    for k, v in over.items():
        base[k] = v
    if not str(base.get("viewer", "")).strip():
        base["viewer"] = _DEFAULT_VIEWER_PASSWORD
    return base


def has_configured_passwords() -> bool:
    m = load_effective_passwords()
    return any(m.get(k) for k in _KEYS)


def _digest(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def check_role_password(plain: str, role: str) -> bool:
    if not (plain and str(plain).strip()):
        return False
    m = load_effective_passwords()
    role_key = {
        "管理员": "admin",
        "填报人员": "reporter",
        "产量数据可视化": "viewer",
    }
    key = role_key.get(role, "reporter")
    correct = m.get(key, "")
    if not correct:
        return False
    d1 = _digest(plain.strip())
    d2 = _digest(correct)
    return hmac.compare_digest(d1, d2)


def _verify_admin_password(plain: str) -> bool:
    return check_role_password(plain, "管理员")


def save_password_updates(updates: dict[str, str], admin_confirm: str) -> tuple[bool, str]:
    if not (admin_confirm and str(admin_confirm).strip()):
        return False, "请填写「当前管理员密码」以确认修改。"
    if not _verify_admin_password(admin_confirm.strip()):
        return False, "当前管理员密码不正确，无法保存。"

    for k, v in updates.items():
        if k not in _KEYS:
            return False, f"不支持的键: {k}"
        s = (v or "").strip()
        if not s:
            return False, "新密码不能为空。"

    base = load_effective_passwords()
    for k, v in updates.items():
        base[k] = (v or "").strip()
    path = get_settings().app_passwords_json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lockp = path + ".lock"
    with FileLock(lockp):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({k: base[k] for k in _KEYS}, f, ensure_ascii=False, indent=2)
    return True, "密码已保存。新密码立即生效，无需重启。"


def is_debug_toml_enabled() -> bool:
    s = get_settings()
    p = s.optional_secrets_toml
    if not p or not p.is_file():
        return False
    try:
        with open(p, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return False
    dbg = data.get("debug", {})
    if isinstance(dbg, dict) and bool(dbg.get("local_password_autofill", False)):
        return True
    return False


def should_debug_prefill() -> bool:
    s = get_settings()
    if s.local_debug_password_autofill:
        return True
    v = (os.environ.get("YMKY_LOCAL_DEBUG") or "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    return is_debug_toml_enabled()


def debug_prefill_for_role(temp_role: str) -> str:
    m = load_effective_passwords()
    role_key = {
        "管理员": "admin",
        "填报人员": "reporter",
        "产量数据可视化": "viewer",
    }
    k = role_key.get(temp_role, "reporter")
    return (m.get(k) or "").strip()
