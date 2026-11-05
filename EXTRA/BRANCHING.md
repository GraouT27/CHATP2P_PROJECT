# Quy ước làm việc với Git

Nhóm làm việc theo mô hình **nhánh tính năng → `main`**.

## Nhánh
| Nhánh | Mục đích |
|---|---|
| `main` | Bản ổn định, luôn chạy được. Chỉ thay đổi qua Pull Request. |
| `feature/<tv>-<tên>` | Mỗi tính năng/công việc một nhánh. |
| `fix/<tên>` | Sửa lỗi. |

Ví dụ: `feature/tv2-chat-box`, `feature/tv4-udp-discovery`, `feature/tv5-file-queue`, `feature/tv6-aes-session`.

## Quy trình một công việc
```bash
git checkout main
git pull
git checkout -b feature/tv2-chat-box
# ... code, commit nhỏ và thường xuyên ...
git push -u origin feature/tv2-chat-box
# Tạo Pull Request vào main, chọn 1 người review
```
Trước khi code luôn `git pull` trên `main`. Trước khi tạo PR chạy `python -m pytest`.

## Quy ước commit
Định dạng: `type(scope): mô tả ngắn`

| type | Dùng khi |
|---|---|
| feat | Thêm tính năng |
| fix | Sửa lỗi |
| docs | Tài liệu |
| test | Thêm/sửa test |
| refactor | Đổi cấu trúc, không đổi hành vi |
| chore | Cấu hình, thư viện |

Ví dụ: `feat(core): add udp peer discovery`, `test(stress): add python benchmark script for 2 load levels`.
Mỗi commit một mục đích; không gộp nhiều việc không liên quan.

## Quy tắc Pull Request
- Có ít nhất 1 người review (không tự duyệt PR của mình).
- Mô tả rõ: làm gì, test thế nào, kèm ảnh chụp nếu là GUI.
- Xung đột (conflict): người tạo PR tự giải quyết, hỏi TV1 nếu cần.
- Không `git push --force` lên `main`.

## Cài đặt GitHub cho `main` (chủ repo hoặc người có quyền Admin)
Settings → Branches → Add branch ruleset/rule cho `main`:
- Require a pull request before merging
- Require approvals: 1
- Block force pushes

## Thư mục
| Thư mục | Nội dung | Phụ trách chính |
|---|---|---|
| `CODE/` | Mã nguồn ứng dụng | TV2–TV6 theo module |
| `tests/` | Test tự động | TV1 |
| `DOCX/` | Báo cáo, tài liệu đặc tả | TV1 (tổng hợp) |
| `EXTRA/` | Hướng dẫn, tài nguyên phụ | TV1 |
| `PPTX/` | Slide | Cả nhóm |
