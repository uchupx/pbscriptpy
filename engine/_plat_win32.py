# engine/_plat_win32.py — All Windows API implementation
# Consolidates input_sim + hook + shortcuts from existing code
# Exports: click_left, click_right, mouse_move, press_key, _wait
#          start_listener, stop_listener, listener utils
#          start_shortcut_polling, stop_shortcut_polling

import ctypes
import ctypes.wintypes
import threading
import time
from engine import _state

# 1ms timer precision for sleeps
ctypes.windll.winmm.timeBeginPeriod(1)


# ====================================================================
# INPUT SIMULATION
# ====================================================================

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MOVE = 0x0001
KEYEVENTF_KEYUP = 0x0002

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long), ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_void_p),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", _INPUT_UNION)]

def _send(inp):
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def click_left(delay_ms=0):
    """Left mouse button click (platform-agnostic API)."""
    inp = INPUT(type=INPUT_MOUSE, union=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_LEFTDOWN)))
    _send(inp)
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)
    inp.union.mi.dwFlags = MOUSEEVENTF_LEFTUP
    _send(inp)

def click_right(delay_ms=0):
    """Right mouse button click (platform-agnostic API)."""
    inp = INPUT(type=INPUT_MOUSE, union=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_RIGHTDOWN)))
    _send(inp)
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)
    inp.union.mi.dwFlags = MOUSEEVENTF_RIGHTUP
    _send(inp)

def mouse_move(dx, dy):
    inp = INPUT(type=INPUT_MOUSE, union=_INPUT_UNION(mi=MOUSEINPUT(dx=dx, dy=dy, dwFlags=MOUSEEVENTF_MOVE)))
    _send(inp)

def press_key(char, hold_ms=0):
    """Press a key by character or VK code (platform-agnostic API).
    Accepts single char ('q', '3', '1') or int VK code for compat."""
    if isinstance(char, str) and len(char) == 1:
        vk = ord(char.upper())
    else:
        vk = int(char)
    inp = INPUT(type=INPUT_KEYBOARD, union=_INPUT_UNION(ki=KEYBDINPUT(wVk=vk)))
    _send(inp)
    if hold_ms > 0:
        time.sleep(hold_ms / 1000.0)
    inp.union.ki.dwFlags = KEYEVENTF_KEYUP
    _send(inp)

def _wait(delay_ms):
    """Sleep with early-exit check (macro cancel)."""
    if delay_ms <= 0:
        return
    for _ in range(max(1, delay_ms // 10)):
        if _state._stop_macro.is_set():
            break
        time.sleep(0.010)


# ====================================================================
# MOUSE HOOK (WH_MOUSE_LL)
# ====================================================================

WH_MOUSE_LL = 14
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002

class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", ctypes.c_long * 2), ("mouseData", ctypes.c_ulong),
        ("flags", ctypes.c_ulong), ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]

class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p), ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t), ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_ulong), ("pt", ctypes.c_long * 2),
    ]

HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_long, ctypes.POINTER(ctypes.c_long))

def _make_mouse_callback():
    def callback(nCode, wParam, lParam):
        try:
            if nCode != 0 or not _state._listening:
                return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)
            ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            xbtn = (ms.mouseData >> 16) & 0xFFFF if wParam in (WM_XBUTTONDOWN, WM_XBUTTONUP) else 0
            trigger = _state._cfg["trigger"]
            mode = _state._cfg["mode"]

            down = (trigger == "lclick" and wParam == WM_LBUTTONDOWN) or \
                   (trigger == "xbutton1" and wParam == WM_XBUTTONDOWN and xbtn == XBUTTON1) or \
                   (trigger == "xbutton2" and wParam == WM_XBUTTONDOWN and xbtn == XBUTTON2)
            up = (trigger == "lclick" and wParam == WM_LBUTTONUP) or \
                 (trigger == "xbutton1" and wParam == WM_XBUTTONUP and xbtn == XBUTTON1) or \
                 (trigger == "xbutton2" and wParam == WM_XBUTTONUP and xbtn == XBUTTON2)
            block = False

            if down and not _state._running and not _state._trigger_blocked:
                _state._running = True
                _state._trigger_held = True
                _state._stop_macro.clear()
                block = True
                if _state._status_callback:
                    _state._status_callback("Macro Running")
                from engine.macros import _run_sniper, _run_shotgun, _run_ar_smg  # lazy: avoid circular
                tgt = {"sniper": _run_sniper, "shotgun": _run_shotgun, "ar_smg": _run_ar_smg}.get(mode)
                if tgt:
                    _state._log(f"{mode.title()} triggered")
                    _state._macro_thread = threading.Thread(target=tgt, daemon=True)
                    _state._macro_thread.start()
            elif up and _state._running and mode == "ar_smg":
                _state._trigger_held = False
                block = True
            if block:
                return 1
        except Exception as e:
            _state._log(f"Hook error: {e}")
        return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)
    return callback

