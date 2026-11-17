"""
Chat Widgets Module - Các thành phần giao diện tin nhắn, Avatar và Emoji (TV2).

Lưu ý quan trọng tương thích PyQt6:
Trong các hàm vẽ QPainter (như drawEllipse, drawRoundedRect, drawText),
luôn dùng số nguyên int hoặc bao bọc số thực trong QRectF để tránh lỗi TypeError.
"""

import os
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QSize, QAbstractListModel, QModelIndex
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QPainterPath, QBrush, QPen, QFontMetrics
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QScrollArea, QGridLayout, QFrame, QStyledItemDelegate, QStyleOptionViewItem
)


# ========================== AVATAR WIDGET ==========================

class AvatarWidget(QLabel):
    """
    Hiển thị Avatar hình tròn sử dụng QPixmap.
    Hỗ trợ nạp file ảnh cá nhân hoặc vẽ chữ cái đầu trên nền màu.
    """

    def __init__(self, name: str = "", size: int = 40,
                 color: str = "#1a73e8", image_path: str = "", parent=None):
        super().__init__(parent)
        self._name = str(name or "")
        # Chặn size < 16 để tránh rect_f có bán kính âm/0 làm lỗi QPainterPath khi vẽ hình tròn.
        self._size = max(int(size or 40), 16)
        # Kiểm tra QColor.isValid() trước khi lưu để tránh vẽ nền đen nếu chuỗi màu sai cú pháp.
        self._color = color if QColor(str(color or "")).isValid() else "#1a73e8"
        self._image_path = str(image_path or "")
        self.setFixedSize(self._size, self._size)
        self._render_avatar()

    def _render_avatar(self):
        # Tạo QPixmap trong suốt (alpha = 0) để phần góc vuông bên ngoài hình tròn không bị đen nền.
        pixmap = QPixmap(self._size, self._size)
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Tạo đường bao tròn chuẩn kiểu float trong QRectF
        # (PyQt6 yêu cầu int hoặc QRectF cho setClipPath/drawText, không nhận trực tiếp 4 số float rời).
        rect_f = QRectF(1.0, 1.0, float(self._size - 2), float(self._size - 2))
        path = QPainterPath()
        path.addEllipse(rect_f)
        # setClipPath cắt bỏ mọi pixel vẽ ra ngoài hình tròn, tạo hiệu ứng Avatar bo tròn mượt.
        painter.setClipPath(path)

        # 1. Nếu có file ảnh avatar hợp lệ
        if self._image_path and os.path.exists(self._image_path):
            img = QPixmap(self._image_path)
            if not img.isNull():
                scaled = img.scaled(
                    self._size, self._size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                x = (scaled.width() - self._size) // 2
                y = (scaled.height() - self._size) // 2
                painter.drawPixmap(0, 0, scaled, x, y, self._size, self._size)
                painter.end()
                self.setPixmap(pixmap)
                return

        # 2. Vẽ hình tròn nền và chữ cái đầu
        painter.setBrush(QBrush(QColor(self._color)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)

        painter.setPen(QColor(255, 255, 255))
        font_size = max(self._size // 3, 10)
        font = QFont("Segoe UI", font_size, QFont.Weight.Bold)
        painter.setFont(font)
        initial = self._name[0].upper() if self._name else "?"
        painter.drawText(rect_f, Qt.AlignmentFlag.AlignCenter, initial)

        painter.end()
        self.setPixmap(pixmap)

    def set_name(self, name: str):
        self._name = str(name or "")
        self._render_avatar()

    def set_color(self, color: str):
        self._color = color
        self._render_avatar()

    def set_image_path(self, path: str):
        self._image_path = str(path or "")
        self._render_avatar()


# ========================== REPLY PREVIEW ==========================

class ReplyPreview(QFrame):
    """Khung xem trước tin nhắn đang được Reply nằm trên ô soạn thảo."""
    cancel_reply = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("replyPreview")
        self.setFixedHeight(50)
        self.setVisible(False)
        self._reply_data = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 8, 4)
        layout.setSpacing(8)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(0)

        self.author_label = QLabel()
        self.author_label.setStyleSheet("color: #1a73e8; font-size: 11px; font-weight: bold;")
        info_layout.addWidget(self.author_label)

        self.content_label = QLabel()
        self.content_label.setStyleSheet("color: #b0b0c8; font-size: 12px;")
        info_layout.addWidget(self.content_label)
        layout.addLayout(info_layout, 1)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("replyPreviewClose")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._on_cancel)
        layout.addWidget(close_btn)

    def set_reply(self, sender: str, content: str, msg_id: str = ""):
        self.author_label.setText(f"↩ Đang trả lời {sender}:")
        display_content = content if len(content) <= 60 else content[:60] + "..."
        self.content_label.setText(display_content)
        self._reply_data = {"msg_id": msg_id, "sender": sender, "content": content}
        self.setVisible(True)

    def get_reply_data(self) -> dict | None:
        return self._reply_data

    def _on_cancel(self):
        self._reply_data = None
        self.setVisible(False)
        self.cancel_reply.emit()

    def clear(self):
        self._reply_data = None
        self.setVisible(False)


# ========================== EMOJI PICKER ==========================

class EmojiPicker(QWidget):
    """Widget bảng chọn biểu tượng cảm xúc dạng lưới Popup."""
    emoji_selected = pyqtSignal(str)

    EMOJI_CATEGORIES = {
        "😀 Mặt cười": [
            "😀", "😃", "😄", "😁", "😆", "😅", "🤣", "😂",
            "🙂", "😉", "😊", "😇", "🥰", "😍", "🤩", "😘",
            "😗", "😚", "😙", "🥲", "😋", "😛", "😜", "🤪",
            "😝", "🤑", "🤗", "🤭", "🤫", "🤔", "🫡", "🤐",
        ],
        "😢 Cảm xúc": [
            "😮", "🤯", "😱", "🥵", "🥶", "😰", "😨", "😧",
            "😦", "😯", "😲", "🥺", "😢", "😥", "😭", "😤",
            "😠", "😡", "🤬", "😈", "👿", "💀", "☠️", "💩",
            "🤡", "👻", "👽", "🤖", "🙈", "🙉", "🙊", "💤",
        ],
        "👍 Cử chỉ": [
            "👋", "🤚", "🖐️", "✋", "🖖", "👌", "🤌", "🤏",
            "✌️", "🤞", "🫰", "🤟", "🤘", "🤙", "👈", "👉",
            "👆", "🖕", "👇", "☝️", "🫵", "👍", "👎", "✊",
            "👊", "🤛", "🤜", "👏", "🙌", "🫶", "🙏", "🤝",
        ],
        "❤️ Biểu tượng": [
            "❤️", "🧡", "💛", "💚", "💙", "💜", "🖤", "🤍",
            "💔", "❤️‍🔥", "💕", "💞", "💓", "💗", "💖", "💘",
            "🔥", "💯", "🎉", "🎊", "🏆", "🥇", "⭐", "✨",
            "🌟", "💡", "🎯", "🚀", "⚡", "🎁", "🎈", "🔒",
        ],
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("emojiPicker")
        self.setWindowFlags(Qt.WindowType.Popup)
        self.setFixedSize(320, 280)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.category_combo = QComboBox()
        for cat in self.EMOJI_CATEGORIES:
            self.category_combo.addItem(cat)
        self.category_combo.currentIndexChanged.connect(self._on_category_changed)
        layout.addWidget(self.category_combo)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(2)
        self.grid.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.container)
        layout.addWidget(scroll)

        self._load_category(list(self.EMOJI_CATEGORIES.values())[0])

    def _on_category_changed(self, idx: int):
        cats = list(self.EMOJI_CATEGORIES.values())
        if 0 <= idx < len(cats):
            self._load_category(cats[idx])

    def _load_category(self, emojis: list[str]):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = 8
        for i, emo in enumerate(emojis):
            btn = QPushButton(emo)
            btn.setFixedSize(34, 34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, e=emo: self._select_emoji(e))
            self.grid.addWidget(btn, i // cols, i % cols)

    def _select_emoji(self, emoji: str):
        self.emoji_selected.emit(emoji)
        self.hide()


# ========================== MESSAGE MODEL & DELEGATE ==========================

class MessageData:
    """
    Đối tượng dữ liệu 1 tin nhắn được làm sạch trước khi đưa vào QListView.
    Cách dùng: luôn bọc dữ liệu nhận từ mạng qua MessageData thay vì truyền dict thô vào UI.
    """
    # Giới hạn độ dài tin nhắn hiển thị để QFontMetrics.boundingRect không bị đơ CPU (GUI DoS)
    # nếu Peer gửi chuỗi rác vài trăm KB - hàng MB.
    MAX_CONTENT_LEN = 10000

    def __init__(self, msg_id: str, sender: str, content: str, timestamp: float,
                 is_sent: bool, reply_to: dict = None, forward_from: dict = None,
                 is_system: bool = False, avatar_path: str = ""):
        self.msg_id = str(msg_id or "")
        self.sender = str(sender if sender is not None else "")[:64]
        raw_content = "" if content is None else str(content)
        if len(raw_content) > self.MAX_CONTENT_LEN:
            raw_content = raw_content[:self.MAX_CONTENT_LEN] + "\n... [Đã rút gọn nội dung quá dài]"
        self.content = raw_content
        try:
            self.timestamp = float(timestamp) if timestamp is not None else 0.0
        except (TypeError, ValueError):
            self.timestamp = 0.0
        self.is_sent = bool(is_sent)
        # Chỉ nhận dict hợp lệ cho reply_to và forward_from (chống Type Confusion gây crash khi paint).
        self.reply_to = reply_to if isinstance(reply_to, dict) else None
        self.forward_from = forward_from if isinstance(forward_from, dict) else None
        self.is_system = bool(is_system)
        self.avatar_path = str(avatar_path or "")

    @property
    def time_str(self) -> str:
        import time
        import math
        try:
            # Trên Windows, time.localtime() sẽ văng OSError/ValueError nếu timestamp âm, NaN hoặc > năm 2100 (4102444800).
            if not math.isfinite(self.timestamp) or self.timestamp < 0 or self.timestamp > 4102444800:
                return "--:--"
            t = time.localtime(self.timestamp)
            return f"{t.tm_hour:02d}:{t.tm_min:02d}"
        except (TypeError, ValueError, OSError, OverflowError):
            return "--:--"


class MessageListModel(QAbstractListModel):
    """
    Model danh sách tin nhắn phục vụ QListView Virtualization (Tối ưu hóa Chặng 7).
    Cách dùng: thay vì tạo hàng nghìn QWidget nặng nề, QListView chỉ gọi MessageDelegate.paint()
    cho những tin nhắn đang nằm trong khung nhìn màn hình -> cuộn mượt ngay cả khi có nhiều tin.
    """
    # Giới hạn tối đa số tin nhắn giữ trong RAM cho mỗi cuộc hội thoại để chống tràn bộ nhớ (Memory Exhaustion).
    MAX_MESSAGES = 5000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._messages: list[MessageData] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._messages)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._messages):
            return None
        return self._messages[index.row()]

    def add_message(self, msg: MessageData):
        # Xóa bớt tin nhắn cũ nhất (FIFO) nếu chạm ngưỡng MAX_MESSAGES và báo beginRemoveRows cho QListView đồng bộ.
        if len(self._messages) >= self.MAX_MESSAGES:
            overflow = len(self._messages) - self.MAX_MESSAGES + 1
            self.beginRemoveRows(QModelIndex(), 0, overflow - 1)
            del self._messages[:overflow]
            self.endRemoveRows()
        row = len(self._messages)
        # Bắt buộc gọi cặp beginInsertRows/endInsertRows để QListView cập nhật vùng cuộn mà không vẽ lại toàn bộ list.
        self.beginInsertRows(QModelIndex(), row, row)
        self._messages.append(msg)
        self.endInsertRows()

    def add_messages(self, msgs: list[MessageData]):
        """Thêm hàng loạt tin nhắn một lần để chống lag/giật UI khi tải nặng."""
        if not msgs:
            return
        if len(msgs) > self.MAX_MESSAGES:
            msgs = msgs[-self.MAX_MESSAGES:]
        total = len(self._messages) + len(msgs)
        if total > self.MAX_MESSAGES:
            overflow = total - self.MAX_MESSAGES
            self.beginRemoveRows(QModelIndex(), 0, overflow - 1)
            del self._messages[:overflow]
            self.endRemoveRows()
        first = len(self._messages)
        last = first + len(msgs) - 1
        self.beginInsertRows(QModelIndex(), first, last)
        self._messages.extend(msgs)
        self.endInsertRows()

    def clear(self):
        self.beginResetModel()
        self._messages.clear()
        self.endResetModel()

    def get_message(self, row: int) -> MessageData | None:
        if 0 <= row < len(self._messages):
            return self._messages[row]
        return None


