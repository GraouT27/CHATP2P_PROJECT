# P2P MESSAGE PROTOCOL SPECIFICATION

Mỗi thông điệp có hai phần chính: `header` và `payload` 
```json 
{
  "header":
      "message_id": "UUID",
      "message_type": "TEXT",
      "sender_id": "peer_A",
      "receiver_id": "peer_B",
      "timestamp": "2026-10-26T01:00:00Z"
},
  "payload":{
    "text": "Xin chào!"
  }
```
## 1. Header:
| Field |  Type | Required | Description | Quy tắc |
|---|---|---|---|---|
| `message_id` | String | Yes | ID duy nhất của thông điệp | UUID của message hiện tại; tạo mới cho message logic mới |
| `message_type` | String | Yes | Loại thông điệp | loại thông điệp (phân việt chữ hoa); phải được `handler` hỗ trợ |
| `sender_id` | String | Yes | ID của peer gửi thông điệp hiện tại | ID Peer gửi, không phải IP; không rỗng |
| `receiver_id` | String | Yes | ID của peer nhận thông điệp | ID Peer nhận, không phải IP; không rỗng |
| `timestamp` | String | Yes | Thời điểm tạo thông điệp theo UTC | IS0 8601 có UTC |

## 2. Danh sách message type
| Message type | Ý nghĩa | 
|---|---|
| `TEXT` | tin nhắn văn bản | 
| `EMOJI` | emoji UTF-8 |
| `REPLY` | tin nhắn trả lời |
| `FORWARD` | tin nhắn chuyển tiếp |
| `FILE_OFFER` | đề nghị gửi file |
| `FILE_CHUNK` | một chunk dữ liệu |
| `FILE_END` | kết thúc gửi và xác minh |
| `AVATAR_META` | metadata ảnh đại diện |
| `AVATAR_CHUNK` | chunk ảnh đại diện |
| `ERROR` | báo lỗi ở tầng ứng dụng |
| `DISCONNECT` | thông báo đóng phiên chủ động | 
| `KEY_EXHCHANGE` | Trao đổi và xác nhận khóa | 

## 3. Payload 
### 3.1. TEXT 
| Field | Type | Required | Description |
|---|----|---|---|
| `text` | String | YES | Văn bản UTF-8 | 

Ví dụ payload: 
```json 
  "payload":{
    "text": "Xin chào!"
  }
```
### 3.2. EMOJI
| Field | Type | Required | Description |
|---|---|---|---|
| `emoji` | String | Yes | Emoji Unicode mã hóa UTF-8 trong JSON |

Ví dụ payload: 
```json 
  "payload":{
    "emoji": "😂"
  }
```
### 3.3. REPLY 
| Field | Type | Required | Description |
|---|---|---|---|
| `reply_to_message_id` | String | Yes | ID của tin nhắn gốc |
| `text` | String | Yes | Nội dung trả lời |

Ví dụ payload: 
```json 
  "payload":{
    "reply_to_message_id": "550e8400-e29b-41d4-a716-446655440001",
    "text": "Xin chào! Bạn khỏe không ?"
  }
```
Quy tắc: 
- Tin nhắn trả lời phải có `message_id` mới. 
- `reply_to_message_id` tham chiếu đến `message_id` của thông điệp gốc.
- Giao diên tra cứu thông điệp gốc bằng ID để hiển thị nội dung được trả lời. 
- Không dùng `sender_id` để thay thế `reply_to_message_id`.

### 3.4. FORWARD 
| Field | Type | Required | Description |
|---|---|---|---|
| `original_message_id` | String | Yes | ID của tin nhắn gốc |
| `original_sender_id` | String | Yes | Peer gửi tin nhắn gốc |
| `original_message_type` | String | Yes | Loại thông điệp gốc |
| `original_payload` | Object | Yes | Payload gốc được chuyển tiếp |

