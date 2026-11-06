import socket
import json
import sys

from  core.peer_manager import PeerManager
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






if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Cách dùng:")
        print("python udp_discovery.py listen")
        print("python udp_discovery.py send")

    elif sys.argv[1] == "listen":
        listen_discovery(peer_manager)

    elif sys.argv[1] == "send":
        send_discovery()

    else:
        print("Lệnh không hợp lệ.")
