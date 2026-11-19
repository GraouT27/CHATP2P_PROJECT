"""
Kiểm thử Bảo mật Chuyên sâu, Tấn công Thâm nhập & Xung đột Đa luồng [BT_TV2].
Bao gồm các nhóm kiểm thử:
1. Path Traversal & Arbitrary File Overwrite (storage.py)
2. Malicious Avatar Payload / Decompression Bomb / .exe Disguised (app.py)
3. Cross-IP Identity Spoofing & Username Control-Char Injection (app.py)
4. Type Confusion, Bool/Port Bypass & Oversized Payload DoS (validator.py)
5. GUI Render DoS, Model/Cache Memory Leak & Invalid Types (chat_widgets.py, peer_list_widget.py)
6. Anti-Downgrade Attack & Ciphertext Tampering (handler.py)
7. Forward Plaintext Leakage Prevention (app.py)
8. Zombie Ephemeral Disconnect Leak & PeerList UserRole Isolation (app.py, peer_list_widget.py)
9. P2PListener Concurrent Flood & Thread Safety (listener.py)
10. End-to-End Real Loopback Handshake -> ACK -> Key Exchange -> Encrypted Emoji/Reply Chat
"""

import os
import sys
import time
import struct
import socket
import base64
import threading
import pytest
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPixmap, QImage, QPainter
from PyQt6.QtWidgets import QApplication, QStyleOptionViewItem

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(ROOT_DIR, "CODE")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from config import config
from security.crypto_manager import CryptoManager
from shared.protocol import (
    make_handshake_header,
    make_handshake_ack_header,
    make_key_exchange_header,
    make_chat_header,
    make_file_chunk_header,
)
from shared.validator import validate_header
from p2p_node.storage import (
    sanitize_filename,
    resolve_filename,
    get_temp_filepath,
    save_avatar_cache,
)
from p2p_node.handler import MessageHandler
from p2p_node.listener import P2PListener
from ui.chat_widgets import (
    AvatarWidget,
    MessageData,
    MessageListModel,
    MessageDelegate,
)
from ui.peer_list_widget import PeerListWidget
from ui.app import MainWindow


@pytest.fixture(scope="session")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# =========================================================
# 1. PATH TRAVERSAL & ARBITRARY FILE OVERWRITE
# =========================================================

def test_path_traversal_and_reserved_names_blocked(tmp_path):
    base = str(tmp_path)
    assert "/" not in sanitize_filename("../../etc/passwd")
    assert "\\" not in sanitize_filename("..\\..\\Windows\\win.ini")
    assert sanitize_filename("CON") == "_CON"
    assert sanitize_filename("") == "received_file"

    resolved = resolve_filename(base, "../../../../evil_payload.bat")
    assert os.path.abspath(resolved).startswith(os.path.abspath(base) + os.sep)
    assert os.path.basename(resolved) == "evil_payload.bat"

    temp_p = get_temp_filepath(base, "../id", "..\\..\\evil")
    assert os.path.abspath(temp_p).startswith(os.path.abspath(base) + os.sep)

    av_p = save_avatar_cache(base, "../127.0.0.1:9001/../../evil", b"dummy")
    assert av_p is not None
    assert os.path.abspath(av_p).startswith(os.path.abspath(base) + os.sep)


# =========================================================
# 2. AVATAR MALICIOUS PAYLOAD & DECOMPRESSION BOMB
# =========================================================

