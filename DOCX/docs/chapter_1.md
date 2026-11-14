# CHƯƠNG 1: MỞ ĐẦU
## 1.1. Lý do chọn đề tài
Một trong những mô h mô hình mạng được sử dụng để xây dựng trao đổi dữ liệu là mô hình Peer-to-Peer (P2P). Đây là mô hình cho phép các thiết bị tham gia mạng có thể trực tiếp giao tiếp với nhau và trao đổi dữ liệu với nhau, khác so với mô hình Client-Server truyền thống, trong đó các thiết bị thường phải giao tiếp thông qua một máy chủ trung tâm. 
Nhóm đã vận dụng các kiến thức liên quan đến lập trình mạng, giao thức TCP/IP, lập trình socket, truyền thông UDP và xử lý dữ liệu JSON, ngoài ra còn có lập trình đa luồng và mã hóa dữ liệu nhằm nâng cao khả năng xử lý và bảo mật thông tin để nghiên cứu và xây dựng đề tài P2P Chat & File Transfer Application - ứng dụng nhắn tin và truyền tải tệp tin theo mô hình P2P.
Mục tiêu sau nghiên cứu và xây dựng đề tài là một ứng dụng cho phép các thiết bị trong cùng mạng có thể phát hiện nhau, thiết lập kết nối và thực hiện trao đổi thông tin trực tiếp. 

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
- Định dạng dữ liệu: JSON.
- Lập trình đa luồng: QThread.
- Mã hóa: RSA và AES-256.