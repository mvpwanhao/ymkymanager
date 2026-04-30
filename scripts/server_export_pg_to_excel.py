#!/usr/bin/env python3
"""
在项目根 ymky_manager 下执行（通常在服务器）：从 .env 的 DATABASE_URL 连接 PostgreSQL，
将 actual_production / energy_reporting 导出到本仓库 data/*.xlsx。

说明：本机配置了 DATABASE_URL 时，overwrite_records 只写数据库不写 Excel，
故子进程中临时清空 DATABASE_URL，仅以 --source-db 读库并落地 xlsx（不改动线上库）。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    env_path = _ROOT / ".env"
    if not env_path.is_file():
        print("no .env", file=sys.stderr)
        sys.exit(1)
    db = ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("#") or "=" not in s:
            continue
        key, _, val = s.partition("=")
        if key.strip() == "DATABASE_URL":
            db = val.strip().strip('"').strip("'")
            break
    if not db:
        print("no DATABASE_URL in .env", file=sys.stderr)
        sys.exit(1)
    os.chdir(_ROOT)
    env = os.environ.copy()
    env["DATABASE_URL"] = ""
    r = subprocess.run(
        [
            sys.executable,
            str(_ROOT / "scripts" / "import_legacy_db_to_data.py"),
            "--source-db",
            db,
        ],
        cwd=str(_ROOT),
        env=env,
        check=False,
    )
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
