"""
Module hộp thoại (Modals / QDialog) cho ứng dụng Chat P2P PyQt6 (TV3):
- ForwardDialog: Hộp thoại chọn 1 hoặc nhiều Peer để chuyển tiếp (Forward) tin nhắn.
- ConfigDialog: Hộp thoại chọn ảnh đại diện (Avatar), đổi Username và kết nối Peer thủ công qua IP/Port.
- validate_avatar_file(): Kiểm tra tính hợp lệ của tệp ảnh đại diện (chặn tệp rỗng, sai định dạng, quá dung lượng).
"""
import ipaddress
import os
from typing import Any, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QFileDialog,
    QMessageBox, QFrame, QSpinBox, QGroupBox, QFormLayout, QWidget
)

MAX_AVATAR_BYTES = 5 * 1024 * 1024  # Giới hạn ảnh Avatar tối đa 5 MB
VALID_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}


def validate_avatar_file(file_path: str) -> tuple[bool, str]:
    """
    Kiểm tra tệp ảnh đại diện (Avatar) trước khi nạp lên giao diện.
    Phục vụ kịch bản kiểm thử dữ liệu không hợp lệ (Invalid Data Test).
    """
    if not file_path or not str(file_path).strip():
        return False, "Đường dẫn ảnh trống."

    clean_path = os.path.normpath(str(file_path).strip())
    if not os.path.exists(clean_path) or not os.path.isfile(clean_path):
        return False, f"Không tìm thấy tệp ảnh:\n{clean_path}"

    ext = os.path.splitext(clean_path)[1].lower()
    if ext not in VALID_IMAGE_EXTS:
        return False, (
            f"Định dạng '{ext}' không được hỗ trợ làm Avatar.\n"
            "Vui lòng chọn ảnh .png, .jpg, .jpeg, .bmp hoặc .webp."
        )

    try:
        size = os.path.getsize(clean_path)
    except OSError as exc:
        return False, f"Không thể đọc tệp ảnh:\n{exc}"

    if size <= 0:
        return False, "Tệp ảnh rỗng (0 Byte)."

    if size > MAX_AVATAR_BYTES:
        return False, f"Ảnh quá lớn ({size / (1024 * 1024):.1f} MB). Vui lòng chọn ảnh dưới 5 MB."

    pixmap = QPixmap(clean_path)
    if pixmap.isNull():
        return False, "Tệp bị hỏng hoặc không phải là dữ liệu hình ảnh hợp lệ."

    return True, ""


def make_circular_pixmap(image_path: str, size: int = 64) -> Optional[QPixmap]:
    """Tạo ảnh QPixmap cắt tròn mượt mà để xem trước Avatar."""
    src = QPixmap(image_path)
    if src.isNull():
        return None
    scaled = src.scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)

    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)

    x_offset = (scaled.width() - size) // 2
    y_offset = (scaled.height() - size) // 2
    painter.drawPixmap(-x_offset, -y_offset, scaled)
    painter.end()
    return out


