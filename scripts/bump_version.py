#!/usr/bin/env python3
# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
"""
递增仓库根目录 VERSION（语义化 MAJOR.MINOR.PATCH）。

用法（在项目根）:
  python scripts/bump_version.py patch
  python scripts/bump_version.py minor
  python scripts/bump_version.py major
  python scripts/bump_version.py --set 2.0.0

随后在 CHANGELOG.md 增加对应章节并提交推送。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

_SEMVER_CORE = re.compile(r"^\s*v?(\d+)\.(\d+)\.(\d+)(.*)\s*$")


def read_version_bytes() -> str:
    path = _ROOT / "VERSION"
    raw = path.read_text(encoding="utf-8").strip("\n\r")
    if not raw.strip():
        print("VERSION 为空", file=sys.stderr)
        sys.exit(1)
    return raw.strip()


def write_version(s: str) -> None:
    path = _ROOT / "VERSION"
    path.write_text(s.strip() + "\n", encoding="utf-8", newline="\n")


def bump(part: str) -> str:
    line = read_version_bytes()
    m = _SEMVER_CORE.match(line)
    if not m:
        print(f"无法解析 VERSION: {line!r}（期望如 1.2.3 或 v1.2.3）", file=sys.stderr)
        sys.exit(1)
    maj, mn, pt, suf = int(m.group(1)), int(m.group(2)), int(m.group(3)), (m.group(4) or "")
    if suf.strip():
        print("警告：VERSION 含有预发布后缀，仍会按三段式整数递增", file=sys.stderr)
        suf = ""
    if part == "major":
        maj, mn, pt = maj + 1, 0, 0
    elif part == "minor":
        mn, pt = mn + 1, 0
    else:
        pt = pt + 1
    return f"{maj}.{mn}.{pt}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    mx = ap.add_mutually_exclusive_group(required=True)
    mx.add_argument("part", nargs="?", choices=("patch", "minor", "major"), help="递增部位")
    mx.add_argument("--set", metavar="SEMVER", help="设为指定版本（可带或不带 v 前缀）")
    args = ap.parse_args()

    if args.set is not None:
        s = args.set.strip()
        mm = _SEMVER_CORE.match(s)
        if not mm:
            print(f"非法版本字符串: {s!r}", file=sys.stderr)
            sys.exit(1)
        newv = f"{int(mm.group(1))}.{int(mm.group(2))}.{int(mm.group(3))}"
    else:
        newv = bump(args.part)

    write_version(newv)
    print(f"VERSION → {newv}")
    print("下一步：编辑 CHANGELOG.md 添加 ## [vx.y.z] 条目后再 git commit。")


if __name__ == "__main__":
    main()
