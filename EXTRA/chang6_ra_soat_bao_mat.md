# Chặng 6: Rà soát bảo mật và kiểm thử chịu lỗi (TV1)

Phạm vi: rà soát bảo mật source code Python, đảm bảo khóa không lộ trong Traceback, kiểm thử dữ liệu rác, rút mạng, kill process đột ngột và giải phóng tài nguyên.

## 1. Cách chạy

Trong venv, ở thư mục gốc của repo:

```powershell
python tests/audit_source.py CODE        # rà soát tĩnh toàn bộ CODE, in bảng phát hiện
python -m pytest tests -q                # toàn bộ test (gồm rà soát, khóa không lộ, chịu lỗi)
python -m pytest tests/test_resilience.py -v
```

`audit_source.py` thoát với mã 1 nếu có phát hiện mức HIGH.

## 2. Rà soát bảo mật mã nguồn

Công cụ `tests/audit_source.py` đọc cây cú pháp (AST) của từng file `.py` và tìm:

| Mức | Quy tắc |
|---|---|
| HIGH | Khóa riêng viết cứng trong code; `eval`, `exec`, `pickle.load`, `os.system`, `subprocess(shell=True)`, `breakpoint`; `capture_locals=True`; đưa biến nhạy cảm (`session_key`, `private_key`, `password`...) vào `print`, `log`, hay thông báo `raise` |
| MEDIUM | `except:` trần; nuốt lỗi im lặng (`except Exception: pass` không có `noqa`); dùng `random` trong module bảo mật; `socket`/`open` không dùng `with` và không có `close()` |
| LOW | `assert` trong mã chạy thật; in nội dung tin nhắn ra màn hình |

`test_security_audit.py` kiểm tra chính công cụ (15 mẫu mã xấu phải bị bắt, 7 mẫu mã tốt phải qua) rồi áp dụng lên `CODE/`: module bảo mật và `logger.py` phải sạch HIGH và MEDIUM, toàn bộ `CODE/` phải sạch HIGH, repo không được có file khóa `.pem/.key/.p12/.pfx`.

**Kết quả trên các file mình có:** HIGH = 0, MEDIUM = 0, LOW = 1 (`server.py` in nội dung tin nhận được ra console, hành vi hiển thị bình thường).

**Giới hạn:** mình chỉ rà soát được các file đã có trong tay (`client.py`, `server.py`, `logger.py`, `CODE/security/`). Mã GUI, truyền file và `shared/protocol.py` của các bạn khác chưa được rà soát. Chạy `python tests/audit_source.py CODE` trên repo đầy đủ để có kết quả thật. Công cụ tìm theo mẫu, không thay thế việc đọc code.

## 3. Khóa không lộ trong Traceback

"Lộ trong Traceback" nghĩa là giá trị khóa xuất hiện khi Traceback được in kèm giá trị biến cục bộ (`pytest --showlocals`, `traceback` với `capture_locals=True`, các trang lỗi debug). Python mặc định không làm vậy, nhưng chỉ cần một công cụ bật lên là khóa hiện ra.

**Phát hiện:** trước khi sửa, khi `SessionCrypto` hoặc `decrypt_session_key` lỗi, khóa phiên và khóa vừa giải mã hiện nguyên giá trị trong phần biến cục bộ.

**Cách sửa:** mọi khóa (khóa phiên, khóa hai chiều, khóa file, khóa RSA vừa giải mã) được gói trong `SecretBytes`, một kiểu `bytes` mà `repr`, `str`, `print`, f-string chỉ hiện `<SecretBytes len=32>`, và không thể `pickle` hay `copy` (tránh vô tình ghi khóa ra đĩa). Vẫn dùng như `bytes` thường.

**Kiểm chứng:** `tests/test_secret_hygiene.py` (10 test) gây lỗi ở 4 nơi giữ khóa (SessionCrypto, giải mã khóa phiên, ChunkCrypto, bắt tay bị peer bỏ giữa chừng) rồi soi mọi biến cục bộ và thuộc tính của các frame trong `CODE/`, tìm khóa ở 4 dạng (bytes, hex, base64, danh sách số). Có một test đối chứng chứng minh bộ dò bắt được khóa nằm trong biến bytes thường. Khi thử gỡ phần che khóa ra, 5 test lập tức fail, nên các test này có hiệu lực.

**Giới hạn:** nếu code chủ động gọi `.hex()` hay base64 trên khóa rồi in ra thì vẫn lộ, đó là lỗi của người viết, và quy tắc `secret-in-log` của công cụ rà soát sẽ bắt khi tên biến nhạy cảm đi vào `print/log`. Khóa RSA riêng nằm trong đối tượng của thư viện `cryptography` (repr không chứa khóa).

## 4. Kiểm thử chịu lỗi tự động

`tests/test_resilience.py` chạy máy chủ mẫu (`tests/resilience_hub.py`) ở một **tiến trình riêng** rồi tấn công bằng các cách có thật. Sau mỗi tình huống: máy chủ còn sống, không in Traceback, và vẫn phục vụ được kết nối mới.

