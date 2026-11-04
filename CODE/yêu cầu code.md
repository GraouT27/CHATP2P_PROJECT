# Yêu cầu Kỹ thuật & Mã nguồn - Dự án Chat P2P (GUI)

Tài liệu này định nghĩa chi tiết các yêu cầu kiến trúc, chức năng và quy chuẩn mã nguồn cho việc lập trình ứng dụng **Chat & Truyền File Ngang hàng (P2P)** không sử dụng Server trung tâm.

---

## 1. Yêu cầu Kiến trúc & Công nghệ (Core Architecture)

* **Mô hình P2P (Peer-to-Peer):** 
  * Mỗi instance chạy trên máy người dùng đồng thời đóng vai trò là **Server Listener** và **Client Socket**.
  * **Peer Listener (Server Socket):** Mở cổng TCP (mặc định: `8080`) chạy ngầm để chờ nhận kết nối, tin nhắn và dữ liệu từ các Peer khác.
  * **Peer Client (Client Socket):** Tự động khởi tạo kết nối TCP trực tiếp tới IP/Port của Peer đối phương khi thực hiện gửi tin nhắn hoặc truyền file.
* **Cơ chế Khám phá nút mạng (Peer Discovery):**
  * Sử dụng **UDP Broadcast** (gửi gói tin tới IP `255.255.255.255` hoặc dải subnet LAN) định kỳ mỗi 3–5 giây để tự động nhận diện các máy đang Online trong cùng mạng nội bộ mà không cần Server phân giải.
* **Xử lý Đa luồng (Multi-threading / Async):**
  * Luồng giao diện GUI chính (Main Thread) tuyệt đối **không** thực hiện các thao tác blocking I/O (lắng nghe socket, đọc/ghi file dung lượng lớn).
  * Sử dụng các luồng chạy ngầm (`QThread` / `threading.Thread`) riêng biệt cho:
    1. Lắng nghe tín hiệu UDP Broadcast Discovery.
    2. Lắng nghe kết nối TCP đến.
    3. Luồng gửi và nhận từng file độc lập.

---

## 2. Yêu cầu Chức năng Mã nguồn (Functional Requirements)

### 2.1. Giao diện GUI (User Interface)
* **Danh sách Peer:** Tự động cập nhật danh sách các nút mạng Online (Tên máy, IP, Port, Trạng thái hoạt động).
* **Khung Trò chuyện (Chat View):** Nhập và hiển thị lịch sử tin nhắn văn bản (Text) tức thời 1-1 giữa các Peer.
* **Bảng Quản lý Truyền File:**
  * **Drag & Drop:** Cho phép kéo thả trực tiếp một hoặc nhiều file vào khu vực chuyển dữ liệu trên GUI.
  * **Progress Bar:** Hiển thị phần trăm hoàn thành (%) và tốc độ truyền thực tế (KB/s, MB/s) riêng biệt cho từng file.
  * **Trạng thái file:** Hiển thị rõ ràng 4 trạng thái độc lập: `Chờ (Waiting)`, `Đang tải (Transferring)`, `Hoàn tất (Completed)`, `Lỗi (Failed)`.

### 2.2. Xử lý Truyền & Nhận File (File Transfer Core)
* **Cắt & Ghép File (Chunking):**
  * Đọc và truyền file theo từng khối dữ liệu nhỏ (Chunk size: 4KB - 64KB) qua kết nối TCP.
* **Hàng đợi & Truyền đồng thời (Queue & Concurrency):**
  * Cho phép thiết lập giới hạn số file truyền đồng thời cùng lúc (Mặc định: Tối đa 3 file song song).
  * Các file vượt quá giới hạn sẽ tự động xếp vào hàng đợi (`Queue`) và được xử lý tuần tự khi có luồng rảnh.
* **Quản lý Lỗi độc lập:**
  * Lỗi kết nối hoặc sự cố truyền dẫn ở 1 file sẽ chỉ đánh dấu file đó là `Lỗi` và không làm gián đoạn hay dừng các file khác trong hàng đợi.
