# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
# 本文件为「云煤矿业产销量管理系统」的组成部分。
# 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
# 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE。
import os
import shutil
from datetime import date

import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from app.config import get_settings
from app.storage import read_records
from app.timeutil import get_26day_statistical_month_label, get_26day_year_range, today_beijing

REMOVED_MINE_KEYWORDS = ("羊街", "竹麻地")
EXPORT_RETENTION_DAYS = 7


def get_statistical_year_start(target_dt: date) -> date:
    year_start, _ = get_26day_year_range(target_dt)
    return year_start


def set_cell_integer(ws, row, col, value):
    val = float(value) if pd.notna(value) else 0
    cell = ws.cell(row=row, column=col, value=val)
    cell.number_format = "0"


def _cleanup_old_exports(out_dir: str, keep_days: int = EXPORT_RETENTION_DAYS) -> None:
    """删除导出目录中超过保留天数的历史文件（按 mtime）。"""
    try:
        now_ts = today_beijing().timestamp()
    except Exception:
        return
    max_age_seconds = max(int(keep_days), 1) * 24 * 60 * 60
    for name in os.listdir(out_dir):
        p = os.path.join(out_dir, name)
        if not os.path.isfile(p):
            continue
        try:
            st = os.stat(p)
        except OSError:
            continue
        if now_ts - st.st_mtime > max_age_seconds:
            try:
                os.remove(p)
            except OSError:
                # 清理失败不影响主流程
                pass


def _merge_notes(series: pd.Series) -> str:
    if series is None or series.empty:
        return ""
    out: list[str] = []
    seen: set[str] = set()
    for raw in series.tolist():
        s = str(raw or "").strip()
        if not s or s.lower() == "nan":
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return "；".join(out)


MONTHLY_PLAN_BY_MINE = {
    "郭家山煤矿": 300000,
    "姚家村煤矿": 250000,
    "金所煤矿": 200000,
    "芒东二矿": 180000,
    "胜利煤矿": 150000,
    "竜浪煤矿": 120000,
    "双河煤矿": 100000,
}


def generate_sjcl_report(target_date) -> tuple[str | None, str]:
    s = get_settings()
    TEMPLATE_SJCL = s.sjcl_template_v2
    ACTUAL_FILE = s.actual_production_path

    if not os.path.exists(TEMPLATE_SJCL):
        return None, f"未找到实际产量模板：{TEMPLATE_SJCL}"

    try:
        df = read_records(ACTUAL_FILE)
        if df.empty:
            return None, "暂无实际产量数据"
        df["生产日期"] = pd.to_datetime(df["生产日期"]).dt.date
        df["所属煤矿"] = df["所属煤矿"].astype(str)
        df = df[~df["所属煤矿"].str.contains("|".join(REMOVED_MINE_KEYWORDS), na=False)].copy()
        target_dt = pd.to_datetime(target_date).date()

        out_dir = os.path.join(s.data_dir, "exports")
        os.makedirs(out_dir, exist_ok=True)
        _cleanup_old_exports(out_dir)
        date_str = today_beijing().strftime("%m.%d").lstrip("0").replace(".0", ".")
        output_fn = os.path.join(out_dir, f"云煤矿业原煤实际产量统计表（{date_str}）.xlsx")

        shutil.copy(TEMPLATE_SJCL, output_fn)
        wb = load_workbook(output_fn, read_only=False, keep_links=True)
        ws = wb.active

        ws["G1"] = f"填报日期：{today_beijing().strftime('%Y年%m月%d日')}"

        SJCL_MAP = {"郭家山煤矿": 4, "姚家村煤矿": 5, "金所煤矿": 6, "芒东二矿": 7, "胜利煤矿": 8, "竜浪煤矿": 9, "双河煤矿": 10}
        year_start = get_statistical_year_start(target_dt)

        for mine, row in SJCL_MAP.items():
            mine_df = df[df["所属煤矿"].str.startswith(mine, na=False)]

            d_val = mine_df[mine_df["生产日期"] == target_dt]["产量(吨)"].sum()
            set_cell_integer(ws, row, 4, d_val)

            y_val = mine_df[(mine_df["生产日期"] >= year_start) & (mine_df["生产日期"] <= target_dt)]["产量(吨)"].sum()
            set_cell_integer(ws, row, 6, y_val)

            mine_day_df = mine_df[mine_df["生产日期"] == target_dt]
            note_text = _merge_notes(mine_day_df["备注"]) if "备注" in mine_day_df.columns else ""
            ws.cell(row=row, column=7, value=note_text)

        wb.save(output_fn)
        return output_fn, "实际产量报表生成成功"
    except Exception as e:
        return None, f"出错: {e!s}"


