"""Frontend application for PySciCompTool."""

from __future__ import annotations

import ctypes
import multiprocessing
import queue
import sys
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk
import threading
import time

from 后端 import data_analysis, numeric_calc, symbolic_calc
from . import common_widgets, settings, theme_switcher, themes
from .theme_models import AppTheme
from .plot_view import DataPlotView
from .startup_splash import StartupSplash


APP_TITLE = "星算工坊"
APP_USER_MODEL_ID = "StarCalc.Workshop.PySciCompTool"
WINDOW_SIZE = "2280x1520"
DESIGN_WIDTH = 2280
DESIGN_HEIGHT = 1520


def _resource_path(relative_path: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parents[1] / relative_path


APP_ICON_PATH = _resource_path("assets/app_icon.ico")
APP_ICON_PNG_PATH = _resource_path("assets/app_icon.png")


def _calculation_process(task_type: str, action_name: str, payload: dict[str, str], result_queue) -> None:
    """Run a user-requested calculation outside Tk's event thread.

    The process boundary gives the cancel button a real effect: terminating a
    worker cannot leave SymPy or SciPy running in Tk's UI thread.
    """
    try:
        expression = payload.get("expression", "")
        variable = payload.get("variable", "x") or "x"
        if not expression:
            raise ValueError("empty expression")

        if task_type == "symbolic":
            # Reject explosive power/factorial expressions before starting SymPy.
            if symbolic_calc._has_dangerous_growth(expression):
                raise ValueError("dangerous expression")
            if action_name == "表达式计算":
                result = symbolic_calc.evaluate_expression(expression)
            elif action_name == "求导":
                result = symbolic_calc.derivative(expression, variable)
            elif action_name == "不定积分":
                result = symbolic_calc.indefinite_integral(expression, variable)
            elif action_name == "定积分":
                result = symbolic_calc.definite_integral(
                    expression, variable, payload.get("lower", "0"), payload.get("upper", "1")
                )
            elif action_name == "方程求解":
                prepared = symbolic_calc._prepare_expression_text(expression)
                result = symbolic_calc._solve_equation_worker(prepared, variable)
            elif action_name == "傅里叶变换":
                result = symbolic_calc.fourier_transform(expression, variable, payload.get("frequency", "k") or "k")
            else:
                raise ValueError("unknown symbolic action")
        elif task_type == "numeric":
            if action_name == "数值积分":
                result = numeric_calc.numeric_integral(
                    expression, payload.get("lower", "0"), payload.get("upper", "1"), variable
                )
            elif action_name == "数值求导":
                result = numeric_calc.numeric_derivative(expression, payload.get("point", "0"), variable)
            elif action_name == "数值求根":
                result = numeric_calc.numeric_root(
                    expression,
                    payload.get("lower", ""),
                    payload.get("upper", ""),
                    variable,
                    payload.get("root_count", ""),
                )
            else:
                raise ValueError("unknown numeric action")
        else:
            raise ValueError("unknown calculation type")

        result_queue.put((True, result))
    except Exception:
        result_queue.put((False, "错误"))


def _equation_solver_process(expression: str, variable: str, result_queue) -> None:
    """Backward-compatible dedicated entry point for older saved sessions."""
    try:
        if symbolic_calc._has_dangerous_growth(expression):
            result_queue.put((False, "错误"))
            return
        prepared = symbolic_calc._prepare_expression_text(expression)
        result = symbolic_calc._solve_equation_worker(prepared, variable)
        result_queue.put((True, result))
    except Exception:
        result_queue.put((False, "错误"))


def _enable_high_dpi_awareness() -> None:
    """Avoid blurry Tkinter windows on Windows display scaling."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class ScientificCalculatorApp:
    """Main GUI application."""

    MODES = ("表达式计算", "求导", "不定积分", "定积分", "方程求解", "傅里叶变换")
    NUMERIC_MODES = ("数值积分", "数值求导", "数值求根")

    def __init__(self, root: tk.Tk, initial_theme_name: str | None = None) -> None:
        self.root = root
        self.status_var = tk.StringVar(value="就绪")
        self.initial_theme_name = initial_theme_name or themes.DEFAULT_THEME_NAME
        self.theme_var = tk.StringVar(value=self.initial_theme_name)
        self.current_theme: AppTheme | None = None
        self.result_text: tk.Text | None = None
        self.symbolic_expression: tk.Text | None = None
        self.symbolic_mode = tk.StringVar(value="表达式计算")
        self.symbolic_variable = tk.StringVar(value="x")
        self.symbolic_lower = tk.StringVar(value="0")
        self.symbolic_upper = tk.StringVar(value="1")
        self.symbolic_frequency = tk.StringVar(value="k")
        self.symbolic_parameter_frame: ttk.Frame | None = None
        self.symbolic_keypad_frame: ttk.Frame | None = None
        self.symbolic_mode_menu: tk.Menu | None = None
        self._auto_calc_job: str | None = None
        self._calculation_process: multiprocessing.Process | None = None
        self._calculation_result_queue = None
        self._calculation_poll_job: str | None = None
        self._calculation_task_type: str | None = None
        self._calculation_action_name: str | None = None
        self.symbolic_start_button: ttk.Button | None = None
        self.symbolic_cancel_button: ttk.Button | None = None
        self.numeric_expression: tk.Text | None = None
        self.numeric_result_text: tk.Text | None = None
        self.numeric_mode = tk.StringVar(value="数值积分")
        self.numeric_variable = tk.StringVar(value="x")
        self.numeric_lower = tk.StringVar(value="0")
        self.numeric_upper = tk.StringVar(value="1")
        self.numeric_point = tk.StringVar(value="0")
        self.numeric_root_count = tk.StringVar(value="")
        self.numeric_hint = tk.StringVar(value="")
        self.numeric_parameter_frame: ttk.Frame | None = None
        self.numeric_keypad_frame: ttk.Frame | None = None
        self.numeric_mode_menu: tk.Menu | None = None
        self._numeric_auto_calc_job: str | None = None
        self.numeric_start_button: ttk.Button | None = None
        self.numeric_cancel_button: ttk.Button | None = None
        self._data_import_thread: threading.Thread | None = None
        self._data_import_result_queue: queue.Queue = queue.Queue()
        self._data_import_poll_job: str | None = None
        self._data_import_request_id = 0
        self.data_frame = None
        self.data_stats = None
        self.data_file_var = tk.StringVar(value="尚未导入数据")
        self.data_column_var = tk.StringVar(value="")
        self.data_column_selector: ttk.Combobox | None = None
        self.data_preview_table: ttk.Treeview | None = None
        self.data_stats_table: ttk.Treeview | None = None
        self.data_controls_frame: ttk.LabelFrame | None = None
        self.data_import_button: ttk.Button | None = None
        self.data_file_label: tk.Label | None = None
        self.data_column_caption: tk.Label | None = None
        self.data_current_stats_button: ttk.Button | None = None
        self.data_all_stats_button: ttk.Button | None = None
        self.data_export_stats_button: ttk.Button | None = None
        self._data_controls_compact: bool | None = None
        self.plot_view: DataPlotView | None = None
        self.notebook: ttk.Notebook | None = None
        self.dashboard_chart_preview: tk.Canvas | None = None
        self.dashboard_function_card: ttk.LabelFrame | None = None
        self.dashboard_home_frame: ttk.Frame | None = None
        self.dashboard_overview: ttk.Frame | None = None
        self.dashboard_input_card: ttk.LabelFrame | None = None
        self.dashboard_result_card: ttk.LabelFrame | None = None
        self.dashboard_data_card: ttk.LabelFrame | None = None
        self._dashboard_compact_mode: bool | None = None
        self.dashboard_card_labels: list[tuple[tk.Label, tk.Label]] = []
        self.dashboard_card_widgets: list[tk.Frame] = []
        self._skinned_labels: list[tuple[tk.Label, str, str]] = []
        self.topbar_title_label: tk.Label | None = None
        self.symbolic_display_frame: ttk.LabelFrame | None = None
        self.numeric_display_frame: ttk.LabelFrame | None = None
        self._responsive_job: str | None = None
        self._text_fit_job: str | None = None
        self._theme_animation_job: str | None = None
        self._theme_animation_window: tk.Toplevel | None = None
        self._theme_animation_canvas: tk.Canvas | None = None
        self._theme_animation_target = self.initial_theme_name
        self._last_ui_scale = 0.0
        self._last_font_scale = 0.0

        self._bind_parameter_traces()
        self._configure_window()
        self._configure_style()
        self._build_layout()
        if self.current_theme is not None:
            self._apply_text_widget_theme(self.current_theme)
            self._apply_responsive_scale(force=True)
        self._apply_button_cursor(self.root)
        self.root.bind("<Configure>", self._schedule_responsive_update, add="+")
        self.root.after(160, lambda: self._apply_responsive_scale(force=True))
        self.root.after(420, lambda: self._apply_responsive_scale(force=True))

    def _bind_parameter_traces(self) -> None:
        for variable in (
            self.numeric_variable,
            self.numeric_lower,
            self.numeric_upper,
            self.numeric_point,
            self.numeric_root_count,
        ):
            variable.trace_add("write", lambda *_args: self._schedule_numeric_auto_calculate())

    def _configure_window(self) -> None:
        self.root.title(APP_TITLE)
        self._apply_window_icon()
        window_size = settings.load_window_size(WINDOW_SIZE)
        self.root.geometry(self._centered_geometry(window_size))
        self.root.minsize(1120, 720)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _apply_window_icon(self) -> None:
        self._window_icon_image = None
        if APP_ICON_PNG_PATH.exists():
            try:
                self._window_icon_image = tk.PhotoImage(file=str(APP_ICON_PNG_PATH))
                self.root.iconphoto(True, self._window_icon_image)
            except tk.TclError:
                self._window_icon_image = None
        if APP_ICON_PATH.exists():
            try:
                self.root.iconbitmap(default=str(APP_ICON_PATH))
            except tk.TclError:
                pass
        # Tk's icon APIs are not always reflected in the Windows taskbar.
        # Set both Win32 icon slots explicitly, following the proven approach
        # used by the paper-search desktop app.
        threading.Thread(target=self._apply_windows_taskbar_icon, daemon=True).start()

    def _apply_windows_taskbar_icon(self) -> None:
        if sys.platform != "win32":
            return

        for _ in range(50):
            time.sleep(0.1)
            try:
                hwnd = ctypes.windll.user32.FindWindowW(None, APP_TITLE)
                if not hwnd:
                    continue

                IMAGE_ICON = 1
                LR_LOADFROMFILE = 0x00000010
                WM_SETICON = 0x0080
                ICON_BIG = 0
                ICON_SMALL = 1

                if getattr(sys, "frozen", False):
                    # The packaged app's icon is an exe resource.  Loading an
                    # exe with LR_LOADFROMFILE is unreliable; ExtractIconExW
                    # reads the embedded 32/16 px icon resources directly.
                    large_icon = ctypes.c_void_p()
                    small_icon = ctypes.c_void_p()
                    extracted = ctypes.windll.shell32.ExtractIconExW(
                        str(sys.executable), 0, ctypes.byref(large_icon), ctypes.byref(small_icon), 1
                    )
                    if not extracted:
                        return
                    icon_handles = ((ICON_BIG, large_icon.value), (ICON_SMALL, small_icon.value))
                else:
                    if not APP_ICON_PATH.exists():
                        return
                    icon_handles = []
                    for slot, size in ((ICON_BIG, 32), (ICON_SMALL, 16)):
                        hicon = ctypes.windll.user32.LoadImageW(
                            None, str(APP_ICON_PATH), IMAGE_ICON, size, size, LR_LOADFROMFILE
                        )
                        icon_handles.append((slot, hicon))

                for slot, hicon in icon_handles:
                    if hicon:
                        ctypes.windll.user32.SendMessageW(
                            hwnd,
                            WM_SETICON,
                            slot,
                            hicon,
                        )
                        # Keep a Python reference for the lifetime of the app.
                        # Windows owns the displayed copy, but this also avoids
                        # accidental early cleanup of the handle wrapper.
                        if not hasattr(self, "_taskbar_icons"):
                            self._taskbar_icons = []
                        self._taskbar_icons.append(hicon)
                return
            except Exception:
                return

    def _centered_geometry(self, size: str) -> str:
        try:
            width_text, height_text = size.lower().split("x", 1)
            width = int(width_text)
            height = int(height_text)
        except ValueError:
            width, height = 1200, 800
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = min(width, screen_width)
        height = min(height, screen_height)
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        return f"{width}x{height}+{x}+{y}"

    def _on_close(self) -> None:
        self._cancel_running_calculation(show_message=False)
        try:
            width = max(self.root.winfo_width(), 1280)
            height = max(self.root.winfo_height(), 800)
            settings.save_window_size(f"{width}x{height}")
        except tk.TclError:
            pass
        self.root.destroy()

    def _configure_style(self) -> None:
        self.current_theme = theme_switcher.apply_theme(self.root, self.initial_theme_name)
        self.root.configure(background=self.current_theme.background)

    def _build_layout(self) -> None:
        self._build_topbar()

        main = ttk.Frame(self.root, padding=(12, 8, 12, 8))
        main.pack(expand=True, fill="both")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(main)
        self.notebook = notebook
        notebook.grid(row=0, column=0, sticky="nsew")
        notebook.add(self._build_dashboard_home(notebook), text="首页")
        notebook.add(self._build_symbolic_tab(notebook), text="符号计算")
        notebook.add(self._build_numeric_tab(notebook), text="数值计算")
        notebook.add(self._build_data_tab(notebook), text="数据分析")
        notebook.add(self._build_plot_tab(notebook), text="数据可视化")

        self._build_statusbar()

    def _select_tab(self, index: int) -> None:
        if self.notebook is None:
            return
        try:
            self.notebook.select(index)
        except tk.TclError:
            return

    def _build_dashboard_home(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = common_widgets.new_tab_frame(parent)
        self.dashboard_home_frame = frame
        for column, weight in enumerate((3, 3, 3, 4)):
            frame.columnconfigure(column, weight=weight)
        frame.rowconfigure(0, weight=0)
        frame.rowconfigure(1, weight=3)
        frame.rowconfigure(2, weight=2)

        overview = ttk.Frame(frame, padding=(10, 10), style="Surface.TFrame")
        self.dashboard_overview = overview
        overview.grid(row=0, column=0, columnspan=4, sticky="ew", padx=6, pady=(0, 8))
        for column in range(4):
            overview.columnconfigure(column, weight=1)
        self._dashboard_metric(overview, 0, "计算模块", "2 类", "符号计算 / 数值计算")
        self._dashboard_metric(overview, 1, "数据能力", "CSV / Excel", "导入、统计、导出")
        self._dashboard_metric(overview, 2, "图表工具", "3 种", "折线、散点、拟合")
        self._dashboard_metric(overview, 3, "当前状态", "就绪", "可直接开始操作")

        input_card = common_widgets.section(frame, "快速开始", 1, 0)
        self.dashboard_input_card = input_card
        input_card.rowconfigure(3, weight=1)
        self._skinned_label(
            input_card, "surface", "heading",
            text="选择一个入口开始本次计算。",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(
            input_card,
            text="符号计算",
            style="Primary.TButton",
            command=lambda: self._select_tab(1),
        ).grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(
            input_card,
            text="数值计算",
            command=lambda: self._select_tab(2),
        ).grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(
            input_card,
            text="导入数据",
            command=self._import_data_file,
        ).grid(row=3, column=0, sticky="new")

        function_card = common_widgets.section(frame, "功能工作台", 1, 1)
        self.dashboard_function_card = function_card
        function_card.grid(row=1, column=1, columnspan=2, sticky="nsew", padx=6, pady=6)
        for column in range(3):
            function_card.columnconfigure(column, weight=1, uniform="dashboard_actions_columns")
        for row in range(3):
            function_card.rowconfigure(row, weight=1, uniform="dashboard_actions_rows", minsize=104)
        function_buttons = (
            ("d/dx\n求导", lambda: self._open_symbolic_mode(1)),
            ("∫\n积分", lambda: self._open_symbolic_mode(2)),
            ("f(x)=0\n方程求解", lambda: self._open_symbolic_mode(4)),
            ("F\n傅里叶变换", lambda: self._open_symbolic_mode(5)),
            ("Σ\n统计分析", lambda: self._select_tab(3)),
            ("≈\n曲线拟合", lambda: self._select_plot_fit()),
            ("∿\n绘制图表", lambda: self._select_tab(4)),
            ("Excel\n导入数据", self._import_data_file),
            ("↗\n导出结果", self._export_data_stats),
        )
        for index, (text, command) in enumerate(function_buttons):
            self._dashboard_card_button(function_card, index // 3, index % 3, text, command)

        result_card = common_widgets.section(frame, "结果与图表", 1, 3)
        self.dashboard_result_card = result_card
        result_card.rowconfigure(1, weight=1)
        self._skinned_label(
            result_card, "surface", "text",
            textvariable=self.status_var,
            wraplength=360,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.dashboard_chart_preview = tk.Canvas(
            result_card,
            height=150,
            highlightthickness=0,
            background=self.current_theme.chart_background if self.current_theme is not None else "#ffffff",
        )
        self.dashboard_chart_preview.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.dashboard_chart_preview.bind("<Configure>", lambda _event: self._redraw_dashboard_chart_preview())
        chart_hint = self._skinned_label(
            result_card, "surface", "hint",
            text="导入数据后可生成折线图、\n散点图和多项式拟合图。",
            justify="center",
        )
        # Keep this deliberately balanced two-line hint intact while resizing.
        chart_hint._keep_explicit_wrap = True
        chart_hint.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(result_card, text="打开图表工具", command=lambda: self._select_tab(4)).grid(row=3, column=0, sticky="ew")

        data_card = common_widgets.section(frame, "数据文件与预览", 2, 0)
        self.dashboard_data_card = data_card
        data_card.grid(columnspan=4)
        # With only the file controls shown, keep the compact row centered in
        # the expandable card instead of leaving a large empty area below it.
        data_card.grid_anchor("center")
        data_card.columnconfigure(0, weight=1)
        data_card.columnconfigure(1, weight=0)
        self._skinned_label(
            data_card, "surface", "hint",
            textvariable=self.data_file_var, wraplength=760,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 12))
        ttk.Button(data_card, text="导入 CSV/Excel", style="Primary.TButton", command=self._import_data_file).grid(
            row=0, column=1, sticky="ew", padx=(0, 8)
        )
        ttk.Button(data_card, text="进入数据分析", command=lambda: self._select_tab(3)).grid(
            row=0, column=2, sticky="ew"
        )
        self._redraw_dashboard_chart_preview()

        return frame

    def _update_dashboard_layout(self, compact: bool) -> None:
        """Prioritize the functional workbench when the home page is narrow."""
        frame = self.dashboard_home_frame
        overview = self.dashboard_overview
        input_card = self.dashboard_input_card
        function_card = self.dashboard_function_card
        result_card = self.dashboard_result_card
        data_card = self.dashboard_data_card
        if None in (frame, overview, input_card, function_card, result_card, data_card):
            return
        if compact == self._dashboard_compact_mode:
            return
        self._dashboard_compact_mode = compact

        if compact:
            overview.grid_remove()
            input_card.grid_remove()
            result_card.grid_remove()
            function_card.grid(row=1, column=0, columnspan=4, sticky="nsew", padx=6, pady=(0, 6))
            data_card.grid(row=2, column=0, columnspan=4, sticky="ew", padx=6, pady=(0, 6))
            frame.rowconfigure(0, weight=0, minsize=0)
            frame.rowconfigure(1, weight=1, minsize=0)
            frame.rowconfigure(2, weight=0, minsize=0)
        else:
            overview.grid(row=0, column=0, columnspan=4, sticky="ew", padx=6, pady=(0, 8))
            input_card.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
            function_card.grid(row=1, column=1, columnspan=2, sticky="nsew", padx=6, pady=6)
            result_card.grid(row=1, column=3, sticky="nsew", padx=6, pady=6)
            data_card.grid(row=2, column=0, columnspan=4, sticky="ew", padx=6, pady=6)
            frame.rowconfigure(0, weight=0, minsize=0)
            frame.rowconfigure(1, weight=3, minsize=0)
            frame.rowconfigure(2, weight=2, minsize=0)
        self.root.after_idle(self._redraw_dashboard_chart_preview)

    def _dashboard_metric(self, parent: ttk.Frame, column: int, title: str, value: str, detail: str) -> None:
        card = ttk.Frame(parent, padding=(12, 9), style="DashboardMetric.TFrame")
        card.grid(row=0, column=column, sticky="ew", padx=5)
        self._skinned_label(card, "surface_alt", "hint", text=title).grid(row=0, column=0, sticky="w")
        self._skinned_label(card, "surface_alt", "heading", text=value, font=("Microsoft YaHei UI", 18, "bold")).grid(row=1, column=0, sticky="w", pady=(3, 1))
        self._skinned_label(card, "surface_alt", "hint", text=detail).grid(row=2, column=0, sticky="w")

    def _redraw_dashboard_chart_preview(self) -> None:
        canvas = self.dashboard_chart_preview
        if canvas is None:
            return
        theme = self.current_theme
        chart_bg = theme.chart_background if theme is not None else "#ffffff"
        chart_line = theme.chart_line if theme is not None else "#2563eb"
        chart_point = theme.chart_point if theme is not None else "#f97316"
        chart_fit = theme.chart_fit if theme is not None else "#16a34a"
        chart_grid = theme.border if theme is not None else "#d9e2ec"

        canvas.configure(background=chart_bg)
        canvas.delete("all")
        width = max(canvas.winfo_width(), 260)
        height = max(canvas.winfo_height(), 130)
        left, right = 28, width - 18
        top, bottom = 18, height - 24
        canvas.create_rectangle(left, top, right, bottom, outline=chart_grid)
        for i in range(1, 4):
            y = top + (bottom - top) * i / 4
            canvas.create_line(left, y, right, y, fill=chart_grid)
        points = (
            (left + 10, bottom - 18),
            (left + 58, bottom - 52),
            (left + 105, bottom - 36),
            (left + 158, top + 34),
            (right - 55, top + 58),
            (right - 12, top + 40),
        )
        canvas.create_line(*[coord for point in points for coord in point], fill=chart_line, width=3, smooth=True)
        canvas.create_line(left + 12, bottom - 42, right - 12, top + 38, fill=chart_fit, width=2, dash=(5, 3))
        for x, y in points:
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=chart_point, outline=chart_bg)

    def _dashboard_card_button(
        self,
        parent: ttk.Frame,
        row: int,
        column: int,
        text: str,
        command,
    ) -> None:
        theme = self.current_theme
        background = theme.surface if theme is not None else "#ffffff"
        hover_background = theme.surface_alt if theme is not None else "#f3f6fa"
        border = theme.border if theme is not None else "#d9e2ec"
        text_color = theme.heading if theme is not None else "#0f172a"
        accent = theme.accent if theme is not None else "#2563eb"

        symbol, label = (text.split("\n", 1) + [""])[:2]
        card = tk.Frame(
            parent,
            background=background,
            highlightbackground=border,
            highlightcolor=border,
            highlightthickness=1,
            cursor="hand2",
        )
        card.grid(row=row, column=column, sticky="nsew", padx=5, pady=5)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)

        symbol_label = tk.Label(
            card,
            text=symbol,
            anchor="s",
            justify="center",
            background=background,
            foreground=text_color,
            font=("Microsoft YaHei UI", 18, "bold"),
            cursor="hand2",
        )
        symbol_label.grid(row=0, column=0, sticky="sew", padx=8, pady=(18, 0))
        text_label = tk.Label(
            card,
            text=label,
            anchor="n",
            justify="center",
            background=background,
            foreground=text_color,
            font=("Microsoft YaHei UI", 16, "bold"),
            cursor="hand2",
        )
        text_label.grid(row=1, column=0, sticky="new", padx=8, pady=(2, 18))
        self.dashboard_card_labels.append((symbol_label, text_label))
        self.dashboard_card_widgets.append(card)

        def set_colors(bg: str, fg: str) -> None:
            card.configure(background=bg, highlightbackground=fg)
            symbol_label.configure(background=bg, foreground=fg)
            text_label.configure(background=bg, foreground=fg)

        def theme_colors() -> tuple[str, str, str, str]:
            active_theme = self.current_theme
            if active_theme is None:
                return "#ffffff", "#f3f6fa", "#0f172a", "#2563eb"
            return active_theme.surface, active_theme.surface_alt, active_theme.heading, active_theme.accent

        def on_enter(_event: tk.Event) -> None:
            _background, current_hover, _text, current_accent = theme_colors()
            set_colors(current_hover, current_accent)

        def on_leave(_event: tk.Event) -> None:
            current_background, _hover, current_text, _accent = theme_colors()
            set_colors(current_background, current_text)

        def on_click(_event: tk.Event) -> None:
            command()

        for widget in (card, symbol_label, text_label):
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<Button-1>", on_click)

    def _open_symbolic_mode(self, mode_index: int) -> None:
        self._select_tab(1)
        try:
            self._set_symbolic_mode(self.MODES[mode_index])
        except IndexError:
            return

    def _select_plot_fit(self) -> None:
        self._select_tab(4)
        if self.plot_view is not None:
            self.plot_view.kind_var.set("fit")
            self.status_var.set("已切换到多项式拟合，请先导入数据并选择列")

    def _build_topbar(self) -> None:
        topbar = ttk.Frame(self.root, padding=(12, 10, 12, 6), style="Topbar.TFrame")
        topbar.pack(fill="x")
        topbar.columnconfigure(0, weight=1)

        self.topbar_title_label = self._skinned_label(topbar, "background", "heading", text=APP_TITLE, font=("Microsoft YaHei UI", 18, "bold"))
        self.topbar_title_label.grid(row=0, column=0, sticky="w")
        theme_group = ttk.Frame(topbar)
        theme_group.grid(row=0, column=1, sticky="e")
        self._skinned_label(theme_group, "background", "text", text="界面皮肤").pack(side="left", padx=(0, 8))
        theme_selector = ttk.Combobox(
            theme_group,
            textvariable=self.theme_var,
            values=themes.theme_names(),
            state="readonly",
            width=12,
        )
        theme_selector.pack(side="left")
        theme_selector.bind("<<ComboboxSelected>>", self._start_theme_animation, add="+")

    def _build_statusbar(self) -> None:
        statusbar = ttk.Frame(self.root, padding=(12, 6), style="Status.TFrame")
        statusbar.pack(fill="x")
        self._skinned_label(statusbar, "surface", "text", textvariable=self.status_var).pack(side="left")
        self._skinned_label(statusbar, "surface", "text", text=APP_TITLE).pack(side="right")

    def _build_symbolic_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14, style="Surface.TFrame")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=3, uniform="symbolic")
        frame.rowconfigure(1, weight=4, uniform="symbolic")

        display = ttk.LabelFrame(frame, text="公式与结果", padding=14, style="Card.TLabelframe")
        self.symbolic_display_frame = display
        display.grid(row=0, column=0, sticky="nsew")
        display.columnconfigure(0, weight=1)
        display.rowconfigure(0, weight=1)
        display.rowconfigure(1, weight=2)

        mode_button = ttk.Menubutton(display, textvariable=self.symbolic_mode, width=12)
        mode_button.grid(row=0, column=1, sticky="ne", padx=(8, 0))
        menu_font = ("Microsoft YaHei UI", 12, "bold")
        mode_menu = tk.Menu(
            mode_button,
            tearoff=False,
            font=menu_font,
            bg=self.current_theme.surface if self.current_theme is not None else "#ffffff",
            fg=self.current_theme.text if self.current_theme is not None else "#000000",
            activebackground=self.current_theme.surface_alt if self.current_theme is not None else "#eef2ff",
            activeforeground=self.current_theme.accent if self.current_theme is not None else "#2563eb",
        )
        for mode in self.MODES:
            mode_menu.add_command(label=mode, command=lambda value=mode: self._set_symbolic_mode(value))
        mode_button["menu"] = mode_menu
        self.symbolic_mode_menu = mode_menu

        symbolic_text_bg = self.current_theme.surface if self.current_theme is not None else "#ffffff"
        symbolic_text_fg = self.current_theme.text if self.current_theme is not None else "#000000"
        self.symbolic_expression = tk.Text(
            display,
            height=2,
            wrap="none",
            undo=True,
            maxundo=100,
            font=("Microsoft YaHei UI", 28),
            background=symbolic_text_bg,
            foreground=symbolic_text_fg,
            insertbackground=self.current_theme.accent if self.current_theme is not None else "#000000",
            relief="solid",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=self.current_theme.border if self.current_theme is not None else "#d9e2ec",
        )
        self.symbolic_expression.grid(row=0, column=0, sticky="nsew")
        self.symbolic_expression.tag_configure("placeholder", foreground="#9ca3af")
        self.symbolic_expression.bind("<KeyPress>", self._prepare_text_keypress)
        self.symbolic_expression.bind("<KeyRelease>", lambda _event: self._schedule_auto_calculate())
        self.symbolic_expression.bind("<Return>", lambda _event: "break")
        self.symbolic_expression.bind("<BackSpace>", self._smart_backspace_event)
        self.symbolic_expression.bind("<Control-a>", self._select_text_content)
        self.symbolic_expression.bind("<Control-A>", self._select_text_content)
        self.symbolic_expression.bind("<Control-z>", self._undo_symbolic_expression)

        self.result_text = tk.Text(
            display,
            height=4,
            wrap="word",
            font=("Microsoft YaHei UI", 20),
            background=symbolic_text_bg,
            foreground=symbolic_text_fg,
            relief="solid",
            borderwidth=1,
            highlightthickness=0,
        )
        self.result_text.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        self._lock_display_text(self.result_text)
        self._write_result("")

        self.symbolic_parameter_frame = ttk.Frame(display, height=42, style="Surface.TFrame")
        self.symbolic_parameter_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.symbolic_parameter_frame.grid_propagate(False)

        keypad_area = ttk.LabelFrame(frame, text="点按键盘", padding=10, style="Card.TLabelframe")
        keypad_area.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        keypad_area.columnconfigure(0, weight=1)
        keypad_area.rowconfigure(0, weight=1)
        self.symbolic_keypad_frame = ttk.Frame(keypad_area, style="Surface.TFrame")
        self.symbolic_keypad_frame.grid(row=0, column=0, sticky="nsew")

        self._refresh_symbolic_controls()
        return frame

    def _lock_display_text(self, text_widget: tk.Text) -> None:
        text_widget.bind("<Key>", lambda _event: "break")

    def _refresh_symbolic_controls(self) -> None:
        if self.symbolic_parameter_frame is None or self.symbolic_keypad_frame is None:
            return

        for child in self.symbolic_parameter_frame.winfo_children():
            child.destroy()
        for child in self.symbolic_keypad_frame.winfo_children():
            child.destroy()

        mode = self.symbolic_mode.get()
        if mode != "表达式计算":
            self._skinned_label(self.symbolic_parameter_frame, "surface", "hint", text="变量").pack(side="left")
            ttk.Entry(self.symbolic_parameter_frame, width=8, textvariable=self.symbolic_variable).pack(
                side="left", padx=(6, 14)
            )
        is_running = self._calculation_process is not None
        self.symbolic_cancel_button = ttk.Button(
            self.symbolic_parameter_frame,
            text="取消计算",
            command=self._cancel_running_calculation,
            style="DataAction.TButton",
            state="normal" if is_running else "disabled",
        )
        self.symbolic_cancel_button.pack(side="right")
        self.symbolic_start_button = ttk.Button(
            self.symbolic_parameter_frame,
            text="开始计算",
            command=self._start_symbolic_calculation,
            style="Primary.TButton",
            state="disabled" if is_running else "normal",
        )
        self.symbolic_start_button.pack(side="right", padx=(0, 8))
        if mode == "定积分":
            self._skinned_label(self.symbolic_parameter_frame, "surface", "hint", text="下限").pack(side="left")
            ttk.Entry(self.symbolic_parameter_frame, width=8, textvariable=self.symbolic_lower).pack(
                side="left", padx=(6, 14)
            )
            self._skinned_label(self.symbolic_parameter_frame, "surface", "hint", text="上限").pack(side="left")
            ttk.Entry(self.symbolic_parameter_frame, width=8, textvariable=self.symbolic_upper).pack(
                side="left", padx=(6, 14)
            )
        if mode == "傅里叶变换":
            self._skinned_label(self.symbolic_parameter_frame, "surface", "hint", text="变换后变量").pack(side="left")
            ttk.Entry(self.symbolic_parameter_frame, width=8, textvariable=self.symbolic_frequency).pack(
                side="left", padx=(6, 14)
            )
        self._build_symbolic_buttons(self.symbolic_keypad_frame, self._button_rows_for_mode(mode))
        self._apply_button_cursor(self.symbolic_keypad_frame)

    def _button_rows_for_mode(self, mode: str) -> tuple[tuple[tuple[str, str] | tuple[str, str, int], ...], ...]:
        variable_button = ("x", "x") if mode != "表达式计算" else ("x³", "^3")
        equals_button = ("=", "=") if mode == "方程求解" else ("=", "__calculate__")
        return (
            (("(", "("), (")", ")"), ("π", "π"), ("e", "e"), ("AC", "__clear__"), ("⌫", "__backspace__"), ("%", "/100"), ("/", "/")),
            (("x²", "^2"), ("x³", "^3"), ("xʸ", "^"), ("mod", "mod"), ("7", "7"), ("8", "8"), ("9", "9"), ("*", "*")),
            (("n!", "!"), ("1/x", "1/()"), ("√", "√("), ("ⁿ√", "__nth_root__"), ("4", "4"), ("5", "5"), ("6", "6"), ("-", "-")),
            (("sin", "sin("), ("cos", "cos("), ("tan", "tan("), ("ln", "ln("), ("1", "1"), ("2", "2"), ("3", "3"), ("+", "+")),
            (("log", "__log_template__"), ("lg", "lg("), ("| |", "Abs("), ("10ˣ", "10^"), ("x", "x"), ("0", "0"), (".", "."), equals_button),
        )

    def _build_symbolic_buttons(
        self,
        parent: ttk.Frame,
        rows: tuple[tuple[tuple[str, str] | tuple[str, str, int], ...], ...],
    ) -> None:
        for column in range(8):
            parent.columnconfigure(column, weight=1, uniform="symbolic_keypad")
        for row, buttons in enumerate(rows):
            parent.rowconfigure(row, weight=1, minsize=54, uniform="symbolic_keypad_rows")
            column = 0
            for button_info in buttons:
                if len(button_info) == 3:
                    label, token, columnspan = button_info
                else:
                    label, token = button_info
                    columnspan = 1
                ttk.Button(
                    parent,
                    text=label,
                    style="Calculator.TButton",
                    command=lambda value=token: self._handle_symbolic_key(value),
                ).grid(row=row, column=column, columnspan=columnspan, sticky="nsew", padx=5, pady=5)
                column += columnspan

    def _insert_into_expression(self, token: str) -> None:
        if self.symbolic_expression is None:
            return
        self._delete_selection_if_placeholder(self.symbolic_expression)
        if token == "__nth_root__":
            self._insert_nth_root_template(self.symbolic_expression)
            return
        if token == "__log_template__":
            self._insert_log_template(self.symbolic_expression)
            return
        token = self._formula_token_for_insert(token)
        self.symbolic_expression.edit_separator()
        self.symbolic_expression.insert("insert", token)
        if token == "ⁿ√(,)":
            self.symbolic_expression.mark_set("insert", "insert-2c")
        elif token == "1/()":
            self.symbolic_expression.mark_set("insert", "insert-1c")
        else:
            self.symbolic_expression.mark_set("insert", "insert")
        self.symbolic_expression.edit_separator()
        self.symbolic_expression.see("insert")
        self.symbolic_expression.focus_set()

    def _undo_symbolic_expression(self, _event: tk.Event) -> str:
        if self.symbolic_expression is None:
            return "break"
        try:
            self.symbolic_expression.edit_undo()
        except tk.TclError:
            pass
        self.symbolic_expression.see("insert")
        self._schedule_auto_calculate()
        return "break"

    def _insert_nth_root_template(self, text_widget: tk.Text) -> None:
        text_widget.edit_separator()
        text_widget.insert("insert", "ⁿ√(")
        degree_start = text_widget.index("insert")
        text_widget.insert("insert", "次数", "placeholder")
        degree_end = text_widget.index("insert")
        text_widget.insert("insert", ",")
        text_widget.insert("insert", "被开方数", "placeholder")
        text_widget.insert("insert", ")")
        text_widget.mark_set("insert", degree_start)
        text_widget.tag_add("sel", degree_start, degree_end)
        text_widget.edit_separator()
        text_widget.see("insert")
        text_widget.focus_set()

    def _insert_log_template(self, text_widget: tk.Text) -> None:
        """Insert log(底数,真数) with placeholder hints."""
        text_widget.edit_separator()
        text_widget.insert("insert", "log(")
        base_start = text_widget.index("insert")
        text_widget.insert("insert", "底数", "placeholder")
        base_end = text_widget.index("insert")
        text_widget.insert("insert", ",")
        text_widget.insert("insert", "真数", "placeholder")
        text_widget.insert("insert", ")")
        text_widget.mark_set("insert", base_start)
        text_widget.tag_add("sel", base_start, base_end)
        text_widget.edit_separator()
        text_widget.see("insert")
        text_widget.focus_set()

    def _formula_token_for_insert(self, token: str) -> str:
        formula_tokens = {"sin()", "cos()", "tan()", "ln()", "log()", "lg()", "Abs()", "√()"}
        if token in formula_tokens:
            return token[:-1]
        return token

    def _clear_selected_placeholder(self, event: tk.Event) -> str | None:
        if event.keysym in {
            "Left",
            "Right",
            "Up",
            "Down",
            "Home",
            "End",
            "Shift_L",
            "Shift_R",
            "Control_L",
            "Control_R",
            "Alt_L",
            "Alt_R",
        }:
            return None
        widget = event.widget
        if isinstance(widget, tk.Text):
            self._delete_selection_if_placeholder(widget)
        return None

    def _prepare_text_keypress(self, event: tk.Event) -> str | None:
        result = self._clear_selected_placeholder(event)
        if result == "break":
            return result
        if event.keysym in {
            "Left",
            "Right",
            "Up",
            "Down",
            "Home",
            "End",
            "Shift_L",
            "Shift_R",
            "Control_L",
            "Control_R",
            "Alt_L",
            "Alt_R",
            "BackSpace",
            "Delete",
        }:
            return None
        widget = event.widget
        if isinstance(widget, tk.Text):
            self._move_cursor_out_of_operator_token(widget)
        return None

    def _smart_backspace_event(self, event: tk.Event) -> str:
        widget = event.widget
        if isinstance(widget, tk.Text):
            self._smart_backspace(widget)
            if widget is self.symbolic_expression:
                self._schedule_auto_calculate()
            elif widget is self.numeric_expression:
                self._schedule_numeric_auto_calculate()
        return "break"

    def _move_cursor_out_of_operator_token(self, text_widget: tk.Text) -> None:
        try:
            selection = text_widget.tag_ranges("sel")
            if len(selection) == 2:
                return
        except tk.TclError:
            return

        try:
            content = text_widget.get("1.0", "end-1c")
            count_result = text_widget.count("1.0", "insert", "chars")
        except tk.TclError:
            return
        # Tk can temporarily return None while the insert mark is being
        # updated by a key, paste or focus event.  Skip this optional cursor
        # adjustment instead of raising from the Tkinter callback.
        if not count_result:
            return
        cursor = int(count_result[0])
        bounds = self._operator_token_bounds(content, cursor)
        if bounds is None:
            return
        _start, end = bounds
        text_widget.mark_set("insert", f"1.0+{end}c")

    def _operator_token_bounds(self, content: str, cursor: int) -> tuple[int, int] | None:
        operator_words = ("sin", "cos", "tan", "ln", "log", "lg", "Abs", "mod", "sqrt", "root")
        if not content:
            return None

        safe_cursor = max(0, min(cursor, len(content)))
        probe = safe_cursor
        if probe == len(content) or not content[probe].isalpha():
            probe -= 1
        if probe < 0 or not content[probe].isalpha():
            return None

        start = probe
        while start > 0 and content[start - 1].isalpha():
            start -= 1
        end = probe + 1
        while end < len(content) and content[end].isalpha():
            end += 1

        word = content[start:end]
        if word not in operator_words:
            return None
        if not (start < safe_cursor < end):
            return None

        token_end = end
        if token_end < len(content) and content[token_end] == "(":
            match = self._matching_close_paren(content, token_end)
            if match is not None:
                token_end = match + 1
        return start, token_end

    def _matching_close_paren(self, content: str, open_index: int) -> int | None:
        depth = 0
        for index in range(open_index, len(content)):
            char = content[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return index
        return None

    def _delete_selection_if_placeholder(self, text_widget: tk.Text) -> None:
        try:
            selection = text_widget.tag_ranges("sel")
        except tk.TclError:
            return
        if len(selection) != 2:
            return

        selection_start, selection_end = selection
        placeholder_ranges = text_widget.tag_ranges("placeholder")
        selection_is_placeholder = False
        for index in range(0, len(placeholder_ranges), 2):
            placeholder_start = placeholder_ranges[index]
            placeholder_end = placeholder_ranges[index + 1]
            if (
                text_widget.compare(selection_start, ">=", placeholder_start)
                and text_widget.compare(selection_end, "<=", placeholder_end)
            ):
                selection_is_placeholder = True
                break

        if not selection_is_placeholder:
            return

        text_widget.mark_set("_placeholder_insert", selection_start)
        text_widget.mark_gravity("_placeholder_insert", "left")
        for index in range(len(placeholder_ranges) - 2, -1, -2):
            placeholder_start = placeholder_ranges[index]
            placeholder_end = placeholder_ranges[index + 1]
            text_widget.delete(placeholder_start, placeholder_end)
        text_widget.mark_set("insert", "_placeholder_insert")
        text_widget.mark_unset("_placeholder_insert")

    def _select_text_content(self, event: tk.Event) -> str:
        widget = event.widget
        if not isinstance(widget, tk.Text):
            return "break"

        widget.tag_remove("sel", "1.0", "end")
        if not widget.get("1.0", "end-1c").strip():
            widget.mark_set("insert", "1.0")
            return "break"

        widget.tag_add("sel", "1.0", "end-1c")
        widget.mark_set("insert", "end-1c")
        widget.see("insert")
        return "break"

    def _smart_backspace(self, text_widget: tk.Text) -> None:
        self._delete_selection_if_placeholder(text_widget)
        try:
            selection = text_widget.tag_ranges("sel")
            if len(selection) == 2:
                text_widget.delete(selection[0], selection[1])
                return
        except tk.TclError:
            pass

        insert = text_widget.index("insert")
        if text_widget.compare(insert, "<=", "1.0"):
            return

        content = text_widget.get("1.0", "end-1c")
        cursor = int(text_widget.count("1.0", insert, "chars")[0])
        operator_bounds = self._operator_token_bounds(content, cursor)
        if operator_bounds is not None:
            text_widget.delete(f"1.0+{operator_bounds[0]}c", f"1.0+{operator_bounds[1]}c")
            text_widget.see("insert")
            text_widget.focus_set()
            return
        start = self._smart_backspace_start(content, cursor)
        text_widget.delete(f"1.0+{start}c", f"1.0+{cursor}c")
        text_widget.see("insert")
        text_widget.focus_set()

    def _smart_backspace_start(self, content: str, cursor: int) -> int:
        before_cursor = content[:cursor]
        grouped_tokens = (
            "sin(",
            "cos(",
            "tan(",
            "ln(",
            "log(",
            "lg(",
            "Abs(",
            "log(底数,真数)",
            "1/()",
            "10^",
            "e^",
            "/100",
            "mod",
            "^2",
            "^",
            "√(",
            "ⁿ√(,)",
        )
        for token in sorted(grouped_tokens, key=len, reverse=True):
            if before_cursor.endswith(token):
                return cursor - len(token)

        for function_name in ("sin", "cos", "tan", "ln", "log", "lg", "Abs", "sqrt", "root"):
            start = cursor - len(function_name)
            if start >= 0 and content[start:cursor] == function_name:
                if start == 0 or not content[start - 1].isalpha():
                    return start

        return cursor - 1

    def _build_numeric_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=14, style="Surface.TFrame")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=3, uniform="numeric")
        frame.rowconfigure(1, weight=4, uniform="numeric")

        display = ttk.LabelFrame(frame, text="公式与结果", padding=14, style="Card.TLabelframe")
        self.numeric_display_frame = display
        display.grid(row=0, column=0, sticky="nsew")
        display.columnconfigure(0, weight=1)
        display.rowconfigure(0, weight=1)
        display.rowconfigure(1, weight=2)

        mode_button = ttk.Menubutton(display, textvariable=self.numeric_mode, width=12)
        mode_button.grid(row=0, column=1, sticky="ne", padx=(8, 0))
        menu_font = ("Microsoft YaHei UI", 12, "bold")
        mode_menu = tk.Menu(
            mode_button,
            tearoff=False,
            font=menu_font,
            bg=self.current_theme.surface if self.current_theme is not None else "#ffffff",
            fg=self.current_theme.text if self.current_theme is not None else "#000000",
            activebackground=self.current_theme.surface_alt if self.current_theme is not None else "#eef2ff",
            activeforeground=self.current_theme.accent if self.current_theme is not None else "#2563eb",
        )
        for mode in self.NUMERIC_MODES:
            mode_menu.add_command(label=mode, command=lambda value=mode: self._set_numeric_mode(value))
        mode_button["menu"] = mode_menu
        self.numeric_mode_menu = mode_menu

        numeric_text_bg = self.current_theme.surface if self.current_theme is not None else "#ffffff"
        numeric_text_fg = self.current_theme.text if self.current_theme is not None else "#000000"
        self.numeric_expression = tk.Text(
            display,
            height=2,
            wrap="none",
            undo=True,
            maxundo=100,
            font=("Microsoft YaHei UI", 28),
            background=numeric_text_bg,
            foreground=numeric_text_fg,
            insertbackground=self.current_theme.accent if self.current_theme is not None else "#000000",
            relief="solid",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=self.current_theme.border if self.current_theme is not None else "#d9e2ec",
        )
        self.numeric_expression.grid(row=0, column=0, sticky="nsew")
        self.numeric_expression.tag_configure("placeholder", foreground="#9ca3af")
        self.numeric_expression.bind("<KeyPress>", self._prepare_text_keypress)
        self.numeric_expression.bind("<KeyRelease>", lambda _event: self._schedule_numeric_auto_calculate())
        self.numeric_expression.bind("<Return>", lambda _event: "break")
        self.numeric_expression.bind("<BackSpace>", self._smart_backspace_event)
        self.numeric_expression.bind("<Control-a>", self._select_text_content)
        self.numeric_expression.bind("<Control-A>", self._select_text_content)
        self.numeric_expression.bind("<Control-z>", self._undo_numeric_expression)

        self.numeric_result_text = tk.Text(
            display,
            height=4,
            wrap="word",
            font=("Microsoft YaHei UI", 20),
            background=numeric_text_bg,
            foreground=numeric_text_fg,
            relief="solid",
            borderwidth=1,
            highlightthickness=0,
        )
        self.numeric_result_text.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        self.numeric_result_text.bind("<Key>", lambda _event: "break")
        self._write_numeric_result("")

        self.numeric_parameter_frame = ttk.Frame(display, height=42, style="Surface.TFrame")
        self.numeric_parameter_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.numeric_parameter_frame.grid_propagate(False)

        keypad_area = ttk.LabelFrame(frame, text="点按键盘", padding=10, style="Card.TLabelframe")
        keypad_area.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        keypad_area.columnconfigure(0, weight=1)
        keypad_area.rowconfigure(0, weight=1)
        self.numeric_keypad_frame = ttk.Frame(keypad_area, style="Surface.TFrame")
        self.numeric_keypad_frame.grid(row=0, column=0, sticky="nsew")

        self._refresh_numeric_controls()
        return frame

    def _refresh_numeric_controls(self) -> None:
        if self.numeric_parameter_frame is None or self.numeric_keypad_frame is None:
            return

        for child in self.numeric_parameter_frame.winfo_children():
            child.destroy()
        for child in self.numeric_keypad_frame.winfo_children():
            child.destroy()

        self._skinned_label(self.numeric_parameter_frame, "surface", "hint", text="变量").pack(side="left")
        ttk.Entry(self.numeric_parameter_frame, width=8, textvariable=self.numeric_variable).pack(
            side="left", padx=(6, 14)
        )

        mode = self.numeric_mode.get()
        if mode == "数值求根":
            self._skinned_label(self.numeric_parameter_frame, "surface", "hint", text="下限").pack(side="left")
            ttk.Entry(self.numeric_parameter_frame, width=8, textvariable=self.numeric_lower).pack(
                side="left", padx=(6, 14)
            )
            self._skinned_label(self.numeric_parameter_frame, "surface", "hint", text="上限").pack(side="left")
            ttk.Entry(self.numeric_parameter_frame, width=8, textvariable=self.numeric_upper).pack(
                side="left", padx=(6, 14)
            )
            self._skinned_label(self.numeric_parameter_frame, "surface", "hint", text="需要").pack(side="left")
            ttk.Entry(self.numeric_parameter_frame, width=6, textvariable=self.numeric_root_count).pack(
                side="left", padx=(6, 4)
            )
            self._skinned_label(self.numeric_parameter_frame, "surface", "hint", text="个解").pack(side="left", padx=(0, 14))
            self._skinned_label(
                self.numeric_parameter_frame, "surface", "hint",
                textvariable=self.numeric_hint,
            ).pack(side="left", fill="x", expand=True)
        elif mode == "数值积分":
            self._skinned_label(self.numeric_parameter_frame, "surface", "hint", text="下限").pack(side="left")
            ttk.Entry(self.numeric_parameter_frame, width=8, textvariable=self.numeric_lower).pack(
                side="left", padx=(6, 14)
            )
            self._skinned_label(self.numeric_parameter_frame, "surface", "hint", text="上限").pack(side="left")
            ttk.Entry(self.numeric_parameter_frame, width=8, textvariable=self.numeric_upper).pack(
                side="left", padx=(6, 14)
            )
        if mode == "数值求导":
            self._skinned_label(self.numeric_parameter_frame, "surface", "hint", text="求导点").pack(side="left")
            ttk.Entry(self.numeric_parameter_frame, width=8, textvariable=self.numeric_point).pack(
                side="left", padx=(6, 14)
            )

        is_running = self._calculation_process is not None
        self.numeric_cancel_button = ttk.Button(
            self.numeric_parameter_frame,
            text="取消计算",
            command=self._cancel_running_calculation,
            style="DataAction.TButton",
            state="normal" if is_running else "disabled",
        )
        self.numeric_cancel_button.pack(side="right")
        self.numeric_start_button = ttk.Button(
            self.numeric_parameter_frame,
            text="开始计算",
            command=self._start_numeric_calculation,
            style="Primary.TButton",
            state="disabled" if is_running else "normal",
        )
        self.numeric_start_button.pack(side="right", padx=(0, 8))

        self._build_numeric_buttons(self.numeric_keypad_frame, self._numeric_button_rows())
        self._apply_button_cursor(self.numeric_keypad_frame)

    def _numeric_button_rows(self) -> tuple[tuple[tuple[str, str] | tuple[str, str, int], ...], ...]:
        return (
            (("(", "("), (")", ")"), ("π", "π"), ("e", "e"), ("AC", "__clear__"), ("⌫", "__backspace__"), ("%", "/100"), ("/", "/")),
            (("x²", "^2"), ("xʸ", "^"), ("√", "√("), ("ⁿ√", "__nth_root__"), ("7", "7"), ("8", "8"), ("9", "9"), ("*", "*")),
            (("1/x", "1/()"), ("x", "x"), ("| |", "Abs("), ("mod", "mod"), ("4", "4"), ("5", "5"), ("6", "6"), ("-", "-")),
            (("sin", "sin("), ("cos", "cos("), ("tan", "tan("), ("ln", "ln("), ("1", "1"), ("2", "2"), ("3", "3"), ("+", "+")),
            (("log", "log("), ("lg", "lg("), ("10ˣ", "10^"), ("eˣ", "e^"), ("x", "x"), ("0", "0"), (".", "."), ("=", "__calculate__")),
        )

    def _build_numeric_buttons(
        self,
        parent: ttk.Frame,
        rows: tuple[tuple[tuple[str, str] | tuple[str, str, int], ...], ...],
    ) -> None:
        for column in range(8):
            parent.columnconfigure(column, weight=1, uniform="numeric_keypad")
        for row, buttons in enumerate(rows):
            parent.rowconfigure(row, weight=1, minsize=54, uniform="numeric_keypad_rows")
            column = 0
            for button_info in buttons:
                if len(button_info) == 3:
                    label, token, columnspan = button_info
                else:
                    label, token = button_info
                    columnspan = 1
                ttk.Button(
                    parent,
                    text=label,
                    style="Calculator.TButton",
                    command=lambda value=token: self._handle_numeric_key(value),
                ).grid(row=row, column=column, columnspan=columnspan, sticky="nsew", padx=5, pady=5)
                column += columnspan

    def _write_numeric_result(self, text: str) -> None:
        if self.numeric_result_text is None:
            return
        theme = self.current_theme
        bg = theme.surface if theme is not None else "#ffffff"
        fg = theme.text if theme is not None else "#000000"
        self.numeric_result_text.configure(state="normal", background=bg, foreground=fg)
        self.numeric_result_text.delete("1.0", "end")
        self.numeric_result_text.insert("1.0", text)
        self.numeric_result_text.configure(state="disabled", background=bg, foreground=fg)

    def _get_numeric_expression(self) -> str:
        if self.numeric_expression is None:
            return ""
        return self.numeric_expression.get("1.0", "end").strip()

    def _set_numeric_mode(self, mode: str) -> None:
        if self._calculation_task_type == "numeric":
            self._cancel_running_calculation(show_message=False)
        self.numeric_mode.set(mode)
        self.numeric_hint.set("")
        self._write_numeric_result("")
        self._refresh_numeric_controls()
        self._schedule_numeric_auto_calculate()
        self.status_var.set(f"当前计算方式：{mode}")

    def _handle_numeric_key(self, token: str) -> None:
        if token == "__calculate__":
            self._run_numeric_action(self.numeric_mode.get())
            return
        if self.numeric_expression is None:
            return
        if token == "__clear__":
            self.numeric_expression.delete("1.0", "end")
            self._write_numeric_result("")
            self.numeric_hint.set("")
            return
        if token == "__backspace__":
            self._smart_backspace(self.numeric_expression)
            self._schedule_numeric_auto_calculate()
            return
        self._insert_into_numeric_expression(token)
        self._schedule_numeric_auto_calculate()

    def _insert_into_numeric_expression(self, token: str) -> None:
        if self.numeric_expression is None:
            return
        self._delete_selection_if_placeholder(self.numeric_expression)
        if token == "__nth_root__":
            self._insert_nth_root_template(self.numeric_expression)
            return
        token = self._formula_token_for_insert(token)
        self.numeric_expression.edit_separator()
        self.numeric_expression.insert("insert", token)
        if token == "ⁿ√(,)":
            self.numeric_expression.mark_set("insert", "insert-2c")
        elif token == "1/()":
            self.numeric_expression.mark_set("insert", "insert-1c")
        self.numeric_expression.edit_separator()
        self.numeric_expression.see("insert")
        self.numeric_expression.focus_set()

    def _undo_numeric_expression(self, _event: tk.Event) -> str:
        if self.numeric_expression is None:
            return "break"
        try:
            self.numeric_expression.edit_undo()
        except tk.TclError:
            pass
        self.numeric_expression.see("insert")
        self._schedule_numeric_auto_calculate()
        return "break"

    def _schedule_numeric_auto_calculate(self) -> None:
        if self._numeric_auto_calc_job is not None:
            self.root.after_cancel(self._numeric_auto_calc_job)
        self._numeric_auto_calc_job = self.root.after(350, self._auto_calculate_numeric)

    def _auto_calculate_numeric(self) -> None:
        self._numeric_auto_calc_job = None
        if self._calculation_process is not None:
            return
        if not self._get_numeric_expression():
            self._write_numeric_result("")
            return
        result = self._calculate_numeric(self.numeric_mode.get(), silent=True)
        if result is not None:
            self._write_numeric_result(result)
        else:
            self._write_numeric_result("")

    def _calculate_numeric(self, action_name: str, silent: bool = False) -> str | None:
        expression = self._get_numeric_expression()
        variable = self.numeric_variable.get().strip() or "x"
        try:
            if action_name == "数值积分":
                return numeric_calc.numeric_integral(expression, self.numeric_lower.get(), self.numeric_upper.get(), variable)
            if action_name == "数值求导":
                return numeric_calc.numeric_derivative(expression, self.numeric_point.get(), variable)
            if action_name == "数值求根":
                self.numeric_hint.set("")
                return numeric_calc.numeric_root(
                    expression,
                    self.numeric_lower.get(),
                    self.numeric_upper.get(),
                    variable,
                    self.numeric_root_count.get(),
                )
            raise numeric_calc.NumericCalculationError(f"未知功能：{action_name}")
        except numeric_calc.NumericCalculationTimeout:
            self.numeric_hint.set("计算超时，请输入需要解的个数或设置上下界。")
            return None
        except Exception:
            if action_name == "数值求根" and not silent:
                self.numeric_hint.set("未找到满足条件的根，请减少范围或填写需要的解的个数。")
            return None

    def _run_numeric_action(self, action_name: str) -> None:
        self._start_numeric_calculation(action_name)

    def _start_numeric_calculation(self, action_name: str | None = None) -> None:
        action_name = action_name or self.numeric_mode.get()
        payload = {
            "expression": self._get_numeric_expression(),
            "variable": self.numeric_variable.get().strip() or "x",
            "lower": self.numeric_lower.get(),
            "upper": self.numeric_upper.get(),
            "point": self.numeric_point.get(),
            "root_count": self.numeric_root_count.get(),
        }
        self._start_background_calculation("numeric", action_name, payload)

    def _build_data_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = self._new_tab_frame(parent)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=5)
        frame.rowconfigure(1, weight=0)
        frame.rowconfigure(2, weight=4)

        preview = self._section(frame, "\u6570\u636e\u9884\u89c8\uff08\u4ec5\u9884\u89c8\u524d20\u884c\uff09", 0, 0)
        controls = self._section(frame, "\u6570\u636e\u6587\u4ef6\u4e0e\u64cd\u4f5c", 1, 0)
        self.data_controls_frame = controls
        stats = self._section(frame, "\u7edf\u8ba1\u7ed3\u679c", 2, 0)
        for column in range(6):
            controls.columnconfigure(column, weight=1 if column in {1, 2} else 0)

        self.data_import_button = ttk.Button(
            controls,
            text="\u5bfc\u5165 CSV/Excel",
            command=self._import_data_file,
            style="Primary.TButton",
            width=18,
        )
        self.data_import_button.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 12), pady=2)
        self.data_file_label = self._skinned_label(
            controls, "surface", "hint", textvariable=self.data_file_var, wraplength=900,
        )
        self.data_file_label.grid(row=0, column=1, columnspan=5, sticky="ew", pady=(0, 8))
        self.data_column_caption = self._skinned_label(controls, "surface", "hint", text="\u9009\u62e9\u7edf\u8ba1\u5217")
        self.data_column_caption.grid(row=1, column=1, sticky="e", padx=(0, 6), pady=2)
        self.data_column_selector = ttk.Combobox(
            controls,
            textvariable=self.data_column_var,
            values=("\u7b49\u5f85\u5bfc\u5165\u6570\u636e",),
            state="readonly",
            width=18,
        )
        self.data_column_selector.grid(row=1, column=2, sticky="ew", padx=(0, 10), pady=2)
        self.data_current_stats_button = ttk.Button(controls, text="\u7edf\u8ba1\u5f53\u524d\u5217", command=self._analyze_selected_column, style="DataAction.TButton", width=14)
        self.data_current_stats_button.grid(row=1, column=3, sticky="ew", padx=(0, 8), pady=2)
        self.data_all_stats_button = ttk.Button(controls, text="\u7edf\u8ba1\u5168\u90e8\u6570\u503c\u5217", command=self._analyze_all_columns, style="DataAction.TButton", width=16)
        self.data_all_stats_button.grid(row=1, column=4, sticky="ew", padx=(0, 8), pady=2)
        self.data_export_stats_button = ttk.Button(controls, text="\u5bfc\u51fa\u7edf\u8ba1\u7ed3\u679c", command=self._export_data_stats, style="DataAction.TButton", width=14)
        self.data_export_stats_button.grid(row=1, column=5, sticky="ew", pady=2)

        self.data_preview_table = ttk.Treeview(preview, show="headings", height=10)
        self._clear_tree_selection_on_blank(self.data_preview_table)
        preview_scroll_y = ttk.Scrollbar(preview, orient="vertical", command=self.data_preview_table.yview)
        preview_scroll_x = ttk.Scrollbar(preview, orient="horizontal", command=self.data_preview_table.xview)
        self.data_preview_table.configure(yscrollcommand=preview_scroll_y.set, xscrollcommand=preview_scroll_x.set)
        self.data_preview_table.grid(row=0, column=0, sticky="nsew")
        preview_scroll_y.grid(row=0, column=1, sticky="ns")
        preview_scroll_x.grid(row=1, column=0, sticky="ew")

        self.data_stats_table = ttk.Treeview(stats, show="headings", height=8)
        self._clear_tree_selection_on_blank(self.data_stats_table)
        stats_scroll_y = ttk.Scrollbar(stats, orient="vertical", command=self.data_stats_table.yview)
        stats_scroll_x = ttk.Scrollbar(stats, orient="horizontal", command=self.data_stats_table.xview)
        self.data_stats_table.configure(yscrollcommand=stats_scroll_y.set, xscrollcommand=stats_scroll_x.set)
        self.data_stats_table.grid(row=0, column=0, sticky="nsew")
        stats_scroll_y.grid(row=0, column=1, sticky="ns")
        stats_scroll_x.grid(row=1, column=0, sticky="ew")
        return frame

    def _update_data_controls_layout(self, compact: bool) -> None:
        """Keep import and core analysis actions visible at narrow widths."""
        controls = self.data_controls_frame
        required = (
            self.data_import_button, self.data_file_label, self.data_column_caption,
            self.data_column_selector, self.data_current_stats_button,
            self.data_all_stats_button, self.data_export_stats_button,
        )
        if controls is None or any(item is None for item in required):
            return
        if compact == self._data_controls_compact:
            return
        self._data_controls_compact = compact
        for column in range(6):
            controls.columnconfigure(column, weight=1 if compact or column in {1, 2} else 0, minsize=0)
        if compact:
            self.data_import_button.configure(width=0)
            self.data_column_selector.configure(width=9)
            self.data_current_stats_button.configure(width=0)
            self.data_all_stats_button.configure(width=0)
            self.data_export_stats_button.configure(width=0)
            self.data_import_button.grid_configure(row=0, column=0, rowspan=1, padx=(0, 6))
            self.data_file_label.grid_configure(row=0, column=1, columnspan=5, pady=(0, 6))
            self.data_column_caption.grid_configure(row=1, column=0, sticky="w", padx=(0, 4))
            self.data_column_selector.grid_configure(row=1, column=1, padx=(0, 4))
            self.data_current_stats_button.grid_configure(row=1, column=2, padx=(0, 4))
            self.data_all_stats_button.grid_configure(row=1, column=3, columnspan=2, padx=(0, 4))
            self.data_export_stats_button.grid_configure(row=1, column=5)
        else:
            self.data_import_button.configure(width=18)
            self.data_column_selector.configure(width=18)
            self.data_current_stats_button.configure(width=14)
            self.data_all_stats_button.configure(width=16)
            self.data_export_stats_button.configure(width=14)
            self.data_import_button.grid_configure(row=0, column=0, rowspan=2, padx=(0, 12))
            self.data_file_label.grid_configure(row=0, column=1, columnspan=5, pady=(0, 8))
            self.data_column_caption.grid_configure(row=1, column=1, sticky="e", padx=(0, 6))
            self.data_column_selector.grid_configure(row=1, column=2, columnspan=1, padx=(0, 10))
            self.data_current_stats_button.grid_configure(row=1, column=3, columnspan=1, padx=(0, 8))
            self.data_all_stats_button.grid_configure(row=1, column=4, columnspan=1, padx=(0, 8))
            self.data_export_stats_button.grid_configure(row=1, column=5, columnspan=1)

    def _import_data_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="选择数据文件",
            filetypes=(("表格文件", "*.csv *.xlsx"), ("CSV 文件", "*.csv"), ("Excel 文件", "*.xlsx")),
        )
        if not file_path:
            return

        request_id = self._data_import_request_id + 1
        self._data_import_request_id = request_id
        self.data_file_var.set("正在导入数据…")
        self.status_var.set("正在后台导入数据…")
        worker = threading.Thread(
            target=self._load_data_in_background,
            args=(request_id, file_path),
            daemon=True,
        )
        self._data_import_thread = worker
        worker.start()
        if self._data_import_poll_job is None:
            self._data_import_poll_job = self.root.after(30, self._poll_data_import_results)

    def _load_data_in_background(self, request_id: int, file_path: str) -> None:
        """Read Excel/CSV and inspect numeric columns without blocking Tk."""
        try:
            data_frame = data_analysis.load_table(file_path)
            columns = data_analysis.numeric_columns(data_frame)
            self._data_import_result_queue.put((request_id, file_path, data_frame, columns, None))
        except Exception as exc:
            self._data_import_result_queue.put((request_id, file_path, None, [], exc))

    def _poll_data_import_results(self) -> None:
        """Apply completed imports from Tk's event thread only."""
        self._data_import_poll_job = None
        try:
            while True:
                request_id, file_path, data_frame, columns, error = self._data_import_result_queue.get_nowait()
                if request_id != self._data_import_request_id:
                    continue
                if error is not None or data_frame is None:
                    self.data_file_var.set("尚未导入数据")
                    messagebox.showerror("导入失败", str(error or "无法读取数据文件"))
                    self.status_var.set("导入数据失败")
                    continue
                self._apply_imported_data(file_path, data_frame, columns)
        except queue.Empty:
            pass
        if (
            (self._data_import_thread is not None and self._data_import_thread.is_alive())
            or not self._data_import_result_queue.empty()
        ):
            self._data_import_poll_job = self.root.after(30, self._poll_data_import_results)

    def _apply_imported_data(self, file_path: str, data_frame, columns: list[str]) -> None:
        """Update controls after a background import has completed."""
        self.data_frame = data_frame
        self.data_stats = None
        self.data_file_var.set(file_path)
        self.data_column_var.set("全部数值列" if columns else "没有数值列")
        if self.data_column_selector is not None:
            self.data_column_selector.configure(values=("全部数值列", *columns) if columns else ("没有数值列",))
        if self.plot_view is not None:
            self.plot_view.set_data(self.data_frame, columns)

        self._fill_table(self.data_preview_table, self.data_frame.head(20))
        self._clear_table(self.data_stats_table)
        self.status_var.set(f"已导入 {len(self.data_frame)} 行?{len(self.data_frame.columns)} 列数据")

    def _analyze_selected_column(self) -> None:
        if self.data_frame is None:
            messagebox.showwarning("没有数据", "请先导入 CSV 或 Excel 文件")
            return

        selected = self.data_column_var.get()
        columns = None if selected in {"", "全部数值列", "没有数值列"} else [selected]
        self._run_data_analysis(columns)

    def _analyze_all_columns(self) -> None:
        if self.data_frame is None:
            messagebox.showwarning("没有数据", "请先导入 CSV 或 Excel 文件")
            return
        self._run_data_analysis(None)

    def _run_data_analysis(self, columns: list[str] | None) -> None:
        try:
            self.data_stats = data_analysis.describe_numeric_columns(self.data_frame, columns)
        except Exception as exc:
            messagebox.showerror("统计失败", str(exc))
            return

        self._fill_table(self.data_stats_table, self.data_stats)
        self.status_var.set("数据统计完成")

    def _export_data_stats(self) -> None:
        if self.data_stats is None:
            messagebox.showwarning("没有结果", "请先完成统计分析")
            return

        file_path = filedialog.asksaveasfilename(
            title="保存统计结果",
            defaultextension=".xlsx",
            filetypes=(("Excel 文件", "*.xlsx"), ("CSV 文件", "*.csv")),
        )
        if not file_path:
            return

        try:
            data_analysis.export_table(self.data_stats, file_path)
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))
            return
        self.status_var.set(f"统计结果已导出：{file_path}")

    def _fill_table(self, table: ttk.Treeview | None, data) -> None:
        if table is None:
            return

        table.delete(*table.get_children())
        columns = [str(column) for column in data.columns]
        table.configure(columns=columns)

        theme = self.current_theme
        row_even = theme.surface if theme else "#ffffff"
        row_odd = theme.surface_alt if theme else "#f5f5f5"

        table.tag_configure("even_row", background=row_even)
        table.tag_configure("odd_row", background=row_odd)

        for column in columns:
            table.heading(column, text=column)
            if table is self.data_stats_table:
                # Statistics include long decimals; keep their columns wide and
                # use the horizontal scrollbar instead of squeezing values.
                width = max(220, min(300, len(column) * 20 + 80))
                minwidth = 180
            else:
                width = max(150, min(240, len(column) * 16 + 48))
                minwidth = 130
            table.column(column, width=width, minwidth=minwidth, anchor="center", stretch=True)

        for index, row in enumerate(data.where(data.notna(), "").itertuples(index=False, name=None)):
            tag = "even_row" if index % 2 == 0 else "odd_row"
            table.insert("", "end", values=tuple(str(value) for value in row), tags=(tag,))

    def _clear_table(self, table: ttk.Treeview | None) -> None:
        if table is None:
            return
        table.delete(*table.get_children())
        table.configure(columns=())

    def _build_plot_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        self.plot_view = DataPlotView(self.root, self.status_var, self.current_theme)
        return self.plot_view.build(parent, self.current_theme)

    def _new_tab_frame(self, parent: ttk.Notebook) -> ttk.Frame:
        return common_widgets.new_tab_frame(parent)

    def _section(self, parent: ttk.Frame, title: str, row: int, column: int) -> ttk.LabelFrame:
        return common_widgets.section(parent, title, row, column)

    def _write_result(self, text: str) -> None:
        if self.result_text is None:
            return
        theme = self.current_theme
        bg = theme.surface if theme is not None else "#ffffff"
        fg = theme.text if theme is not None else "#000000"
        self.result_text.configure(state="normal", background=bg, foreground=fg)
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", text)
        self.result_text.configure(state="disabled", background=bg, foreground=fg)

    def _get_symbolic_expression(self) -> str:
        if self.symbolic_expression is None:
            return ""
        return self.symbolic_expression.get("1.0", "end").strip()

    def _set_symbolic_mode(self, mode: str) -> None:
        if self._calculation_task_type == "symbolic":
            self._cancel_running_calculation(show_message=False)
        self.symbolic_mode.set(mode)
        self._write_result("")
        self._refresh_symbolic_controls()
        self._schedule_auto_calculate()
        self.status_var.set(f"当前计算方式：{mode}")

    def _handle_symbolic_key(self, token: str) -> None:
        if token == "__calculate__":
            self._run_symbolic_action(self.symbolic_mode.get())
            return
        if self.symbolic_expression is None:
            return
        if token == "__clear__":
            self.symbolic_expression.delete("1.0", "end")
            self._write_result("")
            return
        if token == "__backspace__":
            self._smart_backspace(self.symbolic_expression)
            self._schedule_auto_calculate()
            return
        self._insert_into_expression(token)
        self._schedule_auto_calculate()

    def _schedule_auto_calculate(self) -> None:
        if self._auto_calc_job is not None:
            self.root.after_cancel(self._auto_calc_job)
        self._auto_calc_job = self.root.after(350, self._auto_calculate)

    def _auto_calculate(self) -> None:
        self._auto_calc_job = None
        if self._calculation_process is not None:
            return
        if not self._get_symbolic_expression():
            self._write_result("")
            return
        if self.symbolic_mode.get() == "方程求解":
            return
        result = self._calculate_symbolic(self.symbolic_mode.get(), silent=True)
        self._write_result(result or "")

    def _calculate_symbolic(self, action_name: str, silent: bool = False) -> str | None:
        expression = self._get_symbolic_expression()
        variable = self.symbolic_variable.get().strip() or "x"
        try:
            mode_index = self.MODES.index(action_name)
            if mode_index == 0:
                return symbolic_calc.evaluate_expression(expression)
            if mode_index == 1:
                return symbolic_calc.derivative(expression, variable)
            if mode_index == 2:
                return symbolic_calc.indefinite_integral(expression, variable)
            if mode_index == 3:
                return symbolic_calc.definite_integral(
                    expression,
                    variable,
                    self.symbolic_lower.get(),
                    self.symbolic_upper.get(),
                )
            if mode_index == 4:
                return symbolic_calc.solve_equation(expression, variable)
            if mode_index == 5:
                return symbolic_calc.fourier_transform(
                    expression,
                    variable,
                    self.symbolic_frequency.get().strip() or "k",
                )
            raise symbolic_calc.SymbolicCalculationError(f"未知功能：{action_name}")
        except Exception:
            return None

    def _run_symbolic_action(self, action_name: str) -> None:
        self._start_symbolic_calculation(action_name)

    def _start_symbolic_calculation(self, action_name: str | None = None) -> None:
        action_name = action_name or self.symbolic_mode.get()
        payload = {
            "expression": self._get_symbolic_expression(),
            "variable": self.symbolic_variable.get().strip() or "x",
            "lower": self.symbolic_lower.get(),
            "upper": self.symbolic_upper.get(),
            "frequency": self.symbolic_frequency.get().strip() or "k",
        }
        self._start_background_calculation("symbolic", action_name, payload)

    def _start_background_calculation(
        self,
        task_type: str,
        action_name: str,
        payload: dict[str, str],
    ) -> None:
        """Start one cancellable calculation and disable duplicate submissions."""
        if self._calculation_process is not None:
            return
        if not payload.get("expression", "").strip():
            self._write_calculation_result(task_type, "错误")
            return

        context = multiprocessing.get_context()
        result_queue = context.Queue(maxsize=1)
        process = context.Process(
            target=_calculation_process,
            args=(task_type, action_name, payload, result_queue),
            daemon=True,
        )
        try:
            process.start()
        except Exception:
            result_queue.close()
            self._write_calculation_result(task_type, "错误")
            return

        self._calculation_process = process
        self._calculation_result_queue = result_queue
        self._calculation_task_type = task_type
        self._calculation_action_name = action_name
        self._write_calculation_result(task_type, "正在计算")
        self.status_var.set(f"正在{action_name}")
        self._refresh_symbolic_controls()
        self._refresh_numeric_controls()
        self._calculation_poll_job = self.root.after(80, self._poll_background_calculation)

    def _poll_background_calculation(self) -> None:
        self._calculation_poll_job = None
        process = self._calculation_process
        result_queue = self._calculation_result_queue
        if process is None or result_queue is None:
            return
        if process.is_alive():
            self._calculation_poll_job = self.root.after(80, self._poll_background_calculation)
            return

        try:
            success, result = result_queue.get(timeout=0.2)
        except queue.Empty:
            success, result = False, "错误"
        self._finish_background_calculation(result if success else "错误")

    def _cancel_running_calculation(self, show_message: bool = True) -> None:
        process = self._calculation_process
        if process is None:
            return
        if self._calculation_poll_job is not None:
            self.root.after_cancel(self._calculation_poll_job)
            self._calculation_poll_job = None
        if process.is_alive():
            process.terminate()
            process.join(timeout=0.2)
        self._finish_background_calculation("已取消计算" if show_message else None)

    def _finish_background_calculation(self, result: str | None) -> None:
        process = self._calculation_process
        result_queue = self._calculation_result_queue
        task_type = self._calculation_task_type
        action_name = self._calculation_action_name
        self._calculation_process = None
        self._calculation_result_queue = None
        self._calculation_task_type = None
        self._calculation_action_name = None
        if process is not None:
            process.join(timeout=0.1)
        if result_queue is not None:
            result_queue.close()
        self._refresh_symbolic_controls()
        self._refresh_numeric_controls()
        if result is not None and task_type is not None:
            self._write_calculation_result(task_type, result)
            self.status_var.set(result if result == "已取消计算" else f"{action_name}完成")

    def _write_calculation_result(self, task_type: str, result: str) -> None:
        if task_type == "numeric":
            self._write_numeric_result(result)
        else:
            self._write_result(result)

    def _apply_theme(self) -> None:
        theme = theme_switcher.apply_theme(self.root, self.theme_var.get())
        self.current_theme = theme
        self._apply_text_widget_theme(theme)
        self._apply_custom_widget_theme(theme)
        self._update_skinned_labels(theme)
        if self.plot_view is not None:
            self.plot_view.update_theme(theme)
        self._apply_responsive_scale(force=True)
        self._redraw_dashboard_chart_preview()
        settings.save_theme_name(theme.display_name)
        self.status_var.set(f"已应用皮肤：{theme.display_name}")

    def _apply_custom_widget_theme(self, theme: AppTheme) -> None:
        for card in self.dashboard_card_widgets:
            card.configure(
                background=theme.surface,
                highlightbackground=theme.border,
                highlightcolor=theme.border,
            )
        for symbol_label, text_label in self.dashboard_card_labels:
            symbol_label.configure(background=theme.surface, foreground=theme.heading)
            text_label.configure(background=theme.surface, foreground=theme.heading)

    def _start_theme_animation(self, _event: tk.Event | None = None) -> None:
        target = self.theme_var.get()
        if self.current_theme is not None and target == self.current_theme.display_name:
            return
        self._theme_animation_target = target
        self._cancel_theme_animation()

        theme = themes.get_theme(target)
        window = tk.Toplevel(self.root)
        window.overrideredirect(True)
        window.transient(self.root)
        try:
            window.attributes("-topmost", True)
            window.attributes("-alpha", 0.95)
        except tk.TclError:
            pass

        width, height = 360, 92
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_w = max(self.root.winfo_width(), width)
        root_h = max(self.root.winfo_height(), height)
        x = root_x + (root_w - width) // 2
        y = root_y + 96
        window.geometry(f"{width}x{height}+{x}+{y}")

        canvas = tk.Canvas(
            window,
            width=width,
            height=height,
            highlightthickness=0,
            background=theme.surface,
        )
        canvas.pack(fill="both", expand=True)
        self._theme_animation_window = window
        self._theme_animation_canvas = canvas
        self.status_var.set(f"正在切换皮肤：{target}")
        self._animate_theme_switch(0)

    def _cancel_theme_animation(self) -> None:
        if self._theme_animation_job is not None:
            self.root.after_cancel(self._theme_animation_job)
            self._theme_animation_job = None
        if self._theme_animation_window is not None:
            try:
                self._theme_animation_window.destroy()
            except tk.TclError:
                pass
        self._theme_animation_window = None
        self._theme_animation_canvas = None

    def _animate_theme_switch(self, frame: int) -> None:
        canvas = self._theme_animation_canvas
        window = self._theme_animation_window
        if canvas is None or window is None:
            return

        target_theme = themes.get_theme(self._theme_animation_target)
        progress = min(1.0, frame / 14)
        width = int(canvas["width"])
        height = int(canvas["height"])
        canvas.delete("all")
        canvas.create_rectangle(0, 0, width, height, fill=target_theme.surface, outline=target_theme.border)
        canvas.create_text(
            width // 2,
            30,
            text=f"切换到 {target_theme.display_name}",
            fill=target_theme.heading,
            font=("Microsoft YaHei UI", 12, "bold"),
        )
        bar_left, bar_top, bar_right, bar_bottom = 34, 58, width - 34, 68
        canvas.create_rectangle(bar_left, bar_top, bar_right, bar_bottom, fill=target_theme.surface_alt, outline=target_theme.border)
        canvas.create_rectangle(
            bar_left,
            bar_top,
            bar_left + int((bar_right - bar_left) * progress),
            bar_bottom,
            fill=target_theme.primary,
            outline=target_theme.primary,
        )

        if frame == 7:
            self.theme_var.set(self._theme_animation_target)
            self._apply_theme()

        if frame >= 14:
            self._cancel_theme_animation()
            return

        self._theme_animation_job = self.root.after(35, lambda: self._animate_theme_switch(frame + 1))

    def _schedule_responsive_update(self, event: tk.Event) -> None:
        if event.widget is not self.root:
            return
        if self._responsive_job is not None:
            self.root.after_cancel(self._responsive_job)
        self._responsive_job = self.root.after(80, self._apply_responsive_scale)

    def _current_responsive_scale(self) -> float:
        width = max(self.root.winfo_width(), 1)
        height = max(self.root.winfo_height(), 1)
        width_scale = width / DESIGN_WIDTH
        height_scale = height / DESIGN_HEIGHT
        area_scale = ((width * height) / (DESIGN_WIDTH * DESIGN_HEIGHT)) ** 0.5
        # Keep a readable lower bound, but use one shared scale for all visual
        # elements rather than letting fonts and frames diverge.
        return max(0.42, min(1.0, width_scale, height_scale, area_scale * 0.92))

    def _current_font_scale(self, layout_scale: float) -> float:
        return layout_scale

    def _scaled_font(self, size: int, scale: float, *, weight: str = "normal", minimum: int = 6) -> tuple[str, int, str]:
        return ("Microsoft YaHei UI", max(minimum, int(size * scale)), weight)

    def _apply_named_fonts(self, scale: float) -> None:
        default_size = max(8, int(12 * scale))
        font_specs = {
            "TkDefaultFont": ("Microsoft YaHei UI", default_size),
            "TkTextFont": ("Microsoft YaHei UI", default_size),
            "TkMenuFont": ("Microsoft YaHei UI", default_size),
            "TkCaptionFont": ("Microsoft YaHei UI", max(11, int(13 * scale)), "bold"),
            "TkHeadingFont": ("Microsoft YaHei UI", max(11, int(13 * scale)), "bold"),
        }
        for font_name, spec in font_specs.items():
            try:
                tkfont.nametofont(font_name).configure(family=spec[0], size=spec[1], weight=spec[2] if len(spec) > 2 else "normal")
            except tk.TclError:
                continue

    def _apply_responsive_scale(self, force: bool = False) -> None:
        self._responsive_job = None
        theme = self.current_theme
        if theme is None:
            return

        scale = self._current_responsive_scale()
        font_scale = self._current_font_scale(scale)
        compact_dashboard = self.root.winfo_width() < 1280
        layout_changed = compact_dashboard != self._dashboard_compact_mode
        if not force and not layout_changed and abs(scale - self._last_ui_scale) < 0.015 and abs(font_scale - self._last_font_scale) < 0.015:
            return
        self._last_ui_scale = scale
        self._last_font_scale = font_scale
        self._update_dashboard_layout(compact_dashboard)

        self._apply_named_fonts(font_scale)

        style = ttk.Style()
        label_font = self._scaled_font(12, font_scale, minimum=8)
        label_bold_font = self._scaled_font(12, font_scale, weight="bold", minimum=8)
        style.configure("TLabel", font=label_font)
        style.configure("Surface.TLabel", font=label_font)
        style.configure("Header.TLabel", font=self._scaled_font(26, font_scale, weight="bold", minimum=12))
        style.configure("DashboardTitle.TLabel", font=self._scaled_font(17, font_scale, weight="bold", minimum=12))
        style.configure("DashboardMetricTitle.TLabel", font=self._scaled_font(12, font_scale, minimum=10))
        style.configure("DashboardMetricValue.TLabel", font=self._scaled_font(26, font_scale, weight="bold", minimum=12))
        style.configure("Hint.TLabel", font=self._scaled_font(12, font_scale, minimum=10))
        style.configure(
            "TButton",
            padding=(max(4, int(12 * scale)), max(3, int(8 * scale))),
            font=label_font,
        )
        style.configure(
            "Primary.TButton",
            padding=(max(5, int(16 * scale)), max(4, int(9 * scale))),
            font=label_bold_font,
        )
        style.configure(
            "DashboardNav.TButton",
            padding=(max(5, int(14 * scale)), max(3, int(9 * scale))),
            font=label_bold_font,
        )
        style.configure(
            "DashboardCard.TButton",
            padding=(max(6, int(18 * scale)), max(5, int(18 * scale))),
            font=self._scaled_font(17, font_scale, weight="bold", minimum=12),
        )
        style.configure(
            "DataAction.TButton",
            padding=(max(5, int(14 * scale)), max(3, int(8 * scale))),
            font=label_bold_font,
        )
        style.configure(
            "Calculator.TButton",
            padding=(max(2, int(6 * scale)), max(2, int(6 * scale))),
            font=("Microsoft YaHei UI", self._calculator_button_font_size(font_scale)),
        )
        style.configure(
            "TNotebook.Tab",
            padding=(max(10, int(22 * scale)), max(7, int(12 * scale))),
            font=self._scaled_font(14, font_scale, weight="bold", minimum=9),
        )
        style.configure(
            "TMenubutton",
            padding=(max(5, int(12 * scale)), max(3, int(8 * scale))),
            font=label_bold_font,
        )
        for menu in (self.symbolic_mode_menu, self.numeric_mode_menu):
            if menu is not None:
                menu.configure(font=label_bold_font)
        style.configure(
            "TEntry",
            padding=(max(3, int(6 * scale)), max(2, int(5 * scale))),
            font=label_font,
        )
        style.configure(
            "TCombobox",
            padding=(max(3, int(8 * scale)), max(2, int(6 * scale))),
            font=label_font,
        )
        style.configure(
            "TLabelframe.Label",
            font=self._scaled_font(13, font_scale, weight="bold", minimum=9),
        )
        style.configure(
            "Card.TLabelframe.Label",
            font=self._scaled_font(13, font_scale, weight="bold", minimum=9),
        )
        style.configure(
            "Treeview",
            font=label_font,
            rowheight=max(26, int(44 * scale)),
        )
        style.configure(
            "Treeview.Heading",
            font=label_bold_font,
        )

        expression_size = max(10, int(22 * font_scale))
        result_size = max(9, int(18 * font_scale))
        expression_font = ("Microsoft YaHei UI", expression_size)
        result_font = ("Microsoft YaHei UI", result_size)
        input_min_height = max(32, int(72 * scale))
        result_min_height = max(38, int(116 * scale))
        parameter_height = max(22, int(42 * scale))

        for display_frame in (self.symbolic_display_frame, self.numeric_display_frame):
            if display_frame is not None:
                display_frame.configure(padding=max(6, int(14 * scale)))
                display_frame.rowconfigure(0, minsize=input_min_height)
                display_frame.rowconfigure(1, minsize=result_min_height)

        for parameter_frame in (self.symbolic_parameter_frame, self.numeric_parameter_frame):
            if parameter_frame is not None:
                parameter_frame.configure(height=parameter_height)

        self._scale_keypad_layout(scale)

        for widget in (self.symbolic_expression, self.numeric_expression):
            if widget is not None:
                widget.configure(
                    font=expression_font,
                    height=2,
                    padx=max(5, int(10 * scale)),
                    pady=max(1, int(3 * scale)),
                )
                widget.see("insert")
        for widget in (self.result_text, self.numeric_result_text):
            if widget is not None:
                widget.configure(font=result_font, padx=max(5, int(10 * scale)), pady=max(4, int(8 * scale)))
        self._fit_text_widgets(expression_size, result_size)
        if self._text_fit_job is not None:
            self.root.after_cancel(self._text_fit_job)
        self._text_fit_job = self.root.after(120, lambda: self._run_delayed_text_fit(expression_size, result_size))

        if self.topbar_title_label is not None:
            self.topbar_title_label.configure(font=("Microsoft YaHei UI", max(12, int(18 * font_scale)), "bold"))
        self._scale_dashboard_cards(scale, font_scale)
        self._update_data_controls_layout(compact_dashboard)
        self._scale_wrapped_labels(scale)

        self._scale_tables(scale)

        # 必须在字体缩放后重新应用颜色，防止 style.configure 覆盖颜色属性
        if self.current_theme is not None:
            themes.apply_theme_colors_only(self.current_theme)

    def _calculator_button_font_size(self, font_scale: float) -> int:
        return max(9, int(21 * font_scale))

    def _scale_keypad_layout(self, scale: float) -> None:
        """Scale button cells and their labels together on every resize."""
        cell_min_height = max(28, int(64 * scale))
        padding = max(1, int(5 * scale))
        for keypad in (self.symbolic_keypad_frame, self.numeric_keypad_frame):
            if keypad is None:
                continue
            for row in range(5):
                keypad.rowconfigure(row, minsize=cell_min_height)
            for child in keypad.winfo_children():
                if isinstance(child, ttk.Button):
                    child.grid_configure(padx=padding, pady=padding)

    def _run_delayed_text_fit(self, expression_size: int, result_size: int) -> None:
        self._text_fit_job = None
        self._fit_text_widgets(expression_size, result_size)

    def _fit_text_widgets(self, expression_size: int, result_size: int) -> None:
        for widget in (self.symbolic_expression, self.numeric_expression):
            if widget is None:
                continue
            height = widget.winfo_height()
            if height <= 1:
                continue
            fitted_size = max(9, min(expression_size, int((height - 10) / 2.25)))
            widget.configure(font=("Microsoft YaHei UI", fitted_size), height=2, pady=1)
        for widget in (self.result_text, self.numeric_result_text):
            if widget is None:
                continue
            height = widget.winfo_height()
            if height <= 1:
                continue
            fitted_size = max(8, min(result_size, int((height - 10) / 2.35)))
            widget.configure(font=("Microsoft YaHei UI", fitted_size), pady=1)

    def _scale_dashboard_cards(self, scale: float, font_scale: float) -> None:
        if self.dashboard_function_card is None:
            return

        raw_function_width = self.dashboard_function_card.winfo_width()
        root_width = self.root.winfo_width()
        if raw_function_width <= 120:
            function_width = max(420, int(root_width * 0.32))
            columns = 3
        else:
            function_width = raw_function_width

        if function_width < 420:
            columns = 2
        else:
            columns = 3

        self.dashboard_function_card.configure(padding=max(3, int(10 * scale)))
        for column in range(3):
            self.dashboard_function_card.columnconfigure(
                column,
                weight=1 if column < columns else 0,
                minsize=0,
                uniform="dashboard_actions_columns" if column < columns else "",
            )

        rows = max(1, (len(self.dashboard_card_widgets) + columns - 1) // columns)
        minsize = max(30, int(112 * scale / max(1, columns - 1)))
        for row in range(9):
            self.dashboard_function_card.rowconfigure(
                row,
                weight=1 if row < rows else 0,
                minsize=minsize if row < rows else 0,
                uniform="dashboard_actions_rows" if row < rows else "",
            )

        cell_width = function_width / columns
        symbol_size = max(9, min(int(25 * font_scale), int(cell_width / 5.8)))
        label_size = max(8, min(int(21 * font_scale), int(cell_width / 6.1)))
        symbol_font = ("Microsoft YaHei UI", symbol_size, "bold")
        label_font = ("Microsoft YaHei UI", label_size, "bold")
        card_pad_x = max(2, int(5 * scale))
        card_pad_y = max(2, int(5 * scale))
        label_pad_x = max(2, int(6 * scale))
        top_pad = max(1, int(10 * scale))
        bottom_pad = max(1, int(10 * scale))

        for index, card in enumerate(self.dashboard_card_widgets):
            card.grid_configure(
                row=index // columns,
                column=index % columns,
                padx=card_pad_x,
                pady=card_pad_y,
                sticky="nsew",
            )
        for symbol_label, text_label in self.dashboard_card_labels:
            symbol_label.configure(font=symbol_font)
            text_label.configure(font=label_font, wraplength=max(34, int(cell_width - label_pad_x * 2)))
            symbol_label.grid_configure(padx=label_pad_x, pady=(top_pad, 0))
            text_label.grid_configure(padx=label_pad_x, pady=(1, bottom_pad))

    def _scale_wrapped_labels(self, scale: float) -> None:
        width = max(self.root.winfo_width(), 1)
        wrap = max(120, int(width * 0.34))
        for label in self.root.winfo_children():
            self._scale_wrapped_labels_in(label, wrap, scale)

    def _scale_wrapped_labels_in(self, widget: tk.Widget, wrap: int, scale: float) -> None:
        if isinstance(widget, ttk.Label):
            try:
                if not getattr(widget, "_keep_explicit_wrap", False):
                    widget.configure(wraplength=max(80, int(wrap * scale * 1.6)))
            except tk.TclError:
                pass
        for child in widget.winfo_children():
            self._scale_wrapped_labels_in(child, wrap, scale)

    def _scale_tables(self, scale: float) -> None:
        for table in (self.data_preview_table, self.data_stats_table):
            if table is None:
                continue
            for column in table["columns"]:
                if table is self.data_stats_table:
                    base_width = max(220, min(300, len(str(column)) * 20 + 80))
                    min_width = 180
                else:
                    base_width = max(150, min(240, len(str(column)) * 16 + 48))
                    min_width = 130
                table.column(
                    column,
                    width=max(min_width, int(base_width * scale)),
                    minwidth=min_width,
                )

    def _apply_text_widget_theme(self, theme: AppTheme) -> None:
        text_widgets = (
            self.symbolic_expression,
            self.result_text,
            self.numeric_expression,
            self.numeric_result_text,
        )
        for widget in text_widgets:
            if widget is None:
                continue
            widget.configure(
                background=theme.surface,
                foreground=theme.text,
                insertbackground=theme.accent,
                selectbackground=theme.surface_alt,
                selectforeground=theme.text,
                relief="solid",
                borderwidth=1,
                highlightthickness=1,
                highlightbackground=theme.border,
                highlightcolor=theme.accent,
                padx=10,
                pady=8,
            )

    def _skinned_label(
        self,
        parent: tk.Widget,
        bg_key: str = "surface",
        fg_key: str = "text",
        **kwargs,
    ) -> tk.Label:
        """Create a tk.Label with a background that perfectly matches its parent frame.

        bg_key: 'background', 'surface', or 'surface_alt'
        fg_key: 'text', 'heading', or 'hint'
        """
        theme = self.current_theme
        bg_defaults = {"background": "#f0f0f0", "surface": "#ffffff", "surface_alt": "#f5f5f5"}
        fg_defaults = {"text": "#000000", "heading": "#000000", "hint": "#888888"}
        if theme is not None:
            bg_map = {"background": theme.background, "surface": theme.surface, "surface_alt": theme.surface_alt}
            fg_map = {"text": theme.text, "heading": theme.heading, "hint": theme.hint}
        else:
            bg_map = bg_defaults
            fg_map = fg_defaults
        label = tk.Label(
            parent,
            highlightthickness=0,
            bd=0,
            bg=bg_map.get(bg_key, "#ffffff"),
            fg=fg_map.get(fg_key, "#000000"),
            **kwargs,
        )
        self._skinned_labels.append((label, bg_key, fg_key))
        return label

    def _update_skinned_labels(self, theme: AppTheme) -> None:
        """Update all tracked skinned labels to match a new theme."""
        bg_map = {"background": theme.background, "surface": theme.surface, "surface_alt": theme.surface_alt}
        fg_map = {"text": theme.text, "heading": theme.heading, "hint": theme.hint}
        for label, bg_key, fg_key in self._skinned_labels:
            try:
                label.configure(bg=bg_map.get(bg_key, "#ffffff"), fg=fg_map.get(fg_key, "#000000"))
            except tk.TclError:
                pass

    def _apply_button_cursor(self, widget: tk.Widget) -> None:
        for child in widget.winfo_children():
            if isinstance(child, (ttk.Button, ttk.Menubutton)):
                child.configure(cursor="hand2")
            self._apply_button_cursor(child)


    def _clear_tree_selection_on_blank(self, table: ttk.Treeview) -> None:
        def clear_if_blank(event: tk.Event) -> None:
            if table.identify_row(event.y):
                return
            table.selection_remove(table.selection())
            table.focus("")

        table.bind("<Button-1>", clear_if_blank, add="+")


def create_main_window(initial_theme_name: str | None = None) -> tk.Tk:
    """Create the main GUI window."""
    _enable_high_dpi_awareness()
    root = tk.Tk()
    ScientificCalculatorApp(root, initial_theme_name=initial_theme_name)
    return root


def main() -> None:
    """Run the GUI application."""
    _enable_high_dpi_awareness()
    initial_theme_name = settings.load_theme_name(themes.DEFAULT_THEME_NAME, themes.theme_names())
    root = tk.Tk()
    StartupSplash(root, themes.get_theme(initial_theme_name)).show()
    ScientificCalculatorApp(root, initial_theme_name=initial_theme_name)
    root.mainloop()
