# app/toast.py - Toast overlay (Toplevel, topmost, auto-hide)
# ponytail: flat globals, no class tax

import tkinter as tk

_root = None
_toast_window = None
_toast_timer = None


def init(root):
    global _root
    _root = root

def show_toast(text, duration=2500):
    global _toast_window, _toast_timer
    if _toast_timer:
        _root.after_cancel(_toast_timer)
        _toast_timer = None
    if _toast_window is None:
        _toast_window = tk.Toplevel(_root)
        _toast_window.overrideredirect(True)
        _toast_window.attributes('-topmost', True)
        _toast_window.configure(bg='#1e1e1e')
        _toast_label = tk.Label(
            _toast_window, text='', font=('Consolas', 10, 'bold'),
            fg='#ffffff', bg='#1e1e1e', padx=8, pady=4,
            anchor='w', justify='left'
        )
        _toast_label.pack()
    _toast_label = _toast_window.winfo_children()[0]
    _toast_label.config(text=text)
    _toast_window.update_idletasks()
    w = min(_toast_window.winfo_reqwidth(), _root.winfo_screenwidth() - 20)
    _toast_window.geometry(f'{w}x{_toast_window.winfo_reqheight()}+10+10')
    _toast_window.deiconify()
    _toast_timer = _root.after(duration, _hide_toast)

def _hide_toast():
    global _toast_timer
    _toast_timer = None
    if _toast_window:
        _toast_window.withdraw()
