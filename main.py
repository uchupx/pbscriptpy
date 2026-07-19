# main.py - tkinter UI for PB Script Macro
# ponytail: flat layout, no class tax, stdlib only

import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import core
from config import DEFAULT
from queue import Queue
import atexit
import json
import os
import threading
import time

# --- Constants ---
TRIGGER_OPTIONS = {"L-Click": "lclick", "X Button Forward": "xbutton1", "X Button Backward": "xbutton2"}
TRIGGER_TO_LABEL = {v: k for k, v in TRIGGER_OPTIONS.items()}
MODE_OPTIONS = {"Sniper": "sniper", "AR / SMG": "ar_smg", "Shotgun": "shotgun"}
MODE_TO_LABEL = {v: k for k, v in MODE_OPTIONS.items()}
PROFILES_FILE = "profiles.json"

PROFILE_TEMPLATE = {
    "name": "New Profile",
    "mode": "sniper", "trigger": "xbutton1",
    "sniper_delays": [50, 50, 50, 50],
    "shotgun_delays": [50, 50],
    "ar_smg_delay": 80,
    "switch_method": "qq",
    "key_hold_delay": 40,
    "recoil": True, "recoil_amount": 4,
    "recoil_smooth": True,
    "recoil_timeout_ms": 1000,
}

# --- State ---
log_queue = Queue()
status_queue = Queue()
action_queue = Queue()
profiles = []
active_idx = 0
_save_timer = None
_loading_profile = False

# --- Toast System ---
_toast_window = None
_toast_timer = None

def show_toast(text):
    global _toast_window, _toast_timer
    if _toast_timer:
        root.after_cancel(_toast_timer)
        _toast_timer = None
    if _toast_window is None:
        _toast_window = tk.Toplevel(root)
        _toast_window.overrideredirect(True)
        _toast_window.attributes('-topmost', True)
        _toast_window.configure(bg='#1e1e1e')
        _toast_label = tk.Label(
            _toast_window, text='', font=('Consolas', 10, 'bold'),
            fg='#ffffff', bg='#1e1e1e', padx=8, pady=4,
            anchor='w', justify='left'
        )
        _toast_label.pack()
    _toast_label = _toast_window.winfo_children()[0]
    _toast_label.config(text=text)
    _toast_window.update_idletasks()
    w = min(_toast_window.winfo_reqwidth(), root.winfo_screenwidth() - 20)
    _toast_window.geometry(f'{w}x{_toast_window.winfo_reqheight()}+10+10')
    _toast_window.deiconify()
    _toast_timer = root.after(2500, _hide_toast)

def _hide_toast():
    global _toast_timer
    _toast_timer = None
    if _toast_window:
        _toast_window.withdraw()

_selected_delay_slot = 0
_selected_recoil = False
_selected_timeout = False
_last_action = ""
_last_action_time = 0

# --- Core callbacks ---
def _log(msg):
    log_queue.put(msg)

def _status(msg):
    status_queue.put(msg)

core.set_log_callback(_log)
core.set_status_callback(_status)
core.set_action_callback(lambda name, data: action_queue.put((name, data)))

# ===================== PROFILE ENGINE =====================

def _profile_path():
    docs = os.path.join(os.path.expanduser("~"), "Documents", "pbscriptpy")
    os.makedirs(docs, exist_ok=True)
    return os.path.join(docs, PROFILES_FILE)

def load_profiles():
    global profiles, active_idx
    path = _profile_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            profiles = data.get("profiles", [])
            active_idx = data.get("active", 0)
            if active_idx >= len(profiles):
                active_idx = 0
        except Exception as e:
            _log(f"Load failed: {e}")
            profiles = []
    if not profiles:
        profiles.append(dict(PROFILE_TEMPLATE, name="Default"))
        active_idx = 0

def save_profiles():
    path = _profile_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({"profiles": profiles, "active": active_idx}, f, indent=2)
    except Exception as e:
        _log(f"Save failed: {e}")

def _schedule_save():
    global _save_timer
    if _save_timer:
        root.after_cancel(_save_timer)
    _save_timer = root.after(500, _do_save)

