# Functional Test các chức năng bắt buộc (Chặng 5, TV1)

Phạm vi: Reply, Forward, Avatar, Emoji, Truyền File và tính đúng đắn của giải mã AES-256.
Chia hai phần: **kiểm thử tự động** (chạy bằng `pytest`, kiểm tra giao thức và mã hóa) và **kiểm thử thủ công trên GUI** (kiểm tra hiển thị và thao tác).

## 1. Cách chạy phần tự động

Trong venv, ở thư mục gốc của repo:

```powershell
python -m pytest tests -q            # toàn bộ
python -m pytest tests/test_functional_e2e.py -v   # chức năng đầu-cuối
python -m pytest tests/test_aes_correctness.py -v  # AES-256
```

Các file kiểm thử:

| File | Nội dung |
|---|---|
| `tests/qa_helpers.py` | Công cụ dùng chung: `validate_message` (kiểm tra thông điệp theo `message_protocol.md`), tạo thông điệp mẫu, truyền file chia chunk, tạo và kiểm tra ảnh PNG |
| `tests/test_qa_spec.py` | Kiểm tra chính bộ kiểm tra thông điệp (thông điệp đúng thì qua, sai thì bị chặn) |
| `tests/test_functional_e2e.py` | Chức năng đầu-cuối trên kênh thật: bắt tay RSA rồi mã hóa AES-256-GCM |
| `tests/test_aes_correctness.py` | Vector chuẩn NIST, giải mã độc lập, tính chất an toàn |

`validate_message(msg)` dùng được với thông điệp thật của ứng dụng: khi code của nhóm tạo ra thông điệp, truyền vào hàm này, danh sách trả về rỗng nghĩa là đúng giao thức.

## 2. Bảng kiểm thử tự động

Cột **Kết quả** điền sau khi chạy trên máy của bạn (Pass/Fail).

### 2.1. Emoji và Text
| Mã | Kiểm thử | Test | Kết quả |
|---|---|---|---|
| FN-TXT-01 | Tin có dấu tiếng Việt, xuống dòng, emoji, 20.000 ký tự đến nguyên vẹn qua kênh mã hóa | `test_fn_txt_01_unicode_text_intact` | |
| FN-EMO-01 | 45 emoji (gồm ZWJ, tông da, cờ, 50 emoji liền) đúng nguyên văn và đúng thứ tự | `test_fn_emo_01_emoji_exact_and_ordered` | |

### 2.2. Reply
| Mã | Kiểm thử | Test | Kết quả |
|---|---|---|---|
| FN-REP-01 | Reply tham chiếu `reply_to_message_id`, tra lại được nội dung tin gốc, reply có `message_id` mới | `test_fn_rep_01_reply_resolves_original` | |
| FN-REP-02 | Chuỗi reply 3 cấp, mỗi tin trỏ đúng tin ngay trước | `test_fn_rep_02_reply_chain` | |
| FN-REP-03 | Reply thiếu ID, ID sai, tự trả lời chính mình bị chặn | `test_reply_rules` | |

### 2.3. Forward
| Mã | Kiểm thử | Test | Kết quả |
|---|---|---|---|
| FN-FWD-01 | A gửi B, B chuyển tiếp C: giữ `original_message_id`, `original_sender_id`, `original_payload`, tin mới có `message_id` mới | `test_fn_fwd_01_forward_text_to_other_peer` | |
| FN-FWD-02 | Chuyển tiếp tin emoji và tin reply giữ nguyên nội dung | `test_fn_fwd_02_forward_emoji_and_reply` | |
| FN-FWD-03 | Chuyển tiếp tin đã chuyển tiếp vẫn trỏ về tin gốc đầu tiên | `test_fn_fwd_03_forward_of_forward_keeps_first_original` | |
| FN-FWD-04 | Thiếu trường gốc, loại thông điệp không được phép, trùng `message_id` bị chặn | `test_forward_rules` | |

### 2.4. Truyền file
| Mã | Kiểm thử | Test | Kết quả |
|---|---|---|---|
| FN-FIL-01 | File 0, 1, 16383, 16384, 16385, 100.000 byte: nhận đủ, SHA-256 trùng, tên có dấu giữ nguyên | `test_fn_fil_01_sizes_roundtrip` | |
| FN-FIL-02 | File 2 MiB, 8 luồng, thứ tự chunk xáo trộn: SHA-256 trùng | `test_fn_fil_02_large_file_multithread` | |
| FN-FIL-03 | Một chunk bị sửa giữa đường: bị phát hiện, không ghép thành file | `test_fn_fil_03_tampered_chunk_detected` | |
| FN-FIL-04 | Thiếu một chunk rồi ngắt kết nối: phát hiện file chưa đủ | `test_fn_fil_04_missing_chunk_detected` | |
| FN-FIL-05 | Chunk của lần truyền khác chèn vào: bị từ chối | `test_fn_fil_05_chunks_of_other_transfer_rejected` | |
| FN-FIL-06 | OFFER có tên file `../../evil.exe`: bị từ chối | `test_fn_fil_06_bad_offer_rejected`, `test_file_offer_rules` | |

