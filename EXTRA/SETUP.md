# Hướng dẫn thiết lập môi trường

Yêu cầu: **Python 3.12 (khuyến nghị)** và Git. Python 3.13 trở lên có thể chưa được PyQt6 hỗ trợ.

## 1. Clone repo
```bash
git clone https://github.com/GraouT27/CHATP2P_PROJECT.git
cd CHATP2P_PROJECT
```

## 2. Tạo và kích hoạt môi trường ảo (venv)

**Windows (PowerShell)**
```powershell
py -3.12 -m venv venv
venv\Scripts\Activate.ps1
```
Nếu báo "running scripts is disabled", chạy một lần:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**macOS / Linux**
```bash
python3.12 -m venv venv
source venv/bin/activate
```

Đầu dòng lệnh có `(venv)` là đã kích hoạt. Mỗi lần mở terminal mới phải kích hoạt lại.

## 3. Cài thư viện
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Kiểm tra môi trường
```bash
python -m pytest tests/test_environment.py -v
```
Kết quả đúng: `4 passed`.

## Quy tắc
- Không commit thư mục `venv/` (đã có trong `.gitignore`).
- Cài thêm thư viện mới: cập nhật `requirements.txt` và báo TV1.
- Thoát venv: `deactivate`.

## Lỗi thường gặp
| Lỗi | Cách xử lý |
|---|---|
| `Python was not found` | Chưa kích hoạt venv, hoặc dùng `py -3.12` thay cho `python` |
| `running scripts is disabled` | Chạy lệnh `Set-ExecutionPolicy` ở trên |
| `No module named pytest` | Chưa chạy `pip install -r requirements.txt` trong venv |
| Cài PyQt6 lỗi | Kiểm tra `python --version` phải là 3.10–3.12 |
