"""
Unit Tests cho Phân hệ Giao diện Đồ họa Desktop PyQt6 [Thành viên 2 - TV2]
Kiểm thử các thành phần:
- AvatarWidget (QPixmap, bo tròn, nạp ảnh hoặc chữ cái đầu)
- ReplyPreview (Khung trích dẫn xem trước tin nhắn reply)
- EmojiPicker (Bộ chọn biểu tượng cảm xúc UTF-8)
- MessageListModel & MessageDelegate (QListView Virtualization, vẽ bong bóng, reply, avatar, thời gian)
- PeerItemWidget & PeerListWidget (Đổi màu QSS Online/Offline, cập nhật tin nhắn cuối)
- MainWindow (Luồng Reply, ngắt kết nối khóa nút Gửi)
"""

import os
import sys
import time
import pytest
from PyQt6.QtCore import Qt, QModelIndex, QRect, QPoint
from PyQt6.QtGui import QPixmap, QImage, QPainter, QFont
from PyQt6.QtWidgets import QApplication, QStyleOptionViewItem

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(ROOT_DIR, "CODE")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ui.chat_widgets import (
    AvatarWidget, ReplyPreview, EmojiPicker,
    MessageData, MessageListModel, MessageDelegate
)
from ui.peer_list_widget import PeerItemWidget, PeerListWidget
from ui.app import MainWindow


