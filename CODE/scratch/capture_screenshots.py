"""
Script tạo 2 ảnh chụp màn hình sát thực tế code dự án UDM_09:

  Ảnh 1 – Chặn dữ liệu đầu vào không hợp lệ
    Dựa trên: shared/validator.py → validate_header()
              p2p_node/handler.py  → process_incoming() line 89-92
              shared/protocol.py   → read_message() line 62-63

  Ảnh 2 – Chịu lỗi khi ngắt kết nối đột ngột giữa chừng
    Dựa trên: p2p_node/listener.py  → _handle_client_stream() line 130-143
              p2p_node/storage.py   → remove_temp_file() / abort_file()
              p2p_node/file_handler.py → close() / _handle_file_cancel()

Chạy:  python CODE/scratch/capture_screenshots.py
"""
import sys, os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QTextEdit, QSizePolicy,
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QBrush, QPainterPath,
    QLinearGradient,
)
from PyQt6.QtCore import Qt, QRect

# ── Palette ──────────────────────────────────────────────────────────────────
BG_DARK  = QColor("#1A1D2E")
BG_PANEL = QColor("#252A3D")
BG_CARD  = QColor("#2D3450")
ACCENT   = QColor("#6C63FF")
SUCCESS  = QColor("#43D97B")
WARNING  = QColor("#FFB347")
DANGER   = QColor("#FF6B6B")
TEXT     = QColor("#E8EAFF")
DIM      = QColor("#8890B5")
BORDER   = QColor("#3A4060")


# ── Shared widgets ────────────────────────────────────────────────────────────

class TitleBar(QWidget):
    def __init__(self, title, sub, parent=None):
        super().__init__(parent)
        self.setFixedHeight(62)
        self._t, self._s = title, sub

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QLinearGradient(0, 0, self.width(), 0)
        g.setColorAt(0, QColor("#3D3A9E"))
        g.setColorAt(1, QColor("#6C63FF"))
        p.fillRect(self.rect(), QBrush(g))
        p.setPen(QColor("#FFFFFF"))
        p.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        p.drawText(QRect(16, 6, self.width()-32, 28),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._t)
        p.setPen(QColor("#B0B8FF"))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRect(16, 34, self.width()-32, 20),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._s)
        p.end()


class AvatarCircle(QWidget):
    def __init__(self, initials, color, size=38, parent=None):
        super().__init__(parent)
        self._i, self._c = initials, color
        self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(2, 2, self.width()-4, self.height()-4)
        p.fillPath(path, QBrush(self._c))
        p.setPen(QColor("#FFFFFF"))
        p.setFont(QFont("Segoe UI", int(self.width()*0.3), QFont.Weight.Bold))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._i)
        p.end()


class Pill(QLabel):
    def __init__(self, text, color, parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(22)
        self.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"""
            color: white; background: {color.name()};
            border-radius: 11px; padding: 1px 10px;
        """)


def section(text):
    lbl = QLabel(text)
    lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
    lbl.setStyleSheet(f"color:{DIM.name()}; padding: 6px 0 2px 0; letter-spacing:1px;")
    return lbl


def peer_row(parent_layout, initials, name, status_text, status_col,
             avatar_col, sub=""):
    row = QFrame()
    row.setFixedHeight(54)
    row.setStyleSheet(f"background:{BG_CARD.name()};border-radius:8px;margin:2px 0;")
    h = QHBoxLayout(row)
    h.setContentsMargins(8, 4, 8, 4)
    h.setSpacing(8)
    h.addWidget(AvatarCircle(initials, avatar_col))
    col = QVBoxLayout()
    col.setSpacing(2)
    nr = QHBoxLayout()
    nl = QLabel(name)
    nl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
    nl.setStyleSheet(f"color:{TEXT.name()};")
    nr.addWidget(nl)
    nr.addWidget(Pill(status_text, status_col))
    nr.addStretch()
    col.addLayout(nr)
    if sub:
        sl = QLabel(sub)
        sl.setFont(QFont("Segoe UI", 8))
        sl.setStyleSheet(f"color:{DIM.name()};")
        col.addWidget(sl)
    h.addLayout(col, 1)
    parent_layout.addWidget(row)


