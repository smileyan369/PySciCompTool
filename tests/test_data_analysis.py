"""Tests for data analysis backend."""

from __future__ import annotations

import pandas as pd

from 后端 import data_analysis


def test_numeric_columns_detect_convertible_values() -> None:
    data = pd.DataFrame(
        {
            "name": ["A", "B", "C"],
            "score": ["80", "90", ""],
            "height": [170, 168, 172],
        }
    )

    assert data_analysis.numeric_columns(data) == ["score", "height"]


def test_describe_numeric_columns() -> None:
    data = pd.DataFrame({"score": [80, 90, 100, None], "group": ["A", "A", "B", "B"]})

    result = data_analysis.describe_numeric_columns(data)
    row = result.iloc[0].to_dict()

    assert row["列名"] == "score"
    assert row["数量"] == 3
    assert row["缺失值"] == 1
    assert row["平均值"] == 90
    assert row["中位数"] == 90
    assert row["最小值"] == 80
    assert row["最大值"] == 100


def test_load_and_export_csv(tmp_path) -> None:
    source = tmp_path / "source.csv"
    output = tmp_path / "stats.csv"
    pd.DataFrame({"x": [1, 2, 3]}).to_csv(source, index=False)

    data = data_analysis.load_table(source)
    stats = data_analysis.describe_numeric_columns(data)
    data_analysis.export_table(stats, output)

    exported = pd.read_csv(output)
    assert exported.loc[0, "列名"] == "x"
    assert exported.loc[0, "平均值"] == 2


def test_load_and_export_xlsx(tmp_path) -> None:
    source = tmp_path / "source.xlsx"
    output = tmp_path / "stats.xlsx"
    pd.DataFrame({"x": [2, 4, 6]}).to_excel(source, index=False)

    data = data_analysis.load_table(source)
    stats = data_analysis.describe_numeric_columns(data)
    data_analysis.export_table(stats, output)

    exported = pd.read_excel(output)
    assert exported.loc[0, "列名"] == "x"
    assert exported.loc[0, "平均值"] == 4


def test_old_xls_extension_is_rejected(tmp_path) -> None:
    source = tmp_path / "source.xls"
    source.write_text("x\n1\n", encoding="utf-8")

    try:
        data_analysis.load_table(source)
    except data_analysis.DataAnalysisError as exc:
        assert "CSV 或 XLSX" in str(exc)
    else:
        raise AssertionError("old xls files should be rejected clearly")


def test_describe_rejects_non_numeric_data() -> None:
    data = pd.DataFrame({"name": ["A", "B"]})

    try:
        data_analysis.describe_numeric_columns(data)
    except data_analysis.DataAnalysisError as exc:
        assert "没有可以统计的数值列" in str(exc)
    else:
        raise AssertionError("non-numeric data should not be described")
