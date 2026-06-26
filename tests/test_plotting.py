"""Tests for plotting backend."""

from __future__ import annotations

import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import ScalarFormatter

from 后端 import plotting


def test_create_line_plot() -> None:
    data = pd.DataFrame({"x": [0, 1, 2], "y": [1, 3, 5]})

    figure = plotting.create_line_plot(data, "x", "y")

    assert isinstance(figure, Figure)
    assert len(figure.axes[0].lines) == 1


def test_create_scatter_plot() -> None:
    data = pd.DataFrame({"x": [0, 1, 2], "y": [1, 3, 5]})

    figure = plotting.create_scatter_plot(data, "x", "y")

    assert isinstance(figure, Figure)
    assert len(figure.axes[0].collections) == 1
    assert isinstance(figure.axes[0].xaxis.get_major_formatter(), ScalarFormatter)
    assert isinstance(figure.axes[0].yaxis.get_major_formatter(), ScalarFormatter)


def test_create_function_plot() -> None:
    figure = plotting.create_function_plot("sin(x)", 0, "π")

    assert isinstance(figure, Figure)
    assert len(figure.axes[0].lines) == 1


def test_create_polynomial_fit_plot() -> None:
    data = pd.DataFrame({"x": [0, 1, 2, 3], "y": [1, 3, 5, 7]})

    result = plotting.create_polynomial_fit_plot(data, "x", "y", degree=1)

    assert isinstance(result.figure, Figure)
    assert result.r_squared > 0.999
    assert "x" in result.formula


def test_save_figure(tmp_path) -> None:
    data = pd.DataFrame({"x": [0, 1, 2], "y": [1, 3, 5]})
    figure = plotting.create_line_plot(data, "x", "y")
    output = tmp_path / "line.png"

    plotting.save_figure(figure, output)

    assert output.exists()
    assert output.stat().st_size > 0


def test_rejects_missing_column() -> None:
    data = pd.DataFrame({"x": [0, 1, 2]})

    try:
        plotting.create_line_plot(data, "x", "y")
    except plotting.PlottingError as exc:
        assert "column not found" in str(exc)
    else:
        raise AssertionError("missing column should be rejected")
