# -*- coding: utf-8 -*-
"""
Antigravity Swarm Manager (Multi-Account x Multi-Project Launcher)
==================================================================
Phiên bản: 2.0 (Nâng cấp Pro)

Tính năng chính:
- [P0 - Win32 Title Hook]: Tự động đổi tiêu đề cửa sổ Antigravity & Taskbar Windows:
  "[Gmail: <Tên/Email>] - <Tên Dự Án> - Antigravity" giúp phân biệt tức thì các cửa sổ.
- [P0 - Nhập liệu]: Hộp thoại thêm Profile cho phép nhập Tên hiển thị, Email/Ghi chú và thư mục lưu trữ.
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
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# ---------------------------------------------------------------------------
# Win32 API Integration (Pure ctypes, 64-bit safe, không cần cài pywin32)
# ---------------------------------------------------------------------------
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

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

# Setup exact ctypes prototypes for 64-bit Windows safety
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
# Cấu hình & Dữ liệu
# ---------------------------------------------------------------------------
CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Antigravity_Swarm_Manager")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def get_default_antigravity_path():
    """Tự động tìm kiếm đường dẫn thực thi của Antigravity.exe."""
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", "")
    candidates = [
        os.path.join(local_app_data, "Programs", "Antigravity", "Antigravity.exe"),
        os.path.join(local_app_data, "Antigravity", "Antigravity.exe"),
        os.path.join(program_files, "Antigravity", "Antigravity.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return ""

def load_config():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    default_profiles_base = os.path.join(os.environ.get("APPDATA", ""), "Antigravity_Profiles")
    default_config = {
        "antigravity_path": get_default_antigravity_path(),
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
    save_config(default_config)
    return default_config

def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)


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
# Giao Diện Người Dùng (GUI)
# ---------------------------------------------------------------------------
class SwarmManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Antigravity Swarm Manager - Quản Lý Đa Tài Khoản & Dự Án")
        self.geometry("980x680")
        self.minsize(850, 550)

        # Style & Theme
        self.style = ttk.Style(self)
        self._setup_theme()

        self.config_data = load_config()
        self.running_instances = [] # list of dicts: pid, proc, profile, project, start_time, hwnd, hook_thread

        self._build_ui()
        self._start_monitor_timer()

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

    def _build_ui(self):
        # 1. Header Frame
        header_frame = ttk.Frame(self, padding=12)
        header_frame.pack(fill=tk.X)

        title_lbl = ttk.Label(header_frame, text="⚡ ANTIGRAVITY SWARM MANAGER", style="Header.TLabel")
        title_lbl.pack(anchor=tk.W)

        desc_lbl = ttk.Label(
            header_frame,
            text="Hệ thống vận hành song song nhiều tài khoản Gmail & nhiều dự án với tính năng gắn nhãn cửa sổ tự động.",
            style="SubHeader.TLabel"
        )
        desc_lbl.pack(anchor=tk.W)

        # Path to Antigravity.exe bar
        exe_frame = ttk.Frame(header_frame, padding=(0, 8, 0, 0))
        exe_frame.pack(fill=tk.X)
        ttk.Label(exe_frame, text="Antigravity EXE:").pack(side=tk.LEFT)
        self.exe_entry = ttk.Entry(exe_frame)
        self.exe_entry.insert(0, self.config_data.get("antigravity_path", ""))
        self.exe_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Button(exe_frame, text="Duyệt...", command=self._browse_antigravity_exe).pack(side=tk.LEFT)

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
        self.quick_profile_cb = ttk.Combobox(q_grid, state="readonly", width=35)
        self.quick_profile_cb.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(q_grid, text="Chọn Dự Án:").grid(row=0, column=2, sticky=tk.W, padx=15, pady=5)
        self.quick_project_cb = ttk.Combobox(q_grid, state="readonly", width=35)
        self.quick_project_cb.grid(row=0, column=3, padx=5, pady=5)

        btn_launch_single = ttk.Button(q_grid, text="▶ Mở Cửa Sổ Này", command=self._launch_single_selected)
        btn_launch_single.grid(row=0, column=4, padx=15, pady=5)

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

        cols = ("id", "name", "path")
        self.projects_tree = ttk.Treeview(self.tab_projects, columns=cols, show="headings")
        self.projects_tree.heading("id", text="Mã Dự Án")
        self.projects_tree.heading("name", text="Tên Dự Án")
        self.projects_tree.heading("path", text="Đường Dẫn Dự Án (Workspace Directory)")

        self.projects_tree.column("id", width=120)
        self.projects_tree.column("name", width=220)
        self.projects_tree.column("path", width=500)

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

    def _refresh_comboboxes(self):
        prof_names = [f"{p['name']} ({p['email']})" for p in self.config_data.get("profiles", [])]
        proj_names = [f"{pr['name']}" for pr in self.config_data.get("projects", [])]

        self.quick_profile_cb["values"] = prof_names
        if prof_names:
            self.quick_profile_cb.current(0)

        self.quick_project_cb["values"] = proj_names
        if proj_names:
            self.quick_project_cb.current(0)

    def _refresh_profiles_table(self):
        for item in self.profiles_tree.get_children():
            self.profiles_tree.delete(item)
        for p in self.config_data.get("profiles", []):
            self.profiles_tree.insert("", tk.END, values=(p["id"], p["name"], p["email"], p["data_dir"]))

    def _refresh_projects_table(self):
        for item in self.projects_tree.get_children():
            self.projects_tree.delete(item)
        for pr in self.config_data.get("projects", []):
            self.projects_tree.insert("", tk.END, values=(pr["id"], pr["name"], pr["path"]))

    def _refresh_matrix_table(self):
        for item in self.matrix_tree.get_children():
            self.matrix_tree.delete(item)

        mappings = self.config_data.get("mappings", {})
        projects = {pr["id"]: pr["name"] for pr in self.config_data.get("projects", [])}
        default_proj_name = next(iter(projects.values())) if projects else "Chưa chọn dự án"

        for p in self.config_data.get("profiles", []):
            pid = p["id"]
            assigned_proj_id = mappings.get(pid)
            assigned_name = projects.get(assigned_proj_id, default_proj_name)
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

            proj_names = [pr["name"] for pr in projects]
            dlg = tk.Toplevel(self)
            dlg.title("Gán Dự Án cho Profile")
            dlg.geometry("380x150")
            dlg.transient(self)
            dlg.grab_set()

            ttk.Label(dlg, text=f"Chọn dự án cho: {vals[1]}", font=("Segoe UI", 9, "bold")).pack(pady=10)
            cb = ttk.Combobox(dlg, values=proj_names, state="readonly", width=30)
            cb.pack(pady=5)
            if vals[3] in proj_names:
                cb.set(vals[3])
            else:
                cb.current(0)

            def save_assign():
                selected_name = cb.get()
                vals[3] = selected_name
                self.matrix_tree.item(item, values=vals)
                # Lưu vào config
                for pr in projects:
                    if pr["name"] == selected_name:
                        if "mappings" not in self.config_data:
                            self.config_data["mappings"] = {}
                        self.config_data["mappings"][item] = pr["id"]
                        save_config(self.config_data)
                        break
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
                new_item = {"id": new_id, "name": name, "path": path}
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
        if proj_path and os.path.exists(proj_path):
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
        projects = {pr["name"]: pr for pr in self.config_data.get("projects", [])}

        launch_pairs = []
        for item in self.matrix_tree.get_children():
            vals = self.matrix_tree.item(item, "values")
            if vals[0] == "✔ Có":
                prof_id = item
                assigned_proj_name = vals[3]
                if prof_id in profiles and assigned_proj_name in projects:
                    launch_pairs.append((profiles[prof_id], projects[assigned_proj_name]))

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
    app = SwarmManagerApp()
    app.mainloop()
