# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
# 本文件为「云煤矿业产销量管理系统」的组成部分。
# 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
# 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE。
import logging
import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from app.timeutil import TZ_BEIJING

_log = logging.getLogger("ymky.storage")

_ENGINE: Optional[Engine] = None
_ENGINE_READY = False
_ENGINE_LAST_ATTEMPT: float = 0.0
_ENGINE_RETRY_INTERVAL: float = 30.0
_PENDING_SYNC = False


def _pending_sync_file() -> str:
    """返回持久化标记文件路径（data/runtime/pending_sync.flag）。"""
    from app.config import get_settings
    s = get_settings()
    d = s.runtime_dir
    return str(d / "pending_sync.flag")


def _set_pending_sync(value: bool) -> None:
    """原子地更新内存标记并同步到磁盘文件，确保容器重启后不丢失。"""
    global _PENDING_SYNC
    _PENDING_SYNC = value
    try:
        flag_path = _pending_sync_file()
        if value:
            os.makedirs(os.path.dirname(flag_path) or ".", exist_ok=True)
            Path(flag_path).touch()
            _log.info("pending_sync 标记已持久化到 %s", flag_path)
        else:
            if os.path.exists(flag_path):
                os.remove(flag_path)
                _log.info("pending_sync 标记文件已清除")
    except Exception as exc:
        _log.warning("pending_sync 标记文件操作失败（不影响内存状态）: %s", exc, exc_info=True)


def _restore_pending_sync() -> None:
    """模块加载时从磁盘恢复 _PENDING_SYNC 状态。"""
    global _PENDING_SYNC
    try:
        if os.path.exists(_pending_sync_file()):
            _PENDING_SYNC = True
            _log.info("从磁盘恢复 pending_sync = True（上次容器运行期间有未同步数据）")
    except Exception:
        pass  # 首次运行时 data/runtime 可能不存在，忽略


_restore_pending_sync()

FILE_TABLE_MAP = {
    "actual_production.xlsx": "actual_production",
    "energy_reporting.xlsx": "energy_reporting",
    "actual_sales.xlsx": "actual_sales",
}

# 两表列顺序与旧 Streamlit / PG 写库习惯一致
ACTUAL_PRODUCTION_WRITE_ORDER: tuple[str, ...] = (
    "提交时间",
    "所属煤矿",
    "生产日期",
    "产量(吨)",
    "填报人",
    "备注",
)
# 读入时追加列（老表/补报）
ACTUAL_PRODUCTION_READ_EXTRA: tuple[str, ...] = ("年度总产量(吨)",)
ENERGY_REPORTING_WRITE_ORDER: tuple[str, ...] = (
    "报送时间",
    "所属煤矿",
    "生产日期",
    "产量(吨)",
    "销量(吨)",
    "填报人",
    "备注",
)
# energy 读入时可能多「提交时间」列；新写入行不含该列
ENERGY_REPORTING_READ_EXTRA: tuple[str, ...] = ("提交时间",)

# 实际销量台账（周频填报）
ACTUAL_SALES_WRITE_ORDER: tuple[str, ...] = (
    "填报时间",
    "所属煤矿",
    "周起始日期",
    "周结束日期",
    "销量(吨)",
    "月累计自产煤销量(吨)",
    "年累计自产煤销量(吨)",
    "年累计掺配煤销量(吨)",
    "年累计外购煤量(吨)",
    "填报人",
    "备注",
)


def reorder_ledger_dataframe_for_table(table_name: str, df: pd.DataFrame) -> pd.DataFrame:
    """统一列顺序：与老项目 to_excel / to_sql 习惯一致，避免 SELECT * 与 Excel 导出的列序不一致。"""
    if df.empty:
        return df
    if table_name == "actual_production":
        first = [c for c in ACTUAL_PRODUCTION_WRITE_ORDER if c in df.columns]
        extra = [c for c in ACTUAL_PRODUCTION_READ_EXTRA if c in df.columns and c not in first]
    elif table_name == "energy_reporting":
        first = [c for c in ENERGY_REPORTING_WRITE_ORDER if c in df.columns]
        extra = [c for c in ENERGY_REPORTING_READ_EXTRA if c in df.columns and c not in first]
    elif table_name == "actual_sales":
        first = [c for c in ACTUAL_SALES_WRITE_ORDER if c in df.columns]
        extra = []
    else:
        return df
    rest = [c for c in df.columns if c not in first + extra]
    return df[first + extra + rest].copy()


