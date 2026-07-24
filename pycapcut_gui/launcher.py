"""Modern React/WebView2 launcher with browser and legacy fallbacks."""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser
from typing import Optional

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_until_ready(port: int, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("GUI server did not start")


def _run_server(app, port: int):
    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Thiếu FastAPI/Uvicorn. Chạy: pip install -r requirements-gui.txt"
        ) from exc
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
        )
    )
    thread = threading.Thread(target=server.run, daemon=True, name="pycapcut-api")
    thread.start()
    _wait_until_ready(port)
    return server, thread


def _legacy() -> None:
    try:
        from .app import main as legacy_main
    except ModuleNotFoundError as exc:
        if exc.name == "tkinter":
            raise SystemExit("Tkinter chưa được cài / Tkinter is not installed") from exc
        raise
    legacy_main()


class NativeBridge:
    """Native dialogs only; all business operations remain in FastAPI."""

    def select_files(self, file_types=None):
        import webview

        result = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=tuple(
                file_types
                or ("Media (*.mp4;*.mov;*.mkv;*.mp3;*.wav;*.png;*.jpg)",)
            ),
        )
        return list(result or [])

    def select_folder(self):
        import webview

        result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
        return result[0] if result else ""


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="pyCapCut Studio")
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--legacy", action="store_true")
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args(argv)

    if args.legacy:
        _legacy()
        return

    try:
        from .server import StudioState, create_app
    except ModuleNotFoundError as exc:
        if exc.name in {"pydantic", "fastapi"}:
            raise SystemExit(
                "Thiếu dependency GUI. Chạy: pip install -r requirements-gui.txt"
            ) from exc
        raise
    state = StudioState()
    app = create_app(state)
    port = args.port or _free_port()
    server, thread = _run_server(app, port)
    url = f"http://127.0.0.1:{port}/auth?token={state.token}"
    browser_mode = args.browser or sys.platform != "win32"

    if browser_mode:
        print(f"pyCapCut Studio: {url}")
        if not args.no_open:
            webbrowser.open(url)
        try:
            thread.join()
        except KeyboardInterrupt:
            server.should_exit = True
        return

    try:
        import webview
    except ModuleNotFoundError as exc:
        server.should_exit = True
        raise SystemExit(
            "Thiếu pywebview. Chạy: pip install -r requirements-gui.txt"
        ) from exc
    webview.create_window(
        "pyCapCut Studio",
        url,
        width=1440,
        height=900,
        min_size=(1280, 720),
        js_api=NativeBridge(),
        background_color="#0f1720",
    )
    try:
        webview.start(gui="edgechromium", debug=False)
    finally:
        server.should_exit = True
