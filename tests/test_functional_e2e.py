"""Functional test dau-cuoi cho cac chuc nang bat buoc (Chang 5, TV1).

Chay tren kenh THAT: bat tay RSA + ma hoa AES-256-GCM giua cac peer, dung dung dinh dang
thong diep trong message_protocol.md. Kiem tra chuc nang o muc giao thuc va ma hoa.
Phan hien thi tren GUI kiem tra bang tay (xem EXTRA/functional_test_chang5.md).
"""
import hashlib
import random
import socket
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa_helpers import (  # noqa: E402
    TransferError,
    emoji_msg,
    forward_msg,
    make_png,
    png_size,
    reply_msg,
    secure_pair,
    text_msg,
    transfer,
    validate_message,
)
from security.crypto import DecryptError, KeyPair  # noqa: E402
from security.handshake import recv_secure, send_secure  # noqa: E402

EMOJIS = ["😀", "😂", "❤️", "👍🏽", "👨‍👩‍👧‍👦", "🇻🇳", "🙂" * 50, "Cờ 🇻🇳 và pháo 🎆", "\u200d\ufe0f"]


@pytest.fixture(scope="module")
def keys():
    return [KeyPair.generate() for _ in range(3)]


@pytest.fixture
def make_link(keys):
    opened = []

    def factory(a=0, b=1, ids=("peer-A", "peer-B")):
        link = secure_pair(keys[a], keys[b], ids)
        opened.extend([link.sock_a, link.sock_b])
        return link

    yield factory
    for sock in opened:
        sock.close()


def sha(data):
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------ TEXT, EMOJI
def test_fn_txt_01_unicode_text_intact(make_link):
    link = make_link()
    for text in ["Xin chào các bạn!", "dòng 1\ndòng 2\ttab", "Tiếng Việt có dấu ăâêôơư 😀", "a" * 20_000]:
        msg = text_msg("peer-A", "peer-B", text)
        send_secure(link.sock_a, link.sess_a, msg)
        got = recv_secure(link.sock_b, link.sess_b)
        assert got == msg and validate_message(got) == []


def test_fn_emo_01_emoji_exact_and_ordered(make_link):
    link = make_link()
    sent = [emoji_msg("peer-A", "peer-B", e) for e in EMOJIS * 5]

    def sender():                       # gui o luong rieng, nhan o luong chinh (nhu ung dung that)
        for msg in sent:
            send_secure(link.sock_a, link.sess_a, msg)

    thread = threading.Thread(target=sender, daemon=True)
    thread.start()
    got = [recv_secure(link.sock_b, link.sess_b) for _ in sent]
    thread.join(10)
    assert [m["payload"]["emoji"] for m in got] == [m["payload"]["emoji"] for m in sent]
    assert all(validate_message(m) == [] for m in got)


# ------------------------------------------------------------------ REPLY
def test_fn_rep_01_reply_resolves_original(make_link):
    link = make_link()
    history = {}                                    # lich su chat cua A: message_id -> tin
    original = text_msg("peer-A", "peer-B", "Hôm nay họp lúc mấy giờ?")
    history[original["header"]["message_id"]] = original
    send_secure(link.sock_a, link.sess_a, original)
    seen_by_b = recv_secure(link.sock_b, link.sess_b)

    reply = reply_msg("peer-B", "peer-A", seen_by_b["header"]["message_id"], "9 giờ sáng")
    send_secure(link.sock_b, link.sess_b, reply)
    got = recv_secure(link.sock_a, link.sess_a)

    assert validate_message(got) == []
    assert got["header"]["message_id"] != original["header"]["message_id"]
    quoted = history[got["payload"]["reply_to_message_id"]]
    assert quoted["payload"]["text"] == "Hôm nay họp lúc mấy giờ?"
    assert got["payload"]["text"] == "9 giờ sáng"


