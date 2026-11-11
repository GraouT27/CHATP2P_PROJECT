"""Test bat tay RSA + AES giua 2 peer (CODE/security/handshake.py)."""
import json
import re
import socket
import struct
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "CODE"))

from logger import setup_logging, shutdown_logging  # noqa: E402
from security.crypto import KeyPair  # noqa: E402
from security.handshake import (  # noqa: E402
    FrameError,
    HandshakeError,
    decode_message,
    encode_message,
    handshake_initiator,
    handshake_responder,
    make_message,
    recv_frame,
    recv_secure,
    send_frame,
    send_secure,
)


@pytest.fixture(scope="module")
def keys():
    return KeyPair.generate(), KeyPair.generate()


@pytest.fixture
def pair():
    a, b = socket.socketpair()
    yield a, b
    a.close()
    b.close()


def run_both(sock_a, sock_b, key_a, key_b, init_kw=None, resp_kw=None):
    out = {}

    def init():
        try:
            out["a"] = handshake_initiator(sock_a, key_a, "peer_A", "peer_B", **(init_kw or {}))
        except Exception as exc:  # noqa: BLE001
            out["a"] = exc

    def resp():
        try:
            out["b"] = handshake_responder(sock_b, key_b, "peer_B", **(resp_kw or {}))
        except Exception as exc:  # noqa: BLE001
            out["b"] = exc

    threads = [threading.Thread(target=init, daemon=True), threading.Thread(target=resp, daemon=True)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    return out["a"], out["b"]


def test_handshake_success_and_secure_chat(pair, keys):
    (sa, sb), (ka, kb) = pair, keys
    ra, rb = run_both(sa, sb, ka, kb)
    assert not isinstance(ra, Exception) and not isinstance(rb, Exception)
    assert ra.peer_id == "peer_B" and rb.peer_id == "peer_A"
    assert ra.peer_fingerprint == kb.fingerprint()
    assert rb.peer_fingerprint == ka.fingerprint()

    msg = make_message("TEXT", "peer_A", "peer_B", {"text": "Xin chào 😀"})
    send_secure(sa, ra.session, msg)
    assert recv_secure(sb, rb.session)["payload"]["text"] == "Xin chào 😀"
    reply = make_message("REPLY", "peer_B", "peer_A", {"reply_to_message_id": msg["header"]["message_id"], "text": "ok"})
    send_secure(sb, rb.session, reply)
    assert recv_secure(sa, ra.session)["payload"]["text"] == "ok"


def test_data_after_handshake_is_not_plaintext(pair, keys):
    (sa, sb), (ka, kb) = pair, keys
    ra, rb = run_both(sa, sb, ka, kb)
    send_secure(sa, ra.session, make_message("TEXT", "peer_A", "peer_B", {"text": "bi mat"}))
    raw = recv_frame(sb)
    assert b"bi mat" not in raw and b"TEXT" not in raw


def test_user_rejects_fingerprint(pair, keys):
    (sa, sb), (ka, kb) = pair, keys
    seen = []
    ra, _ = run_both(sa, sb, ka, kb, init_kw={"confirm_peer": lambda fp: seen.append(fp) or False},
                     resp_kw={"timeout": 0.5})
    assert isinstance(ra, HandshakeError) and seen == [kb.fingerprint()]


def test_timeout_when_peer_silent(pair, keys):
    sa, sb = pair
    result = {}

    def silent():
        recv_frame(sb)  # doc khung dau roi im lang

    threading.Thread(target=silent, daemon=True).start()
    with pytest.raises(HandshakeError):
        handshake_initiator(sa, keys[0], "peer_A", timeout=0.3)


def test_garbage_reply_rejected(pair, keys):
    sa, sb = pair

    def fake():
        recv_frame(sb)
        send_frame(sb, b"khong phai json")

    threading.Thread(target=fake, daemon=True).start()
    with pytest.raises(HandshakeError):
        handshake_initiator(sa, keys[0], "peer_A", timeout=2)


def test_wrong_action_rejected(pair, keys):
    sa, sb = pair

    def fake():
        recv_frame(sb)
        send_frame(sb, encode_message(make_message("KEY_EXCHANGE", "peer_B", "peer_A", {"action": "SESSION_KEY"})))

    threading.Thread(target=fake, daemon=True).start()
    with pytest.raises(HandshakeError):
        handshake_initiator(sa, keys[0], "peer_A", timeout=2)


def test_oversized_frame_length_rejected(pair, keys):
    sa, sb = pair

    def fake():
        recv_frame(sb)
        sb.sendall(struct.pack(">I", 2 ** 31))

    threading.Thread(target=fake, daemon=True).start()
    with pytest.raises(HandshakeError):
        handshake_initiator(sa, keys[0], "peer_A", timeout=2)


def test_bad_key_confirm_rejected(pair, keys):
    sa, sb = pair

    def fake():
        first = decode_message(recv_frame(sb))
        send_frame(sb, encode_message(make_message(
            "KEY_EXCHANGE", "peer_B", "peer_A",
            {"action": "PUBLIC_KEY", "algorithm": "RSA-2048", "key_id": "k", "public_key": keys[1].public_pem()})))
        recv_frame(sb)                      # SESSION_KEY
        send_frame(sb, b"\x00" * 64)        # KEY_CONFIRM gia

    threading.Thread(target=fake, daemon=True).start()
    with pytest.raises(HandshakeError):
        handshake_initiator(sa, keys[0], "peer_A", timeout=2)


def test_connection_closed_midway(pair, keys):
    sa, sb = pair
    sb.close()
    with pytest.raises(HandshakeError):
        handshake_initiator(sa, keys[0], "peer_A", timeout=1)


def test_recv_frame_rejects_zero_length(pair):
    sa, sb = pair
    sa.sendall(struct.pack(">I", 0))
    with pytest.raises(FrameError):
        recv_frame(sb)


def test_decode_message_validation():
    with pytest.raises(HandshakeError):
        decode_message(b'{"header": {}, "payload": {}}')
    with pytest.raises(HandshakeError):
        decode_message(b"[1, 2]")
    with pytest.raises(HandshakeError):
        decode_message(b"\xff\xfe")


def test_handshake_log_has_no_secrets(pair, keys, tmp_path):
    (sa, sb), (ka, kb) = pair, keys
    setup_logging(str(tmp_path), level="DEBUG")
    try:
        ra, rb = run_both(sa, sb, ka, kb)
        send_secure(sa, ra.session, make_message("TEXT", "peer_A", "peer_B", {"text": "tin rat bi mat"}))
    finally:
        shutdown_logging()
    content = (tmp_path / "app.log").read_text(encoding="utf-8")
    assert "HANDSHAKE_START" in content and "HANDSHAKE_OK" in content
    assert "BEGIN" not in content and "tin rat bi mat" not in content
    assert not re.search(r"[A-Za-z0-9+/]{40,}", content)
    assert not re.search(r"\b[0-9a-fA-F]{32,}\b", content)
    for line in content.splitlines():
        json.loads(line)


def test_tcp_loopback_end_to_end_and_close_detected(keys):
    import socket as _s
    ka, kb = keys
    srv = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    got = {}

    def server():
        conn, _ = srv.accept()
        with conn:
            res = handshake_responder(conn, kb, "peer-B")
            got["msg"] = recv_secure(conn, res.session)
            send_secure(conn, res.session, make_message("TEXT", "peer-B", "peer-A", {"text": "pong"}))
        # dong ket noi o day

    t = threading.Thread(target=server, daemon=True)
    t.start()
    cli = _s.create_connection(("127.0.0.1", port))
    try:
        res = handshake_initiator(cli, ka, "peer-A", "peer-B")
        send_secure(cli, res.session, make_message("TEXT", "peer-A", "peer-B", {"text": "ping"}))
        assert recv_secure(cli, res.session)["payload"]["text"] == "pong"
        with pytest.raises(ConnectionError):       # server dong -> ConnectionError
            recv_secure(cli, res.session)
    finally:
        cli.close()
        srv.close()
    t.join(5)
    assert got["msg"]["payload"]["text"] == "ping"


def test_recv_secure_accepts_minimal_header(pair, keys):
    (sa, sb), (ka, kb) = pair, keys
    ra, rb = run_both(sa, sb, ka, kb)
    minimal = {"header": {"message_type": "TEXT"}, "payload": {"text": "hi"}}
    send_secure(sa, ra.session, minimal)
    assert recv_secure(sb, rb.session)["payload"]["text"] == "hi"
