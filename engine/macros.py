# engine/macros.py - Macro sequences (sniper / shotgun / ar_smg)
# ponytail: flat functions, platform-agnostic (uses click_left/right, press_key)

import time
from engine import _state
from engine.input_sim import click_left, click_right, mouse_move, press_key, _wait


# ===================== Timing measurement =====================

_timing_last = 0.0

def _timing_reset():
    """Call at macro start to reset interval tracking."""
    global _timing_last
    _timing_last = time.time()

def _timing_log(label, configured_ms):
    """Log actual interval since last mark vs configured, then reset."""
    global _timing_last
    now = time.time()
    actual = int((now - _timing_last) * 1000)
    _timing_last = now
    _state._log(f"Timing | {label}: cfg={configured_ms}ms act={actual}ms")


# ===================== Shared =====================

def _finish_macro():
    _state._running = False
    _state._trigger_held = False
    if _state._status_callback:
        _state._status_callback("Idle")

def _do_switch(method, delay_ms):
    """QQ: Q→delay→Q | 31: 3→delay→1. Each key down→hold→up."""
    hold = _state._cfg.get("key_hold_delay", 30)
    if method == "qq":
        press_key('q', hold)
        _wait(delay_ms)
        press_key('q', hold)
    else:  # "31"
        press_key('3', hold)
        _wait(delay_ms)
        press_key('1', hold)


# ===================== Sniper =====================

def _run_sniper():
    """RClick→delay0→LClick→delay1→RClick→delay2→Switch→delay3"""
    try:
        delays = _state._cfg.get("sniper_delays", [50, 50, 50, 50])
        method = _state._cfg.get("switch_method", "qq")
        _timing_reset()

        click_right(15)
        if _state._stop_macro.is_set(): return
        _wait(delays[0])
        _timing_log("Scope→Fire", delays[0])

        click_left(15)
        if _state._stop_macro.is_set(): return
        _wait(delays[1])
        _timing_log("Fire→Close", delays[1])

        click_right(15)
        if _state._stop_macro.is_set(): return
        _wait(delays[2])
        _timing_log("Close→Switch", delays[2])

        _do_switch(method, delays[3])
        _timing_log("Switch", delays[3])
    except Exception as e:
        _state._log(f"Sniper error: {e}")
    finally:
        _finish_macro()


# ===================== Shotgun =====================

def _run_shotgun():
    """LClick→delay0→Switch→delay1"""
    try:
        delays = _state._cfg.get("shotgun_delays", [50, 50])
        while len(delays) < 2:
            delays.append(50)
        method = _state._cfg.get("switch_method", "qq")
        _timing_reset()

        click_left(15)
        if _state._stop_macro.is_set(): return
        _wait(delays[0])
        _timing_log("Fire→Switch", delays[0])

        _do_switch(method, delays[1])
        _timing_log("Switch", delays[1])
    except Exception as e:
        _state._log(f"Shotgun error: {e}")
    finally:
        _finish_macro()


# ===================== AR/SMG =====================

def _run_ar_smg():
    """Hold loop: LClick → delay → LClick → delay ... with optional recoil pull."""
    try:
        delay = _state._cfg.get("ar_smg_delay", 80)
        recoil_amt = _state._cfg.get("recoil_amount", 4)
        has_recoil = recoil_amt > 0
        shot_count = 0

        # First shot — fires immediately on trigger press
        _timing_reset()
        click_left(15)
        shot_count += 1

        while not _state._stop_macro.is_set():
            if not _state._trigger_held:
                break

            # Recoil pull — move mouse down recoil_amt pixels at once
            if has_recoil:
                mouse_move(0, recoil_amt)
                if _state._stop_macro.is_set():
                    break

            if not _state._trigger_held:
                break
            _wait(delay)

            if _state._stop_macro.is_set() or not _state._trigger_held:
                break

            # Next shot
            click_left(15)
            shot_count += 1
            _timing_log(f"Shot#{shot_count-1}→{shot_count}", delay)

        _state._log(f"AR/SMG stopped ({shot_count} shots)")
    except Exception as e:
        _state._log(f"AR/SMG error: {e}")
    finally:
        _finish_macro()
