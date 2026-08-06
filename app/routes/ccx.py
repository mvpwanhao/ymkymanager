
# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
# 本文件为「云煤矿业产销量管理系统」的组成部分。
# 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
# 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE.
"""产销量 JSON API（供 AQ 前端合并接入）。

与旧表单流程（app/routes/entry.py / report.py）共用同一套
storage / report_engine / notify 逻辑，返回统一信封 {code, message, data}，
便于 aq 前端 axios 拦截器直接消费。

认证：由 aq 后端代理注入 X-CCX-Internal-Key + X-User-* 可信头，
CcxAuthMiddleware 完成角色映射（adminer→管理员、admin→产量数据可视化、zk→填报人员）。
"""

from __future__ import annotations

import logging
import math
import os
import re
from datetime import date
from io import StringIO
from typing import Any
from urllib.parse import quote

import pandas as pd
from fastapi import APIRouter, Body, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from filelock import FileLock

from app.config import get_settings
from app.constants import (
    ACTUAL_REPORTER_MAP,
    ENERGY_REPORTER_MAP,
    MINE_LIST,
    REMOVED_MINE_KEYWORDS,
)
from app.helpers import (
    get_paths,
    safe_append,
    safe_replace,
    safe_replace_sales,
    coerce_ledger_value,
    safe_overwrite,
)
from app.utils import content_disposition_attachment, exclude_mines
from app.report_engine import (
    generate_nybb_report,
    generate_sjcl_report,
    generate_brief_report,
    generate_weekly_report,
    read_sjcl_v2_daily_plans_from_template,
)
from app.services.notify import (
    notify_submit_actual,
    notify_submit_energy,
    notify_submit_sales,
)
from app.storage import (
    dataframe_actual_production_new_row,
    dataframe_actual_sales_new_row,
    dataframe_energy_reporting_new_row,
    find_records_by_mine_date,
    find_sales_records_by_mine_week,
    overwrite_records,
    read_records,
    reorder_ledger_dataframe_for_table,
    verify_actual_submission_visible,
    verify_energy_submission_visible,
    verify_sales_submission_visible,
)
from app.timeutil import get_weekly_range, now_str, today_beijing
from app.viz_engine import build_viz_data, export_viz_excel

router = APIRouter(prefix="/api/ccx", tags=["ccx"])

_log = logging.getLogger("ymky.ccx")

ADMIN_ROLE = "管理员"
VIEWER_ROLE = "产量数据可视化"
REPORTER_ROLE = "填报人员"

LEDGER_TABLE = {
    "actual": "actual_production",
    "energy": "energy_reporting",
    "sales": "actual_sales",
}
LEDGER_PATH = {
    "actual": lambda: get_paths()[0],
    "energy": lambda: get_paths()[1],
    "sales": lambda: get_settings().actual_sales_path,
}


def _ok(data: Any = None, message: str = "OK") -> JSONResponse:
    return JSONResponse({"code": 200, "message": message, "data": data})


def _err(status: int, message: str) -> JSONResponse:
    return JSONResponse({"code": status, "message": message, "data": None}, status_code=status)


def _ident(request: Request) -> dict | None:
    """返回 CcxAuthMiddleware 注入的身份；未认证返回 None。"""
    return request.scope.get("ccx")


def _require(request: Request, roles: tuple[str, ...] | None = None) -> dict | None:
    ident = _ident(request)
    if not ident:
        return None
    if roles is not None and ident["role"] not in roles:
        return None
    return ident


