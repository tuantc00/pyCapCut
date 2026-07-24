"""Draft, template, batch and Windows export services."""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .adapter import build_script, enum_member
from .models import (
    MaterialModel,
    ProjectModel,
    SegmentModel,
    parse_time,
)


class DraftService:
    def __init__(self, folder: str):
        import pycapcut as cc

        self.cc = cc
        self.folder_path = folder
        self.folder = cc.DraftFolder(folder)

    def list(self) -> List[str]:
        return sorted(self.folder.list_drafts(), key=str.casefold)

    def duplicate(self, source: str, target: str, overwrite: bool = False) -> Path:
        script = self.folder.duplicate_as_template(source, target, allow_replace=overwrite)
        script.save()
        return Path(self.folder_path) / target

    def remove(self, name: str) -> None:
        self.folder.remove(name)

    def inspect(self, name: str) -> str:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.folder.inspect_material(name)
        return output.getvalue()


class TemplateSession:
    """Supported template operations, with no direct JSON patching."""

    def __init__(self, folder: str, template_name: str):
        import pycapcut as cc

        self.cc = cc
        self.folder_path = folder
        self.folder = cc.DraftFolder(folder)
        self.template_name = template_name
        self.script = self.folder.load_template(template_name)

    @property
    def imported_tracks(self) -> list[Any]:
        return self.script.imported_tracks

    def duplicate(self, target: str, overwrite: bool = False) -> "TemplateSession":
        self.folder.duplicate_as_template(
            self.template_name,
            target,
            allow_replace=overwrite,
        )
        return TemplateSession(self.folder_path, target)

    def inspect(self) -> str:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.script.inspect_material()
        return output.getvalue()

    def get_track(self, kind: str, name: str = "", index: int = 0):
        kwargs: Dict[str, Any] = {"index": index}
        if name:
            kwargs = {"name": name}
        return self.script.get_imported_track(
            enum_member(self.cc.TrackType, kind),
            **kwargs,
        )

    def replace_by_name(
        self,
        material_name: str,
        path: str,
        kind: str,
        material_name_override: str = "",
        replace_crop: bool = True,
    ) -> None:
        material = self._material(path, kind, material_name_override)
        self.script.replace_material_by_name(
            material_name,
            material,
            replace_crop=replace_crop,
        )

    def replace_by_segment(
        self,
        track,
        segment_index: int,
        path: str,
        kind: str,
        source_start: str = "0s",
        source_duration: str = "",
        shrink: str = "cut_tail",
        extend_modes: Optional[List[str]] = None,
    ) -> None:
        material = self._material(path, kind)
        source = None
        if source_duration:
            source = self.cc.Timerange(
                parse_time(source_start),
                parse_time(source_duration),
            )
        extend_modes = extend_modes or ["cut_material_tail"]
        self.script.replace_material_by_seg(
            track,
            segment_index,
            material,
            source_timerange=source,
            handle_shrink=enum_member(self.cc.ShrinkMode, shrink),
            handle_extend=[
                enum_member(self.cc.ExtendMode, mode) for mode in extend_modes
            ],
        )

    def replace_text(
        self,
        track,
        segment_index: int,
        text: str,
        recalc_style: bool = True,
    ) -> None:
        values: Any = [item for item in text.split("\n---\n")]
        if len(values) == 1:
            values = values[0]
        self.script.replace_text(track, segment_index, values, recalc_style=recalc_style)

    def import_track(
        self,
        source_session: "TemplateSession",
        source_track,
        offset: str = "0s",
        new_name: str = "",
        relative_index: int = 0,
    ) -> None:
        self.script.import_track(
            source_session.script,
            source_track,
            offset=parse_time(offset),
            new_name=new_name or None,
            relative_index=relative_index,
        )

    def save(self) -> None:
        self.script.save()

    def _material(self, path: str, kind: str, name: str = ""):
        if kind in ("video", "image"):
            return self.cc.VideoMaterial(path, name or None)
        return self.cc.AudioMaterial(path, name or None)


@dataclass
class BatchOptions:
    source_folder: str
    draft_folder: str
    voice_path: str = ""
    subtitle_path: str = ""
    duration: str = "30s"
    width: int = 1920
    height: int = 1080
    fps: int = 30
    voice_volume: float = 1.0
    mute_source: bool = True
    add_subtitles: bool = True
    limit: int = 10
    test_mode: bool = False
    overwrite: bool = False
    prefix: str = "auto_video"


