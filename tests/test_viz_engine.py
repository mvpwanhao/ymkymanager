# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
"""viz_engine 单元测试：build_viz_data 核心统计逻辑。

重点回归 v1.4.1 修复的 bug：
  mine_key.startswith(prefix, na=False) → mine_key.startswith(prefix)
"""

from datetime import date

from app.viz_engine import build_viz_data


class TestBuildVizDataYear:
    """年度维度数据可视化。"""

    def test_returns_dict(self):
        result = build_viz_data(period="year")
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        result = build_viz_data(period="year")
        for key in ("kpis", "mine_details", "prod_trend", "period", "period_name"):
            assert key in result, f"Missing key: {key}"

    def test_kpis_count(self):
        result = build_viz_data(period="year")
        assert len(result["kpis"]) == 6

    def test_mine_details_not_empty(self):
        result = build_viz_data(period="year")
        assert len(result["mine_details"]) > 0

    def test_period_name_year(self):
        result = build_viz_data(period="year")
        assert result["period_name"] == "年度"

    def test_kpi_labels_use_period_name(self):
        """回归：KPI 标签应包含"年度"而非"期间"。"""
        result = build_viz_data(period="year")
        labels = [k["label"] for k in result["kpis"]]
        assert any("年度" in l for l in labels), f"No '年度' in labels: {labels}"


class TestBuildVizDataMonth:
    """月度维度数据可视化。"""

    def test_period_name_month(self):
        result = build_viz_data(period="month")
        # 当前月或指定月，period_name 应为 "X月" 格式
        assert "月" in result["period_name"]

    def test_specified_month(self):
        result = build_viz_data(period="month", stat_month="2026-06")
        assert result["period_name"] == "6月"

    def test_kpis_count(self):
        result = build_viz_data(period="month")
        assert len(result["kpis"]) == 6


class TestBuildVizDataCustom:
    """自定义区间数据可视化。"""

    def test_period_name_custom(self):
        result = build_viz_data(
            period="custom",
            custom_start=date(2026, 7, 1),
            custom_end=date(2026, 7, 10),
        )
        assert result["period_name"] == "期间"

    def test_custom_range(self):
        result = build_viz_data(
            period="custom",
            custom_start=date(2026, 7, 1),
            custom_end=date(2026, 7, 10),
        )
        assert result["period"] == "custom"
        assert isinstance(result["kpis"], list)


class TestBuildVizDataNoCrash:
    """回归 v1.4.1 bug：ensure no TypeError from startswith(na=False)。"""

    def test_year_no_exception(self):
        """年度数据不应抛出 TypeError。"""
        try:
            build_viz_data(period="year")
        except TypeError as e:
            if "na" in str(e):
                assert False, f"Regression: TypeError from startswith(na=False): {e}"

    def test_month_no_exception(self):
        try:
            build_viz_data(period="month")
        except TypeError as e:
            if "na" in str(e):
                assert False, f"Regression: TypeError from startswith(na=False): {e}"

    def test_custom_no_exception(self):
        try:
            build_viz_data(
                period="custom",
                custom_start=date(2026, 7, 1),
                custom_end=date(2026, 7, 10),
            )
        except TypeError as e:
            if "na" in str(e):
                assert False, f"Regression: TypeError from startswith(na=False): {e}"