def _denied(request: Request) -> JSONResponse:
    if _ident(request):
        return _err(403, "无权限执行该操作")
    return _err(401, "产销量服务未认证")


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clean_value(value: Any) -> Any:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _row_dicts(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    return [{k: _clean_value(v) for k, v in rec.items()} for rec in df.to_dict("records")]


@router.get("/me")
def ccx_me(request: Request) -> JSONResponse:
    ident = _require(request)
    if not ident:
        return _denied(request)
    return _ok(
        {
            "role": ident["role"],
            "aq_role": ident["aq_role"],
            "username": ident["username"],
            "user_id": ident["user_id"],
        }
    )


@router.post("/entry/actual/submit")
def submit_actual(request: Request, payload: dict = Body(...)) -> JSONResponse:
    ident = _require(request, (ADMIN_ROLE, REPORTER_ROLE))
    if not ident:
        return _denied(request)

    mine = str(payload.get("mine") or "").strip()
    prod_date = str(payload.get("prod_date") or "").strip()
    production = _to_float(payload.get("production"))
    reporter = str(payload.get("reporter") or "").strip()
    note = str(payload.get("note") or "").strip()
    confirm = str(payload.get("confirm") or "").strip()

    if not mine:
        return _err(400, "请选择煤矿")
    try:
        pd_ = date.fromisoformat(prod_date)
    except (ValueError, TypeError):
        return _err(400, "日期无效")
    if production == 0.0 and not note:
        return _err(400, "产量为 0 时须填备注")
    tmpl = get_settings().sjcl_template_v2
    daily_plan = read_sjcl_v2_daily_plans_from_template(tmpl).get(mine, 0.0)
    if daily_plan > 0 and production > 0 and production < daily_plan * 0.9 and not note:
        return _err(
            400,
            f"产量低于日计划量的 90%（模板 B 列日计划量参考 {round(daily_plan, 2):.2f} 吨），须填备注说明原因",
        )
    mapped_rep = ACTUAL_REPORTER_MAP.get(mine, "")
    if ident["role"] != ADMIN_ROLE and not reporter and not mapped_rep:
        return _err(400, "请填写填报人")
    who = ADMIN_ROLE if ident["role"] == ADMIN_ROLE else (reporter or mapped_rep)
    prod_date_iso = pd_.strftime("%Y-%m-%d")

    new_data = dataframe_actual_production_new_row(
        submit_time=now_str(),
        mine=mine,
        prod_date=prod_date_iso,
        production_t=production,
        reporter=who,
        note=note,
    )
    act_path = get_paths()[0]

    if confirm not in ("append", "replace"):
        existing = find_records_by_mine_date(act_path, mine, prod_date_iso)
        if not existing.empty:
            return _ok(
                {
                    "duplicate": True,
                    "existing": _row_dicts(existing),
                    "pending": _row_dicts(new_data)[0],
                    "fields": {
                        "mine": mine,
                        "prod_date": prod_date_iso,
                        "production": str(production),
                        "reporter": who,
                        "note": note,
                    },
                },
                message="该矿该日已有记录，请选择追加或覆盖",
            )

    if confirm == "replace":
        removed = safe_replace(act_path, mine, prod_date_iso, new_data)
        save_msg = f"已覆盖：删除旧记录 {removed} 条，写入新记录 1 条"
    else:
        safe_append(new_data, act_path)
        save_msg = "提交成功" if confirm != "append" else "已追加（保留旧记录）"

    if not verify_actual_submission_visible(act_path, mine, prod_date_iso, production):
        _log.error("actual 写入后校验失败 mine=%s date=%s prod=%s", mine, prod_date_iso, production)
        return _err(500, "保存后校验未通过：本次可能未成功保存，请重试或联系管理员")

    ok, msg = notify_submit_actual(
        mine=mine, prod_date=prod_date_iso, reporter=who, production=production, note=note
    )
    return _ok({"ok": True, "saved": save_msg}, message=(save_msg if ok else f"{save_msg}。{msg}"))


@router.post("/entry/energy/submit")
def submit_energy(request: Request, payload: dict = Body(...)) -> JSONResponse:
    ident = _require(request, (ADMIN_ROLE, REPORTER_ROLE))
    if not ident:
        return _denied(request)

    mine = str(payload.get("mine") or "").strip()
    prod_date = str(payload.get("prod_date") or "").strip()
    production = _to_float(payload.get("production"))
    sales = _to_float(payload.get("sales"))
    reporter = str(payload.get("reporter") or "").strip()
    note = str(payload.get("note") or "").strip()
    confirm = str(payload.get("confirm") or "").strip()

    if not mine:
        return _err(400, "请选择煤矿")
    try:
        pd_ = date.fromisoformat(prod_date)
    except (ValueError, TypeError):
        return _err(400, "日期无效")
    if (production == 0.0 or sales == 0.0) and not note:
        return _err(400, "产量或销量为 0 时须填备注")
    mapped_rep = ENERGY_REPORTER_MAP.get(mine, "")
    if ident["role"] != ADMIN_ROLE and not reporter and not mapped_rep:
        return _err(400, "请填写填报人")
    who = ADMIN_ROLE if ident["role"] == ADMIN_ROLE else (reporter or mapped_rep)
    prod_date_iso = pd_.strftime("%Y-%m-%d")

    new_data = dataframe_energy_reporting_new_row(
        report_time=now_str(),
        mine=mine,
        prod_date=prod_date_iso,
        production_t=production,
        sales_t=sales,
        reporter=who,
        note=note,
    )
    en_path = get_paths()[1]

    if confirm not in ("append", "replace"):
        existing = find_records_by_mine_date(en_path, mine, prod_date_iso)
        if not existing.empty:
            return _ok(
                {
                    "duplicate": True,
                    "existing": _row_dicts(existing),
                    "pending": _row_dicts(new_data)[0],
                    "fields": {
                        "mine": mine,
                        "prod_date": prod_date_iso,
                        "production": str(production),
                        "sales": str(sales),
                        "reporter": who,
                        "note": note,
                    },
                },
                message="该矿该日已有记录，请选择追加或覆盖",
            )

    if confirm == "replace":
        removed = safe_replace(en_path, mine, prod_date_iso, new_data)
        save_msg = f"已覆盖：删除旧记录 {removed} 条，写入新记录 1 条"
    else:
        safe_append(new_data, en_path)
        save_msg = "提交成功" if confirm != "append" else "已追加（保留旧记录）"

    if not verify_energy_submission_visible(en_path, mine, prod_date_iso, production, sales):
        _log.error("energy 写入后校验失败 mine=%s date=%s prod=%s sales=%s", mine, prod_date_iso, production, sales)
        return _err(500, "保存后校验未通过：本次可能未成功保存，请重试或联系管理员")

    ok, msg = notify_submit_energy(
        mine=mine, prod_date=prod_date_iso, reporter=who, production=production, sales=sales, note=note
    )
    return _ok({"ok": True, "saved": save_msg}, message=(save_msg if ok else f"{save_msg}。{msg}"))


@router.post("/entry/sales/submit")
def submit_sales(request: Request, payload: dict = Body(...)) -> JSONResponse:
    ident = _require(request, (ADMIN_ROLE, REPORTER_ROLE))
    if not ident:
        return _denied(request)

    mine = str(payload.get("mine") or "").strip()
    week_end = str(payload.get("week_end") or "").strip()
    sales = _to_float(payload.get("sales"))
    reporter = str(payload.get("reporter") or "").strip()
    note = str(payload.get("note") or "").strip()
    confirm = str(payload.get("confirm") or "").strip()
    blended_f = _to_float(payload.get("year_blended"))
    purchased_f = _to_float(payload.get("year_purchased"))

    if not mine:
        if blended_f == 0.0 and purchased_f == 0.0:
            return _err(400, "请选择煤矿，或填写年累计掺配煤销量/外购煤量")
    try:
        we_dt = date.fromisoformat(week_end)
    except (ValueError, TypeError):
        return _err(400, "周末日期无效")
    ws_dt, we_dt = get_weekly_range(we_dt)
    week_start_iso = ws_dt.strftime("%Y-%m-%d")
    week_end_iso = we_dt.strftime("%Y-%m-%d")
    if mine:
        if sales == 0.0 and not note:
            return _err(400, "销量为 0 时须填备注")
    else:
        sales = 0.0
    who = reporter or ADMIN_ROLE

    sales_path = get_settings().actual_sales_path

    # I/J 为 0 或空时，沿用最近一期"合计"记录的值（仅在选择煤矿时）
    if mine and (blended_f == 0.0 or purchased_f == 0.0):
        _existing_df = read_records(sales_path)
        if _existing_df is not None and not _existing_df.empty:
            _existing_df = _existing_df.copy()
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

    if mine:
        new_data = dataframe_actual_sales_new_row(
            submit_time=now_str(),
            mine=mine,
            week_start=week_start_iso,
            week_end=week_end_iso,
            sales_t=sales,
            reporter=who,
            note=note,
            year_blended=blended_f,
            year_purchased=purchased_f,
        )

        if confirm not in ("append", "replace"):
            existing = find_sales_records_by_mine_week(
                sales_path, mine, week_start_iso, week_end_iso
            )
            if not existing.empty:
                return _ok(
                    {
                        "duplicate": True,
                        "existing": _row_dicts(existing),
                        "pending": _row_dicts(new_data)[0],
                        "fields": {
                            "mine": mine,
                            "week_end": week_end_iso,
                            "sales": str(sales),
                            "reporter": who,
                            "note": note,
                            "year_blended": str(blended_f),
                            "year_purchased": str(purchased_f),
                        },
                    },
                    message="该矿该周已有记录，请选择追加或覆盖",
                )

        if confirm == "replace":
            removed = safe_replace_sales(sales_path, mine, week_start_iso, week_end_iso, new_data)
            save_msg = f"已覆盖：删除旧记录 {removed} 条，写入新记录 1 条"
        else:
            safe_append(new_data, sales_path)
            save_msg = "提交成功" if confirm != "append" else "已追加（保留旧记录）"

        if not verify_sales_submission_visible(
            sales_path, mine, week_start_iso, week_end_iso, sales
        ):
            _log.error(
                "sales 写入后校验失败 mine=%s week=%s~%s sales=%s",
                mine, week_start_iso, week_end_iso, sales,
            )
            return _err(500, "保存后校验未通过：本次可能未成功保存，请重试或联系管理员")
    else:
        save_msg = "年累计掺配煤销量/外购煤量已更新"

    # 同步更新/创建"合计"记录的 I/J 值（确保简报和周报表能取到当前周累计值）
    _totals_lock = FileLock(sales_path + ".lock")
    with _totals_lock:
        _df = read_records(sales_path)
        if _df is not None and not _df.empty:
            _df = _df.copy()
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

    ok, msg = notify_submit_sales(
        mine=mine,
        week_range=f"{week_start_iso} 至 {week_end_iso}",
        reporter=who,
        sales=sales,
        year_blended=blended_f,
        year_purchased=purchased_f,
        note=note,
    )
    return _ok({"ok": True, "saved": save_msg}, message=(save_msg if ok else f"{save_msg}。{msg}"))


@router.get("/ledger")
def ledger(
    request: Request,
    kind: str = "all",
    mine: str = "",
    start: str = "",
    end: str = "",
    limit: int = 1000,
) -> JSONResponse:
    ident = _require(request)
    if not ident:
        return _denied(request)

    keys = [kind] if kind in LEDGER_PATH else list(LEDGER_PATH)
    out: list[dict] = []
    for k in keys:
        raw = read_records(LEDGER_PATH[k]())
        df = exclude_mines(raw) if raw is not None and not raw.empty else raw
        if df is None or df.empty:
            continue
        df = reorder_ledger_dataframe_for_table(LEDGER_TABLE[k], df)
        if mine:
            df = df[df["所属煤矿"].astype(str).str.strip() == mine]
        date_col = "生产日期" if k in ("actual", "energy") else "周起始日期"
        if start:
            df = df[df[date_col].astype(str) >= start]
        if end:
            df = df[df[date_col].astype(str) <= end]
        for idx, row in df.iterrows():
            rec = {col: _clean_value(row[col]) for col in df.columns}
            rec["_kind"] = k
            rec["_orig_idx"] = int(idx)
            out.append(rec)

    out.sort(
        key=lambda r: str(r.get("生产日期") or r.get("周起始日期") or ""),
        reverse=True,
    )
    return _ok(out[:limit])


@router.post("/ledger/save")
def ledger_save(request: Request, payload: dict = Body(...)) -> JSONResponse:
    """管理员保存台账编辑：按 kind 整表覆盖（更新/删除），与旧版 /admin/ledger/save 同语义。"""
    ident = _require(request, (ADMIN_ROLE,))
    if not ident:
        return _denied(request)
    kind = str(payload.get("kind") or "").strip()
    if kind not in LEDGER_PATH:
        return _err(400, "未知台账类型 kind，支持 actual / energy / sales")
    updates = payload.get("updates") or []
    deleted = payload.get("deleted") or []
    p = LEDGER_PATH[kind]()
    raw = read_records(p)
    df_full = exclude_mines(raw) if raw is not None and not raw.empty else raw
    if df_full is None or df_full.empty:
        return _err(400, "无数据可保存")
    full_index_set = set(df_full.index.tolist())
    deleted_indices: set[int] = set()
    for d in deleted:
        try:
            idx = int(d)
        except (TypeError, ValueError):
            continue
        if idx in full_index_set:
            deleted_indices.add(idx)
    updated_idx_map: dict[int, dict] = {}
    for u in updates:
        try:
            idx = int(u.get("orig_idx"))
        except (TypeError, ValueError):
            continue
        if idx not in full_index_set or idx in deleted_indices:
            continue
        vals = u.get("values") or {}
        row: dict = {}
        for col in df_full.columns:
            if col in vals:
                row[col] = coerce_ledger_value(col, str(vals[col]))
            else:
                row[col] = df_full.loc[idx, col]
        updated_idx_map[idx] = row
    result_rows: list[dict] = []
    for idx in df_full.index:
        if idx in deleted_indices:
            continue
        if idx in updated_idx_map:
            result_rows.append(updated_idx_map[idx])
        else:
            result_rows.append(df_full.loc[idx].to_dict())
    if not result_rows:
        new_df = pd.DataFrame(columns=df_full.columns)
    else:
        new_df = pd.DataFrame(result_rows)
        for c in df_full.columns:
            if c not in new_df.columns:
                new_df[c] = None
        new_df = new_df[[c for c in df_full.columns]]
    excluded_rows = pd.DataFrame()
    if raw is not None and not raw.empty and "所属煤矿" in raw.columns:
        excl_mask = raw["所属煤矿"].astype(str).str.contains(
            "|".join(REMOVED_MINE_KEYWORDS), na=False
        )
        excluded_rows = raw.loc[excl_mask].copy()
    if not excluded_rows.empty:
        for c in new_df.columns:
            if c not in excluded_rows.columns:
                excluded_rows[c] = None
        save_df = pd.concat([new_df, excluded_rows[new_df.columns]], ignore_index=True)
    else:
        save_df = new_df
    safe_overwrite(save_df, p)
    return _ok({"saved": len(result_rows)}, message=f"已保存，当前共 {len(result_rows)} 行")


@router.get("/stats")
def stats(
    request: Request,
    period: str = "year",
    start: str = "",
    end: str = "",
    stat_year: str = "",
    stat_month: str = "",
) -> JSONResponse:
    ident = _require(request, (ADMIN_ROLE, VIEWER_ROLE))
    if not ident:
        return _denied(request)
    c_start = c_end = None
    if period == "custom" and start and end:
        try:
            c_start = date.fromisoformat(start)
            c_end = date.fromisoformat(end)
        except ValueError:
            pass
    sy = int(stat_year) if stat_year.isdigit() else None
    sm = stat_month if stat_month and len(stat_month) == 7 else None
    try:
        data = build_viz_data(
            period=period,
            custom_start=c_start,
            custom_end=c_end,
            stat_year=sy,
            stat_month=sm,
        )
        return _ok(data)
    except Exception as exc:
        _log.warning("ccx.stats failed: %s", exc)
        return _err(500, str(exc))


@router.post("/report/generate")
def report_generate(request: Request, payload: dict = Body(...)) -> JSONResponse:
    ident = _require(request, (ADMIN_ROLE, VIEWER_ROLE))
    if not ident:
        return _denied(request)
    kind = str(payload.get("kind") or "").strip()
    target_date = str(payload.get("target_date") or "").strip()
    start = str(payload.get("start") or "").strip()
    end = str(payload.get("end") or "").strip()

    if kind == "sjcl":
        out, msg = generate_sjcl_report(target_date)
    elif kind == "nybb":
        out, msg = generate_nybb_report(target_date)
    elif kind == "weekly":
        out, msg = generate_weekly_report(start, end)
    else:
        return _err(400, "未知报表类型 kind，支持 sjcl / nybb / weekly")

    if not out:
        return _err(400, msg or "生成失败")
    name = os.path.basename(out)
    return _ok(
        {"file": name, "download_url": f"/api/ccx/report/download?f={quote(name)}"},
        message=msg or "已生成",
    )


@router.get("/report/download", response_model=None)
def report_download(request: Request, f: str = "") -> FileResponse | JSONResponse:
    ident = _require(request, (ADMIN_ROLE, VIEWER_ROLE))
    if not ident:
        return _denied(request)
    base = (get_settings().data_dir / "exports").resolve()
    p = (base / os.path.basename(f)).resolve()
    if not p.is_file():
        return _err(404, "文件不存在")
    try:
        p.relative_to(base)
    except ValueError:
        return _err(404, "文件不存在")
    return FileResponse(
        str(p),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=p.name,
    )
# ============================================================
# 导出 / 状态 / 元数据 接口（供 aq 前端合并使用）
# ============================================================

@router.get("/export/viz", response_model=None)
def ccx_export_viz(
    request: Request,
    period: str = "year",
    start: str = "",
    end: str = "",
    stat_year: str = "",
    stat_month: str = "",
) -> Any:
    ident = _require(request, (ADMIN_ROLE, VIEWER_ROLE))
    if not ident:
        return _denied(request)
    c_start = c_end = None
    if period == "custom" and start and end:
        try:
            c_start = date.fromisoformat(start)
            c_end = date.fromisoformat(end)
        except ValueError:
            period = "year"
    sy_int = int(stat_year) if stat_year.isdigit() else None
    sm_str = stat_month if re.fullmatch(r"\d{4}-\d{2}", stat_month) else None
    try:
        blob, ascii_n, utf_n = export_viz_excel(
            period=period,
            custom_start=c_start,
            custom_end=c_end,
            stat_year=sy_int,
            stat_month=sm_str,
        )
    except Exception as exc:
        _log.warning("ccx.viz.export failed: %s", exc)
        return _err(400, f"导出失败：{exc}")
    cd = content_disposition_attachment(str(ascii_n), str(utf_n))
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": cd, "Cache-Control": "no-store"},
    )


