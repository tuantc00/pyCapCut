"""In-memory editing models used by the desktop GUI."""

from __future__ import annotations

import copy
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


SEC = 1_000_000
TRACK_KINDS = ("video", "audio", "text", "sticker", "effect", "filter")
MEDIA_KINDS = ("video", "image", "audio")
SEGMENT_KINDS = TRACK_KINDS + ("subtitle",)


def new_id() -> str:
    return uuid.uuid4().hex


def parse_time(value: Any) -> int:
    """Parse the same user-facing time syntax as ``pycapcut.tim``."""
    if isinstance(value, (int, float)):
        return int(round(value))
    text = str(value).strip().lower()
    if not text:
        raise ValueError("Thời gian không được để trống / Time is required")
    try:
        # GUI convenience: a unitless string is interpreted as seconds.
        return int(round(float(text) * SEC))
    except ValueError:
        pass
    sign = -1 if text.startswith("-") else 1
    if sign < 0:
        text = text[1:]
    matches = list(re.finditer(r"(\d+(?:\.\d+)?)\s*([hms])", text))
    if not matches or "".join(match.group(0).replace(" ", "") for match in matches) != text.replace(" ", ""):
        raise ValueError(
            f"Thời gian '{value}' không hợp lệ; dùng dạng 1.5s, 2m3s / "
            "Invalid time; use 1.5s or 2m3s"
        )
    factors = {"h": 3600 * SEC, "m": 60 * SEC, "s": SEC}
    return sign * int(round(sum(float(m.group(1)) * factors[m.group(2)] for m in matches)))


def format_time(value: int) -> str:
    seconds = value / SEC
    text = f"{seconds:.3f}".rstrip("0").rstrip(".")
    return f"{text}s"


@dataclass
class MaterialModel:
    kind: str
    path: str = ""
    name: str = ""
    resource_id: str = ""
    id: str = field(default_factory=new_id)

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.kind not in MEDIA_KINDS + ("sticker",):
            errors.append(f"Loại material không hợp lệ / Invalid material kind: {self.kind}")
        if self.kind == "sticker":
            if not self.resource_id.strip():
                errors.append("Sticker cần resource ID / Sticker resource ID is required")
        elif not os.path.isfile(self.path):
            errors.append(f"Không tìm thấy material / Material not found: {self.path}")
        return errors


@dataclass
class KeyframeModel:
    property: str
    time: str = "0s"
    value: float = 0.0
    id: str = field(default_factory=new_id)


@dataclass
class SegmentModel:
    kind: str
    start: str = "0s"
    duration: str = "1s"
    material_id: str = ""
    name: str = ""
    options: Dict[str, Any] = field(default_factory=dict)
    keyframes: List[KeyframeModel] = field(default_factory=list)
    id: str = field(default_factory=new_id)

    @property
    def start_us(self) -> int:
        return parse_time(self.start)

    @property
    def duration_us(self) -> int:
        return parse_time(self.duration)

    @property
    def end_us(self) -> int:
        return self.start_us + self.duration_us

    def validate(self, materials: Dict[str, MaterialModel]) -> List[str]:
        errors: List[str] = []
        if self.kind not in SEGMENT_KINDS:
            errors.append(f"Loại segment không hợp lệ / Invalid segment kind: {self.kind}")
        try:
            start = self.start_us
            duration = self.duration_us
            if start < 0:
                errors.append(f"{self.name or self.kind}: start phải >= 0 / start must be >= 0")
            if duration <= 0:
                errors.append(f"{self.name or self.kind}: duration phải > 0 / duration must be > 0")
        except ValueError as exc:
            errors.append(str(exc))
        if self.kind in ("video", "audio") and self.material_id not in materials:
            errors.append(f"{self.name or self.kind}: chưa chọn material / material is required")
        if self.kind == "sticker" and not self.options.get("resource_id"):
            errors.append(f"{self.name or self.kind}: sticker cần resource ID / resource ID is required")
        if self.kind == "subtitle" and not os.path.isfile(self.options.get("srt_path", "")):
            errors.append(f"{self.name or self.kind}: không tìm thấy SRT / SRT file not found")
        if self.kind in ("effect", "filter") and not self.options.get("name"):
            errors.append(f"{self.name or self.kind}: chưa chọn metadata / metadata name is required")
        for keyframe in self.keyframes:
            try:
                offset = parse_time(keyframe.time)
                if offset < 0 or offset > self.duration_us:
                    errors.append(
                        f"Keyframe {keyframe.property} nằm ngoài segment / is outside the segment"
                    )
            except ValueError as exc:
                errors.append(str(exc))
        return errors


@dataclass
class TrackModel:
    kind: str
    name: str
    mute: bool = False
    relative_index: int = 0
    absolute_index: Optional[int] = None
    segments: List[SegmentModel] = field(default_factory=list)
    id: str = field(default_factory=new_id)

    def validate(self, materials: Dict[str, MaterialModel]) -> List[str]:
        errors: List[str] = []
        if self.kind not in TRACK_KINDS:
            errors.append(f"Loại track không hợp lệ / Invalid track type: {self.kind}")
        if not self.name.strip():
            errors.append("Tên track không được trống / Track name is required")
        ordered = sorted(self.segments, key=lambda item: item.start_us if _valid_time(item.start) else 0)
        for segment in ordered:
            errors.extend(segment.validate(materials))
        for left, right in zip(ordered, ordered[1:]):
            try:
                if left.end_us > right.start_us:
                    errors.append(
                        f"Track '{self.name}' có segment chồng nhau / contains overlapping segments: "
                        f"{left.name or left.kind}, {right.name or right.kind}"
                    )
            except ValueError:
                pass
        accepted = "text" if self.kind == "text" else self.kind
        for segment in self.segments:
            segment_kind = "text" if segment.kind == "subtitle" else segment.kind
            if segment_kind != accepted:
                errors.append(
                    f"Track '{self.name}' không nhận segment {segment.kind} / incompatible segment"
                )
        return errors


