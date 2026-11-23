# CHƯƠNG 5: KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

## 5.1. Tổng kết kết quả thực hiện đề tài

Các kết quả triển khai chính bao gồm:

- **Peer Discovery:** Xây dựng cơ chế phát hiện các Peer trong mạng LAN bằng UDP Broadcast, kết hợp phát beacon định kỳ và theo dõi thời điểm nhận thông tin để cập nhật trạng thái Peer.
- **TCP Communication:** Xây dựng các thành phần TCP Sender và TCP Listener, cho phép các Peer chủ động thiết lập kết nối và tiếp nhận dữ liệu thông qua TCP Socket.
- **Messaging:** Tích hợp chức năng gửi và nhận tin nhắn văn bản, hỗ trợ tiếng Việt và các ký tự Unicode, bao gồm biểu tượng cảm xúc.
- **Reply và Forward:** Triển khai chức năng trả lời và chuyển tiếp tin nhắn thông qua việc bổ sung metadata vào thông điệp Chat, hỗ trợ hiển thị nội dung tham chiếu và chuyển tiếp đến các Peer được lựa chọn.
- **File Transfer:** Xây dựng cơ chế chia tập tin thành các chunk, quản lý tiến độ và trạng thái truyền, hỗ trợ hủy tác vụ và kiểm tra tính toàn vẹn dữ liệu bằng SHA-256.
- **Security:** Triển khai các thành phần quản lý khóa RSA-2048, trao đổi khóa phiên và mã hóa dữ liệu bằng AES-256-GCM. Phạm vi mã hóa phụ thuộc vào cơ chế truyền thông và trạng thái khóa phiên của từng luồng xử lý.
- **Graphical User Interface:** Xây dựng giao diện desktop bằng PyQt6, tích hợp danh sách Peer, khu vực trò chuyện, Emoji Picker, Reply Preview, Forward Dialog và các thành phần quản lý truyền tập tin.
- **Testing:** Xây dựng các chương trình kiểm thử tự động cho giao thức, giao diện, truyền thông, bảo mật, khả năng chịu lỗi và hiệu năng.

Về kiểm thử, phiên chạy pytest được ghi nhận tại Chương 4 cho thấy **26/26 bài kiểm thử tự động thuộc ba nhóm Resilience, Security Conflicts và QA Specification đều đạt yêu cầu**, không có bài kiểm thử thất bại trong phạm vi đã thực thi.

Ngoài ra, chương trình benchmark được lưu trong repository ghi nhận kết quả PASS tại hai mức tải: 5 Peer với tốc độ 50 tin nhắn/giây và 15 Peer với tốc độ 200 tin nhắn/giây.

Tuy nhiên, benchmark được thực hiện trên môi trường loopback bằng các thành phần thử nghiệm riêng, không phải phép đo trực tiếp toàn bộ ứng dụng GUI trong mạng LAN thực tế.

Nhìn chung, đề tài đã xây dựng được các thành phần cốt lõi của một ứng dụng Chat P2P, đồng thời cung cấp các kết quả kiểm thử nhằm đánh giá một phần khả năng hoạt động, tính đúng đắn và hiệu năng của hệ thống.

## 5.2. Đánh giá mức độ đạt được mục tiêu

Các tiêu chí đánh giá tập trung vào khả năng phát hiện Peer, thiết lập kết nối TCP, trao đổi tin nhắn, truyền tập tin, bảo vệ dữ liệu và duy trì khả năng hoạt động của giao diện.

**Bảng 5.1. Đánh giá mức độ thực hiện các mục tiêu của đề tài**