Ví dụ payload: 
```json
{
  "original_message_id": "550e8400-e29b-41d4-a716-446655440001",
  "original_message_type": "TEXT",
  "original_sender_id": "peer_A",
  "original_payload": {
      "text": "Mai nhớ nộp bài nha !"
  } 
}
```
Quy tắc:
- Thông điệp FORWARD có `message_id`  mới
- `sender_id` là peer đang chuyển tiếp
- `receiver_id` là peer nhận nội dung được chuyển tiếp
- `original_message_id` giữ nguyên ID của tin nhắn gốc
- Chỉ chuyển tiếp các loại thông điệp được Protocol cho phép.
- Không tự động chuyển tiếp dữ liệu khóa riêng hoặc thông tin bí mật.

### 3.5. FILE_OFFER 
| Field | Type | Required | Description |
|---|---|---|---|
| `action` | String | Yes | gửi truyền file |
| `transfer_id` | UUID String | Yes | ID duy nhất của phiên truyền file |
| `file_name` | String | Yes ( dùng cho OFFER ) | Tên file |
| `file_size` | Integer | Yes (dùng cho OFFER) | Kích thước file tính bằng bytes không âm |
| `chunk_size` | Integer | Yes | Kích thước mỗi khối dữ liệu |
| `total_chunks` | Integer | Yes | Tổng số khối dữ liệu |

Ví dụ payload: 
```json
{
  "action": "FILE_OFFER",
  "transfer_id": "UUID_PHIEU_TRUYEN_FILE",
  "file_name": "baocao.pdf",
  "file_size": 102400,
  "chunk_size": 16384,
  "total_chunks": 7 
}
```
Quy tắc:
- Kích thước mỗi khối dữ liệu dự kiến nằm trong khoảng 4 KB đến 64 KB.
- Kích thước thực tế của khối cuối có thể nhỏ hơn các khối trước.
- Phía nhận cần kiểm tra kích thước tệp và dữ liệu nhận được.
- Tệp nên được ghi vào tệp tạm trong lúc nhận; chỉ đổi sang tên chính thức khi hoàn tất và kiểm tra thành công
- Nếu tên tệp đã tồn tại, cần tạo tên mới hoặc yêu cầu người dùng xác nhận
- `file_name` chỉ là tên tệp, không được dùng trực tiếp làm đường dẫn lưu 

### 3.7. FILE_CHUNK 
| Field | Type | Required | Ý nghĩa |
|---|---|---|---|
| `action` | string | có | ... |
|`transfer_id` | UUID | string | có | ID của phiên truyền đang xử lý |
| `chunk_index` | integer | có | bắt đầu từ 0 |
| data_b64 | string | có | dữ liệu chunk mã hóa base64 |

```json
{"action":"CHUNK",
"transfer_id":"550e8400-e29b-41d4-a716-446655440012",
"chunk_index":0,
"data_b64":"SGVsbG8="}
```
### 3.8. AVATAR_META (đề xuất)

| File | Type | Required | Description |
|---|---|---|---|
| `transfer_id` | String (UUID) | Yes | định danh lần truyền Avatar |
| `file_name` | String | Yes | tên tập tin ảnh |
| `file_size` | Integer | Yes | kích thước ảnh tính bằng byte |
| `total_chunks` | Integer | Yes | tổng số chunk |
| `sha256` | String | Yes | mã băm SHA-256 của ảnh |

Ví dụ Payload:

```json
{
  "transfer_id": "550e8400-e29b-41d4-a716-446655440001",
  "file_name": "avatar.png",
  "file_size": 204800,
  "total_chunks": 5,
  "sha256": "SHA256_HEX_CUA_ANH"
}
```

Quy tắc:
- Metadata không trực tiếp chứa nội dung ảnh.

- `file_name` chỉ là tên tập tin, không phải đường dẫn.

- Bên nhận cần kiểm tra định dạng, kích thước và mã băm.

- Chỉ cập nhật Avatar sau khi đã nhận và kiểm tra dữ liệu thành công.

### 3.9 AVATAR_CHUNK (đề xuất)

| Field | Type | Required | Description |
|---|---|---|---|
| `transfer_id` | String (UUID) | Yes | định danh lần truyền Avatar |
| `chunk_index` | Integer | Yes | chỉ số chunk, bắt đầu từ 0 |
| `data_ba64` | String | Yes | dữ liệu chunk mã hóa Base64 |

Ví dụ Payload:

