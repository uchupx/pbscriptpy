# main.py - NiceGUI version with profiles
# ponytail: flat layout, dark theme, no class tax

from nicegui import app, ui
import core
from config import DEFAULT
from queue import Queue
import atexit
import json
import os

# --- Constants ---
TRIGGER_OPTIONS = {"L-Click": "lclick", "X Button Forward": "xbutton1", "X Button Backward": "xbutton2"}
MODE_OPTIONS = {"Sniper": "sniper", "AR / SMG": "ar_smg", "Shotgun": "shotgun"}
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
}

# --- State ---
log_queue = Queue()
status_queue = Queue()
delay_sliders = []
key_hold_slider = None
switch_radio = None
recoil_check = None
recoil_slider = None
mode_select = None
trigger_select = None
start_btn = None
stop_btn = None
status_label = None
log_area = None
delay_container = None
recoil_card = None
key_hold_card = None
switch_card = None
profile_dropdown = None
profile_name_input = None

# Profile state
profiles = []
active_idx = 0
_save_timer = None
_loading_profile = False

# --- Core callbacks (thread-safe via queue) ---
def _log(msg):
    log_queue.put(msg)

def _status(msg):
    status_queue.put(msg)

core.set_log_callback(_log)
core.set_status_callback(_status)

# ===================== PROFILE ENGINE =====================

def _profile_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), PROFILES_FILE)

def load_profiles():
    global profiles, active_idx
    path = _profile_path()
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        profiles = data.get("profiles", [])
        active_idx = data.get("active", 0)
        if active_idx >= len(profiles):
            active_idx = 0
    if not profiles:
        profiles = [dict(PROFILE_TEMPLATE, name="Default")]
        active_idx = 0
        _write_profiles()

def _write_profiles():
    path = _profile_path()
    with open(path, "w") as f:
        json.dump({"profiles": profiles, "active": active_idx}, f, indent=2)

def _profile_list():
    return [p["name"] for p in profiles]

def _ensure_active():
    global active_idx
    if active_idx >= len(profiles):
        active_idx = max(0, len(profiles) - 1)

def apply_profile(idx):
    """Load profile idx settings into UI and core."""
    global active_idx, _loading_profile
    if idx < 0 or idx >= len(profiles):
        return
    active_idx = idx
    _loading_profile = True
    p = profiles[idx]

    mode_select.value = next(k for k, v in MODE_OPTIONS.items() if v == p["mode"])
    trigger_select.value = next(k for k, v in TRIGGER_OPTIONS.items() if v == p["trigger"])

    # Force rebuild delays + card visibility (on_change may not fire if same mode)
    on_mode_change()

    # Fill delays based on current mode
    mk = p["mode"]
    if mk == "sniper":
        vals = p.get("sniper_delays", [50, 50, 50, 50])
        for i, v in enumerate(vals):
            if i < len(delay_sliders):
                delay_sliders[i].value = v
    elif mk == "shotgun":
        vals = p.get("shotgun_delays", [50, 50])
        for i, v in enumerate(vals):
            if i < len(delay_sliders):
                delay_sliders[i].value = v
    else:
        if delay_sliders:
            delay_sliders[0].value = p.get("ar_smg_delay", 80)

    switch_radio.value = "QQ (quick switch)" if p.get("switch_method", "qq") == "qq" else "31 (slot switch)"
    key_hold_slider.value = p.get("key_hold_delay", 40)
    recoil_check.value = p.get("recoil", True)
    recoil_slider.value = p.get("recoil_amount", 4)

    # Sync core config immediately so running macro picks it up
    _sync_core()

    _update_dropdown()
    _loading_profile = False

def _snap_ui_to_profile():
    """Read all UI controls into the current profile dict."""
    if active_idx >= len(profiles):
        return
    p = profiles[active_idx]
    mk = MODE_OPTIONS[mode_select.value]
    p["mode"] = mk
    p["trigger"] = TRIGGER_OPTIONS[trigger_select.value]
    p["switch_method"] = "qq" if switch_radio.value == "QQ (quick switch)" else "31"
    p["key_hold_delay"] = key_hold_slider.value

    if mk == "sniper":
        p["sniper_delays"] = [s.value for s in delay_sliders]
    elif mk == "shotgun":
        p["shotgun_delays"] = [s.value for s in delay_sliders]
    else:
        p["ar_smg_delay"] = delay_sliders[0].value if delay_sliders else 80

    p["recoil"] = recoil_check.value
    p["recoil_amount"] = recoil_slider.value