* **Xử lý Trùng tên File trên Máy nhận:**
  * Kiểm tra thư mục lưu trữ mặc định (`Downloads/`). Nếu file trùng tên đã tồn tại, ứng dụng tự động đánh số thứ tự hậu tố (ví dụ: `Data(1).zip`) hoặc hiển thị hộp thoại xác nhận đổi tên/ghi đè.

---

## 3. Quy chuẩn Cấu trúc Mã nguồn (Project Structure) ( đề xuất phương án )

Thư mục mã nguồn được phân chia rõ ràng theo mô hình Layered Architecture:

```đề xuất 
UDM_09_ChatP2P_Repo/                        # Thư mục gốc trên GitHub của nhóm
│
├── .gitignore                              # Chặn __pycache__/, .venv/, *.part, *.log, .vscode/, .idea/ (Bắt buộc)
├── README.md                               # Tên & mã đề tài (UDM_09), DS 6 thành viên, kiến trúc P2P, cấu hình, HD chạy & Link Video Demo
│
├── DOCX/                                   # Thư mục chứa Báo cáo Word (Theo yêu cầu cấu trúc Repo)
│   └── Bao_Cao_Do_An_UDM_09_ChatP2P.docx   # Báo cáo: Mục tiêu, kiến trúc, protocol, cấu trúc message, GUI, phân công, kiểm thử, hạn chế
│
├── PPTX/                                   # Thư mục chứa Slide thuyết trình (Theo yêu cầu cấu trúc Repo)
│   └── Slide_Bao_Ve_UDM_09_ChatP2P.pptx    # Slide trình bày khi bảo vệ đồ án
│
├── Extra/                                  # Thư mục chứa bằng chứng kiểm thử, hình ảnh, log mẫu (Theo yêu cầu cấu trúc Repo)
│   ├── logs_evidence/                      # Lưu file log bằng chứng khi chạy demo và test ngắt kết nối
│   ├── stress_test_results/                # Lưu bảng số liệu, ảnh chụp CPU/RAM/Throughput ở 2 mức tải khác nhau
│   └── gui_screenshots/                    # Ảnh chụp giao diện phục vụ nhúng vào README.md và Báo cáo
│
└── Code/                                   # THƯ MỤC MÃ NGUỒN CHÍNH CỦA ỨNG DỤNG PYTHON
    │
    ├── requirements.txt                    # Khai báo thư viện: PyQt6, cryptography, psutil, pytest (TV1)
    ├── config.py                           # Quản lý cấu hình động: HOST, LISTEN_PORT, TIMEOUT, MAX_CONCURRENT, CHUNK_SIZE (TV4)
    ├── main.py                             # [ĐIỂM CHẠY DUY NHẤT] Khởi tạo Logger, bật P2P Listener ngầm và mở cửa sổ GUI PyQt6 (TV1, TV2, TV4)
    │
    ├── p2p_node/                           # PHÂN HỆ LÕI MẠNG P2P & TRUYỀN TẢI ĐA LUỒNG (TV4 & TV5)
    │   ├── __init__.py
    │   ├── discovery.py                    # [TV4] UDP Broadcast tự động quét và thông báo sự hiện diện của Peer trong mạng LAN
    │   ├── listener.py                     # [TV4] QThread mở TCP Socket lắng nghe kết nối đến từ các Peer khác (không dùng Server trung tâm)
    │   ├── sender.py                       # [TV4, TV5] Thiết lập kết nối TCP tới Peer đích, gửi gói tin chat/chunk file có kiểm soát Timeout
    │   ├── handler.py                      # [TV4, TV5] Xử lý luồng dữ liệu đến: giải mã, phân loại Text/Emoji/Reply/Forward/Avatar/File và trả ACK
    │   ├── transfer_task.py                # [TV5] Lớp đối tượng quản lý trạng thái 1 tác vụ truyền file (path, size, status, sent, speed, error)
    │   ├── transfer_manager.py             # [TV5] Quản lý Hàng đợi (Queue) + Semaphore giới hạn luồng + QThread truyền đa file song song
    │   ├── storage.py                      # [TV5] Ghi chunk vào file tạm (.part), kiểm tra hoàn tất mới rename, xử lý trùng tên & lưu cache Avatar
    │   └── speed_meter.py                  # [TV5] Thuật toán cửa sổ trượt tính tốc độ truyền (KB/s, MB/s, message/s) theo thời gian thực
    │
    ├── ui/                                 # PHÂN HỆ GIAO DIỆN ĐỒ HỌA DESKTOP PYQT6 (TV2 & TV3)
    │   ├── __init__.py
    │   ├── app.py                          # [TV2] Cửa sổ chính (MainWindow), bố cục tổng thể và thanh hiển thị trạng thái kết nối/xử lý
    │   ├── peer_list_widget.py             # [TV2] Khung danh sách Peer bên trái: hiển thị Avatar (QPixmap), tên, IP:Port và trạng thái Online/Offline
    │   ├── chat_widgets.py                 # [TV2] Bong bóng chat (kèm Avatar), khung trích dẫn Reply tin nhắn, và bảng chọn Emoji (Emoji Picker)
    │   ├── dialogs.py                      # [TV3] Hộp thoại (QDialog) chọn Peer để Forward tin nhắn & Hộp thoại đổi IP/Port/Chọn ảnh Avatar
    │   ├── file_row.py                     # [TV3] Widget hiển thị 1 dòng truyền file: Tên, dung lượng, thanh QProgressBar, tốc độ, nút Hủy
    │   ├── dnd.py                          # [TV3] Xử lý sự kiện Kéo & Thả file (dragEnterEvent, dropEvent) trực tiếp vào khu vực trò chuyện
    │   └── styles.qss                      # [TV2, TV3] Bảng định dạng giao diện Qt Style Sheets (bo góc khung chat, màu sắc chủ đạo)
    │
    ├── security/                           # PHÂN HỆ BẢO MẬT, MÃ HÓA & GHI LOG AN TOÀN (TV6)
    │   ├── __init__.py
    │   ├── crypto_manager.py               # [TV6] Sinh cặp khóa RSA động trên RAM (không hard-code), trao đổi khóa và mã hóa/giải mã AES-256
    │   └── logger.py                       # [TV6] Ghi log sự kiện (thời gian, kết nối, ngắt kết nối, lỗi) ra file và lọc bỏ khóa bí mật khỏi log
    │
    ├── shared/                             # PHÂN HỆ GIAO THỨC & TIỆN ÍCH DÙNG CHUNG (TV3, TV4, TV6)
    │   ├── __init__.py
    │   ├── protocol.py                     # [TV4] Đóng gói & bóc tách khung bản tin: [4 bytes Length] + [JSON Header/UUID/Reply/Forward] + [Payload]
    │   ├── validator.py                    # [TV6] Kiểm tra tính hợp lệ của JSON Header nhận được & đối chiếu mã băm toàn vẹn SHA-256
    │   └── format.py                       # [TV3] Hàm tiện ích định dạng hiển thị dung lượng (KB, MB, GB), tốc độ (MB/s) và nhãn thời gian
    │
    ├── received_files/                     # Thư mục mặc định lưu các File hoàn chỉnh và cache Avatar nhận được từ Peer khác
    │   └── .gitkeep                        # Giữ cấu trúc thư mục trống trên Git (bỏ qua các file tải về bên trong)
    │
    └── tests/                              # PHÂN HỆ KIỂM THỬ CHỨC NĂNG, BẮT LỖI & ĐO HIỆU NĂNG 2 MỨC TẢI (TV1)
        ├── __init__.py
        ├── test_protocol_security.py       # [TV1] Kiểm thử đóng gói bản tin, mã hóa AES-256 và từ chối dữ liệu sai định dạng (Malformed data)
        ├── test_storage_rename.py          # [TV1] Kiểm thử quy tắc đổi tên khi trùng file và tự động xóa file .part khi ngắt kết nối đột ngột
        ├── test_transfer_manager.py        # [TV1] Kiểm thử giới hạn luồng đồng thời (MAX_CONCURRENT) và cô lập lỗi khi 1 Peer bị sập
        └── benchmark_stress.py             # [TV1] Script tự động chạy Stress Test & Performance Test ở 2 mức tải (đo Latency, Throughput, CPU, RAM)