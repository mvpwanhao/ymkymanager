# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
# 本文件为「云煤矿业产销量管理系统」的组成部分。
# 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
# 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE。
from __future__ import annotations

import json
import os
from datetime import date
from urllib import parse, request

from app.config import get_settings
from app.timeutil import now_str


def get_sendkey() -> str:
    s = get_settings()
    v = s.serverchan_sendkey.strip() or (os.environ.get("SERVERCHAN_SENDKEY") or "").strip()
    return v


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
    except Exception as e:
        return False, f"微信提醒发送异常：{e!s}"


def notify_submit_actual(
    *,
    mine: str,
    prod_date: date,
    reporter: str,
    production: float,
    note: str,
) -> tuple[bool, str]:
    title = "云煤填报提醒｜实际生产产量提交成功"
    lines = [
        f"- 煤矿：{mine}",
        f"- 生产日期：{prod_date.strftime('%Y-%m-%d')}",
        f"- 填报人：{reporter}",
        f"- 当日产量：{production:.2f} 吨",
    ]
    if str(note).strip():
        lines.append(f"- 备注：{str(note).strip()}")
    lines.append(f"- 提交时间：{now_str()}")
    return send_serverchan(title=title, desp="\n".join(lines))


def notify_submit_energy(
    *,
    mine: str,
    prod_date: date,
    reporter: str,
    production: float,
    sales: float,
    note: str,
) -> tuple[bool, str]:
    title = "云煤填报提醒｜能源局产销量提交成功"
    lines = [
        f"- 煤矿：{mine}",
        f"- 生产日期：{prod_date.strftime('%Y-%m-%d')}",
        f"- 填报人：{reporter}",
        f"- 当日产量：{production:.2f} 吨",
        f"- 当日销量：{sales:.2f} 吨",
    ]
    if str(note).strip():
        lines.append(f"- 备注：{str(note).strip()}")
    lines.append(f"- 提交时间：{now_str()}")
    return send_serverchan(title=title, desp="\n".join(lines))