def test_fn_rep_02_reply_chain(make_link):
    link = make_link()
    chain = [text_msg("peer-A", "peer-B", "gốc")]
    sides = [(link.sock_a, link.sess_a, link.sock_b, link.sess_b),
             (link.sock_b, link.sess_b, link.sock_a, link.sess_a)]
    for depth in range(1, 4):
        sender, sender_sess, receiver, receiver_sess = sides[depth % 2]
        who = "peer-A" if depth % 2 == 0 else "peer-B"
        other = "peer-B" if who == "peer-A" else "peer-A"
        msg = reply_msg(who, other, chain[-1]["header"]["message_id"], f"trả lời cấp {depth}")
        send_secure(sender, sender_sess, msg)
        got = recv_secure(receiver, receiver_sess)
        assert validate_message(got) == []
        assert got["payload"]["reply_to_message_id"] == chain[-1]["header"]["message_id"]
        chain.append(got)
    assert len({m["header"]["message_id"] for m in chain}) == 4


# ------------------------------------------------------------------ FORWARD
def forward_via_b(make_link, original):
    """A gui `original` cho B, B chuyen tiep cho C. Tra ve tin C nhan duoc."""
    ab = make_link(0, 1, ("peer-A", "peer-B"))
    bc = make_link(1, 2, ("peer-B", "peer-C"))
    send_secure(ab.sock_a, ab.sess_a, original)
    at_b = recv_secure(ab.sock_b, ab.sess_b)
    fwd = forward_msg("peer-B", "peer-C", at_b)
    send_secure(bc.sock_a, bc.sess_a, fwd)
    return at_b, recv_secure(bc.sock_b, bc.sess_b)


def test_fn_fwd_01_forward_text_to_other_peer(make_link):
    original = text_msg("peer-A", "peer-B", "Mai nhớ nộp bài nha !")
    _, at_c = forward_via_b(make_link, original)
    assert validate_message(at_c) == []
    p = at_c["payload"]
    assert at_c["header"]["sender_id"] == "peer-B" and at_c["header"]["receiver_id"] == "peer-C"
    assert at_c["header"]["message_id"] != original["header"]["message_id"]
    assert p["original_message_id"] == original["header"]["message_id"]
    assert p["original_sender_id"] == "peer-A" and p["original_message_type"] == "TEXT"
    assert p["original_payload"] == {"text": "Mai nhớ nộp bài nha !"}


def test_fn_fwd_02_forward_emoji_and_reply(make_link):
    emoji = emoji_msg("peer-A", "peer-B", "👨‍👩‍👧‍👦")
    _, at_c = forward_via_b(make_link, emoji)
    assert at_c["payload"]["original_message_type"] == "EMOJI"
    assert at_c["payload"]["original_payload"] == {"emoji": "👨‍👩‍👧‍👦"}

    reply = reply_msg("peer-A", "peer-B", "550e8400-e29b-41d4-a716-446655440001", "đồng ý")
    _, at_c = forward_via_b(make_link, reply)
    assert at_c["payload"]["original_message_type"] == "REPLY"
    assert at_c["payload"]["original_payload"]["reply_to_message_id"] == "550e8400-e29b-41d4-a716-446655440001"


def test_fn_fwd_03_forward_of_forward_keeps_first_original(make_link):
    original = text_msg("peer-A", "peer-B", "tin gốc")
    _, first = forward_via_b(make_link, original)
    second = forward_msg("peer-C", "peer-D", first)
    assert validate_message(second) == []
    assert second["payload"]["original_message_id"] == original["header"]["message_id"]
    assert second["payload"]["original_sender_id"] == "peer-A"
    assert second["header"]["message_id"] not in (original["header"]["message_id"], first["header"]["message_id"])


# ------------------------------------------------------------------ FILE
@pytest.mark.parametrize("size", [0, 1, 16383, 16384, 16385, 100_000])
def test_fn_fil_01_sizes_roundtrip(make_link, size):
    data = random.Random(size).randbytes(size)
    name, got = transfer(make_link(), data, name="tài liệu (1).bin")
    assert name == "tài liệu (1).bin" and len(got) == size and sha(got) == sha(data)


def test_fn_fil_02_large_file_multithread(make_link):
    data = random.Random(5).randbytes(2 * 1024 * 1024)
    _, got = transfer(make_link(), data, threads=8, chunk_size=16384)
    assert sha(got) == sha(data)


