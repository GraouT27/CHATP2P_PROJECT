"""
Storage Module - Quản lý ghi file tạm .part, xử lý trùng tên và cache Avatar (TV5).

Ràng buộc kỹ thuật sống còn:
- Dữ liệu chưa truyền hoàn tất KHÔNG được công nhận là dữ liệu hoàn chỉnh.
- Mọi dữ liệu đang nhận phải ghi vào file tạm '.part'.
- Khi hoàn tất kiểm tra mã băm SHA-256 mới đổi tên (rename) sang file chính thức.
- Nếu xảy ra lỗi hoặc mất mạng giữa chừng, lập tức xóa file tạm bằng os.remove().
"""

import os
import re
import hashlib
from typing import Optional
from security.logger import log


# Danh sách tên thiết bị dành riêng của Windows (CON, PRN, NUL, COM1..9, LPT1..9).
# Lý do phải chặn: trên Windows, mở file mang tên 'CON.txt' hoặc 'NUL' sẽ ghi vào thiết bị hệ thống
# thay vì tạo file thường, dễ gây treo hoặc lỗi I/O không mong muốn.
_RESERVED_WIN_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *{f"COM{i}" for i in range(1, 10)},
    *{f"LPT{i}" for i in range(1, 10)},
}


def sanitize_filename(filename: str) -> str:
    """
    Làm sạch tên file nhận từ mạng để chống tấn công Path Traversal (../).
    Cách dùng: gọi hàm này cho mọi tên file/ID do Peer gửi sang trước khi ghép vào đường dẫn lưu đĩa.
    """
    # Chuyển '\' sang '/' rồi lấy basename -> cắt bỏ hoàn toàn thư mục cha kiểu '../../Windows/System32'.
    name = os.path.basename(str(filename or "received_file").replace("\\", "/"))
    # Thay thế ký tự cấm trên Windows và ký tự điều khiển ASCII (0x00-0x1F) bằng '_' để tránh lỗi mở file.
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    # Bỏ dấu '.' ở đầu (tránh tạo file ẩn hoặc '.' / '..' trên hệ điều hành).
    name = name.lstrip(".") or "received_file"
    # Tách phần tên gốc (không gồm đuôi) để kiểm tra xem có trùng tên thiết bị Windows hay không.
    stem = os.path.splitext(name)[0].upper()
    if stem in _RESERVED_WIN_NAMES:
        name = f"_{name}"
    return name


def resolve_filename(directory: str, filename: str) -> str:
    """
    Xử lý tự động đổi tên khi file đã tồn tại trong thư mục đích:
    Ví dụ: 'document.pdf' -> 'document (1).pdf' -> 'document (2).pdf'
    """
    os.makedirs(directory, exist_ok=True)
    safe_filename = sanitize_filename(filename)
    base_name, ext = os.path.splitext(safe_filename)
    candidate = os.path.join(directory, safe_filename)
    counter = 1

    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base_name} ({counter}){ext}")
        counter += 1

    # Defense-in-Depth (Phòng thủ nhiều lớp / Directory Jail):
    # Chuyển cả thư mục gốc và file đích về đường dẫn tuyệt đối chuẩn (abspath) rồi kiểm tra prefix.
    # Lý do: đảm bảo tuyệt đối file kết quả không bao giờ thoát ra ngoài thư mục 'directory'.
    abs_dir = os.path.abspath(directory)
    abs_cand = os.path.abspath(candidate)
    if not abs_cand.startswith(abs_dir):
        raise ValueError(f"Đường dẫn không hợp lệ (Path Traversal bị chặn): {filename}")

    return candidate


def get_temp_filepath(download_dir: str, file_id: str, original_filename: str) -> str:
    """Tạo đường dẫn file tạm '.part' an toàn theo file_id."""
    os.makedirs(download_dir, exist_ok=True)
    safe_id = re.sub(r'[^a-zA-Z0-9_-]', "_", str(file_id or "tmp"))[:64]
    safe_name = sanitize_filename(original_filename)
    temp_name = f"{safe_name}.part_{safe_id}"
    return os.path.join(download_dir, temp_name)


def append_chunk(temp_path: str, chunk_data: bytes):
    """Ghi nối tiếp một chunk nhị phân vào file tạm."""
    with open(temp_path, "ab") as f:
        f.write(chunk_data)


def finalize_file(temp_path: str, final_path: str, expected_sha256: str) -> bool:
    """
    Kiểm tra đối chiếu toàn vẹn mã băm SHA-256 toàn bộ file tạm.
    Nếu khớp: Đổi tên thành file chính thức.
    Nếu sai lệch: Xóa file tạm và trả về False.
    """
    if not os.path.exists(temp_path):
        return False

    hasher = hashlib.sha256()
    try:
        with open(temp_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_hash = hasher.hexdigest().lower()

        if expected_sha256 and actual_hash != expected_sha256.lower():
            log.error(f"Checksum SHA-256 không khớp! Kỳ vọng {expected_sha256}, thực tế {actual_hash}")
            remove_temp_file(temp_path)
            return False

        # Đổi tên file tạm thành file chính thức
        if os.path.exists(final_path):
            os.remove(final_path)
        os.replace(temp_path, final_path)
        log.info(f"Đã hoàn tất lưu file: {final_path}")
        return True

    except Exception as e:
        log.error(f"Lỗi khi hoàn tất file {final_path}: {e}")
        remove_temp_file(temp_path)
        return False


def remove_temp_file(temp_path: str):
    """Xóa file tạm .part ngay lập tức khỏi ổ cứng khi xảy ra lỗi hoặc hủy bỏ."""
    if temp_path and os.path.exists(temp_path):
        try:
            os.remove(temp_path)
            log.info(f"Đã xóa an toàn file tạm dở dang: {temp_path}")
        except Exception as e:
            log.warning(f"Không thể xóa file tạm {temp_path}: {e}")


def save_avatar_cache(avatar_dir: str, peer_id: str, avatar_bytes: bytes) -> Optional[str]:
    """
    Lưu ảnh avatar của Peer vào thư mục cache cục bộ một cách an toàn.
    Lý do: peer_id có chứa dấu ':' hoặc có thể bị giả mạo '../', nên phải chuẩn hóa ký tự
    và kiểm tra đường dẫn nằm gọn trong avatar_dir (chống ghi đè file hệ thống).
    """
    os.makedirs(avatar_dir, exist_ok=True)
    # Chỉ giữ chữ và số cho peer_id (127.0.0.1:9001 -> 127_0_0_1_9001) để tạo tên file hợp lệ trên mọi OS.
    safe_id = "".join(c if c.isalnum() else "_" for c in str(peer_id or "peer"))
    safe_name = sanitize_filename(f"avatar_{safe_id}.png")
    avatar_dir_abs = os.path.abspath(avatar_dir)
    target_path = os.path.abspath(os.path.join(avatar_dir_abs, safe_name))
    # Dùng '+ os.sep' để tránh lỗ hổng cùng tiền tố thư mục (vd: 'avatars_evil' qua mặt check 'avatars').
    if not target_path.startswith(avatar_dir_abs + os.sep):
        return None
    try:
        with open(target_path, "wb") as f:
            f.write(avatar_bytes)
        return target_path
    except Exception as e:
        log.error(f"Lỗi lưu cache avatar cho {peer_id}: {e}")
        return None


class FileStorage:
    """Quản lý file đang nhận và file đã nhận (dành cho CLI compatibility)."""
    def __init__(self, download_dir=None):
        from config import RECEIVED_FILES_DIR
        self.download_dir = download_dir or RECEIVED_FILES_DIR
        os.makedirs(self.download_dir, exist_ok=True)

