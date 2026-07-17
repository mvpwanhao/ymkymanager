# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
"""健康检查与诊断路由。"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.release_version import health_version
from app.storage import has_pending_sync, read_records, storage_uses_database

router = APIRouter()


@router.get("/health")
def health() -> JSONResponse:
    s2 = get_settings()
    body: dict[str, object] = {"ok": True, "db": storage_uses_database()}
    v = health_version(s2.app_version or "")
    if v:
        body["version"] = v
    return JSONResponse(
        body,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


@router.get("/health/diag")
def health_diag() -> JSONResponse:
    """诊断端点：返回各表记录数与日期范围，用于排查数据丢失问题。"""
    s2 = get_settings()
    diag: dict[str, object] = {
        "db_connected": storage_uses_database(),
        "pending_sync": has_pending_sync(),
    }
    for label, path in [("actual", s2.actual_production_path), ("energy", s2.energy_reporting_path)]:
        try:
            df = read_records(path)
            info: dict[str, object] = {"rows": len(df)}
            if not df.empty and "生产日期" in df.columns:
                dates = pd.to_datetime(df["生产日期"], errors="coerce").dropna()
                if not dates.empty:
                    info["date_min"] = str(dates.min().date())
                    info["date_max"] = str(dates.max().date())
            diag[label] = info
        except Exception as exc:
            diag[label] = {"error": str(exc)}
    return JSONResponse(
        diag,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )
