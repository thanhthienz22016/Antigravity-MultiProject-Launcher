# Hướng Dẫn Triển Khai & Báo Cáo Nâng Cấp Hệ Thống Antigravity Swarm Manager

## 1. Tổng quan các nâng cấp mới (Phiên bản 2.2 Pro)

### A. Tự động Auto-Sync Projects từ Database Antigravity
- **Cơ chế hoạt động**:
  - Đọc trực tiếp file SQLite `C:\Users\maing\.gemini\antigravity\conversation_summaries.db` của Antigravity ở chế độ read-only (`mode=ro`) để tuyệt đối không gây xung đột lock/WAL khi Antigravity đang hoạt động.
  - Quét bảng `conversation_summaries` lấy `workspace_uris` và `title`.
  - Tự động giải mã URL encoding và chuyển đổi URI `file:///...` thành Windows path chuẩn:
    - `file:///z:/home/thanhthien/projects/timioffice` -> `Z:\home\thanhthien\projects\timioffice`
    - `file:///c:/laragon/www/gecafe`                 -> `C:\laragon\www\gecafe`
    - `file:///c%3A/Docker`                           -> `C:\Docker`
    - `file:///c:/laragon/www/baogiaTimioffice`       -> `C:\laragon\www\baogiaTimioffice`
  - Thống kê chi tiết cho từng dự án:
    - **Số lượng cuộc hội thoại (`conv_count`)**: Sắp xếp ưu tiên các dự án hoạt động nhiều nhất lên đầu.
    - **Tiêu đề hội thoại gần nhất (`latest_title`)**: Hiển thị tác vụ gần nhất đang thực hiện trên dự án.
  - Nạp trực tiếp vào combobox **"Chọn Dự Án"** tại tab `Khởi Chạy Matrix` và bảng Matrix, định dạng:
    `Timioffice (28 convs - Fix header layout...)`
  - Nút **"🔄 Đồng Bộ từ Antigravity"** được bố trí ngay cạnh dropdown dự án và tại thanh công cụ quản lý dự án để người dùng làm mới danh sách bất cứ lúc nào.

---

### B. Tiện ích Chọn Thư Mục Mới (Quick Folder Picker)
- **Nút "📁 Chọn Thư Mục Mới..."** đặt ngay cạnh combobox chọn dự án.
- Bấm vào sẽ mở Windows Folder Picker native cho phép người dùng chọn bất kỳ thư mục mã nguồn nào trên máy tính (Windows hoặc WSL2 Z:).
- Khi người dùng chọn thư mục mới:
  - Tự động chuẩn hóa đường dẫn và đặt tên dự án theo tên thư mục.
  - Tự động ghi nhận vào danh sách dự án trong `config.json`.
  - Tự động chọn dự án này trên combobox và sẵn sàng khởi chạy ngay.
  - Hiển thị thông báo hoặc xác nhận khởi chạy nhanh Antigravity cho thư mục vừa chọn.

---

### C. Chạy ngầm dưới Khay Hệ Thống (System Tray) khi đóng ứng dụng
- **Cơ chế hoạt động**:
  - Khi bấm nút tắt `[X]`, app tự động ẩn ngầm vào **Khay Hệ Thống (System Tray icon)** bên cạnh đồng hồ Windows.
  - Click chuột hoặc double click vào icon khay để mở lại giao diện.
  - Chuột phải mở menu Win32 native: "🖥️ Mở Giao Dien", "💥 Đóng Tất Cả Cửa Sổ AI", "❌ Thoát Hoàn Toàn".
- **Công nghệ triển khai**: Pure Win32 API qua ctypes (`Shell_NotifyIconW`, `TrackPopupMenu`, `NOTIFYICONDATAW`), không phụ thuộc thư viện ngoài.

---

### D. Tự khởi động cùng Windows khi bật máy (Windows Registry Run & Silent Launch)
- Tích hợp Windows Registry tại: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, key `AntigravitySwarmManager`.
- Khi máy tính khởi động, cờ `--tray` tự động ẩn giao diện vào khay hệ thống, không làm chớp nháy màn hình.

---

### E. Lưu trữ cấu hình VĨNH VIỄN (Zero Configuration Persistence)
- Tự động lưu cấu hình vào `%APPDATA%\Antigravity_Swarm_Manager\config.json`, Desktop và thư mục nguồn.
- Tự động ghi nhớ `Antigravity.exe`, tài khoản Profile và dự án đã chọn gần nhất. Bật máy lên là sẵn sàng làm việc ngay.

---

