"""Interaction checks for the Matplotlib chart view."""

import tkinter as tk
from tkinter import ttk
import time

import pandas as pd
import pytest
from matplotlib.backend_bases import MouseEvent

from 前端.plot_view import DataPlotView


def test_hover_crosshair_and_x_range_controls() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"当前子进程没有可用的 Tk 运行时：{exc}")
    root.withdraw()
    try:
        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)
        view = DataPlotView(root, tk.StringVar(value=""))
        view.build(notebook)
        view.set_data(pd.DataFrame({"x": [0.0, 1.0, 2.0], "y": [1.0, 3.0, 5.0]}), ["x", "y"])
        root.update()
        view.plot_current()
        deadline = time.monotonic() + 5
        while view.canvas is None and time.monotonic() < deadline:
            root.update()
            time.sleep(0.02)

        assert view.canvas is not None
        assert view.current_figure is not None
        assert view._navigation_frame is not None
        ax = view.current_figure.axes[0]
        pixel_x, pixel_y = ax.transData.transform((1.0, 3.0))
        event = MouseEvent("motion_notify_event", view.canvas.figure.canvas, pixel_x, pixel_y)
        view._update_hover_crosshair(event)
        assert view._hover_annotation is not None
        assert "x = 1" in view._hover_annotation.get_text()
        assert "y = 3" in view._hover_annotation.get_text()

        initial_span = ax.get_xlim()[1] - ax.get_xlim()[0]
        view._x_range_start.set(20.0)
        view._x_range_end.set(80.0)
        view._apply_x_range_from_controls()
        assert ax.get_xlim()[1] - ax.get_xlim()[0] < initial_span
        view._reset_plot_view()
        assert view._x_range_start.get() == 0.0
        assert view._x_range_end.get() == 100.0
    finally:
        root.destroy()
