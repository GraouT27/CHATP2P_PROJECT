# Chặng 7: Kiểm thử hiệu năng (Stress Test & Performance Test 2 mức tải) (TV1)

Yêu cầu: script `benchmark_stress.py` tự động chạy Stress Test và Performance Test ở 2 mức tải và đo tốc độ AES-256.

| | Số peer | Tốc độ tin nhắn (tổng) | File |
|---|---|---|---|
| Mức 1 | 5 | 50 tin/giây | 10 MB |
| Mức 2 | 15 | 200 tin/giây | 100 MB |

## 1. Cách chạy

Trong venv, ở thư mục gốc của repo (cần `psutil`, đã có trong `requirements.txt`):

```powershell
python tests/benchmark_stress.py                 # AES + cả 2 mức tải (khoảng 2 đến 4 phút)
python tests/benchmark_stress.py --level 1       # chỉ Mức 1
python tests/benchmark_stress.py --level 2       # chỉ Mức 2
python tests/benchmark_stress.py --aes-only      # chỉ đo tốc độ AES-256 (khoảng 20 giây)
python tests/benchmark_stress.py --quick         # bản thu nhỏ để kiểm tra script chạy được
```

Trong lúc chạy hãy **đóng bớt các ứng dụng nặng** (trình duyệt nhiều tab, Zoom, Meet) và **cắm điện** nếu dùng laptop, nếu không số liệu sẽ thấp và dao động.

Kết quả lưu ở `benchmark_results/benchmark_<ngày_giờ>.md` (bản báo cáo đã định dạng, dán thẳng vào báo cáo) và `.json` (số liệu thô). Nên thêm `benchmark_results/` vào `.gitignore` rồi chỉ sao chép bản `.md` chọn lọc vào `EXTRA/` làm bằng chứng. Script thoát với mã 1 nếu có mức không đạt.

Các tùy chọn đổi ngưỡng và cấu hình: `--min-duration 30` (giây giữ tải tin nhắn), `--threads 8` (số luồng mã hóa chunk), `--max-p95-ms 300`, `--max-loss-percent 0`, `--payload 128` (kích thước mỗi tin), `--skip-aes`.

## 2. Script đo như thế nào

Mỗi mức tải khởi chạy:

- **1 máy chủ mẫu** (1 tiến trình), nhận tin và gửi lại nguyên văn (echo), nhận file.
- **N tiến trình peer** (mỗi peer một tiến trình Python riêng): bắt tay RSA thật, rồi gửi tin nhắn mã hóa AES-256-GCM với tốc độ cố định, đo độ trễ khứ hồi của từng tin. Tổng tốc độ chia đều cho các peer (Mức 2: 200 chia 15, khoảng 13,3 tin/giây mỗi peer).
- **1 kết nối riêng truyền file**, chia chunk 64 KiB, mã hóa từng chunk bằng `ChunkCrypto` (nhiều luồng), **lặp lại liên tục** suốt thời gian chịu tải (ít nhất 1 lần), mỗi lần kiểm SHA-256 phía máy chủ.
- Một luồng lấy mẫu CPU và RAM (psutil) mỗi 0,5 giây.

Phần đo AES gồm: tốc độ mã hóa và giải mã `SessionCrypto` (tin nhắn) và `ChunkCrypto` (chunk file) theo các kích thước 64 B đến 1 MiB, so với AESGCM thô của thư viện để thấy chi phí của lớp bảo mật; mã hóa và giải mã cả file 10 MB và 100 MB (một luồng và nhiều luồng); thời gian sinh khóa RSA-2048 và bắt tay.

## 3. Tiêu chí ĐẠT

Các ngưỡng này **do mình đề xuất, nhóm không quy định**, có thể đổi bằng cờ dòng lệnh.

