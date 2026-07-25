# Crosshair Overlay Implementation Plan

> **For agentic workers:** Execute tasks sequentially. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add a transparent click-through crosshair overlay (dot / +) togglable via Ctrl+9/Ctrl+0, visible only in sniper mode.

**Architecture:** tkinter Toplevel with `transparentcolor` + `Canvas` for drawing. All state in `app/crosshair.py` as module-level globals (existing codebase pattern). Integrated via `app/__main__.py` init, `app/profiles.py` mode-switch hooks, and shortcut polling in `engine/_plat_win32.py`.

**Tech Stack:** Python 3.x, tkinter, ctypes (WS_EX_TRANSPARENT).

## Global Constraints

- Zero new dependencies (tkinter + ctypes only)
- Follow existing codebase patterns: flat functions, module-level globals, no classes
- Crosshair appears only when mode == "sniper"
- Ctrl+9 cycles shape: dot → + → off → dot
- Ctrl+0 cycles color: merah → ijo → cyan → kuning
- Window: 32×32px, always-on-top, transparent background, click-through

---

### Task 1: Create `app/crosshair.py`

**Files:**
- Create: `app/crosshair.py`

**Interfaces:**
- Produces: `init(parent)`, `show()`, `hide()`, `cycle_shape()`, `cycle_color()`, `set_color(val)`, `set_shape(idx)`, `destroy()`

- [ ] **Write `app/crosshair.py`**

```python
# app/crosshair.py - Transparent click-through crosshair overlay (sniper mode only)
# ponytail: flat globals, tkinter + ctypes, zero deps

import ctypes
import tkinter as tk

# --- Constants ---
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
GWL_EXSTYLE = -20

# --- State ---
_shape = 0       # 0=dot, 1=cross, 2=off
_color_idx = 0
_colors = ["#ff0000", "#00ff00", "#00ffff", "#ffff00"]
_win = None
_canvas = None

COLORS = list(_colors)  # public read-only snapshot


def init(parent):
    """Create overlay Toplevel with canvas. Call once at startup."""
    global _win, _canvas
    _win = tk.Toplevel(parent)
    _win.overrideredirect(True)
    _win.attributes('-topmost', True)
    _win.attributes('-transparentcolor', 'black')
    _win.configure(bg='black')
    _win.geometry("32x32+{}+{}".format(
        (_win.winfo_screenwidth() - 32) // 2,
        (_win.winfo_screenheight() - 32) // 2
    ))

    # Click-through: WS_EX_TRANSPARENT | WS_EX_LAYERED
    hwnd = ctypes.c_void_p(_win.winfo_id())
    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED)

    _canvas = tk.Canvas(_win, width=32, height=32, bg='black', highlightthickness=0)
    _canvas.pack()

    _win.withdraw()  # hidden until sniper mode


def show():
    if _win and _shape != 2:
        _win.deiconify()


def hide():
    if _win:
        _win.withdraw()


def set_shape(idx):
    global _shape
    _shape = idx % 3
    if _shape == 2:
        hide()
    else:
        _redraw()
        show()


def cycle_shape():
    set_shape(_shape + 1)


def set_color(val):
    global _color_idx
    if isinstance(val, int):
        _color_idx = val % len(_colors)
    elif val in _colors:
        _color_idx = _colors.index(val)
    else:
        _colors.append(val)
        _color_idx = len(_colors) - 1
    if _shape != 2:
        _redraw()


def cycle_color():
    global _color_idx
    _color_idx = (_color_idx + 1) % len(_colors)
    if _shape != 2:
        _redraw()


def destroy():
    if _win:
        _win.destroy()


def _redraw():
    if not _canvas:
        return
    _canvas.delete("all")
    color = _colors[_color_idx]
    cx, cy = 16, 16
    if _shape == 0:  # dot
        r = 3
        _canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline='')
    elif _shape == 1:  # cross
        s = 10
        w = 2
        _canvas.create_line(cx - s, cy, cx + s, cy, fill=color, width=w)
        _canvas.create_line(cx, cy - s, cx, cy + s, fill=color, width=w)
```

