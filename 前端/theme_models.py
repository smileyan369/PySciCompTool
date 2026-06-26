"""Theme data models for the Tkinter frontend."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppTheme:
    """Visual settings shared by all frontend layouts."""

    name: str
    display_name: str
    background: str
    surface: str
    surface_alt: str
    border: str
    text: str
    heading: str
    hint: str
    primary: str
    primary_hover: str
    accent: str
    danger: str
    chart_background: str
    chart_grid: str
    chart_line: str
    chart_point: str
    chart_fit: str


DEFAULT_DASHBOARD = AppTheme(
    name="default_dashboard",
    display_name="默认仪表盘",
    background="#edf5ff",
    surface="#ffffff",
    surface_alt="#eaf2ff",
    border="#d8e4fb",
    text="#263764",
    heading="#18246b",
    hint="#6479a8",
    primary="#4267f6",
    primary_hover="#3157e7",
    accent="#4f6df5",
    danger="#dc2626",
    chart_background="#ffffff",
    chart_grid="#dbe6fb",
    chart_line="#4267f6",
    chart_point="#4f6df5",
    chart_fit="#7c5cff",
)

SOFT_BLUE = AppTheme(
    name="soft_blue",
    display_name="浅蓝助手",
    background="#f4f7ff",
    surface="#ffffff",
    surface_alt="#eef2ff",
    border="#dde5fb",
    text="#26345f",
    heading="#16205f",
    hint="#6676a4",
    primary="#6c5cf6",
    primary_hover="#5b4be6",
    accent="#7c67ff",
    danger="#dc2626",
    chart_background="#ffffff",
    chart_grid="#e1e6fb",
    chart_line="#6c5cf6",
    chart_point="#4f7df5",
    chart_fit="#ec5f9d",
)

PYLAB_WORKBENCH = AppTheme(
    name="pylab_workbench",
    display_name="PyLab 工作台",
    background="#f5f7fa",
    surface="#ffffff",
    surface_alt="#eef2f6",
    border="#dce3eb",
    text="#111827",
    heading="#172033",
    hint="#64748b",
    primary="#00a99d",
    primary_hover="#079185",
    accent="#0078d7",
    danger="#dc2626",
    chart_background="#ffffff",
    chart_grid="#d7dde5",
    chart_line="#008fb3",
    chart_point="#d9467d",
    chart_fit="#84cc16",
)

SCI_DARK = AppTheme(
    name="sci_dark",
    display_name="深色科技",
    background="#0d141b",
    surface="#151d25",
    surface_alt="#1f2a35",
    border="#2f3b48",
    text="#d7dee8",
    heading="#29c7f4",
    hint="#91a0af",
    primary="#0ea5c6",
    primary_hover="#0885a3",
    accent="#22d3ee",
    danger="#f87171",
    chart_background="#111923",
    chart_grid="#293747",
    chart_line="#22d3ee",
    chart_point="#f59e0b",
    chart_fit="#38bdf8",
)

PASTEL_CARD = AppTheme(
    name="pastel_card",
    display_name="浅紫卡片",
    background="#f8f4ff",
    surface="#ffffff",
    surface_alt="#f1ebff",
    border="#e3d7ff",
    text="#342b75",
    heading="#1d185b",
    hint="#7b74a0",
    primary="#7b61ff",
    primary_hover="#6b50ef",
    accent="#8b5cf6",
    danger="#dc2626",
    chart_background="#ffffff",
    chart_grid="#e7dcff",
    chart_line="#7b61ff",
    chart_point="#4f7df5",
    chart_fit="#ec5f9d",
)

FORMULA_LAB = AppTheme(
    name="formula_lab",
    display_name="公式实验室",
    background="#08271f",
    surface="#0d332b",
    surface_alt="#173f35",
    border="#315e52",
    text="#f4ecd1",
    heading="#f4cf74",
    hint="#b7c7b5",
    primary="#d9a441",
    primary_hover="#bf8f32",
    accent="#22d3c5",
    danger="#f87171",
    chart_background="#0b2a22",
    chart_grid="#315e52",
    chart_line="#20d7d2",
    chart_point="#f5d37b",
    chart_fit="#d9a441",
)


THEMES: dict[str, AppTheme] = {
    DEFAULT_DASHBOARD.display_name: DEFAULT_DASHBOARD,
    SOFT_BLUE.display_name: SOFT_BLUE,
    PYLAB_WORKBENCH.display_name: PYLAB_WORKBENCH,
    SCI_DARK.display_name: SCI_DARK,
    PASTEL_CARD.display_name: PASTEL_CARD,
    FORMULA_LAB.display_name: FORMULA_LAB,
}

THEME_NAMES = tuple(THEMES.keys())