def dataframe_actual_production_new_row(
    *,
    submit_time: str,
    mine: str,
    prod_date: str,
    production_t: float,
    reporter: str,
    note: str,
) -> pd.DataFrame:
    """构造一行实际产量台账，列名/顺序与旧版 Streamlit 写库/写 Excel 一致。"""
    return pd.DataFrame(
        [
            {
                "提交时间": submit_time,
                "所属煤矿": mine,
                "生产日期": prod_date,
                "产量(吨)": production_t,
                "填报人": reporter,
                "备注": note,
            }
        ],
        columns=list(ACTUAL_PRODUCTION_WRITE_ORDER),
    )


def dataframe_energy_reporting_new_row(
    *,
    report_time: str,
    mine: str,
    prod_date: str,
    production_t: float,
    sales_t: float,
    reporter: str,
    note: str,
) -> pd.DataFrame:
    """构造一行能源局产销量台账，列名/顺序与旧版一致（不含仅历史库中存在的 `提交时间` 列，追加时由库中留空）。"""
    return pd.DataFrame(
        [
            {
                "报送时间": report_time,
                "所属煤矿": mine,
                "生产日期": prod_date,
                "产量(吨)": production_t,
                "销量(吨)": sales_t,
                "填报人": reporter,
                "备注": note,
            }
        ],
        columns=list(ENERGY_REPORTING_WRITE_ORDER),
    )


def dataframe_actual_sales_new_row(
    *,
    submit_time: str,
    mine: str,
    week_start: str,
    week_end: str,
    sales_t: float,
    reporter: str,
    note: str,
    month_cumul: float = 0.0,
    year_cumul: float = 0.0,
    year_blended: float = 0.0,
    year_purchased: float = 0.0,
) -> pd.DataFrame:
    """构造一行实际销量台账（周频填报）。"""
    return pd.DataFrame(
        [
            {
                "填报时间": submit_time,
                "所属煤矿": mine,
                "周起始日期": week_start,
                "周结束日期": week_end,
                "销量(吨)": sales_t,
                "月累计自产煤销量(吨)": month_cumul,
                "年累计自产煤销量(吨)": year_cumul,
                "年累计掺配煤销量(吨)": year_blended,
                "年累计外购煤量(吨)": year_purchased,
                "填报人": reporter,
                "备注": note,
            }
        ],
        columns=list(ACTUAL_SALES_WRITE_ORDER),
    )


def _get_engine() -> Optional[Engine]:
    global _ENGINE, _ENGINE_READY, _ENGINE_LAST_ATTEMPT

    if _ENGINE_READY and _ENGINE is not None:
        return _ENGINE

    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        _ENGINE_READY = True
        _ENGINE = None
        return None

    now = time.monotonic()
    if _ENGINE_READY and _ENGINE is None:
        if now - _ENGINE_LAST_ATTEMPT < _ENGINE_RETRY_INTERVAL:
            return None

    was_disconnected = _ENGINE_READY and _ENGINE is None
    _ENGINE_LAST_ATTEMPT = now
    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        _ENGINE = engine
        _ENGINE_READY = True
        _log.info("数据库连接成功")
        if was_disconnected:
            _try_sync_pending(engine)
        return _ENGINE
    except Exception as exc:
        _log.error("数据库连接失败（%.0f 秒后重试）: %s", _ENGINE_RETRY_INTERVAL, exc, exc_info=True)
        _ENGINE = None
        _ENGINE_READY = True
        return None


def storage_uses_database() -> bool:
    return _get_engine() is not None


def _table_name(file_path: str) -> Optional[str]:
    return FILE_TABLE_MAP.get(os.path.basename(file_path))


