# Đề xuất hợp đồng API giữa TV4 và TV5

**Trạng thái:** Bản đề xuất để TV4 và TV5 cùng duyệt; chưa phải API đã triển khai.

**Phạm vi:** Kết nối TCP, message ứng dụng, truyền file/avatar và thông báo tiến trình.

**Nhánh soạn thảo:** `feature/p2p-tcp-client-server` sau khi đồng bộ `main`.

## 1. Quyết định nền tảng

- Trên một kết nối TCP, mỗi message ứng dụng dùng **4 byte độ dài không dấu, big-endian**, sau đó là **JSON UTF-8**. Độ dài tính theo số byte JSON. Giới hạn hiện tại trong `CODE/shared/protocol.py` là 1 MiB.
- `CODE/shared/protocol.py` là nơi duy nhất tạo, mã hóa, đọc và kiểm tra message ứng dụng. `CODE/protocol.py` hiện dùng frame nhị phân khác định dạng; không trộn hai định dạng trên một socket. Chưa xóa file này trước khi kiểm tra các phần khác phụ thuộc vào nó.
- Mỗi socket chỉ có **một vòng đọc**. `listener.py` sở hữu socket và vòng đời kết nối; nó gọi `recv_message()` đúng một lần cho mỗi message rồi chuyển kết quả cho handler.
- TCP sender chỉ gửi `bytes` đã được đóng khung. Sender không tự tạo JSON, không tự thêm tiền tố độ dài.
- Các thao tác mạng và ghi file chạy ngoài luồng GUI.

> Cần TV1 xác nhận cách ghép với `security/handshake.py`: module này cũng dùng tiền tố độ dài 4 byte, nhưng dữ liệu sau handshake là ciphertext. Khi bật bảo mật, chỉ đóng khung **một lần** và phải giải mã trước khi phân loại JSON; không gọi `encode_message()` rồi bọc thêm `send_secure()` quanh cả frame.

## 2. Vị trí file và người sở hữu

| File đích | Chủ trì | Trách nhiệm |
| --- | --- | --- |
| `CODE/shared/protocol.py` | TV4 | Tạo, kiểm tra, encode/decode và đọc đủ một JSON message. |
| `CODE/p2p_node/peer_manager.py` | TV4 | Quản lý peer và địa chỉ TCP. Chuyển từ `CODE/core/peer_manager.py`. |
| `CODE/p2p_node/discovery.py` | TV4 | UDP discovery. Chuyển từ `CODE/core/udp_discovery.py`. |
| `CODE/p2p_node/handler.py` | TV4 | Phân loại message, đăng ký callback; không ghi file. |
| `CODE/p2p_node/sender.py` | TV5 | Kết nối, timeout, `sendall`, đóng socket. |
| `CODE/p2p_node/listener.py` | TV5 | Mở cổng, nhận kết nối, chạy vòng đọc và đóng socket. |
| `CODE/p2p_node/transfer_task.py` | TV5 | Dữ liệu và trạng thái một phiên truyền file. |
| `CODE/p2p_node/transfer_manager.py` | TV5 | Queue, ghi chunk, retry, progress và hoàn tất file. |
| `CODE/main.py` | Tích hợp chung | Tạo các đối tượng và nối callback; không chứa logic protocol/file. |

`CODE/core/client.py`, `CODE/core/server.py`, `CODE/core/main.py` và các file TCP cũ ở gốc `CODE/` hiện vẫn là đường chạy thử. Chỉ dọn chúng sau khi điểm chạy chung hoạt động. GUI hiện import `p2p_node.*`, nhưng nhiều module đó chưa tồn tại; việc đổi tên file phải cập nhật import và chạy kiểm tra tích hợp cùng lúc.

## 3. API public dự kiến

Các hàm đã có được giữ tên để giảm thay đổi. Chữ **mới** chỉ API dự kiến, chưa được code.

