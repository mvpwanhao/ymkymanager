# Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
"""utils 单元测试：exclude_mines、content_disposition_attachment。"""

import pandas as pd

from app.utils import content_disposition_attachment, exclude_mines


class TestExcludeMines:
    def test_filters_yangjie(self):
        df = pd.DataFrame({"所属煤矿": ["郭家山煤矿", "羊街煤矿", "金所煤矿"]})
        result = exclude_mines(df)
        assert "羊街煤矿" not in result["所属煤矿"].values
        assert len(result) == 2

    def test_filters_zhumadi(self):
        df = pd.DataFrame({"所属煤矿": ["竹麻地煤矿", "姚家村煤矿"]})
        result = exclude_mines(df)
        assert "竹麻地煤矿" not in result["所属煤矿"].values
        assert len(result) == 1

    def test_empty_df(self):
        df = pd.DataFrame()
        result = exclude_mines(df)
        assert result.empty

    def test_no_mine_column(self):
        df = pd.DataFrame({"其他列": [1, 2, 3]})
        result = exclude_mines(df)
        assert len(result) == 3

    def test_all_kept(self):
        df = pd.DataFrame({"所属煤矿": ["郭家山煤矿", "姚家村煤矿", "金所煤矿"]})
        result = exclude_mines(df)
        assert len(result) == 3

    def test_na_handling(self):
        df = pd.DataFrame({"所属煤矿": ["郭家山煤矿", None, "羊街煤矿"]})
        result = exclude_mines(df)
        assert "羊街煤矿" not in result["所属煤矿"].values


class TestContentDisposition:
    def test_ascii_filename(self):
        result = content_disposition_attachment("report.xlsx", "report.xlsx")
        assert 'filename="report.xlsx"' in result

    def test_chinese_filename(self):
        result = content_disposition_attachment(
            "ymky_report.xlsx", "云煤矿业报表.xlsx"
        )
        assert "filename*=UTF-8''" in result
        assert "%E4%BA%91%E7%85%A4" in result  # 云煤 URL-encoded

    def test_special_chars(self):
        result = content_disposition_attachment(
            "file_2026.xlsx", "报表 (2026).xlsx"
        )
        assert "filename*=UTF-8''" in result
        assert "%20" in result  # space encoded
