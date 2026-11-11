"""
Module xử lý sự kiện Kéo & Thả file (Drag & Drop) vào khu vực trò chuyện (TV3).
Cung cấp:
- validate_file_path(): Kiểm tra tính hợp lệ của file (chặn thư mục, file rỗng 0 byte, file lỗi).
- DragDropFilter: Bộ lọc sự kiện gắn trực tiếp lên QListView/QWidget trong MainWindow (app.py).
- DropZoneWidget: Khung vùng thả file độc lập sử dụng trực tiếp dragEnterEvent và dropEvent.
"""
import os
from typing import Optional
from PyQt6.QtCore import QObject, QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent
from PyQt6.QtWidgets import QWidget, QFrame, QVBoxLayout, QLabel, QMessageBox


def validate_file_path(file_path: str) -> tuple[bool, str]:
    """
    Kiểm tra đường dẫn file trước khi đưa vào hàng đợi truyền P2P.
    Trả về: (Hợp_lệ: bool, Thông_báo_lỗi: str)
    """
    if not file_path or not str(file_path).strip():
        return False, "Đường dẫn tệp trống hoặc không hợp lệ."

    clean_path = os.path.normpath(str(file_path).strip())

    if not os.path.exists(clean_path):
        return False, f"Tệp không tồn tại:\n{clean_path}"

    if os.path.isdir(clean_path):
        return False, (
            f"Không hỗ trợ kéo thả thư mục:\n'{os.path.basename(clean_path)}'\n"
            "Vui lòng nén thành file .zip hoặc chọn từng tệp riêng lẻ."
        )

    if not os.path.isfile(clean_path):
        return False, f"Đường dẫn không phải là tệp thông thường:\n{clean_path}"

    try:
        file_size = os.path.getsize(clean_path)
    except OSError as exc:
        return False, f"Không thể đọc thông tin tệp:\n{exc}"

    if file_size <= 0:
        return False, (
            f"Tệp rỗng (0 Byte): '{os.path.basename(clean_path)}'\n"
            "Không thể truyền tệp không có dữ liệu."
        )

    if not os.access(clean_path, os.R_OK):
        return False, f"Không có quyền đọc tệp:\n{clean_path}"

    return True, ""