```python
# TV4: CODE/shared/protocol.py
create_message(sender_id: str, receiver_id: str,
               message_type: str, payload: dict) -> dict        # đã có
encode_message(message: dict) -> bytes                          # đã có; gồm cả 4 byte độ dài
recv_message(sock) -> dict                                      # đã có; đọc đủ một message
validate_message(message: dict) -> None                         # mới; ValueError nếu sai schema

# TV4: CODE/p2p_node/peer_manager.py
PeerManager.add_peer(peer_id: str, ip: str, tcp_port: int) -> None
PeerManager.get_peer(peer_id: str) -> dict | None
# dict tối thiểu: {"ip": str, "tcp_port": int}

# TV4: CODE/p2p_node/handler.py (mới)
MessageHandler.register(message_type: str, callback) -> None
MessageHandler.handle_message(message: dict, send_reply) -> None
# callback(message: dict, send_reply: Callable[[dict], None]) -> None
# send_reply nhận dict; vòng kết nối mã hóa và gửi qua cùng socket.

# TV5: CODE/p2p_node/sender.py
TCPSender.connect(host: str, port: int) -> bool                 # hiện có trong CODE/tv5/sender.py
TCPSender.send(data: bytes) -> None                             # hiện có; dùng sendall
TCPSender.close() -> None                                       # hiện có

# TV5: CODE/p2p_node/listener.py
TCPListener.start() -> None                                     # hiện có trong CODE/tv5/listener.py
TCPListener.accept_peer() -> tuple                              # hiện có
TCPListener.close() -> None                                     # hiện có
```

Ví dụ luồng gửi: `peer = manager.get_peer(peer_id)` → `sender.connect(peer["ip"], peer["tcp_port"])` → `sender.send(encode_message(message))`. Luồng nhận: `listener.accept_peer()` → `recv_message(conn)` → `handler.handle_message(message, send_reply)`. **Chỉ một nơi được gọi `recv_message(conn)` trên cùng socket.** Điểm chạy chung đăng ký callback file của TV5 vào handler TV4; hai module không import vòng nhau.

TV4 sở hữu callback `TEXT`/`EMOJI` và lỗi schema. TV5 sở hữu callback `FILE_META`/`FILE_CHUNK`/`FILE_END`; TV5 chỉ gửi ACK sau khi thao tác file tương ứng thành công. Callback avatar cần chốt với TV2/TV5: avatar nhỏ có thể nằm trong JSON metadata, avatar lớn đi theo chunk và dùng cùng quy tắc giới hạn kích thước.

## 4. Tên và schema message cần giữ cố định

Mọi message dùng `header = {message_id, message_type, sender_id, receiver_id, timestamp}` và `payload` là object. `message_id` và `transfer_id` là UUID dạng chuỗi; `timestamp` là UTC ISO 8601. `sender_id`/`receiver_id` là ID peer, không phải IP. Tên loại message viết hoa. Các tên dưới đây **cần TV5 duyệt trước khi triển khai**:

| `message_type` | Trường bắt buộc trong `payload` | Người xử lý |
| --- | --- | --- |
| `TEXT` | `text: str` | TV4/UI |
| `EMOJI` | `emoji: str` (UTF-8) | TV4/UI |
| `FILE_META` | `transfer_id`, `file_name`, `file_size`, `chunk_size`, `total_chunks` | TV5 |
| `FILE_CHUNK` | `transfer_id`, `chunk_index`, `data_b64` | TV5 |
| `FILE_END` | `transfer_id`, `sha256` | TV5 |
| `AVATAR_META` | `transfer_id`, `file_size`, `total_chunks` | TV5/UI, cần chốt chủ sở hữu |
| `AVATAR_CHUNK` | `transfer_id`, `chunk_index`, `data_b64` | TV5/UI, cần chốt chủ sở hữu |
| `ACK` | `reply_to_message_id`, `status`; thêm `transfer_id`, `chunk_index` khi áp dụng | Bên gửi ban đầu |
| `ERROR` | `reply_to_message_id`, `error_code`, `detail`; thêm `transfer_id` khi áp dụng | Bên gửi ban đầu |

