# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).parent.parent
web_dist = ROOT / "pycapcut_gui" / "web_dist"
if not (web_dist / "index.html").is_file():
    raise SystemExit("React frontend is missing. Run: cd frontend && npm run build")

datas = collect_data_files("pycapcut")
datas.append((str(web_dist), "pycapcut_gui/web_dist"))

a = Analysis(
    [str(ROOT / "gui.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "webview.platforms.edgechromium",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "cefpython3",
        "matplotlib",
        "IPython",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pyCapCutStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch="x86_64",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="pyCapCutStudio",
)
