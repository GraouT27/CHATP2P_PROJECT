# Kiểm thử Avatar và Emoji trên nhiều tiến trình Peer (Chặng 4, TV1)

## 1. Phần tự động (đã có trong `tests/`)

Chạy trong venv: `python -m pytest tests/test_multiprocess_peers.py -v`

Mỗi lần chạy khởi động **8 tiến trình Python độc lập** (4 cặp peer) cùng lúc. Mỗi cặp: bắt tay RSA, trao 10 tin emoji, rồi gửi avatar PNG cho nhau (chia chunk 4 KB, mã hóa từng chunk, gửi 4 luồng, thứ tự xáo trộn). Kiểm tra dữ liệu nhận về giống hệt dữ liệu gốc, khóa mỗi tiến trình khác nhau, log không lộ bí mật.

Phần này chỉ kiểm tra **đường truyền và mã hóa**. Việc hiển thị trên giao diện (mục 2) phải kiểm tra bằng tay.

## 2. Phần kiểm tra bằng tay trên GUI

Chuẩn bị: mở 3 cửa sổ ứng dụng (3 tiến trình Peer) trên một máy, hoặc 2 máy cùng LAN, mỗi peer đặt một avatar khác nhau.

| Mã | Kiểm thử | Kỳ vọng | Kết quả |
|---|---|---|---|
| AV-01 | Peer A đặt avatar, B kết nối | B thấy avatar của A ở danh sách peer và khung chat | |
| AV-02 | A đổi avatar khi đang chat | B cập nhật avatar mới, không phải kết nối lại | |
| AV-03 | A, B, C cùng chat, cả 3 có avatar khác nhau | Mỗi tin hiện đúng avatar của người gửi | |
| AV-04 | Avatar nhỏ (dưới 10 KB) và lớn (khoảng 1 MB) | Cả hai hiển thị, ảnh lớn được thu nhỏ, giao diện không đơ | |
| AV-05 | File avatar hỏng hoặc không phải ảnh | Hiện avatar mặc định, ứng dụng không sập | |
| AV-06 | Ngắt mạng giữa lúc đang gửi avatar | Hiện avatar mặc định, không treo, có ghi log lỗi | |
| EM-01 | Gửi emoji đơn: 😀 😂 ❤️ 👍 | Hiển thị đúng ở máy gửi và máy nhận | |
| EM-02 | Emoji tổ hợp: 👍🏽 (tông da), 👨‍👩‍👧‍👦 (ghép bằng ZWJ) | Hiển thị thành 1 biểu tượng, không vỡ thành nhiều ký tự | |
| EM-03 | Cờ 🇻🇳 | Lưu ý: Windows thường hiện chữ "VN" thay vì lá cờ, ghi nhận là giới hạn của hệ điều hành | |
| EM-04 | Tin trộn chữ tiếng Việt có dấu và emoji | Hiển thị đủ, không lỗi font | |
| EM-05 | 50 emoji liên tiếp, và emoji trong tin REPLY, FORWARD | Hiển thị đủ, khung chat tự xuống dòng | |
| EM-06 | A, B, C cùng gửi emoji liên tục | Không mất tin, không lẫn thứ tự, không đơ giao diện | |
| EM-07 | Chọn emoji từ bảng emoji trong ứng dụng | Emoji vào ô soạn tin và gửi đúng | |

## 3. Ghi chú khi gặp lỗi hiển thị

- **Emoji hiện ô vuông trống:** thêm font `Segoe UI Emoji` vào danh sách `font-family` trong QSS (Windows) để Qt tìm được font có emoji.
- **Avatar bị méo:** đặt kích thước cố định và dùng `Qt.KeepAspectRatioByExpanding` khi thu nhỏ.
- **Giao diện đơ khi nhận avatar lớn:** giải mã và dựng ảnh trong luồng nền (QThread), chỉ cập nhật giao diện qua signal.
- Nhóm nên đặt giới hạn kích thước avatar (ví dụ 256 KB) và kiểm tra ảnh hợp lệ trước khi hiển thị.

## 4. Báo cáo lỗi

Ghi lỗi theo **Test Cases Template** của nhóm (mã test, bước tái hiện, kết quả thực tế, ảnh chụp) và gửi người phụ trách giao diện. Kèm file log của peer lúc lỗi: log đã lọc khóa và nội dung tin nên gửi được.
