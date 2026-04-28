# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
# 本文件为「云煤矿业产销量管理系统」的组成部分。
# 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
# 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE。
"""部署用 HTTP 中间件：安全响应头、静态资源缓存提示。"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """通用安全相关响应头（不启用严格 CSP，以免与内联脚本冲突）。"""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        h = response.headers
        if "x-content-type-options" not in {k.lower() for k in h.keys()}:
            h["X-Content-Type-Options"] = "nosniff"
        if "x-frame-options" not in {k.lower() for k in h.keys()}:
            h["X-Frame-Options"] = "SAMEORIGIN"
        if "referrer-policy" not in {k.lower() for k in h.keys()}:
            h["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if "permissions-policy" not in {k.lower() for k in h.keys()}:
            h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


class StaticCacheMiddleware(BaseHTTPMiddleware):
    """为 /static/* 设较长缓存。模板中 CSS/JS 已带 ?v= 指纹，可安全更新。"""

    _max_age = 86400  # 1 天

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        path = request.url.path
        if not path.startswith("/static/"):
            return response
        if response.status_code >= 400:
            return response
        if "cache-control" in {k.lower() for k in response.headers.keys()}:
            return response
        response.headers["Cache-Control"] = f"public, max-age={self._max_age}"
        return response
