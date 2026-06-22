# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
# 本文件为「云煤矿业产销量管理系统」的组成部分。
# 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
# 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE。
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import re
from markupsafe import Markup
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from io import StringIO
from typing import Any
from urllib.parse import quote, urlencode

import pandas as pd
from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from filelock import FileLock
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.auth import (
    check_role_password,
    create_login_token,
    debug_prefill_for_role,
    get_login_by_token,
    has_configured_passwords,
    revoke_token,
    save_password_updates,
    should_debug_prefill,
)
from app.config import get_settings
from app.middleware_production import SecurityHeadersMiddleware, StaticCacheMiddleware
from app.constants import ACTUAL_REPORTER_MAP, ENERGY_REPORTER_MAP, MINE_LIST
from app.dashboard_data import build_summary_and_charts, exclude_mines
from app.visual_export import content_disposition_attachment, try_visual_export_bytes
from app.release_version import health_version
from app.report_engine import (
    generate_nybb_report,
    generate_sjcl_report,
    read_sjcl_v2_daily_plans_from_template,
)
from app.services.notify import notify_alert, notify_startup
from app.storage import (
    append_records,
    dataframe_actual_production_new_row,
    dataframe_energy_reporting_new_row,
    find_records_by_mine_date,
    has_pending_sync,
    overwrite_records,
    read_records,
    replace_records_for_mine_date,
    storage_uses_database,
    verify_actual_submission_visible,
    verify_energy_submission_visible,
)
from app.timeutil import format_series_as_beijing_display, now_str, today_beijing


def _df_to_html_table(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    return df.to_html(index=False, classes="data-table", border=0, escape=True)


def _coerce_ledger_value(col: str, raw: str) -> Any:
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
        return s
    return s


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


LOG_FILE = get_settings().data_dir / "ymky_system.log"


def _configure_runtime_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)
    root.setLevel(logging.INFO)

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)


_DEFAULT_SECRET_MARKER = "dev-change-me-please-use-yml-or-env-YMKY_SECRET_KEY"


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_runtime_logging()
    s = get_settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    s.runtime_dir.mkdir(parents=True, exist_ok=True)
    (s.data_dir / "exports").mkdir(exist_ok=True)
    if s.database_url.strip():
        os.environ["DATABASE_URL"] = s.database_url.strip()
    log = logging.getLogger("ymky")
    if s.is_production and _DEFAULT_SECRET_MARKER in s.secret_key:
        log.warning(
            "YMKY_ENV=production 但会话密钥仍为开发默认值，请在 .env 中设置强随机 YMKY_SECRET_KEY 后再对公网开放访问。"
        )
    if s.is_production and s.local_debug_password_autofill:
        log.warning("YMKY_ENV=production 但 YMKY_LOCAL_DEBUG 已开启，生产环境请关闭。")
    # ?? ??????????? Server? ??????
    if s.is_production:
        from app.release_version import read_version_from_file
        v = s.app_version.strip() or read_version_from_file()
        ok, msg = notify_startup(success=True, version=v)
        if ok:
            log.info("???????")
        else:
            log.warning("????????%s", msg)
    yield