## 2. Các Tập Tin Được Tạo & Cập Nhật

Toàn bộ các file đã được hoàn thiện tại thư mục:
`z:\home\thanhthien\projects\timioffice\antigravity_swarm_upgrade\`

1. **`Antigravity_Swarm_Manager.pyw`**: Mã nguồn chính cập nhật phiên bản 2.2 tích hợp Auto-Sync SQLite DB và Quick Folder Picker.
2. **`config.json`**: Cấu hình mẫu mặc định sẵn sàng sử dụng.
3. **`AntigravitySwarmManager.spec`**: File cấu hình PyInstaller bổ sung `sqlite3`, `urllib`, `urllib.parse`.
4. **`deploy_to_desktop.bat`**: Script Batch 1-Click tự động:
   - Bước 1: Kiểm tra cú pháp bằng Python 3.13 (`C:\laragon\bin\python\python-3.13\python.exe` hoặc PATH).
   - Bước 2: Sao lưu phiên bản cũ trên Desktop.
   - Bước 3: Copy mã nguồn và spec vào Desktop (`C:\Users\maing\Desktop\Antigravity-MultiProject-Launcher`).
   - Bước 4: Đóng gói PyInstaller EXE (`AntigravitySwarmManager.exe`).
   - Bước 5: Tự động commit và push lên GitHub (`https://github.com/thanhthienz22016/Antigravity-MultiProject-Launcher.git`).
   - Bước 6: Báo cáo kết quả chi tiết.
5. **`deploy_to_desktop.ps1`**: Script PowerShell tương đương cho người dùng ưa chuộng PowerShell.

---

## 3. Hướng Dẫn Kích Hoạt 1-Click (Swarm Manager)

Người dùng chỉ cần nhấp đúp vào một trong 2 file script:
👉 **`z:\home\thanhthien\projects\timioffice\antigravity_swarm_upgrade\deploy_to_desktop.bat`**
hoặc chuột phải chọn "Run with PowerShell" vào:
👉 **`z:\home\thanhthien\projects\timioffice\antigravity_swarm_upgrade\deploy_to_desktop.ps1`**

---

## 4. Nâng Cấp Antigravity Auto-Submit v3.1 (Swarm Background Resilience)

### A. Vấn đề giải quyết triệt để:
- **Hiện tượng cũ**: Khi người dùng dùng 2 màn hình, di chuyển chuột sang màn hình khác hoặc để Antigravity chạy ngầm ở màn hình phụ, Chromium/Electron tự động bóp băng thông (background throttling), dừng render và hoãn timer, dẫn đến công cụ auto-submit bị tạm ngưng (phải click chuột vào tab Antigravity thì nó mới "tỉnh dậy").
- **Các khiếm khuyết được khắc phục triệt để trong bản vá v3.1 Pro**:
  1. **Khắc phục lỗi lệch bộ đệm WebSocket (Zero Buffer Desync)**: Thay thế hoàn toàn cơ chế đọc từng phần (`_recv_exact`) bằng kiến trúc Atomic Frame Buffer Parser (`_parse_frame_from_buf`). Nếu socket timeout xảy ra giữa chừng, toàn bộ buffer được bảo toàn nguyên vẹn 100%, không bị nuốt byte làm lệch header frame của các gói tin tiếp theo. Hỗ trợ đầy đủ gói tin phân mảnh (fragmented frames/continuation opcodes).
  2. **Quét toàn diện mục tiêu Electron (Full Target Discovery)**: Mở rộng bộ lọc CDP không chỉ giới hạn ở `type: "page"` mà hỗ trợ cả `type: "webview"` và `type: "iframe"`. Trong VS Code/Antigravity, các thẻ tool execution và hội thoại AI thường nằm trong WebView panel. Nhờ đó, Auto-Submit kết nối trực tiếp vào đúng execution context của webview.
  3. **Chống Flapping Worker Pool (Anti-Flapping Retention)**: Khắc phục lỗi worker bị hủy ngay lập tức khi một truy vấn HTTP `/json` bị nghẽn trong 1 chu kỳ. Hệ thống duy trì kết nối WebSocket hiện có làm chân lý (ground truth) và chỉ dọn dẹp khi cổng thực sự đóng hoặc mất kết nối 3 chu kỳ liên tiếp.
  4. **Tự động kích hoạt DevTools Port từ Swarm Manager**: Bổ sung cờ `--remote-debugging-port=0` vào lệnh khởi chạy trong `Antigravity_Swarm_Manager.pyw`. Mọi cửa sổ mở từ Swarm Manager đều tự động cấp phát cổng và sinh file `DevToolsActivePort`.
  5. **CDP Focus Emulation & Active Lifecycle**: Gọi `Emulation.setFocusEmulationEnabled(enabled=True)`, `Emulation.setBackgroundThrottlingEnabled(enabled=False)`, `Emulation.setIdleOverride(isUserActive=True, isScreenUnlocked=True)` và `Page.setWebLifecycleState(state="active")` định kỳ mỗi 30s để duy trì execution context hoạt động 100% tốc độ kể cả khi thu nhỏ hay ở màn hình phụ.
  6. **Multi-Layer Synthetic & Hardware Click Engine**: Kết hợp W3C DOM Level 3 Pointer/Mouse events (`button: 0, buttons: 1` down, `buttons: 0` up), native `btn.click()`, `KeyboardEvent Enter`, và CDP Hardware `Input.dispatchMouseEvent` (`mouseMoved` -> `mousePressed` -> `mouseReleased`) tại tọa độ chính xác. Kèm theo Win32 Background Fallback (`PostMessageW`) khi có HWND. Tuyệt đối không cướp chuột, không đổi cửa sổ active của người dùng.
  7. **Bộ từ điển nhận diện mở rộng**: Bổ sung đầy đủ các biến thể tiếng Anh và tiếng Việt: "Proceed", "Proceed anyway", "Run Command", "Run in Terminal", "Always Run", "Execute Command", "Approve Command", "Allow", "Always Allow", "Allow Always", "Run Tool", "Trust", "Tiến hành", "Chạy lệnh", "Luôn chạy", "Cho phép luôn", "Đồng ý chạy", "Chấp thuận"... Loại trừ tuyệt đối các nút hủy/từ chối.