def test_avatar_executable_svg_and_oversized_blocked(qapp, tmp_path):
    old_dl = config.download_dir
    config.download_dir = str(tmp_path)
    try:
        # 1. File thực thi MZ (.exe) giả mạo làm avatar
        fake_exe = base64.b64encode(b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 64).decode("utf-8")
        assert MainWindow._save_safe_avatar("127.0.0.1:9002", fake_exe) == ""

        # 2. Payload SVG XSS giả mạo
        fake_svg = base64.b64encode(b'<svg onload="alert(1)"></svg>').decode("utf-8")
        assert MainWindow._save_safe_avatar("127.0.0.1:9002", fake_svg) == ""

        # 3. Chuỗi base64 khổng lồ (> 350KB)
        huge_b64 = "A" * 360_000
        assert MainWindow._save_safe_avatar("127.0.0.1:9002", huge_b64) == ""

        # 4. PNG hợp lệ -> giải mã, scale <=128x128 và lưu sạch
        img = QImage(256, 256, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.cyan)
        src_png = tmp_path / "valid.png"
        assert img.save(str(src_png), "PNG")
        valid_b64 = base64.b64encode(src_png.read_bytes()).decode("utf-8")

        saved_path = MainWindow._save_safe_avatar("127.0.0.1:9002", valid_b64)
        assert saved_path != ""
        assert os.path.exists(saved_path)
        reloaded = QImage(saved_path)
        assert not reloaded.isNull()
        assert reloaded.width() <= 128 and reloaded.height() <= 128
    finally:
        config.download_dir = old_dl


# =========================================================
# 3. CROSS-IP USERNAME SPOOFING & SANITIZATION
# =========================================================

def test_cross_ip_username_spoofing_blocked(qapp):
    port = _get_free_port()
    win = MainWindow(username="Defender", listen_port=port, demo_mode=True)
    try:
        win._peer_info_map["192.168.1.10:9001"] = {
            "ip": "192.168.1.10",
            "port": 9001,
            "username": "Alice",
            "status": "online",
        }
        # Kẻ tấn công ở IP khác giả mạo tên "Alice"
        spoofed = win._find_canonical_peer_id("10.66.66.66:54321", sender_name="Alice", sender_port=0)
        assert spoofed == "10.66.66.66:54321"
        assert spoofed != "192.168.1.10:9001"

        # Cùng IP thật sự gửi trên ephemeral port thì vẫn ánh xạ đúng
        legit = win._find_canonical_peer_id("192.168.1.10:54321", sender_name="Alice", sender_port=0)
        assert legit == "192.168.1.10:9001"

        # Kiểm tra lọc ký tự điều khiển trong username
        assert win._sanitize_username("Bad\x00\n\tUser\x7f") == "BadUser"
        assert len(win._sanitize_username("X" * 200)) == 64
    finally:
        win.listener.stop()
        win.discovery.stop()
        win.close()


# =========================================================
# 4. VALIDATOR TYPE CONFUSION & PROTOCOL ABUSE
# =========================================================

def test_validator_rejects_bool_ports_type_confusion_and_oversize():
    # Bool trong Python là subclass của int (True == 1) -> phải chặn
    h_bool_port = make_handshake_header("Attacker", True, "PEM")
    ok, _ = validate_header(h_bool_port)
    assert not ok

    # Port ngoài dải 1..65535
    ok, _ = validate_header(make_handshake_header("Attacker", 70000, "PEM"))
    assert not ok
    ok, _ = validate_header(make_handshake_header("Attacker", 0, "PEM"))
    assert not ok

    # Type confusion ở reply_to / forward_from
    h_bad_reply = make_chat_header("Attacker", "hi", reply_to="string_not_dict")
    ok, _ = validate_header(h_bad_reply)
    assert not ok

    h_bad_fwd = make_chat_header("Attacker", "hi", forward_from=["list_not_dict"])
    ok, _ = validate_header(h_bad_fwd)
    assert not ok

    # sender_port âm hoặc bool
    h_bad_sp = make_chat_header("Attacker", "hi")
    h_bad_sp["sender_port"] = -1
    ok, _ = validate_header(h_bad_sp)
    assert not ok

    # Oversized RSA public key
    ok, _ = validate_header(make_handshake_header("Attacker", 9001, "K" * 9000))
    assert not ok

    # Negative payload_size
    h_neg_payload = make_chat_header("Attacker", "hi")
    h_neg_payload["payload_size"] = -100
    ok, _ = validate_header(h_neg_payload)
    assert not ok


# =========================================================
# 5. GUI RENDER DOS & BOUNDED MEMORY
# =========================================================

