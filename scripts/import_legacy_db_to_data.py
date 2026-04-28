"""
将原项目 PostgreSQL 中的台账数据导入本项目「Excel 存盘」或「目标库」中的同名表。

方式一（无数据库连接）：解析 database_backup/ 下 pg_dump 导出的单条 INSERT 语句
方式二：设置 SOURCE_DATABASE_URL 从旧库只读两表，写入本机 data/ 的 xlsx
方式三：同时设置 TARGET_DATABASE_URL 时，在写入 xlsx 之外再 to_sql 到目标库

用法（在项目根 ymky_manager 下）:
  python scripts/import_legacy_db_to_data.py
  set SOURCE_DATABASE_URL=postgresql+psycopg2://...  && python scripts/import_legacy_db_to_data.py
  python scripts/import_legacy_db_to_data.py --backup-dir my_backup
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# 包根目录 = 本脚本父级的父级
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

import pandas as pd
from sqlalchemy import create_engine, text

import app.storage as st

from app.config import get_settings


def _find_matching_open_paren(s: str, close_idx: int) -> int:
    """在忽略双引号内字符的前提下，与 close_idx 处的 `)` 配对的 `(` 下标。"""
    if close_idx < 0 or close_idx >= len(s) or s[close_idx] != ")":
        raise ValueError("close_idx 须指向 `)`")
    depth = 0
    in_dq = False
    j = close_idx
    while j >= 0:
        c = s[j]
        if in_dq:
            if c == '"':
                in_dq = False
            j -= 1
            continue
        if c == '"':
            in_dq = True
            j -= 1
            continue
        if c == ")":
            depth += 1
        elif c == "(":
            depth -= 1
            if depth == 0:
                return j
        j -= 1
    raise ValueError("列名括号不匹配")


def _parse_columns_and_values(text: str) -> tuple[list[str], str]:
    t = text.strip()
    m = re.split(r"\bVALUES\b", t, maxsplit=1, flags=re.IGNORECASE)
    if len(m) != 2:
        raise ValueError("未找到 VALUES 子句")
    head, val_blob = m[0], m[1]
    h = head.rstrip()
    if not h.endswith(")"):
        raise ValueError("VALUES 前预期出现列名列表的 `)`")
    close_p = h.rindex(")")
    open_p = _find_matching_open_paren(h, close_p)
    col_blob = h[open_p + 1 : close_p]
    cols = re.findall(r'"([^"]+)"', col_blob)
    if not cols:
        raise ValueError("无法解析列名")
    rest = val_blob.strip().rstrip(";").strip()
    return cols, rest


def _split_top_level_tuples(s: str) -> list[str]:
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        while i < n and s[i] in " \t\n\r,":
            i += 1
        if i >= n:
            break
        if s[i] != "(":
            raise ValueError(f"VALUES 处预期 '('，实得 {s[i: i + 20]!r}")
        depth = 0
        in_str = False
        j = i
        while j < n:
            c = s[j]
            if in_str:
                if c == "'":
                    if j + 1 < n and s[j + 1] == "'":
                        j += 2
                    else:
                        in_str = False
                        j += 1
                else:
                    j += 1
                continue
            if c == "'":
                in_str = True
                j += 1
                continue
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    out.append(s[i + 1 : j])
                    j += 1
                    break
            j += 1
        i = j
    return out


def _split_row_fields(row: str) -> list[str]:
    out: list[str] = []
    i = 0
    n = len(row)
    cur: list[str] = []
    in_str = False
    while i < n:
        c = row[i]
        if in_str:
            if c == "'":
                if i + 1 < n and row[i + 1] == "'":
                    cur.append("'")
                    i += 2
                else:
                    in_str = False
                    i += 1
                continue
            cur.append(c)
            i += 1
            continue
        if c == "'":
            in_str = True
            i += 1
            continue
        if c == ",":
            out.append("".join(cur).strip())
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    if cur or (not cur and not out and row.strip() == ""):
        t = "".join(cur).strip()
        if t or out:
            out.append(t)
    return out


def _parse_cell(raw: str) -> object:
    s = raw.strip()
    if s.lower() == "null" or s == "":
        return None
    if s.startswith("'") and s.endswith("'"):
        inner = s[1:-1].replace("''", "'")
        return inner
    if re.match(r"^-?[\d]+(\.[\d]+)?([eE][+-]?\d+)?$", s):
        if "." in s or "e" in s.lower():
            return float(s)
        return int(s)
    return s


def parse_pg_insert_file(path: Path) -> pd.DataFrame:
    text = path.read_text(encoding="utf-8")
    return parse_pg_insert_text(text, source=str(path))


def parse_pg_insert_text(text: str, source: str = "内存") -> pd.DataFrame:
    cols, rest = _parse_columns_and_values(text)
    tuples = _split_top_level_tuples(rest)
    rows: list[list[object]] = []
    for tup in tuples:
        fields = _split_row_fields(tup)
        if len(fields) != len(cols):
            raise ValueError(
                f"{source}: 行字段数 {len(fields)} 与列数 {len(cols)} 不一致: {tup[:120]!r}..."
            )
        rows.append([_parse_cell(f) for f in fields])
    return pd.DataFrame(rows, columns=cols)


def read_tables_from_postgres(url: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    eng = create_engine(url, pool_pre_ping=True)
    with eng.connect() as c:
        c.execute(text("SELECT 1"))
    a = pd.read_sql_query(text('SELECT * FROM "actual_production"'), eng)
    b = pd.read_sql_query(text('SELECT * FROM "energy_reporting"'), eng)
    return a, b


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--backup-dir",
        type=Path,
        default=_ROOT / "database_backup",
        help="含 actual_production_rows.sql / energy_reporting_rows.sql 的目录",
    )
    ap.add_argument(
        "--source-db",
        help="从 PostgreSQL 拉取两表，覆盖参数（也可用环境变量 SOURCE_DATABASE_URL）",
    )
    ap.add_argument(
        "--target-db",
        help="将结果写入此连接串下的同名表（if_exists=replace），也可用环境变量 TARGET_DATABASE_URL",
    )
    args = ap.parse_args()
    get_settings()  # 加载 .env，确定 data/ 路径

    src = args.source_db or os.getenv("SOURCE_DATABASE_URL", "").strip()
    if src:
        print("从数据库读取: actual_production, energy_reporting")
        dfa, dfb = read_tables_from_postgres(src)
    else:
        f_act = args.backup_dir / "actual_production_rows.sql"
        f_en = args.backup_dir / "energy_reporting_rows.sql"
        if not f_act.is_file() or not f_en.is_file():
            ap.error(f"未找到 {f_act} 或 {f_en}，请用 --source-db 或把备份 SQL 放到 database_backup")
        dfa = parse_pg_insert_file(f_act)
        dfb = parse_pg_insert_file(f_en)
        print(f"从 SQL 文件解析: {f_act.name} {len(dfa)} 行, {f_en.name} {len(dfb)} 行")

    dfa = st._normalize_ledger_time_columns(dfa)  # noqa: SLF001
    dfb = st._normalize_ledger_time_columns(dfb)  # noqa: SLF001

    s2 = get_settings()
    p_act, p_en = s2.actual_production_path, s2.energy_reporting_path
    print(f"写入 actual_production -> {p_act} ({len(dfa)} 行)")
    st.overwrite_records(p_act, dfa)
    print(f"写入 energy_reporting -> {p_en} ({len(dfb)} 行)")
    st.overwrite_records(p_en, dfb)

    target = (args.target_db or os.getenv("TARGET_DATABASE_URL", "")).strip()
    if target:
        print(f"同时写入目标库: {target.split('@')[-1] if '@' in target else target}")
        e = create_engine(target, pool_pre_ping=True)
        dfa_t = st.reorder_ledger_dataframe_for_table("actual_production", dfa)
        dfb_t = st.reorder_ledger_dataframe_for_table("energy_reporting", dfb)
        dfa_t.to_sql("actual_production", e, if_exists="replace", index=False)
        dfb_t.to_sql("energy_reporting", e, if_exists="replace", index=False)

    print("完成。")


if __name__ == "__main__":
    main()