### B. Hướng dẫn Triển Khai 1-Click Auto-Submit v3.1:
Người dùng chỉ cần nhấp đúp vào:
👉 **`z:\home\thanhthien\projects\timioffice\antigravity_swarm_upgrade\deploy_auto_submit.bat`**
hoặc chuột phải chọn "Run with PowerShell" vào:
👉 **`z:\home\thanhthien\projects\timioffice\antigravity_swarm_upgrade\deploy_auto_submit.ps1`**

Script sẽ tự động:
1. Kiểm tra cú pháp bằng Python `py_compile`.
2. Đóng tiến trình `AntigravityAutoSubmit.exe` cũ đang chạy.
3. Sao chép mã nguồn và spec vào `C:\Users\maing\Desktop\Antigravity-AutoSubmit`.
4. Đóng gói file EXE độc lập bằng PyInstaller (`AntigravityAutoSubmit.spec`).
5. Khởi động lại ứng dụng `AntigravityAutoSubmit.exe` mới nhất.
6. Tự động cấu hình remote và push lên GitHub repo: `https://github.com/thanhthienz22016/auto-submit-antigravity.git`.

---

## 5. Nâng Cấp Phiên Bản 2.3 Pro: Phân Vùng Độc Lập 10 Gmail Profiles & Bào Quota Song Song

### A. Nguyên nhân cốt lõi gây ra hiện tượng logout chéo:
1. **Trùng Profile mặc định cũ (`prof_default`)**:
   - Trước đây trong cấu hình chỉ có duy nhất 1 profile "Tài khoản Mặc Định (Thành Thiện)". Khi mở 2 dự án khác nhau nhưng vẫn dùng chung Profile này (như trong ảnh chụp `media_1790152895769.png`), cả 2 cửa sổ đều trỏ về thư mục dữ liệu gốc.
2. **Không phân lập `USERPROFILE` & `HOME`**:
   - Antigravity / Gemini AI lưu trữ thông tin đăng nhập Google OAuth và SQLite database tại `~/.gemini/antigravity` (dựa trên `os.homedir()`).
   - Nếu biến môi trường `USERPROFILE` và `HOME` không được chuyển hướng vào thư mục riêng của từng Profile, các tiến trình Antigravity sẽ đều đọc/ghi vào `C:\Users\maing\.gemini`. Khi một cửa sổ đăng xuất hoặc đổi tài khoản, cửa sổ kia sẽ bị logout theo.
3. **Trùng lặp `%TEMP%` & Chromium Single-Instance Lock**:
   - Khi chạy nhiều tiến trình Electron trên cùng một Windows user, nếu dùng chung `%TEMP%` và Credential Store, chúng có thể kết nối vào cùng socket hoặc xung đột lock file.

