# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
"""模块级辅助函数（从 main.py 闭包中提取）。"""

from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from datetime import date, datetime
from typing import Any

import pandas as pd
from filelock import FileLock
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from app.config import get_settings
from app.constants import ACTUAL_REPORTER_MAP, ENERGY_REPORTER_MAP, MINE_LIST
from app.storage import (
    append_records,
    overwrite_records,
    replace_records_for_mine_date,
    replace_sales_records_for_mine_week,
    storage_uses_database,
)
from app.timeutil import format_series_as_beijing_display


def df_to_html_table(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    return df.to_html(index=False, classes="data-table", border=0, escape=True)


def coerce_ledger_value(col: str, raw: str) -> Any:
    s = (raw or "").strip()
    if not s:
        return ""
    if "日期" in col and not ("时间" in col):
        try:
            return date.fromisoformat(s).strftime("%Y-%m-%d")
        except ValueError:
            return s
    if "吨" in col or "产量" in col or "销量" in col or "进尺" in col:
        try:
            return float(s.replace(",", ""))
        except ValueError:
            return s
    if "时间" in col:
        # 简短格式 MM-DD HH:MM → 补全年份
        try:
            t = datetime.strptime(s, "%m-%d %H:%M")
            return t.replace(year=datetime.now().year).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass
        return s
    return s


@lru_cache(maxsize=1)
def compute_asset_version() -> str:
    """基于静态文件 mtime 生成缓存版本号。"""
    h = hashlib.sha1()
    base = get_settings().base_dir
    for rel in ("static/app.css", "static/app.js"):
        p = base / rel
        try:
            h.update(str(p.stat().st_mtime_ns).encode())
        except OSError:
            continue
    return h.hexdigest()[:10] or "dev"


def get_paths() -> tuple[str, str]:
    """返回 (actual_production_path, energy_reporting_path)。"""
    s = get_settings()
    return s.actual_production_path, s.energy_reporting_path


def safe_append(df: pd.DataFrame, file_path: str) -> None:
    lock = FileLock(file_path + ".lock")
    with lock:
        append_records(file_path, df)


def safe_overwrite(df: pd.DataFrame, file_path: str) -> None:
    lock = FileLock(file_path + ".lock")
    with lock:
        overwrite_records(file_path, df)


def safe_replace(file_path: str, mine: str, prod_date_iso: str, df_new: pd.DataFrame) -> int:
    lock = FileLock(file_path + ".lock")
    with lock:
        return replace_records_for_mine_date(file_path, mine, prod_date_iso, df_new)


def safe_replace_sales(
    file_path: str, mine: str, week_start_iso: str, week_end_iso: str, df_new: pd.DataFrame
) -> int:
    lock = FileLock(file_path + ".lock")
    with lock:
        return replace_sales_records_for_mine_week(
            file_path, mine, week_start_iso, week_end_iso, df_new
        )


def nav_and_page(role: str, reporter_kind: str | None, session: dict) -> tuple[list[dict], str]:
    if role == "管理员":
        nav = [
            {"id": "visual", "label": "数据可视化", "path": "/go/visual", "group": "数据查看"},
            {"id": "admin_ledger", "label": "历史台账", "path": "/go/admin_ledger", "group": "数据查看"},
            {"id": "entry_actual", "label": "实际产量填报", "path": "/go/entry_actual", "group": "填报"},
            {"id": "entry_energy", "label": "能源局产销量填报", "path": "/go/entry_energy", "group": "填报"},
            {"id": "entry_sales", "label": "实际销量填报", "path": "/go/entry_sales", "group": "填报"},
            {"id": "reports", "label": "生成报表", "path": "/go/reports", "group": "系统"},
            {"id": "passwords", "label": "密码管理", "path": "/go/passwords", "group": "系统"},
            {"id": "logs", "label": "系统日志", "path": "/go/logs", "group": "系统"},
        ]
        default = "visual"
    elif role == "填报人员" and (reporter_kind or "") == "实际产量填报":
        nav = [
            {"id": "entry_actual", "label": "实际产量", "path": "/go/entry_actual"},
            {"id": "history", "label": "历史记录", "path": "/go/history"},
        ]
        default = "entry_actual"
    elif role == "填报人员":
        nav = [
            {"id": "entry_energy", "label": "能源局", "path": "/go/entry_energy"},
            {"id": "history", "label": "历史记录", "path": "/go/history"},
        ]
        default = "entry_energy"
    else:
        nav = [
            {"id": "visual", "label": "数据可视化", "path": "/go/visual"},
            {"id": "admin_ledger", "label": "历史台账", "path": "/go/admin_ledger"},
        ]
        default = "visual"
    active = (session or {}).get("active_section") or default
    valid = {n["id"] for n in nav}
    if active not in valid:
        active = default
    return nav, active


def render_duplicate_confirmation(
    request: Request,
    templates: Jinja2Templates,
    *,
    kind: str,
    mine: str,
    prod_date_iso: str,
    existing_df: pd.DataFrame,
    pending_df: pd.DataFrame,
    form_fields: dict[str, str],
) -> Any:
    ex = existing_df.copy()
    for c in ("提交时间", "报送时间", "填报时间"):
        if c in ex.columns:
            ex[c] = format_series_as_beijing_display(ex[c])
    kind_label = {"actual": "实际产量", "energy": "能源局产销量", "sales": "实际销量"}.get(kind, kind)
    submit_path = {
        "actual": "/entry/actual/submit",
        "energy": "/entry/energy/submit",
        "sales": "/entry/sales/submit",
    }.get(kind, "/entry/actual/submit")
    role_str = str(request.session.get("role") or "")
    nav, _session_page = nav_and_page(role_str, request.session.get("reporter_kind"), request.session)
    page_here = {"actual": "entry_actual", "energy": "entry_energy", "sales": "entry_sales"}.get(kind, kind)
    return templates.TemplateResponse(
        request,
        "entry_duplicate.html",
        {
            "request": request,
            "role": request.session.get("role"),
            "reporter_kind": request.session.get("reporter_kind"),
            "nav": nav,
            "page": page_here,
            "storage_db": storage_uses_database(),
            "form_error": None,
            "flash": None,
            "actual_reporter_map": {},
            "energy_reporter_map": {},
            "kind_label": kind_label,
            "mine": mine,
            "prod_date": prod_date_iso,
            "existing_count": int(len(ex)),
            "existing_html": df_to_html_table(ex),
            "pending_html": df_to_html_table(pending_df),
            "form_fields": form_fields,
            "submit_path": submit_path,
        },
    )
