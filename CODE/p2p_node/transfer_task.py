"""
Transfer Task Module - Đối tượng quản lý trạng thái tác vụ truyền nhận file (TV5).
"""

import os
from enum import Enum
from p2p_node.speed_meter import SpeedMeter
from shared.format import format_bytes, format_speed


class TransferDirection(Enum):
    UPLOAD = "upload"
    DOWNLOAD = "download"


class TransferStatus(Enum):
    PENDING = "pending"
    TRANSFERRING = "transferring"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class TransferTask:
    """Quản lý trạng thái và tiến độ của 1 phiên gửi hoặc nhận file."""

    def __init__(self, task_id: str, peer_id: str, direction: TransferDirection,
                 file_path: str = "", file_name: str = "", file_size: int = 0,
                 total_chunks: int = 0, file_hash: str = ""):
        self.task_id = task_id
        self.peer_id = peer_id
        self.direction = direction
        self.file_path = file_path
        self.file_name = file_name or os.path.basename(file_path)
        self.file_size = file_size or (os.path.getsize(file_path) if os.path.exists(file_path) else 0)
        self.total_chunks = total_chunks
        self.current_chunk = 0
        self.file_hash = file_hash

        self.transferred_bytes = 0
        self.status = TransferStatus.PENDING
        self.error_msg = ""
        self.speed_meter = SpeedMeter()
        self.temp_path = ""
        self.final_path = ""
        self.is_aborted = False

    @property
    def progress_percent(self) -> float:
        """Tính % tiến độ hoàn thành."""
        if self.file_size <= 0:
            return 100.0 if self.status == TransferStatus.COMPLETED else 0.0
        return min(100.0, (self.transferred_bytes / self.file_size) * 100)

    @property
    def speed_str(self) -> str:
        """Lấy chuỗi tốc độ tức thời."""
        if self.status != TransferStatus.TRANSFERRING:
            return ""
        return self.speed_meter.get_speed_str()

    @property
    def size_str(self) -> str:
        """Chuỗi hiển thị tiến độ dung lượng: ví dụ '4.2 MB / 10.0 MB'."""
        cur = format_bytes(self.transferred_bytes)
        tot = format_bytes(self.file_size)
        return f"{cur} / {tot}"

    def update_progress(self, added_bytes: int):
        """Cập nhật tiến độ sau khi gửi/nhận thêm một số bytes."""
        self.transferred_bytes += added_bytes
        self.speed_meter.add_bytes(added_bytes)
        self.status = TransferStatus.TRANSFERRING

    def abort(self, reason: str = "Đã hủy"):
        """Đánh dấu hủy tác vụ."""
        self.is_aborted = True
        self.status = TransferStatus.CANCELLED
        self.error_msg = reason
