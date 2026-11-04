from datetime import datetime


def format_size(num_bytes: int) -> str:
    """Định dạng dung lượng file từ Bytes sang B, KB, MB, GB"""
    if num_bytes < 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024.0 or unit == "GB":
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{int(num_bytes)} B"
        num_bytes /= 1024.0
    return "0 B"


def format_speed(bytes_per_sec: float) -> str:
    """Định dạng tốc độ truyền thực tế sang KB/s hoặc MB/s"""
    if bytes_per_sec <= 0:
        return "0 KB/s"
    kb_per_sec = bytes_per_sec / 1024.0
    if kb_per_sec < 1024.0:
        return f"{kb_per_sec:.1f} KB/s"
    mb_per_sec = kb_per_sec / 1024.0
    return f"{mb_per_sec:.2f} MB/s"


def format_timestamp(dt: datetime = None) -> str:
    """Định dạng nhãn thời gian hiển thị trên giao diện (HH:MM:SS)"""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%H:%M:%S")