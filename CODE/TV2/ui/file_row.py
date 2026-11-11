"""
Module hiển thị dòng tiến trình truyền file (FileRowWidget) trên GUI PyQt6 (TV3).
Tích hợp trực tiếp với MainWindow (app.py) thông qua:
- FileRowWidget(task, parent)
- Tín hiệu cancel_requested(str) gửi task_id khi người dùng bấm Hủy
- Phương thức update_task(task) cập nhật QProgressBar, tốc độ và trạng thái không gây đơ GUI.
"""
import os
import sys
from typing import Any, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel,
    QProgressBar, QPushButton, QWidget
)

# Đảm bảo import được format.py dù chạy từ thư mục gốc hay thư mục CODE
try:
    from shared.format import format_size, format_speed, format_progress_text
except ImportError:
    from CODE.shared.format import format_size, format_speed, format_progress_text


class FileRowWidget(QFrame):
    """
    Widget hiển thị 1 tác vụ truyền file (Gửi hoặc Nhận):
    - Biểu tượng chiều truyền (📤 Gửi / 📥 Nhận) + Tên file
    - Nhãn trạng thái: Chờ (Waiting), Đang tải (Transferring), Hoàn tất (Completed), Lỗi (Failed)
    - Thanh tiến trình QProgressBar (0% - 100%)
    - Thông tin chi tiết: Dung lượng đã truyền / Tổng dung lượng + Tốc độ (KB/s, MB/s)
    - Nút Hủy (✕) để dừng truyền file giữa chừng.
    """
    cancel_requested = pyqtSignal(str)  # Phát ra task_id khi bấm nút Hủy

    def __init__(self, task: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("fileRowWidget")
        self.task_id: str = str(getattr(task, "task_id", ""))

        self._setup_ui()
        self.update_task(task)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(6)

        # Hàng 1: Tên file + Trạng thái + Nút Hủy
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.file_name_label = QLabel("📄 Đang chuẩn bị tệp...")
        self.file_name_label.setObjectName("fileRowName")
        top_row.addWidget(self.file_name_label, 1)

        self.status_badge = QLabel("Chờ")
        self.status_badge.setObjectName("fileRowStatus")
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self.status_badge)

        self.cancel_btn = QPushButton("✕ Hủy")
        self.cancel_btn.setObjectName("fileRowCancelBtn")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setToolTip("Hủy phiên truyền tệp này")
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        top_row.addWidget(self.cancel_btn)

        main_layout.addLayout(top_row)

        # Hàng 2: Thanh tiến trình QProgressBar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("fileRowProgressBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(16)
        main_layout.addWidget(self.progress_bar)

        # Hàng 3: Chi tiết dung lượng & tốc độ (VD: 1.2 MB / 5.0 MB (24%) • 3.1 MB/s)
        bottom_row = QHBoxLayout()
        self.detail_label = QLabel("0 B / 0 B (0%)")
        self.detail_label.setObjectName("fileRowDetail")
        bottom_row.addWidget(self.detail_label, 1)

        main_layout.addLayout(bottom_row)

    def _on_cancel_clicked(self) -> None:
        if self.task_id:
            self.cancel_btn.setEnabled(False)
            self.status_badge.setText("Đang hủy...")
            self.cancel_requested.emit(self.task_id)

    @staticmethod
    def _extract_value(val: Any) -> str:
        """Lấy chuỗi từ Enum (ví dụ TransferStatus.COMPLETED.value) hoặc str thường."""
        if hasattr(val, "value"):
            return str(val.value).lower()
        return str(val or "").lower()

    def _apply_status_style(self, state_key: str) -> None:
        """Cập nhật thuộc tính động để QSS đổi màu theo trạng thái (waiting/transferring/completed/failed)."""
        self.setProperty("transferStatus", state_key)
        self.status_badge.setProperty("transferStatus", state_key)
        self.progress_bar.setProperty("transferStatus", state_key)
        for widget in (self, self.status_badge, self.progress_bar):
            style = widget.style()
            if style is not None:
                style.unpolish(widget)
                style.polish(widget)

    def update_task(self, task: Any) -> None:
        """
        Cập nhật giao diện từ đối tượng TransferTask mà không làm treo GUI.
        Tự động tương thích với mọi tên thuộc tính của TransferTask (TV5).
        """
        if task is None:
            return

        self.task_id = str(getattr(task, "task_id", self.task_id))

        # 1. Xác định tên file và chiều truyền (upload / download)
        file_name = getattr(task, "file_name", None)
        if not file_name:
            file_path = getattr(task, "file_path", "") or getattr(task, "path", "")
            file_name = os.path.basename(file_path) if file_path else "unknown_file"

        direction_raw = self._extract_value(getattr(task, "direction", "upload"))
        is_upload = direction_raw in ("upload", "send", "out", "up")
        icon = "📤 Gửi:" if is_upload else "📥 Nhận:"
        self.file_name_label.setText(f"{icon} {file_name}")

        # 2. Lấy kích thước tổng, số byte đã truyền và tốc độ
        total_size = int(
            getattr(task, "file_size", None)
            or getattr(task, "total_size", None)
            or getattr(task, "size", 0)
            or 0
        )
        transferred = int(
            getattr(task, "bytes_transferred", None)
            or getattr(task, "transferred", None)
            or getattr(task, "sent", 0)
            or 0
        )
        speed = float(getattr(task, "speed", 0.0) or 0.0)

        # Tính phần trăm
        if hasattr(task, "progress") and isinstance(getattr(task, "progress"), (int, float)):
            raw_prog = float(getattr(task, "progress"))
            percent = int(raw_prog * 100) if 0 < raw_prog <= 1.0 and total_size > 100 else int(raw_prog)
        elif total_size > 0:
            percent = int((transferred / total_size) * 100)
        else:
            percent = 0
        percent = max(0, min(100, percent))

        # 3. Phân tích trạng thái (Waiting / Transferring / Completed / Failed / Cancelled)
        status_raw = self._extract_value(getattr(task, "status", "waiting"))
        error_msg = str(getattr(task, "error", "") or getattr(task, "error_message", "") or "")

        if status_raw in ("completed", "done", "success", "finished"):
            percent = 100
            transferred = total_size if total_size > 0 else transferred
            self.progress_bar.setValue(100)
            self.status_badge.setText("✅ Hoàn tất")
            self.detail_label.setText(f"{format_size(total_size)} (100%) • Thành công")
            self.cancel_btn.setVisible(False)
            self._apply_status_style("completed")

        elif status_raw in ("failed", "error", "cancelled", "canceled", "aborted"):
            self.progress_bar.setValue(percent)
            is_cancelled = status_raw in ("cancelled", "canceled", "aborted")
            badge_text = "🚫 Đã hủy" if is_cancelled else "❌ Thất bại"
            self.status_badge.setText(badge_text)
            reason = error_msg if error_msg else ("Người dùng đã hủy" if is_cancelled else "Mất kết nối — Đã xóa file .part")
            self.detail_label.setText(f"{format_size(transferred)} / {format_size(total_size)} • {reason}")
            self.cancel_btn.setVisible(False)
            self._apply_status_style("failed")

        elif status_raw in ("transferring", "running", "in_progress", "sending", "receiving", "active"):
            self.progress_bar.setValue(percent)
            self.status_badge.setText("⏳ Đang tải")
            self.detail_label.setText(format_progress_text(transferred, total_size, speed))
            self.cancel_btn.setVisible(True)
            self.cancel_btn.setEnabled(True)
            self._apply_status_style("transferring")

        else:
            # Mặc định: Waiting / Pending / Queued
            self.progress_bar.setValue(percent)
            self.status_badge.setText("🕒 Đang chờ")
            self.detail_label.setText(f"Đang xếp hàng đợi • {format_size(total_size)}")
            self.cancel_btn.setVisible(True)
            self.cancel_btn.setEnabled(True)
            self._apply_status_style("waiting")