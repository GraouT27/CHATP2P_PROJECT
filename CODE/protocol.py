
"""Giao thức đóng gói dữ liệu nhị phân cho Chat P2P."""

import struct
import uuid
from dataclasses import dataclass

MAGIC = b"P2PC"
VERSION = 1
CHUNK_SIZE = 64 * 1024  # 64 KiB
MAX_PAYLOAD = CHUNK_SIZE

# magic(4), version(1), kind(1), UUID(16),
# index(4), total(4), payload_len(4) = 34 byte
HEADER = struct.Struct("!4sBB16sIII")
HEADER_SIZE = HEADER.size

MESSAGE = 1
FILE_META = 2
FILE_CHUNK = 3
AVATAR_META = 4
AVATAR_CHUNK = 5
CANCEL = 6


@dataclass
class Frame:
    kind: int
    transfer_id: uuid.UUID
    index: int
    total: int
    payload: bytes


def encode_frame(frame: Frame) -> bytes:
    """Ghép header và payload thành một frame."""
    if not isinstance(frame.payload, bytes):
        raise TypeError("Payload phải là bytes")

    if len(frame.payload) > MAX_PAYLOAD:
        raise ValueError("Payload vượt quá 64 KiB")

    if frame.total < 1 or not 0 <= frame.index < frame.total:
        raise ValueError("Index hoặc total không hợp lệ")

    if frame.kind not in {
        MESSAGE, FILE_META, FILE_CHUNK,
        AVATAR_META, AVATAR_CHUNK, CANCEL
    }:
        raise ValueError("Loại frame không hợp lệ")

    header = HEADER.pack(
        MAGIC,
        VERSION,
        frame.kind,
        frame.transfer_id.bytes,
        frame.index,
        frame.total,
        len(frame.payload),
    )

    return header + frame.payload


def recv_exact(sock, size: int) -> bytes:
    """Đọc chính xác size byte từ socket."""
    data = bytearray()

    while len(data) < size:
        part = sock.recv(size - len(data))

        if not part:
            raise ConnectionError("Peer đã ngắt kết nối")

        data.extend(part)

    return bytes(data)


def recv_frame(sock) -> Frame:
    """Đọc một frame hoàn chỉnh từ TCP."""
    raw_header = recv_exact(sock, HEADER_SIZE)

    magic, version, kind, transfer_bytes, index, total, length = (
        HEADER.unpack(raw_header)
    )

    if magic != MAGIC or version != VERSION:
        raise ValueError("Sai định dạng hoặc phiên bản giao thức")

    if kind not in {
        MESSAGE, FILE_META, FILE_CHUNK,
        AVATAR_META, AVATAR_CHUNK, CANCEL
    }:
        raise ValueError("Loại frame không hợp lệ")

    if total < 1 or not 0 <= index < total:
        raise ValueError("Index hoặc total không hợp lệ")

    if length > MAX_PAYLOAD:
        raise ValueError("Payload vượt quá 64 KiB")

    payload = recv_exact(sock, length)

    return Frame(
        kind=kind,
        transfer_id=uuid.UUID(bytes=transfer_bytes),
        index=index,
        total=total,
        payload=payload,
    )


def split_bytes(data: bytes) -> list[bytes]:
    """Chia dữ liệu thành các chunk tối đa 64 KiB."""
    if not data:
        return [b""]

    return [
        data[i:i + CHUNK_SIZE]
        for i in range(0, len(data), CHUNK_SIZE)
    ]