def _do_save():
    global _save_timer
    _save_timer = None
    was = core.is_listening()
    if was:
        core.stop_listener()
    save_profiles()
    if was:
        core.start_listener()
    _log("Profiles saved")

def _profile_list():
    return [p["name"] for p in profiles]

def apply_profile(idx):
    global _loading_profile, active_idx
    _loading_profile = True
    active_idx = idx
    p = profiles[idx]
    mode_var.set(MODE_TO_LABEL.get(p["mode"], "Sniper"))
    trigger_var.set(TRIGGER_TO_LABEL.get(p["trigger"], "X Button Forward"))
    switch_var.set("qq" if p["switch_method"] == "qq" else "31")

    # Rebuild delay sliders for current mode
    rebuild_delays()

    key_hold_var.set(p["key_hold_delay"])
    recoil_var.set(p["recoil"])
    recoil_amt_var.set(p["recoil_amount"])
    try:
        recoil_timeout_var.set(p.get("recoil_timeout_ms", 1000))
    except NameError:
        pass
    try:
        if p["recoil"]:
            recoil_mode_var.set("Smooth" if p.get("recoil_smooth", True) else "Hold")
        else:
            recoil_mode_var.set("OFF")
    except NameError:
        pass

    _sync_core()
    _loading_profile = False

def on_profile_select(name):
    for i, p in enumerate(profiles):
        if p["name"] == name:
            apply_profile(i)
            break

def add_profile():
    global active_idx
    base = "New Profile"
    names = {p["name"] for p in profiles}
    name = base
    n = 2
    while name in names:
        name = f"{base} ({n})"
        n += 1
    profiles.append(dict(PROFILE_TEMPLATE, name=name))
    active_idx = len(profiles) - 1
    _refresh_profile_dropdown()
    apply_profile(active_idx)
    _schedule_save()

def delete_profile():
    global active_idx
    if len(profiles) <= 1:
        return
    p = profiles[active_idx]
    if not messagebox.askyesno("Delete", f"Delete '{p['name']}'?"):
        return
    profiles.pop(active_idx)
    if active_idx >= len(profiles):
        active_idx = len(profiles) - 1
    _refresh_profile_dropdown()
    apply_profile(active_idx)
    _schedule_save()

def rename_profile():
    global _loading_profile
    p = profiles[active_idx]
    new = simpledialog.askstring("Rename", "New name:", initialvalue=p["name"])
    if new and new.strip() and new.strip() != p["name"]:
        p["name"] = new.strip()
        _refresh_profile_dropdown()
        _schedule_save()

def _refresh_profile_dropdown():
    menu = profile_dropdown["menu"]
    menu.delete(0, "end")
    for p in profiles:
        menu.add_command(label=p["name"], command=lambda n=p["name"]: on_profile_select(n))
    profile_var.set(profiles[active_idx]["name"] if active_idx < len(profiles) else "")

def export_profiles():
    path = _profile_path().replace(".json", "_export.json")
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({"profiles": profiles, "active": active_idx}, f, indent=2)
        _log(f"Exported to {os.path.basename(path)}")
    except Exception as e:
        _log(f"Export failed: {e}")

# ===================== SYNCE =====================

def _sync_core():
    p = profiles[active_idx]
    core.set_config("mode", p["mode"])
    core.set_config("trigger", p["trigger"])
    core.set_config("switch_method", p["switch_method"])
    core.set_config("key_hold_delay", p["key_hold_delay"])
    core.set_config("recoil", p["recoil"])
    core.set_config("recoil_amount", p["recoil_amount"])
    core.set_config("recoil_smooth", p.get("recoil_smooth", True))
    core.set_config("recoil_timeout_ms", p.get("recoil_timeout_ms", 1000))
    if p["mode"] == "sniper":
        core.set_config("sniper_delays", p["sniper_delays"])
    elif p["mode"] == "shotgun":
        core.set_config("shotgun_delays", p["shotgun_delays"])
    elif p["mode"] == "ar_smg":
        core.set_config("ar_smg_delay", p["ar_smg_delay"])