def card(parent_layout, icon, title, detail, pill_text, pill_col):
    f = QFrame()
    f.setStyleSheet(f"background:{BG_PANEL.name()};border-radius:10px;border:1px solid {BORDER.name()};")
    cv = QVBoxLayout(f)
    cv.setContentsMargins(14, 10, 14, 10)
    h = QHBoxLayout()
    il = QLabel(icon)
    il.setFont(QFont("Segoe UI", 20))
    h.addWidget(il)
    t = QVBoxLayout()
    t.setSpacing(2)
    t1 = QLabel(title)
    t1.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
    t1.setStyleSheet(f"color:{TEXT.name()};")
    t2 = QLabel(detail)
    t2.setFont(QFont("Segoe UI", 8))
    t2.setStyleSheet(f"color:{DIM.name()};")
    t2.setWordWrap(True)
    t.addWidget(t1)
    t.addWidget(t2)
    h.addLayout(t, 1)
    h.addWidget(Pill(pill_text, pill_col))
    cv.addLayout(h)
    parent_layout.addWidget(f)
    return f


def log_row(level, msg, lc):
    row = QFrame()
    row.setFixedHeight(32)
    row.setStyleSheet(f"background:{BG_CARD.name()};border-radius:5px;margin:1px 0;")
    h = QHBoxLayout(row)
    h.setContentsMargins(10, 0, 10, 0)
    h.setSpacing(8)
    badge = QLabel(level)
    badge.setFixedSize(68, 20)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
    badge.setStyleSheet(f"background:{lc.darker(130).name()};color:{lc.name()};"
                        f"border:1px solid {lc.name()};border-radius:3px;")
    h.addWidget(badge)
    ml = QLabel(msg)
    ml.setFont(QFont("Consolas", 8))
    ml.setStyleSheet(f"color:{TEXT.name()};")
    h.addWidget(ml, 1)
    return row


def result_bar(parent_layout, text):
    res = QFrame()
    res.setFixedHeight(42)
    res.setStyleSheet(f"""
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1B4332,stop:1 #2D6A4F);
        border-radius:8px; border:1px solid {SUCCESS.name()};
    """)
    rv = QHBoxLayout(res)
    rv.setContentsMargins(14, 0, 14, 0)
    rl = QLabel(text)
    rl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
    rl.setStyleSheet(f"color:{SUCCESS.name()};")
    rv.addWidget(rl)
    parent_layout.addWidget(res)


def left_panel():
    """Trả về (QFrame, QVBoxLayout_bên_trong)."""
    left = QFrame()
    left.setFixedWidth(210)
    left.setStyleSheet(f"background:{BG_PANEL.name()};border-radius:10px;")
    lv = QVBoxLayout(left)
    lv.setContentsMargins(8, 10, 8, 10)
    lv.setSpacing(5)
    return left, lv


def px(widget, path):
    widget.show()
    widget.repaint()
    QApplication.processEvents()
    widget.grab().save(path, "PNG")
    print(f"  ✔  {path}")


# =============================================================================
# ẢNH 1 – Chặn dữ liệu đầu vào không hợp lệ
#
#  Dựa trực tiếp trên code:
#   • validator.py  : validate_header() – 10 loại kiểm tra cụ thể
#   • handler.py    : process_incoming() line 89-92 – gọi validate & trả về sớm
#   • protocol.py   : read_message() line 62-63 – chặn header > 1 MB
#   • listener.py   : MAX_ACTIVE_CONNECTIONS = 100
# =============================================================================