- [ ] **Verify no syntax errors**

Run: `python -c "import ast; ast.parse(open('app/crosshair.py').read()); print('OK')"`

---

### Task 2: Wire crosshair init in `app/__main__.py`

**Files:**
- Modify: `app/__main__.py`

- [ ] **Add import and init call in `main()` + destroy on close**

```python
# After `from app import ui, toast, profiles, action_handlers` (line 11)
from app import crosshair
```

Inside `main()`, after `toast.init(root)` (line ~67):
```python
    # --- Init crosshair overlay (starts hidden, apply_profile shows if sniper) ---
    crosshair.init(root)
```

In `on_close()` function (line ~120), add before `root.destroy()`:
```python
        crosshair.destroy()
```

- [ ] **Verify import works**

Run: `python -c "from app.crosshair import init, show, hide; print('OK')"`

---

### Task 3: Show/hide on mode change in `app/profiles.py`

**Files:**
- Modify: `app/profiles.py`

- [ ] **Add import at top**

```python
from app import crosshair
```

- [ ] **Add show/hide in `on_mode_change()` after rebuild_delays (line ~320)**

```python
    # Show crosshair only in sniper mode
    if _state.get_config("mode") == "sniper":
        crosshair.show()
    else:
        crosshair.hide()
```

Also add to `apply_profile()` (line ~150), after `_sync_core()`:
```python
    # Sync crosshair visibility
    if p["mode"] == "sniper":
        crosshair.show()
    else:
        crosshair.hide()
```

- [ ] **Verify no import errors**

Run: `python -c "from app import crosshair; print('OK')"`

---

### Task 4: Add Ctrl+9 / Ctrl+0 shortcuts

**Files:**
- Modify: `engine/_plat_win32.py`
- Modify: `app/action_handlers.py`

- [ ] **Add VK codes in `engine/_plat_win32.py` near line 229**

```python
VK_9 = 0x39; VK_0 = 0x30
```

- [ ] **Add shortcut entries in `_shortcut_poll()` list (near line 238)**

```python
            (VK_9, "cycle_crosshair_shape", None),
            (VK_0, "cycle_crosshair_color", None),
```

- [ ] **Add dispatch for Ctrl+9 / Ctrl+0 in `_shortcut_poll()` before the `elif not ctrl:` block**

Insert after the `VK_OEM_PLUS/OEM_MINUS` branch (~line 264):
```python
                elif ctrl and vk in (VK_9, VK_0):
                    _state._queue_action(action_name, {})
```

- [ ] **Add import and handlers in `app/action_handlers.py`**

Add import at top:
```python
from app import crosshair
```

Add handler functions (after `_handle_show_guide`, before `ACTION_MAP`):
```python
def _handle_crosshair_shape(data):
    from engine import _state
    if _state.get_config("mode") != "sniper":
        return None
    crosshair.cycle_shape()
    return "Crosshair: " + ["Dot", "+", "Off"][crosshair._shape]

def _handle_crosshair_color(data):
    from engine import _state
    if _state.get_config("mode") != "sniper":
        return None
    crosshair.cycle_color()
    return "Color: " + crosshair._colors[crosshair._color_idx]
```

Add to `ACTION_MAP` (line ~241):
```python
    "cycle_crosshair_shape": _handle_crosshair_shape,
    "cycle_crosshair_color": _handle_crosshair_color,
```

- [ ] **Verify no errors**

Run: `python -c "from app.action_handlers import _handle_crosshair_shape, _handle_crosshair_color; print('OK')"`

---

### Task 5: Commit

- [ ] **Create commit**

```
git add app/crosshair.py app/__main__.py app/profiles.py app/action_handlers.py engine/_plat_win32.py
git commit -m "feat: add sniper crosshair overlay (dot/+, color, Ctrl+9/Ctrl+0)"
```