def _sync_core():
    """Push UI values to core config immediately."""
    mk = MODE_OPTIONS[mode_select.value]
    core.set_config("mode", mk)
    core.set_config("trigger", TRIGGER_OPTIONS[trigger_select.value])
    core.set_config("switch_method", "qq" if switch_radio.value == "QQ (quick switch)" else "31")
    core.set_config("key_hold_delay", key_hold_slider.value)
    if mk == "sniper":
        core.set_config("sniper_delays", [s.value for s in delay_sliders])
    elif mk == "shotgun":
        core.set_config("shotgun_delays", [s.value for s in delay_sliders])
    else:
        core.set_config("ar_smg_delay", delay_sliders[0].value if delay_sliders else 80)
    core.set_config("recoil", recoil_check.value)
    core.set_config("recoil_amount", recoil_slider.value)

def _update_dropdown():
    names = _profile_list()
    profile_dropdown.options = names
    profile_dropdown.value = names[active_idx] if names else ""

# --- Profile CRUD ---

def add_profile():
    global active_idx
    base = "New Profile"
    names = _profile_list()
    i = 1
    while base in names:
        base = f"New Profile ({i})"
        i += 1
    profiles.append(dict(PROFILE_TEMPLATE, name=base))
    active_idx = len(profiles) - 1
    apply_profile(active_idx)
    _write_profiles()
    _log(f"Profile '{base}' created")

async def _rename_handler():
    if active_idx >= len(profiles):
        return
    p = profiles[active_idx]
    with ui.dialog() as dlg, ui.card():
        ui.label("Rename Profile").classes("text-h6")
        inp = ui.input("Name", value=p["name"]).classes("w-full")
        with ui.row().classes("justify-end w-full gap-2"):
            ui.button("Cancel", on_click=dlg.close)
            ui.button("Save", on_click=lambda: dlg.submit(inp.value))
    name = await dlg
    if name and name.strip():
        profiles[active_idx]["name"] = name.strip()
        _write_profiles()
        _update_dropdown()
        _log(f"Profile renamed to '{name.strip()}'")

def delete_profile():
    if len(profiles) <= 1:
        _log("Cannot delete last profile")
        return
    if active_idx >= len(profiles):
        return
    name = profiles[active_idx]["name"]
    profiles.pop(active_idx)
    _ensure_active()
    apply_profile(active_idx)
    _write_profiles()
    _log(f"Profile '{name}' deleted")

def export_profiles():
    path = _profile_path()
    # Save current UI to profile first
    _snap_ui_to_profile()
    _write_profiles()
    # Trigger download
    app.download(path)

def on_profile_select(name):
    global _loading_profile
    idx = _profile_list().index(name)
    if idx == active_idx:
        return
    apply_profile(idx)
    _schedule_save()

def cycle_profile():
    """Cycle to next profile."""
    if len(profiles) <= 1:
        return
    nxt = (active_idx + 1) % len(profiles)
    apply_profile(nxt)
    _schedule_save()
    _log(f"Switched to '{profiles[nxt]['name']}'")

# ===================== AUTO-SAVE =====================

def _cancel_save():
    global _save_timer
    if _save_timer:
        _save_timer.deactivate()
        _save_timer = None

def _schedule_save():
    _cancel_save()
    global _save_timer
    _save_timer = ui.timer(3.0, _do_auto_save, once=True)

def _do_auto_save():
    global _save_timer
    _save_timer = None
    was_running = not start_btn.enabled
    _snap_ui_to_profile()
    _sync_core()
    _write_profiles()
    if was_running:
        on_stop()
        ui.timer(0.3, on_start, once=True)

def on_setting_change():
    """Called from any control change to trigger auto-save."""
    if _loading_profile:
        return
    _sync_core()
    _schedule_save()

# ===================== UI BUILDING =====================

# --- Poll queues from UI thread ---
def poll_queues():
    while not log_queue.empty():
        log_area.push(log_queue.get_nowait())
    while not status_queue.empty():
        status_label.set_text(status_queue.get_nowait())

# --- Dynamic delay sliders ---
def rebuild_delays():
    delay_container.clear()
    delay_sliders.clear()
    mk = MODE_OPTIONS[mode_select.value]
    if mk == "sniper":
        labels = ["Scope -> Fire", "Fire -> Close scope", "Close scope -> Switch", "Between switch keys"]
        defs = core.get_config("sniper_delays")
    elif mk == "shotgun":
        labels = ["Fire -> Switch", "Between switch keys"]
        defs = core.get_config("shotgun_delays")
    else:
        labels = ["Between clicks"]
        defs = [core.get_config("ar_smg_delay")]
    with delay_container:
        for label, default in zip(labels, defs):
            max_val = 100 if "switch" in label.lower() else 200
            with ui.row().classes("items-center w-full"):
                ui.label(label).classes("w-44")
                s = ui.slider(min=0, max=max_val, step=1, value=default, on_change=lambda _: on_setting_change()).props("label-always").classes("flex-grow")
                delay_sliders.append(s)