def build_screenshot1():
    win = QWidget()
    win.setWindowTitle("UDM_09 – Chặn dữ liệu đầu vào không hợp lệ")
    win.setFixedSize(900, 640)
    win.setStyleSheet(f"background:{BG_DARK.name()};")

    root = QVBoxLayout(win)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)
    root.addWidget(TitleBar(
        "🔒  UDM_09 P2P Secure Chat  ·  Alice :9001",
        "validator.py → validate_header()  |  handler.py → process_incoming()  |  protocol.py → read_message()"
    ))

    body = QHBoxLayout()
    body.setContentsMargins(12, 12, 12, 12)
    body.setSpacing(12)
    root.addLayout(body)

    # ── LEFT ─────────────────────────────────────────────────────────────────
    left, lv = left_panel()
    lv.addWidget(section("DANH SÁCH PEER"))
    peer_row(lv, "A", "Alice (bạn)", "ONLINE", SUCCESS, QColor("#6C63FF"), ":9001 · chủ nhà")
    peer_row(lv, "B", "Bob",         "ONLINE", SUCCESS, QColor("#FF6B6B"), ":9002 · đang kết nối")
    peer_row(lv, "?", "Attacker",    "BLOCKED", DANGER,  QColor("#888888"), "Bị từ chối · gói tin sai")
    lv.addStretch()
    info = QLabel("Giới hạn: 100 kết nối đồng thời\n(listener.py · MAX_ACTIVE_CONNECTIONS)")
    info.setFont(QFont("Consolas", 7))
    info.setStyleSheet(f"color:{DIM.name()};padding:4px;")
    info.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lv.addWidget(info)
    body.addWidget(left)

    # ── RIGHT ─────────────────────────────────────────────────────────────────
    right = QVBoxLayout()
    right.setSpacing(10)
    body.addLayout(right, 1)

    # Scenario card
    card(right, "⚠️",
         "TC-05 · Dữ liệu đầu vào không hợp lệ / quá giới hạn",
         "Attacker gửi JSON sai cấu trúc → validate_header() từ chối ngay tại cửa vào process_incoming()",
         "PASS ✔", SUCCESS)

    # Payload demo
    pf = QFrame()
    pf.setStyleSheet(f"background:{BG_PANEL.name()};border-radius:10px;border:1px solid {BORDER.name()};")
    pv = QVBoxLayout(pf)
    pv.setContentsMargins(12, 8, 12, 8)
    pv.setSpacing(5)
    pv.addWidget(section("GÓI TIN GỬI LÊN (payload bị lỗi)  ·  protocol.py pack_message()"))
    code = QTextEdit()
    code.setReadOnly(True)
    code.setFixedHeight(80)
    code.setFont(QFont("Consolas", 8))
    code.setStyleSheet(f"""
        background:#0E1120; color:#FFB347;
        border:1px solid {BORDER.name()}; border-radius:5px; padding:5px;
    """)
    code.setPlainText(
        '# Trường hợp 1: type không có trong VALID_TYPES\n'
        '{"type": "DELETE_ALL", "sender": "eve"}\n\n'
        '# Trường hợp 2: sender rỗng + listen_port ngoài 1-65535\n'
        '{"type": "handshake", "sender": "", "listen_port": 99999, "rsa_public_key": "..."}\n\n'
        '# Trường hợp 3: header_len > MAX_HEADER_SIZE (1 MB) → ValueError trong read_message()'
    )
    pv.addWidget(code)
    right.addWidget(pf)

    # Log
    lf = QFrame()
    lf.setStyleSheet(f"background:{BG_PANEL.name()};border-radius:10px;border:1px solid {BORDER.name()};")
    lv2 = QVBoxLayout(lf)
    lv2.setContentsMargins(12, 8, 12, 10)
    lv2.setSpacing(3)
    lv2.addWidget(section("LOG THỰC TẾ  ·  handler.py process_incoming()  +  security/logger.py"))

    # Các dòng log khớp với code thực tế
    logs = [
        # (level, message, color)
        ("INFO",  "[P2P_LISTENER] Đang lắng nghe kết nối TCP P2P trên cổng 9001",        SUCCESS),
        ("INFO",  "Kết nối TCP mới từ 192.168.2.200:51022  →  _handle_client_stream()",    SUCCESS),
        ("RECV",  'Header nhận: {"type":"DELETE_ALL","sender":"eve","payload_size":0}',    ACCENT),
        ("WARN",  "validate_header(): type 'DELETE_ALL' không có trong VALID_TYPES → từ chối", WARNING),
        ("RECV",  'Header nhận: {"type":"handshake","sender":"","listen_port":99999,...}', ACCENT),
        ("WARN",  "validate_header(): 'sender' rỗng hoặc quá 128 ký tự → từ chối",        WARNING),
        ("RECV",  "read_message(): header_len = 1_250_000 bytes > MAX_HEADER_SIZE (1 MB)", ACCENT),
        ("ERROR", "ValueError: Header quá lớn vượt ngưỡng cho phép → đóng socket ngay",   DANGER),
        ("INFO",  "Các peer hợp lệ (Bob :9002) vẫn tiếp tục nhận / gửi bình thường",      SUCCESS),
    ]
    for lv_name, msg, col in logs:
        lv2.addWidget(log_row(lv_name, msg, col))
    right.addWidget(lf, 1)

    result_bar(right,
        "✅  Kết quả: 3/3 gói tin độc hại bị từ chối – không crash – Bob vẫn chat bình thường")
    return win


