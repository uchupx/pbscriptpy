# app/ui.py - Tkinter UI builder
# ponytail: single build_ui() function, returns widget handles, no business logic

import tkinter as tk
from tkinter import ttk


def build_ui():
    """Create main window, build all widgets, return (root, vars_dict, widgets_dict)."""
    root = tk.Tk()
    root.title("PB Script Macro")
    root.geometry("620x700")
    root.minsize(500, 600)
    root.configure(bg="#1e1e1e")

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TLabel", background="#1e1e1e", foreground="#ffffff")
    style.configure("TFrame", background="#1e1e1e")
    style.configure("TLabelframe", background="#1e1e1e", foreground="#ffffff")
    style.configure("TLabelframe.Label", background="#1e1e1e", foreground="#ffffff")
    style.configure("TButton", background="#333333", foreground="#ffffff")
    style.configure("TScale", background="#1e1e1e")
    style.configure("TRadiobutton", background="#1e1e1e", foreground="#ffffff")
    style.configure("TCheckbutton", background="#1e1e1e", foreground="#ffffff")
    style.map("TButton", background=[("active", "#555555")])

    # ===== Profile section =====
    prof_frame = ttk.LabelFrame(root, text="Profile", padding=5)
    prof_frame.pack(fill="x", padx=10, pady=(10, 2))

    prof_row = ttk.Frame(prof_frame)
    prof_row.pack(fill="x")
    profile_var = tk.StringVar()
    profile_dropdown = ttk.OptionMenu(prof_row, profile_var, "", *[])
    profile_dropdown.pack(side="left", fill="x", expand=True, padx=(0, 5))
    rename_btn = ttk.Button(prof_row, text="Rename", width=7)
    rename_btn.pack(side="left", padx=1)
    delete_btn = ttk.Button(prof_row, text="Delete", width=7)
    delete_btn.pack(side="left", padx=1)
    add_btn = ttk.Button(prof_row, text="+Add", width=7)
    add_btn.pack(side="left", padx=1)

    export_row = ttk.Frame(prof_frame)
    export_row.pack(fill="x", pady=(4, 0))
    export_btn = ttk.Button(export_row, text="Export All")
    export_btn.pack(side="right")

    # ===== Mode & Trigger =====
    mode_frame = ttk.LabelFrame(root, text="Mode & Trigger", padding=5)
    mode_frame.pack(fill="x", padx=10, pady=2)

    mode_row = ttk.Frame(mode_frame)
    mode_row.pack(fill="x")
    ttk.Label(mode_row, text="Mode:").pack(side="left")
    mode_var = tk.StringVar()
    mode_dropdown = ttk.Combobox(mode_row, textvariable=mode_var,
                                 values=["Sniper", "AR / SMG", "Shotgun"],
                                 state="readonly", width=20)
    mode_dropdown.pack(side="left", padx=5)

    ttk.Label(mode_row, text="Trigger:").pack(side="left", padx=(20, 0))
    trigger_var = tk.StringVar()
    trigger_dropdown = ttk.Combobox(mode_row, textvariable=trigger_var,
                                    values=["L-Click", "X Button Forward", "X Button Backward"],
                                    state="readonly", width=18)
    trigger_dropdown.pack(side="left", padx=5)

    # ===== Switch Method =====
    switch_frame = ttk.LabelFrame(root, text="Switch Method", padding=5)
    switch_frame.pack(fill="x", padx=10, pady=2)
    switch_var = tk.StringVar(value="qq")
    ttk.Radiobutton(switch_frame, text="QQ (quick switch)", variable=switch_var,
                    value="qq").pack(side="left", padx=10)
    ttk.Radiobutton(switch_frame, text="31 (slot switch)", variable=switch_var,
                    value="31").pack(side="left", padx=10)

    # ===== Delay sliders container =====
    delay_frame_box = ttk.LabelFrame(root, text="Delays (ms)", padding=5)
    delay_frame_box.pack(fill="x", padx=10, pady=2)
    delay_frame = ttk.Frame(delay_frame_box)
    delay_frame.pack(fill="x")

    # ===== Key hold time =====
    hold_frame = ttk.LabelFrame(root, text="Key Hold Time (ms)", padding=5)
    hold_frame.pack(fill="x", padx=10, pady=2)
    hold_row = ttk.Frame(hold_frame)
    hold_row.pack(fill="x")
    ttk.Label(hold_row, text="Hold duration:", width=14).pack(side="left")
    key_hold_var = tk.IntVar(value=40)
    hold_scale = ttk.Scale(hold_row, from_=0, to=200, orient="horizontal",
                           variable=key_hold_var)
    hold_scale.pack(side="left", fill="x", expand=True, padx=5)
    ttk.Label(hold_row, textvariable=key_hold_var, width=4).pack(side="right")

    # ===== Recoil Control =====
    recoil_frame = ttk.LabelFrame(root, text="Recoil Control (AR/SMG)", padding=5)
    recoil_frame.pack(fill="x", padx=10, pady=2)
    recoil_row = ttk.Frame(recoil_frame)
    recoil_row.pack(fill="x")
    ttk.Label(recoil_row, text="Pixels per shot:", width=14).pack(side="left")
    recoil_amt_var = tk.IntVar(value=4)
    recoil_scale = ttk.Scale(recoil_row, from_=0, to=20, orient="horizontal",
                             variable=recoil_amt_var)
    recoil_scale.pack(side="left", fill="x", expand=True, padx=5)
    ttk.Label(recoil_row, textvariable=recoil_amt_var, width=4).pack(side="right")

    # Timeout slider
    timeout_row = ttk.Frame(recoil_frame)
    timeout_row.pack(fill="x", pady=(4, 0))
    ttk.Label(timeout_row, text="Timeout (ms):", width=14).pack(side="left")
    recoil_timeout_var = tk.IntVar(value=1000)
    timeout_scale = ttk.Scale(timeout_row, from_=500, to=3000, orient="horizontal",
                              variable=recoil_timeout_var)
    timeout_scale.pack(side="left", fill="x", expand=True, padx=5)
    ttk.Label(timeout_row, textvariable=recoil_timeout_var, width=5).pack(side="right")

    # Recoil mode indicator
    mode_row2 = ttk.Frame(recoil_frame)
    mode_row2.pack(fill="x", pady=(2, 0))
    ttk.Label(mode_row2, text="Mode:").pack(side="left")
    recoil_mode_var = tk.StringVar(value="Smooth")
    ttk.Label(mode_row2, textvariable=recoil_mode_var,
              font=("", 9, "bold")).pack(side="left", padx=5)

    # ===== Buttons =====
    btn_frame = ttk.Frame(root)
    btn_frame.pack(fill="x", padx=10, pady=5)
    start_btn = ttk.Button(btn_frame, text="Start Listener")
    start_btn.pack(side="left", expand=True, padx=2)
    stop_btn = ttk.Button(btn_frame, text="Stop Listener", state="disabled")
    stop_btn.pack(side="left", expand=True, padx=2)

    # ===== Status =====
    status_var = tk.StringVar(value="Idle")
    ttk.Label(root, textvariable=status_var, font=("", 12, "bold")).pack(pady=2)

    # ===== Event Log =====
    log_frame = ttk.LabelFrame(root, text="Event Log", padding=5)
    log_frame.pack(fill="both", expand=True, padx=10, pady=(2, 10))
    log_text = tk.Text(log_frame, height=10, bg="#2d2d2d", fg="#cccccc",
                       insertbackground="#ffffff", borderwidth=0, wrap="word",
                       state="disabled")
    log_text.pack(fill="both", expand=True)
    log_scroll = ttk.Scrollbar(log_text, command=log_text.yview)
    log_scroll.pack(side="right", fill="y")
    log_text.configure(yscrollcommand=log_scroll.set)

    # --- Collect refs ---
    vars_dict = {
        "mode_var": mode_var,
        "trigger_var": trigger_var,
        "switch_var": switch_var,
        "key_hold_var": key_hold_var,
        "recoil_amt_var": recoil_amt_var,
        "recoil_timeout_var": recoil_timeout_var,
        "recoil_mode_var": recoil_mode_var,
        "profile_var": profile_var,
        "status_var": status_var,
    }

    widgets = {
        "profile_dropdown": profile_dropdown,
        "btn_rename": rename_btn,
        "btn_delete": delete_btn,
        "btn_add": add_btn,
        "btn_export": export_btn,
        "log_text": log_text,
        "delay_frame": delay_frame,
        "start_btn": start_btn,
        "stop_btn": stop_btn,
        "mode_dropdown": mode_dropdown,
        "trigger_dropdown": trigger_dropdown,
        "hold_scale": hold_scale,
        "recoil_scale": recoil_scale,
        "timeout_scale": timeout_scale,
    }

    return root, vars_dict, widgets