class ForwardDialog(QDialog):
    """
    Hộp thoại chọn Peer để chuyển tiếp (Forward) tin nhắn.
    Khớp trực tiếp với lời gọi trong app.py:
        dlg = ForwardDialog(msg.content, peers, self)
        if dlg.exec():
            selected = dlg.get_selected_peers()
    """

    def __init__(
        self,
        message_content: str,
        peers: Any,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("forwardDialog")
        self.setWindowTitle("↪ Chuyển Tiếp Tin Nhắn (Forward)")
        self.setMinimumSize(420, 380)
        self.resize(450, 420)

        self.message_content = str(message_content or "")
        self._normalized_peers = self._normalize_peers(peers)
        self._selected_peers: list[str] = []

        self._setup_ui()

    @staticmethod
    def _normalize_peers(peers: Any) -> list[dict[str, str]]:
        """
        Chuẩn hóa danh sách peers từ PeerListWidget (hỗ trợ dict, list[dict], list[str], object).
        """
        result: list[dict[str, str]] = []
        if not peers:
            return result

        if isinstance(peers, dict):
            for pid, info in peers.items():
                if isinstance(info, dict):
                    uname = str(info.get("username") or pid)
                    status = str(info.get("status", "online"))
                else:
                    uname = str(info or pid)
                    status = "online"
                result.append({"peer_id": str(pid), "username": uname, "status": status})
            return result

        if isinstance(peers, (list, tuple, set)):
            for item in peers:
                if isinstance(item, dict):
                    pid = str(item.get("peer_id") or item.get("id") or f"{item.get('ip', '')}:{item.get('port', '')}")
                    uname = str(item.get("username") or item.get("name") or pid)
                    status = str(item.get("status", "online"))
                    result.append({"peer_id": pid, "username": uname, "status": status})
                elif isinstance(item, str):
                    result.append({"peer_id": item, "username": item, "status": "online"})
                else:
                    pid = str(getattr(item, "peer_id", getattr(item, "id", str(item))))
                    uname = str(getattr(item, "username", getattr(item, "name", pid)))
                    status = str(getattr(item, "status", "online"))
                    result.append({"peer_id": pid, "username": uname, "status": status})
        return result

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 1. Khung xem trước nội dung tin nhắn sẽ chuyển tiếp
        preview_title = QLabel("Nội dung tin nhắn chuyển tiếp:")
        preview_title.setObjectName("dialogSectionLabel")
        layout.addWidget(preview_title)

        self.preview_box = QFrame()
        self.preview_box.setObjectName("forwardPreviewBox")
        p_layout = QVBoxLayout(self.preview_box)
        p_layout.setContentsMargins(10, 8, 10, 8)

        short_text = (
            self.message_content[:140] + "..."
            if len(self.message_content) > 140
            else self.message_content
        )
        self.preview_label = QLabel(f"“{short_text}”")
        self.preview_label.setWordWrap(True)
        self.preview_label.setObjectName("forwardPreviewText")
        p_layout.addWidget(self.preview_label)
        layout.addWidget(self.preview_box)

        # 2. Ô tìm kiếm nhanh Peer
        self.search_input = QLineEdit()
        self.search_input.setObjectName("forwardSearchInput")
        self.search_input.setPlaceholderText("🔍 Tìm kiếm Peer theo tên hoặc IP:Port...")
        self.search_input.textChanged.connect(self._filter_peer_list)
        layout.addWidget(self.search_input)

        # 3. Danh sách Peer kèm Checkbox
        list_header = QHBoxLayout()
        list_label = QLabel("Chọn Peer nhận tin nhắn:")
        list_label.setObjectName("dialogSectionLabel")
        list_header.addWidget(list_label, 1)

        self.select_all_btn = QPushButton("Chọn tất cả")
        self.select_all_btn.setObjectName("secondaryButton")
        self.select_all_btn.clicked.connect(self._toggle_select_all)
        list_header.addWidget(self.select_all_btn)
        layout.addLayout(list_header)

        self.peer_list_widget = QListWidget()
        self.peer_list_widget.setObjectName("forwardPeerList")
        self.peer_list_widget.itemChanged.connect(self._update_send_button_state)
        layout.addWidget(self.peer_list_widget, 1)

        self._populate_peers()

        # 4. Hàng nút bấm Dưới cùng
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.cancel_btn = QPushButton("Hủy")
        self.cancel_btn.setObjectName("secondaryButton")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        self.send_btn = QPushButton("↪ Chuyển tiếp (0)")
        self.send_btn.setObjectName("primaryButton")
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self._on_confirm_forward)
        btn_row.addWidget(self.send_btn)

        layout.addLayout(btn_row)

    def _populate_peers(self) -> None:
        self.peer_list_widget.clear()
        if not self._normalized_peers:
            empty_item = QListWidgetItem("⚠️ Hiện không có Peer nào đang Online")
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.peer_list_widget.addItem(empty_item)
            self.select_all_btn.setEnabled(False)
            return

        for p in self._normalized_peers:
            pid = p["peer_id"]
            uname = p["username"]
            display = f"🟢 {uname} ({pid})" if uname != pid else f"🟢 {pid}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, pid)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.peer_list_widget.addItem(item)

    def _filter_peer_list(self, keyword: str) -> None:
        kw = keyword.strip().lower()
        for i in range(self.peer_list_widget.count()):
            item = self.peer_list_widget.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole):
                item.setHidden(kw not in item.text().lower())

    def _toggle_select_all(self) -> None:
         selectable = [
             self.peer_list_widget.item(i)
             for i in range(self.peer_list_widget.count())
             if self.peer_list_widget.item(i).data(Qt.ItemDataRole.UserRole)
             and not self.peer_list_widget.item(i).isHidden()
         ]
         if not selectable:
             return
         all_checked = all(item.checkState() == Qt.CheckState.Checked for item in selectable)
         target_state = Qt.CheckState.Unchecked if all_checked else Qt.CheckState.Checked
         for item in selectable:
             item.setCheckState(target_state)

    def _update_send_button_state(self) -> None:
        selected = self._collect_checked()
        count = len(selected)
        self.send_btn.setText(f"↪ Chuyển tiếp ({count})")
        self.send_btn.setEnabled(count > 0)

    def _collect_checked(self) -> list[str]:
        checked: list[str] = []
        for i in range(self.peer_list_widget.count()):
            item = self.peer_list_widget.item(i)
            pid = item.data(Qt.ItemDataRole.UserRole) if item else None
            if pid and item.checkState() == Qt.CheckState.Checked:
                checked.append(str(pid))
        return checked

    def _on_confirm_forward(self) -> None:
        self._selected_peers = self._collect_checked()
        if not self._selected_peers:
            QMessageBox.warning(self, "Chưa chọn Peer", "Vui lòng chọn ít nhất 1 Peer để chuyển tiếp!")
            return
        self.accept()

    def get_selected_peers(self) -> list[str]:
        """Trả về danh sách các peer_id đã được người dùng tích chọn."""
        return list(self._selected_peers)


