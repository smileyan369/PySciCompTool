"""Theme switching helpers."""

from __future__ import annotations

import tkinter as tk

from . import themes
from .theme_models import AppTheme


def apply_theme(root: tk.Tk, theme_name: str) -> AppTheme:
    """Apply a named theme to the application root and ttk styles."""
    theme = themes.apply_theme(themes.get_theme(theme_name))
    root.configure(background=theme.background)
    return theme

