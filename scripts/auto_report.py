#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""自动报表生成与邮件发送脚本。

由服务器定时任务触发（8:30 起，每 5 分钟一次）。

流程：
  1. 检查昨日报表是否已处理过（状态文件存在则直接退出）
  2. 检查"姚家村煤矿""金所煤矿""芒东二矿"在两个台账昨日数据的填报状态
     - 实际产量台账 (actual_production.xlsx)
     - 能源局产销量台账 (energy_reporting.xlsx)
  3a. 三个矿两个台账都填了 → 生成两个报表 → 邮件发送 Excel 附件 → 写状态文件
  3b. 8:55 仍未全填 → 发提醒邮件（列出未填报的矿）→ 写状态文件
  3c. 还没到 8:55 且未填全 → 退出，等下次轮询

用法:
    cd /path/to/ymky_manager && venv/bin/python scripts/auto_report.py

配置 (.env):
    YMKY_SMTP_HOST=smtp.qq.com
    YMKY_SMTP_PORT=465
    YMKY_SMTP_USER=xxx@qq.com
    YMKY_SMTP_PASSWORD=授权码
    YMKY_MAIL_TO=收件人1@xx.com,收件人2@xx.com
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import sys
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate
from pathlib import Path

# ── 确保能导入 app 模块（先 chdir 再 import）──────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
os.chdir(_PROJECT_ROOT)

from app.config import get_settings
from app.report_engine import generate_nybb_report, generate_sjcl_report
from app.storage import find_records_by_mine_date
from datetime import timedelta

from app.timeutil import now_beijing, today_beijing

# ── 配置 ──────────────────────────────────────────────
CHECK_MINES: list[str] = ["姚家村煤矿", "金所煤矿", "芒东二矿"]
DEADLINE_HOUR = 8
DEADLINE_MINUTE = 55

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("auto_report")


# ═══════════════════════════════════════════════════════
#  填报状态检查
# ═══════════════════════════════════════════════════════
def check_mines_submitted(target_date_iso: str) -> dict:
    """检查三矿在两个台账的填报状态。

    返回:
        {
            "actual":  {矿名: bool, ...},
            "energy":  {矿名: bool, ...},
            "all_done": bool,
            "missing": [(矿名, 台账类型), ...],
        }
    """
    s = get_settings()
    result: dict = {
        "actual": {},
        "energy": {},
        "all_done": True,
        "missing": [],
    }

    # 实际产量台账
    for mine in CHECK_MINES:
        records = find_records_by_mine_date(
            s.actual_production_path, mine, target_date_iso
        )
        done = not records.empty
        result["actual"][mine] = done
        if not done:
            result["all_done"] = False
            result["missing"].append((mine, "实际产量"))

    # 能源局产销量台账
    for mine in CHECK_MINES:
        records = find_records_by_mine_date(
            s.energy_reporting_path, mine, target_date_iso
        )
        done = not records.empty
        result["energy"][mine] = done
        if not done:
            result["all_done"] = False
            result["missing"].append((mine, "能源局产销量"))

    return result


# ═══════════════════════════════════════════════════════
#  状态文件（防止当天重复执行）
# ═══════════════════════════════════════════════════════
def _state_dir() -> Path:
    s = get_settings()
    d = s.data_dir / "auto_report_state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_state_file(target_date_iso: str) -> Path:
    return _state_dir() / f"{target_date_iso}.json"


def has_already_run(target_date_iso: str) -> bool:
    return get_state_file(target_date_iso).exists()


def write_state(target_date_iso: str, status: str, detail: str = "") -> None:
    data = {
        "date": target_date_iso,
        "status": status,  # "sent" | "reminder"
        "detail": detail,
        "timestamp": now_beijing().isoformat(),
    }
    get_state_file(target_date_iso).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ═══════════════════════════════════════════════════════
