# -*- coding: utf-8 -*-
r"""
Antigravity Swarm Manager (Multi-Account x Multi-Project Launcher)
==================================================================
Phiên bản: 2.2 (Nâng Cấp Pro: Auto-Sync Antigravity Projects & Quick Folder Picker)

Tính năng chính:
- [P0 - Tự Động Auto-Sync Projects từ Database Antigravity]:
  - Đọc trực tiếp file SQLite conversation_summaries.db của Antigravity.
  - Quét workspace_uris và title, giải mã URI file:///... thành Windows path chuẩn (Z:\..., C:\...).
  - Thống kê số lượng cuộc hội thoại (convs) và tên tác vụ gần nhất cho từng dự án.
  - Nút "🔄 Đồng Bộ Lại Từ Antigravity" làm mới danh sách tức thời.
- [P0 - Tiện Ích Chọn Thư Mục Khác (Quick Folder Picker)]:
  - Nút "📁 Chọn Thư Mục Khác..." mở Windows Folder Picker chọn bất kỳ thư mục nào (Windows / WSL2 Z:).
  - Tự động ghi nhận vào danh sách dự án và sẵn sàng mở ngay với Antigravity.
- [P0 - Win32 Title Hook]: Tự động đổi tiêu đề cửa sổ Antigravity & Taskbar Windows:
  "[Gmail: <Tên/Email>] - <Tên Dự Án> - Antigravity" giúp phân biệt tức thì các cửa sổ.
- [P0 - Khay Hệ Thống (System Tray)]: 
  - Khi bấm tắt (dấu X), app tự động ẩn ngầm vào System Tray bên cạnh đồng hồ Windows.
  - Click chuột hoặc double click vào icon khay để mở lại giao diện.
  - Chuột phải vào tray icon mở menu: "🖥️ Mở Giao Diện", "💥 Đóng Tất Cả Cửa Sổ AI", "❌ Thoát Hoàn Toàn".
- [P0 - Tự Khởi Động Cùng Windows]:
  - Đăng ký vào Windows Registry (HKCU Run), tự khởi động ngầm vào System Tray khi bật máy (--tray).
  - Tùy chọn Bật/Tắt trực tiếp trên giao diện người dùng.
- [P0 - Lưu Cấu Hình Vĩnh Viễn]:
  - Tự động lưu và nhớ đường dẫn Antigravity.exe, tài khoản Gmail và dự án đã chọn gần nhất.
  - Bật máy lên chỉ việc vào app và chọn tài khoản + dự án làm việc ngay.
- [P1 - Quản lý CRUD]: Thêm / Sửa / Xóa Profile và Dự án trực quan.
- [P1 - Cảnh báo xung đột]: Tự động phát hiện và cảnh báo nguy cơ đè code khi nhiều Gmail
  cùng mở 1 thư mục dự án (khuyến nghị Git Worktree).
- [P2 - Giám sát Realtime]: Bảng theo dõi tiến trình sống (PID, Tài khoản, Dự án, Uptime),
  kèm tính năng Focus cửa sổ và Dừng / Kill tiến trình (đơn lẻ hoặc hàng loạt).
"""

import os
import sys
import re
import json
import time
import threading
import subprocess
import glob
from pathlib import Path
import shutil
import sqlite3
import urllib.parse
import hashlib
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import winreg

# ---------------------------------------------------------------------------
# Win32 API Integration (Pure ctypes, 64-bit safe, không cần cài pywin32)
# ---------------------------------------------------------------------------
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

TH32CS_SNAPPROCESS = 0x00000002

class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260)
    ]

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG)
    ]

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HICON),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON)
    ]

# Setup Win32 Process and Window API Prototypes
kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE

kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32FirstW.restype = wintypes.BOOL

kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.restype = wintypes.BOOL

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL

user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int

user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

user32.SetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
user32.SetWindowTextW.restype = wintypes.BOOL

user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL

user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL

user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND

user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL

user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL

user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL

user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL

# Setup Win32 System Tray & Window Class API Prototypes
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wintypes.ATOM

user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID
]
user32.CreateWindowExW.restype = wintypes.HWND

user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t

user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL

user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL

user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.TranslateMessage.restype = wintypes.BOOL

user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = ctypes.c_ssize_t

user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostQuitMessage.restype = None

user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL

user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
user32.LoadIconW.restype = wintypes.HICON

user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.LoadImageW.restype = wintypes.HANDLE

user32.CreatePopupMenu.argtypes = []
user32.CreatePopupMenu.restype = wintypes.HMENU

user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
user32.AppendMenuW.restype = wintypes.BOOL

user32.TrackPopupMenu.argtypes = [
    wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, ctypes.c_void_p
]
user32.TrackPopupMenu.restype = wintypes.UINT

user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.DestroyMenu.restype = wintypes.BOOL

# ---------------------------------------------------------------------------
# Constants for System Tray & Win32 Popup Menu
# ---------------------------------------------------------------------------
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIM_SETVERSION = 0x00000004

NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010

NIIF_INFO = 0x00000001
NIIF_WARNING = 0x00000002
NIIF_ERROR = 0x00000003

WM_USER = 0x0400
WM_TRAYICON = WM_USER + 1024

WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_CONTEXTMENU = 0x007B
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
IDI_APPLICATION = 32512

# Win32 Menu Flags and Command IDs
MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080

ID_TRAY_OPEN = 1001
ID_TRAY_KILL_ALL = 1002
ID_TRAY_QUIT = 1003

class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", ctypes.c_wchar * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", ctypes.c_wchar * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", ctypes.c_wchar * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HICON)
    ]

shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL


# ---------------------------------------------------------------------------
# Windows Registry Autostart Management
# ---------------------------------------------------------------------------
REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_APP_NAME = "AntigravitySwarmManager"
DESKTOP_EXE_PATH = r"C:\Users\maing\Desktop\Antigravity-MultiProject-Launcher\AntigravitySwarmManager.exe"

def get_registered_exe_path():
    """Xác định đường dẫn file exe phù hợp để đăng ký vào Registry Run."""
    if getattr(sys, 'frozen', False):
        return sys.executable
    if os.path.isfile(DESKTOP_EXE_PATH):
        return DESKTOP_EXE_PATH
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_exe = os.path.join(script_dir, "AntigravitySwarmManager.exe")
    if os.path.isfile(local_exe):
        return local_exe
    return DESKTOP_EXE_PATH

def is_autostart_registered() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, REG_APP_NAME)
            return bool(val)
    except Exception:
        return False

def set_autostart_registry(enable: bool) -> bool:
    try:
        if enable:
            exe = get_registered_exe_path()
            cmd = f'"{exe}" --tray'
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY) as key:
                winreg.SetValueEx(key, REG_APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, REG_APP_NAME)
            except FileNotFoundError:
                pass
        return True
    except Exception as e:
        print(f"Lỗi thiết lập Registry Run: {e}")
        return False


# ---------------------------------------------------------------------------
# Pure ctypes Win32 System Tray Manager (Native Menu, Không phụ thuộc thư viện ngoài)
# ---------------------------------------------------------------------------
class SystemTrayManager:
    """
    Quản lý icon khay hệ thống (System Tray) bằng Win32 API thuần (ctypes).
    Chạy trong luồng ngầm độc lập với native Win32 context menu,
    tự động giải phóng chuột khi click ra ngoài, và giao tiếp an toàn với Tkinter main loop.
    """
    def __init__(self, tooltip="Antigravity Swarm Manager", on_open=None, on_kill_all=None, on_quit=None):
        self.tooltip = tooltip
        self.on_open = on_open
        self.on_kill_all = on_kill_all
        self.on_quit = on_quit
        self.hwnd = None
        self.nid = None
        self.thread = None
        self.running = False
        self._last_click_time = 0.0
        self._wndproc_ref = None # Giữ reference chống bị garbage collection
        self._start_tray_thread()

    def _start_tray_thread(self):
        ready_event = threading.Event()
        self.thread = threading.Thread(target=self._run_message_loop, args=(ready_event,), daemon=True)
        self.thread.start()
        ready_event.wait(timeout=2.0)

    def _get_icon_handle(self):
        # 1. Thử nạp icon từ file app_icon.ico
        search_dirs = [
            r"C:\Users\maing\Desktop\Antigravity-MultiProject-Launcher",
            os.path.dirname(os.path.abspath(__file__))
        ]
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            search_dirs.insert(0, getattr(sys, '_MEIPASS', base_dir))
            search_dirs.insert(0, base_dir)

        for d in search_dirs:
            for name in ["app_icon.ico", "icon.ico", "app.ico", "antigravity.ico", "favicon.ico"]:
                p = os.path.join(d, name)
                if os.path.isfile(p):
                    try:
                        h = user32.LoadImageW(None, p, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
                        if h:
                            return h
                    except Exception:
                        pass

        # 2. Thử nạp icon từ module exe hiện tại (ExtractIconExW)
        try:
            h_icon = wintypes.HICON()
            shell32.ExtractIconExW.argtypes = [wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.HICON), ctypes.POINTER(wintypes.HICON), wintypes.UINT]
            shell32.ExtractIconExW.restype = wintypes.UINT
            exe_path = sys.executable if getattr(sys, 'frozen', False) else r"C:\Users\maing\Desktop\Antigravity-MultiProject-Launcher\AntigravitySwarmManager.exe"
            if os.path.isfile(exe_path):
                cnt = shell32.ExtractIconExW(exe_path, 0, None, ctypes.byref(h_icon), 1)
                if cnt > 0 and h_icon.value:
                    return h_icon.value
        except Exception:
            pass

        # 3. Fallback: Icon mặc định của Windows
        try:
            h = user32.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION))
            if h:
                return h
        except Exception:
            pass
        return 0

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAYICON:
            if lparam == WM_LBUTTONDBLCLK:
                self._last_click_time = time.time()
                if self.on_open:
                    self.on_open()
                return 0
            elif lparam == WM_LBUTTONUP:
                now = time.time()
                # Debounce: chỉ kích hoạt khi không trùng double-click trong 0.4s
                if now - self._last_click_time > 0.4:
                    self._last_click_time = now
                    if self.on_open:
                        self.on_open()
                return 0
            elif lparam in (WM_RBUTTONUP, WM_CONTEXTMENU):
                pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                user32.SetForegroundWindow(hwnd)

                h_menu = user32.CreatePopupMenu()
                user32.AppendMenuW(h_menu, MF_STRING, ID_TRAY_OPEN, "🖥️  Mở Giao Diện")
                user32.AppendMenuW(h_menu, MF_STRING, ID_TRAY_KILL_ALL, "💥  Đóng Tất Cả Cửa Sổ AI")
                user32.AppendMenuW(h_menu, MF_SEPARATOR, 0, None)
                user32.AppendMenuW(h_menu, MF_STRING, ID_TRAY_QUIT, "❌  Thoát Hoàn Toàn")

                cmd = user32.TrackPopupMenu(
                    h_menu,
                    TPM_RETURNCMD | TPM_NONOTIFY | TPM_RIGHTBUTTON,
                    pt.x, pt.y,
                    0,
                    hwnd,
                    None
                )
                # Standard Win32 fix: post WM_NULL để Windows tự đóng menu khi click ra ngoài
                user32.PostMessageW(hwnd, 0, 0, 0)
                user32.DestroyMenu(h_menu)

                if cmd == ID_TRAY_OPEN and self.on_open:
                    self.on_open()
                elif cmd == ID_TRAY_KILL_ALL and self.on_kill_all:
                    self.on_kill_all()
                elif cmd == ID_TRAY_QUIT and self.on_quit:
                    self.on_quit()
                return 0
        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run_message_loop(self, ready_event):
        self.running = True
        h_inst = kernel32.GetModuleHandleW(None)
        class_name = f"AntigravityTrayWnd_{int(time.time() * 1000)}"

        self._wndproc_ref = WNDPROC(self._wndproc)

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = 0
        wc.lpfnWndProc = self._wndproc_ref
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = h_inst
        wc.hIcon = 0
        wc.hCursor = 0
        wc.hbrBackground = 0
        wc.lpszMenuName = None
        wc.lpszClassName = class_name
        wc.hIconSm = 0

        reg = user32.RegisterClassExW(ctypes.byref(wc))
        if not reg:
            ready_event.set()
            return

        self.hwnd = user32.CreateWindowExW(
            0, class_name, "AntigravityTrayWindow",
            0, 0, 0, 0, 0,
            0, 0, h_inst, None
        )

        if not self.hwnd:
            ready_event.set()
            return

        h_icon = self._get_icon_handle()

        self.nid = NOTIFYICONDATAW()
        self.nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        self.nid.hWnd = self.hwnd
        self.nid.uID = 2024
        self.nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        self.nid.uCallbackMessage = WM_TRAYICON
        self.nid.hIcon = h_icon
        self.nid.szTip = self.tooltip[:127]

        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self.nid))
        ready_event.set()

        msg = wintypes.MSG()
        while self.running:
            res = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if res <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self.nid and self.hwnd:
            try:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self.nid))
            except Exception:
                pass
        if self.hwnd:
            try:
                user32.DestroyWindow(self.hwnd)
            except Exception:
                pass

    def show_balloon(self, title, message):
        """Hiển thị thông báo Toast / Balloon tooltip trên khay hệ thống."""
        if not self.nid or not self.hwnd:
            return
        try:
            self.nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_INFO
            self.nid.szInfoTitle = title[:63]
            self.nid.szInfo = message[:255]
            self.nid.dwInfoFlags = NIIF_INFO
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self.nid))
        except Exception as e:
            print(f"Lỗi show_balloon: {e}")

    def destroy(self):
        """Dừng luồng khay và gỡ icon khỏi Windows Taskbar."""
        self.running = False
        if self.hwnd:
            if self.nid:
                try:
                    shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self.nid))
                except Exception:
                    pass
            try:
                user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Tiến trình con & Tiêu đề cửa sổ (Process Tree & Window Title Functions)
