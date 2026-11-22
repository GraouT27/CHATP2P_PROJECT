# CHƯƠNG 3: PHÂN TÍCH VÀ THIẾT KẾ HỆ THỐNG

## 3.1. Kiến trúc tổng thể hệ thống P2P

### 3.1.1. Mô hình hoạt động P2P

Ứng dụng được xây dựng dựa trên mô hình mạng ngang hàng (Peer-to-Peer – P2P), trong đó mỗi thiết bị tham gia mạng vừa có thể đóng vai trò là bên gửi, vừa có thể đóng vai trò là bên nhận dữ liệu. Các Peer giao tiếp trực tiếp với nhau thông qua kết nối mạng, không cần một máy chủ trung tâm đứng ra tiếp nhận và chuyển tiếp toàn bộ thông điệp.

Trong mô hình này, mỗi Peer có thể thực hiện các chức năng chính như phát hiện những Peer khác trong mạng LAN, tiếp nhận yêu cầu kết nối, chủ động thiết lập kết nối đến Peer đích và trao đổi dữ liệu thông qua giao thức TCP.

Để hỗ trợ quá trình phát hiện và giao tiếp giữa các thiết bị, hệ thống sử dụng kết hợp hai giao thức mạng:
- UDP Broadcast: Được sử dụng để gửi thông tin nhận diện Peer trong mạng LAN, giúp các thiết bị có thể phát hiện lẫn nhau mà không cần nhập thủ công địa chỉ IP.
- TCP: Được sử dụng để thiết lập kết nối trực tiếp giữa các Peer và truyền dữ liệu, bảo đảm dữ liệu được truyền theo cơ chế tin cậy của TCP.
Mỗi Peer có một định danh riêng (peer_id) cùng thông tin địa chỉ IP và cổng TCP đang lắng nghe. Khi phát hiện một Peer mới, hệ thống lưu thông tin của Peer đó để phục vụ việc lựa chọn thiết bị đích và thực hiện giao tiếp.

Như vậy, mô hình P2P cho phép các thiết bị giao tiếp trực tiếp với nhau, đồng thời kết hợp UDP Broadcast để phát hiện Peer và TCP để trao đổi dữ liệu.

### 3.1.2. Các thành phần chính của hệ thống

Hệ thống được tổ chức thành các thành phần chính sau:

1. Thành phần quản lý cấu hình (Configuration)
Thành phần này chịu trách nhiệm cung cấp các thông tin cấu hình phục vụ hoạt động mạng, chẳng hạn như Peer ID, địa chỉ lắng nghe và các cổng giao tiếp. Việc tách thông tin cấu hình khỏi mã nguồn giúp hệ thống thuận tiện hơn khi thay đổi thông số trong quá trình triển khai và kiểm thử.

2. Thành phần phát hiện Peer (Peer Discovery)
Thành phần này sử dụng UDP Broadcast để quảng bá thông tin của Peer trong mạng LAN. Đồng thời, nó lắng nghe các gói tin Discovery được gửi từ những thiết bị khác, kiểm tra tính hợp lệ của dữ liệu nhận được và chuyển thông tin Peer mới phát hiện đến thành phần quản lý Peer.

3. Thành phần quản lý Peer (Peer Manager)
Thành phần này lưu trữ và quản lý danh sách các Peer đã được phát hiện, bao gồm Peer ID, địa chỉ IP, cổng TCP, thời điểm phát hiện và thời điểm nhận diện gần nhất. Các thao tác truy cập dữ liệu được bảo vệ bằng cơ chế Lock nhằm hạn chế xung đột khi nhiều luồng cùng truy cập danh sách Peer.

4. Thành phần kết nối và giao tiếp TCP
Thành phần này đảm nhiệm việc mở cổng lắng nghe kết nối từ các Peer khác và thực hiện kết nối đến Peer đích.

5. Thành phần xử lý giao thức truyền thông
Thành phần này chịu trách nhiệm tổ chức dữ liệu theo định dạng thống nhất trước khi truyền qua mạng, đồng thời hỗ trợ quá trình tiếp nhận và xử lý thông điệp. Việc chuẩn hóa cấu trúc dữ liệu giúp các Peer có thể hiểu và xử lý thông tin được trao đổi.

6. Thành phần bảo mật và truyền file
Đây là các thành phần phục vụ những chức năng mở rộng của ứng dụng, bao gồm xử lý bảo mật thông tin trao đổi và hỗ trợ truyền nhận tập tin giữa các Peer. Các chức năng cụ thể sẽ được trình bày trong những mục thiết kế tương ứng của chương này.

7. Thành phần giao diện người dùng (GUI)
Giao diện người dùng được xây dựng bằng PyQt6 trong mã nguồn app.py đã được cung cấp. Giao diện dự kiến hỗ trợ hiển thị danh sách Peer, khu vực trò chuyện, nhập và gửi tin nhắn, lựa chọn biểu tượng cảm xúc, trả lời, chuyển tiếp tin nhắn và gửi tập tin.

### 3.1.3. Cấu trúc module và vai trò của từng thành phần

| Module | Vai trò |
|---|---|
| config/ | lưu trữ và tải thông tin cấu hình mạng |
| core/ | Chứa các module điều phối hoạt động chính, bao gồm chương trình khởi chạy, TCP Server và TCP Client. |
| p2p_node/ | Chứa các module liên quan đến hoạt động của Peer như phát hiện Peer, quản lý Peer, xử lý thông điệp và truyền file. |
| security/ | Chứa các module phục vụ chức năng bảo mật và trao đổi khóa. |
| shared/ | Chứa các thành phần dùng chung giữa các module, trong đó có module định nghĩa giao thức truyền thông. |
| CODE/ui/ | Chứa mã nguồn giao diện người dùng |

Một số module quan trọng được xác định như sau:

- `config/config_loader.py`: Đọc thông tin cấu hình mạng từ file cấu hình, cung cấp các thông số cần thiết cho những thành phần khác.

- `core/main.py`: Là điểm khởi chạy của chương trình dạng dòng lệnh trong mã nguồn đã kiểm tra. Module này khởi tạo PeerManager, khởi động các luồng TCP Server, UDP Discovery Listener và UDP Broadcast. Sau đó, chương trình hiển thị danh sách Peer đã phát hiện và cho phép người dùng nhập Peer ID để lựa chọn thiết bị cần gửi tin nhắn.

- `core/server.py`: Thực hiện chức năng TCP Server, tiếp nhận kết nối, nhận và kiểm tra thông điệp từ Client, sau đó gửi phản hồi. Phiên bản hiện tại xử lý lần lượt từng kết nối.

- `core/client.py`: Thực hiện chức năng TCP Client, lấy thông tin IP và cổng TCP từ PeerManager, thiết lập kết nối đến Peer đích, gửi thông điệp và nhận phản hồi.

- `p2p_node/discovery.py`: Thực hiện gửi và lắng nghe các gói tin UDP Broadcast. Thông tin Discovery bao gồm loại thông điệp, Peer ID và cổng TCP của Peer gửi.

- `p2p_node/peer_manager.py`: Quản lý danh sách Peer bằng cấu trúc từ điển kết hợp với threading.Lock, hỗ trợ thêm, cập nhật, xóa và truy xuất thông tin Peer.

- `p2p_node/listener.py`: Cung cấp lớp PeerListener để tiếp nhận kết nối TCP và tạo luồng xử lý riêng cho từng Client. Module này sử dụng FileMessageCallbacks để chuyển thông điệp đến thành phần xử lý tương ứng.

- `shared/protocol.py`: Đảm nhiệm việc xây dựng, mã hóa và tiếp nhận cấu trúc thông điệp dùng chung giữa các Peer.

Ngoài ra, mã nguồn giao diện app.py thể hiện một hướng tổ chức giao diện riêng với lớp MainWindow, sử dụng các thành phần như PeerListWidget, MessageHandler, P2PListener, PeerDiscovery và TransferManager. 

### 3.1.4. Sơ đồ kiến trúc tổng thể

## 3.2. Thiết kế kết nối và phát hiện Peer

Trong hệ thống P2P, mỗi thiết bị tham gia mạng được xem là một Peer và có khả năng giao tiếp trực tiếp với các Peer khác mà không cần thông qua máy chủ trung tâm. Để thực hiện việc này, hệ thống sử dụng UDP Broadcast để phát hiện các Peer trong mạng LAN, kết hợp với TCP để thiết lập kết nối và trao đổi dữ liệu.

Quá trình kết nối được chia thành các thành phần chính gồm: phát hiện Peer, quản lý thông tin Peer, thiết lập kết nối TCP và trao đổi khóa phục vụ giao tiếp an toàn.

### 3.2.1. Cơ chế phát hiện Peer bằng UDP Discovery

Hệ thống sử dụng UDP Broadcast để các thiết bị trong cùng mạng LAN có thể tự động thông báo sự hiện diện của mình và phát hiện các Peer khác.

Chức năng này được triển khai trong module p2p_node/discovery.py, gồm hai hoạt động chính:

