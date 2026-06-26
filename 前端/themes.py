"""Theme configuration for the Tkinter frontend."""

from __future__ import annotations

from tkinter import ttk

from .theme_models import AppTheme, DEFAULT_DASHBOARD, THEME_NAMES, THEMES


DEFAULT_THEME_NAME = DEFAULT_DASHBOARD.display_name


def theme_names() -> tuple[str, ...]:
    """Return all skin names shown in the UI."""
    return THEME_NAMES


def get_theme(name: str) -> AppTheme:
    """Return a theme by display name, falling back to the default skin."""
    return THEMES.get(name, DEFAULT_DASHBOARD)


def configure_default_style() -> AppTheme:
    """Apply the default dashboard theme to ttk widgets."""
    return apply_theme(DEFAULT_DASHBOARD)


def apply_theme(theme: AppTheme) -> AppTheme:
    """Apply a theme to ttk widgets and return it."""
    style = ttk.Style()
    if "clam" in style.theme_names():
        style.theme_use("clam")
    _configure_theme_colors(style, theme)
    _configure_theme_fonts(style)
    return theme


def apply_theme_colors_only(theme: AppTheme) -> None:
    """Re-apply only color-related properties without touching fonts/paddings."""
    style = ttk.Style()
    if "clam" in style.theme_names():
        style.theme_use("clam")
    _configure_theme_colors(style, theme)


def _configure_theme_colors(style: ttk.Style, theme: AppTheme) -> None:
    """Set all color-related ttk style properties (background, foreground, border, etc.)."""
    style.configure("TFrame", background=theme.background)
    style.configure("Surface.TFrame", background=theme.surface)
    style.configure("Topbar.TFrame", background=theme.background)
    style.configure("Status.TFrame", background=theme.surface)
    style.configure("TLabel", background=theme.background, foreground=theme.text)
    style.configure("Surface.TLabel", background=theme.surface, foreground=theme.text)
    style.configure("Header.TLabel", foreground=theme.heading)
    style.configure("Hint.TLabel", background=theme.surface, foreground=theme.hint)
    style.configure(
        "DashboardTitle.TLabel",
        background=theme.surface,
        foreground=theme.heading,
    )
    style.configure(
        "DashboardMetric.TFrame",
        background=theme.surface_alt,
        bordercolor=theme.border,
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "DashboardMetricTitle.TLabel",
        background=theme.surface_alt,
        foreground=theme.hint,
    )
    style.configure(
        "DashboardMetricValue.TLabel",
        background=theme.surface_alt,
        foreground=theme.heading,
    )
    style.configure(
        "TButton",
        foreground=theme.text,
        background=theme.surface,
        bordercolor=theme.border,
        lightcolor=theme.surface,
        darkcolor=theme.border,
        relief="solid",
        borderwidth=1,
    )
    style.map(
        "TButton",
        background=[("active", theme.surface_alt), ("pressed", theme.surface_alt)],
        foreground=[("active", theme.accent), ("pressed", theme.accent)],
        relief=[("active", "raised"), ("pressed", "sunken")],
    )
    style.configure(
        "DashboardNav.TButton",
        foreground=theme.text,
        background=theme.surface,
        bordercolor=theme.border,
        relief="solid",
        borderwidth=1,
    )
    style.map(
        "DashboardNav.TButton",
        background=[("active", theme.surface_alt), ("pressed", theme.surface_alt)],
        foreground=[("active", theme.accent), ("pressed", theme.accent)],
    )
    style.configure(
        "DashboardCard.TButton",
        foreground=theme.heading,
        background=theme.surface,
        bordercolor=theme.border,
        relief="solid",
        borderwidth=1,
    )
    style.map(
        "DashboardCard.TButton",
        background=[("active", theme.surface_alt), ("pressed", theme.surface_alt)],
        foreground=[("active", theme.accent), ("pressed", theme.accent)],
        relief=[("active", "raised"), ("pressed", "sunken")],
    )
    style.configure(
        "Primary.TButton",
        foreground="#ffffff",
        background=theme.primary,
        bordercolor=theme.primary,
        relief="solid",
        borderwidth=1,
    )
    style.map(
        "Primary.TButton",
        background=[("active", theme.primary_hover), ("pressed", theme.primary_hover)],
        foreground=[("active", "#ffffff"), ("pressed", "#ffffff")],
        relief=[("active", "raised"), ("pressed", "sunken")],
    )
    style.configure(
        "Calculator.TButton",
        foreground=theme.heading,
        background=theme.surface,
        bordercolor=theme.border,
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "TMenubutton",
        foreground=theme.heading,
        background=theme.surface_alt,
        bordercolor=theme.border,
        relief="solid",
        borderwidth=1,
    )
    style.map(
        "TMenubutton",
        background=[("active", theme.surface), ("pressed", theme.surface)],
        foreground=[("active", theme.accent), ("pressed", theme.accent)],
        relief=[("active", "raised"), ("pressed", "sunken")],
    )
    style.configure(
        "TEntry",
        foreground=theme.text,
        fieldbackground=theme.surface,
        bordercolor=theme.border,
        lightcolor=theme.surface,
        darkcolor=theme.border,
    )
    style.configure(
        "TCombobox",
        foreground=theme.text,
        fieldbackground=theme.surface,
        background=theme.surface,
        bordercolor=theme.border,
        lightcolor=theme.surface,
        darkcolor=theme.border,
        arrowcolor=theme.accent,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", theme.surface), ("focus", theme.surface)],
        background=[("readonly", theme.surface), ("active", theme.surface_alt)],
        foreground=[("readonly", theme.text)],
        selectbackground=[("readonly", theme.surface_alt)],
        selectforeground=[("readonly", theme.text)],
    )
    style.map(
        "Calculator.TButton",
        background=[("active", theme.surface_alt), ("pressed", theme.surface_alt)],
        foreground=[("active", theme.accent), ("pressed", theme.accent)],
        relief=[("active", "raised"), ("pressed", "sunken")],
    )
    style.configure("TLabelframe", background=theme.background, bordercolor=theme.border)
    style.configure("TLabelframe.Label", background=theme.background, foreground=theme.heading)
    style.configure(
        "Card.TLabelframe",
        background=theme.surface,
        bordercolor=theme.border,
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "Card.TLabelframe.Label",
        background=theme.surface,
        foreground=theme.heading,
    )
    style.configure("TNotebook", background=theme.background, borderwidth=0, tabmargins=(0, 0, 0, 0))
    style.configure(
        "TNotebook.Tab",
        background=theme.surface_alt,
        foreground=theme.text,
        bordercolor=theme.border,
        lightcolor=theme.surface,
        darkcolor=theme.border,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", theme.primary), ("active", theme.surface)],
        foreground=[("selected", "#ffffff"), ("active", theme.accent)],
    )
    style.configure(
        "Treeview",
        background=theme.surface,
        fieldbackground=theme.surface,
        foreground=theme.text,
        bordercolor=theme.border,
        lightcolor=theme.surface,
        darkcolor=theme.border,
    )
    style.map(
        "Treeview",
        background=[("selected", theme.accent)],
        foreground=[("selected", "#ffffff")],
    )
    style.configure(
        "Treeview.Heading",
        background=theme.surface_alt,
        foreground=theme.heading,
    )
    style.configure(
        "DataAction.TButton",
        foreground=theme.heading,
        background=theme.surface,
        bordercolor=theme.border,
        relief="solid",
        borderwidth=1,
    )
    style.map(
        "DataAction.TButton",
        background=[("active", theme.surface_alt), ("pressed", theme.surface_alt)],
        foreground=[("active", theme.accent), ("pressed", theme.accent)],
        relief=[("active", "raised"), ("pressed", "sunken")],
    )