# ---------------------------------------------------------------------------
def get_child_pids(parent_pid):
    """Lấy danh sách tất cả PID con của một tiến trình cha (O(N) BFS traversal)."""
    pids = {parent_pid}
    h_snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if h_snapshot == wintypes.HANDLE(-1).value or h_snapshot == 0:
        return pids

    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)

    tree = {}
    if kernel32.Process32FirstW(h_snapshot, ctypes.byref(pe)):
        while True:
            tree.setdefault(pe.th32ParentProcessID, []).append(pe.th32ProcessID)
            if not kernel32.Process32NextW(h_snapshot, ctypes.byref(pe)):
                break
    kernel32.CloseHandle(h_snapshot)

    queue = [parent_pid]
    while queue:
        curr = queue.pop(0)
        for child in tree.get(curr, []):
            if child not in pids:
                pids.add(child)
                queue.append(child)
    return pids

def get_window_pid(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value

def get_window_title(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length > 0:
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    return ""

def set_window_title(hwnd, new_title):
    user32.SetWindowTextW(hwnd, new_title)

def find_windows_for_pids(pids):
    """Tìm tất cả HWND hiển thị của cửa sổ giao diện chính thuộc danh sách PID."""
    results = []
    GW_OWNER = 4

    def enum_windows_callback(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True

        pid = get_window_pid(hwnd)
        if pid in pids:
            # Bỏ qua các cửa sổ con/popup bị sở hữu bởi cửa sổ khác
            owner = user32.GetWindow(hwnd, GW_OWNER)
            if owner != 0:
                return True

            title = get_window_title(hwnd)
            if not title or not title.strip():
                return True

            # Bỏ qua các cửa sổ phụ/accessibility nội bộ của Chromium
            skip_titles = {"Chrome Legacy Window", "Default IME", "MSCTFIME UI"}
            if title.strip() in skip_titles:
                return True

            # Bỏ qua các cửa sổ dummy 0x0
            rect = RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                width = rect.right - rect.left
                height = rect.bottom - rect.top
                if width > 150 and height > 150:
                    results.append((hwnd, pid, title))
        return True

    cb = WNDENUMPROC(enum_windows_callback)
    user32.EnumWindows(cb, 0)
    return results

def kill_process_tree(pid, hwnd=None, extra_pids=None):
    """Dừng triệt để tiến trình và toàn bộ tiến trình con bằng taskkill và WM_CLOSE."""
    pids_to_kill = set()
    if pid:
        pids_to_kill.add(pid)
        pids_to_kill.update(get_child_pids(pid))
    if extra_pids:
        pids_to_kill.update(extra_pids)
    if hwnd and user32.IsWindow(hwnd):
        w_pid = get_window_pid(hwnd)
        if w_pid:
            pids_to_kill.add(w_pid)
            pids_to_kill.update(get_child_pids(w_pid))
        try:
            user32.PostMessageW(hwnd, 0x0010, 0, 0) # WM_CLOSE
        except Exception:
            pass

    for p in pids_to_kill:
        try:
            subprocess.run(f"taskkill /F /T /PID {p}", shell=True, capture_output=True)
        except Exception as e:
            print(f"Lỗi khi kill PID {p}: {e}")


# ---------------------------------------------------------------------------
# Cấu hình & Dữ liệu Vĩnh Viễn (Config & Persistence)
# ---------------------------------------------------------------------------
CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Antigravity_Swarm_Manager")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LOCAL_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
DESKTOP_CONFIG_FILE = os.path.join(r"C:\Users\maing\Desktop\Antigravity-MultiProject-Launcher", "config.json")

def get_default_antigravity_path():
    """Tự động tìm kiếm đường dẫn thực thi của Antigravity.exe trong Registry và hệ thống."""
    # 1. Thử tìm qua Registry App Paths (chuẩn Windows)
    for root_hkey in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
        for subkey in [
            r"Software\Microsoft\Windows\CurrentVersion\App Paths\Antigravity.exe",
            r"Software\Microsoft\Windows\CurrentVersion\App Paths\antigravity.exe"
        ]:
            try:
                with winreg.OpenKey(root_hkey, subkey) as k:
                    val, _ = winreg.QueryValueEx(k, "")
                    if val and os.path.isfile(val):
                        return val
            except Exception:
                pass

    # 2. Thử tìm qua PATH môi trường
    try:
        which_path = shutil.which("Antigravity.exe") or shutil.which("antigravity.exe") or shutil.which("antigravity")
        if which_path and os.path.isfile(which_path):
            return which_path
    except Exception:
        pass

    # 3. Thử tìm qua các thư mục cài đặt tiêu chuẩn
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", "")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "")
    user_profile = os.environ.get("USERPROFILE", "")
    candidates = [
        os.path.join(local_app_data, "Programs", "Antigravity", "Antigravity.exe"),
        os.path.join(local_app_data, "Programs", "antigravity", "Antigravity.exe"),
        os.path.join(local_app_data, "Antigravity", "Antigravity.exe"),
        os.path.join(local_app_data, "antigravity", "Antigravity.exe"),
        os.path.join(local_app_data, "Google", "Antigravity", "Antigravity.exe"),
        os.path.join(program_files, "Antigravity", "Antigravity.exe"),
        os.path.join(program_files_x86, "Antigravity", "Antigravity.exe"),
        os.path.join(user_profile, r"AppData\Local\Programs\Antigravity\Antigravity.exe"),
        r"C:\Users\maing\AppData\Local\Programs\Antigravity\Antigravity.exe"
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return ""

def load_config():
    """Đọc cấu hình vĩnh viễn với cơ chế kiểm tra nhiều vị trí và ưu tiên file mới nhất theo mtime."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    candidate_files = [CONFIG_FILE, LOCAL_CONFIG_FILE, DESKTOP_CONFIG_FILE]
    existing_files = [f for f in candidate_files if os.path.isfile(f)]
    # Sắp xếp file theo modification time giảm dần (mới nhất lên đầu)
    existing_files.sort(key=lambda p: os.path.getmtime(p), reverse=True)

    cfg = None
    for target_file in existing_files:
        try:
            with open(target_file, "r", encoding="utf-8") as fp:
                loaded = json.load(fp)
                if isinstance(loaded, dict) and loaded:
                    cfg = loaded
                    break
        except Exception:
            pass

    default_profiles_base = os.path.join(os.environ.get("APPDATA", ""), "Antigravity_Profiles")
    default_config = {
        "antigravity_path": get_default_antigravity_path(),
        "autostart": True,
        "last_profile_id": "profile_1",
        "last_project_id": "proj_timioffice",
        "profiles": [
            {
                "id": "profile_1",
                "name": "Tài khoản Chính (Main)",
                "email": "thanhthien.work@gmail.com",
                "data_dir": os.path.join(default_profiles_base, "profile_main")
            },
            {
                "id": "profile_2",
                "name": "Tài khoản Phụ 1 (Dev)",
                "email": "dev1.antigravity@gmail.com",
                "data_dir": os.path.join(default_profiles_base, "profile_dev1")
            }
        ],
        "projects": [
            {
                "id": "proj_timioffice",
                "name": "Timioffice",
                "path": r"Z:\home\thanhthien\projects\timioffice"
            }
        ],
        "mappings": {}
    }

    if not cfg:
        cfg = default_config
    else:
        # Bảo đảm các trường bắt buộc luôn hiện diện
        for k, v in default_config.items():
            if k not in cfg or cfg[k] is None:
                cfg[k] = v

    # Nếu antigravity_path trong config rỗng hoặc không tồn tại, thử tìm lại tự động
    if not cfg.get("antigravity_path") or not os.path.isfile(cfg["antigravity_path"]):
        detected = get_default_antigravity_path()
        if detected:
            cfg["antigravity_path"] = detected

    save_config(cfg)
    return cfg

def save_config(cfg):
    """Lưu vĩnh viễn cấu hình vào %APPDATA% và đồng bộ thư mục Desktop/Local."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Lỗi lưu config vào {CONFIG_FILE}: {e}")

    for target in [LOCAL_CONFIG_FILE, DESKTOP_CONFIG_FILE]:
        try:
            d = os.path.dirname(target)
            if os.path.isdir(d):
                with open(target, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=4, ensure_ascii=False)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Antigravity Database Integration & Auto-Sync (conversation_summaries.db)
# ---------------------------------------------------------------------------
def get_antigravity_db_path():
    """Tự động phát hiện vị trí file SQLite conversation_summaries.db của Antigravity."""
    home = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    candidates = [
        os.path.join(home, ".gemini", "antigravity", "conversation_summaries.db"),
        r"C:\Users\maing\.gemini\antigravity\conversation_summaries.db",
        os.path.join(home, ".antigravity", "conversation_summaries.db"),
        os.path.join(os.environ.get("APPDATA", ""), "Antigravity", "conversation_summaries.db"),
        os.path.join(os.environ.get("APPDATA", ""), "..", ".gemini", "antigravity", "conversation_summaries.db"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "..", ".gemini", "antigravity", "conversation_summaries.db")
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return os.path.abspath(c)

    # Thử quét tìm kiếm nhanh trong thư mục .gemini
    gemini_dir = os.path.join(home, ".gemini")
    if os.path.isdir(gemini_dir):
        try:
            found = glob.glob(os.path.join(gemini_dir, "**", "conversation_summaries.db"), recursive=True)
            if found and os.path.isfile(found[0]):
                return os.path.abspath(found[0])
        except Exception:
            pass

    return os.path.join(home, ".gemini", "antigravity", "conversation_summaries.db")

def uri_to_windows_path(uri_str):
    r"""
    Chuyển đổi URI file:///... hoặc WSL path thành đường dẫn Windows chuẩn.
    Ví dụ:
      file:///z:/home/thanhthien/projects/timioffice -> Z:\home\thanhthien\projects\timioffice
      file:///z%3A/home/thanhthien/projects/timioffice -> Z:\home\thanhthien\projects\timioffice
      file:///home/thanhthien/projects/timioffice   -> Z:\home\thanhthien\projects\timioffice
      file:///c:/laragon/www/gecafe                 -> C:\laragon\www\gecafe
      file:///c%3A/Docker                           -> C:\Docker
      file:///c:/laragon/www/baogiaTimioffice       -> C:\laragon\www\baogiaTimioffice
      file://wsl$/Ubuntu/home/thanhthien            -> \\wsl$\Ubuntu\home\thanhthien
    """
    if not uri_str:
        return ""
    uri_str = str(uri_str).strip().strip("'\"")
    decoded = urllib.parse.unquote(uri_str)

    # 1. Xử lý VS Code remote URI (ví dụ: vscode-remote://wsl%2Bubuntu/home/...)
    if "vscode-remote://" in decoded or "vscode-vfs://" in decoded:
        m = re.search(r'/(home/[^\s?#]+)', decoded)
        if m:
            decoded = "z:/" + m.group(1)
        else:
            decoded = re.sub(r'^[a-z\-]+://[^/]+/', '/', decoded)

    # 2. Xử lý UNC path (wsl$ hoặc mạng nội bộ)
    is_unc = False
    if decoded.startswith("file:////") or decoded.startswith("file://wsl$") or decoded.startswith("file://wsl.localhost"):
        is_unc = True
        decoded = decoded[7:] # bỏ tiền tố "file://"
    elif decoded.startswith("file:///"):
        decoded = decoded[8:]
    elif decoded.startswith("file://"):
        decoded = decoded[7:]
    elif decoded.startswith("file:"):
        decoded = decoded[5:]

    if is_unc or decoded.startswith("wsl$") or decoded.startswith("wsl.localhost") or decoded.startswith("//") or decoded.startswith("\\\\"):
        decoded = decoded.replace("/", "\\")
        if not decoded.startswith("\\\\"):
            decoded = "\\\\" + decoded.lstrip("\\")
        return os.path.normpath(decoded)

    # Xử lý URI có authority localhost/ (ví dụ file://localhost/C:/...)
    if decoded.lower().startswith("localhost/") or decoded.lower().startswith("localhost\\"):
        decoded = decoded[10:]

    # 3. Chuẩn hóa nếu có dấu gạch chéo đứng trước ổ đĩa (ví dụ /z:/ hoặc /c:/)
    while decoded.startswith("/") and len(decoded) >= 3 and decoded[2] == ":":
        decoded = decoded[1:]

    # 4. Nhận diện đường dẫn WSL Linux (/home/... hoặc home/...) -> map sang ổ Z: trên Windows
    if decoded.startswith("/home/") or decoded.startswith("\\home\\") or decoded == "/home" or decoded == "\\home":
        decoded = "z:" + ("/" + decoded.lstrip("/\\"))
    elif decoded.startswith("home/") or decoded.startswith("home\\"):
        decoded = "z:/" + decoded

    # 5. Viết hoa ký tự ổ đĩa (z: -> Z:, c: -> C:)
    if len(decoded) >= 2 and decoded[1] == ":" and decoded[0].isalpha():
        decoded = decoded[0].upper() + decoded[1:]

    path = decoded.replace("/", "\\")
    return os.path.normpath(path)

def parse_workspace_uris(raw_val):
    """
    Trích xuất danh sách URI từ trường workspace_uris.
    Hỗ trợ mọi định dạng: JSON array of objects/strings, Dict, Single String, CSV, Multi-line.
    """
    if not raw_val:
        return []

    results = []

    def _extract(val):
        if not val:
            return
        if isinstance(val, list):
            for item in val:
                _extract(item)
        elif isinstance(val, dict):
            # Nhận diện các thuộc tính tiêu chuẩn trong vscode.Uri serialization
            for key in ["_formatted", "fsPath", "path", "uri", "external", "raw"]:
                if key in val and val[key]:
                    _extract(val[key])
                    return
            for v in val.values():
                if isinstance(v, (str, dict, list)):
                    _extract(v)
        elif isinstance(val, str):
            s = val.strip().strip("'\"")
            if not s:
                return
            # Thử giải mã nếu là chuỗi JSON hợp lệ
            if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
                try:
                    loaded = json.loads(s)
                    _extract(loaded)
                    return
                except Exception:
                    pass
            # Tìm kiếm các URI bằng regex
            uris = re.findall(r'(?:file|vscode-remote|vscode-vfs):///[^\s",\'\]\}]+', s)
            if uris:
                results.extend(uris)
                return
            # Tách dòng nếu có nhiều dòng
            if "\n" in s:
                for line in s.splitlines():
                    _extract(line)
                return
            # Phân tách theo dấu phẩy nếu chứa chuỗi URI
            if "," in s and ("file:" in s or "/" in s or "\\" in s):
                for part in s.split(","):
                    _extract(part)
                return
            results.append(s)

    _extract(raw_val)

    # Khử trùng lặp và giữ nguyên thứ tự xuất hiện
    clean_list = []
    seen = set()
    for item in results:
        item_str = str(item).strip().strip("'\"")
        if item_str and item_str not in seen:
            seen.add(item_str)
            clean_list.append(item_str)
    return clean_list

def sync_projects_from_db():
    """
    Đọc trực tiếp file SQLite conversation_summaries.db của Antigravity.
    Quét bảng conversation_summaries lấy workspace_uris và title thực tế.
    Trả về danh sách dự án với số lượng hội thoại và tên hội thoại gần nhất.
    """
    db_path = get_antigravity_db_path()
    if not db_path or not os.path.isfile(db_path):
        return []

    conn = None
    try:
        # Chuẩn hóa URI mở read-only an toàn tuyệt đối trên Windows (RFC compliant)
        try:
            db_uri = Path(os.path.abspath(db_path)).as_uri() + "?mode=ro"
            conn = sqlite3.connect(db_uri, uri=True, timeout=3.0)
        except Exception:
            try:
                db_abs = os.path.abspath(db_path).replace("\\", "/")
                uri_conn = f"file:///{urllib.parse.quote(db_abs, safe='/:')}?mode=ro"
                conn = sqlite3.connect(uri_conn, uri=True, timeout=3.0)
            except Exception:
                conn = sqlite3.connect(db_path, timeout=3.0)

        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conversation_summaries'")
        if not cursor.fetchone():
            return []

        cursor.execute("PRAGMA table_info(conversation_summaries)")
        columns = [row[1] for row in cursor.fetchall()]

        uri_col = None
        for c in ["workspace_uris", "workspace_uri", "workspaces", "workspace"]:
            if c in columns:
                uri_col = c
                break
        if not uri_col:
            return []

        title_col = "title" if "title" in columns else None

        time_col = None
        for c in ["updated_at", "last_updated_at", "last_modified", "timestamp", "created_at"]:
            if c in columns:
                time_col = c
                break
        if not time_col:
            time_col = "rowid"

        query = f"SELECT {uri_col}"
        if title_col:
            query += f", {title_col}"
        else:
            query += ", ''"
        query += f", {time_col} FROM conversation_summaries WHERE {uri_col} IS NOT NULL AND {uri_col} != '' ORDER BY {time_col} DESC"

        cursor.execute(query)
        rows = cursor.fetchall()

        project_map = {}
        for raw_uris, conv_title, _ts in rows:
            extracted_uris = parse_workspace_uris(raw_uris)
            clean_title = " ".join((conv_title or "").split()).strip()

            for u in extracted_uris:
                w_path = uri_to_windows_path(u)
                if not w_path or len(w_path) < 3:
                    continue
                # Nếu đường dẫn trỏ tới 1 file lẻ thì lấy thư mục cha
                if os.path.isfile(w_path):
                    w_path = os.path.dirname(w_path)

                w_path = os.path.normpath(w_path)
                norm_key = os.path.normcase(w_path)

                if norm_key not in project_map:
                    base_name = os.path.basename(w_path)
                    if not base_name:
                        base_name = w_path
                    display_name = base_name.capitalize() if base_name.islower() else base_name
                    project_map[norm_key] = {
                        "path": w_path,
                        "name": display_name,
                        "conv_count": 1,
                        "latest_title": clean_title,
                        "titles": [clean_title] if clean_title else []
                    }
                else:
                    project_map[norm_key]["conv_count"] += 1
                    if not project_map[norm_key]["latest_title"] and clean_title:
                        project_map[norm_key]["latest_title"] = clean_title
                    if clean_title and clean_title not in project_map[norm_key]["titles"]:
                        if len(project_map[norm_key]["titles"]) < 10:
                            project_map[norm_key]["titles"].append(clean_title)

        # Sắp xếp dự án theo số lượng cuộc hội thoại giảm dần
        sorted_projects = sorted(project_map.values(), key=lambda x: x["conv_count"], reverse=True)
        return sorted_projects
    except Exception as e:
        print(f"Lỗi khi đọc SQLite Antigravity DB: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Background Window Title Hook
# ---------------------------------------------------------------------------
class WindowTitleHook(threading.Thread):
    """
    Theo dõi tiến trình Antigravity và đảm bảo tiêu đề cửa sổ luôn mang định dạng:
    [Gmail: <Tên/Email>] - <Tên Dự Án> - Antigravity
    """
    def __init__(self, root_pid, tag_label, project_name, instance_tracker):
        super().__init__(daemon=True)
        self.root_pid = root_pid
        self.tag_label = tag_label
        self.project_name = project_name
        self.instance_tracker = instance_tracker
        self.stop_event = threading.Event()
        self.target_prefix = f"[Gmail: {self.tag_label}]"
        self.known_pids = {root_pid}

    def run(self):
        consecutive_missing = 0

        while not self.stop_event.is_set():
            # Cập nhật và tích lũy các PID con của cây tiến trình
            new_pids = get_child_pids(self.root_pid)
            self.known_pids.update(new_pids)
            if self.instance_tracker:
                self.instance_tracker.setdefault("known_pids", set()).update(self.known_pids)

            windows = find_windows_for_pids(self.known_pids)

            if not windows:
                consecutive_missing += 1
                # Nếu tiến trình gốc đã dừng và liên tiếp không có cửa sổ thì thoát luồng
                proc = self.instance_tracker.get("proc") if self.instance_tracker else None
                if proc and proc.poll() is not None and consecutive_missing > 8:
                    break
                if consecutive_missing > 60:
                    break
            else:
                consecutive_missing = 0
                for hwnd, pid, title in windows:
                    # Ghi nhận HWND chính cho tracker
                    if self.instance_tracker:
                        self.instance_tracker["hwnd"] = hwnd

                    # Nếu tiêu đề chưa có tag định danh hoặc chưa khớp tag
                    if not title.startswith(self.target_prefix):
                        try:
                            # Làm sạch bất kỳ tag [Gmail: ...] cũ nếu có
                            clean_title = re.sub(r"^\[Gmail:[^\]]+\]\s*-\s*", "", title).strip()
                            if self.project_name.lower() not in clean_title.lower():
                                new_title = f"{self.target_prefix} - {self.project_name} - {clean_title}"
                            else:
                                new_title = f"{self.target_prefix} - {clean_title}"
                            set_window_title(hwnd, new_title)
                        except Exception as e:
                            print(f"Lỗi đặt tiêu đề cho hwnd {hwnd}: {e}")

            time.sleep(1.2)


# ---------------------------------------------------------------------------
# Giao Diện Người Dùng (GUI) & Quản Lý Khay Hệ Thống
# ---------------------------------------------------------------------------
class SwarmManagerApp(tk.Tk):
    def __init__(self, start_in_tray=False):
        super().__init__()
        # Nếu được gọi tự khởi động với --tray / --minimized: Ẩn ngay lập tức từ đầu để triệt tiêu nhấp nháy cửa sổ
        if start_in_tray:
            self.withdraw()

        self.title("Antigravity Swarm Manager - Quản Lý Đa Tài Khoản & Dự Án")
        self.geometry("980x700")
        self.minsize(850, 580)

        # Set window icon
        for p in [
            os.path.join(getattr(sys, '_MEIPASS', ''), "app_icon.ico"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico"),
            r"C:\Users\maing\Desktop\Antigravity-MultiProject-Launcher\app_icon.ico"
        ]:
            if os.path.isfile(p):
                try:
                    self.iconbitmap(p)
                    break
                except Exception:
                    pass

        # Style & Theme
        self.style = ttk.Style(self)
        self._setup_theme()

        self.config_data = load_config()
        self.running_instances = [] # list of dicts: pid, proc, profile, project, start_time, hwnd, hook_thread

        # Tự động nạp và cập nhật các dự án từ database Antigravity khi khởi động
        try:
            self._sync_projects_from_db(silent=True)
        except Exception as e:
            print(f"Lỗi tự động sync DB khi khởi động: {e}")

        self._build_ui()
        self._setup_system_tray()
        self._start_monitor_timer()

        # Khi bấm nút [X] đóng cửa sổ: Ẩn vào khay hệ thống (System Tray)
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        # Nếu không ở chế độ tray: Hiển thị giao diện bình thường
        if not start_in_tray:
            self.deiconify()

    def _setup_theme(self):
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        self.style.configure("TLabel", font=("Segoe UI", 10))
        self.style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=5)
        self.style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground="#007acc")
        self.style.configure("SubHeader.TLabel", font=("Segoe UI", 9, "italic"), foreground="#666666")
        self.style.configure("Warning.TLabel", font=("Segoe UI", 10, "bold"), foreground="#d9534f")
        self.style.configure("Success.TButton", font=("Segoe UI", 10, "bold"), foreground="#28a745")
        self.style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        self.style.configure("Treeview", font=("Segoe UI", 9), rowheight=26)

    def _setup_system_tray(self):
        """Khởi tạo SystemTrayManager với native Win32 context menu."""
        self.tray = SystemTrayManager(
            tooltip="Antigravity Swarm Manager",
            on_open=lambda: self.after(0, self.show_window),
            on_kill_all=lambda: self.after(0, self._tray_kill_all),
            on_quit=lambda: self.after(0, self.quit_app)
        )

    def show_window(self):
        """Hiện lại cửa sổ chính từ khay hệ thống và đưa lên trước màn hình."""
        self.deiconify()
        self.state("normal")
        self.lift()
        self.attributes("-topmost", True)
        self.after(50, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def hide_to_tray(self):
        """Ẩn cửa sổ vào khay icon và hiển thị thông báo Toast."""
        self.withdraw()
        self._save_current_state()
        if self.tray:
            self.tray.show_balloon(
                "Antigravity Swarm Manager",
                "Ứng dụng đang chạy ngầm trong khay hệ thống (System Tray).\nNhấp chuột hoặc click đúp vào icon để mở lại."
            )

    def _tray_kill_all(self):
        self.show_window()
        self._kill_all_instances()

    def quit_app(self):
        """Đóng hoàn toàn ứng dụng sau khi xác nhận dừng các tiến trình."""
        running = [inst for inst in self.running_instances if inst.get("status") == "🟢 Running"]
        if running:
            self.show_window()
            if not messagebox.askyesno(
                "Thoát Hoàn Toàn",
                f"Hiện vẫn còn {len(running)} cửa sổ Antigravity đang hoạt động.\n"
                "Bạn có chắc chắn muốn đóng tất cả các cửa sổ AI và thoát ứng dụng không?"
            ):
                return
            for inst in running:
                kill_process_tree(inst["pid"], hwnd=inst.get("hwnd"), extra_pids=inst.get("known_pids"))
                inst["status"] = "⚪ Killed"
                if "hook_thread" in inst:
                    inst["hook_thread"].stop_event.set()

        self._save_current_state()
        if self.tray:
            self.tray.destroy()
        self.destroy()
        sys.exit(0)

    def _save_current_state(self):
        """Lưu tự động các giá trị hiện hành vào config.json."""
        try:
            if hasattr(self, "exe_entry"):
                exe_p = self.exe_entry.get().strip()
                if exe_p:
                    self.config_data["antigravity_path"] = exe_p

            if hasattr(self, "quick_profile_cb"):
                p_idx = self.quick_profile_cb.current()
                profiles = self.config_data.get("profiles", [])
                if 0 <= p_idx < len(profiles):
                    self.config_data["last_profile_id"] = profiles[p_idx]["id"]

            if hasattr(self, "quick_project_cb"):
                pr_idx = self.quick_project_cb.current()
                projects = self.config_data.get("projects", [])
                if 0 <= pr_idx < len(projects):
                    self.config_data["last_project_id"] = projects[pr_idx]["id"]

            if hasattr(self, "autostart_var"):
                self.config_data["autostart"] = self.autostart_var.get()

            save_config(self.config_data)
        except Exception as e:
            print(f"Lỗi lưu trạng thái: {e}")

    def _build_ui(self):
        # 1. Header Frame
        header_frame = ttk.Frame(self, padding=12)
        header_frame.pack(fill=tk.X)

        title_lbl = ttk.Label(header_frame, text="⚡ ANTIGRAVITY SWARM MANAGER", style="Header.TLabel")
        title_lbl.pack(anchor=tk.W)

        desc_lbl = ttk.Label(
            header_frame,
            text="Hệ thống vận hành song song nhiều tài khoản Gmail & nhiều dự án với tính năng khay hệ thống tự động.",
            style="SubHeader.TLabel"
        )
        desc_lbl.pack(anchor=tk.W)

        # Path to Antigravity.exe bar
        exe_frame = ttk.Frame(header_frame, padding=(0, 6, 0, 0))
        exe_frame.pack(fill=tk.X)
        ttk.Label(exe_frame, text="Antigravity EXE:").pack(side=tk.LEFT)
        self.exe_entry = ttk.Entry(exe_frame)
        self.exe_entry.insert(0, self.config_data.get("antigravity_path", ""))
        self.exe_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.exe_entry.bind("<FocusOut>", lambda e: self._save_current_state())
        self.exe_entry.bind("<KeyRelease>", lambda e: self._save_current_state())
        ttk.Button(exe_frame, text="Duyệt...", command=self._browse_antigravity_exe).pack(side=tk.LEFT)

        # Autostart & Tray hints bar
        options_frame = ttk.Frame(header_frame, padding=(0, 6, 0, 0))
        options_frame.pack(fill=tk.X)

        is_reg = is_autostart_registered()
        cfg_auto = self.config_data.get("autostart", True)
        self.autostart_var = tk.BooleanVar(value=is_reg or cfg_auto)

        # Tự động đồng bộ Registry nếu config yêu cầu bật
        if cfg_auto and not is_reg:
            set_autostart_registry(True)

        autostart_cb = ttk.Checkbutton(
            options_frame,
            text="🔄 Tự khởi động cùng Windows khi bật máy (Chạy ngầm dưới khay icon)",
            variable=self.autostart_var,
            command=self._on_toggle_autostart
        )
        autostart_cb.pack(side=tk.LEFT)

        status_tray_lbl = ttk.Label(
            options_frame,
            text="💡 Khi bấm [X] tắt cửa sổ, app vẫn chạy dưới khay icon bên cạnh đồng hồ",
            style="SubHeader.TLabel"
        )
        status_tray_lbl.pack(side=tk.RIGHT)

        # 2. Tabs: [Bảng Điều Khiển Launch], [Quản Lý Profiles], [Quản Lý Dự Án], [Giám Sát Realtime]
        self.notebook = ttk.Notebook(self, padding=8)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_launch = ttk.Frame(self.notebook, padding=10)
        self.tab_profiles = ttk.Frame(self.notebook, padding=10)
        self.tab_projects = ttk.Frame(self.notebook, padding=10)
        self.tab_monitor = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.tab_launch, text="🚀 Khởi Chạy Matrix")
        self.notebook.add(self.tab_profiles, text="👤 Quản Lý Gmail Profiles")
        self.notebook.add(self.tab_projects, text="📁 Quản Lý Dự Án")
        self.notebook.add(self.tab_monitor, text="📊 Giám Sát Realtime")

        self._build_launch_tab()
        self._build_profiles_tab()
        self._build_projects_tab()
        self._build_monitor_tab()

    def _on_toggle_autostart(self):
        enabled = self.autostart_var.get()
        success = set_autostart_registry(enabled)
        self.config_data["autostart"] = enabled
        save_config(self.config_data)
        if success:
            state_str = "BẬT" if enabled else "TẮT"
            messagebox.showinfo(
                "Tự khởi động cùng Windows",
                f"Đã {state_str} thành công tính năng tự khởi động cùng Windows khi bật máy.\n"
                f"Ứng dụng sẽ tự động chạy ngầm dưới khay icon khi bạn mở máy tính."
            )
        else:
            messagebox.showerror("Lỗi", "Không thể ghi thiết lập vào Windows Registry.")

    # -----------------------------------------------------------------------
    # TAB 1: KHỞI CHẠY MATRIX
    # -----------------------------------------------------------------------
    def _build_launch_tab(self):
        # Frame chọn nhanh 1 cặp
        quick_frame = ttk.LabelFrame(self.tab_launch, text="Khởi Chạy Nhanh (1 Cửa Sổ)", padding=10)
        quick_frame.pack(fill=tk.X, pady=(0, 10))

        q_grid = ttk.Frame(quick_frame)
        q_grid.pack(fill=tk.X)

        ttk.Label(q_grid, text="Chọn Profile:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.quick_profile_cb = ttk.Combobox(q_grid, state="readonly", width=30)
        self.quick_profile_cb.grid(row=0, column=1, padx=5, pady=5)
        self.quick_profile_cb.bind("<<ComboboxSelected>>", lambda e: self._save_current_state())

        ttk.Label(q_grid, text="Chọn Dự Án:").grid(row=0, column=2, sticky=tk.W, padx=10, pady=5)
        self.quick_project_cb = ttk.Combobox(q_grid, state="readonly", width=38)
        self.quick_project_cb.grid(row=0, column=3, sticky=tk.EW, padx=5, pady=5)
        self.quick_project_cb.bind("<<ComboboxSelected>>", lambda e: self._save_current_state())
        q_grid.columnconfigure(3, weight=1)

        btn_pick_folder = ttk.Button(
            q_grid,
            text="📁 Chọn Thư Mục Mới...",
            command=self._pick_and_open_new_folder
        )
        btn_pick_folder.grid(row=0, column=4, padx=5, pady=5)

        btn_sync = ttk.Button(
            q_grid,
            text="🔄 Đồng Bộ từ Antigravity",
            command=lambda: self._sync_projects_from_db(silent=False)
        )
        btn_sync.grid(row=0, column=5, padx=5, pady=5)

        btn_launch_single = ttk.Button(
            q_grid,
            text="▶ Mở Cửa Sổ Này",
            style="Success.TButton",
            command=self._launch_single_selected
        )
        btn_launch_single.grid(row=0, column=6, padx=(10, 5), pady=5)

        # Matrix Mapping Table: Cho phép gán từng Profile -> Dự Án cụ thể
        matrix_frame = ttk.LabelFrame(self.tab_launch, text="Bảng Phân Bổ Swarm Matrix (Multi-Launch)", padding=10)
        matrix_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        help_lbl = ttk.Label(
            matrix_frame,
            text="Chọn dự án tương ứng cho từng tài khoản và tích chọn các tài khoản muốn mở đồng thời.",
            font=("Segoe UI", 9, "italic")
        )
        help_lbl.pack(anchor=tk.W, pady=(0, 6))

        # Matrix Treeview
        columns = ("selected", "profile_name", "email", "assigned_project")
        self.matrix_tree = ttk.Treeview(matrix_frame, columns=columns, show="headings", height=8)
        self.matrix_tree.heading("selected", text="Kích hoạt")
        self.matrix_tree.heading("profile_name", text="Tên Profile")
        self.matrix_tree.heading("email", text="Gmail / Email")
        self.matrix_tree.heading("assigned_project", text="Dự án gán (Double click để đổi)")

        self.matrix_tree.column("selected", width=90, anchor=tk.CENTER)
        self.matrix_tree.column("profile_name", width=180)
        self.matrix_tree.column("email", width=220)
        self.matrix_tree.column("assigned_project", width=250)

        self.matrix_tree.pack(fill=tk.BOTH, expand=True)
        self.matrix_tree.bind("<Double-1>", self._on_matrix_double_click)

        # Bottom Buttons
        btn_frame = ttk.Frame(self.tab_launch, padding=(0, 10, 0, 0))
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="✔ Chọn Tất Cả", command=self._matrix_select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="✖ Bỏ Chọn", command=self._matrix_deselect_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            btn_frame,
            text="🔄 Đồng Bộ từ Antigravity",
            command=lambda: self._sync_projects_from_db(silent=False)
        ).pack(side=tk.LEFT, padx=10)

        btn_launch_matrix = ttk.Button(
            btn_frame,
            text="🚀 MỞ ĐỒNG LOẠT CÁC CỬA SỔ ĐÃ CHỌN",
            style="Success.TButton",
            command=self._launch_matrix
        )
        btn_launch_matrix.pack(side=tk.RIGHT, padx=5)

        self._refresh_comboboxes()
        self._refresh_matrix_table()

    # -----------------------------------------------------------------------
    # TAB 2: QUẢN LÝ GMAIL PROFILES (CRUD)
    # -----------------------------------------------------------------------
    def _build_profiles_tab(self):
        top_bar = ttk.Frame(self.tab_profiles)
        top_bar.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(top_bar, text="➕ Thêm Gmail Mới", command=self._open_add_profile_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_bar, text="✏ Sửa Profile", command=self._open_edit_profile_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_bar, text="🗑 Xóa Profile", command=self._delete_profile).pack(side=tk.LEFT, padx=5)

        cols = ("id", "name", "email", "data_dir")
        self.profiles_tree = ttk.Treeview(self.tab_profiles, columns=cols, show="headings")
        self.profiles_tree.heading("id", text="Mã ID")
        self.profiles_tree.heading("name", text="Tên Hiển Thị")
        self.profiles_tree.heading("email", text="Email / Ghi Chú")
        self.profiles_tree.heading("data_dir", text="Thư Mục Lưu Trữ Profile (User Data Dir)")

        self.profiles_tree.column("id", width=100)
        self.profiles_tree.column("name", width=180)
        self.profiles_tree.column("email", width=220)
        self.profiles_tree.column("data_dir", width=380)

        self.profiles_tree.pack(fill=tk.BOTH, expand=True)
        self._refresh_profiles_table()

    # -----------------------------------------------------------------------
    # TAB 3: QUẢN LÝ DỰ ÁN (CRUD)
    # -----------------------------------------------------------------------
    def _build_projects_tab(self):
        top_bar = ttk.Frame(self.tab_projects)
        top_bar.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(top_bar, text="➕ Thêm Dự Án Mới", command=self._open_add_project_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_bar, text="✏ Sửa Dự Án", command=self._open_edit_project_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_bar, text="🗑 Xóa Dự Án", command=self._delete_project).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            top_bar,
            text="🔄 Đồng Bộ Từ Antigravity",
            command=lambda: self._sync_projects_from_db(silent=False)
        ).pack(side=tk.LEFT, padx=15)

        cols = ("id", "name", "path", "conv_count", "latest_title")
        self.projects_tree = ttk.Treeview(self.tab_projects, columns=cols, show="headings")
        self.projects_tree.heading("id", text="Mã Dự Án")
        self.projects_tree.heading("name", text="Tên Dự Án")
        self.projects_tree.heading("path", text="Đường Dẫn Thư Mục (Workspace)")
        self.projects_tree.heading("conv_count", text="Số Hội Thoại")
        self.projects_tree.heading("latest_title", text="Hội Thoại Gần Nhất")

        self.projects_tree.column("id", width=110)
        self.projects_tree.column("name", width=150)
        self.projects_tree.column("path", width=340)
        self.projects_tree.column("conv_count", width=95, anchor=tk.CENTER)
        self.projects_tree.column("latest_title", width=220)

        self.projects_tree.pack(fill=tk.BOTH, expand=True)
        self._refresh_projects_table()

    # -----------------------------------------------------------------------
    # TAB 4: GIÁM SÁT REALTIME (PROCESS & WINDOW MONITOR)
    # -----------------------------------------------------------------------
    def _build_monitor_tab(self):
        top_bar = ttk.Frame(self.tab_monitor)
        top_bar.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(top_bar, text="🎯 Kích Hoạt / Focus Cửa Sổ", command=self._focus_selected_instance).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_bar, text="🛑 Đóng Cửa Sổ Đã Chọn (Kill)", command=self._kill_selected_instance).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_bar, text="💥 ĐÓNG TẤT CẢ (Kill All)", command=self._kill_all_instances).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_bar, text="🔄 Làm Mới", command=self._refresh_monitor_table).pack(side=tk.RIGHT, padx=5)

        cols = ("pid", "profile", "email", "project", "hwnd", "status", "uptime")
        self.monitor_tree = ttk.Treeview(self.tab_monitor, columns=cols, show="headings")
        self.monitor_tree.heading("pid", text="PID")
        self.monitor_tree.heading("profile", text="Profile")
        self.monitor_tree.heading("email", text="Email")
        self.monitor_tree.heading("project", text="Dự Án")
        self.monitor_tree.heading("hwnd", text="HWND Window")
        self.monitor_tree.heading("status", text="Trạng Thái")
        self.monitor_tree.heading("uptime", text="Thời Gian Chạy")

        self.monitor_tree.column("pid", width=70, anchor=tk.CENTER)
        self.monitor_tree.column("profile", width=140)
        self.monitor_tree.column("email", width=180)
        self.monitor_tree.column("project", width=160)
        self.monitor_tree.column("hwnd", width=100, anchor=tk.CENTER)
        self.monitor_tree.column("status", width=110, anchor=tk.CENTER)
        self.monitor_tree.column("uptime", width=110, anchor=tk.CENTER)

        self.monitor_tree.pack(fill=tk.BOTH, expand=True)

    # -----------------------------------------------------------------------
    # Helper Refresh Functions
    # -----------------------------------------------------------------------
    def _browse_antigravity_exe(self):
        path = filedialog.askopenfilename(
            title="Chọn tập tin Antigravity.exe",
            filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")]
        )
        if path:
            self.exe_entry.delete(0, tk.END)
            self.exe_entry.insert(0, path)
            self.config_data["antigravity_path"] = path
            save_config(self.config_data)

    def _format_project_label(self, pr):
        """Format tên dự án hiển thị đẹp kèm số cuộc hội thoại và tiêu đề gần nhất."""
        if not pr:
            return "Chưa chọn dự án"
        name = pr.get("name", "Unnamed")
        cnt = pr.get("conv_count", 0)
        latest_title = " ".join((pr.get("latest_title") or "").split()).strip()

        if cnt and cnt > 0:
            if latest_title:
                clean_t = latest_title
                if len(clean_t) > 35:
                    clean_t = clean_t[:32] + "..."
                return f"{name} ({cnt} convs - {clean_t})"
            return f"{name} ({cnt} convs)"
        return name

    def _sync_projects_from_db(self, silent=False):
        """
        Quét và tự động nạp các dự án thực tế từ database Antigravity (conversation_summaries.db).
        Bảo toàn các dự án người dùng đã cấu hình trước đó.
        """
        db_path = get_antigravity_db_path()
        if not db_path:
            if not silent:
                messagebox.showwarning(
                    "Không tìm thấy Database",
                    "Không tìm thấy file SQLite conversation_summaries.db của Antigravity tại:\n"
                    r"C:\Users\maing\.gemini\antigravity\conversation_summaries.db"
                )
            return

        db_projects = sync_projects_from_db()
        if not db_projects and not silent:
            messagebox.showinfo("Thông báo", "Không tìm thấy dữ liệu cuộc hội thoại nào trong Antigravity Database.")
            return

        existing_projects = self.config_data.get("projects", [])
        existing_map = {}
        for pr in existing_projects:
            norm = os.path.normcase(os.path.normpath(pr.get("path", "")))
            if norm:
                existing_map[norm] = pr

        new_count = 0
        updated_count = 0

        for db_p in db_projects:
            norm = os.path.normcase(os.path.normpath(db_p["path"]))
            if norm in existing_map:
                existing_map[norm]["conv_count"] = db_p["conv_count"]
                existing_map[norm]["latest_title"] = db_p["latest_title"]
                existing_map[norm]["path"] = db_p["path"]
                updated_count += 1
            else:
                new_id = f"proj_auto_{hashlib.md5(norm.encode('utf-8')).hexdigest()[:8]}"
                new_item = {
                    "id": new_id,
                    "name": db_p["name"],
                    "path": db_p["path"],
                    "conv_count": db_p["conv_count"],
                    "latest_title": db_p["latest_title"]
                }
                existing_projects.append(new_item)
                existing_map[norm] = new_item
                new_count += 1

        # Sắp xếp các dự án theo số lượng cuộc hội thoại giảm dần để ưu tiên dự án đang hoạt động
        existing_projects.sort(key=lambda x: x.get("conv_count", 0), reverse=True)
        self.config_data["projects"] = existing_projects
        save_config(self.config_data)

        if hasattr(self, "quick_project_cb"):
            self._refresh_comboboxes()
        if hasattr(self, "projects_tree"):
            self._refresh_projects_table()
        if hasattr(self, "matrix_tree"):
            self._refresh_matrix_table()

        if not silent:
            messagebox.showinfo(
                "Đồng Bộ Antigravity Thành Công",
                f"Đã hoàn tất đồng bộ dự án từ Antigravity SQLite Database:\n\n"
                f"• Dự án mới phát hiện: {new_count}\n"
                f"• Dự án cập nhật hội thoại: {updated_count}\n"
                f"• Tổng số dự án khả dụng: {len(existing_projects)}"
            )

    def _pick_and_open_new_folder(self):
        """
        Mở Windows Folder Picker để người dùng chọn bất kỳ thư mục nào (Windows / WSL2 Z:).
        Tự động ghi nhận vào danh sách dự án và sẵn sàng mở ngay với Antigravity.
        """
        chosen_dir = filedialog.askdirectory(
            title="Chọn thư mục dự án mới...",
            parent=self
        )
        if not chosen_dir:
            return

        norm_path = os.path.normpath(chosen_dir)
        folder_name = os.path.basename(norm_path)
        if not folder_name:
            folder_name = norm_path
        if folder_name.islower():
            folder_name = folder_name.capitalize()

        existing_projects = self.config_data.get("projects", [])
        found_proj = None
        norm_key = os.path.normcase(norm_path)

        for pr in existing_projects:
            if os.path.normcase(os.path.normpath(pr.get("path", ""))) == norm_key:
                found_proj = pr
                break

        if not found_proj:
            new_id = f"proj_folder_{hashlib.md5(norm_path.encode('utf-8')).hexdigest()[:8]}"
            found_proj = {
                "id": new_id,
                "name": folder_name,
                "path": norm_path,
                "conv_count": 0,
                "latest_title": ""
            }
            existing_projects.append(found_proj)
            self.config_data["projects"] = existing_projects

        self.config_data["last_project_id"] = found_proj["id"]
        save_config(self.config_data)

        self._refresh_comboboxes()
        self._refresh_projects_table()
        self._refresh_matrix_table()

        # Chọn dự án vừa thêm vào combobox
        for idx, pr in enumerate(self.config_data.get("projects", [])):
            if pr["id"] == found_proj["id"]:
                self.quick_project_cb.current(idx)
                break

        # Sẵn sàng mở ngay: Hỏi người dùng có muốn mở luôn không
        if messagebox.askyesno(
            "Đã Thêm Thư Mục Mới",
            f"Đã ghi nhận dự án mới:\n- Tên: {found_proj['name']}\n- Thư mục: {found_proj['path']}\n\n"
            f"Bạn có muốn khởi chạy Antigravity ngay cho dự án này không?"
        ):
            self._launch_single_selected()

    def _refresh_comboboxes(self):
        profiles = self.config_data.get("profiles", [])
        projects = self.config_data.get("projects", [])

        prof_names = [f"{p['name']} ({p['email']})" for p in profiles]
        proj_names = [self._format_project_label(pr) for pr in projects]

        self.quick_profile_cb["values"] = prof_names
        last_prof_id = self.config_data.get("last_profile_id")
        selected_prof_idx = 0
        if last_prof_id:
            for idx, p in enumerate(profiles):
                if p.get("id") == last_prof_id:
                    selected_prof_idx = idx
                    break
        if prof_names:
            if selected_prof_idx >= len(prof_names):
                selected_prof_idx = 0
            self.quick_profile_cb.current(selected_prof_idx)

        self.quick_project_cb["values"] = proj_names
        last_proj_id = self.config_data.get("last_project_id")
        selected_proj_idx = 0
        if last_proj_id:
            for idx, pr in enumerate(projects):
                if pr.get("id") == last_proj_id:
                    selected_proj_idx = idx
                    break
        if proj_names:
            if selected_proj_idx >= len(proj_names):
                selected_proj_idx = 0
            self.quick_project_cb.current(selected_proj_idx)

    def _refresh_profiles_table(self):
        for item in self.profiles_tree.get_children():
            self.profiles_tree.delete(item)
        for p in self.config_data.get("profiles", []):
            self.profiles_tree.insert("", tk.END, values=(p["id"], p["name"], p["email"], p["data_dir"]))

    def _refresh_projects_table(self):
        for item in self.projects_tree.get_children():
            self.projects_tree.delete(item)
        for pr in self.config_data.get("projects", []):
            cnt = pr.get("conv_count", 0)
            cnt_str = str(cnt) if cnt else "-"
            title_str = pr.get("latest_title", "")
            self.projects_tree.insert(
                "", tk.END,
                values=(pr["id"], pr["name"], pr["path"], cnt_str, title_str)
            )

    def _refresh_matrix_table(self):
        for item in self.matrix_tree.get_children():
            self.matrix_tree.delete(item)

        mappings = self.config_data.get("mappings", {})
        projects_dict = {pr["id"]: pr for pr in self.config_data.get("projects", [])}
        default_proj = next(iter(projects_dict.values())) if projects_dict else None
        default_label = self._format_project_label(default_proj) if default_proj else "Chưa chọn dự án"

        for p in self.config_data.get("profiles", []):
            pid = p["id"]
            assigned_proj_id = mappings.get(pid)
            if assigned_proj_id and assigned_proj_id in projects_dict:
                assigned_name = self._format_project_label(projects_dict[assigned_proj_id])
            else:
                assigned_name = default_label
            self.matrix_tree.insert("", tk.END, iid=pid, values=("✔ Có", p["name"], p["email"], assigned_name))

    def _matrix_select_all(self):
        for item in self.matrix_tree.get_children():
            vals = list(self.matrix_tree.item(item, "values"))
            vals[0] = "✔ Có"
            self.matrix_tree.item(item, values=vals)

    def _matrix_deselect_all(self):
        for item in self.matrix_tree.get_children():
            vals = list(self.matrix_tree.item(item, "values"))
            vals[0] = "✖ Không"
            self.matrix_tree.item(item, values=vals)

    def _on_matrix_double_click(self, event):
        item = self.matrix_tree.identify_row(event.y)
        column = self.matrix_tree.identify_column(event.x)
        if not item:
            return

        vals = list(self.matrix_tree.item(item, "values"))
        if column == "#1":
            # Toggle check
            vals[0] = "✖ Không" if vals[0] == "✔ Có" else "✔ Có"
            self.matrix_tree.item(item, values=vals)
        elif column == "#4":
            # Chọn dự án gán
            projects = self.config_data.get("projects", [])
            if not projects:
                messagebox.showwarning("Thông báo", "Vui lòng thêm Dự Án trong tab Quản Lý Dự Án trước.")
                return

            proj_labels = [self._format_project_label(pr) for pr in projects]
            dlg = tk.Toplevel(self)
            dlg.title("Gán Dự Án cho Profile")
            dlg.geometry("460x160")
            dlg.transient(self)
            dlg.grab_set()

            ttk.Label(dlg, text=f"Chọn dự án cho: {vals[1]}", font=("Segoe UI", 9, "bold")).pack(pady=10)
            cb = ttk.Combobox(dlg, values=proj_labels, state="readonly", width=42)
            cb.pack(pady=5)
            if vals[3] in proj_labels:
                cb.set(vals[3])
            else:
                cb.current(0)

            def save_assign():
                sel_idx = cb.current()
                if 0 <= sel_idx < len(projects):
                    target_pr = projects[sel_idx]
                    vals[3] = self._format_project_label(target_pr)
                    self.matrix_tree.item(item, values=vals)
                    if "mappings" not in self.config_data:
                        self.config_data["mappings"] = {}
                    self.config_data["mappings"][item] = target_pr["id"]
                    save_config(self.config_data)
                dlg.destroy()

            ttk.Button(dlg, text="Xác nhận", command=save_assign).pack(pady=10)

    # -----------------------------------------------------------------------
    # MODAL: THÊM / SỬA PROFILE
    # -----------------------------------------------------------------------
    def _open_add_profile_dialog(self):
        self._show_profile_dialog(mode="add")

    def _open_edit_profile_dialog(self):
        selected = self.profiles_tree.selection()
        if not selected:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 Profile trong danh sách để sửa.")
            return
        item_vals = self.profiles_tree.item(selected[0], "values")
        profile_data = {
            "id": item_vals[0],
            "name": item_vals[1],
            "email": item_vals[2],
            "data_dir": item_vals[3]
        }
        self._show_profile_dialog(mode="edit", initial_data=profile_data)

    def _show_profile_dialog(self, mode="add", initial_data=None):
        dlg = tk.Toplevel(self)
        dlg.title("➕ Thêm Gmail Profile Mới" if mode == "add" else "✏ Chỉnh Sửa Profile")
        dlg.geometry("520x280")
        dlg.transient(self)
        dlg.grab_set()

        grid = ttk.Frame(dlg, padding=15)
        grid.pack(fill=tk.BOTH, expand=True)

        ttk.Label(grid, text="Tên Hiển Thị:").grid(row=0, column=0, sticky=tk.W, pady=6)
        name_ent = ttk.Entry(grid, width=40)
        name_ent.grid(row=0, column=1, sticky=tk.W, pady=6)

        ttk.Label(grid, text="Email / Ghi Chú:").grid(row=1, column=0, sticky=tk.W, pady=6)
        email_ent = ttk.Entry(grid, width=40)
        email_ent.grid(row=1, column=1, sticky=tk.W, pady=6)

        ttk.Label(grid, text="Thư Mục Profile:").grid(row=2, column=0, sticky=tk.W, pady=6)
        dir_frame = ttk.Frame(grid)
        dir_frame.grid(row=2, column=1, sticky=tk.W, pady=6)
        dir_ent = ttk.Entry(dir_frame, width=32)
        dir_ent.pack(side=tk.LEFT)

        def browse_dir():
            p = filedialog.askdirectory(title="Chọn thư mục User Data Dir cho Profile")
            if p:
                dir_ent.delete(0, tk.END)
                dir_ent.insert(0, p)

        ttk.Button(dir_frame, text="Duyệt...", command=browse_dir).pack(side=tk.LEFT, padx=5)

        if initial_data:
            name_ent.insert(0, initial_data["name"])
            email_ent.insert(0, initial_data["email"])
            dir_ent.insert(0, initial_data["data_dir"])
        else:
            # Gợi ý tự động
            count = len(self.config_data.get("profiles", [])) + 1
            name_ent.insert(0, f"Gmail Dev {count}")
            email_ent.insert(0, f"account{count}@gmail.com")
            def_base = os.path.join(os.environ.get("APPDATA", ""), "Antigravity_Profiles", f"profile_dev{count}")
            dir_ent.insert(0, def_base)

        def save_profile():
            name = name_ent.get().strip()
            email = email_ent.get().strip()
            data_dir = dir_ent.get().strip()

            if not name:
                messagebox.showerror("Lỗi", "Tên Profile không được để trống.")
                return
            if not data_dir:
                messagebox.showerror("Lỗi", "Thư mục Profile không được để trống.")
                return

            if mode == "add":
                new_id = f"profile_{int(time.time())}"
                new_item = {"id": new_id, "name": name, "email": email, "data_dir": data_dir}
                self.config_data.setdefault("profiles", []).append(new_item)
            else:
                p_id = initial_data["id"]
                for p in self.config_data.get("profiles", []):
                    if p["id"] == p_id:
                        p["name"] = name
                        p["email"] = email
                        p["data_dir"] = data_dir
                        break

            save_config(self.config_data)
            self._refresh_profiles_table()
            self._refresh_comboboxes()
            self._refresh_matrix_table()
            dlg.destroy()

        btn_box = ttk.Frame(grid)
        btn_box.grid(row=3, column=0, columnspan=2, pady=15)
        ttk.Button(btn_box, text="Lưu Thông Tin", command=save_profile).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_box, text="Hủy", command=dlg.destroy).pack(side=tk.LEFT, padx=10)

    def _delete_profile(self):
        selected = self.profiles_tree.selection()
        if not selected:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 Profile để xóa.")
            return
        p_id = self.profiles_tree.item(selected[0], "values")[0]
        if messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn xóa Profile này khỏi danh sách quản lý?"):
            self.config_data["profiles"] = [p for p in self.config_data.get("profiles", []) if p["id"] != p_id]
            if "mappings" in self.config_data and p_id in self.config_data["mappings"]:
                del self.config_data["mappings"][p_id]
            save_config(self.config_data)
            self._refresh_profiles_table()
            self._refresh_comboboxes()
            self._refresh_matrix_table()

    # -----------------------------------------------------------------------
    # MODAL: THÊM / SỬA DỰ ÁN
    # -----------------------------------------------------------------------
    def _open_add_project_dialog(self):
        self._show_project_dialog(mode="add")

    def _open_edit_project_dialog(self):
        selected = self.projects_tree.selection()
        if not selected:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 Dự Án trong danh sách để sửa.")
            return
        item_vals = self.projects_tree.item(selected[0], "values")
        project_data = {
            "id": item_vals[0],
            "name": item_vals[1],
            "path": item_vals[2]
        }
        self._show_project_dialog(mode="edit", initial_data=project_data)

    def _show_project_dialog(self, mode="add", initial_data=None):
        dlg = tk.Toplevel(self)
        dlg.title("➕ Thêm Dự Án Mới" if mode == "add" else "✏ Chỉnh Sửa Dự Án")
        dlg.geometry("520x220")
        dlg.transient(self)
        dlg.grab_set()

        grid = ttk.Frame(dlg, padding=15)
        grid.pack(fill=tk.BOTH, expand=True)

        ttk.Label(grid, text="Tên Dự Án:").grid(row=0, column=0, sticky=tk.W, pady=6)
        name_ent = ttk.Entry(grid, width=40)
        name_ent.grid(row=0, column=1, sticky=tk.W, pady=6)

        ttk.Label(grid, text="Thư Mục Dự Án:").grid(row=1, column=0, sticky=tk.W, pady=6)
        path_frame = ttk.Frame(grid)
        path_frame.grid(row=1, column=1, sticky=tk.W, pady=6)
        path_ent = ttk.Entry(path_frame, width=32)
        path_ent.pack(side=tk.LEFT)

        def browse_project():
            p = filedialog.askdirectory(title="Chọn thư mục dự án (hoặc Git Worktree)")
            if p:
                path_ent.delete(0, tk.END)
                path_ent.insert(0, p)
                if not name_ent.get().strip():
                    name_ent.insert(0, os.path.basename(os.path.normpath(p)))

        ttk.Button(path_frame, text="Duyệt...", command=browse_project).pack(side=tk.LEFT, padx=5)

        if initial_data:
            name_ent.insert(0, initial_data["name"])
            path_ent.insert(0, initial_data["path"])

        def save_project():
            name = name_ent.get().strip()
            path = path_ent.get().strip()
            if not name:
                messagebox.showerror("Lỗi", "Tên Dự Án không được để trống.")
                return
            if not path or not os.path.isdir(path):
                messagebox.showerror("Lỗi", "Đường dẫn thư mục dự án không hợp lệ hoặc không tồn tại.")
                return

            if mode == "add":
                new_id = f"proj_{int(time.time())}"
                new_item = {"id": new_id, "name": name, "path": path, "conv_count": 0, "latest_title": ""}
                self.config_data.setdefault("projects", []).append(new_item)
            else:
                p_id = initial_data["id"]
                for pr in self.config_data.get("projects", []):
                    if pr["id"] == p_id:
                        pr["name"] = name
                        pr["path"] = path
                        break

            save_config(self.config_data)
            self._refresh_projects_table()
            self._refresh_comboboxes()
            self._refresh_matrix_table()
            dlg.destroy()

        btn_box = ttk.Frame(grid)
        btn_box.grid(row=2, column=0, columnspan=2, pady=15)
        ttk.Button(btn_box, text="Lưu Dự Án", command=save_project).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_box, text="Hủy", command=dlg.destroy).pack(side=tk.LEFT, padx=10)

    def _delete_project(self):
        selected = self.projects_tree.selection()
        if not selected:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 Dự Án để xóa.")
            return
        p_id = self.projects_tree.item(selected[0], "values")[0]
        if messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn xóa Dự Án này khỏi danh sách quản lý?"):
            self.config_data["projects"] = [pr for pr in self.config_data.get("projects", []) if pr["id"] != p_id]
            save_config(self.config_data)
            self._refresh_projects_table()
            self._refresh_comboboxes()
            self._refresh_matrix_table()

    # -----------------------------------------------------------------------
    # KIỂM TRA XUNG ĐỘT & KHỞI CHẠY (CONFLICT DETECTION & LAUNCH)
    # -----------------------------------------------------------------------
    def _check_conflicts_and_warn(self, launch_pairs):
        """
        [P1 - Cảnh báo xung đột]: Kiểm tra xem các cặp dự định mở có bị trùng thư mục
        với nhau HOẶC trùng với các cửa sổ đang chạy hay không.
        """
        all_pairs = []
        # Thêm các instance đang chạy thực tế
        for inst in self.running_instances:
            hwnd = inst.get("hwnd", 0)
            proc = inst.get("proc")
            is_alive = (proc and proc.poll() is None) or (hwnd and user32.IsWindow(hwnd))
            if is_alive:
                all_pairs.append((inst["profile"], inst["project"], "Đang chạy"))

        for prof, proj in launch_pairs:
            all_pairs.append((prof, proj, "Sắp mở"))

        path_to_entries = {}
        for prof, proj, state in all_pairs:
            raw_p = proj.get("path", "")
            norm_path = os.path.normcase(os.path.realpath(os.path.expandvars(os.path.expanduser(raw_p))))
            path_to_entries.setdefault(norm_path, []).append((prof, proj, state))

        conflicts = {k: v for k, v in path_to_entries.items() if len(v) > 1}
        if conflicts:
            # Chỉ cảnh báo nếu có ít nhất một cặp trong danh sách sắp mở bị xung đột
            has_new_in_conflict = any(any(e[2] == "Sắp mở" for e in entries) for entries in conflicts.values())
            if not has_new_in_conflict:
                return True

            msg_lines = [
                "⚠️ CẢNH BÁO XUNG ĐỘT MÃ NGUỒN (CONFLICT WARNING)!\n",
                "Phát hiện nhiều tài khoản cùng được chỉ định mở chung MỘT thư mục mã nguồn vật lý duy nhất:\n"
            ]
            for norm_p, entries in conflicts.items():
                real_p = entries[0][1]["path"]
                names = ", ".join([f"[{e[0].get('name')} ({e[0].get('email', '')}) - {e[2]}]" for e in entries])
                msg_lines.append(f"• Thư mục: {real_p}")
                msg_lines.append(f"  Các tài khoản: {names}\n")

            msg_lines.append(
                "NGUY CƠ: Nếu nhiều AI Agent cùng sửa đổi code trên cùng một thư mục đồng thời, "
                "sẽ xảy ra hiện tượng ghi đè file (overwrite) và mất mã nguồn!\n\n"
                "KHUYẾN NGHỊ: Hãy sử dụng Git Worktree để mỗi tài khoản làm việc trên một thư mục/nhánh riêng biệt.\n\n"
                "Bạn có chắc chắn vẫn muốn tiếp tục mở không?"
            )
            return messagebox.askyesno("Cảnh báo xung đột", "\n".join(msg_lines), icon="warning")
        return True

    def _execute_launch(self, profile, project):
        """Thực thi khởi chạy 1 cửa sổ Antigravity với Profile và Dự án tương ứng."""
        exe_path = self.exe_entry.get().strip()
        if not exe_path or not os.path.isfile(exe_path):
            messagebox.showerror("Lỗi", "Đường dẫn Antigravity.exe không hợp lệ hoặc chưa được chọn.")
            return False

        profile_dir = os.path.expandvars(os.path.expanduser(profile["data_dir"]))
        os.makedirs(profile_dir, exist_ok=True)
        proj_path = os.path.expandvars(os.path.expanduser(project["path"]))

        # Lệnh khởi chạy: --user-data-dir riêng biệt và mở workspace mới
        cmd = [
            exe_path,
            f"--user-data-dir={profile_dir}"
        ]
        if proj_path:
            cmd.append(proj_path)

        try:
            # Khởi chạy tiến trình độc lập
            proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

            # Khởi tạo object theo dõi instance
            instance_info = {
                "pid": proc.pid,
                "proc": proc,
                "profile": profile,
                "project": project,
                "start_time": time.time(),
                "hwnd": 0,
                "known_pids": {proc.pid},
                "status": "🟢 Running"
            }

            # [P0 - Win32 Title Hook]: Luồng đổi tiêu đề cửa sổ trong background
            tag_label = profile.get("email") or profile.get("name")
            hook = WindowTitleHook(proc.pid, tag_label, project["name"], instance_info)
            hook.start()
            instance_info["hook_thread"] = hook

            self.running_instances.append(instance_info)
            self._save_current_state()
            return True
        except Exception as e:
            messagebox.showerror("Lỗi khởi chạy", f"Không thể mở Antigravity: {e}")
            return False

    def _launch_single_selected(self):
        p_idx = self.quick_profile_cb.current()
        pr_idx = self.quick_project_cb.current()
        profiles = self.config_data.get("profiles", [])
        projects = self.config_data.get("projects", [])

        if p_idx < 0 or p_idx >= len(profiles):
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn Profile hợp lệ.")
            return
        if pr_idx < 0 or pr_idx >= len(projects):
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn Dự Án hợp lệ.")
            return

        target_profile = profiles[p_idx]
        target_project = projects[pr_idx]

        if not self._check_conflicts_and_warn([(target_profile, target_project)]):
            return

        if self._execute_launch(target_profile, target_project):
            tag_label = target_profile.get("email") or target_profile.get("name")
            messagebox.showinfo(
                "Khởi chạy thành công",
                f"Đã mở Antigravity cho:\n- Profile: {target_profile['name']}\n- Dự án: {target_project['name']}\n\n"
                f"Tiêu đề cửa sổ & Taskbar sẽ tự động gắn nhãn: [Gmail: {tag_label}] - {target_project['name']} - Antigravity."
            )
            self.notebook.select(self.tab_monitor)

    def _launch_matrix(self):
        """Khởi chạy đồng loạt tất cả các cặp đã được chọn trong bảng Matrix."""
        profiles = {p["id"]: p for p in self.config_data.get("profiles", [])}
        projects_by_id = {pr["id"]: pr for pr in self.config_data.get("projects", [])}
        projects_by_name = {pr["name"]: pr for pr in self.config_data.get("projects", [])}
        projects_by_label = {self._format_project_label(pr): pr for pr in self.config_data.get("projects", [])}
        mappings = self.config_data.get("mappings", {})

        launch_pairs = []
        for item in self.matrix_tree.get_children():
            vals = self.matrix_tree.item(item, "values")
            if vals[0] == "✔ Có":
                prof_id = item
                assigned_proj_label = vals[3]
                target_project = None
                if prof_id in mappings and mappings[prof_id] in projects_by_id:
                    target_project = projects_by_id[mappings[prof_id]]
                elif assigned_proj_label in projects_by_label:
                    target_project = projects_by_label[assigned_proj_label]
                elif assigned_proj_label in projects_by_name:
                    target_project = projects_by_name[assigned_proj_label]
                else:
                    # Bóc tách tên dự án gốc loại bỏ phần phụ lục (X convs - ...)
                    clean_name = re.sub(r"\s*\(\d+\s*convs.*?\)$", "", assigned_proj_label).strip()
                    if clean_name in projects_by_name:
                        target_project = projects_by_name[clean_name]
                    elif projects_by_id:
                        target_project = next(iter(projects_by_id.values()))

                if prof_id in profiles and target_project:
                    launch_pairs.append((profiles[prof_id], target_project))

        if not launch_pairs:
            messagebox.showwarning("Cảnh báo", "Chưa có tài khoản nào được chọn để mở (cột 'Kích hoạt' là '✔ Có').")
            return

        # Kiểm tra xung đột trước khi mở (bao gồm cả các cửa sổ đang chạy)
        if not self._check_conflicts_and_warn(launch_pairs):
            return

        success_count = 0
        for prof, proj in launch_pairs:
            if self._execute_launch(prof, proj):
                success_count += 1
                time.sleep(1.0) # Nghỉ nhẹ giữa các lần mở để tránh nghẽn I/O

        messagebox.showinfo(
            "Hoàn tất mở Swarm",
            f"Đã khởi chạy thành công {success_count}/{len(launch_pairs)} cửa sổ Antigravity!\n"
            "Các cửa sổ đang được gắn nhãn định danh [Gmail: ...] trên Taskbar."
        )
        self.notebook.select(self.tab_monitor)

    # -----------------------------------------------------------------------
    # TAB 4: GIÁM SÁT REALTIME & KILL
    # -----------------------------------------------------------------------
    def _start_monitor_timer(self):
        self._refresh_monitor_table()
        self.after(1500, self._start_monitor_timer)

    def _refresh_monitor_table(self):
        now = time.time()
        active_iids = set()

        for inst in self.running_instances:
            proc = inst.get("proc")
            hwnd = inst.get("hwnd", 0)
            poll = proc.poll() if proc else None

            is_window_valid = bool(hwnd and user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd))

            if is_window_valid or poll is None:
                inst["status"] = "🟢 Running"
            elif inst.get("status") == "⚪ Killed":
                inst["status"] = "⚪ Killed"
            else:
                inst["status"] = f"⚪ Exited ({poll if poll is not None else 'Closed'})"

            uptime_sec = int(now - inst["start_time"])
            mins, secs = divmod(uptime_sec, 60)
            hours, mins = divmod(mins, 60)
            uptime_str = f"{hours:02d}:{mins:02d}:{secs:02d}"

            hwnd_str = f"0x{hwnd:08X}" if hwnd else "Đang chờ..."
            iid = str(inst["pid"])
            active_iids.add(iid)

            row_vals = (
                inst["pid"],
                inst["profile"]["name"],
                inst["profile"]["email"],
                inst["project"]["name"],
                hwnd_str,
                inst["status"],
                uptime_str
            )

            # Cập nhật in-place để tránh giật lag UI và giữ selection
            if self.monitor_tree.exists(iid):
                self.monitor_tree.item(iid, values=row_vals)
            else:
                self.monitor_tree.insert("", tk.END, iid=iid, values=row_vals)

        # Xóa các dòng không còn tồn tại
        for item in self.monitor_tree.get_children():
            if item not in active_iids:
                self.monitor_tree.delete(item)

    def _focus_selected_instance(self):
        sel = self.monitor_tree.selection()
        if not sel:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 cửa sổ trong danh sách giám sát.")
            return
        pid = int(sel[0])
        for inst in self.running_instances:
            if inst["pid"] == pid:
                hwnd = inst.get("hwnd", 0)
                if hwnd and user32.IsWindow(hwnd):
                    user32.ShowWindow(hwnd, 9) # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                else:
                    messagebox.showinfo("Thông báo", "Chưa tìm thấy HWND của cửa sổ này (có thể đang khởi động hoặc đã đóng).")
                break

    def _kill_selected_instance(self):
        sel = self.monitor_tree.selection()
        if not sel:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 tiến trình để đóng.")
            return
        pid = int(sel[0])
        if messagebox.askyesno("Xác nhận Đóng", f"Bạn có chắc chắn muốn đóng (Kill) toàn bộ tiến trình của PID {pid}?"):
            for inst in self.running_instances:
                if inst["pid"] == pid:
                    kill_process_tree(pid, hwnd=inst.get("hwnd"), extra_pids=inst.get("known_pids"))
                    inst["status"] = "⚪ Killed"
                    if "hook_thread" in inst:
                        inst["hook_thread"].stop_event.set()
            self._refresh_monitor_table()

    def _kill_all_instances(self):
        running = [inst for inst in self.running_instances if inst["status"] == "🟢 Running"]
        if not running:
            messagebox.showinfo("Thông báo", "Hiện không có cửa sổ nào đang chạy.")
            return

        if messagebox.askyesno("Xác nhận Đóng Tất Cả", f"Bạn có chắc chắn muốn đóng toàn bộ {len(running)} cửa sổ đang chạy?"):
            for inst in running:
                kill_process_tree(inst["pid"], hwnd=inst.get("hwnd"), extra_pids=inst.get("known_pids"))
                inst["status"] = "⚪ Killed"
                if "hook_thread" in inst:
                    inst["hook_thread"].stop_event.set()
            self._refresh_monitor_table()
            messagebox.showinfo("Đã đóng", "Toàn bộ các tiến trình Antigravity Swarm đã được dừng.")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    is_tray_mode = ("--tray" in sys.argv) or ("--minimized" in sys.argv)
    app = SwarmManagerApp(start_in_tray=is_tray_mode)
    app.mainloop()