def _infer_sql_type(series: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return "TIMESTAMP"
    if pd.api.types.is_integer_dtype(series):
        return "BIGINT"
    if pd.api.types.is_float_dtype(series):
        return "DOUBLE PRECISION"
    if pd.api.types.is_bool_dtype(series):
        return "BOOLEAN"
    return "TEXT"


def _normalize_ledger_time_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    for col in ("提交时间", "报送时间", "填报时间"):
        if col not in out.columns:
            continue

        norm_vals: list[object] = []
        for v in out[col]:
            if v is None or (isinstance(v, float) and pd.isna(v)) or (isinstance(v, str) and not v.strip()):
                norm_vals.append(v)
                continue
            t = pd.to_datetime(v, errors="coerce")
            if pd.isna(t):
                norm_vals.append(v)
                continue
            ts = t if isinstance(t, pd.Timestamp) else pd.Timestamp(t)
            if ts.tzinfo is not None:
                ts = ts.tz_convert(TZ_BEIJING)
            norm_vals.append(ts.strftime("%Y-%m-%d %H:%M"))
        out[col] = pd.Series(norm_vals, index=out.index, dtype=object)
    return out


def _sync_table_columns(engine: Engine, table_name: str, df: pd.DataFrame) -> None:
    inspector = inspect(engine)
    if not inspector.has_table(table_name):
        return

    existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
    with engine.begin() as conn:
        for col in df.columns:
            if col in existing_cols:
                continue
            sql_type = _infer_sql_type(df[col])
            conn.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{col}" {sql_type}'))


def _append_to_excel(file_path: str, df_new: pd.DataFrame, table_name: Optional[str] = None) -> None:
    """将 df_new 追加到 Excel 文件（write-through 镜像）。"""
    os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
    df_old = pd.read_excel(file_path) if os.path.exists(file_path) else pd.DataFrame()
    if table_name and not df_old.empty:
        df_old = reorder_ledger_dataframe_for_table(table_name, df_old)
    df_final = pd.concat([df_old, df_new], ignore_index=True)
    if table_name:
        df_final = reorder_ledger_dataframe_for_table(table_name, df_final)
    df_final.to_excel(file_path, index=False)


def _overwrite_excel(file_path: str, df: pd.DataFrame) -> None:
    """整体覆写 Excel 文件（write-through 镜像）。"""
    os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
    df.to_excel(file_path, index=False)


def _sync_key_cols(table_name: str) -> list[str]:
    """用于同步比对的联合键列。"""
    if table_name == "actual_production":
        return ["所属煤矿", "生产日期", "提交时间"]
    if table_name == "actual_sales":
        return ["所属煤矿", "周起始日期", "周结束日期"]
    return ["所属煤矿", "生产日期", "报送时间"]


def _try_sync_pending(engine: Engine) -> None:
    """DB 重连后，将 Excel 中存在但 DB 缺失的记录回灌到 DB。"""
    if not _PENDING_SYNC:
        return

    from app.config import get_settings
    s = get_settings()

    for xlsx_path, table_name in [
        (s.actual_production_path, "actual_production"),
        (s.energy_reporting_path, "energy_reporting"),
        (s.actual_sales_path, "actual_sales"),
    ]:
        if not os.path.exists(xlsx_path):
            continue
        try:
            excel_df = pd.read_excel(xlsx_path)
            if excel_df.empty:
                continue
            db_df = pd.read_sql_query(text(f'SELECT * FROM "{table_name}"'), engine)

            key_cols = _sync_key_cols(table_name)
            usable_keys = [c for c in key_cols if c in excel_df.columns and c in db_df.columns]
            if not usable_keys:
                continue

            for c in usable_keys:
                excel_df[c] = excel_df[c].astype(str).str.strip()
                db_df[c] = db_df[c].astype(str).str.strip()

            merged = excel_df.merge(db_df[usable_keys].drop_duplicates(), on=usable_keys, how="left", indicator=True)
            missing = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])

            if missing.empty:
                _log.info("sync [%s] 无缺失记录", table_name)
                continue

            drop_cols = [c for c in missing.columns if c not in db_df.columns]
            if drop_cols:
                missing = missing.drop(columns=drop_cols)
            missing.to_sql(table_name, engine, if_exists="append", index=False)
            _log.info("sync [%s] 已回灌 %d 条记录到 DB", table_name, len(missing))
        except Exception as exc:
            _log.error("sync [%s] 同步失败: %s", table_name, exc, exc_info=True)

    _set_pending_sync(False)
    _log.info("pending sync 已完成")


def has_pending_sync() -> bool:
    """供 /health/diag 端点查询是否有待同步数据。"""
    return _PENDING_SYNC


def read_records(file_path: str) -> pd.DataFrame:
    engine = _get_engine()
    table_name = _table_name(file_path)
    if engine is not None and table_name:
        try:
            raw = pd.read_sql_query(text(f'SELECT * FROM "{table_name}"'), engine)
            _log.info("read_records [DB] table=%s rows=%d", table_name, len(raw))
            return reorder_ledger_dataframe_for_table(table_name, raw)
        except Exception as exc:
            _log.error("read_records [DB] 查询失败 table=%s，降级读 Excel: %s", table_name, exc, exc_info=True)

    if not os.path.exists(file_path):
        _log.warning("read_records 文件不存在且 DB 不可用: %s", file_path)
        return pd.DataFrame()
    try:
        raw = pd.read_excel(file_path)
        _log.info("read_records [Excel fallback] file=%s rows=%d", file_path, len(raw))
        if table_name:
            return reorder_ledger_dataframe_for_table(table_name, raw)
        return raw
    except Exception as exc:
        _log.error("read_records [Excel] 读取失败 file=%s: %s", file_path, exc, exc_info=True)
        return pd.DataFrame()


