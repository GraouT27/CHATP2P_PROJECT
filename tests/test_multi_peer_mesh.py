"""
Kiểm thử tích hợp 3 Peer (Alice:9101, Bob:9102, Eve:9103) cùng IP:
Xác minh không còn lỗi tra cứu nhầm khóa AES-256 giữa các port khác nhau trên cùng 1 IP.
"""

import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(ROOT_DIR, "CODE")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from security.crypto_manager import CryptoManager
from p2p_node.handler import MessageHandler
from shared.protocol import (
    make_handshake_header,
    make_key_exchange_header,
    make_chat_header,
)


def test_three_peers_same_ip_independent_session_keys():
    """Alice (9101), Bob (9102), Eve (9103) cùng IP 127.0.0.1 trao đổi khóa độc lập và giải mã đúng."""
    alice_crypto = CryptoManager()
    bob_crypto = CryptoManager()
    eve_crypto = CryptoManager()

    alice_h = MessageHandler(alice_crypto)
    bob_h = MessageHandler(bob_crypto)
    eve_h = MessageHandler(eve_crypto)

    # 1. Bob nhận handshake từ Alice (127.0.0.1:9101) và trao đổi khóa AES-256 với Alice
    bob_crypto.register_peer_public_key("127.0.0.1:9101", alice_crypto.get_public_key_pem())
    enc_k_ab = bob_crypto.generate_and_encrypt_session_key("127.0.0.1:9101")
    assert enc_k_ab is not None
    assert alice_crypto.receive_and_decrypt_session_key("127.0.0.1:9102", enc_k_ab) is True

    # 2. Bob kiểm tra khóa của Eve (127.0.0.1:9103) -> PHẢI là False (không được dùng nhầm khóa của Alice!)
    assert bob_crypto.has_session_key("127.0.0.1:9103") is False

    # 3. Bob và Eve trao đổi khóa riêng biệt
    bob_crypto.register_peer_public_key("127.0.0.1:9103", eve_crypto.get_public_key_pem())
    enc_k_be = bob_crypto.generate_and_encrypt_session_key("127.0.0.1:9103")
    assert enc_k_be is not None
    assert eve_crypto.receive_and_decrypt_session_key("127.0.0.1:9102", enc_k_be) is True

    # 4. Eve mã hóa tin nhắn gửi Bob (port 9103 -> 9102)
    ct_b64, nonce_b64 = eve_crypto.encrypt_text("127.0.0.1:9102", "Chào Bob, mình là Eve!")
    chat_hdr = make_chat_header(
        username="Eve",
        text=ct_b64,
        is_encrypted=True,
        nonce=nonce_b64,
    )
    chat_hdr["sender_port"] = 9103

    received_msgs = []
    bob_h.chat_received.connect(lambda pid, data: received_msgs.append((pid, data)))
    bob_h.process_incoming("127.0.0.1:55444", chat_hdr, b"")

    assert len(received_msgs) == 1
    assert received_msgs[0][1]["content"] == "Chào Bob, mình là Eve!"


def test_forward_message_history_and_model_data_roles():
    """Kiểm tra Forward lưu lịch sử phía người gửi, giữ đúng metadata Carol->Alice->Bob và không lộ object repr."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
    from ui.app import MainWindow
    from ui.chat_widgets import MessageData, MessageListModel

    app = QApplication.instance()
    if not app:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication([])

    # 1. Kiểm tra MessageListModel.data() với các Qt roles
    model = MessageListModel()
    m = MessageData("m1", "Carol", "Nội dung gốc", 1700000000.0, False)
    model.add_message(m)
    idx = model.index(0, 0)
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) is m
    assert model.data(idx, Qt.ItemDataRole.ToolTipRole) == "Nội dung gốc"
    assert model.data(idx, Qt.ItemDataRole.AccessibleTextRole) == "Nội dung gốc"
    assert model.data(idx, Qt.ItemDataRole.DecorationRole) is None
    assert str(m) == "Nội dung gốc"
    assert "MessageData object at" not in str(m)

    # 2. Kiểm tra Forward từ Alice sang Bob (tin gốc của Carol)
    win_alice = MainWindow(username="Alice", listen_port=9961, demo_mode=True)
    try:
        bob_pid = "127.0.0.1:9962"
        win_alice._on_peer_discovered(bob_pid, "Bob", "127.0.0.1", 9962)

        # Kiểm tra GROUP_ALL không lọt vào danh sách Forward
        peers_for_fwd = win_alice.peer_list_panel.get_all_peers(online_only=True)
        assert all(pid != "GROUP_ALL" for pid, _ in peers_for_fwd)

        # Mô phỏng logic tạo bản ghi Forward khi người dùng xác nhận trong ForwardDialog
        carol_msg = MessageData("c1", "Carol", "Hẹn gặp lúc 8h", 1700000000.0, False)
        fwd_from = {"original_sender": "Carol", "forwarded_by": "Alice"}
        win_alice._message_models[bob_pid] = MessageListModel(win_alice)
        win_alice._message_models[bob_pid].add_message(
            MessageData(
                msg_id="f1",
                sender="Alice",
                content=carol_msg.content,
                timestamp=1700000010.0,
                is_sent=True,
                forward_from=fwd_from,
            )
        )
        win_alice.peer_list_panel.update_last_message(bob_pid, f"↪ Bạn: {carol_msg.content}")

        saved = win_alice._message_models[bob_pid].get_message(0)
        assert saved is not None
        assert saved.content == "Hẹn gặp lúc 8h"
        assert saved.forward_from == {"original_sender": "Carol", "forwarded_by": "Alice"}
        assert "↪ Bạn: Hẹn gặp lúc 8h" in win_alice.peer_list_panel.get_peer_widget(bob_pid).last_msg_label.text()
    finally:
        win_alice.listener.stop()
        win_alice.discovery.stop()
        win_alice.close()