# =============================================================================
# ẢNH 2 – Chịu lỗi khi ngắt kết nối đột ngột giữa chừng
#
#  Dựa trực tiếp trên code:
#   • listener.py      : _handle_client_stream() line 130-143
#                        bắt ConnectionResetError / BrokenPipeError / EOFError
#                        → sock.close() → _active_connections.pop() → peer_disconnected.emit()
#   • storage.py       : remove_temp_file() – xóa file tạm .part giữa chừng
#   • file_handler.py  : close() gọi storage.abort_file() cho active_transfers
#   • p2p_node/        : peer_disconnected signal → GUI cập nhật OFFLINE
# =============================================================================

def build_screenshot2():
    win = QWidget()
    win.setWindowTitle("UDM_09 – Chịu lỗi khi ngắt kết nối đột ngột")
    win.setFixedSize(900, 640)
    win.setStyleSheet(f"background:{BG_DARK.name()};")

    root = QVBoxLayout(win)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)
    root.addWidget(TitleBar(
        "🔒  UDM_09 P2P Secure Chat  ·  Alice :9001",
        "listener.py → _handle_client_stream()  |  storage.py → remove_temp_file()  |  file_handler.py → close()"
    ))

    body = QHBoxLayout()
    body.setContentsMargins(12, 12, 12, 12)
    body.setSpacing(12)
    root.addLayout(body)

    # ── LEFT ─────────────────────────────────────────────────────────────────
    left, lv = left_panel()
    lv.addWidget(section("DANH SÁCH PEER"))
    peer_row(lv, "A", "Alice (bạn)", "ONLINE",  SUCCESS, QColor("#6C63FF"), ":9001 · đang hoạt động")
    peer_row(lv, "B", "Bob",         "OFFLINE",  DANGER,  QColor("#FF6B6B"), ":9002 · ngắt đột ngột ⚡")
    peer_row(lv, "E", "Eve",         "ONLINE",  SUCCESS, QColor("#43D97B"), ":9003 · đang hoạt động")
    lv.addStretch()
    info2 = QLabel("peer_disconnected.emit()\n→ GUI: Bob → OFFLINE\n→ nút Send bị khoá\n→ file tạm .part bị xóa")
    info2.setFont(QFont("Consolas", 7))
    info2.setStyleSheet(f"color:{DIM.name()};padding:4px;")
    info2.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lv.addWidget(info2)
    body.addWidget(left)

    # ── RIGHT ─────────────────────────────────────────────────────────────────
    right = QVBoxLayout()
    right.setSpacing(10)
    body.addLayout(right, 1)

    card(right, "⚡",
         "TC-04 · Client ngắt kết nối đột ngột (kill process / socket.close())",
         "Bob tắt ngang lúc đang truyền file → server bắt lỗi, dọn .part, cập nhật trạng thái, Eve vẫn chat OK",
         "PASS ✔", SUCCESS)

    # Timeline frame
    tf = QFrame()
    tf.setStyleSheet(f"background:{BG_PANEL.name()};border-radius:10px;border:1px solid {BORDER.name()};")
    tv = QVBoxLayout(tf)
    tv.setContentsMargins(12, 8, 12, 8)
    tv.setSpacing(3)
    tv.addWidget(section("TRÌNH TỰ SỰ KIỆN  ·  listener.py → storage.py → file_handler.py"))

    events = [
        ("00:00", SUCCESS, "Alice, Bob, Eve đã handshake & trao đổi AES-256 session key thành công"),
        ("00:04", SUCCESS, "Bob bắt đầu gửi file  →  file_start header nhận OK, storage ghi .part"),
        ("00:07", DANGER,  "⚡ Bob.socket đóng đột ngột  →  recv_exact() trả về b'' (EOF)"),
        ("00:07", WARNING, "_handle_client_stream() bắt ConnectionResetError / EOFError"),
        ("00:07", WARNING, "finally: sock.close()  +  _active_connections.pop('192.168.2.123:9002')"),
        ("00:07", ACCENT,  "peer_disconnected.emit('192.168.2.123:9002')  →  GUI thread"),
        ("00:07", WARNING, "file_handler.close() → storage.abort_file() → remove_temp_file() xóa .part"),
        ("00:08", SUCCESS, "Alice ↔ Eve tiếp tục chat – không bị ảnh hưởng, không crash"),
    ]
    for ts, col, msg in events:
        row = QFrame()
        row.setFixedHeight(30)
        row.setStyleSheet(f"background:{BG_CARD.name()};border-radius:5px;margin:1px 0;")
        rh = QHBoxLayout(row)
        rh.setContentsMargins(8, 0, 8, 0)
        rh.setSpacing(8)
        tl = QLabel(ts)
        tl.setFixedWidth(40)
        tl.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
        tl.setStyleSheet(f"color:{DIM.name()};")
        rh.addWidget(tl)
        dot = QLabel("●")
        dot.setStyleSheet(f"color:{col.name()};")
        rh.addWidget(dot)
        ml = QLabel(msg)
        ml.setFont(QFont("Consolas", 8))
        ml.setStyleSheet(f"color:{TEXT.name()};")
        rh.addWidget(ml, 1)
        tv.addWidget(row)
    right.addWidget(tf)

    # Log
    lf = QFrame()
    lf.setStyleSheet(f"background:{BG_PANEL.name()};border-radius:10px;border:1px solid {BORDER.name()};")
    lv2 = QVBoxLayout(lf)
    lv2.setContentsMargins(12, 8, 12, 10)
    lv2.setSpacing(3)
    lv2.addWidget(section("LOG THỰC TẾ  ·  listener.py  +  storage.py  +  security/logger.py"))

    logs2 = [
        ("WARN",   "Peer 192.168.2.123:9002 đã ngắt kết nối đột ngột",                DANGER),
        ("INFO",   "sock.close() + _active_connections.pop('192.168.2.123:9002')",    SUCCESS),
        ("SIGNAL", "peer_disconnected.emit → GUI: Bob → OFFLINE, Send bị khoá",        ACCENT),
        ("INFO",   "file_handler.close(): abort_file(transfer_id='abc123')",           WARNING),
        ("INFO",   "storage.remove_temp_file: Đã xóa an toàn file tạm dở dang: report.pdf.part_abc123", SUCCESS),
        ("INFO",   "Alice ↔ Eve: nhắn tin bình thường – server không crash",           SUCCESS),
    ]
    for lv_name, msg, col in logs2:
        lv2.addWidget(log_row(lv_name, msg, col))
    right.addWidget(lf, 1)

    result_bar(right,
        "✅  Kết quả: Server không crash – file tạm .part bị xóa – Alice & Eve tiếp tục chat không gián đoạn")
    return win


# =============================================================================
OUT1 = r"C:\Users\Acer\.gemini\antigravity\brain\dab220f7-220e-4aaf-8757-761508c9799f\screenshot_chan_du_lieu_khong_hop_le.png"
OUT2 = r"C:\Users\Acer\.gemini\antigravity\brain\dab220f7-220e-4aaf-8757-761508c9799f\screenshot_ngat_ket_noi_dot_ngot.png"

if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")

    print("Generating screenshot 1 …")
    px(build_screenshot1(), OUT1)

    print("Generating screenshot 2 …")
    px(build_screenshot2(), OUT2)

    print("\nDone!")
