"""Main visual editor workspace."""

from __future__ import annotations

import copy
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Dict

from .adapter import build_script, materialize_project, metadata_catalog
from .jobs import JobEvent, JobRunner
from .models import (
    KeyframeModel,
    MaterialModel,
    ProjectHistory,
    ProjectModel,
    SegmentModel,
)
from .services import open_path
from .tooltip import Tooltip
from .widgets import (
    FormDialog,
    ListEditor,
    LogPanel,
    ScrollableFrame,
    TimelineCanvas,
    clear_children,
    labelled_entry,
)


VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".gif")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
AUDIO_EXTENSIONS = (".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg")


class EditorWorkspace(ttk.Frame):
    def __init__(self, master, runner: JobRunner, on_draft_created=None):
        super().__init__(master)
        self.runner = runner
        self.on_draft_created = on_draft_created
        self.history = ProjectHistory(self._fresh_project())
        self.selected_kind = "project"
        self.selected_id = ""
        self.catalog: Dict[str, list[str]] = {}
        self._build_ui()
        self.refresh_all()

    @property
    def project(self) -> ProjectModel:
        return self.history.current

    def _fresh_project(self) -> ProjectModel:
        project = ProjectModel()
        project.add_track("video", "video")
        project.add_track("audio", "audio")
        project.add_track("text", "text")
        return project

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self, padding=(8, 6))
        toolbar.pack(fill="x")
        buttons = [
            ("Mới / New", self.new_project, "Tạo project trống mới.", "Create a new empty project."),
            ("Đặt lại / Reset", self.reset_project, "Khôi phục project mặc định.", "Reset to the default project."),
            ("Kiểm tra / Validate", self.validate_project, "Dựng thử bằng core nhưng chưa ghi draft.", "Build in memory with core without writing a draft."),
            ("Hoàn tác / Undo", self.undo, "Hoàn tác thay đổi gần nhất.", "Undo the latest change."),
            ("Làm lại / Redo", self.redo, "Khôi phục thay đổi vừa hoàn tác.", "Redo the latest undone change."),
            ("Tạo Draft / Create", self.create_draft, "Tạo và lưu CapCut draft.", "Create and save the CapCut draft."),
        ]
        for text, command, vi, en in buttons:
            button = ttk.Button(toolbar, text=text, command=command)
            button.pack(side="left", padx=3)
            Tooltip.attach(button, vi, en)

        project_bar = ttk.LabelFrame(self, text="Project / Draft", padding=5)
        project_bar.pack(fill="x", padx=8)
        self.folder_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.width_var = tk.IntVar()
        self.height_var = tk.IntVar()
        self.fps_var = tk.IntVar()
        self.overwrite_var = tk.BooleanVar()
        self._bar_field(project_bar, "Thư mục / Folder", self.folder_var, 0, 34)
        browse = ttk.Button(project_bar, text="…", width=3, command=self.choose_draft_folder)
        browse.grid(row=0, column=2, padx=2)
        Tooltip.attach(browse, "Chọn thư mục draft thực tế của CapCut.", "Choose the actual CapCut drafts folder.")
        self._bar_field(project_bar, "Tên / Name", self.name_var, 0, 14, column=3)
        self._bar_field(project_bar, "W", self.width_var, 0, 6, column=5)
        self._bar_field(project_bar, "H", self.height_var, 0, 6, column=7)
        self._bar_field(project_bar, "FPS", self.fps_var, 0, 5, column=9)
        overwrite = ttk.Checkbutton(project_bar, text="Ghi đè / Overwrite", variable=self.overwrite_var)
        overwrite.grid(row=0, column=11, padx=5)
        Tooltip.attach(
            overwrite,
            "Cho phép thay draft trùng tên; vẫn yêu cầu xác nhận trước khi ghi.",
            "Allow replacing an existing draft; confirmation is still required.",
        )
        apply_project = ttk.Button(project_bar, text="Áp dụng / Apply", command=self.apply_project_bar)
        apply_project.grid(row=0, column=12, padx=4)
        Tooltip.attach(apply_project, "Ghi các trường trên vào model.", "Apply the fields above to the model.")
        project_bar.columnconfigure(1, weight=1)

        pane = ttk.Panedwindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=6)
        self.left = ttk.Frame(pane, width=245)
        self.center = ttk.Frame(pane)
        self.right = ttk.Frame(pane, width=360)
        pane.add(self.left, weight=0)
        pane.add(self.center, weight=3)
        pane.add(self.right, weight=1)
        self._build_library()
        self._build_center()
        self._build_inspector()
        self.log = LogPanel(self, height=6)
        self.log.pack(fill="x", padx=8, pady=(0, 8))

    def _bar_field(self, parent, label, variable, row, width, column=0):
        ttk.Label(parent, text=label).grid(row=row, column=column, padx=(3, 1))
        entry = ttk.Entry(parent, textvariable=variable, width=width)
        entry.grid(row=row, column=column + 1, sticky="ew", padx=2)
        Tooltip.attach(
            entry,
            f"Thiết lập {label}; nhấn Apply để cập nhật.",
            f"Set {label}; press Apply to update.",
        )

    def _build_library(self) -> None:
        material_frame = ttk.LabelFrame(self.left, text="Material Library", padding=4)
        material_frame.pack(fill="both", expand=True, pady=(0, 5))
        self.material_tree = ttk.Treeview(
            material_frame,
            columns=("kind",),
            show="tree headings",
            height=8,
            selectmode="browse",
        )
        self.material_tree.heading("#0", text="Tên / Name")
        self.material_tree.heading("kind", text="Loại / Type")
        self.material_tree.column("#0", width=145)
        self.material_tree.column("kind", width=70)
        self.material_tree.pack(fill="both", expand=True)
        Tooltip.attach(
            self.material_tree,
            "Thư viện material của project; video/audio segment tham chiếu material tại đây.",
            "Project material library; video/audio segments reference these entries.",
        )
        row = ttk.Frame(material_frame)
        row.pack(fill="x", pady=3)
        for text, command, vi, en in [
            ("+ Media", self.add_media, "Thêm video, ảnh hoặc audio cục bộ.", "Add local video, image or audio."),
            ("+ Sticker", self.add_sticker_material, "Lưu resource ID sticker để tái sử dụng.", "Store a sticker resource ID for reuse."),
            ("Preview", self.preview_material, "Mở file bằng player mặc định.", "Open the file with the default player."),
            ("−", self.remove_material, "Xóa material chưa được dùng.", "Remove an unused material."),
        ]:
            button = ttk.Button(row, text=text, command=command)
            button.pack(side="left", padx=1)
            Tooltip.attach(button, vi, en)

        track_frame = ttk.LabelFrame(self.left, text="Tracks / Rãnh", padding=4)
        track_frame.pack(fill="both", expand=True)
        self.track_tree = ttk.Treeview(
            track_frame,
            columns=("kind", "count"),
            show="tree headings",
            height=8,
            selectmode="browse",
        )
        self.track_tree.heading("#0", text="Tên")
        self.track_tree.heading("kind", text="Loại")
        self.track_tree.heading("count", text="#")
        self.track_tree.column("#0", width=115)
        self.track_tree.column("kind", width=70)
        self.track_tree.column("count", width=30)
        self.track_tree.pack(fill="both", expand=True)
        self.track_tree.bind("<<TreeviewSelect>>", self._track_selected)
        Tooltip.attach(
            self.track_tree,
            "Chọn track để xem thuộc tính hoặc thêm segment đúng loại.",
            "Select a track to inspect it or add a compatible segment.",
        )
        row = ttk.Frame(track_frame)
        row.pack(fill="x", pady=3)
        for text, command, vi, en in [
            ("+ Track", self.add_track, "Thêm video/audio/text/sticker/effect/filter track.", "Add a video/audio/text/sticker/effect/filter track."),
            ("+ Segment", self.add_segment, "Thêm segment vào track đang chọn.", "Add a segment to the selected track."),
            ("Xóa", self.delete_selected, "Xóa track hoặc segment đang chọn.", "Delete the selected track or segment."),
        ]:
            button = ttk.Button(row, text=text, command=command)
            button.pack(side="left", padx=1)
            Tooltip.attach(button, vi, en)

    def _build_center(self) -> None:
        tools = ttk.Frame(self.center)
        tools.pack(fill="x")
        ttk.Label(tools, text="Timeline").pack(side="left", padx=4)
        self.zoom_var = tk.DoubleVar(value=60)
        zoom = ttk.Scale(
            tools,
            from_=20,
            to=300,
            variable=self.zoom_var,
            command=lambda value: self.timeline.set_zoom(float(value)),
        )
        zoom.pack(side="left", fill="x", expand=True, padx=5)
        Tooltip.attach(
            zoom,
            "Zoom timeline từ 20–300 pixel/giây.",
            "Timeline zoom from 20–300 pixels per second.",
        )
        snap = ttk.Checkbutton(tools, text="Snap 0.1s", variable=tk.BooleanVar(value=False))
        snap.pack(side="left", padx=4)
        Tooltip.attach(snap, "Bật bắt dính theo bước 0.1 giây.", "Snap move/resize operations to 0.1 seconds.")
        self.timeline = TimelineCanvas(
            self.center,
            lambda: self.project,
            self.history,
            self.select_entity,
            self._timeline_changed,
        )
        snap.configure(variable=self.timeline.snap)
        self.timeline.pack(fill="both", expand=True)

    def _build_inspector(self) -> None:
        title = ttk.Frame(self.right)
        title.pack(fill="x")
        ttk.Label(title, text="Inspector / Thuộc tính", font=("Segoe UI", 10, "bold")).pack(side="left", padx=5, pady=4)
        self.inspector = ScrollableFrame(self.right)
        self.inspector.pack(fill="both", expand=True)

    def choose_draft_folder(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.folder_var.get() or str(Path.home()))
        if folder:
            self.folder_var.set(folder)

    def apply_project_bar(self) -> None:
        try:
            width, height, fps = int(self.width_var.get()), int(self.height_var.get()), int(self.fps_var.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("pyCapCut", "Canvas/FPS phải là số nguyên / must be integers")
            return
        self.history.checkpoint()
        project = self.project
        project.draft_folder = self.folder_var.get().strip()
        project.draft_name = self.name_var.get().strip()
        project.width, project.height, project.fps = width, height, fps
        project.overwrite = self.overwrite_var.get()
        self.refresh_all()

    def new_project(self) -> None:
        if not messagebox.askyesno(
            "pyCapCut",
            "Bỏ phiên chưa tạo draft và tạo project mới?\nDiscard the current in-memory session?",
        ):
            return
        self.history.reset(self._fresh_project())
        self.selected_kind, self.selected_id = "project", ""
        self.refresh_all()

    def reset_project(self) -> None:
        self.new_project()

    def undo(self) -> None:
        self.history.undo()
        self.refresh_all()

    def redo(self) -> None:
        self.history.redo()
        self.refresh_all()

    def validate_project(self) -> None:
        self.apply_project_bar()
        errors = self.project.validate()
        if errors:
            self.log.log("\n".join(errors), "error")
            messagebox.showerror("Validation", "\n".join(errors[:10]))
            return

        def work(context):
            context.log("Đang dựng thử bằng pycapcut / Validating with pycapcut", "processing")
            materialize_project(snapshot)
            return "Project hợp lệ / Project is valid"

        snapshot = copy.deepcopy(self.project)
        self._submit(work, success_title="Validation")

    def create_draft(self) -> None:
        self.apply_project_bar()
        errors = self.project.validate()
        if errors:
            messagebox.showerror("Validation", "\n".join(errors[:10]))
            return
        target = Path(self.project.draft_folder) / self.project.draft_name
        if target.exists():
            if not self.project.overwrite:
                messagebox.showerror(
                    "pyCapCut",
                    f"Draft '{self.project.draft_name}' đã tồn tại; bật Overwrite nếu muốn thay.",
                )
                return
            if not messagebox.askyesno(
                "Xác nhận ghi đè / Confirm overwrite",
                f"Thay toàn bộ draft '{self.project.draft_name}'?\nReplace this draft completely?",
            ):
                return

        def work(context):
            context.log(f"Creating {snapshot.draft_name}", "processing")
            return build_script(snapshot)

        snapshot = copy.deepcopy(self.project)
        self._submit(work, success_title="Create Draft", created=True)

    def _submit(self, work, success_title: str, created: bool = False) -> None:
        if not self.runner.submit(
            work,
            lambda event: self._job_event(event, success_title, created),
        ):
            messagebox.showwarning("pyCapCut", "Đang có tác vụ khác / Another job is running")

    def _job_event(self, event: JobEvent, title: str, created: bool) -> None:
        if event.kind == "log":
            self.log.log(*event.payload)
        elif event.kind == "error":
            exc, trace = event.payload
            self.log.log(trace, "error")
            messagebox.showerror(title, str(exc))
        elif event.kind == "done":
            self.log.log(str(event.payload), "success")
            messagebox.showinfo(title, str(event.payload))
            if created and self.on_draft_created:
                self.on_draft_created()

    def add_media(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Thêm media / Add media",
            filetypes=[
                ("Media", "*.mp4 *.mov *.avi *.mkv *.webm *.gif *.jpg *.jpeg *.png *.bmp *.webp *.mp3 *.wav *.aac *.m4a *.flac *.ogg"),
                ("All files", "*.*"),
            ],
        )
        if not paths:
            return
        self.history.checkpoint()
        for path in paths:
            extension = Path(path).suffix.lower()
            kind = "audio" if extension in AUDIO_EXTENSIONS else "image" if extension in IMAGE_EXTENSIONS else "video"
            self.project.add_material(MaterialModel(kind=kind, path=path, name=os.path.basename(path)))
        self.refresh_all()

    def add_sticker_material(self) -> None:
        resource_id = simpledialog.askstring("Sticker", "Resource ID:")
        if not resource_id:
            return
        name = simpledialog.askstring("Sticker", "Tên / Name:") or resource_id
        self.history.checkpoint()
        self.project.add_material(MaterialModel(kind="sticker", name=name, resource_id=resource_id))
        self.refresh_all()

    def preview_material(self) -> None:
        selection = self.material_tree.selection()
        if not selection:
            return
        material = next(item for item in self.project.materials if item.id == selection[0])
        if material.path:
            try:
                open_path(material.path)
            except Exception as exc:
                messagebox.showerror("Preview", str(exc))
        else:
            messagebox.showinfo("Sticker", f"Resource ID: {material.resource_id}")

    def remove_material(self) -> None:
        selection = self.material_tree.selection()
        if not selection:
            return
        self.history.checkpoint()
        try:
            self.project.remove_material(selection[0])
        except ValueError as exc:
            self.history.undo()
            messagebox.showerror("pyCapCut", str(exc))
            return
        self.refresh_all()

    def add_track(self) -> None:
        schema = [
            ("kind", "Loại / Type", "video", "choice", ["video", "audio", "text", "sticker", "effect", "filter"], "Loại track phải khớp segment.", "Track type must match its segments."),
            ("name", "Tên / Name", "", "entry", None, "Tên duy nhất trong project.", "Unique name within the project."),
            ("mute", "Tắt tiếng / Mute", False, "bool", None, "Áp dụng attribute mute của track.", "Apply the track mute attribute."),
            ("relative_index", "Layer tương đối", "0", "entry", None, "Số lớn hơn gần foreground hơn.", "Higher values render closer to foreground."),
            ("absolute_index", "Layer tuyệt đối", "", "entry", None, "Để trống để dùng relative index.", "Leave blank to use relative index."),
        ]
        data = FormDialog.ask(self, "Thêm Track / Add Track", schema)
        if not data:
            return
        self.history.checkpoint()
        track = self.project.add_track(data["kind"], data["name"] or None)
        track.mute = data["mute"]
        track.relative_index = int(data["relative_index"] or 0)
        track.absolute_index = int(data["absolute_index"]) if data["absolute_index"] else None
        self.select_entity("track", track.id)
        self.refresh_all()

    def add_segment(self) -> None:
        track = self._selected_track()
        if not track:
            messagebox.showinfo("pyCapCut", "Hãy chọn track / Select a track")
            return
        kind = track.kind
        if kind in ("video", "audio"):
            accepted = {"video", "image"} if kind == "video" else {"audio"}
            materials = [item for item in self.project.materials if item.kind in accepted]
            if not materials:
                messagebox.showinfo("pyCapCut", "Hãy thêm material phù hợp trước / Add a compatible material first")
                return
            choices = [f"{item.name} [{item.id[:8]}]" for item in materials]
            data = FormDialog.ask(
                self,
                "Thêm Segment / Add Segment",
                [
                    ("material", "Material", choices[0], "choice", choices, "Chọn material nguồn.", "Choose source material."),
                    ("start", "Bắt đầu / Start", "0s", "entry", None, "Vị trí trên timeline.", "Position on the timeline."),
                    ("duration", "Thời lượng / Duration", "5s", "entry", None, "Thời lượng đích, không phải end.", "Target duration, not end time."),
                ],
            )
            if not data:
                return
            material = materials[choices.index(data["material"])]
            segment = SegmentModel(
                kind=kind,
                start=data["start"],
                duration=data["duration"],
                material_id=material.id,
                name=material.name,
                options={"volume": 1.0, "clip": {}, "crop": {}},
            )
        elif kind == "text":
            choice = messagebox.askyesnocancel(
                "Text Track",
                "Có = thêm Text thường\nKhông = nhập Subtitle SRT\n"
                "Yes = regular text, No = import SRT subtitle",
            )
            if choice is None:
                return
            if choice:
                segment = SegmentModel(
                    kind="text",
                    name="Text",
                    options={"text": "Text", "style": {}, "clip": {}},
                )
            else:
                srt_path = filedialog.askopenfilename(
                    title="Subtitle SRT",
                    filetypes=[("SubRip", "*.srt"), ("All files", "*.*")],
                )
                if not srt_path:
                    return
                offset = simpledialog.askstring(
                    "Subtitle",
                    "Time offset, ví dụ 0s / e.g. 0s:",
                    initialvalue="0s",
                )
                if offset is None:
                    return
                segment = SegmentModel(
                    kind="subtitle",
                    name=os.path.basename(srt_path),
                    options={
                        "srt_path": srt_path,
                        "time_offset": offset,
                        "style": {
                            "size": 5,
                            "align": 1,
                            "auto_wrapping": True,
                        },
                        "clip": {"transform_y": -0.8},
                    },
                )
        elif kind == "sticker":
            stickers = [item for item in self.project.materials if item.kind == "sticker"]
            resource = stickers[0].resource_id if stickers else ""
            segment = SegmentModel(kind="sticker", name="Sticker", options={"resource_id": resource, "clip": {}})
        elif kind == "effect":
            segment = SegmentModel(kind="effect", name="Effect", options={"family": "scene", "name": ""})
        elif kind == "filter":
            segment = SegmentModel(kind="filter", name="Filter", options={"name": "", "intensity": 100})
        else:
            return
        self.history.checkpoint()
        track.segments.append(segment)
        self.selected_kind, self.selected_id = "segment", segment.id
        self.refresh_all()

    def delete_selected(self) -> None:
        if self.selected_kind == "track" and self.selected_id:
            track = self.project.find_track(self.selected_id)
            if not messagebox.askyesno("pyCapCut", f"Xóa track '{track.name}' và mọi segment?"):
                return
            self.history.checkpoint()
            self.project.remove_track(track.id)
        elif self.selected_kind == "segment" and self.selected_id:
            track, segment = self.project.find_segment(self.selected_id)
            self.history.checkpoint()
            track.segments = [item for item in track.segments if item.id != segment.id]
        else:
            return
        self.selected_kind, self.selected_id = "project", ""
        self.refresh_all()

    def _track_selected(self, _event=None) -> None:
        selection = self.track_tree.selection()
        if selection:
            self.select_entity("track", selection[0])

    def _selected_track(self):
        if self.selected_kind == "track" and self.selected_id:
            return self.project.find_track(self.selected_id)
        if self.selected_kind == "segment" and self.selected_id:
            return self.project.find_segment(self.selected_id)[0]
        selection = self.track_tree.selection()
        return self.project.find_track(selection[0]) if selection else None

    def select_entity(self, kind: str, entity_id: str) -> None:
        self.selected_kind, self.selected_id = kind, entity_id
        self.refresh_inspector()

    def refresh_all(self) -> None:
        project = self.project
        self.folder_var.set(project.draft_folder)
        self.name_var.set(project.draft_name)
        self.width_var.set(project.width)
        self.height_var.set(project.height)
        self.fps_var.set(project.fps)
        self.overwrite_var.set(project.overwrite)
        self.material_tree.delete(*self.material_tree.get_children())
        for material in project.materials:
            self.material_tree.insert("", "end", iid=material.id, text=material.name, values=(material.kind,))
        self.track_tree.delete(*self.track_tree.get_children())
        for track in project.tracks:
            self.track_tree.insert("", "end", iid=track.id, text=track.name, values=(track.kind, len(track.segments)))
        self.timeline.history = self.history
        self.timeline.redraw()
        self.refresh_inspector()

    def refresh_inspector(self) -> None:
        body = self.inspector.body
        clear_children(body)
        if self.selected_kind == "track" and self.selected_id:
            self._track_inspector(body, self.project.find_track(self.selected_id))
        elif self.selected_kind == "segment" and self.selected_id:
            track, segment = self.project.find_segment(self.selected_id)
            self._segment_inspector(body, track, segment)
        else:
            ttk.Label(
                body,
                text="Chọn track hoặc segment trên timeline.\nSelect a track or segment on the timeline.",
                justify="center",
            ).pack(fill="x", padx=10, pady=20)

    def _track_inspector(self, body, track) -> None:
        vars_ = {
            "name": tk.StringVar(value=track.name),
            "mute": tk.BooleanVar(value=track.mute),
            "relative": tk.StringVar(value=track.relative_index),
            "absolute": tk.StringVar(value="" if track.absolute_index is None else track.absolute_index),
        }
        frame = ttk.LabelFrame(body, text=f"Track [{track.kind}]", padding=6)
        frame.pack(fill="x", padx=4, pady=4)
        labelled_entry(frame, 0, "Tên / Name", vars_["name"], "Tên duy nhất.", "Unique track name.")
        mute = ttk.Checkbutton(frame, text="Tắt tiếng / Mute", variable=vars_["mute"])
        mute.grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=3)
        Tooltip.attach(mute, "Đặt attribute mute của track.", "Set the track mute attribute.")
        labelled_entry(frame, 2, "Layer tương đối", vars_["relative"], "Lớp so với track cùng loại.", "Layer relative to tracks of the same type.")
        labelled_entry(frame, 3, "Layer tuyệt đối", vars_["absolute"], "Để trống để dùng relative.", "Leave blank to use relative layering.")

        def apply():
            self.history.checkpoint()
            track.name = vars_["name"].get().strip()
            track.mute = vars_["mute"].get()
            track.relative_index = int(vars_["relative"].get() or 0)
            track.absolute_index = int(vars_["absolute"].get()) if vars_["absolute"].get() else None
            self.refresh_all()

        button = ttk.Button(frame, text="Áp dụng / Apply", command=apply)
        button.grid(row=4, column=0, columnspan=2, sticky="ew", padx=4, pady=6)
        Tooltip.attach(button, "Áp dụng thuộc tính track.", "Apply track properties.")

    def _segment_inspector(self, body, track, segment: SegmentModel) -> None:
        ttk.Label(body, text=f"{segment.kind.upper()} — {track.name}", font=("Segoe UI", 10, "bold")).pack(fill="x", padx=6, pady=4)
        notebook = ttk.Notebook(body)
        notebook.pack(fill="both", expand=True, padx=2, pady=2)
        common = ttk.Frame(notebook, padding=5)
        notebook.add(common, text="Cơ bản / Basic")
        Tooltip.attach(notebook, "Các nhóm thuộc tính của segment.", "Segment property groups.")
        bindings: Dict[str, Any] = {}
        self._field(common, bindings, "name", "Tên / Name", segment.name, "Tên hiển thị trong GUI.", "GUI display name.")
        self._field(common, bindings, "start", "Bắt đầu / Start", segment.start, "Vị trí trên timeline; 1.5 hoặc 1.5s đều là 1.5 giây.", "Timeline position; 1.5 and 1.5s both mean 1.5 seconds.")
        self._field(common, bindings, "duration", "Thời lượng / Duration", segment.duration, "Không phải end; 30 hoặc 30s đều là 30 giây.", "Duration, not end time; 30 and 30s both mean 30 seconds.")
        if segment.kind in ("video", "audio"):
            self._field(common, bindings, "source_start", "Nguồn từ / Source start", segment.options.get("source_start", ""), "Để trống để bắt đầu từ 0.", "Leave blank to start at zero.")
            self._field(common, bindings, "source_duration", "Độ dài nguồn", segment.options.get("source_duration", ""), "Để trống để core tự tính.", "Leave blank for core calculation.")
            self._field(common, bindings, "speed", "Tốc độ / Speed", segment.options.get("speed", ""), "Tốc độ phát; trống dùng 1.0.", "Playback speed; blank means 1.0.")
            self._field(common, bindings, "volume", "Âm lượng / Volume", segment.options.get("volume", 1.0), "Hệ số âm lượng; 1.0 = 100%.", "Volume multiplier; 1.0 = 100%.")

        if segment.kind in ("video", "text", "sticker"):
            transform = ttk.Frame(notebook, padding=5)
            notebook.add(transform, text="Transform")
            for key, label, default, vi, en in [
                ("clip.alpha", "Opacity", 1.0, "Độ trong suốt 0–1.", "Opacity from 0 to 1."),
                ("clip.rotation", "Rotation", 0.0, "Góc xoay theo độ.", "Clockwise degrees."),
                ("clip.scale_x", "Scale X", 1.0, "Tỷ lệ ngang.", "Horizontal scale."),
                ("clip.scale_y", "Scale Y", 1.0, "Tỷ lệ dọc.", "Vertical scale."),
                ("clip.transform_x", "Position X", 0.0, "Đơn vị nửa chiều rộng canvas.", "Units of half canvas width."),
                ("clip.transform_y", "Position Y", 0.0, "Đơn vị nửa chiều cao canvas.", "Units of half canvas height."),
                ("clip.flip_horizontal", "Flip H", False, "Lật ngang.", "Flip horizontally."),
                ("clip.flip_vertical", "Flip V", False, "Lật dọc.", "Flip vertically."),
            ]:
                self._field(transform, bindings, key, label, _get_path(segment.options, key, default), vi, en, bool_field=isinstance(default, bool))

        if segment.kind == "video":
            self._video_tabs(notebook, segment, bindings)
        elif segment.kind == "audio":
            self._audio_tabs(notebook, segment, bindings)
        elif segment.kind == "text":
            self._text_tabs(notebook, segment, bindings)
        elif segment.kind == "sticker":
            sticker = ttk.Frame(notebook, padding=5)
            notebook.add(sticker, text="Sticker")
            self._field(sticker, bindings, "resource_id", "Resource ID", segment.options.get("resource_id", ""), "ID lấy từ Inspect Material.", "ID obtained from Inspect Material.")
        elif segment.kind == "effect":
            fx = ttk.Frame(notebook, padding=5)
            notebook.add(fx, text="Effect")
            self._choice(fx, bindings, "family", "Family", segment.options.get("family", "scene"), ["scene", "character"], "Loại effect video.", "Video effect family.")
            names = self._catalog("video_scene_effect") + self._catalog("video_character_effect")
            self._choice(fx, bindings, "name", "Effect", segment.options.get("name", ""), names, "Tên enum effect.", "Effect enum name.")
            self._field(fx, bindings, "params", "Params", _csv(segment.options.get("params", "")), "Danh sách 0–100, cách nhau dấu phẩy.", "Comma-separated 0–100 values.")
        elif segment.kind == "filter":
            fx = ttk.Frame(notebook, padding=5)
            notebook.add(fx, text="Filter")
            self._choice(fx, bindings, "name", "Filter", segment.options.get("name", ""), self._catalog("filter"), "Tên filter.", "Filter enum name.")
            self._field(fx, bindings, "intensity", "Intensity", segment.options.get("intensity", 100), "Cường độ 0–100.", "Intensity from 0 to 100.")
        elif segment.kind == "subtitle":
            subtitle = ttk.Frame(notebook, padding=5)
            notebook.add(subtitle, text="Subtitle")
            self._field(
                subtitle,
                bindings,
                "srt_path",
                "SRT path",
                segment.options.get("srt_path", ""),
                "Đường dẫn file SubRip UTF-8.",
                "Path to a UTF-8 SubRip file.",
            )
            self._field(
                subtitle,
                bindings,
                "time_offset",
                "Time offset",
                segment.options.get("time_offset", "0s"),
                "Dịch toàn bộ subtitle, hỗ trợ số âm.",
                "Shift all subtitles; negative values are supported.",
            )
            text_ids = [
                item.id
                for project_track in self.project.tracks
                for item in project_track.segments
                if item.kind == "text"
            ]
            self._choice(
                subtitle,
                bindings,
                "style_reference_id",
                "Style reference",
                segment.options.get("style_reference_id", ""),
                [""] + text_ids,
                "ID của Text segment trong project; trống dùng style bên dưới.",
                "ID of a project Text segment; blank uses the style fields below.",
            )
            self._field(
                subtitle,
                bindings,
                "style.size",
                "Font size",
                _get_path(segment.options, "style.size", 5),
                "Cỡ chữ subtitle.",
                "Subtitle font size.",
            )
            self._field(
                subtitle,
                bindings,
                "style.color",
                "Color",
                _get_path(segment.options, "style.color", "#FFFFFF"),
                "Màu #RRGGBB.",
                "Color in #RRGGBB.",
            )
            self._field(
                subtitle,
                bindings,
                "style.align",
                "Align",
                _get_path(segment.options, "style.align", 1),
                "0 trái, 1 giữa, 2 phải.",
                "0 left, 1 center, 2 right.",
            )
            self._field(
                subtitle,
                bindings,
                "style.auto_wrapping",
                "Auto wrap",
                _get_path(segment.options, "style.auto_wrapping", True),
                "Tự động xuống dòng.",
                "Automatically wrap long lines.",
                bool_field=True,
            )
            self._field(
                subtitle,
                bindings,
                "style.max_line_width",
                "Max line width",
                _get_path(segment.options, "style.max_line_width", 0.82),
                "Tỷ lệ chiều rộng 0–1.",
                "Maximum width ratio from 0 to 1.",
            )
            self._field(
                subtitle,
                bindings,
                "clip.transform_y",
                "Position Y",
                _get_path(segment.options, "clip.transform_y", -0.8),
                "Mặc định -0.8 giống CapCut subtitle.",
                "Default -0.8 matches CapCut subtitle placement.",
            )

        if segment.kind in ("video", "audio", "text", "sticker"):
            keyframes = ttk.Frame(notebook, padding=4)
            notebook.add(keyframes, text="Keyframes")
            values = [
                {"property": item.property, "time": item.time, "value": item.value}
                for item in segment.keyframes
            ]
            if segment.kind == "audio":
                props = ["volume"]
            elif segment.kind == "video":
                props = [
                    "position_x",
                    "position_y",
                    "rotation",
                    "scale_x",
                    "scale_y",
                    "uniform_scale",
                    "alpha",
                    "saturation",
                    "contrast",
                    "brightness",
                    "volume",
                ]
            else:
                props = [
                    "position_x",
                    "position_y",
                    "rotation",
                    "scale_x",
                    "scale_y",
                    "uniform_scale",
                ]
            editor = ListEditor(
                keyframes,
                "Keyframes",
                ("property", "time", "value"),
                [
                    ("property", "Property", props[0], "choice", props, "Thuộc tính cần điều khiển.", "Property to animate."),
                    ("time", "Offset", "0s", "entry", None, "Offset tính từ đầu segment.", "Offset from segment start."),
                    ("value", "Value", "0", "entry", None, "Giá trị keyframe.", "Keyframe value."),
                ],
                values,
            )
            editor.pack(fill="both", expand=True)
            bindings["_keyframes"] = values

        apply = ttk.Button(body, text="Áp dụng tất cả / Apply all", command=lambda: self._apply_segment(segment, bindings))
        apply.pack(fill="x", padx=8, pady=8)
        Tooltip.attach(
            apply,
            "Ghi toàn bộ giá trị Inspector vào model; chưa ghi draft.",
            "Apply all Inspector values to the in-memory model; does not write a draft.",
        )

    def _video_tabs(self, notebook, segment, bindings):
        media = ttk.Frame(notebook, padding=5)
        notebook.add(media, text="Video")
        for key, label, default in [
            ("crop.upper_left_x", "Crop UL X", 0.0), ("crop.upper_left_y", "Crop UL Y", 0.0),
            ("crop.upper_right_x", "Crop UR X", 1.0), ("crop.upper_right_y", "Crop UR Y", 0.0),
            ("crop.lower_left_x", "Crop LL X", 0.0), ("crop.lower_left_y", "Crop LL Y", 1.0),
            ("crop.lower_right_x", "Crop LR X", 1.0), ("crop.lower_right_y", "Crop LR Y", 1.0),
        ]:
            self._field(media, bindings, key, label, _get_path(segment.options, key, default), "Tọa độ crop chuẩn hóa 0–1.", "Normalized crop coordinate from 0 to 1.")
        fx = ttk.Frame(notebook, padding=5)
        notebook.add(fx, text="FX")
        self._field(fx, bindings, "fade.enabled", "Fade enabled", _get_path(segment.options, "fade.enabled", False), "Bật audio fade của video.", "Enable video audio fade.", bool_field=True)
        self._field(fx, bindings, "fade.in", "Fade in", _get_path(segment.options, "fade.in", "0s"), "Thời lượng fade in.", "Fade-in duration.")
        self._field(fx, bindings, "fade.out", "Fade out", _get_path(segment.options, "fade.out", "0s"), "Thời lượng fade out.", "Fade-out duration.")
        self._field(fx, bindings, "mask.enabled", "Mask enabled", _get_path(segment.options, "mask.enabled", False), "Mỗi segment chỉ có một mask.", "Only one mask per segment.", bool_field=True)
        self._choice(fx, bindings, "mask.name", "Mask", _get_path(segment.options, "mask.name", ""), self._catalog("mask"), "Loại mask.", "Mask type.")
        for key, label, default in [
            ("mask.center_x", "Mask center X", 0), ("mask.center_y", "Mask center Y", 0),
            ("mask.size", "Mask size", 0.5), ("mask.rotation", "Mask rotation", 0),
            ("mask.feather", "Mask feather", 0), ("mask.rect_width", "Rect width", ""),
            ("mask.round_corner", "Round corner", ""),
        ]:
            self._field(fx, bindings, key, label, _get_path(segment.options, key, default), "Tham số mask theo README.", "Mask parameter documented by pycapcut.")
        self._field(fx, bindings, "mask.invert", "Invert mask", _get_path(segment.options, "mask.invert", False), "Đảo vùng mask.", "Invert the mask.", bool_field=True)
        self._field(fx, bindings, "transition.enabled", "Transition enabled", _get_path(segment.options, "transition.enabled", False), "Transition đặt trên segment phía trước.", "Transition belongs to the preceding segment.", bool_field=True)
        self._choice(fx, bindings, "transition.name", "Transition", _get_path(segment.options, "transition.name", ""), self._catalog("transition"), "Loại transition.", "Transition type.")
        self._field(fx, bindings, "transition.duration", "Transition duration", _get_path(segment.options, "transition.duration", ""), "Trống dùng mặc định metadata.", "Blank uses metadata default.")
        self._field(fx, bindings, "background.enabled", "Background enabled", _get_path(segment.options, "background.enabled", False), "Chỉ có tác dụng ở video track đáy.", "Only affects the bottom video track.", bool_field=True)
        self._choice(fx, bindings, "background.type", "Background type", _get_path(segment.options, "background.type", "blur"), ["blur", "color"], "Blur hoặc color.", "Blur or solid color.")
        self._field(fx, bindings, "background.blur", "Blur", _get_path(segment.options, "background.blur", 0.0625), "Mức blur 0–1.", "Blur amount from 0 to 1.")
        self._field(fx, bindings, "background.color", "Color", _get_path(segment.options, "background.color", "#00000000"), "Màu #RRGGBBAA.", "Color in #RRGGBBAA.")
        lists = ttk.Frame(notebook, padding=4)
        notebook.add(lists, text="Lists")
        animations = segment.options.setdefault("animations", [])
        effects = segment.options.setdefault("effects", [])
        filters = segment.options.setdefault("filters", [])
        video_animation_names = (
            self._catalog("video_intro")
            + self._catalog("video_outro")
            + self._catalog("video_group")
        )
        video_effect_names = (
            self._catalog("video_scene_effect")
            + self._catalog("video_character_effect")
        )
        ListEditor(lists, "Animations", ("family", "name", "duration"), [
            ("family", "Family", "intro", "choice", ["intro", "outro", "group"], "Intro/outro/group.", "Intro/outro/group."),
            ("name", "Enum name", video_animation_names[0] if video_animation_names else "", "choice", video_animation_names, "Chọn enum metadata phù hợp family.", "Choose a metadata enum matching the selected family."),
            ("duration", "Duration", "", "entry", None, "Trống dùng mặc định.", "Blank uses default."),
        ], animations, before_change=self.history.checkpoint).pack(fill="x", pady=2)
        ListEditor(lists, "Effects", ("family", "name", "params"), [
            ("family", "Family", "scene", "choice", ["scene", "character"], "Scene hoặc character.", "Scene or character."),
            ("name", "Enum name", video_effect_names[0] if video_effect_names else "", "choice", video_effect_names, "Chọn enum phù hợp family.", "Choose an enum matching the effect family."),
            ("params", "Params", "", "entry", None, "Giá trị 0–100, dấu phẩy.", "Comma-separated 0–100 values."),
        ], effects, before_change=self.history.checkpoint).pack(fill="x", pady=2)
        ListEditor(lists, "Filters", ("name", "intensity"), [
            ("name", "Enum name", self._catalog("filter")[0] if self._catalog("filter") else "", "choice", self._catalog("filter"), "Chọn filter metadata.", "Choose filter metadata."),
            ("intensity", "Intensity", "100", "entry", None, "Cường độ 0–100.", "Intensity 0–100."),
        ], filters, before_change=self.history.checkpoint).pack(fill="x", pady=2)

    def _audio_tabs(self, notebook, segment, bindings):
        fx = ttk.Frame(notebook, padding=5)
        notebook.add(fx, text="Audio FX")
        self._field(fx, bindings, "fade.enabled", "Fade enabled", _get_path(segment.options, "fade.enabled", False), "Bật fade in/out.", "Enable fade in/out.", bool_field=True)
        self._field(fx, bindings, "fade.in", "Fade in", _get_path(segment.options, "fade.in", "0s"), "Thời lượng fade in.", "Fade-in duration.")
        self._field(fx, bindings, "fade.out", "Fade out", _get_path(segment.options, "fade.out", "0s"), "Thời lượng fade out.", "Fade-out duration.")
        effects = segment.options.setdefault("effects", [])
        audio_names = self._catalog("audio_effect")
        ListEditor(fx, "Audio Effects", ("name", "params"), [
            ("name", "Enum name", audio_names[0] if audio_names else "", "choice", audio_names, "Chọn AudioSceneEffectType.", "Choose AudioSceneEffectType metadata."),
            ("params", "Params", "", "entry", None, "Giá trị 0–100, dấu phẩy.", "Comma-separated 0–100 values."),
        ], effects, before_change=self.history.checkpoint).grid(row=3, column=0, columnspan=2, sticky="nsew", pady=4)

    def _text_tabs(self, notebook, segment, bindings):
        text = ttk.Frame(notebook, padding=5)
        notebook.add(text, text="Text")
        self._field(text, bindings, "text", "Nội dung / Content", segment.options.get("text", ""), "Nội dung text, hỗ trợ xuống dòng.", "Text content; line breaks are supported.", text_field=True)
        self._choice(text, bindings, "font", "Font", segment.options.get("font", ""), [""] + self._catalog("font"), "FontType; trống dùng system font.", "FontType; blank uses system font.")
        for key, label, default, help_vi, help_en in [
            ("style.size", "Size", 8.0, "Cỡ chữ.", "Font size."),
            ("style.color", "Color", "#FFFFFF", "Màu #RRGGBB.", "Color in #RRGGBB."),
            ("style.alpha", "Alpha", 1.0, "Độ trong suốt 0–1.", "Opacity from 0 to 1."),
            ("style.align", "Align", 0, "0 trái, 1 giữa, 2 phải.", "0 left, 1 center, 2 right."),
            ("style.letter_spacing", "Letter spacing", 0, "Khoảng cách chữ.", "Letter spacing."),
            ("style.line_spacing", "Line spacing", 0, "Khoảng cách dòng.", "Line spacing."),
            ("style.max_line_width", "Max line width", 0.82, "Tỷ lệ chiều rộng 0–1.", "Maximum width ratio 0–1."),
        ]:
            self._field(text, bindings, key, label, _get_path(segment.options, key, default), help_vi, help_en)
        for key, label in [
            ("style.bold", "Bold"), ("style.italic", "Italic"), ("style.underline", "Underline"),
            ("style.vertical", "Vertical"), ("style.auto_wrapping", "Auto wrap"),
        ]:
            self._field(text, bindings, key, label, _get_path(segment.options, key, False), label, label, bool_field=True)
        decoration = ttk.Frame(notebook, padding=5)
        notebook.add(decoration, text="Decoration")
        schemas = [
            ("border", [("alpha", 1), ("color", "#000000"), ("width", 40)]),
            ("text_background", [("style", 1), ("color", "#000000"), ("alpha", 1), ("round_radius", 0), ("height", 0.14), ("width", 0.14), ("horizontal_offset", 0.5), ("vertical_offset", 0.5)]),
            ("shadow", [("alpha", 1), ("color", "#000000"), ("diffuse", 15), ("distance", 5), ("angle", -45)]),
        ]
        for prefix, fields in schemas:
            self._field(decoration, bindings, f"{prefix}.enabled", f"{prefix} enabled", _get_path(segment.options, f"{prefix}.enabled", False), f"Bật {prefix}.", f"Enable {prefix}.", bool_field=True)
            for name, default in fields:
                self._field(decoration, bindings, f"{prefix}.{name}", f"{prefix}.{name}", _get_path(segment.options, f"{prefix}.{name}", default), f"Tham số {prefix}.", f"{prefix} parameter.")
        for prefix, fields in [
            ("bubble", [("effect_id", ""), ("resource_id", "")]),
            ("flower_text", [("effect_id", "")]),
        ]:
            self._field(decoration, bindings, f"{prefix}.enabled", f"{prefix} enabled", _get_path(segment.options, f"{prefix}.enabled", False), f"Bật {prefix}.", f"Enable {prefix}.", bool_field=True)
            for name, default in fields:
                self._field(decoration, bindings, f"{prefix}.{name}", f"{prefix}.{name}", _get_path(segment.options, f"{prefix}.{name}", default), "ID lấy từ Template Inspect.", "ID obtained from Template Inspect.")
        animations = segment.options.setdefault("animations", [])
        text_animation_names = (
            self._catalog("text_intro")
            + self._catalog("text_outro")
            + self._catalog("text_loop")
        )
        ListEditor(decoration, "Text Animations", ("family", "name", "duration"), [
            ("family", "Family", "intro", "choice", ["intro", "outro", "loop"], "Thêm intro/outro trước loop.", "Intro/outro are applied before loop."),
            ("name", "Enum name", text_animation_names[0] if text_animation_names else "", "choice", text_animation_names, "Chọn enum phù hợp family.", "Choose an enum matching the animation family."),
            ("duration", "Duration", "0.5s", "entry", None, "Loop tự phủ phần còn lại.", "Loop fills the remaining duration."),
        ], animations, before_change=self.history.checkpoint).grid(row=30, column=0, columnspan=2, sticky="nsew", pady=4)

    def _field(self, parent, bindings, path, label, value, vi, en, bool_field=False, text_field=False):
        row = getattr(parent, "_pycapcut_form_row", 0)
        setattr(parent, "_pycapcut_form_row", row + 1)
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="nw", padx=3, pady=2)
        if bool_field:
            variable = tk.BooleanVar(value=bool(value))
            widget = ttk.Checkbutton(parent, variable=variable)
        elif text_field:
            variable = None
            widget = tk.Text(parent, height=5, width=26)
            widget.insert("1.0", str(value))
        else:
            variable = tk.StringVar(value="" if value is None else str(value))
            widget = ttk.Entry(parent, textvariable=variable)
        widget.grid(row=row, column=1, sticky="ew", padx=3, pady=2)
        parent.columnconfigure(1, weight=1)
        bindings[path] = (variable, widget, "bool" if bool_field else "text" if text_field else "entry")
        Tooltip.attach(widget, vi, en)

    def _choice(self, parent, bindings, path, label, value, choices, vi, en):
        row = getattr(parent, "_pycapcut_form_row", 0)
        setattr(parent, "_pycapcut_form_row", row + 1)
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=3, pady=2)
        normalized = list(dict.fromkeys([str(item) for item in choices if item is not None]))
        if str(value) and str(value) not in normalized:
            normalized.insert(0, str(value))
        variable = tk.StringVar(value=str(value))
        widget = ttk.Combobox(parent, textvariable=variable, values=normalized, state="readonly")
        widget.grid(row=row, column=1, sticky="ew", padx=3, pady=2)
        parent.columnconfigure(1, weight=1)
        bindings[path] = (variable, widget, "choice")
        Tooltip.attach(widget, vi, en)

    def _apply_segment(self, segment: SegmentModel, bindings: Dict[str, Any]) -> None:
        self.history.checkpoint()
        for path, item in bindings.items():
            if path == "_keyframes":
                segment.keyframes = [
                    KeyframeModel(
                        property=value["property"],
                        time=value["time"],
                        value=float(value["value"]),
                    )
                    for value in item
                ]
                continue
            variable, widget, kind = item
            value = widget.get("1.0", "end-1c") if kind == "text" else variable.get()
            if path == "name":
                segment.name = value
            elif path == "start":
                segment.start = value
            elif path == "duration":
                segment.duration = value
            else:
                _set_path(segment.options, path, _coerce(value))
        self.refresh_all()

    def _catalog(self, key: str) -> list[str]:
        if not self.catalog:
            try:
                self.catalog = metadata_catalog()
            except Exception as exc:
                self.log.log(f"Metadata unavailable: {exc}", "warning")
                self.catalog = {"_loaded": []}
        return self.catalog.get(key, [])

    def _timeline_changed(self) -> None:
        errors = []
        try:
            errors = self._selected_track().validate(self.project.material_map) if self._selected_track() else []
        except Exception:
            pass
        if errors:
            self.log.log("\n".join(errors), "warning")
        self.refresh_all()


def _get_path(data: Dict[str, Any], path: str, default=None):
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _set_path(data: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _coerce(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    text = str(value).strip()
    if text == "":
        return ""
    if "," in text and all(_number_or_keyword(item) for item in text.split(",")):
        return [None if item.strip().lower() in ("none", "default", "") else float(item) for item in text.split(",")]
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def _number_or_keyword(value: str) -> bool:
    if value.strip().lower() in ("none", "default", ""):
        return True
    try:
        float(value)
        return True
    except ValueError:
        return False


def _csv(value: Any) -> str:
    if isinstance(value, list):
        return ",".join("default" if item is None else str(item) for item in value)
    return str(value)
