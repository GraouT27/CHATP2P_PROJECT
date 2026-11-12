"""
File Row Module - Widget hiển thị tiến độ 1 dòng truyền file (TV3 & TV5).
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton
from p2p_node.transfer_task import TransferTask, TransferDirection, TransferStatus


class FileRowWidget(QFrame):
    """Widget thanh tiến trình cho từng file đang gửi hoặc nhận."""
    cancel_requested = pyqtSignal(str)  # (task_id)

    def __init__(self, task: TransferTask, parent=None):
        super().__init__(parent)
        self.task_id = task.task_id
        self.setObjectName("fileRowWidget")
        self._setup_ui(task)
        self.update_task(task)

    def _setup_ui(self, task: TransferTask):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Hàng 1: Icon + Tên file + Nút Hủy
        top_row = QHBoxLayout()
        icon = "📤 Gửi:" if task.direction == TransferDirection.UPLOAD else "📥 Nhận:"
        self.title_label = QLabel(f"{icon} {task.file_name}")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        top_row.addWidget(self.title_label, 1)

        self.cancel_btn = QPushButton("✕")
        self.cancel_btn.setObjectName("fileCancelBtn")
        self.cancel_btn.setToolTip("Hủy truyền file")
        self.cancel_btn.clicked.connect(lambda: self.cancel_requested.emit(self.task_id))
        top_row.addWidget(self.cancel_btn)
        layout.addLayout(top_row)

        # Hàng 2: QProgressBar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Hàng 3: Chi tiết dung lượng + Tốc độ + Trạng thái
        bottom_row = QHBoxLayout()
        self.size_label = QLabel("")
        self.size_label.setStyleSheet("color: #b0b0c8; font-size: 11px;")
        bottom_row.addWidget(self.size_label)

        bottom_row.addStretch()

        self.speed_label = QLabel("")
        self.speed_label.setStyleSheet("color: #e8f0fe; font-size: 11px;")
        bottom_row.addWidget(self.speed_label)
        layout.addLayout(bottom_row)

    def update_task(self, task: TransferTask):
        """Cập nhật dữ liệu hiển thị từ TransferTask."""
        self.progress_bar.setValue(int(task.progress_percent))
        self.size_label.setText(f"{task.size_str} ({task.progress_percent:.1f}%)")
        self.speed_label.setText(task.speed_str)

        if task.status == TransferStatus.COMPLETED:
            self.progress_bar.setValue(100)
            self.size_label.setText(f"✅ Hoàn tất ({task.size_str})")
            self.size_label.setStyleSheet("color: #34a853; font-weight: bold; font-size: 11px;")
            self.speed_label.setText("")
            self.cancel_btn.setVisible(False)

        elif task.status in (TransferStatus.ERROR, TransferStatus.CANCELLED):
            err_text = task.error_msg or "Thất bại"
            self.size_label.setText(f"❌ {err_text}")
            self.size_label.setStyleSheet("color: #ea4335; font-weight: bold; font-size: 11px;")
            self.speed_label.setText("")
            self.cancel_btn.setVisible(False)
