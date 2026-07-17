# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
"""可视化数据 API 与导出路由。"""

from __future__ import annotations

import logging
import re
from datetime import date
from io import StringIO
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from app.config import get_settings
from app.helpers import get_paths
from app.storage import read_records, storage_uses_database
from app.timeutil import today_beijing
from app.utils import content_disposition_attachment, exclude_mines
from app.viz_engine import build_viz_data, export_viz_excel

router = APIRouter()


@router.get("/api/viz/data")
def viz_data(
    request: Request,
    period: str = "year",
    start: str = "",
    end: str = "",
    stat_year: str = "",
    stat_month: str = "",
) -> JSONResponse:
    if not request.session.get("role"):
        return JSONResponse({"error": "未登录"}, status_code=401)
    today_cap = today_beijing()
    c_start = c_end = None
    if period == "custom" and start and end:
        try:
            c_start = date.fromisoformat(start)
            c_end = date.fromisoformat(end)
            if c_start > today_cap:
                c_start = today_cap
            if c_end > today_cap:
                c_end = today_cap
            if c_start > c_end:
                c_start, c_end = c_end, c_start
        except ValueError:
            period = "year"
    sy_int = int(stat_year) if stat_year.isdigit() else None
    sm_str = stat_month if re.fullmatch(r"\d{4}-\d{2}", stat_month) else None
    try:
        data = build_viz_data(
            period=period,
            custom_start=c_start,
            custom_end=c_end,
            stat_year=sy_int,
            stat_month=sm_str,
        )
        return JSONResponse(data)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/export/viz-data.xlsx")
def export_viz_data(
    request: Request,
    period: str = "year",
    start: str = "",
    end: str = "",
    stat_year: str = "",
    stat_month: str = "",
) -> Any:
    role = request.session.get("role")
    if role not in ("管理员", "产量数据可视化"):
        return RedirectResponse("/login", status_code=303)
    today_cap = today_beijing()
    c_start = c_end = None
    if period == "custom" and start and end:
        try:
            c_start = date.fromisoformat(start)
            c_end = date.fromisoformat(end)
            if c_start > today_cap:
                c_start = today_cap
            if c_end > today_cap:
                c_end = today_cap
            if c_start > c_end:
                c_start, c_end = c_end, c_start
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
        msg = str(exc)
        logging.getLogger(__name__).warning("viz.export.failed role=%s err=%s", role, msg)
        err_ascii = "ymky_viz_export_error.txt"
        disp_err = (
            f'attachment; filename="{err_ascii}"; '
            f"filename*=UTF-8''{quote('云煤矿业_导出失败说明.txt')}"
        )
        return Response(
            content=msg.encode("utf-8"),
            status_code=400,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": disp_err, "Cache-Control": "no-store"},
        )
    cd = content_disposition_attachment(str(ascii_n), str(utf_n))
    return Response(
        content=blob,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": cd},
    )


@router.get("/export/history")
def export_history(request: Request) -> Response:
    role = request.session.get("role")
    if role not in ("填报人员", "管理员"):
        return Response(status_code=401)
    act_path, en_path = get_paths()
    is_actual = role == "填报人员" and (request.session.get("reporter_kind") or "") == "实际产量填报"
    p = act_path if is_actual else en_path
    df = exclude_mines(read_records(p))
    if df.empty:
        return Response("暂无数据", media_type="text/plain; charset=utf-8", status_code=400)
    df = df.sort_index(ascending=False)
    buf = StringIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    name = "actual_history.csv" if is_actual else "energy_history.csv"
    return Response(
        content=buf.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