def _nav_and_page(role: str, reporter_kind: str | None, session: dict) -> tuple[list[dict], str]:  # type: ignore[type-arg]
    if role == "管理员":
        nav = [
            {"id": "visual", "label": "数据可视化", "path": "/go/visual", "group": "数据查看"},
            {"id": "admin_ledger", "label": "历史台账", "path": "/go/admin_ledger", "group": "数据查看"},
            {"id": "entry_actual", "label": "实际产量填报", "path": "/go/entry_actual", "group": "填报"},
            {"id": "entry_energy", "label": "能源局产销量填报", "path": "/go/entry_energy", "group": "填报"},
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


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="云南云煤矿业开发有限公司 · 产销量管理系统",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=s.secret_key,
        max_age=s.session_ttl_seconds,
        same_site="lax",
    )
    app.add_middleware(GZipMiddleware, minimum_size=800)
    app.add_middleware(StaticCacheMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    if s.trusted_host_list:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=s.trusted_host_list)

    base = s.base_dir
    templates = Jinja2Templates(directory=str(base / "templates"))
    templates.env.filters["tojson"] = lambda v: Markup(
        json.dumps(v, ensure_ascii=False)
    )

    def _compute_asset_version() -> str:
        import hashlib
        h = hashlib.sha1()
        for rel in ("static/app.css", "static/app.js", "static/plotly-theme.js"):
            p = base / rel
            try:
                h.update(str(p.stat().st_mtime_ns).encode())
            except OSError:
                continue
        return h.hexdigest()[:10] or "dev"

    templates.env.globals["asset_version"] = _compute_asset_version()

    def get_paths():
        s2 = get_settings()
        return s2.actual_production_path, s2.energy_reporting_path

    def _safe_append(df: pd.DataFrame, file_path: str) -> None:
        lock = FileLock(file_path + ".lock")
        with lock:
            append_records(file_path, df)

    def _safe_overwrite(df: pd.DataFrame, file_path: str) -> None:
        lock = FileLock(file_path + ".lock")
        with lock:
            overwrite_records(file_path, df)

    def _safe_replace(file_path: str, mine: str, prod_date_iso: str, df_new: pd.DataFrame) -> int:
        lock = FileLock(file_path + ".lock")
        with lock:
            return replace_records_for_mine_date(file_path, mine, prod_date_iso, df_new)

    def _render_duplicate_confirmation(
        request: Request,
        *,
        kind: str,
        mine: str,
        prod_date_iso: str,
        existing_df: pd.DataFrame,
        pending_df: pd.DataFrame,
        form_fields: dict[str, str],
    ) -> Any:
        ex = existing_df.copy()
        for c in ("提交时间", "报送时间"):
            if c in ex.columns:
                ex[c] = format_series_as_beijing_display(ex[c])
        kind_label = "实际产量" if kind == "actual" else "能源局产销量"
        submit_path = "/entry/actual/submit" if kind == "actual" else "/entry/energy/submit"
        role_str = str(request.session.get("role") or "")
        nav, _session_page = _nav_and_page(role_str, request.session.get("reporter_kind"), request.session)
        page_here = "entry_actual" if kind == "actual" else "entry_energy"
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
                "existing_html": _df_to_html_table(ex),
                "pending_html": _df_to_html_table(pending_df),
                "form_fields": form_fields,
                "submit_path": submit_path,
            },
        )

    @app.get("/health")
    def health() -> JSONResponse:
        s2 = get_settings()
        body: dict[str, object] = {"ok": True, "db": storage_uses_database()}
        v = health_version(s2.app_version or "")
        if v:
            body["version"] = v
        return JSONResponse(
            body,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
        )

    @app.get("/health/diag")
    def health_diag() -> JSONResponse:
        """诊断端点：返回各表记录数与日期范围，用于排查数据丢失问题。"""
        s2 = get_settings()
        diag: dict[str, object] = {
            "db_connected": storage_uses_database(),
            "pending_sync": has_pending_sync(),
        }
        for label, path in [("actual", s2.actual_production_path), ("energy", s2.energy_reporting_path)]:
            try:
                df = read_records(path)
                info: dict[str, object] = {"rows": len(df)}
                if not df.empty and "生产日期" in df.columns:
                    dates = pd.to_datetime(df["生产日期"], errors="coerce").dropna()
                    if not dates.empty:
                        info["date_min"] = str(dates.min().date())
                        info["date_max"] = str(dates.max().date())
                diag[label] = info
            except Exception as exc:
                diag[label] = {"error": str(exc)}
        return JSONResponse(
            diag,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
        )

    @app.get("/login", response_class=HTMLResponse)
    def login_get(request: Request) -> Any:
        if request.session.get("role"):
            return RedirectResponse("/", status_code=303)
        if not has_configured_passwords():
            return templates.TemplateResponse(
                request,
                "message.html",
                {
                    "title": "暂未配置登录密码",
                    "message": "系统尚未设置任何登录密码，请联系管理员处理。",
                },
            )
        prefill = ""
        if should_debug_prefill() and request.session.get("login_temp_role"):
            prefill = debug_prefill_for_role(str(request.session["login_temp_role"]))
        le = request.session.pop("login_error", None)
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "step": "identity" if not request.session.get("login_temp_role") else "password",
                "temp_role": request.session.get("login_temp_role"),
                "debug_prefill": prefill,
                "login_error": le,
            },
        )

    @app.post("/login/identity")
    def login_identity(
        request: Request,
        role: str = Form(...),
    ) -> RedirectResponse:
        if role in ("填报人员", "管理员", "产量数据可视化"):
            request.session["login_temp_role"] = role
        return RedirectResponse("/login", status_code=303)

    @app.get("/login/reset")
    def login_reset(request: Request) -> RedirectResponse:
        # Clear temporary role/password step so user can re-pick identity.
        request.session["login_temp_role"] = None
        request.session["login_error"] = None
        return RedirectResponse("/login", status_code=303)

    @app.post("/login/verify")
    def login_verify(
        request: Request,
        password: str = Form(""),
    ) -> RedirectResponse:
        tr = request.session.get("login_temp_role")
        if not tr or not str(password).strip():
            return RedirectResponse("/login", status_code=303)
        if not check_role_password(str(password), tr):
            request.session["login_error"] = "密码错误，请重试"
            return RedirectResponse("/login", status_code=303)
        if tr == "填报人员":
            request.session["reporter_pick_pending"] = True
            request.session["login_temp_role"] = None
            return RedirectResponse("/reporter/choose", status_code=303)
        request.session["role"] = tr
        tok = create_login_token(role=tr, reporter_kind=None)
        request.session["auth_token"] = tok
        request.session["login_temp_role"] = None
        return RedirectResponse("/", status_code=303)

    @app.get("/reporter/choose", response_class=HTMLResponse)
    def reporter_choose(request: Request) -> Any:
        if not request.session.get("reporter_pick_pending"):
            return RedirectResponse("/login", status_code=303)
        return templates.TemplateResponse(request, "reporter_choose.html", {})

    @app.post("/reporter/confirm")
    def reporter_confirm(
        request: Request,
        kind: str = Form(...),
    ) -> RedirectResponse:
        if not request.session.get("reporter_pick_pending"):
            return RedirectResponse("/login", status_code=303)
        if kind not in ("actual", "nybb"):
            return RedirectResponse("/reporter/choose", status_code=303)
        rk = "实际产量填报" if kind == "actual" else "能源局口径产销量填报"
        request.session["role"] = "填报人员"
        request.session["reporter_kind"] = rk
        request.session["reporter_pick_pending"] = None
        tok = create_login_token(role="填报人员", reporter_kind=rk)
        request.session["auth_token"] = tok
        return RedirectResponse("/", status_code=303)

    @app.get("/logout")
    def logout(request: Request) -> RedirectResponse:
        tok = request.session.get("auth_token")
        if tok:
            revoke_token(str(tok))
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    @app.get("/export/history")
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

    @app.get("/export/visual-production.xlsx")
    def export_visual_production(request: Request) -> Any:
        role = request.session.get("role")
        if role not in ("管理员", "产量数据可视化"):
            return RedirectResponse("/login", status_code=303)
        blob, ascii_n, utf_n, err = try_visual_export_bytes(request)
        if err or not blob:
            msg = err or "导出失败。"
            # 带 download 的请求若仅以 URL 存盘，会为 .xlsx 名塞入正文或 HTML→Excel 报「格式无效」；附 .txt 的 Content-Disposition 降低误保存。
            request.session["flash"] = msg
            logging.getLogger(__name__).warning("visual.export.failed role=%s err=%s", role, msg)
            err_ascii = "ymky_visual_export_error.txt"
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

    @app.get("/go/{section}")
    def go(request: Request, section: str) -> RedirectResponse:
        request.session["active_section"] = section
        p = request.query_params.get("period")
        t = request.query_params.get("t", "")
        if section == "visual" and p:
            return RedirectResponse(f"/?period={p}", status_code=303)
        if section == "admin_ledger" and t in ("actual", "nybb"):
            request.session["ledger_t"] = t
            mines = [m.strip() for m in request.query_params.getlist("mine") if m.strip()]
            if mines:
                qs = "&".join(f"mine={quote(m)}" for m in mines)
                return RedirectResponse(f"/?{qs}", status_code=303)
        return RedirectResponse("/", status_code=303)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> Any:
        rdr = restore_rt_to_session(request)
        if rdr:
            return rdr
        role = request.session.get("role")
        if not role:
            return RedirectResponse("/login", status_code=303)
        p_q = request.query_params.get("period")
        if p_q in ("year", "month", "custom") and role in ("管理员", "产量数据可视化"):
            request.session["active_section"] = "visual"
        act_path, en_path = get_paths()
        nav, page = _nav_and_page(
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
        if page == "visual":
            period = request.query_params.get("period", "year")
            ds = request.query_params.get("start")
            de = request.query_params.get("end")
            today_cap = today_beijing()
            c_start = c_end = None
            tpl_start = (ds or "").strip()
            tpl_end = (de or "").strip()
            if period == "custom" and tpl_start and tpl_end:
                try:
                    c_start = date.fromisoformat(str(tpl_start))
                    c_end = date.fromisoformat(str(tpl_end))
                    if c_start > today_cap:
                        c_start = today_cap
                    if c_end > today_cap:
                        c_end = today_cap
                    if c_start > c_end:
                        c_start, c_end = c_end, c_start
                    tpl_start = c_start.isoformat()
                    tpl_end = c_end.isoformat()
                except ValueError:
                    period = "year"
            sy_raw = (request.query_params.get("stat_year") or "").strip()
            sm_raw = (request.query_params.get("stat_month") or "").strip()
            stat_year_int: int | None = int(sy_raw) if sy_raw.isdigit() else None
            stat_month_str: str | None = (
                sm_raw if re.fullmatch(r"\d{4}-\d{2}", sm_raw) else None
            )
            d = build_summary_and_charts(
                period=period,
                custom_start=c_start,
                custom_end=c_end,
                stat_year=stat_year_int,
                stat_month=stat_month_str,
            )
            return templates.TemplateResponse(
                request,
                "dashboard.html",
                {
                    **ctx,
                    "dash": d,
                    "period": period,
                    "c_start": tpl_start,
                    "c_end": tpl_end,
                    "visual_custom_max_date": today_cap.isoformat(),
                },
            )
        if page == "entry_actual":
            return templates.TemplateResponse(
                request,
                "entry_actual.html",
                {**ctx, "mines": MINE_LIST, "yesterday": (today_beijing() - timedelta(days=1))},
            )
        if page == "entry_energy":
            return templates.TemplateResponse(
                request,
                "entry_energy.html",
                {**ctx, "mines": MINE_LIST, "yesterday": (today_beijing() - timedelta(days=1))},
            )
        if page == "history":
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
                    "table_html": _df_to_html_table(df) if not df.empty else None,
                    "mine_status": mine_status,
                },
            )
        if page == "admin_ledger":
            ft = request.query_params.get("t") or request.session.get("ledger_t") or "actual"
            if ft not in ("actual", "nybb"):
                ft = "actual"
            selected_mines = [m.strip() for m in request.query_params.getlist("mine") if m.strip()]
            p = act_path if ft == "actual" else en_path
            df = exclude_mines(read_records(p))

            today_str = today_beijing().isoformat()
            mine_status: list[dict[str, object]] = []
            time_col_key = "提交时间" if ft == "actual" else "报送时间"
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
                            row_cells.append(x.strftime("%Y-%m-%d %H:%M"))
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
        if page == "reports":
            return templates.TemplateResponse(
                request,
                "reports.html",
                {**ctx, "default_date": (today_beijing() - timedelta(days=1))},
            )
        if page == "passwords" and role == "管理员":
            return templates.TemplateResponse(
                request, "passwords.html", {**ctx, "msg": None, "ok": None}
            )
        if page == "logs" and role == "管理员":
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
        return templates.TemplateResponse(
            request,
            "message.html",
            {**ctx, "title": "无法访问", "message": "您没有访问该功能的权限。"},
        )

    @app.post("/entry/actual/submit", response_model=None)
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
                return _render_duplicate_confirmation(
                    request,
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
            removed = _safe_replace(act_path, mine, prod_date_iso, new_data)
            save_msg = f"已覆盖：删除旧记录 {removed} 条，写入新记录 1 条"
        else:
            _safe_append(new_data, act_path)
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


    @app.post("/entry/energy/submit", response_model=None)
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
                return _render_duplicate_confirmation(
                    request,
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
            removed = _safe_replace(en_path, mine, prod_date_iso, new_data)
            save_msg = f"已覆盖：删除旧记录 {removed} 条，写入新记录 1 条"
        else:
            _safe_append(new_data, en_path)
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


    @app.post("/admin/ledger/save")
    async def admin_ledger_save(request: Request) -> RedirectResponse:
        if request.session.get("role") != "管理员":
            return RedirectResponse("/login", status_code=303)
        form = await request.form()
        form_type = str(form.get("form_type", "actual"))
        act_path, en_path = get_paths()
        p = act_path if form_type == "actual" else en_path
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
        for i in range(nrows):
            orig_idx_str = str(form.get(f"orig_idx_{i}", ""))
            if not orig_idx_str.lstrip("-").isdigit():
                continue
            orig_idx = int(orig_idx_str)
            if orig_idx < 0 or orig_idx >= len(df_full):
                continue
            if str(form.get(f"del_{i}")) == "1":
                deleted_indices.add(orig_idx)
                continue
            row: dict = {}
            for j, col in enumerate(cols):
                key = f"c_{i}_{j}"
                val = form.get(key)
                row[col] = _coerce_ledger_value(col, str(val) if val is not None else "")
            updated_rows.append((orig_idx, row))

        # ── 合并：保留未出现在表单中的行 + 更新后的行 ──
        updated_idx_set = {r[0] for r in updated_rows}
        result_rows: list[dict] = []
        for idx in range(len(df_full)):
            if idx in deleted_indices:
                continue
            if idx in updated_idx_set:
                for orig_idx, row_dict in updated_rows:
                    if orig_idx == idx:
                        result_rows.append(row_dict)
                        break
            else:
                result_rows.append(df_full.iloc[idx].to_dict())

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
        _safe_overwrite(save_df, p)
        request.session["flash"] = f"已保存，当前共 {len(new_df)} 行"
        request.session["active_section"] = "admin_ledger"
        request.session["ledger_t"] = form_type
        return RedirectResponse("/", status_code=303)

    @app.post("/reports/sjcl", response_model=None)
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

    @app.post("/reports/nybb", response_model=None)
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

    @app.get("/reports/download", response_model=None)
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

    @app.post("/admin/passwords")
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
        nav, _p = _nav_and_page("管理员", None, request.session)
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

    # 路由全注册后再挂 /static
    # ?? ?????????? 5xx ?????????
    @app.middleware("http")
    async def alert_on_5xx(request: Request, call_next):
        try:
            response = await call_next(request)
            if response.status_code >= 500 and get_settings().is_production:
                notify_alert(
                    level="error",
                    title="??? 5xx ??",
                    message=f"{request.method} {request.url.path} ?? {response.status_code}",
                    detail=f"Client: {request.client.host if request.client else 'unknown'}\nUA: {request.headers.get('user-agent', '-')}",
                )
            return response
        except Exception as exc:
            if get_settings().is_production:
                notify_alert(
                    level="critical",
                    title="??????",
                    message=f"{request.method} {request.url.path} ???????",
                    exception=exc,
                )
            raise

    app.mount(
        "/static",
        StaticFiles(directory=str((base / "static").resolve())),
        name="static",
    )

    return app


app = create_app()
