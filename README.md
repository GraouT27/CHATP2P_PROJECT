# P2P Chat & File Transfer Application (GUI)

## 1. Giới thiệu
Ứng dụng trò chuyện và truyền dữ liệu ngang hàng (Peer-to-Peer - P2P) hoàn toàn không phụ thuộc vào Server trung tâm. Mọi thao tác tìm kiếm nút (Peer), kết nối, nhắn tin trực tiếp và truyền file đều được thực hiện thông qua giao diện đồ họa (GUI) thân thiện và trực quan.

## 2. Công nghệ & Giao thức
* **Ngôn ngữ lập trình:** Python 3.x
* **Giao diện người dùng (GUI):** PySide6 / PyQt6
* **Mạng & Giao thức:** Sockets (TCP/IP cho tin nhắn & truyền file, UDP Broadcast/Multicast cho cơ chế Peer Discovery)
* **Mã hóa & Bảo mật:** PyCryptodome (RSA cho trao đổi khóa, AES-256 cho mã hóa tin nhắn/file)
* **Version Control:** Git, GitHub

## 3. Cấu trúc dự án
* `gui/`: Thiết kế giao diện, các màn hình, dialog và luồng sự kiện UI
* `core/`: Xử lý Socket P2P, lắng nghe cổng (Listener), phát hiện nút mạng (Discovery), mã hóa/giải mã
* `transfers/`: Quản lý luồng tải/truyền file, hàng đợt (Queue), tiến trình và trạng thái
* `docs/`: Tài liệu SRS, sơ đồ kiến trúc mạng P2P và kịch bản kiểm thử

## 4. Phân công công việc (Thành viên)
* **TV1:** Project Management, QA, GitHub Administration & Release Manager
* **TV2:** GUI Design (Main UI, Peer List, Chat Box)
* **TV3:** GUI File Transfer Manager (Drag & Drop UI, Progress Bar)
* **TV4:** P2P Core & Network Protocols (Socket TCP/UDP, Peer Discovery)
* **TV5:** File Transfer Logic (Chunking, Multi-thread File Transfer, Queue)
* **TV6:** Encryption & Peer Security (AES-256, Public/Private Key Exchange)

## 5. Trạng thái
Đang trong quá trình phát triển và hoàn thiện theo kế hoạch của nhóm.
