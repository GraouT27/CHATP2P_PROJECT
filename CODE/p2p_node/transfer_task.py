import os
import threading
import uuid
from enum import Enum


class TransferStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


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

        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.file_path = file_path

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