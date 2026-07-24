# pyCapCut Studio GUI

## Linux development/demo

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-gui.txt
cd frontend
npm install
npm run build
cd ..
python gui.py --browser
```

The Linux browser mode can create CapCut draft files and preview raw media.
Windows-only CapCut automation is disabled on Linux.

## Windows development

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-gui.txt
cd frontend
npm install
npm run build
cd ..
python gui.py
```

Use `python gui.py --legacy` while the temporary Tkinter fallback is needed.

## Build the Windows installer

Install Node.js, Python x64 and Inno Setup 6, then make `iscc.exe` available
on `PATH` and run:

```powershell
.\packaging\build_windows.ps1
```

The output is `packaging\output\pyCapCut-Studio-Setup.exe`. It installs per
user and downloads the Evergreen WebView2 bootstrapper only when the runtime
is missing.
