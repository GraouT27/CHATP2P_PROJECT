# CHƯƠNG 1: MỞ ĐẦU
## 1.1. Lý do chọn đề tài
Trong lĩnh vực lập trình mạng, việc trao đổi thông tin và dữ liệu giữa các thiết bị có thể được triển khai theo nhiều mô hình kiến trúc khác nhau. Bên cạnh mô hình Client–Server, mô hình Peer-to-Peer (P2P) cho phép các thiết bị tham gia trực tiếp thiết lập kết nối và trao đổi dữ liệu với nhau mà không bắt buộc phải thông qua một máy chủ trung tâm để chuyển tiếp nội dung.

Đối với môi trường mạng nội bộ (LAN), mô hình P2P có thể được ứng dụng để xây dựng hệ thống nhắn tin và truyền tệp trực tiếp giữa các thiết bị. Việc triển khai ứng dụng theo mô hình này tạo điều kiện nghiên cứu những vấn đề quan trọng của lập trình mạng như phát hiện thiết bị, thiết lập kết nối, truyền nhận dữ liệu, định dạng thông điệp, xử lý đồng thời và bảo mật thông tin.

Xuất phát từ những nội dung trên, nhóm lựa chọn đề tài “P2P Chat & File Transfer Application”, nhằm nghiên cứu và xây dựng ứng dụng nhắn tin và truyền tệp trực tiếp giữa các thiết bị trong cùng mạng LAN.

Thông qua đề tài, nhóm vận dụng kiến thức về giao thức TCP/IP, lập trình Socket, UDP Broadcast, cấu trúc dữ liệu JSON, lập trình đa luồng và mã hóa dữ liệu vào quá trình phân tích, thiết kế và triển khai một ứng dụng thực tế. 

## 1.2. Mục tiêu đề tài
Đề tài hướng đến việc nghiên cứu và xây dựng một ứng dựng nhắn tin và truyền tải tệp tin theo mô hình Peer-to-Peer, trong đó mỗi thiết bị tham gia có khả năng hoạt động như một nút độc lập.
Các mục tiêu cụ thể gồm:
- Nghiên cứu mô hình mạng Peer-to-Peer và nguyên lý giao tiếp trực tiếp các thiết bị.
- Tìm hiểu và ứng dụng giao thức UDP Broadcasr để phát hiện các Peer đang hoạt động trong mạng nội bộ.
- Sử dụng TCP Socket để thiết lập kết nối và trao đổi dữ liệu giữa các Peer.
- Thiết kế cấu trúc bản tin JSON theo mô hình Header/Payload nhằm thống nhất định dạng dữ liệu trao đổi.
- Xây dựng cơ chế nhận diện bản tin thông qua UUID và quản lý thông tin các Peer.
- Nghiên cứu cơ chế lập trình đa luồng nhằm hỗ trợ xử lý các hoạt động mạng mà không làm gián đoạn giao diện người dùng. 
- Tìm hiểu và ứng dụng cơ chế mã hóa lai RSA và AES-256 nhằm bảo về dữ liệu trong quá trình trao đổi.
- Xây dựng giao diện đồ họa hỗ trợ người dùng thực hiện các chức năng nhắn tin và truyền tải tệp tin.
- Kiểm thử và đánh giá khả năng hoạt động của ứng dụng trong môi trường mạng nội bộ. 

## 1.3. Phạm vi đề tài 
Về môi trường hoạt động:
- Ứng dụng được thiết kế để các thiết bị có thể giao tiếp trực tiếp trong cùng mạng nội bộ (LAN).
- Mỗi Peer có khả nưng khởi tạo kết nối và tiếp nhận kết nối từ các Peer khác.
- Hệ thống không yêu cầu máy chủ trung tâm để chuyển tiếp nội dung tin nhắn và tệp.

Về chức năng:
- Phát hiện các Peer đang hoạt động thông qua UDP Broadcast.
- Quản lý danh sách các Peer được phát hiện.
- Thiết lập TCP giữa các Peer.
- Trao đổi thông điệp văn bản thông qua cấu trúc bản tin JSON.
- Thiết kế cơ chế hỗ trợ các loại tin nhắn khác như biểu tượng cảm xúc, trả lời, chuyển tiếp và truyền tải tệp tin.

- Nghiên cứu cơ chế mã hóa và truyền tải đa phương tiện. 
Về công nghê:
- Ngôn ngữ lập trình: Python.
- Giao tiếp mạng: TCP Socket và UDP Broadcast.
- Định dạng dữ liệu: JSON, mã hóa ký tự UTF-8.
- Giao diện đồ họa: Qt for Python.
- Lập trình đa luồng: QThread và các cơ chế xử lý luồng phù hợp.
- Mã hóa: RSA và AES-256.