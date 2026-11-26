"""May chu mau xu ly loi day du (TV1, Chang 6) - khuon mau cho code Socket cua nhom.

Chay: python tests/resilience_hub.py [thoi_gian_cho_bat_tay_giay]
In 'PORT <so>' khi san sang, roi moi ket noi dong lai in 'CLOSED reason=<ly_do>'.
Moi ket noi mot luong; mot ket noi hong KHONG duoc lam sap may chu va PHAI duoc dong sach.
"""
import socket
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "CODE"))

from logger import Event, log_event  # noqa: E402
from security.crypto import CryptoError, DecryptError, KeyPair  # noqa: E402
from security.handshake import HandshakeError, handshake_responder, make_message, recv_secure, send_secure  # noqa: E402
from security.netutil import enable_keepalive  # noqa: E402


_PRINT_LOCK = threading.Lock()


def emit(line: str) -> None:
    """Ghi nguyen mot dong mot lan (print tu nhieu luong co the dinh dong vao nhau)."""
    with _PRINT_LOCK:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


def serve_one(conn: socket.socket, keypair: KeyPair, handshake_timeout: float) -> None:
    reason, established = "unexpected", False
    try:
        enable_keepalive(conn)
        result = handshake_responder(conn, keypair, "hub", timeout=handshake_timeout)
        established = True
        while True:
            message = recv_secure(conn, result.session)
            header, payload = message["header"], message["payload"]
            if header.get("message_type") != "TEXT":
                continue                                    # loai thong diep khac: bo qua
            text = payload.get("text")
            if not isinstance(text, str):
                continue                                    # thieu/sai kieu truong: bo qua, khong sap
            reply = make_message("TEXT", "hub", str(header.get("sender_id", "?")), {"text": "echo: " + text})
            send_secure(conn, result.session, reply)
    except HandshakeError:
        reason = "bad_message" if established else "handshake_failed"
    except (ConnectionError, TimeoutError):                 # peer chet, rut mang (keepalive), RST
        reason = "peer_disconnected"
    except DecryptError:
        reason = "decrypt_fail"
    except CryptoError:
        reason = "protocol_error"
    except OSError:
        reason = "network_error"
    except Exception as exc:  # noqa: BLE001 - mot ket noi hong khong duoc lam sap ca may chu
        log_event(Event.ERROR, "ERROR", reason=type(exc).__name__)
    finally:
        try:
            conn.close()
        except OSError:
            pass
        emit(f"CLOSED reason={reason}")


def main() -> None:
    handshake_timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
    keypair = KeyPair.generate()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.bind(("127.0.0.1", 0))
        server.listen(64)
        emit(f"PORT {server.getsockname()[1]}")
        while True:
            conn, _ = server.accept()
            threading.Thread(target=serve_one, args=(conn, keypair, handshake_timeout), daemon=True).start()
    finally:
        server.close()


if __name__ == "__main__":
    main()