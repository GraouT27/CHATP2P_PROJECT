import os
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent


class DragDropWidget(QLabel):
    """Khu vực kéo & thả trực tiếp một hoặc nhiều file (dragEnterEvent, dropEvent)"""
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setText("📥 KÉO VÀ THẢ FILE VÀO ĐÂY ĐỂ GỬI\n(Hỗ trợ kéo thả một hoặc nhiều file cùng lúc)")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(100)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("dragging", True)
            self.style().unpolish(self)
            self.style().polish(self)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setProperty("dragging", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent):
        self.setProperty("dragging", False)
        self.style().unpolish(self)
        self.style().polish(self)

        file_paths = []
        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if os.path.isfile(local_path):
                file_paths.append(local_path)

        if file_paths:
            self.files_dropped.emit(file_paths)