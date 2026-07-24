"""Typed HTTP DTOs and conversion helpers for the React application."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .models import (
    KeyframeModel,
    MaterialModel,
    ProjectModel,
    SegmentModel,
    TrackModel,
)


class KeyframeDTO(BaseModel):
    property: str
    time: str = "0s"
    value: float = 0.0
    id: str


class MaterialDTO(BaseModel):
    kind: str
    path: str = ""
    name: str = ""
    resource_id: str = ""
    id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SegmentDTO(BaseModel):
    kind: str
    start: str = "0s"
    duration: str = "1s"
    material_id: str = ""
    name: str = ""
    options: Dict[str, Any] = Field(default_factory=dict)
    keyframes: List[KeyframeDTO] = Field(default_factory=list)
    id: str


class TrackDTO(BaseModel):
    kind: str
    name: str
    mute: bool = False
    relative_index: int = 0
    absolute_index: Optional[int] = None
    segments: List[SegmentDTO] = Field(default_factory=list)
    id: str


class ProjectDTO(BaseModel):
    draft_folder: str
    draft_name: str = "new_draft"
    width: int = 1920
    height: int = 1080
    fps: int = 30
    overwrite: bool = False
    materials: List[MaterialDTO] = Field(default_factory=list)
    tracks: List[TrackDTO] = Field(default_factory=list)


class ApiError(BaseModel):
    error_code: str
    message_vi: str
    message_en: str
    path: str = ""


class ValidationResult(BaseModel):
    valid: bool
    errors: List[ApiError] = Field(default_factory=list)


def dump_model(model: BaseModel) -> Dict[str, Any]:
    """Support both Pydantic 1 and 2."""
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[attr-defined]
    return model.dict()


def project_to_dto(project: ProjectModel) -> ProjectDTO:
    return ProjectDTO(
        draft_folder=project.draft_folder,
        draft_name=project.draft_name,
        width=project.width,
        height=project.height,
        fps=project.fps,
        overwrite=project.overwrite,
        materials=[
            MaterialDTO(
                kind=item.kind,
                path=item.path,
                name=item.name,
                resource_id=item.resource_id,
                id=item.id,
            )
            for item in project.materials
        ],
        tracks=[
            TrackDTO(
                kind=track.kind,
                name=track.name,
                mute=track.mute,
                relative_index=track.relative_index,
                absolute_index=track.absolute_index,
                id=track.id,
                segments=[
                    SegmentDTO(
                        kind=segment.kind,
                        start=segment.start,
                        duration=segment.duration,
                        material_id=segment.material_id,
                        name=segment.name,
                        options=segment.options,
                        id=segment.id,
                        keyframes=[
                            KeyframeDTO(
                                property=keyframe.property,
                                time=keyframe.time,
                                value=keyframe.value,
                                id=keyframe.id,
                            )
                            for keyframe in segment.keyframes
                        ],
                    )
                    for segment in track.segments
                ],
            )
            for track in project.tracks
        ],
    )


def dto_to_project(dto: ProjectDTO) -> ProjectModel:
    return ProjectModel(
        draft_folder=dto.draft_folder,
        draft_name=dto.draft_name,
        width=dto.width,
        height=dto.height,
        fps=dto.fps,
        overwrite=dto.overwrite,
        materials=[
            MaterialModel(
                kind=item.kind,
                path=item.path,
                name=item.name,
                resource_id=item.resource_id,
                id=item.id,
            )
            for item in dto.materials
        ],
        tracks=[
            TrackModel(
                kind=track.kind,
                name=track.name,
                mute=track.mute,
                relative_index=track.relative_index,
                absolute_index=track.absolute_index,
                id=track.id,
                segments=[
                    SegmentModel(
                        kind=segment.kind,
                        start=segment.start,
                        duration=segment.duration,
                        material_id=segment.material_id,
                        name=segment.name,
                        options=segment.options,
                        id=segment.id,
                        keyframes=[
                            KeyframeModel(
                                property=keyframe.property,
                                time=keyframe.time,
                                value=keyframe.value,
                                id=keyframe.id,
                            )
                            for keyframe in segment.keyframes
                        ],
                    )
                    for segment in track.segments
                ],
            )
            for track in dto.tracks
        ],
    )
