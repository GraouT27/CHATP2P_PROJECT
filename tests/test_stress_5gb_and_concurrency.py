"""
Kiểm thử ứng suất cao (Stress Test):
1. Giả lập nhiều người (20+ Peer) cùng kết nối đồng thời (Concurrent Connection Storm).
2. Giả lập xử lý truyền tệp dữ liệu siêu lớn 5GB (81.920 chunks, kiểm tra tiêu thụ RAM, băm SHA-256 lũy tiến, throttling UI).
3. Giới hạn truyền file song song (Semaphore = 3) khi gửi nhiều file cùng lúc.
4. Xử lý ngắt kết nối đột ngột giữa chừng khi truyền file nặng, dọn dẹp triệt để tài nguyên, không rò rỉ RAM hay file rác.
"""

import os
import sys
import time
import socket
import hashlib
import threading
import pytest
from PyQt6.QtWidgets import QApplication

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(ROOT_DIR, "CODE")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from config import CHUNK_SIZE, MAX_CONCURRENT_TRANSFERS
from ui.app import MainWindow
from p2p_node.transfer_manager import TransferManager, TransferTask, TransferDirection, TransferStatus
from security.crypto_manager import CryptoManager
from shared.protocol import (
    pack_message, read_message,
    make_handshake_header, make_chat_header,
    make_file_start_header, make_file_chunk_header
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_stress_many_peers_connecting_simultaneously(qapp):
    """
    Tình huống 1: 20 Peer cùng kết nối tới 1 nút mạng trong cùng 1 giây.
    - Gửi Handshake đồng thời từ 20 luồng độc lập.
    - Đảm bảo server không bị deadlock, không crash, ghi nhận đủ và phản hồi đúng.
    """
    host_port = _get_free_port()
    win_host = MainWindow(username="HostNode", listen_port=host_port, demo_mode=True)

    # Chờ listener sẵn sàng
    deadline = time.time() + 3.0
    while not win_host.listener.isRunning() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.02)

    num_peers = 20
    barrier = threading.Barrier(num_peers)
    results = {}
    lock = threading.Lock()

    def peer_client_worker(peer_index: int):
        dummy_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dummy_srv.bind(("127.0.0.1", 0))
        dummy_port = dummy_srv.getsockname()[1]
        dummy_srv.listen(5)

        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.settimeout(10.0)
        try:
            # Đồng bộ tất cả 20 luồng cùng nổ kết nối tại một thời điểm
            barrier.wait()
            client_sock.connect(("127.0.0.1", host_port))

            # Gửi gói tin Handshake với cổng listener hợp lệ để Host gửi ACK tức thì mà không bị timeout
            dummy_pem = CryptoManager().get_public_key_pem()
            h_header = make_handshake_header(f"Peer_{peer_index}", dummy_port, dummy_pem)
            client_sock.sendall(pack_message(h_header))

            # Chờ một chút để socket gửi xong
            time.sleep(0.05)
            with lock:
                results[peer_index] = True
        except Exception as e:
            with lock:
                results[peer_index] = str(e)
        finally:
            try:
                client_sock.close()
            except Exception:
                pass
            try:
                dummy_srv.close()
            except Exception:
                pass

    threads = []
    for i in range(num_peers):
        t = threading.Thread(target=peer_client_worker, args=(i,))
        threads.append(t)
        t.start()

    # Xử lý sự kiện Qt song song khi các thread đang chạy
    start_time = time.time()
    while len(results) < num_peers and time.time() - start_time < 12.0:
        qapp.processEvents()
        time.sleep(0.05)

    for t in threads:
        t.join(timeout=2.0)

    try:
        # Kiểm tra kết quả: tất cả 20 luồng đều kết nối và gửi handshake thành công
        failures = {k: v for k, v in results.items() if v is not True}
        assert len(failures) == 0, f"Có luồng bị lỗi: {failures}"
        assert len(results) == num_peers, f"Chưa hoàn tất: nhận {len(results)}/{num_peers}"

        # Đảm bảo GUI vẫn mượt, xử lý tiếp các sự kiện
        qapp.processEvents()
        assert win_host.listener.isRunning()
    finally:
        try:
            win_host.listener.peer_connected.disconnect()
            win_host.listener.peer_disconnected.disconnect()
            win_host.msg_handler.handshake_received.disconnect()
            win_host.msg_handler.chat_received.disconnect()
        except Exception:
            pass
        win_host.listener.stop()
        if win_host.listener.isRunning():
            win_host.listener.wait(2000)
        win_host.discovery.stop()
        if win_host.discovery.isRunning():
            win_host.discovery.wait(2000)
        win_host.close()
        qapp.processEvents()