`chunk_index` bắt đầu từ **0**; `total_chunks` là tổng số chunk. File rỗng có `total_chunks = 0` và không có `FILE_CHUNK`. Chunk bytes được mã hóa base64 thành `data_b64`; kích thước thô đề xuất tối đa **48 KiB** để còn chỗ cho JSON và tránh vượt giới hạn message. `file_name` chỉ là tên file, không phải đường dẫn. Bên nhận kiểm tra chỉ số chunk, số byte, kích thước file và SHA-256 trước khi xác nhận hoàn tất.

Tài liệu `DOCX/docs/message_protocol.md` hiện mô tả `FILE` với trường `action`; trước khi triển khai cần cập nhật tài liệu đó theo lựa chọn `FILE_META`/`FILE_CHUNK`/`FILE_END`, hoặc cả nhóm giữ `FILE` và quy định `action`. Không dùng hai cách đặt tên cùng lúc.

## 5. ACK, lỗi, retry và progress

- ACK `TEXT`/`EMOJI` sau khi handler kiểm tra và chấp nhận message. ACK `FILE_META` sau khi bên nhận tạo tác vụ. ACK `FILE_CHUNK` sau khi chunk được ghi thành công. ACK `FILE_END` sau khi kiểm tra đủ byte/SHA-256 và đổi file tạm thành file hoàn chỉnh.
- ACK cho chunk chứa cả `reply_to_message_id`, `transfer_id`, `chunk_index`. Bên gửi chỉ tính chunk đã xác nhận sau khi nhận ACK tương ứng. Khi timeout, có thể gửi lại cùng `message_id` và `chunk_index`; bên nhận phải nhận diện bản trùng và không ghi hai lần.
- `ERROR.error_code` là mã ổn định, đề xuất: `INVALID_MESSAGE`, `UNKNOWN_TRANSFER`, `INVALID_CHUNK`, `WRITE_FAILED`, `CHECKSUM_MISMATCH`, `TIMEOUT`. `detail` chỉ phục vụ hiển thị/log, không dùng để phân nhánh logic.
- TV5 phát progress theo `transfer_id`, `bytes_done`, `total_bytes`, `speed_bytes_per_sec`, `status`. Bên gửi tính `bytes_done` từ chunk đã ACK; bên nhận tính từ byte đã ghi. Trạng thái dùng `WAITING`, `TRANSFERRING`, `COMPLETED`, `FAILED`, `CANCELLED`.
- Cần TV5 chốt timeout, số lần retry và giới hạn file song song. Điểm bắt đầu đề xuất: timeout phản hồi **10 giây**, tối đa **3 lần gửi lại/chunk**, tối đa **3 file đồng thời**. Đây là giá trị cấu hình, không hard-code trong handler.

## 6. Điều kiện bàn giao và kiểm tra tích hợp

1. TV4 hoàn thiện và kiểm tra protocol/validator/handler, có ví dụ `TEXT`, `EMOJI`, `FILE_META`, `FILE_CHUNK`, ACK và ERROR. TV4 cập nhật import khi chuyển `PeerManager` và discovery.
2. TV5 dùng đúng API và schema đã chốt; không tạo bộ framing khác trong sender/listener. Điểm chạy chung nối callback file của TV5 với handler.
3. Hai bên kiểm tra hai peer gửi text Unicode, emoji, file rỗng và file nhiều chunk; thử message lỗi, ngắt giữa chừng, gửi chunk trùng và checksum sai. Kiểm tra progress tăng đúng và trạng thái kết thúc.
4. Sau khi luồng chung chạy được, mới dọn các điểm chạy và protocol cũ còn trùng chức năng.

**Các quyết định cần TV5 xác nhận:** tên `FILE_*` hay `FILE` + `action`; callback `MessageHandler.register()`; ACK từng chunk và retry; owner của avatar; thời điểm dùng giao thức mã hóa của TV1. Khi chốt, đổi trạng thái tài liệu thành “Đã thống nhất” và dùng nó làm chuẩn cho hai nhánh.
