"""Thread-safe background job runner for Tkinter."""

from __future__ import annotations

import queue
import threading
import traceback
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class JobEvent:
    kind: str
    payload: Any = None
    job_id: int = 0


class JobContext:
    def __init__(
        self,
        events: "queue.Queue[JobEvent]",
        stop_event: threading.Event,
        job_id: int,
    ):
        self.events = events
        self.stop_event = stop_event
        self.job_id = job_id

    @property
    def stopped(self) -> bool:
        return self.stop_event.is_set()

    def progress(self, current: int, total: int, message: str = "") -> None:
        self.events.put(JobEvent("progress", (current, total, message), self.job_id))

    def log(self, message: str, level: str = "info") -> None:
        self.events.put(JobEvent("log", (message, level), self.job_id))


class JobRunner:
    def __init__(self, root, poll_ms: int = 80):
        self.root = root
        self.poll_ms = poll_ms
        self.events: "queue.Queue[JobEvent]" = queue.Queue()
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.callbacks: dict[int, Callable[[JobEvent], None]] = {}
        self._next_job_id = 1
        self.root.after(self.poll_ms, self._poll)

    @property
    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def submit(
        self,
        func: Callable[[JobContext], Any],
        on_event: Callable[[JobEvent], None],
    ) -> bool:
        if self.running:
            return False
        self.stop_event.clear()
        job_id = self._next_job_id
        self._next_job_id += 1
        self.callbacks[job_id] = on_event

        def target() -> None:
            context = JobContext(self.events, self.stop_event, job_id)
            try:
                result = func(context)
            except Exception as exc:
                self.events.put(
                    JobEvent("error", (exc, traceback.format_exc()), job_id)
                )
            else:
                self.events.put(JobEvent("done", result, job_id))

        self.thread = threading.Thread(target=target, daemon=True)
        self.thread.start()
        return True

    def stop_after_current(self) -> None:
        self.stop_event.set()

    def _poll(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                callback = self.callbacks.get(event.job_id)
                if callback:
                    callback(event)
                if event.kind in ("done", "error"):
                    self.callbacks.pop(event.job_id, None)
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(self.poll_ms, self._poll)
