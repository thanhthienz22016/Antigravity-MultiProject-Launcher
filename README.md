# Antigravity Swarm Manager Pro 🚀 (Multi-Account x Multi-Project Launcher)

Công cụ điều phối mở đồng loạt nhiều cửa sổ Antigravity & Antigravity IDE, gán độc lập từng tài khoản Gmail vào từng Dự án / Git Worktree riêng biệt, tự động gắn nhãn Taskbar và tích hợp giám sát tiến trình realtime.

## 🌟 Tính Năng Nổi Bật

- **Độc Lập Hồ Sơ Tuyệt Đối (Multi-Profile Isolated Environment)**:
  - Bẻ khóa cơ chế `Process Singleton Lock` của Chromium qua `--user-data-dir`.
  - Mỗi cửa sổ Antigravity sở hữu bộ nhớ đệm, session, token Google và **hạn mức Quota riêng biệt 100%**.
- **Tự Động Đổi Tiêu Đề Cửa Sổ & Taskbar (Win32 Window Title Hook)**:
  - Tự động gắn nhãn: `[Gmail: <Tên/Email>] - <Tên Dự Án> - Antigravity`.
  - Phân biệt tức thì các cửa sổ khi xem thanh Taskbar Windows hoặc bấm `Alt + Tab`.
- **Bảo Vệ Xung Đột Mã Nguồn (Conflict Shield)**:
  - Cảnh báo tức thì khi phát hiện nhiều Gmail cùng mở vào một thư mục dự án duy nhất.
  - Khuyến nghị và hướng dẫn phân tách bằng **Git Worktrees** để nhiều AI cùng code một dự án song song mà không bao giờ đè code lên nhau.
- **Bảng Giám Sát Tiến Trình Realtime (Running Instances Monitor)**:
  - Theo dõi trạng thái hoạt động: PID, Tài khoản Gmail, Dự án, Thời gian chạy (Uptime).
  - Nút **Focus**: Đưa ngay cửa sổ tương ứng lên trước màn hình.
  - Nút **Dừng (Kill)**: Đóng chuẩn xác từng tiến trình hoặc dừng hàng loạt.
- **Khởi Chạy Ma Trận 1-Click (Matrix Launch)**:
  - Khởi chạy từng cặp Gmail + Dự Án đã chọn hoặc mở đồng loạt toàn bộ dàn AI tác chiến.
- **Tương Thích Hoàn Hảo Với Auto-Submit Pro**:
  - Phối hợp với [auto-submit-antigravity](https://github.com/thanhthienz22016/auto-submit-antigravity.git) để tự động phê duyệt ngầm song song cho tất cả các cửa sổ AI đang mở.

## 📁 Cấu Trúc Thư Mục

- `Antigravity_Swarm_Manager.pyw`: Mã nguồn giao diện chính (Python + Tkinter + Win32 API).
- `AntigravitySwarmManager.exe`: File thực thi binary độc lập (10.3 MB).
- `AntigravitySwarmManager.spec`: Cấu hình đóng gói PyInstaller.
- `Mo_Manager_Da_Tai_Khoan.bat`: Script khởi chạy nhanh `AntigravitySwarmManager.exe`.
- `app_icon.ico`: Icon ứng dụng.
- `HUONG_DAN_CHI_TIET.txt`: Hướng dẫn vận hành chi tiết.

## 🛠️ Hướng Dẫn Đóng Gói Binary (.exe)

Nếu bạn sửa đổi mã nguồn và muốn đóng gói lại file `.exe`:

```bash
python -m PyInstaller --noconfirm AntigravitySwarmManager.spec
```
