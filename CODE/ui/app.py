"""
App Module - Cửa sổ chính (MainWindow) ứng dụng Chat P2P PyQt6 (TV2 & TV3).
Kết nối toàn bộ tầng UI với lõi mạng p2p_node, crypto_manager và transfer_manager.
"""

import os
import sys
import time
import base64
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QFont, QAction, QClipboard, QImage
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QSplitter, QFrame, QListView,
    QMenu, QMessageBox, QFileDialog, QApplication
)

from config import config
from security.crypto_manager import CryptoManager
from security.logger import log
from p2p_node.handler import MessageHandler
from p2p_node.listener import P2PListener
from p2p_node.discovery import PeerDiscovery
from p2p_node.transfer_manager import TransferManager
from p2p_node.transfer_task import TransferTask, TransferStatus, TransferDirection
from p2p_node.sender import send_message_direct, send_message_direct_async, PeerSocketClient
from shared.protocol import (
    make_handshake_header, make_handshake_ack_header,
    make_key_exchange_header, make_chat_header, make_file_delete_header, pack_message
)
from ui.peer_list_widget import PeerListWidget, is_same_host
from ui.chat_widgets import (
    AvatarWidget, ReplyPreview, EmojiPicker,
    MessageData, MessageListModel, MessageDelegate
)
from ui.file_row import FileRowWidget
from ui.dialogs import ForwardDialog, ConfigDialog
from ui.dnd import DragDropFilter


