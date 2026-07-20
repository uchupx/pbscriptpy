# app/profiles.py - Profile CRUD, persistence, and UI bindings
# ponytail: flat globals, tkinter vars as module-level refs

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from engine import _state
from engine.hook import start_listener, stop_listener

# --- UI refs (set by init()) ---
_root = None
_mode_var = None
_trigger_var = None
_switch_var = None
_key_hold_var = None
_recoil_amt_var = None
_recoil_timeout_var = None
_recoil_mode_var = None
_profile_var = None
_profile_dropdown = None
_log_text = None
_delay_frame = None
_delay_vars = []
_delay_labels = []
_delay_widgets = []
_start_btn = None
_stop_btn = None
_status_var = None

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
    "recoil_amount": 4,
    "recoil_smooth": True,
    "recoil_timeout_ms": 1000,
}

# --- State ---
profiles = []
active_idx = 0
_save_timer = None
_loading_profile = False


def init(root, mode_var, trigger_var, switch_var, key_hold_var,
         recoil_amt_var, recoil_timeout_var, recoil_mode_var,
         profile_var, profile_dropdown, log_text,
         delay_frame, start_btn, stop_btn, status_var):
    global _root, _mode_var, _trigger_var, _switch_var, _key_hold_var
    global _recoil_amt_var, _recoil_timeout_var, _recoil_mode_var
    global _profile_var, _profile_dropdown, _log_text
    global _delay_frame, _start_btn, _stop_btn, _status_var
    _root = root
    _mode_var = mode_var
    _trigger_var = trigger_var
    _switch_var = switch_var
    _key_hold_var = key_hold_var
    _recoil_amt_var = recoil_amt_var
    _recoil_timeout_var = recoil_timeout_var
    _recoil_mode_var = recoil_mode_var
    _profile_var = profile_var
    _profile_dropdown = profile_dropdown
    _log_text = log_text
    _delay_frame = delay_frame
    _start_btn = start_btn
    _stop_btn = stop_btn
    _status_var = status_var


# ===================== Persistence =====================

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
            for p in profiles:
                p.setdefault("recoil_smooth", True)
                p.setdefault("recoil_timeout_ms", 1000)
                if "recoil" in p and not p["recoil"] and p.get("recoil_amount", 0) == 4:
                    p["recoil_amount"] = 0
            active_idx = data.get("active", 0)
            if active_idx >= len(profiles):
                active_idx = 0
        except Exception as e:
            _state._log(f"Load failed: {e}")
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
        _state._log(f"Save failed: {e}")

def _schedule_save():
    global _save_timer
    if _save_timer:
        _root.after_cancel(_save_timer)
    _save_timer = _root.after(500, _do_save)

def _do_save():
    global _save_timer
    _save_timer = None
    was = _state.is_listening()
    if was:
        from engine.hook import stop_listener
        stop_listener()
    save_profiles()
    if was:
        from engine.hook import start_listener
        start_listener()
    _state._log("Profiles saved")


# ===================== Profile CRUD =====================

def _profile_list():
    return [p["name"] for p in profiles]

def apply_profile(idx):
    global _loading_profile, active_idx
    _loading_profile = True
    active_idx = idx
    p = profiles[idx]
    _mode_var.set(MODE_TO_LABEL.get(p["mode"], "Sniper"))
    _trigger_var.set(TRIGGER_TO_LABEL.get(p["trigger"], "X Button Forward"))
    _switch_var.set("qq" if p["switch_method"] == "qq" else "31")
    rebuild_delays()
    _key_hold_var.set(p["key_hold_delay"])
    _recoil_amt_var.set(p.get("recoil_amount", 0))
    _recoil_timeout_var.set(p.get("recoil_timeout_ms", 1000))
    amt = p.get("recoil_amount", 0)
    if amt > 0:
        _recoil_mode_var.set("Smooth" if p.get("recoil_smooth", True) else "Hold")
    else:
        _recoil_mode_var.set("OFF")
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
    p = profiles[active_idx]
    new = simpledialog.askstring("Rename", "New name:", initialvalue=p["name"])
    if new and new.strip() and new.strip() != p["name"]:
        p["name"] = new.strip()
        _refresh_profile_dropdown()
        _schedule_save()

def _refresh_profile_dropdown():
    menu = _profile_dropdown["menu"]
    menu.delete(0, "end")
    for p in profiles:
        menu.add_command(label=p["name"], command=lambda n=p["name"]: on_profile_select(n))
    _profile_var.set(profiles[active_idx]["name"] if active_idx < len(profiles) else "")

def export_profiles():
    path = _profile_path().replace(".json", "_export.json")
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({"profiles": profiles, "active": active_idx}, f, indent=2)
        _state._log(f"Exported to {os.path.basename(path)}")
    except Exception as e:
        _state._log(f"Export failed: {e}")