def test_gui_dos_long_text_invalid_types_and_model_cap(qapp):
    # AvatarWidget size <= 0 không gây crash
    av = AvatarWidget("A", size=0, color="not_a_color")
    assert av.width() >= 16 and av.height() >= 16

    # MessageData xử lý an toàn nội dung 500KB, timestamp NaN/-1e20, reply_to sai kiểu
    m_dos = MessageData(
        msg_id="dos1",
        sender=None,
        content="A" * 500_000,
        timestamp=-1e20,
        is_sent=False,
        reply_to="malformed_string",
        forward_from=12345,
    )
    assert len(m_dos.content) <= MessageData.MAX_CONTENT_LEN + 64
    assert m_dos.time_str == "--:--"
    assert m_dos.reply_to is None
    assert m_dos.forward_from is None

    # Dict reply_to chứa giá trị None/int vẫn paint bình thường không TypeError
    m_weird_dict = MessageData(
        msg_id="dos2",
        sender="Peer",
        content="ok",
        timestamp=float("nan"),
        is_sent=False,
        reply_to={"sender": None, "content": 999999},
        forward_from={"original_sender": None},
    )
    assert m_weird_dict.time_str == "--:--"

    model = MessageListModel()
    delegate = MessageDelegate()
    model.add_messages([m_dos, m_weird_dict])
    opt = QStyleOptionViewItem()
    opt.rect = QRect(0, 0, 600, 120)
    for row in range(2):
        idx = model.index(row, 0)
        sz = delegate.sizeHint(opt, idx)
        pm = QPixmap(600, sz.height())
        p = QPainter(pm)
        try:
            delegate.paint(p, opt, idx)
        finally:
            p.end()

    # Kiểm tra giới hạn MAX_MESSAGES chống tràn RAM
    bulk = [MessageData(f"id_{i}", "U", f"msg {i}", time.time(), True) for i in range(5100)]
    model.clear()
    model.add_messages(bulk)
    assert model.rowCount() == MessageListModel.MAX_MESSAGES
    assert model.get_message(model.rowCount() - 1).msg_id == "id_5099"


# =========================================================
# 6. ANTI-DOWNGRADE & CIPHERTEXT TAMPERING
# =========================================================

def test_anti_downgrade_drops_unencrypted_when_session_active(qapp):
    alice_crypto = CryptoManager()
    bob_crypto = CryptoManager()
    bob_crypto.register_peer_public_key("127.0.0.1:9001", alice_crypto.get_public_key_pem())
    enc_k = bob_crypto.generate_and_encrypt_session_key("127.0.0.1:9001")
    assert alice_crypto.receive_and_decrypt_session_key("127.0.0.1:9002", enc_k)

    handler = MessageHandler(alice_crypto)
    received = []
    chunks = []
    handler.chat_received.connect(lambda pid, d: received.append((pid, d)))
    handler.file_chunk_received.connect(lambda pid, h, c: chunks.append((pid, h, c)))

    # 1. Tấn công hạ cấp (Downgrade): giả mạo tin nhắn chat không mã hóa dù đã có session key
    spoof_plain = make_chat_header("Bob", "Chuyển tiền vào tài khoản X", is_encrypted=False)
    spoof_plain["sender_port"] = 9002
    handler.process_incoming("127.0.0.1:55111", spoof_plain, b"")
    assert len(received) == 0

    # 2. Tấn công chèn chunk file không mã hóa khi đã có session key
    spoof_chunk = make_file_chunk_header("Bob", "f1", 0, 4, "ab" * 32, is_encrypted=False)
    spoof_chunk["sender_port"] = 9002
    handler.process_incoming("127.0.0.1:55111", spoof_chunk, b"evil")
    assert len(chunks) == 0

    # 3. Tin nhắn mã hóa bị sửa đổi ciphertext (tamper) -> báo lỗi giải mã, không lộ text giả
    cipher_b64, nonce_b64 = bob_crypto.encrypt_text("127.0.0.1:9001", "Tin nhắn thật")
    tampered_h = make_chat_header("Bob", cipher_b64[:-4] + "XXXX", is_encrypted=True, nonce=nonce_b64)
    tampered_h["sender_port"] = 9002
    handler.process_incoming("127.0.0.1:55112", tampered_h, b"")
    assert len(received) == 1
    assert "Lỗi giải mã" in received[0][1]["content"]


