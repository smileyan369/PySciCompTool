"""Data loading, statistics, preview, and export functions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


class DataAnalysisError(ValueError):
    """Raised when a data analysis operation cannot be completed."""


def module_ready() -> bool:
    """Return whether the module can be imported successfully."""
    return True


def _detect_bom_encoding(path: Path) -> str | None:
    """Detect encoding from BOM bytes at the start of the file."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(4)
    except OSError:
        return None
    if head[:2] == b"\xff\xfe":
        return "utf-16-le"
    if head[:2] == b"\xfe\xff":
        return "utf-16-be"
    if head[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    return None


def load_table(file_path: str | Path) -> pd.DataFrame:
    """Load a CSV or XLSX table with automatic encoding detection."""
    path = Path(file_path)
    if not path.exists():
        raise DataAnalysisError("文件不存在")

    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            bom_enc = _detect_bom_encoding(path)
            if bom_enc:
                try:
                    return pd.read_csv(path, encoding=bom_enc)
                except Exception:
                    pass
            for enc in ("utf-8", "gbk", "gb18030", "utf-16-le", "utf-16-be"):
                try:
                    return pd.read_csv(path, encoding=enc)
                except (UnicodeDecodeError, UnicodeError, LookupError):
                    continue
            return pd.read_csv(path)
        if suffix == ".xlsx":
            return pd.read_excel(path)
    except Exception as exc:
        raise DataAnalysisError(f"文件读取失败：{exc}") from exc

    raise DataAnalysisError("只支持 CSV 或 XLSX 文件")


def numeric_columns(data: pd.DataFrame) -> list[str]:
    """Return columns that can be treated as numeric data."""
    columns: list[str] = []
    for column in data.columns:
        numeric_values = pd.to_numeric(data[column], errors="coerce")
        if numeric_values.notna().any():
            columns.append(str(column))
    return columns


def preview_rows(data: pd.DataFrame, limit: int = 20) -> list[dict[str, Any]]:
    """Return a small preview that the frontend can display in a table."""
    preview = data.head(limit).where(pd.notna(data.head(limit)), "")
    return preview.to_dict(orient="records")


def describe_numeric_columns(data: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """Calculate common statistics for selected numeric columns."""
    selected_columns = columns or numeric_columns(data)
    if not selected_columns:
        raise DataAnalysisError("没有可以统计的数值列")

    rows: list[dict[str, Any]] = []
    for column in selected_columns:
        if column not in data.columns:
            raise DataAnalysisError(f"数据中没有这一列：{column}")

        series = pd.to_numeric(data[column], errors="coerce")
        valid = series.dropna()
        if valid.empty:
            continue

        rows.append(
            {
                "列名": column,
                "数量": int(valid.count()),
                "缺失值": int(series.isna().sum()),
                "平均值": _round_float(valid.mean()),
                "中位数": _round_float(valid.median()),
                "方差": _round_float(valid.var(ddof=1)) if len(valid) > 1 else 0,
                "标准差": _round_float(valid.std(ddof=1)) if len(valid) > 1 else 0,
                "最小值": _round_float(valid.min()),
                "最大值": _round_float(valid.max()),
            }
        )

    if not rows:
        raise DataAnalysisError("选择的列无法转换成数字")
    return pd.DataFrame(rows)


def export_table(data: pd.DataFrame, file_path: str | Path) -> None:
    """Export a table to CSV or Excel."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if suffix == ".csv":
            data.to_csv(path, index=False, encoding="utf-8-sig")
            return
        if suffix == ".xlsx":
            data.to_excel(path, index=False)
            return
    except Exception as exc:
        raise DataAnalysisError(f"结果导出失败：{exc}") from exc

    raise DataAnalysisError("导出文件只支持 CSV 或 XLSX")


def _round_float(value: Any, digits: int = 10) -> Any:
    if pd.isna(value):
        return ""
    return round(float(value), digits)