### 2.5. Avatar
| Mã | Kiểm thử | Test | Kết quả |
|---|---|---|---|
| FN-AVT-01 | Avatar PNG gửi qua kênh mã hóa đến nguyên vẹn, đọc lại đúng kích thước | `test_fn_avt_01_png_roundtrip` | |
| FN-AVT-02 | Dữ liệu không phải ảnh, ảnh bị cắt, ảnh sai CRC bị phát hiện (để hiện avatar mặc định) | `test_fn_avt_02_non_image_is_rejected_by_check` | |
| FN-AVT-03 | Avatar bị sửa giữa đường không bao giờ được giao | `test_fn_avt_03_tampered_avatar_never_delivered` | |
| FN-AVT-04 | 4 cặp, 8 tiến trình Python chạy cùng lúc trao emoji và avatar | `tests/test_multiprocess_peers.py` | |

### 2.6. AES-256
| Mã | Kiểm thử | Test | Kết quả |
|---|---|---|---|
| FN-AES-01 | 4 vector chuẩn NIST (McGrew và Viega, Test Case 13 đến 16) cho AES-256-GCM | `test_aes01_nist_known_answer` | |
| FN-AES-02 | Gói do ứng dụng tạo giải mã được bằng AES thô độc lập, và ngược lại (đúng định dạng thiết kế) | `test_aes03`, `test_aes04`, `test_aes06` | |
| FN-AES-03 | Sửa bất kỳ byte nào (seq, nonce, bản mã, tag) đều bị phát hiện | `test_aes09_every_byte_flip_is_detected` | |
| FN-AES-04 | Cắt hoặc nối thêm gói bị từ chối; sai khóa hoặc sai salt bị từ chối | `test_aes10`, `test_aes13` | |
| FN-AES-05 | Nonce không trùng trong 2000 lần mã hóa; cùng nội dung cho bản mã khác nhau | `test_aes11_nonce_unique_and_same_plaintext_differs` | |
| FN-AES-06 | Khóa phiên phải 32 byte; khóa phiên ngẫu nhiên; RSA-OAEP bọc và mở khóa đúng | `test_aes14`, `test_aes15`, `test_aes16` | |
| FN-AES-07 | Bản mã không chứa nội dung gốc; trên đường truyền (trạm nghe ghi mọi byte) không thấy nội dung tin và file | `test_aes12`, `test_fn_sec_01_nothing_readable_on_the_wire` | |
| FN-AES-08 | Mọi kích thước dữ liệu (0 đến 5 MiB) mã hóa rồi giải mã đúng | `test_aes07`, `test_aes08` | |

## 3. Kiểm thử thủ công trên GUI

Phần này kiểm tra những gì chương trình tự động không thấy: hiển thị và thao tác. Làm khi các thành viên GUI và truyền file đã tích hợp xong.

Chuẩn bị: mở 3 cửa sổ ứng dụng (3 peer) trên một máy, hoặc 2 máy cùng LAN. Avatar và Emoji xem `EXTRA/test_avatar_emoji.md`.

### 3.1. Reply
| Mã | Kịch bản | Kỳ vọng | Kết quả |
|---|---|---|---|
| RP-01 | Chọn tin của đối phương, bấm Reply, soạn và gửi | Tin mới có khung trích dẫn nội dung tin gốc, cả hai bên đều thấy | |
| RP-02 | Reply tin của chính mình | Như trên | |
| RP-03 | Reply tin emoji | Khung trích dẫn hiện đúng emoji | |
| RP-04 | Reply tin rất dài (hơn 500 ký tự) | Trích dẫn được cắt gọn, giao diện không vỡ | |
| RP-05 | Reply 3 cấp liên tiếp | Mỗi tin trích đúng tin ngay trước | |
| RP-06 | Reply khi đối phương vừa ngắt kết nối | Báo lỗi gửi, không sập | |
| RP-07 | Mở lại ứng dụng rồi xem tin reply có tin gốc không còn trong lịch sử | Hiện "tin gốc không khả dụng", không sập | |

### 3.2. Forward
| Mã | Kịch bản | Kỳ vọng | Kết quả |
|---|---|---|---|
| FW-01 | Chọn tin, bấm Forward, chọn peer khác | Peer nhận thấy nhãn chuyển tiếp, tên người gửi gốc, nội dung đúng | |
| FW-02 | Forward sang cuộc trò chuyện khác | Hiển thị đúng | |
| FW-03 | Forward tin emoji và tin reply | Giữ nguyên nội dung | |
| FW-04 | Forward tin đã forward | Nhãn vẫn ghi người gửi gốc đầu tiên (cần nhóm xác nhận quy tắc này) | |
| FW-05 | Forward khi peer đích offline | Báo lỗi, không sập | |
| FW-06 | Forward liên tiếp cho nhiều peer | Mỗi peer nhận đúng một lần | |