def _get_delay_labels_and_vals(p):
    mode = p["mode"]
    if mode == "sniper":
        labels = ["Scope", "Fire→Close", "Close→Switch", "Betw keys"]
        vals = p["sniper_delays"]
    elif mode == "shotgun":
        labels = ["Fire→Switch", "Betw keys"]
        vals = p["shotgun_delays"]
    else:  # ar_smg
        labels = ["Fire Rate"]
        vals = [p["ar_smg_delay"]]
    return labels, vals

# ===================== DELAY SLIDERS =====================

def rebuild_delays():
    for w in delay_widgets:
        w.destroy()
    delay_widgets.clear()
    delay_vars.clear()
    delay_labels.clear()

    p = profiles[active_idx]
    mode = p["mode"]
    if mode == "sniper":
        labels = ["Scope→Fire", "Fire→Close", "Close→Switch", "Between keys"]
        keys = p["sniper_delays"]
    elif mode == "shotgun":
        labels = ["Fire→Switch", "Between keys"]
        keys = p["shotgun_delays"]
    else:  # ar_smg
        labels = ["Fire rate"]
        keys = [p["ar_smg_delay"]]

    for i, label in enumerate(labels):
        frame = ttk.Frame(delay_frame)
        frame.pack(fill="x", pady=2)
        ttk.Label(frame, text=label, width=14).pack(side="left")
        var = tk.IntVar(value=keys[i])
        delay_vars.append(var)
        s = ttk.Scale(frame, from_=0, to=200, orient="horizontal",
                      variable=var, command=lambda v, idx=i: _on_delay_change(idx, v))
        s.pack(side="left", fill="x", expand=True, padx=5)
        lbl = ttk.Label(frame, text=str(keys[i]), width=4)
        lbl.pack(side="right")
        delay_labels.append(lbl)
        delay_widgets.append(frame)

def _on_delay_change(idx, val):
    val = int(float(val))
    delay_labels[idx].configure(text=str(val))
    if not _loading_profile:
        p = profiles[active_idx]
        mode = p["mode"]
        vals = [int(float(v.get())) for v in delay_vars]
        if mode == "sniper":
            p["sniper_delays"] = vals[:4]
        elif mode == "shotgun":
            p["shotgun_delays"] = vals[:2]
        else:
            p["ar_smg_delay"] = vals[0]
        _sync_core()
        _schedule_save()

# ===================== UI CONTROLS =====================

def on_mode_change(*args):
    if _loading_profile:
        return
    label = mode_var.get()
    p = profiles[active_idx]
    p["mode"] = MODE_OPTIONS.get(label, "sniper")
    rebuild_delays()
    _sync_core()
    _schedule_save()

def on_trigger_change(*args):
    if _loading_profile:
        return
    label = trigger_var.get()
    profiles[active_idx]["trigger"] = TRIGGER_OPTIONS.get(label, "xbutton1")
    _sync_core()
    _schedule_save()

def on_switch_change(*args):
    if _loading_profile:
        return
    profiles[active_idx]["switch_method"] = "qq" if switch_var.get() == "qq" else "31"
    _sync_core()
    _schedule_save()

def on_key_hold_change(val):
    if _loading_profile:
        return
    profiles[active_idx]["key_hold_delay"] = int(float(val))
    _sync_core()
    _schedule_save()

def on_recoil_toggle():
    if _loading_profile:
        return
    profiles[active_idx]["recoil"] = recoil_var.get()
    _sync_core()
    _schedule_save()

def on_recoil_amt_change(val):
    if _loading_profile:
        return
    profiles[active_idx]["recoil_amount"] = int(float(val))
    _sync_core()
    _schedule_save()

def on_timeout_change(val):
    if _loading_profile:
        return
    profiles[active_idx]["recoil_timeout_ms"] = int(float(val))
    _sync_core()
    _schedule_save()

def on_start():
    _sync_core()
    start_btn.config(state="disabled")
    stop_btn.config(state="normal")
    core.start_listener()
    _status("Running")

def on_stop():
    core.stop_listener()
    start_btn.config(state="normal")
    stop_btn.config(state="disabled")
    _status("Idle")