def _configure_theme_fonts(style: ttk.Style) -> None:
    """Set all font/padding-related ttk style properties."""
    style.configure("Header.TLabel", font=("Microsoft YaHei UI", 18, "bold"))
    style.configure(
        "DashboardTitle.TLabel",
        font=("Microsoft YaHei UI", 15, "bold"),
    )
    style.configure(
        "DashboardMetricTitle.TLabel",
        font=("Microsoft YaHei UI", 11),
    )
    style.configure(
        "DashboardMetricValue.TLabel",
        font=("Microsoft YaHei UI", 18, "bold"),
    )
    style.configure(
        "TButton",
        padding=(12, 8),
        font=("Microsoft YaHei UI", 12),
    )
    style.configure(
        "DashboardNav.TButton",
        padding=(14, 9),
        font=("Microsoft YaHei UI", 12, "bold"),
    )
    style.configure(
        "DashboardCard.TButton",
        padding=(18, 18),
        font=("Microsoft YaHei UI", 17, "bold"),
    )
    style.configure(
        "Primary.TButton",
        padding=(16, 9),
        font=("Microsoft YaHei UI", 12, "bold"),
    )
    style.configure(
        "Calculator.TButton",
        font=("Microsoft YaHei UI", 19),
        padding=(10, 12),
    )
    style.configure(
        "TMenubutton",
        padding=(12, 8),
        font=("Microsoft YaHei UI", 12, "bold"),
    )
    style.configure(
        "TEntry",
        padding=(6, 5),
    )
    style.configure(
        "TCombobox",
        padding=(8, 6),
        font=("Microsoft YaHei UI", 12),
    )
    style.configure(
        "Card.TLabelframe.Label",
        font=("Microsoft YaHei UI", 11, "bold"),
    )
    style.configure(
        "TNotebook.Tab",
        padding=(18, 9),
        font=("Microsoft YaHei UI", 14, "bold"),
    )
    style.configure(
        "Treeview",
        rowheight=32,
    )
    style.configure(
        "Treeview.Heading",
        font=("Microsoft YaHei UI", 12, "bold"),
    )
    style.configure(
        "DataAction.TButton",
        padding=(14, 8),
        font=("Microsoft YaHei UI", 12, "bold"),
    )
