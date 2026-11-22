import os
import sys
import time
import socket
import hashlib
import tempfile
import pytest
from PyQt6.QtWidgets import QApplication

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(ROOT_DIR, "CODE")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from config import config
from ui.app import MainWindow
from ui.peer_list_widget import PeerListWidget
from p2p_node.transfer_manager import TransferManager, TransferTask, TransferDirection, TransferStatus
from security.crypto_manager import CryptoManager


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication([])
    return app


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_peer_list_widget_deduplication_methods(qapp):
    """Kiểm tra deduplication trực tiếp trên PeerListWidget: không nhân bản khi trùng port, loopback hoặc tên."""
    widget = PeerListWidget("Alice", 9001)
    assert widget.list_widget.count() == 0

    # 1. Thêm peer placeholder khi người dùng gõ IP:Port (127.0.0.1:9002)
    widget.add_or_update_peer("127.0.0.1:9002", "Peer_9002", "127.0.0.1", 9002, "online")
    assert widget.list_widget.count() == 1
    assert any(name == "Peer_9002" for pid, name in widget.get_all_peers())

    # 2. Bắt tay thành công trả về tên thật "Bob" với cùng IP:Port -> Cập nhật, không nhân bản
    widget.add_or_update_peer("127.0.0.1:9002", "Bob", "127.0.0.1", 9002, "online")
    assert widget.list_widget.count() == 1
    item_w = widget.list_widget.itemWidget(widget.list_widget.item(0))
    assert item_w.name_label.text() == "Bob"

    # 3. Kết nối qua alias loopback 'localhost:9002' -> Nhận diện cùng port loopback, tái sử dụng hàng cũ
    widget.add_or_update_peer("localhost:9002", "Bob", "localhost", 9002, "online")
    assert widget.list_widget.count() == 1

    # 4. UDP Discovery phát hiện cùng port 9002 và cùng tên "Bob" -> Không tạo thêm hàng rác
    widget.add_or_update_peer("192.168.1.100:9002", "Bob", "192.168.1.100", 9002, "online")
    assert widget.list_widget.count() == 1

    # 5. Xóa peer theo canonical id hoặc port
    widget.remove_peer("127.0.0.1:9002")
    assert widget.list_widget.count() == 0


def test_peer_deduplication_config_dialog_and_handshake(qapp):
    """Kiểm tra luồng kết nối nhập IP -> placeholder -> Handshake -> UDP Discovery không làm nhân bản Peer trên UI."""
    port_a = _get_free_port()
    port_b = _get_free_port()

    win_a = MainWindow(username="AliceTest", listen_port=port_a, demo_mode=True)
    try:
        # Giả lập nhập IP kết nối tới Bob trên port_b
        pid_b_manual = f"127.0.0.1:{port_b}"
        win_a._peer_info_map[pid_b_manual] = {
            "ip": "127.0.0.1", "port": port_b, "username": f"Peer_{port_b}", "status": "online"
        }
        win_a.peer_list_panel.add_or_update_peer(pid_b_manual, f"Peer_{port_b}", "127.0.0.1", port_b, "online")
        assert win_a.peer_list_panel.list_widget.count() == 1

        # Handshake ACK từ Bob trả về (username="BobReal", listen_port=port_b)
        win_a._handle_handshake(
            peer_id=f"127.0.0.1:{port_b}",
            username="BobReal",
            listen_port=port_b,
            pub_key="",
            avatar_b64="",
            is_ack=True
        )
        assert win_a.peer_list_panel.list_widget.count() == 1, "Bị nhân bản sau khi Handshake ACK!"
        info = win_a._peer_info_map.get(pid_b_manual)
        assert info is not None
        assert info["username"] == "BobReal"

        # UDP Discovery sau đó tìm thấy BobReal với IP LAN (192.168.1.50:port_b)
        win_a._on_peer_discovered(
            peer_id=f"192.168.1.50:{port_b}",
            username="BobReal",
            ip="192.168.1.50",
            port=port_b
        )
        assert win_a.peer_list_panel.list_widget.count() == 1, "Bị nhân bản sau khi UDP Discovery quét thấy!"
    finally:
        win_a.listener.stop()
        win_a.discovery.stop()
        win_a.close()
        qapp.processEvents()


def test_lan_ip_discovery_first_then_manual_loopback_connect(qapp):
    """
    Tái hiện chính xác hình ảnh người dùng gặp:
    1. Bob phát hiện Alice trước qua UDP Discovery với IP LAN (192.168.2.122:9001).
    2. Sau đó kết nối thủ công bằng IP loopback (127.0.0.1:9001) hoặc nhận Handshake từ 127.0.0.1.
    -> Đảm bảo không tạo 2 dòng Alice trên danh sách (chỉ duy nhất 1 dòng!).
    """
    port_bob = _get_free_port()
    port_alice = _get_free_port()

    win_bob = MainWindow(username="Bob", listen_port=port_bob, demo_mode=True)
    try:
        # Bước 1: UDP Discovery tìm thấy Alice trên LAN IP (192.168.2.122)
        win_bob._on_peer_discovered(
            peer_id=f"192.168.2.122:{port_alice}",
            username="Alice",
            ip="192.168.2.122",
            port=port_alice
        )
        assert win_bob.peer_list_panel.list_widget.count() == 1

        # Bước 2: Thêm thủ công hoặc Handshake từ 127.0.0.1
        win_bob.peer_list_panel.add_or_update_peer(
            f"127.0.0.1:{port_alice}", f"Peer_{port_alice}", "127.0.0.1", port_alice, "online"
        )
        assert win_bob.peer_list_panel.list_widget.count() == 1, "Không được nhân bản khi gõ IP 127.0.0.1 sau Discovery!"

        # Bước 3: Handshake ACK trả về tên 'Alice'
        win_bob._handle_handshake(
            peer_id=f"127.0.0.1:{port_alice}",
            username="Alice",
            listen_port=port_alice,
            pub_key="",
            avatar_b64="",
            is_ack=True
        )
        assert win_bob.peer_list_panel.list_widget.count() == 1, "Không được nhân bản sau Handshake ACK!"
    finally:
        win_bob.listener.stop()
        win_bob.discovery.stop()
        win_bob.close()
        qapp.processEvents()


