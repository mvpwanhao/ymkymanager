
# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
# 本文件为「云煤矿业产销量管理系统」的组成部分。
# 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
# 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE.
"""AQ 前端合并接入的可信头认证中间件。

当请求携带正确的 X-CCX-Internal-Key（由 aq 后端代理注入）时：
1. 根据 aq 用户角色映射 ymky 角色，身份写入 scope["ccx"]；
2. 兼容旧版基于 session 的路由（注入 role / reporter_kind）。

注意：本中间件须注册在 SessionMiddleware 之内（main.py 中先于
SessionMiddleware add_middleware），才能读写 request.session。
"""

from __future__ import annotations

import hmac

from app.config import get_settings

# aq 角色 → ymky 角色
ROLE_MAP = {
    "adminer": "管理员",
    "admin": "产量数据可视化",
    "zk": "填报人员",
}

# 路径前缀 → 填报通道（旧路由 reporter_kind 兼容）
CHANNEL_BY_PATH = (
    ("/api/ccx/entry/actual", "实际产量填报"),
    ("/api/ccx/entry/energy", "能源局口径产销量填报"),
    ("/api/ccx/entry/sales", "实际销量填报"),
)


def _header(scope, name: bytes) -> str:
    try:
        for k, v in scope.get("headers", []):
            if k == name:
                return v.decode("utf-8", "ignore")
    except Exception:
        pass
    return ""


class CcxAuthMiddleware:
    """纯 ASGI 中间件：校验内网可信头并注入产销量身份。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        incoming = _header(scope, b"x-ccx-internal-key")
        s = get_settings()
        if incoming and s.ccx_internal_key and hmac.compare_digest(incoming, s.ccx_internal_key):
            aq_role = _header(scope, b"x-user-role")
            role = ROLE_MAP.get(aq_role)
            if role:
                username = _header(scope, b"x-username")
                user_id = _header(scope, b"x-user-id")
                scope["ccx"] = {
                    "user_id": user_id,
                    "username": username,
                    "aq_role": aq_role,
                    "role": role,
                }
                session = scope.setdefault("session", {})
                session["role"] = role
                session["ccx_username"] = username
                path = scope.get("path", "")
                for prefix, rk in CHANNEL_BY_PATH:
                    if path.startswith(prefix):
                        session["reporter_kind"] = rk
                        break

        await self.app(scope, receive, send)
