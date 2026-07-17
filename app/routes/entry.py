# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
"""数据填报路由（实际产量、能源局产销量、实际销量）。"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd
from filelock import FileLock
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.constants import ACTUAL_REPORTER_MAP, ENERGY_REPORTER_MAP
from app.helpers import (
    get_paths,
    render_duplicate_confirmation,
    safe_append,
    safe_replace,
    safe_replace_sales,
)
from app.report_engine import read_sjcl_v2_daily_plans_from_template
from app.storage import (
    dataframe_actual_production_new_row,
    dataframe_actual_sales_new_row,
    dataframe_energy_reporting_new_row,
    find_records_by_mine_date,
    find_sales_records_by_mine_week,
    overwrite_records,
    read_records,
    storage_uses_database,
    verify_actual_submission_visible,
    verify_energy_submission_visible,
    verify_sales_submission_visible,
)
from app.timeutil import get_weekly_range, now_str

router = APIRouter()


@router.post("/entry/actual/submit", response_model=None)
def submit_actual(
    request: Request,
    mine: str = Form(""),
    prod_date: str = Form(""),
    production: str = Form("0"),
    reporter: str = Form(""),
    note: str = Form(""),
    action: str = Form("submit"),
    confirm: str = Form(""),
) -> Any:
    role = request.session.get("role")
    if role not in ("管理员", "填报人员"):
        return RedirectResponse("/login", status_code=303)
    rkind = str(request.session.get("reporter_kind", ""))
    if role == "填报人员" and rkind != "实际产量填报":
        return RedirectResponse("/", status_code=303)
    if action == "switch_nybb":
        request.session["reporter_kind"] = "能源局口径产销量填报"
        return RedirectResponse("/", status_code=303)
    if action == "logout":
        return RedirectResponse("/logout", status_code=303)
    if not mine:
        request.session["form_error"] = "请选择煤矿"
        return RedirectResponse("/", status_code=303)
    try:
        pd_ = date.fromisoformat(prod_date)
    except (ValueError, TypeError):
        request.session["form_error"] = "日期无效"
        return RedirectResponse("/", status_code=303)
    try:
        prod = float(production)
    except (TypeError, ValueError):
        prod = 0.0
    if prod == 0.0 and not str(note).strip():
        request.session["form_error"] = "产量为 0 时须填备注"
        return RedirectResponse("/", status_code=303)
    tmpl = get_settings().sjcl_template_v2
    daily_plan = read_sjcl_v2_daily_plans_from_template(tmpl).get(mine, 0.0)
    if daily_plan > 0 and prod > 0 and prod < daily_plan * 0.9 and not str(note).strip():
        rounded = round(daily_plan, 2)
        request.session["form_error"] = (
            f"产量低于日计划量的 90%（模板 B 列日计划量参考 {rounded:.2f} 吨），须填备注说明原因"
        )
        return RedirectResponse("/", status_code=303)
    rep_input = (reporter or "").strip()
    mapped_rep = ACTUAL_REPORTER_MAP.get(mine, "")
    if role != "管理员" and not rep_input and not mapped_rep:
        request.session["form_error"] = "请填写填报人"
        return RedirectResponse("/", status_code=303)
    who = "管理员" if role == "管理员" else (rep_input or mapped_rep)
    prod_date_iso = pd_.strftime("%Y-%m-%d")
    new_data = dataframe_actual_production_new_row(
        submit_time=now_str(),
        mine=mine,
        prod_date=prod_date_iso,
        production_t=prod,
        reporter=who,
        note=note,
    )
    act_path = get_paths()[0]

    if confirm not in ("append", "replace"):
        existing = find_records_by_mine_date(act_path, mine, prod_date_iso)
        if not existing.empty:
            return render_duplicate_confirmation(
                request,
                request.app.state.templates,
                kind="actual",
                mine=mine,
                prod_date_iso=prod_date_iso,
                existing_df=existing,
                pending_df=new_data,
                form_fields={
                    "mine": mine,
                    "prod_date": prod_date_iso,
                    "production": str(prod),
                    "reporter": who,
                    "note": note,
                },
            )

    ymky_log = logging.getLogger("ymky")
    if confirm == "replace":
        removed = safe_replace(act_path, mine, prod_date_iso, new_data)
        save_msg = f"已覆盖：删除旧记录 {removed} 条，写入新记录 1 条"
    else:
        safe_append(new_data, act_path)
        save_msg = "提交成功" if confirm != "append" else "已追加（保留旧记录）"

    if not verify_actual_submission_visible(act_path, mine, prod_date_iso, prod):
        ymky_log.error(
            "实际产量写入后校验失败 path=%s mine=%s date=%s prod=%s db=%s",
            act_path,
            mine,
            prod_date_iso,
            prod,
            storage_uses_database(),
        )
        request.session["form_error"] = (
            "保存后校验未通过：未能在台账（数据库/文件中）查到与本次一致的产量记录，本次可能未成功保存。"
            "请勿以为已提交成功，请重试或联系管理员。"
        )
        return RedirectResponse("/", status_code=303)

    request.session["flash"] = save_msg
    return RedirectResponse("/", status_code=303)


@router.post("/entry/energy/submit", response_model=None)
def submit_energy(
    request: Request,
    mine: str = Form(""),
    prod_date: str = Form(""),
    production: str = Form("0"),
    sales: str = Form("0"),
    reporter: str = Form(""),
    note: str = Form(""),
    action: str = Form("submit"),
    confirm: str = Form(""),
) -> Any:
    role = request.session.get("role")
    if role not in ("管理员", "填报人员"):
        return RedirectResponse("/login", status_code=303)
    rkind = str(request.session.get("reporter_kind", ""))
    if role == "填报人员" and rkind != "能源局口径产销量填报":
        return RedirectResponse("/", status_code=303)
    if action == "switch_actual":
        request.session["reporter_kind"] = "实际产量填报"
        return RedirectResponse("/", status_code=303)
    if action == "logout":
        return RedirectResponse("/logout", status_code=303)
    if not mine:
        request.session["form_error"] = "请选择煤矿"
        return RedirectResponse("/", status_code=303)
    try:
        pd_ = date.fromisoformat(prod_date)
    except (ValueError, TypeError):
        request.session["form_error"] = "日期无效"
        return RedirectResponse("/", status_code=303)
    try:
        p_f = float(production)
    except (TypeError, ValueError):
        p_f = 0.0
    try:
        s_f = float(sales)
    except (TypeError, ValueError):
        s_f = 0.0
    if (p_f == 0.0 or s_f == 0.0) and not str(note).strip():
        request.session["form_error"] = "产量或销量为 0 时须填备注"
        return RedirectResponse("/", status_code=303)
    rep_input = (reporter or "").strip()
    mapped_rep = ENERGY_REPORTER_MAP.get(mine, "")
    if role != "管理员" and not rep_input and not mapped_rep:
        request.session["form_error"] = "请填写填报人"
        return RedirectResponse("/", status_code=303)
    who = "管理员" if role == "管理员" else (rep_input or mapped_rep)
    prod_date_iso = pd_.strftime("%Y-%m-%d")
    new_data = dataframe_energy_reporting_new_row(
        report_time=now_str(),
        mine=mine,
        prod_date=prod_date_iso,
        production_t=p_f,
        sales_t=s_f,
        reporter=who,
        note=note,
    )
    en_path = get_paths()[1]

    if confirm not in ("append", "replace"):
        existing = find_records_by_mine_date(en_path, mine, prod_date_iso)
        if not existing.empty:
            return render_duplicate_confirmation(
                request,
                request.app.state.templates,
                kind="energy",
                mine=mine,
                prod_date_iso=prod_date_iso,
                existing_df=existing,
                pending_df=new_data,
                form_fields={
                    "mine": mine,
                    "prod_date": prod_date_iso,
                    "production": str(p_f),
                    "sales": str(s_f),
                    "reporter": who,
                    "note": note,
                },
            )

    ymky_log = logging.getLogger("ymky")
    if confirm == "replace":
        removed = safe_replace(en_path, mine, prod_date_iso, new_data)
        save_msg = f"已覆盖：删除旧记录 {removed} 条，写入新记录 1 条"
    else:
        safe_append(new_data, en_path)
        save_msg = "提交成功" if confirm != "append" else "已追加（保留旧记录）"

    if not verify_energy_submission_visible(en_path, mine, prod_date_iso, p_f, s_f):
        ymky_log.error(
            "能源局台账写入后校验失败 path=%s mine=%s date=%s prod=%s sales=%s db=%s",
            en_path,
            mine,
            prod_date_iso,
            p_f,
            s_f,
            storage_uses_database(),
        )
        request.session["form_error"] = (
            "保存后校验未通过：未能在台账中查到与本次产量、销量均一致的记录，本次可能未成功保存。"
            "请勿以为已提交成功，请重试或联系管理员。"
        )
        return RedirectResponse("/", status_code=303)

    request.session["flash"] = save_msg
    return RedirectResponse("/", status_code=303)


@router.post("/entry/sales/submit", response_model=None)
def submit_sales(
    request: Request,
    mine: str = Form(""),
    week_end: str = Form(""),
    sales: str = Form("0"),
    reporter: str = Form(""),
    note: str = Form(""),
    action: str = Form("submit"),
    confirm: str = Form(""),
    year_blended: str = Form("0"),
    year_purchased: str = Form("0"),
) -> Any:
    role = request.session.get("role")
    if role != "管理员":
        return RedirectResponse("/login", status_code=303)
    if action == "logout":
        return RedirectResponse("/logout", status_code=303)
    if not mine:
        request.session["form_error"] = "请选择煤矿"
        return RedirectResponse("/go/entry_sales", status_code=303)
    try:
        we_dt = date.fromisoformat(week_end)
    except (ValueError, TypeError):
        request.session["form_error"] = "周末日期无效"
        return RedirectResponse("/go/entry_sales", status_code=303)
    ws_dt, we_dt = get_weekly_range(we_dt)
    week_start_iso = ws_dt.strftime("%Y-%m-%d")
    week_end_iso = we_dt.strftime("%Y-%m-%d")
    try:
        sales_f = float(sales)
    except (TypeError, ValueError):
        sales_f = 0.0
    if sales_f == 0.0 and not str(note).strip():
        request.session["form_error"] = "销量为 0 时须填备注"
        return RedirectResponse("/go/entry_sales", status_code=303)
    rep_input = (reporter or "").strip()
    who = rep_input or "管理员"

    def _parse_float(val: str) -> float:
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    sales_path = get_settings().actual_sales_path
    blended_f = _parse_float(year_blended)
    purchased_f = _parse_float(year_purchased)

    # I/J 为 0 或空时，沿用最近一期"合计"记录的值（保持不变）
    if blended_f == 0.0 or purchased_f == 0.0:
        _existing_df = read_records(sales_path)
        if not _existing_df.empty:
            _existing_df["_we"] = pd.to_datetime(
                _existing_df["周结束日期"], errors="coerce"
            ).dt.date
            _totals = _existing_df[
                _existing_df["所属煤矿"].astype(str).str.strip() == "合计"
            ]
            if not _totals.empty:
                _we_date = pd.to_datetime(week_end_iso).date()
                _recent = _totals[_totals["_we"] <= _we_date]
                if not _recent.empty:
                    _latest = _recent.sort_values("_we").iloc[-1]
                    if blended_f == 0.0:
                        _v = pd.to_numeric(
                            _latest.get("年累计掺配煤销量(吨)", 0), errors="coerce"
                        )
                        blended_f = float(_v) if pd.notna(_v) else 0.0
                    if purchased_f == 0.0:
                        _v = pd.to_numeric(
                            _latest.get("年累计外购煤量(吨)", 0), errors="coerce"
                        )
                        purchased_f = float(_v) if pd.notna(_v) else 0.0

    new_data = dataframe_actual_sales_new_row(
        submit_time=now_str(),
        mine=mine,
        week_start=week_start_iso,
        week_end=week_end_iso,
        sales_t=sales_f,
        reporter=who,
        note=note,
        year_blended=blended_f,
        year_purchased=purchased_f,
    )

    if confirm not in ("append", "replace"):
        existing = find_sales_records_by_mine_week(sales_path, mine, week_start_iso, week_end_iso)
        if not existing.empty:
            return render_duplicate_confirmation(
                request,
                request.app.state.templates,
                kind="sales",
                mine=mine,
                prod_date_iso=f"{week_start_iso} 至 {week_end_iso}",
                existing_df=existing,
                pending_df=new_data,
                form_fields={
                    "mine": mine,
                    "week_end": week_end_iso,
                    "sales": str(sales_f),
                    "reporter": who,
                    "note": note,
                    "year_blended": str(blended_f),
                    "year_purchased": str(purchased_f),
                },
            )

    ymky_log = logging.getLogger("ymky")
    if confirm == "replace":
        removed = safe_replace_sales(sales_path, mine, week_start_iso, week_end_iso, new_data)
        save_msg = f"已覆盖：删除旧记录 {removed} 条，写入新记录 1 条"
    else:
        safe_append(new_data, sales_path)
        save_msg = "提交成功" if confirm != "append" else "已追加（保留旧记录）"

    if not verify_sales_submission_visible(sales_path, mine, week_start_iso, week_end_iso, sales_f):
        ymky_log.error(
            "实际销量台账写入后校验失败 path=%s mine=%s week=%s~%s sales=%s db=%s",
            sales_path,
            mine,
            week_start_iso,
            week_end_iso,
            sales_f,
            storage_uses_database(),
        )
        request.session["form_error"] = (
            "保存后校验未通过：未能在台账中查到与本次一致的销量记录，本次可能未成功保存。"
            "请勿以为已提交成功，请重试或联系管理员。"
        )
        return RedirectResponse("/go/entry_sales", status_code=303)

    # 同步更新/创建"合计"记录的 I/J 值（确保简报和周报表能取到当前周累计值）
    _totals_lock = FileLock(sales_path + ".lock")
    with _totals_lock:
        _df = read_records(sales_path)
        if not _df.empty:
            _df["_we"] = pd.to_datetime(_df["周结束日期"], errors="coerce").dt.date
            _df["_ws"] = pd.to_datetime(_df["周起始日期"], errors="coerce").dt.date
            _we_d = pd.to_datetime(week_end_iso).date()
            _ws_d = pd.to_datetime(week_start_iso).date()
            _mask = (
                (_df["所属煤矿"].astype(str).str.strip() == "合计")
                & (_df["_we"] == _we_d)
                & (_df["_ws"] == _ws_d)
            )
            if _mask.any():
                _df.loc[_mask, "年累计掺配煤销量(吨)"] = blended_f
                _df.loc[_mask, "年累计外购煤量(吨)"] = purchased_f
            else:
                _totals_row = dataframe_actual_sales_new_row(
                    submit_time=now_str(),
                    mine="合计",
                    week_start=week_start_iso,
                    week_end=week_end_iso,
                    sales_t=0.0,
                    reporter=who,
                    note="公司合计",
                    year_blended=blended_f,
                    year_purchased=purchased_f,
                )
                _df = pd.concat([_df, _totals_row], ignore_index=True)
            _df = _df.drop(columns=["_we", "_ws"], errors="ignore")
            overwrite_records(sales_path, _df)

    request.session["flash"] = save_msg
    return RedirectResponse("/go/entry_sales", status_code=303)
