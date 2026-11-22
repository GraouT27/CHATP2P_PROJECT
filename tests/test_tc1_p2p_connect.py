"""
Kiểm thử TC_1: Khởi tạo & Kết nối P2P (Main UI / Config) giữa 2 tiến trình độc lập.
- Tiến trình 1 (Peer A): Cổng 9001, Avatar alice.png
- Tiến trình 2 (Peer B - subprocess độc lập): Cổng 9002, Avatar bob.png
- Thao tác: Nhập IP/Port của Peer B (127.0.0.1:9002) trên ConfigDialog của Peer A và bấm Lưu & Áp Dụng.
- Kỳ vọng:
  + 2 Peer bắt tay (Handshake -> Handshake ACK -> Key Exchange) trao đổi khóa RSA/AES-256 thành công.
  + Cả 2 bên hiển thị trạng thái Online và nạp được Avatar của đối phương trong danh sách Peer.
"""

import os
import sys
import json
import time
import socket
import subprocess
import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(ROOT_DIR, "CODE")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import ui.app as app_mod
from config import config
from ui.app import MainWindow
from ui.dialogs import ConfigDialog


PEER_B_SCRIPT = r'''
import os, sys, json, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, sys.argv[1])

from PyQt6.QtWidgets import QApplication
from config import config
from ui.app import MainWindow

config.download_dir = sys.argv[2]
app = QApplication([])
win_b = MainWindow(username="PeerB_9102", listen_port=9102, demo_mode=True)
bob_av = os.path.join(sys.argv[1], "resources", "avatars", "bob.png")
if os.path.exists(bob_av):
    win_b.avatar_path = bob_av
    win_b.peer_list_panel.update_self_info(win_b.username, win_b.listen_port, bob_av)

deadline = time.time() + 10.0
while not win_b.listener.isRunning() and time.time() < deadline:
    app.processEvents()
    time.sleep(0.02)

print("TC1_JSON:" + json.dumps({"event": "READY", "port": 9102}), flush=True)

peer_a_id = "127.0.0.1:9101"
reported_connected = False
deadline = time.time() + 15.0
while time.time() < deadline:
    app.processEvents()
    target_id = peer_a_id
    if target_id not in win_b._peer_info_map:
        for pid, inf in win_b._peer_info_map.items():
            if inf.get("port") == 9101:
                target_id = pid
                break
    info = win_b._peer_info_map.get(target_id, {})
    has_key = win_b.crypto_mgr.has_session_key(target_id)
    status = win_b.peer_list_panel.get_peer_status(target_id)
    av_path = info.get("avatar_path", "")
    if not reported_connected and has_key and status == "online" and av_path and os.path.exists(av_path):
        reported_connected = True
        print("TC1_JSON:" + json.dumps({
            "event": "CONNECTED",
            "has_key": has_key,
            "status": status,
            "username": info.get("username"),
            "avatar_exists": os.path.exists(av_path),
        }), flush=True)
    time.sleep(0.02)

win_b.listener.stop()
win_b.discovery.stop()
win_b.close()
'''


@pytest.fixture(scope="session")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def _wait_port_free(port: int, timeout: float = 8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("0.0.0.0", port))
            s.close()
            return
        except OSError:
            s.close()
            time.sleep(0.1)


