# config.py - Default settings
# ponytail: flat dict, no class tax

DEFAULT = {
    "mode": "sniper",
    "trigger": "xbutton1",

    # Sniper: scope→fire→close→switch→internal_delay
    "sniper_delays": [50, 50, 50, 50],

    # Shotgun: fire→switch→internal_delay
    "shotgun_delays": [50, 50],

    # AR/SMG
    "ar_smg_delay": 80,
    "recoil": True,
    "recoil_amount": 4,

    # Switch method: "qq" or "31"
    "switch_method": "qq",
    # Key hold time (ms) for down→up of each switch key
    "key_hold_delay": 40,
}