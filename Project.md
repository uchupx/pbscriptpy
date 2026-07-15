# Product Requirements Document (PRD)

**Project Name:** Python Raw Input Macro Tool (CLI & GUI)  
**Document Status:** Draft  
**Platform:** Windows OS  

Minimal Depencies


---

## 1. Ringkasan Proyek (Executive Summary)
Aplikasi ini adalah *tool* automasi makro berbasis Python yang dirancang agar ringan, mandiri (standalone `.exe`), dan mampu berjalan di latar belakang. Aplikasi ini memanfaatkan Windows API (`ctypes`) secara langsung untuk mengelola *Global Hooking* (mendengarkan input) dan *Raw Input Simulation* (mengirim perintah). Dilengkapi dengan antarmuka pengguna (GUI) sederhana, aplikasi ini mengutamakan efisiensi memori tanpa mengandalkan instalasi dependensi pihak ketiga yang kompleks.
ada TIGA mode di sini
  - Sniper: 4-step sequence (RClick → LClick → RClick → Switch), trigger on L-Click 
  - AR/SMG: hold-to-spray loop with optional recoil pull, trigger on L-Click press/release
  - Shotgun: 2-step sequence (LClick → Switch), trigger on L-Click
Bisa pilih trigger antara L-Click, X button forward, X button backward
setiap'->' itu ada lah delay dan delay bisa di setting sesuka hati dari 0ms - 200ms

## 2. Tujuan & Sasaran (Objectives)
* **Aksesibilitas:** Menyediakan aplikasi makro yang bisa dijalankan langsung dengan klik ganda (`.exe`) tanpa perlu instalasi Python di komputer pengguna.
* **Performa:** Memastikan simulasi input dan *listener* berjalan secara asinkron tanpa menyebabkan *freeze* pada sistem operasi atau GUI aplikasi.
* **Akurasi:** Menggunakan metode *low-level input* (`SendInput`) untuk memastikan instruksi makro dieksekusi dengan *delay* yang presisi dan terbaca oleh sistem Windows.

## 3. Spesifikasi Teknis Utama (Technical Specifications)
* **Bahasa Pemrograman:** Python 3.x
* **Library Utama:**
  * `nicegui` (Untuk antarmuka pengguna web-based yang modern, menggantikan tkinter).
  * `ctypes` (Untuk interaksi dengan `user32.dll` Windows API).
  * `threading` (Untuk memisahkan proses UI dan *listener*).
  * `time` (Untuk manajemen *delay* dan *interval*).
* **Kompilasi (Build Tool):** `PyInstaller` (Mode `--onefile` dan `--noconsole`).
* **Target OS:** Windows 10 & Windows 11 (Mewajibkan hak akses *Run as Administrator*).

## 4. Ruang Lingkup Fitur (Feature Scope)

### 4.1. Modul Listener (Global Hooking)
* **Fungsi:** Memantau aktivitas perangkat keras secara global di seluruh sistem operasi.
* **Mekanisme:** Menggunakan `SetWindowsHookEx` (`WH_KEYBOARD_LL` atau `WH_MOUSE_LL`).
* **Kemampuan:** Menangkap pemicu (*trigger*) berupa tombol spesifik (misalnya F8 untuk mulai, F10 untuk berhenti) bahkan saat aplikasi target (*game*/browser) sedang dalam posisi *full screen* atau *in-focus*.

### 4.2. Modul Eksekusi Input (Input Simulation)
* **Fungsi:** Mengirim perintah klik atau ketukan *keyboard* ke sistem operasi.
* **Mekanisme:** Menggunakan fungsi `SendInput` dari Windows API dengan mengkonstruksi struktur `INPUT` dan `MOUSEINPUT` secara manual.
* **Kemampuan:** Melakukan *mouse click* (kiri/kanan) dan *keyboard press* dengan durasi jeda (*delay*) yang bisa dikonfigurasi untuk mensimulasikan jeda manusiawi.

### 4.3. Antarmuka Pengguna (GUI)
* **Fungsi:** Memberikan kontrol visual kepada pengguna untuk mengoperasikan makro.
* **Komponen UI:**
  * **Label Status:** Menampilkan status *Real-time* (Contoh: "Idle", "Listening...", "Macro Running").
  * **Tombol Kontrol:** Tombol *Start Listener* dan *Stop Listener*.
  * **Log Sederhana:** (Opsional) Kotak teks kecil untuk menampilkan aktivitas terakhir.
* **Threading:** UI wajib dijalankan di *Main Thread*, sementara fungsi *Listener* dan *Input Simulation* dieksekusi di *Background Thread* (`daemon=True`) untuk mencegah UI berstatus *Not Responding*.

