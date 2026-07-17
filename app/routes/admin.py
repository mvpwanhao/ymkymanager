# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
"""管理员后台路由（台账编辑保存、密码管理）。"""

from __future__ import annotations

import logging

import pandas as pd
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import save_password_updates
from app.config import get_settings
from app.constants import MINE_LIST
from app.helpers import coerce_ledger_value, get_paths, nav_and_page, safe_overwrite
from app.storage import read_records, storage_uses_database
from app.utils import exclude_mines

router = APIRouter()


@router.post("/admin/ledger/save")
async def admin_ledger_save(request: Request) -> RedirectResponse:
    if request.session.get("role") != "管理员":
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    form_type = str(form.get("form_type", "actual"))
    s = get_settings()
    act_path, en_path = get_paths()
    if form_type == "actual":
        p = act_path
    elif form_type == "sales":
        p = s.actual_sales_path
    else:
        p = en_path
    raw = read_records(p)
    df_full = exclude_mines(raw) if not raw.empty else raw
    if df_full.empty:
        request.session["flash"] = "无数据可保存"
        return RedirectResponse("/go/admin_ledger", status_code=303)
    cols = [str(c) for c in df_full.columns]
    nrows = int(str(form.get("nrows", "0")))

    # ── 收集表单中可见行的变更（更新/删除）────
    updated_rows: list[tuple[int, dict]] = []
    deleted_indices: set[int] = set()
    full_index_set = set(df_full.index.tolist())
    for i in range(nrows):
        orig_idx_str = str(form.get(f"orig_idx_{i}", ""))
        if not orig_idx_str.lstrip("-").isdigit():
            continue
        orig_idx = int(orig_idx_str)
        if orig_idx not in full_index_set:
            continue
        if str(form.get(f"del_{i}")) == "1":
            deleted_indices.add(orig_idx)
            continue
        row: dict = {}
        for j, col in enumerate(cols):
            key = f"c_{i}_{j}"
            val = form.get(key)
            row[col] = coerce_ledger_value(col, str(val) if val is not None else "")
        updated_rows.append((orig_idx, row))

    # ── 合并：保留未出现在表单中的行 + 更新后的行 ──
    updated_idx_set = {r[0] for r in updated_rows}
    result_rows: list[dict] = []
    for idx in df_full.index:
        if idx in deleted_indices:
            continue
        if idx in updated_idx_set:
            for orig_idx, row_dict in updated_rows:
                if orig_idx == idx:
                    result_rows.append(row_dict)
                    break
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
    if not raw.empty and "所属煤矿" in raw.columns:
        from app.constants import REMOVED_MINE_KEYWORDS
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

    ymky_log = logging.getLogger("ymky")
    ymky_log.info(
        "admin_ledger_save table=%s visible=%d excluded=%d total=%d",
        form_type, len(new_df), len(excluded_rows), len(save_df),
    )
    safe_overwrite(save_df, p)
    request.session["flash"] = f"已保存，当前共 {len(new_df)} 行"
    request.session["active_section"] = "admin_ledger"
    request.session["ledger_t"] = form_type
    return RedirectResponse("/", status_code=303)


@router.post("/admin/passwords")
def admin_passwords(
    request: Request,
    action: str = Form(""),
    cur_adm: str = Form(""),
    new_adm: str = Form(""),
    new_adm2: str = Form(""),
    adm_r: str = Form(""),
    new_r: str = Form(""),
    new_r2: str = Form(""),
    adm_v: str = Form(""),
    new_v: str = Form(""),
    new_v2: str = Form(""),
) -> HTMLResponse:
    templates = request.app.state.templates
    if request.session.get("role") != "管理员":
        return HTMLResponse("未授权", status_code=401)  # type: ignore[return-value]
    msg = ""
    ok: bool | None = None
    if action == "admin":
        if new_adm != new_adm2:
            msg = "两次新密码不一致"
        else:
            ok, msg = save_password_updates({"admin": new_adm}, cur_adm)
    elif action == "reporter":
        if new_r != new_r2:
            msg = "两次新密码不一致"
        else:
            ok, msg = save_password_updates({"reporter": new_r}, adm_r)
    elif action == "viewer":
        if new_v != new_v2:
            msg = "两次新密码不一致"
        else:
            ok, msg = save_password_updates({"viewer": new_v}, adm_v)
    nav, _p = nav_and_page("管理员", None, request.session)
    return templates.TemplateResponse(
        request,
        "passwords.html",
        {
            "role": "管理员",
            "reporter_kind": None,
            "nav": nav,
            "page": "passwords",
            "storage_db": storage_uses_database(),
            "form_error": None,
            "flash": None,
            "actual_reporter_map": {},
            "energy_reporter_map": {},
            "msg": msg,
            "ok": ok,
        },
    )
