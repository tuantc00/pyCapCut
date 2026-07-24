"""Shared Tkinter widgets for the pyCapCut desktop application."""

from __future__ import annotations

import json
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional, Sequence

from .models import ProjectHistory, ProjectModel, format_time
from .tooltip import Tooltip


class ScrollableFrame(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.body.bind(
            "<Configure>",
            lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda event: self.canvas.itemconfigure(self.window_id, width=event.width),
        )
        Tooltip.attach(
            self.canvas,
            "Cuộn để xem các thuộc tính còn lại.",
            "Scroll to view the remaining properties.",
        )


class LogPanel(ttk.LabelFrame):
    COLORS = {
        "info": "#b45f06",
        "success": "#287a38",
        "warning": "#b45f06",
        "error": "#b3261e",
        "processing": "#1f5f99",
    }

    def __init__(self, master, height: int = 7):
        super().__init__(master, text="Nhật ký / Log")
        scrollbar = ttk.Scrollbar(self)
        scrollbar.pack(side="right", fill="y")
        self.text = tk.Text(
            self,
            height=height,
            wrap="word",
            state="disabled",
            font=("Consolas", 9),
            yscrollcommand=scrollbar.set,
        )
        self.text.pack(fill="both", expand=True)
        scrollbar.configure(command=self.text.yview)
        for name, color in self.COLORS.items():
            self.text.tag_configure(name, foreground=color)
        Tooltip.attach(
            self.text,
            "Hiển thị thao tác và lỗi gốc; có thể chọn và sao chép nội dung.",
            "Shows operations and original errors; text can be selected and copied.",
        )

    def log(self, message: str, level: str = "info") -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.text.configure(state="normal")
        self.text.insert("end", f"[{stamp}] {message}\n", level)
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")


class FormDialog(tk.Toplevel):
    """Small schema-driven dialog.

    Schema entries: ``(key, label, default, kind, choices, vi_help, en_help)``.
    Kind is one of ``entry``, ``bool``, ``choice`` or ``text``.
    """

    def __init__(
        self,
        master,
        title: str,
        schema: Sequence[tuple],
        initial: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(master)
        self.title(title)
        self.transient(master.winfo_toplevel())
        self.resizable(True, True)
        self.result: Optional[Dict[str, Any]] = None
        self.vars: Dict[str, Any] = {}
        initial = initial or {}
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        for row, item in enumerate(schema):
            key, label, default, kind, choices, vi_help, en_help = item
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="nw", padx=(0, 8), pady=4)
            value = initial.get(key, default)
            if kind == "bool":
                variable = tk.BooleanVar(value=bool(value))
                widget = ttk.Checkbutton(body, variable=variable)
            elif kind == "choice":
                variable = tk.StringVar(value=str(value))
                widget = ttk.Combobox(
                    body,
                    textvariable=variable,
                    values=list(choices or []),
                    state="readonly",
                    width=38,
                )
            elif kind == "text":
                variable = None
                widget = tk.Text(body, height=5, width=44)
                widget.insert("1.0", str(value))
            else:
                variable = tk.StringVar(value="" if value is None else str(value))
                widget = ttk.Entry(body, textvariable=variable, width=42)
            widget.grid(row=row, column=1, sticky="ew", pady=4)
            self.vars[key] = (variable, widget, kind)
            Tooltip.attach(widget, vi_help, en_help)
        body.columnconfigure(1, weight=1)
        buttons = ttk.Frame(body)
        buttons.grid(row=len(schema), column=0, columnspan=2, sticky="e", pady=(12, 0))
        ok = ttk.Button(buttons, text="Áp dụng / Apply", command=self._accept)
        ok.pack(side="left", padx=4)
        cancel = ttk.Button(buttons, text="Hủy / Cancel", command=self.destroy)
        cancel.pack(side="left", padx=4)
        Tooltip.attach(ok, "Xác nhận các giá trị trong hộp thoại.", "Accept values in this dialog.")
        Tooltip.attach(cancel, "Đóng mà không lưu thay đổi.", "Close without saving changes.")
        self.bind("<Escape>", lambda _event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def _accept(self) -> None:
        result: Dict[str, Any] = {}
        for key, (variable, widget, kind) in self.vars.items():
            if kind == "text":
                result[key] = widget.get("1.0", "end-1c")
            elif kind == "bool":
                result[key] = bool(variable.get())
            else:
                result[key] = variable.get()
        self.result = result
        self.destroy()

    @classmethod
    def ask(
        cls,
        master,
        title: str,
        schema: Sequence[tuple],
        initial: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        dialog = cls(master, title, schema, initial)
        master.wait_window(dialog)
        return dialog.result


class ListEditor(ttk.LabelFrame):
    def __init__(
        self,
        master,
        title: str,
        columns: Sequence[str],
        schema: Sequence[tuple],
        values: Optional[List[Dict[str, Any]]] = None,
        on_change: Optional[Callable[[], None]] = None,
        before_change: Optional[Callable[[], None]] = None,
    ):
        super().__init__(master, text=title)
        self.columns = list(columns)
        self.schema = schema
        self.values = values if values is not None else []
        self.on_change = on_change
        self.before_change = before_change
        self.tree = ttk.Treeview(
            self,
            columns=self.columns,
            show="headings",
            height=4,
            selectmode="browse",
        )
        for column in self.columns:
            self.tree.heading(column, text=column)
            self.tree.column(column, width=95, stretch=True)
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=4, pady=(0, 4))
        add = ttk.Button(buttons, text="+ Thêm / Add", command=self._add)
        edit = ttk.Button(buttons, text="Sửa / Edit", command=self._edit)
        remove = ttk.Button(buttons, text="Xóa / Delete", command=self._remove)
        add.pack(side="left", padx=2)
        edit.pack(side="left", padx=2)
        remove.pack(side="left", padx=2)
        Tooltip.attach(self.tree, f"Danh sách {title}; chọn một dòng để sửa.", f"{title} list; select a row to edit.")
        Tooltip.attach(add, f"Thêm mục mới vào {title}.", f"Add a new item to {title}.")
        Tooltip.attach(edit, f"Sửa mục đang chọn trong {title}.", f"Edit the selected {title} item.")
        Tooltip.attach(remove, f"Xóa mục đang chọn khỏi {title}.", f"Remove the selected {title} item.")
        self.refresh()

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, value in enumerate(self.values):
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=[_display(value.get(column, "")) for column in self.columns],
            )

    def _add(self) -> None:
        result = FormDialog.ask(self, f"Thêm / Add — {self.cget('text')}", self.schema)
        if result is not None:
            if self.before_change:
                self.before_change()
            self.values.append(result)
            self.refresh()
            if self.on_change:
                self.on_change()

    def _edit(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("pyCapCut", "Hãy chọn một dòng / Select a row")
            return
        index = int(selection[0])
        result = FormDialog.ask(
            self,
            f"Sửa / Edit — {self.cget('text')}",
            self.schema,
            self.values[index],
        )
        if result is not None:
            if self.before_change:
                self.before_change()
            self.values[index] = result
            self.refresh()
            if self.on_change:
                self.on_change()

    def _remove(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        if self.before_change:
            self.before_change()
        self.values.pop(int(selection[0]))
        self.refresh()
        if self.on_change:
            self.on_change()


class TimelineCanvas(ttk.Frame):
    TRACK_HEIGHT = 58
    HEADER_WIDTH = 130
    RULER_HEIGHT = 28
    COLORS = {
        "video": "#4c78a8",
        "audio": "#59a14f",
        "text": "#f28e2b",
        "subtitle": "#edc949",
        "sticker": "#b07aa1",
        "effect": "#e15759",
        "filter": "#76b7b2",
    }

    def __init__(
        self,
        master,
        get_project: Callable[[], ProjectModel],
        history: ProjectHistory,
        on_select: Callable[[str, str], None],
        on_change: Callable[[], None],
    ):
        super().__init__(master)
        self.get_project = get_project
        self.history = history
        self.on_select = on_select
        self.on_change = on_change
        self.pixels_per_second = 60.0
        self.snap = tk.BooleanVar(value=False)
        self.canvas = tk.Canvas(self, background="#1f2329", highlightthickness=0)
        xbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        ybar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xbar.set, yscrollcommand=ybar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.segment_boxes: Dict[int, tuple[str, str, float, float, float, float]] = {}
        self.drag: Optional[Dict[str, Any]] = None
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<MouseWheel>", self._wheel)
        Tooltip.attach(
            self.canvas,
            "Timeline: chọn segment; kéo để đổi vị trí; kéo sát mép phải để đổi thời lượng; Ctrl+wheel để zoom.",
            "Timeline: select a segment; drag to move; drag its right edge to resize; Ctrl+wheel zooms.",
        )

    def set_zoom(self, value: float) -> None:
        self.pixels_per_second = max(20, min(300, float(value)))
        self.redraw()

    def redraw(self) -> None:
        project = self.get_project()
        canvas = self.canvas
        canvas.delete("all")
        self.segment_boxes.clear()
        duration_sec = max(10.0, project.duration_us / 1_000_000 + 2)
        width = self.HEADER_WIDTH + duration_sec * self.pixels_per_second
        height = self.RULER_HEIGHT + max(1, len(project.tracks)) * self.TRACK_HEIGHT
        canvas.configure(scrollregion=(0, 0, width, height))
        canvas.create_rectangle(0, 0, width, self.RULER_HEIGHT, fill="#16191d", outline="")
        for second in range(int(duration_sec) + 1):
            x = self.HEADER_WIDTH + second * self.pixels_per_second
            canvas.create_line(x, 0, x, height, fill="#343b43")
            canvas.create_text(x + 3, 4, text=f"{second}s", fill="#c8d0da", anchor="nw", font=("Segoe UI", 8))
        for row, track in enumerate(project.tracks):
            y1 = self.RULER_HEIGHT + row * self.TRACK_HEIGHT
            y2 = y1 + self.TRACK_HEIGHT
            fill = "#252b32" if row % 2 == 0 else "#2b3139"
            canvas.create_rectangle(0, y1, width, y2, fill=fill, outline="#3b434d")
            track_id = canvas.create_text(
                8,
                (y1 + y2) / 2,
                text=f"{track.name}\n[{track.kind}]",
                fill="#edf2f7",
                anchor="w",
                font=("Segoe UI", 9),
            )
            canvas.tag_bind(
                track_id,
                "<Button-1>",
                lambda _event, tid=track.id: self.on_select("track", tid),
            )
            for segment in track.segments:
                try:
                    start_us = segment.start_us
                    duration_us = segment.duration_us
                    invalid = False
                except ValueError:
                    start_us = 0
                    duration_us = 1_000_000
                    invalid = True
                x1 = self.HEADER_WIDTH + start_us / 1_000_000 * self.pixels_per_second
                x2 = x1 + duration_us / 1_000_000 * self.pixels_per_second
                sy1, sy2 = y1 + 7, y2 - 7
                item = canvas.create_rectangle(
                    x1,
                    sy1,
                    max(x1 + 6, x2),
                    sy2,
                    fill="#b3261e" if invalid else self.COLORS.get(segment.kind, "#777"),
                    outline="#f7f7f7",
                    width=1,
                    tags=("segment",),
                )
                label = canvas.create_text(
                    x1 + 6,
                    (sy1 + sy2) / 2,
                    text=segment.name or segment.kind,
                    fill="white",
                    anchor="w",
                    font=("Segoe UI", 9),
                    tags=("segment_label",),
                )
                box = (track.id, segment.id, x1, sy1, max(x1 + 6, x2), sy2)
                self.segment_boxes[item] = box
                self.segment_boxes[label] = box

    def _hit(self, x: float, y: float):
        for item in reversed(self.canvas.find_overlapping(x, y, x, y)):
            if item in self.segment_boxes:
                return self.segment_boxes[item]
        return None

    def _press(self, event) -> None:
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        hit = self._hit(x, y)
        if not hit:
            return
        track_id, segment_id, x1, _y1, x2, _y2 = hit
        self.on_select("segment", segment_id)
        _track, segment = self.get_project().find_segment(segment_id)
        try:
            start_us = segment.start_us
            duration_us = segment.duration_us
        except ValueError:
            return
        self.history.checkpoint()
        self.drag = {
            "track_id": track_id,
            "segment_id": segment_id,
            "origin_x": x,
            "start": start_us,
            "duration": duration_us,
            "mode": "resize" if x2 - x <= 8 else "move",
        }

    def _drag(self, event) -> None:
        if not self.drag:
            return
        x = self.canvas.canvasx(event.x)
        delta = int(round((x - self.drag["origin_x"]) / self.pixels_per_second * 1_000_000))
        _track, segment = self.get_project().find_segment(self.drag["segment_id"])
        if self.drag["mode"] == "move":
            value = max(0, self.drag["start"] + delta)
            if self.snap.get():
                value = round(value / 100_000) * 100_000
            segment.start = format_time(value)
        else:
            value = max(10_000, self.drag["duration"] + delta)
            if self.snap.get():
                value = max(100_000, round(value / 100_000) * 100_000)
            segment.duration = format_time(value)
        self.redraw()

    def _release(self, _event) -> None:
        if self.drag:
            self.drag = None
            self.on_change()

    def _wheel(self, event) -> None:
        if event.state & 0x0004:
            self.set_zoom(self.pixels_per_second + (10 if event.delta > 0 else -10))
        else:
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")


def clear_children(widget) -> None:
    for child in widget.winfo_children():
        child.destroy()


def labelled_entry(
    parent,
    row: int,
    label: str,
    variable,
    vi_help: str,
    en_help: str,
    width: int = 16,
):
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=3)
    entry = ttk.Entry(parent, textvariable=variable, width=width)
    entry.grid(row=row, column=1, sticky="ew", padx=4, pady=3)
    Tooltip.attach(entry, vi_help, en_help)
    parent.columnconfigure(1, weight=1)
    return entry


def _display(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