def _valid_time(value: str) -> bool:
    try:
        parse_time(value)
        return True
    except ValueError:
        return False


@dataclass
class ProjectModel:
    draft_folder: str = field(
        default_factory=lambda: str(Path.home() / "Documents" / "CapCut Drafts")
    )
    draft_name: str = "new_draft"
    width: int = 1920
    height: int = 1080
    fps: int = 30
    overwrite: bool = False
    materials: List[MaterialModel] = field(default_factory=list)
    tracks: List[TrackModel] = field(default_factory=list)

    @property
    def material_map(self) -> Dict[str, MaterialModel]:
        return {material.id: material for material in self.materials}

    @property
    def duration_us(self) -> int:
        values = []
        for track in self.tracks:
            for segment in track.segments:
                try:
                    values.append(segment.end_us)
                except ValueError:
                    continue
        return max(values, default=0)

    def find_track(self, track_id: str) -> TrackModel:
        return next(track for track in self.tracks if track.id == track_id)

    def find_segment(self, segment_id: str) -> tuple[TrackModel, SegmentModel]:
        for track in self.tracks:
            for segment in track.segments:
                if segment.id == segment_id:
                    return track, segment
        raise KeyError(segment_id)

    def add_track(self, kind: str, name: Optional[str] = None) -> TrackModel:
        base = name or kind
        candidate = base
        suffix = 2
        names = {track.name for track in self.tracks}
        while candidate in names:
            candidate = f"{base}_{suffix}"
            suffix += 1
        track = TrackModel(kind=kind, name=candidate)
        self.tracks.append(track)
        return track

    def remove_track(self, track_id: str) -> None:
        self.tracks = [track for track in self.tracks if track.id != track_id]

    def add_material(self, material: MaterialModel) -> None:
        self.materials.append(material)

    def remove_material(self, material_id: str) -> None:
        if any(
            segment.material_id == material_id
            for track in self.tracks
            for segment in track.segments
        ):
            raise ValueError(
                "Material đang được segment sử dụng / Material is used by a segment"
            )
        self.materials = [item for item in self.materials if item.id != material_id]

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.draft_name.strip():
            errors.append("Tên draft không được trống / Draft name is required")
        if any(char in self.draft_name for char in '<>:"/\\|?*'):
            errors.append("Tên draft chứa ký tự cấm của Windows / Invalid Windows filename")
        if not os.path.isdir(self.draft_folder):
            errors.append(f"Thư mục draft không tồn tại / Draft folder not found: {self.draft_folder}")
        elif not os.access(self.draft_folder, os.W_OK):
            errors.append(f"Không có quyền ghi thư mục draft / Draft folder is not writable: {self.draft_folder}")
        if self.width <= 0 or self.height <= 0:
            errors.append("Canvas phải có kích thước dương / Canvas dimensions must be positive")
        if self.fps <= 0:
            errors.append("FPS phải > 0 / FPS must be positive")
        if not self.tracks:
            errors.append("Project chưa có track / Project has no tracks")
        names = [track.name for track in self.tracks]
        if len(names) != len(set(names)):
            errors.append("Tên track phải duy nhất / Track names must be unique")
        for material in self.materials:
            errors.extend(material.validate())
        materials = self.material_map
        segment_ids = {segment.id for segment in iter_segments(self)}
        for track in self.tracks:
            errors.extend(track.validate(materials))
            for segment in track.segments:
                reference = segment.options.get("style_reference_id", "")
                if reference and reference not in segment_ids:
                    errors.append(
                        f"{segment.name or segment.kind}: style reference không tồn tại / does not exist"
                    )
        return errors


class ProjectHistory:
    """Snapshot history for predictable GUI undo and redo."""

    def __init__(self, project: ProjectModel, limit: int = 50):
        self.limit = limit
        self._undo: List[ProjectModel] = []
        self._redo: List[ProjectModel] = []
        self.current = project

    def checkpoint(self) -> None:
        self._undo.append(copy.deepcopy(self.current))
        self._undo = self._undo[-self.limit :]
        self._redo.clear()

    def undo(self) -> ProjectModel:
        if not self._undo:
            return self.current
        self._redo.append(copy.deepcopy(self.current))
        self.current = self._undo.pop()
        return self.current

    def redo(self) -> ProjectModel:
        if not self._redo:
            return self.current
        self._undo.append(copy.deepcopy(self.current))
        self.current = self._redo.pop()
        return self.current

    def reset(self, project: Optional[ProjectModel] = None) -> ProjectModel:
        self._undo.clear()
        self._redo.clear()
        self.current = project or ProjectModel()
        return self.current

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)


def enum_name(value: Any) -> str:
    return getattr(value, "name", str(value))


def ensure_float_list(value: Any) -> Optional[List[Optional[float]]]:
    if value in (None, "", []):
        return None
    if isinstance(value, list):
        return [None if item in (None, "") else float(item) for item in value]
    return [
        None if part.strip().lower() in ("", "none", "default") else float(part)
        for part in str(value).split(",")
    ]


def iter_segments(project: ProjectModel) -> Iterable[SegmentModel]:
    for track in project.tracks:
        yield from track.segments
