# Refactor: Modular Architecture

**Date:** 2026-07-20
**Status:** Approved (verbal)

## Goal

Split monolithic `main.py` (802 lines) and `core.py` (543 lines) into a clean folder-per-layer structure. Zero behavior change. Every function moves as-is unless merging reduces duplication.

## Non-Goals

- No new features
- No OOP/class tax
- No dependency additions
- No external API changes (main.py entry point preserved)
- No refactoring of macro logic or hook behavior

## Architecture

```
pbscriptpy/
├── main.py                  # Shim: `python main.py` → from app.__main__ import main
├── requirements.txt
├── .agents/
├── docs/
│
├── engine/                  # Pure Windows API — zero tkinter imports
│   ├── __init__.py
│   ├── config.py            # DEFAULT dict (from current config.py)
│   ├── _state.py            # Shared mutable state globals
│   ├── input_sim.py         # SendInput wrappers
│   ├── macros.py            # Macro sequences (sniper/shotgun/ar_smg)
│   ├── hook.py              # WH_MOUSE_LL + start/stop listener
│   └── shortcuts.py         # GetAsyncKeyState polling thread
│
├── app/                     # tkinter layer
│   ├── __init__.py
│   ├── __main__.py          # Entry: build UI, start polling, root.mainloop()
│   ├── ui.py                # Widget creation (style, frames, sliders, buttons)
│   ├── profiles.py          # Profile CRUD + persistence
│   ├── toast.py             # Toast overlay
│   └── action_handlers.py   # _handle_* functions + ACTION_MAP
│
└── data/                    # Runtime profiles.json (created automatically)
```

## Module Boundaries

### engine/config.py
- `DEFAULT` dict — copy of current `config.py` verbatim

### engine/_state.py
Consolidates all shared globals from `core.py` and `main.py`:
- `_cfg: dict` — runtime config
- `_listening, _running, _trigger_held: bool`
- `_stop_macro: threading.Event`
- `_hook, _hook_proc, _hook_thread, _hook_thread_id`
- `_macro_thread: Thread`
- `_log_callback, _status_callback, _action_callback`
- `_shortcut_running, _shortcut_thread, _shortcut_prev, _slot_selected_at`
- `_pb_hwnd, _trigger_blocked`

Keep as module-level globals. No class.

### engine/input_sim.py
Pure functions from current `core.py` lines 139–173:
- `mouse_down(flags)`, `mouse_up(flags)`
- `mouse_click(flags_down, flags_up, delay_ms)`
- `mouse_move(dx, dy)`
- `key_press(vk, hold_ms=0)`
- `_wait(delay_ms)` — sleep with early-exit check (uses `_stop_macro` from _state)

### engine/macros.py
From current `core.py` lines 176–280:
- `_do_switch(method, delay_ms)`
- `_run_sniper()`
- `_run_shotgun()`
- `_run_ar_smg()`
- `_finish_macro()`

### engine/hook.py
From current `core.py`:
- `HOOKPROC` type, `MSLLHOOKSTRUCT`, `MSG` structs (or import from _state)
- `_make_mouse_callback()`
- `start_listener()`, `stop_listener()`
- `set_pb_hwnd()`, `toggle_trigger_blocked()`, `is_trigger_blocked()`

### engine/shortcuts.py
From current `core.py` lines 289–381:
- `VK_*` constants
- `_shortcut_poll()`
- `start_shortcut_polling()`, `stop_shortcut_polling()`

### app/profiles.py
From current `main.py` lines 98–244:
- `PROFILE_TEMPLATE`, `PROFILES_FILE`
- `_profile_path()`
- `load_profiles()`, `save_profiles()`, `_schedule_save()`, `_do_save()`
- `_profile_list()`
- `apply_profile(idx)`, `on_profile_select(name)`
- `add_profile()`, `delete_profile()`, `rename_profile()`
- `_refresh_profile_dropdown()`, `export_profiles()`
- `_sync_core()`, `_get_delay_labels_and_vals()`
- `rebuild_delays()`, `_on_delay_change()`

Note: These reference `root` and tkinter vars (`mode_var`, `trigger_var`, etc.) — will use module-level globals in `app/profiles.py` that `ui.py` sets after `build_ui()`. No DI/tax, just `profiles.init_ui_vars(root, mode_var, ...)` called once from `__main__`.

### app/ui.py
From current `main.py` lines 640–775:
- `build_ui()` function that creates root, style, all frames, returns root
- All ttk.Frame/Button/Label/Scale creation
- `style` config
- Button commands bound to callbacks from action_handlers

### app/toast.py
From current `main.py` lines 46–77:
- `show_toast(text, duration=2500)`
- `_hide_toast()`
- References `root` for `after()` calls

### app/action_handlers.py
From current `main.py` lines 412–613:
- `_handle_*` functions
- `ACTION_MAP` dict
- `poll_queues()` function
- `on_start()`, `on_stop()`, `on_f5()`, `on_f12()`
- `on_mode_change()`, `on_trigger_change()`, `on_switch_change()`
- `on_key_hold_change()`, `on_recoil_amt_change()`, `on_timeout_change()`
- `_selected_delay_slot`, `_selected_recoil`, `_selected_timeout`

### app/__main__.py
From current `main.py` lines 777–802:
- Create root window via `ui.build_ui()`
- Load profiles
- Apply initial profile
- Start queue polling
- Start shortcut polling
- Register cleanup
- `root.mainloop()`

## Data Flow

```
User input (mouse/keyboard)
    │
    ▼
hook.py ──trigger──► macros.py ──sendinput──► input_sim.py
    │                                              │
    │ callback                                     │ Windows API
    ▼                                              ▼
app/action_handlers.py ◄──── engine/shortcuts.py ──► user32.dll
    │
    │ toast / profile CRUD
    ▼
app/ui.py / app/toast.py / app/profiles.py
```

## Migration Strategy

1. Write all new files in-place alongside existing `main.py` and `core.py`
2. `main.py` becomes 3-line shim
3. `core.py` gets deleted entirely after migration
4. No function signatures changed — pure move + import fix

## File Sizes (estimated)

| File | Est. Lines |
|------|-----------|
| app/__main__.py | ~30 |
| app/ui.py | ~160 |
| app/profiles.py | ~200 |
| app/toast.py | ~35 |
| app/action_handlers.py | ~210 |
| engine/config.py | ~25 |
| engine/_state.py | ~25 |
| engine/input_sim.py | ~50 |
| engine/macros.py | ~110 |
| engine/hook.py | ~180 |
| engine/shortcuts.py | ~100 |
| main.py (shim) | ~3 |
| **Total** | **~1128** |
| (was 802+543=1345) | **↓ ~200 lines** |

The reduction comes from deduplicating constants and removing docstrings that move to this spec.

## Dependencies (unchanged)
- stdlib only: tkinter, ctypes, threading, queue, json, os, time, atexit, traceback
