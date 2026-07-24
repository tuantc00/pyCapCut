"""Application shell and workspace navigation."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox, ttk

from .editor import EditorWorkspace
from .jobs import JobRunner
from .tooltip import Tooltip, missing_tooltips
from .workspaces import (
    BatchWorkspace,
    DraftManagerWorkspace,
    ExportWorkspace,
    TemplateWorkspace,
)


class CapCutApplication:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("pyCapCut Studio GUI")
        self.root.geometry("1500x940")
        self.root.minsize(1120, 720)
        self._configure_style()
        self.runner = JobRunner(root)
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _configure_style(self):
        style = ttk.Style()
        try:
            style.theme_use("vista" if sys.platform == "win32" else "clam")
        except tk.TclError:
            style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"), foreground="#1f5f99")
        style.configure("Status.TLabel", padding=(8, 4))
        style.configure("TNotebook.Tab", padding=(12, 6))

    def _build(self):
        header = ttk.Frame(self.root, padding=(10, 7))
        header.pack(fill="x")
        ttk.Label(header, text="🎬 pyCapCut Studio", style="Title.TLabel").pack(side="left")
        ttk.Label(
            header,
            text="GUI orchestration only — pycapcut processing remains unchanged",
        ).pack(side="left", padx=16)
        help_button = ttk.Button(header, text="? Hướng dẫn / Help", command=self.show_help)
        help_button.pack(side="right")
        Tooltip.attach(
            help_button,
            "Mở hướng dẫn nhanh về output, tooltip và giới hạn preview/export.",
            "Open quick help about output, tooltips and preview/export limitations.",
        )

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)
        self.drafts = DraftManagerWorkspace(self.notebook)
        self.editor = EditorWorkspace(self.notebook, self.runner, self.refresh_drafts)
        self.batch = BatchWorkspace(self.notebook, self.runner, self.refresh_drafts)
        self.template = TemplateWorkspace(self.notebook)
        self.export = ExportWorkspace(self.notebook, self.runner)
        self.notebook.add(self.editor, text="Editor / Dựng Draft")
        self.notebook.add(self.drafts, text="Draft Manager")
        self.notebook.add(self.batch, text="Batch Creator")
        self.notebook.add(self.template, text="Template Mode")
        self.notebook.add(self.export, text="Export Queue")
        Tooltip.attach(
            self.notebook,
            "Chuyển giữa dựng mới, quản lý draft, batch, template và export.",
            "Switch between editing, draft management, batch, template and export.",
        )
        self.status = ttk.Label(
            self.root,
            text="Windows target • Hover any control for bilingual help",
            style="Status.TLabel",
            relief="sunken",
            anchor="w",
        )
        self.status.pack(fill="x")
        self.notebook.bind("<<NotebookTabChanged>>", lambda _event: self.root.after_idle(self.audit_tooltips))
        self.root.after_idle(self.audit_tooltips)

    def audit_tooltips(self):
        missing = missing_tooltips(self.root)
        if missing:
            names = ", ".join(str(widget) for widget in missing[:4])
            self.status.configure(
                text=f"⚠ Missing tooltip: {len(missing)} — {names}"
            )
        else:
            self.status.configure(
                text="Tooltip audit: PASS • Windows target • Hover any control for bilingual help"
            )

    def refresh_drafts(self):
        try:
            self.drafts.refresh()
        except Exception:
            pass
        try:
            self.template.refresh_drafts()
        except Exception:
            pass
        try:
            self.export.refresh()
        except Exception:
            pass

    def show_help(self):
        messagebox.showinfo(
            "pyCapCut Studio",
            "• Hover control để xem tooltip Việt–Anh / bilingual tooltip.\n"
            "• Editor và Batch tạo CapCut draft, không render MP4.\n"
            "• Preview mở media bằng player mặc định của Windows.\n"
            "• Template chỉ dùng các thao tác README hỗ trợ.\n"
            "• Export Queue cần Windows, CapCut/Jianying ≤ 6 và CapCut đang mở.\n"
            "• Project Editor chỉ nằm trong RAM; hãy Create Draft trước khi đóng.",
        )

    def close(self):
        if self.runner.running:
            if not messagebox.askyesno(
                "pyCapCut Studio",
                "Tác vụ đang chạy. Đóng GUI sẽ không hủy an toàn thao tác CapCut hiện tại.\n"
                "A job is running. Close anyway?",
            ):
                return
        if messagebox.askyesno(
            "pyCapCut Studio",
            "Đóng ứng dụng? Phiên Editor chưa tạo draft sẽ bị mất.\n"
            "Close the application? Unsaved in-memory edits will be lost.",
        ):
            self.root.destroy()


def main():
    root = tk.Tk()
    CapCutApplication(root)
    root.mainloop()
