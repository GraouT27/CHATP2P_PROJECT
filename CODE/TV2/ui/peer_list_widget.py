"""
Peer List Widget Module - Khung danh sách Peer bên trái (TV2).
"""

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame
)
from ui.chat_widgets import AvatarWidget


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
        self.addr_label.setToolTip(f"Địa chỉ TCP: {self.ip}:{self.port}")
        info_layout.addWidget(self.addr_label)

        self.last_msg_label = QLabel("")
        self.last_msg_label.setStyleSheet("color: #b0b0c8; font-size: 11px;")
        self.last_msg_label.setVisible(False)
        info_layout.addWidget(self.last_msg_label)

        layout.addLayout(info_layout, 1)

    def set_status(self, status: str):
        """Cập nhật trạng thái và đổi màu QSS."""
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
        self.username = name
        self.name_label.setText(name)
        self.avatar.set_name(name)

    def set_avatar_path(self, path: str):
        self.avatar_path = path
        self.avatar.set_image_path(path)

    def set_last_message(self, text: str):
        if text:
            disp = text if len(text) <= 26 else text[:26] + "..."
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
        self.my_port_label.setStyleSheet("color: #6c6c8a; font-size: 11px;")
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

    def add_or_update_peer(self, peer_id: str, username: str, ip: str, port: int,
                           status: str = "online", avatar_path: str = ""):
        if peer_id in self._peer_widgets:
            widget = self._peer_widgets[peer_id]
            widget.set_username(username)
            widget.set_status(status)
            if avatar_path:
                widget.set_avatar_path(avatar_path)
            return

        item = QListWidgetItem(self.list_widget)
        item.setSizeHint(QSize(280, 68))

        widget = PeerItemWidget(peer_id, username, ip, port, status, avatar_path, self.list_widget)
        self.list_widget.setItemWidget(item, widget)
        self._peer_widgets[peer_id] = widget

    def set_peer_status(self, peer_id: str, status: str):
        if peer_id in self._peer_widgets:
            self._peer_widgets[peer_id].set_status(status)

    def update_last_message(self, peer_id: str, text: str):
        if peer_id in self._peer_widgets:
            self._peer_widgets[peer_id].set_last_message(text)

    def _on_selection_changed(self):
        items = self.list_widget.selectedItems()
        if not items:
            return
        row = self.list_widget.row(items[0])
        # Tìm peer_id tương ứng với row
        peer_ids = list(self._peer_widgets.keys())
        if 0 <= row < len(peer_ids):
            self.peer_selected.emit(peer_ids[row])

    def get_peer_widget(self, peer_id: str) -> PeerItemWidget | None:
        return self._peer_widgets.get(peer_id)

    def get_peer_status(self, peer_id: str) -> str:
        w = self._peer_widgets.get(peer_id)
        return w.status if w else "offline"

    def select_peer(self, peer_id: str):
        """Chọn trực quan một Peer trên danh sách theo peer_id."""
        peer_ids = list(self._peer_widgets.keys())
        if peer_id in peer_ids:
            row = peer_ids.index(peer_id)
            self.list_widget.setCurrentRow(row)

    def get_all_peers(self, online_only: bool = False) -> list[tuple[str, str]]:
        res = []
        for pid, w in self._peer_widgets.items():
            if not online_only or w.status == "online":
                res.append((pid, w.username))
        return res
