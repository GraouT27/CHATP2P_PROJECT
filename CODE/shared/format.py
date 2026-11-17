"""
Format Module - Các tiện ích định dạng hiển thị cho giao diện (TV3).
"""

import time


def format_bytes(num_bytes: int) -> str:
    """Định dạng số bytes thành chuỗi dễ đọc (B, KB, MB, GB)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_speed(bytes_per_sec: float) -> str:
    """Định dạng tốc độ truyền tải (KB/s, MB/s)."""
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:.0f} B/s"
    elif bytes_per_sec < 1024 * 1024:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    else:
        return f"{bytes_per_sec / (1024 * 1024):.2f} MB/s"


def format_timestamp(ts: float = None) -> str:
    """Định dạng tem thời gian dạng HH:MM."""
    t = time.localtime(ts if ts else time.time())
    return f"{t.tm_hour:02d}:{t.tm_min:02d}"


def format_datetime(ts: float = None) -> str:
    """Định dạng đầy đủ YYYY-MM-DD HH:MM:SS."""
    t = time.localtime(ts if ts else time.time())
    return time.strftime("%Y-%m-%d %H:%M:%S", t)