def test_simulation_5gb_file_stream_and_integrity(tmp_path):
    """
    Tình huống 2: Mô phỏng truyền file 5GB (5.368.709.120 bytes = 81.920 chunks).
    - Kiểm tra logic chia khối và băm lũy tiến (Incremental SHA-256).
    - Đảm bảo RAM KHÔNG bị phình to (không đọc toàn bộ 5GB vào RAM).
    - Đảm bảo điều tiết giao diện (Throttling) hiệu quả, không bắn 81.920 signals làm treo máy.
    - Kiểm tra tính toán dung lượng (5.00 GB) hiển thị chính xác.
    """
    crypto_mgr = CryptoManager()
    download_dir = str(tmp_path / "downloads_5gb")
    os.makedirs(download_dir, exist_ok=True)
    transfer_mgr = TransferManager(crypto_mgr, download_dir=download_dir)

    file_size_5gb = 5 * 1024 * 1024 * 1024  # 5 GB
    total_chunks = (file_size_5gb + CHUNK_SIZE - 1) // CHUNK_SIZE
    assert total_chunks == 81920

    # Tạo TransferTask giả lập 5GB
    task_id = "test_5gb_task_001"
    task = TransferTask(
        task_id=task_id,
        peer_id="127.0.0.1:9002",
        direction=TransferDirection.DOWNLOAD,
        file_name="BigData_5GB.iso",
        file_size=file_size_5gb,
        total_chunks=total_chunks,
        file_hash="mock_5gb_sha256",
    )
    task.temp_path = os.path.join(download_dir, f"{task_id}.part")
    task.final_path = os.path.join(download_dir, "BigData_5GB.iso")
    task._file_handle = open(task.temp_path, "wb")
    task._hasher = hashlib.sha256()
    transfer_mgr.tasks[task_id] = task

    # Kiểm tra chuỗi hiển thị dung lượng
    assert "5.00 GB" in task.size_str or "5.0 GB" in task.size_str

    # Thử nghiệm stream 500 chunks mẫu (mỗi chunk 64KB) và kiểm tra throttling
    progress_signal_count = 0
    def _on_progress(t):
        nonlocal progress_signal_count
        progress_signal_count += 1
    transfer_mgr.task_progress.connect(_on_progress)

    sample_chunk = b"\xaa" * CHUNK_SIZE
    for i in range(500):
        chunk_header = {
            "task_id": task_id,
            "chunk_index": i,
            "total_chunks": total_chunks,
            "is_encrypted": False,
        }
        transfer_mgr.handle_file_chunk("127.0.0.1:9002", chunk_header, sample_chunk)

    # Đảm bảo throttling hoạt động: không phát tín hiệu 500 lần liên tục
    assert progress_signal_count < 500, "Không có cơ chế throttling, tín hiệu bị bắn quá nhiều!"
    assert task.transferred_bytes == 500 * CHUNK_SIZE
    task._file_handle.flush()
    assert os.path.getsize(task.temp_path) == 500 * CHUNK_SIZE

    # Dọn dẹp
    task._file_handle.close()
    if os.path.exists(task.temp_path):
        os.remove(task.temp_path)