| Mục tiêu | Kết quả triển khai | Mức độ đánh giá |
|---|---|---|
| Phát hiện Peer trong LAN | Đã xây dựng UDP Discovery, beacon và cơ chế theo dõi trạng thái Peer | Đã triển khai; cần đối chiếu thêm kết quả kiểm thử LAN thực tế |
| Thiết lập kết nối TCP | Đã xây dựng TCP Sender, Listener và cơ chế thiết lập kết nối | Đã triển khai; có kịch bản kiểm thử kết nối |
| Gửi và nhận tin nhắn | Đã tích hợp chức năng Chat vào GUI và xử lý văn bản Unicode | Đã triển khai; có kiểm thử thành phần và minh chứng giao diện |
| Emoji, Reply và Forward | Đã xây dựng thành phần giao diện và metadata hỗ trợ | Đã triển khai; có kiểm thử giao thức và các thành phần liên quan |
| Truyền tập tin | Đã xây dựng cơ chế Chunking, quản lý tác vụ, lưu tệp tạm và hủy truyền | Đã triển khai; cần phân biệt kết quả phía gửi và phía nhận |
| Kiểm tra tính toàn vẹn dữ liệu | Đã sử dụng SHA-256 trong xử lý truyền tập tin | Đã triển khai; có kết quả kiểm thử trong phạm vi tương ứng |
| Bảo mật dữ liệu | Đã xây dựng các thành phần RSA-2048, AES-256-GCM và quản lý khóa phiên | Đã triển khai; phạm vi tích hợp và bảo vệ dữ liệu còn giới hạn |
| Giao diện đồ họa | Đã xây dựng giao diện PyQt6 và tích hợp các chức năng chính | Đã triển khai; có kiểm thử widget và minh chứng giao diện |

Từ những kết quả trên, có thể nhận định rằng nhóm đã thực hiện được phần lớn nội dung xây dựng theo phạm vi đề tài, hình thành ứng dụng có các thành phần chức năng chính và xây dựng cơ sở kiểm thử phục vụ đánh giá hệ thống.

Mức độ ổn định và khả năng đáp ứng trong môi trường sử dụng thực tế vẫn cần được tiếp tục xác nhận bằng các kịch bản kiểm thử tích hợp trên nhiều thiết bị và điều kiện mạng khác nhau.

## 5.3. Hạn chế của hệ thống

### 5.3.1. Giới hạn phạm vi mạng

Hệ thống tập trung triển khai trong môi trường mạng LAN, sử dụng UDP Broadcast để hỗ trợ tự động phát hiện các Peer.

Do đặc điểm của Broadcast, khả năng phát hiện Peer phụ thuộc vào cấu hình mạng, chính sách tường lửa và phạm vi truyền thông của mạng cục bộ.

Ứng dụng chưa triển khai đầy đủ cơ chế phát hiện và kết nối Peer qua Internet hoặc hỗ trợ những trường hợp thiết bị nằm sau NAT và thuộc các mạng khác nhau.

Vì vậy, phạm vi kết nối hiện tại phù hợp chủ yếu với mục tiêu nghiên cứu và xây dựng ứng dụng giao tiếp trong mạng LAN.

### 5.3.2. Giới hạn trong quản lý thông điệp

Trong luồng GUI hiện tại, nội dung cuộc trò chuyện được quản lý chủ yếu thông qua các đối tượng trong bộ nhớ.

Hệ thống chưa thể hiện cơ chế lưu trữ lịch sử hội thoại bền vững bằng cơ sở dữ liệu. Do đó, nội dung trò chuyện có thể không được bảo toàn sau khi ứng dụng kết thúc và khởi chạy lại.

Bên cạnh đó, thao tác gửi dữ liệu qua TCP thành công không đồng nghĩa Peer nhận đã xử lý, hiển thị hoặc người dùng đã đọc tin nhắn.

Chức năng Reply và Forward được xây dựng dựa trên metadata của thông điệp Chat, hỗ trợ các thao tác tương tác cơ bản nhưng chưa cung cấp cơ chế quản lý toàn bộ chuỗi tham chiếu và nguồn gốc của những lần chuyển tiếp.

Ngoài ra, mã nguồn hiện còn tồn tại các nhóm API giao thức với cấu trúc đóng khung khác nhau. Mặc dù các nhóm API có thể phục vụ những luồng xử lý riêng, sự khác biệt này làm tăng yêu cầu về kiểm soát tính tương thích khi tích hợp và bảo trì.

### 5.3.3. Giới hạn của cơ chế truyền tập tin

Hệ thống đã triển khai cơ chế chia tập tin thành chunk, theo dõi tiến độ và hỗ trợ kiểm tra tính toàn vẹn dữ liệu.

Tuy nhiên, khả năng tiếp tục truyền từ vị trí gián đoạn (Resume Transfer) chưa được xác nhận hoàn chỉnh trong luồng GUI.

Trong luồng truyền file sử dụng `FileSenderThread`, trạng thái hoàn tất phía gửi được xác định sau khi worker hoàn thành quá trình gửi dữ liệu. Điều này chưa đồng nghĩa phía nhận đã kiểm tra và lưu tập tin thành công.

