# engine/hook.py - WH_MOUSE_LL global hook + listener lifecycle
# ponytail: single callback factory, no OOP tax

import ctypes
import ctypes.wintypes
import threading
from engine import _state
from engine.macros import _run_sniper, _run_shotgun, _run_ar_smg

# --- Constants ---
WH_MOUSE_LL = 14

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002


# --- Structures ---
class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", ctypes.c_long * 2),
        ("mouseData", ctypes.c_ulong),
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

HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_long, ctypes.POINTER(ctypes.c_long))


# --- Hook callback ---
def _make_mouse_callback():
    def callback(nCode, wParam, lParam):
        try:
            if nCode != 0 or not _state._listening:
                return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

            mouse_struct = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            xbtn = (mouse_struct.mouseData >> 16) & 0xFFFF if wParam in (WM_XBUTTONDOWN, WM_XBUTTONUP) else 0

            trigger = _state._cfg["trigger"]
            mode = _state._cfg["mode"]

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

            if is_trigger_down and not _state._running and not _state._trigger_blocked:
                _state._running = True
                _state._trigger_held = True
                _state._stop_macro.clear()
                block = True

                if _state._status_callback:
                    _state._status_callback("Macro Running")

                if mode == "sniper":
                    _state._log("Sniper triggered")
                    _state._macro_thread = threading.Thread(target=_run_sniper, daemon=True)
                    _state._macro_thread.start()
                elif mode == "shotgun":
                    _state._log("Shotgun triggered")
                    _state._macro_thread = threading.Thread(target=_run_shotgun, daemon=True)
                    _state._macro_thread.start()
                elif mode == "ar_smg":
                    _state._log("AR/SMG triggered (hold)")
                    _state._macro_thread = threading.Thread(target=_run_ar_smg, daemon=True)
                    _state._macro_thread.start()

            elif is_trigger_up and _state._running and mode == "ar_smg":
                _state._trigger_held = False
                block = True

            if block:
                return 1  # block input from reaching target window

        except Exception as e:
            _state._log(f"Hook error: {e}")

        return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

    return callback


# --- Public API ---
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
            if ret == 0:  # WM_QUIT
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
