# engine/_plat_linux.py — Linux implementation (ydotool + evdev)
# Exports same API as _plat_win32.py
# Input sim: ydotool via subprocess
# Key state: evdev via raw /dev/input reads

import struct
import subprocess
import threading
import time
import os
import fcntl
from engine import _state


# ====================================================================
# INPUT SIMULATION (ydotool via subprocess)
# ====================================================================

_YDOTOOL = None  # cached path
_YDOTOOLD_WARNED = False

def _find_ydotool():
    global _YDOTOOL
    if _YDOTOOL is not None:
        return _YDOTOOL
    for p in ["/usr/bin/ydotool", "/usr/local/bin/ydotool"]:
        if os.path.exists(p):
            _YDOTOOL = p
            return p
    _YDOTOOL = False
    return False

def _ydotool(args):
    exe = _find_ydotool()
    if not exe:
        global _YDOTOOLD_WARNED
        if not _YDOTOOLD_WARNED:
            _state._log("ydotool not found — install: sudo apt install ydotool")
            _YDOTOOLD_WARNED = True
        return
    try:
        subprocess.run([exe] + args, capture_output=True, timeout=2)
    except Exception as e:
        _state._log(f"ydotool error: {e}")

def click_left(delay_ms=0):
    _ydotool(["click", "1"])
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)

def click_right(delay_ms=0):
    _ydotool(["click", "3"])
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)

def mouse_move(dx, dy):
    _ydotool(["mousemove", str(dx), str(dy)])

def press_key(char, hold_ms=0):
    """Press a key by character or name. Accepts str ('q', '3') or int."""
    if isinstance(char, int):
        # Convert VK code to char for common keys
        char = chr(char).lower() if 0x20 <= char <= 0x7E else str(char)
    key_name = char.lower() if isinstance(char, str) else str(char)
    _ydotool(["key", f"{key_name}:1", f"{key_name}:0"])
    if hold_ms > 0:
        time.sleep(hold_ms / 1000.0)