def on_f5():
    global active_idx
    if not profiles:
        return
    active_idx = (active_idx + 1) % len(profiles)
    _refresh_profile_dropdown()
    apply_profile(active_idx)

def on_f12():
    if core.is_listening():
        on_stop()
    else:
        on_start()

# ===================== ACTION HANDLERS (shortcut dispatch) =====================

def _handle_show_status(data):
    p = profiles[active_idx]
    mode_label = MODE_TO_LABEL.get(p["mode"], p["mode"])
    trigger_label = TRIGGER_TO_LABEL.get(p["trigger"], p["trigger"])
    switch = p["switch_method"].upper()
    labels, vals = _get_delay_labels_and_vals(p)
    delays_str = " ".join(f"{l}:{v}" for l, v in zip(labels, vals))
    rec_str = f"Rec:{p['recoil_amount']}px ON" if p["recoil"] else "Rec:OFF"
    if p["mode"] == "ar_smg" and p["recoil"]:
        mode_name = "Smooth" if p.get("recoil_smooth", True) else "Hold"
        timeout = p.get("recoil_timeout_ms", 1000)
        rec_str += f" {mode_name} T:{timeout}"
    return f"{mode_label} | {trigger_label} | {switch} | {delays_str} | {rec_str}"

def _handle_cycle_profile(data):
    global active_idx
    if len(profiles) <= 1:
        return None
    active_idx = (active_idx + 1) % len(profiles)
    _refresh_profile_dropdown()
    apply_profile(active_idx)
    return f"Profile: {profiles[active_idx]['name']}"

def _handle_toggle_trigger_block(data):
    state = core.toggle_trigger_blocked()
    return f"Trigger Block: {'ON' if state else 'OFF'}"

def _handle_cycle_mode(data):
    global _selected_delay_slot
    order = ["sniper", "shotgun", "ar_smg"]
    p = profiles[active_idx]
    idx = order.index(p["mode"]) if p["mode"] in order else 0
    p["mode"] = order[(idx + 1) % len(order)]
    _selected_delay_slot = 0
    rebuild_delays()
    _sync_core()
    _schedule_save()
    return f"Mode: {MODE_TO_LABEL.get(p['mode'], p['mode'])}"

def _handle_toggle_recoil(data):
    p = profiles[active_idx]
    p["recoil"] = not p["recoil"]
    recoil_var.set(p["recoil"])
    _sync_core()
    _schedule_save()
    return f"Recoil: {'ON' if p['recoil'] else 'OFF'}"

def _toggle_recoil_mode():
    """Cycle: OFF → Smooth → Hold → OFF. Returns toast text."""
    p = profiles[active_idx]
    if not p["recoil"]:
        p["recoil"] = True
        p["recoil_smooth"] = True
        mode_label = "Smooth"
    elif p["recoil_smooth"]:
        p["recoil_smooth"] = False
        mode_label = "Hold"
    else:
        p["recoil"] = False
        mode_label = "OFF"
    recoil_var.set(p["recoil"])
    try:
        recoil_mode_var.set(mode_label)
    except NameError:
        pass
    _sync_core()
    _schedule_save()
    show_toast(f"Recoil: {mode_label}")

def _handle_toggle_listener(data):
    if core.is_listening():
        core.stop_listener()
        start_btn.config(state="normal")
        stop_btn.config(state="disabled")
        _status("Idle")
        return "Listener Stopped"
    else:
        _sync_core()
        core.start_listener()
        start_btn.config(state="disabled")
        stop_btn.config(state="normal")
        _status("Running")
        return "Listener Started"

def _handle_add_profile(data):
    add_profile()
    return f"Profile: {profiles[active_idx]['name']}"

