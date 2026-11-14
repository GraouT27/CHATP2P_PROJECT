"""
Bảng điều khiển chạy thử & kiểm thử trực quan toàn bộ chức năng GUI của TV3:
1. Kéo thả file trực tiếp từ máy tính vào cửa sổ (Drag & Drop UI) + chặn file/thư mục lỗi.
2. Thanh tiến trình truyền file (QProgressBar) chạy mượt mà không gây treo GUI.
3. Kịch bản ngắt kết nối đột ngột (báo lỗi đỏ & hủy file .part).
4. Hộp thoại chọn Peer để Forward tin nhắn (ForwardDialog).
5. Hộp thoại chọn ảnh đại diện Avatar & Cấu hình IP/Port (ConfigDialog).
"""
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

# Thêm thư mục gốc và thư mục CODE vào sys.path để chạy được từ mọi vị trí
UI_DIR = Path(__file__).resolve().parent
CODE_DIR = UI_DIR.parents[1]
ROOT_DIR = CODE_DIR.parent
for p in (str(ROOT_DIR), str(CODE_DIR), str(UI_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QMessageBox
)

from dnd import DropZoneWidget
from file_row import FileRowWidget
from dialogs import ForwardDialog, ConfigDialog


@dataclass
class DemoTransferTask:
    task_id: str
    file_name: str
    file_size: int
    transferred: int = 0
    speed: float = 0.0
    status: str = "waiting"
    direction: str = "upload"
    error: str = ""


class TV3ShowcaseWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🖥️ Demo Giao Diện TV3 - Quản Lý Truyền File & Hộp Thoại P2P (Phạm Hữu Phước)")
        self.resize(760, 560)

        self.username = "Phuoc_TV3"
        self.listen_port = 5000
        self.avatar_path = ""
        self._tasks: dict[str, DemoTransferTask] = {}
        self._rows: dict[str, FileRowWidget] = {}

        # Nạp file styles.qss
        qss_file = UI_DIR / "styles.qss"
        if qss_file.exists():
            self.setStyleSheet(qss_file.read_text(encoding="utf-8"))

        self._setup_ui()

        # Timer mô phỏng tốc độ truyền file đa luồng (cập nhật mỗi 150ms)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick_progress)
        self.timer.start(150)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Thanh thông tin hồ sơ
        self.profile_banner = QLabel(
            f"👤 Người dùng: {self.username} | Cổng TCP: {self.listen_port} | Avatar: Mặc định"
        )
        self.profile_banner.setObjectName("dialogSectionLabel")
        layout.addWidget(self.profile_banner)

        # 1. Vùng Kéo & Thả File (Drag & Drop UI)
        self.drop_zone = DropZoneWidget(self)
        self.drop_zone.file_dropped.connect(self._add_real_file_task)
        layout.addWidget(self.drop_zone)

        # 2. Hàng nút bấm chức năng để test nhanh và chụp ảnh
        btn_row = QHBoxLayout()

        btn_sim_ok = QPushButton("📤 Giả lập truyền File (Chạy 0% -> 100%)")
        btn_sim_ok.setObjectName("primaryButton")
        btn_sim_ok.clicked.connect(self._simulate_normal_transfer)
        btn_row.addWidget(btn_sim_ok)

        btn_sim_disconnect = QPushButton("⚡ Giả lập đứt mạng đột ngột (Lỗi)")
        btn_sim_disconnect.setObjectName("secondaryButton")
        btn_sim_disconnect.clicked.connect(self._simulate_disconnect_error)
        btn_row.addWidget(btn_sim_disconnect)

        btn_forward = QPushButton("↪ Mở hộp thoại Forward")
        btn_forward.setObjectName("secondaryButton")
        btn_forward.clicked.connect(self._open_forward_demo)
        btn_row.addWidget(btn_forward)

        btn_config = QPushButton("🖼️ Chọn Avatar / Cấu hình IP")
        btn_config.setObjectName("secondaryButton")
        btn_config.clicked.connect(self._open_config_demo)
        btn_row.addWidget(btn_config)

        layout.addLayout(btn_row)

        # 3. Danh sách các thanh tiến trình QProgressBar
        list_title = QLabel("📋 Danh sách tiến trình truyền file (FileRowWidget):")
        list_title.setObjectName("dialogSectionLabel")
        layout.addWidget(list_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.list_layout.setSpacing(8)
        scroll.setWidget(self.list_container)
        layout.addWidget(scroll, 1)

        # Tạo sẵn 2 dòng mẫu để giao diện hiển thị ngay khi mở
        self._simulate_normal_transfer("Bao_Cao_LTM_Nhom.docx", 5 * 1024 * 1024, "upload")
        self._simulate_normal_transfer("Slide_Thuyet_Trinh_P2P.pptx", 8 * 1024 * 1024, "download")

    def _add_real_file_task(self, file_path: str):
        size = os.path.getsize(file_path)
        name = os.path.basename(file_path)
        self._simulate_normal_transfer(name, size, "upload")

    def _simulate_normal_transfer(
        self,
        file_name: str = "Du_Lieu_Kiem_Thu.zip",
        file_size: int = 10 * 1024 * 1024,
        direction: str = "upload",
    ):
        if isinstance(file_name, bool):
            file_name = f"Tai_Lieu_P2P_{len(self._tasks) + 1}.pdf"
            file_size = 6 * 1024 * 1024
        tid = str(uuid.uuid4())[:8]
        task = DemoTransferTask(
            task_id=tid,
            file_name=file_name,
            file_size=file_size,
            transferred=0,
            speed=2.4 * 1024 * 1024,
            status="transferring",
            direction=direction,
        )
        row = FileRowWidget(task, self.list_container)
        row.cancel_requested.connect(self._cancel_task)
        self._tasks[tid] = task
        self._rows[tid] = row
        self.list_layout.insertWidget(0, row)

    def _tick_progress(self):
        for tid, task in list(self._tasks.items()):
            if task.status != "transferring":
                continue
            step = max(int(task.file_size * 0.06), 4096)
            task.transferred = min(task.transferred + step, task.file_size)
            if task.transferred >= task.file_size:
                task.status = "completed"
                task.speed = 0.0
            self._rows[tid].update_task(task)

    def _cancel_task(self, task_id: str):
        task = self._tasks.get(task_id)
        if task:
            task.status = "cancelled"
            task.error = "Người dùng đã bấm Hủy"
            self._rows[task_id].update_task(task)

    def _simulate_disconnect_error(self):
        active_found = False
        for tid, task in self._tasks.items():
            if task.status == "transferring":
                task.status = "failed"
                task.error = "Peer ngắt kết nối đột ngột — Đã xóa file .part"
                self._rows[tid].update_task(task)
                active_found = True
        if not active_found:
            self._simulate_normal_transfer("Video_Demo_Loi_Mang.mp4", 15 * 1024 * 1024)
            newest_id = list(self._tasks.keys())[-1]
            t = self._tasks[newest_id]
            t.transferred = int(t.file_size * 0.42)
            t.status = "failed"
            t.error = "Peer ngắt kết nối đột ngột — Đã xóa file .part"
            self._rows[newest_id].update_task(t)

    def _open_forward_demo(self):
        sample_peers = [
            {"peer_id": "192.168.1.10:5000", "username": "TV1_TruongNhom", "status": "online"},
            {"peer_id": "192.168.1.11:5000", "username": "TV2_MainGUI", "status": "online"},
            {"peer_id": "192.168.1.14:5000", "username": "TV4_Protocol", "status": "online"},
            {"peer_id": "192.168.1.15:5000", "username": "TV5_SocketCore", "status": "online"},
        ]
        dlg = ForwardDialog(
            "Nhớ kiểm tra tiến trình truyền file 64KB và chụp ảnh gửi vào báo cáo nhé!",
            sample_peers,
            self,
        )
        if dlg.exec():
            selected = dlg.get_selected_peers()
            QMessageBox.information(
                self,
                "Chuyển Tiếp Thành Công",
                f"Đã chọn chuyển tiếp tin nhắn tới {len(selected)} Peer:\n• " + "\n• ".join(selected),
            )

    def _open_config_demo(self):
        dlg = ConfigDialog(self.username, self.listen_port, self, avatar_path=self.avatar_path)
        if dlg.exec():
            cfg = dlg.get_config()
            self.username = cfg["username"]
            self.avatar_path = cfg["avatar_path"]
            av_name = os.path.basename(self.avatar_path) if self.avatar_path else "Mặc định"
            peer_str = f"{cfg['peer_ip']}:{cfg['peer_port']}" if cfg["peer_ip"] else "Chưa nhập"
            self.profile_banner.setText(
                f"👤 Người dùng: {self.username} | Cổng TCP: {self.listen_port} | "
                f"Avatar: {av_name} | Kết nối tới: {peer_str}"
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = TV3ShowcaseWindow()
    win.show()
    sys.exit(app.exec())