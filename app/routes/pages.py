# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
"""页面渲染路由（首页、go/{section} 导航）。"""

from __future__ import annotations

import logging
import logging.handlers
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlencode

import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import get_login_by_token
from app.config import get_settings
from app.constants import ACTUAL_REPORTER_MAP, ENERGY_REPORTER_MAP, MINE_LIST
from app.helpers import df_to_html_table, get_paths, nav_and_page
from app.report_engine import read_sjcl_v2_daily_plans_from_template
from app.storage import read_records, storage_uses_database
from app.timeutil import format_series_as_beijing_display, get_weekly_range, today_beijing
from app.utils import exclude_mines

LOG_FILE = get_settings().log_file

router = APIRouter()


def restore_rt_to_session(request: Request) -> RedirectResponse | None:
    if request.session.get("role"):
        return None
    tok = request.query_params.get("rt")
    if not tok:
        return None
    data = get_login_by_token(str(tok))
    if not data:
        return None
    request.session["role"] = data["role"]
    if data.get("reporter_kind"):
        request.session["reporter_kind"] = data["reporter_kind"]
    request.session["auth_token"] = str(tok)
    new_q: list[tuple[str, str]] = []
    for k, v in request.query_params.multi_items():
        if k == "rt":
            continue
        new_q.append((k, v))
    path = str(request.url.path) or "/"
    if new_q:
        path = f"{path}?{urlencode(new_q, doseq=True)}"
    return RedirectResponse(path, status_code=303)


@router.get("/go/{section}")
def go(request: Request, section: str) -> RedirectResponse:
    request.session["active_section"] = section
    t = request.query_params.get("t", "")
    if section == "admin_ledger" and t in ("actual", "nybb", "sales"):
        request.session["ledger_t"] = t
        mines = [m.strip() for m in request.query_params.getlist("mine") if m.strip()]
        if mines:
            qs = "&".join(f"mine={quote(m)}" for m in mines)
            return RedirectResponse(f"/?{qs}", status_code=303)
    return RedirectResponse("/", status_code=303)


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> Any:
    templates = request.app.state.templates
    rdr = restore_rt_to_session(request)
    if rdr:
        return rdr
    role = request.session.get("role")
    if not role:
        return RedirectResponse("/login", status_code=303)
    act_path, en_path = get_paths()
    nav, page = nav_and_page(
        str(role), request.session.get("reporter_kind"), request.session
    )
    ctx = {
        "request": request,
        "role": role,
        "reporter_kind": request.session.get("reporter_kind"),
        "nav": nav,
        "page": page,
        "storage_db": storage_uses_database(),
        "db_healthy": storage_uses_database(),
        "form_error": request.session.pop("form_error", None),
        "flash": request.session.pop("flash", None),
        "actual_reporter_map": ACTUAL_REPORTER_MAP,
        "actual_daily_plan_map": read_sjcl_v2_daily_plans_from_template(
            get_settings().sjcl_template_v2
        ),
        "energy_reporter_map": ENERGY_REPORTER_MAP,
    }
    # ── 分页分发 ──
    _PAGE_HANDLERS = {
        "visual": _render_visual,
        "entry_actual": _render_entry_actual,
        "entry_energy": _render_entry_energy,
        "entry_sales": _render_entry_sales,
        "history": _render_history,
        "admin_ledger": _render_admin_ledger,
        "reports": _render_reports,
        "passwords": _render_passwords,
        "logs": _render_logs,
    }
    handler = _PAGE_HANDLERS.get(page)
    if handler:
        return handler(request, templates, ctx, role, act_path, en_path)
    return templates.TemplateResponse(
        request,
        "message.html",
        {**ctx, "title": "无法访问", "message": "您没有访问该功能的权限。"},
    )

# ── 分页渲染函数 ──

def _render_visual(request: Request, templates: Jinja2Templates, ctx: dict, role: str, act_path: str, en_path: str) -> Any:
    today_cap = today_beijing()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {**ctx, "visual_custom_max_date": today_cap.isoformat()},
    )

def _render_entry_actual(request: Request, templates: Jinja2Templates, ctx: dict, role: str, act_path: str, en_path: str) -> Any:
    return templates.TemplateResponse(
        request,
        "entry_actual.html",
        {**ctx, "mines": MINE_LIST, "yesterday": (today_beijing() - timedelta(days=1))},
    )

def _render_entry_energy(request: Request, templates: Jinja2Templates, ctx: dict, role: str, act_path: str, en_path: str) -> Any:
    return templates.TemplateResponse(
        request,
        "entry_energy.html",
        {**ctx, "mines": MINE_LIST, "yesterday": (today_beijing() - timedelta(days=1))},
    )

def _render_entry_sales(request: Request, templates: Jinja2Templates, ctx: dict, role: str, act_path: str, en_path: str) -> Any:
    today = today_beijing()
    wk_start, wk_end = get_weekly_range(today)
    return templates.TemplateResponse(
        request,
        "entry_sales.html",
        {
            **ctx,
            "mines": MINE_LIST,
            "today_iso": today.isoformat(),
            "default_week_end": wk_end.isoformat(),
            "default_week_start": wk_start.isoformat(),
        },
    )

