"""Test bo ghi log an toan (CODE/logger.py)."""
import json
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "CODE"))

import logger  # noqa: E402
from logger import Event, log_event, mask_ip, sanitize_text, sanitize_value, setup_logging, shutdown_logging  # noqa: E402
from security.crypto import KeyPair  # noqa: E402


@pytest.fixture
def logdir(tmp_path):
    setup_logging(str(tmp_path), level="DEBUG")
    yield tmp_path
    shutdown_logging()


def read_lines(path):
    shutdown_logging()
    return [json.loads(x) for x in (path / "app.log").read_text(encoding="utf-8").splitlines()]


def test_line_is_valid_json_with_core_fields(logdir):
    log_event(Event.PEER_CONNECTED, peer="ab12cd34", session="a1b2c3")
    line = read_lines(logdir)[0]
    assert line["event"] == "PEER_CONNECTED" and line["level"] == "INFO"
    assert line["ts"].endswith("Z") and line["peer"] == "ab12cd34"


def test_pem_is_redacted():
    pem = KeyPair.generate().public_pem()
    out = sanitize_text("khoa: " + pem)
    assert "BEGIN" not in out and "REDACTED:PEM" in out


def test_long_hex_and_base64_redacted():
    assert "REDACTED:HEX" in sanitize_text("k=" + "ab" * 32)
    assert "REDACTED:B64" in sanitize_text("x " + "QUJD" * 20)


def test_short_ids_are_kept():
    assert sanitize_text("peer ab12cd34 key-ab12cd34") == "peer ab12cd34 key-ab12cd34"


def test_sensitive_fields_redacted(logdir):
    log_event("X", session_key="abc", text="noi dung tin nhan bi mat", reason="timeout")
    line = read_lines(logdir)[0]
    assert line["session_key"] == "[REDACTED]" and line["text"] == "[REDACTED]"
    assert line["reason"] == "timeout"
    assert "bi mat" not in json.dumps(line)


def test_bytes_never_logged_raw():
    out = sanitize_value({"anything": b"\x00\x01secret"})
    assert out["anything"] == "[REDACTED:bytes len=8]"


def test_nested_structures_sanitized():
    out = sanitize_value({"info": {"original_payload": {"text": "hi"}, "note": "ab" * 32}})
    assert out["info"]["original_payload"] == "[REDACTED]"
    assert "REDACTED:HEX" in out["info"]["note"]


def test_message_text_is_sanitized(logdir):
    log_event("X", msg="loi voi " + KeyPair.generate().public_pem())
    assert "BEGIN" not in read_lines(logdir)[0]["msg"]


def test_mask_ip():
    assert mask_ip("192.168.1.23") == "192.168.1.x"
    assert mask_ip("khong-phai-ip") == "[masked]"


def test_setup_twice_does_not_duplicate_handlers(tmp_path):
    try:
        setup_logging(str(tmp_path))
        log = setup_logging(str(tmp_path))
        mine = [h for h in log.handlers if getattr(h, "_p2p_handler", False)]
        assert len(mine) == 1 and isinstance(mine[0], RotatingFileHandler)
    finally:
        shutdown_logging()


def test_log_event_never_raises(logdir):
    log_event("X", weird=object(), other={1, 2, 3})
    log_event("X", "NOT_A_LEVEL")
    assert read_lines(logdir)


def test_log_file_has_no_secret_patterns(logdir):
    for i in range(20):
        log_event(Event.HANDSHAKE_FAIL, "WARNING", detail=KeyPair.generate().public_pem(),
                  encrypted_session_key="QUJD" * 30)
    shutdown_logging()
    content = (logdir / "app.log").read_text(encoding="utf-8")
    assert "BEGIN" not in content
    assert not re.search(r"[A-Za-z0-9+/]{40,}", content)
