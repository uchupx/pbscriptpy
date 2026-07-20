# engine/macros.py - Macro sequences (sniper / shotgun / ar_smg)
# ponytail: flat functions, reads _cfg from _state, no OOP tax

from engine import _state
from engine.input_sim import mouse_click, key_press, mouse_move, _wait

# Re-export constants used by macro sequences
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010


def _finish_macro():
    _state._running = False
    _state._trigger_held = False
    if _state._status_callback:
        _state._status_callback("Idle")

def _do_switch(method, delay_ms):
    """QQ: Q→delay→Q | 31: 3→delay→1. Each key down→hold→up."""
    hold = _state._cfg.get("key_hold_delay", 30)
    if method == "qq":
        key_press(0x51, hold)  # Q
        _wait(delay_ms)
        key_press(0x51, hold)  # Q
    else:  # "31"
        key_press(0x33, hold)  # 3
        _wait(delay_ms)
        key_press(0x31, hold)  # 1

def _run_sniper():
    """RClick→delay0→LClick→delay1→RClick→delay2→Switch→delay3"""
    try:
        delays = _state._cfg.get("sniper_delays", [50, 50, 50, 50])
        method = _state._cfg.get("switch_method", "qq")
        mouse_click(MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP, 15)
        if _state._stop_macro.is_set(): return
        _wait(delays[0])
        mouse_click(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, 15)
        if _state._stop_macro.is_set(): return
        _wait(delays[1])
        mouse_click(MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP, 15)
        if _state._stop_macro.is_set(): return
        _wait(delays[2])
        _do_switch(method, delays[3])
    except Exception as e:
        _state._log(f"Sniper error: {e}")
    finally:
        _finish_macro()

def _run_shotgun():
    """LClick→delay0→Switch→delay1"""
    try:
        delays = _state._cfg.get("shotgun_delays", [50, 50])
        # ponytail: pad if profile was corrupted
        while len(delays) < 2:
            delays.append(50)
        method = _state._cfg.get("switch_method", "qq")
        mouse_click(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, 15)
        if _state._stop_macro.is_set(): return
        _wait(delays[0])
        _do_switch(method, delays[1])
    except Exception as e:
        _state._log(f"Shotgun error: {e}")
    finally:
        _finish_macro()

def _run_ar_smg():
    """Hold loop: LClick → delay → LClick → delay ... with optional recoil pull."""
    try:
        delay = _state._cfg.get("ar_smg_delay", 80)
        recoil_amt = _state._cfg.get("recoil_amount", 4)
        has_recoil = recoil_amt > 0
        is_smooth = _state._cfg.get("recoil_smooth", True)
        hold_timeout = _state._cfg.get("recoil_timeout_ms", 1000)
        _state._log(f"AR/SMG started (recoil={'smooth' if is_smooth else 'hold'})")

        step_ms = max(10, delay // max(1, recoil_amt))
        recoil_started = False
        recoil_active = False
        recoil_elapsed = 0

        while not _state._stop_macro.is_set():
            if not _state._trigger_held:
                break

            mouse_click(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, 15)

            # Start recoil on first shot (hold) or every shot (smooth)
            if has_recoil:
                if is_smooth:
                    recoil_active = True
                elif not recoil_started:
                    recoil_started = True
                    recoil_active = True
                    recoil_elapsed = 0

            # Pull recoil gradually
            if has_recoil and recoil_active:
                for _ in range(recoil_amt):
                    if _state._stop_macro.is_set():
                        break
                    mouse_move(0, 1)
                    _wait(step_ms)
                    recoil_elapsed += step_ms
                    if not is_smooth and recoil_elapsed >= hold_timeout:
                        recoil_active = False
                        _state._log("Hold timeout end")
                        break

            if _state._stop_macro.is_set():
                break
            _wait(delay)

        _state._log("AR/SMG loop stopped")
    except Exception as e:
        _state._log(f"AR/SMG error: {e}")
    finally:
        _finish_macro()
