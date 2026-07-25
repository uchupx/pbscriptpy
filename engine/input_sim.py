# engine/input_sim.py — Platform-aware input simulation dispatch
# Exports: click_left, click_right, mouse_move, press_key, _wait

import sys

if sys.platform == "win32":
    from engine._plat_win32 import click_left, click_right, mouse_move, press_key, _wait
else:
    from engine._plat_linux import click_left, click_right, mouse_move, press_key, _wait
