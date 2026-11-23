"""
Peer List Widget Module - Khung danh sách Peer bên trái (TV2).
"""

import socket
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame
)
from ui.chat_widgets import AvatarWidget


def get_local_ips() -> set[str]:
    """Lấy danh sách các IP đại diện cho chính máy tính cục bộ (loopback + LAN IPs)."""
    ips = {"127.0.0.1", "localhost", "::1"}
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            ips.add(ip)
    except Exception:
        pass
    return ips


def is_same_host(ip1: str, ip2: str) -> bool:
    """Kiểm tra 2 IP có trỏ đến cùng một máy chủ (host) hay không."""
    if not ip1 or not ip2:
        return False
    if ip1 == ip2:
        return True
    local_ips = get_local_ips()
    return (ip1 in local_ips and ip2 in local_ips)


class PeerItemWidget(QWidget):
    """Widget 1 dòng trong danh sách Peer bên trái."""

    def __init__(self, peer_id: str, username: str, ip: str, port: int,
                 status: str = "online", avatar_path: str = "", parent=None):
        super().__init__(parent)
        self.peer_id = peer_id
        self.username = username
        self.ip = ip
        self.port = port
        self.status = status
        self.avatar_path = avatar_path
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        # Avatar
        self.avatar = AvatarWidget(self.username, size=38, image_path=self.avatar_path)
        layout.addWidget(self.avatar)

        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        top_row = QHBoxLayout()
        self.name_label = QLabel(self.username)
        self.name_label.setObjectName("peerNameLabel")
        self.name_label.setToolTip(self.username)
        top_row.addWidget(self.name_label, 1)

        self.status_label = QLabel(self.status.capitalize())
        self.status_label.setObjectName("peerStatusLabel")
        self.status_label.setProperty("status", self.status)
        top_row.addWidget(self.status_label)
        info_layout.addLayout(top_row)

        self.addr_label = QLabel(f"{self.ip}:{self.port}")
        self.addr_label.setObjectName("peerIpLabel")
        self.addr_label.setStyleSheet("color: #ffffff; font-size: 11px;")
        self.addr_label.setToolTip(f"Địa chỉ TCP: {self.ip}:{self.port}")
        info_layout.addWidget(self.addr_label)

        self.last_msg_label = QLabel("")
        self.last_msg_label.setStyleSheet("color: #b0b0c8; font-size: 11px;")
        self.last_msg_label.setVisible(False)
        info_layout.addWidget(self.last_msg_label)

        layout.addLayout(info_layout, 1)

    def set_status(self, status: str):
        """
        Cập nhật trạng thái Online/Offline và ép Qt nạp lại style QSS.
        Lý do phải dùng unpolish() rồi polish(): trong Qt, khi thay đổi dynamic property
        ([status="offline"]), QSS không tự vẽ lại màu ngay mà cần tháo/nạp lại style.
        """
        self.status = status
        self.status_label.setText(status.capitalize())
        self.status_label.setProperty("status", status)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        if status == "offline":
            self.name_label.setStyleSheet("color: #8c8ca0; font-size: 14px; font-weight: bold;")
        else:
            self.name_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold;")

    def set_username(self, name: str):
        safe = str(name or "Peer")
        self.username = safe
        self.name_label.setText(safe)
        self.avatar.set_name(safe)

    def update_endpoint(self, ip: str, port: int):
        """Cập nhật lại IP và cổng mạng của Peer khi khởi động lại hoặc chuyển cổng."""
        self.ip = ip
        self.port = port
        self.addr_label.setText(f"{self.ip}:{self.port}")
        self.addr_label.setToolTip(f"Địa chỉ TCP: {self.ip}:{self.port}")

    def set_avatar_path(self, path: str):
        self.avatar_path = path
        self.avatar.set_image_path(path)

    def set_last_message(self, text: str):
        # Loại bỏ \r và \n để nội dung xem trước luôn nằm gọn trên 1 dòng, tránh vỡ chiều cao item.
        clean = str(text or "").replace("\r", " ").replace("\n", " ").strip()
        if clean:
            disp = clean if len(clean) <= 26 else clean[:26] + "..."
            self.last_msg_label.setText(disp)
            self.last_msg_label.setVisible(True)


