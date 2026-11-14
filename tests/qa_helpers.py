"""Cong cu QA dung chung (TV1, Chang 5).

- validate_message(): kiem tra thong diep theo message_protocol.md cua nhom.
  Dung duoc voi thong diep that do code cua cac thanh vien tao ra.
- Ham tao thong diep mau: text/emoji/reply/forward.
- send_file / recv_file / transfer: truyen file chia chunk, ma hoa tung chunk, gui da luong.
- make_png / png_size: tao va kiem tra anh PNG (avatar).
"""
import base64
import binascii
import copy
import json
import random
import re
import socket
import struct
import threading
import uuid
import zlib
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "CODE"))

from security.handshake import (  # noqa: E402
    handshake_initiator,
    handshake_responder,
    make_message,
    recv_frame,
    recv_secure,
    send_frame,
    send_secure,
)

# ------------------------------------------------------------------ kiem tra theo giao thuc
SUPPORTED_TYPES = {"TEXT", "EMOJI", "REPLY", "FORWARD", "FILE", "KEY_EXCHANGE"}
FORWARDABLE_TYPES = {"TEXT", "EMOJI", "REPLY"}
FILE_ACTIONS = {"OFFER", "ACCEPT", "REJECT", "COMPLETE", "ERROR"}
KEY_ACTIONS = {"PUBLIC_KEY", "SESSION_KEY", "KEY_CONFIRM"}
FORBIDDEN_FIELDS = {"private_key", "password", "session_key", "aes_key"}
_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def _is_str(value):
    return isinstance(value, str) and value != ""


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_uuid(value):
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _walk_keys(value):
    if isinstance(value, dict):
        for key, sub in value.items():
            yield str(key)
            yield from _walk_keys(sub)
    elif isinstance(value, list):
        for sub in value:
            yield from _walk_keys(sub)


def validate_message(msg):
    """Tra ve danh sach loi (rong = hop le) theo message_protocol.md."""
    if not isinstance(msg, dict):
        return ["thong diep khong phai object"]
    header, payload = msg.get("header"), msg.get("payload")
    errors = []
    if not isinstance(header, dict):
        errors.append("thieu header")
    if not isinstance(payload, dict):
        errors.append("thieu payload")
    if errors:
        return errors
    for name in ("message_id", "message_type", "sender_id", "receiver_id", "timestamp"):
        if not _is_str(header.get(name)):
            errors.append(f"header.{name} thieu hoac khong phai chuoi")
    if errors:
        return errors
    if not _is_uuid(header["message_id"]):
        errors.append("message_id khong phai UUID")
    if not _TS.match(header["timestamp"]):
        errors.append("timestamp khong theo UTC dang YYYY-MM-DDTHH:MM:SSZ")
    for name in ("sender_id", "receiver_id"):
        if _IPV4.match(header[name]):
            errors.append(f"{name} khong duoc la dia chi IP")
    mtype = header["message_type"]
    if mtype not in SUPPORTED_TYPES:
        return errors + [f"message_type khong ho tro: {mtype}"]
    errors += _check_payload(mtype, header, payload)
    bad = FORBIDDEN_FIELDS & {key.lower() for key in _walk_keys(payload)}
    if bad:
        errors.append(f"payload chua truong bi mat: {sorted(bad)}")
    return errors


def _check_payload(mtype, header, payload):
    errors = []
    if mtype == "TEXT":
        if not _is_str(payload.get("text")):
            errors.append("TEXT thieu text")
    elif mtype == "EMOJI":
        if not _is_str(payload.get("emoji")):
            errors.append("EMOJI thieu emoji")
    elif mtype == "REPLY":
        ref = payload.get("reply_to_message_id")
        if not _is_uuid(ref):
            errors.append("REPLY thieu hoac sai reply_to_message_id")
        elif ref == header["message_id"]:
            errors.append("REPLY khong duoc tra loi chinh no")
        if not _is_str(payload.get("text")):
            errors.append("REPLY thieu text")
    elif mtype == "FORWARD":
        for name in ("original_message_id", "original_sender_id", "original_message_type"):
            if not _is_str(payload.get(name)):
                errors.append(f"FORWARD thieu {name}")
        if not isinstance(payload.get("original_payload"), dict):
            errors.append("FORWARD thieu original_payload")
        if _is_str(payload.get("original_message_id")):
            if not _is_uuid(payload["original_message_id"]):
                errors.append("original_message_id khong phai UUID")
            elif payload["original_message_id"] == header["message_id"]:
                errors.append("FORWARD phai co message_id moi")
        if payload.get("original_message_type") not in FORWARDABLE_TYPES:
            errors.append("original_message_type khong duoc phep chuyen tiep")
    elif mtype == "FILE":
        errors += _check_file(payload)
    elif mtype == "KEY_EXCHANGE":
        errors += _check_key_exchange(payload)
    return errors


