# core.py - Hook, SendInput, macro engine
# ponytail: single file, no OOP tax

import ctypes
import ctypes.wintypes
import threading
import time
import traceback
from config import DEFAULT

# --- Constants ---
WH_MOUSE_LL = 14
WH_KEYBOARD_LL = 13

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MOVE = 0x0001

KEYEVENTF_KEYUP = 0x0002

# Common VK names for logging
VK_NAMES = {
    0x01: "LMB", 0x02: "RMB", 0x03: "CANCEL", 0x04: "MMB",
    0x05: "XB1", 0x06: "XB2",
    0x08: "BKSP", 0x09: "TAB", 0x0C: "CLR", 0x0D: "ENTER",
    0x10: "SHIFT", 0x11: "CTRL", 0x12: "ALT", 0x13: "PAUSE",
    0x14: "CAPS", 0x1B: "ESC",
    0x20: "SPACE", 0x21: "PGUP", 0x22: "PGDN", 0x23: "END",
    0x24: "HOME", 0x25: "LEFT", 0x26: "UP", 0x27: "RIGHT", 0x28: "DOWN",
    0x2D: "INS", 0x2E: "DEL",
    0x30: "0", 0x31: "1", 0x32: "2", 0x33: "3", 0x34: "4",
    0x35: "5", 0x36: "6", 0x37: "7", 0x38: "8", 0x39: "9",
    0x41: "A", 0x42: "B", 0x43: "C", 0x44: "D", 0x45: "E",
    0x46: "F", 0x47: "G", 0x48: "H", 0x49: "I", 0x4A: "J",
    0x4B: "K", 0x4C: "L", 0x4D: "M", 0x4E: "N", 0x4F: "O",
    0x50: "P", 0x51: "Q", 0x52: "R", 0x53: "S", 0x54: "T",
    0x55: "U", 0x56: "V", 0x57: "W", 0x58: "X", 0x59: "Y", 0x5A: "Z",
    0x5B: "WIN", 0x5C: "WIN", 0x5D: "APPS",
    0x60: "NP0", 0x61: "NP1", 0x62: "NP2", 0x63: "NP3",
    0x64: "NP4", 0x65: "NP5", 0x66: "NP6", 0x67: "NP7",
    0x68: "NP8", 0x69: "NP9",
    0x70: "F1", 0x71: "F2", 0x72: "F3", 0x73: "F4",
    0x74: "F5", 0x75: "F6", 0x76: "F7", 0x77: "F8",
    0x78: "F9", 0x79: "F10", 0x7A: "F11", 0x7B: "F12",
    0x90: "NUMLK", 0x91: "SCRLK",
    0xA0: "LSHIFT", 0xA1: "RSHIFT", 0xA2: "LCTRL", 0xA3: "RCTRL",
    0xA4: "LALT", 0xA5: "RALT",
}

# --- Structures ---
class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", ctypes.c_long * 2),
        ("mouseData", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.c_ulong),
        ("scanCode", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]

class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_ulong),
        ("pt", ctypes.c_long * 2),
    ]

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

# --- State ---
_listening = False
_running = False
_trigger_held = False
_stop_macro = threading.Event()
_cfg = dict(DEFAULT)
_hook = None
_hook_proc = None       # FIX: keep HOOKPROC alive so Windows doesn't crash
_hook_thread = None
_hook_thread_id = None  # FIX: store hook thread ID for wake-up
_log_callback = None
_status_callback = None
_macro_thread = None
# Keyboard hook state
_kb_hook = None
_kb_hook_proc = None

# --- Input Simulation ---

