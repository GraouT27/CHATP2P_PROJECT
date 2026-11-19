"""
Transfer Task Module - Đối tượng quản lý trạng thái tác vụ truyền nhận file (TV5).
"""

import os
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

class TransferDirection(Enum):
    UPLOAD = "upload"
    DOWNLOAD = "download"


class TransferTask:

    def __init__(
        self,
        sender_id,
        receiver_id,
        file_path,
        direction=TransferDirection.UPLOAD,
        transfer_id=None,
        file_size=None,
    ):
        self.transfer_id = transfer_id or str(uuid.uuid4())

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
        self.direction = (
            direction
            if isinstance(direction, TransferDirection)
            else TransferDirection(direction)
        )

        if file_size is not None:
            self._file_size = int(file_size)
        elif file_path and os.path.isfile(file_path):
            self._file_size = os.path.getsize(file_path)
        else:
            self._file_size = 0

        self.status = TransferStatus.PENDING
        self.progress = 0.0
        self.speed = 0.0
        self.error = None

        self.cancel_event = threading.Event()
        self._lock = threading.Lock()

    @property
    def task_id(self):
        return self.transfer_id

    @property
    def peer_id(self):
        if self.direction == TransferDirection.UPLOAD:
            return self.receiver_id
        return self.sender_id

    @property
    def file_name(self):
        return os.path.basename(self.file_path) if self.file_path else ""

    @property
    def file_size(self):
        return self._file_size

    def start(self):
        with self._lock:
            if self.status != TransferStatus.PENDING:
                return False

            self.status = TransferStatus.RUNNING
            return True

    def update_progress(self, progress, speed):
        with self._lock:
            if self.status != TransferStatus.RUNNING:
                return

            self.progress = max(0.0, min(100.0, float(progress)))
            self.speed = max(0.0, float(speed))

    def complete(self):
        with self._lock:
            if self.status != TransferStatus.RUNNING:
                return False

            self.progress = 100.0
            self.status = TransferStatus.COMPLETED
            return True

    def fail(self, error):
        with self._lock:
            if self.status != TransferStatus.RUNNING:
                return False

            self.error = str(error)
            self.status = TransferStatus.FAILED
            return True

    def cancel(self):
        with self._lock:
            if self.status in (
                TransferStatus.COMPLETED,
                TransferStatus.FAILED,
                TransferStatus.CANCELLED,
            ):
                return False

            self.cancel_event.set()
            self.status = TransferStatus.CANCELLED
            return True

    def is_cancelled(self):
        return self.cancel_event.is_set()

    def get_info(self):
        with self._lock:
            return {
                "task_id": self.transfer_id,
                "transfer_id": self.transfer_id,
                "sender_id": self.sender_id,
                "receiver_id": self.receiver_id,
                "peer_id": self.peer_id,
                "file_name": self.file_name,
                "file_path": self.file_path,
                "file_size": self.file_size,
                "direction": self.direction.value,
                "status": self.status.value,
                "progress": self.progress,
                "speed": self.speed,
                "error": self.error,
            }
