# main.py - NiceGUI version
# ponytail: flat layout, dark theme, no class tax

from nicegui import app, ui
import core
from config import DEFAULT
from queue import Queue
import atexit

# --- Constants ---
TRIGGER_OPTIONS = {"L-Click": "lclick", "X Button Forward": "xbutton1", "X Button Backward": "xbutton2"}
MODE_OPTIONS = {"Sniper": "sniper", "AR / SMG": "ar_smg", "Shotgun": "shotgun"}

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

# --- Core callbacks (thread-safe via queue) ---
def _log(msg):
    log_queue.put(msg)

def _status(msg):
    status_queue.put(msg)

core.set_log_callback(_log)
core.set_status_callback(_status)

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
                s = ui.slider(min=0, max=max_val, step=1, value=default).props("label-always").classes("flex-grow")
                delay_sliders.append(s)

# --- Mode change ---
def on_mode_change():
    mk = MODE_OPTIONS[mode_select.value]
    is_ar = mk == "ar_smg"

    rebuild_delays()
    recoil_card.visible = is_ar
    key_hold_card.visible = not is_ar
    switch_card.visible = not is_ar

# --- Start / Stop ---
def on_start():
    mk = MODE_OPTIONS[mode_select.value]
    core.set_config("mode", mk)
    core.set_config("trigger", TRIGGER_OPTIONS[trigger_select.value])
    core.set_config("switch_method", "qq" if switch_radio.value == "QQ (quick switch)" else "31")

    if mk == "sniper":
        core.set_config("sniper_delays", [s.value for s in delay_sliders])
    elif mk == "shotgun":
        core.set_config("shotgun_delays", [s.value for s in delay_sliders])
    else:
        core.set_config("ar_smg_delay", delay_sliders[0].value if delay_sliders else 80)

    if key_hold_slider:
        core.set_config("key_hold_delay", key_hold_slider.value)

    core.set_config("recoil", recoil_check.value)
    core.set_config("recoil_amount", recoil_slider.value)

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

# --- Build UI ---
with ui.header(elevated=True).classes("items-center justify-between"):
    ui.label("PB Script Macro").classes("text-h6 font-bold")
    ui.space()
    ui.icon("sports_esports", size="32px")

with ui.column().classes("w-full max-w-3xl mx-auto p-4 gap-4"):
    # Mode & Trigger
    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center gap-4"):
            ui.label("Mode").classes("font-bold")
            mode_select = ui.select(list(MODE_OPTIONS.keys()), value="Sniper", on_change=on_mode_change).classes("flex-grow")
            ui.label("Trigger").classes("font-bold")
            trigger_select = ui.select(list(TRIGGER_OPTIONS.keys()), value="X Button Forward").classes("flex-grow")

    # Switch Method
    with ui.card().classes("w-full") as switch_card:
        ui.label("Switch Method").classes("font-bold")
        switch_radio = ui.radio(["QQ (quick switch)", "31 (slot switch)"], value="QQ (quick switch)").props("inline")

    # Delay Sliders
    with ui.card().classes("w-full"):
        ui.label("Delays (ms)").classes("font-bold")
        delay_container = ui.column().classes("w-full gap-1")

    # Key Hold Time
    with ui.card().classes("w-full") as key_hold_card:
        ui.label("Key Hold Time (ms)").classes("font-bold")
        with ui.row().classes("items-center w-full"):
            ui.label("Hold duration:").classes("w-32")
            key_hold_slider = ui.slider(min=0, max=200, step=1, value=core.get_config("key_hold_delay")).props("label-always").classes("flex-grow")

    # Recoil Control
    with ui.card().classes("w-full") as recoil_card:
        ui.label("Recoil Control (AR/SMG)").classes("font-bold")
        recoil_check = ui.checkbox("Enable recoil pull", value=core.get_config("recoil"))
        with ui.row().classes("items-center w-full"):
            ui.label("Pixels per shot:").classes("w-32")
            recoil_slider = ui.slider(min=1, max=20, step=1, value=core.get_config("recoil_amount")).props("label-always").classes("flex-grow")

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

# --- Init ---
on_mode_change()
ui.timer(0.1, poll_queues)

# --- Cleanup ---
atexit.register(core.stop_listener)

ui.run(title="PB Script Macro", dark=True, reload=False, native=True, window_size=(800, 700))