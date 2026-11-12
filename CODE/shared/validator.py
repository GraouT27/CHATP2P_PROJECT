"""
Validator Module - Kiểm tra tính hợp lệ dữ liệu & đối chiếu Checksum SHA-256 (TV6).

Yêu cầu kỹ thuật:
- Kiểm tra tính hợp lệ của Header nhận được trước khi xử lý, từ chối gói tin dị dạng và trả về mã lỗi rõ ràng.
- Phòng chống tấn công tiêm nhiễm kiểu dữ liệu (Type Confusion), DoS kích thước trường, và Path Traversal.
- Đối chiếu mã băm SHA-256 của từng chunk và toàn bộ file.
"""

import hashlib
from typing import Tuple

VALID_TYPES = {
    "handshake", "handshake_ack", "key_exchange",
    "chat", "avatar_sync",
    "file_start", "file_chunk", "file_ack", "file_cancel",
    "ping", "pong"
}


def _is_int(val) -> bool:
    """
    Kiểm tra chặt chẽ biến có đúng kiểu int hay không.
    Lý do phải dùng 'not isinstance(val, bool)': trong Python, bool là lớp con của int
    nên isinstance(True, int) == True. Nếu không loại trừ bool, kẻ tấn công có thể
    gửi listen_port=true (tương đương cổng 1) hoặc chunk_size=true để vượt qua kiểm tra.
    """
    return isinstance(val, int) and not isinstance(val, bool)


def validate_header(header: dict) -> Tuple[bool, str]:
    """
    Kiểm tra cấu trúc và tính hợp lệ của JSON Header trước khi đưa vào xử lý nghiệp vụ/UI.
    Cách dùng: luôn gọi ngay tại cửa ngõ nhận gói tin (MessageHandler.process_incoming).
    Trả về (is_valid, error_reason).
    """
    # Chặn trường hợp attacker gửi JSON dạng list/string/null thay vì object (dict).
    if not isinstance(header, dict):
        return False, "Header không phải là một JSON object hợp lệ"

    msg_type = header.get("type")
    if not msg_type or not isinstance(msg_type, str) or msg_type not in VALID_TYPES:
        return False, f"Trường 'type' không hợp lệ hoặc không được hỗ trợ: {msg_type}"

    # Giới hạn độ dài sender <= 128 ký tự để chống tấn công phình bộ nhớ/treo UI khi vẽ tên.
    sender = header.get("sender")
    if not sender or not isinstance(sender, str) or len(sender) > 128:
        return False, "Thiếu trường 'sender' hoặc định dạng không hợp lệ"

    # Kiểm tra payload_size phải nằm trong [0, 16MB] nhằm tránh lỗi cấp phát RAM khổng lồ (OOM DoS).
    if "payload_size" in header:
        ps = header["payload_size"]
        if not _is_int(ps) or ps < 0 or ps > 16 * 1024 * 1024:
            return False, "Trường 'payload_size' không hợp lệ"

    # Kiểm tra theo từng loại gói tin cụ thể
    if msg_type == "handshake":
        lp = header.get("listen_port")
        # Cổng TCP hợp lệ bắt buộc nằm trong 1..65535 để tránh lỗi socket hoặc cổng giả 0.
        if not _is_int(lp) or lp < 1 or lp > 65535:
            return False, "Handshake có 'listen_port' không hợp lệ (phải từ 1 đến 65535)"
        pub = header.get("rsa_public_key")
        # Khóa RSA-2048 PEM chuẩn chỉ dài ~450 ký tự; chặn > 8192 để tránh gói tin rác quá cỡ.
        if not pub or not isinstance(pub, str) or len(pub) > 8192:
            return False, "Handshake thiếu 'rsa_public_key' hoặc vượt quá giới hạn"

    elif msg_type == "handshake_ack":
        if "listen_port" in header:
            lp = header["listen_port"]
            if not _is_int(lp) or lp < 0 or lp > 65535:
                return False, "Handshake ACK có 'listen_port' không hợp lệ"

    elif msg_type == "key_exchange":
        enc_key = header.get("encrypted_key")
        if not enc_key or not isinstance(enc_key, str) or len(enc_key) > 8192:
            return False, "Key exchange thiếu trường 'encrypted_key' hoặc định dạng sai"

    elif msg_type == "chat":
        # Chặn Type Confusion: nếu caller ở UI gọi .get(...) lên reply_to/forward_from dạng chuỗi hoặc list
        # sẽ gây AttributeError làm văng ứng dụng -> bắt buộc kiểm tra phải là dict hoặc None.
        if "reply_to" in header and header["reply_to"] is not None:
            if not isinstance(header["reply_to"], dict):
                return False, "Trường 'reply_to' không đúng định dạng JSON object"
        if "forward_from" in header and header["forward_from"] is not None:
            if not isinstance(header["forward_from"], dict):
                return False, "Trường 'forward_from' không đúng định dạng JSON object"
        if "sender_port" in header and header["sender_port"] is not None:
            sp = header["sender_port"]
            if not _is_int(sp) or sp < 0 or sp > 65535:
                return False, "Trường 'sender_port' không hợp lệ"

    elif msg_type == "file_start":
        for req in ["file_id", "file_name", "file_size", "total_chunks", "file_hash"]:
            if req not in header:
                return False, f"file_start thiếu trường bắt buộc: {req}"
        if not isinstance(header["file_name"], str) or not header["file_name"].strip():
            return False, "Tên file không hợp lệ"
        if not _is_int(header["file_size"]) or not _is_int(header["total_chunks"]):
            return False, "Thông số kích thước hoặc số lượng chunk phải là số nguyên"
        if header["file_size"] < 0 or header["total_chunks"] <= 0:
            return False, "Thông số kích thước hoặc số lượng chunk file không hợp lệ"

    elif msg_type == "file_chunk":
        for req in ["file_id", "chunk_index", "chunk_size", "chunk_hash"]:
            if req not in header:
                return False, f"file_chunk thiếu trường bắt buộc: {req}"
        if not _is_int(header["chunk_index"]) or not _is_int(header["chunk_size"]):
            return False, "Chỉ số chunk hoặc kích thước chunk phải là số nguyên"
        if header["chunk_index"] < 0 or header["chunk_size"] < 0:
            return False, "Chỉ số chunk hoặc kích thước chunk không hợp lệ"

    return True, "OK"


def verify_checksum(data: bytes, expected_sha256: str) -> bool:
    """Xác thực mã băm SHA-256 của khối dữ liệu."""
    if not expected_sha256 or not isinstance(expected_sha256, str):
        return False
    computed = hashlib.sha256(data).hexdigest()
    return computed.lower() == expected_sha256.lower()
