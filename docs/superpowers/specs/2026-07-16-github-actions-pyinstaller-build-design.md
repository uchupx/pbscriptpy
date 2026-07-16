# GitHub Actions PyInstaller Build — Design Doc

**Date:** 2026-07-16
**Project:** PB Script Macro (Python)
**Status:** Approved

## Overview

Build PB Script Macro Python project into a single Windows `.exe` file using GitHub Actions and PyInstaller. Output uploaded as a downloadable artifact.

## Objective

Automate Windows EXE builds from the Python codebase so the user can download a ready-to-run binary without needing Python installed.

## Build Environment

- **Runner:** `windows-latest` (GitHub-hosted Windows Server)
- **Python:** 3.12
- **Trigger:** `workflow_dispatch` (manual) + push to `main` branch

## Dependencies

The project depends on:

- `nicegui` — Web-based GUI framework (renders via native pywebview window)
- `pywebview` — Native OS window for NiceGUI
- `ctypes` — stdlib (Windows API calls)
- `threading`, `json`, `os`, `time`, `atexit` — stdlib

PyInstaller dependencies (build-time only):

- `pyinstaller`

A `requirements.txt` will be added to the project root:
```
nicegui
pywebview
```

## PyInstaller Flags

```
pyinstaller --onefile ^
  --name "PB-Script-Macro" ^
  --collect-all nicegui ^
  --hide-console hide-early ^
  main.py
```

### Flag Rationale

| Flag | Reason |
|------|--------|
| `--onefile` | Single `.exe` output for easy distribution |
| `--name "PB-Script-Macro"` | Descriptive executable name |
| `--collect-all nicegui` | Bundle all NiceGUI submodules + data (required for frozen app) |
| `--hide-console hide-early` | Hide console window on startup (alternative to `--windowed` which breaks NiceGUI native mode) |
| `main.py` | Entry point |

## Workflow Design

File: `.github/workflows/build.yml`

```yaml
name: Build Windows EXE

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  build:
    runs-on: windows-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          python -m pip install -U pip
          pip install -r requirements.txt
          pip install pyinstaller

      - name: Build with PyInstaller
        run: |
          pyinstaller --onefile --name "PB-Script-Macro" --collect-all nicegui --hide-console hide-early main.py

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: PB-Script-Macro-Windows
          path: dist/PB-Script-Macro.exe
```

## Output

- **Artifact name:** `PB-Script-Macro-Windows`
- **File:** `PB-Script-Macro.exe` (~20-40MB depending on deps)
- **Download:** GitHub Actions run page → Artifacts section

## Limitations

- The `.exe` must be run as Administrator (Windows hooks require it)
- Antivirus may flag PyInstaller-packaged EXEs as false positives
- NiceGUI native mode with `--hide-console` is preferred over `--windowed` (known upstream issue)

## Files to Create/Modify

1. `requirements.txt` — new file, lists runtime dependencies
2. `.github/workflows/build.yml` — new file, GitHub Actions workflow
3. `.gitignore` — ensure `dist/`, `build/`, `*.spec` are ignored (already has `.gitignore` — verify)