a. Gửi thông điệp Discovery 

Phương thức send_discovery() tạo một thông điệp JSON chứa các thông tin:

| Trường | Ý nghĩa |
|---|---|
| `type` | loại thông điệp, có giá trị DISCOVERY |
| `peer_id` | định danh của Peer gửi thông điệp |
| `tcp_port` | cổng TCP mà Peer sử dụng để tiếp nhận kết nối |

Thông điệp sau khi được tạo sẽ chuyển thành dữ liệu bytes bằng UTF-8 và gửi đến địa chỉ Broadcast IPv4 255.255.255.255 thông qua UDP socket.

Cổng UDP Discovery được lấy từ cấu hình network.json thông qua thuộc tính discovery_port. Nếu không có giá trị cấu hình, chương trình sử dụng cổng mặc định 9999.

Trong chương trình chính, hoạt động Broadcast được thực hiện định kỳ thông qua hàm broadcast_loop(), với khoảng thời gian gửi giữa hai lần là 10 giây.

b. Lắng nghe và xử lý thông điệp Discovery

Phương thức listen_discovery() tạo UDP socket và liên kết với cổng Discovery để tiếp nhận thông điệp từ các Peer khác.

Khi nhận được dữ liệu, chương trình thực hiện các bước kiểm tra:

- Giải mã dữ liệu từ UTF-8 và chuyển đổi JSON.

- Kiểm tra dữ liệu nhận được có cấu trúc dictionary hay không.

- Kiểm tra peer_id là chuỗi không rỗng.

- Kiểm tra tcp_port là số nguyên nằm trong khoảng từ 1 đến 65535.

- Kiểm tra loại thông điệp có phải DISCOVERY hay không.

- Loại bỏ thông điệp do chính Peer hiện tại gửi đi dựa trên peer_id.

Nếu thông điệp hợp lệ, chương trình lấy địa chỉ IP của Peer gửi từ thông tin địa chỉ nguồn của UDP socket và chuyển các thông tin peer_id, IP, TCP Port đến PeerManager để cập nhật danh sách Peer.

Nhờ cơ chế này, các thiết bị trong cùng mạng LAN có thể tự động phát hiện nhau mà không cần nhập thủ công địa chỉ IP của từng thiết bị.

### 3.2.2. Quản lý danh sách Peer (Peer Manager)

Sau khi một Peer được phát hiện, thông tin của Peer được quản lý thông qua lớp PeerManager trong module p2p_node/peer_manager.py.

PeerManager sử dụng cấu trúc dictionary để lưu trữ thông tin của từng Peer, trong đó peer_id được sử dụng làm khóa định danh.

Các thông tin được lưu trữ gồm:
| Thuộc tính | Ý nghĩa |
|---|---|
| ip | địa chỉ IP của Peer |
| tcp_port | cổng TCP của Peer |
| discovery_at | thời điểm Peer được phát hiện lần đầu |
| last_seen | thời điểm gần nhất nhận được thông tin Discovery từ Peer | 

PeerManager cung cấp các phương thức quản lý chính:

- `add_peer()`: Thêm Peer mới vào danh sách hoặc cập nhật thông tin nếu Peer đã tồn tại.

- `remove_peer()`: Xóa Peer khỏi danh sách quản lý.

- `get_peer()`: Lấy thông tin của một Peer dựa trên peer_id.

- `get_all_peers()`: Trả về danh sách thông tin của các Peer đã được phát hiện.

- `peer_count()`: Lấy số lượng Peer hiện có.

- `get_all_peer_ids()`: Lấy danh sách định danh của các Peer.

Để đảm bảo an toàn khi nhiều luồng cùng truy cập dữ liệu, PeerManager sử dụng threading.Lock để đồng bộ các thao tác đọc và ghi lên danh sách Peer. Ngoài ra, các phương thức truy xuất thông tin trả về bản sao dữ liệu nhằm hạn chế việc thay đổi trực tiếp cấu trúc dữ liệu nội bộ.

Việc quản lý tập trung thông tin Peer giúp các thành phần khác của hệ thống có thể tra cứu địa chỉ IP và TCP Port của Peer đích khi cần thiết lập kết nối.

Lưu ý, danh sách do PeerManager quản lý là danh sách các Peer đã được phát hiện thông qua UDP Discovery, không đồng nghĩa tất cả các Peer trong danh sách đều đang duy trì kết nối TCP.

### 3.2.3. Thiết lập kết nối TCP giữa các Peer

Sau khi phát hiện được Peer cần liên lạc, hệ thống sử dụng TCP để thiết lập kết nối trực tiếp và trao đổi dữ liệu.

Quá trình kết nối gồm các bước:

1. Peer khởi tạo yêu cầu lựa chọn Peer đích thông qua peer_id.

2. Client truy vấn Peer Manager để lấy địa chỉ IP và cổng TCP của Peer đích.

3. lient tạo TCP socket và thực hiện kết nối đến địa chỉ nhận được.
                                               
4. Sau khi kết nối thành công, hai bên có thể trao đổi thông điệp thông qua socket TCP.

5. bKhi kết thúc trao đổi hoặc xảy ra lỗi kết nối, socket được đóng và giải phóng tài nguyên.

Trong mã nguồn hiện tại, core/client.py thực hiện vai trò Client. Module này lấy thông tin Peer đích từ Peer Manager, sử dụng TCP socket với thời gian chờ kết nối 10 giây và xử lý các trường hợp như kết nối bị từ chối, hết thời gian chờ hoặc lỗi socket.

Ở phía nhận, core/server.py tạo TCP socket, thiết lập địa chỉ lắng nghe theo cấu hình, gọi listen() và chờ kết nối thông qua accept(). Server tiếp nhận kết nối và xử lý các thông điệp nhận được. Phiên bản này xử lý lần lượt từng kết nối, sau khi kết nối hiện tại kết thúc mới quay lại chờ kết nối tiếp theo.

Ngoài ra, dự án còn có module p2p_node/listener.py với lớp PeerListener, được thiết kế theo hướng tạo một luồng xử lý riêng cho mỗi kết nối TCP được chấp nhận. Tuy nhiên, module này cần được phân biệt với luồng khởi chạy hiện tại trong core/main.py, vì core/main.py đang khởi chạy core/server.py.

### 3.2.4. Quy trình trao đổi khóa (Key Exchange)

Để bảo vệ dữ liệu trao đổi giữa hai Peer, hệ thống xây dựng cơ chế bắt tay (Handshake) nhằm trao đổi khóa và thiết lập khóa phiên trước khi truyền dữ liệu được mã hóa.

Cơ chế bảo mật sử dụng:

- RSA-2048 để tạo cặp khóa và mã hóa khóa phiên khi trao đổi.

- RSA-OAEP với SHA-256 để bảo vệ khóa phiên trong quá trình gửi.

- AES-256-GCM để mã hóa và xác thực dữ liệu trao đổi.

- HKDF-SHA256 để tạo các khóa mã hóa riêng theo từng chiều truyền dữ liệu.

a. Khởi tạo cặp khóa RSA

Mỗi Peer tạo một cặp khóa RSA-2048 động trong quá trình chạy chương trình. Cặp khóa gồm:

- Khóa công khai (Public Key): Có thể gửi cho Peer khác trong quá trình bắt tay.

- Khóa riêng (Private Key): Được giữ trong bộ nhớ của đối tượng KeyPair, không cung cấp chức năng xuất khóa riêng ra file.

Khóa công khai được chuyển đổi sang định dạng PEM để trao đổi. Ngoài ra, hệ thống tạo dấu vân tay (Fingerprint) bằng cách tính SHA-256 trên biểu diễn DER của khóa công khai. Fingerprint được sử dụng để nhận diện và hỗ trợ người dùng đối chiếu khóa của Peer.

b. Quy trình bắt tay giữa hai Peer

Quy trình bắt tay được chia thành hai vai trò: Initiator (Peer chủ động kết nối) và Responder (Peer tiếp nhận kết nối).

Bước 1: Initiator gửi khóa công khai

Initiator gửi thông điệp KEY_EXCHANGE với hành động PUBLIC_KEY, chứa các thông tin:

- Thuật toán: RSA-2048.

- key_id: Định danh rút gọn của khóa công khai.

- public_key: Khóa công khai ở định dạng PEM.

Bước 2: Responder gửi khóa công khai

Responder nhận và kiểm tra thông điệp, sau đó gửi lại khóa công khai của mình theo cùng cấu trúc.

Bước 3: Kiểm tra khóa công khai của Peer

Hai bên tính Fingerprint từ khóa công khai nhận được. Module Handshake hỗ trợ sử dụng hàm confirm_peer để xác nhận khóa của Peer. Nếu hàm xác nhận trả về giá trị từ chối, quá trình bắt tay sẽ thất bại.

Bước 4: Tạo và trao đổi khóa phiên

Initiator tạo khóa phiên ngẫu nhiên K có độ dài 32 byte (256 bit). Khóa này được mã hóa bằng khóa công khai của Responder thông qua RSA-OAEP-SHA256, sau đó được gửi trong thông điệp KEY_EXCHANGE với hành động SESSION_KEY.