class ConfigDialog(QDialog):
    """
    Hộp thoại Cấu hình Hồ sơ (Tên hiển thị, Ảnh đại diện Avatar) & Kết nối Peer thủ công.
    Khớp trực tiếp với lời gọi trong app.py:
        dlg = ConfigDialog(self.username, self.listen_port, self)
        if dlg.exec():
            res = dlg.get_config()
    """

    def __init__(
        self,
        username: str = "User",
        listen_port: int = 5000,
        parent: Optional[QWidget] = None,
        avatar_path: str = "",
    ):
        super().__init__(parent)
        self.setObjectName("configDialog")
        self.setWindowTitle("⚙️ Hồ Sơ & Kết Nối Mạng P2P")
        self.setMinimumSize(460, 440)
        self.resize(480, 470)

        self._username = str(username or "User")
        self._listen_port = int(listen_port or 5000)
        self._avatar_path = avatar_path or str(getattr(parent, "avatar_path", "") or "")
        self._peer_ip = ""
        self._peer_port = 0

        self._setup_ui()
        self._refresh_avatar_preview()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # --- NHÓM 1: HỒ SƠ CÁ NHÂN & AVATAR ---
        profile_group = QGroupBox("👤 Hồ sơ cá nhân & Ảnh đại diện (Avatar)")
        profile_layout = QVBoxLayout(profile_group)
        profile_layout.setSpacing(10)

        avatar_row = QHBoxLayout()
        avatar_row.setSpacing(14)

        self.avatar_preview = QLabel("👤")
        self.avatar_preview.setObjectName("avatarPreviewLabel")
        self.avatar_preview.setFixedSize(68, 68)
        self.avatar_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_row.addWidget(self.avatar_preview)

        avatar_btn_col = QVBoxLayout()
        self.choose_avatar_btn = QPushButton("🖼️ Chọn ảnh đại diện...")
        self.choose_avatar_btn.setObjectName("secondaryButton")
        self.choose_avatar_btn.clicked.connect(self._on_choose_avatar)
        avatar_btn_col.addWidget(self.choose_avatar_btn)

        self.avatar_path_label = QLabel("Chưa chọn ảnh (Dùng chữ cái tên)")
        self.avatar_path_label.setObjectName("dialogHintLabel")
        avatar_btn_col.addWidget(self.avatar_path_label)
        avatar_row.addLayout(avatar_btn_col, 1)

        profile_layout.addLayout(avatar_row)

        form_profile = QFormLayout()
        form_profile.setSpacing(8)

        self.username_input = QLineEdit(self._username)
        self.username_input.setObjectName("configInput")
        self.username_input.setPlaceholderText("Nhập tên hiển thị của bạn...")
        form_profile.addRow("Tên hiển thị:", self.username_input)

        self.listen_port_spin = QSpinBox()
        self.listen_port_spin.setRange(1024, 65535)
        self.listen_port_spin.setValue(self._listen_port)
        self.listen_port_spin.setEnabled(False)
        self.listen_port_spin.setToolTip("Cổng lắng nghe TCP hiện tại của máy bạn")
        form_profile.addRow("Cổng lắng nghe (TCP):", self.listen_port_spin)

        profile_layout.addLayout(form_profile)
        layout.addWidget(profile_group)

        # --- NHÓM 2: KẾT NỐI THỦ CÔNG TỚI PEER ---
        conn_group = QGroupBox("🔌 Kết nối trực tiếp tới Peer mới (Tùy chọn)")
        conn_form = QFormLayout(conn_group)
        conn_form.setSpacing(8)

        self.peer_ip_input = QLineEdit()
        self.peer_ip_input.setObjectName("configInput")
        self.peer_ip_input.setPlaceholderText("Ví dụ: 127.0.0.1 hoặc 192.168.1.15 (Để trống nếu chỉ lưu hồ sơ)")
        conn_form.addRow("Địa chỉ IP Peer:", self.peer_ip_input)

        self.peer_port_spin = QSpinBox()
        self.peer_port_spin.setRange(0, 65535)
        self.peer_port_spin.setValue(0)
        self.peer_port_spin.setSpecialValueText("Không kết nối (0)")
        conn_form.addRow("Cổng TCP Peer:", self.peer_port_spin)

        layout.addWidget(conn_group)
        layout.addStretch(1)

        # --- HÀNG NÚT BẤM ---
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.cancel_btn = QPushButton("Hủy")
        self.cancel_btn.setObjectName("secondaryButton")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("💾 Lưu & Áp dụng")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._on_save_clicked)
        btn_row.addWidget(self.save_btn)

        layout.addLayout(btn_row)

    def _refresh_avatar_preview(self) -> None:
        if self._avatar_path and os.path.exists(self._avatar_path):
            circ = make_circular_pixmap(self._avatar_path, 64)
            if circ is not None:
                self.avatar_preview.setPixmap(circ)
                self.avatar_path_label.setText(os.path.basename(self._avatar_path))
                return
        initial = self._username.strip()[:1].upper() if self._username.strip() else "U"
        self.avatar_preview.setPixmap(QPixmap())
        self.avatar_preview.setText(initial)

    def _on_choose_avatar(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn ảnh đại diện (Avatar)",
            "",
            "Hình ảnh (*.png *.jpg *.jpeg *.bmp *.webp);;Tất cả các tệp (*.*)",
        )
        if not file_path:
            return

        is_valid, err_msg = validate_avatar_file(file_path)
        if not is_valid:
            QMessageBox.warning(self, "Ảnh Đại Diện Không Hợp Lệ", err_msg)
            return

        self._avatar_path = os.path.normpath(file_path)
        self._refresh_avatar_preview()

    @staticmethod
    def _is_valid_host(host: str) -> bool:
        if host.lower() == "localhost":
            return True
        try:
            ipaddress.ip_address(host)
            return True
        except ValueError:
            return False

    def _on_save_clicked(self) -> None:
        uname = self.username_input.text().strip()
        if not uname:
            QMessageBox.warning(self, "Thiếu Tên Hiển Thị", "Tên hiển thị không được để trống!")
            self.username_input.setFocus()
            return

        peer_ip = self.peer_ip_input.text().strip()
        peer_port = int(self.peer_port_spin.value())

        if peer_ip:
            if not self._is_valid_host(peer_ip):
                QMessageBox.warning(
                    self,
                    "Địa Chỉ IP Không Hợp Lệ",
                    f"Địa chỉ IP '{peer_ip}' không đúng định dạng IPv4 (ví dụ: 192.168.1.10 hoặc 127.0.0.1).",
                )
                self.peer_ip_input.setFocus()
                return
            if peer_port < 1024 or peer_port > 65535:
                QMessageBox.warning(
                    self,
                    "Cổng TCP Không Hợp Lệ",
                    "Khi nhập IP Peer, vui lòng chọn cổng TCP trong khoảng 1024 – 65535.",
                )
                self.peer_port_spin.setFocus()
                return

        self._username = uname
        self._listen_port = int(self.listen_port_spin.value())
        self._peer_ip = peer_ip
        self._peer_port = peer_port if peer_ip else 0
        self.accept()

    def get_config(self) -> dict[str, Any]:
        """Trả về dictionary cấu hình khớp 100% với _show_config_dialog() trong app.py."""
        return {
            "username": self._username,
            "listen_port": self._listen_port,
            "avatar_path": self._avatar_path,
            "peer_ip": self._peer_ip,
            "peer_port": self._peer_port,
        }