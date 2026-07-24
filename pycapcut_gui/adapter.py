"""Adapters from GUI models to the unmodified pycapcut public API."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .models import (
    KeyframeModel,
    MaterialModel,
    ProjectModel,
    SegmentModel,
    TrackModel,
    ensure_float_list,
    parse_time,
)


def _cc():
    import pycapcut as cc

    return cc


def enum_member(enum_cls, name: Any):
    if name is None or name == "":
        return None
    if isinstance(name, enum_cls):
        return name
    text = str(name)
    try:
        return enum_cls[text]
    except KeyError:
        return enum_cls.from_name(text)


def enum_names(enum_cls) -> list[str]:
    return [member.name for member in enum_cls]


def metadata_catalog() -> Dict[str, list[str]]:
    cc = _cc()
    return {
        "font": enum_names(cc.FontType),
        "mask": enum_names(cc.MaskType),
        "filter": enum_names(cc.FilterType),
        "transition": enum_names(cc.TransitionType),
        "video_intro": enum_names(cc.IntroType),
        "video_outro": enum_names(cc.OutroType),
        "video_group": enum_names(cc.GroupAnimationType),
        "text_intro": enum_names(cc.TextIntro),
        "text_outro": enum_names(cc.TextOutro),
        "text_loop": enum_names(cc.TextLoopAnim),
        "audio_effect": enum_names(cc.AudioSceneEffectType),
        "video_scene_effect": enum_names(cc.VideoSceneEffectType),
        "video_character_effect": enum_names(cc.VideoCharacterEffectType),
    }


def make_clip(options: Dict[str, Any]):
    cc = _cc()
    data = options.get("clip", {}) or {}
    return cc.ClipSettings(
        alpha=float(data.get("alpha", 1.0)),
        flip_horizontal=bool(data.get("flip_horizontal", False)),
        flip_vertical=bool(data.get("flip_vertical", False)),
        rotation=float(data.get("rotation", 0.0)),
        scale_x=float(data.get("scale_x", 1.0)),
        scale_y=float(data.get("scale_y", 1.0)),
        transform_x=float(data.get("transform_x", 0.0)),
        transform_y=float(data.get("transform_y", 0.0)),
    )


def make_crop(options: Dict[str, Any]):
    cc = _cc()
    data = options.get("crop", {}) or {}
    return cc.CropSettings(
        upper_left_x=float(data.get("upper_left_x", 0.0)),
        upper_left_y=float(data.get("upper_left_y", 0.0)),
        upper_right_x=float(data.get("upper_right_x", 1.0)),
        upper_right_y=float(data.get("upper_right_y", 0.0)),
        lower_left_x=float(data.get("lower_left_x", 0.0)),
        lower_left_y=float(data.get("lower_left_y", 1.0)),
        lower_right_x=float(data.get("lower_right_x", 1.0)),
        lower_right_y=float(data.get("lower_right_y", 1.0)),
    )


def make_material(model: MaterialModel, options: Optional[Dict[str, Any]] = None):
    cc = _cc()
    name = model.name or None
    if model.kind in ("video", "image"):
        return cc.VideoMaterial(model.path, name, make_crop(options or {}))
    if model.kind == "audio":
        return cc.AudioMaterial(model.path, name)
    raise TypeError(f"Material '{model.kind}' không được core hỗ trợ / is unsupported")


def _source_range(segment: SegmentModel):
    cc = _cc()
    start = segment.options.get("source_start", "")
    duration = segment.options.get("source_duration", "")
    if start in ("", None) and duration in ("", None):
        return None
    return cc.Timerange(
        parse_time(start or "0s"),
        parse_time(duration or segment.duration),
    )


def _apply_keyframes(segment_obj, keyframes: Iterable[KeyframeModel], audio: bool = False) -> None:
    cc = _cc()
    for keyframe in keyframes:
        if audio:
            segment_obj.add_keyframe(parse_time(keyframe.time), float(keyframe.value))
        else:
            prop = enum_member(cc.KeyframeProperty, keyframe.property)
            segment_obj.add_keyframe(prop, parse_time(keyframe.time), float(keyframe.value))


def _apply_video_modifiers(segment_obj, options: Dict[str, Any]) -> None:
    cc = _cc()
    fade = options.get("fade") or {}
    if fade.get("enabled"):
        segment_obj.add_fade(
            parse_time(fade.get("in", "0s")),
            parse_time(fade.get("out", "0s")),
        )

    for animation in options.get("animations", []):
        family = animation.get("family", "intro")
        enum_cls = {
            "intro": cc.IntroType,
            "outro": cc.OutroType,
            "group": cc.GroupAnimationType,
        }[family]
        duration = (
            parse_time(animation.get("duration"))
            if animation.get("duration")
            else None
        )
        segment_obj.add_animation(enum_member(enum_cls, animation["name"]), duration)

    for effect in options.get("effects", []):
        family = effect.get("family", "scene")
        enum_cls = (
            cc.VideoSceneEffectType
            if family == "scene"
            else cc.VideoCharacterEffectType
        )
        segment_obj.add_effect(
            enum_member(enum_cls, effect["name"]),
            ensure_float_list(effect.get("params")),
        )

    for filter_item in options.get("filters", []):
        segment_obj.add_filter(
            enum_member(cc.FilterType, filter_item["name"]),
            float(filter_item.get("intensity", 100)),
        )

    mask = options.get("mask") or {}
    if mask.get("enabled"):
        segment_obj.add_mask(
            enum_member(cc.MaskType, mask["name"]),
            center_x=float(mask.get("center_x", 0)),
            center_y=float(mask.get("center_y", 0)),
            size=float(mask.get("size", 0.5)),
            rotation=float(mask.get("rotation", 0)),
            feather=float(mask.get("feather", 0)),
            invert=bool(mask.get("invert", False)),
            rect_width=_optional_float(mask.get("rect_width")),
            round_corner=_optional_float(mask.get("round_corner")),
        )

    transition = options.get("transition") or {}
    if transition.get("enabled"):
        segment_obj.add_transition(
            enum_member(cc.TransitionType, transition["name"]),
            duration=(
                parse_time(transition.get("duration"))
                if transition.get("duration")
                else None
            ),
        )

    background = options.get("background") or {}
    if background.get("enabled"):
        segment_obj.add_background_filling(
            background.get("type", "blur"),
            blur=float(background.get("blur", 0.0625)),
            color=background.get("color", "#00000000"),
        )


def _apply_audio_modifiers(segment_obj, segment: SegmentModel) -> None:
    cc = _cc()
    options = segment.options
    fade = options.get("fade") or {}
    if fade.get("enabled"):
        segment_obj.add_fade(
            parse_time(fade.get("in", "0s")),
            parse_time(fade.get("out", "0s")),
        )
    for effect in options.get("effects", []):
        segment_obj.add_effect(
            enum_member(cc.AudioSceneEffectType, effect["name"]),
            ensure_float_list(effect.get("params")),
        )
    _apply_keyframes(segment_obj, segment.keyframes, audio=True)


def _make_text_style(options: Dict[str, Any]):
    cc = _cc()
    style = options.get("style", {}) or {}
    return cc.TextStyle(
        size=float(style.get("size", 8.0)),
        bold=bool(style.get("bold", False)),
        italic=bool(style.get("italic", False)),
        underline=bool(style.get("underline", False)),
        color=_rgb(style.get("color", "#FFFFFF")),
        alpha=float(style.get("alpha", 1.0)),
        align=int(style.get("align", 0)),
        vertical=bool(style.get("vertical", False)),
        letter_spacing=int(style.get("letter_spacing", 0)),
        line_spacing=int(style.get("line_spacing", 0)),
        auto_wrapping=bool(style.get("auto_wrapping", False)),
        max_line_width=float(style.get("max_line_width", 0.82)),
    )


def _make_text_border(options: Dict[str, Any]):
    cc = _cc()
    data = options.get("border") or {}
    if not data.get("enabled"):
        return None
    return cc.TextBorder(
        alpha=float(data.get("alpha", 1.0)),
        color=_rgb(data.get("color", "#000000")),
        width=float(data.get("width", 40)),
    )


def _make_text_background(options: Dict[str, Any]):
    cc = _cc()
    data = options.get("text_background") or {}
    if not data.get("enabled"):
        return None
    return cc.TextBackground(
        color=data.get("color", "#000000"),
        style=int(data.get("style", 1)),
        alpha=float(data.get("alpha", 1.0)),
        round_radius=float(data.get("round_radius", 0)),
        height=float(data.get("height", 0.14)),
        width=float(data.get("width", 0.14)),
        horizontal_offset=float(data.get("horizontal_offset", 0.5)),
        vertical_offset=float(data.get("vertical_offset", 0.5)),
    )


def _make_text_shadow(options: Dict[str, Any]):
    cc = _cc()
    data = options.get("shadow") or {}
    if not data.get("enabled"):
        return None
    return cc.TextShadow(
        alpha=float(data.get("alpha", 1.0)),
        color=_rgb(data.get("color", "#000000")),
        diffuse=float(data.get("diffuse", 15)),
        distance=float(data.get("distance", 5)),
        angle=float(data.get("angle", -45)),
    )


def _apply_text_modifiers(segment_obj, options: Dict[str, Any]) -> None:
    cc = _cc()
    animations = options.get("animations", [])
    order = {"intro": 0, "outro": 1, "loop": 2}
    for animation in sorted(animations, key=lambda item: order.get(item.get("family"), 9)):
        family = animation.get("family", "intro")
        enum_cls = {
            "intro": cc.TextIntro,
            "outro": cc.TextOutro,
            "loop": cc.TextLoopAnim,
        }[family]
        segment_obj.add_animation(
            enum_member(enum_cls, animation["name"]),
            parse_time(animation.get("duration") or "0.5s"),
        )
    bubble = options.get("bubble") or {}
    if bubble.get("enabled"):
        segment_obj.add_bubble(bubble.get("effect_id", ""), bubble.get("resource_id", ""))
    flower = options.get("flower_text") or {}
    if flower.get("enabled"):
        segment_obj.add_effect(flower.get("effect_id", ""))


def _make_text_segment_object(segment: SegmentModel):
    cc = _cc()
    options = segment.options
    font = enum_member(cc.FontType, options.get("font")) if options.get("font") else None
    obj = cc.TextSegment(
        options.get("text", segment.name or "Text"),
        cc.Timerange(segment.start_us, segment.duration_us),
        font=font,
        style=_make_text_style(options),
        clip_settings=make_clip(options),
        border=_make_text_border(options),
        background=_make_text_background(options),
        shadow=_make_text_shadow(options),
    )
    _apply_text_modifiers(obj, options)
    _apply_keyframes(obj, segment.keyframes)
    return obj


def _build_segment(
    script,
    track: TrackModel,
    segment: SegmentModel,
    materials: Dict[str, MaterialModel],
    material_cache: Dict[str, Any],
    object_cache: Dict[str, Any],
) -> None:
    cc = _cc()
    target = cc.Timerange(segment.start_us, segment.duration_us)
    options = segment.options
    if segment.kind == "video":
        model = materials[segment.material_id]
        material = material_cache.get(model.id)
        if material is None:
            material = make_material(model, options)
            material_cache[model.id] = material
        obj = cc.VideoSegment(
            material,
            target,
            source_timerange=_source_range(segment),
            speed=_optional_float(options.get("speed")),
            volume=float(options.get("volume", 1.0)),
            clip_settings=make_clip(options),
        )
        _apply_video_modifiers(obj, options)
        _apply_keyframes(obj, segment.keyframes)
        script.add_segment(obj, track.name)
        object_cache[segment.id] = obj
    elif segment.kind == "audio":
        model = materials[segment.material_id]
        material = material_cache.get(model.id)
        if material is None:
            material = make_material(model)
            material_cache[model.id] = material
        obj = cc.AudioSegment(
            material,
            target,
            source_timerange=_source_range(segment),
            speed=_optional_float(options.get("speed")),
            volume=float(options.get("volume", 1.0)),
        )
        _apply_audio_modifiers(obj, segment)
        script.add_segment(obj, track.name)
        object_cache[segment.id] = obj
    elif segment.kind == "text":
        obj = object_cache.get(segment.id) or _make_text_segment_object(segment)
        script.add_segment(obj, track.name)
        object_cache[segment.id] = obj
    elif segment.kind == "sticker":
        obj = cc.StickerSegment(
            options.get("resource_id", ""),
            target,
            clip_settings=make_clip(options),
        )
        _apply_keyframes(obj, segment.keyframes)
        script.add_segment(obj, track.name)
        object_cache[segment.id] = obj
    elif segment.kind == "effect":
        family = options.get("family", "scene")
        enum_cls = (
            cc.VideoSceneEffectType if family == "scene" else cc.VideoCharacterEffectType
        )
        script.add_effect(
            enum_member(enum_cls, options["name"]),
            target,
            track.name,
            params=ensure_float_list(options.get("params")),
        )
    elif segment.kind == "filter":
        script.add_filter(
            enum_member(cc.FilterType, options["name"]),
            target,
            track.name,
            intensity=float(options.get("intensity", 100)),
        )
    elif segment.kind == "subtitle":
        script.import_srt(
            options["srt_path"],
            track.name,
            time_offset=parse_time(options.get("time_offset", "0s")),
            style_reference=object_cache.get(options.get("style_reference_id", "")),
            text_style=_make_text_style(options),
            clip_settings=make_clip(options),
        )
    else:
        raise ValueError(f"Không hỗ trợ segment / Unsupported segment: {segment.kind}")


def materialize_project(project: ProjectModel):
    """Construct a ScriptFile entirely in memory for validation."""
    cc = _cc()
    errors = project.validate()
    if errors:
        raise ValueError("\n".join(errors))
    script = cc.ScriptFile(project.width, project.height, project.fps)
    return _populate_script(script, project)


def _populate_script(script, project: ProjectModel):
    cc = _cc()
    for track in project.tracks:
        kwargs = {
            "mute": track.mute,
            "relative_index": track.relative_index,
        }
        if track.absolute_index is not None:
            kwargs["absolute_index"] = track.absolute_index
            kwargs.pop("relative_index")
        script.add_track(enum_member(cc.TrackType, track.kind), track.name, **kwargs)
    materials = project.material_map
    cache: Dict[str, Any] = {}
    object_cache: Dict[str, Any] = {
        segment.id: _make_text_segment_object(segment)
        for track in project.tracks
        for segment in track.segments
        if segment.kind == "text"
    }
    for track in project.tracks:
        for segment in sorted(track.segments, key=lambda item: item.start_us):
            _build_segment(script, track, segment, materials, cache, object_cache)
    script.dumps()
    return script


def build_script(project: ProjectModel, overwrite: Optional[bool] = None) -> Path:
    """Create and save one CapCut draft using only existing core APIs."""
    cc = _cc()
    errors = project.validate()
    if errors:
        raise ValueError("\n".join(errors))
    draft_folder = cc.DraftFolder(project.draft_folder)
    allow_replace = project.overwrite if overwrite is None else overwrite
    target = Path(project.draft_folder) / project.draft_name
    if target.exists() and not allow_replace:
        raise FileExistsError(f"Draft '{project.draft_name}' đã tồn tại / already exists")
    # Exercise every core constructor before DraftFolder.create_draft can remove
    # an existing target.  This keeps invalid media/ranges/effects non-destructive.
    materialize_project(project)
    script = draft_folder.create_draft(
        project.draft_name,
        project.width,
        project.height,
        project.fps,
        allow_replace=allow_replace,
    )
    _populate_script(script, project)
    script.save()
    return target


def _optional_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    return float(value)


def _rgb(value: Any) -> tuple[float, float, float]:
    if isinstance(value, (tuple, list)) and len(value) == 3:
        vals = [float(item) for item in value]
        return tuple(item / 255 if item > 1 else item for item in vals)  # type: ignore[return-value]
    text = str(value).strip().lstrip("#")
    if len(text) != 6:
        raise ValueError(f"Màu không hợp lệ / Invalid color: {value}")
    return tuple(int(text[index : index + 2], 16) / 255 for index in (0, 2, 4))  # type: ignore[return-value]