def _check_file(payload):
    action = payload.get("action")
    errors = []
    if action not in FILE_ACTIONS:
        errors.append(f"FILE.action khong hop le: {action!r}")
    if not _is_str(payload.get("transfer_id")):
        errors.append("FILE thieu transfer_id")
    if action != "OFFER":
        return errors
    name = payload.get("file_name")
    if not _is_str(name) or any(ch in name for ch in "/\\\0") or name in {".", ".."}:
        errors.append("file_name phai la ten tep, khong chua duong dan")
    size, chunk, total = payload.get("file_size"), payload.get("chunk_size"), payload.get("total_chunks")
    if not all(_is_int(v) for v in (size, chunk, total)):
        return errors + ["file_size, chunk_size, total_chunks phai la so nguyen"]
    if size < 0:
        errors.append("file_size am")
    if not 4096 <= chunk <= 65536:
        errors.append("chunk_size ngoai khoang 4 KB den 64 KB")
    elif size >= 0 and total != max(1, -(-size // chunk)):
        errors.append("total_chunks khong khop file_size va chunk_size")
    return errors


def _check_key_exchange(payload):
    action = payload.get("action")
    if action not in KEY_ACTIONS:
        return [f"KEY_EXCHANGE.action khong hop le: {action!r}"]
    errors = []
    if action == "PUBLIC_KEY":
        for name in ("algorithm", "key_id", "public_key"):
            if not _is_str(payload.get(name)):
                errors.append(f"PUBLIC_KEY thieu {name}")
    elif action == "SESSION_KEY":
        for name in ("algorithm", "key_id"):
            if not _is_str(payload.get(name)):
                errors.append(f"SESSION_KEY thieu {name}")
        try:
            base64.b64decode(payload.get("encrypted_session_key", ""), validate=True)
            if not payload.get("encrypted_session_key"):
                raise binascii.Error
        except (binascii.Error, ValueError, TypeError):
            errors.append("SESSION_KEY thieu hoac sai base64 encrypted_session_key")
    return errors


# ------------------------------------------------------------------ tao thong diep mau
def text_msg(sender, receiver, text):
    return make_message("TEXT", sender, receiver, {"text": text})


def emoji_msg(sender, receiver, emoji):
    return make_message("EMOJI", sender, receiver, {"emoji": emoji})


def reply_msg(sender, receiver, original_id, text):
    return make_message("REPLY", sender, receiver, {"reply_to_message_id": original_id, "text": text})


def forward_msg(sender, receiver, original):
    """Chuyen tiep. Neu `original` da la FORWARD thi giu nguyen tin GOC dau tien."""
    header, payload = original["header"], original["payload"]
    if header["message_type"] == "FORWARD":
        body = copy.deepcopy(payload)
    else:
        body = {
            "original_message_id": header["message_id"],
            "original_message_type": header["message_type"],
            "original_sender_id": header["sender_id"],
            "original_payload": copy.deepcopy(payload),
        }
    return make_message("FORWARD", sender, receiver, body)


# ------------------------------------------------------------------ ket noi bao mat de test
Link = namedtuple("Link", "sock_a sess_a sock_b sess_b")


def secure_pair(key_a, key_b, ids=("peer-A", "peer-B"), socks=None):
    """Bat tay that giua 2 dau (initiator = A). socks=(sa, sb) neu muon tu cap socket."""
    sa, sb = socks or socket.socketpair()
    sa.settimeout(15)
    sb.settimeout(15)
    out = {}
    thread = threading.Thread(
        target=lambda: out.__setitem__("b", handshake_responder(sb, key_b, ids[1])), daemon=True)
    thread.start()
    result_a = handshake_initiator(sa, key_a, ids[0], ids[1])
    thread.join(10)
    return Link(sa, result_a.session, sb, out["b"].session)


# ------------------------------------------------------------------ truyen file
class TransferError(Exception):
    """Truyen file that bai (thieu chunk, sai kich thuoc, OFFER sai...)."""


def send_file(sock, session, my_id, peer_id, data, name="file.bin", chunk_size=16384, threads=4,
              tamper_index=None, drop_index=None, crypto_transfer_id=None):
    parts = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)] or [b""]
    total = len(parts)
    tid = str(uuid.uuid4())
    crypto = session.chunk_crypto(crypto_transfer_id or tid, total, sending=True)
    send_secure(sock, session, make_message("FILE", my_id, peer_id, {
        "action": "OFFER", "transfer_id": tid, "file_name": name, "file_size": len(data),
        "chunk_size": chunk_size, "total_chunks": total}))
    order = list(range(total))
    random.Random(7).shuffle(order)
    lock = threading.Lock()

    def task(i):
        if i == drop_index:
            return
        blob = crypto.encrypt_chunk(i, parts[i])
        if i == tamper_index:
            blob = bytes([blob[0] ^ 1]) + blob[1:]
        body = json.dumps({"action": "CHUNK", "transfer_id": tid, "index": i,
                           "data": base64.b64encode(blob).decode("ascii")}).encode()
        with lock:
            send_frame(sock, body)

    with ThreadPoolExecutor(threads) as pool:
        list(pool.map(task, order))
    return tid


