import json
import struct
import uuid
from datetime import datetime, timedelta, timezone

MAX_MESSAGE_SIZE = 1024 * 1024
HEADER_FIELDS = ("message_id", "message_type", "sender_id", "receiver_id", "timestamp")


def validate_message(message):
    """Kiểm tra phần chung của message và payload TEXT/EMOJI."""
    if not isinstance(message, dict):
        raise ValueError("Message phải là object")

    header = message.get("header")
    if not isinstance(header, dict):
        raise ValueError("Header phải là object")

    for field in HEADER_FIELDS:
        value = header.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Header thiếu hoặc sai {field}")

    try:
        uuid.UUID(header["message_id"])
        timestamp = datetime.fromisoformat(header["timestamp"])
    except ValueError as exc:
        raise ValueError("message_id hoặc timestamp không hợp lệ") from exc

    if timestamp.utcoffset() != timedelta(0):
        raise ValueError("timestamp phải ở múi giờ UTC")

    payload = message.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Payload phải là object")

    required_field = {"TEXT": "text", "EMOJI": "emoji"}.get(
        header["message_type"]
    )
    if required_field is not None and not isinstance(
        payload.get(required_field), str
    ):
        raise ValueError(f"Payload thiếu hoặc sai {required_field}")

    return None

def create_message(sender_id, receiver_id, message_type, payload):
    message = {
        "header": {
            "message_id": str(uuid.uuid4()),
            "message_type": message_type,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        },

        "payload": payload
    }

    validate_message(message)
    return message

def create_text_message(sender_id, receiver_id, text):

    return create_message (
        sender_id,
        receiver_id,
        "TEXT",
        {"text": text}
    )



def encode_message(message):
    validate_message(message)
    json_text = json.dumps(message, ensure_ascii=False)
    payload = json_text.encode("utf-8")

    if len(payload) > MAX_MESSAGE_SIZE:
        raise ValueError("Message quá lớn !")

    length_prefix = struct.pack("!I", len(payload))

    return length_prefix + payload

def decode_message(data):
    if not isinstance(data, bytes) or not data or len(data) > MAX_MESSAGE_SIZE:
        raise ValueError("Dữ liệu message không hợp lệ")
    try:
        message = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Message không phải JSON UTF-8 hợp lệ") from exc
    validate_message(message)
    return message

def recv_exact(sock, n):
    chunks = []
    bytes_received = 0

    while bytes_received < n:
        chunk = sock.recv(n - bytes_received)

        if not chunk:
            raise ConnectionError("Peer đã ngắt kết nối !")

        chunks.append(chunk)
        bytes_received += len(chunk)

    return b"".join(chunks)

def recv_message(sock):
    prefix = recv_exact(sock, 4)

    message_length = struct.unpack("!I", prefix)[0]

    if message_length == 0 or message_length > MAX_MESSAGE_SIZE:
        raise ValueError("Độ dài message không hợp lệ !")

    data = recv_exact(sock, message_length)

    return decode_message(data)
