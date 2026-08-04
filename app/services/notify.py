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

ALERT_LEVEL_EMOJI = {"critical": "🚨", "error": "❌", "warning": "⚠️", "info": "ℹ️"}


# ── 低层 API ──────────────────────────────────────────


def get_sendkey() -> str:
    s = get_settings()
    v = s.serverchan_sendkey.strip() or (os.environ.get("SERVERCHAN_SENDKEY") or "").strip()
    return v


def _serverchan_available() -> bool:
    """Server酱 是否已配置"""
    return bool(get_sendkey())


def get_push_api() -> tuple[str, str]:
    """自建微信推送服务器配置（url, token）。"""
    s = get_settings()
    url = (s.push_api_url.strip() or os.environ.get("WECHAT_PUSH_API_URL") or "").strip()
    token = (s.push_api_token.strip() or os.environ.get("WECHAT_PUSH_API_TOKEN") or "").strip()
    return url, token


def _push_available() -> bool:
    """自建微信推送服务器是否已配置"""
    url, token = get_push_api()
    return bool(url and token)


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


def send_wechat_push(*, title: str, content: str) -> tuple[bool, str]:
    """发送到自建微信推送服务器（POST /api/v1/send，Bearer 鉴权）。"""
    url, token = get_push_api()
    if not url or not token:
        return False, "未配置 WECHAT_PUSH_API_URL/WECHAT_PUSH_API_TOKEN"

    body = json.dumps({"title": title, "content": content}, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        payload = json.loads(raw) if raw else {}
        if payload.get("delivered") is True and int(payload.get("errcode", -1)) == 0:
            return True, "微信提醒已发送"
        return False, f"微信提醒发送失败：{payload.get('errmsg') or '未知错误'}"
    except HTTPError as e:
        detail = ""
        try:
            raw = e.read().decode("utf-8", errors="ignore")
            payload = json.loads(raw) if raw else {}
            inner = payload.get("detail")
            if isinstance(inner, dict):
                detail = str(inner.get("errmsg") or inner.get("detail") or "")
            else:
                detail = str(payload.get("errmsg") or payload.get("detail") or "")
        except Exception:
            detail = ""
        if detail:
            return False, f"微信提醒发送失败：{detail}"
        return False, f"微信提醒发送失败：HTTP {e.code}"
    except Exception as e:
        return False, f"微信提醒发送异常：{e!s}"


# ── 填报成功通知────────────────────────


def _append_note_and_time(lines: list[str], note: str) -> list[str]:
    """追加备注（如有）与提交时间，返回原列表。"""
    if str(note).strip():
        lines.append(f"- 备注：{str(note).strip()}")
    lines.append(f"- 提交时间：{now_str()}")
    return lines


def _send_success_notification(*, title: str, lines: list[str]) -> tuple[bool, str]:
    """发送填报成功提醒。

    优先使用自建微信推送服务器（WECHAT_PUSH_API_URL/TOKEN，微信测试号模板消息）；
    未配置或发送失败时，回退到 Server酱（SERVERCHAN_SENDKEY）。
    """
    if not _push_available() and not _serverchan_available():
        return False, "未配置推送通道（WECHAT_PUSH_API_* 或 SERVERCHAN_SENDKEY），跳过通知"

    full_desp = "\n".join(lines)
    if _push_available():
        # 自建推送是模板消息，单字段有长度限制：只传精简内容
        ok, msg = send_wechat_push(title=title, content=full_desp[:500])
        if ok or not _serverchan_available():
            return ok, msg
    return send_serverchan(title=title, desp=full_desp)


def notify_submit_actual(
    *,
    mine: str,
    prod_date: str,
    reporter: str,
    production: float,
    note: str = "",
) -> tuple[bool, str]:
    """实际产量填报成功提醒。"""
    title = "✅ 填报成功｜实际产量"
    lines = [
        f"{mine} {prod_date} 产量{production:.2f}吨",
        f"- 填报人：{reporter}",
    ]
    return _send_success_notification(title=title, lines=_append_note_and_time(lines, note))


def notify_submit_energy(
    *,
    mine: str,
    prod_date: str,
    reporter: str,
    production: float,
    sales: float,
    note: str = "",
) -> tuple[bool, str]:
    """能源局产销量填报成功提醒。"""
    title = "✅ 填报成功｜能源局产销量"
    lines = [
        f"{mine} {prod_date} 产{production:.2f}吨 销{sales:.2f}吨",
        f"- 填报人：{reporter}",
    ]
    return _send_success_notification(title=title, lines=_append_note_and_time(lines, note))


def notify_submit_sales(
    *,
    mine: str,
    week_range: str,
    reporter: str,
    sales: float = 0.0,
    year_blended: float = 0.0,
    year_purchased: float = 0.0,
    note: str = "",
) -> tuple[bool, str]:
    """实际销量填报成功提醒（不选煤矿时仅汇总年累计掺配煤/外购煤量）。"""
    title = "✅ 填报成功｜实际销量"
    if mine:
        lines = [
            f"{mine} 周销量{sales:.2f}吨",
            f"- 统计周期：{week_range}",
            f"- 填报人：{reporter}",
        ]
    else:
        lines = [
            f"年累计掺配煤{year_blended:.2f}吨 外购{year_purchased:.2f}吨",
            f"- 填报人：{reporter}",
        ]
    return _send_success_notification(title=title, lines=_append_note_and_time(lines, note))


# ── 异常告警通知────────────────────────


def notify_alert(
    *,
    level: Literal["critical", "error", "warning", "info"] = "error",
    title: str,
    message: str,
    detail: str = "",
    exception: BaseException | None = None,
) -> tuple[bool, str]:
    """发送异常告警到微信。

    优先使用自建微信推送服务器（WECHAT_PUSH_API_URL/TOKEN，微信测试号模板消息）；
    未配置或发送失败时，回退到 Server酱（SERVERCHAN_SENDKEY）。

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
    if not _push_available() and not _serverchan_available():
        return False, "未配置推送通道（WECHAT_PUSH_API_* 或 SERVERCHAN_SENDKEY），跳过告警"

    emoji = ALERT_LEVEL_EMOJI.get(level, "⚠️")
    full_title = f"{emoji} 【{level.upper()}】{title}"

    lines = [f"📌 {message}", f"🕐 {now_str()}"]
    if detail:
        lines.append("")
        lines.append(detail)
    tb = ""
    if exception is not None:
        tb = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        lines.append("")
        lines.append("📎 异常调用栈：")
        lines.append(f"```\n{tb}\n```")
    full_desp = "\n".join(lines)

    if _push_available():
        # 自建推送是模板消息，单字段有长度限制：只传 标题+摘要+异常首行 的精简内容
        compact_lines = [f"📌 {message}", f"🕐 {now_str()}"]
        if detail:
            compact_lines.extend(["", detail])
        if tb:
            compact_lines.extend(["", "📎 异常：", tb.splitlines()[0] if tb else ""])
        ok, msg = send_wechat_push(title=full_title, content="\n".join(compact_lines)[:500])
        if ok or not _serverchan_available():
            return ok, msg

    return send_serverchan(title=full_title, desp=full_desp)