Responder sử dụng khóa riêng RSA tương ứng để giải mã và thu được khóa phiên K.

Bước 5: Sinh khóa theo từng chiều truyền

Sau khi có khóa phiên, hai bên sử dụng HKDF-SHA256 để dẫn xuất hai khóa AES-256 riêng biệt:

- Khóa a2b: Dùng cho chiều truyền từ Initiator đến Responder.

- Khóa b2a: Dùng cho chiều truyền từ Responder đến Initiator.

Salt được tạo bằng cách tính SHA-256 trên chuỗi nối khóa công khai của Initiator và khóa công khai của Responder theo đúng thứ tự.

Việc tách khóa theo chiều truyền giúp mỗi chiều sử dụng một khóa mã hóa riêng, tránh sử dụng chung một khóa cho cả gửi và nhận.

Bước 6: Xác nhận hoàn tất bắt tay

Sau khi khởi tạo phiên mã hóa, Responder gửi thông điệp KEY_CONFIRM được mã hóa bằng AES-256-GCM. Initiator giải mã và kiểm tra thông điệp xác nhận. Nếu quá trình kiểm tra thành công, hai bên có thể sử dụng khóa phiên để trao đổi dữ liệu an toàn.

Kết quả bắt tay được lưu trong đối tượng HandshakeResult, bao gồm:

- session: Đối tượng quản lý phiên mã hóa.

- session_id: Định danh phiên.

- peer_id: Định danh Peer đối tác.

- peer_fingerprint: Fingerprint của khóa công khai Peer đối tác.

- peer_key_id: Định danh khóa công khai Peer đối tác.

c. Mã hóa và giải mã dữ liệu bằng AES-256-GCM

Sau khi bắt tay thành công, hệ thống sử dụng AES-256-GCM để mã hóa và xác thực dữ liệu trước khi gửi qua TCP.

Mỗi khung dữ liệu mã hóa có cấu trúc:

| seq (8 byte) | nonce (12 byte) | ciphertext | tag (16 byte) |

Trong đó:

- seq: Số thứ tự của gói tin, được biểu diễn bằng 8 byte.

- nonce: Giá trị ngẫu nhiên có độ dài 12 byte.

- ciphertext: Dữ liệu sau khi mã hóa.

- tag: Thẻ xác thực có độ dài 16 byte, được AES-GCM tạo ra để kiểm tra tính toàn vẹn và xác thực dữ liệu.

Trường seq được sử dụng làm AAD (Additional Authenticated Data), tức dữ liệu bổ sung được xác thực nhưng không mã hóa. Khi nhận dữ liệu, hệ thống kiểm tra tag và số thứ tự gói tin. Nếu dữ liệu bị thay đổi hoặc số thứ tự không hợp lệ do gói tin cũ được gửi lại, quá trình giải mã sẽ bị từ chối.

Hệ thống sử dụng hai bộ đếm riêng cho chiều gửi và chiều nhận. Việc quản lý số thứ tự giúp phát hiện các gói tin bị phát lại (Replay).

d. Mã hóa riêng cho từng chunk khi truyền file

Ngoài mã hóa dữ liệu theo từng khung thông thường, module crypto.py còn cung cấp lớp ChunkCrypto để mã hóa và giải mã từng chunk của file.

Khóa mã hóa file được dẫn xuất từ khóa phiên theo chiều truyền và transfer_id thông qua HKDF-SHA256. Mỗi chunk sử dụng nonce được tạo từ chỉ số chunk và AAD chứa chỉ số chunk cùng tổng số chunk.

Cơ chế này có các đặc điểm:

- Mỗi lần truyền file có khóa riêng được dẫn xuất theo transfer_id.

- Có thể giải mã các chunk theo thứ tự bất kỳ, phù hợp với thiết kế truyền file đa luồng.

- Phát hiện chunk bị thay đổi, bị tráo đổi vị trí hoặc thuộc về một lần truyền khác.

- Mỗi transfer_id phải duy nhất trong cùng một phiên để tránh sử dụng lại nonce với cùng khóa.

e. Một số nguyên tắc bảo mật

Hệ thống áp dụng các nguyên tắc sau:

- Khóa riêng RSA được giữ trong bộ nhớ, không ghi trực tiếp ra file hoặc đưa vào mã nguồn.

- Khóa phiên được tạo ngẫu nhiên cho từng lần thiết lập phiên.

- Không ghi log khóa bí mật, plaintext hoặc toàn bộ ciphertext.

- Các hàm bắt tay có thời gian chờ mặc định 5 giây và khôi phục timeout ban đầu của socket sau khi hoàn tất.

- Các hàm bắt tay là hàm chặn (blocking), do đó cần được thực thi trong luồng riêng thay vì luồng giao diện.

- Khi nhiều luồng cùng gửi dữ liệu qua một phiên, thao tác mã hóa và gửi dữ liệu cần được đồng bộ trong cùng một khóa khóa (lock) bên ngoài để bảo đảm thứ tự gói tin.

### 3.2.5. Tổng kết và sơ đồ quy trình kết nối và phát hiện Peer

Quy trình kết nối giữa hai Peer được tổ chức theo trình tự:

1. Mỗi Peer gửi UDP Broadcast định kỳ để thông báo sự hiện diện trên mạng.

2. Peer nhận thông điệp Discovery, kiểm tra dữ liệu và cập nhật thông tin vào Peer Manager.

3. Người dùng lựa chọn Peer đích từ danh sách Peer đã phát hiện.

4. Client sử dụng địa chỉ IP và cổng TCP được lưu trong Peer Manager để thiết lập kết nối.

5. Hai Peer thực hiện quá trình bắt tay RSA để trao đổi khóa phiên.

6. Hai bên dẫn xuất khóa AES-256 theo từng chiều và xác nhận phiên bảo mật.

7. Sau khi hoàn tất, dữ liệu có thể được mã hóa, gửi và giải mã thông qua phiên bảo mật đã thiết lập.

## 3.3. Thiết kế giao thức truyền thông

Giao thức truyền thông được xây dựng nhằm thống nhất cấu trúc dữ liệu trao đổi giữa các Peer trong hệ thống P2P. Mỗi thông điệp được tổ chức theo cấu trúc JSON gồm hai thành phần chính là Header và Payload. Trong đó, Header chứa thông tin định danh và điều khiển thông điệp, còn Payload chứa dữ liệu tương ứng với từng loại thông điệp.

Đối với kết nối TCP, hệ thống sử dụng cơ chế Length-Prefix Framing để xác định ranh giới giữa các thông điệp, kết hợp với JSON để biểu diễn dữ liệu. Cách tổ chức này giúp các Peer có thể trao đổi nhiều loại thông điệp trên cùng một kết nối TCP và hỗ trợ việc kiểm tra tính hợp lệ của dữ liệu trước khi xử lý.


### 3.3.1. Cơ chế đóng gói và phân tách dữ liệu (Length-Prefix Framing)

Mỗi thông điệp được thiết kế theo cấu trúc gồm hai thành phần:

Header: Chứa các thông tin quản lý thông điệp như mã định danh, loại thông điệp, Peer gửi, Peer nhận và thời điểm tạo.

Payload: Chứa nội dung dữ liệu cần truyền, được tổ chức tùy theo loại thông điệp.

Cấu trúc tổng quát:

```json
{
    "header": {
        "message_id": "UUID",
        "message_type": "TEXT",
        "sender_id": "peer_A",
        "receiver_id": "peer_B",
        "timestamp": "2026-11-16T10:00:00+00:00"
    },
    "payload": {
        "text": "Xin chào!"
    }
}
```

### 3.3.2. Cấu trúc thông điệp JSON Header/Payload

a. Header

Header chứa các trường thông tin cơ bản sau:

| Trường | Kiểu dữ liệu | Ý nghĩa |
|---|---|---|
| `message_id` | string (UUID) | mã định danh duy nhất của thông điệp |
| `message_type` | string | xác định loại thông điệp |
| `sender_id` | string | ID của Peer gửi |
| `receiver_id` | string | ID của Peer nhận |
| `timestamp` | string | thời điểm tạo thông điệp theo định dành ISO 8601, sử dụng UTC |

Các trường trong Header được kiểm tra để đảm bảo tồn tại và có giá trị chuỗi không rỗng. Riêng message_id phải có định dạng UUID hợp lệ và timestamp phải biểu diễn thời gian theo múi giờ UTC.

b. Payload

Payload chứa nội dung dữ liệu được truyền đi. Tùy theo message_type, cấu trúc Payload sẽ khác nhau.

Ví dụ đối với thông điệp văn bản:

```json 
{
    "text": "Xin chào!"
}
```

Đối với thông điệp trả lời:

```json
{
    "reply_to": "UUID_CUA_TIN_NHAN_GOC",
    "text": "Tôi đồng ý với ý kiến này."
}
```

Đối với thông điệp chuyển tiếp:

