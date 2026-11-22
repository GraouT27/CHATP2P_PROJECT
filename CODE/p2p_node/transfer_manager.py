"""
Transfer Manager Module - Quản lý hàng đợi và luồng truyền đa file song song (TV5).

Tính năng:
- Giới hạn số file truyền/nhận đồng thời bằng Semaphore(MAX_CONCURRENT_TRANSFERS).
- Đọc file nhị phân theo khối (Chunking 64KB), mã hóa AES-256-GCM.
- Ghi dữ liệu vào file tạm .part và tự động xóa ngay lập tức nếu xảy ra lỗi.
- Điều tiết tín hiệu (Throttling) để giao diện luôn mượt mà.
"""

import os
import time
import uuid
import base64
import hashlib
import threading
from typing import Optional, Callable
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from config import CHUNK_SIZE, MAX_CONCURRENT_TRANSFERS, RECEIVED_FILES_DIR
from p2p_node.transfer_task import TransferTask, TransferDirection, TransferStatus
from p2p_node.storage import resolve_filename, get_temp_filepath, append_chunk, finalize_file, remove_temp_file
from security.crypto_manager import CryptoManager
from security.logger import log
from shared.protocol import (
    make_file_start_header, make_file_chunk_header, make_file_cancel_header, pack_message
)


class FileSenderThread(QThread):
    """QThread worker chuyên dụng chịu trách nhiệm cắt file và gửi qua socket."""
    task_progress = pyqtSignal(str)   # task_id
    task_done = pyqtSignal(str)       # task_id
    task_failed = pyqtSignal(str, str)# (task_id, error_msg)

    def __init__(self, task: TransferTask, target_ip: str, target_port: int,
                 crypto_mgr: CryptoManager, semaphore: threading.Semaphore,
                 listen_port: int = 0, parent=None):
        super().__init__(parent)
        self.task = task
        self.target_ip = target_ip
        self.target_port = target_port
        self.crypto_mgr = crypto_mgr
        self.semaphore = semaphore
        self.listen_port = listen_port

    def run(self):
        # Chờ Semaphore cho phép chạy trong giới hạn đồng thời
        self.semaphore.acquire()
        import socket
        sock = None
        try:
            self.task.status = TransferStatus.TRANSFERRING
            self.task_progress.emit(self.task.task_id)

            # 1. Tính toán SHA-256 file
            file_hash = CryptoManager.sha256_file(self.task.file_path)
            self.task.file_hash = file_hash
            total_chunks = (self.task.file_size + CHUNK_SIZE - 1) // CHUNK_SIZE if self.task.file_size > 0 else 1
            self.task.total_chunks = total_chunks

            # 2. Mở kết nối Socket TCP (timeout 60s để truyền file lớn ổn định)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(60.0)
            sock.connect((self.target_ip, self.target_port))

            # 3. Gửi gói tin file_start
            start_header = make_file_start_header(
                username=self.crypto_mgr._peer_session_keys.get(self.task.peer_id, "User") and "User" or "User",
                file_id=self.task.task_id,
                file_name=self.task.file_name,
                file_size=self.task.file_size,
                total_chunks=total_chunks,
                file_hash=file_hash,
            )
            if self.listen_port:
                start_header["sender_port"] = self.listen_port
            sock.sendall(pack_message(start_header))

            # 4. Đọc file nhị phân và gửi từng chunk 64KB
            last_emit = 0.0
            with open(self.task.file_path, "rb") as f:
                chunk_idx = 0
                while not self.task.is_aborted:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break

                    chunk_hash = CryptoManager.sha256_bytes(chunk)
                    payload_to_send = chunk
                    is_encrypted = False
                    nonce_str = None

                    # Mã hóa chunk nếu có khóa phiên
                    if self.crypto_mgr and self.crypto_mgr.has_session_key(self.task.peer_id):
                        enc_res = self.crypto_mgr.encrypt_bytes(self.task.peer_id, chunk)
                        if enc_res:
                            ct, nonce_b = enc_res
                            payload_to_send = ct
                            is_encrypted = True
                            nonce_str = base64.b64encode(nonce_b).decode("utf-8")

                    chunk_header = make_file_chunk_header(
                        username="User",
                        file_id=self.task.task_id,
                        chunk_index=chunk_idx,
                        chunk_size=len(chunk),
                        chunk_hash=chunk_hash,
                        is_encrypted=is_encrypted,
                        nonce=nonce_str,
                    )
                    if self.listen_port:
                        chunk_header["sender_port"] = self.listen_port

                    sock.sendall(pack_message(chunk_header, payload_to_send))

                    self.task.update_progress(len(chunk))
                    self.task.current_chunk = chunk_idx
                    chunk_idx += 1

                    # Throttling tín hiệu (tối đa mỗi 50ms)
                    now = time.time()
                    if now - last_emit >= 0.05 or self.task.transferred_bytes >= self.task.file_size:
                        self.task_progress.emit(self.task.task_id)
                        last_emit = now

                    # Sleep nhẹ để socket buffer không nghẽn
                    time.sleep(0.001)

            if self.task.is_aborted:
                cancel_h = make_file_cancel_header("User", self.task.task_id, "Người dùng đã hủy")
                try:
                    sock.sendall(pack_message(cancel_h))
                except Exception:
                    pass
                self.task_failed.emit(self.task.task_id, "Tác vụ đã bị hủy")
                return

            self.task.status = TransferStatus.COMPLETED
            self.task_done.emit(self.task.task_id)
            log.info(f"Gửi file hoàn tất: {self.task.file_name}")

        except Exception as e:
            self.task.status = TransferStatus.ERROR
            self.task.error_msg = str(e)
            log.error(f"Lỗi gửi file {self.task.task_id}: {e}")
            self.task_failed.emit(self.task.task_id, str(e))
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
            self.semaphore.release()