@router.get("/export/ledger", response_model=None)
def ccx_export_ledger(request: Request, kind: str = "all") -> Response:
    ident = _require(request)
    if not ident:
        return _denied(request)
    keys = [kind] if kind in LEDGER_PATH else list(LEDGER_PATH)
    frames: list[pd.DataFrame] = []
    for k in keys:
        df = read_records(LEDGER_PATH[k]())
        if df is None or df.empty:
            continue
        df = reorder_ledger_dataframe_for_table(LEDGER_TABLE[k], df)
        df["_kind"] = k
        frames.append(df)
    if not frames:
        return _err(400, "暂无数据")
    out_df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    buf = StringIO()
    out_df.to_csv(buf, index=False, encoding="utf-8-sig")
    name = "ccx_ledger.csv"
    return Response(
        content=buf.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/ledger/mine-status")
def ccx_ledger_mine_status(request: Request) -> JSONResponse:
    ident = _require(request)
    if not ident:
        return _denied(request)
    today_str = today_beijing().isoformat()
    time_col = {"actual": "提交时间", "energy": "报送时间", "sales": "填报时间"}
    out: dict[str, dict[str, bool]] = {}
    for k in LEDGER_PATH:
        df = read_records(LEDGER_PATH[k]())
        mine_map: dict[str, bool] = {}
        for mine_name in MINE_LIST:
            submitted = False
            if df is not None and not df.empty and "所属煤矿" in df.columns and time_col[k] in df.columns:
                mine_rows = df[df["所属煤矿"].astype(str).str.strip() == mine_name]
                submitted = bool(mine_rows[time_col[k]].astype(str).str.startswith(today_str).any())
            mine_map[mine_name] = submitted
        out[k] = mine_map
    return _ok(out)


@router.get("/entry/meta")
def ccx_entry_meta(request: Request) -> JSONResponse:
    ident = _require(request)
    if not ident:
        return _denied(request)
    try:
        plans = read_sjcl_v2_daily_plans_from_template(get_settings().sjcl_template_v2)
    except Exception:
        plans = {}
    return _ok(
        {
            "mines": MINE_LIST,
            "actual_reporter_map": ACTUAL_REPORTER_MAP,
            "energy_reporter_map": ENERGY_REPORTER_MAP,
            "actual_daily_plan_map": plans,
        }
    )


@router.get("/report/brief")
def ccx_report_brief(request: Request, start: str = "", end: str = "") -> JSONResponse:
    ident = _require(request, (ADMIN_ROLE,))
    if not ident:
        return _denied(request)
    if not start or not end:
        return _err(400, "请提供 start 与 end")
    brief_text, msg = generate_brief_report(start, end)
    if not brief_text:
        return _err(400, msg or "生成失败")
    return _ok({"brief": brief_text}, message=msg or "已生成")