def append_records(file_path: str, df_new: pd.DataFrame) -> None:
    df_new = _normalize_ledger_time_columns(df_new)
    engine = _get_engine()
    table_name = _table_name(file_path)
    if table_name:
        df_new = reorder_ledger_dataframe_for_table(table_name, df_new)

    db_ok = False
    if engine is not None and table_name:
        try:
            _sync_table_columns(engine, table_name, df_new)
            df_new.to_sql(table_name, engine, if_exists="append", index=False)
            db_ok = True
        except Exception as exc:
            _log.error("append_records [DB] 写入失败，数据仅存 Excel: %s", exc, exc_info=True)
            _set_pending_sync(True)

    if not db_ok and engine is None:
        _set_pending_sync(True)

    try:
        _append_to_excel(file_path, df_new, table_name)
    except Exception as exc:
        _log.error("append_records [Excel write-through] 写入失败: %s", exc, exc_info=True)
        if not db_ok:
            raise


def overwrite_records(file_path: str, df: pd.DataFrame) -> None:
    df = _normalize_ledger_time_columns(df)
    engine = _get_engine()
    table_name = _table_name(file_path)
    if table_name:
        df = reorder_ledger_dataframe_for_table(table_name, df)

    db_ok = False
    if engine is not None and table_name:
        try:
            _log.info("overwrite_records [DB] table=%s rows=%d", table_name, len(df))
            df.to_sql(table_name, engine, if_exists="replace", index=False)
            db_ok = True
        except Exception as exc:
            _log.error("overwrite_records [DB] 写入失败，数据仅存 Excel: %s", exc, exc_info=True)
            _set_pending_sync(True)

    if not db_ok and engine is None:
        _set_pending_sync(True)

    try:
        _log.info("overwrite_records [Excel write-through] file=%s rows=%d", file_path, len(df))
        _overwrite_excel(file_path, df)
    except Exception as exc:
        _log.error("overwrite_records [Excel write-through] 写入失败: %s", exc, exc_info=True)
        if not db_ok:
            raise


def _mask_mine_date(df: pd.DataFrame, mine: str, prod_date_iso: str) -> pd.Series:
    """构造「所属煤矿 == mine 且 生产日期 == prod_date_iso」的布尔 mask。

    生产日期支持字符串、datetime、date 等多种类型；将其规范化为日期再比较，
    避免 Excel 读出的 Timestamp 与字符串 ISO 比较失败。
    """
    if df.empty or "所属煤矿" not in df.columns or "生产日期" not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    target = pd.to_datetime(prod_date_iso, errors="coerce")
    if pd.isna(target):
        return pd.Series([False] * len(df), index=df.index)
    target_d = target.date()
    dates = pd.to_datetime(df["生产日期"], errors="coerce").dt.date
    return (df["所属煤矿"].astype(str).str.strip() == str(mine).strip()) & (dates == target_d)


def find_records_by_mine_date(file_path: str, mine: str, prod_date_iso: str) -> pd.DataFrame:
    """查找指定煤矿 + 生产日期的已有台账行（用于「重复填报检测」）。"""
    df = read_records(file_path)
    if df.empty:
        return df
    mask = _mask_mine_date(df, mine, prod_date_iso)
    return df.loc[mask].copy()


def _numeric_close(a: float, b: float, *, abs_tol: float = 0.02) -> bool:
    return abs(float(a) - float(b)) <= abs_tol + 1e-9


def verify_actual_submission_visible(
    file_path: str, mine: str, prod_date_iso: str, production_t: float
) -> bool:
    """提交后读回：同一煤矿·同一生产日期下是否存在与本次产量一致（容差吨）的记录。"""
    df = find_records_by_mine_date(file_path, mine, prod_date_iso)
    if df.empty or "产量(吨)" not in df.columns:
        return False
    nums = pd.to_numeric(df["产量(吨)"], errors="coerce")
    for v in nums:
        if pd.isna(v):
            continue
        if _numeric_close(float(v), production_t):
            return True
    return False


def verify_energy_submission_visible(
    file_path: str,
    mine: str,
    prod_date_iso: str,
    production_t: float,
    sales_t: float,
) -> bool:
    """提交后读回：同上，且产量、销量均与本次一致（同行的两列）。"""
    df = find_records_by_mine_date(file_path, mine, prod_date_iso)
    if df.empty:
        return False
    if "产量(吨)" not in df.columns or "销量(吨)" not in df.columns:
        return False
    for _, row in df.iterrows():
        p = pd.to_numeric(row.get("产量(吨)"), errors="coerce")
        s = pd.to_numeric(row.get("销量(吨)"), errors="coerce")
        if pd.isna(p) or pd.isna(s):
            continue
        if _numeric_close(float(p), production_t) and _numeric_close(float(s), sales_t):
            return True
    return False


