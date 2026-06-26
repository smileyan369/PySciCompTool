"""Themed, non-blocking startup splash screen."""

from __future__ import annotations

import math
import time
import tkinter as tk

from .theme_models import AppTheme


class StartupSplash:
    """An independent splash window that stays visible while the workbench is built."""

    def __init__(self, root: tk.Tk, theme: AppTheme) -> None:
        self.root = root
        self.theme = theme
        self.width = 560
        self.height = 320
        self.window: tk.Toplevel | None = None
        self.canvas: tk.Canvas | None = None
        self._bar_width = 0
        self._opened = False

    def open(self) -> None:
        """Show the splash immediately and keep the main root hidden."""
        if self._opened:
            return
        self.root.withdraw()
        window = tk.Toplevel(self.root)
        self.window = window
        window.withdraw()
        window.overrideredirect(True)
        window.configure(background=self.theme.background)
        canvas = tk.Canvas(window, width=self.width, height=self.height, highlightthickness=0, background=self.theme.background)
        self.canvas = canvas
        canvas.pack(fill="both", expand=True)
        window.update_idletasks()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = max(0, (screen_width - self.width) // 2)
        y = max(0, (screen_height - self.height) // 2)
        window.geometry(f"{self.width}x{self.height}+{x}+{y}")
        try:
            window.attributes("-topmost", True)
        except tk.TclError:
            pass
        window.deiconify()
        self._opened = True
        self.update(0.03, "\u6b63\u5728\u542f\u52a8", "\u6b63\u5728\u51c6\u5907\u542f\u52a8\u754c\u9762")

    def update(self, progress: float, status: str, detail: str) -> None:
        """Render a frame; the percentage reflects actual startup stages."""
        if not self._opened:
            self.open()
        self._draw(max(0.0, min(1.0, progress)), time.monotonic(), status, detail)
        if self.window is not None:
            self.window.update_idletasks()

    def close(self, *, show_root: bool = True) -> None:
        """Remove splash; optionally reveal the already-built main window."""
        if not self._opened:
            return
        if self.window is not None:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
        self.window = None
        self.canvas = None
        self._opened = False
        if show_root:
            self.root.deiconify()
            try:
                self.root.lift()
            except tk.TclError:
                pass

    def show(self, duration_ms: int = 1200) -> None:
        """Backward-compatible blocking presentation for direct callers."""
        self.open()
        start = time.monotonic()
        duration = max(duration_ms, 300) / 1000
        while True:
            elapsed = time.monotonic() - start
            progress = min(1.0, elapsed / duration)
            self.update(progress, "\u6b63\u5728\u52a0\u8f7d", "\u6b63\u5728\u51c6\u5907\u8ba1\u7b97\u3001\u6570\u636e\u4e0e\u56fe\u8868\u6a21\u5757")
            self.root.update()
            if progress >= 1.0:
                break
            time.sleep(0.025)
        self.close(show_root=True)

    def _draw(self, progress: float, clock: float, status: str, detail: str) -> None:
        c = self.canvas
        if c is None:
            return
        c.delete("all")
        theme = self.theme
        c.configure(background=theme.background)
        margin = 22
        c.create_rectangle(margin, margin, self.width - margin, self.height - margin, fill=theme.surface, outline=theme.border, width=1)
        c.create_rectangle(margin + 1, margin + 1, self.width - margin - 1, 88, fill=theme.surface_alt, outline="")
        c.create_text(48, 54, text="\u661f\u7b97\u5de5\u574a", anchor="w", fill=theme.heading, font=("Microsoft YaHei UI", 20, "bold"))
        c.create_text(48, 122, text=status, anchor="w", fill=theme.text, font=("Microsoft YaHei UI", 12))
        c.create_text(48, 154, text=detail, anchor="w", fill=theme.hint, font=("Microsoft YaHei UI", 10))
        dot_y = 198
        for index in range(5):
            phase = clock * 5.2 - index * 0.65
            radius = 5 + 4 * (math.sin(phase) + 1) / 2
            color = theme.accent if index % 2 == 0 else theme.primary
            x = 48 + index * 28
            c.create_oval(x - radius, dot_y - radius, x + radius, dot_y + radius, fill=color, outline="")
        bar_x, bar_y, bar_h = 48, 246, 10
        bar_w = self.width - 96
        self._bar_width = int(bar_w * progress)
        percentage = int(progress * 100)
        c.create_rectangle(bar_x, bar_y, bar_x + bar_w, bar_y + bar_h, fill=theme.surface_alt, outline=theme.border)
        c.create_rectangle(bar_x, bar_y, bar_x + self._bar_width, bar_y + bar_h, fill=theme.primary, outline="")
        c.create_text(self.width - 48, 122, text=f"{percentage:>3}%", anchor="e", fill=theme.accent, font=("Microsoft YaHei UI", 18, "bold"))