```json
{
    "forwarded_from": "peer_A",
    "original_message_id": "UUID_TIN_NHAN_GOC",
    "original_message_type": "TEXT",
    "original_payload": {
        "text": "Nội dung được chuyển tiếp"
    }
}
```

### 3.3.3. Cơ chế định danh thông điệp bằng UUID

Mỗi thông điệp được gán một mã định danh duy nhất thông qua UUID (Universally Unique Identifier). Mã này được tạo tự động khi khởi tạo thông điệp bằng hàm uuid.uuid4().

- Việc sử dụng UUID mang lại các lợi ích:

- Hạn chế trùng lặp mã định danh giữa các thông điệp.

- Phân biệt từng thông điệp trong quá trình trao đổi.

- Hỗ trợ xác định thông điệp gốc khi thực hiện chức năng Reply và Forward.

- Tạo cơ sở để theo dõi và quản lý các thông điệp trong hệ thống.

Đối với chức năng Reply, trường reply_to trong Payload lưu UUID của thông điệp được trả lời. Đối với chức năng Forward, hệ thống sử dụng original_message_id để lưu mã định danh của thông điệp gốc.

### 3.3.4. Cơ chế Lenghth-Prefix Framing

Trong TCP, dữ liệu được truyền dưới dạng luồng byte liên tục. TCP không tự xác định ranh giới giữa các thông điệp. Vì vậy, hệ thống sử dụng cơ chế Length-Prefix Framing để xác định chính xác kích thước dữ liệu của từng thông điệp.

Cấu trúc một khung dữ liệu:

```text
+----------------------+---------------------------+
| Length Prefix (4B)   | JSON Payload (N bytes)    |
+----------------------+---------------------------+
```

Trong đó:

- Length Prefix: Gồm 4 byte, biểu diễn độ dài của phần dữ liệu JSON.

- JSON Payload: Nội dung thông điệp sau khi được mã hóa thành chuỗi byte UTF-8.

- N: Số byte thực tế của dữ liệu JSON.

Hệ thống sử dụng struct.pack("!I", length) để đóng gói độ dài dữ liệu theo định dạng số nguyên 4 byte, sử dụng thứ tự byte Big-Endian (Network Byte Order).

Giới hạn kích thước một thông điệp được thiết lập thông qua hằng số MAX_MESSAGE_SIZE = 1024 * 1024, tương đương 1 MiB.

Quá trình nhận dữ liệu được thực hiện theo các bước:

1. Đọc chính xác 4 byte đầu tiên để xác định độ dài thông điệp.

2. Giải mã 4 byte thành số nguyên biểu diễn kích thước dữ liệu.

3. Kiểm tra độ dài có hợp lệ và không vượt quá giới hạn cho phép.

4. Đọc tiếp đúng số byte dữ liệu JSON tương ứng.

5. Giải mã dữ liệu và kiểm tra tính hợp lệ của thông điệp.

Hàm `recv_exact()` được sử dụng để đảm bảo nhận đủ số byte yêu cầu. Hàm này tiếp tục gọi `socket.recv()` cho đến khi nhận đủ dữ liệu; nếu kết nối bị đóng trước khi hoàn tất, hệ thống phát sinh ngoại lệ ConnectionError.

### 3.3.5. Mã hóa và giải mã dữ liệu JSON

Sau khi xây dựng cấu trúc Header và Payload, thông điệp được chuyển đổi sang định dạng JSON để thuận tiện cho việc trao đổi giữa các Peer.

Quá trình gửi:

1. Kiểm tra tính hợp lệ của thông điệp.

2. Chuyển đối tượng Python thành chuỗi JSON bằng json.dumps().

3. Sử dụng ensure_ascii=False để giữ nguyên các ký tự Unicode, bao gồm tiếng Việt.

4. Mã hóa chuỗi JSON thành byte theo chuẩn UTF-8.

5. Kiểm tra kích thước dữ liệu.

6. Length Prefix 4 byte vào phía trước dữ liệu JSON.

Quá trình nhận:

1. Nhận đủ dữ liệu JSON dựa trên Length Prefix.

2. Giải mã byte thành chuỗi UTF-8.

3. Chuyển chuỗi JSON thành đối tượng Python bằng json.loads().

4. Kiểm tra cấu trúc và tính hợp lệ của thông điệp trước khi chuyển sang bước xử lý tiếp theo.

Việc sử dụng JSON giúp dữ liệu có cấu trúc rõ ràng, dễ đọc, dễ kiểm tra và thuận tiện khi mở rộng các loại thông điệp.

### 3.3.6. Kiểm tra tính hợp lệ và phân phối thông điệp 

Để hạn chế dữ liệu không hợp lệ trong quá trình trao đổi, hệ thống thực hiện kiểm tra thông điệp trước khi xử lý. Chức năng kiểm tra được triển khai trong hàm validate_message().

Các nội dung kiểm tra chính gồm:

| Nội dung | Yêu cầu |
|---|---|
| Cấu trúc thông điệp | thông điệp phải là Dictionary |
| Header | phải tồn tại và chứa đầy đủ các trường bắt buộc |
| Message ID | phải là UUID hợp lệ |
| Timestamp | phải đúng định dạng thời gian và sử dụng UTC |
| Payload | phải tồn tại và có kiểu Dictionary |
| TEXT, EMOJI | trường dữ liệu tương ứng phải có kiểu string |
| REPLY | phải có UUID của tin nhắn gốc và nội dung trả lời hợp lệ | 
| FORWARD | phải có thông tin nguồn, UUID tin nhắn gốc, loại tin nhắn gốc và Payload tương ứng |
| FILE | phải sử dụng loại thông điệp theo dạng FILE_<ACTION> và trường action phải khớp với hậu tố của loại thông điệp |

Sau khi thông điệp được kiểm tra hợp lệ, module MessageHandler thực hiện phân phối thông điệp dựa trên trường message_type trong Header.

Cơ chế xử lý được tổ chức theo mô hình Callback:

- `register()`: Đăng ký hàm xử lý tương ứng với từng loại thông điệp.

- `handle_message()`: Kiểm tra thông điệp, xác định message_type và gọi Callback đã đăng ký.

- Callback: Chịu trách nhiệm xử lý nội dung và gửi phản hồi khi cần thiết.

MessageHandler không trực tiếp đọc dữ liệu từ Socket mà chỉ đảm nhiệm việc phân phối thông điệp đã được nhận đầy đủ. Cách tổ chức này giúp tách biệt quá trình nhận dữ liệu mạng với quá trình xử lý từng loại thông điệp.

Đối với truyền file, lớp FileMessageCallbacks trong p2p_node/handler2.py đăng ký các callback xử lý FILE_START, FILE_CHUNK và FILE_END. Các Callback tương ứng thực hiện khởi tạo file, ghi dữ liệu từng phần và hoàn tất quá trình lưu file. Khi xử lý thành công, hệ thống gửi FILE_ACK; khi phát sinh lỗi, hệ thống gửi FILE_ERROR.

### 3.3.7. Các loại thông điệp trong hệ thống 

Hệ thống sử dụng trường message_type để phân biệt mục đích và cách xử lý của từng thông điệp. Dựa trên thiết kế chức năng toàn hệ thống và các module đã cung cấp, các nhóm thông điệp được tổng hợp như sau:

| Nhóm chức năng | Message Type | Mục đích |
|---|---|---|
| Nhắn tin | TEXT | gửi nội dung văn bản giữa các Peer |
| Nhắn tin | EMOJI | gửi biểu tượng cảm xúc |
| Nhắn tin | REPLY | trả lời một thông điệp đã nhận |
| Nhắn tin | FORWARD | chuyển tiếp thông điệp gốc |
| Avatar | AVATAR_UPDATE | thông báo Peer đã cập nhật ảnh đại diện | 
| Truyền file | FILE_START | thông báo bắt đầu truyền file và gửi thông tin file |
| Truyền file | FILE_CHUNK | truyền từng phần dữ liệu của file |
| Truyền file | FILE_END | thông báo kết thúc quá trình gửi file |
| Truyền file | FILE_ACK | xác nhận quá trình nhận file hoàn tất |
| Truyền file | FILE_ERROR | thông báo lỗi trong quá trình truyền file |
| Trao đổi khóa | KEY_EXCHANGE | phục vụ quá trình trao đổi khóa giữa các Peer | 
| Xử lý kết nối | ERROR | thông báo lỗi phát sinh trong quá trình giao tiếp |
| Xử lý kết nối | DISCONNECT | thông báo ngắt kết nối giữa các Peer | 

a. Nhóm thông điệp nhắn tin

Các thông điệp TEXT, EMOJI, REPLY và FORWARD phục vụ chức năng trao đổi nội dung giữa các Peer. Mỗi loại thông điệp có cấu trúc Payload tương ứng với nội dung cần truyền. Trong đó, REPLY sử dụng trường reply_to để xác định thông điệp được trả lời, còn FORWARD sử dụng original_message_id để định danh thông điệp gốc.

b. Nhóm thông điệp Avatar