def test_heavy_file_transfer_memory_and_integrity(qapp, tmp_path):
    """
    Kiểm thử truyền file nặng (10MB) qua TCP cục bộ:
    - Kiểm tra chunking 64KB (160 chunks), mở file 1 lần không đóng mở liên tục.
    - Kiểm tra tính băm SHA-256 tăng dần (incremental hashing), không đọc lại 10MB lúc kết thúc.
    - Kiểm tra file nhận được khớp 100% SHA-256 và bit-identical với file gốc.
    """
    crypto_mgr = CryptoManager()
    download_dir = str(tmp_path / "downloads")
    os.makedirs(download_dir, exist_ok=True)
    transfer_mgr = TransferManager(crypto_mgr, download_dir=download_dir)

    # Tạo tệp dữ liệu giả lập nặng 10MB (10 * 1024 * 1024 bytes)
    heavy_file = tmp_path / "heavy_test_file.dat"
    file_size = 10 * 1024 * 1024  # 10 MB
    chunk_pattern = b"CHATP2P_HEAVY_FILE_TRANSFER_TEST_DATA_BLOCK_" * 1000  # ~45KB
    hasher = hashlib.sha256()

    with open(heavy_file, "wb") as f:
        bytes_written = 0
        while bytes_written < file_size:
            to_write = min(len(chunk_pattern), file_size - bytes_written)
            block = chunk_pattern[:to_write]
            f.write(block)
            hasher.update(block)
            bytes_written += to_write

    expected_sha256 = hasher.hexdigest()
    assert os.path.getsize(heavy_file) == file_size

    # Giả lập quá trình nhận file từ `handle_file_start`
    sender_peer_id = "127.0.0.1:9999"
    task_id = "heavy_task_001"
    start_header = {
        "task_id": task_id,
        "file_name": "received_heavy_file.dat",
        "file_size": file_size,
        "total_chunks": (file_size + 65535) // 65536,
        "sha256": expected_sha256,
    }

    transfer_mgr.handle_file_start(sender_peer_id, start_header)
    task = transfer_mgr.tasks.get(task_id)
    assert task is not None
    assert task._file_handle is not None

    # Gửi từng chunk 64KB mô phỏng stream dữ liệu
    progress_count = 0
    def _on_progress(t):
        nonlocal progress_count
        progress_count += 1
    transfer_mgr.task_progress.connect(_on_progress)

    with open(heavy_file, "rb") as f:
        chunk_idx = 0
        while True:
            chunk_data = f.read(65536)
            if not chunk_data:
                break
            chunk_header = {
                "task_id": task_id,
                "chunk_index": chunk_idx,
                "total_chunks": (file_size + 65535) // 65536,
                "is_encrypted": False,
            }
            transfer_mgr.handle_file_chunk(sender_peer_id, chunk_header, chunk_data)
            chunk_idx += 1

    # Kiểm tra task hoàn tất
    assert task.status == TransferStatus.COMPLETED
    assert task._file_handle is None  # Đã đóng file an toàn

    # Kiểm tra file đã được lưu vào thư mục download
    saved_file = os.path.join(download_dir, "received_heavy_file.dat")
    assert os.path.exists(saved_file)
    assert os.path.getsize(saved_file) == file_size

    # Kiểm tra tính toàn vẹn băm của file đã nhận
    with open(saved_file, "rb") as f:
        saved_sha256 = hashlib.sha256(f.read()).hexdigest()
    assert saved_sha256 == expected_sha256

    # Đảm bảo có throttling progress (không phát ra đủ 160 lần tín hiệu làm nghẽn UI)
    assert progress_count < 160
    assert progress_count > 0


def test_heavy_file_cancel_cleans_up_handle_and_part_file(tmp_path):
    """Kiểm tra khi hủy truyền giữa chừng: File handle được đóng và file .part bị xóa dọn dẹp sạch sẽ."""
    download_dir = str(tmp_path / "downloads_cancel")
    os.makedirs(download_dir, exist_ok=True)
    transfer_mgr = TransferManager(CryptoManager(), download_dir=download_dir)

    task_id = "cancel_task_001"
    start_header = {
        "task_id": task_id,
        "file_name": "cancelled_file.bin",
        "file_size": 5 * 1024 * 1024,
        "total_chunks": 80,
        "sha256": "fakehash",
    }
    transfer_mgr.handle_file_start("127.0.0.1:9998", start_header)
    task = transfer_mgr.tasks.get(task_id)
    assert task is not None
    assert task._file_handle is not None

    temp_path = task.temp_path
    assert os.path.exists(temp_path)

    # Ghi 2 chunks
    transfer_mgr.handle_file_chunk("127.0.0.1:9998", {"task_id": task_id, "chunk_index": 0, "total_chunks": 80}, b"A" * 65536)
    transfer_mgr.handle_file_chunk("127.0.0.1:9998", {"task_id": task_id, "chunk_index": 1, "total_chunks": 80}, b"B" * 65536)

    # Hủy task
    transfer_mgr.cancel_task(task_id)

    # Kiểm tra handle đã đóng và file .part đã bị xóa
    assert task._file_handle is None
    assert not os.path.exists(temp_path), "File tạm .part phải được xóa khi tác vụ bị hủy!"
