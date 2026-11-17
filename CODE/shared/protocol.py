"""
Protocol Module - Đóng gói & Bóc tách khung bản tin P2P (TV4).

Cấu trúc khung bản tin (Message Framing):
┌───────────────────────────┬────────────────────────────┬────────────────────────────┐
│ 4 Bytes Header Length     │ JSON Header (UTF-8)        │ Payload nhị phân / chunk   │
│ (unsigned int, big-endian)│ (msg_id, type, sender, ...)│ (kích thước = payload_size)│
└───────────────────────────┴────────────────────────────┴────────────────────────────┘
"""

import struct
import json
import uuid
import time
import socket
from typing import Tuple, Optional

# Giới hạn kích thước header tối đa để chống DoS
MAX_HEADER_SIZE = 1024 * 1024  # 1 MB


def pack_message(header: dict, payload: bytes = b"") -> bytes:
    """
    Đóng gói bản tin thành mảng bytes có tiền tố 4 bytes chỉ độ dài JSON Header:
    [4 bytes Header Length] + [JSON Header] + [Payload]
    """
    header["payload_size"] = len(payload)
    if "msg_id" not in header:
        header["msg_id"] = str(uuid.uuid4())
    if "timestamp" not in header:
        header["timestamp"] = time.time()

    header_bytes = json.dumps(header, ensure_ascii=False).encode("utf-8")
    header_len = len(header_bytes)
    prefix = struct.pack("!I", header_len)
    return prefix + header_bytes + payload


def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """
    Đọc chính xác số bytes yêu cầu từ socket.
    Ném lỗi ConnectionResetError nếu đối tác đóng kết nối đột ngột giữa chừng.
    """
    data = bytearray()
    while len(data) < num_bytes:
        packet = sock.recv(num_bytes - len(data))
        if not packet:
            raise ConnectionResetError("Đối tác đã ngắt kết nối đột ngột")
        data.extend(packet)
    return bytes(data)


def read_message(sock: socket.socket) -> Tuple[dict, bytes]:
    """
    Đọc 1 bản tin hoàn chỉnh từ socket theo định dạng khung phân định:
    Trả về (header_dict, payload_bytes).
    """
    # 1. Đọc 4 bytes header length
    raw_len = recv_exact(sock, 4)
    (header_len,) = struct.unpack("!I", raw_len)

    if header_len > MAX_HEADER_SIZE:
        raise ValueError(f"Header quá lớn vượt ngưỡng cho phép: {header_len} bytes")

    # 2. Đọc JSON Header
    header_bytes = recv_exact(sock, header_len)
    header = json.loads(header_bytes.decode("utf-8"))

    # 3. Đọc Payload nhị phân nếu có
    payload_size = header.get("payload_size", 0)
    payload = b""
    if payload_size > 0:
        payload = recv_exact(sock, payload_size)

    return header, payload


# ========================== BUILDER TIỆN ÍCH CHO HEADER ==========================

def make_handshake_header(username: str, listen_port: int, rsa_public_key: str, avatar_b64: str = "") -> dict:
    return {
        "msg_id": str(uuid.uuid4()),
        "type": "handshake",
        "sender": username,
        "listen_port": listen_port,
        "rsa_public_key": rsa_public_key,
        "avatar_b64": avatar_b64,
        "timestamp": time.time(),
    }


def make_handshake_ack_header(username: str, rsa_public_key: str, avatar_b64: str = "", listen_port: int = 0) -> dict:
    return {
        "msg_id": str(uuid.uuid4()),
        "type": "handshake_ack",
        "sender": username,
        "listen_port": listen_port,
        "rsa_public_key": rsa_public_key,
        "avatar_b64": avatar_b64,
        "timestamp": time.time(),
    }


def make_key_exchange_header(username: str, encrypted_key: str, listen_port: int = 0) -> dict:
    return {
        "msg_id": str(uuid.uuid4()),
        "type": "key_exchange",
        "sender": username,
        "listen_port": listen_port,
        "encrypted_key": encrypted_key,
        "timestamp": time.time(),
    }


def make_chat_header(username: str, text: str = "", reply_to: dict = None,
                     forward_from: dict = None, is_encrypted: bool = False,
                     nonce: str = None) -> dict:
    header = {
        "msg_id": str(uuid.uuid4()),
        "type": "chat",
        "sender": username,
        "text": text,
        "is_encrypted": is_encrypted,
        "nonce": nonce,
        "timestamp": time.time(),
    }
    if reply_to:
        header["reply_to"] = reply_to
    if forward_from:
        header["forward_from"] = forward_from
    return header


def make_file_start_header(username: str, file_id: str, file_name: str,
                           file_size: int, total_chunks: int, file_hash: str) -> dict:
    return {
        "msg_id": str(uuid.uuid4()),
        "type": "file_start",
        "sender": username,
        "file_id": file_id,
        "file_name": file_name,
        "file_size": file_size,
        "total_chunks": total_chunks,
        "file_hash": file_hash,
        "timestamp": time.time(),
    }


def make_file_chunk_header(username: str, file_id: str, chunk_index: int,
                           chunk_size: int, chunk_hash: str,
                           is_encrypted: bool = False, nonce: str = None) -> dict:
    return {
        "msg_id": str(uuid.uuid4()),
        "type": "file_chunk",
        "sender": username,
        "file_id": file_id,
        "chunk_index": chunk_index,
        "chunk_size": chunk_size,
        "chunk_hash": chunk_hash,
        "is_encrypted": is_encrypted,
        "nonce": nonce,
        "timestamp": time.time(),
    }


def make_file_ack_header(username: str, file_id: str, chunk_index: int) -> dict:
    return {
        "msg_id": str(uuid.uuid4()),
        "type": "file_ack",
        "sender": username,
        "file_id": file_id,
        "chunk_index": chunk_index,
        "timestamp": time.time(),
    }


def make_file_cancel_header(username: str, file_id: str, reason: str = "") -> dict:
    return {
        "msg_id": str(uuid.uuid4()),
        "type": "file_cancel",
        "sender": username,
        "file_id": file_id,
        "reason": reason,
        "timestamp": time.time(),
    }


def make_ping_header(username: str) -> dict:
    return {
        "msg_id": str(uuid.uuid4()),
        "type": "ping",
        "sender": username,
        "timestamp": time.time(),
    }


def make_pong_header(username: str) -> dict:
    return {
        "msg_id": str(uuid.uuid4()),
        "type": "pong",
        "sender": username,
        "timestamp": time.time(),
    }
