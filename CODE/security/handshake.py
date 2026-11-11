"""Bat tay RSA + khoa phien AES-256 giua 2 peer (TV1, Chang 3).

Dung thong diep KEY_EXCHANGE cua giao thuc nhom (header + payload, JSON UTF-8)
va khung 4 byte do dai big-endian. Sau khi bat tay, moi khung deu duoc ma hoa
(SessionCrypto) va dung send_secure / recv_secure.

Luu y: confirm_peer chay GIUA luc bat tay nen phai tra loi NHANH (vi du so voi danh sach
khoa da biet). KHONG hoi nguoi dung trong confirm_peer vi ben kia dang cho va se het thoi gian.
De nguoi dung doi chieu van tay, hien result.peer_fingerprint SAU khi bat tay xong.

Cac ham bat tay la HAM CHAN (blocking): goi trong QThread/luong rieng, khong goi
tren luong giao dien. Ham khong tu dong dong socket khi loi, noi goi tu quyet dinh.
"""
import json
import secrets
import socket
import struct
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

from logger import Event, log_event

from .crypto import (
    CryptoError,
    KeyPair,
    SessionCrypto,
    encrypt_session_key,
    fingerprint_of_pem,
    handshake_salt,
    new_session_key,
)

MAX_FRAME_SIZE = 1024 * 1024   # 1 MiB
DEFAULT_TIMEOUT = 5.0          # giay


class FrameError(CryptoError):
    """Khung du lieu sai do dai hoac ket noi dong giua chung."""


class ConnectionClosedError(FrameError, ConnectionError):
    """Doi phuong dong ket noi. La ConnectionError nen 'except ConnectionError' cua code cu van chay."""


class HandshakeError(CryptoError):
    """Bat tay that bai."""


@dataclass
class HandshakeResult:
    session: SessionCrypto
    session_id: str
    peer_id: str
    peer_fingerprint: str
    peer_key_id: str


# ------------------------------------------------------------- khung 4 byte
def _recv_exact(sock: socket.socket, count: int) -> bytes:
    chunks, remaining = [], count
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionClosedError("Ket noi dong giua chung")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def send_frame(sock: socket.socket, data: bytes) -> None:
    if len(data) > MAX_FRAME_SIZE:
        raise FrameError("Khung qua lon")
    sock.sendall(struct.pack(">I", len(data)) + data)


def recv_frame(sock: socket.socket) -> bytes:
    (length,) = struct.unpack(">I", _recv_exact(sock, 4))
    if length == 0 or length > MAX_FRAME_SIZE:
        raise FrameError("Do dai khung khong hop le")
    return _recv_exact(sock, length)