```json
{
  "transfer_id": "550e8400-e29b-41d4-a716-446655440001",
  "chunk_index": 0,
  "data_b64": "BASE64_ENCODED_IMAGE_CHUNK"
}
```

Quy tắc:

- Mỗi chunk thuộc một `transfer_id` cụ thể.

- `chunk_index` phải nằm trong phạm vi cho phép.

- Bên nhận cần kiểm tra kích thước và dữ liệu sau khi giải mã Base64.

- Chỉ hoàn tất việc cập nhật Avatar khi nhận đủ dữ liệu và kiểm tra SHA-256 thành công.

- Cơ chế ACK và gửi lại chunk cần thống nhất với TV5 trước khi triển khai.

### 3.10. ACK (đề xuất)
| Field | Type | Required | Ý nghĩa |
|---|---|---|---|
| `reply_to_message_id` | UUID string | có | message được xác nhận |
| `status` | string | có | trạng thái xử lý, cần chốt tập giá trị |
| `transfer_id` | UUID string | có điều kiện | ID khi xác nhận file |
| `chunk_index` | integer | có điều kiện | khi xác nhận chunk |

```json
{
  "reply_to_message_id":"550e8400-e29b-41d4-a716-446655440011",
  "status":"OK",
  "transfer_id":"550e8400-e29b-41d4-a716-446655440012"}
```
### 3.11. ERROR (đề xuất)

Thông điệp ERROR được đề xuất để thông báo lỗi trong quá trình xử lý thông điệp hoặc giao tiếp giữa các Peer. 

| Field | Type | Required | Description |
| `reply_to_message_id` | String (UUID) | Yes | định danh thông điệp gây lỗi |
| `error_code` | String | Yes | mã lỗi |
| `detail` | String | Yes | mô tả ngắn gọn về lỗi | 

Ví dụ Payload:

```json
{
  "reply_to_message_id": "550e8400-e29b-41d4-a716-446655440001",
  "error_code": "INVALID_MESSAGE",
  "detail": "Thong diep khong dung dinh dang"
}
```

Quy định các mã lỗi:

| Error Code | Ý nghĩa |
|---|---|
| `INVALID_ID_MESSAGE` | thông điệp không hợp lệ |
| `UNSUPPORTED_TYPE` | loại thông điệp chưa được hỗ trợ |
| `INVALID_PAYLOAD` | Payload không đúng cấu trúc |
| `TIMEOUT` | quá thời gian chờ |
| `INTERNAL_ERROR` | lỗi xử lý nội bộ |

Quy tắc:

- Mã lỗi phải ổn định để chương trình có thể xử lý.

- Trường detail phục vụ hiển thị và ghi log, không dùng làm mã điều khiển nghiệp vụ.

- Không đưa khóa bí mật hoặc dữ liệu nhạy cảm vào thông báo lỗi.

- Nếu không thể xác định thông điệp gây lỗi, cần quy định riêng cách xử lý trường `reply_to_message_id`.

### 3.12. DISCONNECT (đề xuất)

Thông điệp DISCONNECT được đề xuất để một Peer chủ động thông báo việc kết thúc phiên giao tiếp trước khi đóng kết nối TCP.

| Field | Type | Required | Description |
|---|---|---|---|
| reason | String | Yes | lý do ngắt kết nối | 

Ví dụ Payload: 
```json 
{
  "reason": "USER_EXIT"
}
```

Các giá trị `reason` có thể gồm:

| Giá trị | Ý nghĩa |
|---|---|
| `USER_EXIT` | người dùng chủ động thoát |
| `SESSION_END` | kết thúc phiên giao tiếp |
| `SHUTDOWN` | ứng dụng đang đóng |

Quy tắc:

- Peer gửi có thể truyền DISCONNECT trước khi đóng socket nếu kết nối còn hoạt động.

- Peer nhận cập nhật trạng thái phiên giao tiếp sau khi xử lý thông báo.

- Không bắt buộc phải nhận được DISCONNECT mới xử lý mất kết nối.

- Kết nối bị ngắt đột ngột phải được phát hiện bằng cơ chế socket và xử lý ngoại lệ riêng.

