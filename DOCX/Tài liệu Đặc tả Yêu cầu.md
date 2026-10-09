# Tài liệu Đặc tả Yêu cầu (SRS) - Dự án Ứng dụng Chat P2P GUI

## 1. Tổng quan dự án
- **Tên dự án:** P2P Chat & Direct File Sharing System.
- **Mục tiêu:** Xây dựng phần mềm trò chuyện và chia sẻ dữ liệu trực tiếp giữa các máy tính trong mạng nội bộ (LAN) hoặc mạng ngang hàng không qua server trung tâm, quản lý hoàn toàn bằng giao diện GUI.
- **Môi trường hoạt động:** Windows / macOS / Linux (Chạy ứng dụng desktop).

## 2. Các vai trò & Khái niệm
1. **Peer (Nút mạng):** Một thể hiện (instance) ứng dụng chạy trên máy người dùng. Mỗi Peer vừa đóng vai trò Client vừa đóng vai trò Server (P2P Node).
2. **Local Peer:** Máy hiện tại đang mở ứng dụng.
3. **Remote Peer:** Các máy đối phương đang kết nối đến trong mạng.

## 3. Yêu cầu chức năng

### 3.1. Phân hệ Kết nối & Quản lý Peer (P2P Core)
- `F-NET-01`: Tự động tìm kiếm các Peer đang hoạt động trong cùng mạng LAN (Sử dụng UDP Broadcast/Multicast).
- `F-NET-02`: Hiển thị danh sách các Peer khả dụng lên giao diện GUI (Tên máy, IP, Port, Trạng thái Online/Offline).
- `F-NET-03`: Cho phép kết nối trực tiếp thủ công tới Peer bằng IP và Port nếu nằm ngoài dải Broadcast.

### 3.2. Phân hệ Trò chuyện Trực tiếp (Direct Messaging)
- `F-CHAT-01`: Mở cửa sổ chat 1-1 trực tiếp với một Peer bất kỳ trong danh sách.
- `F-CHAT-02`: Mã hóa tin nhắn đầu-cuối (End-to-End Encryption) trước khi gửi qua socket TCP.
- `F-CHAT-03`: Hiển thị lịch sử trò chuyện tạm thời trong phiên làm việc.

### 3.3. Phân hệ Truyền & Tải File (P2P File Transfer)
- `F-FILE-01`: Cho phép kéo thả (Drag & Drop) một hoặc nhiều file trực tiếp vào khu vực upload/chat trên GUI.
- `F-FILE-02`: Quản lý danh sách file truyền đi/nhận về với trạng thái riêng biệt cho từng file: **Chờ (Waiting)**, **Đang tải (Transferring)**, **Hoàn tất (Completed)** hoặc **Lỗi (Failed)**.
- `F-FILE-03`: Hiển thị tiến trình (Progress Bar), tốc độ truyền (KB/s, MB/s) riêng cho từng file.
- `F-FILE-04`: Hỗ trợ hàng đợi truyền file (Queue) và cho phép truyền đồng thời (Nhóm thiết lập giới hạn tối đa 3 file truyền song song cùng lúc).
- `F-FILE-05`: Xử lý lỗi độc lập: Nếu 1 file bị lỗi truyền dẫn, các file khác trong hàng đợi vẫn tiếp tục được xử lý bình thường mà không dừng hệ thống.
- `F-FILE-06`: Quy tắc xử lý trùng tên file trên Peer nhận: Tự động đánh số thứ tự hậu tố (VD: `file(1).txt`) hoặc hiển thị thông báo ghi đè/đổi tên trên GUI.

## 4. Yêu cầu phi chức năng
- **Bảo mật:** Trao đổi khóa RSA khi thiết lập kết nối, mã hóa gói tin bằng AES-256.
- **Hiệu năng:** Độ trễ truyền tin nhắn trong mạng LAN < 100ms. Tốc độ truyền file tối ưu hóa theo băng thông kết nối nội bộ mà không làm treo giao diện GUI (Sử dụng QThread / Multi-threading).
- **Giao diện:** Thân thiện, không cần thao tác dòng lệnh (CLI). Hỗ trợ thông báo trạng thái kết nối rõ ràng trên màn hình.