"""Atomic settings and recovery snapshots for the modern GUI."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional


def app_data_dir() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = root / "pycapcut-studio"
    path.mkdir(parents=True, exist_ok=True)
    return path


class RecoveryStore:
    def __init__(self) -> None:
        root = app_data_dir()
        self.path = root / "recovery-v1.json"
        self.settings_path = root / "settings-v1.json"

    def load(self) -> Optional[Dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            return None
        return data if data.get("schema_version") == 1 else None

    def save(self, project: Dict[str, Any], dirty: bool) -> None:
        self._atomic_write(
            self.path,
            {"schema_version": 1, "dirty": dirty, "project": project},
        )

    def discard(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def load_settings(self) -> Dict[str, Any]:
        try:
            return json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            return {"language": "vi"}

    def save_settings(self, settings: Dict[str, Any]) -> None:
        self._atomic_write(self.settings_path, settings)

    @staticmethod
    def _atomic_write(path: Path, data: Dict[str, Any]) -> None:
        handle, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