def generate_nybb_report(target_date) -> tuple[str | None, str]:
    s = get_settings()
    TEMPLATE_NYBB = s.nybb_template
    ENERGY_FILE = s.energy_reporting_path

    if not os.path.exists(TEMPLATE_NYBB):
        return None, f"未找到能源局模板：{TEMPLATE_NYBB}"

    try:
        df = read_records(ENERGY_FILE)
        if df.empty:
            return None, "暂无能源局产销量填报数据"
        df["生产日期"] = pd.to_datetime(df["生产日期"]).dt.date
        df["所属煤矿"] = df["所属煤矿"].astype(str)
        df = df[~df["所属煤矿"].str.contains("|".join(REMOVED_MINE_KEYWORDS), na=False)].copy()
        target_dt = pd.to_datetime(target_date).date()

        out_dir = os.path.join(s.data_dir, "exports")
        os.makedirs(out_dir, exist_ok=True)
        _cleanup_old_exports(out_dir)
        today_str = today_beijing().strftime("%m.%d").lstrip("0").replace(".0", ".")
        output_fn = os.path.join(
            out_dir, f"{target_dt.year}年云煤矿业煤炭产量、销量、流向日报表（{today_str}）.xlsx"
        )

        shutil.copy(TEMPLATE_NYBB, output_fn)
        wb = load_workbook(output_fn)
        ws = wb.active

        ws["R2"] = f"日期：{target_dt.strftime('%Y年%m月%d日')}"

        NYBB_MAP = {"郭家山": 5, "姚家村": 6, "金所": 7, "芒东二矿": 8, "胜利": 9, "竜浪": 10}
        current_stat_month = get_26day_statistical_month_label(target_dt)
        year_start = get_statistical_year_start(target_dt)

        for mine, row in NYBB_MAP.items():
            mine_df = df[df["所属煤矿"].str.startswith(mine, na=False)].copy()
            mine_df["统计月"] = mine_df["生产日期"].apply(get_26day_statistical_month_label)

            set_cell_integer(ws, row, 5, mine_df[mine_df["生产日期"] == target_dt]["产量(吨)"].sum())
            set_cell_integer(ws, row, 7, mine_df[mine_df["生产日期"] == target_dt]["销量(吨)"].sum())

            r_val = mine_df[(mine_df["统计月"] == current_stat_month) & (mine_df["生产日期"] <= target_dt)]["产量(吨)"].sum()
            set_cell_integer(ws, row, 18, r_val)

            s_val = mine_df[(mine_df["生产日期"] >= year_start) & (mine_df["生产日期"] <= target_dt)]["产量(吨)"].sum()
            set_cell_integer(ws, row, 19, s_val)

            u_val = mine_df[(mine_df["统计月"] == current_stat_month) & (mine_df["生产日期"] <= target_dt)]["销量(吨)"].sum()
            set_cell_integer(ws, row, 21, u_val)

        sum_cols = [5, 7, 18, 19, 21]
        for c in sum_cols:
            col_let = get_column_letter(c)
            cell = ws.cell(row=11, column=c, value=f"=SUM({col_let}5:{col_let}10)")
            cell.number_format = "0"

        wb.save(output_fn)
        return output_fn, "能源局报表生成成功"
    except Exception as e:
        return None, f"出错: {e!s}"