Do đó, việc xác nhận hoàn tất ở tầng ứng dụng cần được hoàn thiện để phản ánh chính xác trạng thái truyền tập tin tại cả hai Peer.

Ngoài ra, khả năng xử lý tệp rỗng, các lỗi phát sinh khi mất kết nối và việc phục hồi tác vụ trong những điều kiện mạng không ổn định vẫn là các nội dung cần tiếp tục kiểm chứng.

### 5.3.4. Giới hạn về bảo mật

Hệ thống đã xây dựng các thành phần bảo mật sử dụng RSA-2048 và AES-256-GCM nhằm hỗ trợ bảo vệ dữ liệu trao đổi trực tiếp giữa các Peer.

Tuy nhiên, phạm vi mã hóa phụ thuộc vào từng luồng xử lý và trạng thái thiết lập khóa phiên.

Trong luồng giao tiếp của GUI, nội dung tin nhắn và các chunk dữ liệu có thể được mã hóa nhưng JSON Header không được bảo vệ tính bí mật toàn phần.

Đặc biệt, metadata Reply có thể chứa nội dung trích dẫn từ tin nhắn gốc dưới dạng bản rõ, làm phát sinh giới hạn trong việc bảo vệ thông tin liên quan đến cuộc trò chuyện.

Bên cạnh đó, việc trao đổi khóa công khai chưa mặc nhiên bảo đảm xác thực danh tính Peer nếu không có cơ chế xác minh khóa đáng tin cậy.

Mặc dù mã nguồn đã có các thành phần hỗ trợ kiểm tra và xử lý một số trường hợp dữ liệu không hợp lệ, hệ thống chưa thể được xem là một giải pháp truyền thông đầu cuối đã được kiểm chứng toàn diện về bảo mật.

### 5.3.5. Giới hạn về hiệu năng và kiểm thử

Các kết quả benchmark được ghi nhận trong repository được thực hiện trên cùng một máy tính thông qua kết nối loopback.

Điều kiện này chưa phản ánh đầy đủ ảnh hưởng của môi trường LAN thực tế, bao gồm độ trễ mạng, giới hạn băng thông, nhiễu kết nối và sự khác biệt về cấu hình phần cứng giữa các thiết bị.

Ngoài ra, chương trình benchmark sử dụng máy chủ và các tiến trình Peer thử nghiệm riêng, chưa phải phép đo trực tiếp toàn bộ ứng dụng GUI.

Kết quả 26 bài kiểm thử tự động đạt yêu cầu cũng chỉ phản ánh các kịch bản đã được thực thi trong phiên kiểm thử tương ứng, không đại diện cho toàn bộ test suite hoặc mọi tình huống vận hành của hệ thống.

Vì vậy, ứng dụng cần được tiếp tục kiểm thử tích hợp trên nhiều thiết bị, nhiều cấu hình mạng và những tình huống sử dụng đồng thời để đánh giá toàn diện hơn về độ ổn định và hiệu năng thực tế.

## 5.4. Hướng phát triển trong tương lai

Trên cơ sở kết quả đã xây dựng và những hạn chế được xác định, hệ thống có thể được tiếp tục hoàn thiện theo các hướng phát triển sau.

### 5.4.1. Mở rộng phạm vi kết nối

Một hướng phát triển là bổ sung cơ chế hỗ trợ các Peer kết nối và trao đổi dữ liệu khi không nằm trong cùng một mạng LAN.

Hệ thống có thể nghiên cứu và triển khai các kỹ thuật NAT Traversal hoặc cơ chế hỗ trợ thiết lập kết nối phù hợp để mở rộng phạm vi giao tiếp giữa các thiết bị.

Bên cạnh đó, việc cải tiến cơ chế phát hiện Peer có thể giúp ứng dụng hoạt động trong nhiều môi trường mạng hơn thay vì phụ thuộc chủ yếu vào UDP Broadcast.

### 5.4.2. Hoàn thiện quản lý tin nhắn và lịch sử hội thoại

Hệ thống có thể bổ sung cơ sở dữ liệu cục bộ để lưu trữ lịch sử trò chuyện, cho phép người dùng truy xuất lại nội dung sau khi khởi chạy lại ứng dụng.

