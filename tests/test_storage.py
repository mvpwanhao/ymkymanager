# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
"""storage 单元测试：Excel 读写基础逻辑。"""

import os
import tempfile
from datetime import date

import pandas as pd
import pytest

from app.storage import read_records


class TestReadRecords:
    """read_records 基础读取。"""

    def test_read_nonexistent_file(self):
        """读取不存在的文件应返回空 DataFrame。"""
        result = read_records("/nonexistent/path/file.xlsx")
        assert result.empty

    def test_read_existing_file(self):
        """读取存在的 Excel 文件应返回 DataFrame。"""
        # 使用实际的台账文件
        from app.config import get_settings
        s = get_settings()
        if not os.path.exists(s.actual_production_path):
            pytest.skip("actual_production.xlsx not found")
        result = read_records(s.actual_production_path)
        assert isinstance(result, pd.DataFrame)

    def test_read_returns_dataframe(self):
        result = read_records("/nonexistent/file.xlsx")
        assert isinstance(result, pd.DataFrame)


class TestStorageUsesDatabase:
    """storage_uses_database 配置检测。"""

    def test_returns_bool(self):
        from app.storage import storage_uses_database
        result = storage_uses_database()
        assert isinstance(result, bool)


class TestPendingSyncPersistence:
    """_PENDING_SYNC 持久化标记：容器重启后应能恢复。"""

    def test_set_true_creates_flag_file(self, monkeypatch, tmp_path):
        """设置 _set_pending_sync(True) 应创建标记文件。"""
        import app.storage as st
        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir()
        monkeypatch.setattr(st, "_pending_sync_file", lambda: str(runtime_dir / "pending_sync.flag"))

        st._set_pending_sync(True)
        assert st._PENDING_SYNC is True
        assert os.path.exists(str(runtime_dir / "pending_sync.flag"))

        # 清理
        st._set_pending_sync(False)
        assert st._PENDING_SYNC is False
        assert not os.path.exists(str(runtime_dir / "pending_sync.flag"))

    def test_set_false_removes_flag_file(self, monkeypatch, tmp_path):
        """设置 _set_pending_sync(False) 应删除标记文件。"""
        import app.storage as st
        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir()
        flag = runtime_dir / "pending_sync.flag"
        flag.touch()
        monkeypatch.setattr(st, "_pending_sync_file", lambda: str(flag))

        st._PENDING_SYNC = True  # 模拟内存中已为 True
        st._set_pending_sync(False)
        assert st._PENDING_SYNC is False
        assert not flag.exists()

    def test_set_false_when_no_file(self, monkeypatch, tmp_path):
        """标记文件不存在时 _set_pending_sync(False) 不报错。"""
        import app.storage as st
        monkeypatch.setattr(st, "_pending_sync_file", lambda: str(tmp_path / "nonexistent.flag"))

        st._set_pending_sync(False)  # 不应抛异常
        assert st._PENDING_SYNC is False
