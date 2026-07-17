# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
"""pytest 共享配置与 fixtures。"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