class PeerListWidget(QWidget):
    """Toàn bộ khung danh sách Peer bên trái."""
    peer_selected = pyqtSignal(str)              # (peer_id)
    connect_clicked = pyqtSignal()               # Mở hộp thoại kết nối thủ công
    settings_clicked = pyqtSignal()              # Mở cấu hình

    def __init__(self, username: str, port: int, parent=None):
        super().__init__(parent)
        self.setObjectName("peerListContainer")
        self.username = username
        self.port = port
        self._peer_widgets: dict[str, PeerItemWidget] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header: Thông tin bản thân
        header = QFrame()
        header.setObjectName("peerListHeader")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 10, 12, 10)

        self.my_avatar = AvatarWidget(self.username, size=38)
        h_layout.addWidget(self.my_avatar)

        my_info = QVBoxLayout()
        my_info.setSpacing(2)
        self.my_name_label = QLabel(self.username)
        self.my_name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.my_port_label = QLabel(f"Cổng: {self.port}")
        self.my_port_label.setStyleSheet("color: #ffffff; font-size: 11px;")
        my_info.addWidget(self.my_name_label)
        my_info.addWidget(self.my_port_label)
        h_layout.addLayout(my_info, 1)

        # Nút cài đặt & kết nối
        add_btn = QPushButton("➕")
        add_btn.setToolTip("Kết nối tới Peer mới")
        add_btn.setFixedSize(30, 30)
        add_btn.clicked.connect(self.connect_clicked.emit)
        h_layout.addWidget(add_btn)

        settings_btn = QPushButton("⚙️")
        settings_btn.setToolTip("Cấu hình nút P2P")
        settings_btn.setFixedSize(30, 30)
        settings_btn.clicked.connect(self.settings_clicked.emit)
        h_layout.addWidget(settings_btn)

        layout.addWidget(header)

        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("peerListWidget")
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.list_widget, 1)

    def update_self_info(self, username: str, port: int, avatar_path: str = ""):
        self.username = username
        self.port = port
        self.my_name_label.setText(username)
        self.my_port_label.setText(f"Cổng: {port}")
        self.my_avatar.set_name(username)
        if avatar_path:
            self.my_avatar.set_image_path(avatar_path)

    def remove_peer(self, peer_id: str):
        """Xóa một Peer khỏi danh sách giao diện."""
        widget = self._get_widget(peer_id)
        if not widget:
            return

        # Xóa toàn bộ các alias trỏ đến widget này trong _peer_widgets
        for pid, w in list(self._peer_widgets.items()):
            if w == widget:
                del self._peer_widgets[pid]

        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if item and self.list_widget.itemWidget(item) == widget:
                self.list_widget.takeItem(row)
                widget.deleteLater()
                break

    def add_or_update_peer(self, peer_id: str, username: str, ip: str, port: int,
                           status: str = "online", avatar_path: str = ""):
        matched_widget = None
        matched_pid = None

        if peer_id in self._peer_widgets:
            matched_widget = self._peer_widgets[peer_id]
            matched_pid = peer_id
        else:
            is_real_name = bool(username and not username.startswith("Peer_"))
            for existing_pid, widget in list(self._peer_widgets.items()):
                same_host = is_same_host(widget.ip, ip)
                is_widget_real = bool(widget.username and not widget.username.startswith("Peer_"))
                same_real_name = is_real_name and is_widget_real and (widget.username.lower() == username.lower())
                same_port = (port > 0 and widget.port == port)
                either_placeholder = widget.username.startswith("Peer_") or username.startswith("Peer_")

                # Trùng nếu:
                # 1) Cùng tên thật (AliceTest, Bob, ...) -> luôn đại diện cho cùng 1 người, không nhân bản
                # 2) HOẶC cùng port (khi kết nối qua loopback / LAN IP / placeholder)
                if same_real_name or (same_port and (same_host or either_placeholder)):
                    matched_widget = widget
                    matched_pid = existing_pid
                    break

        if matched_widget:
            if username and (not username.startswith("Peer_") or matched_widget.username.startswith("Peer_")):
                matched_widget.set_username(username)
            if port > 0:
                matched_widget.update_endpoint(ip, port)
            matched_widget.set_status(status)
            if avatar_path:
                matched_widget.set_avatar_path(avatar_path)

            self._peer_widgets[matched_pid] = matched_widget
            self._peer_widgets[peer_id] = matched_widget

            for row in range(self.list_widget.count()):
                item = self.list_widget.item(row)
                if item and item.data(Qt.ItemDataRole.UserRole) in (matched_pid, peer_id):
                    item.setData(Qt.ItemDataRole.UserRole, peer_id)
                    break

            # Dọn dẹp triệt để bất kỳ mục rác trùng lặp cũ nào khác cùng tên
            is_real_name = bool(matched_widget.username and not matched_widget.username.startswith("Peer_"))
            if is_real_name:
                for other_pid, other_w in list(self._peer_widgets.items()):
                    if other_w != matched_widget and other_w.username.lower() == matched_widget.username.lower():
                        if other_w.status == "offline" or is_same_host(other_w.ip, matched_widget.ip):
                            self.remove_peer(other_pid)
            return

        item = QListWidgetItem(self.list_widget)
        # Lưu trực tiếp peer_id vào Qt.ItemDataRole.UserRole của QListWidgetItem.
        item.setData(Qt.ItemDataRole.UserRole, peer_id)
        item.setSizeHint(QSize(280, 68))

        widget = PeerItemWidget(peer_id, username, ip, port, status, avatar_path, self.list_widget)
        self.list_widget.setItemWidget(item, widget)
        self._peer_widgets[peer_id] = widget

    def _get_widget(self, peer_id: str) -> PeerItemWidget | None:
        if peer_id in self._peer_widgets:
            return self._peer_widgets[peer_id]
        ip, _, port_s = peer_id.partition(":")
        if port_s.isdigit():
            port = int(port_s)
            for pid, w in self._peer_widgets.items():
                if w.port == port and is_same_host(w.ip, ip):
                    return w
        return None

    def set_peer_status(self, peer_id: str, status: str):
        w = self._get_widget(peer_id)
        if w:
            w.set_status(status)

    def update_last_message(self, peer_id: str, text: str):
        w = self._get_widget(peer_id)
        if w:
            w.set_last_message(text)

    def _on_selection_changed(self):
        items = self.list_widget.selectedItems()
        if not items:
            return
        # Đọc lại peer_id trực tiếp từ UserRole của item đang được chọn.
        peer_id = items[0].data(Qt.ItemDataRole.UserRole)
        if peer_id:
            self.peer_selected.emit(str(peer_id))

    def get_peer_widget(self, peer_id: str) -> PeerItemWidget | None:
        return self._get_widget(peer_id)

    def get_peer_status(self, peer_id: str) -> str:
        w = self._get_widget(peer_id)
        return w.status if w else "offline"

    def select_peer(self, peer_id: str):
        """Chọn trực quan một Peer trên danh sách theo peer_id."""
        w = self._get_widget(peer_id)
        target_id = w.peer_id if w else peer_id
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole) in (peer_id, target_id):
                self.list_widget.setCurrentRow(row)
                return

    def get_all_peers(self, online_only: bool = False) -> list[tuple[str, str]]:
        seen_widgets = set()
        res = []
        for pid, w in self._peer_widgets.items():
            if w not in seen_widgets:
                seen_widgets.add(w)
                if not online_only or w.status == "online":
                    res.append((w.peer_id, w.username))
        return res