| Tiêu chí | Điều kiện ĐẠT |
|---|---|
| `khong_loi_ket_noi` | Không peer nào lỗi kết nối, máy chủ còn sống đến cuối |
| `khong_mat_tin` | Tỷ lệ mất tin không quá 0% (mặc định) |
| `tre_p95_dat` | Độ trễ khứ hồi p95 không quá 500 ms (mặc định) |
| `dat_toc_do_gui` | Tốc độ gửi thực tế đạt ít nhất 90% mục tiêu |
| `file_sha256_dung` | Mọi lần truyền file đều khớp SHA-256 |

## 4. Giới hạn cần nói thật khi báo cáo

1. **Chạy trên một máy qua loopback**, không qua card mạng, nên không phản ánh độ trễ và băng thông của LAN hay Wi-Fi thật. Tốc độ truyền file ở đây bị giới hạn bởi CPU và Python, không bởi mạng.
2. **Đo lớp bảo mật của TV1** (bắt tay RSA, AES-256-GCM) với **định dạng chunk riêng của script**, không phải giao thức truyền file hay giao diện thật của ứng dụng. Muốn đo ứng dụng thật thì làm các test thủ công ở mục 6.
3. Máy chủ mẫu là mô hình gần với ứng dụng nhưng không phải `p2p_node/` thật.
4. 17 tiến trình (1 máy chủ, 15 peer, 1 kết nối file) cùng tranh CPU trên một máy, nên Mức 2 thể hiện cả sức tải của máy đang chạy thử. Ghi rõ cấu hình máy (script tự ghi vào báo cáo).
5. Đo tốc độ phụ thuộc phiên bản Python, thư viện `cryptography` và phần cứng (AES-NI). Con số của máy này không so sánh được với máy khác nếu không kèm cấu hình.

## 5. Mẫu bảng kết quả (điền bằng số đo trên máy của bạn)

| Chỉ số | Mức 1 | Mức 2 |
|---|---|---|
| Tin gửi / nhận / mất | | |
| Tốc độ gửi đạt được (tin/giây) | | |
| Độ trễ p50 / p95 / p99 / max (ms) | | |
| Truyền file: số lần, MiB/s trung bình, chậm nhất | | |
| Tốc độ mã hóa thực / giải mã thực (MiB/s) | | |
| CPU máy chủ trung bình / cao nhất (% của 1 nhân) | | |
| RAM đỉnh máy chủ / tổng peer (MiB) | | |
| Kết quả | | |

| Tốc độ AES-256-GCM (MiB/s) | Mã hóa | Giải mã |
|---|---|---|
| SessionCrypto 1 KiB | | |
| SessionCrypto 64 KiB | | |
| ChunkCrypto 64 KiB | | |
| File 10 MB (1 luồng / nhiều luồng) | | |
| File 100 MB (1 luồng / nhiều luồng) | | |

## 6. Kiểm thử hiệu năng thủ công trên ứng dụng thật

| Mã | Kịch bản | Cách đo | Kết quả |
|---|---|---|---|
| PF-01 | Gửi file 10 MB giữa 2 peer của ứng dụng (2 máy cùng LAN) | Đồng hồ bấm giờ, tính MiB/s; SHA-256 trước và sau (`Get-FileHash <file> -Algorithm SHA256`) | |
| PF-02 | Gửi file 100 MB | Như trên; giao diện không đơ; thanh tiến trình chạy mượt | |
| PF-03 | Theo dõi Task Manager khi gửi 100 MB | CPU, RAM, mạng của tiến trình Python | |
| PF-04 | So sánh Wi-Fi và cáp mạng | Tốc độ file 100 MB trên cả hai | |
| PF-05 | Mở nhiều peer cùng lúc (5, rồi 15 cửa sổ trên một máy đủ mạnh) và chat liên tục | Có sập, có chậm rõ rệt, có mất tin không | |
| PF-06 | Gửi file 100 MB trong khi đang chat | Chat có bị đơ, độ trễ cảm nhận được | |

## 7. Commit mẫu

`test(stress): add python benchmark script for 2 load levels`
