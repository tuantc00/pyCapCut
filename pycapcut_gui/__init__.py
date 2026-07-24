"""React/WebView2 and legacy Tkinter orchestration for pyCapCut."""

__all__ = ["ProjectModel", "TrackModel", "SegmentModel", "build_script"]


def __getattr__(name):
    if name in {"ProjectModel", "TrackModel", "SegmentModel"}:
        from . import models

        return getattr(models, name)
    if name == "build_script":
        from .adapter import build_script

        return build_script
    raise AttributeError(name)