def _handle_select_delay_slot(data):
    global _selected_delay_slot, _selected_recoil, _selected_timeout
    p = profiles[active_idx]
    slot = data["slot"]

    _selected_recoil = False
    _selected_timeout = False

    if p["mode"] == "ar_smg":
        if slot == 0:  # Ctrl+1 → Fire Rate
            _selected_delay_slot = 0
            _log("Selected: Fire Rate")
        elif slot == 1:  # Ctrl+2 → Recoil Amount
            _selected_recoil = True
            _log("Selected: Recoil Amount")
        elif slot == 2:  # Ctrl+3 → Toggle mode
            _toggle_recoil_mode()
            return
        elif slot == 3:  # Ctrl+4 → Timeout
            _selected_timeout = True
            _log("Selected: Recoil Timeout")
        return

    # Sniper / Shotgun: existing delay slot select
    _, vals = _get_delay_labels_and_vals(p)
    _selected_delay_slot = max(0, min(slot, len(vals) - 1))
    _log(f"Slot selected: {_selected_delay_slot} (mode={p['mode']}, delays={len(vals)})")

def _handle_delay_adjust(data):
    global _selected_delay_slot, _selected_recoil, _selected_timeout
    if _selected_recoil:
        return _handle_recoil_adjust(data)
    if _selected_timeout:
        return _handle_timeout_adjust(data)
    p = profiles[active_idx]
    mode = p["mode"]
    labels, vals = _get_delay_labels_and_vals(p)
    idx = min(_selected_delay_slot, len(vals) - 1)
    old_val = vals[idx]
    new_val = max(0, min(200, old_val + data["delta"]))
    vals[idx] = new_val
    _log(f"Delay adjust: slot={idx} ({labels[idx]}) {old_val}->{new_val}ms")
    if mode == "sniper":
        p["sniper_delays"] = vals[:4]
    elif mode == "shotgun":
        p["shotgun_delays"] = vals[:2]
    else:
        p["ar_smg_delay"] = vals[0]
    if idx < len(delay_vars):
        delay_vars[idx].set(new_val)
    if idx < len(delay_labels):
        delay_labels[idx].configure(text=str(new_val))
    _sync_core()
    _schedule_save()
    return f"{labels[idx]}: {new_val}ms"

def _handle_recoil_adjust(data):
    p = profiles[active_idx]
    new_val = max(1, min(20, p["recoil_amount"] + data["delta"]))
    p["recoil_amount"] = new_val
    recoil_amt_var.set(new_val)
    _sync_core()
    _schedule_save()
    return f"Recoil: {new_val}px"

def _handle_timeout_adjust(data):
    p = profiles[active_idx]
    old_val = p.get("recoil_timeout_ms", 1000)
    new_val = max(500, min(3000, old_val + data["delta"] * 100))
    p["recoil_timeout_ms"] = new_val
    try:
        recoil_timeout_var.set(new_val)
    except NameError:
        pass
    _sync_core()
    _schedule_save()
    return f"Timeout: {new_val}ms"

ACTION_MAP = {
    "show_status": _handle_show_status,
    "cycle_profile": _handle_cycle_profile,
    "toggle_trigger_block": _handle_toggle_trigger_block,
    "cycle_mode": _handle_cycle_mode,
    "toggle_recoil": _handle_toggle_recoil,
    "toggle_listener": _handle_toggle_listener,
    "add_profile": _handle_add_profile,
    "select_delay_slot": _handle_select_delay_slot,
    "delay_adjust": _handle_delay_adjust,
    "recoil_adjust": _handle_recoil_adjust,
}

def poll_queues():
    while not log_queue.empty():
        msg = log_queue.get_nowait()
        log_text.configure(state="normal")
        log_text.insert("end", msg + "\n")
        log_text.see("end")
        log_text.configure(state="disabled")
    while not status_queue.empty():
        status_var.set(status_queue.get_nowait())
    while not action_queue.empty():
        action, data = action_queue.get_nowait()
        global _last_action, _last_action_time
        now = int(time.time() * 1000)
        if action == _last_action and (now - _last_action_time) < 250:
            continue
        _last_action = action
        _last_action_time = now
        handler = ACTION_MAP.get(action)
        if handler:
            toast_text = handler(data)
            if toast_text:
                show_toast(toast_text)
    root.after(100, poll_queues)

# ===================== BUILD UI =====================

root = tk.Tk()
root.title("PB Script Macro")
root.geometry("620x700")
root.minsize(500, 600)
root.configure(bg="#1e1e1e")

