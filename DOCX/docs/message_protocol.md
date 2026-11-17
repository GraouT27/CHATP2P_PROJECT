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
| Field |  Type | Required | Description |
|---|---|---|---|
| `message_id` | String | Yes | ID duy nhất của thông điệp |
| `message_type` | String | Yes | Loại thông điệp |
| `sender_id` | String | Yes | ID của peer gửi thông điệp hiện tại |
| `receiver_id` | String | Yes | ID của peer nhận thông điệp |
| `timestamp` | String | Yes | Thời điểm tạo thông điệp theo UTC |

Quy tắc:
- message_id được tạo bằng UUID
- message_type phải thuộc danh sách loại thông điệp được hỗ trợ 
- sender_id và receiver_id là ID của peer trong ứng dụng, không phải địa chỉ IP
- timestamp: sử dụng thời gian UTC

## 2. Danh sách message type
| Message type | Mục đích |
|---|---|
| `TEXT` | Gửi tin nhắn văn bản |
| `EMOJI` | Gửi emoji |
| `REPLY` | Trả lời một thông điệp cụ thể |
| `FORWARD` | Chuyển tiếp thông điệp |
| `FILE` | Trao đổi metadata và trạng thái truyền file |
| `KEY_EXHCHANGE` | Trao đổi thông tin mã hóa | 

## 3. Payload 
### 3.1. TEXT 
| Field | Type | Required | Description |
|---|----|---|---|
| `text` | String | YES | Nội dung tin nhắn | 

Ví dụ payload: 
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
### 3.2. EMOJI
| Field | Type | Required | Description |
|---|---|---|---|
| `emoji` | String | Yes | Nội dung tin nhắn |

Ví dụ payload: 
```json 
  "payload":{
    "emmoji": "😂"
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

### 3.5. FILE
| Field | Type | Required | Description |
|---|---|---|---|
| `action` | String | Yes | Loại thao tác truyền tệp, ví dụ: OFFER, ACCEPT, REJECT, COMPLETE, ERROR |
| `transfer_id` | String | Yes | ID duy nhất của phiên truyền file |
| `file_name` | String | Yes ( dùng cho OFFER ) | Tên file |
| `file_size` | Integer | Yes (dùng cho OFFER) | Kích thước file tính bằng bytes |
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

### 3.6. KEY_EXCHANGE 
| Field | Type | Description |
|---|---|---|
| `action` | String | Hành động trao đổi khóa |
| `algorithm` | String | Thuật toán sử dụng |
| `key_id` | String | ID của khóa |
| `public_key` | String | Khóa công khai |
| `encryted_session_key` | String | Khóa đã mã khóa | 

Ví dụ payload - gửi khóa công khai:
```json
{
  "action": "PUBLIC_KEY",
  "algorithm": "RSA",
  "key_id": "key-peer-A-001",
  "public_key": "NOI_DUNG_KHOA_CONG_KHAI"
}
```
Ví dụ payload - gửi khóa đã được mã hóa:
```json
{
  "action": "SESSION_KEY",
  "algorithm": "RSA-OAEP-SHA256",
  "key_id": "key-peer-B-001",
  "encrypted_session_key": "BASE64_ENCODED_CIPHERTEXT"
}
```
Quy tắc:
-  Chỉ chia sẻ khóa công khai, không gửi khóa riêng RSA qua mạng 
-  Khi dùng RSA-OAEP, phải sử dụng thư viện mật mã đáng tin cậy và tham số tương thích ở hai phía
-  Khóa AES-256 phải được tạo bằng bộ sinh số ngẫu nhiên an toàn
-  Không gửi khóa AES ở dạng văn bản thuần
-  Cần xác thực khóa công khai của peer để giảm nguy cơ tấn công trung gian

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