# ===================== Config Sync =====================

def _sync_core():
    p = profiles[active_idx]
    _state.set_config("mode", p["mode"])
    _state.set_config("trigger", p["trigger"])
    _state.set_config("switch_method", p["switch_method"])
    _state.set_config("key_hold_delay", p["key_hold_delay"])
    _state.set_config("recoil", p.get("recoil_amount", 0) > 0)
    _state.set_config("recoil_amount", p.get("recoil_amount", 0))
    _state.set_config("recoil_smooth", p.get("recoil_smooth", True))
    _state.set_config("recoil_timeout_ms", p.get("recoil_timeout_ms", 1000))
    cfg = p["mode"]
    if cfg == "sniper":
        _state.set_config("sniper_delays", p["sniper_delays"])
    elif cfg == "shotgun":
        _state.set_config("shotgun_delays", p["shotgun_delays"])
    elif cfg == "ar_smg":
        _state.set_config("ar_smg_delay", p["ar_smg_delay"])

def _get_delay_labels_and_vals(p):
    mode = p["mode"]
    if mode == "sniper":
        labels = ["Scope", "Fire→Close", "Close→Switch", "Betw keys"]
        vals = p["sniper_delays"]
    elif mode == "shotgun":
        labels = ["Fire→Switch", "Betw keys"]
        vals = p["shotgun_delays"]
    else:
        labels = ["Fire Rate"]
        vals = [p["ar_smg_delay"]]
    return labels, vals


# ===================== Delay Sliders =====================

def rebuild_delays():
    for w in _delay_widgets:
        w.destroy()
    _delay_widgets.clear()
    _delay_vars.clear()
    _delay_labels.clear()

    p = profiles[active_idx]
    mode = p["mode"]
    if mode == "sniper":
        labels = ["Scope→Fire", "Fire→Close", "Close→Switch", "Between keys"]
        keys = p["sniper_delays"]
    elif mode == "shotgun":
        labels = ["Fire→Switch", "Between keys"]
        keys = p["shotgun_delays"]
    else:
        labels = ["Fire rate"]
        keys = [p["ar_smg_delay"]]

    for i, label in enumerate(labels):
        frame = ttk.Frame(_delay_frame)
        frame.pack(fill="x", pady=2)
        ttk.Label(frame, text=label, width=14).pack(side="left")
        var = tk.IntVar(value=keys[i])
        _delay_vars.append(var)
        s = ttk.Scale(frame, from_=0, to=200, orient="horizontal",
                      variable=var, command=lambda v, idx=i: _on_delay_change(idx, v))
        s.pack(side="left", fill="x", expand=True, padx=5)
        lbl = ttk.Label(frame, text=str(keys[i]), width=4)
        lbl.pack(side="right")
        _delay_labels.append(lbl)
        _delay_widgets.append(frame)

def _on_delay_change(idx, val):
    val = int(float(val))
    _delay_labels[idx].configure(text=str(val))
    if not _loading_profile:
        p = profiles[active_idx]
        mode = p["mode"]
        vals = [int(float(v.get())) for v in _delay_vars]
        if mode == "sniper":
            p["sniper_delays"] = vals[:4]
        elif mode == "shotgun":
            p["shotgun_delays"] = vals[:2]
        else:
            p["ar_smg_delay"] = vals[0]
        _sync_core()
        _schedule_save()


# ===================== UI Callbacks =====================

def on_mode_change(*args):
    if _loading_profile:
        return
    label = _mode_var.get()
    p = profiles[active_idx]
    p["mode"] = MODE_OPTIONS.get(label, "sniper")
    rebuild_delays()
    _sync_core()
    _schedule_save()

def on_trigger_change(*args):
    if _loading_profile:
        return
    label = _trigger_var.get()
    profiles[active_idx]["trigger"] = TRIGGER_OPTIONS.get(label, "xbutton1")
    _sync_core()
    _schedule_save()

def on_switch_change(*args):
    if _loading_profile:
        return
    profiles[active_idx]["switch_method"] = "qq" if _switch_var.get() == "qq" else "31"
    _sync_core()
    _schedule_save()

def on_key_hold_change(val):
    if _loading_profile:
        return
    profiles[active_idx]["key_hold_delay"] = int(float(val))
    _sync_core()
    _schedule_save()

def on_recoil_amt_change(val):
    if _loading_profile:
        return
    p = profiles[active_idx]
    amt = int(float(val))
    p["recoil_amount"] = amt
    _recoil_mode_var.set("OFF" if amt == 0 else ("Smooth" if p.get("recoil_smooth", True) else "Hold"))
    _sync_core()
    _schedule_save()

def on_timeout_change(val):
    if _loading_profile:
        return
    profiles[active_idx]["recoil_timeout_ms"] = int(float(val))
    _sync_core()
    _schedule_save()
