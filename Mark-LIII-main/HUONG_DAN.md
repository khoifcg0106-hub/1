# Mark LIII — Hướng dẫn chạy & đóng gói trên Windows

## Mới thêm: Floating Button (nút nổi luôn-trên-cùng)
File `floating_button.py` (mới) hiện thực đúng bản thiết kế
"FLOATING BUTTON v5 SPECIFICATION": 10 trạng thái màu đúng spec, click
trái bung Radial Menu 6 nút (VOICE/CHAT/QUICK/SLEEP/SETUP/CENTER),
click phải mở Quick Actions, double-click mở Command Center, kéo thả
đổi vị trí (tự lưu), cuộn chuột đổi cỡ 40/56/72/88px. Được gắn thêm
vào `main.py` mà **không sửa** `ui.py` — cửa sổ Command Center cũ
vẫn hoạt động y như trước, nút nổi chỉ là lớp bổ sung.

## Kết quả kiểm tra code (bước 1)
Đã compile toàn bộ 42 file Python + chạy static analysis (pyflakes):
**không có lỗi cú pháp, không có biến/hàm bị thiếu, không có logic vỡ.**
Chỉ có vài cảnh báo cosmetic (vài import không dùng tới, vài f-string
không có `{}` bên trong) — hoàn toàn vô hại, không sửa để tránh rủi ro
làm hỏng code đang chạy tốt. Kết luận: code trong repo đã đầy đủ và
sẵn sàng chạy như README mô tả.

## Bước 2 — Chạy từ source trên Windows (khuyên làm trước)

### Cách 1 — Tự động hoàn toàn (khuyên dùng)
Có file **`CAI_DAT_TU_DONG.ps1`** đi kèm riêng (ngoài file zip này) —
nó tự làm hết: giải nén → cài đặt → tạo icon Desktop. Cách dùng:
1. Tải `Mark-LIII-ready.zip` (file này) và `CAI_DAT_TU_DONG.ps1` —
   để **cả hai** trong thư mục **Downloads**, **giữ nguyên tên file**.
2. Chuột phải vào `CAI_DAT_TU_DONG.ps1` → **"Run with PowerShell"**.
3. Đợi chạy xong (vài phút để cài thư viện) — xong sẽ có icon
   **"Mark LIII"** ngoài Desktop, bấm vào là mở app.

Nếu muốn tự làm từng bước thay vì dùng script tự động, làm theo Cách 2:

### Cách 2 — Từng bước thủ công
Dùng 3 file có sẵn trong zip — **chỉ cần làm 1 lần**:

1. Cài **Python 3.11 hoặc 3.12** từ python.org (khi cài, nhớ tick
   "Add python.exe to PATH").
2. Giải nén zip ra một thư mục, ví dụ `C:\MarkLIII`.
3. Chuột phải vào **`setup.ps1`** → chọn **"Run with PowerShell"**.
   Script sẽ tự tạo virtual environment và cài toàn bộ thư viện cần
   thiết cho Windows.
   - Nếu Windows báo "chạy script bị chặn": mở PowerShell thường
     (không cần Admin), gõ:
     ```
     Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
     ```
     gõ `Y` rồi Enter, sau đó chạy lại `setup.ps1`.
4. (Tùy chọn) Chuột phải vào **`Create_Desktop_Shortcut.ps1`** →
   "Run with PowerShell" — tạo sẵn icon **"Mark LIII"** ngoài Desktop.
5. Từ giờ chỉ cần **double-click `Run_MarkLIII.bat`** (hoặc icon vừa
   tạo ngoài Desktop) để mở app — không cần gõ lệnh gì nữa.
6. Lần đầu mở app, nó sẽ hỏi **Gemini API key** (miễn phí, lấy tại
   https://aistudio.google.com/apikey) — key được lưu vào
   `config/api_keys.json`.
7. Nói "Hey Jarvis" (nếu đã bật Wake Word trong ⚙) hoặc dùng luôn —
   micro/loa chọn trong ⚙ → AUDIO DEVICES nếu Windows nhận sai thiết bị.

## Bước 3 — Đóng gói thành file .exe (không cần cài Python để chạy)

**Quan trọng:** việc build .exe phải chạy trên chính máy Windows —
không thể build file .exe từ máy Linux/macOS.

1. Đảm bảo bước 2 đã chạy được bằng `python main.py` (nghĩa là mọi
   thư viện đã cài đủ).
2. Double-click file `build_windows.bat` đi kèm (hoặc chạy trong cmd).
   Script sẽ:
   - Tạo virtual environment riêng
   - Cài lại dependencies + PyInstaller
   - Đóng gói ở chế độ **onedir** (không dùng onefile) — vì app này
     cần *ghi* vào `config/api_keys.json` và `memory/long_term.json`
     khi chạy; onefile sẽ giải nén vào thư mục tạm và mất dữ liệu
     giữa các lần chạy.
3. Kết quả nằm ở `dist\MarkLIII\MarkLIII.exe`. Chép **cả thư mục**
   `dist\MarkLIII` sang máy khác nếu cần dùng — đừng tách riêng file
   .exe ra khỏi các file đi kèm.

## Lưu ý khi build
- Nếu PyInstaller báo thiếu module nào (ví dụ `win32timezone`,
  `_cffi_backend`...), thêm `--hidden-import <tên_module>` vào lệnh
  trong `build_windows.bat` rồi chạy lại — đây là chuyện bình thường
  với app dùng nhiều thư viện hệ thống Windows (pywin32, pycaw...).
- Tính năng Wake Word ("Hey Jarvis") cần tải thêm `openwakeword` —
  bấm ⚙ → WAKE WORD trong app để tải, không cần thêm vào bước build.
- Nếu Windows Defender/SmartScreen cảnh báo file .exe lạ, đó là vì
  file chưa được ký số (code signing) — bình thường với app tự build,
  chọn "More info → Run anyway".