def recv_file(sock, session):
    offer = recv_secure(sock, session)
    errors = validate_message(offer)
    if errors:
        raise TransferError("OFFER sai: " + "; ".join(errors))
    payload = offer["payload"]
    if payload["action"] != "OFFER":
        raise TransferError("mong doi OFFER")
    tid, total = payload["transfer_id"], payload["total_chunks"]
    crypto = session.chunk_crypto(tid, total, sending=False)
    parts = {}
    try:
        while len(parts) < total:
            msg = json.loads(recv_frame(sock).decode("utf-8"))
            if msg.get("transfer_id") != tid:
                raise TransferError("sai transfer_id")
            parts[msg["index"]] = crypto.decrypt_chunk(msg["index"], base64.b64decode(msg["data"]))
    except ConnectionError as exc:
        raise TransferError("thieu chunk, ket noi da dong") from exc
    data = b"".join(parts[i] for i in range(total))
    if len(data) != payload["file_size"]:
        raise TransferError("sai kich thuoc file")
    return payload["file_name"], data


def transfer(link, data, close_sender=False, **kwargs):
    """Gui tu A sang B (gui o luong rieng, nhan o luong chinh). Tra ve (ten, du lieu)."""
    errors = {}

    def run():
        try:
            send_file(link.sock_a, link.sess_a, "peer-A", "peer-B", data, **kwargs)
        except Exception as exc:  # noqa: BLE001
            errors["send"] = exc
        finally:
            if close_sender:
                link.sock_a.close()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    result, recv_error = None, None
    try:
        result = recv_file(link.sock_b, link.sess_b)
    except Exception as exc:  # noqa: BLE001
        recv_error = exc
        link.sock_b.close()          # bao ben gui dung lai, tranh ben gui bi treo vi bo dem day
    thread.join(15)
    if recv_error is not None:       # loi cua ben nhan luon duoc uu tien
        raise recv_error
    if "send" in errors:
        raise errors["send"]
    return result


# ------------------------------------------------------------------ anh PNG (avatar)
_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def make_png(size=32, seed=0):
    rnd = random.Random(seed)
    raw = b"".join(b"\x00" + bytes(rnd.getrandbits(8) for _ in range(size * 3)) for _ in range(size))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    return (_PNG_SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def png_size(data):
    """(rong, cao) neu la PNG hop le (dung chu ky, CRC tung khoi, ket thuc bang IEND), nguoc lai None."""
    if not data.startswith(_PNG_SIG):
        return None
    pos, dims = 8, None
    while pos + 12 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + length]
        crc = data[pos + 8 + length:pos + 12 + length]
        if len(body) != length or len(crc) != 4:
            return None
        if zlib.crc32(kind + body) & 0xFFFFFFFF != struct.unpack(">I", crc)[0]:
            return None
        if dims is None:
            if kind != b"IHDR":
                return None
            dims = struct.unpack(">II", body[:8])
        if kind == b"IEND":
            return dims if pos + 12 + length == len(data) else None
        pos += 12 + length
    return None