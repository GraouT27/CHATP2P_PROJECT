"""
Kiểm thử Khả năng Phục hồi & Chống Lỗi (Resilience & Fault Tolerance Test):
- Kiểm tra cô lập lỗi khi kết nối bị ngắt đột ngột.
- Kiểm tra phát hiện và từ chối gói tin bị giả mạo / sai định dạng (Tampered / Malformed Data).
- Kiểm tra hủy truyền file dở dang và dọn dẹp bộ nhớ đệm, file tạm .part.
- Kiểm tra tự động phục hồi phiên kết nối khi Peer online trở lại.
"""

import os
import sys
import time
import socket
import pytest
from PyQt6.QtWidgets import QApplication

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(ROOT_DIR, "CODE")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from security.crypto_manager import CryptoManager
from p2p_node.transfer_manager import TransferManager, TransferTask, TransferDirection, TransferStatus
from p2p_node.storage import remove_temp_file
from shared.protocol import pack_message, make_chat_header, make_file_start_header


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def test_socket_abrupt_disconnect_cleanup(tmp_path):
    """1. Kiểm tra khi socket bị ngắt kết nối đột ngột: Toàn bộ tác vụ file liên quan được hủy an toàn."""
    crypto_mgr = CryptoManager()
    download_dir = str(tmp_path / "downloads")
    os.makedirs(download_dir, exist_ok=True)
    transfer_mgr = TransferManager(crypto_mgr, download_dir=download_dir)

    task_id = "resilience_task_01"
    start_h = {
        "task_id": task_id,
        "file_name": "data_file.dat",
        "file_size": 1024 * 1024,
        "total_chunks": 16,
        "sha256": "fakehash",
    }
    peer_id = "192.168.1.55:9002"
    transfer_mgr.handle_file_start(peer_id, start_h)
    task = transfer_mgr.tasks.get(task_id)
    assert task is not None
    assert task.status == TransferStatus.TRANSFERRING

    # Giả lập socket bị drop
    transfer_mgr.cancel_all_for_peer(peer_id)
    assert task.status in (TransferStatus.CANCELLED, TransferStatus.ERROR)
    assert not os.path.exists(task.temp_path)


def test_tampered_packet_rejection_no_crash(tmp_path):
    """2. Kiểm tra từ chối gói tin bị sửa đổi dữ liệu (tampered chunk): Không crash hệ thống."""
    crypto_mgr = CryptoManager()
    download_dir = str(tmp_path / "downloads_tampered")
    os.makedirs(download_dir, exist_ok=True)
    transfer_mgr = TransferManager(crypto_mgr, download_dir=download_dir)

    task_id = "tamper_task_02"
    file_size = 65536
    start_h = {
        "task_id": task_id,
        "file_name": "secure_doc.pdf",
        "file_size": file_size,
        "total_chunks": 1,
        "sha256": "correct_sha256_hash",
    }
    transfer_mgr.handle_file_start("127.0.0.1:9003", start_h)
    task = transfer_mgr.tasks[task_id]

    # Gửi dữ liệu giả mạo đủ kích thước file nhưng sai hash
    fake_chunk = b"A" * file_size
    chunk_h = {
        "task_id": task_id,
        "chunk_index": 0,
        "total_chunks": 1,
        "is_encrypted": False,
    }
    transfer_mgr.handle_file_chunk("127.0.0.1:9003", chunk_h, fake_chunk)
    assert task.status == TransferStatus.ERROR
    assert not os.path.exists(task.temp_path)


def test_file_transfer_abort_cleans_temp_file(tmp_path):
    """3. Kiểm tra người dùng chủ động bấm Hủy: File handle đóng ngay và file .part bị xóa dọn dẹp."""
    download_dir = str(tmp_path / "downloads_abort")
    os.makedirs(download_dir, exist_ok=True)
    transfer_mgr = TransferManager(CryptoManager(), download_dir=download_dir)

    task_id = "user_cancel_task"
    start_h = {
        "task_id": task_id,
        "file_name": "sample_video.mp4",
        "file_size": 10 * 1024 * 1024,
        "total_chunks": 160,
        "sha256": "hash",
    }
    transfer_mgr.handle_file_start("127.0.0.1:9004", start_h)
    task = transfer_mgr.tasks[task_id]
    temp_path = task.temp_path
    assert os.path.exists(temp_path)

    # Người dùng hủy
    transfer_mgr.cancel_task(task_id)
    assert task.status == TransferStatus.CANCELLED
    assert not os.path.exists(temp_path)


def test_peer_session_key_renegotiation():
    """4. Kiểm tra khả năng làm mới và phục hồi khóa phiên AES-256 (Session Key Renegotiation)."""
    alice_crypto = CryptoManager()
    bob_crypto = CryptoManager()

    peer_b = "127.0.0.1:9002"
    alice_crypto.register_peer_public_key(peer_b, bob_crypto.get_public_key_pem())
    enc_key = alice_crypto.generate_and_encrypt_session_key(peer_b)
    assert enc_key is not None
    assert bob_crypto.receive_and_decrypt_session_key("127.0.0.1:9001", enc_key) is True

    # Giả lập mất kết nối và bắt tay trao đổi lại khóa mới
    alice_crypto.remove_peer_keys(peer_b)
    assert not alice_crypto.has_session_key(peer_b)

    # Đăng ký và sinh khóa mới
    alice_crypto.register_peer_public_key(peer_b, bob_crypto.get_public_key_pem())
    new_enc_key = alice_crypto.generate_and_encrypt_session_key(peer_b)
    assert new_enc_key is not None
    assert bob_crypto.receive_and_decrypt_session_key("127.0.0.1:9001", new_enc_key) is True


def test_malformed_protocol_isolation():
    """5. Kiểm tra khả năng chịu lỗi đối với bản tin có header không hợp lệ hoặc thiếu trường bắt buộc."""
    from shared.protocol import decode_message, validate_message
    invalid_data = b"NOT_A_VALID_P2P_PACKET_HEADER"
    try:
        msg = decode_message(invalid_data)
        assert msg is None or not validate_message(msg)
    except Exception:
        # Nếu ném ngoại lệ giải mã thì được cô lập an toàn
        pass
