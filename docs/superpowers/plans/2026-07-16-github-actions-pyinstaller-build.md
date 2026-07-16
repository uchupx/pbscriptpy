# GitHub Actions PyInstaller Build — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement task-by-task.

**Goal:** Add GitHub Actions workflow to build PB Script Macro into a single Windows `.exe` via PyInstaller.

**Architecture:** Single `windows-latest` runner, `requirements.txt` for deps, `build.yml` for CI, output uploaded as artifact.

**Tech Stack:** GitHub Actions, PyInstaller, NiceGUI, pywebview, Python 3.12

## Global Constraints

- Use `windows-latest` runner
- Use Python 3.12
- Single `.exe` via `--onefile`
- Must include `--collect-all nicegui` and `--add-data "nicegui;nicegui"`
- Use `--hide-console hide-early` not `--windowed`
- Output artifact named `PB-Script-Macro-Windows`

---

### Task 1: Update .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Read current .gitignore**

```
/__pycache__
/docs
```

- [ ] **Step 2: Change `/docs` to only ignore non-superpowers docs**

```
/__pycache__
/docs/*
!/docs/superpowers/
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: keep docs/superpowers/ tracked in gitignore"
```

---

### Task 2: Create requirements.txt

**Files:**
- Create: `requirements.txt`

- [ ] **Step 1: Write requirements.txt**

```
nicegui
pywebview
```

- [ ] **Step 2: Commit**

```bash
git add requirements.txt
git commit -m "chore: add requirements.txt for runtime deps"
```

---

### Task 3: Create GitHub Actions workflow

**Files:**
- Create: `.github/workflows/build.yml`

- [ ] **Step 1: Create `.github/workflows/` directory**

```bash
mkdir -p .github/workflows
```

- [ ] **Step 2: Write `build.yml`**

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
          pyinstaller --onefile --name "PB-Script-Macro" --collect-all nicegui --add-data "nicegui;nicegui" --hide-console hide-early main.py

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: PB-Script-Macro-Windows
          path: dist/PB-Script-Macro.exe
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/build.yml
git commit -m "ci: add GitHub Actions workflow for PyInstaller Windows EXE build"
```
