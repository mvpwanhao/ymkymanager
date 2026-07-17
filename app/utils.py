# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
# 本文件为「云煤矿业产销量管理系统」的组成部分。
# 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
# 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE。
"""通用工具函数。"""

from __future__ import annotations

from urllib.parse import quote

import pandas as pd

from app.constants import REMOVED_MINE_KEYWORDS


def exclude_mines(df: pd.DataFrame) -> pd.DataFrame:
    """排除已关停/不参与统计的煤矿（羊街、竹麻地）。"""
    if df.empty or "所属煤矿" not in df.columns:
        return df
    mask = ~df["所属煤矿"].astype(str).str.contains("|".join(REMOVED_MINE_KEYWORDS), na=False)
    return df.loc[mask].copy()


def content_disposition_attachment(ascii_name: str, utf8_name: str) -> str:
    """生成 Content-Disposition header，兼容 ASCII 和 UTF-8 文件名。"""
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(utf8_name)}'