Việc xây dựng cơ chế xác nhận ở tầng ứng dụng cũng có thể giúp phân biệt các trạng thái gửi thành công, Peer đã tiếp nhận và người dùng đã đọc tin nhắn.

Đối với Reply và Forward, hệ thống có thể mở rộng khả năng quản lý quan hệ giữa các thông điệp, hỗ trợ truy xuất tin nhắn gốc và theo dõi nguồn gốc của nội dung được chuyển tiếp.

Ngoài ra, cần xem xét chuẩn hóa giao thức truyền thông để giảm sự khác biệt giữa các nhóm API và cải thiện khả năng tích hợp giữa những thành phần trong hệ thống.

### 5.4.3. Nâng cao khả năng truyền tập tin

Đối với chức năng truyền tập tin, một hướng phát triển quan trọng là bổ sung cơ chế tiếp tục truyền dữ liệu từ vị trí gián đoạn (Resume Transfer).

Hệ thống có thể xây dựng cơ chế xác nhận hoàn tất lưu trữ từ phía nhận, giúp phản ánh chính xác kết quả truyền dữ liệu thay vì chỉ dựa trên trạng thái hoàn thành của thao tác gửi.

Bên cạnh đó, ứng dụng có thể cải thiện việc quản lý hàng đợi, tối ưu kích thước chunk và tăng khả năng điều phối nhiều tác vụ truyền tập tin đồng thời.

Các cải tiến cần được kiểm thử trong điều kiện mạng không ổn định để đánh giá hiệu quả thực tế.

### 5.4.4. Tăng cường cơ chế bảo mật

Một hướng phát triển quan trọng là hoàn thiện cơ chế xác thực khóa công khai và quản lý danh tính giữa các Peer.

Hệ thống có thể nghiên cứu các biện pháp xác minh fingerprint hoặc cơ chế tin cậy phù hợp để hạn chế nguy cơ tấn công trung gian.

Đối với dữ liệu trao đổi, cần mở rộng phạm vi bảo vệ sang những metadata có thể chứa thông tin nhạy cảm, đặc biệt là nội dung trích dẫn trong chức năng Reply.

Ngoài ra, việc thống nhất cơ chế trao đổi khóa, quản lý vòng đời khóa phiên và xử lý các trạng thái mã hóa có thể giúp hạn chế sự khác biệt giữa những module bảo mật hiện có.

Những thay đổi liên quan đến bảo mật cần được đánh giá bằng các bài kiểm thử chuyên biệt trước khi áp dụng trong môi trường sử dụng thực tế.

### 5.4.5. Nâng cao trải nghiệm người dùng và khả năng vận hành

Giao diện ứng dụng có thể được mở rộng với những chức năng như tìm kiếm tin nhắn, lưu trữ và quản lý lịch sử truyền tập tin, thông báo trạng thái kết nối và tùy chỉnh giao diện.

Bên cạnh đó, nhóm có thể nghiên cứu đóng gói ứng dụng thành chương trình thực thi hoặc bộ cài đặt để người dùng không cần trực tiếp thiết lập môi trường Python và các thư viện phụ thuộc.

Việc bổ sung hướng dẫn sử dụng, cơ chế quản lý cấu hình nhất quán và hệ thống ghi nhận lỗi cũng góp phần nâng cao khả năng vận hành và bảo trì sản phẩm.

Ngoài ra, nhóm có thể xây dựng quy trình kiểm thử tích hợp tự động, kết hợp kiểm thử trên nhiều thiết bị và trong những điều kiện mạng khác nhau để nâng cao độ tin cậy của hệ thống.

## Kết luận chương

Thông qua quá trình nghiên cứu và triển khai, nhóm đã vận dụng kiến thức về lập trình mạng, TCP/UDP Socket, cơ chế đóng khung dữ liệu, xử lý đa luồng và bảo mật để xây dựng các thành phần chính của một ứng dụng giao tiếp ngang hàng trong mạng LAN.

Các kết quả kiểm thử tự động và benchmark cung cấp minh chứng cho khả năng hoạt động của những thành phần được kiểm tra trong phạm vi thử nghiệm. Tuy nhiên, việc đánh giá toàn diện mức độ ổn định và hiệu năng của ứng dụng vẫn cần dựa trên kết quả kiểm thử tích hợp trong môi trường sử dụng thực tế.
