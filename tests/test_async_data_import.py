from __future__ import annotations

import importlib
import queue
import sys
import threading
import time
from pathlib import Path

import pytest
import tkinter as tk

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
_frontend_name = chr(0x524D) + chr(0x7AEF)
ScientificCalculatorApp = importlib.import_module(f"{_frontend_name}.app").ScientificCalculatorApp


def test_background_csv_import_updates_application_state(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("x,y\n1,2\n3,4\n", encoding="utf-8")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available in this test environment")
    root.withdraw()
    try:
        app = object.__new__(ScientificCalculatorApp)
        app.root = root
        app._data_import_thread = None
        app._data_import_result_queue = queue.Queue()
        app._data_import_poll_job = None
        app._data_import_request_id = 1
        app.data_frame = None
        app.data_stats = None
        app.data_file_var = tk.StringVar(value="")
        app.data_column_var = tk.StringVar(value="")
        app.data_column_selector = None
        app.data_preview_table = None
        app.data_stats_table = None
        app.plot_view = None
        app.status_var = tk.StringVar(value="")

        worker = threading.Thread(target=app._load_data_in_background, args=(1, str(csv_path)), daemon=True)
        app._data_import_thread = worker
        worker.start()
        deadline = time.monotonic() + 5
        while worker.is_alive() and time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
        app._poll_data_import_results()

        assert app.data_frame is not None
        assert list(app.data_frame.columns) == ["x", "y"]
        assert len(app.data_frame) == 2
    finally:
        root.destroy()
