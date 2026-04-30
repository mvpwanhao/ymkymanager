# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
# 本文件为「云煤矿业产销量管理系统」的组成部分。
# 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
# 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE。
"""仓库根目录 `VERSION` 中的发行编号；`/health` 默认使用，可被 `YMKY_APP_VERSION` 覆盖。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@lru_cache
def read_version_from_file() -> str:
    p = repo_root() / "VERSION"
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                return s
        return ""
    except OSError:
        return ""


def health_version(env_override: str) -> str:
    """传给 /health：`YMKY_APP_VERSION` 优先，否则 VERSION 文件；统一加 `v` 前缀（若尚无）。"""
    raw = (env_override or "").strip()
    if not raw:
        raw = read_version_from_file().strip()
    if not raw:
        return ""
    if raw.startswith("v") or raw.startswith("V"):
        return raw
    return "v" + raw
