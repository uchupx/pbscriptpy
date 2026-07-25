# app/action_handlers.py - Keyboard shortcut handlers + queue polling
# ponytail: flat functions, ACTION_MAP dispatch, no OOP tax

import time
from queue import Queue
from engine import _state
from engine.hook import start_listener, stop_listener
from engine.shortcuts import start_shortcut_polling, stop_shortcut_polling
from app import profiles, toast, crosshair

# --- Queues (bridges engine callbacks → UI) ---
log_queue = Queue()
status_queue = Queue()
action_queue = Queue()

# --- Inline-adjust state ---
_selected_delay_slot = 0
_selected_recoil = False
_selected_timeout = False

# --- Debounce ---
_last_action = ""
_last_action_time = 0


# ===================== Listener Controls =====================

def on_start():
    profiles._sync_core()
    profiles._start_btn.config(state="disabled")
    profiles._stop_btn.config(state="normal")
    start_listener()
    profiles._status_var.set("Running")

def on_stop():
    stop_listener()
    profiles._start_btn.config(state="normal")
    profiles._stop_btn.config(state="disabled")
    profiles._status_var.set("Idle")

def on_f5():
    if not profiles.profiles:
        return
    profiles.active_idx = (profiles.active_idx + 1) % len(profiles.profiles)
    profiles._refresh_profile_dropdown()
    profiles.apply_profile(profiles.active_idx)

def on_f12():
    if _state.is_listening():
        on_stop()
    else:
        on_start()


# ===================== Action Handlers =====================

def _handle_show_status(data):
    p = profiles.profiles[profiles.active_idx]
    mode_label = profiles.MODE_TO_LABEL.get(p["mode"], p["mode"])
    trigger_label = profiles.TRIGGER_TO_LABEL.get(p["trigger"], p["trigger"])
    switch = p["switch_method"].upper()
    labels, vals = profiles._get_delay_labels_and_vals(p)
    delays_str = " ".join(f"{l}:{v}" for l, v in zip(labels, vals))
    amt = p.get("recoil_amount", 0)
    rec_str = f"Rec:{amt}px" if amt > 0 else "Rec:OFF"
    if p["mode"] == "ar_smg" and amt > 0:
        mode_name = "Smooth" if p.get("recoil_smooth", True) else "Hold"
        timeout = p.get("recoil_timeout_ms", 1000)
        rec_str += f" {mode_name} T:{timeout}"
    return f"{mode_label} | {trigger_label} | {switch} | {delays_str} | {rec_str}"

def _handle_cycle_profile(data):
    if len(profiles.profiles) <= 1:
        return None
    profiles.active_idx = (profiles.active_idx + 1) % len(profiles.profiles)
    profiles._refresh_profile_dropdown()
    profiles.apply_profile(profiles.active_idx)
    return f"Profile: {profiles.profiles[profiles.active_idx]['name']}"

def _handle_cycle_trigger(data):
    p = profiles.profiles[profiles.active_idx]
    order = ["lclick", "xbutton1", "xbutton2"]
    idx = order.index(p["trigger"]) if p["trigger"] in order else 0
    new_trigger = order[(idx + 1) % len(order)]
    p["trigger"] = new_trigger
    profiles._trigger_var.set(profiles.TRIGGER_TO_LABEL[new_trigger])
    profiles._sync_core()
    profiles._schedule_save()
    return f"Trigger: {profiles.TRIGGER_TO_LABEL[new_trigger]}"

def _handle_cycle_mode(data):
    global _selected_delay_slot
    order = ["sniper", "shotgun", "ar_smg"]
    p = profiles.profiles[profiles.active_idx]
    idx = order.index(p["mode"]) if p["mode"] in order else 0
    p["mode"] = order[(idx + 1) % len(order)]
    _selected_delay_slot = 0
    profiles.rebuild_delays()
    profiles._sync_core()
    profiles._schedule_save()
    return f"Mode: {profiles.MODE_TO_LABEL.get(p['mode'], p['mode'])}"

def _toggle_recoil_mode():
    p = profiles.profiles[profiles.active_idx]
    amount = p.get("recoil_amount", 4)
    if amount == 0:
        p["recoil_amount"] = 4
        p["recoil_smooth"] = True
        mode_label = "Smooth"
        profiles._recoil_amt_var.set(4)
    elif p.get("recoil_smooth", True):
        p["recoil_smooth"] = False
        mode_label = "Hold"
    else:
        p["recoil_amount"] = 0
        mode_label = "OFF"
        profiles._recoil_amt_var.set(0)
    profiles._recoil_mode_var.set(mode_label)
    profiles._sync_core()
    profiles._schedule_save()
    toast.show_toast(f"Recoil: {mode_label}")

def _handle_toggle_listener(data):
    if _state.is_listening():
        stop_listener()
        profiles._start_btn.config(state="normal")
        profiles._stop_btn.config(state="disabled")
        profiles._status_var.set("Idle")
        return "Listener Stopped"
    else:
        profiles._sync_core()
        start_listener()
        profiles._start_btn.config(state="disabled")
        profiles._stop_btn.config(state="normal")
        profiles._status_var.set("Running")
        return "Listener Started"

def _handle_add_profile(data):
    profiles.add_profile()
    return f"Profile: {profiles.profiles[profiles.active_idx]['name']}"