| Mã | Tình huống | Kỳ vọng |
|---|---|---|
| RS-01 | Kill -9 một peer đang gửi dữ liệu lớn (giữa khung) | Đóng sạch, ghi `peer_disconnected`, không còn kết nối ESTABLISHED |
| RS-02 | Nối rồi đóng ngay | `handshake_failed` |
| RS-03 | Đặt lại kết nối (RST) giữa lúc bắt tay | `handshake_failed` |
| RS-04 | RST sau khi bắt tay xong | `peer_disconnected` |
| RS-05 | Peer nối vào rồi im lặng | Hết thời gian bắt tay, không treo vô hạn |
| RS-06 | 4096 byte ngẫu nhiên thay cho bắt tay | `handshake_failed` |
| RS-07 | Khung hợp lệ về độ dài nhưng nội dung rác sau bắt tay | `decrypt_fail` |
| RS-08 | Khung khai báo dài 4 GB | `protocol_error`, không cấp phát bộ nhớ |
| RS-09 | Gói mã hóa đúng nhưng không phải JSON | `bad_message` |
| RS-10 | Tin thiếu hoặc sai kiểu `text`, loại tin lạ | Bỏ qua, kết nối sống tiếp |
| RS-11 | Gửi lại gói cũ (phát lại) | `decrypt_fail`, chỉ đóng kết nối đó |
| RS-12 | 40 lần ngắt đột ngột liên tiếp | Số handle/fd, luồng không tăng, không còn ESTABLISHED |
| RS-13 | 24 máy khách phá hoại chạy song song | Máy chủ sống, đủ 24 kết nối được đóng |
| RS-14 | Bật TCP keepalive | `SO_KEEPALIVE` bật, đúng tham số trên Linux |

Ngoài bộ test, mình chạy thật `server.py` và `client.py` mới (với `shared/protocol.py` giả) qua 6 tình huống: client bị kill giữa chat, rác sau bắt tay, tin thiếu trường `text`, rác thay cho bắt tay, phát lại gói, server bị kill khi client đang chờ. Cả 6 đều không Traceback, dọn sạch rồi thoát. Làm lại trên repo thật khi có `shared/protocol.py` thật.

## 5. Kiểm thử thủ công (phần tự động không làm được)

| Mã | Kịch bản | Kỳ vọng | Kết quả |
|---|---|---|---|
| MT-01 | Đang chat, rút cáp mạng hoặc tắt Wi-Fi của một máy | Trong khoảng 20 giây bên kia báo ngắt kết nối, không treo, ứng dụng không sập | |
| MT-02 | Bật lại mạng sau MT-01 | Không sập; tạo được kết nối mới | |
| MT-03 | Đang gửi file lớn, kill ứng dụng bằng Task Manager (End task) | Bên kia báo lỗi, file dở không bị coi là hoàn tất, file tạm được dọn | |
| MT-04 | Nhấn Ctrl+C khi chạy bản console | Thoát gọn, không Traceback | |
| MT-05 | Đóng cửa sổ GUI giữa lúc đang truyền | Luồng nền dừng, tiến trình thoát hẳn (không còn trong Task Manager) | |
| MT-06 | Gửi rác bằng PowerShell (lệnh dưới) vào cổng đang nghe | Ứng dụng báo lỗi bắt tay, không sập | |
| MT-07 | Mở `logs/*/app.log` sau các thử nghiệm trên | Không có khóa, không có nội dung tin nhắn | |
| MT-08 | Chat và ngắt kết nối 50 lần, theo dõi Task Manager | Bộ nhớ, handle, luồng không tăng dần | |

Gửi rác bằng PowerShell:

```powershell
$c = New-Object System.Net.Sockets.TcpClient("127.0.0.1", 5000)
$s = $c.GetStream(); $b = New-Object byte[] 2000
(New-Object Random).NextBytes($b); $s.Write($b, 0, $b.Length); $c.Close()
```

## 6. Khuyến nghị cho code Socket và GUI của nhóm

1. **Bắt đủ loại lỗi mạng.** Khi mất mạng, Windows có thể ném `TimeoutError` (không phải `ConnectionError`), nên bắt `(ConnectionError, TimeoutError)` rồi `OSError`. `client.py` và `server.py` đã sửa theo cách này.
2. **Một kết nối hỏng không được làm sập tất cả.** Mẫu chuẩn là `serve_one()` trong `tests/resilience_hub.py`: `try ... except ... finally: conn.close()`, mỗi kết nối một luồng.
3. **Đóng socket trong `finally`** ở luồng QThread, và dừng luồng khi đóng cửa sổ.
4. **Dùng `enable_keepalive(sock)`** (`security/netutil.py`) sau khi kết nối để phát hiện peer chết ngầm. Trên Windows số lần thăm dò cố định nên thời gian phát hiện khác Linux, cần đo thực tế (MT-01).
5. **Không in Traceback cho người dùng cuối**, chỉ ghi loại lỗi vào log (có sẵn trong `client.py`, `server.py` mới).
6. **Kiểm tra dữ liệu nhận được** trước khi truy cập (`.get`, `isinstance`) thay vì `message["payload"]["text"]`.

## 7. Mẫu báo cáo

| Hạng mục | Tổng | Pass | Fail | Chưa chạy |
|---|---|---|---|---|
| Tự động (`pytest tests`) | | | | |
| Thủ công (MT-01 đến MT-08) | 8 | | | |

Nhật ký lỗi (mỗi lỗi một Issue trên GitHub):

| Mã lỗi | Mã test | Mô tả | Bước tái hiện | Người phụ trách | Trạng thái |
|---|---|---|---|---|---|
| | | | | | |
