
import hashlib
import os
import threading
import uuid
from pathlib import Path


class FileStorage:
    """Quản lý file đang nhận và file đã nhận."""

    def __init__(self, download_dir="downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self._transfers = {}
        self._lock = threading.RLock()

    @staticmethod
    def _safe_filename(file_name):
        if not isinstance(file_name, str) or not file_name.strip():
            raise ValueError("Tên file không hợp lệ")

        # Xử lý cả đường dẫn Windows và Linux.
        normalized = file_name.replace("\\", "/")
        safe_name = normalized.split("/")[-1].strip()

        if safe_name in ("", ".", ".."):
            raise ValueError("Tên file không hợp lệ")

        return safe_name

    def _unique_path(self, file_name):
        path = self.download_dir / file_name

        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        index = 1

        while True:
            candidate = self.download_dir / f"{stem}_{index}{suffix}"

            if not candidate.exists():
                return candidate

            index += 1

    def start_file(self, transfer_id, file_name, file_size, sha256):
        if not isinstance(transfer_id, str) or not transfer_id:
            raise ValueError("transfer_id không hợp lệ")

        if not isinstance(file_size, int) or file_size < 0:
            raise ValueError("file_size không hợp lệ")

        if (
            not isinstance(sha256, str)
            or len(sha256) != 64
            or any(c not in "0123456789abcdefABCDEF" for c in sha256)
        ):
            raise ValueError("SHA-256 không hợp lệ")

        safe_name = self._safe_filename(file_name)

        with self._lock:
            if transfer_id in self._transfers:
                raise ValueError("transfer_id đã tồn tại")

            final_path = self._unique_path(safe_name)
            temp_path = final_path.with_name(
                final_path.name + f".{uuid.uuid4().hex}.part"
            )

            file_obj = open(temp_path, "wb")

            self._transfers[transfer_id] = {
                "file": file_obj,
                "temp_path": temp_path,
                "final_path": final_path,
                "file_size": file_size,
                "sha256": sha256.lower(),
                "received_size": 0,
                "expected_chunk_index": 0,
                "hash": hashlib.sha256()
            }

    def write_chunk(self, transfer_id, chunk, chunk_index):
        if not isinstance(chunk, bytes):
            raise TypeError("chunk phải là bytes")

        with self._lock:
            transfer = self._transfers.get(transfer_id)

            if transfer is None:
                raise ValueError("Không tìm thấy transfer_id")

            if chunk_index != transfer["expected_chunk_index"]:
                raise ValueError("Thứ tự chunk không hợp lệ")

            new_size = transfer["received_size"] + len(chunk)

            if new_size > transfer["file_size"]:
                raise ValueError("Dữ liệu nhận vượt quá kích thước file")

            transfer["file"].write(chunk)
            transfer["hash"].update(chunk)

            transfer["received_size"] = new_size
            transfer["expected_chunk_index"] += 1

    def finish_file(self, transfer_id):
        with self._lock:
            transfer = self._transfers.get(transfer_id)

            if transfer is None:
                raise ValueError("Không tìm thấy transfer_id")

            try:
                transfer["file"].flush()
                os.fsync(transfer["file"].fileno())
                transfer["file"].close()

                if transfer["received_size"] != transfer["file_size"]:
                    raise ValueError("Kích thước file không khớp")

                actual_hash = transfer["hash"].hexdigest()

                if actual_hash != transfer["sha256"]:
                    raise ValueError("SHA-256 không khớp")

                os.replace(
                    transfer["temp_path"],
                    transfer["final_path"]
                )

                return str(transfer["final_path"])

            except Exception:
                if not transfer["file"].closed:
                    transfer["file"].close()

                transfer["temp_path"].unlink(missing_ok=True)
                raise

            finally:
                self._transfers.pop(transfer_id, None)

    def abort_file(self, transfer_id):
        with self._lock:
            transfer = self._transfers.pop(transfer_id, None)

            if transfer is None:
                return

            try:
                if not transfer["file"].closed:
                    transfer["file"].close()
            finally:
                transfer["temp_path"].unlink(missing_ok=True)

    def abort_all(self):
        with self._lock:
            transfer_ids = list(self._transfers.keys())

        for transfer_id in transfer_ids:
            self.abort_file(transfer_id)