# --------------------------------------------------------- thong diep JSON
def make_message(message_type: str, sender_id: str, receiver_id: str, payload: dict) -> dict:
    return {
        "header": {
            "message_id": str(uuid.uuid4()),
            "message_type": message_type,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "payload": payload,
    }


def encode_message(message: dict) -> bytes:
    return json.dumps(message, ensure_ascii=False).encode("utf-8")


_HEADER_FIELDS = ("message_id", "message_type", "sender_id", "receiver_id", "timestamp")


def decode_message(data: bytes, strict: bool = True) -> dict:
    """strict=True kiem tra du 5 truong header (dung khi bat tay). Sau bat tay
    recv_secure dung strict=False, viec kiem tra chi tiet do shared/protocol lo."""
    try:
        message = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandshakeError("Thong diep sai dinh dang") from exc
    if not isinstance(message, dict):
        raise HandshakeError("Thong diep sai dinh dang")
    header, payload = message.get("header"), message.get("payload")
    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise HandshakeError("Thieu header hoac payload")
    if strict and any(not isinstance(header.get(name), str) for name in _HEADER_FIELDS):
        raise HandshakeError("Header thieu truong bat buoc")
    return message


def send_secure(sock: socket.socket, session: SessionCrypto, message: dict) -> None:
    """Ma hoa roi gui. Neu nhieu luong cung gui, dat ca ham nay trong 1 lock."""
    send_frame(sock, session.encrypt(encode_message(message)))


def recv_secure(sock: socket.socket, session: SessionCrypto) -> dict:
    """Nhan 1 khung, giai ma, tra ve thong diep (dict). Doi phuong dong ket noi -> ConnectionError,
    sai khoa/bi sua/phat lai -> DecryptError/ReplayError (deu la CryptoError)."""
    return decode_message(session.decrypt(recv_frame(sock)), strict=False)


# ------------------------------------------------------------- bat tay
def _short(fingerprint: str) -> str:
    return fingerprint.replace(" ", "")[:8].lower()


def _key_exchange(sender: str, receiver: str, payload: dict) -> bytes:
    return encode_message(make_message("KEY_EXCHANGE", sender, receiver, payload))


def _public_key_payload(keypair: KeyPair) -> dict:
    return {
        "action": "PUBLIC_KEY",
        "algorithm": "RSA-2048",
        "key_id": "key-" + keypair.short_id(),
        "public_key": keypair.public_pem(),
    }


def _expect(message: dict, action: str) -> dict:
    if message["header"]["message_type"] != "KEY_EXCHANGE" or message["payload"].get("action") != action:
        raise HandshakeError(f"Mong doi {action}")
    return message["payload"]


def _check_peer_key(pem, confirm_peer: Optional[Callable[[str], bool]]) -> str:
    if not isinstance(pem, str):
        raise HandshakeError("Thieu khoa cong khai")
    try:
        fingerprint = fingerprint_of_pem(pem)
    except CryptoError as exc:
        raise HandshakeError("Khoa cong khai khong hop le") from exc
    if confirm_peer is not None and not confirm_peer(fingerprint):
        raise HandshakeError("Nguoi dung tu choi khoa cua peer")
    return fingerprint


def _fail(session_id: str, role: str, exc: Exception) -> None:
    log_event(Event.HANDSHAKE_FAIL, "WARNING", session=session_id, role=role,
              reason=type(exc).__name__, detail=str(exc))


def _restore_timeout(sock: socket.socket, old) -> None:
    try:
        sock.settimeout(old)
    except OSError:
        pass


def handshake_initiator(sock: socket.socket, keypair: KeyPair, my_id: str, peer_id: str = "",
                        *, timeout: float = DEFAULT_TIMEOUT,
                        confirm_peer: Optional[Callable[[str], bool]] = None) -> HandshakeResult:
    """Ben goi (da connect). confirm_peer(fingerprint) -> bool de GUI hoi nguoi dung."""
    sid = secrets.token_hex(3)
    log_event(Event.HANDSHAKE_START, session=sid, role="initiator")
    old = sock.gettimeout()
    sock.settimeout(timeout)
    try:
        send_frame(sock, _key_exchange(my_id, peer_id, _public_key_payload(keypair)))
        reply = decode_message(recv_frame(sock))
        peer_payload = _expect(reply, "PUBLIC_KEY")
        peer_pem = peer_payload.get("public_key")
        fingerprint = _check_peer_key(peer_pem, confirm_peer)
        real_peer = reply["header"]["sender_id"] or peer_id

        key = new_session_key()
        send_frame(sock, _key_exchange(my_id, real_peer, {
            "action": "SESSION_KEY",
            "algorithm": "RSA-OAEP-SHA256",
            "key_id": str(peer_payload.get("key_id", "")),
            "encrypted_session_key": encrypt_session_key(peer_pem, key),
        }))
        session = SessionCrypto(key, True, handshake_salt(keypair.public_pem(), peer_pem))
        _expect(recv_secure(sock, session), "KEY_CONFIRM")
    except HandshakeError as exc:
        _fail(sid, "initiator", exc)
        raise
    except (CryptoError, OSError, ValueError, TypeError) as exc:
        _fail(sid, "initiator", exc)
        raise HandshakeError("Bat tay that bai") from exc
    finally:
        _restore_timeout(sock, old)
    log_event(Event.HANDSHAKE_OK, session=sid, peer=_short(fingerprint), role="initiator")
    return HandshakeResult(session, sid, real_peer, fingerprint, str(peer_payload.get("key_id", "")))


def handshake_responder(sock: socket.socket, keypair: KeyPair, my_id: str, *,
                        timeout: float = DEFAULT_TIMEOUT,
                        confirm_peer: Optional[Callable[[str], bool]] = None) -> HandshakeResult:
    """Ben nhan (da accept)."""
    sid = secrets.token_hex(3)
    log_event(Event.HANDSHAKE_START, session=sid, role="responder")
    old = sock.gettimeout()
    sock.settimeout(timeout)
    try:
        first = decode_message(recv_frame(sock))
        peer_payload = _expect(first, "PUBLIC_KEY")
        peer_pem = peer_payload.get("public_key")
        fingerprint = _check_peer_key(peer_pem, confirm_peer)
        peer_id = first["header"]["sender_id"]
        my_pem = keypair.public_pem()
        send_frame(sock, _key_exchange(my_id, peer_id, _public_key_payload(keypair)))

        wrapped = _expect(decode_message(recv_frame(sock)), "SESSION_KEY")
        key = keypair.decrypt_session_key(str(wrapped.get("encrypted_session_key", "")))
        session = SessionCrypto(key, False, handshake_salt(peer_pem, my_pem))
        send_secure(sock, session, make_message(
            "KEY_EXCHANGE", my_id, peer_id,
            {"action": "KEY_CONFIRM", "algorithm": "AES-256-GCM"}))
    except HandshakeError as exc:
        _fail(sid, "responder", exc)
        raise
    except (CryptoError, OSError, ValueError, TypeError) as exc:
        _fail(sid, "responder", exc)
        raise HandshakeError("Bat tay that bai") from exc
    finally:
        _restore_timeout(sock, old)
    log_event(Event.HANDSHAKE_OK, session=sid, peer=_short(fingerprint), role="responder")
    return HandshakeResult(session, sid, peer_id, fingerprint, str(peer_payload.get("key_id", "")))