class MainWindow(QMainWindow):
    """Cửa sổ chính của ứng dụng Chat P2P."""

    def __init__(self, username: str = None, listen_port: int = None, demo_mode: bool = False):
        super().__init__()
        self.setWindowTitle("💬 P2P Secure Chat - PyQt6 [UDM_09]")
        self.setMinimumSize(950, 650)
        self.resize(1150, 750)
        self.demo_mode = demo_mode

        # Nạp cấu hình
        self.username = username or config.username
        self.listen_port = listen_port or config.listen_port
        self.avatar_path = config.avatar_path

        # Nạp StyleSheet QSS
        qss_path = os.path.join(os.path.dirname(__file__), "styles.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                qss_data = f.read()
                self.setStyleSheet(qss_data)
                app_inst = QApplication.instance()
                if app_inst:
                    app_inst.setStyleSheet(qss_data)

        # 1. Khởi tạo Core Cryptography & File Manager
        self.crypto_mgr = CryptoManager()
        self.transfer_mgr = TransferManager(self.crypto_mgr, config.download_dir, listen_port=self.listen_port, parent=self)

        # 2. Khởi tạo Message Handler & Network Listener
        self.msg_handler = MessageHandler(self.crypto_mgr, parent=self)
        self.listener = P2PListener(self.listen_port, self.msg_handler, parent=self)

        # 3. Khởi tạo Discovery
        self.discovery = PeerDiscovery(self.username, self.listen_port, parent=self)

        # Dữ liệu nội bộ
        self._current_peer_id: Optional[str] = None
        self._message_models: dict[str, MessageListModel] = {}
        self._peer_info_map: dict[str, dict] = {}  # {peer_id: {ip, port, username, status}}
        self._peer_clients: dict[str, PeerSocketClient] = {}
        self._file_row_widgets: dict[str, FileRowWidget] = {}
        self._last_sent_file: Optional[dict] = None

        # 4. Xây dựng giao diện
        self._setup_ui()
        self._setup_menu()
        self._bind_signals()

        # 5. Khởi động mạng ngầm
        self.listener.start()
        if config.discovery_enabled:
            self.discovery.start()

        self.statusBar().showMessage(f"Sẵn sàng | Đang lắng nghe trên cổng TCP {self.listen_port}")

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)

        # Cột trái: Peer List
        self.peer_list_panel = PeerListWidget(self.username, self.listen_port, self)
        self.splitter.addWidget(self.peer_list_panel)

        # Cột phải: Chat Box
        self.chat_panel = self._create_chat_panel()
        self.splitter.addWidget(self.chat_panel)

        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 7)
        self.splitter.setSizes([320, 830])

    def _create_chat_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("chatBoxContainer")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Header cuộc trò chuyện
        self.chat_header = QFrame()
        self.chat_header.setObjectName("chatHeader")
        h_layout = QHBoxLayout(self.chat_header)
        h_layout.setContentsMargins(16, 8, 16, 8)

        self.header_avatar = AvatarWidget("?", size=38)
        h_layout.addWidget(self.header_avatar)

        name_layout = QVBoxLayout()
        name_layout.setSpacing(2)
        self.header_name_label = QLabel("Chọn một Peer để bắt đầu trò chuyện")
        self.header_name_label.setObjectName("chatPeerName")
        self.header_status_label = QLabel("Chưa kết nối")
        self.header_status_label.setObjectName("chatPeerStatus")
        name_layout.addWidget(self.header_name_label)
        name_layout.addWidget(self.header_status_label)
        h_layout.addLayout(name_layout, 1)

        # Nút gửi file và mở thư mục lưu trữ trên header
        self.header_attach_btn = QPushButton("📎 Gửi File...")
        self.header_attach_btn.setEnabled(False)
        self.header_attach_btn.clicked.connect(self._open_file_picker)
        h_layout.addWidget(self.header_attach_btn)

        self.header_open_folder_btn = QPushButton("📂 Thư Mục File")
        self.header_open_folder_btn.setToolTip("Mở thư mục chứa các file đã nhận (received_files)")
        self.header_open_folder_btn.clicked.connect(self._open_received_files_folder)
        h_layout.addWidget(self.header_open_folder_btn)
        layout.addWidget(self.chat_header)

        # 2. Khung chứa danh sách dòng tiến trình truyền file (File Row Container)
        self.file_container = QWidget()
        self.file_container_layout = QVBoxLayout(self.file_container)
        self.file_container_layout.setContentsMargins(12, 4, 12, 4)
        self.file_container_layout.setSpacing(4)
        self.file_container.setVisible(False)
        layout.addWidget(self.file_container)

        # 3. Message List View (Virtualization)
        self.message_view = QListView()
        self.message_view.setObjectName("messageListView")
        self.message_delegate = MessageDelegate(self.message_view)
        self.message_view.setItemDelegate(self.message_delegate)
        self.message_view.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.message_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.message_view.customContextMenuRequested.connect(self._show_message_context_menu)
        self.message_view.doubleClicked.connect(self._on_message_double_clicked)
        layout.addWidget(self.message_view, 1)

        # Gắn Drag & Drop Filter lên khung chat
        self.dnd_filter = DragDropFilter(self.message_view, self)
        self.dnd_filter.file_dropped.connect(self._on_file_dropped)

        # 4. Reply Preview
        self.reply_preview = ReplyPreview(self)
        layout.addWidget(self.reply_preview)

        # 5. Input Area
        input_container = QFrame()
        input_container.setObjectName("inputArea")
        in_layout = QHBoxLayout(input_container)
        in_layout.setContentsMargins(12, 8, 12, 8)
        in_layout.setSpacing(8)

        # Nút Đính kèm (📎)
        self.attach_btn = QPushButton("📎")
        self.attach_btn.setObjectName("attachButton")
        self.attach_btn.setToolTip("Đính kèm file")
        self.attach_btn.setEnabled(False)
        self.attach_btn.clicked.connect(self._open_file_picker)
        in_layout.addWidget(self.attach_btn)

        # Nút Emoji (😀)
        self.emoji_btn = QPushButton("😀")
        self.emoji_btn.setObjectName("emojiButton")
        self.emoji_btn.setToolTip("Chọn biểu tượng cảm xúc")
        self.emoji_btn.clicked.connect(self._toggle_emoji_picker)
        in_layout.addWidget(self.emoji_btn)

        self.emoji_picker = EmojiPicker(self)
        self.emoji_picker.emoji_selected.connect(self._on_emoji_selected)

        # Ô nhập tin nhắn
        self.input_field = QLineEdit()
        self.input_field.setObjectName("messageInput")
        self.input_field.setPlaceholderText("Nhập tin nhắn hoặc kéo thả file vào đây... (Enter để gửi)")
        self.input_field.setEnabled(False)
        self.input_field.returnPressed.connect(self._send_chat_message)
        in_layout.addWidget(self.input_field, 1)

        # Nút Gửi
        self.send_btn = QPushButton("Gửi ➤")
        self.send_btn.setObjectName("sendButton")
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self._send_chat_message)
        in_layout.addWidget(self.send_btn)

        layout.addWidget(input_container)
        return panel

    def _setup_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Tệp")

        conn_act = QAction("🔌 Kết Nối / Cấu Hình...", self)
        conn_act.triggered.connect(self._show_config_dialog)
        file_menu.addAction(conn_act)

        open_folder_act = QAction("📁 Mở Thư Mục File Đã Nhận", self)
        open_folder_act.setShortcut("Ctrl+O")
        open_folder_act.triggered.connect(self._open_received_files_folder)
        file_menu.addAction(open_folder_act)

        file_menu.addSeparator()
        exit_act = QAction("Thoát", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        help_menu = menubar.addMenu("Trợ Giúp")
        about_act = QAction("Thông Tin Đề Tài UDM_09", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _bind_signals(self):
        # UI Peer List
        self.peer_list_panel.peer_selected.connect(self._on_peer_selected)
        self.peer_list_panel.connect_clicked.connect(self._show_config_dialog)
        self.peer_list_panel.settings_clicked.connect(self._show_config_dialog)

        # Network Listener
        self.listener.server_started.connect(self._on_server_started)
        self.listener.server_error.connect(self._on_server_error)
        self.listener.peer_connected.connect(self._on_peer_connected)
        self.listener.peer_disconnected.connect(self._on_peer_disconnected)

        # Discovery
        self.discovery.peer_discovered.connect(self._on_peer_discovered)
        self.discovery.peer_lost.connect(self._on_peer_lost)

        # Handler
        self.msg_handler.handshake_received.connect(self._on_handshake_received)
        self.msg_handler.handshake_ack_received.connect(self._on_handshake_ack_received)
        self.msg_handler.key_exchange_done.connect(self._on_key_exchange_done)
        self.msg_handler.chat_received.connect(self._on_chat_received)
        self.msg_handler.file_start_received.connect(self.transfer_mgr.handle_file_start)
        self.msg_handler.file_chunk_received.connect(self.transfer_mgr.handle_file_chunk)
        self.msg_handler.file_cancel_received.connect(self.transfer_mgr.cancel_task)
        self.msg_handler.file_delete_received.connect(self._on_file_delete_received)

        # Transfer Manager
        self.transfer_mgr.task_added.connect(self._on_file_task_added)
        self.transfer_mgr.task_progress.connect(self._on_file_task_progress)
        self.transfer_mgr.task_completed.connect(self._on_file_task_completed)
        self.transfer_mgr.task_failed.connect(self._on_file_task_failed)

    # ========================== EVENT HANDLERS ==========================

    def _on_server_started(self, port: int):
        self.listen_port = port
        self.peer_list_panel.update_self_info(self.username, port, self.avatar_path)
        self.discovery.update_info(self.username, port)
        self.statusBar().showMessage(f"✅ Đang lắng nghe P2P trên cổng {port}")

    def _on_server_error(self, err: str):
        QMessageBox.critical(self, "Lỗi Server", f"Không thể bind port {self.listen_port}:\n{err}")

    def _on_peer_connected(self, peer_id: str, ip: str, port: int):
        log.info(f"Peer kết nối đến: {peer_id}")
        self.statusBar().showMessage(f"🔗 Kết nối mới từ {peer_id}")

    def _on_peer_disconnected(self, peer_id: str):
        # Lý do phải kiểm tra peer_id in _peer_info_map:
        # P2PListener phát tín hiệu peer_disconnected cho MỌI kết nối socket TCP đóng lại,
        # kể cả cổng socket tạm thời (ephemeral port) dùng để gửi xong 1 tin nhắn rồi đóng.
        # Nếu không bỏ qua cổng tạm, UI sẽ tạo nhầm cửa sổ chat rác và hiện cảnh báo mất kết nối giả.
        if peer_id not in self._peer_info_map:
            self.transfer_mgr.cancel_all_for_peer(peer_id)
            return

        log.warning(f"Peer ngắt kết nối: {peer_id}")
        self._peer_info_map[peer_id]["status"] = "offline"

        # Hủy các tác vụ truyền file dở dang và xóa file .part
        self.transfer_mgr.cancel_all_for_peer(peer_id)
        self.crypto_mgr.remove_peer_keys(peer_id)

        # Cập nhật trạng thái trên danh sách Peer
        self.peer_list_panel.set_peer_status(peer_id, "offline")

        if self._current_peer_id == peer_id:
            self.header_status_label.setText("Offline (Đã mất kết nối)")
            self.header_status_label.setProperty("status", "offline")
            self.header_status_label.style().unpolish(self.header_status_label)
            self.header_status_label.style().polish(self.header_status_label)

            self.send_btn.setEnabled(False)
            self.attach_btn.setEnabled(False)
            self.header_attach_btn.setEnabled(False)
            self.input_field.setEnabled(False)
            self.input_field.setPlaceholderText("Peer đã ngắt kết nối. Không thể gửi tin nhắn.")

        self._add_system_message(peer_id, f"⚠️ Peer {peer_id} đã ngắt kết nối đột ngột.")

    def _on_peer_discovered(self, peer_id: str, username: str, ip: str, port: int):
        """Khi tìm thấy Peer mới qua mạng LAN."""
        safe_name = self._sanitize_username(username)
        canonical_peer_id = f"{ip}:{port}"

        # Chống nhân bản: Kiểm tra xem đã có mục nào đại diện cho Peer này chưa
        found_pid = None
        is_real_name = bool(safe_name and not safe_name.startswith("Peer_"))

        for existing_pid, info in list(self._peer_info_map.items()):
            if existing_pid == canonical_peer_id:
                found_pid = existing_pid
                break
            same_host = is_same_host(info.get("ip", ""), ip)
            existing_name = info.get("username", "")
            is_info_real_name = bool(existing_name and not existing_name.startswith("Peer_"))
            same_real_name = is_real_name and is_info_real_name and (existing_name.lower() == safe_name.lower())
            same_port = (port > 0 and info.get("port") == port)
            is_placeholder = existing_name.startswith("Peer_") or safe_name.startswith("Peer_")

            if same_real_name or (same_port and (same_host or is_placeholder)):
                found_pid = existing_pid
                break

        if found_pid:
            self._peer_info_map[found_pid]["status"] = "online"
            self._peer_info_map[found_pid]["port"] = port
            self._peer_info_map[found_pid]["ip"] = ip
            if self._peer_info_map[found_pid].get("username", "").startswith("Peer_") or is_real_name:
                self._peer_info_map[found_pid]["username"] = safe_name
            current_name = self._peer_info_map[found_pid]["username"]
            current_ip = self._peer_info_map[found_pid]["ip"]
            current_avatar = self._peer_info_map[found_pid].get("avatar_path", "")
            if canonical_peer_id != found_pid:
                self._peer_info_map[canonical_peer_id] = self._peer_info_map[found_pid]
                if found_pid in self._message_models:
                    self._message_models[canonical_peer_id] = self._message_models[found_pid]

            # Dọn dẹp các mục cũ trùng lặp trong cache thông tin peer
            if is_real_name:
                for other_pid, other_info in list(self._peer_info_map.items()):
                    if other_pid not in (found_pid, canonical_peer_id):
                        if other_info.get("username", "").lower() == safe_name.lower():
                            if other_info.get("status") == "offline" or is_same_host(other_info.get("ip", ""), ip):
                                self._peer_info_map.pop(other_pid, None)

            self.peer_list_panel.add_or_update_peer(found_pid, current_name, current_ip, port, "online", current_avatar)
            if not self.crypto_mgr.has_session_key(found_pid):
                self._send_handshake(found_pid, current_ip, port)
            return

        old_info = self._peer_info_map.get(canonical_peer_id, {})
        final_avatar = old_info.get("avatar_path", "")
        self._peer_info_map[canonical_peer_id] = {
            "ip": ip, "port": port, "username": safe_name,
            "status": "online", "avatar_path": final_avatar
        }
        self.peer_list_panel.add_or_update_peer(canonical_peer_id, safe_name, ip, port, "online", final_avatar)

        # Tự động gửi Handshake nếu chưa có khóa
        if not self.crypto_mgr.has_session_key(canonical_peer_id):
            self._send_handshake(canonical_peer_id, ip, port)

    def _on_peer_lost(self, peer_id: str):
        if peer_id in self._peer_info_map:
            self._peer_info_map[peer_id]["status"] = "offline"
        self.peer_list_panel.set_peer_status(peer_id, "offline")
        if self._current_peer_id == peer_id:
            self.header_status_label.setText("Offline (Mất tín hiệu)")
            self.header_status_label.setProperty("status", "offline")
            self.header_status_label.style().unpolish(self.header_status_label)
            self.header_status_label.style().polish(self.header_status_label)

            self.send_btn.setEnabled(False)
            self.attach_btn.setEnabled(False)
            self.header_attach_btn.setEnabled(False)
            self.input_field.setEnabled(False)
            self.input_field.setPlaceholderText("Peer đã ngắt kết nối. Không thể gửi tin nhắn.")

    @staticmethod
    def _sanitize_username(username: str) -> str:
        """Loại bỏ ký tự điều khiển và giới hạn độ dài tên người dùng để chống giả mạo hiển thị."""
        cleaned = "".join(ch for ch in str(username or "") if ch >= " " and ch != "\x7f").strip()
        return (cleaned[:64] or "Peer")

    def _read_my_avatar_b64(self) -> str:
        """Đọc và mã hóa Base64 ảnh avatar cá nhân (giới hạn <= 256 KB)."""
        if self.avatar_path and os.path.exists(self.avatar_path):
            try:
                if os.path.getsize(self.avatar_path) <= 256 * 1024:
                    with open(self.avatar_path, "rb") as f:
                        return base64.b64encode(f.read()).decode("utf-8")
            except Exception:
                pass
        return ""

    @staticmethod
    def _save_safe_avatar(canonical_peer_id: str, avatar_b64: str) -> str:
        """
        Giải mã và kiểm tra an toàn ảnh avatar trước khi lưu cache ra ổ đĩa.
        Lý do không được ghi trực tiếp bytes decode ra file '.png':
        1. Attacker có thể nhồi payload .exe/.bat/SVG độc hại đội lốt Base64 avatar.
        2. Ảnh bị nén thành Image Bomb (ví dụ 100KB nhưng bung ra 20000x20000 px) sẽ làm treo/tràn RAM UI.
        Giải pháp: kiểm tra size + magic bytes (PNG/JPEG) + nạp qua QImage để xác thực kích thước thật
        rồi re-encode lại thành ảnh PNG nhỏ (<= 128x128) trước khi ghi đĩa.
        """
        if not avatar_b64 or not isinstance(avatar_b64, str) or len(avatar_b64) > 350_000:
            return ""
        try:
            # validate=True buộc base64 phải hợp lệ nghiêm ngặt, từ chối ký tự rác tiêm nhiễm.
            avatar_bytes = base64.b64decode(avatar_b64.encode("utf-8"), validate=True)
            if not avatar_bytes or len(avatar_bytes) > 256 * 1024:
                return ""
            # Kiểm tra chữ ký đầu tệp (Magic Bytes) của PNG hoặc JPEG.
            is_png = avatar_bytes.startswith(b"\x89PNG\r\n\x1a\n")
            is_jpeg = avatar_bytes.startswith(b"\xff\xd8\xff")
            if not (is_png or is_jpeg):
                log.warning(f"Từ chối avatar không phải PNG/JPEG từ {canonical_peer_id}")
                return ""

            img = QImage.fromData(avatar_bytes)
            if img.isNull() or img.width() <= 0 or img.height() <= 0 or img.width() > 2048 or img.height() > 2048:
                log.warning(f"Từ chối avatar kích thước bất thường từ {canonical_peer_id}")
                return ""

            safe_img = img.scaled(
                128, 128,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            cache_dir = os.path.join(config.download_dir, "peer_avatars")
            os.makedirs(cache_dir, exist_ok=True)
            safe_id = "".join(c if c.isalnum() else "_" for c in canonical_peer_id)
            avatar_path = os.path.abspath(os.path.join(cache_dir, f"avatar_{safe_id}.png"))
            cache_abs = os.path.abspath(cache_dir)
            if not avatar_path.startswith(cache_abs + os.sep):
                return ""
            # Gọi safe_img.save(..., "PNG") để ghi lại dữ liệu pixel đã làm sạch thay vì bytes thô từ mạng.
            if safe_img.save(avatar_path, "PNG"):
                return avatar_path
            return ""
        except Exception as e:
            log.warning(f"Không thể giải mã avatar an toàn từ {canonical_peer_id}: {e}")
            return ""

    def _find_canonical_peer_id(self, raw_peer_id: str, sender_name: str = "", sender_port: int = 0) -> str:
        """
        Ánh xạ kết nối socket tạm thời (ephemeral port) về đúng Canonical Peer ID (<IP>:<listen_port>).
        Cách dùng: gọi hàm này ở _on_chat_received để tin nhắn đến từ cổng ngẫu nhiên vẫn vào đúng khung chat của Peer.
        """
        raw_ip = raw_peer_id.split(":")[0] if ":" in raw_peer_id else raw_peer_id
        # Ưu tiên 1: Ghép IP thật của socket kết nối + sender_port khai báo trong header.
        if isinstance(sender_port, int) and not isinstance(sender_port, bool) and 1 <= sender_port <= 65535:
            target = f"{raw_ip}:{sender_port}"
            if target in self._peer_info_map:
                return target
            for pid, info in self._peer_info_map.items():
                if info.get("port") == sender_port and is_same_host(info.get("ip", ""), raw_ip):
                    return pid
            for pid, info in self._peer_info_map.items():
                if info.get("port") == sender_port:
                    return pid

        if raw_peer_id in self._peer_info_map:
            return raw_peer_id

        # Ưu tiên 2: Tìm theo username (cùng host)
        if sender_name:
            for pid, info in self._peer_info_map.items():
                if is_same_host(info.get("ip", ""), raw_ip) and info.get("username", "").lower() == sender_name.lower():
                    return pid

        # Ưu tiên 3: Nếu chỉ có duy nhất 1 Peer cùng host thì ánh xạ về Peer đó.
        matching = [
            pid for pid, info in self._peer_info_map.items()
            if is_same_host(info.get("ip", ""), raw_ip)
        ]
        if len(matching) == 1:
            return matching[0]

        return raw_peer_id

    def _send_handshake(self, peer_id: str, ip: str, port: int):
        """Gửi gói tin Handshake kèm RSA Public Key và Avatar sang Peer."""
        pub_key = self.crypto_mgr.get_public_key_pem()
        avatar_b64 = self._read_my_avatar_b64()
        h = make_handshake_header(self.username, self.listen_port, pub_key, avatar_b64=avatar_b64)
        send_message_direct_async(ip, port, h)

    def _on_handshake_received(self, peer_id: str, username: str, listen_port: int, pub_key: str, avatar_b64: str):
        self._handle_handshake(peer_id, username, listen_port, pub_key, avatar_b64, is_ack=False)

    def _on_handshake_ack_received(self, peer_id: str, username: str, listen_port: int, pub_key: str, avatar_b64: str):
        self._handle_handshake(peer_id, username, listen_port, pub_key, avatar_b64, is_ack=True)

    def _handle_handshake(self, peer_id: str, username: str, listen_port: int, pub_key: str, avatar_b64: str, is_ack: bool = False):
        ip = peer_id.split(":")[0] if ":" in peer_id else peer_id
        raw_port = 0
        if ":" in peer_id:
            try:
                raw_port = int(peer_id.split(":")[1])
            except ValueError:
                raw_port = 0

        actual_port = listen_port if (isinstance(listen_port, int) and 1 <= listen_port <= 65535) else raw_port
        if not (1 <= actual_port <= 65535):
            log.warning(f"Từ chối Handshake từ {peer_id}: cổng lắng nghe không hợp lệ ({actual_port})")
            return

        canonical_peer_id = f"{ip}:{actual_port}"
        safe_username = self._sanitize_username(username)

        # Chống nhân bản: Kiểm tra xem đã có mục nào trong _peer_info_map đại diện cho Peer này chưa
        target_pid = canonical_peer_id
        is_real_name = bool(safe_username and not safe_username.startswith("Peer_"))

        for existing_pid, info in list(self._peer_info_map.items()):
            if existing_pid == canonical_peer_id:
                target_pid = existing_pid
                break
            same_host = is_same_host(info.get("ip", ""), ip)
            existing_name = info.get("username", "")
            is_info_real_name = bool(existing_name and not existing_name.startswith("Peer_"))
            same_real_name = is_real_name and is_info_real_name and (existing_name.lower() == safe_username.lower())
            same_port = (actual_port > 0 and info.get("port") == actual_port)
            is_placeholder = existing_name.startswith("Peer_") or safe_username.startswith("Peer_")

            if same_real_name or (same_port and (same_host or is_placeholder)):
                target_pid = existing_pid
                break

        if pub_key:
            self.crypto_mgr.register_peer_public_key(target_pid, pub_key)
            if target_pid != canonical_peer_id:
                self.crypto_mgr.register_peer_public_key(canonical_peer_id, pub_key)

        avatar_path = self._save_safe_avatar(target_pid, avatar_b64)

        old_info = self._peer_info_map.get(target_pid, {})
        final_avatar = avatar_path or old_info.get("avatar_path", "")
        dest_ip = old_info.get("ip", ip)
        info_dict = {
            "ip": dest_ip, "port": actual_port, "username": safe_username,
            "status": "online", "avatar_path": final_avatar
        }
        self._peer_info_map[target_pid] = info_dict
        if canonical_peer_id != target_pid:
            self._peer_info_map[canonical_peer_id] = info_dict
            if target_pid in self._message_models:
                self._message_models[canonical_peer_id] = self._message_models[target_pid]

        # Dọn dẹp bất kỳ mục trùng lặp nào khác cùng tên thật
        if is_real_name:
            for other_pid, other_info in list(self._peer_info_map.items()):
                if other_pid not in (target_pid, canonical_peer_id):
                    if other_info.get("username", "").lower() == safe_username.lower():
                        if other_info.get("status") == "offline" or is_same_host(other_info.get("ip", ""), ip):
                            self._peer_info_map.pop(other_pid, None)

        self.peer_list_panel.add_or_update_peer(target_pid, safe_username, dest_ip, actual_port, "online", final_avatar)

        if self._current_peer_id == target_pid:
            self.header_name_label.setText(safe_username)
            if final_avatar:
                self.header_avatar.set_image_path(final_avatar)

        # Chỉ bên nhận gói handshake ban đầu (is_ack=False) mới phản hồi handshake_ack và sinh session key.
        # Lý do: Nếu xử lý handshake_ack mà lại tiếp tục gửi handshake_ack hoặc sinh đè khóa mới,
        # hai máy sẽ bị lặp vô tận (handshake loop) hoặc làm lệch khóa AES-256 giữa 2 chiều.
        if not is_ack:
            ack_h = make_handshake_ack_header(
                self.username,
                self.crypto_mgr.get_public_key_pem(),
                avatar_b64=self._read_my_avatar_b64(),
                # Bắt buộc đính kèm listen_port của mình để bên khởi tạo map đúng IP:listen_port (tránh tạo Ghost Peer).
                listen_port=self.listen_port,
            )
            send_message_direct_async(ip, actual_port, ack_h)

            if not self.crypto_mgr.has_session_key(target_pid):
                enc_session_key = self.crypto_mgr.generate_and_encrypt_session_key(target_pid)
                if enc_session_key:
                    if target_pid != canonical_peer_id and self.crypto_mgr.has_session_key(target_pid):
                        self.crypto_mgr._peer_session_keys[canonical_peer_id] = self.crypto_mgr._peer_session_keys[target_pid]
                    key_h = make_key_exchange_header(
                        self.username, enc_session_key, listen_port=self.listen_port
                    )
                    send_message_direct_async(ip, actual_port, key_h)

        self._add_system_message(target_pid, f"🔒 Đã thiết lập kênh bảo mật RSA/AES-256 với {safe_username}.")

    def _on_key_exchange_done(self, peer_id: str):
        self.statusBar().showMessage(f"✅ Đã thiết lập mã hóa AES-256 với {peer_id}")

    def _on_peer_selected(self, peer_id: str):
        self._current_peer_id = peer_id
        info = self._peer_info_map.get(peer_id, {})
        username = info.get("username", peer_id)
        status = info.get("status", "online")
        avatar_path = info.get("avatar_path", "")

        self.header_name_label.setText(username)
        self.header_status_label.setText(status.capitalize())
        self.header_status_label.setProperty("status", status)
        self.header_status_label.style().unpolish(self.header_status_label)
        self.header_status_label.style().polish(self.header_status_label)
        self.header_avatar.set_name(username)
        if avatar_path:
            self.header_avatar.set_image_path(avatar_path)

        is_online = (status == "online")
        self.send_btn.setEnabled(is_online)
        self.attach_btn.setEnabled(is_online)
        self.header_attach_btn.setEnabled(is_online)
        self.input_field.setEnabled(is_online)
        if is_online:
            self.input_field.setPlaceholderText("Nhập tin nhắn hoặc kéo thả file vào đây... (Enter để gửi)")
        else:
            self.input_field.setPlaceholderText("Peer đã ngắt kết nối. Không thể gửi tin nhắn.")

        # Nạp model tin nhắn
        if peer_id not in self._message_models:
            self._message_models[peer_id] = MessageListModel(self)
        self.message_view.setModel(self._message_models[peer_id])
        self.message_view.scrollToBottom()

    def _on_message_double_clicked(self, index):
        """Hỗ trợ double click vào tin nhắn để Reply nhanh (Chặng 5)."""
        if not index.isValid() or not self._current_peer_id:
            return
        model = self._message_models.get(self._current_peer_id)
        if not model:
            return
        msg = model.get_message(index.row())
        if not msg or msg.is_system:
            return
        self.reply_preview.set_reply(msg.sender, msg.content, msg.msg_id)
        self.input_field.setFocus()

    def _encrypt_text_if_ready(self, peer_id: str, text: str) -> tuple[str, bool, Optional[str]]:
        """
        Helper dùng chung cho cả Gửi tin nhắn mới và Chuyển tiếp (Forward).
        Cách dùng: truyền peer_id đích và chuỗi bản rõ; trả về (nội_dung_gửi, is_encrypted, nonce_b64).
        Lý do tách helper: đảm bảo mọi đường đi gửi tin (kể cả Forward) đều đi qua cùng một cơ chế mã hóa AES-256-GCM.
        """
        if self.crypto_mgr.has_session_key(peer_id):
            enc_res = self.crypto_mgr.encrypt_text(peer_id, text)
            if enc_res:
                cipher_b64, nonce_b64 = enc_res
                return cipher_b64, True, nonce_b64
        return text, False, None

    def _send_chat_message(self):
        text = self.input_field.text().strip()
        if not text or not self._current_peer_id:
            return

        info = self._peer_info_map.get(self._current_peer_id)
        if not info or info.get("status") != "online":
            QMessageBox.warning(self, "Không thể gửi", "Peer đang Offline!")
            return

        ip = info["ip"]
        port = info["port"]

        reply_data = self.reply_preview.get_reply_data()
        text_to_header, is_encrypted, nonce_str = self._encrypt_text_if_ready(
            self._current_peer_id, text
        )

        header = make_chat_header(
            username=self.username,
            text=text_to_header,
            reply_to=reply_data,
            is_encrypted=is_encrypted,
            nonce=nonce_str,
        )
        header["sender_port"] = self.listen_port

        ok, err = send_message_direct(ip, port, header, b"")
        if not ok:
            self._on_peer_disconnected(self._current_peer_id)
            QMessageBox.warning(self, "Lỗi Gửi Tin Nhắn", f"Không thể gửi tới {self._current_peer_id}:\n{err}")
            return

        # Hiển thị trên UI của mình
        msg = MessageData(
            msg_id=header["msg_id"],
            sender=self.username,
            content=text,
            timestamp=header["timestamp"],
            is_sent=True,
            reply_to=reply_data,
            avatar_path=self.avatar_path,
        )
        self._message_models[self._current_peer_id].add_message(msg)
        self.peer_list_panel.update_last_message(self._current_peer_id, f"Bạn: {text}")
        self.message_view.scrollToBottom()

        self.input_field.clear()
        self.reply_preview.clear()

    def _on_chat_received(self, peer_id: str, data: dict):
        canonical_peer_id = self._find_canonical_peer_id(
            peer_id, data.get("sender", ""), data.get("sender_port", 0)
        )

        if canonical_peer_id not in self._message_models:
            self._message_models[canonical_peer_id] = MessageListModel(self)

        info = self._peer_info_map.get(canonical_peer_id, {})
        peer_avatar = info.get("avatar_path", "")

        msg = MessageData(
            msg_id=data.get("msg_id"),
            sender=self._sanitize_username(data.get("sender")),
            content=data.get("content"),
            timestamp=data.get("timestamp"),
            is_sent=False,
            reply_to=data.get("reply_to"),
            forward_from=data.get("forward_from"),
            avatar_path=peer_avatar,
        )
        self._message_models[canonical_peer_id].add_message(msg)
        self.peer_list_panel.update_last_message(canonical_peer_id, data.get("content"))

        if self._current_peer_id == canonical_peer_id:
            self.message_view.scrollToBottom()

    def _add_system_message(self, peer_id: str, content: str):
        if peer_id not in self._message_models:
            self._message_models[peer_id] = MessageListModel(self)
        msg = MessageData(
            msg_id="",
            sender="Hệ thống",
            content=content,
            timestamp=time.time(),
            is_sent=False,
            is_system=True,
        )
        self._message_models[peer_id].add_message(msg)
        if self._current_peer_id == peer_id:
            self.message_view.scrollToBottom()

    # ========================== TRUYỀN FILE ==========================

    def _open_file_picker(self):
        if not self._current_peer_id:
            return
        f, _ = QFileDialog.getOpenFileName(self, "Chọn file gửi qua P2P", "", "Tất cả các file (*.*)")
        if f:
            self._send_file(f)

    def _on_file_dropped(self, file_path: str):
        if not self._current_peer_id:
            QMessageBox.warning(self, "Chưa chọn Peer", "Vui lòng chọn 1 Peer trước khi kéo thả file!")
            return
        self._send_file(file_path)

    def _send_file(self, file_path: str):
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Tệp Không Tồn Tại", f"Không tìm thấy file:\n{file_path}")
            return

        info = self._peer_info_map.get(self._current_peer_id)
        if not info or info.get("status") != "online":
            QMessageBox.warning(self, "Không thể gửi", "Peer đang Offline!")
            return

        ip = info["ip"]
        port = info["port"]
        task_id = self.transfer_mgr.start_send_file(self._current_peer_id, ip, port, file_path)
        if task_id:
            self._last_sent_file = {
                "file_name": os.path.basename(file_path),
                "task_id": task_id,
                "peer_id": self._current_peer_id
            }
            self._add_system_message(self._current_peer_id, f"📤 Đang gửi file: {os.path.basename(file_path)}...")

    def _on_file_task_added(self, task: TransferTask):
        # Chuẩn hóa task.peer_id về Canonical ID để tin nhắn và tiến độ vào đúng khung chat
        canonical_pid = self._find_canonical_peer_id(
            task.peer_id,
            getattr(task, "sender_name", ""),
            getattr(task, "sender_port", 0)
        )
        if canonical_pid:
            task.peer_id = canonical_pid

        widget = FileRowWidget(task, self.file_container)
        widget.cancel_requested.connect(self.transfer_mgr.cancel_task)
        widget.delete_requested.connect(self._on_file_delete_requested)
        self._file_row_widgets[task.task_id] = widget
        self.file_container_layout.addWidget(widget)
        self.file_container.setVisible(True)

        # Thông báo nhận file rõ ràng cho người nhận
        is_download = (task.direction == TransferDirection.DOWNLOAD) or (getattr(task.direction, "value", "") == "download")
        if is_download:
            sender = getattr(task, "sender_name", "") or self._peer_info_map.get(task.peer_id, {}).get("username", "Đối phương")
            self._add_system_message(
                task.peer_id,
                f"📥 Đang nhận file: '{task.file_name}' ({task.size_str}) từ {sender}..."
            )
            self.statusBar().showMessage(f"📥 Đang nhận file '{task.file_name}' từ {sender}...", 8000)
            self.peer_list_panel.update_last_message(task.peer_id, f"📥 Nhận file: {task.file_name}")

    def _on_file_task_progress(self, task: TransferTask):
        if not task:
            return
        try:
            w = self._file_row_widgets.get(task.task_id)
            if w:
                w.update_task(task)
        except Exception as e:
            log.warning(f"Lỗi cập nhật tiến độ file: {e}")

    def _on_file_task_completed(self, task: TransferTask):
        if not task:
            return
        try:
            canonical_pid = self._find_canonical_peer_id(
                task.peer_id,
                getattr(task, "sender_name", ""),
                getattr(task, "sender_port", 0)
            )
            if canonical_pid:
                task.peer_id = canonical_pid

            w = self._file_row_widgets.get(task.task_id)
            if w:
                w.update_task(task)
            act = "Đã gửi" if task.direction.value == "upload" else "Đã nhận"
            tip = "(Có thể bấm '🗑️ Thu Hồi' nếu gửi nhầm)" if task.direction.value == "upload" else "(Lưu tại: received_files)"
            self._add_system_message(task.peer_id, f"✅ {act} file '{task.file_name}' thành công! {tip}")
            self.peer_list_panel.update_last_message(task.peer_id, f"✅ {act}: {task.file_name}")
            self.statusBar().showMessage(f"✅ {act} file '{task.file_name}' thành công!", 8000)
            # Giữ widget tiến độ 30 giây để người dùng bấm nút [📂 Mở File], [📁 Thư Mục] hoặc [🗑️ Thu Hồi]
            QTimer.singleShot(30000, lambda tid=task.task_id: self._remove_file_row(tid))
        except Exception as e:
            log.warning(f"Lỗi hoàn thành task file: {e}")

    def _open_received_files_folder(self):
        """Mở thư mục chứa file đã nhận trong Windows File Explorer."""
        folder = getattr(config, "download_dir", "")
        if not folder or not os.path.exists(folder):
            folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "received_files")
        os.makedirs(folder, exist_ok=True)
        try:
            os.startfile(folder)
        except Exception as e:
            QMessageBox.information(
                self,
                "Thư Mục Lưu File",
                f"Đường dẫn thư mục nhận file:\n{folder}\n\nLỗi mở tự động: {e}"
            )

    def _on_file_task_failed(self, task: TransferTask):
        if not task:
            return
        try:
            canonical_pid = self._find_canonical_peer_id(
                task.peer_id,
                getattr(task, "sender_name", ""),
                getattr(task, "sender_port", 0)
            )
            if canonical_pid:
                task.peer_id = canonical_pid

            w = self._file_row_widgets.get(task.task_id)
            if w:
                w.update_task(task)
            err_msg = task.error_msg or "Lỗi không xác định"
            self._add_system_message(task.peer_id, f"❌ Truyền file '{task.file_name}' thất bại: {err_msg}")
            self.statusBar().showMessage(f"❌ Truyền file '{task.file_name}' thất bại: {err_msg}", 8000)
            QTimer.singleShot(8000, lambda tid=task.task_id: self._remove_file_row(tid))
        except Exception as e:
            log.warning(f"Lỗi thất bại task file: {e}")

    def _remove_file_row(self, task_id: str):
        w = self._file_row_widgets.pop(task_id, None)
        if w:
            w.deleteLater()
        if not self._file_row_widgets:
            self.file_container.setVisible(False)

    def _on_file_delete_requested(self, task_id: str, file_name: str, direction_val: str):
        """Xử lý khi người dùng bấm nút [🗑️ Thu Hồi] hoặc [🗑️ Xóa File]."""
        if direction_val == "upload":
            # Bên gửi muốn thu hồi file gửi nhầm
            reply = QMessageBox.question(
                self,
                "Xác Nhận Thu Hồi File",
                f"Bạn có chắc chắn muốn thu hồi file:\n'{file_name}'?\n\nFile này sẽ được tự động xóa khỏi máy của đối phương.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            # Gửi gói tin file_delete sang cho đối phương
            if self._current_peer_id:
                info = self._peer_info_map.get(self._current_peer_id)
                if info and info.get("status") == "online":
                    ip = info["ip"]
                    port = info["port"]
                    h = make_file_delete_header(self.username, file_name, file_id=task_id)
                    send_message_direct_async(ip, port, h)

            self.transfer_mgr.delete_transferred_file(file_name, task_id)
            w = self._file_row_widgets.get(task_id)
            if w:
                w.mark_deleted(f"Đã thu hồi '{file_name}'")
            self._add_system_message(self._current_peer_id, f"🗑️ Bạn đã thu hồi file '{file_name}' thành công.")
            QTimer.singleShot(5000, lambda tid=task_id: self._remove_file_row(tid))

        else:
            # Bên nhận muốn xóa file khỏi máy
            reply = QMessageBox.question(
                self,
                "Xác Nhận Xóa File",
                f"Bạn có muốn xóa file '{file_name}' khỏi thư mục nhận (received_files) không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            self.transfer_mgr.delete_transferred_file(file_name, task_id)
            w = self._file_row_widgets.get(task_id)
            if w:
                w.mark_deleted(f"Đã xóa '{file_name}' khỏi máy")
            self._add_system_message(self._current_peer_id, f"🗑️ Đã xóa file '{file_name}' khỏi thư mục nhận.")
            QTimer.singleShot(5000, lambda tid=task_id: self._remove_file_row(tid))

    def _on_file_delete_received(self, peer_id: str, header: dict):
        """Xử lý khi đối phương gửi yêu cầu thu hồi / xóa file."""
        file_name = header.get("file_name", "")
        file_id = header.get("file_id", "")
        sender = header.get("sender", "Đối phương")

        # Tự động xóa file vật lý khỏi thư mục download
        self.transfer_mgr.delete_transferred_file(file_name, file_id)

        # Cập nhật widget tiến độ nếu còn hiển thị
        if file_id and file_id in self._file_row_widgets:
            w = self._file_row_widgets[file_id]
            w.mark_deleted(f"{sender} đã thu hồi file")
            QTimer.singleShot(6000, lambda tid=file_id: self._remove_file_row(tid))

        msg = f"⚠️ {sender} đã thu hồi file '{file_name}' (Đã tự động xóa khỏi thư mục received_files)."
        self._add_system_message(peer_id, msg)

    # ========================== CONTEXT MENU (REPLY & FORWARD) ==========================

    def _show_message_context_menu(self, pos):
        idx = self.message_view.indexAt(pos)
        if not idx.isValid() or not self._current_peer_id:
            return

        model = self._message_models.get(self._current_peer_id)
        if not model:
            return
        msg = model.get_message(idx.row())
        if not msg or msg.is_system:
            return

        menu = QMenu(self)
        reply_act = menu.addAction("↩ Trả lời (Reply)")
        fwd_act = menu.addAction("↪ Chuyển tiếp (Forward)")
        copy_act = menu.addAction("📋 Sao chép")
        menu.addSeparator()
        folder_act = menu.addAction("📂 Mở thư mục file đã nhận")
        recall_act = menu.addAction("🗑️ Thu hồi file vừa gửi gần nhất")

        action = menu.exec(self.message_view.viewport().mapToGlobal(pos))
        if action == reply_act:
            self.reply_preview.set_reply(msg.sender, msg.content, msg.msg_id)
            self.input_field.setFocus()
        elif action == fwd_act:
            self._trigger_forward(msg)
        elif action == copy_act:
            QApplication.clipboard().setText(msg.content)
        elif action == folder_act:
            self._open_received_files_folder()
        elif action == recall_act:
            if self._last_sent_file and self._last_sent_file.get("peer_id") == self._current_peer_id:
                self._on_file_delete_requested(
                    self._last_sent_file["task_id"],
                    self._last_sent_file["file_name"],
                    "upload"
                )
            else:
                QMessageBox.information(self, "Thu Hồi File", "Không tìm thấy file nào vừa được gửi tới Peer này.")

    def _trigger_forward(self, msg: MessageData):
        peers = self.peer_list_panel.get_all_peers(online_only=True)
        dlg = ForwardDialog(msg.content, peers, self)
        if dlg.exec():
            selected = dlg.get_selected_peers()
            sent_count = 0
            for pid in selected:
                info = self._peer_info_map.get(pid)
                if info and info.get("status") == "online":
                    text_to_header, is_encrypted, nonce_str = self._encrypt_text_if_ready(pid, msg.content)
                    # Bảo mật Forward: KHÔNG nhúng 'original_content' bản rõ vào forward_from vì JSON Header
                    # đi qua mạng không bị mã hóa toàn phần; chỉ giữ 'original_sender' để UI hiển thị dòng trích dẫn.
                    fwd_from = {"original_sender": self._sanitize_username(msg.sender)}
                    h = make_chat_header(
                        self.username,
                        text_to_header,
                        forward_from=fwd_from,
                        is_encrypted=is_encrypted,
                        nonce=nonce_str,
                    )
                    # Gắn sender_port để Peer nhận biết đúng Canonical ID khi giải mã gói Forward.
                    h["sender_port"] = self.listen_port
                    ok, err = send_message_direct(info["ip"], info["port"], h)
                    if ok:
                        sent_count += 1
                    else:
                        log.warning(f"Chuyển tiếp tới {pid} thất bại: {err}")
            self.statusBar().showMessage(f"↪ Đã chuyển tiếp tin nhắn tới {sent_count}/{len(selected)} Peer")

    # ========================== DIALOGS & EMOJI ==========================

    def _toggle_emoji_picker(self):
        if self.emoji_picker.isVisible():
            self.emoji_picker.hide()
        else:
            p = self.emoji_btn.mapToGlobal(self.emoji_btn.rect().topLeft())
            self.emoji_picker.move(p.x(), p.y() - self.emoji_picker.height() - 8)
            self.emoji_picker.show()

    def _on_emoji_selected(self, emo: str):
        self.input_field.insert(emo)
        self.input_field.setFocus()

    def _show_config_dialog(self):
        dlg = ConfigDialog(self.username, self.listen_port, self)
        if dlg.exec():
            res = dlg.get_config()
            self.username = self._sanitize_username(res["username"])
            config.username = self.username
            if res.get("avatar_path"):
                self.avatar_path = res["avatar_path"]
                config.avatar_path = self.avatar_path
            config.save()

            self.peer_list_panel.update_self_info(self.username, self.listen_port, self.avatar_path)
            self.transfer_mgr.listen_port = self.listen_port
            self.discovery.update_info(self.username, self.listen_port)

            peer_ip = res.get("peer_ip")
            peer_port = res.get("peer_port")
            if peer_ip and peer_port > 0:
                # Chuẩn hóa loopback IP
                norm_ip = "127.0.0.1" if peer_ip in ("localhost", "::1") else peer_ip
                if is_same_host(norm_ip, "127.0.0.1") and peer_port == self.listen_port:
                    QMessageBox.warning(self, "Lỗi Kết Nối", "Không thể kết nối tới chính cổng lắng nghe của bạn!")
                    return
                pid = f"{norm_ip}:{peer_port}"

                # Kiểm tra nếu peer này đã tồn tại trong _peer_info_map (tránh tạo trùng mục)
                target_pid = pid
                for existing_pid, info in self._peer_info_map.items():
                    if info.get("port") == peer_port:
                        if is_same_host(info.get("ip", ""), norm_ip):
                            target_pid = existing_pid
                            break

                if target_pid not in self._peer_info_map:
                    info_dict = {
                        "ip": norm_ip, "port": peer_port, "username": f"Peer_{peer_port}", "status": "online"
                    }
                    self._peer_info_map[target_pid] = info_dict
                    if pid != target_pid:
                        self._peer_info_map[pid] = info_dict
                    self.peer_list_panel.add_or_update_peer(target_pid, f"Peer_{peer_port}", norm_ip, peer_port, "online")
                else:
                    self._peer_info_map[target_pid]["status"] = "online"
                    if pid != target_pid:
                        self._peer_info_map[pid] = self._peer_info_map[target_pid]
                    self.peer_list_panel.set_peer_status(target_pid, "online")

                self.peer_list_panel.select_peer(target_pid)
                self._send_handshake(target_pid, norm_ip, peer_port)

    def _show_about(self):
        info = (
            "ỨNG DỤNG CHAT P2P BẢO MẬT (UDM_09)\n\n"
            "• Mô hình: Peer-to-Peer thuần túy (No Central Server)\n"
            "• Bảo mật: RSA-2048 động + AES-256-GCM + Checksum SHA-256\n"
            "• Truyền file: Chunking 64KB đa luồng, xóa file .part khi lỗi\n"
            "• Giao diện: PyQt6 Desktop, Avatar, Emoji, Reply, Forward\n"
            "• Chống treo GUI: Toàn bộ I/O trên QThread, giao tiếp qua pyqtSignal\n"
        )
        QMessageBox.information(self, "Thông Tin Đồ Án UDM_09", info)

    def closeEvent(self, event):
        """Dừng server và luồng discovery khi đóng cửa sổ."""
        self.listener.stop()
        self.discovery.stop()
        event.accept()
