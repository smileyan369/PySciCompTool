"""Data visualization view for the frontend."""

from __future__ import annotations

import time
import threading
import queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from 后端 import plotting
from . import common_widgets
from .theme_models import AppTheme


# Keep the embedded Matplotlib canvas within a stable workbench-sized viewport.
MAX_CHART_WIDTH = 1280
MAX_CHART_HEIGHT = 600


NO_NUMERIC_COLUMNS = "没有数值列"


class DataPlotView:
    """Interactive data visualization tab."""

    def __init__(self, root: tk.Tk, status_var: tk.StringVar, theme: AppTheme | None = None) -> None:
        self.root = root
        self.status_var = status_var
        self.theme = theme
        self._skinned_labels: list[tuple[tk.Label, str, str]] = []
        self.data_frame: pd.DataFrame | None = None
        self.x_var = tk.StringVar(value="")
        self.y_var = tk.StringVar(value="")
        self.kind_var = tk.StringVar(value="line")
        self.fit_degree_var = tk.StringVar(value="2")
        self.x_selector: ttk.Combobox | None = None
        self.y_selector: ttk.Combobox | None = None
        self.preview_host: ttk.Frame | None = None
        self.chart_host: ttk.Frame | None = None
        self.canvas: FigureCanvasTkAgg | None = None
        self.current_figure = None
        self._refresh_job: str | None = None
        self._plot_request_id = 0
        self._plot_thread: threading.Thread | None = None
        self._plot_result_queue: queue.Queue = queue.Queue()
        self._plot_poll_job: str | None = None
        self._loading_label: tk.Label | None = None
        self._resize_job: str | None = None
        self._last_canvas_size: tuple[int, int] | None = None
        self._pan_state = None
        self._last_scroll_time = 0.0
        self._hover_crosshair = None
        self._hover_annotation = None
        self._hover_axes = None
        self._hover_background = None
        self._hover_data_points = np.empty((0, 2), dtype=float)
        self._hover_pixel_points = np.empty((0, 2), dtype=float)
        self._hover_last_update = 0.0
        self._hover_draw_connection: int | None = None
        self._x_full_limits: tuple[float, float] | None = None
        self._y_full_limits: tuple[float, float] | None = None
        self._x_range_start = tk.DoubleVar(value=0.0)
        self._x_range_end = tk.DoubleVar(value=100.0)
        self._range_control_updating = False
        self._navigation_frame: ttk.Frame | None = None

    def build(self, parent: ttk.Notebook, theme: AppTheme | None = None) -> ttk.Frame:
        """Build and return the visualization tab frame."""
        if theme is not None:
            self.theme = theme
        frame = common_widgets.new_tab_frame(parent)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=0)
        frame.rowconfigure(1, weight=1)

        controls = common_widgets.section(frame, "绘图设置", 0, 0)
        controls.grid(sticky="ew", padx=6, pady=(0, 8))
        controls.columnconfigure(1, weight=1, uniform="plot_selectors")
        controls.columnconfigure(3, weight=1, uniform="plot_selectors")

        self._skinned_label(controls, "surface", "hint", text="x 列").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        self.x_selector = ttk.Combobox(
            controls,
            textvariable=self.x_var,
            values=("请先导入数据",),
            state="readonly",
            width=24,
        )
        self.x_selector.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=4)

        self._skinned_label(controls, "surface", "hint", text="y 列").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=4)
        self.y_selector = ttk.Combobox(
            controls,
            textvariable=self.y_var,
            values=("请先导入数据",),
            state="readonly",
            width=24,
        )
        self.y_selector.grid(row=0, column=3, sticky="ew", padx=(0, 14), pady=4)

        buttons = (
            ("折线图", lambda: self._set_plot_kind("line")),
            ("散点图", lambda: self._set_plot_kind("scatter")),
            ("多项式拟合", lambda: self._set_plot_kind("fit")),
            ("保存图表", self.save_current_plot),
        )
        for index, (text, command) in enumerate(buttons, start=4):
            ttk.Button(controls, text=text, command=command, width=12).grid(
                row=0, column=index, sticky="ew", padx=(0, 8), pady=4
            )

        self._skinned_label(controls, "surface", "hint", text="拟合阶数").grid(
            row=1, column=0, sticky="w", padx=(0, 6), pady=(4, 0)
        )
        ttk.Combobox(
            controls,
            textvariable=self.fit_degree_var,
            values=("1", "2", "3", "4", "5", "6"),
            state="readonly",
            width=8,
        ).grid(row=1, column=1, sticky="w", padx=(0, 14), pady=(4, 0))
        self._skinned_label(
            controls, "surface", "hint",
            text="注：拟合阶数越高，曲线通常越接近原始数据，但阶数过高可能出现过拟合。",
        ).grid(row=1, column=2, columnspan=6, sticky="w", pady=(4, 0))

        preview = common_widgets.section(frame, "图表预览", 1, 0)
        preview.grid(sticky="nsew", padx=6, pady=6)
        preview.columnconfigure(0, weight=1)
        preview.rowconfigure(0, weight=1)

        self.preview_host = ttk.Frame(preview, style="Surface.TFrame")
        self.preview_host.grid(row=0, column=0, sticky="nsew")
        self.preview_host.columnconfigure(0, weight=1)
        self.preview_host.rowconfigure(0, weight=1)
        self.preview_host.bind("<Configure>", self._schedule_canvas_resize, add="+")
        self.chart_host = ttk.Frame(self.preview_host, style="Surface.TFrame")
        self.chart_host.grid(row=0, column=0, sticky="nsew")
        self.chart_host.columnconfigure(0, weight=1)
        self.chart_host.rowconfigure(0, weight=1)
        self._skinned_label(
            self.chart_host, "surface", "hint",
            text=(
                "导入数据后自动显示图表。鼠标滚轮缩放，按住左键拖动平移。\n"
                "如遇图像显示异常，请反复切换图像格式后重试。"
            ),
            anchor="center",
        ).grid(row=0, column=0, sticky="nsew")

        self.x_var.trace_add("write", lambda *_args: self.schedule_refresh())
        self.y_var.trace_add("write", lambda *_args: self.schedule_refresh())
        self.fit_degree_var.trace_add("write", lambda *_args: self.schedule_refresh())
        self._apply_button_cursor(controls)
        return frame

    def _skinned_label(self, parent: tk.Widget, bg_key: str = "surface", fg_key: str = "text", **kwargs) -> tk.Label:
        """Create a tk.Label with no visible background rectangle."""
        theme = self.theme
        bg_map = {"background": theme.background, "surface": theme.surface, "surface_alt": theme.surface_alt} if theme else {"background": "#f0f0f0", "surface": "#ffffff", "surface_alt": "#f5f5f5"}
        fg_map = {"text": theme.text, "heading": theme.heading, "hint": theme.hint} if theme else {"text": "#000000", "heading": "#000000", "hint": "#888888"}
        label = tk.Label(parent, highlightthickness=0, bd=0, bg=bg_map.get(bg_key, "#ffffff"), fg=fg_map.get(fg_key, "#000000"), **kwargs)
        self._skinned_labels.append((label, bg_key, fg_key))
        return label

    def update_theme(self, theme: AppTheme) -> None:
        """Update all tracked labels to match a new theme."""
        self.theme = theme
        bg_map = {"background": theme.background, "surface": theme.surface, "surface_alt": theme.surface_alt}
        fg_map = {"text": theme.text, "heading": theme.heading, "hint": theme.hint}
        for label, bg_key, fg_key in self._skinned_labels:
            try:
                label.configure(bg=bg_map.get(bg_key, "#ffffff"), fg=fg_map.get(fg_key, "#000000"))
            except tk.TclError:
                pass

    def _apply_button_cursor(self, widget: tk.Widget) -> None:
        for child in widget.winfo_children():
            if isinstance(child, ttk.Button):
                child.configure(cursor="hand2")
            self._apply_button_cursor(child)

    def set_data(self, data_frame: pd.DataFrame | None, numeric_columns: list[str]) -> None:
        """Update source data and refresh column selectors."""
        # Invalidate a pending render from the previous imported file.
        self._plot_request_id += 1
        self.data_frame = data_frame
        values = tuple(numeric_columns) if numeric_columns else (NO_NUMERIC_COLUMNS,)
        if self.x_selector is not None:
            self.x_selector.configure(values=values)
        if self.y_selector is not None:
            self.y_selector.configure(values=values)

        if numeric_columns:
            self.x_var.set(numeric_columns[0])
            self.y_var.set(numeric_columns[1] if len(numeric_columns) > 1 else numeric_columns[0])
            self.schedule_refresh()
        else:
            self.x_var.set(NO_NUMERIC_COLUMNS)
            self.y_var.set(NO_NUMERIC_COLUMNS)

    def schedule_refresh(self) -> None:
        """Refresh the current plot shortly after selector changes."""
        if self._refresh_job is not None:
            self.root.after_cancel(self._refresh_job)
        self._refresh_job = self.root.after(160, self.plot_current)

    def save_current_plot(self) -> None:
        """Save the current matplotlib figure."""
        if self.current_figure is None:
            messagebox.showwarning("没有图表", "请先绘制图表")
            return
        file_path = filedialog.asksaveasfilename(
            title="保存图表",
            defaultextension=".png",
            filetypes=(("PNG 图片", "*.png"), ("JPEG 图片", "*.jpg"), ("PDF 文件", "*.pdf")),
        )
        if not file_path:
            return
        try:
            plotting.save_figure(self.current_figure, file_path)
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))
            return
        self.status_var.set(f"图表已保存：{file_path}")

    def _selected_columns(self, show_warning: bool = True) -> tuple[str, str] | None:
        x_col = self.x_var.get().strip()
        y_col = self.y_var.get().strip()
        if not x_col or not y_col or x_col == NO_NUMERIC_COLUMNS or y_col == NO_NUMERIC_COLUMNS:
            if show_warning:
                messagebox.showwarning("没有列", "请选择用于绘图的 x 列和 y 列")
            return None
        return x_col, y_col

    def _set_plot_kind(self, kind: str) -> None:
        self.kind_var.set(kind)
        self.plot_current(show_warning=True)

    def plot_current(self, show_warning: bool = False) -> None:
        """Request a plot without blocking Tk while large data is processed."""
        self._refresh_job = None
        if self.data_frame is None:
            if show_warning:
                messagebox.showwarning("没有数据", "请先在数据分析页导入 CSV 或 Excel 文件")
            return

        columns = self._selected_columns(show_warning=show_warning)
        if columns is None:
            return
        request_id = self._plot_request_id + 1
        self._plot_request_id = request_id
        data = self.data_frame
        kind = self.kind_var.get()
        degree = self._fit_degree()
        self.status_var.set("正在后台生成图表…")
        self._show_loading()
        worker = threading.Thread(
            target=self._build_plot_in_background,
            args=(request_id, data, columns[0], columns[1], kind, degree, show_warning),
            daemon=True,
        )
        self._plot_thread = worker
        worker.start()
        if self._plot_poll_job is None:
            self._plot_poll_job = self.root.after(20, self._poll_plot_results)

    def _show_loading(self) -> None:
        """Show a non-layout-affecting overlay while a plot is built."""
        if self.chart_host is None:
            return
        if self._loading_label is None or not self._loading_label.winfo_exists():
            theme = self.theme
            self._loading_label = tk.Label(
                self.chart_host,
                text="图像正在加载中…",
                bg=theme.surface if theme else "#ffffff",
                fg=theme.hint if theme else "#64748b",
                font=("Microsoft YaHei UI", 12),
                padx=18,
                pady=10,
            )
        self._loading_label.place(relx=0.5, rely=0.5, anchor="center")
        self._loading_label.lift()

    def _hide_loading(self) -> None:
        """Remove the temporary loading overlay without changing chart geometry."""
        if self._loading_label is not None:
            try:
                self._loading_label.destroy()
            except tk.TclError:
                pass
            self._loading_label = None

    def _build_plot_in_background(
        self,
        request_id: int,
        data: pd.DataFrame,
        x_column: str,
        y_column: str,
        kind: str,
        degree: int,
        show_warning: bool,
    ) -> None:
        """Build a Figure off Tk's event thread, like the peer app's backend job."""
        figure = None
        status = ""
        error: Exception | None = None
        try:
            if kind == "scatter":
                figure = plotting.create_scatter_plot(data, x_column, y_column)
                status = "散点图已更新"
            elif kind == "fit":
                result = plotting.create_polynomial_fit_plot(data, x_column, y_column, degree)
                figure = result.figure
                status = f"{degree} 阶多项式拟合完成：{result.formula}?R?={result.r_squared:.4f}"
            else:
                figure = plotting.create_line_plot(data, x_column, y_column)
                status = "折线图已更新"
        except Exception as exc:
            error = exc

        self._plot_result_queue.put((request_id, figure, status, error, show_warning))

    def _poll_plot_results(self) -> None:
        """Apply worker results from Tk's event thread only."""
        self._plot_poll_job = None
        try:
            while True:
                request_id, figure, status, error, show_warning = self._plot_result_queue.get_nowait()
                self._finish_plot_request(request_id, figure, status, error, show_warning)
        except queue.Empty:
            pass
        if (
            (self._plot_thread is not None and self._plot_thread.is_alive())
            or not self._plot_result_queue.empty()
        ):
            self._plot_poll_job = self.root.after(20, self._poll_plot_results)

    def _finish_plot_request(
        self,
        request_id: int,
        figure,
        status: str,
        error: Exception | None,
        show_warning: bool,
    ) -> None:
        """Only let the newest background request update the Tk canvas."""
        if request_id != self._plot_request_id:
            if figure is not None:
                figure.clear()
            return
        if error is not None:
            self._hide_loading()
            if show_warning:
                messagebox.showerror("绘图失败", str(error))
            self.status_var.set(f"绘图失败：{error}")
            return
        if figure is None:
            self._hide_loading()
            self.status_var.set("绘图失败：未生成图表")
            return
        self._show_figure(figure)
        self.status_var.set(status)

    def _fit_degree(self) -> int:
        try:
            return max(1, min(6, int(self.fit_degree_var.get())))
        except ValueError:
            self.fit_degree_var.set("2")
            return 2

    def _show_figure(self, figure) -> None:
        if self.preview_host is None or self.chart_host is None:
            return
        self._hide_loading()
        for child in self.chart_host.winfo_children():
            child.destroy()
        if self.canvas is not None:
            try:
                self.canvas.get_tk_widget().destroy()
            except Exception:
                pass
        if self._navigation_frame is not None:
            try:
                self._navigation_frame.destroy()
            except tk.TclError:
                pass
            self._navigation_frame = None

        self._hover_crosshair = None
        self._hover_annotation = None
        self._hover_axes = None
        self._hover_background = None
        self._hover_data_points = np.empty((0, 2), dtype=float)
        self._hover_pixel_points = np.empty((0, 2), dtype=float)
        self._x_full_limits = None
        self._y_full_limits = None
        self.current_figure = figure

        # Reserve the range-control row before measuring the chart area.  This
        # prevents the canvas and navigation bar from repeatedly competing for
        # the same height after switching chart kinds.
        self._build_x_range_controls()
        self.root.update_idletasks()
        width, height = self._preview_size()
        self._last_canvas_size = (width, height)
        self._resize_figure(figure, width, height)

        self.canvas = FigureCanvasTkAgg(figure, master=self.chart_host)
        # Do not let Tk stretch the canvas after Matplotlib has sized it.
        # A stretched canvas receives a second Configure event and makes the
        # rendered image jump from small to full-panel size after chart switches.
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nw")
        self._enable_plot_interaction()
        self.canvas.draw_idle()

    def _build_x_range_controls(self) -> None:
        """Add a bottom range slider equivalent to a chart data-zoom control."""
        if self.preview_host is None or self.current_figure is None:
            return
        self._navigation_frame = ttk.Frame(self.preview_host, style="Surface.TFrame")
        self._navigation_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 6))
        self._navigation_frame.columnconfigure(1, weight=1)
        self._navigation_frame.columnconfigure(3, weight=1)
        self._skinned_label(self._navigation_frame, "surface", "hint", text="X 轴范围").grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        ttk.Scale(
            self._navigation_frame,
            from_=0,
            to=100,
            variable=self._x_range_start,
            command=lambda _value: self._apply_x_range_from_controls(),
        ).grid(row=0, column=1, sticky="ew")
        ttk.Scale(
            self._navigation_frame,
            from_=0,
            to=100,
            variable=self._x_range_end,
            command=lambda _value: self._apply_x_range_from_controls(),
        ).grid(row=0, column=3, sticky="ew", padx=(8, 8))
        ttk.Button(self._navigation_frame, text="重置视图", command=self._reset_plot_view, width=10).grid(
            row=0, column=4, sticky="e"
        )

        ax = self.current_figure.axes[0] if self.current_figure.axes else None
        if ax is not None:
            left, right = ax.dataLim.intervalx
            if np.isfinite(left) and np.isfinite(right) and right > left:
                padding = (right - left) * 0.02
                self._x_full_limits = (float(left - padding), float(right + padding))
            else:
                self._x_full_limits = None
            bottom, top = ax.dataLim.intervaly
            if np.isfinite(bottom) and np.isfinite(top) and top > bottom:
                padding = (top - bottom) * 0.05
                self._y_full_limits = (float(bottom - padding), float(top + padding))
            else:
                self._y_full_limits = None
            self._sync_x_range_controls(ax)

    def _apply_x_range_from_controls(self) -> None:
        if self._range_control_updating or self.current_figure is None or self._x_full_limits is None:
            return
        ax = self.current_figure.axes[0] if self.current_figure.axes else None
        if ax is None:
            return
        start = max(0.0, min(99.0, self._x_range_start.get()))
        end = max(1.0, min(100.0, self._x_range_end.get()))
        if end - start < 1.0:
            if start >= self._x_range_end.get():
                end = min(100.0, start + 1.0)
            else:
                start = max(0.0, end - 1.0)
        full_left, full_right = self._x_full_limits
        full_span = full_right - full_left
        self._hide_hover_crosshair()
        self._hover_background = None
        ax.set_xlim(full_left + full_span * start / 100.0, full_left + full_span * end / 100.0)
        self._set_x_range_values(start, end)
        if self.canvas is not None:
            self.canvas.draw_idle()

    def _sync_x_range_controls(self, ax) -> None:
        if self._x_full_limits is None:
            return
        full_left, full_right = self._x_full_limits
        full_span = full_right - full_left
        if full_span <= 0:
            return
        left, right = ax.get_xlim()
        start = max(0.0, min(100.0, (left - full_left) / full_span * 100.0))
        end = max(0.0, min(100.0, (right - full_left) / full_span * 100.0))
        if end - start < 1.0:
            return
        self._set_x_range_values(start, end)

    def _set_x_range_values(self, start: float, end: float) -> None:
        self._range_control_updating = True
        self._x_range_start.set(start)
        self._x_range_end.set(end)
        self._range_control_updating = False

    def _reset_plot_view(self) -> None:
        if self.current_figure is None:
            return
        ax = self.current_figure.axes[0] if self.current_figure.axes else None
        if ax is None:
            return
        self._hide_hover_crosshair()
        self._hover_background = None
        if self._x_full_limits is not None:
            ax.set_xlim(*self._x_full_limits)
        if self._y_full_limits is not None:
            ax.set_ylim(*self._y_full_limits)
        self._set_x_range_values(0.0, 100.0)
        if self.canvas is not None:
            self.canvas.draw_idle()

    def _schedule_canvas_resize(self, _event=None) -> None:
        if self.current_figure is None or self.canvas is None:
            return
        if self._resize_job is not None:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(80, self._resize_current_canvas)

    def _resize_current_canvas(self) -> None:
        self._resize_job = None
        if self.current_figure is None or self.canvas is None:
            return
        width, height = self._preview_size()
        size = (width, height)
        # Canvas drawing itself may emit Configure.  Only resize when the
        # available chart viewport genuinely changed (for example, window resize).
        if size == self._last_canvas_size:
            return
        self._last_canvas_size = size
        self._resize_figure(self.current_figure, width, height)
        self.canvas.draw_idle()

    def _preview_size(self) -> tuple[int, int]:
        if self.preview_host is None:
            return 1200, 760
        # Measure the outer preview panel, not the canvas host.  The latter
        # inherits the old canvas request after a window shrink and therefore
        # cannot tell us that the page has grown again.
        width = self.preview_host.winfo_width()
        height = self.preview_host.winfo_height()
        if self._navigation_frame is not None:
            try:
                height -= self._navigation_frame.winfo_height() + 12
            except tk.TclError:
                pass
        if width <= 80:
            width = max(320, self.root.winfo_width() - 80)
        if height <= 80:
            header_space = 250
            height = max(260, self.root.winfo_height() - header_space)
        # Use the actual remaining workbench area as an additional cap.  A
        # fixed 1280px canvas is too wide for a small window and gets clipped
        # after importing data, so the graph must shrink with the page first.
        root_width = max(self.root.winfo_width(), 1)
        root_height = max(self.root.winfo_height(), 1)
        page_width = max(320, root_width - 72)
        page_height = max(260, root_height - 340)
        return (
            min(MAX_CHART_WIDTH, page_width, max(320, width)),
            min(MAX_CHART_HEIGHT, page_height, max(260, height)),
        )

    def _resize_figure(self, figure, width: int, height: int) -> None:
        dpi = figure.get_dpi() or 100
        figure.set_size_inches(width / dpi, height / dpi, forward=True)
        try:
            figure.subplots_adjust(left=0.075, right=0.975, bottom=0.12, top=0.9)
        except Exception:
            pass

    @staticmethod
    def _format_coordinate_value(value: float) -> str:
        """Format hover values like the peer chart's compact tooltip."""
        magnitude = abs(value)
        if magnitude and (magnitude >= 1e5 or magnitude < 1e-3):
            return f"{value:.3e}"
        return f"{value:.6g}"

    def _prepare_hover_overlay(self) -> None:
        if self.current_figure is None or not self.current_figure.axes:
            return
        ax = self.current_figure.axes[0]
        vertical = ax.axvline(0, color="#64748b", linestyle="--", linewidth=0.8, alpha=0.78, visible=False)
        horizontal = ax.axhline(0, color="#64748b", linestyle="--", linewidth=0.8, alpha=0.78, visible=False)
        vertical.set_gid("hover_crosshair")
        horizontal.set_gid("hover_crosshair")
        vertical.set_animated(True)
        horizontal.set_animated(True)
        annotation = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(10, 10),
            textcoords="offset points",
            fontsize=9,
            color="#0f172a",
            bbox={"boxstyle": "round,pad=0.28", "fc": "#ffffff", "ec": "#94a3b8", "alpha": 0.95},
            zorder=12,
            visible=False,
        )
        annotation.set_animated(True)
        self._hover_axes = ax
        self._hover_crosshair = (vertical, horizontal)
        self._hover_annotation = annotation

    def _capture_hover_background(self, _event=None) -> None:
        if self.canvas is None or self._hover_axes is None:
            return
        if self._hover_crosshair is not None:
            for line in self._hover_crosshair:
                line.set_visible(False)
        if self._hover_annotation is not None:
            self._hover_annotation.set_visible(False)
        self._hover_background = self.canvas.copy_from_bbox(self._hover_axes.bbox)
        self._cache_hover_points(self._hover_axes)

    def _cache_hover_points(self, ax) -> None:
        data_sets = []
        for collection in ax.collections:
            offsets = np.asarray(collection.get_offsets(), dtype=float)
            if offsets.ndim == 2 and offsets.shape[1] >= 2:
                data_sets.append(offsets[:, :2])
        for line in ax.lines:
            if line.get_gid() == "hover_crosshair":
                continue
            x_values = np.asarray(line.get_xdata(orig=False), dtype=float)
            y_values = np.asarray(line.get_ydata(orig=False), dtype=float)
            if x_values.size and x_values.shape == y_values.shape:
                data_sets.append(np.column_stack((x_values, y_values)))
        if not data_sets:
            self._hover_data_points = np.empty((0, 2), dtype=float)
            self._hover_pixel_points = np.empty((0, 2), dtype=float)
            return
        points = np.vstack(data_sets)
        points = points[np.isfinite(points).all(axis=1)]
        self._hover_data_points = points
        self._hover_pixel_points = ax.transData.transform(points) if len(points) else np.empty((0, 2), dtype=float)

    def _nearest_visible_point(self, ax, event) -> tuple[float, float] | None:
        if event.x is None or event.y is None:
            return None
        if ax is not self._hover_axes:
            self._cache_hover_points(ax)
        if not len(self._hover_pixel_points):
            return None
        distances = (self._hover_pixel_points[:, 0] - event.x) ** 2 + (self._hover_pixel_points[:, 1] - event.y) ** 2
        index = int(np.argmin(distances))
        if distances[index] > 14.0**2:
            return None
        return float(self._hover_data_points[index, 0]), float(self._hover_data_points[index, 1])

    def _update_hover_crosshair(self, event) -> None:
        if self.canvas is None or self.current_figure is None:
            return
        ax = event.inaxes
        if ax is None or event.xdata is None or event.ydata is None:
            self._hide_hover_crosshair()
            return
        now = time.perf_counter()
        if now - self._hover_last_update < 1 / 40:
            return
        self._hover_last_update = now
        point = self._nearest_visible_point(ax, event)
        x_value, y_value = point if point is not None else (float(event.xdata), float(event.ydata))
        if self._hover_crosshair is None or ax is not self._hover_axes:
            return
        vertical, horizontal = self._hover_crosshair
        vertical.set_xdata([x_value, x_value])
        horizontal.set_ydata([y_value, y_value])
        vertical.set_visible(True)
        horizontal.set_visible(True)
        if self._hover_annotation is not None:
            self._hover_annotation.xy = (x_value, y_value)
            self._hover_annotation.set_text(
                f"x = {self._format_coordinate_value(x_value)}\ny = {self._format_coordinate_value(y_value)}"
            )
            self._hover_annotation.set_visible(True)
        if self._hover_background is None:
            self.canvas.draw_idle()
            return
        try:
            self.canvas.restore_region(self._hover_background)
            ax.draw_artist(vertical)
            ax.draw_artist(horizontal)
            if self._hover_annotation is not None:
                ax.draw_artist(self._hover_annotation)
            self.canvas.blit(ax.bbox)
        except Exception:
            self.canvas.draw_idle()

    def _hide_hover_crosshair(self) -> None:
        if self.canvas is None or self._hover_crosshair is None:
            return
        changed = False
        for line in self._hover_crosshair:
            if line.get_visible():
                line.set_visible(False)
                changed = True
        if self._hover_annotation is not None and self._hover_annotation.get_visible():
            self._hover_annotation.set_visible(False)
            changed = True
        if changed:
            if self._hover_background is None or self._hover_axes is None:
                self.canvas.draw_idle()
                return
            try:
                self.canvas.restore_region(self._hover_background)
                self.canvas.blit(self._hover_axes.bbox)
            except Exception:
                self.canvas.draw_idle()

    def _enable_plot_interaction(self) -> None:
        if self.canvas is None:
            return
        self._prepare_hover_overlay()
        self._hover_draw_connection = self.canvas.mpl_connect("draw_event", self._capture_hover_background)

        def on_scroll(event) -> None:
            if event.inaxes is None or event.xdata is None or event.ydata is None:
                return
            now = time.perf_counter()
            if now - self._last_scroll_time < 0.025:
                return
            self._last_scroll_time = now

            step = getattr(event, "step", None)
            if not step:
                step = 1 if event.button == "up" else -1
            step = max(-3, min(3, step))
            scale = 0.9 ** step
            ax = event.inaxes
            x_left, x_right = ax.get_xlim()
            y_bottom, y_top = ax.get_ylim()
            x_span = x_right - x_left
            y_span = y_top - y_bottom
            if x_span == 0 or y_span == 0:
                return
            new_width = x_span * scale
            new_height = y_span * scale
            rel_x = (x_right - event.xdata) / x_span
            rel_y = (y_top - event.ydata) / y_span
            self._hide_hover_crosshair()
            self._hover_background = None
            ax.set_xlim(event.xdata - new_width * (1 - rel_x), event.xdata + new_width * rel_x)
            ax.set_ylim(event.ydata - new_height * (1 - rel_y), event.ydata + new_height * rel_y)
            self._sync_x_range_controls(ax)
            self.canvas.draw_idle()

        def on_press(event) -> None:
            if event.inaxes is None or event.button != 1:
                return
            ax = event.inaxes
            self._pan_state = (ax, event.x, event.y, ax.get_xlim(), ax.get_ylim())

        def on_motion(event) -> None:
            if self._pan_state is None:
                return
            ax, start_x, start_y, old_xlim, old_ylim = self._pan_state
            bbox = ax.bbox
            if bbox.width == 0 or bbox.height == 0:
                return
            dx_pixels = event.x - start_x
            dy_pixels = event.y - start_y
            x_span = old_xlim[1] - old_xlim[0]
            y_span = old_ylim[1] - old_ylim[0]
            dx = dx_pixels / bbox.width * x_span
            dy = dy_pixels / bbox.height * y_span
            self._hide_hover_crosshair()
            self._hover_background = None
            ax.set_xlim(old_xlim[0] - dx, old_xlim[1] - dx)
            ax.set_ylim(old_ylim[0] - dy, old_ylim[1] - dy)
            self._sync_x_range_controls(ax)
            self.canvas.draw_idle()
            return
            
        def on_hover(event) -> None:
            if self._pan_state is not None:
                self._hide_hover_crosshair()
                return
            self._update_hover_crosshair(event)

        def on_release(_event) -> None:
            self._pan_state = None

        self.canvas.mpl_connect("scroll_event", on_scroll)
        self.canvas.mpl_connect("button_press_event", on_press)
        self.canvas.mpl_connect("motion_notify_event", on_motion)
        self.canvas.mpl_connect("motion_notify_event", on_hover)
        self.canvas.mpl_connect("button_release_event", on_release)
        self.canvas.mpl_connect("figure_leave_event", lambda _event: self._hide_hover_crosshair())
