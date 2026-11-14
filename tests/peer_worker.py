"""Tien trinh peer gia lap de kiem thu nhieu tien trinh Python cung luc (TV1, Chang 4).

Chay: python tests/peer_worker.py listen  <my_id> <log_dir>
      python tests/peer_worker.py connect <my_id> <log_dir> <port>

Moi peer: bat tay RSA -> trao doi emoji (da ma hoa) -> gui/nhan avatar (PNG) bang cach
chia chunk, ma hoa tung chunk (ChunkCrypto), gui bang nhieu luong, thu tu xao tron.
Cuoi cung in 1 dong 'RESULT {...}' va thoat ma 0 neu moi thu dung.
"""
import base64
import hashlib
import json
import random
import socket
import struct
import sys
import threading
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "CODE"))

from logger import setup_logging, shutdown_logging  # noqa: E402
from security.crypto import KeyPair  # noqa: E402
from security.handshake import (  # noqa: E402
    handshake_initiator,
    handshake_responder,
    make_message,
    recv_frame,
    recv_secure,
    send_frame,
    send_secure,
)

EMOJIS = [
    "😀", "😂", "❤️", "👍🏽", "👨‍👩‍👧‍👦", "🇻🇳", "🙂" * 50,
    "Xin chào 😀 tiếng Việt có dấu", "Cờ 🇻🇳 và pháo 🎆", "\u200d\ufe0f",
]
CHUNK = 4096
THREADS = 4
TIMEOUT = 20


def make_avatar(peer_id: str, size: int = 64) -> bytes:
    """PNG hop le, noi dung xac dinh theo peer_id (ben nhan tu tinh lai de doi chieu)."""
    seed = int.from_bytes(hashlib.sha256(peer_id.encode()).digest()[:4], "big")
    rnd = random.Random(seed)
    raw = b"".join(b"\x00" + bytes(rnd.getrandbits(8) for _ in range(size * 3)) for _ in range(size))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))


def send_emojis(sock, session, my_id, peer_id):
    for emoji in EMOJIS:
        send_secure(sock, session, make_message("EMOJI", my_id, peer_id, {"emoji": emoji}))


def recv_emojis(sock, session):
    got = [recv_secure(sock, session)["payload"]["emoji"] for _ in EMOJIS]
    return got == EMOJIS


def send_avatar(sock, session, my_id, peer_id):
    png = make_avatar(my_id)
    parts = [png[i:i + CHUNK] for i in range(0, len(png), CHUNK)]
    tid = "avatar-" + my_id
    crypto = session.chunk_crypto(tid, len(parts), sending=True)
    send_secure(sock, session, make_message("FILE", my_id, peer_id, {
        "action": "OFFER", "transfer_id": tid, "file_name": "avatar.png",
        "file_size": len(png), "chunk_size": CHUNK, "total_chunks": len(parts)}))
    order = list(range(len(parts)))
    random.Random(1).shuffle(order)          # gui sai thu tu co chu y
    lock = threading.Lock()

    def task(i):
        blob = crypto.encrypt_chunk(i, parts[i])
        body = json.dumps({"action": "CHUNK", "transfer_id": tid, "index": i,
                           "data": base64.b64encode(blob).decode("ascii")}).encode()
        with lock:
            send_frame(sock, body)

    with ThreadPoolExecutor(THREADS) as pool:
        list(pool.map(task, order))


def recv_avatar(sock, session, sender_id):
    offer = recv_secure(sock, session)["payload"]
    total, size, tid = offer["total_chunks"], offer["file_size"], offer["transfer_id"]
    crypto = session.chunk_crypto(tid, total, sending=False)
    parts = {}
    for _ in range(total):
        msg = json.loads(recv_frame(sock).decode("utf-8"))
        if msg["transfer_id"] != tid:
            raise ValueError("sai transfer_id")
        parts[msg["index"]] = crypto.decrypt_chunk(msg["index"], base64.b64decode(msg["data"]))
    png = b"".join(parts[i] for i in range(total))
    expected = make_avatar(sender_id)
    return png.startswith(b"\x89PNG\r\n\x1a\n") and len(png) == size and png == expected, len(png)


def main():
    role, my_id, log_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    setup_logging(log_dir)
    keypair = KeyPair.generate()
    if role == "listen":
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        srv.settimeout(TIMEOUT)
        print("PORT", srv.getsockname()[1], flush=True)
        conn, _ = srv.accept()
        conn.settimeout(TIMEOUT)
        res = handshake_responder(conn, keypair, my_id)
    else:
        conn = socket.create_connection(("127.0.0.1", int(sys.argv[4])), timeout=TIMEOUT)
        res = handshake_initiator(conn, keypair, my_id, "")
    session, peer = res.session, res.peer_id

    if role == "connect":
        send_emojis(conn, session, my_id, peer)
        emoji_ok = recv_emojis(conn, session)
        send_avatar(conn, session, my_id, peer)
        avatar_ok, size = recv_avatar(conn, session, peer)
    else:
        emoji_ok = recv_emojis(conn, session)
        send_emojis(conn, session, my_id, peer)
        avatar_ok, size = recv_avatar(conn, session, peer)
        send_avatar(conn, session, my_id, peer)

    print("RESULT", json.dumps({
        "id": my_id, "peer_id": peer, "emoji_ok": emoji_ok, "avatar_ok": avatar_ok,
        "avatar_bytes": size, "fingerprint": keypair.fingerprint(),
        "peer_fingerprint": res.peer_fingerprint}), flush=True)
    conn.close()
    shutdown_logging()
    return 0 if emoji_ok and avatar_ok else 1


if __name__ == "__main__":
    sys.exit(main())