style = ttk.Style()
style.theme_use("clam")
style.configure("TLabel", background="#1e1e1e", foreground="#ffffff")
style.configure("TFrame", background="#1e1e1e")
style.configure("TLabelframe", background="#1e1e1e", foreground="#ffffff")
style.configure("TLabelframe.Label", background="#1e1e1e", foreground="#ffffff")
style.configure("TButton", background="#333333", foreground="#ffffff")
style.configure("TScale", background="#1e1e1e")
style.configure("TRadiobutton", background="#1e1e1e", foreground="#ffffff")
style.configure("TCheckbutton", background="#1e1e1e", foreground="#ffffff")
style.map("TButton", background=[("active", "#555555")])

# Profile section
prof_frame = ttk.LabelFrame(root, text="Profile", padding=5)
prof_frame.pack(fill="x", padx=10, pady=(10, 2))

prof_row = ttk.Frame(prof_frame)
prof_row.pack(fill="x")
profile_var = tk.StringVar()
profile_dropdown = ttk.OptionMenu(prof_row, profile_var, "", *[], command=on_profile_select)
profile_dropdown.pack(side="left", fill="x", expand=True, padx=(0, 5))
ttk.Button(prof_row, text="Rename", command=rename_profile, width=7).pack(side="left", padx=1)
ttk.Button(prof_row, text="Delete", command=delete_profile, width=7).pack(side="left", padx=1)
ttk.Button(prof_row, text="+Add", command=add_profile, width=7).pack(side="left", padx=1)

export_row = ttk.Frame(prof_frame)
export_row.pack(fill="x", pady=(4, 0))
ttk.Button(export_row, text="Export All", command=export_profiles).pack(side="right")

# Mode & Trigger
mode_frame = ttk.LabelFrame(root, text="Mode & Trigger", padding=5)
mode_frame.pack(fill="x", padx=10, pady=2)

mode_row = ttk.Frame(mode_frame)
mode_row.pack(fill="x")
ttk.Label(mode_row, text="Mode:").pack(side="left")
mode_var = tk.StringVar()
mode_dropdown = ttk.Combobox(mode_row, textvariable=mode_var, values=list(MODE_OPTIONS.keys()), state="readonly", width=20)
mode_dropdown.pack(side="left", padx=5)
mode_dropdown.bind("<<ComboboxSelected>>", on_mode_change)

ttk.Label(mode_row, text="Trigger:").pack(side="left", padx=(20, 0))
trigger_var = tk.StringVar()
trigger_dropdown = ttk.Combobox(mode_row, textvariable=trigger_var, values=list(TRIGGER_OPTIONS.keys()), state="readonly", width=18)
trigger_dropdown.pack(side="left", padx=5)
trigger_dropdown.bind("<<ComboboxSelected>>", on_trigger_change)

# Switch method
switch_frame = ttk.LabelFrame(root, text="Switch Method", padding=5)
switch_frame.pack(fill="x", padx=10, pady=2)
switch_var = tk.StringVar(value="qq")
ttk.Radiobutton(switch_frame, text="QQ (quick switch)", variable=switch_var, value="qq", command=on_switch_change).pack(side="left", padx=10)
ttk.Radiobutton(switch_frame, text="31 (slot switch)", variable=switch_var, value="31", command=on_switch_change).pack(side="left", padx=10)

# Delay sliders
delay_frame_box = ttk.LabelFrame(root, text="Delays (ms)", padding=5)
delay_frame_box.pack(fill="x", padx=10, pady=2)
delay_frame = ttk.Frame(delay_frame_box)
delay_frame.pack(fill="x")
delay_vars = []
delay_labels = []
delay_widgets = []

# Key hold time
hold_frame = ttk.LabelFrame(root, text="Key Hold Time (ms)", padding=5)
hold_frame.pack(fill="x", padx=10, pady=2)
hold_row = ttk.Frame(hold_frame)
hold_row.pack(fill="x")
ttk.Label(hold_row, text="Hold duration:", width=14).pack(side="left")
key_hold_var = tk.IntVar(value=40)
hold_scale = ttk.Scale(hold_row, from_=0, to=200, orient="horizontal",
                       variable=key_hold_var, command=on_key_hold_change)