def replace_records_for_mine_date(
    file_path: str, mine: str, prod_date_iso: str, df_new: pd.DataFrame
) -> int:
    """删除指定煤矿 + 生产日期的所有旧行后写入 df_new（覆盖式纠错）。

    返回被删除的旧行数。Excel 与 PostgreSQL 两种存储下表现一致，
    DB 模式下通过 to_sql(if_exists='replace') 整表重写，确保列序与 Excel 写入一致。
    """
    df = read_records(file_path)
    removed = 0
    if not df.empty:
        mask = _mask_mine_date(df, mine, prod_date_iso)
        removed = int(mask.sum())
        df = df.loc[~mask].copy()
    df_new = _normalize_ledger_time_columns(df_new)
    table_name = _table_name(file_path)
    if table_name:
        df_new = reorder_ledger_dataframe_for_table(table_name, df_new)
        if not df.empty:
            df = reorder_ledger_dataframe_for_table(table_name, df)
    df_final = pd.concat([df, df_new], ignore_index=True) if not df.empty else df_new
    overwrite_records(file_path, df_final)
    return removed


# ── 实际销量台账：按矿 + 周区间查重 / 覆写 ──────────────────────────

def _mask_mine_week(
    df: pd.DataFrame, mine: str, week_start_iso: str, week_end_iso: str
) -> pd.Series:
    """构造「所属煤矿 == mine 且 周起始日期 == week_start 且 周结束日期 == week_end」的布尔 mask。"""
    if (
        df.empty
        or "所属煤矿" not in df.columns
        or "周起始日期" not in df.columns
        or "周结束日期" not in df.columns
    ):
        return pd.Series([False] * len(df), index=df.index)
    ws = pd.to_datetime(week_start_iso, errors="coerce")
    we = pd.to_datetime(week_end_iso, errors="coerce")
    if pd.isna(ws) or pd.isna(we):
        return pd.Series([False] * len(df), index=df.index)
    ws_d = ws.date()
    we_d = we.date()
    dates_s = pd.to_datetime(df["周起始日期"], errors="coerce").dt.date
    dates_e = pd.to_datetime(df["周结束日期"], errors="coerce").dt.date
    return (
        (df["所属煤矿"].astype(str).str.strip() == str(mine).strip())
        & (dates_s == ws_d)
        & (dates_e == we_d)
    )


def find_sales_records_by_mine_week(
    file_path: str, mine: str, week_start_iso: str, week_end_iso: str
) -> pd.DataFrame:
    """查找指定煤矿 + 周区间的已有销量台账行（用于「重复填报检测」）。"""
    df = read_records(file_path)
    if df.empty:
        return df
    mask = _mask_mine_week(df, mine, week_start_iso, week_end_iso)
    return df.loc[mask].copy()


def verify_sales_submission_visible(
    file_path: str, mine: str, week_start_iso: str, week_end_iso: str, sales_t: float
) -> bool:
    """提交后读回：同一煤矿·同一周区间下是否存在与本次销量一致（容差吨）的记录。"""
    df = find_sales_records_by_mine_week(file_path, mine, week_start_iso, week_end_iso)
    if df.empty or "销量(吨)" not in df.columns:
        return False
    nums = pd.to_numeric(df["销量(吨)"], errors="coerce")
    for v in nums:
        if pd.isna(v):
            continue
        if _numeric_close(float(v), sales_t):
            return True
    return False


def replace_sales_records_for_mine_week(
    file_path: str,
    mine: str,
    week_start_iso: str,
    week_end_iso: str,
    df_new: pd.DataFrame,
) -> int:
    """删除指定煤矿 + 周区间的所有旧行后写入 df_new（覆盖式纠错）。返回被删除的旧行数。"""
    df = read_records(file_path)
    removed = 0
    if not df.empty:
        mask = _mask_mine_week(df, mine, week_start_iso, week_end_iso)
        removed = int(mask.sum())
        df = df.loc[~mask].copy()
    df_new = _normalize_ledger_time_columns(df_new)
    table_name = _table_name(file_path)
    if table_name:
        df_new = reorder_ledger_dataframe_for_table(table_name, df_new)
        if not df.empty:
            df = reorder_ledger_dataframe_for_table(table_name, df)
    df_final = pd.concat([df, df_new], ignore_index=True) if not df.empty else df_new
    overwrite_records(file_path, df_final)
    return removed
