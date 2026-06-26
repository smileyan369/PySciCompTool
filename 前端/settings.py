"""Small persistent settings for the frontend."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


APP_DIR_NAME = "PySciCompTool"
SETTINGS_FILE_NAME = "settings.json"
WINDOW_SIZE_PATTERN = re.compile(r"^\d+x\d+$")


def _settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_DIR_NAME / SETTINGS_FILE_NAME
    return Path.home() / f".{APP_DIR_NAME.lower()}_{SETTINGS_FILE_NAME}"


def _load_settings() -> dict[str, object]:
    path = _settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(data, dict):
        return data
    return {}


def _save_settings(data: dict[str, object]) -> None:
    path = _settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_theme_name(default: str, valid_names: tuple[str, ...]) -> str:
    """Load the last selected theme name."""
    data = _load_settings()
    theme_name = str(data.get("theme_name", "")).strip()
    if theme_name in valid_names:
        return theme_name
    return default


def save_theme_name(theme_name: str) -> None:
    """Save the selected theme name for the next launch."""
    data = _load_settings()
    data["theme_name"] = theme_name
    _save_settings(data)


def load_window_size(default: str) -> str:
    """Load the last window size, without restoring the last position."""
    size = str(_load_settings().get("window_size", "")).strip()
    if WINDOW_SIZE_PATTERN.match(size):
        return size
    return default


def save_window_size(size: str) -> None:
    """Save the current window size."""
    size = size.strip()
    if not WINDOW_SIZE_PATTERN.match(size):
        return
    data = _load_settings()
    data["window_size"] = size
    _save_settings(data)