def mouse_down(flags):
    inp = INPUT(type=INPUT_MOUSE, union=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=flags)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def mouse_up(flags):
    inp = INPUT(type=INPUT_MOUSE, union=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=flags)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def mouse_click(flags_down, flags_up, delay_ms):
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
    """Sleep with early exit check."""
    if delay_ms <= 0:
        return
    for _ in range(max(1, delay_ms // 10)):
        if _stop_macro.is_set():
            break
        time.sleep(0.010)

# --- Macro Sequences ---

def _do_switch(method, delay_ms):
    """QQ: Q→delay→Q | 31: 3→delay→1. Each key down→hold→up."""
    hold = _cfg.get("key_hold_delay", 30)
    if method == "qq":
        key_press(0x51, hold)  # Q down→hold→up
        _wait(delay_ms)
        key_press(0x51, hold)  # Q down→hold→up
    else:  # "31"
        key_press(0x33, hold)  # 3 down→hold→up
        _wait(delay_ms)
        key_press(0x31, hold)  # 1 down→hold→up

def _run_sniper():
    """RClick→delay0→LClick→delay1→RClick→delay2→Switch→delay3"""
    try:
        delays = _cfg.get("sniper_delays", [50, 50, 50, 50])
        method = _cfg.get("switch_method", "qq")
        mouse_click(MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP, 15)
        if _stop_macro.is_set(): return
        _wait(delays[0])
        mouse_click(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, 15)
        if _stop_macro.is_set(): return
        _wait(delays[1])
        mouse_click(MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP, 15)
        if _stop_macro.is_set(): return
        _wait(delays[2])
        _do_switch(method, delays[3])
    except Exception as e:
        _log(f"Sniper error: {e}")
    finally:
        _finish_macro()

def _run_shotgun():
    """LClick→delay0→Switch→delay1"""
    try:
        delays = _cfg.get("shotgun_delays", [50, 50])
        method = _cfg.get("switch_method", "qq")
        mouse_click(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, 15)
        if _stop_macro.is_set(): return
        _wait(delays[0])
        _do_switch(method, delays[1])
    except Exception as e:
        _log(f"Shotgun error: {e}")
    finally:
        _finish_macro()

def _run_ar_smg():
    """Hold loop: LClick → delay → LClick → delay ..."""
    try:
        delay = _cfg.get("ar_smg_delay", 80)
        recoil = _cfg.get("recoil", True)
        recoil_amt = _cfg.get("recoil_amount", 4)
        _log("AR/SMG loop started")
        while _trigger_held and not _stop_macro.is_set():
            mouse_click(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, 15)
            if recoil and recoil_amt:
                mouse_move(0, recoil_amt)
            if _stop_macro.is_set():
                break
            _wait(delay)
        _log("AR/SMG loop stopped")
    except Exception as e:
        _log(f"AR/SMG error: {e}")
    finally:
        _finish_macro()

def _finish_macro():
    global _running
    _running = False
    _trigger_held = False
    if _status_callback:
        _status_callback("Idle")

# --- Hook Callback ---
HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_long, ctypes.POINTER(ctypes.c_long))

def _make_mouse_callback():
    def callback(nCode, wParam, lParam):
        global _trigger_held, _running, _macro_thread

        try:
            if nCode != 0 or not _listening:
                return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

            # Log all mouse events for debugging
            mouse_struct = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            xbtn = (mouse_struct.mouseData >> 16) & 0xFFFF if wParam in (WM_XBUTTONDOWN, WM_XBUTTONUP) else 0

            if wParam == WM_LBUTTONDOWN:
                _log("Mouse: L-Click DOWN")
            elif wParam == WM_RBUTTONDOWN:
                _log("Mouse: R-Click DOWN")
            elif wParam == WM_MBUTTONDOWN:
                _log("Mouse: M-Click DOWN")
            elif wParam == WM_XBUTTONDOWN and xbtn == XBUTTON1:
                _log("Mouse: X-Button Forward DOWN")
            elif wParam == WM_XBUTTONDOWN and xbtn == XBUTTON2:
                _log("Mouse: X-Button Backward DOWN")

            trigger = _cfg["trigger"]
            mode = _cfg["mode"]

            # Detect trigger press
            is_trigger_down = False
            if trigger == "lclick" and wParam == WM_LBUTTONDOWN:
                is_trigger_down = True
            elif trigger == "xbutton1" and wParam == WM_XBUTTONDOWN and xbtn == XBUTTON1:
                is_trigger_down = True
            elif trigger == "xbutton2" and wParam == WM_XBUTTONDOWN and xbtn == XBUTTON2:
                is_trigger_down = True

            # Detect trigger release
            is_trigger_up = False
            if trigger == "lclick" and wParam == WM_LBUTTONUP:
                is_trigger_up = True
            elif trigger == "xbutton1" and wParam == WM_XBUTTONUP and xbtn == XBUTTON1:
                is_trigger_up = True
            elif trigger == "xbutton2" and wParam == WM_XBUTTONUP and xbtn == XBUTTON2:
                is_trigger_up = True

            block = False

            if is_trigger_down and not _running:
                _running = True
                _trigger_held = True
                _stop_macro.clear()
                block = True

                if _status_callback:
                    _status_callback("Macro Running")

                if mode == "sniper":
                    _log("Sniper triggered")
                    _macro_thread = threading.Thread(target=_run_sniper, daemon=True)
                    _macro_thread.start()
                elif mode == "shotgun":
                    _log("Shotgun triggered")
                    _macro_thread = threading.Thread(target=_run_shotgun, daemon=True)
                    _macro_thread.start()
                elif mode == "ar_smg":
                    _log("AR/SMG triggered (hold)")
                    _macro_thread = threading.Thread(target=_run_ar_smg, daemon=True)
                    _macro_thread.start()

            elif is_trigger_up and _running and mode == "ar_smg":
                _trigger_held = False
                block = True

            if block:
                return 1  # block input

        except Exception as e:
            _log(f"Hook error: {e}")

        return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

    return callback

# --- Keyboard Hook ---

def _make_kb_callback():
    def callback(nCode, wParam, lParam):
        try:
            if nCode != 0 or not _listening:
                return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = kb.vkCode
            name = VK_NAMES.get(vk, f"VK_{hex(vk)}")
            if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                _log(f"Keyboard: {name} DOWN")
            elif wParam == WM_KEYUP:
                _log(f"Keyboard: {name} UP")
        except Exception as e:
            _log(f"KB hook error: {e}")

        return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)
    return callback

