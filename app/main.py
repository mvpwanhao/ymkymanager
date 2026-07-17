# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
# 本文件为「云煤矿业产销量管理系统」的组成部分。
# 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
# 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE.
"""应用工厂：创建 FastAPI 应用，配置中间件，挂载路由模块。"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import get_settings
from app.helpers import compute_asset_version
from app.middleware_production import SecurityHeadersMiddleware, StaticCacheMiddleware
from app.routes import admin, auth, entry, health, pages, report, viz
from app.services.notify import notify_alert

LOG_FILE = get_settings().data_dir / "ymky_system.log"

_DEFAULT_SECRET_MARKER = "dev-change-me-please-use-yml-or-env-YMKY_SECRET_KEY"


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
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="云南云煤矿业开发有限公司 · 产销量管理系统",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )

    # ── 中间件 ──
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

    # ── 模板引擎 ──
    base = s.base_dir
    templates = Jinja2Templates(directory=str(base / "templates"))
    templates.env.filters["tojson"] = lambda v: Markup(
        json.dumps(v, ensure_ascii=False)
    )
    templates.env.globals["asset_version"] = compute_asset_version()
    app.state.templates = templates

    # ── 路由模块 ──
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(pages.router)
    app.include_router(entry.router)
    app.include_router(report.router)
    app.include_router(viz.router)
    app.include_router(admin.router)

    # ── 5xx 告警中间件 ──
    @app.middleware("http")
    async def alert_on_5xx(request: Request, call_next):
        try:
            response = await call_next(request)
            if response.status_code >= 500 and get_settings().is_production:
                notify_alert(
                    level="error",
                    title="线上 5xx 告警",
                    message=f"{request.method} {request.url.path} 返回 {response.status_code}",
                    detail=f"Client: {request.client.host if request.client else 'unknown'}\nUA: {request.headers.get('user-agent', '-')}",
                )
            return response
        except Exception as exc:
            if get_settings().is_production:
                notify_alert(
                    level="critical",
                    title="请求处理异常",
                    message=f"{request.method} {request.url.path} 处理异常",
                    exception=exc,
                )
            raise

    # ── 静态文件 ──
    app.mount(
        "/static",
        StaticFiles(directory=str((base / "static").resolve())),
        name="static",
    )

    return app


app = create_app()