def _read_tc1_event(proc, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        line = line.strip()
        if line.startswith("TC1_JSON:"):
            return json.loads(line[len("TC1_JSON:"):])
    raise AssertionError(f"Không nhận được sự kiện TC1_JSON từ Peer B. stderr={proc.stderr.read()}")


def test_tc1_p2p_two_independent_processes_config_connect(qapp, tmp_path, monkeypatch):
    qapp.setQuitOnLastWindowClosed(False)
    _wait_port_free(9101)
    _wait_port_free(9102)

    old_dl = config.download_dir
    dl_a = tmp_path / "dl_a"
    dl_b = tmp_path / "dl_b"
    dl_a.mkdir()
    dl_b.mkdir()
    config.download_dir = str(dl_a)

    # Khởi chạy Peer B (Port 9102) trong một tiến trình OS hoàn toàn độc lập
    proc_b = subprocess.Popen(
        [sys.executable, "-c", PEER_B_SCRIPT, CODE_DIR, str(dl_b)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    win_a = None
    try:
        ready_msg = _read_tc1_event(proc_b, timeout=10.0)
        assert ready_msg["event"] == "READY" and ready_msg["port"] == 9102

        # Khởi chạy Peer A (Port 9101) ở tiến trình hiện tại
        win_a = MainWindow(username="PeerA_9101", listen_port=9101, demo_mode=True)
        alice_av = os.path.join(CODE_DIR, "resources", "avatars", "alice.png")
        assert os.path.exists(alice_av)
        win_a.avatar_path = alice_av
        win_a.peer_list_panel.update_self_info(win_a.username, win_a.listen_port, alice_av)

        deadline = time.time() + 5.0
        while not win_a.listener.isRunning() and time.time() < deadline:
            qapp.processEvents()
            time.sleep(0.02)

        # Giả lập thao tác người dùng mở ConfigDialog trên GUI Peer A, nhập IP=127.0.0.1, Port=9102 và bấm Lưu & Áp Dụng
        class AutoFilledConfigDialog(ConfigDialog):
            def exec(self):
                self.peer_ip_input.setText("127.0.0.1")
                self.peer_port_input.setValue(9102)
                self._on_save()
                return 1

        monkeypatch.setattr(app_mod, "ConfigDialog", AutoFilledConfigDialog)
        win_a._show_config_dialog()

        # Chờ Peer A hoàn tất bắt tay + nhận Handshake ACK + nhận Session Key AES-256 + Avatar của Peer B
        peer_b_id = "127.0.0.1:9102"
        deadline = time.time() + 10.0
        while time.time() < deadline:
            qapp.processEvents()
            if proc_b.poll() is not None:
                break
            actual_b_id = peer_b_id
            if actual_b_id not in win_a._peer_info_map:
                for pid, inf in win_a._peer_info_map.items():
                    if inf.get("port") == 9102:
                        actual_b_id = pid
                        break
            info_b = win_a._peer_info_map.get(actual_b_id, {})
            if (
                win_a.crypto_mgr.has_session_key(actual_b_id)
                and win_a.peer_list_panel.get_peer_status(actual_b_id) == "online"
                and info_b.get("avatar_path")
                and os.path.exists(info_b["avatar_path"])
            ):
                peer_b_id = actual_b_id
                break
            time.sleep(0.02)

        # Kiểm tra kết quả phía Peer A (9101)
        assert win_a.crypto_mgr.has_session_key(peer_b_id), "Peer A chưa có khóa phiên AES-256 với Peer B"
        assert win_a.peer_list_panel.get_peer_status(peer_b_id) == "online", "Peer B không ở trạng thái Online trên Peer A"
        peer_b_widget = win_a.peer_list_panel.get_peer_widget(peer_b_id)
        assert peer_b_widget is not None
        assert peer_b_widget.username == "PeerB_9102"
        assert peer_b_widget.avatar.pixmap() is not None and not peer_b_widget.avatar.pixmap().isNull()
        assert os.path.exists(win_a._peer_info_map[peer_b_id]["avatar_path"])

        # Kiểm tra kết quả phía Peer B (9102) từ tiến trình độc lập
        conn_msg = _read_tc1_event(proc_b, timeout=10.0)
        assert conn_msg["event"] == "CONNECTED"
        assert conn_msg["has_key"] is True
        assert conn_msg["status"] == "online"
        assert conn_msg["username"] == "PeerA_9101"
        assert conn_msg["avatar_exists"] is True

    finally:
        config.download_dir = old_dl
        if win_a is not None:
            win_a.listener.stop()
            if win_a.listener.isRunning():
                win_a.listener.wait(2000)
            win_a.discovery.stop()
            if win_a.discovery.isRunning():
                win_a.discovery.wait(2000)
            win_a.close()
            win_a.deleteLater()
            qapp.processEvents()
        if proc_b.poll() is None:
            proc_b.terminate()
            try:
                proc_b.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc_b.kill()