def start_listener():
    if _state._listening:
        return
    _state._listening = True
    _state._running = False
    _state._trigger_held = False
    _state._stop_macro.clear()
    cb = _make_mouse_callback()
    _state._hook_proc = HOOKPROC(cb)
    _state._hook = ctypes.windll.user32.SetWindowsHookExA(WH_MOUSE_LL, _state._hook_proc, None, 0)
    if not _state._hook:
        _state._log("Failed to set mouse hook!")
        _state._listening = False
        _state._hook_proc = None
        return
    def _msg_loop():
        _state._hook_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        msg = MSG()
        while _state._listening:
            ret = ctypes.windll.user32.GetMessageA(ctypes.byref(msg), None, 0, 0)
            if ret == 0:
                break
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageA(ctypes.byref(msg))
        _state._log("Hook thread exited")
    _state._hook_thread = threading.Thread(target=_msg_loop, daemon=True)
    _state._hook_thread.start()
    _state._log("Listener started")

def stop_listener():
    _state._listening = False
    _state._running = False
    _state._trigger_held = False
    _state._stop_macro.set()
    if _state._hook:
        ctypes.windll.user32.UnhookWindowsHookEx(_state._hook)
        _state._hook = None
    _state._hook_proc = None
    if _state._hook_thread_id:
        ctypes.windll.user32.PostThreadMessageA(_state._hook_thread_id, 0x0012, 0, 0)
    _state._log("Listener stopped")

def set_pb_hwnd(hwnd):
    _state._pb_hwnd = hwnd

def toggle_trigger_blocked():
    _state._trigger_blocked = not _state._trigger_blocked
    return _state._trigger_blocked

def is_trigger_blocked():
    return _state._trigger_blocked


# ====================================================================
# KEYBOARD SHORTCUT POLLING (GetAsyncKeyState)
# ====================================================================

VK_CONTROL = 0x11
VK_F1 = 0x70; VK_F2 = 0x71; VK_F5 = 0x74; VK_F6 = 0x75; VK_F7 = 0x76; VK_F8 = 0x77; VK_F12 = 0x7B
VK_1 = 0x31; VK_2 = 0x32; VK_3 = 0x33; VK_4 = 0x34; VK_9 = 0x39; VK_0 = 0x30
VK_OEM_PLUS = 0xBB; VK_OEM_MINUS = 0xBD; VK_N = 0x4E
SHORTCUT_POLL_MS = 50

def _key_down(vk):
    return (ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000) != 0

def _shortcut_poll():
    try:
        for vk, action_name, slot in [
            (VK_F1, "show_status", None), (VK_F2, "show_guide", None),
            (VK_F5, "cycle_profile", None), (VK_F6, "cycle_trigger", None),
            (VK_F7, "cycle_mode", None), (VK_F12, "toggle_listener", None),
            (VK_1, "select_delay_slot", 0), (VK_2, "select_delay_slot", 1),
            (VK_3, "select_delay_slot", 2), (VK_4, "select_delay_slot", 3),
            (VK_N, "add_profile", None),
            (VK_9, "cycle_crosshair_shape", None), (VK_0, "cycle_crosshair_color", None),
            (VK_OEM_PLUS, "delay_adjust", None), (VK_OEM_MINUS, "delay_adjust", None),
        ]:
            now_down = _key_down(vk)
            was_down = _state._shortcut_prev.get(vk, False)
            _state._shortcut_prev[vk] = now_down
            if now_down and not was_down:
                ctrl = _key_down(VK_CONTROL)
                data = {}
                if ctrl and vk == VK_N:
                    _state._queue_action("add_profile", {})
                elif ctrl and vk in (VK_1, VK_2, VK_3, VK_4):
                    data["slot"] = slot
                    _state._slot_selected_at = ctypes.windll.kernel32.GetTickCount()
                    _state._queue_action(action_name, data)
                elif ctrl and vk in (VK_OEM_PLUS, VK_OEM_MINUS):
                    now = ctypes.windll.kernel32.GetTickCount()
                    is_slot = _state._slot_selected_at and (now - _state._slot_selected_at) < 500
                    target = "delay_adjust" if is_slot else "recoil_adjust"
                    delta = 1 if vk == VK_OEM_PLUS else -1
                    _state._queue_action(target, {"delta": delta})
                elif ctrl and vk in (VK_9, VK_0):
                    _state._queue_action(action_name, {})
                elif not ctrl:
                    if action_name == "select_delay_slot" or vk == VK_N:
                        continue
                    if vk in (VK_OEM_PLUS, VK_OEM_MINUS):
                        _state._queue_action("delay_adjust", {"delta": 1 if vk == VK_OEM_PLUS else -1})
                    else:
                        _state._queue_action(action_name, {})
    except Exception as e:
        _state._log(f"Shortcut poll error: {e}")

def start_shortcut_polling():
    if _state._shortcut_running:
        return
    _state._shortcut_running = True
    _state._shortcut_prev = {}
    def _loop():
        while _state._shortcut_running:
            _shortcut_poll()
            time.sleep(SHORTCUT_POLL_MS / 1000.0)
    _state._shortcut_thread = threading.Thread(target=_loop, daemon=True)
    _state._shortcut_thread.start()
    _state._log("Shortcut polling started")

def stop_shortcut_polling():
    _state._shortcut_running = False
    _state._shortcut_thread = None
    _state._log("Shortcut polling stopped")