# =========================================================
# 7. FORWARD PLAINTEXT LEAK PREVENTION
# =========================================================

def test_forward_encrypts_message_and_strips_original_content(qapp, monkeypatch):
    import ui.app as app_mod

    port = _get_free_port()
    win = MainWindow(username="Alice", listen_port=port, demo_mode=True)
    bob_crypto = CryptoManager()
    try:
        target_pid = "127.0.0.1:9002"
        win._peer_info_map[target_pid] = {
            "ip": "127.0.0.1", "port": 9002, "username": "Bob", "status": "online"
        }
        win.peer_list_panel.add_or_update_peer(target_pid, "Bob", "127.0.0.1", 9002, "online")

        # Thiết lập khóa phiên giữa win (Alice) và Bob
        win.crypto_mgr.register_peer_public_key(target_pid, bob_crypto.get_public_key_pem())
        enc_key = win.crypto_mgr.generate_and_encrypt_session_key(target_pid)
        assert bob_crypto.receive_and_decrypt_session_key(f"127.0.0.1:{port}", enc_key)

        class FakeForwardDlg:
            def __init__(self, *args, **kwargs):
                pass
            def exec(self):
                return True
            def get_selected_peers(self):
                return [target_pid]

        sent_packets = []
        monkeypatch.setattr(app_mod, "ForwardDialog", FakeForwardDlg)
        monkeypatch.setattr(
            app_mod,
            "send_message_direct",
            lambda ip, p, h, payload=b"": (sent_packets.append((ip, p, h)), (True, ""))[1],
        )

        secret_msg = MessageData("m1", "Charlie", "BÍ MẬT QUỐC GIA 999", time.time(), False)
        win._trigger_forward(secret_msg)

        assert len(sent_packets) == 1
        _, _, hdr = sent_packets[0]
        assert hdr["is_encrypted"] is True
        assert hdr["text"] != "BÍ MẬT QUỐC GIA 999"
        assert "original_content" not in hdr["forward_from"]
        assert hdr["sender_port"] == port

        decrypted = bob_crypto.decrypt_text(f"127.0.0.1:{port}", hdr["text"], hdr["nonce"])
        assert decrypted == "BÍ MẬT QUỐC GIA 999"
    finally:
        win.listener.stop()
        win.discovery.stop()
        win.close()


# =========================================================
# 8. ZOMBIE DISCONNECT LEAK & PEERLIST USERROLE
# =========================================================

def test_ephemeral_disconnect_no_zombie_model_and_peerlist_userrole(qapp):
    port = _get_free_port()
    win = MainWindow(username="Tester", listen_port=port, demo_mode=True)
    try:
        ephemeral_id = "127.0.0.1:59876"
        win._on_peer_disconnected(ephemeral_id)
        assert ephemeral_id not in win._message_models

        plist = PeerListWidget("Me", port)
        plist.add_or_update_peer("127.0.0.1:9001", "P1", "127.0.0.1", 9001, "online")
        plist.add_or_update_peer("127.0.0.1:9002", "P2", "127.0.0.1", 9002, "online")
        picked = []
        plist.peer_selected.connect(lambda pid: picked.append(pid))
        plist.select_peer("127.0.0.1:9002")
        assert picked == ["127.0.0.1:9002"]
    finally:
        win.listener.stop()
        win.discovery.stop()
        win.close()


# =========================================================
# 9. LISTENER CONCURRENCY FLOOD & MALFORMED FRAMING
# =========================================================