Thông điệp AVATAR_UPDATE được đề xuất để thông báo việc cập nhật ảnh đại diện của Peer. Payload có thể chứa các thông tin như:

| Trường | Ý nghĩa |
|---|---|
| avatar_id | mã định danh ảnh đại diện |
| transfer_id | mã định danh phiên truyền dữ liệu ảnh |
| file_name | tên file ảnh |
| file_size | kích thước dữ liệu ảnh |
| sha256 | giá trị kiểm tra tính toàn vẹn của ảnh |

Thông điệp AVATAR_UPDATE đảm nhiệm việc thông báo và cung cấp thông tin về ảnh đại diện, không trực tiếp chứa toàn bộ dữ liệu ảnh. Dữ liệu ảnh được truyền thông qua cơ chế truyền dữ liệu theo từng phần đã sử dụng cho chức năng truyền file.

c. Nhóm thông điệp truyền file và dữ liệu Avatar

Hệ thống sử dụng chung cơ chế truyền dữ liệu theo từng phần cho file thông thường và ảnh đại diện nhằm hạn chế việc xây dựng nhiều cơ chế truyền dữ liệu riêng biệt.

Để phân biệt loại dữ liệu đang được truyền, Payload của FILE_START được đề xuất bổ sung trường file_kind:

- FILE: Dữ liệu là file thông thường.

- AVATAR: Dữ liệu là ảnh đại diện.

```json
{
    "header": {
        "message_type": "FILE_START"
    },
    "payload": {
        "action": "START",
        "transfer_id": "UUID",
        "file_kind": "AVATAR",
        "file_name": "avatar.png",
        "file_size": 204800,
        "sha256": "HASH_VALUE"
    }
}
```
Với cách tổ chức này, hệ thống có thể tái sử dụng cơ chế truyền dữ liệu hiện có, đồng thời giúp phía nhận xác định mục đích sử dụng của dữ liệu sau khi hoàn tất quá trình truyền.

d. Nhóm thông điệp trao đổi khóa

KEY_EXCHANGE phục vụ quá trình trao đổi khóa giữa các Peer trong cơ chế bảo mật. Theo module trao đổi khóa, nhóm thông điệp này có các thao tác như PUBLIC_KEY, SESSION_KEY và KEY_CONFIRM.

Nhóm thông điệp này được xử lý bởi module bảo mật riêng, không thuộc nhóm Callback truyền file trong FileMessageCallbacks.

e. Nhóm thông điệp xử lý lỗi và kết nối

Theo kế hoạch thiết kế hệ thống, ERROR được sử dụng để thông báo lỗi phát sinh trong quá trình giao tiếp, còn DISCONNECT được sử dụng để thông báo việc ngắt kết nối giữa các Peer.

## 3.4. Thiết kế chức năng nhắn tin

### 3.4.1. Mục tiêu và phạm vi chức năng nhắn tin

Chức năng nhắn tin cho phép các Peer trao đổi thông tin trực tiếp thông qua kết nối TCP trong mạng LAN mà không cần máy chủ trung gian để chuyển tiếp nội dung.

Hệ thống được thiết kế hỗ trợ các chức năng nhắn tin cơ bản và mở rộng, bao gồm:

- TEXT: Gửi và nhận tin nhắn văn bản.

- EMOJI: Gửi và hiển thị biểu tượng cảm xúc.

- REPLY: Trả lời một tin nhắn đã có trong cuộc trò chuyện.

- FORWARD: Chuyển tiếp nội dung tin nhắn đến Peer khác.

Mỗi thông điệp cần có thông tin định danh, nguồn gửi, đích nhận và thời điểm tạo để hỗ trợ quá trình xử lý, hiển thị và quản lý dữ liệu.

### 3.4.2. Thiết kế chức năng gửi và nhận TEXT

Chức năng TEXT cho phép người dùng nhập và gửi nội dung văn bản đến Peer đã lựa chọn.

a. Quy trình gửi tin nhắn

Quy trình gửi tin nhắn được thiết kế như sau:

1. Người dùng lựa chọn Peer đích từ danh sách Peer.

2. Người dùng nhập nội dung vào ô soạn thảo và nhấn nút Gửi.

3. Giao diện kiểm tra nội dung tin nhắn và thông tin Peer đích.

4. Hệ thống tạo thông điệp chứa thông tin định danh, loại thông điệp, người gửi, người nhận và nội dung.

5. Thông điệp được mã hóa theo quy trình bảo mật nếu phiên truyền thông đã được thiết lập phù hợp.

6. Dữ liệu được đóng khung và gửi đến Peer đích thông qua TCP.

7. Giao diện cập nhật nội dung tin nhắn theo kết quả xử lý gửi.

b. Quy trình nhận tin nhắn

1. Thành phần lắng nghe TCP tiếp nhận dữ liệu từ Peer gửi.

2. Hệ thống đọc đầy đủ khung dữ liệu và xác định thông điệp.

3. Thông điệp được giải mã nếu dữ liệu đã được mã hóa.

4. Hệ thống kiểm tra tính hợp lệ của thông điệp.

5. Thành phần xử lý thông điệp chuyển dữ liệu đến chức năng tương ứng.

6. Giao diện cập nhật khu vực trò chuyện để hiển thị nội dung nhận được.

c. Cấu trúc dữ liệu

```json
{
  "text": "Xin chào!"
}
```

Header chứa các trường message_id, message_type, sender_id, receiver_id và timestamp.

Trong đó, message_type có giá trị TEXT, còn nội dung văn bản được lưu trong trường text.

Dữ liệu được mã hóa bằng UTF-8 nhằm hỗ trợ tiếng Việt và các ký tự Unicode.

### 3.4.3. Thiết kế chức năng gửi và nhận EMOJI

Chức năng EMOJI giúp người dùng sử dụng các biểu tượng cảm xúc trong quá trình trao đổi tin nhắn.

Giao diện cung cấp thành phần lựa chọn Emoji, cho phép người dùng chọn biểu tượng từ danh sách có sẵn.

a. Quy trình xử lý

1. Người dùng mở bảng lựa chọn Emoji.

2. Người dùng lựa chọn biểu tượng cảm xúc mong muốn.

3. Giao diện đưa Emoji vào nội dung soạn thảo hoặc chuẩn bị thông điệp Emoji theo quy tắc giao thức được thống nhất.

4. Hệ thống gửi dữ liệu đến Peer đích qua TCP.

5. Peer nhận xử lý dữ liệu Unicode và hiển thị biểu tượng trong khu vực trò chuyện.

b. Cấu trúc dữ liệu

```json
{
  "emoji": "😊"
}
```

Giá trị message_type tương ứng là EMOJI.


### 3.4.4. Thiết kế chức năng REPLY

Chức năng REPLY cho phép người dùng trả lời trực tiếp một tin nhắn cụ thể trong cuộc trò chuyện.

Mục tiêu của chức năng là giữ được mối liên hệ giữa nội dung trả lời và tin nhắn gốc, giúp người dùng theo dõi ngữ cảnh trao đổi.

a. Quy trình xử lý

1. Người dùng lựa chọn tin nhắn cần trả lời.

2. Giao diện hiển thị khung xem trước tin nhắn gốc.

3. Người dùng nhập nội dung trả lời.

4. Hệ thống tạo thông điệp mới, đồng thời lưu thông tin tham chiếu đến tin nhắn gốc.

5. Thông điệp được gửi đến Peer nhận.

6. Peer nhận xử lý nội dung và thông tin tham chiếu.

7. Giao diện hiển thị tin nhắn trả lời kèm thông tin của tin nhắn được tham chiếu.

b. Cơ chế tham chiếu tin nhắn

Mỗi tin nhắn có một mã định danh riêng. Khi thực hiện Reply, hệ thống cần lưu mã định danh của tin nhắn gốc để phân biệt thông điệp mới và thông điệp được trả lời.

```json
{
  "reply_to": "550e8400-e29b-41d4-a716-446655440001",
  "text": "Tôi đồng ý với ý kiến này."
}
```
Trong đó:

- reply_to: Mã định danh của tin nhắn gốc.

- text: Nội dung trả lời của người dùng.

Tin nhắn trả lời phải có mã định danh riêng và không thay đổi thông tin của tin nhắn gốc.

### 3.4.5. Thiết kế chức năng FORWARD

Chức năng FORWARD cho phép người dùng chuyển tiếp nội dung từ một tin nhắn đã có đến một hoặc nhiều Peer khác.

Chức năng này giúp chia sẻ thông tin trong hệ thống mà không cần nhập lại nội dung thủ công.

a. Quy trình xử lý

1. Người dùng lựa chọn tin nhắn cần chuyển tiếp.

2. Giao diện hiển thị chức năng Forward.

3. Người dùng lựa chọn Peer đích.

4. Hệ thống lấy nội dung tin nhắn được chọn và chuẩn bị thông tin chuyển tiếp.

5.Hệ thống tạo thông điệp mới với thông tin người gửi hiện tại và Peer nhận.

6. Nội dung được mã hóa theo phiên giao tiếp với Peer đích nếu cơ chế bảo mật tương ứng được sử dụng.