class TransferManager(QObject):
    """Điều phối toàn bộ các tác vụ truyền và nhận file."""
    task_added = pyqtSignal(object)       # (TransferTask)
    task_progress = pyqtSignal(object)    # (TransferTask)
    task_completed = pyqtSignal(object)   # (TransferTask)
    task_failed = pyqtSignal(object)      # (TransferTask)

    def __init__(self, crypto_mgr: CryptoManager, download_dir: str = RECEIVED_FILES_DIR, parent=None):
        super().__init__(parent)
        self.crypto_mgr = crypto_mgr
        self.download_dir = download_dir
        self.semaphore = threading.Semaphore(MAX_CONCURRENT_TRANSFERS)

        self.tasks: dict[str, TransferTask] = {}  # {task_id: TransferTask}
        self._sender_threads: dict[str, FileSenderThread] = {}

    def start_send_file(self, peer_id: str, ip: str, port: int, file_path: str) -> Optional[str]:
        """Tạo tác vụ gửi file và bắt đầu worker luồng nền."""
        if not os.path.exists(file_path):
            return None

        task_id = str(uuid.uuid4())
        task = TransferTask(
            task_id=task_id,
            peer_id=peer_id,
            direction=TransferDirection.UPLOAD,
            file_path=file_path,
        )
        self.tasks[task_id] = task
        self.task_added.emit(task)

        worker = FileSenderThread(
            task, ip, port, self.crypto_mgr, self.semaphore,
            listen_port=getattr(self, "listen_port", 0) or getattr(config, "listen_port", 0),
            parent=self
        )
        worker.task_progress.connect(lambda tid: self.tasks.get(tid) and self.task_progress.emit(self.tasks.get(tid)))
        worker.task_done.connect(lambda tid: self.tasks.get(tid) and self.task_completed.emit(self.tasks.get(tid)))
        worker.task_failed.connect(lambda tid, err: self.tasks.get(tid) and self.task_failed.emit(self.tasks.get(tid)))

        self._sender_threads[task_id] = worker
        worker.start()
        return task_id

    def handle_file_start(self, peer_id: str, header: dict):
        """Xử lý khi bên kia bắt đầu gửi file."""
        file_id = header.get("file_id") or header.get("task_id")
        file_name = header.get("file_name", "downloaded_file")
        file_size = header.get("file_size", 0)
        total_chunks = header.get("total_chunks", 1)
        file_hash = header.get("file_hash") or header.get("sha256", "")

        # Đường dẫn lưu tạm .part và đường dẫn đích
        temp_path = get_temp_filepath(self.download_dir, file_id, file_name)
        final_path = resolve_filename(self.download_dir, file_name)

        # Xóa file tạm cũ nếu có
        remove_temp_file(temp_path)

        task = TransferTask(
            task_id=file_id,
            peer_id=peer_id,
            direction=TransferDirection.DOWNLOAD,
            file_name=file_name,
            file_size=file_size,
            total_chunks=total_chunks,
            file_hash=file_hash,
        )
        task.temp_path = temp_path
        task.final_path = final_path
        task.status = TransferStatus.TRANSFERRING
        task._last_progress_emit = 0.0

        # Mở sẵn file handle và khởi tạo hasher để ghi liên tục và tính SHA-256 lũy tiến
        try:
            task._file_handle = open(temp_path, "wb")
            task._hasher = hashlib.sha256()
        except Exception as e:
            log.error(f"Không thể mở file tạm {temp_path}: {e}")
            task._file_handle = None
            task._hasher = None

        self.tasks[file_id] = task
        self.task_added.emit(task)
        log.info(f"Bắt đầu nhận file '{file_name}' ({file_size} bytes) từ {peer_id}")

    def handle_file_chunk(self, peer_id: str, header: dict, chunk_bytes: bytes):
        """Ghi nhận một chunk dữ liệu nhị phân."""
        file_id = header.get("file_id") or header.get("task_id")
        task = self.tasks.get(file_id)
        if not task or task.is_aborted or task.status == TransferStatus.COMPLETED:
            return

        try:
            # Ghi trực tiếp vào file handle mở sẵn để tối ưu I/O và tránh nghẽn luồng
            if getattr(task, "_file_handle", None) and not task._file_handle.closed:
                task._file_handle.write(chunk_bytes)
            else:
                append_chunk(task.temp_path, chunk_bytes)

            if getattr(task, "_hasher", None) is not None:
                task._hasher.update(chunk_bytes)

            task.update_progress(len(chunk_bytes))

            # Điều tiết tín hiệu GUI (tối đa mỗi 50ms) để không làm đơ/sập giao diện khi truyền file lớn
            now = time.time()
            if now - getattr(task, "_last_progress_emit", 0.0) >= 0.05 or task.transferred_bytes >= task.file_size:
                task._last_progress_emit = now
                self.task_progress.emit(task)

            # Nếu đã nhận đủ số byte
            if task.transferred_bytes >= task.file_size:
                if getattr(task, "_file_handle", None) and not task._file_handle.closed:
                    task._file_handle.flush()
                    try:
                        os.fsync(task._file_handle.fileno())
                    except OSError:
                        pass
                    task._file_handle.close()
                    task._file_handle = None

                actual_hash = task._hasher.hexdigest().lower() if getattr(task, "_hasher", None) else None
                success = False
                if actual_hash and task.file_hash:
                    if actual_hash == task.file_hash.lower():
                        if os.path.exists(task.final_path):
                            try:
                                os.remove(task.final_path)
                            except OSError:
                                pass
                        os.replace(task.temp_path, task.final_path)
                        success = True
                    else:
                        remove_temp_file(task.temp_path)
                else:
                    success = finalize_file(task.temp_path, task.final_path, task.file_hash)

                if success:
                    task.status = TransferStatus.COMPLETED
                    self.task_completed.emit(task)
                    log.info(f"Nhận file hoàn tất: {task.final_path}")
                else:
                    task.status = TransferStatus.ERROR
                    task.error_msg = "Kiểm tra toàn vẹn SHA-256 thất bại!"
                    remove_temp_file(task.temp_path)
                    self.task_failed.emit(task)

        except Exception as e:
            task.status = TransferStatus.ERROR
            task.error_msg = str(e)
            if getattr(task, "_file_handle", None) and not task._file_handle.closed:
                try:
                    task._file_handle.close()
                except Exception:
                    pass
                task._file_handle = None
            remove_temp_file(task.temp_path)
            self.task_failed.emit(task)

    def cancel_task(self, task_id: str):
        """Hủy bỏ một tác vụ truyền/nhận file và xóa file tạm."""
        task = self.tasks.get(task_id)
        if not task:
            return

        task.abort("Người dùng đã hủy")
        if getattr(task, "_file_handle", None) and not task._file_handle.closed:
            try:
                task._file_handle.close()
            except Exception:
                pass
            task._file_handle = None

        if task_id in self._sender_threads:
            self._sender_threads[task_id].quit()

        if task.temp_path:
            remove_temp_file(task.temp_path)

        self.task_failed.emit(task)

    def cancel_all_for_peer(self, peer_id: str):
        """Hủy bỏ và dọn sạch toàn bộ tác vụ của Peer bị ngắt kết nối đột ngột."""
        for tid, task in list(self.tasks.items()):
            if task.peer_id == peer_id and task.status == TransferStatus.TRANSFERRING:
                log.warning(f"Peer {peer_id} ngắt kết nối: Hủy tác vụ file {tid}")
                if getattr(task, "_file_handle", None) and not task._file_handle.closed:
                    try:
                        task._file_handle.close()
                    except Exception:
                        pass
                    task._file_handle = None
                self.cancel_task(tid)
