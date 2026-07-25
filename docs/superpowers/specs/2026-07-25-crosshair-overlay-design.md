# Crosshair Overlay — Sniper Mode

**Date:** 2026-07-25  
**Status:** Draft  
**Author:** AI-assisted brainstorming

## Problem

Sniper mode (RClick→LClick→RClick→Switch) membuka scope yang menghalangi view. Pemain perlu acuan tengah layar untuk aim. Crosshair overlay di mode sniper solves this.

## Design

### Approach: tkinter Toplevel + Canvas + transparent color key

- Window overlay terpisah, `overrideredirect(True)`, `attributes('-topmost', True)`
- Transparansi via `attributes('-transparentcolor', 'black')` — background hitam = invisible
- Click-through via `WS_EX_TRANSPARENT | WS_EX_LAYERED` (ctypes `SetWindowLong`) — klik tembus ke game
- Crosshair digambar dengan `Canvas` (`create_oval` untuk dot, `create_line` untuk +)
- Ukuran overlay: 32×32 px. Posisi: center layar (`winfo_screenwidth/height`)

### State (`shape` cycle)

```
0 → dot
1 → cross (+)
2 → off (hidden)
```

`Ctrl+9` memutar siklus ini. Default: `0` (dot).

### Warna

4 warna default, fungsi bisa terima hex `"#rrggbb"` juga:

| Index | Warna  | Hex       |
|-------|--------|-----------|
| 0     | Merah  | `#ff0000` |
| 1     | Hijau  | `#00ff00` |
| 2     | Cyan   | `#00ffff` |
| 3     | Kuning | `#ffff00` |

`Ctrl+0` cycle warna. Default: merah.

### File baru: `app/crosshair.py`

Module-level state + functions:

| Function          | Behavior                                  |
|-------------------|-------------------------------------------|
| `init(parent)`    | Bikin Toplevel + Canvas, center window    |
| `show()`          | `deiconify()`                             |
| `hide()`          | `withdraw()`                              |
| `cycle_shape()`   | `(shape + 1) % 3`, redraw. Jika 2 → hide |
| `set_shape(idx)`  | Set shape langsung, redraw                |
| `cycle_color()`   | `(color_idx + 1) % 4`, redraw             |
| `set_color(val)`  | Accept int index atau hex string          |

`redraw()` internal — hapus item canvas, gambar sesuai `_shape` dan `_warna`.

### Integrasi

- **Mode switch** (`app/profiles.py` `on_mode_change` atau `rebuild_delays`): jika mode `"sniper"` → `crosshair.show()`, jika bukan → `crosshair.hide()`
- **Auto-show on start**: pas app jalan, kalo profile aktif mode sniper → `show()`
- **On close**: `crosshair.hide()` + `destroy()` di `on_close`
- **Shortcuts** (`app/action_handlers.py`):
  - `Ctrl+9` → `crosshair.cycle_shape()` — cuma jalan jika mode `"sniper"`
  - `Ctrl+0` → `crosshair.cycle_color()` — cuma jalan jika mode `"sniper"`

### Dependencies

Zero baru. Tkinter + ctypes sudah ada di codebase.

### File changes summary

| File                      | Change                                    |
|---------------------------|-------------------------------------------|
| `app/crosshair.py`        | **New** — overlay window + canvas drawing |
| `app/__main__.py`         | Init crosshair di `main()`, panggil `on_close` destroy |
| `app/profiles.py`         | Show/hide crosshair on mode change        |
| `app/action_handlers.py`  | `Ctrl+9`, `Ctrl+0` handler — cuma sniper mode |
| `engine/shortcuts.py`     | (maybe) tambah bind `Ctrl+9`, `Ctrl+0` jika perlu |

### Self-review notes

- Tidak ada TBD/TODO di spec ini.
- Scope terdefinisi jelas: overlay crosshair untuk sniper mode.
- Semua bagian konsisten: tkinter style, ponytail-friendly, tanpa dependency baru.