### B. Giải pháp nâng cấp triệt để & hoàn hảo:
1. **Tự động di chuyển & chuẩn hóa (Legacy Migration)**:
   - Tự động phát hiện và chuyển đổi profile cũ `prof_default` thành `profile_01` ("Tài khoản 01 (Chính)").
   - Luôn khởi tạo và duy trì chuẩn xác 10 Profiles độc lập từ `profile_01` đến `profile_10` tại `%APPDATA%\Antigravity_Profiles\profile_xx`.
2. **Bảo tồn nguyên vẹn phiên đăng nhập chính cho Profile 01 (`mainguyenz22016@gmail.com`)**:
   - Khi khởi chạy `profile_01` lần đầu, hệ thống tự động sao chép an toàn dữ liệu `.gemini` và `.gitconfig` từ máy chính sang `profile_01\UserProfile`.
   - Nhờ đó, người dùng **KHÔNG CẦN đăng nhập lại** tài khoản chính `mainguyenz22016@gmail.com`.
3. **Phân vùng Sandbox 100% cho Profile 02 đến Profile 10**:
   - Các Profile từ 02 đến 10 là môi trường hoàn toàn sạch sẽ, độc lập.
   - Mỗi Profile sở hữu một `UserProfile` riêng:
     * `USERPROFILE` & `HOME` trỏ về `profile_xx\UserProfile`
     * `APPDATA` trỏ về `profile_xx\UserProfile\AppData\Roaming`
     * `LOCALAPPDATA` trỏ về `profile_xx\UserProfile\AppData\Local`
     * `TEMP` & `TMP` trỏ về `profile_xx\Temp`
     * `GEMINI_HOME` trỏ về `profile_xx\UserProfile\.gemini`
     * `ANTIGRAVITY_DATA_DIR` trỏ về `profile_xx\antigravity_data`
   - Cờ dòng lệnh Chromium/VS Code:
     * `--new-window`: Bắt buộc mở cửa sổ độc lập.
     * `--user-data-dir`: Phân vùng cookies, LocalStorage, IndexedDB riêng biệt.
     * `--extensions-dir`: Tiện ích mở rộng riêng.
     * `--profile-directory=Default` & `--password-store=basic`.
4. **Cơ chế chống chọn trùng & Hỗ trợ thao tác cực nhanh**:
   - Dropdown tự động hiển thị trạng thái `[🟢 Đang chạy]` hoặc `[⚪ Sẵn sàng]`.
   - Sau khi bấm "▶ Mở Cửa Sổ Này", dropdown tự động nhảy sang Profile rảnh tiếp theo (Profile 2, Profile 3...).
   - Bảng Giám sát Realtime bổ sung cột **"Phân Vùng User Data"** (`...\profile_xx`).
   - Nút **"📂 Mở Thư Mục Profile"** trong Tab Quản Lý Profiles cho phép mở ngay thư mục trên Windows Explorer để kiểm tra file.
   - Hộp thoại cảnh báo xung đột sẽ lập tức nhắc nhở nếu người dùng cố ý mở 2 cửa sổ với cùng một Profile Gmail.

### C. Quy trình người dùng đăng nhập 10 Gmail để bào Quota:
1. Mở `AntigravitySwarmManager.exe` (hoặc chạy qua `deploy_to_desktop.bat`).
2. Mở Cửa sổ 1 (Profile 01): Tài khoản chính `mainguyenz22016@gmail.com` đã được giữ nguyên và sẵn sàng làm việc.
3. Chọn Profile 02 -> Bấm "▶ Mở Cửa Sổ Này":
   - Cửa sổ Antigravity mới hiện lên với màn hình "Welcome to Antigravity" / "Sign in - Continue with Google".
   - Bấm **"Continue with Google"**, trên trình duyệt chọn **"Sử dụng một tài khoản khác" (Use another account)** và đăng nhập Gmail thứ 2.
4. Lặp lại với Profile 03, 04... 10:
   - Mỗi cửa sổ lưu phiên đăng nhập riêng trong `Antigravity_Profiles\profile_xx`.
   - 10 tài khoản chạy song song 100%, độc lập Quota, không bao giờ bị logout chéo!

---

## 6. Nâng Cấp Phiên Bản 2.4 Pro: Giám Sát Quota Từng Model (Gemini / Claude / GPT) & Nút Thông Minh Smart Focus