### 3.13. KEY_EXCHANGE 

- PUBLIC_KEY: Trao đổi khóa công khai RSA.

- SESSION_KEY: Gửi khóa phiên được mã hóa.

- KEY_CONFIRM: Xác nhận quá trình thiết lập phiên bảo mật.

a. PUBLIC KEY

| Field | Type | Description |
|---|---|---|
| `action` | String | Hành động trao đổi khóa |
| `algorithm` | String | RSA-2048 |
| `key_id` | String | ID của khóa |
| `public_key` | String | Khóa công khai |

Ví dụ payload - gửi khóa công khai:
```json
{
  "action": "PUBLIC_KEY",
  "algorithm": "RSA",
  "key_id": "key-peer-A-001",
  "public_key": "NOI_DUNG_KHOA_CONG_KHAI"
}
```
b. SESSION KEY 
| Field | Type | Description |
|---|---|---|
| `action` | String | Hành động trao đổi khóa |
| `algorithm` | String | RSA-OAEP-SHA256 |
| `key_id` | String | ID của khóa |
| `encrypted_session_key` | String | Khóa phiên được mã hóa RSA-OAEP và biểu diễn Base64 | 

Ví dụ payload - gửi khóa đã được mã hóa:
```json
{
  "action": "SESSION_KEY",
  "algorithm": "RSA-OAEP-SHA256",
  "key_id": "key-peer-B-001",
  "encrypted_session_key": "BASE64_ENCODED_CIPHERTEXT"
}
```
c. KEY_CONFIRM
Sau khi hai Peer thiết lập khóa phiên, phía nhận gửi thông điệp xác nhận được bảo vệ bằng AES-256-GCM.

Ví dụ Payload trước khi mã hóa:

```json
{
  "action": "KEY_CONFIRM",
  "algorithm": "AES-256-GCM"
}
```

Quy tắc:
- Khóa riêng RSA không được gửi qua mạng.

- Khóa phiên được tạo ngẫu nhiên và mã hóa bằng RSA-OAEP-SHA256 khi trao đổi.

- Fingerprint của khóa công khai được sử dụng để hỗ trợ xác nhận Peer.

- Sau khi thiết lập phiên, dữ liệu có thể được mã hóa bằng AES-256-GCM.

- Hai chiều truyền sử dụng khóa mã hóa được dẫn xuất riêng bằng HKDF-SHA256.

- Khi Handshake thất bại hoặc quá thời gian chờ, quá trình thiết lập phiên phải được hủy và xử lý lỗi phù hợp.

## 4. Quy tắc xử lý chung
1. Mỗi tin nhắn phải có `header` và `payload`.
2. Tất cả tin nhắn phải là JSON hợp lệ và được mã hóa UTF-8.
3. `message_id` phải duy nhất cho từng tin nhắn
4. Peer nhận phải kiểm tra `message_type`, các field và data type
5. Tin nhắn sai định dạng phải được xử lý an toàn
6. Phải có timeout và xử lý trường hợp peer ngắt kết nối
7. Không đưa mật khẩu, khóa riêng hoặc dữ liệu bí mật vào log.

## 5. TCP framing và truyền file 
TCP là luồng byte, không tự giữ ranh giới giữa các tin nhắn. Thống nhất quy tắc framing chung: 
1. Chuyển JSON thành chuỗi và mã hóa thành byte UTF-8.
2. Tính độ dài dữ liệu JSON theo byte, không theo ký tự
3. Chuyển độ dài thành số nguyên không dấu 4 byte theo thứ tự byte big-endian
4. Gửi 4 byte độ dài, sau đó gửi dữ liệu JSON 
5. Phía nhận phải đọc đủ 4 byte độ dài trước
6. Sau đó, phía nhận đọc đúng số byte đã được khai báo để tạo thành một thông điệp hoàn chỉnh
7. Cần quy định giới hạn kích thước thông điệp để tránh cấp phát bộ nhớ quá lớn
8. Nếu kết nối đóng giữa chừng, dữ liệu sai định dạng hoặc độ dài không hợp lệ, ứng dụng phải xử lý lỗi và không bị crash