class DragDropFilter(QObject):
    """
    Bộ lọc sự kiện Kéo & Thả (Drag & Drop) gắn vào khung chat (message_view) trong app.py.
    Phát tín hiệu `file_dropped(str)` mỗi khi có một file hợp lệ được thả vào.
    """
    file_dropped = pyqtSignal(str)
    invalid_dropped = pyqtSignal(str, str)  # (file_path, error_message)

    def __init__(
        self,
        target_widget: QWidget,
        parent: Optional[QObject] = None,
        show_warning_dialog: bool = True,
    ):
        super().__init__(parent)
        self.target_widget = target_widget
        self.show_warning_dialog = show_warning_dialog

        # Bật chế độ nhận kéo thả trên widget đích
        if self.target_widget is not None:
            self.target_widget.setAcceptDrops(True)
            self.target_widget.installEventFilter(self)

            # Nếu widget đích là QListView / QScrollArea thì sự kiện chuột rơi vào viewport()
            if hasattr(self.target_widget, "viewport") and callable(self.target_widget.viewport):
                vp = self.target_widget.viewport()
                if vp is not None:
                    vp.setAcceptDrops(True)
                    vp.installEventFilter(self)

    def _set_drag_highlight(self, active: bool) -> None:
        """Đổi trạng thái viền khung chat khi đang rê file vào."""
        if self.target_widget is None:
            return
        self.target_widget.setProperty("dragActive", active)
        style = self.target_widget.style()
        if style is not None:
            style.unpolish(self.target_widget)
            style.polish(self.target_widget)
        self.target_widget.update()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        etype = event.type()

        if etype == QEvent.Type.DragEnter:
            return self.dragEnterEvent(event)  # type: ignore[arg-type]

        if etype == QEvent.Type.DragMove:
            return self.dragMoveEvent(event)  # type: ignore[arg-type]

        if etype == QEvent.Type.DragLeave:
            return self.dragLeaveEvent(event)  # type: ignore[arg-type]

        if etype == QEvent.Type.Drop:
            return self.dropEvent(event)  # type: ignore[arg-type]

        return super().eventFilter(watched, event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> bool:
        """Kiểm tra dữ liệu kéo vào có chứa đường dẫn file (URLs) hay không."""
        mime = event.mimeData()
        if mime is not None and mime.hasUrls():
            event.acceptProposedAction()
            self._set_drag_highlight(True)
            return True
        event.ignore()
        return False

    def dragMoveEvent(self, event: QDragMoveEvent) -> bool:
        """Duy trì trạng thái cho phép thả khi di chuyển chuột trong vùng chat."""
        mime = event.mimeData()
        if mime is not None and mime.hasUrls():
            event.acceptProposedAction()
            return True
        event.ignore()
        return False

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> bool:
        """Tắt hiệu ứng viền sáng khi kéo chuột ra ngoài vùng chat."""
        self._set_drag_highlight(False)
        event.accept()
        return True

    def dropEvent(self, event: QDropEvent) -> bool:
        """Xử lý danh sách các file được thả xuống."""
        self._set_drag_highlight(False)
        mime = event.mimeData()
        if mime is None or not mime.hasUrls():
            event.ignore()
            return False

        event.acceptProposedAction()

        for url in mime.urls():
            local_path = url.toLocalFile()
            if not local_path:
                continue

            is_valid, err_msg = validate_file_path(local_path)
            if is_valid:
                self.file_dropped.emit(os.path.normpath(local_path))
            else:
                self.invalid_dropped.emit(local_path, err_msg)
                if self.show_warning_dialog:
                    parent_widget = (
                        self.parent() if isinstance(self.parent(), QWidget) else self.target_widget
                    )
                    QMessageBox.warning(
                        parent_widget,
                        "Tệp Không Hợp Lệ",
                        err_msg,
                    )
        return True


class DropZoneWidget(QFrame):
    """
    Widget vùng kéo thả file trực quan (dùng cho màn hình test độc lập hoặc bảng truyền file).
    Ghi đè trực tiếp dragEnterEvent, dragLeaveEvent và dropEvent.
    """
    file_dropped = pyqtSignal(str)
    invalid_dropped = pyqtSignal(str, str)

    def __init__(self, parent: Optional[QWidget] = None, show_warning_dialog: bool = True):
        super().__init__(parent)
        self.setObjectName("dropZonePanel")
        self.setAcceptDrops(True)
        self.show_warning_dialog = show_warning_dialog
        self.setMinimumHeight(90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        self.label = QLabel("📂 Kéo và thả tệp vào đây để gửi qua P2P")
        self.label.setObjectName("dropZoneLabel")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

    def _update_highlight(self, active: bool) -> None:
        self.setProperty("dragActive", active)
        if active:
            self.label.setText("📥 Thả chuột ra để bắt đầu gửi tệp...")
        else:
            self.label.setText("📂 Kéo và thả tệp vào đây để gửi qua P2P")
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData() and event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._update_highlight(True)
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData() and event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._update_highlight(False)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        self._update_highlight(False)
        if not event.mimeData() or not event.mimeData().hasUrls():
            event.ignore()
            return

        event.acceptProposedAction()
        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if not local_path:
                continue
            is_valid, err_msg = validate_file_path(local_path)
            if is_valid:
                self.file_dropped.emit(os.path.normpath(local_path))
            else:
                self.invalid_dropped.emit(local_path, err_msg)
                if self.show_warning_dialog:
                    QMessageBox.warning(self, "Tệp Không Hợp Lệ", err_msg)