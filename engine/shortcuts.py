# engine/shortcuts.py - Keyboard shortcut polling (GetAsyncKeyState)
# ponytail: flat poll loop, no class tax

import ctypes
import threading
import time
from engine import _state

# --- VK codes ---
VK_CONTROL = 0x11
VK_F1 = 0x70
VK_F2 = 0x71
VK_F5 = 0x74
VK_F6 = 0x75
VK_F7 = 0x76
VK_F8 = 0x77
VK_F12 = 0x7B
VK_1 = 0x31
VK_2 = 0x32
VK_3 = 0x33
VK_4 = 0x34
VK_OEM_PLUS = 0xBB    # =
VK_OEM_MINUS = 0xBD   # -
VK_N = 0x4E           # N

SHORTCUT_POLL_MS = 50


def _shortcut_poll():
    """Poll each shortcut key for rising edge (up→down transition)."""
    try:
        for vk, action_name, slot in [
            (VK_F1, "show_status", None),
            (VK_F2, "show_guide", None),
            (VK_F5, "cycle_profile", None),
            (VK_F6, "cycle_trigger", None),
            (VK_F7, "cycle_mode", None),
            (VK_F12, "toggle_listener", None),
            (VK_1, "select_delay_slot", 0),
            (VK_2, "select_delay_slot", 1),
            (VK_3, "select_delay_slot", 2),
            (VK_4, "select_delay_slot", 3),
            (VK_N, "add_profile", None),
            (VK_OEM_PLUS, "delay_adjust", None),
            (VK_OEM_MINUS, "delay_adjust", None),
        ]:
            now_down = (ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000) != 0
            was_down = _state._shortcut_prev.get(vk, False)
            _state._shortcut_prev[vk] = now_down

            if now_down and not was_down:
                ctrl_down = (ctypes.windll.user32.GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0
                data = {}

                if ctrl_down and vk == VK_N:
                    _state._log("Poll: Ctrl+N → add_profile")
                    _state._queue_action("add_profile", {})
                elif ctrl_down and vk in (VK_1, VK_2, VK_3, VK_4):
                    data["slot"] = slot
                    _state._slot_selected_at = ctypes.windll.kernel32.GetTickCount()
                    _state._log(f"Poll: Ctrl+{vk-0x30} → select_delay_slot slot={slot}")
                    _state._queue_action(action_name, data)
                elif ctrl_down and vk == VK_OEM_PLUS:
                    now = ctypes.windll.kernel32.GetTickCount()
                    if _state._slot_selected_at and now - _state._slot_selected_at < 500:
                        _state._log("Poll: Ctrl+= → delay_adjust +1 (slot mode)")
                        _state._queue_action("delay_adjust", {"delta": 1})
                    else:
                        _state._log("Poll: Ctrl+= → recoil_adjust +1")
                        _state._queue_action("recoil_adjust", {"delta": 1})
                elif ctrl_down and vk == VK_OEM_MINUS:
                    now = ctypes.windll.kernel32.GetTickCount()
                    if _state._slot_selected_at and now - _state._slot_selected_at < 500:
                        _state._log("Poll: Ctrl+- → delay_adjust -1 (slot mode)")
                        _state._queue_action("delay_adjust", {"delta": -1})
                    else:
                        _state._log("Poll: Ctrl+- → recoil_adjust -1")
                        _state._queue_action("recoil_adjust", {"delta": -1})
                elif not ctrl_down:
                    if action_name == "select_delay_slot" or vk == VK_N:
                        continue
                    if vk in (VK_OEM_PLUS, VK_OEM_MINUS):
                        data["delta"] = 1 if vk == VK_OEM_PLUS else -1
                        _state._log("Poll: =/- → delay_adjust delta={}".format(data["delta"]))
                        _state._queue_action(action_name, data)
                    else:
                        _state._log("Poll: vk={:02X} → {}".format(vk, action_name))
                        _state._queue_action(action_name, data)
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
