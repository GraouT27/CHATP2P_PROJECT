# Báo cáo kiểm thử hiệu năng (Stress Test & Performance Test)

Thời gian: 2026-11-22T10:48:36 | Hệ điều hành: Windows 11 | Python 3.12.10 | 12 nhân logic, 7.8 GiB RAM | cryptography 50.0.2

## 1. Tốc độ AES-256-GCM

| Lớp | Kích thước | Mã hóa (MiB/s) | Giải mã (MiB/s) | Mã hóa (µs/lần) | Giải mã (µs/lần) |
|---|---|---|---|---|---|
| SessionCrypto (tin nhan) | 64 B | 24 | 29 | 2.5 | 2.1 |
| SessionCrypto (tin nhan) | 1 KiB | 351 | 477 | 2.8 | 2.0 |
| SessionCrypto (tin nhan) | 16 KiB | 1228 | 2181 | 12.7 | 7.2 |
| SessionCrypto (tin nhan) | 64 KiB | 1558 | 1885 | 40.1 | 33.2 |
| SessionCrypto (tin nhan) | 1024 KiB | 1504 | 1222 | 664.9 | 818.5 |
| ChunkCrypto (chunk file) | 64 KiB | 1563 | 2788 | 40.0 | 22.4 |
| AESGCM tho (doi chung) | 64 KiB | 1624 | 2917 | 38.5 | 21.4 |

Mã hóa và giải mã cả file (chunk 64 KiB):

| File | Số luồng | Mã hóa (MiB/s) | Giải mã (MiB/s) |
|---|---|---|---|
| 10 MB | 1 luong | 854 | 825 |
| 10 MB | 4 luong | 838 | 982 |
| 100 MB | 1 luong | 946 | 919 |
| 100 MB | 4 luong | 893 | 900 |

RSA-2048: sinh khóa trung vị 36 ms; bắt tay đầy đủ trung vị 1.9 ms.

## 2. Muc 1: 5 peer, 50 tin/giây, file 10 MB: **PASS**

| Chỉ số | Giá trị |
|---|---|
| Tin gửi / nhận / mất | 750 / 750 / 0 (0.00%) |
| Tốc độ gửi đạt được | 50.0 tin/giây (mục tiêu 50) |
| Độ trễ khứ hồi p50 / p95 / p99 / max | 0.6 / 0.7 / 0.9 / 1.0 ms |
| Truyền file 10 MB (lặp 297 lần suốt thời gian chịu tải) | trung bình 0.05 s/lần, 198.8 MiB/s (chậm nhất 144.7), SHA-256 đúng cả |
| Tốc độ mã hóa thực (bên gửi) / giải mã thực (máy chủ) | 928 / 2949 MiB/s (4 luồng mã hóa) |
| Bắt tay (kết nối + RSA) trung bình / lớn nhất | 8 / 12 ms |
| CPU máy chủ trung bình / cao nhất | 0% / 0% (của 1 nhân) |
| RAM đỉnh máy chủ / tổng các peer | 3 MiB / 21 MiB |
| CPU toàn máy trung bình / cao nhất | 4% / 7% |

Tiêu chí: khong_loi_ket_noi: đạt, khong_mat_tin: đạt, tre_p95_dat: đạt, dat_toc_do_gui: đạt, file_sha256_dung: đạt

## 3. Muc 2: 15 peer, 200 tin/giây, file 100 MB: **PASS**

| Chỉ số | Giá trị |
|---|---|
| Tin gửi / nhận / mất | 2999 / 2999 / 0 (0.00%) |
| Tốc độ gửi đạt được | 200.0 tin/giây (mục tiêu 200) |
| Độ trễ khứ hồi p50 / p95 / p99 / max | 0.7 / 1.0 / 1.1 / 1.3 ms |
| Truyền file 100 MB (lặp 30 lần suốt thời gian chịu tải) | trung bình 0.51 s/lần, 194.8 MiB/s (chậm nhất 154.7), SHA-256 đúng cả |
| Tốc độ mã hóa thực (bên gửi) / giải mã thực (máy chủ) | 857 / 2598 MiB/s (4 luồng mã hóa) |
| Bắt tay (kết nối + RSA) trung bình / lớn nhất | 30 / 90 ms |
| CPU máy chủ trung bình / cao nhất | 0% / 0% (của 1 nhân) |
| RAM đỉnh máy chủ / tổng các peer | 3 MiB / 55 MiB |
| CPU toàn máy trung bình / cao nhất | 10% / 28% |

Tiêu chí: khong_loi_ket_noi: đạt, khong_mat_tin: đạt, tre_p95_dat: đạt, dat_toc_do_gui: đạt, file_sha256_dung: đạt
