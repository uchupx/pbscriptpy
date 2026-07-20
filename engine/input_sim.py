# engine/input_sim.py - SendInput wrappers
# ponytail: pure functions, no shared state except _stop_macro for _wait

import ctypes
import time
from engine import _state

# --- Constants ---
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MOVE = 0x0001

KEYEVENTF_KEYUP = 0x0002


# --- Structures ---
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", _INPUT_UNION),
    ]


# --- Functions ---

def mouse_down(flags):
    inp = INPUT(type=INPUT_MOUSE, union=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=flags)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def mouse_up(flags):
    inp = INPUT(type=INPUT_MOUSE, union=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=flags)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def mouse_click(flags_down, flags_up, delay_ms=0):
    mouse_down(flags_down)
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)
    mouse_up(flags_up)

def mouse_move(dx, dy):
    inp = INPUT(type=INPUT_MOUSE, union=_INPUT_UNION(mi=MOUSEINPUT(dx=dx, dy=dy, dwFlags=MOUSEEVENTF_MOVE)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def key_press(vk, hold_ms=0):
    inp_down = INPUT(type=INPUT_KEYBOARD, union=_INPUT_UNION(ki=KEYBDINPUT(wVk=vk)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(inp_down))
    if hold_ms > 0:
        time.sleep(hold_ms / 1000.0)
    inp_up = INPUT(type=INPUT_KEYBOARD, union=_INPUT_UNION(ki=KEYBDINPUT(wVk=vk, dwFlags=KEYEVENTF_KEYUP)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(inp_up))

def _wait(delay_ms):
    """Sleep with early-exit check (stops immediately when macro is cancelled)."""
    if delay_ms <= 0:
        return
    for _ in range(max(1, delay_ms // 10)):
        if _state._stop_macro.is_set():
            break
        time.sleep(0.010)