7. Thông điệp được gửi qua TCP.

8. Peer nhận hiển thị nội dung và thông tin cho biết đây là tin nhắn được chuyển tiếp.

b. Thông tin chuyển tiếp

Theo đặc tả giao thức dự kiến, chức năng Forward cần bảo toàn thông tin nguồn của tin nhắn gốc.

```json
{
  "forwarded_from": "peer_A",
  "original_message_id": "550e8400-e29b-41d4-a716-446655440001",
  "original_message_type": "TEXT",
  "original_payload": {
    "text": "Nội dung được chuyển tiếp"
  }
}
```
Trong đó:

- forwarded_from: Thông tin người gửi của tin nhắn gốc.

- original_message_id: Mã định danh tin nhắn gốc.

- original_message_type: Loại thông điệp gốc.

- original_payload: Nội dung được chuyển tiếp.

Thông điệp Forward được tạo mới và mã định danh riêng 

### 3.4.6. Sơ đồ luồng xử lý tin nhắn

Quá trình xử lý nhắn tin trong hệ thống có thể chia thành hai luồng chính: gửi và nhận.

a. Luồng gửi

Người dùng thực hiện thao tác trên GUI. Thành phần giao diện kiểm tra dữ liệu đầu vào và tạo yêu cầu gửi tin nhắn. Dữ liệu sau đó được chuyển đến tầng xử lý giao thức, thực hiện các thao tác mã hóa và đóng khung cần thiết trước khi gửi qua TCP.

b. Luồng nhận

Thành phần TCP Listener tiếp nhận dữ liệu từ kết nối mạng, đọc thông điệp và chuyển đến bộ xử lý tương ứng. Sau khi kiểm tra và giải mã nếu cần, nội dung được chuyển đến giao diện để hiển thị.

Đối với Reply và Forward, hệ thống còn xử lý metadata để xác định thông tin tham chiếu đến tin nhắn gốc hoặc thông tin chuyển tiếp.


## 3.5. Thiết kế truyền File và Avatar

### 3.5.1. Cấu trúc metadata của tệp

Chức năng truyền tệp cho phép các Peer trao đổi dữ liệu dạng tệp trực tiếp thông qua kết nối TCP. Khác với tin nhắn văn bản, dữ liệu file có thể có dung lượng lớn nên cần được quản lý và truyền theo từng phần.

Các thành phần trong quy trình truyền file
| Trường | Ý nghĩa |
|---|---|
| `transfer_id` | mã định danh riêng cho một lần truyền file |
| `file_name` | tên tệp cần truyền |
| `file_size` | tổng dung lượng tệp tính bằng byte |
| `sha256` | mã băm dùng để kiếm tra tính toàn vẹn |
| `chunk_size` | kích thước tối đa của mỗi phần dữ liệu |
| `total_chunks` | tổng số phần dữ liệu sau khi chia tệp |
| `action` | hành động trong quy trình: FILE_OFFER, FILE_ACCEPT, FILE_REJECT, FILE_COMPLETE hoặc FILE_ERROR| 

Ví dụ:
```json
{
  "action": "START",
  "transfer_id": "550e8400-e29b-41d4-a716-446655440001",
  "file_name": "baocao.pdf",
  "file_size": 102400,
  "sha256": "SHA256_CUA_TAP_TIN"
}

```

### 3.5.2. Quy trình đề nghị và chấp nhận truyền tệp

Quy trình truyền file được tổ chức theo các giai đoạn sau:

1. Người dùng lựa chọn file cần gửi thông qua giao diện.

2. Hệ thống kiểm tra file và thu thập thông tin metadata.

3. Peer gửi thiết lập kết nối TCP đến Peer nhận.

4. Peer gửi tạo và truyền thông điệp FILE_START.

5. Peer nhận kiểm tra metadata và khởi tạo trạng thái tiếp nhận file.

6. Peer gửi chia file thành các chunk và lần lượt truyền thông điệp FILE_CHUNK.

7. Peer nhận tiếp nhận và ghi dữ liệu từng chunk.

8. Sau khi gửi hết dữ liệu, Peer gửi gửi thông điệp FILE_END.

9. Peer nhận hoàn tất lưu file và kiểm tra tính toàn vẹn dữ liệu.

10. Nếu thành công, Peer nhận gửi FILE_ACK; nếu xảy ra lỗi, hệ thống phản hồi bằng FILE_ERROR.

### 3.5.3. Cơ chế chia nhỏ và truyền dữ liệu (Chunking)

Để truyền file có kích thước lớn, hệ thống đọc tập tin theo từng phần thay vì tải toàn bộ nội dung vào bộ nhớ.

Trong module sender.py, kích thước mỗi chunk được cấu hình là 48 KiB.

Mỗi chunk được gắn với một chỉ số chunk_index, bắt đầu từ 0 và tăng dần theo thứ tự đọc dữ liệu.

Dữ liệu nhị phân được chuyển sang Base64 để có thể biểu diễn trong Payload JSON.

Ví dụ:

```json
{
  "action": "CHUNK",
  "transfer_id": "550e8400-e29b-41d4-a716-446655440001",
  "chunk_index": 0,
  "data": "BASE64_ENCODED_CHUNK"
}
```

Quá trình nhận dữ liệu sử dụng transfer_id để xác định phiên truyền và chunk_index để xác định vị trí tương ứng của chunk.

Việc chia nhỏ file giúp giảm lượng dữ liệu phải giữ đồng thời trong bộ nhớ và tạo cơ sở cho việc theo dõi tiến độ truyền.

### 3.5.4. Cơ chế xác nhận và kiểm tra tính toàn vẹn dữ liệu

Hệ thống sử dụng SHA-256 để kiểm tra tính toàn vẹn của file sau khi truyền.

Trước khi bắt đầu truyền, Peer gửi tính mã băm SHA-256 của tập tin và đưa giá trị này vào metadata.

Phía nhận sử dụng thông tin mã băm để kiểm tra dữ liệu sau khi tiếp nhận.

Quy trình kiểm tra được thiết kế gồm:

1. Nhận metadata của file từ thông điệp FILE_START.

2. Tiếp nhận và ghi các chunk theo phiên truyền.

3. Nhận thông điệp FILE_END.

4. Kiểm tra dữ liệu đã nhận và đối chiếu mã băm SHA-256.

5. Nếu hợp lệ, hoàn tất lưu tập tin.

6. Gửi thông điệp FILE_ACK để thông báo hoàn thành.

Ví dụ Payload xác nhận:

```json
{
  "action": "ACK",
  "transfer_id": "550e8400-e29b-41d4-a716-446655440001",
  "status": "COMPLETED"
}
```

Nếu dữ liệu không hợp lệ hoặc quá trình ghi file thất bại, phía nhận phản hồi bằng FILE_ERROR.

Trong luồng mã nguồn hiện tại, ACK hoàn tất được gửi sau khi xử lý FILE_END. Cơ chế ACK từng chunk, gửi lại chunk và phục hồi phiên truyền khi gián đoạn vẫn cần được kiểm chứng riêng.

### 3.5.5. Quản lý tiến độ và xử lý lỗi truyền tệp

Hệ thống cần quản lý trạng thái và tiến độ của từng tác vụ truyền file nhằm cung cấp thông tin cho người dùng.

Tiến độ truyền được tính dựa trên lượng dữ liệu đã xử lý so với tổng kích thước tập tin.

Công thức:

[
Progress=\frac{Bytes_{processed}}{FileSize}\times100%
]

Trong đó:

- Bytes_processed: Số byte dữ liệu đã xử lý tại thời điểm tính.

- FileSize: Tổng kích thước tập tin.

### 3.5.6. Thiết kế truyền Avatar

Avatar là hình ảnh đại diện của người dùng trong giao diện trò chuyện.

Về mặt thiết kế, việc đồng bộ Avatar giữa các Peer có thể tái sử dụng cơ chế truyền dữ liệu đã xây dựng cho chức năng truyền file.

Quy trình dự kiến gồm:

1. Người dùng lựa chọn hoặc cập nhật Avatar.

2. Ứng dụng chuẩn bị dữ liệu hình ảnh và metadata tương ứng.

3. Peer gửi truyền thông tin Avatar đến Peer nhận.

4. Peer nhận kiểm tra dữ liệu và lưu hình ảnh hợp lệ.

5. Giao diện cập nhật Avatar trong danh sách Peer và khu vực trò chuyện.

### 3.5.7. Sơ đồ trình tự truyền tệp

Sơ đồ trình tự mô tả quá trình trao đổi thông điệp giữa Peer gửi và Peer nhận.

Các thành phần chính bao gồm:

- Người dùng và giao diện GUI.

- Thành phần quản lý truyền file.

- TCP Sender.

- TCP Listener.

- Thành phần xử lý và lưu file.

![sơ đồ trình tự truyền file](image-6.png)

## 3.6. Thiết kế giao diện GUI và đa luồng

### 3.6.1. Các thành phần chính của giao diện