#  邮件发送
# ═══════════════════════════════════════════════════════
def send_email(
    subject: str, body: str, attachments: list[str] | None = None
) -> bool:
    """发送邮件，支持附件。返回是否成功。"""
    s = get_settings()

    if not s.smtp_host or not s.smtp_user or not s.smtp_password:
        log.error("SMTP 配置不完整 (host/user/password 为空)，无法发送邮件")
        return False

    recipients = [addr.strip() for addr in s.mail_to.split(",") if addr.strip()]
    if not recipients:
        log.error("收件人地址为空 (YMKY_MAIL_TO 未配置)")
        return False

    msg = MIMEMultipart()
    msg["From"] = formataddr((s.mail_from_name, s.smtp_user))
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)

    msg.attach(MIMEText(body, "plain", "utf-8"))

    for filepath in attachments or []:
        if not filepath or not os.path.exists(filepath):
            log.warning("附件不存在，跳过: %s", filepath)
            continue
        with open(filepath, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            filename = os.path.basename(filepath)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{filename}"',
            )
            msg.attach(part)
        log.info("已添加附件: %s", filename)

    try:
        port = s.smtp_port
        if port == 465:
            with smtplib.SMTP_SSL(s.smtp_host, port, timeout=30) as server:
                server.login(s.smtp_user, s.smtp_password)
                server.sendmail(s.smtp_user, recipients, msg.as_string())
        else:
            with smtplib.SMTP(s.smtp_host, port, timeout=30) as server:
                server.starttls()
                server.login(s.smtp_user, s.smtp_password)
                server.sendmail(s.smtp_user, recipients, msg.as_string())
        log.info("邮件已发送: %s -> %s", subject, recipients)
        return True
    except Exception as e:
        log.error("邮件发送失败: %s", e)
        return False


# ═══════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════
def main() -> int:
    target_date = (today_beijing() - timedelta(days=1)).isoformat()
    now = now_beijing()
    log.info("=== 自动报表检查 start | target_date=%s(昨日) | now=%s ===", target_date, now.strftime("%H:%M"))

    # 1. 今天已执行过 → 退出
    if has_already_run(target_date):
        log.info("%s 已执行过，跳过", target_date)
        return 0

    # 2. 检查填报状态
    status = check_mines_submitted(target_date)

    deadline = now.replace(
        hour=DEADLINE_HOUR, minute=DEADLINE_MINUTE, second=0, microsecond=0
    )

    if status["all_done"]:
        # 3a. 全部填报 → 生成报表 → 发邮件
        log.info("三矿两个台账均已填报，开始生成报表...")

        sjcl_path, sjcl_msg = generate_sjcl_report(target_date)
        nybb_path, nybb_msg = generate_nybb_report(target_date)

        attachments = [p for p in [sjcl_path, nybb_path] if p]
        results: list[str] = []

        if sjcl_path:
            results.append(f"  [OK] 实际产量统计表: {sjcl_msg}")
        else:
            results.append(f"  [FAIL] 实际产量统计表: {sjcl_msg}")

        if nybb_path:
            results.append(f"  [OK] 能源局日报: {nybb_msg}")
        else:
            results.append(f"  [FAIL] 能源局日报: {nybb_msg}")

        body = (
            f"云煤矿业 {target_date} 每日报表已自动生成，详见附件。\n\n"
            f"生成结果:\n" + "\n".join(results)
        )

        ok = send_email(
            subject=f"云煤矿业每日报表 {target_date}",
            body=body,
            attachments=attachments,
        )
        write_state(target_date, "sent", "; ".join(results))
        if ok:
            log.info("报表已生成并邮件发送完成")
        else:
            log.warning("报表已生成但邮件发送失败，状态仍标记为 sent（报表文件在 exports 目录）")
        return 0

    elif now >= deadline:
        # 3b. 到截止时间未填完 → 发提醒
        missing_lines = [f"  - {m[0]}: {m[1]}台账" for m in status["missing"]]
        body = (
            f"截至 {DEADLINE_HOUR}:{DEADLINE_MINUTE:02d}，"
            f"以下煤矿尚未完成 {target_date} 的数据填报，"
            f"今日报表未自动生成:\n\n"
            + "\n".join(missing_lines)
            + "\n\n请尽快完成填报，填报完成后可登录系统手动生成报表。"
        )
        send_email(
            subject=f"【提醒】云煤矿业报表未生成 {target_date}",
            body=body,
        )
        write_state(target_date, "reminder", "\n".join(missing_lines))
        log.info("已发送未填报提醒: %s", status["missing"])
        return 0

    else:
        # 3c. 还没到截止时间，等下次轮询
        log.info(
            "尚有矿未填报 (缺失: %s), 当前 %s, 截止 %d:%02d, 等待下次轮询",
            status["missing"],
            now.strftime("%H:%M"),
            DEADLINE_HOUR,
            DEADLINE_MINUTE,
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
