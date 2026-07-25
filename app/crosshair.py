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
