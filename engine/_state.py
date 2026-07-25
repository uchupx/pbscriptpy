# engine/_state.py - Shared mutable state (module-level globals)
# ponytail: flat globals, no class tax. Single source of truth for engine-wide state.

import threading
from engine.config import DEFAULT

# --- Listener state ---
_listening = False

# --- Macro state ---
_running = False
_trigger_held = False
_stop_macro = threading.Event()
_cfg = dict(DEFAULT)
_macro_thread = None

# --- Mouse hook state ---
_hook = None
_hook_proc = None
_hook_thread = None
_hook_thread_id = None
_pb_hwnd = None
_trigger_blocked = False

# --- Callbacks ---
_log_callback = None
_status_callback = None
_action_callback = None

# --- Shortcut polling state ---
_shortcut_running = False
_shortcut_thread = None
_shortcut_prev = {}
_slot_selected_at = 0


# ===== Public API =====

def set_config(key, value):
    _cfg[key] = value

def get_config(key):
    return _cfg.get(key)

def is_listening():
    return _listening

def set_log_callback(cb):
    global _log_callback
    _log_callback = cb

def set_status_callback(cb):
    global _status_callback
    _status_callback = cb

def set_action_callback(cb):
    global _action_callback
    _action_callback = cb

def _queue_action(name, data=None):
    if _action_callback:
        _action_callback(name, data or {})

def _log(msg):
    if _log_callback:
        _log_callback(msg)

def set_pb_hwnd(hwnd):
    global _pb_hwnd
    _pb_hwnd = hwnd

def toggle_trigger_blocked():
    global _trigger_blocked
    _trigger_blocked = not _trigger_blocked
    return _trigger_blocked

def is_trigger_blocked():
    return _trigger_blocked
