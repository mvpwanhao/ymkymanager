# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
"""报表生成与下载路由。"""

from __future__ import annotations

import os
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import FileResponse, RedirectResponse, Response

from app.config import get_settings
from app.report_engine import (
    generate_brief_report,
    generate_nybb_report,
    generate_sjcl_report,
    generate_weekly_report,
)

router = APIRouter()


@router.post("/reports/sjcl", response_model=None)
def report_sjcl(
    request: Request,
    target_date: str = Form(...),
) -> FileResponse | RedirectResponse:
    if request.session.get("role") != "管理员":
        return RedirectResponse("/login", status_code=303)
    out, msg = generate_sjcl_report(target_date)
    if not out or not os.path.isfile(out):
        request.session["flash"] = msg or "生成失败"
        return RedirectResponse("/go/reports", status_code=303)
    request.session["flash"] = msg or "已生成，开始下载"
    q = urlencode({"f": os.path.basename(out)})
    return RedirectResponse(f"/reports/download?{q}", status_code=303)


@router.post("/reports/nybb", response_model=None)
def report_nybb(
    request: Request,
    target_date: str = Form(...),
) -> FileResponse | RedirectResponse:
    if request.session.get("role") != "管理员":
        return RedirectResponse("/login", status_code=303)
    out, msg = generate_nybb_report(target_date)
    if not out or not os.path.isfile(out):
        request.session["flash"] = msg or "生成失败"
        return RedirectResponse("/go/reports", status_code=303)
    request.session["flash"] = msg or "已生成，开始下载"
    q = urlencode({"f": os.path.basename(out)})
    return RedirectResponse(f"/reports/download?{q}", status_code=303)


@router.post("/reports/weekly", response_model=None)
def report_weekly(
    request: Request,
    start_date: str = Form(...),
    end_date: str = Form(...),
) -> FileResponse | RedirectResponse:
    if request.session.get("role") != "管理员":
        return RedirectResponse("/login", status_code=303)
    out, msg = generate_weekly_report(start_date, end_date)
    if not out or not os.path.isfile(out):
        request.session["flash"] = msg or "生成失败"
        return RedirectResponse("/go/reports", status_code=303)
    request.session["flash"] = msg or "已生成，开始下载"
    q = urlencode({"f": os.path.basename(out)})
    return RedirectResponse(f"/reports/download?{q}", status_code=303)


@router.post("/reports/brief", response_model=None)
def report_brief(
    request: Request,
    start_date: str = Form(...),
    end_date: str = Form(...),
) -> RedirectResponse:
    if request.session.get("role") != "管理员":
        return RedirectResponse("/login", status_code=303)
    brief_text, msg = generate_brief_report(start_date, end_date)
    if not brief_text:
        request.session["flash"] = msg or "生成失败"
        return RedirectResponse("/go/reports", status_code=303)
    request.session["brief_text"] = brief_text
    request.session["flash"] = msg or "产销量简报已生成"
    return RedirectResponse("/go/reports", status_code=303)



@router.post("/reports/weekly-and-brief", response_model=None)
def report_weekly_and_brief(
    request: Request,
    start_date: str = Form(...),
    end_date: str = Form(...),
) -> RedirectResponse:
    """同时生成周报表（Excel 下载）和产销量简报（文本展示）。"""
    if request.session.get("role") != "管理员":
        return RedirectResponse("/login", status_code=303)

    # 生成周报表
    out, weekly_msg = generate_weekly_report(start_date, end_date)
    if not out or not os.path.isfile(out):
        request.session["flash"] = weekly_msg or "周报表生成失败"
        return RedirectResponse("/go/reports", status_code=303)

    # 生成简报
    brief_text, brief_msg = generate_brief_report(start_date, end_date)
    if brief_text:
        request.session["brief_text"] = brief_text
    request.session["weekly_download_file"] = os.path.basename(out)
    request.session["flash"] = "周报表和产销量简报已生成"
    return RedirectResponse("/go/reports", status_code=303)

@router.get("/reports/download", response_model=None)
def report_download(
    request: Request,
    f: str = "",
) -> FileResponse | Response:
    if request.session.get("role") != "管理员":
        return Response(status_code=401)
    base = (get_settings().data_dir / "exports").resolve()
    p = (base / os.path.basename(f)).resolve()
    if not p.is_file():
        return Response(status_code=404)
    try:
        p.relative_to(base)
    except ValueError:
        return Response(status_code=404)
    return FileResponse(
        str(p),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=p.name,
    )