hold_scale.pack(side="left", fill="x", expand=True, padx=5)
hold_val = ttk.Label(hold_row, textvariable=key_hold_var, width=4)
hold_val.pack(side="right")

# Recoil control
recoil_frame = ttk.LabelFrame(root, text="Recoil Control (AR/SMG)", padding=5)
recoil_frame.pack(fill="x", padx=10, pady=2)
recoil_var = tk.BooleanVar(value=True)
recoil_check = ttk.Checkbutton(recoil_frame, text="Enable recoil pull", variable=recoil_var, command=on_recoil_toggle)
recoil_check.pack(anchor="w")
recoil_row = ttk.Frame(recoil_frame)
recoil_row.pack(fill="x")
ttk.Label(recoil_row, text="Pixels per shot:", width=14).pack(side="left")
recoil_amt_var = tk.IntVar(value=4)
recoil_scale = ttk.Scale(recoil_row, from_=1, to=20, orient="horizontal",
                         variable=recoil_amt_var, command=on_recoil_amt_change)
recoil_scale.pack(side="left", fill="x", expand=True, padx=5)
recoil_amt_label = ttk.Label(recoil_row, textvariable=recoil_amt_var, width=4)
recoil_amt_label.pack(side="right")

# Timeout slider
timeout_row = ttk.Frame(recoil_frame)
timeout_row.pack(fill="x", pady=(4, 0))
ttk.Label(timeout_row, text="Timeout (ms):", width=14).pack(side="left")
recoil_timeout_var = tk.IntVar(value=1000)
timeout_scale = ttk.Scale(timeout_row, from_=500, to=3000, orient="horizontal",
                          variable=recoil_timeout_var, command=on_timeout_change)
timeout_scale.pack(side="left", fill="x", expand=True, padx=5)
timeout_val = ttk.Label(timeout_row, textvariable=recoil_timeout_var, width=5)
timeout_val.pack(side="right")

# Mode indicator (controlled via Ctrl+3)
mode_row = ttk.Frame(recoil_frame)
mode_row.pack(fill="x", pady=(2, 0))
ttk.Label(mode_row, text="Mode:").pack(side="left")
recoil_mode_var = tk.StringVar(value="Smooth")
ttk.Label(mode_row, textvariable=recoil_mode_var, font=("", 9, "bold")).pack(side="left", padx=5)

# Buttons
btn_frame = ttk.Frame(root)
btn_frame.pack(fill="x", padx=10, pady=5)
start_btn = ttk.Button(btn_frame, text="Start Listener", command=on_start)
start_btn.pack(side="left", expand=True, padx=2)
stop_btn = ttk.Button(btn_frame, text="Stop Listener", command=on_stop, state="disabled")
stop_btn.pack(side="left", expand=True, padx=2)

# Status
status_var = tk.StringVar(value="Idle")
status_label = ttk.Label(root, textvariable=status_var, font=("", 12, "bold"))
status_label.pack(pady=2)

# Log
log_frame = ttk.LabelFrame(root, text="Event Log", padding=5)
log_frame.pack(fill="both", expand=True, padx=10, pady=(2, 10))
log_text = tk.Text(log_frame, height=10, bg="#2d2d2d", fg="#cccccc",
                   insertbackground="#ffffff", borderwidth=0, wrap="word", state="disabled")
log_text.pack(fill="both", expand=True)
log_scroll = ttk.Scrollbar(log_text, command=log_text.yview)
log_scroll.pack(side="right", fill="y")
log_text.configure(yscrollcommand=log_scroll.set)

# --- Init ---
load_profiles()
_refresh_profile_dropdown()
if profiles:
    apply_profile(active_idx)

# Keyboard bindings (only non-shortcut keys; F5/F12/F1/etc handled by polling thread)

# Poll queues
root.after(100, poll_queues)

# Start shortcut polling thread (always-on, independent of listener)
core.start_shortcut_polling()

# Cleanup
atexit.register(core.stop_listener)

# Fix window close
def on_close():
    core.stop_listener()
    core.stop_shortcut_polling()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)

root.mainloop()