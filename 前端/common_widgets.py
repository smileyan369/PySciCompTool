"""Shared Tkinter layout helpers."""

from __future__ import annotations

from tkinter import ttk


def new_tab_frame(parent: ttk.Notebook) -> ttk.Frame:
    """Create a padded tab frame with a flexible first row."""
    frame = ttk.Frame(parent, padding=14, style="Surface.TFrame")
    frame.rowconfigure(0, weight=1)
    return frame


def section(parent: ttk.Frame, title: str, row: int, column: int) -> ttk.LabelFrame:
    """Create a labelled section using the project's default spacing."""
    area = ttk.LabelFrame(parent, text=title, padding=14, style="Card.TLabelframe")
    area.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
    area.columnconfigure(0, weight=1)
    area.rowconfigure(0, weight=1)
    return area
