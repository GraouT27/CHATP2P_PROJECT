import json
import struct
import uuid
from datetime import datetime, timedelta, timezone

MAX_MESSAGE_SIZE = 1024 * 1024
HEADER_FIELDS = ("message_id", "message_type", "sender_id", "receiver_id", "timestamp")



def validate_uuid(value, field_name):
    """Kiểm tra giá trị là UUID hợp lệ."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} phải là UUID hợp lệ")

    try:
        uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError(
            f"{field_name} phải là UUID hợp lệ"
        ) from exc
    
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
        validate_uuid(header["message_id"], "message_id")
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

    message_type = header["message_type"]
    if message_type == "FILE":
        raise ValueError("Loại file phải có dạng FILE_<ACTION>")
    if message_type.startswith("FILE_"):
        action = message_type.removeprefix("FILE_")
        if not action or payload.get("action") != action:
            raise ValueError("payload.action phải khớp với FILE_<ACTION>")

    if message_type == "REPLY":
        validate_uuid(
            payload.get("reply_to"),
            "reply_to"
        )

        if not isinstance(payload.get("text"), str):
            raise ValueError("REPLY thiếu hoặc sai text")

        if not payload["text"].strip():
            raise ValueError("REPLY text không được rỗng")

        if uuid.UUID(payload["reply_to"]) == uuid.UUID(header["message_id"]):
            raise ValueError(
                "REPLY không được tham chiếu chính nó"
            )

    if message_type == "FORWARD":
        forwarded_from = payload.get("forwarded_from")

        if not isinstance(forwarded_from, str) or not forwarded_from.strip():
            raise ValueError("FORWARD thiếu forwarded_from")

        validate_uuid(
            payload.get("original_message_id"),
            "original_message_id"
        )

        original_type = payload.get("original_message_type")

        if original_type not in ("TEXT", "EMOJI"):
            raise ValueError(
                "FORWARD chỉ hỗ trợ TEXT hoặc EMOJI"
            )

        original_payload = payload.get("original_payload")

        if not isinstance(original_payload, dict):
            raise ValueError(
                "FORWARD original_payload phải là object"
            )

        required = "text" if original_type == "TEXT" else "emoji"

        if not isinstance(original_payload.get(required), str):
            raise ValueError(
                f"FORWARD thiếu hoặc sai original_payload.{required}"
            )

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


def create_reply_message(sender_id, receiver_id, reply_to, text):
    """Tạo thông điệp trả lời."""
    return create_message(
        sender_id,
        receiver_id,
        "REPLY",
        {
            "reply_to": reply_to,
            "text": text
        }
    )


def create_forward_message(
    sender_id,
    receiver_id,
    forwarded_from,
    original_message_id,
    original_message_type,
    original_payload
):
    """Tạo thông điệp chuyển tiếp."""
    return create_message(
        sender_id,
        receiver_id,
        "FORWARD",
        {
            "forwarded_from": forwarded_from,
            "original_message_id": original_message_id,
            "original_message_type": original_message_type,
            "original_payload": original_payload.copy()
        }
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
