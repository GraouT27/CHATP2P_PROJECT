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

## 3. Quy chuẩn Cấu trúc Mã nguồn (Project Structure)

Thư mục mã nguồn được phân chia rõ ràng theo mô hình Layered Architecture:

```text
CHAT_P2P/
│
├── core/                   # Phân hệ Mạng & P2P Core
│   ├── discovery.py        # Lắng nghe & phát tín hiệu UDP Broadcast
│   ├── listener.py         # Lắng nghe kết nối TCP ngầm
│   └── socket_client.py    # Khởi tạo kết nối TCP gửi tin nhắn
│
├── transfers/              # Phân hệ Xử lý truyền file & Hàng đợi
│   ├── file_sender.py      # Cắt nhỏ file và gửi chunk dữ liệu
│   ├── file_receiver.py    # Nhận chunk dữ liệu và ghép thành file
│   └── queue_manager.py    # Quản lý hàng đợi & giới hạn truyền đồng thời
│
├── gui/                    # Phân hệ Giao diện Người dùng
│   ├── main_window.py      # Màn hình chính & hiển thị danh sách Peer
│   ├── chat_panel.py       # Khung trò chuyện 1-1
│   └── transfer_panel.py   # Bảng kéo thả file & Thanh tiến trình
│
├── config.py               # Cấu hình hệ thống (Port, Chunk Size, Paths)
├── REQUIREMENTS.md         # Tài liệu yêu cầu kỹ thuật
└── main.py                 # File khởi chạy ứng dụng (Entry Point)
```