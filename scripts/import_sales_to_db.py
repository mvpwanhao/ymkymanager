"""
将本地 data/actual_sales.xlsx 中的销量台账数据导入到部署环境的 PostgreSQL 数据库。

脚本本身不含任何业务数据，可安全纳入版本控制。
数据来源是运行此脚本所在机器上的 Excel 文件，不会从仓库读取数据。

用法（在项目根 ymky_manager 下）:

  方式一：通过环境变量指定目标库
    set TARGET_DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname
    python scripts/import_sales_to_db.py

  方式二：通过命令行参数指定目标库
    python scripts/import_sales_to_db.py --target-db "postgresql+psycopg2://user:pass@host:5432/dbname"

  方式三：在部署服务器上运行（DATABASE_URL 已在 .env 中配置）
    python scripts/import_sales_to_db.py

  选项：
    --mode replace   整表覆写（默认，适合首次导入或完全同步）
    --mode upsert    按「煤矿+周区间」去重后合并（保留目标库中已有但本地不存在的记录）
    --dry-run        仅预览将要导入的数据，不实际写入
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

import pandas as pd
from sqlalchemy import create_engine, inspect, text

import app.storage as st
from app.config import get_settings


SYNC_KEY_COLS = ["所属煤矿", "周起始日期", "周结束日期"]


def _load_local_excel(excel_path: str) -> pd.DataFrame:
    """读取本地 actual_sales.xlsx 并规范列顺序。"""
    if not os.path.exists(excel_path):
        print(f"[错误] 本地 Excel 文件不存在: {excel_path}")
        sys.exit(1)
    df = pd.read_excel(excel_path)
    if df.empty:
        print(f"[错误] 本地 Excel 文件为空: {excel_path}")
        sys.exit(1)
    df = st._normalize_ledger_time_columns(df)
    df = st.reorder_ledger_dataframe_for_table("actual_sales", df)
    return df


def _ensure_table(engine, df: pd.DataFrame) -> None:
    """确保目标库中 actual_sales 表存在且列完整。"""
    inspector = inspect(engine)
    if not inspector.has_table("actual_sales"):
        print("[信息] 目标库中不存在 actual_sales 表，将自动创建")
        df.head(0).to_sql("actual_sales", engine, if_exists="append", index=False)
        print("[信息] 表已创建")
        return
    st._sync_table_columns(engine, "actual_sales", df)
    print("[信息] 目标表列结构已检查/同步")


def _mode_replace(engine, df: pd.DataFrame) -> None:
    """整表覆写：用本地数据完全替换目标库中的 actual_sales 表。"""
    df.to_sql("actual_sales", engine, if_exists="replace", index=False)
    print(f"[完成] 整表覆写完成，共写入 {len(df)} 行")


def _mode_upsert(engine, df_local: pd.DataFrame) -> None:
    """按「煤矿+周区间」去重合并：
    - 本地有、目标库也有的记录 → 用本地数据覆盖目标库中的同键记录
    - 本地有、目标库没有的记录 → 追加
    - 目标库有、本地没有的记录 → 保留不动
    """
    db_df = pd.read_sql_query(text('SELECT * FROM "actual_sales"'), engine)

    for c in SYNC_KEY_COLS:
        if c in df_local.columns:
            df_local[c] = df_local[c].astype(str).str.strip()
        if c in db_df.columns:
            db_df[c] = db_df[c].astype(str).str.strip()

    if not db_df.empty:
        merged = df_local.merge(
            db_df[SYNC_KEY_COLS].drop_duplicates(),
            on=SYNC_KEY_COLS,
            how="left",
            indicator=True,
        )
        new_rows = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])

        overlap_keys = df_local.merge(
            db_df[SYNC_KEY_COLS].drop_duplicates(),
            on=SYNC_KEY_COLS,
            how="inner",
        )

        if not overlap_keys.empty:
            print(f"[信息] 目标库中已有同键记录 {len(overlap_keys)} 行，将先删除再写入")
            for _, row in overlap_keys.iterrows():
                conditions = " AND ".join(
                    [f'"{c}" = \'{row[c]}\'' for c in SYNC_KEY_COLS]
                )
                with engine.begin() as conn:
                    conn.execute(
                        text(f'DELETE FROM "actual_sales" WHERE {conditions}')
                    )

        if not new_rows.empty:
            drop_cols = [
                c for c in new_rows.columns if c not in db_df.columns
            ]
            if drop_cols:
                new_rows = new_rows.drop(columns=drop_cols)
            print(f"[信息] 追加新记录 {len(new_rows)} 行")
            new_rows.to_sql("actual_sales", engine, if_exists="append", index=False)
    else:
        df_local.to_sql("actual_sales", engine, if_exists="append", index=False)

    print(f"[完成] 合并写入完成，本次处理 {len(df_local)} 行")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="将本地 actual_sales.xlsx 导入到部署环境的 PostgreSQL 数据库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--target-db",
        help="目标数据库连接串（也可用环境变量 TARGET_DATABASE_URL 或 DATABASE_URL）",
    )
    ap.add_argument(
        "--mode",
        choices=["replace", "upsert"],
        default="replace",
        help="replace=整表覆写(默认); upsert=按煤矿+周区间去重合并",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览数据，不实际写入",
    )
    args = ap.parse_args()

    get_settings()
    s = get_settings()
    excel_path = s.actual_sales_path

    target_url = (
        args.target_db
        or os.getenv("TARGET_DATABASE_URL", "").strip()
        or os.getenv("DATABASE_URL", "").strip()
    )
    if not target_url:
        print("[错误] 未指定目标数据库。请设置 TARGET_DATABASE_URL 或 DATABASE_URL 环境变量，或使用 --target-db 参数")
        sys.exit(1)

    print(f"[1/4] 读取本地 Excel: {excel_path}")
    df = _load_local_excel(excel_path)
    print(f"      共 {len(df)} 行，列: {list(df.columns)}")
    print(f"      煤矿分布:")
    for mine, count in df["所属煤矿"].value_counts().items():
        print(f"        {mine}: {count} 行")
    print(f"      周区间: {df['周起始日期'].min()} ~ {df['周结束日期'].max()}")

    if args.dry_run:
        print("\n[预览模式] 以下为将要导入的数据（不实际写入）:")
        print(df.to_string(index=False))
        print(f"\n[预览] 模式: {args.mode}, 目标库: {target_url.split('@')[-1] if '@' in target_url else target_url}")
        return

    print(f"\n[2/4] 连接目标数据库: {target_url.split('@')[-1] if '@' in target_url else target_url}")
    engine = create_engine(target_url, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("      连接成功")

    print(f"\n[3/4] 检查目标表结构")
    _ensure_table(engine, df)

    print(f"\n[4/4] 写入数据 (模式: {args.mode})")
    if args.mode == "replace":
        _mode_replace(engine, df)
    else:
        _mode_upsert(engine, df)

    verify_df = pd.read_sql_query(text('SELECT * FROM "actual_sales"'), engine)
    print(f"\n[验证] 目标库 actual_sales 表现有 {len(verify_df)} 行")
    if not verify_df.empty:
        print(f"       煤矿分布:")
        for mine, count in verify_df["所属煤矿"].value_counts().items():
            print(f"         {mine}: {count} 行")

    print("\n导入完成。")


if __name__ == "__main__":
    main()