## 5. Alur Pengguna (User Flow)
1. Pengguna membuka aplikasi `MacroTool.exe` menggunakan klik kanan -> *Run as Administrator*.
2. Jendela UI terbuka menampilkan status "Aplikasi Siap".
3. Pengguna mengklik tombol "Mulai Listener" pada GUI.
4. UI memberikan umpan balik visual bahwa aplikasi sedang mendengarkan pemicu.
5. Pengguna menekan tombol pemicu (*hotkey*) yang telah ditentukan (misal: F8) di mana pun di Windows.
6. Aplikasi menangkap pemicu tersebut dan menjalankan instruksi `SendInput` (misal: melakukan klik kiri berulang).
7. Pengguna menekan tombol berhenti (misal: F10), dan aplikasi berhenti mengirimkan input dan kembali ke status siaga.

## 6. Batasan Sistem & Risiko (Constraints & Limitations)
* **Anti-Cheat Compatibility:** Aplikasi berjalan di lingkungan *User-Mode* (Ring 3). *Game* yang dilindungi oleh sistem keamanan *Kernel-Level Anti-Cheat* (seperti Vanguard, EAC, BattlEye) secara desain akan memblokir perintah simulasi dari aplikasi ini. Aplikasi ini tidak dirancang untuk memintas (*bypass*) proteksi level *kernel*.
* **Keamanan Antivirus (False Positives):** Karena metode pembungkusan `PyInstaller` dan penggunaan *global hooking*, aplikasi `.exe` hasil akhir mungkin terdeteksi sebagai peringatan *False Positive* oleh Windows Defender. Pengecualian (*Exclusion*) direktori perlu diinstruksikan kepada pengguna akhir.

## 7. Kriteria Penerimaan (Acceptance Criteria)
* Aplikasi dapat di-klik ganda dan langsung menampilkan antarmuka `Tkinter`.
* Tombol pemicu dapat terdeteksi meskipun aplikasi tidak sedang aktif dibuka di layar depan (*background execution*).
* Aplikasi tidak mengalami *Crash* atau *Not Responding* saat makro sedang dieksekusi.
* Ukuran file akhir setelah proses *build* tidak memakan memori RAM secara berlebihan (< 50MB *usage*).

contoh script listener dan sendinput
import ctypes

# Konstanta Windows API
WH_MOUSE_LL = 14
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204

# Struktur untuk koordinat mouse
class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", ctypes.c_long * 2),
                ("mouseData", ctypes.c_ulong),
                ("flags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_void_p)]

# Struktur untuk Message Windows (PENTING: Ini yang menyebabkan error tadi)
class MSG(ctypes.Structure):
    _fields_ = [("hwnd", ctypes.c_void_p),
                ("message", ctypes.c_uint),
                ("wParam", ctypes.c_size_t),
                ("lParam", ctypes.c_ssize_t),
                ("time", ctypes.c_ulong),
                ("pt", ctypes.c_long * 2)]

def low_level_mouse_handler(nCode, wParam, lParam):
    if nCode == 0:
        if wParam == WM_LBUTTONDOWN:
            print("Klik Kiri terdeteksi!")
        elif wParam == WM_RBUTTONDOWN:
            print("Klik Kanan terdeteksi!")
    return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

# Mendefinisikan tipe fungsi untuk hook
HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_long, ctypes.POINTER(ctypes.c_long))
proc = HOOKPROC(low_level_mouse_handler)

# Memasang hook
hook = ctypes.windll.user32.SetWindowsHookExA(WH_MOUSE_LL, proc, None, 0)

print("Mouse listener aktif! Silakan klik di desktop/aplikasi.")

# Menggunakan struktur MSG yang sudah benar
msg = MSG()
while ctypes.windll.user32.GetMessageA(ctypes.byref(msg), None, 0, 0):
    ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
    ctypes.windll.user32.DispatchMessageA(ctypes.byref(msg))
	
	import ctypes
import time

# Konstanta Windows API untuk simulasi input
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("mi", MOUSEINPUT)]

def klik_kiri():
    # Down
    x_down = INPUT(type=0, mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_LEFTDOWN))
    ctypes.windll.user32.SendInput(1, ctypes.byref(x_down), ctypes.sizeof(x_down))
    
    # Sedikit delay antar klik agar lebih "manusiawi" (opsional)
    time.sleep(0.05)
    
    # Up
    x_up = INPUT(type=0, mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_LEFTUP))
    ctypes.windll.user32.SendInput(1, ctypes.byref(x_up), ctypes.sizeof(x_up))

# --- EKSEKUSI ---
print("Program dimulai. Menunggu 3 detik sebelum klik...")
time.sleep(3)  # Delay 3 detik yang Anda minta
klik_kiri()
print("Klik kiri berhasil dieksekusi!")