# --- Mode change ---
def on_mode_change():
    mk = MODE_OPTIONS[mode_select.value]
    is_ar = mk == "ar_smg"
    rebuild_delays()
    recoil_card.visible = is_ar
    key_hold_card.visible = not is_ar
    switch_card.visible = not is_ar
    if not _loading_profile:
        on_setting_change()

# --- Start / Stop ---
def on_start():
    _sync_core()
    start_btn.enabled = False
    stop_btn.enabled = True
    mode_select.enabled = False
    trigger_select.enabled = False
    core.start_listener()

def on_stop():
    core.stop_listener()
    start_btn.enabled = True
    stop_btn.enabled = False
    mode_select.enabled = True
    trigger_select.enabled = True
    _status("Idle")

# --- Keyboard ---
def on_key(e):
    if e.key == "F5" and e.action.keydown:
        cycle_profile()

# ===================== BUILD UI =====================

# Load profiles first
load_profiles()

with ui.header(elevated=True).classes("items-center justify-between"):
    ui.label("PB Script Macro").classes("text-h6 font-bold")
    ui.space()
    ui.icon("sports_esports", size="32px")

with ui.column().classes("w-full max-w-3xl mx-auto p-4 gap-4"):
    # Profile section
    with ui.card().classes("w-full"):
        ui.label("Profiles").classes("font-bold")
        with ui.row().classes("items-center w-full gap-2"):
            ui.icon("folder", size="20px")
            profile_dropdown = ui.select(_profile_list(), value=_profile_list()[active_idx] if profiles else "",
                                         on_change=lambda e: on_profile_select(e.value)).classes("flex-grow")
            ui.button(icon="edit", on_click=_rename_handler).props("flat dense")
            ui.button(icon="delete", on_click=delete_profile).props("flat dense color=negative")
            ui.button(icon="add", on_click=add_profile).props("flat dense color=positive")
        with ui.row().classes("w-full"):
            ui.space()
            ui.button("Export All", icon="download", on_click=export_profiles).props("flat dense")

    # Mode & Trigger
    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center gap-4"):
            ui.label("Mode").classes("font-bold")
            mode_select = ui.select(list(MODE_OPTIONS.keys()), value="Sniper", on_change=on_mode_change).classes("flex-grow")
            ui.label("Trigger").classes("font-bold")
            trigger_select = ui.select(list(TRIGGER_OPTIONS.keys()), value="X Button Forward", on_change=lambda _: on_setting_change()).classes("flex-grow")

    # Switch Method
    with ui.card().classes("w-full") as switch_card:
        ui.label("Switch Method").classes("font-bold")
        switch_radio = ui.radio(["QQ (quick switch)", "31 (slot switch)"], value="QQ (quick switch)", on_change=lambda _: on_setting_change()).props("inline")

    # Delay Sliders
    with ui.card().classes("w-full"):
        ui.label("Delays (ms)").classes("font-bold")
        delay_container = ui.column().classes("w-full gap-1")

    # Key Hold Time
    with ui.card().classes("w-full") as key_hold_card:
        ui.label("Key Hold Time (ms)").classes("font-bold")
        with ui.row().classes("items-center w-full"):
            ui.label("Hold duration:").classes("w-32")
            key_hold_slider = ui.slider(min=0, max=200, step=1, value=core.get_config("key_hold_delay"),
                                        on_change=lambda _: on_setting_change()).props("label-always").classes("flex-grow")

    # Recoil Control
    with ui.card().classes("w-full") as recoil_card:
        ui.label("Recoil Control (AR/SMG)").classes("font-bold")
        recoil_check = ui.checkbox("Enable recoil pull", value=core.get_config("recoil"), on_change=lambda _: on_setting_change())
        with ui.row().classes("items-center w-full"):
            ui.label("Pixels per shot:").classes("w-32")
            recoil_slider = ui.slider(min=1, max=20, step=1, value=core.get_config("recoil_amount"),
                                      on_change=lambda _: on_setting_change()).props("label-always").classes("flex-grow")

    # Buttons
    with ui.row().classes("justify-center gap-4 w-full"):
        start_btn = ui.button("Start Listener", on_click=on_start, icon="play_arrow").props("size=lg")
        stop_btn = ui.button("Stop Listener", on_click=on_stop, icon="stop").props("size=lg")
        stop_btn.enabled = False

    # Status
    status_label = ui.label("Idle").classes("text-center text-h6 text-primary")

    # Log
    with ui.card().classes("w-full"):
        ui.label("Event Log").classes("font-bold")
        log_area = ui.log(max_lines=100).classes("w-full h-48")

# Keyboard handler (global, outside cards so it catches all)
ui.keyboard(on_key=on_key)

# --- Init ---
if profiles:
    apply_profile(active_idx)
else:
    on_mode_change()
ui.timer(0.1, poll_queues)

# --- Cleanup ---
atexit.register(core.stop_listener)

ui.run(title="PB Script Macro", dark=True, reload=False, native=True, window_size=(800, 750))