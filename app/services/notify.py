# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
# 本文件为「云煤矿业产销量管理系统」的组成部分。
# 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
# 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE。
from __future__ import annotations

import json
import os
import traceback
from typing import Literal
from urllib.error import HTTPError
from urllib import parse, request

from app.config import get_settings
from app.timeutil import now_str


# ── 低层 API ──────────────────────────────────────────


def get_sendkey() -> str:
    s = get_settings()
    v = s.serverchan_sendkey.strip() or (os.environ.get("SERVERCHAN_SENDKEY") or "").strip()
    return v


def _serverchan_available() -> bool:
    """Server酱 是否已配置"""
    return bool(get_sendkey())


def send_serverchan(*, title: str, desp: str) -> tuple[bool, str]:
    send_key = get_sendkey()
    if not send_key:
        return False, "未配置 SERVERCHAN_SENDKEY"

    api_url = f"https://sctapi.ftqq.com/{send_key}.send"
    body = parse.urlencode({"title": title, "desp": desp}).encode("utf-8")
    req = request.Request(api_url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        payload = json.loads(raw) if raw else {}
        if int(payload.get("code", -1)) == 0:
            return True, "微信提醒已发送"
        return False, f"微信提醒发送失败：{payload.get('message', '未知错误')}"
    except HTTPError as e:
        detail = ""
        try:
            raw = e.read().decode("utf-8", errors="ignore")
            payload = json.loads(raw) if raw else {}
            detail = str(payload.get("message") or payload.get("info") or "").strip()
        except Exception:
            detail = ""
        if detail:
            return False, f"微信提醒发送失败：{detail}"
        return False, f"微信提醒发送失败：HTTP {e.code}"
    except Exception as e:
        return False, f"微信提醒发送异常：{e!s}"


# ── 填报成功通知（保留原有功能）────────────────────────


def notify_alert(
    *,
    level: Literal["critical", "error", "warning", "info"] = "error",
    title: str,
    message: str,
    detail: str = "",
    exception: BaseException | None = None,
) -> tuple[bool, str]:
    """发送异常告警到微信（Server酱）。

    适用场景：
    - 服务启动失败 / 容器重启
    - 数据库断连
    - 健康检查异常
    - 导出/报表生成异常
    - 其他需要人工关注的异常

    Parameters
    ----------
    level : 告警级别（影响标题前缀表情）。
    title : 告警标题，例如 "数据库断连"。
    message : 一行摘要。
    detail : 可选的上下文详情（多行）。
    exception : 可选的异常对象，自动添加调用栈。
    """
    if not _serverchan_available():
        return False, "未配置 SERVERCHAN_SENDKEY，跳过告警"

    emoji = ALERT_LEVEL_EMOJI.get(level, "⚠️")
    full_title = f"{emoji} 【{level.upper()}】{title}"

    lines = [f"📌 {message}", f"🕐 {now_str()}"]
    if detail:
        lines.append("")
        lines.append(detail)
    if exception is not None:
        tb = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        lines.append("")
        lines.append("📎 异常调用栈：")
        lines.append(f"```\n{tb}\n```")

    return send_serverchan(title=full_title, desp="\n".join(lines))


# ── 启动通知（新增）────────────────────────────────────


def notify_startup(*, success: bool, version: str, detail: str = "") -> tuple[bool, str]:
    """服务启动/重启时发送通知。

    无论成功或失败都会发送，让用户感知服务状态。
    """
    if not _serverchan_available():
        return False, "未配置 SERVERCHAN_SENDKEY，跳过启动通知"

    if success:
        emoji, level, status = "✅", "info", "启动成功"
    else:
        emoji, level, status = "🚨", "critical", "启动失败"

    title = f"{emoji} 服务{status}"
    message = f"YMKY 产销量管理系统 v{version} 已在服务器上 {status}"
    lines = [f"📌 {message}", f"🕐 {now_str()}"]
    if version:
        lines.append(f"📦 版本：{version}")
    if detail:
        lines.append(f"📋 详情：{detail}")

    return send_serverchan(title=title, desp="\n".join(lines))
