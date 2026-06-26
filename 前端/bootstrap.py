"""Fast launcher that keeps a visible splash alive while heavy modules import."""

from __future__ import annotations

import ctypes
import importlib
import queue
import sys
import threading
import time
import tkinter as tk
from types import ModuleType

from . import settings, themes
from .startup_splash import StartupSplash

APP_USER_MODEL_ID = "StarCalc.Workshop.PySciCompTool"
_FRONTEND = chr(0x524D) + chr(0x7AEF)
_APP_MODULE = _FRONTEND + ".app"


def _enable_high_dpi_awareness() -> None:
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


def _close_native_splash() -> None:
    """Close PyInstaller's early splash after Tk has a visible replacement."""
    try:
        import pyi_splash  # type: ignore

        if pyi_splash.is_alive():
            pyi_splash.update_text("Loading application...")
            pyi_splash.close()
    except Exception:
        pass


def _import_application(result_queue: queue.Queue) -> None:
    try:
        result_queue.put((importlib.import_module(_APP_MODULE), None))
    except Exception as exc:
        result_queue.put((None, exc))


def main() -> None:
    """Display progress first, then import heavy numerical and chart modules."""
    _enable_high_dpi_awareness()
    initial_theme_name = settings.load_theme_name(themes.DEFAULT_THEME_NAME, themes.theme_names())
    root = tk.Tk()
    splash = StartupSplash(root, themes.get_theme(initial_theme_name))
    splash.open()
    root.update()
    _close_native_splash()

    results: queue.Queue[tuple[ModuleType | None, Exception | None]] = queue.Queue()
    worker = threading.Thread(target=_import_application, args=(results,), daemon=True, name="starcalc-runtime-loader")
    worker.start()
    started_at = time.monotonic()

    def poll_loader() -> None:
        elapsed = time.monotonic() - started_at
        try:
            app_module, error = results.get_nowait()
        except queue.Empty:
            # Move smoothly toward 84% while the actual import work continues.
            splash.update(min(0.84, 0.06 + elapsed * 0.16), "\u6b63\u5728\u52a0\u8f7d\u529f\u80fd\u6a21\u5757", "\u6b63\u5728\u51c6\u5907\u8ba1\u7b97\u3001\u6570\u636e\u4e0e\u56fe\u8868\u5f15\u64ce")
            root.after(25, poll_loader)
            return

        if error is not None or app_module is None:
            splash.update(1.0, "\u542f\u52a8\u5931\u8d25", "\u8bf7\u68c0\u67e5 Python \u73af\u5883\u4e0e\u4f9d\u8d56")
            root.after(300, root.destroy)
            return

        # The final 100% is intentionally delayed until the workbench itself
        # has been constructed, so the percentage means "ready to use".
        splash.update(0.88, "\u6a21\u5757\u52a0\u8f7d\u5b8c\u6210", "\u6b63\u5728\u521b\u5efa\u5de5\u4f5c\u53f0")
        root.update_idletasks()
        app_module.ScientificCalculatorApp(root, initial_theme_name=initial_theme_name)
        splash.update(1.0, "\u542f\u52a8\u5b8c\u6210", "\u5de5\u4f5c\u53f0\u5df2\u51c6\u5907\u5c31\u7eea")
        root.update_idletasks()
        root.after(120, lambda: splash.close(show_root=True))

    root.after(20, poll_loader)
    root.mainloop()
