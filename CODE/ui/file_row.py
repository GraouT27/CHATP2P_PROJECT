"""
File Row Module - Widget hiển thị tiến độ 1 dòng truyền file (TV3 & TV5).
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton
from p2p_node.transfer_task import TransferTask, TransferDirection, TransferStatus


class FileRowWidget(QFrame):
    """Widget thanh tiến trình cho từng file đang gửi hoặc nhận."""
    cancel_requested = pyqtSignal(str)  # (task_id)
    delete_requested = pyqtSignal(str, str, str)  # (task_id, file_name, direction_value)

    def __init__(self, task: TransferTask, parent=None):
        super().__init__(parent)
        self.task_id = task.task_id
        self.file_name = task.file_name
        self.direction_val = task.direction.value
        self.setObjectName("fileRowWidget")
        self._setup_ui(task)
        self.update_task(task)

    def _setup_ui(self, task: TransferTask):
        self.final_path = getattr(task, "final_path", "")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Hàng 1: Icon + Tên file + Nút Mở/Hủy/Thu Hồi
        top_row = QHBoxLayout()
        icon = "📤 Gửi:" if task.direction == TransferDirection.UPLOAD else "📥 Nhận:"
        self.title_label = QLabel(f"{icon} {task.file_name}")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        top_row.addWidget(self.title_label, 1)

        self.open_btn = QPushButton("📂 Mở File")
        self.open_btn.setObjectName("fileOpenBtn")
        self.open_btn.setToolTip("Mở trực tiếp file vừa truyền xong")
        self.open_btn.setVisible(False)
        self.open_btn.clicked.connect(self._open_file)
        top_row.addWidget(self.open_btn)

        self.open_folder_btn = QPushButton("📁 Thư Mục")
        self.open_folder_btn.setObjectName("fileOpenBtn")
        self.open_folder_btn.setToolTip("Mở thư mục chứa file")
        self.open_folder_btn.setVisible(False)
        self.open_folder_btn.clicked.connect(self._open_folder)
        top_row.addWidget(self.open_folder_btn)

        self.delete_btn = QPushButton("🗑️ Thu Hồi" if task.direction == TransferDirection.UPLOAD else "🗑️ Xóa File")
        self.delete_btn.setObjectName("fileDeleteBtn")
        self.delete_btn.setToolTip("Thu hồi file đã gửi sang đối phương" if task.direction == TransferDirection.UPLOAD else "Xóa file này khỏi máy")
        self.delete_btn.setVisible(False)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.task_id, self.file_name, self.direction_val))
        top_row.addWidget(self.delete_btn)

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
        if not task:
            return
        self.progress_bar.setValue(int(task.progress_percent))
        self.size_label.setText(f"{task.size_str} ({task.progress_percent:.1f}%)")
        self.speed_label.setText(task.speed_str)

        if task.status == TransferStatus.COMPLETED:
            self.progress_bar.setValue(100)
            self.final_path = getattr(task, "final_path", "") or self.final_path
            self.file_name = task.file_name
            self.direction_val = task.direction.value
            self.size_label.setText(f"✅ Hoàn tất ({task.size_str})")
            self.size_label.setStyleSheet("color: #34a853; font-weight: bold; font-size: 11px;")
            self.speed_label.setText("")
            self.cancel_btn.setVisible(False)
            self.open_btn.setVisible(True)
            self.open_folder_btn.setVisible(True)
            self.delete_btn.setText("🗑️ Thu Hồi" if task.direction == TransferDirection.UPLOAD else "🗑️ Xóa File")
            self.delete_btn.setVisible(True)

        elif task.status in (TransferStatus.ERROR, TransferStatus.CANCELLED):
            err_text = task.error_msg or "Thất bại"
            self.size_label.setText(f"❌ {err_text}")
            self.size_label.setStyleSheet("color: #ea4335; font-weight: bold; font-size: 11px;")
            self.speed_label.setText("")
            self.cancel_btn.setVisible(False)
            self.open_btn.setVisible(False)
            self.open_folder_btn.setVisible(False)
            self.delete_btn.setVisible(False)

    def mark_deleted(self, text: str = "Đã thu hồi / xóa"):
        """Đánh dấu tác vụ đã bị thu hồi hoặc xóa."""
        self.size_label.setText(f"🗑️ {text}")
        self.size_label.setStyleSheet("color: #ea4335; font-weight: bold; font-size: 11px;")
        self.open_btn.setVisible(False)
        self.open_folder_btn.setVisible(False)
        self.delete_btn.setVisible(False)

    def _open_file(self):
        """Mở trực tiếp file bằng ứng dụng mặc định của hệ thống."""
        import os
        path = getattr(self, "final_path", "")
        if path and os.path.exists(path):
            try:
                os.startfile(path)
                return
            except Exception:
                pass
        self._open_folder()

    def _open_folder(self):
        """Mở thư mục chứa file trong File Explorer."""
        import os
        path = getattr(self, "final_path", "")
        folder = os.path.dirname(path) if path else ""
        if not folder or not os.path.exists(folder):
            try:
                from config import config
                folder = getattr(config, "download_dir", "")
            except Exception:
                pass
        if folder and os.path.exists(folder):
            try:
                os.startfile(folder)
            except Exception:
                pass