def test_fn_fil_03_tampered_chunk_detected(make_link):
    data = random.Random(6).randbytes(100_000)
    with pytest.raises(DecryptError):
        transfer(make_link(), data, tamper_index=3)


def test_fn_fil_04_missing_chunk_detected(make_link):
    data = random.Random(7).randbytes(100_000)
    with pytest.raises(TransferError):
        transfer(make_link(), data, drop_index=2, close_sender=True)


def test_fn_fil_05_chunks_of_other_transfer_rejected(make_link):
    data = random.Random(8).randbytes(50_000)
    with pytest.raises(DecryptError):
        transfer(make_link(), data, crypto_transfer_id="mot-lan-truyen-khac")


def test_fn_fil_06_bad_offer_rejected(make_link):
    link = make_link()
    from security.handshake import make_message
    bad = make_message("FILE", "peer-A", "peer-B", {
        "action": "OFFER", "transfer_id": "t", "file_name": "../../evil.exe",
        "file_size": 10, "chunk_size": 16384, "total_chunks": 1})
    send_secure(link.sock_a, link.sess_a, bad)
    from qa_helpers import recv_file
    with pytest.raises(TransferError):
        recv_file(link.sock_b, link.sess_b)


# ------------------------------------------------------------------ AVATAR
def test_fn_avt_01_png_roundtrip(make_link):
    png = make_png(48, seed=1)
    assert png_size(png) == (48, 48)
    name, got = transfer(make_link(), png, name="avatar.png")
    assert got == png and png_size(got) == (48, 48)


def test_fn_avt_02_non_image_is_rejected_by_check():
    assert png_size(b"khong phai anh") is None
    assert png_size(b"") is None
    png = make_png(16)
    assert png_size(png[:-5]) is None                    # cat cut
    corrupted = bytearray(png)
    corrupted[40] ^= 0xFF
    assert png_size(bytes(corrupted)) is None            # sai CRC


def test_fn_avt_03_tampered_avatar_never_delivered(make_link):
    with pytest.raises(DecryptError):
        transfer(make_link(), make_png(64, seed=2), tamper_index=0, chunk_size=4096)


# ------------------------------------------------------------------ AES tren duong truyen
def tapped_link(keys):
    """2 peer noi qua 1 'tram nghe' ghi lai moi byte di qua (giong Wireshark)."""
    a1, a2 = socket.socketpair()
    b1, b2 = socket.socketpair()
    captured = bytearray()

    def pump(src, dst):
        while True:
            try:
                chunk = src.recv(65536)
            except OSError:
                break
            if not chunk:
                break
            captured.extend(chunk)
            try:
                dst.sendall(chunk)
            except OSError:
                break

    for src, dst in ((a2, b2), (b2, a2)):
        threading.Thread(target=pump, args=(src, dst), daemon=True).start()
    link = secure_pair(keys[0], keys[1], socks=(a1, b1))
    return link, captured, (a1, a2, b1, b2)


def test_fn_sec_01_nothing_readable_on_the_wire(keys):
    link, captured, socks = tapped_link(keys)
    try:
        secret_text = "BI-MAT-XYZ-123 tin nhắn riêng"
        send_secure(link.sock_a, link.sess_a, text_msg("peer-A", "peer-B", secret_text))
        recv_secure(link.sock_b, link.sess_b)
        marker = b"NOI-DUNG-FILE-BI-MAT-"
        _, got = transfer(link, marker * 2000)
        assert got == marker * 2000
        wire = bytes(captured)
        assert len(wire) > 30_000
        assert b"BI-MAT-XYZ-123" not in wire and "tin nhắn riêng".encode() not in wire
        assert marker not in wire
        # Cac chuoi dac trung cua JSON thong diep khong duoc lo ra sau khi bat tay xong
        # (khong tim 'text' tran vi du lieu ngau nhien co the vo tinh chua 4 chu do)
        assert b'"TEXT"' not in wire and b'"text"' not in wire and b'"reply_to_message_id"' not in wire
    finally:
        for sock in socks:
            sock.close()