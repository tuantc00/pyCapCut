"""Thread-safe background jobs exposed through HTTP and WebSocket."""

from __future__ import annotations

import asyncio
import queue
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobState:
    id: str
    kind: str
    status: str = "started"
    current: int = 0
    total: int = 0
    message: str = ""
    result: Any = None
    error: str = ""
    logs: list[Dict[str, Any]] = field(default_factory=list)
    updated_at: str = field(default_factory=_now)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "current": self.current,
            "total": self.total,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "logs": self.logs[-300:],
            "updated_at": self.updated_at,
        }


class WebJobContext:
    def __init__(self, manager: "JobManager", job_id: str, stop: threading.Event):
        self.manager = manager
        self.job_id = job_id
        self.stop_event = stop

    @property
    def stopped(self) -> bool:
        return self.stop_event.is_set()

    def progress(self, current: int, total: int, message: str = "") -> None:
        self.manager.update(
            self.job_id,
            "progress",
            current=current,
            total=total,
            message=message,
        )

    def log(self, message: str, level: str = "info") -> None:
        self.manager.log(self.job_id, message, level)


class JobManager:
    """One mutating CapCut job at a time, with reconnectable snapshots."""

    def __init__(self) -> None:
        self.jobs: Dict[str, JobState] = {}
        self.stops: Dict[str, threading.Event] = {}
        self.active_id: Optional[str] = None
        self.lock = threading.RLock()
        self.events: "queue.Queue[Dict[str, Any]]" = queue.Queue()

    def start(self, kind: str, callback: Callable[[WebJobContext], Any]) -> JobState:
        with self.lock:
            if self.active_id:
                active = self.jobs.get(self.active_id)
                if active and active.status in {"started", "progress", "stopping"}:
                    raise RuntimeError("Một tác vụ đang chạy / Another job is running")
            job = JobState(id=uuid.uuid4().hex, kind=kind)
            stop = threading.Event()
            self.jobs[job.id] = job
            self.stops[job.id] = stop
            self.active_id = job.id
            self._emit(job, "started")

        def target() -> None:
            context = WebJobContext(self, job.id, stop)
            try:
                result = callback(context)
            except Exception as exc:
                with self.lock:
                    job.status = "failed"
                    job.error = str(exc)
                    job.updated_at = _now()
                    job.logs.append(
                        {
                            "level": "error",
                            "message": traceback.format_exc(),
                            "time": job.updated_at,
                        }
                    )
                    self._emit(job, "failed")
            else:
                with self.lock:
                    job.status = "completed"
                    job.result = result
                    job.updated_at = _now()
                    self._emit(job, "completed")
            finally:
                with self.lock:
                    if self.active_id == job.id:
                        self.active_id = None

        threading.Thread(target=target, daemon=True, name=f"pycapcut-{kind}").start()
        return job

    def stop(self, job_id: str) -> JobState:
        with self.lock:
            job = self.jobs[job_id]
            self.stops[job_id].set()
            job.status = "stopping"
            job.updated_at = _now()
            self._emit(job, "stopping")
            return job

    def update(self, job_id: str, event: str, **values: Any) -> None:
        with self.lock:
            job = self.jobs[job_id]
            for key, value in values.items():
                setattr(job, key, value)
            job.status = event
            job.updated_at = _now()
            self._emit(job, event)

    def log(self, job_id: str, message: str, level: str) -> None:
        with self.lock:
            job = self.jobs[job_id]
            job.logs.append({"level": level, "message": message, "time": _now()})
            job.updated_at = _now()
            self._emit(job, "log", {"level": level, "message": message})

    def snapshots(self) -> list[Dict[str, Any]]:
        with self.lock:
            return [job.as_dict() for job in self.jobs.values()]

    def _emit(
        self,
        job: JobState,
        event: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.events.put({"event": event, "job": job.as_dict(), "payload": payload or {}})

    async def next_event(self) -> Dict[str, Any]:
        return await asyncio.to_thread(self.events.get)