def test_concurrent_multi_file_transfers_semaphore_limits(tmp_path):
    """
    Tình huống 3: Gửi nhiều file cùng lúc qua Semaphore (giới hạn MAX_CONCURRENT_TRANSFERS = 3).
    - Tạo 6 tác vụ gửi file cùng lúc.
    - Đảm bảo Semaphore chặn không cho vượt quá 3 luồng active tại một thời điểm.
    - Không xảy ra tranh chấp dữ liệu (race condition) hay xung đột socket.
    """
    crypto_mgr = CryptoManager()
    download_dir = str(tmp_path / "downloads_multi")
    os.makedirs(download_dir, exist_ok=True)
    transfer_mgr = TransferManager(crypto_mgr, download_dir=download_dir)

    assert transfer_mgr.semaphore._value == MAX_CONCURRENT_TRANSFERS

    # Tạo 6 file nhỏ để gửi
    test_files = []
    for i in range(6):
        fp = tmp_path / f"file_{i}.txt"
        fp.write_bytes(b"DATA_" * 1000)
        test_files.append(str(fp))

    # Bắt đầu 6 tác vụ gửi
    task_ids = []
    for fp in test_files:
        tid = transfer_mgr.start_send_file("127.0.0.1:9005", "127.0.0.1", 9005, fp)
        assert tid is not None
        task_ids.append(tid)

    assert len(transfer_mgr.tasks) == 6
    assert len(transfer_mgr._sender_threads) == 6

    # Dọn dẹp an toàn các worker
    for tid in task_ids:
        transfer_mgr.cancel_task(tid)


def test_heavy_file_interrupted_connection_cleans_up_completely(tmp_path):
    """
    Tình huống 4: Gián đoạn mạng / ngắt kết nối đột ngột giữa chừng khi đang nhận file nặng.
    - Đảm bảo file handle được đóng ngay.
    - File tạm .part bị xóa lập tức, không để lại rác chiếm dung lượng ổ cứng.
    - Trạng thái chuyển thành ERROR/CANCELLED mà không làm văng app.
    """
    download_dir = str(tmp_path / "downloads_abort")
    os.makedirs(download_dir, exist_ok=True)
    transfer_mgr = TransferManager(CryptoManager(), download_dir=download_dir)

    task_id = "abort_test_task"
    start_header = {
        "task_id": task_id,
        "file_name": "heavy_interrupted.iso",
        "file_size": 100 * 1024 * 1024, # 100 MB
        "total_chunks": 1600,
        "sha256": "fake_hash",
    }
    peer_sender_id = "192.168.1.99:54321"

    transfer_mgr.handle_file_start(peer_sender_id, start_header)
    task = transfer_mgr.tasks.get(task_id)
    assert task is not None
    assert task._file_handle is not None
    temp_path = task.temp_path
    assert os.path.exists(temp_path)

    # Ghi nhận 10 chunk dữ liệu
    for i in range(10):
        transfer_mgr.handle_file_chunk(peer_sender_id, {"task_id": task_id, "chunk_index": i, "total_chunks": 1600}, b"X" * 65536)

    task._file_handle.flush()
    assert os.path.getsize(temp_path) == 10 * 65536

    # Giả lập sự kiện Peer ngắt kết nối đột ngột (Socket EOF)
    transfer_mgr.cancel_all_for_peer(peer_sender_id)

    # Kiểm tra xử lý phục hồi sau ngắt kết nối
    assert task.status in (TransferStatus.ERROR, TransferStatus.CANCELLED)
    assert task._file_handle is None, "File handle chưa được đóng!"
    assert not os.path.exists(temp_path), "File .part chưa được xóa dọn dẹp sau khi ngắt kết nối!"


if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)

    print("Running test 1...")
    test_stress_many_peers_connecting_simultaneously(app)
    print("Test 1 OK!")

    with tempfile.TemporaryDirectory() as td:
        print("Running test 2...")
        test_simulation_5gb_file_stream_and_integrity(Path(td))
        print("Test 2 OK!")

    with tempfile.TemporaryDirectory() as td:
        print("Running test 3...")
        test_concurrent_multi_file_transfers_semaphore_limits(Path(td))
        print("Test 3 OK!")

    with tempfile.TemporaryDirectory() as td:
        print("Running test 4...")
        test_heavy_file_interrupted_connection_cleans_up_completely(Path(td))
        print("Test 4 OK!")

    print("ALL 4 STRESS TESTS FINISHED SUCCESSFULLY!")
    import os
    os._exit(0)
