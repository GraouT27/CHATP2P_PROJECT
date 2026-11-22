"""Kiem tra bo kiem tra thong diep (validate_message) theo message_protocol.md - Chang 5, TV1."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa_helpers import (  # noqa: E402
    emoji_msg,
    forward_msg,
    reply_msg,
    text_msg,
    validate_message,
)
from security.handshake import make_message  # noqa: E402


def offer(**over):
    payload = {"action": "OFFER", "transfer_id": "t-1", "file_name": "baocao.pdf",
               "file_size": 102400, "chunk_size": 16384, "total_chunks": 7}
    payload.update(over)
    return make_message("FILE", "peer-A", "peer-B", payload)


def has_error(msg, fragment):
    return any(fragment in e for e in validate_message(msg))


def test_valid_messages_pass():
    t = text_msg("peer-A", "peer-B", "Xin chào!")
    for msg in (
        t,
        emoji_msg("peer-A", "peer-B", "😂"),
        reply_msg("peer-B", "peer-A", t["header"]["message_id"], "Khỏe, cảm ơn"),
        forward_msg("peer-B", "peer-C", t),
        offer(),
        offer(file_size=0, total_chunks=1),
        make_message("KEY_EXCHANGE", "a", "b", {"action": "PUBLIC_KEY", "algorithm": "RSA-2048",
                                               "key_id": "k1", "public_key": "PEM"}),
        make_message("KEY_EXCHANGE", "a", "b", {"action": "SESSION_KEY", "algorithm": "RSA-OAEP-SHA256",
                                               "key_id": "k1", "encrypted_session_key": "QUJD"}),
        make_message("KEY_EXCHANGE", "a", "b", {"action": "KEY_CONFIRM"}),
    ):
        assert validate_message(msg) == [], msg


def test_structure_errors():
    assert validate_message("khong phai dict")
    assert has_error({"payload": {}}, "thieu header")
    assert has_error({"header": {}}, "thieu payload")
    msg = text_msg("a", "b", "x")
    del msg["header"]["timestamp"]
    assert has_error(msg, "timestamp")


def test_header_rules():
    msg = text_msg("a", "b", "x")
    msg["header"]["message_id"] = "khong-phai-uuid"
    assert has_error(msg, "UUID")
    msg = text_msg("a", "b", "x")
    msg["header"]["timestamp"] = "2026-11-14 10:00:00"
    assert has_error(msg, "timestamp")
    assert has_error(text_msg("192.168.1.5", "b", "x"), "dia chi IP")
    assert has_error(text_msg("a", "10.0.0.1", "x"), "dia chi IP")
    msg = text_msg("a", "b", "x")
    msg["header"]["message_type"] = "VIDEO"
    assert has_error(msg, "khong ho tro")


def test_reply_rules():
    msg = reply_msg("a", "b", "550e8400-e29b-41d4-a716-446655440001", "ok")
    assert validate_message(msg) == []
    del msg["payload"]["reply_to_message_id"]
    assert has_error(msg, "reply_to_message_id")
    msg = reply_msg("a", "b", "khong-phai-uuid", "ok")
    assert has_error(msg, "reply_to_message_id")
    msg = reply_msg("a", "b", "550e8400-e29b-41d4-a716-446655440001", "ok")
    msg["payload"]["reply_to_message_id"] = msg["header"]["message_id"]
    assert has_error(msg, "chinh no")


def test_forward_rules():
    original = text_msg("peer-A", "peer-B", "Mai nộp bài")
    fwd = forward_msg("peer-B", "peer-C", original)
    assert fwd["header"]["message_id"] != original["header"]["message_id"]
    assert fwd["payload"]["original_message_id"] == original["header"]["message_id"]
    for field in ("original_message_id", "original_sender_id", "original_message_type", "original_payload"):
        broken = copy.deepcopy(fwd)
        del broken["payload"][field]
        assert has_error(broken, field), field
    broken = copy.deepcopy(fwd)
    broken["payload"]["original_message_type"] = "KEY_EXCHANGE"
    assert has_error(broken, "chuyen tiep")
    broken = copy.deepcopy(fwd)
    broken["payload"]["original_message_id"] = broken["header"]["message_id"]
    assert has_error(broken, "message_id moi")


def test_file_offer_rules():
    assert has_error(offer(action="FILE_OFFER"), "action")          # ten action trong vi du cua giao thuc
    assert has_error(offer(transfer_id=""), "transfer_id")
    for bad in ("../x.txt", "a/b.txt", "a\\b.txt", "..", ""):
        assert has_error(offer(file_name=bad), "file_name"), bad
    assert validate_message(offer(file_name="báo cáo (1).pdf")) == []
    assert has_error(offer(chunk_size=1024), "chunk_size")
    assert has_error(offer(chunk_size=1_000_000), "chunk_size")
    assert has_error(offer(total_chunks=8), "total_chunks")
    assert has_error(offer(file_size=-1), "file_size")
    assert has_error(offer(file_size="100"), "so nguyen")
    assert validate_message(offer(file_size=16384, total_chunks=1)) == []
    assert validate_message(offer(file_size=16385, total_chunks=2)) == []


def test_key_exchange_rules():
    base = {"action": "PUBLIC_KEY", "algorithm": "RSA", "key_id": "k", "public_key": "p"}
    for field in ("algorithm", "key_id", "public_key"):
        payload = dict(base)
        del payload[field]
        assert has_error(make_message("KEY_EXCHANGE", "a", "b", payload), field)
    assert has_error(make_message("KEY_EXCHANGE", "a", "b", {"action": "HELLO"}), "action")
    bad = {"action": "SESSION_KEY", "algorithm": "x", "key_id": "k", "encrypted_session_key": "@@@"}
    assert has_error(make_message("KEY_EXCHANGE", "a", "b", bad), "base64")


@pytest.mark.parametrize("field", ["private_key", "password", "session_key", "aes_key"])
def test_secret_fields_rejected_anywhere(field):
    msg = text_msg("a", "b", "x")
    msg["payload"]["nested"] = {field: "bi mat"}
    assert has_error(msg, "bi mat")