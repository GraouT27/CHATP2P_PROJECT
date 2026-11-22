"""
Transfer Task Module - Đối tượng quản lý trạng thái tác vụ truyền nhận file (TV5).
"""

import os
import threading
import uuid
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
    RUNNING = "transferring"
    FAILED = "error"


class TransferTask:
    """Quản lý trạng thái và tiến độ của 1 phiên gửi hoặc nhận file."""

    def __init__(self, task_id: str = None, peer_id: str = "", direction: TransferDirection = TransferDirection.UPLOAD,
                 file_path: str = "", file_name: str = "", file_size: int = 0,
                 total_chunks: int = 0, file_hash: str = ""):
        self.task_id = task_id or str(uuid.uuid4())
        self.peer_id = peer_id
        self.direction = direction if isinstance(direction, TransferDirection) else TransferDirection(direction)
        self.file_path = file_path
        self.file_name = file_name or (os.path.basename(file_path) if file_path else "")
        self.file_size = file_size or (os.path.getsize(file_path) if file_path and os.path.exists(file_path) else 0)
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
        self._file_handle = None
        self._hasher = None
        self.cancel_event = threading.Event()
        self._lock = threading.Lock()

    @property
    def transfer_id(self) -> str:
        return self.task_id

    @property
    def progress(self) -> float:
        return self.progress_percent

    @property
    def speed(self) -> float:
        return getattr(self.speed_meter, "current_speed", 0.0)

    @property
    def error(self) -> str:
        return self.error_msg

    @property
    def progress_percent(self) -> float:
        """Tính % tiến độ hoàn thành."""
        if self.file_size <= 0:
            return 100.0 if self.status == TransferStatus.COMPLETED else 0.0
        return min(100.0, (self.transferred_bytes / self.file_size) * 100)

    @property
    def speed_str(self) -> str:
        """Lấy chuỗi tốc độ tức thời."""
        if self.status not in (TransferStatus.TRANSFERRING, TransferStatus.RUNNING):
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
        with self._lock:
            self.transferred_bytes += added_bytes
            self.speed_meter.add_bytes(added_bytes)
            self.status = TransferStatus.TRANSFERRING

    def abort(self, reason: str = "Đã hủy"):
        """Đánh dấu hủy tác vụ."""
        with self._lock:
            self.is_aborted = True
            self.cancel_event.set()
            self.status = TransferStatus.CANCELLED
            self.error_msg = reason

    def is_cancelled(self) -> bool:
        return self.is_aborted or self.cancel_event.is_set()

    def get_info(self) -> dict:
        with self._lock:
            return {
                "task_id": self.task_id,
                "transfer_id": self.task_id,
                "peer_id": self.peer_id,
                "file_name": self.file_name,
                "file_path": self.file_path,
                "file_size": self.file_size,
                "direction": self.direction.value,
                "status": self.status.value,
                "progress": self.progress_percent,
                "speed": self.speed_str,
                "error": self.error_msg,
            }
