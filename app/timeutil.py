# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
# 本文件为「云煤矿业产销量管理系统」的组成部分。
# 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
# 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE。
"""业务时间统一为北京时间 (Asia/Shanghai)，避免云服务器 UTC 与本地混用。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

TZ_BEIJING = ZoneInfo("Asia/Shanghai")
TZ_UTC = ZoneInfo("UTC")


def now_beijing() -> datetime:
    return datetime.now(TZ_BEIJING)


def today_beijing() -> date:
    return now_beijing().date()


def now_str() -> str:
    return now_beijing().strftime("%Y-%m-%d %H:%M")


def get_26day_month_range(anchor_dt: date) -> tuple[date, date]:
    """返回 anchor 所在的 26 日制统计月区间（含两端）。

    规则：每个统计月从「上月 26 日」开始、到「本月 25 日」结束；
    若 anchor 的日 ≥ 26，则它已经进入下一个统计月——
    例：anchor=2026-04-27 → 区间 (2026-04-26, 2026-05-25)。
    """
    if anchor_dt.day >= 26:
        start = date(anchor_dt.year, anchor_dt.month, 26)
        end_year = anchor_dt.year if anchor_dt.month < 12 else anchor_dt.year + 1
        end_month = anchor_dt.month + 1 if anchor_dt.month < 12 else 1
        return start, date(end_year, end_month, 25)
    start_year = anchor_dt.year if anchor_dt.month > 1 else anchor_dt.year - 1
    start_month = anchor_dt.month - 1 if anchor_dt.month > 1 else 12
    return date(start_year, start_month, 26), date(anchor_dt.year, anchor_dt.month, 25)


def get_26day_year_range(anchor_dt: date) -> tuple[date, date]:
    """返回 anchor 所在的 26 日制统计年区间（含两端）。

    规则：统计年从「上年 12 月 26 日」开始、到「本年 12 月 25 日」结束；
    若 anchor 的(月, 日) ≥ (12, 26)，则它已经进入下一个统计年——
    例：anchor=2026-12-30 → 区间 (2026-12-26, 2027-12-25)。
    """
    if (anchor_dt.month, anchor_dt.day) >= (12, 26):
        return date(anchor_dt.year, 12, 26), date(anchor_dt.year + 1, 12, 25)
    return date(anchor_dt.year - 1, 12, 26), date(anchor_dt.year, 12, 25)


def _next_friday(d: date) -> date:
    """返回 >= d 的最近一个周五（含 d 本身）。"""
    days_ahead = 4 - d.weekday()  # Friday == 4
    if days_ahead < 0:
        days_ahead += 7
    return d + timedelta(days=days_ahead)


def enumerate_weekly_ranges(month_start: date, month_end: date) -> list[tuple[date, date]]:
    """枚举一个 26 日制统计月内的所有周区间（含两端）。

    规则：
    - 首周从 month_start（26 日）开始，到最近的周五结束（不论有几天）；
    - 中间各周为周六至周五（7 天）；
    - 末周从上周六开始，到 month_end（25 日）结束（不论有几天）；
    - 若某周五超过 month_end，则截断为 month_end。
    """
    ranges: list[tuple[date, date]] = []
    current = month_start
    while current <= month_end:
        friday = _next_friday(current)
        week_end = min(friday, month_end)
        ranges.append((current, week_end))
        current = week_end + timedelta(days=1)
    return ranges


def get_weekly_range(anchor_dt: date) -> tuple[date, date]:
    """返回 anchor_dt 所属的周区间 (start, end)。

    先定位 26 日制统计月，再枚举该月所有周区间并匹配。
    """
    month_start, month_end = get_26day_month_range(anchor_dt)
    for start, end in enumerate_weekly_ranges(month_start, month_end):
        if start <= anchor_dt <= end:
            return start, end
    return month_start, month_end


def get_26day_statistical_month_label(d: object) -> str:
    """将日期映射为它所属的 26 日制统计月标签（YYYY年MM月）。"""
    dt = pd.to_datetime(d).date()
    _, end = get_26day_month_range(dt)
    return f"{end.year}年{end.month:02d}月"


def format_series_as_beijing_display(
    s: pd.Series,
    *,
    treat_naive_as_utc: bool = False,
) -> pd.Series:
    """
    将一列时间用于界面展示为北京时间字符串。
    - 含时区（如 timestamptz）→ 转为 Asia/Shanghai 再格式化
    - 无时区：若 treat_naive_as_utc 为真（从 PostgreSQL 等读出的 naive 常为 UTC 墙钟）→ 先按 UTC 再转北京；
      为假时（本地 Excel/应用 now_str 写入）→ 按原样墙钟显示，不外加偏移
    """
    out: list[object] = []
    current_year = datetime.now().year
    for v in s:
        if v is None or (isinstance(v, float) and pd.isna(v)) or (isinstance(v, str) and not str(v).strip()):
            out.append(v)
            continue
        t = pd.to_datetime(v, errors="coerce")
        if pd.isna(t):
            out.append(v)
            continue
        t = t if isinstance(t, pd.Timestamp) else pd.Timestamp(t)
        if t.tzinfo is not None:
            t_bj = t.tz_convert(TZ_BEIJING)
        elif treat_naive_as_utc:
            t_bj = t.tz_localize(TZ_UTC).tz_convert(TZ_BEIJING)
        else:
            t_bj = t
        fmt = "%m-%d %H:%M" if t_bj.year == current_year else "%Y-%m-%d %H:%M"
        out.append(t_bj.strftime(fmt))
    return pd.Series(out, index=s.index, dtype=object)