def _wait(delay_ms):
    if delay_ms <= 0:
        return
    for _ in range(max(1, delay_ms // 10)):
        if _state._stop_macro.is_set():
            break
        time.sleep(0.010)


# ====================================================================
# HOOK (evdev polling-based trigger detection)
# ====================================================================

EV_KEY = 0x01
EV_SYN = 0x00
BTN_LEFT = 0x110
BTN_RIGHT = 0x111
BTN_SIDE = 0x113    # XButton1 equiv
BTN_EXTRA = 0x114   # XButton2 equiv

INPUT_EVENT_FMT = 'llHHI'
INPUT_EVENT_SIZE = struct.calcsize(INPUT_EVENT_FMT)

_kbd_fd = None
_mouse_fd = None
_hook_thread = None

def _find_evdev(pattern):
    """Find first readable event device matching glob pattern."""
    import glob as _glob
    for path in _glob.glob(pattern):
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            return fd, path
        except PermissionError:
            continue
    return None, None

def _open_devices():
    global _kbd_fd, _mouse_fd
    if _kbd_fd is None:
        _kbd_fd, _ = _find_evdev("/dev/input/by-path/*-kbd")
        if _kbd_fd is None:
            _kbd_fd, _ = _find_evdev("/dev/input/event*")
    if _mouse_fd is None:
        _mouse_fd, _ = _find_evdev("/dev/input/by-path/*-mouse")
        if _mouse_fd is None:
            _mouse_fd = _kbd_fd  # fallback: read from keyboard if no mouse dev found

def _evdev_read(fd):
    """Read one input_event from fd. Returns (type, code, value) or None."""
    if fd is None:
        return None
    try:
        data = os.read(fd, INPUT_EVENT_SIZE)
        if len(data) == INPUT_EVENT_SIZE:
            _, _, ev_type, code, value = struct.unpack(INPUT_EVENT_FMT, data)
            return (ev_type, code, value)
    except (BlockingIOError, OSError):
        pass
    return None

# Key state tracking
_key_state = {}

def _is_key_down(code):
    return _key_state.get(code, 0) != 0

def _hook_poll_loop():
    """Poll evdev for trigger mouse events in a thread."""
    _open_devices()
    while _state._listening:
        # Read mouse events (trigger detection)
        ev = _evdev_read(_mouse_fd)
        while ev is not None:
            etype, code, value = ev
            if etype == EV_KEY:
                _key_state[code] = value  # 0=up, 1=down, 2=hold
                _handle_trigger_event(code, value)
            ev = _evdev_read(_mouse_fd)

        # Drain keyboard events to keep key_state updated
        ev = _evdev_read(_kbd_fd)
        while ev is not None:
            etype, code, value = ev
            if etype == EV_KEY:
                _key_state[code] = value
            ev = _evdev_read(_kbd_fd)

        time.sleep(0.005)  # 5ms poll

def _handle_trigger_event(code, value):
    """Map evdev button code + trigger config → macro dispatch."""
    # Map trigger string → evdev code
    TRIGGER_MAP = {"lclick": BTN_LEFT, "xbutton1": BTN_SIDE, "xbutton2": BTN_EXTRA}
    trigger = _state._cfg.get("trigger", "xbutton1")
    target_code = TRIGGER_MAP.get(trigger, BTN_LEFT)

    if code != target_code:
        return

    mode = _state._cfg.get("mode", "sniper")

    if value == 1 and not _state._running and not _state._trigger_blocked:
        from engine.macros import _run_sniper, _run_shotgun, _run_ar_smg  # lazy: avoid circular
        _state._running = True
        _state._trigger_held = True
        _state._stop_macro.clear()
        if _state._status_callback:
            _state._status_callback("Macro Running")
        tgt = {"sniper": _run_sniper, "shotgun": _run_shotgun, "ar_smg": _run_ar_smg}.get(mode)
        if tgt:
            _state._log(f"{mode.title()} triggered")
            _state._macro_thread = threading.Thread(target=tgt, daemon=True)
            _state._macro_thread.start()

    elif value == 0 and _state._running and mode == "ar_smg":
        _state._trigger_held = False


# ====================================================================
# KEYBOARD SHORTCUT POLLING (evdev-based)
# ====================================================================

# Key code mappings (linux/input-event-codes.h)
KEY_LEFTSHIFT = 42; KEY_LEFTCTRL = 29; KEY_LEFTALT = 56
KEY_F1 = 59; KEY_F2 = 60; KEY_F5 = 63; KEY_F6 = 64; KEY_F7 = 65
KEY_F8 = 66; KEY_F12 = 88
KEY_1 = 2; KEY_2 = 3; KEY_3 = 4; KEY_4 = 5
KEY_N = 49
KEY_EQUAL = 13; KEY_MINUS = 12

SHORTCUT_POLL_MS = 50

_shortcut_running = False
_shortcut_thread = None
_shortcut_prev = {}

_VK_TO_CODE = {}  # Keep VK-style names for compat with shortcut_prev dict

# Map from "VK name" to evdev code
_KEYS = [
    (KEY_F1, "F1"), (KEY_F2, "F2"), (KEY_F5, "F5"), (KEY_F6, "F6"),
    (KEY_F7, "F7"), (KEY_F12, "F12"),
    (KEY_1, "1"), (KEY_2, "2"), (KEY_3, "3"), (KEY_4, "4"),
    (KEY_N, "N"), (KEY_EQUAL, "="), (KEY_MINUS, "-"),
]

_shortcut_list = [
    (KEY_F1, "show_status", None), (KEY_F2, "show_guide", None),
    (KEY_F5, "cycle_profile", None), (KEY_F6, "cycle_trigger", None),
    (KEY_F7, "cycle_mode", None), (KEY_F12, "toggle_listener", None),
    (KEY_1, "select_delay_slot", 0), (KEY_2, "select_delay_slot", 1),
    (KEY_3, "select_delay_slot", 2), (KEY_4, "select_delay_slot", 3),
    (KEY_N, "add_profile", None),
    (KEY_EQUAL, "delay_adjust", None), (KEY_MINUS, "delay_adjust", None),
]

def _shortcut_poll():
    try:
        for code, action_name, slot in _shortcut_list:
            now_down = _is_key_down(code)
            was_down = _shortcut_prev.get(code, False)
            _shortcut_prev[code] = now_down
            if now_down and not was_down:
                ctrl = _is_key_down(KEY_LEFTCTRL)
                if ctrl and code == KEY_N:
                    _state._queue_action("add_profile", {})
                elif ctrl and code in (KEY_1, KEY_2, KEY_3, KEY_4):
                    _state._queue_action(action_name, {"slot": slot})
                elif ctrl and code in (KEY_EQUAL, KEY_MINUS):
                    now = time.time_ns() // 1000000
                    is_slot = _state._slot_selected_at and (now - _state._slot_selected_at) < 500
                    target = "delay_adjust" if is_slot else "recoil_adjust"
                    delta = 1 if code == KEY_EQUAL else -1
                    _state._queue_action(target, {"delta": delta})
                elif not ctrl:
                    if action_name == "select_delay_slot" or code == KEY_N:
                        continue
                    if code in (KEY_EQUAL, KEY_MINUS):
                        _state._queue_action("delay_adjust", {"delta": 1 if code == KEY_EQUAL else -1})
                    else:
                        _state._queue_action(action_name, {})
    except Exception as e:
        _state._log(f"Shortcut poll error: {e}")

def start_shortcut_polling():
    global _shortcut_running, _shortcut_thread, _shortcut_prev
    if _shortcut_running:
        return
    _shortcut_running = True
    _shortcut_prev.clear()
    _state._log("Shortcut polling started")
    # Open evdev for key state if not already
    _open_devices()
    def _loop():
        while _shortcut_running:
            # Drain events to keep key_state fresh
            ev = _evdev_read(_kbd_fd)
            while ev is not None:
                etype, code, value = ev
                if etype == EV_KEY:
                    _key_state[code] = value
                ev = _evdev_read(_kbd_fd)
            _shortcut_poll()
            time.sleep(SHORTCUT_POLL_MS / 1000.0)
    _shortcut_thread = threading.Thread(target=_loop, daemon=True)
    _shortcut_thread.start()

def stop_shortcut_polling():
    global _shortcut_running, _shortcut_thread
    _shortcut_running = False
    _shortcut_thread = None
    _state._log("Shortcut polling stopped")


# ====================================================================
# PUBLIC LISTENER API (shared with _plat_win32)
# ====================================================================

def start_listener():
    if _state._listening:
        return
    _state._listening = True
    _state._running = False
    _state._trigger_held = False
    _state._stop_macro.clear()
    _state._log("Listener started (evdev polling)")
    global _hook_thread
    _hook_thread = threading.Thread(target=_hook_poll_loop, daemon=True)
    _hook_thread.start()

def stop_listener():
    _state._listening = False
    _state._running = False
    _state._trigger_held = False
    _state._stop_macro.set()
    _state._log("Listener stopped")

def set_pb_hwnd(hwnd):
    pass  # no-op on Linux

def toggle_trigger_blocked():
    _state._trigger_blocked = not _state._trigger_blocked
    return _state._trigger_blocked

def is_trigger_blocked():
    return _state._trigger_blocked
