"""
Dialogs Module - Hộp thoại cấu hình, chọn Avatar và Chuyển tiếp (Forward) tin nhắn (TV3).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QListWidget, QListWidgetItem, QCheckBox,
    QFrame, QFileDialog
)


class ForwardDialog(QDialog):
    """Hộp thoại chọn 1 hoặc nhiều Peer để chuyển tiếp tin nhắn."""

    def __init__(self, message_text: str, available_peers: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chuyển Tiếp Tin Nhắn")
        self.setFixedSize(380, 420)
        self.setModal(True)
        self.message_text = message_text
        self.available_peers = available_peers
        self.selected_peer_ids: list[str] = []
        self._checkboxes: dict[str, QCheckBox] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Khung preview tin nhắn
        preview_frame = QFrame()
        preview_frame.setStyleSheet("background-color: #2a2a40; border-left: 3px solid #1a73e8; border-radius: 4px; padding: 6px;")
        prev_layout = QVBoxLayout(preview_frame)
        prev_layout.addWidget(QLabel("Nội dung chuyển tiếp:"))
        disp_text = self.message_text if len(self.message_text) <= 120 else self.message_text[:120] + "..."
        lbl = QLabel(disp_text)
        lbl.setWordWrap(True)
        prev_layout.addWidget(lbl)
        layout.addWidget(preview_frame)

        # Danh sách Peer
        layout.addWidget(QLabel("Chọn Peer nhận:"))
        self.list_widget = QListWidget()
        if not self.available_peers:
            item = QListWidgetItem("Không có Peer nào đang Online")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
        else:
            for pid, uname in self.available_peers:
                item = QListWidgetItem(self.list_widget)
                cb = QCheckBox(f"{uname} ({pid})")
                self._checkboxes[pid] = cb
                self.list_widget.setItemWidget(item, cb)
        layout.addWidget(self.list_widget, 1)

        # Nút xác nhận
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("Hủy")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        fwd_btn = QPushButton("Chuyển tiếp")
        fwd_btn.setStyleSheet("background-color: #1a73e8; color: white; font-weight: bold; padding: 6px 14px; border-radius: 6px;")
        fwd_btn.clicked.connect(self._on_confirm)
        btn_box.addWidget(fwd_btn)

        layout.addLayout(btn_box)

    def _on_confirm(self):
        self.selected_peer_ids = [pid for pid, cb in self._checkboxes.items() if cb.isChecked()]
        self.accept()

    def get_selected_peers(self) -> list[str]:
        return self.selected_peer_ids


class ConfigDialog(QDialog):
    """Hộp thoại cấu hình người dùng, cổng mạng P2P và kết nối nhanh."""

    def __init__(self, current_username: str, current_port: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cấu Hình Mạng P2P")
        self.setFixedSize(420, 420)
        self.setModal(True)
        self._result = {}
        self._setup_ui(current_username, current_port)

    def _setup_ui(self, username: str, port: int):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(12)

        title = QLabel("⚙️ Cấu Hình Nút Mạng P2P")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a73e8;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Username
        layout.addWidget(QLabel("Tên người dùng:"))
        self.user_input = QLineEdit(username)
        layout.addWidget(self.user_input)

        # Local Port
        layout.addWidget(QLabel("Cổng lắng nghe (Listen Port):"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1024, 65535)
        self.port_input.setValue(port)
        layout.addWidget(self.port_input)

        # Chọn Avatar
        avatar_row = QHBoxLayout()
        self.avatar_label = QLabel("Chưa chọn ảnh avatar mới")
        self.avatar_label.setStyleSheet("color: #b0b0c8; font-size: 11px;")
        self.avatar_path = ""
        browse_btn = QPushButton("📷 Chọn Avatar...")
        browse_btn.clicked.connect(self._browse_avatar)
        avatar_row.addWidget(self.avatar_label, 1)
        avatar_row.addWidget(browse_btn)
        layout.addLayout(avatar_row)

        # Kết nối nhanh tới Peer từ xa
        conn_frame = QFrame()
        conn_frame.setStyleSheet("border: 1px solid #4a4a66; border-radius: 6px; padding: 10px;")
        cf_layout = QVBoxLayout(conn_frame)
        cf_layout.addWidget(QLabel("🔗 Kết nối nhanh tới Peer từ xa (Tùy chọn):"))

        ip_row = QHBoxLayout()
        ip_row.addWidget(QLabel("IP:"))
        self.peer_ip_input = QLineEdit("")
        self.peer_ip_input.setPlaceholderText("Để trống nếu không kết nối")
        ip_row.addWidget(self.peer_ip_input, 2)
        ip_row.addWidget(QLabel("Port:"))
        self.peer_port_input = QSpinBox()
        self.peer_port_input.setRange(0, 65535)
        self.peer_port_input.setValue(0)
        self.peer_port_input.setSpecialValueText("--")
        ip_row.addWidget(self.peer_port_input, 1)
        cf_layout.addLayout(ip_row)
        layout.addWidget(conn_frame)

        # Nút hành động
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("Hủy")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("Lưu & Áp Dụng")
        save_btn.setStyleSheet("background-color: #1a73e8; color: white; font-weight: bold; padding: 6px 14px; border-radius: 6px;")
        save_btn.clicked.connect(self._on_save)
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)

    def _browse_avatar(self):
        f, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh đại diện", "", "Hình ảnh (*.png *.jpg *.jpeg *.bmp)")
        if f:
            self.avatar_path = f
            self.avatar_label.setText(f.split("/")[-1].split("\\")[-1])

    def _on_save(self):
        self._result = {
            "username": self.user_input.text().strip() or "User",
            "listen_port": self.port_input.value(),
            "avatar_path": self.avatar_path,
            "peer_ip": self.peer_ip_input.text().strip(),
            "peer_port": self.peer_port_input.value(),
        }
        self.accept()

    def get_config(self) -> dict:
        return self._result
