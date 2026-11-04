import socket
import json
import sys



BROADCAST_IP = "255.255.255.255"
DISCOVERY_PORT = 9999

def send_discovery():

    message = {
        "type": "DISCOVERY",
        "peer_id": "peer_A",
        "tcp_port": 5000
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

        print ("Đã gửi Discovery Broadcast.")


def listen_discovery():
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    ) as sock:
        sock.bind(("", DISCOVERY_PORT))
        sock.settimeout(3)
        print("Đang lắng nghe Discovey.....")

        while True:
            try: 
                data, addr = sock.recvfrom(4096)

                message = json.loads(
                    data.decode("utf-8")
                )

                if message.get("type") == "DISCOVERY":
                    peer_id = message.get("peer_id")
                    tcp_port = message.get("tcp_port")
                    peer_ip = addr[0]

                    print("\nĐã phát hiện Peer!")
                    print("Peer ID: ", peer_id)
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
