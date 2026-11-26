"""Peer gia lap goi lien tuc du lieu lon cho den khi bi kill (TV1, Chang 6).

Chay: python tests/resilience_peer.py <port>
Bat tay xong in 'READY', roi gui vo han cac thong diep 60 KB (luon o giua mot khung khi bi kill).
"""
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "CODE"))

from security.crypto import KeyPair  # noqa: E402
from security.handshake import handshake_initiator, make_message, send_secure  # noqa: E402


def main() -> None:
    with socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=10) as sock:
        result = handshake_initiator(sock, KeyPair.generate(), "peer-bulk", "hub")
        sock.settimeout(None)
        print("READY", flush=True)
        message = make_message("FILE", "peer-bulk", "hub", {"action": "CHUNK", "data": "x" * 60_000})
        while True:
            send_secure(sock, result.session, message)


if __name__ == "__main__":
    main()