class BatchCreator:
    VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm")

    def __init__(self, options: BatchOptions):
        self.options = options
        self.files = sorted(
            (
                name
                for name in os.listdir(options.source_folder)
                if name.lower().endswith(self.VIDEO_EXTENSIONS)
            ),
            key=str.casefold,
        )
        limit = min(options.limit, len(self.files))
        if options.test_mode:
            limit = min(limit, 3)
        self.files = self.files[:limit]
        self.next_index = 0
        self.success = 0
        self.failed = 0
        self.skipped = 0

    def run(self, context) -> Dict[str, int]:
        total = len(self.files)
        for index in range(self.next_index, total):
            if context.stopped:
                self.next_index = index
                break
            source_name = self.files[index]
            draft_name = f"{self.options.prefix}_{index + 1:03d}"
            context.progress(index, total, draft_name)
            try:
                build_script(self._project(source_name, draft_name))
            except FileExistsError:
                self.skipped += 1
                context.log(f"⏭ {draft_name}: đã tồn tại / already exists", "warning")
            except Exception as exc:
                self.failed += 1
                context.log(f"❌ {draft_name}: {exc}", "error")
            else:
                self.success += 1
                context.log(f"✅ {draft_name}: created", "success")
            self.next_index = index + 1
            context.progress(self.next_index, total, draft_name)
        return {
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "remaining": max(0, total - self.next_index),
        }

    def _project(self, source_name: str, draft_name: str) -> ProjectModel:
        options = self.options
        project = ProjectModel(
            draft_folder=options.draft_folder,
            draft_name=draft_name,
            width=options.width,
            height=options.height,
            fps=options.fps,
            overwrite=options.overwrite,
        )
        source = MaterialModel(
            kind="video",
            path=os.path.join(options.source_folder, source_name),
            name=source_name,
        )
        project.materials.append(source)
        video_track = project.add_track("video", "source")
        video_track.segments.append(
            SegmentModel(
                kind="video",
                start="0s",
                duration=options.duration,
                material_id=source.id,
                name=source_name,
                options={"volume": 0.0 if options.mute_source else 1.0},
            )
        )
        if options.voice_path:
            voice = MaterialModel(
                kind="audio",
                path=options.voice_path,
                name=os.path.basename(options.voice_path),
            )
            project.materials.append(voice)
            audio_track = project.add_track("audio", "voice")
            audio_track.segments.append(
                SegmentModel(
                    kind="audio",
                    start="0s",
                    duration=options.duration,
                    material_id=voice.id,
                    name=voice.name,
                    options={"volume": options.voice_volume},
                )
            )
        if options.add_subtitles and options.subtitle_path:
            text_track = project.add_track("text", "subtitle")
            text_track.segments.append(
                SegmentModel(
                    kind="subtitle",
                    start="0s",
                    duration=options.duration,
                    name=os.path.basename(options.subtitle_path),
                    options={
                        "srt_path": options.subtitle_path,
                        "time_offset": "0s",
                        "style": {"size": 5, "align": 1, "auto_wrapping": True},
                        "clip": {"transform_y": -0.8},
                    },
                )
            )
        return project


class ExportQueue:
    def __init__(
        self,
        drafts: Iterable[str],
        output_folder: str = "",
        resolution: str = "",
        framerate: str = "",
        timeout: float = 1200,
    ):
        self.drafts = list(drafts)
        self.output_folder = output_folder
        self.resolution = resolution
        self.framerate = framerate
        self.timeout = timeout

    def run(self, context) -> Dict[str, int]:
        if sys.platform != "win32":
            raise RuntimeError("Export automation chỉ hỗ trợ Windows / Windows only")
        from pycapcut.jianying_controller import (
            ExportFramerate,
            ExportResolution,
            JianyingController,
        )

        controller = JianyingController()
        success = failed = 0
        for index, draft in enumerate(self.drafts):
            if context.stopped:
                break
            context.progress(index, len(self.drafts), draft)
            output = (
                os.path.join(self.output_folder, f"{draft}.mp4")
                if self.output_folder
                else None
            )
            try:
                controller.export_draft(
                    draft,
                    output,
                    resolution=enum_member(ExportResolution, self.resolution),
                    framerate=enum_member(ExportFramerate, self.framerate),
                    timeout=self.timeout,
                )
            except Exception as exc:
                failed += 1
                context.log(f"❌ Export {draft}: {exc}", "error")
            else:
                success += 1
                context.log(f"✅ Export {draft}", "success")
            context.progress(index + 1, len(self.drafts), draft)
        return {"success": success, "failed": failed}


def open_path(path: str) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def find_capcut_executable() -> Optional[str]:
    if sys.platform != "win32":
        return None
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "CapCut" / "Apps" / "CapCut.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "CapCut" / "CapCut.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "CapCut" / "CapCut.exe",
    ]
    which = shutil.which("CapCut.exe")
    if which:
        candidates.insert(0, Path(which))
    return next((str(path) for path in candidates if path.is_file()), None)


def open_capcut() -> str:
    executable = find_capcut_executable()
    if not executable:
        raise FileNotFoundError(
            "Không tìm thấy CapCut.exe; hãy mở CapCut thủ công / CapCut.exe not found"
        )
    subprocess.Popen([executable])
    return executable