GỨng dụng Chat P2P sử dụng thư viện PyQt6 để xây dựng giao diện đồ họa, cho phép người dùng thực hiện các chức năng phát hiện Peer, thiết lập kết nối, nhắn tin và truyền tập tin.

Giao diện được tổ chức theo hướng tách biệt thành phần hiển thị và thành phần xử lý truyền thông, nhằm tăng khả năng bảo trì và mở rộng hệ thống.

Các thành phần bao gồm:
| Thành phần | Vai trò |
|---|---|
| MainWindow | quản lý cửa sổ ứng dụng và điều phối các thành phần giao diện |
| Peer List | hiển thị danh sách Peer được phát hiện và thông tin trạng thái |
| Chat Area | hiển thị nội dung tin nhắn giữa các Peer |
| Message Input | cho phép người dùng nhập nội dung tin nhắn |
| Send button | kích hoạt thao tác gửi tin nhắn |
| Emoji Picker | cung cấp danh sách biểu tượng cảm xúc |
| Reply Preview | hiển thị thông tin tin nhắn đang được trả lời |
| Forward Dialog | hỗ trợ lựa chọn Peer nhận tin nhắn chuyển tiếp |
| File Transfer UI | hiển thị thông tin và tiến độ truyền file |
| Connection Status | cung cấp thông tin trạng thái kết nối | 

Giao diện chính được bố trí thành hai khu vực: danh sách Peer ở bên trái và khu vực trò chuyện ở bên phải.

Khu vực trò chuyện bao gồm thông tin Peer đang được lựa chọn, danh sách tin nhắn, các thành phần hỗ trợ tương tác và vùng nhập dữ liệu.

Để quản lý danh sách tin nhắn, hệ thống sử dụng các thành phần MessageListModel và MessageDelegate. Trong đó, Model quản lý dữ liệu tin nhắn, còn Delegate đảm nhiệm việc trình bày nội dung trên giao diện.

Cách tổ chức này giúp phân tách dữ liệu tin nhắn khỏi phương thức hiển thị, đồng thời hỗ trợ tùy chỉnh giao diện cho các loại tin nhắn như TEXT, REPLY và FORWARD.

### 3.6.2. Thiết kế luồng xử lý đa luồng 

Trong ứng dụng giao tiếp mạng, các thao tác như chờ kết nối, nhận dữ liệu TCP và truyền tập tin có thể kéo dài hoặc bị gián đoạn do điều kiện mạng.

Nếu thực hiện các thao tác chặn trực tiếp trong luồng giao diện, ứng dụng có thể không phản hồi thao tác của người dùng trong thời gian xử lý.

Vì vậy, hệ thống được thiết kế theo hướng phân tách hoạt động giao diện và truyền thông mạng.

Các nhóm luồng xử lý chính gồm:

a. Main Thread (Luồng giao diện)

- Main Thread chịu trách nhiệm:

- Khởi tạo và quản lý các thành phần giao diện PyQt6.

- Tiếp nhận thao tác của người dùng.

- Hiển thị danh sách Peer và nội dung trò chuyện.

- Cập nhật trạng thái kết nối và tiến độ truyền file.

- Hiển thị thông báo khi xảy ra lỗi.

Các thao tác cập nhật widget cần được thực hiện trong luồng giao diện để đảm bảo an toàn khi sử dụng các thành phần Qt.

b. Network Worker (Luồng xử lý mạng)

Network Worker chịu trách nhiệm thực hiện các tác vụ liên quan đến truyền thông, bao gồm:

- Lắng nghe kết nối TCP.

- Tiếp nhận dữ liệu từ Peer khác.

- Thực hiện gửi và nhận thông điệp.

- Xử lý timeout và các sự kiện ngắt kết nối.

- Chuyển kết quả xử lý về thành phần điều phối phù hợp.

Việc tách xử lý mạng khỏi giao diện giúp giảm nguy cơ ứng dụng bị treo khi chờ dữ liệu từ socket.

c. File Transfer Worker (Luồng truyền file)

Các tác vụ truyền file được xử lý độc lập với luồng giao diện.

Trong thiết kế, File Transfer Worker đảm nhiệm việc đọc file, gửi dữ liệu theo từng chunk, theo dõi tiến độ và trả kết quả xử lý.

Việc quản lý và giới hạn số tác vụ đồng thời giúp hạn chế tình trạng sử dụng quá nhiều tài nguyên hệ thống

### 3.6.3. Cơ chế Signal/SLot giữa GUI và Network

PyQt6 cung cấp cơ chế Signal/Slot để trao đổi sự kiện giữa các thành phần trong ứng dụng.

Trong thiết kế giao tiếp giữa GUI và Network, Signal được sử dụng để thông báo rằng một sự kiện đã xảy ra, còn Slot là hàm tiếp nhận và xử lý sự kiện tương ứng.

Cơ chế này phù hợp với các ứng dụng sử dụng nhiều luồng vì cho phép chuyển thông tin về luồng giao diện thông qua kết nối Signal/Slot thích hợp.

a. Luồng xử lý từ GUI đến Network

Khi người dùng thực hiện thao tác như gửi tin nhắn hoặc truyền file:

1. Giao diện tiếp nhận sự kiện từ người dùng.

2. Thành phần điều phối kiểm tra dữ liệu đầu vào.

3. Yêu cầu được chuyển đến thành phần xử lý mạng.

4. Network Worker thực hiện thao tác truyền thông.

5. Kết quả được gửi về thành phần giao diện để cập nhật trạng thái.

b. Luồng xử lý từ Network đến GUI

Khi hệ thống nhận được dữ liệu từ một Peer:

1. Thành phần Network tiếp nhận dữ liệu qua socket.

2. Dữ liệu được đọc và xử lý theo giao thức truyền thông.

3. Hệ thống xác định nội dung thông điệp hoặc loại sự kiện.

4. Kết quả được chuyển đến thành phần xử lý giao diện.

5. Main Thread cập nhật danh sách tin nhắn hoặc trạng thái tương ứng.

Ví dụ, khi nhận được tin nhắn, giao diện có thể bổ sung thông điệp mới vào MessageListModel để hiển thị trong khu vực trò chuyện.

c. Nguyên tắc đồng bộ giữa các luồng

Để hạn chế lỗi trong quá trình xử lý đồng thời, thiết kế cần bảo đảm:

- Không cập nhật trực tiếp widget từ luồng mạng.

-Sử dụng Signal/Slot hoặc cơ chế chuyển sự kiện an toàn giữa các luồng.

- Đồng bộ dữ liệu dùng chung khi nhiều luồng cùng truy cập.

- Quản lý vòng đời Worker khi đóng ứng dụng.

- Xử lý ngoại lệ để lỗi kết nối không làm gián đoạn toàn bộ giao diện.

### 3.6.4. Sơ đồ luồng tương tác GUI và Network

Sơ đồ tương tác GUI và Network mô tả mối quan hệ giữa người dùng, Main Thread, Network Worker và Peer đích.

Khi người dùng gửi tin nhắn, Main Thread tiếp nhận yêu cầu và chuyển công việc xử lý đến thành phần mạng.

Network Worker thực hiện truyền dữ liệu qua TCP. Sau khi nhận kết quả, hệ thống thông báo lại cho giao diện để cập nhật thông tin tương ứng.

Tương tự, khi Peer gửi dữ liệu đến ứng dụng, Network Worker tiếp nhận và xử lý thông điệp trước khi chuyển kết quả về Main Thread.

![sơ đồ tương tác GUI và Network Worker](image-7.png)

Thiết kế giao diện và đa luồng giúp phân tách trách nhiệm giữa quá trình tương tác người dùng và xử lý truyền thông mạng.

Nhờ đó, hệ thống có thể tổ chức các chức năng nhắn tin và truyền file một cách độc lập hơn, đồng thời tạo điều kiện thuận lợi cho việc mở rộng, bảo trì và kiểm thử ứng dụng.

## 3.7. Thiết kế bảo mật và xử lý lỗi 

### 3.7.1. Cơ chế mã hóa và trao đổi khóa RSA/AES

Để bảo vệ thông tin trao đổi giữa các Peer, hệ thống xây dựng cơ chế mã hóa kết hợp giữa thuật toán bất đối xứng RSA và thuật toán mã hóa đối xứng AES.

Trong đó, RSA được sử dụng trong quá trình trao đổi khóa phiên, còn AES đảm nhiệm việc mã hóa và xác thực dữ liệu trong quá trình truyền thông.

Quy trình trao đổi khóa được trình bày chi tiết tại mục 3.2.4. Phần này tập trung vào việc áp dụng khóa phiên để bảo vệ dữ liệu trao đổi giữa các Peer.

a. Các thành phần bảo mật

Hệ thống sử dụng những thành phần chính sau:

| Thành phần | Chức năng |
|---|---|
| RSA-2048  |  tạo cặp khóa công khai và khóa riêng |
| RSA-OAEP-SHA256 | mã hóa khóa phiên khi trao đổi giữa các Peer |
| AES-256-GCM | mã hóa và xác thực dữ liệu truyền thông |
| HKDF-SHA256 | dẫn xuất khóa mã hóa theo từng chiều truyền |
| SHA-256 | tạo fingerprint và phục vụ các thao tác kiểm tra tính toàn vẹn |

