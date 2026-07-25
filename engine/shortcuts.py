# engine/shortcuts.py — Platform-aware shortcut polling dispatch
# Exports: start_shortcut_polling, stop_shortcut_polling

import sys

if sys.platform == "win32":
    from engine._plat_win32 import start_shortcut_polling, stop_shortcut_polling
else:
    from engine._plat_linux import start_shortcut_polling, stop_shortcut_polling