def _handle_select_delay_slot(data):
    global _selected_delay_slot, _selected_recoil, _selected_timeout
    p = profiles.profiles[profiles.active_idx]
    slot = data["slot"]

    _selected_recoil = False
    _selected_timeout = False

    if p["mode"] == "ar_smg":
        if slot == 0:
            _selected_delay_slot = 0
            return "Fire Rate | press -/= to adjust"
        elif slot == 1:
            _selected_recoil = True
            return "Recoil | press -/= to adjust"
        elif slot == 2:
            _toggle_recoil_mode()
            return
        elif slot == 3:
            _selected_timeout = True
            return "Timeout | press -/= to adjust"

    labels, vals = profiles._get_delay_labels_and_vals(p)
    _selected_delay_slot = max(0, min(slot, len(vals) - 1))
    return f"{labels[_selected_delay_slot]} | press -/= to adjust"

def _handle_delay_adjust(data):
    global _selected_delay_slot, _selected_recoil, _selected_timeout
    if _selected_recoil:
        return _handle_recoil_adjust(data)
    if _selected_timeout:
        return _handle_timeout_adjust(data)

    p = profiles.profiles[profiles.active_idx]
    mode = p["mode"]
    labels, vals = profiles._get_delay_labels_and_vals(p)
    idx = min(_selected_delay_slot, len(vals) - 1)
    old_val = vals[idx]
    new_val = max(0, min(200, old_val + data["delta"]))
    vals[idx] = new_val
    _state._log(f"Delay adjust: slot={idx} ({labels[idx]}) {old_val}->{new_val}ms")

    if mode == "sniper":
        p["sniper_delays"] = vals[:4]
    elif mode == "shotgun":
        p["shotgun_delays"] = vals[:2]
    else:
        p["ar_smg_delay"] = vals[0]

    if idx < len(profiles._delay_vars):
        profiles._delay_vars[idx].set(new_val)
    if idx < len(profiles._delay_labels):
        profiles._delay_labels[idx].configure(text=str(new_val))
    profiles._sync_core()
    profiles._schedule_save()
    return f"{labels[idx]}: {new_val}ms"

def _handle_recoil_adjust(data):
    p = profiles.profiles[profiles.active_idx]
    new_val = max(1, min(20, p["recoil_amount"] + data["delta"]))
    p["recoil_amount"] = new_val
    profiles._recoil_amt_var.set(new_val)
    profiles._sync_core()
    profiles._schedule_save()
    return f"Recoil: {new_val}px"

def _handle_timeout_adjust(data):
    p = profiles.profiles[profiles.active_idx]
    old_val = p.get("recoil_timeout_ms", 1000)
    new_val = max(500, min(3000, old_val + data["delta"] * 100))
    p["recoil_timeout_ms"] = new_val
    profiles._recoil_timeout_var.set(new_val)
    profiles._sync_core()
    profiles._schedule_save()
    return f"Timeout: {new_val}ms"

def _handle_show_guide(data):
    p = profiles.profiles[profiles.active_idx]
    mode = p["mode"]
    lines = []
    if mode == "sniper":
        lines.append("Ctrl+1:Scope  Ctrl+2:Fire→Close")
        lines.append("Ctrl+3:Close→Switch  Ctrl+4:Betw keys")
    elif mode == "shotgun":
        lines.append("Ctrl+1:Fire→Switch  Ctrl+2:Betw keys")
    else:
        smooth = "Smooth" if p.get("recoil_smooth", True) else "Hold"
        lines.append(f"Ctrl+1:Fire Rate  Ctrl+2:Recoil")
        lines.append(f"Ctrl+3:Mode({smooth})  Ctrl+4:Timeout")
    lines.append("")
    lines.append("F1:Status  F2:Guide  F5:Profile")
    lines.append("F6:Trigger  F7:Mode  F12:Tog  Ctrl+N:New")
    lines.append("=/-:adjust")
    if mode == "ar_smg":
        lines.append("Ctrl+=/-:recoil")
    toast.show_toast("\n".join(lines), duration=4000)
    return None


# ===================== Crosshair =====================

def _handle_crosshair_shape(data):
    if _state.get_config("mode") != "sniper":
        return None
    crosshair.cycle_shape()
    return "Crosshair: " + ["Dot", "+", "Off"][crosshair._shape]

def _handle_crosshair_color(data):
    if _state.get_config("mode") != "sniper":
        return None
    crosshair.cycle_color()
    return "Color: " + crosshair._colors[crosshair._color_idx]


ACTION_MAP = {
    "show_status": _handle_show_status,
    "show_guide": _handle_show_guide,
    "cycle_profile": _handle_cycle_profile,
    "cycle_trigger": _handle_cycle_trigger,
    "cycle_mode": _handle_cycle_mode,
    "toggle_listener": _handle_toggle_listener,
    "add_profile": _handle_add_profile,
    "select_delay_slot": _handle_select_delay_slot,
    "delay_adjust": _handle_delay_adjust,
    "recoil_adjust": _handle_recoil_adjust,
    "cycle_crosshair_shape": _handle_crosshair_shape,
    "cycle_crosshair_color": _handle_crosshair_color,
}


# ===================== Queue Polling =====================

def poll_queues():
    while not log_queue.empty():
        msg = log_queue.get_nowait()
        profiles._log_text.configure(state="normal")
        profiles._log_text.insert("end", msg + "\n")
        profiles._log_text.see("end")
        profiles._log_text.configure(state="disabled")
    while not status_queue.empty():
        profiles._status_var.set(status_queue.get_nowait())
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
                toast.show_toast(toast_text)
    profiles._root.after(100, poll_queues)