b. Bảo vệ dữ liệu trong phiên truyền thông

Sau khi quá trình Handshake hoàn tất, hai Peer có thể sử dụng khóa phiên đã được thiết lập để mã hóa dữ liệu trước khi gửi qua TCP.

Trong module SessionCrypto, hệ thống sử dụng AES-256-GCM để mã hóa và xác thực nội dung.

Mỗi khung dữ liệu mã hóa được tổ chức theo cấu trúc:

seq (8 byte) | nonce (12 byte) | ciphertext | tag (16 byte)

Trong đó:

- seq: Số thứ tự của khung dữ liệu.

- nonce: Giá trị được sử dụng trong quá trình mã hóa AES-GCM.

- ciphertext: Nội dung sau khi mã hóa.

- tag: Thẻ xác thực dùng để kiểm tra tính toàn vẹn của dữ liệu.

Giá trị seq được sử dụng làm Additional Authenticated Data (AAD), cho phép hệ thống xác thực số thứ tự khung mà không cần mã hóa trường này.

Hệ thống quản lý bộ đếm riêng cho chiều gửi và chiều nhận. Khi phát hiện một khung dữ liệu có số thứ tự không hợp lệ, module mật mã có thể từ chối dữ liệu nhằm hạn chế nguy cơ phát lại thông điệp (Replay Attack).

c. Bảo mật dữ liệu khi truyền file

Ngoài mã hóa thông điệp thông thường, hệ thống cung cấp lớp ChunkCrypto để hỗ trợ mã hóa từng chunk trong quá trình truyền file.

Khóa mã hóa file được dẫn xuất từ khóa phiên theo chiều truyền và mã định danh transfer_id bằng HKDF-SHA256.

Mỗi chunk sử dụng thông tin chỉ số chunk_index trong quá trình mã hóa và xác thực.

Cơ chế này cho phép hệ thống kiểm tra tính toàn vẹn của từng phần dữ liệu và phát hiện trường hợp dữ liệu không hợp lệ.

Việc áp dụng mã hóa từng chunk trong quy trình truyền file thực tế cần được kiểm chứng khi tích hợp các module bảo mật và truyền dữ liệu.

### 3.7.2. Kiểm soát và xác thực dữ liệu

Trong hệ thống P2P, các Peer có thể tiếp nhận dữ liệu từ những thiết bị khác trong mạng. Vì vậy, dữ liệu nhận được cần được kiểm tra trước khi đưa vào xử lý nghiệp vụ hoặc hiển thị trên giao diện.

Hệ thống xây dựng các cơ chế kiểm tra tính hợp lệ tại tầng giao thức và tầng xử lý dữ liệu.

a. Kiểm tra cấu trúc thông điệp

Thành phần kiểm tra dữ liệu có nhiệm vụ xác định thông điệp nhận được có phù hợp với định dạng giao thức hay không.

Các nội dung kiểm tra bao gồm:

- Kiểu dữ liệu của thông điệp và các trường bắt buộc.

- Loại thông điệp có thuộc danh sách được hỗ trợ hay không.

- Thông tin người gửi.

- Kích thước dữ liệu.

- Các thuộc tính riêng của từng loại thông điệp.

- Các giá trị không hợp lệ hoặc vượt quá phạm vi cho phép.

b. Giới hạn kích thước dữ liệu

Để hạn chế việc tiếp nhận dữ liệu quá lớn, hệ thống áp dụng giới hạn kích thước tại các thành phần xử lý.

Ngoài việc kiểm tra kích thước, hệ thống cần xác nhận kiểu dữ liệu của các trường số nguyên, tránh chấp nhận những kiểu giá trị không phù hợp.

c. Kiểm tra dữ liệu truyền file

Đối với chức năng truyền file, dữ liệu cần được kiểm tra trước khi ghi vào hệ thống lưu trữ.

Các nội dung kiểm tra bao gồm:

-Tên tập tin.

- Kích thước tập tin.

- Mã định danh phiên truyền.

- Chỉ số và kích thước chunk.

- Dữ liệu Base64.

- Mã băm SHA-256.

Hệ thống sử dụng SHA-256 để đối chiếu dữ liệu và phát hiện sai lệch giữa nội dung nhận được với thông tin đã khai báo.

Tên tập tin cũng cần được kiểm tra để hạn chế nguy cơ sử dụng đường dẫn không hợp lệ hoặc truy cập ra ngoài thư mục lưu trữ được phép.

d. Kiểm tra dữ liệu trước khi hiển thị

Ngoài dữ liệu truyền qua mạng, các thông tin được sử dụng để hiển thị trên GUI cũng cần được kiểm tra kiểu dữ liệu.

Đối với chức năng Reply và Forward, thông tin metadata cần có cấu trúc phù hợp trước khi được giao diện sử dụng.

Việc kiểm tra này nhằm hạn chế lỗi phát sinh khi giao diện truy cập các trường dữ liệu không đúng định dạng.

### 3.7.3. Xử lý timeout và mất kết nối

Trong quá trình giao tiếp P2P, kết nối TCP có thể bị gián đoạn do thiết bị ngắt mạng, Peer đích không phản hồi hoặc xảy ra lỗi truyền thông.

Hệ thống cần phát hiện và xử lý những tình huống này để tránh việc chương trình bị treo trong thời gian dài.

a. Xử lý timeout khi thiết lập kết nối

Khi một Peer chủ động kết nối đến Peer khác, hệ thống thiết lập thời gian chờ nhằm giới hạn khoảng thời gian thực hiện kết nối.

Các giá trị trên thuộc những luồng xử lý khác nhau, không phải một cấu hình timeout duy nhất áp dụng cho toàn hệ thống.

Khi vượt quá thời gian chờ, hệ thống cần thông báo lỗi phù hợp và xử lý tài nguyên kết nối.

b. Xử lý ngắt kết nối trong quá trình truyền dữ liệu

Khi một kết nối TCP bị đóng hoặc phát sinh lỗi trong quá trình truyền, các thành phần mạng cần nhận diện trạng thái lỗi và kết thúc thao tác tương ứng.

Các tình huống có thể xảy ra gồm:

Peer đích từ chối kết nối.

Socket hết thời gian chờ.

Peer ngắt kết nối trong khi đang truyền thông điệp.

Kết nối bị đóng trước khi nhận đủ dữ liệu.

Phát sinh lỗi trong quá trình gửi hoặc nhận file.

Đối với các trường hợp này, hệ thống cần xử lý ngoại lệ và thông báo kết quả đến thành phần điều phối hoặc giao diện.

c. Xử lý gián đoạn khi truyền file

Khi truyền file bị gián đoạn, hệ thống cần xác định phiên truyền chưa hoàn tất để tránh coi dữ liệu thiếu là một tập tin hợp lệ.

Trong thiết kế, các tác vụ thất bại cần được đánh dấu trạng thái phù hợp và giải phóng tài nguyên liên quan.

Cơ chế gửi lại chunk, tiếp tục truyền từ vị trí gián đoạn hoặc khôi phục phiên truyền là những chức năng cần được xác nhận riêng trong quá trình tích hợp.

Không mặc định rằng TCP hoặc cơ chế ACK hoàn tất file có thể tự động khôi phục một phiên truyền đã bị ngắt.

### 3.7.4. Giải phóng tài nguyên và xử lý ngoại lệ

Việc quản lý tài nguyên là yêu cầu quan trọng đối với ứng dụng P2P, đặc biệt khi hệ thống sử dụng nhiều kết nối TCP và nhiều luồng xử lý.

Các tài nguyên cần quản lý bao gồm socket, thread, file đang mở, dữ liệu tạm và trạng thái của các phiên truyền.

a. Quản lý socket

Khi một kết nối không còn được sử dụng, hệ thống cần đóng socket để giải phóng tài nguyên mạng.

b. Quản lý luồng xử lý

Các tác vụ xử lý mạng và truyền file cần có cơ chế kết thúc phù hợp để hạn chế tình trạng luồng còn hoạt động sau khi ứng dụng đã đóng.

Module transfer_manager.py sử dụng ThreadPoolExecutor để thực hiện các tác vụ gửi file và cung cấp phương thức shutdown() để quản lý việc kết thúc executor.

Các thành phần Listener cũng cần quản lý luồng tiếp nhận kết nối và những luồng đang xử lý Client.

c. Xử lý ngoại lệ

Các ngoại lệ cần được phân loại theo nguyên nhân, bao gồm:

- Lỗi kết nối và timeout.

- Lỗi định dạng thông điệp.

- Lỗi mã hóa hoặc giải mã.

- Lỗi truyền và lưu file.

- Lỗi dữ liệu không hợp lệ.

Các thành phần xử lý cần ghi nhận thông tin lỗi cần thiết để hỗ trợ kiểm thử và khắc phục sự cố.

