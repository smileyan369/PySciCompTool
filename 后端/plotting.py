"""Plotting and visualization functions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd
import sympy as sp
from matplotlib.figure import Figure
from matplotlib.ticker import ScalarFormatter
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)


class PlottingError(ValueError):
    """Raised when a plot cannot be created."""


@dataclass(frozen=True)
class FitPlotResult:
    """Polynomial fitting result and its figure."""

    figure: Figure
    formula: str
    r_squared: float
    coefficients: list[float]


TRANSFORMATIONS = standard_transformations + (convert_xor, implicit_multiplication_application)
LINE_COLOR = "#2563eb"
POINT_COLOR = "#f97316"
# Match the peer application's ECharts scatter series: a stable blue 8px
# marker is easier to compare than density-dependent point sizes.
SCATTER_COLOR = "#2563eb"
FIT_COLOR = "#16a34a"
GRID_COLOR = "#94a3b8"

matplotlib.rcParams["font.sans-serif"] = [
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "SimHei",
    "SimSun",
    "Arial Unicode MS",
    "DejaVu Sans",
]
matplotlib.rcParams["axes.unicode_minus"] = False


def module_ready() -> bool:
    """Return whether the module can be imported successfully."""
    return True


def create_line_plot(data: pd.DataFrame, x_col: str, y_col: str, title: str | None = None) -> Figure:
    """Create a line plot from two numeric table columns."""
    x_values, y_values = _numeric_xy(data, x_col, y_col)
    x_values, y_values = _sort_by_x(x_values, y_values)
    figure, ax = _new_figure(title or f"{y_col} 随 {x_col} 变化")
    ax.plot(x_values, y_values, color=LINE_COLOR, linewidth=1.8, label="折线")
    ax.scatter(
        x_values,
        y_values,
        color=POINT_COLOR,
        s=_adaptive_point_sizes(x_values, y_values),
        alpha=_point_alpha(len(x_values)),
        marker="o",
        linewidths=0,
        label="数据点",
    )
    _label_axes(ax, x_col, y_col)
    ax.legend()
    return figure


def create_scatter_plot(data: pd.DataFrame, x_col: str, y_col: str, title: str | None = None) -> Figure:
    """Create a scatter plot from two numeric table columns."""
    x_values, y_values = _numeric_xy(data, x_col, y_col)
    figure, ax = _new_figure(title or f"{x_col} 与 {y_col} 的散点关系")
    ax.scatter(
        x_values,
        y_values,
        color=SCATTER_COLOR,
        s=40,
        alpha=0.9,
        marker="o",
        linewidths=0,
        label="散点",
    )
    _label_axes(ax, x_col, y_col)
    ax.legend()
    return figure


def create_function_plot(
    expression: str,
    start: float | str,
    end: float | str,
    variable: str = "x",
    points: int = 400,
    title: str | None = None,
) -> Figure:
    """Create a function curve plot for an expression on an interval."""
    if points < 2:
        raise PlottingError("points must be at least 2")

    symbol, expr = _parse_function(expression, variable)
    left = _parse_number(start, "start")
    right = _parse_number(end, "end")
    if left >= right:
        raise PlottingError("start must be smaller than end")

    x_values = np.linspace(left, right, points)
    try:
        func = sp.lambdify(symbol, expr, modules=["numpy"])
        y_values = np.asarray(func(x_values), dtype=float)
    except Exception as exc:
        raise PlottingError("function cannot be evaluated on this interval") from exc

    if y_values.shape == ():
        y_values = np.full_like(x_values, float(y_values))
    valid = np.isfinite(x_values) & np.isfinite(y_values)
    if not valid.any():
        raise PlottingError("function has no finite values on this interval")

    figure, ax = _new_figure(title or str(expr))
    ax.plot(x_values[valid], y_values[valid], color=LINE_COLOR, linewidth=1.8)
    _label_axes(ax, variable, "y")
    return figure


def create_polynomial_fit_plot(
    data: pd.DataFrame,
    x_col: str,
    y_col: str,
    degree: int = 2,
    title: str | None = None,
) -> FitPlotResult:
    """Fit a polynomial and plot original points with the fitted curve."""
    if degree < 1:
        raise PlottingError("degree must be at least 1")

    x_values, y_values = _numeric_xy(data, x_col, y_col)
    if len(x_values) < degree + 1:
        raise PlottingError("not enough data points for this polynomial degree")

    x_values, y_values = _sort_by_x(x_values, y_values)
    try:
        coefficients = np.polyfit(x_values, y_values, degree)
        polynomial = np.poly1d(coefficients)
    except Exception as exc:
        raise PlottingError("polynomial fitting failed") from exc

    predicted = polynomial(x_values)
    r_squared = _r_squared(y_values, predicted)
    curve_x = np.linspace(float(np.min(x_values)), float(np.max(x_values)), 300)
    curve_y = polynomial(curve_x)

    figure, ax = _new_figure(title or f"{degree} 阶多项式拟合")
    ax.scatter(
        x_values,
        y_values,
        color=POINT_COLOR,
        s=_adaptive_point_sizes(x_values, y_values),
        alpha=_point_alpha(len(x_values)),
        marker="o",
        linewidths=0,
        label="原始数据",
    )
    ax.plot(curve_x, curve_y, color=FIT_COLOR, linewidth=2.0, label="拟合曲线")
    _label_axes(ax, x_col, y_col)
    ax.legend()

    return FitPlotResult(
        figure=figure,
        formula=_format_polynomial(coefficients),
        r_squared=float(r_squared),
        coefficients=[float(value) for value in coefficients],
    )


def create_auto_fit_plot(
    data: pd.DataFrame,
    x_col: str,
    y_col: str,
    max_degree: int = 3,
    title: str | None = None,
) -> FitPlotResult:
    """Choose a simple polynomial degree automatically and create a fit plot."""
    x_values, _y_values = _numeric_xy(data, x_col, y_col)
    usable_max = max(1, min(max_degree, len(np.unique(x_values)) - 1))
    best_result: FitPlotResult | None = None
    for degree in range(1, usable_max + 1):
        result = create_polynomial_fit_plot(data, x_col, y_col, degree, title)
        if best_result is None or result.r_squared > best_result.r_squared:
            best_result = result
    if best_result is None:
        raise PlottingError("not enough data points for fitting")
    return best_result


def save_figure(figure: Figure, file_path: str | Path, dpi: int = 150) -> None:
    """Save a matplotlib figure to an image file."""
    path = Path(file_path)
    if not path.suffix:
        raise PlottingError("file path must include an image extension")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        figure.savefig(path, dpi=dpi, bbox_inches="tight")
    except Exception as exc:
        raise PlottingError("figure save failed") from exc


def _new_figure(title: str) -> tuple[Figure, Any]:
    figure = Figure(figsize=(8.4, 4.2), dpi=100)
    ax = figure.add_subplot(111)
    ax.set_title(title, fontsize=12, color="#111827", pad=10)
    ax.grid(True, color=GRID_COLOR, alpha=0.25, linewidth=0.8)
    ax.set_facecolor("#ffffff")
    figure.patch.set_facecolor("#ffffff")
    return figure, ax


def _label_axes(ax: Any, x_label: str, y_label: str) -> None:
    ax.set_xlabel(str(x_label), color="#1f2937")
    ax.set_ylabel(str(y_label), color="#1f2937")
    ax.tick_params(colors="#1f2937")
    # Use compact scientific notation for very large/small data, matching the
    # peer chart's readable axis formatting instead of long decimal strings.
    for axis in (ax.xaxis, ax.yaxis):
        formatter = ScalarFormatter(useMathText=True)
        formatter.set_scientific(True)
        formatter.set_powerlimits((-3, 4))
        formatter.set_useOffset(False)
        axis.set_major_formatter(formatter)
    ax.figure.subplots_adjust(left=0.08, right=0.985, bottom=0.11, top=0.92)


def _numeric_xy(data: pd.DataFrame, x_col: str, y_col: str) -> tuple[np.ndarray, np.ndarray]:
    if x_col not in data.columns:
        raise PlottingError(f"column not found: {x_col}")
    if y_col not in data.columns:
        raise PlottingError(f"column not found: {y_col}")

    pairs = pd.DataFrame(
        {
            "x": pd.to_numeric(data[x_col], errors="coerce"),
            "y": pd.to_numeric(data[y_col], errors="coerce"),
        }
    ).dropna()
    if pairs.empty:
        raise PlottingError("selected columns do not contain numeric point pairs")
    return pairs["x"].to_numpy(dtype=float), pairs["y"].to_numpy(dtype=float)


def _sort_by_x(x_values: np.ndarray, y_values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(x_values)
    return x_values[order], y_values[order]


def _point_size(count: int) -> float:
    if count >= 5000:
        return 3
    if count >= 1000:
        return 5
    return 18


def _adaptive_point_sizes(
    x_values: np.ndarray,
    y_values: np.ndarray,
    min_size: float = 5,
    max_size: float = 30,
) -> np.ndarray:
    """Return larger points in sparse areas and smaller points in dense areas."""
    count = len(x_values)
    if count == 0:
        return np.array([], dtype=float)
    if count < 30:
        return np.full(count, max_size, dtype=float)

    x_span = float(np.nanmax(x_values) - np.nanmin(x_values))
    y_span = float(np.nanmax(y_values) - np.nanmin(y_values))
    if x_span == 0 or y_span == 0:
        return np.full(count, _point_size(count), dtype=float)

    bins = int(np.clip(np.sqrt(count) / 2, 18, 80))
    density, x_edges, y_edges = np.histogram2d(x_values, y_values, bins=bins)
    x_index = np.clip(np.searchsorted(x_edges, x_values, side="right") - 1, 0, bins - 1)
    y_index = np.clip(np.searchsorted(y_edges, y_values, side="right") - 1, 0, bins - 1)
    local_density = np.maximum(density[x_index, y_index], 1)

    sizes = max_size / np.sqrt(local_density)
    return np.clip(sizes, min_size, max_size)


def _point_alpha(count: int) -> float:
    if count >= 5000:
        return 0.38
    if count >= 1000:
        return 0.48
    return 0.75


def _scatter_alpha(count: int) -> float:
    if count >= 5000:
        return 0.5
    if count >= 1000:
        return 0.62
    return 0.85


def _prepare_expression_text(expression: str) -> str:
    text = str(expression).strip()
    text = text.replace("π", "pi")
    text = text.replace("ⁿ√", "root")
    text = text.replace("√", "sqrt")
    return text


def _local_dict() -> dict[str, object]:
    return {
        "pi": sp.pi,
        "π": sp.pi,
        "e": sp.E,
        "ln": sp.log,
        "log": sp.log,
        "lg": lambda value: sp.log(value, 10),
        "sqrt": sp.sqrt,
        "root": lambda degree, value: sp.root(value, degree),
        "Abs": sp.Abs,
        "abs": sp.Abs,
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
    }


def _parse_function(expression: str, variable: str) -> tuple[sp.Symbol, sp.Expr]:
    expression_text = _prepare_expression_text(expression)
    variable_text = str(variable).strip() or "x"
    if not expression_text:
        raise PlottingError("expression cannot be empty")
    if not variable_text.isidentifier():
        raise PlottingError("variable name is invalid")

    symbol = sp.symbols(variable_text)
    try:
        expr = parse_expr(
            expression_text,
            local_dict=_local_dict(),
            transformations=TRANSFORMATIONS,
            evaluate=True,
        )
    except Exception as exc:
        raise PlottingError("expression format is invalid") from exc

    extra_symbols = expr.free_symbols - {symbol}
    if extra_symbols:
        names = ", ".join(sorted(str(item) for item in extra_symbols))
        raise PlottingError(f"expression contains unknown variables: {names}")
    return symbol, expr


def _parse_number(value: float | str, field_name: str) -> float:
    try:
        parsed = parse_expr(
            _prepare_expression_text(str(value)),
            local_dict=_local_dict(),
            transformations=TRANSFORMATIONS,
            evaluate=True,
        )
        number = float(sp.N(parsed))
    except Exception as exc:
        raise PlottingError(f"{field_name} is invalid") from exc
    if not np.isfinite(number):
        raise PlottingError(f"{field_name} must be finite")
    return number


def _r_squared(y_values: np.ndarray, predicted: np.ndarray) -> float:
    residual_sum = float(np.sum((y_values - predicted) ** 2))
    total_sum = float(np.sum((y_values - np.mean(y_values)) ** 2))
    if total_sum == 0:
        return 1.0 if residual_sum == 0 else 0.0
    return 1 - residual_sum / total_sum


def _format_polynomial(coefficients: np.ndarray) -> str:
    degree = len(coefficients) - 1
    parts: list[str] = []
    for index, coefficient in enumerate(coefficients):
        power = degree - index
        if abs(coefficient) < 1e-12:
            continue
        sign = "-" if coefficient < 0 else "+"
        value = abs(float(coefficient))
        value_text = f"{value:.6g}"
        if power == 0:
            term = value_text
        elif power == 1:
            term = f"{value_text}x"
        else:
            term = f"{value_text}x^{power}"
        parts.append((sign, term))

    if not parts:
        return "y = 0"

    first_sign, first_term = parts[0]
    formula = f"y = {'-' if first_sign == '-' else ''}{first_term}"
    for sign, term in parts[1:]:
        formula += f" {sign} {term}"
    return formula
