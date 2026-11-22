"""
Main Entry Point - Điểm khởi chạy trung tâm ứng dụng Chat P2P [Đồ án UDM_09].
Tích hợp toàn bộ chức năng của 5 thành viên:
- TV1: Bảo mật RSA-2048, AES-256-GCM, Safe Event Logging
- TV2: Desktop GUI PyQt6 (Main Window, Peer List, Chat Box, Reply UI, Emoji Picker)
- TV3: File Transfer Drag & Drop UI, QProgressBar, Forward Dialog, Avatar Picker
- TV4: Khám phá UDP Broadcast mạng LAN, Cấu hình động config.py, Giao thức JSON Protocol
- TV5: Lõi TCP Socket đa luồng (Listener/Sender QThread), Chunking/Queue truyền file, Checksum SHA-256

Hỗ trợ khởi chạy đồng thời nhiều nút mạng P2P trên cùng 1 máy hoặc trong LAN:
    python main.py --username Alice --port 9001
    python main.py --username Bob --port 9002 --peer-ip 127.0.0.1 --peer-port 9001
    python main.py --username Charlie --port 9003 --peer-ip 127.0.0.1 --peer-port 9001
"""

import sys
import os
import argparse

# Đảm bảo import từ thư mục CODE
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.join(ROOT_DIR, "CODE") if os.path.exists(os.path.join(ROOT_DIR, "CODE")) else ROOT_DIR
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QTimer

from security.logger import log
from ui.app import MainWindow


def main():
    parser = argparse.ArgumentParser(description="UDM_09 - P2P Secure Chat PyQt6 [5 Thành viên]")
    parser.add_argument("--username", "-u", type=str, default="", help="Tên hiển thị của nút mạng Peer")
    parser.add_argument("--port", "-p", type=int, default=0, help="Cổng lắng nghe TCP P2P")
    parser.add_argument("--peer-ip", type=str, default="", help="Địa chỉ IP của Peer muốn kết nối ngay")
    parser.add_argument("--peer-port", type=int, default=0, help="Cổng của Peer muốn kết nối ngay")
    parser.add_argument("--demo", action="store_true", help="Chế độ tự động chạy kịch bản demo")

    args = parser.parse_args()

    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 12)
    app.setFont(font)

    username = args.username or "User"
    port = args.port if args.port > 0 else 9001

    log.info(f"Khởi chạy ứng dụng Chat P2P UDM_09: User={username}, Port={port}")

    window = MainWindow(username=username, listen_port=port, demo_mode=args.demo)
    window.show()

    # Tự động kết nối nếu có truyền tham số qua dòng lệnh
    if args.peer_ip and args.peer_port > 0:
        QTimer.singleShot(
            600,
            lambda: window._on_peer_discovered(
                f"{args.peer_ip}:{args.peer_port}",
                f"Peer_{args.peer_port}",
                args.peer_ip,
                args.peer_port,
            ),
        )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
