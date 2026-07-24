"""Draft manager, batch creator, template and export workspaces."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Optional

from .jobs import JobEvent, JobRunner
from .services import (
    BatchCreator,
    BatchOptions,
    DraftService,
    ExportQueue,
    TemplateSession,
    open_capcut,
    open_path,
)
from .tooltip import Tooltip
from .widgets import FormDialog, LogPanel
    

DEFAULT_DRAFTS = str(Path.home() / "Documents" / "CapCut Drafts")


class DraftManagerWorkspace(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=8)
        self.folder_var = tk.StringVar(value=DEFAULT_DRAFTS)
        self._build()

    def _build(self):
        top = ttk.LabelFrame(self, text="Thư mục Draft / Draft Folder", padding=6)
        top.pack(fill="x")
        entry = ttk.Entry(top, textvariable=self.folder_var)
        entry.pack(side="left", fill="x", expand=True)
        browse = ttk.Button(top, text="Chọn / Browse", command=self.browse)
        browse.pack(side="left", padx=3)
        refresh = ttk.Button(top, text="Làm mới / Refresh", command=self.refresh)
        refresh.pack(side="left", padx=3)
        Tooltip.attach(entry, "Đường dẫn chứa các thư mục draft CapCut.", "Folder containing CapCut draft directories.")
        Tooltip.attach(browse, "Chọn thư mục draft.", "Choose the drafts folder.")
        Tooltip.attach(refresh, "Đọc lại danh sách draft.", "Reload the draft list.")

        pane = ttk.Panedwindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True, pady=6)
        left = ttk.Frame(pane)
        right = ttk.Frame(pane)
        pane.add(left, weight=1)
        pane.add(right, weight=2)
        self.tree = ttk.Treeview(left, show="tree", selectmode="browse")
        self.tree.heading("#0", text="Draft")
        self.tree.pack(fill="both", expand=True)
        Tooltip.attach(self.tree, "Danh sách draft là các thư mục con.", "Drafts are listed from direct child folders.")
        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=4)
        for text, command, vi, en in [
            ("Mở / Open", self.open_selected, "Mở thư mục draft bằng Explorer.", "Open the draft folder in Explorer."),
            ("Duplicate", self.duplicate, "Nhân bản draft bằng API template.", "Duplicate using the template API."),
            ("Inspect", self.inspect, "Trích xuất sticker/bubble/flower-text metadata.", "Extract sticker/bubble/flower-text metadata."),
            ("Xóa / Delete", self.remove, "Xóa toàn bộ draft sau xác nhận.", "Delete the entire draft after confirmation."),
        ]:
            button = ttk.Button(buttons, text=text, command=command)
            button.pack(side="left", padx=2)
            Tooltip.attach(button, vi, en)
        self.details = tk.Text(right, wrap="word", state="disabled")
        self.details.pack(fill="both", expand=True)
        Tooltip.attach(
            self.details,
            "Kết quả Inspect Material; chọn và sao chép resource ID tại đây.",
            "Inspect Material output; copy resource IDs from here.",
        )

    def browse(self):
        folder = filedialog.askdirectory(initialdir=self.folder_var.get() or str(Path.home()))
        if folder:
            self.folder_var.set(folder)
            self.refresh()

    def service(self) -> DraftService:
        return DraftService(self.folder_var.get().strip())

    def refresh(self):
        try:
            names = self.service().list()
        except Exception as exc:
            messagebox.showerror("Draft Manager", str(exc))
            return
        self.tree.delete(*self.tree.get_children())
        for name in names:
            self.tree.insert("", "end", iid=name, text=name)

    def selected(self) -> Optional[str]:
        selection = self.tree.selection()
        return selection[0] if selection else None

    def open_selected(self):
        name = self.selected()
        if name:
            open_path(os.path.join(self.folder_var.get(), name))

    def duplicate(self):
        source = self.selected()
        if not source:
            return
        target = simpledialog.askstring("Duplicate", f"Tên draft mới từ '{source}' / New draft name:")
        if not target:
            return
        path = os.path.join(self.folder_var.get(), target)
        overwrite = False
        if os.path.exists(path):
            overwrite = messagebox.askyesno(
                "Confirm overwrite",
                f"Draft '{target}' đã tồn tại. Ghi đè toàn bộ?\nReplace the existing draft?",
            )
            if not overwrite:
                return
        try:
            self.service().duplicate(source, target, overwrite)
        except Exception as exc:
            messagebox.showerror("Duplicate", str(exc))
        else:
            self.refresh()

    def inspect(self):
        name = self.selected()
        if not name:
            return
        try:
            text = self.service().inspect(name)
        except Exception as exc:
            messagebox.showerror("Inspect", str(exc))
            return
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def remove(self):
        name = self.selected()
        if not name:
            return
        typed = simpledialog.askstring(
            "Xóa Draft / Delete Draft",
            f"Nhập chính xác '{name}' để xóa vĩnh viễn:\nType the exact draft name to delete:",
        )
        if typed != name:
            return
        try:
            self.service().remove(name)
        except Exception as exc:
            messagebox.showerror("Delete", str(exc))
        else:
            self.refresh()


class BatchWorkspace(ttk.Frame):
    def __init__(self, master, runner: JobRunner, on_created=None):
        super().__init__(master, padding=8)
        self.runner = runner
        self.on_created = on_created
        self.creator: Optional[BatchCreator] = None
        self.vars = {
            "source": tk.StringVar(),
            "draft_folder": tk.StringVar(value=DEFAULT_DRAFTS),
            "voice": tk.StringVar(),
            "subtitle": tk.StringVar(),
            "duration": tk.StringVar(value="30s"),
            "width": tk.IntVar(value=1920),
            "height": tk.IntVar(value=1080),
            "fps": tk.IntVar(value=30),
            "volume": tk.DoubleVar(value=1.0),
            "mute_source": tk.BooleanVar(value=True),
            "add_subtitles": tk.BooleanVar(value=True),
            "limit": tk.IntVar(value=10),
            "test": tk.BooleanVar(value=False),
            "overwrite": tk.BooleanVar(value=False),
            "prefix": tk.StringVar(value="auto_video"),
        }
        self._build()

    def _build(self):
        form = ttk.LabelFrame(self, text="Batch Creator — mỗi source → một draft", padding=8)
        form.pack(fill="x")
        row = 0
        for key, label, kind, help_vi, help_en in [
            ("source", "Source folder", "dir", "Thư mục video; đọc trực tiếp, không đệ quy.", "Video folder; direct children only."),
            ("draft_folder", "Draft folder", "dir", "Thư mục output CapCut drafts.", "Output CapCut drafts folder."),
            ("voice", "Voice file", "file", "Audio dùng chung; có thể để trống.", "Shared voice audio; optional."),
            ("subtitle", "Subtitle SRT", "file", "SRT dùng chung khi Add Subtitles bật.", "Shared SRT when Add Subtitles is enabled."),
        ]:
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=3)
            entry = ttk.Entry(form, textvariable=self.vars[key])
            entry.grid(row=row, column=1, sticky="ew", padx=4)
            browse = ttk.Button(form, text="…", width=3, command=lambda k=key, t=kind: self._browse(k, t))
            browse.grid(row=row, column=2)
            Tooltip.attach(entry, help_vi, help_en)
            Tooltip.attach(browse, f"Chọn {label}.", f"Choose {label}.")
            row += 1
        form.columnconfigure(1, weight=1)
        settings = ttk.Frame(form)
        settings.grid(row=row, column=0, columnspan=3, sticky="ew", pady=6)
        for index, (key, label, vi, en) in enumerate([
            ("duration", "Duration", "Thời lượng mỗi video, ví dụ 30s.", "Duration of each video, e.g. 30s."),
            ("width", "Width", "Chiều rộng canvas.", "Canvas width."),
            ("height", "Height", "Chiều cao canvas.", "Canvas height."),
            ("fps", "FPS", "Frame rate của draft.", "Draft frame rate."),
            ("volume", "Voice volume", "Hệ số 0–1; 1 = 100%.", "Multiplier 0–1; 1 = 100%."),
            ("limit", "Count", "Số source tối đa.", "Maximum source count."),
            ("prefix", "Prefix", "Tiền tố tên draft.", "Draft name prefix."),
        ]):
            ttk.Label(settings, text=label).grid(row=index // 4 * 2, column=index % 4, sticky="w", padx=3)
            entry = ttk.Entry(settings, textvariable=self.vars[key], width=13)
            entry.grid(row=index // 4 * 2 + 1, column=index % 4, sticky="ew", padx=3)
            Tooltip.attach(entry, vi, en)
        row += 1
        checks = ttk.Frame(form)
        checks.grid(row=row, column=0, columnspan=3, sticky="w")
        for key, text, vi, en in [
            ("mute_source", "Mute source", "Đặt volume video bằng 0.", "Set source video volume to zero."),
            ("add_subtitles", "Add subtitles", "Nhập SRT nếu có đường dẫn.", "Import SRT when a path is supplied."),
            ("test", "Test ≤ 3", "Giới hạn còn tối đa 3 nhưng không vượt Count.", "Limit to at most 3 without exceeding Count."),
            ("overwrite", "Overwrite", "Cho phép thay draft trùng tên.", "Allow replacing same-name drafts."),
        ]:
            check = ttk.Checkbutton(checks, text=text, variable=self.vars[key])
            check.pack(side="left", padx=6)
            Tooltip.attach(check, vi, en)
        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=6)
        for text, command, vi, en in [
            ("Scan", self.scan, "Đếm video hỗ trợ.", "Count supported videos."),
            ("Start / Resume", self.start, "Bắt đầu hoặc tiếp tục từ item chưa xử lý.", "Start or resume from the next unprocessed item."),
            ("Pause after current", self.pause, "Dừng trước item tiếp theo.", "Stop before the next item."),
            ("Show Folder", self.show_folder, "Mở draft folder trong Explorer.", "Open the drafts folder in Explorer."),
            ("Open CapCut", self.launch_capcut, "Tìm và chạy CapCut.exe.", "Locate and run CapCut.exe."),
        ]:
            button = ttk.Button(actions, text=text, command=command)
            button.pack(side="left", padx=3)
            Tooltip.attach(button, vi, en)
        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(fill="x")
        self.status = ttk.Label(self, text="Ready")
        self.status.pack(fill="x", pady=3)
        self.log = LogPanel(self, height=12)
        self.log.pack(fill="both", expand=True)

    def _browse(self, key, kind):
        if kind == "dir":
            value = filedialog.askdirectory(initialdir=self.vars[key].get() or str(Path.home()))
        else:
            value = filedialog.askopenfilename(initialdir=str(Path.home()))
        if value:
            self.vars[key].set(value)
            self.creator = None

    def scan(self):
        source = self.vars["source"].get()
        try:
            count = len([
                name for name in os.listdir(source)
                if name.lower().endswith(BatchCreator.VIDEO_EXTENSIONS)
            ])
        except Exception as exc:
            messagebox.showerror("Scan", str(exc))
        else:
            self.status.configure(text=f"Tìm thấy / Found: {count}")

    def _batch_options(self) -> BatchOptions:
        return BatchOptions(
            source_folder=self.vars["source"].get().strip(),
            draft_folder=self.vars["draft_folder"].get().strip(),
            voice_path=self.vars["voice"].get().strip(),
            subtitle_path=self.vars["subtitle"].get().strip(),
            duration=self.vars["duration"].get().strip(),
            width=int(self.vars["width"].get()),
            height=int(self.vars["height"].get()),
            fps=int(self.vars["fps"].get()),
            voice_volume=float(self.vars["volume"].get()),
            mute_source=self.vars["mute_source"].get(),
            add_subtitles=self.vars["add_subtitles"].get(),
            limit=int(self.vars["limit"].get()),
            test_mode=self.vars["test"].get(),
            overwrite=self.vars["overwrite"].get(),
            prefix=self.vars["prefix"].get().strip() or "auto_video",
        )

    def start(self):
        try:
            options = self._batch_options()
            if not os.path.isdir(options.source_folder) or not os.path.isdir(options.draft_folder):
                raise ValueError("Source/Draft folder không tồn tại / folders do not exist")
            if options.voice_path and not os.path.isfile(options.voice_path):
                raise ValueError("Voice file không tồn tại / not found")
            if options.add_subtitles and options.subtitle_path and not os.path.isfile(options.subtitle_path):
                raise ValueError("Subtitle file không tồn tại / not found")
        except Exception as exc:
            messagebox.showerror("Batch", str(exc))
            return
        if options.overwrite and (
            self.creator is None or self.creator.next_index >= len(self.creator.files)
        ):
            if not messagebox.askyesno(
                "Batch overwrite",
                f"Batch có thể thay các draft tên '{options.prefix}_NNN'.\n"
                "Cho phép ghi đè toàn bộ mục trùng tên?\n"
                "Allow replacing all matching draft names?",
            ):
                return
        if self.creator is None or self.creator.next_index >= len(self.creator.files):
            self.creator = BatchCreator(options)
        if not self.runner.submit(self.creator.run, self._event):
            messagebox.showwarning("Batch", "Đang có tác vụ khác / Another job is running")

    def pause(self):
        self.runner.stop_after_current()
        self.log.log("Pause requested; stopping before next item", "warning")

    def _event(self, event: JobEvent):
        if event.kind == "log":
            self.log.log(*event.payload)
        elif event.kind == "progress":
            current, total, message = event.payload
            self.progress.configure(maximum=max(1, total), value=current)
            self.status.configure(text=f"{current}/{total} — {message}")
        elif event.kind == "error":
            exc, trace = event.payload
            self.log.log(trace, "error")
            messagebox.showerror("Batch", str(exc))
        elif event.kind == "done":
            result = event.payload
            self.log.log(str(result), "success")
            self.status.configure(
                text=f"Success {result['success']} | Failed {result['failed']} | "
                     f"Skipped {result['skipped']} | Remaining {result['remaining']}"
            )
            if self.on_created:
                self.on_created()

    def show_folder(self):
        try:
            open_path(self.vars["draft_folder"].get())
        except Exception as exc:
            messagebox.showerror("Show Folder", str(exc))

    def launch_capcut(self):
        try:
            executable = open_capcut()
        except Exception as exc:
            messagebox.showerror("Open CapCut", str(exc))
        else:
            self.log.log(f"Opened {executable}", "success")


class TemplateWorkspace(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=8)
        self.folder_var = tk.StringVar(value=DEFAULT_DRAFTS)
        self.draft_var = tk.StringVar()
        self.session: Optional[TemplateSession] = None
        self.is_copy = False
        self._build()

    def _build(self):
        top = ttk.LabelFrame(self, text="Template Mode", padding=6)
        top.pack(fill="x")
        folder = ttk.Entry(top, textvariable=self.folder_var)
        folder.grid(row=0, column=0, sticky="ew")
        browse = ttk.Button(top, text="Folder…", command=self.browse)
        browse.grid(row=0, column=1, padx=3)
        self.drafts = ttk.Combobox(top, textvariable=self.draft_var, state="readonly")
        self.drafts.grid(row=0, column=2, sticky="ew", padx=3)
        load = ttk.Button(top, text="Load", command=self.load)
        load.grid(row=0, column=3, padx=3)
        duplicate = ttk.Button(top, text="Duplicate first", command=self.duplicate)
        duplicate.grid(row=0, column=4, padx=3)
        top.columnconfigure(0, weight=2)
        top.columnconfigure(2, weight=1)
        Tooltip.attach(folder, "Thư mục chứa template draft.", "Folder containing template drafts.")
        Tooltip.attach(browse, "Chọn thư mục template.", "Choose template folder.")
        Tooltip.attach(self.drafts, "Chọn draft không mã hóa để load.", "Choose an unencrypted draft to load.")
        Tooltip.attach(load, "Nạp draft bằng ScriptFile.load_template.", "Load with ScriptFile.load_template.")
        Tooltip.attach(duplicate, "Nhân bản trước khi chỉnh để bảo vệ template gốc.", "Duplicate before editing to protect the original.")

        pane = ttk.Panedwindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True, pady=6)
        left = ttk.Frame(pane)
        right = ttk.Frame(pane)
        pane.add(left, weight=1)
        pane.add(right, weight=2)
        self.track_tree = ttk.Treeview(
            left,
            columns=("type", "segments"),
            show="tree headings",
            selectmode="browse",
        )
        self.track_tree.heading("#0", text="Track / Index")
        self.track_tree.heading("type", text="Type")
        self.track_tree.heading("segments", text="#")
        self.track_tree.pack(fill="both", expand=True)
        Tooltip.attach(
            self.track_tree,
            "Imported tracks; chỉ video/audio/text hỗ trợ replace.",
            "Imported tracks; only video/audio/text support replacement.",
        )
        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=4)
        for text, command, vi, en in [
            ("Inspect", self.inspect, "Đọc metadata sticker/text effect.", "Read sticker/text-effect metadata."),
            ("Replace name", self.replace_name, "Thay material theo tên trong template.", "Replace a template material by name."),
            ("Replace segment", self.replace_segment, "Thay material của segment đang chọn bằng index.", "Replace a segment material by index."),
            ("Replace text", self.replace_text, "Thay text nhưng giữ style.", "Replace text while retaining style."),
            ("Import track", self.import_track, "Import track từ draft khác.", "Import a track from another draft."),
            ("Save", self.save, "Lưu bản copy hiện tại.", "Save the current duplicated draft."),
        ]:
            button = ttk.Button(buttons, text=text, command=command)
            button.pack(side="left", padx=2, pady=2)
            Tooltip.attach(button, vi, en)
        self.output = tk.Text(right, wrap="word")
        self.output.pack(fill="both", expand=True)
        Tooltip.attach(
            self.output,
            "Kết quả Inspect và trạng thái thao tác; có thể sao chép IDs.",
            "Inspect output and operation status; IDs can be copied.",
        )

    def browse(self):
        folder = filedialog.askdirectory(initialdir=self.folder_var.get() or str(Path.home()))
        if folder:
            self.folder_var.set(folder)
            self.refresh_drafts()

    def refresh_drafts(self):
        try:
            values = DraftService(self.folder_var.get()).list()
        except Exception as exc:
            messagebox.showerror("Template", str(exc))
            return
        self.drafts.configure(values=values)
        if values and self.draft_var.get() not in values:
            self.draft_var.set(values[0])

    def load(self):
        if not self.draft_var.get():
            self.refresh_drafts()
            return
        try:
            self.session = TemplateSession(self.folder_var.get(), self.draft_var.get())
        except Exception as exc:
            messagebox.showerror("Template", str(exc))
            return
        self.is_copy = False
        self.refresh_tracks()

    def duplicate(self):
        if not self.session:
            return
        target = simpledialog.askstring("Duplicate", "Tên bản copy / Copy draft name:")
        if not target:
            return
        overwrite = False
        if os.path.exists(os.path.join(self.folder_var.get(), target)):
            overwrite = messagebox.askyesno("Duplicate", f"Ghi đè '{target}'? / Overwrite?")
            if not overwrite:
                return
        try:
            self.session = self.session.duplicate(target, overwrite)
        except Exception as exc:
            messagebox.showerror("Duplicate", str(exc))
            return
        self.draft_var.set(target)
        self.is_copy = True
        self.refresh_drafts()
        self.refresh_tracks()

    def ensure_copy(self) -> bool:
        if not self.session:
            messagebox.showinfo("Template", "Hãy Load template trước / Load a template first")
            return False
        if self.is_copy:
            return True
        if not messagebox.askyesno(
            "Protect source",
            "Template gốc sẽ không bị sửa. Tạo bản copy trước?\nCreate a copy before editing?",
        ):
            return False
        self.duplicate()
        return self.is_copy

    def refresh_tracks(self):
        self.track_tree.delete(*self.track_tree.get_children())
        if not self.session:
            return
        for index, track in enumerate(self.session.imported_tracks):
            count = len(getattr(track, "segments", []))
            self.track_tree.insert(
                "",
                "end",
                iid=str(index),
                text=getattr(track, "name", "") or f"#{index}",
                values=(track.track_type.name, count),
            )

    def selected_track(self):
        if not self.session:
            return None
        selection = self.track_tree.selection()
        return self.session.imported_tracks[int(selection[0])] if selection else None

    def inspect(self):
        if not self.session:
            return
        try:
            text = self.session.inspect()
        except Exception as exc:
            messagebox.showerror("Inspect", str(exc))
        else:
            self.output.delete("1.0", "end")
            self.output.insert("1.0", text)

    def replace_name(self):
        if not self.ensure_copy():
            return
        data = FormDialog.ask(self, "Replace Material by Name", [
            ("material_name", "Tên material cũ", "", "entry", None, "Tên material trong template.", "Existing template material name."),
            ("path", "File mới / New file", "", "entry", None, "Đường dẫn video/image/audio mới.", "New video/image/audio path."),
            ("kind", "Kind", "video", "choice", ["video", "image", "audio"], "Loại phải khớp material cũ.", "Type must match existing material."),
            ("name", "Tên mới / New name", "", "entry", None, "Tùy chọn material name.", "Optional material name."),
            ("replace_crop", "Replace crop", True, "bool", None, "Video: thay crop theo material mới.", "Video: replace crop with the new material crop."),
        ])
        if not data:
            return
        try:
            self.session.replace_by_name(
                data["material_name"], data["path"], data["kind"], data["name"], data["replace_crop"]
            )
        except Exception as exc:
            messagebox.showerror("Replace", str(exc))

    def replace_segment(self):
        selection = self.track_tree.selection()
        if not selection or not self.ensure_copy():
            return
        track = self.session.imported_tracks[int(selection[0])]
        data = FormDialog.ask(self, "Replace Material by Segment", [
            ("index", "Segment index", "0", "entry", None, "Index từ 0.", "Zero-based index."),
            ("path", "File mới / New file", "", "entry", None, "Material mới cùng loại.", "New material of the same type."),
            ("kind", "Kind", track.track_type.name, "choice", ["video", "image", "audio"], "Loại material.", "Material type."),
            ("source_start", "Source start", "0s", "entry", None, "Điểm bắt đầu nguồn.", "Source start."),
            ("source_duration", "Source duration", "", "entry", None, "Trống dùng toàn bộ source.", "Blank uses the entire source."),
            ("shrink", "Shrink mode", "cut_tail", "choice", ["cut_head", "cut_tail", "cut_tail_align", "shrink"], "Cách xử lý khi material mới ngắn hơn.", "How to handle a shorter replacement material."),
            ("extend", "Extend modes", "cut_material_tail", "entry", None, "Danh sách ExtendMode theo thứ tự, dấu phẩy.", "Comma-separated ExtendMode fallback order."),
        ])
        if not data:
            return
        try:
            self.session.replace_by_segment(
                track,
                int(data["index"]),
                data["path"],
                data["kind"],
                data["source_start"],
                data["source_duration"],
                data["shrink"],
                [part.strip() for part in data["extend"].split(",") if part.strip()],
            )
        except Exception as exc:
            messagebox.showerror("Replace Segment", str(exc))

    def replace_text(self):
        selection = self.track_tree.selection()
        if not selection or not self.ensure_copy():
            return
        track = self.session.imported_tracks[int(selection[0])]
        data = FormDialog.ask(self, "Replace Text", [
            ("index", "Segment index", "0", "entry", None, "Index từ 0.", "Zero-based index."),
            ("text", "Text", "", "text", None, "Template nhiều vùng: ngăn bằng dòng ---.", "For multi-part templates, separate values with a line containing ---."),
            ("recalc", "Recalculate style ranges", True, "bool", None, "Giữ tỷ lệ phân bố style.", "Preserve proportional style ranges."),
        ])
        if not data:
            return
        try:
            self.session.replace_text(track, int(data["index"]), data["text"], data["recalc"])
        except Exception as exc:
            messagebox.showerror("Replace Text", str(exc))

    def import_track(self):
        if not self.ensure_copy():
            return
        drafts = DraftService(self.folder_var.get()).list()
        data = FormDialog.ask(self, "Import Track", [
            ("source", "Source draft", drafts[0] if drafts else "", "choice", drafts, "Draft chứa track nguồn.", "Draft containing the source track."),
            ("track_index", "Track index", "0", "entry", None, "Index imported track.", "Imported track index."),
            ("offset", "Offset", "0s", "entry", None, "Vị trí chèn trên timeline.", "Timeline insertion offset."),
            ("new_name", "New name", "", "entry", None, "Tên track mới tùy chọn.", "Optional new track name."),
            ("relative_index", "Relative layer", "0", "entry", None, "Layer tương đối.", "Relative layer."),
        ])
        if not data:
            return
        try:
            source = TemplateSession(self.folder_var.get(), data["source"])
            track = source.imported_tracks[int(data["track_index"])]
            self.session.import_track(
                source, track, data["offset"], data["new_name"], int(data["relative_index"])
            )
        except Exception as exc:
            messagebox.showerror("Import Track", str(exc))
        else:
            self.refresh_tracks()

    def save(self):
        if not self.session or not self.is_copy:
            messagebox.showinfo("Template", "Chỉ lưu bản copy / Save a duplicated draft only")
            return
        if not messagebox.askyesno("Save Template", f"Lưu '{self.draft_var.get()}'? / Save changes?"):
            return
        try:
            self.session.save()
        except Exception as exc:
            messagebox.showerror("Save", str(exc))
        else:
            messagebox.showinfo("Save", "Đã lưu / Saved")


class ExportWorkspace(ttk.Frame):
    def __init__(self, master, runner: JobRunner):
        super().__init__(master, padding=8)
        self.runner = runner
        self.folder_var = tk.StringVar(value=DEFAULT_DRAFTS)
        self.output_var = tk.StringVar()
        self.resolution_var = tk.StringVar()
        self.fps_var = tk.StringVar()
        self.timeout_var = tk.DoubleVar(value=1200)
        self._build()

    def _build(self):
        warning = ttk.Label(
            self,
            text="⚠ Windows only — CapCut/Jianying 6 trở xuống / version 6 or below",
            foreground="#b3261e",
        )
        warning.pack(fill="x", pady=(0, 6))
        top = ttk.LabelFrame(self, text="Export Queue", padding=6)
        top.pack(fill="x")
        for row, (label, variable, command, vi, en) in enumerate([
            ("Draft folder", self.folder_var, self._browse_drafts, "Thư mục chứa draft cần export.", "Folder containing drafts to export."),
            ("Output folder", self.output_var, self._browse_output, "Thư mục nhận MP4; trống dùng mặc định CapCut.", "MP4 destination folder; blank uses CapCut default."),
        ]):
            ttk.Label(top, text=label).grid(row=row, column=0, sticky="w")
            entry = ttk.Entry(top, textvariable=variable)
            entry.grid(row=row, column=1, sticky="ew", padx=4, pady=3)
            button = ttk.Button(top, text="…", width=3, command=command)
            button.grid(row=row, column=2)
            Tooltip.attach(entry, vi, en)
            Tooltip.attach(button, f"Chọn {label}.", f"Choose {label}.")
        top.columnconfigure(1, weight=1)
        settings = ttk.Frame(top)
        settings.grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)
        for index, (label, variable, values, vi, en) in enumerate([
            ("Resolution", self.resolution_var, ["", "RES_480P", "RES_720P", "RES_1080P", "RES_2K", "RES_4K", "RES_8K"], "Trống giữ thiết lập CapCut.", "Blank keeps the CapCut setting."),
            ("FPS", self.fps_var, ["", "FR_24", "FR_25", "FR_30", "FR_50", "FR_60"], "Trống giữ thiết lập CapCut.", "Blank keeps the CapCut setting."),
        ]):
            ttk.Label(settings, text=label).grid(row=0, column=index * 2)
            combo = ttk.Combobox(settings, textvariable=variable, values=values, state="readonly", width=14)
            combo.grid(row=0, column=index * 2 + 1, padx=3)
            Tooltip.attach(combo, vi, en)
        ttk.Label(settings, text="Timeout (s)").grid(row=0, column=4)
        timeout = ttk.Entry(settings, textvariable=self.timeout_var, width=10)
        timeout.grid(row=0, column=5)
        Tooltip.attach(timeout, "Thời gian chờ tối đa cho mỗi draft, mặc định 1200 giây.", "Maximum wait per draft; default 1200 seconds.")
        self.tree = ttk.Treeview(self, show="tree", selectmode="extended")
        self.tree.heading("#0", text="Chọn draft để export / Select drafts")
        self.tree.pack(fill="both", expand=True, pady=6)
        Tooltip.attach(self.tree, "Ctrl/Shift để chọn nhiều draft.", "Use Ctrl/Shift to select multiple drafts.")
        actions = ttk.Frame(self)
        actions.pack(fill="x")
        for text, command, vi, en in [
            ("Refresh", self.refresh, "Đọc lại danh sách draft.", "Reload drafts."),
            ("Select all", self.select_all, "Chọn toàn bộ draft.", "Select every draft."),
            ("Start Export", self.start, "Chạy automation tuần tự.", "Run export automation sequentially."),
            ("Stop after current", self.stop, "Không bắt đầu draft tiếp theo.", "Do not start the next draft."),
        ]:
            button = ttk.Button(actions, text=text, command=command)
            button.pack(side="left", padx=3)
            Tooltip.attach(button, vi, en)
        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(fill="x", pady=5)
        self.log = LogPanel(self, height=9)
        self.log.pack(fill="both", expand=True)

    def _browse_drafts(self):
        value = filedialog.askdirectory(initialdir=self.folder_var.get() or str(Path.home()))
        if value:
            self.folder_var.set(value)
            self.refresh()

    def _browse_output(self):
        value = filedialog.askdirectory(initialdir=self.output_var.get() or str(Path.home()))
        if value:
            self.output_var.set(value)

    def refresh(self):
        try:
            values = DraftService(self.folder_var.get()).list()
        except Exception as exc:
            messagebox.showerror("Export", str(exc))
            return
        self.tree.delete(*self.tree.get_children())
        for value in values:
            self.tree.insert("", "end", iid=value, text=value)

    def select_all(self):
        self.tree.selection_set(self.tree.get_children())

    def start(self):
        drafts = list(self.tree.selection())
        if not drafts:
            messagebox.showinfo("Export", "Hãy chọn draft / Select at least one draft")
            return
        if sys.platform != "win32":
            messagebox.showerror("Export", "Automation chỉ chạy trên Windows / Windows only")
            return
        queue = ExportQueue(
            drafts,
            self.output_var.get().strip(),
            self.resolution_var.get(),
            self.fps_var.get(),
            float(self.timeout_var.get()),
        )
        if not self.runner.submit(queue.run, self._event):
            messagebox.showwarning("Export", "Đang có tác vụ khác / Another job is running")

    def stop(self):
        self.runner.stop_after_current()
        self.log.log("Stop requested; current export continues", "warning")

    def _event(self, event: JobEvent):
        if event.kind == "log":
            self.log.log(*event.payload)
        elif event.kind == "progress":
            current, total, draft = event.payload
            self.progress.configure(maximum=max(1, total), value=current)
            self.log.log(f"{current}/{total}: {draft}", "processing")
        elif event.kind == "error":
            exc, trace = event.payload
            self.log.log(trace, "error")
            messagebox.showerror("Export", str(exc))
        elif event.kind == "done":
            self.log.log(str(event.payload), "success")
            messagebox.showinfo("Export", str(event.payload))