### A. Bối cảnh & Yêu cầu giải quyết
- **Theo dõi Quota trực quan**: Người dùng cần nắm rõ hạn ngạch còn lại của từng dòng model (Gemini Models và Claude / GPT models) cho từng profile Gmail để điều phối công việc hiệu quả và chuyển đổi tài khoản khi một bên sắp hết quota.
- **Nút mở thông minh (Smart Open / Focus)**: Khi người dùng bấm mở một profile đang chạy dở, ứng dụng phải lập tức đưa cửa sổ Antigravity của profile đó lên trên cùng (Foreground/Focus) thay vì hiện hộp thoại cảnh báo gây phiền toái hoặc mở đè tiến trình mới. Nếu profile chưa chạy thì mới khởi chạy cửa sổ mới.

### B. Các tính năng đột phá trong v2.4 Pro:
1. **Thẻ Hiển Thị Quota Chi Tiết (Real-time Model Quota Card)**:
   - Bố trí ngay trên tab **Khởi Chạy Matrix**:
     * **Gemini Models**: Hiển thị hạn mức 5 giờ (`Five Hour Limit Remaining`) và hạn mức tuần (`Weekly Limit Remaining`) kèm thời gian đếm ngược hồi sinh quota (ví dụ `2 hours`, `4 days`).
     * **Claude & GPT Models**: Hiển thị riêng biệt hạn mức 5 giờ và tuần kèm thời gian làm mới (ví dụ `42 minutes`, `2 days`).
   - Hệ thống huy hiệu màu sắc trực quan (Color Badges):
     * 🟢 **Xanh lá (> 50%)**: Quota dồi dào, sẵn sàng cho tác vụ nặng.
     * 🟡 **Vàng (15% - 50%)**: Quota trung bình, nên chuẩn bị chuyển giao tài khoản.
     * 🔴 **Đỏ (< 15%)**: Quota sắp cạn, cần chuyển sang profile khác hoặc chờ hồi phục.
   - Nút **"🔍 Quét Quota Ngay"** để kiểm tra hạn ngạch tức thì theo yêu cầu.

2. **Cột Quota Trên Bảng Ma Trận & Giám Sát**:
   - Bảng Matrix bổ sung 2 cột: `Gemini (5h/Tuần)` và `Claude/GPT (5h/Tuần)`.
   - Định dạng trực quan: `🟢 94% | 🟡 39%`, `🔴 3% | 🟢 68%`. Người dùng nhìn lướt qua là biết tài khoản nào sẵn sàng.

3. **Động cơ Trích Xuất Quota Đa Tầng (Multi-Tier Quota Extractor)**:
   - **Tầng 1 (CDP WebSocket)**: Tự động kết nối qua cổng DevTools của Chromium (`--remote-debugging-port=0`), quét DOM text và `localStorage` của Antigravity để đọc dữ liệu quota chính xác từ giao diện chuẩn.
   - **Tầng 2 (Local Cache)**: Ghi nhớ vào `quota_cache.json` tại thư mục dữ liệu của từng profile để hiển thị ngay lập tức khi mở app.
   - **Tầng 3 (SQLite State Fallback)**: Quét bảng `ItemTable` trong `state.vscdb` để tìm kiếm hạn mức đã được VS Code lưu trữ.

4. **Nút Hành Động Thông Minh (Smart Focus / Launch Button)**:
   - Tự động thay đổi diện mạo và hành vi dựa trên trạng thái của Profile:
     * Khi Profile **ĐANG CHẠY**: Nút hiển thị `"🎯 Focus Cửa Sổ Này"` (được tạo kiểu `Accent.TButton` nổi bật). Bấm vào sẽ:
       1. Khôi phục cửa sổ nếu đang bị thu nhỏ (`SW_RESTORE`).
       2. Đính kèm luồng nhập liệu (`AttachThreadInput`) giữa Swarm Manager và cửa sổ đích.
       3. Gọi `BringWindowToTop` và `SetForegroundWindow` để đưa ngay tab Antigravity lên đầu màn hình.
       4. Tuyệt đối **không hiển thị hộp thoại chặn** (no blocking dialog).
     * Khi Profile **CHƯA CHẠY**: Nút hiển thị `"▶ Mở Cửa Sổ Này"` để khởi chạy Antigravity cho profile đó.
   - **Double-Click Focus**: Người dùng có thể nhấp đúp vào bất kỳ dòng nào trong bảng Giám Sát hoặc ô Quota trong Matrix để đưa ngay cửa sổ Antigravity tương ứng lên trước mặt.

5. **Tự Động Cập Nhật Ngầm (Background Quota Sync)**:
   - Timer chạy ngầm mỗi 8 giây tự động kiểm tra và đồng bộ quota của các profile đang mở, cập nhật giao diện hoàn toàn mượt mà không gây giật lag.
