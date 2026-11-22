import socket
import json
import sys

from p2p_node.peer_manager import PeerManager
from config.config_loader import load_config

peer_manager = PeerManager()
config = load_config()

BROADCAST_IP = "255.255.255.255"
DISCOVERY_PORT = config.get("discovery_port", 9999)

def send_discovery():

    message = {
        "type": "DISCOVERY",
        "peer_id": config.get("peer_id"),
        "tcp_port": config.get("listen_port")
    }

    data = json.dumps(message).encode("utf-8")

    with socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    ) as sock:

        sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_BROADCAST,
            1
        )

        sock.sendto(
            data,
            (BROADCAST_IP, DISCOVERY_PORT)
        )

        print("Đã gửi Discovery Broadcast.")


def listen_discovery(peer_manager):
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    ) as sock:
        sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )
        sock.bind(("", DISCOVERY_PORT))
        sock.settimeout(10)
        print("Đang lắng nghe Discovery.....")

        my_peer_id = config.get("peer_id")

        while True:
            try: 
                data, addr = sock.recvfrom(4096)

                try:
                    message = json.loads(data.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    print("Nhận được message không phải JSON hợp lệ, bỏ qua!")
                    continue

                check_message = isinstance(message, dict)

                if not check_message:
                    print("Nhận được message không hợp lệ, bỏ qua!")
                    continue

                peer_id = message.get("peer_id")
                if not isinstance(peer_id, str) or not peer_id.strip():
                    print("Nhận được message không có peer_id hợp lệ, bỏ qua!")
                    continue

                tcp_port = message.get("tcp_port")
                if type(tcp_port) is not int or not (0 < tcp_port < 65536):
                    print("Nhận được message không có tcp_port hợp lệ, bỏ qua!")
                    continue

                if message.get("type") != "DISCOVERY":
                    continue

                # Không lọc bỏ peer của chính mình khi chạy trên cùng máy
                # với config khác nhau (peer_id khác). Chỉ bỏ qua nếu địa chỉ
                # IP và cổng trùng với máy hiện tại.
                if peer_id == my_peer_id:
                    continue
                
                peer_ip = addr[0]

                peer_manager.add_peer(peer_id, peer_ip, tcp_port)

                print("Danh sach Peer hien tai:", peer_manager.get_all_peers())
               
                print("\nĐã phát hiện Peer!")
                print("Peer ID:", peer_id)
                print("IP:", peer_ip)
                print("TCP Port:", tcp_port)

            except socket.timeout:
                print("Chưa nhận được Discovery, tiếp tục chờ....")






# ===================== GUI QTHREAD PEER DISCOVERY =====================

import time
import uuid
from PyQt6.QtCore import QThread, pyqtSignal
from config import DEFAULT_DISCOVERY_PORT, DISCOVERY_BROADCAST_IP, DISCOVERY_INTERVAL, HEARTBEAT_TIMEOUT
from security.logger import log


class PeerDiscovery(QThread):
    """QThread chạy ngầm quản lý UDP Broadcast tìm kiếm Peer trong mạng cục bộ cho GUI PyQt6."""

    peer_discovered = pyqtSignal(str, str, str, int)  # (peer_id, username, ip, port)
    peer_lost = pyqtSignal(str)                       # (peer_id)

    def __init__(self, username: str, listen_port: int, discovery_port: int = DEFAULT_DISCOVERY_PORT, parent=None):
        super().__init__(parent)
        self.username = username
        self.listen_port = listen_port
        self.discovery_port = discovery_port
        self._is_running = True
        self._known_peers: dict[str, float] = {}  # {peer_id: last_seen_time}
        self._instance_id = str(uuid.uuid4())

    def stop(self):
        """Dừng luồng phát và lắng nghe UDP."""
        self._is_running = False
        if self.isRunning():
            self.wait(1500)

    def update_info(self, username: str, listen_port: int):
        """Cập nhật thông tin định danh."""
        self.username = username
        self.listen_port = listen_port

    def run(self):
        recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass

        try:
            recv_sock.bind(("", self.discovery_port))
        except Exception as e:
            log.warning(f"Không thể bind UDP port {self.discovery_port}: {e}")

        recv_sock.settimeout(1.0)

        send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        send_sock.settimeout(0.5)

        last_broadcast = 0.0

        while self._is_running:
            now = time.time()

            # Phát Beacon định kỳ
            if now - last_broadcast >= DISCOVERY_INTERVAL:
                beacon_data = {
                    "type": "p2p_beacon",
                    "instance_id": self._instance_id,
                    "username": self.username,
                    "port": self.listen_port,
                    "timestamp": now,
                }
                msg_bytes = json.dumps(beacon_data).encode("utf-8")
                try:
                    send_sock.sendto(msg_bytes, (DISCOVERY_BROADCAST_IP, self.discovery_port))
                except Exception:
                    pass
                last_broadcast = now

            # Đọc các Beacon nhận được
            try:
                data, addr = recv_sock.recvfrom(2048)
                ip = addr[0]
                beacon = json.loads(data.decode("utf-8"))
                if beacon.get("type") == "p2p_beacon":
                    peer_port = beacon.get("port")
                    peer_name = beacon.get("username", "Peer")

                    if beacon.get("instance_id") == self._instance_id:
                        continue
                    if peer_port == self.listen_port and (ip in ("127.0.0.1", "localhost") or ip.startswith("192.168.")):
                        continue

                    peer_id = f"{ip}:{peer_port}"
                    is_new = peer_id not in self._known_peers
                    self._known_peers[peer_id] = now

                    if is_new:
                        log.info(f"[UDP_DISCOVERY] Tìm thấy Peer mới qua mạng LAN: {peer_name} ({peer_id})")
                        self.peer_discovered.emit(peer_id, peer_name, ip, peer_port)

            except (socket.timeout, BlockingIOError):
                pass
            except Exception:
                pass

            # Quét các Peer bị mất kết nối (timeout)
            lost_ids = []
            for pid, last_seen in list(self._known_peers.items()):
                if now - last_seen > HEARTBEAT_TIMEOUT:
                    lost_ids.append(pid)

            for pid in lost_ids:
                del self._known_peers[pid]
                log.info(f"[UDP_DISCOVERY] Mất tín hiệu beacon từ: {pid}")
                self.peer_lost.emit(pid)

        recv_sock.close()
        send_sock.close()


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Cách dùng:")
        print("python -m p2p_node.discovery listen")
        print("python -m p2p_node.discovery send")

    elif sys.argv[1] == "listen":
        listen_discovery(peer_manager)

    elif sys.argv[1] == "send":
        send_discovery()

    else:
        print("Lệnh không hợp lệ.")
