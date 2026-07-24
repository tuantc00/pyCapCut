"""Reusable bilingual tooltip support."""

from __future__ import annotations

import tkinter as tk
from typing import Dict


class Tooltip:
    registry: Dict[str, "Tooltip"] = {}

    def __init__(self, widget: tk.Widget, vi_text: str, en_text: str, delay_ms: int = 450):
        self.widget = widget
        self.vi_text = vi_text.strip()
        self.en_text = en_text.strip()
        self.delay_ms = delay_ms
        self.window = None
        self.after_id = None
        setattr(widget, "_pycapcut_tooltip", self)
        Tooltip.registry[str(widget)] = self
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    @classmethod
    def attach(
        cls,
        widget: tk.Widget,
        vi_text: str,
        en_text: str,
        delay_ms: int = 450,
    ) -> "Tooltip":
        return cls(widget, vi_text, en_text, delay_ms)

    @property
    def text(self) -> str:
        return f"{self.vi_text}\n\nEN: {self.en_text}"

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self.after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self) -> None:
        if self.after_id is not None:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def _show(self) -> None:
        if self.window is not None or not self.widget.winfo_exists():
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.window = top = tk.Toplevel(self.widget)
        top.wm_overrideredirect(True)
        top.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            top,
            text=self.text,
            justify=tk.LEFT,
            wraplength=420,
            background="#fff9d8",
            foreground="#202020",
            relief=tk.SOLID,
            borderwidth=1,
            padx=8,
            pady=6,
            font=("Segoe UI", 9),
        )
        label.pack()

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self.window is not None:
            self.window.destroy()
            self.window = None


def tip(widget: tk.Widget, vi: str, en: str) -> tk.Widget:
    Tooltip.attach(widget, vi, en)
    return widget


def missing_tooltips(root: tk.Widget) -> list[tk.Widget]:
    """Return interactive widgets that have not registered a tooltip."""
    interactive_classes = {
        "TButton",
        "TEntry",
        "TCombobox",
        "TCheckbutton",
        "TScale",
        "Treeview",
        "Text",
        "Canvas",
        "TNotebook",
    }
    missing = []
    stack = [root]
    while stack:
        widget = stack.pop()
        stack.extend(widget.winfo_children())
        if (
            widget.winfo_class() in interactive_classes
            and not hasattr(widget, "_pycapcut_tooltip")
        ):
            missing.append(widget)
    return missing
