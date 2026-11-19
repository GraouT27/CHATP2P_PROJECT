"""
Handler Module - Phân loại, giải mã và xử lý các luồng dữ liệu mạng đến (TV4 & TV5).
"""

import time
import base64
from PyQt6.QtCore import QObject, pyqtSignal
from shared.validator import validate_header, verify_checksum
from security.crypto_manager import CryptoManager
from security.logger import log


class MessageHandler(QObject):
    """
    Xử lý và điều hướng các gói tin nhận được từ các Peer khác.
    Cách dùng: P2PListener gọi process_incoming() từ luồng mạng nền; các pyqtSignal bên dưới
    sẽ truyền dữ liệu an toàn qua thread-boundary về MainWindow (UI thread) để hiển thị.
    """
    # Tách riêng tín hiệu handshake vs handshake_ack để UI chỉ trả lời ACK đúng 1 lần,
    # tránh lặp vô tận (ping-pong) giữa hai nút P2P.
    handshake_received = pyqtSignal(str, str, int, str, str)      # (peer_id, username, port, pub_key, avatar_b64)
    handshake_ack_received = pyqtSignal(str, str, int, str, str)  # (peer_id, username, port, pub_key, avatar_b64)
    key_exchange_done = pyqtSignal(str)                           # (peer_id)
    chat_received = pyqtSignal(str, dict)                         # (peer_id, message_data)
    file_start_received = pyqtSignal(str, dict)                   # (peer_id, header)
    file_chunk_received = pyqtSignal(str, dict, bytes)            # (peer_id, header, chunk_data)
    file_cancel_received = pyqtSignal(str, str)                   # (peer_id, file_id)

    def __init__(self, crypto_mgr: CryptoManager = None, parent=None):
        super().__init__(parent)
        self.crypto_mgr = crypto_mgr
        self._callbacks = {}

    def register(self, message_type: str, callback) -> None:
        if not isinstance(message_type, str) or not message_type.strip():
            raise ValueError("message_type không hợp lệ")
        if not callable(callback):
            raise TypeError("callback phải gọi được")
        if message_type in self._callbacks:
            raise ValueError(f"Đã đăng ký {message_type}")
        self._callbacks[message_type] = callback

    def handle_message(self, message: dict, send_reply) -> None:
        from shared.protocol import validate_message
        validate_message(message)
        if not callable(send_reply):
            raise TypeError("send_reply phải gọi được")

        message_type = message["header"]["message_type"]
        callback = self._callbacks.get(message_type)
        if callback is None:
            raise ValueError(f"Chưa có handler cho {message_type}")

        callback(message, send_reply)

    @staticmethod
    def _resolve_canonical_id(peer_id: str, listen_or_sender_port: int) -> str:
        """
        Tạo peer_id chuẩn hóa '<IP>:<cổng_lắng_nghe>'.
        Lý do phải dùng hàm này: mỗi lần kết nối TCP mới, hệ điều hành cấp một cổng nguồn ngẫu nhiên
        (ephemeral port, vd: 54321) thay vì cổng lắng nghe cố định của Peer (vd: 9001).
        Nếu lưu khóa mã hóa theo cổng ngẫu nhiên 54321, kết nối tiếp theo sẽ không tìm thấy khóa để giải mã.
        """
        ip = peer_id.split(":")[0] if ":" in peer_id else peer_id
        if (
            isinstance(listen_or_sender_port, int)
            and not isinstance(listen_or_sender_port, bool)
            and 1 <= listen_or_sender_port <= 65535
        ):
            return f"{ip}:{listen_or_sender_port}"
        return peer_id

    def _resolve_session_key_id(self, peer_id: str, sender_port: int) -> str:
        """
        Tìm ID chính xác đang giữ khóa phiên AES-256 trong CryptoManager.
        Ưu tiên ID chuẩn hóa theo sender_port trước, sau đó mới fallback về peer_id của socket.
        """
        canonical_id = self._resolve_canonical_id(peer_id, sender_port)
        if self.crypto_mgr.has_session_key(canonical_id):
            return canonical_id
        if self.crypto_mgr.has_session_key(peer_id):
            return peer_id
        return canonical_id

    def process_incoming(self, peer_id: str, header: dict, payload: bytes):
        """Xác thực schema trước rồi mới phân loại gói tin đến."""
        # Luôn kiểm tra validate_header trước khi đọc bất kỳ trường nào để chặn gói tin dị dạng/độc hại.
        is_valid, reason = validate_header(header)
        if not is_valid:
            log.warning(f"Từ chối gói tin không hợp lệ từ {peer_id}: {reason}")
            return

        msg_type = header.get("type")
        sender = str(header.get("sender", "Peer"))

        # 1. Gói tin Handshake
        if msg_type == "handshake":
            listen_port = header.get("listen_port", 0)
            pub_key = header.get("rsa_public_key", "")
            avatar_b64 = header.get("avatar_b64", "")
            canonical_id = self._resolve_canonical_id(peer_id, listen_port)
            if pub_key:
                self.crypto_mgr.register_peer_public_key(canonical_id, pub_key)
                if canonical_id != peer_id:
                    self.crypto_mgr.register_peer_public_key(peer_id, pub_key)
            self.handshake_received.emit(peer_id, sender, listen_port, pub_key, avatar_b64)

        # 2. Gói tin Handshake ACK
        elif msg_type == "handshake_ack":
            listen_port = header.get("listen_port", 0)
            pub_key = header.get("rsa_public_key", "")
            avatar_b64 = header.get("avatar_b64", "")
            canonical_id = self._resolve_canonical_id(peer_id, listen_port)
            if pub_key:
                self.crypto_mgr.register_peer_public_key(canonical_id, pub_key)
                if canonical_id != peer_id:
                    self.crypto_mgr.register_peer_public_key(peer_id, pub_key)
            self.handshake_ack_received.emit(peer_id, sender, listen_port, pub_key, avatar_b64)

        # 3. Gói tin Key Exchange (Nhận Khóa phiên AES-256)
        elif msg_type == "key_exchange":
            enc_key = header.get("encrypted_key")
            listen_port = header.get("listen_port", 0)
            canonical_id = self._resolve_canonical_id(peer_id, listen_port)
            if enc_key and self.crypto_mgr.receive_and_decrypt_session_key(canonical_id, enc_key):
                log.info(f"Đã giải mã thành công khóa phiên AES-256 từ {canonical_id}")
                self.key_exchange_done.emit(canonical_id)
            else:
                log.error(f"Thất bại khi giải mã khóa phiên từ {canonical_id}")

        # 4. Gói tin Tin nhắn Trò chuyện (Text / Emoji / Reply / Forward)
        elif msg_type == "chat":
            text = header.get("text", "")
            is_encrypted = bool(header.get("is_encrypted", False))
            nonce = header.get("nonce")
            sender_port = header.get("sender_port", 0)
            key_id = self._resolve_session_key_id(peer_id, sender_port)

            # Phòng thủ Anti-Downgrade: Khi 2 Peer đã có khóa phiên AES-256, tuyệt đối không chấp nhận
            # gói tin văn bản trơn (is_encrypted=False) vì kẻ tấn công MITM có thể chèn nội dung giả mạo
            # mà không cần biết khóa AES.
            if not is_encrypted and self.crypto_mgr.has_session_key(key_id):
                log.warning(
                    f"Cảnh báo Anti-Downgrade: Từ chối gói tin chat không mã hóa từ {key_id}!"
                )
                return

            # Nếu tin nhắn được mã hóa
            if is_encrypted:
                dec_text = None
                if payload and nonce:
                    nonce_bytes = base64.b64decode(nonce.encode("utf-8")) if isinstance(nonce, str) else nonce
                    dec_bytes = self.crypto_mgr.decrypt_bytes(key_id, payload, nonce_bytes)
                    if dec_bytes is not None:
                        dec_text = dec_bytes.decode("utf-8", errors="replace")
                elif text and nonce:
                    dec_text = self.crypto_mgr.decrypt_text(key_id, text, nonce)

                if dec_text is not None:
                    text = dec_text
                else:
                    text = "🔒 [Lỗi giải mã tin nhắn: Dữ liệu bị giả mạo hoặc sai khóa]"
                    log.error(f"Giải mã tin nhắn từ {key_id} thất bại")

            msg_data = {
                "msg_id": header.get("msg_id"),
                "sender": sender,
                "sender_port": sender_port if isinstance(sender_port, int) else 0,
                "content": text,
                "timestamp": header.get("timestamp", time.time()),
                "reply_to": header.get("reply_to"),
                "forward_from": header.get("forward_from"),
            }
            log.info(f"Nhận tin nhắn từ {key_id} ({sender}): {text}")
            self.chat_received.emit(peer_id, msg_data)

        # 5. Gói tin Bắt đầu truyền file (file_start)
        elif msg_type == "file_start":
            self.file_start_received.emit(peer_id, header)

        # 6. Gói tin Từng mảnh file (file_chunk)
        elif msg_type == "file_chunk":
            chunk_data = payload
            is_encrypted = bool(header.get("is_encrypted", False))
            nonce = header.get("nonce")
            chunk_hash = header.get("chunk_hash")
            sender_port = header.get("sender_port", 0)
            key_id = self._resolve_session_key_id(peer_id, sender_port)

            if not is_encrypted and self.crypto_mgr.has_session_key(key_id):
                log.warning(
                    f"Cảnh báo Anti-Downgrade: Từ chối chunk file không mã hóa từ {key_id}!"
                )
                return

            # Giải mã chunk nếu có mã hóa
            if is_encrypted and nonce:
                nonce_bytes = base64.b64decode(nonce.encode("utf-8")) if isinstance(nonce, str) else nonce
                dec_chunk = self.crypto_mgr.decrypt_bytes(key_id, chunk_data, nonce_bytes)
                if dec_chunk is None:
                    log.error(f"Giải mã chunk file thất bại từ {key_id}")
                    return
                chunk_data = dec_chunk

            # Đối chiếu Checksum SHA-256 của chunk
            if chunk_hash and not verify_checksum(chunk_data, chunk_hash):
                log.error(f"Mã băm SHA-256 của chunk không khớp từ {peer_id}! Từ chối gói tin.")
                return

            self.file_chunk_received.emit(peer_id, header, chunk_data)

        # 7. Gói tin Hủy truyền file (file_cancel)
        elif msg_type == "file_cancel":
            file_id = header.get("file_id")
            log.warning(f"Peer {peer_id} đã hủy truyền file {file_id}")
            self.file_cancel_received.emit(peer_id, file_id)