@pytest.fixture(scope="session")
def qapp():
    """Tạo QApplication instance dùng chung cho toàn bộ test suite."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ==========================================
# 1. KIỂM THỬ AVATAR WIDGET (QPIXMAP)
# ==========================================

def test_avatar_widget_initials(qapp):
    """Kiểm tra AvatarWidget vẽ chữ cái viết hoa và có kích thước chuẩn."""
    avatar = AvatarWidget("alice", size=40)
    assert avatar.width() == 40
    assert avatar.height() == 40
    pixmap = avatar.pixmap()
    assert pixmap is not None
    assert not pixmap.isNull()
    assert pixmap.width() == 40
    assert pixmap.height() == 40


def test_avatar_widget_image_file(qapp, tmp_path):
    """Kiểm tra AvatarWidget nạp ảnh file PNG thực tế."""
    test_img = tmp_path / "avatar_test.png"
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.blue)
    pix.save(str(test_img))

    avatar = AvatarWidget("Bob", size=48, image_path=str(test_img))
    assert avatar.width() == 48
    assert avatar.height() == 48
    pixmap = avatar.pixmap()
    assert pixmap is not None
    assert not pixmap.isNull()


# ==========================================
# 2. KIỂM THỬ REPLY PREVIEW
# ==========================================

def test_reply_preview_flow(qapp):
    """Kiểm tra hiển thị trích dẫn Reply và hủy Reply."""
    preview = ReplyPreview()
    assert not preview.isVisible()

    # Thiết lập reply
    preview.set_reply("Alice", "Nội dung tin nhắn cần phản hồi", "uuid-1234")
    assert preview.isVisible()
    data = preview.get_reply_data()
    assert data is not None
    assert data["sender"] == "Alice"
    assert data["content"] == "Nội dung tin nhắn cần phản hồi"
    assert data["msg_id"] == "uuid-1234"

    # Hủy reply
    cancelled = []
    preview.cancel_reply.connect(lambda: cancelled.append(True))
    preview._on_cancel()
    assert not preview.isVisible()
    assert preview.get_reply_data() is None
    assert len(cancelled) == 1


# ==========================================
# 3. KIỂM THỬ EMOJI PICKER
# ==========================================

def test_emoji_picker_selection(qapp):
    """Kiểm tra chọn Emoji và phát tín hiệu UTF-8."""
    picker = EmojiPicker()
    assert picker.category_combo.count() >= 4

    selected = []
    picker.emoji_selected.connect(lambda emo: selected.append(emo))

    # Giả lập chọn emoji 😀
    picker._select_emoji("🔥")
    assert len(selected) == 1
    assert selected[0] == "🔥"
    assert not picker.isVisible()


# ==========================================
# 4. KIỂM THỬ MESSAGE MODEL & VIRTUALIZATION
# ==========================================

def test_message_list_model_single_and_batch(qapp):
    """Kiểm tra thêm tin nhắn đơn lẻ và thêm hàng loạt (Tối ưu Chặng 7)."""
    model = MessageListModel()
    assert model.rowCount() == 0

    # 1. Thêm 1 tin nhắn
    msg1 = MessageData(
        msg_id="m1", sender="Alice", content="Chào bạn!",
        timestamp=time.time(), is_sent=False
    )
    model.add_message(msg1)
    assert model.rowCount() == 1
    assert model.get_message(0).content == "Chào bạn!"

    # 2. Thêm hàng loạt 50 tin nhắn
    batch = [
        MessageData(f"m_{i}", "Bob", f"Tin nhắn số {i}", time.time(), True)
        for i in range(50)
    ]
    model.add_messages(batch)
    assert model.rowCount() == 51
    assert model.get_message(50).content == "Tin nhắn số 49"

    # 3. Xóa danh sách
    model.clear()
    assert model.rowCount() == 0


def test_message_delegate_size_and_paint(qapp):
    """Kiểm tra MessageDelegate tính sizeHint và paint không bị lỗi kiểu dữ liệu PyQt6."""
    model = MessageListModel()
    delegate = MessageDelegate()

    msg_reply = MessageData(
        msg_id="r1", sender="Charlie",
        content="Đây là tin nhắn có trích dẫn reply",
        timestamp=time.time(), is_sent=False,
        reply_to={"sender": "Alice", "content": "Tin nhắn gốc"}
    )
    model.add_message(msg_reply)

    index = model.index(0, 0)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 800, 100)

    # Kiểm tra sizeHint
    size = delegate.sizeHint(option, index)
    assert size.width() == 800
    assert size.height() > 40

    # Kiểm tra hàm paint trực tiếp trên QPixmap
    target_pixmap = QPixmap(800, size.height())
    target_pixmap.fill(Qt.GlobalColor.black)
    painter = QPainter(target_pixmap)
    try:
        delegate.paint(painter, option, index)
    finally:
        painter.end()


# ==========================================
# 5. KIỂM THỬ PEER LIST WIDGET & ĐỔI MÀU QSS
# ==========================================

def test_peer_list_widget_and_status(qapp):
    """Kiểm tra danh sách Peer hiển thị Online/Offline và đổi màu QSS."""
    peer_list = PeerListWidget("UserTest", 9001)

    # Thêm Peer
    peer_list.add_or_update_peer("127.0.0.1:9002", "Bob", "127.0.0.1", 9002, "online")
    assert peer_list.get_peer_status("127.0.0.1:9002") == "online"

    # Cập nhật tin nhắn cuối
    peer_list.update_last_message("127.0.0.1:9002", "Alo Bob ơi")
    w = peer_list.get_peer_widget("127.0.0.1:9002")
    assert w is not None
    assert "Alo Bob ơi" in w.last_msg_label.text()

    # Chuyển trạng thái sang Offline (Chặng 6)
    peer_list.set_peer_status("127.0.0.1:9002", "offline")
    assert peer_list.get_peer_status("127.0.0.1:9002") == "offline"
    assert w.status_label.property("status") == "offline"


# ==========================================
# 6. KIỂM THỬ MAIN WINDOW: KHÓA NÚT GỬI KHI OFFLINE
# ==========================================

def test_main_window_offline_lock(qapp):
    """Kiểm tra khi Peer ngắt kết nối đột ngột, MainWindow tự động khóa nút gửi và input."""
    win = MainWindow(username="AliceTest", listen_port=9988, demo_mode=True)
    try:
        # Giả lập phát hiện peer
        peer_id = "192.168.1.50:9005"
        win._on_peer_discovered(peer_id, "BobRemote", "192.168.1.50", 9005)
        win._on_peer_selected(peer_id)

        # Ban đầu online -> nút gửi bật
        assert win.send_btn.isEnabled() is True
        assert win.input_field.isEnabled() is True

        # Giả lập Peer ngắt kết nối đột ngột (Chặng 6)
        win._on_peer_disconnected(peer_id)

        # Sau khi ngắt kết nối -> nút gửi và input bị khóa
        assert win.send_btn.isEnabled() is False
        assert win.input_field.isEnabled() is False
        assert "Offline" in win.header_status_label.text()
    finally:
        win.listener.stop()
        win.discovery.stop()
        win.close()


# ==========================================
# 7. KIỂM THỬ CÁC TRƯỜNG HỢP BIÊN & NGOẠI LỆ (EDGE CASES)
# ==========================================

def test_message_edge_cases_and_empty_content(qapp):
    """Kiểm thử tin nhắn rỗng, None hoặc ký tự đặc biệt không làm crash QListView Delegate."""
    model = MessageListModel()
    delegate = MessageDelegate()

    # Tin nhắn None / Empty
    msg_empty = MessageData(msg_id="e1", sender="", content="", timestamp=time.time(), is_sent=True)
    msg_none = MessageData(msg_id="e2", sender="Ghost", content=None, timestamp=time.time(), is_sent=False)
    # Tin nhắn rất ngắn có Reply (kiểm tra độ rộng tối thiểu bubble_w)
    msg_short_reply = MessageData(
        msg_id="e3", sender="Alice", content="👍",
        timestamp=time.time(), is_sent=False,
        reply_to={"sender": "Bob", "content": "Tin nhắn rất dài cần phản hồi"}
    )
    model.add_message(msg_empty)
    model.add_message(msg_none)
    model.add_message(msg_short_reply)

    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 800, 100)

    for i in range(3):
        idx = model.index(i, 0)
        size = delegate.sizeHint(option, idx)
        assert size.height() > 0

        pixmap = QPixmap(800, size.height())
        pixmap.fill(Qt.GlobalColor.black)
        painter = QPainter(pixmap)
        try:
            delegate.paint(painter, option, idx)
        finally:
            painter.end()


def test_canonical_peer_id_resolution(qapp):
    """Kiểm tra hàm ánh xạ cổng socket tạm thời (ephemeral) về đúng Canonical Peer ID."""
    win = MainWindow(username="AliceTest", listen_port=9977, demo_mode=True)
    try:
        win._peer_info_map["127.0.0.1:9002"] = {
            "ip": "127.0.0.1", "port": 9002, "username": "BobTV5", "status": "online"
        }

        # 1. Khớp chính xác
        assert win._find_canonical_peer_id("127.0.0.1:9002") == "127.0.0.1:9002"

        # 2. Khớp qua sender_port (kết nối đến từ cổng tạm 54321 nhưng mang sender_port 9002)
        assert win._find_canonical_peer_id("127.0.0.1:54321", sender_port=9002) == "127.0.0.1:9002"

        # 3. Khớp qua username
        assert win._find_canonical_peer_id("127.0.0.1:54321", sender_name="BobTV5") == "127.0.0.1:9002"

        # 4. Peer chưa biết
        assert win._find_canonical_peer_id("192.168.1.99:55555") == "192.168.1.99:55555"
    finally:
        win.listener.stop()
        win.discovery.stop()
        win.close()


def test_peer_list_selection_and_online_filter(qapp):
    """Kiểm tra select_peer và lọc danh sách Peer đang online."""
    peer_list = PeerListWidget("Me", 9001)
    peer_list.add_or_update_peer("127.0.0.1:9002", "Bob", "127.0.0.1", 9002, "online")
    peer_list.add_or_update_peer("127.0.0.1:9003", "Charlie", "127.0.0.1", 9003, "offline")

    # Lọc tất cả vs lọc chỉ online
    all_peers = peer_list.get_all_peers(online_only=False)
    assert len(all_peers) == 2

    online_peers = peer_list.get_all_peers(online_only=True)
    assert len(online_peers) == 1
    assert online_peers[0][0] == "127.0.0.1:9002"

    # Chọn peer theo ID
    selected_signals = []
    peer_list.peer_selected.connect(lambda pid: selected_signals.append(pid))
    peer_list.select_peer("127.0.0.1:9002")
    assert len(selected_signals) == 1
    assert selected_signals[0] == "127.0.0.1:9002"

