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
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
                color: #111111;
            }
            QLabel {
                color: #111111;
                font-size: 13px;
            }
            QListWidget {
                background-color: #ffffff;
                color: #111111;
                border: 1px solid #ced4da;
                border-radius: 6px;
            }
            QCheckBox {
                color: #111111;
                font-size: 13px;
            }
        """)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Khung preview tin nhắn
        preview_frame = QFrame()
        preview_frame.setObjectName("previewFrame")
        preview_frame.setStyleSheet("QFrame#previewFrame { background-color: #e8f0fe; border-left: 3px solid #1a73e8; border-radius: 4px; padding: 6px; }")
        prev_layout = QVBoxLayout(preview_frame)
        lbl_title = QLabel("Nội dung chuyển tiếp:")
        lbl_title.setStyleSheet("color: #1a73e8; font-weight: bold;")
        prev_layout.addWidget(lbl_title)
        disp_text = self.message_text if len(self.message_text) <= 120 else self.message_text[:120] + "..."
        lbl = QLabel(disp_text)
        lbl.setStyleSheet("color: #111111;")
        lbl.setWordWrap(True)
        prev_layout.addWidget(lbl)
        layout.addWidget(preview_frame)

        # Danh sách Peer
        lbl_select = QLabel("Chọn Peer nhận:")
        lbl_select.setStyleSheet("color: #111111; font-weight: bold;")
        layout.addWidget(lbl_select)
        self.list_widget = QListWidget()
        if not self.available_peers:
            item = QListWidgetItem("Không có Peer nào đang Online")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
        else:
            for pid, uname in self.available_peers:
                item = QListWidgetItem(self.list_widget)
                cb = QCheckBox(f"{uname} ({pid})")
                cb.setStyleSheet("color: #111111;")
                self._checkboxes[pid] = cb
                self.list_widget.setItemWidget(item, cb)
        layout.addWidget(self.list_widget, 1)

        # Nút xác nhận
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("Hủy")
        cancel_btn.setStyleSheet("color: #111111; background-color: #e9ecef; border: 1px solid #ced4da; border-radius: 6px; padding: 6px 14px; font-weight: 500;")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        fwd_btn = QPushButton("Chuyển tiếp")
        fwd_btn.setStyleSheet("background-color: #1a73e8; color: white; font-weight: bold; padding: 6px 14px; border-radius: 6px; border: none;")
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
        self.setFixedSize(430, 450)
        self.setModal(True)
        self._result = {}
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
                color: #000000;
            }
            QLabel {
                color: #000000;
                font-size: 13px;
            }
            QLineEdit, QSpinBox {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #ced4da;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                selection-background-color: #1a73e8;
                selection-color: #ffffff;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 1px solid #1a73e8;
            }
            QPushButton {
                background-color: #e9ecef;
                color: #000000;
                border: 1px solid #ced4da;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #dee2e6;
            }
        """)
        self._setup_ui(current_username, current_port)

    def _setup_ui(self, username: str, port: int):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(12)

        title = QLabel("⚙️ Cấu Hình Nút Mạng P2P")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a73e8; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Username
        lbl_user = QLabel("Tên người dùng:")
        lbl_user.setStyleSheet("color: #000000; font-weight: bold;")
        layout.addWidget(lbl_user)
        self.user_input = QLineEdit(username)
        self.user_input.setStyleSheet("color: #000000; background-color: #ffffff; border: 1px solid #ced4da; border-radius: 6px; padding: 6px 10px;")
        layout.addWidget(self.user_input)

        # Local Port
        lbl_port = QLabel("Cổng lắng nghe (Listen Port):")
        lbl_port.setStyleSheet("color: #000000; font-weight: bold;")
        layout.addWidget(lbl_port)
        self.port_input = QSpinBox()
        self.port_input.setRange(1024, 65535)
        self.port_input.setValue(port)
        self.port_input.setStyleSheet("color: #000000; background-color: #ffffff; border: 1px solid #ced4da; border-radius: 6px; padding: 6px 10px;")
        layout.addWidget(self.port_input)

        # Chọn Avatar
        avatar_row = QHBoxLayout()
        self.avatar_label = QLabel("Chưa chọn ảnh avatar mới")
        self.avatar_label.setStyleSheet("color: #333333; font-size: 12px;")
        self.avatar_path = ""
        browse_btn = QPushButton("📷 Chọn Avatar...")
        browse_btn.setStyleSheet("color: #000000; background-color: #e9ecef; border: 1px solid #ced4da; border-radius: 6px; padding: 6px 12px; font-weight: 500;")
        browse_btn.clicked.connect(self._browse_avatar)
        avatar_row.addWidget(self.avatar_label, 1)
        avatar_row.addWidget(browse_btn)
        layout.addLayout(avatar_row)

        # Kết nối nhanh tới Peer từ xa
        conn_frame = QFrame()
        conn_frame.setObjectName("connFrame")
        conn_frame.setStyleSheet("""
            QFrame#connFrame {
                border: 1px solid #ced4da;
                border-radius: 8px;
                background-color: #ffffff;
                padding: 10px;
            }
        """)
        cf_layout = QVBoxLayout(conn_frame)
        lbl_quick = QLabel("🔗 Kết nối nhanh tới Peer từ xa (Tùy chọn):")
        lbl_quick.setStyleSheet("color: #000000; font-weight: bold;")
        cf_layout.addWidget(lbl_quick)

        ip_row = QHBoxLayout()
        lbl_ip = QLabel("IP:")
        lbl_ip.setStyleSheet("color: #000000; font-weight: bold;")
        ip_row.addWidget(lbl_ip)
        self.peer_ip_input = QLineEdit("")
        self.peer_ip_input.setPlaceholderText("Để trống nếu không kết nối")
        self.peer_ip_input.setStyleSheet("color: #000000; background-color: #ffffff; border: 1px solid #ced4da; border-radius: 6px; padding: 5px 8px;")
        ip_row.addWidget(self.peer_ip_input, 2)
        lbl_peer_port = QLabel("Port:")
        lbl_peer_port.setStyleSheet("color: #000000; font-weight: bold;")
        ip_row.addWidget(lbl_peer_port)
        self.peer_port_input = QSpinBox()
        self.peer_port_input.setRange(0, 65535)
        self.peer_port_input.setValue(0)
        self.peer_port_input.setSpecialValueText("--")
        self.peer_port_input.setStyleSheet("color: #000000; background-color: #ffffff; border: 1px solid #ced4da; border-radius: 6px; padding: 5px 8px;")
        ip_row.addWidget(self.peer_port_input, 1)
        cf_layout.addLayout(ip_row)
        layout.addWidget(conn_frame)

        # Nút hành động
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("Hủy")
        cancel_btn.setStyleSheet("color: #000000; background-color: #e9ecef; border: 1px solid #ced4da; border-radius: 6px; padding: 6px 14px; font-weight: 500;")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("Lưu & Áp Dụng")
        save_btn.setStyleSheet("background-color: #1a73e8; color: #ffffff; font-weight: bold; padding: 6px 16px; border-radius: 6px; border: none;")
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
