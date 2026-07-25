# engine/hook.py — Platform-aware listener dispatch
# Exports: start_listener, stop_listener, set_pb_hwnd, toggle_trigger_blocked, is_trigger_blocked

import sys

if sys.platform == "win32":
    from engine._plat_win32 import start_listener, stop_listener, set_pb_hwnd, toggle_trigger_blocked, is_trigger_blocked
else:
    from engine._plat_linux import start_listener, stop_listener, set_pb_hwnd, toggle_trigger_blocked, is_trigger_blocked
