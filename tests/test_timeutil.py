# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
"""timeutil 单元测试：26 日制统计月/年区间、周区间。"""

from datetime import date

from app.timeutil import (
    _next_friday,
    enumerate_weekly_ranges,
    get_26day_month_range,
    get_26day_year_range,
    get_weekly_range,
)


class Test26DayMonthRange:
    """统计月：上月 26 日 — 本月 25 日。"""

    def test_mid_month(self):
        """7 月 15 日 → (6.26, 7.25)"""
        s, e = get_26day_month_range(date(2026, 7, 15))
        assert s == date(2026, 6, 26)
        assert e == date(2026, 7, 25)

    def test_on_26th(self):
        """7 月 26 日 → 进入下一个月 (7.26, 8.25)"""
        s, e = get_26day_month_range(date(2026, 7, 26))
        assert s == date(2026, 7, 26)
        assert e == date(2026, 8, 25)

    def test_on_25th(self):
        """7 月 25 日 → 仍在当月 (6.26, 7.25)"""
        s, e = get_26day_month_range(date(2026, 7, 25))
        assert s == date(2026, 6, 26)
        assert e == date(2026, 7, 25)

    def test_january(self):
        """1 月 10 日 → (上年12.26, 1.25)"""
        s, e = get_26day_month_range(date(2026, 1, 10))
        assert s == date(2025, 12, 26)
        assert e == date(2026, 1, 25)

    def test_december_26(self):
        """12 月 26 日 → 进入下一年 1 月 (12.26, 次年1.25)"""
        s, e = get_26day_month_range(date(2026, 12, 26))
        assert s == date(2026, 12, 26)
        assert e == date(2027, 1, 25)


class Test26DayYearRange:
    """统计年：上年 12 月 26 日 — 本年 12 月 25 日。"""

    def test_mid_year(self):
        s, e = get_26day_year_range(date(2026, 7, 15))
        assert s == date(2025, 12, 26)
        assert e == date(2026, 12, 25)

    def test_on_dec_26(self):
        """12 月 26 日 → 进入下一年"""
        s, e = get_26day_year_range(date(2026, 12, 26))
        assert s == date(2026, 12, 26)
        assert e == date(2027, 12, 25)

    def test_on_dec_25(self):
        """12 月 25 日 → 仍在本年"""
        s, e = get_26day_year_range(date(2026, 12, 25))
        assert s == date(2025, 12, 26)
        assert e == date(2026, 12, 25)

    def test_january(self):
        s, e = get_26day_year_range(date(2026, 1, 5))
        assert s == date(2025, 12, 26)
        assert e == date(2026, 12, 25)


class TestWeeklyRange:
    """周区间：周六至周五。"""

    def test_wednesday(self):
        """周三 → 本周六到本周五"""
        s, e = get_weekly_range(date(2026, 7, 15))  # Wednesday
        assert s.weekday() == 5  # Saturday
        assert e.weekday() == 4  # Friday
        assert (e - s).days == 6

    def test_saturday(self):
        """周六 → 当天到周五"""
        s, e = get_weekly_range(date(2026, 7, 11))  # Saturday
        assert s == date(2026, 7, 11)
        assert e == date(2026, 7, 17)

    def test_friday(self):
        """周五 → 上周六到当天"""
        s, e = get_weekly_range(date(2026, 7, 17))  # Friday
        assert s == date(2026, 7, 11)
        assert e == date(2026, 7, 17)


class TestNextFriday:
    def test_monday(self):
        assert _next_friday(date(2026, 7, 13)) == date(2026, 7, 17)

    def test_friday(self):
        assert _next_friday(date(2026, 7, 17)) == date(2026, 7, 17)

    def test_saturday(self):
        assert _next_friday(date(2026, 7, 18)) == date(2026, 7, 24)


class TestEnumerateWeeklyRanges:
    """统计月内的周区间枚举。"""

    def test_july_2026(self):
        """7 月统计月 (6.26 - 7.25) 的周区间。"""
        s, e = date(2026, 6, 26), date(2026, 7, 25)
        weeks = enumerate_weekly_ranges(s, e)
        assert len(weeks) >= 4
        # 第一周从 26 日开始
        assert weeks[0][0] == date(2026, 6, 26)
        # 最后一周到 25 日结束
        assert weeks[-1][1] == date(2026, 7, 25)
        # 中间各周为周六到周五
        for i in range(1, len(weeks) - 1):
            assert weeks[i][0].weekday() == 5  # Saturday
            assert weeks[i][1].weekday() == 4  # Friday