def _render_history(request: Request, templates: Jinja2Templates, ctx: dict, role: str, act_path: str, en_path: str) -> Any:
    is_actual = (role == "填报人员" and (request.session.get("reporter_kind") or "") == "实际产量填报")
    p = act_path if is_actual else en_path
    df = exclude_mines(read_records(p))

    today_str = today_beijing().isoformat()
    time_col_key = "提交时间" if is_actual else "报送时间"
    mine_status: list[dict[str, object]] = []
    for mine_name in MINE_LIST:
        submitted = False
        if not df.empty and "所属煤矿" in df.columns and time_col_key in df.columns:
            mine_rows = df[df["所属煤矿"].astype(str).str.strip() == mine_name]
            submitted = mine_rows[time_col_key].astype(str).str.startswith(today_str).any()
        mine_status.append({"name": mine_name, "submitted": submitted})

    if not df.empty:
        if time_col_key in df.columns:
            df = df.sort_values(time_col_key, ascending=False, na_position="last").reset_index(drop=True)
        for c in ("提交时间", "报送时间"):
            if c in df.columns:
                df[c] = format_series_as_beijing_display(df[c])

    return templates.TemplateResponse(
        request,
        "history.html",
        {
            **ctx,
            "table_html": df_to_html_table(df) if not df.empty else None,
            "mine_status": mine_status,
        },
    )

def _render_admin_ledger(request: Request, templates: Jinja2Templates, ctx: dict, role: str, act_path: str, en_path: str) -> Any:
    ft = request.query_params.get("t") or request.session.get("ledger_t") or "actual"
    if ft not in ("actual", "nybb", "sales"):
        ft = "actual"
    selected_mines = [m.strip() for m in request.query_params.getlist("mine") if m.strip()]
    s = get_settings()
    if ft == "actual":
        p = act_path
    elif ft == "sales":
        p = s.actual_sales_path
    else:
        p = en_path
    df = exclude_mines(read_records(p))

    today_str = today_beijing().isoformat()
    mine_status: list[dict[str, object]] = []
    time_col_key = "提交时间" if ft == "actual" else ("报送时间" if ft == "nybb" else "填报时间")
    for mine_name in MINE_LIST:
        submitted = False
        if not df.empty and "所属煤矿" in df.columns and time_col_key in df.columns:
            mine_rows = df[df["所属煤矿"].astype(str).str.strip() == mine_name]
            submitted = mine_rows[time_col_key].astype(str).str.startswith(today_str).any()
        mine_status.append({"name": mine_name, "submitted": submitted})

    if not df.empty:
        if time_col_key in df.columns:
            df = df.sort_values(time_col_key, ascending=False, na_position="last")
        for c in ("提交时间", "报送时间", "填报时间"):
            if c in df.columns:
                df[c] = format_series_as_beijing_display(df[c])

    if selected_mines and not df.empty and "所属煤矿" in df.columns:
        df = df[df["所属煤矿"].astype(str).str.strip().isin(selected_mines)].copy()
    ledger_orig_indices: list[int] = df.index.tolist() if not df.empty else []
    rows: list[list[object]] = []
    if not df.empty:
        for _, r in df.iterrows():
            row_cells: list[str] = []
            for x in r.tolist():
                if x is None or (isinstance(x, float) and pd.isna(x)):
                    row_cells.append("")
                elif isinstance(x, datetime):
                    now_year = datetime.now().year
                    fmt = "%m-%d %H:%M" if x.year == now_year else "%Y-%m-%d %H:%M"
                    row_cells.append(x.strftime(fmt))
                elif isinstance(x, date):
                    row_cells.append(x.isoformat())
                else:
                    row_cells.append(str(x))
            rows.append(row_cells)

    return templates.TemplateResponse(
        request,
        "admin_ledger.html",
        {
            **ctx,
            "form_type": ft,
            "nrows": len(df),
            "ledger_cols": list(df.columns) if not df.empty else [],
            "ledger_rows": rows,
            "mine_status": mine_status,
            "mine_list": MINE_LIST,
            "selected_mines": selected_mines,
            "ledger_orig_indices": ledger_orig_indices,
            "readonly": role != "管理员",
        },
    )

def _render_reports(request: Request, templates: Jinja2Templates, ctx: dict, role: str, act_path: str, en_path: str) -> Any:
    today = today_beijing()
    wk_start, wk_end = get_weekly_range(today)
    brief_text = request.session.pop("brief_text", None)
    weekly_dl = request.session.pop("weekly_download_file", None)
    return templates.TemplateResponse(
        request,
        "reports.html",
        {
            **ctx,
            "default_date": (today - timedelta(days=1)),
            "default_week_start": wk_start.isoformat(),
            "default_week_end": wk_end.isoformat(),
            "brief_text": brief_text,
            "weekly_download_file": weekly_dl,
        },
    )

def _render_passwords(request: Request, templates: Jinja2Templates, ctx: dict, role: str, act_path: str, en_path: str) -> Any:
    if role != "管理员":
        return templates.TemplateResponse(
            request,
            "message.html",
            {**ctx, "title": "无法访问", "message": "您没有访问该功能的权限。"},
        )
    return templates.TemplateResponse(
        request, "passwords.html", {**ctx, "msg": None, "ok": None}
    )

def _render_logs(request: Request, templates: Jinja2Templates, ctx: dict, role: str, act_path: str, en_path: str) -> Any:
    if role != "管理员":
        return templates.TemplateResponse(
            request,
            "message.html",
            {**ctx, "title": "无法访问", "message": "您没有访问该功能的权限。"},
        )
    log_lines: list[str] = []
    if LOG_FILE.exists():
        try:
            raw = LOG_FILE.read_text(encoding="utf-8", errors="replace")
            log_lines = raw.splitlines()[-500:]
        except Exception:
            log_lines = ["(无法读取日志文件)"]
    return templates.TemplateResponse(
        request, "logs.html", {**ctx, "log_lines": log_lines}
    )