class MessageDelegate(QStyledItemDelegate):
    """Delegate vẽ bong bóng chat, avatar QPixmap, reply quote và tem thời gian."""

    AVATAR_SIZE = 34
    PADDING = 10
    RADIUS = 10
    # Giới hạn cache QPixmap tối đa 500 mục để tránh rò rỉ bộ nhớ đồ họa khi giao tiếp với nhiều Peer.
    MAX_AVATAR_CACHE = 500

    def __init__(self, parent=None):
        super().__init__(parent)
        self._avatar_cache: dict[str, QPixmap] = {}

    def _cache_put(self, key: str, pm: QPixmap):
        """Lưu QPixmap vào cache theo cơ chế loại bỏ mục cũ nhất (FIFO) khi đạt ngưỡng."""
        if len(self._avatar_cache) >= self.MAX_AVATAR_CACHE:
            oldest_key = next(iter(self._avatar_cache))
            del self._avatar_cache[oldest_key]
        self._avatar_cache[key] = pm

    def _get_avatar(self, sender: str, avatar_path: str = "") -> QPixmap:
        cache_key = f"{sender}_{avatar_path}"
        if cache_key not in self._avatar_cache:
            pm = QPixmap(self.AVATAR_SIZE, self.AVATAR_SIZE)
            pm.fill(QColor(0, 0, 0, 0))
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            rect_f = QRectF(0.0, 0.0, float(self.AVATAR_SIZE), float(self.AVATAR_SIZE))
            path = QPainterPath()
            path.addEllipse(rect_f)
            p.setClipPath(path)

            # Nếu có đường dẫn file avatar hợp lệ
            if avatar_path and os.path.exists(avatar_path):
                img = QPixmap(avatar_path)
                if not img.isNull():
                    scaled = img.scaled(
                        self.AVATAR_SIZE, self.AVATAR_SIZE,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    x = (scaled.width() - self.AVATAR_SIZE) // 2
                    y = (scaled.height() - self.AVATAR_SIZE) // 2
                    p.drawPixmap(0, 0, scaled, x, y, self.AVATAR_SIZE, self.AVATAR_SIZE)
                    p.end()
                    self._cache_put(cache_key, pm)
                    return pm

            colors = ["#1a73e8", "#34a853", "#ea4335", "#fbbc04", "#9c27b0", "#00bcd4"]
            c = QColor(colors[abs(hash(sender)) % len(colors)])
            p.setBrush(QBrush(c))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPath(path)

            p.setPen(QColor(255, 255, 255))
            p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            initial = sender[0].upper() if sender else "?"
            p.drawText(rect_f, Qt.AlignmentFlag.AlignCenter, initial)
            p.end()
            self._cache_put(cache_key, pm)
        return self._avatar_cache[cache_key]

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        msg = index.data(Qt.ItemDataRole.DisplayRole)
        if not msg:
            return QSize(option.rect.width(), 40)

        if msg.is_system:
            return QSize(option.rect.width(), 32)

        view_w = option.rect.width() if option.rect.width() > 0 else 600
        max_bubble_w = int(view_w * 0.70)
        text_max_w = max_bubble_w - self.PADDING * 2

        font = QFont("Segoe UI", 13)
        fm = QFontMetrics(font)
        content_str = str(msg.content or "")
        text_rect = fm.boundingRect(0, 0, text_max_w, 10000, Qt.TextFlag.TextWordWrap, content_str)

        height = self.PADDING * 2 + text_rect.height() + 18
        if not msg.is_sent:
            height += 18  # Khoảng trống cho tên người gửi (Sender header)
        if msg.reply_to:
            height += 42  # Khung trích dẫn tin nhắn gốc
        if msg.forward_from:
            height += 18  # Tiêu đề chuyển tiếp (Forward)

        return QSize(view_w, max(height, self.AVATAR_SIZE + 10))

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        msg = index.data(Qt.ItemDataRole.DisplayRole)
        if not msg:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect

        if msg.is_system:
            painter.setPen(QColor("#6c6c8a"))
            font = QFont("Segoe UI", 11)
            font.setItalic(True)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(msg.content or ""))
            painter.restore()
            return

        view_w = rect.width()
        max_bubble_w = int(view_w * 0.70)
        text_max_w = max_bubble_w - self.PADDING * 2

        font = QFont("Segoe UI", 13)
        fm = QFontMetrics(font)
        content_str = str(msg.content or "")
        text_rect = fm.boundingRect(0, 0, text_max_w, 10000, Qt.TextFlag.TextWordWrap, content_str)

        # Tính toán chiều rộng tối thiểu để bong bóng không bị bóp nghẹt khi text ngắn
        min_bubble_w = 220 if msg.reply_to else (130 if not msg.is_sent else 75)
        bubble_w = max(min(text_rect.width() + self.PADDING * 2 + 16, max_bubble_w), min_bubble_w)
        bubble_h = self.PADDING * 2 + text_rect.height() + 18
        if not msg.is_sent:
            bubble_h += 18  # Chiều cao cho tên người gửi
        if msg.reply_to:
            bubble_h += 42  # Chiều cao cho khung reply
        if msg.forward_from:
            bubble_h += 18  # Chiều cao cho khung forward

        if msg.is_sent:
            bubble_x = rect.right() - bubble_w - 10
            avatar_x = -100
        else:
            avatar_x = rect.left() + 8
            bubble_x = avatar_x + self.AVATAR_SIZE + 8

        bubble_y = rect.top() + 4

        # Avatar
        if not msg.is_sent:
            av = self._get_avatar(msg.sender, getattr(msg, "avatar_path", ""))
            painter.drawPixmap(avatar_x, bubble_y, av)

        # Bubble
        bubble_color = QColor("#1a73e8" if msg.is_sent else "#3a3a52")
        painter.setBrush(QBrush(bubble_color))
        painter.setPen(Qt.PenStyle.NoPen)

        bubble_rect_f = QRectF(float(bubble_x), float(bubble_y), float(bubble_w), float(bubble_h))
        painter.drawRoundedRect(bubble_rect_f, float(self.RADIUS), float(self.RADIUS))

        text_y = bubble_y + self.PADDING

        # Forward header
        if isinstance(msg.forward_from, dict):
            painter.setPen(QColor("#fbbc04"))
            f_font = QFont("Segoe UI", 9)
            f_font.setItalic(True)
            painter.setFont(f_font)
            orig = str(msg.forward_from.get("original_sender") or "ai đó")[:64]
            painter.drawText(
                QRectF(float(bubble_x + self.PADDING), float(text_y), float(bubble_w - self.PADDING * 2), 14.0),
                Qt.AlignmentFlag.AlignLeft, f"↪ Chuyển tiếp từ {orig}"
            )
            text_y += 18

        # Reply quote box
        if isinstance(msg.reply_to, dict):
            rx = float(bubble_x + self.PADDING)
            rw = float(bubble_w - self.PADDING * 2)
            painter.setBrush(QBrush(QColor("#2a2a40")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(rx, float(text_y), rw, 38.0), 4.0, 4.0)

            # Left bar
            painter.setPen(QPen(QColor("#1a73e8"), 3))
            painter.drawLine(int(rx), int(text_y + 2), int(rx), int(text_y + 36))

            # Reply content
            painter.setPen(QColor("#1a73e8"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            rep_sender = str(msg.reply_to.get("sender") or "Peer")[:64]
            painter.drawText(QRectF(rx + 8, float(text_y + 2), rw - 12, 16.0), Qt.AlignmentFlag.AlignLeft, rep_sender)

            painter.setPen(QColor("#b0b0c8"))
            painter.setFont(QFont("Segoe UI", 9))
            rep_txt = str(msg.reply_to.get("content") or "")
            if len(rep_txt) > 40:
                rep_txt = rep_txt[:40] + "..."
            painter.drawText(QRectF(rx + 8, float(text_y + 18), rw - 12, 16.0), Qt.AlignmentFlag.AlignLeft, rep_txt)

            text_y += 42

        # Sender name if received
        if not msg.is_sent:
            painter.setPen(QColor("#e8f0fe"))
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            painter.drawText(
                QRectF(float(bubble_x + self.PADDING), float(text_y), float(bubble_w - self.PADDING * 2), 16.0),
                Qt.AlignmentFlag.AlignLeft, msg.sender
            )
            text_y += 18

        # Message Text
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(font)
        painter.drawText(
            QRectF(float(bubble_x + self.PADDING), float(text_y), float(text_max_w), float(text_rect.height() + 4)),
            Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft, content_str
        )

        # Time
        time_y = float(bubble_y + bubble_h - 18)
        painter.setPen(QColor("#6c6c8a"))
        painter.setFont(QFont("Segoe UI", 9))
        align = Qt.AlignmentFlag.AlignRight if msg.is_sent else Qt.AlignmentFlag.AlignLeft
        painter.drawText(
            QRectF(float(bubble_x + self.PADDING), time_y, float(bubble_w - self.PADDING * 2), 14.0),
            align | Qt.AlignmentFlag.AlignVCenter, msg.time_str
        )

        painter.restore()
