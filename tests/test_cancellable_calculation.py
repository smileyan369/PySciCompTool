"""End-to-end checks for cancellable formula calculations."""

import time
import tkinter as tk

from 前端.app import ScientificCalculatorApp


def _wait_for_worker(root: tk.Tk, app: ScientificCalculatorApp, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while app._calculation_process is not None and time.monotonic() < deadline:
        root.update()
        time.sleep(0.04)
    root.update()
    assert app._calculation_process is None, "后台计算未在预期时间内结束"


def test_symbolic_and_numeric_manual_calculations_can_finish_or_cancel() -> None:
    root = tk.Tk()
    root.withdraw()
    app = ScientificCalculatorApp(root)
    try:
        app.symbolic_expression.insert("1.0", "x^2")
        app._set_symbolic_mode("求导")
        app._start_symbolic_calculation()
        assert app._calculation_process is not None
        assert app.symbolic_start_button is not None and app.symbolic_start_button.instate(["disabled"])
        assert app.symbolic_cancel_button is not None and app.symbolic_cancel_button.instate(["!disabled"])
        _wait_for_worker(root, app)
        assert app.result_text is not None and app.result_text.get("1.0", "end").strip() == "2*x"

        app.numeric_expression.insert("1.0", "sin(x)")
        app._set_numeric_mode("数值求导")
        app._start_numeric_calculation()
        assert app._calculation_process is not None
        _wait_for_worker(root, app)
        assert app.numeric_result_text is not None
        assert app.numeric_result_text.get("1.0", "end").strip() not in {"", "错误"}

        app.symbolic_expression.delete("1.0", "end")
        app.symbolic_expression.insert("1.0", "x^2=4")
        app._set_symbolic_mode("方程求解")
        app._start_symbolic_calculation()
        assert app._calculation_process is not None
        app._cancel_running_calculation()
        assert app._calculation_process is None
        assert app.result_text is not None and app.result_text.get("1.0", "end").strip() == "已取消计算"
        assert app.symbolic_start_button is not None and app.symbolic_start_button.instate(["!disabled"])
        assert app.symbolic_cancel_button is not None and app.symbolic_cancel_button.instate(["disabled"])
    finally:
        app._cancel_running_calculation(show_message=False)
        root.destroy()