### 3.3. Truyền file
SHA-256 một file trên Windows: `Get-FileHash <đường dẫn> -Algorithm SHA256`.

| Mã | Kịch bản | Kỳ vọng | Kết quả |
|---|---|---|---|
| FL-01 | Gửi file nhỏ (dưới 1 MB) bằng nút chọn file | Nhận đủ, SHA-256 trước và sau trùng | |
| FL-02 | Gửi file lớn (từ 100 MB) | Thanh tiến trình chạy, giao diện không đơ, SHA-256 trùng | |
| FL-03 | Kéo thả file vào cửa sổ chat | Bắt đầu gửi | |
| FL-04 | Gửi nhiều file liên tiếp (hàng đợi) | Trạng thái từng file đúng, tất cả nhận đủ | |
| FL-05 | Hủy giữa chừng | Dừng, file tạm được dọn, không sập | |
| FL-06 | Rút mạng hoặc tắt peer giữa lúc gửi | Báo lỗi, không sập, file dở không bị coi là hoàn tất | |
| FL-07 | File 0 byte | Gửi và nhận đúng | |
| FL-08 | Tên file có dấu tiếng Việt, khoảng trắng, ký tự đặc biệt | Lưu đúng tên | |
| FL-09 | Nhận file trùng tên file đã có | Tạo tên mới hoặc hỏi xác nhận, không ghi đè lặng lẽ | |
| FL-10 | Gửi file có tên chứa `..` hoặc đường dẫn | Bị từ chối hoặc làm sạch, không ghi ra ngoài thư mục nhận | |
| FL-11 | Hai peer gửi file cho nhau cùng lúc | Cả hai hoàn tất, SHA-256 trùng | |

### 3.4. AES-256 trên mạng thật
| Mã | Kịch bản | Kỳ vọng | Kết quả |
|---|---|---|---|
| AE-01 | Wireshark: chọn card mạng (cùng máy thì chọn *Adapter for loopback traffic capture*), lọc `tcp.port == 5000`, chat và gửi file, chọn *Follow TCP Stream* | Sau phần bắt tay, không đọc được nội dung tin nhắn hay file | |
| AE-02 | Xem vân tay hiện ở hai bên sau bắt tay | Hai chuỗi vân tay của cùng một khóa giống nhau trên hai máy | |
| AE-03 | Mở `logs/app.log` sau buổi chat | Không có khóa, không có nội dung tin nhắn | |

## 4. Những điểm không nhất quán phát hiện trong giao thức

Khi viết bộ kiểm tra, các điểm sau cần nhóm thống nhất:

| # | Phát hiện | Đề xuất |
|---|---|---|
| 1 | Lỗi chính tả trong `message_protocol.md`: `KEY_EXHCHANGE`, `encryted_session_key`, `emmoji` | Sửa lại |
| 2 | Bảng ghi `action` của FILE là `OFFER`, `ACCEPT`... nhưng ví dụ ghi `FILE_OFFER`. Bộ kiểm tra chỉ chấp nhận tên trong bảng | Chọn một cách |
| 3 | Chưa có loại thông điệp cho Avatar và cho chunk file | Thêm `AVATAR`, `FILE_CHUNK` hoặc quy định dùng chung FILE |
| 4 | Forward của tin đã forward: bộ kiểm tra giả định giữ tin gốc đầu tiên | Nhóm xác nhận |
| 5 | File 0 byte: bộ kiểm tra giả định `total_chunks = 1` với một chunk rỗng | Nhóm xác nhận |
| 6 | Khung chunk hiện gửi dạng JSON ngoài lớp mã hóa phiên, nên `transfer_id` và số thứ tự chunk hiện trên đường truyền (không phải bí mật), còn dữ liệu đã mã hóa | Ghi nhận, chấp nhận được |

## 5. Mẫu báo cáo kết quả

| Hạng mục | Tổng | Pass | Fail | Chưa chạy |
|---|---|---|---|---|
| Tự động (`pytest tests`) | | | | |
| Thủ công: Reply | 7 | | | |
| Thủ công: Forward | 6 | | | |
| Thủ công: Truyền file | 11 | | | |
| Thủ công: Avatar và Emoji (`test_avatar_emoji.md`) | 13 | | | |
| Thủ công: AES-256 | 3 | | | |

**Nhật ký lỗi** (mỗi lỗi một dòng, kèm một Issue trên GitHub):

| Mã lỗi | Mã test | Mô tả | Bước tái hiện | Người phụ trách | Trạng thái |
|---|---|---|---|---|---|
| | | | | | |
