"""FastAPI application serving React and pyCapCut GUI operations."""

from __future__ import annotations

import mimetypes
import logging
import os
import secrets
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import (
    Body,
    Cookie,
    FastAPI,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from .adapter import build_script, metadata_catalog
from .api_models import (
    ApiError,
    ProjectDTO,
    ValidationResult,
    dto_to_project,
    dump_model,
    project_to_dto,
)
from .job_manager import JobManager
from .models import MaterialModel, ProjectModel
from .recovery import RecoveryStore, app_data_dir
from .services import (
    BatchCreator,
    BatchOptions,
    DraftService,
    ExportQueue,
    TemplateSession,
    open_capcut,
    open_path,
)

LOGGER = logging.getLogger(__name__)


class StudioState:
    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token or secrets.token_urlsafe(32)
        self.project = ProjectModel()
        for kind in ("video", "audio", "text"):
            self.project.add_track(kind)
        self.recovery = RecoveryStore()
        self.jobs = JobManager()
        self.template: Optional[TemplateSession] = None
        self.batch_creator: Optional[BatchCreator] = None
        self.upload_dir = app_data_dir() / "imports"
        self.upload_dir.mkdir(parents=True, exist_ok=True)


def _error(code: str, vi: str, en: str, path: str = "") -> Dict[str, Any]:
    return dump_model(ApiError(error_code=code, message_vi=vi, message_en=en, path=path))


def _media_metadata(path: str, kind: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "duration_us": 5_000_000 if kind == "image" else 1_000_000
    }
    try:
        from pymediainfo import MediaInfo

        info = MediaInfo.parse(path)
        for track in info.tracks:
            if track.track_type in {"Video", "Image"}:
                if track.width:
                    result["width"] = int(track.width)
                if track.height:
                    result["height"] = int(track.height)
                if track.frame_rate:
                    result["fps"] = float(track.frame_rate)
                if track.codec_id or track.format:
                    result["codec"] = track.codec_id or track.format
            if track.duration:
                result["duration_us"] = int(float(track.duration) * 1000)
    except Exception:
        pass
    return result


def create_app(state: Optional[StudioState] = None, web_dir: Optional[Path] = None):
    state = state or StudioState()
    static_dir = web_dir or Path(__file__).with_name("web_dist")
    app = FastAPI(title="pyCapCut Studio", docs_url=None, redoc_url=None)
    app.state.studio = state

    def authorized(session: Optional[str]) -> None:
        if not session or not secrets.compare_digest(session, state.token):
            raise HTTPException(status_code=401, detail="Invalid GUI session")

    @app.exception_handler(Exception)
    async def unexpected_error(_request: Request, exc: Exception):
        LOGGER.error(
            "Unhandled GUI API error",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return JSONResponse(
            status_code=500,
            content=_error(
                "internal_error",
                f"Lỗi xử lý: {exc}",
                f"Processing error: {exc}",
            ),
        )

    @app.get("/auth")
    async def authenticate(token: str):
        if not secrets.compare_digest(token, state.token):
            raise HTTPException(status_code=401, detail="Invalid launch token")
        response = RedirectResponse("/")
        response.set_cookie(
            "pycapcut_session",
            state.token,
            httponly=True,
            samesite="strict",
        )
        return response

    @app.get("/api/v1/health")
    async def health(pycapcut_session: Optional[str] = Cookie(default=None)):
        authorized(pycapcut_session)
        return {"ok": True, "platform": sys.platform, "version": 1}

    @app.get("/api/v1/catalog")
    async def catalog(pycapcut_session: Optional[str] = Cookie(default=None)):
        authorized(pycapcut_session)
        return metadata_catalog()

    @app.get("/api/v1/project")
    async def get_project(pycapcut_session: Optional[str] = Cookie(default=None)):
        authorized(pycapcut_session)
        return dump_model(project_to_dto(state.project))

    @app.put("/api/v1/project")
    async def put_project(
        dto: ProjectDTO,
        dirty: bool = True,
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        state.project = dto_to_project(dto)
        state.recovery.save(dump_model(dto), dirty)
        return dump_model(project_to_dto(state.project))

    @app.post("/api/v1/project/validate")
    async def validate_project(
        dto: ProjectDTO,
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        messages = dto_to_project(dto).validate()
        errors = [
            ApiError(
                error_code="validation_error",
                message_vi=message.split(" / ")[0],
                message_en=message.split(" / ", 1)[-1],
            )
            for message in messages
        ]
        return dump_model(ValidationResult(valid=not errors, errors=errors))

    @app.post("/api/v1/project/create")
    async def create_project(
        dto: ProjectDTO,
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        project = dto_to_project(dto)
        errors = project.validate()
        if errors:
            return JSONResponse(
                status_code=422,
                content={
                    "error_code": "validation_failed",
                    "message_vi": errors[0].split(" / ")[0],
                    "message_en": errors[0].split(" / ", 1)[-1],
                    "errors": errors,
                },
            )
        path = build_script(project)
        state.project = project
        state.recovery.save(dump_model(dto), False)
        return {"path": str(path)}

    @app.get("/api/v1/recovery")
    async def recovery(pycapcut_session: Optional[str] = Cookie(default=None)):
        authorized(pycapcut_session)
        return state.recovery.load() or {"schema_version": 1, "dirty": False}

    @app.delete("/api/v1/recovery")
    async def discard_recovery(pycapcut_session: Optional[str] = Cookie(default=None)):
        authorized(pycapcut_session)
        state.recovery.discard()
        return {"ok": True}

    @app.get("/api/v1/settings")
    async def get_settings(pycapcut_session: Optional[str] = Cookie(default=None)):
        authorized(pycapcut_session)
        return state.recovery.load_settings()

    @app.put("/api/v1/settings")
    async def put_settings(
        values: Dict[str, Any] = Body(...),
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        state.recovery.save_settings(values)
        return values

    @app.post("/api/v1/media/register")
    async def register_media(
        values: Dict[str, Any] = Body(...),
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        path = os.path.abspath(str(values.get("path", "")))
        kind = str(values.get("kind", "video"))
        if not os.path.isfile(path):
            raise HTTPException(status_code=404, detail="Material not found")
        material = MaterialModel(kind=kind, path=path, name=os.path.basename(path))
        state.project.materials.append(material)
        data = dump_model(project_to_dto(state.project))["materials"][-1]
        data["metadata"] = _media_metadata(path, kind)
        return data

    @app.post("/api/v1/media/upload")
    async def upload_media(
        file: UploadFile = File(...),
        kind: str = "video",
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        original = Path(file.filename or "media").name
        target = state.upload_dir / f"{uuid.uuid4().hex}-{original}"
        with target.open("wb") as output:
            shutil.copyfileobj(file.file, output)
        material = MaterialModel(kind=kind, path=str(target), name=original)
        state.project.materials.append(material)
        data = dump_model(project_to_dto(state.project))["materials"][-1]
        data["metadata"] = _media_metadata(str(target), kind)
        return data

    @app.get("/api/v1/media/{material_id}/stream")
    async def stream_media(
        material_id: str,
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        material = next(
            (item for item in state.project.materials if item.id == material_id), None
        )
        if not material or not os.path.isfile(material.path):
            raise HTTPException(status_code=404, detail="Material not found")
        media_type = mimetypes.guess_type(material.path)[0] or "application/octet-stream"
        return FileResponse(material.path, media_type=media_type, filename=material.name)

    @app.get("/api/v1/drafts")
    async def list_drafts(
        folder: str,
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        return {"items": DraftService(folder).list()}

    @app.get("/api/v1/drafts/{name}/inspect")
    async def inspect_draft(
        name: str,
        folder: str,
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        return {"text": DraftService(folder).inspect(name)}

    @app.post("/api/v1/drafts/{name}/duplicate")
    async def duplicate_draft(
        name: str,
        values: Dict[str, Any] = Body(...),
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        path = DraftService(str(values["folder"])).duplicate(
            name,
            str(values["target"]),
            bool(values.get("overwrite", False)),
        )
        return {"path": str(path)}

    @app.delete("/api/v1/drafts/{name}")
    async def remove_draft(
        name: str,
        folder: str,
        confirm: str,
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        if confirm != name:
            raise HTTPException(status_code=400, detail="Confirmation does not match")
        DraftService(folder).remove(name)
        return {"ok": True}

    @app.post("/api/v1/template/load")
    async def template_load(
        values: Dict[str, Any] = Body(...),
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        state.template = TemplateSession(str(values["folder"]), str(values["name"]))
        return {
            "inspect": state.template.inspect(),
            "tracks": [
                {
                    "index": index,
                    "name": getattr(track, "name", f"track-{index}"),
                    "type": str(getattr(track, "track_type", "")),
                }
                for index, track in enumerate(state.template.imported_tracks)
            ],
        }

    @app.post("/api/v1/template/duplicate")
    async def template_duplicate(
        values: Dict[str, Any] = Body(...),
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        if not state.template:
            raise HTTPException(status_code=409, detail="Load a template first")
        state.template = state.template.duplicate(
            str(values["target"]), bool(values.get("overwrite", False))
        )
        return {"inspect": state.template.inspect()}

    @app.post("/api/v1/template/replace-material")
    async def template_replace_material(
        values: Dict[str, Any] = Body(...),
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        if not state.template:
            raise HTTPException(status_code=409, detail="Load a template first")
        if values.get("mode", "name") == "name":
            state.template.replace_by_name(
                str(values["material_name"]),
                str(values["path"]),
                str(values.get("kind", "video")),
                str(values.get("material_name_override", "")),
                bool(values.get("replace_crop", True)),
            )
        else:
            track = state.template.get_track(
                str(values.get("track_kind", "video")),
                str(values.get("track_name", "")),
                int(values.get("track_index", 0)),
            )
            state.template.replace_by_segment(
                track,
                int(values.get("segment_index", 0)),
                str(values["path"]),
                str(values.get("kind", "video")),
                str(values.get("source_start", "0s")),
                str(values.get("source_duration", "")),
                str(values.get("shrink", "cut_tail")),
                list(values.get("extend_modes", ["cut_material_tail"])),
            )
        return {"ok": True}

    @app.post("/api/v1/template/replace-text")
    async def template_replace_text(
        values: Dict[str, Any] = Body(...),
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        if not state.template:
            raise HTTPException(status_code=409, detail="Load a template first")
        track = state.template.get_track(
            "text",
            str(values.get("track_name", "")),
            int(values.get("track_index", 0)),
        )
        state.template.replace_text(
            track,
            int(values.get("segment_index", 0)),
            str(values.get("text", "")),
            bool(values.get("recalc_style", True)),
        )
        return {"ok": True}

    @app.post("/api/v1/template/import-track")
    async def template_import_track(
        values: Dict[str, Any] = Body(...),
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        if not state.template:
            raise HTTPException(status_code=409, detail="Load a target template first")
        source = TemplateSession(str(values["source_folder"]), str(values["source_name"]))
        source_track = source.get_track(
            str(values.get("track_kind", "video")),
            str(values.get("track_name", "")),
            int(values.get("track_index", 0)),
        )
        state.template.import_track(
            source,
            source_track,
            str(values.get("offset", "0s")),
            str(values.get("new_name", "")),
            int(values.get("relative_index", 0)),
        )
        return {"ok": True}

    @app.post("/api/v1/template/save")
    async def template_save(pycapcut_session: Optional[str] = Cookie(default=None)):
        authorized(pycapcut_session)
        if not state.template:
            raise HTTPException(status_code=409, detail="Load a template first")
        state.template.save()
        return {"ok": True}

    @app.post("/api/v1/jobs/batch")
    async def start_batch(
        values: Dict[str, Any] = Body(...),
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        state.batch_creator = BatchCreator(BatchOptions(**values))
        return state.jobs.start("batch", state.batch_creator.run).as_dict()

    @app.post("/api/v1/jobs/batch/resume")
    async def resume_batch(pycapcut_session: Optional[str] = Cookie(default=None)):
        authorized(pycapcut_session)
        if not state.batch_creator:
            raise HTTPException(status_code=409, detail="No batch session to resume")
        return state.jobs.start("batch", state.batch_creator.run).as_dict()

    @app.post("/api/v1/jobs/export")
    async def start_export(
        values: Dict[str, Any] = Body(...),
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        export_queue = ExportQueue(
            drafts=values.get("drafts", []),
            output_folder=str(values.get("output_folder", "")),
            resolution=str(values.get("resolution", "")),
            framerate=str(values.get("framerate", "")),
            timeout=float(values.get("timeout", 1200)),
        )
        return state.jobs.start("export", export_queue.run).as_dict()

    @app.get("/api/v1/jobs")
    async def jobs(pycapcut_session: Optional[str] = Cookie(default=None)):
        authorized(pycapcut_session)
        return {"items": state.jobs.snapshots()}

    @app.post("/api/v1/jobs/{job_id}/stop")
    async def stop_job(
        job_id: str,
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        return state.jobs.stop(job_id).as_dict()

    @app.websocket("/api/v1/jobs/ws")
    async def job_events(websocket: WebSocket):
        session = websocket.cookies.get("pycapcut_session")
        if not session or not secrets.compare_digest(session, state.token):
            await websocket.close(code=4401)
            return
        await websocket.accept()
        await websocket.send_json({"event": "snapshot", "jobs": state.jobs.snapshots()})
        try:
            while True:
                await websocket.send_json(await state.jobs.next_event())
        except WebSocketDisconnect:
            return

    @app.post("/api/v1/system/open-path")
    async def system_open_path(
        values: Dict[str, Any] = Body(...),
        pycapcut_session: Optional[str] = Cookie(default=None),
    ):
        authorized(pycapcut_session)
        open_path(str(values["path"]))
        return {"ok": True}

    @app.post("/api/v1/system/open-capcut")
    async def system_open_capcut(pycapcut_session: Optional[str] = Cookie(default=None)):
        authorized(pycapcut_session)
        return {"path": open_capcut()}

    @app.get("/{full_path:path}")
    async def frontend(full_path: str):
        candidate = static_dir / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        index = static_dir / "index.html"
        if index.is_file():
            return FileResponse(index)
        return Response(
            """
            <html><body style="font-family:Segoe UI;background:#0f1720;color:white;padding:40px">
            <h1>pyCapCut Studio frontend chưa được build</h1>
            <p>Run <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>.</p>
            </body></html>
            """,
            media_type="text/html",
            status_code=503,
        )

    return app