def test_listener_concurrent_malformed_and_flood_resilience(qapp):
    port = _get_free_port()
    handler = MessageHandler(CryptoManager())
    listener = P2PListener(port=port, handler=handler)
    started_port = []
    listener.server_started.connect(lambda p: started_port.append(p))
    listener.start()

    deadline = time.time() + 3.0
    while not started_port and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    assert started_port == [port]

    def hammer(idx: int):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.5) as s:
                if idx % 2 == 0:
                    # Frame length khổng lồ (tấn công cạn kiệt RAM)
                    s.sendall(struct.pack("!I", 100 * 1024 * 1024))
                else:
                    # JSON rác
                    s.sendall(struct.pack("!I", 12) + b"{not_json!!!")
        except Exception:
            pass

    threads = [threading.Thread(target=hammer, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=3.0)

    qapp.processEvents()
    listener.stop()
    assert len(listener._active_connections) == 0


# =========================================================
# 10. END-TO-END LOOPBACK HANDSHAKE -> KEY EXCHANGE -> CHAT
# =========================================================

def test_real_loopback_handshake_key_exchange_and_encrypted_chat(qapp):
    port_a = _get_free_port()
    port_b = _get_free_port()
    assert port_a != port_b

    win_a = MainWindow(username="AliceE2E", listen_port=port_a, demo_mode=True)
    win_b = MainWindow(username="BobE2E", listen_port=port_b, demo_mode=True)

    try:
        # Chờ cả 2 P2PListener mở socket xong
        deadline = time.time() + 3.0
        while time.time() < deadline:
            qapp.processEvents()
            if win_a.listener.isRunning() and win_b.listener.isRunning():
                break
            time.sleep(0.02)

        pid_a = f"127.0.0.1:{port_a}"
        pid_b = f"127.0.0.1:{port_b}"

        # Alice bắt đầu Handshake tới Bob
        win_a._peer_info_map[pid_b] = {"ip": "127.0.0.1", "port": port_b, "username": "BobE2E", "status": "online"}
        win_a.peer_list_panel.add_or_update_peer(pid_b, "BobE2E", "127.0.0.1", port_b, "online")
        win_a._on_peer_selected(pid_b)
        win_a._send_handshake(pid_b, "127.0.0.1", port_b)

        # Chờ trao đổi Handshake -> Handshake ACK -> Key Exchange hoàn tất
        deadline = time.time() + 5.0
        while time.time() < deadline:
            qapp.processEvents()
            if (
                win_a.crypto_mgr.has_session_key(pid_b)
                and win_b.crypto_mgr.has_session_key(pid_a)
                and pid_a in win_b._peer_info_map
            ):
                break
            time.sleep(0.02)

        assert win_a.crypto_mgr.has_session_key(pid_b), "Alice chưa nhận được Session Key của Bob!"
        assert win_b.crypto_mgr.has_session_key(pid_a), "Bob chưa có Session Key của Alice!"

        # Alice gửi tin nhắn UTF-8 + Emoji + Reply thực sự qua TCP localhost tới Bob
        win_a.reply_preview.set_reply("BobE2E", "Tin nhắn trước đó", "prev-uuid")
        win_a.input_field.setText("Xin chào Bob 🚀🔒 Tiếng Việt UTF-8!")
        win_a._send_chat_message()

        deadline = time.time() + 5.0
        bob_received = False
        while time.time() < deadline:
            qapp.processEvents()
            model_b = win_b._message_models.get(pid_a)
            if model_b:
                for row in range(model_b.rowCount()):
                    m = model_b.get_message(row)
                    if m and not m.is_system and "Xin chào Bob 🚀🔒" in m.content:
                        bob_received = True
                        assert m.sender == "AliceE2E"
                        assert m.reply_to is not None
                        assert m.reply_to["sender"] == "BobE2E"
                        break
            if bob_received:
                break
            time.sleep(0.02)

        assert bob_received, "Bob không nhận hoặc giải mã được tin nhắn E2E qua loopback!"
    finally:
        win_a.listener.stop()
        win_a.discovery.stop()
        win_b.listener.stop()
        win_b.discovery.stop()
        win_a.close()
        win_b.close()
        qapp.processEvents()
