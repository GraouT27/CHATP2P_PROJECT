import json
import uuid
from datetime import datetime, timezone
import struct

MAX_MESSAGE_SIZE = 1024 * 1024 

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

    return message

def create_text_message(sender_id, receiver_id, text):

    return create_message (
        sender_id,
        receiver_id,
        "TEXT",
        {"text": text}
    )



def encode_message(message):
    json_text = json.dumps(message, ensure_ascii= False)
    payload = json_text.encode("utf-8")

    if len(payload) > MAX_MESSAGE_SIZE:
        raise ValueError("Message quá lớn !")

    length_prefix = struct.pack("!I", len(payload))

    return length_prefix + payload 

def decode_message(data):
    json_text = data.decode("utf-8")
    message = json.loads(json_text)
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

        

