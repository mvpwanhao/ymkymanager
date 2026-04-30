# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
# 本文件为「云煤矿业产销量管理系统」的组成部分。
# 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
# 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE。
"""数据可视化：汇总表与 Plotly 图表（HTML 片段）。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from app.config import get_settings
from app.constants import MINE_LIST, REMOVED_MINE_KEYWORDS
from app.storage import read_records
from app.timeutil import (
    get_26day_month_range,
    get_26day_statistical_month_label,
    get_26day_year_range,
    today_beijing,
)


def exclude_mines(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "所属煤矿" not in df.columns:
        return df
    mask = ~df["所属煤矿"].astype(str).str.contains("|".join(REMOVED_MINE_KEYWORDS), na=False)
    return df.loc[mask].copy()


_PLOT_CONFIG: dict[str, Any] = {
    "responsive": True,
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "showAxisDragHandles": False,
    "showAxisRangeEntryBoxes": False,
    "showTips": False,
    "toImageButtonOptions": {"format": "png"},
}

# 多系列色板（与 static/plotly-theme.js 中 light 色序一致）
_PLOT_COLORWAY: tuple[str, ...] = (
    "#2563eb",
    "#ea580c",
    "#16a34a",
    "#dc2626",
    "#7c3aed",
    "#0d9488",
    "#db2777",
    "#ca8a04",
    "#4f46e5",
    "#059669",
    "#e11d48",
    "#b45309",
)


def _lock_axes(fig: go.Figure) -> None:
    """禁止所有缩放与平移：移动端用单指上下滚动时不会被图表截走。"""
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    fig.update_layout(dragmode=False)


def _fig_to_html(fig: go.Figure) -> str:
    inner = pio.to_html(
        fig,
        full_html=False,
        include_plotlyjs="cdn",
        config=_PLOT_CONFIG,
    )
    return f'<div class="chart-wrap">{inner}</div>'


def _year_label(y: int) -> str:
    """统计年标签：2026 → 2026年（2025.12.26-2026.12.25）。"""
    return f"{y}年（{y - 1}.12.26-{y}.12.25）"


def _month_label(y: int, m: int) -> str:
    """统计月标签：(2026, 5) → 2026年5月（4.26-5.25）。"""
    pm = m - 1 if m > 1 else 12
    return f"{y}年{m}月（{pm}.26-{m}.25）"


def _enum_stat_years(d_lo: date, d_hi: date) -> list[int]:
    """枚举两端日期分别所属的统计年（含两端）。"""
    y_lo = get_26day_year_range(d_lo)[1].year
    y_hi = get_26day_year_range(d_hi)[1].year
    if y_lo > y_hi:
        y_lo, y_hi = y_hi, y_lo
    return list(range(y_lo, y_hi + 1))


def _enum_stat_months(d_lo: date, d_hi: date) -> list[tuple[int, int]]:
    """枚举两端日期所属的统计月（用 end 月份的 (year, month) 表示，含两端）。"""
    e_lo = get_26day_month_range(d_lo)[1]
    e_hi = get_26day_month_range(d_hi)[1]
    if (e_lo.year, e_lo.month) > (e_hi.year, e_hi.month):
        e_lo, e_hi = e_hi, e_lo
    out: list[tuple[int, int]] = []
    y, m = e_lo.year, e_lo.month
    while (y, m) <= (e_hi.year, e_hi.month):
        out.append((y, m))
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return out


def build_summary_and_charts(
    *,
    period: str = "year",
    custom_start: date | None = None,
    custom_end: date | None = None,
    stat_year: int | None = None,
    stat_month: str | None = None,
) -> dict[str, Any]:
    s = get_settings()
    act_path = s.actual_production_path
    en_path = s.energy_reporting_path
    actual_df = exclude_mines(read_records(act_path))
    if actual_df.empty or "生产日期" not in actual_df.columns:
        return {"empty": True, "message": "暂无可视化数据，请先录入台账。"}

    actual_df = actual_df.copy()
    actual_df["生产日期"] = pd.to_datetime(actual_df["生产日期"]).dt.date
    today = today_beijing()
    energy_df = exclude_mines(read_records(en_path))
    if not energy_df.empty and "生产日期" in energy_df.columns:
        energy_df = energy_df.copy()
        energy_df["生产日期"] = pd.to_datetime(energy_df["生产日期"]).dt.date

    actual_df["产量(吨)"] = pd.to_numeric(actual_df.get("产量(吨)"), errors="coerce").fillna(0)
    yesterday = today - timedelta(days=1)
    actual_yesterday = actual_df[actual_df["生产日期"] == yesterday].groupby("所属煤矿")["产量(吨)"].sum()
    month_start, month_end = get_26day_month_range(today)
    actual_month = actual_df[
        (actual_df["生产日期"] >= month_start) & (actual_df["生产日期"] <= month_end)
    ].groupby("所属煤矿")["产量(吨)"].sum()
    annual_start, annual_end = get_26day_year_range(today)
    actual_year_sum = actual_df[
        (actual_df["生产日期"] >= annual_start) & (actual_df["生产日期"] <= annual_end)
    ].groupby("所属煤矿")["产量(吨)"].sum()
    if "年度总产量(吨)" in actual_df.columns:
        annual_col = pd.to_numeric(actual_df["年度总产量(吨)"], errors="coerce")
        actual_year_reported = actual_df.assign(_annual=annual_col).groupby("所属煤矿")["_annual"].max()
        actual_year = (
            pd.concat([actual_year_sum.rename("sum"), actual_year_reported.rename("reported")], axis=1)
            .max(axis=1, skipna=True)
        )
    else:
        actual_year = actual_year_sum

    if not energy_df.empty and {"所属煤矿", "产量(吨)", "销量(吨)", "生产日期"}.issubset(energy_df.columns):
        energy_yest = energy_df[energy_df["生产日期"] == yesterday]
        energy_yesterday_prod = energy_yest.groupby("所属煤矿")["产量(吨)"].sum()
        energy_yesterday_sales = energy_yest.groupby("所属煤矿")["销量(吨)"].sum()
    else:
        energy_yesterday_prod = pd.Series(dtype="float64")
        energy_yesterday_sales = pd.Series(dtype="float64")

    table_df = pd.DataFrame({"煤矿名称": MINE_LIST})
    table_df["昨日实际产量(吨)"] = table_df["煤矿名称"].map(actual_yesterday).fillna(0)
    table_df["月度总产量(吨)"] = table_df["煤矿名称"].map(actual_month).fillna(0)
    table_df["年度总产量(吨)"] = table_df["煤矿名称"].map(actual_year).fillna(0)
    table_df["今日报能源局产量(吨)"] = table_df["煤矿名称"].map(energy_yesterday_prod).fillna(0)
    table_df["今日报能源局销量(吨)"] = table_df["煤矿名称"].map(energy_yesterday_sales).fillna(0)
    for c in [
        "昨日实际产量(吨)",
        "月度总产量(吨)",
        "年度总产量(吨)",
        "今日报能源局产量(吨)",
        "今日报能源局销量(吨)",
    ]:
        table_df[c] = table_df[c].round(2)
    total_row = {"煤矿名称": "合计"}
    kpi_keys = [
        "昨日实际产量(吨)",
        "月度总产量(吨)",
        "年度总产量(吨)",
        "今日报能源局产量(吨)",
        "今日报能源局销量(吨)",
    ]
    for c in kpi_keys:
        total_row[c] = float(table_df[c].sum())
    kpis = [
        {"label": "昨日实际产量", "value": float(total_row["昨日实际产量(吨)"]), "unit": "吨"},
        {"label": "月度累计产量", "value": float(total_row["月度总产量(吨)"]), "unit": "吨"},
        {"label": "年度累计产量", "value": float(total_row["年度总产量(吨)"]), "unit": "吨"},
        {"label": "今日报能源局产量", "value": float(total_row["今日报能源局产量(吨)"]), "unit": "吨"},
        {"label": "今日报能源局销量", "value": float(total_row["今日报能源局销量(吨)"]), "unit": "吨"},
    ]
    table_df = pd.concat([table_df, pd.DataFrame([total_row])], ignore_index=True)
    table_html = table_df.to_html(
        index=False, classes="data-table", border=0, float_format=lambda x: f"{x:.2f}" if isinstance(x, float) else str(x)
    )
    stat_month_label = get_26day_statistical_month_label(today)
    stat_year_label = f"{annual_end.year}统计年"
    cap = (
        f"今天 {today.isoformat()}　·　"
        f"「昨日实际产量」「今日报能源局」均取 {yesterday.isoformat()} 当天数据　·　"
        f"「月度总产量」为 {stat_month_label}（{month_start.isoformat()} 至 {month_end.isoformat()}）　·　"
        f"「年度总产量」为 {stat_year_label}（{annual_start.isoformat()} 至 {annual_end.isoformat()}）"
    )

    min_d = actual_df["生产日期"].min()
    max_d = max(actual_df["生产日期"].max(), today)
    years = _enum_stat_years(min_d, max_d) or [annual_end.year]
    months = _enum_stat_months(min_d, max_d) or [(month_end.year, month_end.month)]

    cur_year = annual_end.year
    cur_month_pair = (month_end.year, month_end.month)

    if stat_year is not None and int(stat_year) in years:
        sel_year = int(stat_year)
    else:
        sel_year = cur_year if cur_year in years else years[-1]

    sel_month_pair = cur_month_pair if cur_month_pair in months else months[-1]
    if stat_month:
        try:
            sm_y, sm_m = (int(x) for x in str(stat_month).split("-", 1))
            if (sm_y, sm_m) in months:
                sel_month_pair = (sm_y, sm_m)
        except ValueError:
            pass
    sel_month = f"{sel_month_pair[0]:04d}-{sel_month_pair[1]:02d}"

    year_options = [
        {"value": y, "label": _year_label(y)} for y in sorted(years, reverse=True)
    ]
    month_options = [
        {"value": f"{y:04d}-{m:02d}", "label": _month_label(y, m)}
        for (y, m) in sorted(months, reverse=True)
    ]

    if period == "year":
        start_date = date(sel_year - 1, 12, 26)
        end_date = date(sel_year, 12, 25)
    elif period == "month":
        sm_y, sm_m = sel_month_pair
        if sm_m > 1:
            start_date = date(sm_y, sm_m - 1, 26)
        else:
            start_date = date(sm_y - 1, 12, 26)
        end_date = date(sm_y, sm_m, 25)
    else:
        if custom_start and custom_end:
            start_date, end_date = custom_start, custom_end
        else:
            start_date, end_date = today - timedelta(days=30), today
        if start_date > end_date:
            return {"empty": True, "message": "开始日期不能晚于结束日期。"}

    period_df = actual_df[
        (actual_df["生产日期"] >= start_date) & (actual_df["生产日期"] <= end_date)
    ].copy()
    prange = f"{start_date.isoformat()} 至 {end_date.isoformat()}"
    period_meta: dict[str, Any] = {
        "selected_year": sel_year,
        "selected_month": sel_month,
        "year_options": year_options,
        "month_options": month_options,
    }
    if period_df.empty:
        pie_h = bar_h = trend_h = "<p class='muted'>当前区间暂无产量数据。</p>"
        return {
            "empty": False,
            "summary_html": table_html,
            "caption": cap,
            "period_caption": prange,
            "kpis": kpis,
            "pie_html": pie_h,
            "bar_html": bar_h,
            "trend_html": trend_h,
            **period_meta,
        }

    share_df = (
        period_df.groupby("所属煤矿", as_index=False)["产量(吨)"]
        .sum()
        .sort_values("产量(吨)", ascending=False)
    )
    period_total_actual = float(share_df["产量(吨)"].sum())
    total_val = period_total_actual or 1
    share_df["占比"] = (share_df["产量(吨)"] / total_val * 100).round(2)
    share_df["标签"] = (
        share_df["所属煤矿"]
        + "<br>"
        + share_df["产量(吨)"].round(0).astype(int).astype(str)
        + "吨"
        + "<br>"
        + share_df["占比"].astype(str)
        + "%"
    )
    pie_fig = go.Figure(
        data=[
            go.Pie(
                labels=share_df["所属煤矿"],
                values=share_df["产量(吨)"],
                text=share_df["标签"],
                textinfo="text",
                textposition="outside",
                hovertemplate="%{label}<br>产量: %{value:.2f} 吨<br>占比: %{percent}<extra></extra>",
                automargin=False,
                domain=dict(x=[0.02, 0.72], y=[0.06, 0.78]),
            )
        ]
    )
    pie_fig.update_layout(
        margin=dict(l=16, r=120, t=56, b=36),
        legend_title_text="煤矿",
        legend=dict(
            x=1,
            xref="paper",
            xanchor="left",
            y=0.52,
            yref="paper",
            yanchor="middle",
            itemwidth=30,
            tracegroupgap=2,
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(0,0,0,0)",
            borderwidth=0,
        ),
        dragmode=False,
        colorway=list(_PLOT_COLORWAY),
    )
    pie_fig.add_annotation(
        text=f"实际总产量：<b>{period_total_actual:.2f}</b> 吨",
        xref="paper",
        yref="paper",
        x=0,
        y=1.015,
        xanchor="left",
        yanchor="top",
        showarrow=False,
        font=dict(size=12),
    )

    rank_df = share_df.copy()
    rank_df["标签"] = rank_df["产量(吨)"].round(0).astype(int).astype(str) + "吨"
    bar_fig = go.Figure(
        data=[
            go.Bar(
                x=rank_df["所属煤矿"],
                y=rank_df["产量(吨)"],
                text=rank_df["标签"],
                textposition="outside",
                cliponaxis=False,
                hovertemplate="%{x}<br>产量: %{y:.2f} 吨<extra></extra>",
            )
        ]
    )
    bar_fig.update_layout(
        xaxis_title="煤矿",
        yaxis_title="产量(吨)",
        margin=dict(l=20, r=20, t=20, b=20),
        colorway=list(_PLOT_COLORWAY),
    )
    bar_fig.update_traces(width=0.4)
    _lock_axes(bar_fig)

    trend_source_df = period_df.copy()
    if "备注" in trend_source_df.columns:
        trend_source_df["备注"] = trend_source_df["备注"].astype(str)
        trend_source_df = trend_source_df[
            ~trend_source_df["备注"].str.contains("补录|年初至", na=False)
        ]
    mine_daily = (
        trend_source_df.groupby(["生产日期", "所属煤矿"], as_index=False)["产量(吨)"]
        .sum()
        .sort_values("生产日期")
    )
    if mine_daily.empty:
        trend_fig = go.Figure()
        trend_fig.add_annotation(text="当前区间无日产量数据", x=0.5, y=0.5, showarrow=False)
        _lock_axes(trend_fig)
    else:
        mine_daily_pivot = mine_daily.pivot(
            index="生产日期", columns="所属煤矿", values="产量(吨)"
        ).fillna(0)
        mine_daily_pivot.index = pd.to_datetime(mine_daily_pivot.index).strftime("%m-%d")
        trend_fig = go.Figure()
        for mine_name in mine_daily_pivot.columns:
            s = mine_daily_pivot[mine_name]
            xs = s.index.tolist()
            ys = s.values
            text_vals = [f"{float(v):.1f}" for v in ys]
            trend_fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=ys,
                    name=mine_name,
                    mode="lines+markers+text",
                    text=text_vals,
                    textposition="top center",
                    textfont=dict(size=9),
                    line=dict(width=2.4),
                    marker=dict(size=6),
                    hovertemplate="%{x}<br>%{fullData.name}: %{y:.2f} 吨<extra></extra>",
                )
            )
        trend_fig.update_layout(
            xaxis_title="日期",
            yaxis_title="产量(吨)",
            margin=dict(l=20, r=20, t=20, b=20),
            legend_title_text="煤矿",
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
            colorway=list(_PLOT_COLORWAY),
        )
        _lock_axes(trend_fig)

    return {
        "empty": False,
        "summary_html": table_html,
        "caption": cap,
        "period_caption": prange,
        "kpis": kpis,
        "pie_html": _fig_to_html(pie_fig),
        "bar_html": _fig_to_html(bar_fig),
        "trend_html": _fig_to_html(trend_fig),
        **period_meta,
    }
