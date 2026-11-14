
import threading
import uuid
from enum import Enum


class TransferStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TransferTask:
    """Lưu trạng thái của một lần truyền file."""

    def __init__(self, sender_id, receiver_id, file_path):
        self.transfer_id = str(uuid.uuid4())

        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.file_path = file_path

        self.status = TransferStatus.PENDING
        self.progress = 0.0
        self.speed = 0.0
        self.error = None

        self.cancel_event = threading.Event()
        self._lock = threading.Lock()

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
            if self.status == TransferStatus.CANCELLED:
                return

            self.progress = 100.0
            self.status = TransferStatus.COMPLETED

    def fail(self, error):
        with self._lock:
            if self.status == TransferStatus.CANCELLED:
                return

            self.error = str(error)
            self.status = TransferStatus.FAILED

    def cancel(self):
        with self._lock:
            if self.status in (
                TransferStatus.COMPLETED,
                TransferStatus.FAILED,
                TransferStatus.CANCELLED
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
                "transfer_id": self.transfer_id,
                "sender_id": self.sender_id,
                "receiver_id": self.receiver_id,
                "file_path": self.file_path,
                "status": self.status.value,
                "progress": self.progress,
                "speed": self.speed,
                "error": self.error
            }
