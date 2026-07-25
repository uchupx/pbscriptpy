# app/__main__.py - Entry point: wire UI + engine, start main loop
# ponytail: thin orchestration layer + auto-restart on code change

import atexit
import os
import sys
import threading
import time
from engine import _state
from engine import shortcuts as engine_shortcuts
from app import ui, toast, profiles, action_handlers, crosshair


# ===================== Auto-restart on code change =====================

def _file_hash(path):
    """Quick first-1KB+last-1KB hash for change detection (fast, no hashlib dep)."""
    try:
        size = os.path.getsize(path)
        with open(path, 'rb') as f:
            if size <= 2048:
                return f.read()
            head = f.read(1024)
            f.seek(-1024, 2)
            tail = f.read(1024)
            return head + tail
    except OSError:
        return b''

_watched_files = []

def _init_watcher():
    """Scan engine/ and app/ for .py files to watch."""
    global _watched_files
    _watched_files = []
    for root in ['engine', 'app']:
        if not os.path.isdir(root):
            continue
        for fname in os.listdir(root):
            if fname.endswith('.py') and not fname.startswith('_state'):
                fpath = os.path.join(root, fname)
                _watched_files.append((fpath, _file_hash(fpath)))

def _watcher_loop():
    """Daemon thread: poll .py file changes every 1s, restart on change."""
    while True:
        time.sleep(1)
        for fpath, old_hash in _watched_files:
            new_hash = _file_hash(fpath)
            if new_hash != old_hash:
                # File changed → restart process
                os.execl(sys.executable, sys.executable, *sys.argv)


# ===================== Main =====================

def main():
    # --- Start file watcher (development auto-restart) ---
    _init_watcher()
    t = threading.Thread(target=_watcher_loop, daemon=True)
    t.start()

    # --- Build UI ---
    root, vars_dict, widgets = ui.build_ui()

    # --- Init modules with UI refs ---
    toast.init(root)

    # --- Init crosshair overlay (starts hidden, apply_profile shows if sniper) ---
    crosshair.init(root)

    profiles.init(
        root,
        mode_var=vars_dict["mode_var"],
        trigger_var=vars_dict["trigger_var"],
        switch_var=vars_dict["switch_var"],
        key_hold_var=vars_dict["key_hold_var"],
        recoil_amt_var=vars_dict["recoil_amt_var"],
        recoil_timeout_var=vars_dict["recoil_timeout_var"],
        recoil_mode_var=vars_dict["recoil_mode_var"],
        profile_var=vars_dict["profile_var"],
        profile_dropdown=widgets["profile_dropdown"],
        log_text=widgets["log_text"],
        delay_frame=widgets["delay_frame"],
        start_btn=widgets["start_btn"],
        stop_btn=widgets["stop_btn"],
        status_var=vars_dict["status_var"],
    )

    # --- Wire engine callbacks → queues ---
    _state.set_log_callback(lambda msg: action_handlers.log_queue.put(msg))
    _state.set_status_callback(lambda msg: action_handlers.status_queue.put(msg))
    _state.set_action_callback(lambda name, data: action_handlers.action_queue.put((name, data)))

    # --- Load profiles ---
    profiles.load_profiles()
    profiles._refresh_profile_dropdown()
    if profiles.profiles:
        profiles.apply_profile(profiles.active_idx)

    # --- Wire UI callbacks ---
    widgets["mode_dropdown"].bind("<<ComboboxSelected>>", profiles.on_mode_change)
    widgets["trigger_dropdown"].bind("<<ComboboxSelected>>", profiles.on_trigger_change)
    vars_dict["switch_var"].trace_add("write", profiles.on_switch_change)
    widgets["start_btn"].configure(command=action_handlers.on_start)
    widgets["stop_btn"].configure(command=action_handlers.on_stop)
    widgets["btn_rename"].configure(command=profiles.rename_profile)
    widgets["btn_delete"].configure(command=profiles.delete_profile)
    widgets["btn_add"].configure(command=profiles.add_profile)
    widgets["btn_export"].configure(command=profiles.export_profiles)

    # Scale callbacks (command= passes current value as string)
    widgets["hold_scale"].configure(command=profiles.on_key_hold_change)
    widgets["recoil_scale"].configure(command=profiles.on_recoil_amt_change)
    widgets["timeout_scale"].configure(command=profiles.on_timeout_change)

    # --- Start polling ---
    root.after(100, action_handlers.poll_queues)
    engine_shortcuts.start_shortcut_polling()

    # --- Cleanup ---
    atexit.register(engine_shortcuts.stop_shortcut_polling)

    def on_close():
        from engine.hook import stop_listener
        stop_listener()
        engine_shortcuts.stop_shortcut_polling()
        crosshair.destroy()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    # --- Go ---
    root.mainloop()


if __name__ == "__main__":
    main()
