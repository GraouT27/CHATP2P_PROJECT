import threading
import time

from p2p_node.peer_manager import PeerManager
from core.server import main as server_main
from p2p_node.discovery import listen_discovery, send_discovery
from core.client import main as client_main

def broadcast_loop():
    while True:
        try:
            send_discovery()
        except OSError as e:
            print(f"Lỗi gửi UDP Discovery: {e}")

        time.sleep(10)  # Send discovery message every 10 seconds

def main():
    peer_manager = PeerManager()

    server_thread = threading.Thread(target=server_main, daemon=True)
    server_thread.start()

    listener_thread = threading.Thread(target=listen_discovery, args=(peer_manager,), daemon=True)
    listener_thread.start()

    broadcast_thread = threading.Thread(target=broadcast_loop, daemon=True)
    broadcast_thread.start()

    print("\nỨng dụng P2P đã khởi động. Bạn có thể bắt đầu gửi tin nhắn.")
    print("\nĐang tìm kiếm các peer khác trong mạng LAN...")
    print("Nhập 'exit' để thoát ứng dụng.\n")

    while True:
        peers = peer_manager.get_all_peers()

        print("\nDanh sách các peer đã kết nối:")
        if not peers:
            print("Chưa có peer nào được phát hiện.")
        else:
            for peer_id, info in peers.items():
                print(f"Peer ID: {peer_id}, IP: {info['ip']}, TCP Port: {info['tcp_port']}, Last Seen: {info['last_seen']}")

        target_peer_id = input("\nNhập Peer ID để gửi tin nhắn (hoặc 'exit' để thoát): ").strip()

        if target_peer_id.lower() == "exit":
            print("Đang thoát ứng dụng...")
            break
        if target_peer_id not in peers:
            print(f"Peer ID '{target_peer_id}' không tồn tại trong danh sách. Vui lòng thử lại.")
            continue

        client_main(peer_manager, target_peer_id)


if __name__ == "__main__":
    main()