# --- Public API ---
def set_config(key, value):
    _cfg[key] = value

def get_config(key):
    return _cfg.get(key)

def set_log_callback(cb):
    global _log_callback
    _log_callback = cb

def set_status_callback(cb):
    global _status_callback
    _status_callback = cb

def _log(msg):
    if _log_callback:
        _log_callback(msg)

def start_listener():
    global _listening, _hook, _hook_proc, _hook_thread, _hook_thread_id
    global _running, _trigger_held
    global _kb_hook, _kb_hook_proc
    if _listening:
        return
    _listening = True
    _running = False
    _trigger_held = False
    _stop_macro.clear()

    # FIX: keep HOOKPROC alive as module-level global
    cb = _make_mouse_callback()
    _hook_proc = HOOKPROC(cb)

    _hook = ctypes.windll.user32.SetWindowsHookExA(WH_MOUSE_LL, _hook_proc, None, 0)
    if not _hook:
        _log("Failed to set mouse hook!")
        _listening = False
        _hook_proc = None
        return

    # Keyboard hook
    kb_cb = _make_kb_callback()
    _kb_hook_proc = HOOKPROC(kb_cb)
    _kb_hook = ctypes.windll.user32.SetWindowsHookExA(WH_KEYBOARD_LL, _kb_hook_proc, None, 0)
    if not _kb_hook:
        _log("Failed to set keyboard hook!")
        # Continue anyway, mouse only
        _kb_hook_proc = None

    def _msg_loop():
        global _hook_thread_id
        _hook_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        msg = MSG()
        while _listening:
            ret = ctypes.windll.user32.GetMessageA(ctypes.byref(msg), None, 0, 0)
            if ret == 0:  # WM_QUIT
                break
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageA(ctypes.byref(msg))
        _log("Hook thread exited")

    _hook_thread = threading.Thread(target=_msg_loop, daemon=True)
    _hook_thread.start()
    _log("Listener started")

def stop_listener():
    global _listening, _running, _trigger_held, _hook, _hook_proc
    global _kb_hook, _kb_hook_proc
    _listening = False
    _running = False
    _trigger_held = False
    _stop_macro.set()

    if _hook:
        ctypes.windll.user32.UnhookWindowsHookEx(_hook)
        _hook = None
    _hook_proc = None

    if _kb_hook:
        ctypes.windll.user32.UnhookWindowsHookEx(_kb_hook)
        _kb_hook = None
    _kb_hook_proc = None

    # FIX: wake up the hook thread's message loop with WM_QUIT
    if _hook_thread_id:
        ctypes.windll.user32.PostThreadMessageA(_hook_thread_id, 0x0012, 0, 0)

    _log("Listener stopped")