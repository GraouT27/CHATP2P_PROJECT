import socket
import json
import sys
from config.config_loader import load_config

config = load_config()

BROADCAST_IP = "255.255.255.255"
DISCOVERY_PORT = config.get("discovery_port")

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
        sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        sock.sendto(
            data,
            (BROADCAST_IP, DISCOVERY_PORT)
        )

        print("Đã gửi Discovery Broadcast.")


def listen_discovery():
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
                if peer_id is None:
                    print("Nhận được message không có peer_id, bỏ qua!")
                    continue

                tcp_port = message.get("tcp_port")
                if type(tcp_port) is not int or not (0 < tcp_port < 65536):
                    print("Nhận được message không có tcp_port hợp lệ, bỏ qua!")
                    continue

                if peer_id == my_peer_id:
                    continue 

                

                if message.get("type") == "DISCOVERY":
                    peer_id = message.get("peer_id")
                    tcp_port = message.get("tcp_port")
                    peer_ip = addr[0]

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
        listen_discovery()

    elif sys.argv[1] == "send":
        send_discovery()

    else:
        print("Lệnh không hợp lệ.")
