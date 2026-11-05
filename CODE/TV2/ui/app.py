"""
App Module - Cửa sổ chính (MainWindow) ứng dụng Chat P2P PyQt6 (TV2 & TV3).
Kết nối toàn bộ tầng UI với lõi mạng p2p_node, crypto_manager và transfer_manager.
"""

import os
import sys
import time
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QFont, QAction, QClipboard
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
from p2p_node.transfer_task import TransferTask, TransferStatus
from p2p_node.sender import send_message_direct, PeerSocketClient
from shared.protocol import (
    make_handshake_header, make_handshake_ack_header,
    make_key_exchange_header, make_chat_header, pack_message
)
from ui.peer_list_widget import PeerListWidget
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
                self.setStyleSheet(f.read())

        # 1. Khởi tạo Core Cryptography & File Manager
        self.crypto_mgr = CryptoManager()
        self.transfer_mgr = TransferManager(self.crypto_mgr, config.download_dir, parent=self)

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

        # Nút gửi file nhanh trên header
        self.header_attach_btn = QPushButton("📎 Gửi File...")
        self.header_attach_btn.setEnabled(False)
        self.header_attach_btn.clicked.connect(self._open_file_picker)
        h_layout.addWidget(self.header_attach_btn)
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
        self.msg_handler.key_exchange_done.connect(self._on_key_exchange_done)
        self.msg_handler.chat_received.connect(self._on_chat_received)
        self.msg_handler.file_start_received.connect(self.transfer_mgr.handle_file_start)
        self.msg_handler.file_chunk_received.connect(self.transfer_mgr.handle_file_chunk)
        self.msg_handler.file_cancel_received.connect(self.transfer_mgr.cancel_task)

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
        log.warning(f"Peer ngắt kết nối: {peer_id}")
        if peer_id in self._peer_info_map:
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
        self._peer_info_map[peer_id] = {"ip": ip, "port": port, "username": username, "status": "online"}
        self.peer_list_panel.add_or_update_peer(peer_id, username, ip, port, "online")

        # Tự động gửi Handshake nếu chưa có khóa
        if not self.crypto_mgr.has_session_key(peer_id):
            self._send_handshake(peer_id, ip, port)

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

    def _find_canonical_peer_id(self, raw_peer_id: str, sender_name: str = "", sender_port: int = 0) -> str:
        """
        Ánh xạ kết nối socket tạm thời (ephemeral port) về đúng Canonical Peer ID (listen_port)
        dựa trên sender_port, IP và Username.
        """
        raw_ip = raw_peer_id.split(":")[0] if ":" in raw_peer_id else raw_peer_id
        if sender_port > 0:
            target = f"{raw_ip}:{sender_port}"
            if target in self._peer_info_map:
                return target

        if raw_peer_id in self._peer_info_map:
            return raw_peer_id

        # Tìm theo username
        if sender_name:
            for pid, info in self._peer_info_map.items():
                if info.get("username") == sender_name:
                    return pid

        # Tìm theo IP nếu chỉ có 1 peer từ IP đó
        matching = [pid for pid, info in self._peer_info_map.items() if info.get("ip") == raw_ip]
        if len(matching) == 1:
            return matching[0]

        return raw_peer_id

    def _send_handshake(self, peer_id: str, ip: str, port: int):
        """Gửi gói tin Handshake kèm RSA Public Key và Avatar sang Peer."""
        pub_key = self.crypto_mgr.get_public_key_pem()
        avatar_b64 = ""
        if self.avatar_path and os.path.exists(self.avatar_path):
            try:
                import base64
                with open(self.avatar_path, "rb") as f:
                    avatar_b64 = base64.b64encode(f.read()).decode("utf-8")
            except Exception:
                pass
        h = make_handshake_header(self.username, self.listen_port, pub_key, avatar_b64=avatar_b64)
        send_message_direct(ip, port, h)

    def _on_handshake_received(self, peer_id: str, username: str, listen_port: int, pub_key: str, avatar_b64: str):
        ip = peer_id.split(":")[0]
        actual_port = listen_port if listen_port > 0 else int(peer_id.split(":")[1])
        canonical_peer_id = f"{ip}:{actual_port}"

        avatar_path = ""
        if avatar_b64:
            try:
                import base64
                avatar_bytes = base64.b64decode(avatar_b64.encode("utf-8"))
                cache_dir = os.path.join(config.download_dir, "peer_avatars")
                os.makedirs(cache_dir, exist_ok=True)
                safe_name = f"avatar_{canonical_peer_id.replace(':', '_').replace('.', '_')}.png"
                avatar_path = os.path.join(cache_dir, safe_name)
                with open(avatar_path, "wb") as f:
                    f.write(avatar_bytes)
            except Exception as e:
                log.warning(f"Không thể giải mã avatar từ {canonical_peer_id}: {e}")

        self._peer_info_map[canonical_peer_id] = {
            "ip": ip, "port": actual_port, "username": username,
            "status": "online", "avatar_path": avatar_path
        }
        self.peer_list_panel.add_or_update_peer(canonical_peer_id, username, ip, actual_port, "online", avatar_path)

        # Nếu là gói handshake đến, gửi lại handshake_ack kèm Public Key của mình và Avatar
        if listen_port > 0:
            my_avatar_b64 = ""
            if self.avatar_path and os.path.exists(self.avatar_path):
                try:
                    import base64
                    with open(self.avatar_path, "rb") as f:
                        my_avatar_b64 = base64.b64encode(f.read()).decode("utf-8")
                except Exception:
                    pass
            ack_h = make_handshake_ack_header(self.username, self.crypto_mgr.get_public_key_pem(), avatar_b64=my_avatar_b64)
            send_message_direct(ip, actual_port, ack_h)

        # Bên khởi tạo sinh Khóa phiên AES-256 và gửi sang
        enc_session_key = self.crypto_mgr.generate_and_encrypt_session_key(canonical_peer_id)
        if enc_session_key:
            key_h = make_key_exchange_header(self.username, enc_session_key)
            send_message_direct(ip, actual_port, key_h)

        self._add_system_message(canonical_peer_id, f"🔒 Đã thiết lập kênh bảo mật RSA/AES-256 với {username}.")

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

        # Mã hóa AES-256 nếu đã có session key
        is_encrypted = False
        payload_bytes = b""
        nonce_str = None

        if self.crypto_mgr.has_session_key(self._current_peer_id):
            enc_res = self.crypto_mgr.encrypt_text(self._current_peer_id, text)
            if enc_res:
                cipher_b64, nonce_b64 = enc_res
                is_encrypted = True
                text_to_header = cipher_b64
                nonce_str = nonce_b64
            else:
                text_to_header = text
        else:
            text_to_header = text

        header = make_chat_header(
            username=self.username,
            text=text_to_header,
            reply_to=reply_data,
            is_encrypted=is_encrypted,
            nonce=nonce_str,
        )
        header["sender_port"] = self.listen_port

        ok, err = send_message_direct(ip, port, header, payload_bytes)
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
            sender=data.get("sender"),
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
            self._add_system_message(self._current_peer_id, f"📤 Đang gửi file: {os.path.basename(file_path)}...")

    def _on_file_task_added(self, task: TransferTask):
        widget = FileRowWidget(task, self.file_container)
        widget.cancel_requested.connect(self.transfer_mgr.cancel_task)
        self._file_row_widgets[task.task_id] = widget
        self.file_container_layout.addWidget(widget)
        self.file_container.setVisible(True)

    def _on_file_task_progress(self, task: TransferTask):
        w = self._file_row_widgets.get(task.task_id)
        if w:
            w.update_task(task)

    def _on_file_task_completed(self, task: TransferTask):
        w = self._file_row_widgets.get(task.task_id)
        if w:
            w.update_task(task)
        act = "Đã gửi" if task.direction.value == "upload" else "Đã nhận"
        self._add_system_message(task.peer_id, f"✅ {act} file '{task.file_name}' thành công!")
        QTimer.singleShot(8000, lambda tid=task.task_id: self._remove_file_row(tid))

    def _on_file_task_failed(self, task: TransferTask):
        w = self._file_row_widgets.get(task.task_id)
        if w:
            w.update_task(task)
        QTimer.singleShot(8000, lambda tid=task.task_id: self._remove_file_row(tid))

    def _remove_file_row(self, task_id: str):
        w = self._file_row_widgets.pop(task_id, None)
        if w:
            w.deleteLater()
        if not self._file_row_widgets:
            self.file_container.setVisible(False)

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

        action = menu.exec(self.message_view.viewport().mapToGlobal(pos))
        if action == reply_act:
            self.reply_preview.set_reply(msg.sender, msg.content, msg.msg_id)
            self.input_field.setFocus()
        elif action == fwd_act:
            self._trigger_forward(msg)
        elif action == copy_act:
            QApplication.clipboard().setText(msg.content)

    def _trigger_forward(self, msg: MessageData):
        peers = self.peer_list_panel.get_all_peers(online_only=True)
        dlg = ForwardDialog(msg.content, peers, self)
        if dlg.exec():
            selected = dlg.get_selected_peers()
            for pid in selected:
                info = self._peer_info_map.get(pid)
                if info and info.get("status") == "online":
                    fwd_from = {"original_sender": msg.sender, "original_content": msg.content}
                    h = make_chat_header(self.username, msg.content, forward_from=fwd_from)
                    h["sender_port"] = self.listen_port
                    send_message_direct(info["ip"], info["port"], h)
            self.statusBar().showMessage(f"↪ Đã chuyển tiếp tin nhắn tới {len(selected)} Peer")

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
            self.username = res["username"]
            config.username = self.username
            if res.get("avatar_path"):
                self.avatar_path = res["avatar_path"]
                config.avatar_path = self.avatar_path
            config.save()

            self.peer_list_panel.update_self_info(self.username, self.listen_port, self.avatar_path)
            self.discovery.update_info(self.username, self.listen_port)

            peer_ip = res.get("peer_ip")
            peer_port = res.get("peer_port")
            if peer_ip and peer_port > 0:
                pid = f"{peer_ip}:{peer_port}"
                self._peer_info_map[pid] = {"ip": peer_ip, "port": peer_port, "username": f"Peer_{peer_port}", "status": "online"}
                self.peer_list_panel.add_or_update_peer(pid, f"Peer_{peer_port}", peer_ip, peer_port, "online")
                self.peer_list_panel.select_peer(pid)
                self._send_handshake(pid, peer_ip, peer_port)

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
