"""
Module tiện ích định dạng hiển thị dung lượng, tốc độ truyền và thời gian (TV3).
Phục vụ cho thanh tiến trình truyền file (FileRowWidget) và giao diện khung chat.
"""
from datetime import datetime


def format_size(num_bytes: int | float) -> str:
    """
    Chuyển đổi số byte sang chuỗi dung lượng dễ đọc (B, KB, MB, GB).
    Ví dụ: 1024 -> '1.0 KB', 1048576 -> '1.00 MB'
    """
    if num_bytes is None or num_bytes < 0:
        return "0 B"
    size = float(num_bytes)
    if size < 1024:
        return f"{int(size)} B"
    elif size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 ** 3:
        return f"{size / (1024 ** 2):.2f} MB"
    else:
        return f"{size / (1024 ** 3):.2f} GB"


def format_speed(bytes_per_sec: int | float) -> str:
    """
    Định dạng tốc độ truyền file theo thời gian thực (B/s, KB/s, MB/s).
    """
    if bytes_per_sec is None or bytes_per_sec <= 0:
        return "0 B/s"
    return f"{format_size(bytes_per_sec)}/s"


def format_progress_text(transferred: int, total: int, speed: float = 0.0) -> str:
    """
    Tạo chuỗi hiển thị chi tiết trên dòng truyền file.
    Ví dụ: '1.20 MB / 5.00 MB (24%) • 2.50 MB/s'
    """
    total_safe = max(int(total or 0), 0)
    trans_safe = max(min(int(transferred or 0), total_safe), 0) if total_safe > 0 else 0
    percent = int((trans_safe / total_safe) * 100) if total_safe > 0 else 0

    base = f"{format_size(trans_safe)} / {format_size(total_safe)} ({percent}%)"
    if speed and speed > 0:
        return f"{base} • {format_speed(speed)}"
    return base


def format_timestamp(ts: float | str | None = None) -> str:
    """
    Định dạng nhãn thời gian hiển thị trên GUI (HH:MM).
    Hỗ trợ cả kiểu float (epoch time) hoặc chuỗi ISO UTC.
    """
    if ts is None:
        return datetime.now().strftime("%H:%M")
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(ts).strftime("%H:%M")
        except (OSError, ValueError):
            return datetime.now().strftime("%H:%M")
    if isinstance(ts, str):
        try:
            clean = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean)
            return dt.astimezone().strftime("%H:%M")
        except ValueError:
            return ts[:5] if len(ts) >= 5 else ts
    return datetime.now().strftime("%H:%M")