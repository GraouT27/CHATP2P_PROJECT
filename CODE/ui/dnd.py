"""
Drag and Drop (DnD) Module - Xử lý sự kiện kéo thả file vào khung chat (TV3).
"""

import os
from PyQt6.QtCore import QObject, QEvent, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import QWidget


class DragDropFilter(QObject):
    """
    Event filter gắn vào QWidget để bắt sự kiện kéo thả file
    mà không cần ghi đè toàn bộ class widget đó.
    """
    file_dropped = pyqtSignal(str)       # (file_path)
    multiple_dropped = pyqtSignal(list)  # (list_of_paths)

    def __init__(self, target_widget: QWidget, parent=None):
        super().__init__(parent or target_widget)
        self.target = target_widget
        self.target.setAcceptDrops(True)
        self.target.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched == self.target:
            if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                    return True

            elif event.type() == QEvent.Type.Drop:
                urls = event.mimeData().urls()
                valid_files = []
                for url in urls:
                    path = url.toLocalFile()
                    if os.path.isfile(path):
                        valid_files.append(path)

                if valid_files:
                    event.acceptProposedAction()
                    self.multiple_dropped.emit(valid_files)
                    self.file_dropped.emit(valid_files[0])
                    return True

        return super().eventFilter(watched, event)
