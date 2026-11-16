"""Test ma hoa tung chunk file (ChunkCrypto) - Chang 4, TV1."""
import hashlib
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "CODE"))

from security.crypto import CHUNK_OVERHEAD, DecryptError, SessionCrypto, new_session_key  # noqa: E402

CHUNK = 16384


def make_pair():
    key = new_session_key()
    return SessionCrypto(key, True), SessionCrypto(key, False)


def split(data, size=CHUNK):
    return [data[i:i + size] for i in range(0, len(data), size)]


def test_ch01_roundtrip_and_overhead():
    a, b = make_pair()
    enc = a.chunk_crypto("t1", 1, sending=True)
    dec = b.chunk_crypto("t1", 1, sending=False)
    blob = enc.encrypt_chunk(0, b"du lieu chunk")
    assert len(blob) == len(b"du lieu chunk") + CHUNK_OVERHEAD
    assert dec.decrypt_chunk(0, blob) == b"du lieu chunk"


def test_empty_chunk_ok():
    a, b = make_pair()
    blob = a.chunk_crypto("t", 1, True).encrypt_chunk(0, b"")
    assert b.chunk_crypto("t", 1, False).decrypt_chunk(0, blob) == b""


def test_ch02_tampered_chunk_rejected():
    a, b = make_pair()
    blob = bytearray(a.chunk_crypto("t", 2, True).encrypt_chunk(0, b"abc"))
    blob[-1] ^= 1
    with pytest.raises(DecryptError):
        b.chunk_crypto("t", 2, False).decrypt_chunk(0, bytes(blob))


def test_ch03_wrong_index_rejected():
    a, b = make_pair()
    blob = a.chunk_crypto("t", 10, True).encrypt_chunk(3, b"abc")
    dec = b.chunk_crypto("t", 10, False)
    with pytest.raises(DecryptError):
        dec.decrypt_chunk(4, blob)          # hoan doi chunk
    assert dec.decrypt_chunk(3, blob) == b"abc"


def test_ch03b_wrong_total_rejected():
    a, b = make_pair()
    blob = a.chunk_crypto("t", 10, True).encrypt_chunk(3, b"abc")
    with pytest.raises(DecryptError):       # gia tong so chunk (cat bot file)
        b.chunk_crypto("t", 9, False).decrypt_chunk(3, blob)


def test_ch04_wrong_transfer_id_rejected():
    a, b = make_pair()
    blob = a.chunk_crypto("file-A", 1, True).encrypt_chunk(0, b"abc")
    with pytest.raises(DecryptError):
        b.chunk_crypto("file-B", 1, False).decrypt_chunk(0, blob)


def test_ch05_other_session_rejected():
    a, _ = make_pair()
    _, other = make_pair()
    blob = a.chunk_crypto("t", 1, True).encrypt_chunk(0, b"abc")
    with pytest.raises(DecryptError):
        other.chunk_crypto("t", 1, False).decrypt_chunk(0, blob)


def test_ch06_out_of_order_reassembly():
    a, b = make_pair()
    data = random.Random(1).randbytes(100_000)
    pieces = split(data)
    total = len(pieces)
    enc, dec = a.chunk_crypto("big", total, True), b.chunk_crypto("big", total, False)
    blobs = {i: enc.encrypt_chunk(i, p) for i, p in enumerate(pieces)}
    order = list(range(total))
    random.Random(2).shuffle(order)
    got = {i: dec.decrypt_chunk(i, blobs[i]) for i in order}
    rebuilt = b"".join(got[i] for i in range(total))
    assert hashlib.sha256(rebuilt).digest() == hashlib.sha256(data).digest()


def test_ch07_parallel_threads():
    a, b = make_pair()
    data = random.Random(3).randbytes(300_000)
    pieces = split(data)
    total = len(pieces)
    enc, dec = a.chunk_crypto("par", total, True), b.chunk_crypto("par", total, False)
    with ThreadPoolExecutor(8) as pool:
        blobs = list(pool.map(lambda i: enc.encrypt_chunk(i, pieces[i]), range(total)))
        plains = list(pool.map(lambda i: dec.decrypt_chunk(i, blobs[i]), range(total)))
    assert b"".join(plains) == data


def test_ch08_directions_use_different_keys():
    a, b = make_pair()
    blob = a.chunk_crypto("t", 1, sending=True).encrypt_chunk(0, b"abc")
    with pytest.raises(DecryptError):       # nhan nham chieu
        b.chunk_crypto("t", 1, sending=True).decrypt_chunk(0, blob)
    back = b.chunk_crypto("t", 1, sending=True).encrypt_chunk(0, b"tra loi")
    assert a.chunk_crypto("t", 1, sending=False).decrypt_chunk(0, back) == b"tra loi"


def test_ch09_duplicate_chunk_is_idempotent():
    a, b = make_pair()
    blob = a.chunk_crypto("t", 2, True).encrypt_chunk(0, b"abc")
    dec = b.chunk_crypto("t", 2, False)
    assert dec.decrypt_chunk(0, blob) == dec.decrypt_chunk(0, blob) == b"abc"


def test_ch10_invalid_inputs():
    a, b = make_pair()
    enc, dec = a.chunk_crypto("t", 5, True), b.chunk_crypto("t", 5, False)
    with pytest.raises(ValueError):
        enc.encrypt_chunk(5, b"x")          # index ngoai khoang
    with pytest.raises(ValueError):
        a.chunk_crypto("t", 0, True)        # total phai >= 1
    for index in (-1, 5, "0"):
        with pytest.raises(DecryptError):
            dec.decrypt_chunk(index, b"x" * 40)
    with pytest.raises(DecryptError):
        dec.decrypt_chunk(0, b"ngan")