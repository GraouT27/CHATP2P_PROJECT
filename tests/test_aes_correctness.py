"""Kiem tra tinh dung dan cua ma hoa/giai ma AES-256-GCM (Chang 5, TV1).

1. Vector chuan NIST (Known-Answer Test): chung minh thu vien AES-256-GCM tinh ra dung ket qua chuan.
2. Kiem tra DOC LAP: tu giai ma goi do SessionCrypto/ChunkCrypto tao ra bang AESGCM tho,
   va nguoc lai, de chung minh dinh dang goi dung nhu thiet ke (khong chi 'ma hoa roi giai ma ra nhu cu').
3. Tinh chat an toan: sua 1 byte bat ky -> that bai, nonce khong trung, khoa phai 32 byte...
"""
import os
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "CODE"))

from security.crypto import (  # noqa: E402
    OVERHEAD,
    DecryptError,
    KeyPair,
    SessionCrypto,
    _derive,
    encrypt_session_key,
    new_session_key,
)

H = bytes.fromhex

# ---- Vector chuan: McGrew & Viega, "The Galois/Counter Mode of Operation", Test Case 13-16 (AES-256)
ZERO_KEY = bytes(32)
GCM_KEY = H("feffe9928665731c6d6a8f9467308308feffe9928665731c6d6a8f9467308308")
GCM_IV = H("cafebabefacedbaddecaf888")
GCM_P = H("d9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a72"
          "1c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b391aafd255")
GCM_AAD = H("feedfacedeadbeeffeedfacedeadbeefabaddad2")

NIST_VECTORS = [
    # (ten, key, iv, aad, plaintext, ciphertext, tag)
    ("TC13 rong", ZERO_KEY, bytes(12), b"", b"", b"", H("530f8afbc74536b9a963b4f1c4cb738b")),
    ("TC14 16 byte 0", ZERO_KEY, bytes(12), b"", bytes(16), H("cea7403d4d606b6e074ec5d3baf39d18"),
     H("d0d1c8a799996bf0265b98b5d48ab919")),
    ("TC15 64 byte", GCM_KEY, GCM_IV, b"", GCM_P,
     H("522dc1f099567d07f47f37a32a84427d643a8cdcbfe5c0c97598a2bd2555d1aa"
       "8cb08e48590dbb3da7b08b1056828838c5f61e6393ba7a0abcc9f662898015ad"),
     H("b094dac5d93471bdec1a502270e3cc6c")),
    ("TC16 60 byte + AAD", GCM_KEY, GCM_IV, GCM_AAD, GCM_P[:60],
     H("522dc1f099567d07f47f37a32a84427d643a8cdcbfe5c0c97598a2bd2555d1aa"
       "8cb08e48590dbb3da7b08b1056828838c5f61e6393ba7a0abcc9f662"),
     H("76fc6ece0f4e1768cddf8853bb2d551b")),
]


@pytest.mark.parametrize("name,key,iv,aad,plain,cipher,tag", NIST_VECTORS, ids=[v[0] for v in NIST_VECTORS])
def test_aes01_nist_known_answer(name, key, iv, aad, plain, cipher, tag):
    aead = AESGCM(key)
    assert aead.encrypt(iv, plain, aad or None) == cipher + tag
    assert aead.decrypt(iv, cipher + tag, aad or None) == plain


def test_aes02_nist_vector_with_wrong_tag_fails():
    _, key, iv, aad, plain, cipher, tag = NIST_VECTORS[3]
    with pytest.raises(Exception):
        AESGCM(key).decrypt(iv, cipher + bytes([tag[0] ^ 1]) + tag[1:], aad)


# ---------------------------------------------------------------- kiem tra doc lap SessionCrypto
def make_pair(salt=b"salt-kiem-thu"):
    key = new_session_key()
    return key, salt, SessionCrypto(key, True, salt), SessionCrypto(key, False, salt)


def test_aes03_independent_decrypt_of_session_blob():
    key, salt, a, _ = make_pair()
    plain = "Tin nhắn thử 😀".encode()
    blob = a.encrypt(plain)
    seq, nonce, rest = blob[:8], blob[8:20], blob[20:]
    raw_key = _derive(key, salt, b"p2p-chat a2b")
    assert AESGCM(raw_key).decrypt(nonce, rest, seq) == plain       # giai ma bang AES tho
    assert len(blob) == OVERHEAD + len(plain) and len(rest) == len(plain) + 16
    assert int.from_bytes(seq, "big") == 1


def test_aes04_independent_encrypt_accepted_by_session():
    key, salt, _, b = make_pair()
    seq, nonce = (1).to_bytes(8, "big"), os.urandom(12)
    blob = seq + nonce + AESGCM(_derive(key, salt, b"p2p-chat a2b")).encrypt(nonce, b"tu ben ngoai", seq)
    assert b.decrypt(blob) == b"tu ben ngoai"


def test_aes05_hkdf_matches_reference_implementation():
    key, salt, a, _ = make_pair()
    reference = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=b"p2p-chat b2a").derive(key)
    assert _derive(key, salt, b"p2p-chat b2a") == reference
    assert _derive(key, salt, b"p2p-chat a2b") != reference            # hai chieu hai khoa khac nhau


def test_aes06_independent_decrypt_of_chunk():
    key, salt, a, _ = make_pair()
    tid, total, index, data = "transfer-xyz", 5, 3, b"noi dung chunk"
    blob = a.chunk_crypto(tid, total, sending=True).encrypt_chunk(index, data)
    send_key = _derive(key, salt, b"p2p-chat a2b")
    file_key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"p2p-chat file " + tid.encode()).derive(send_key)
    nonce = bytes(4) + index.to_bytes(8, "big")
    aad = index.to_bytes(8, "big") + total.to_bytes(8, "big")
    assert AESGCM(file_key).decrypt(nonce, blob, aad) == data
    assert len(blob) == len(data) + 16


# ---------------------------------------------------------------- tinh chat an toan
@pytest.mark.parametrize("size", [0, 1, 15, 16, 17, 255, 256, 1000, 65536])
def test_aes07_roundtrip_all_sizes(size):
    _, _, a, b = make_pair()
    data = os.urandom(size)
    assert b.decrypt(a.encrypt(data)) == data


def test_aes08_large_payload_roundtrip():
    _, _, a, b = make_pair()
    data = os.urandom(5 * 1024 * 1024)
    assert b.decrypt(a.encrypt(data)) == data


def test_aes09_every_byte_flip_is_detected():
    """Sua bat ky byte nao (seq, nonce, ban ma, tag) deu bi tu choi."""
    key, salt, a, _ = make_pair()
    blob = a.encrypt(b"x" * 40)
    for position in range(len(blob)):
        fresh = SessionCrypto(key, False, salt)
        tampered = bytearray(blob)
        tampered[position] ^= 0x01
        with pytest.raises(DecryptError):
            fresh.decrypt(bytes(tampered))
    assert SessionCrypto(key, False, salt).decrypt(blob) == b"x" * 40       # goi goc van dung


def test_aes10_truncated_or_extended_blob_rejected():
    key, salt, a, _ = make_pair()
    blob = a.encrypt(b"hello world")
    for bad in (blob[:-1], blob[:-16], blob[:OVERHEAD - 1], blob + b"\x00", b""):
        with pytest.raises(DecryptError):
            SessionCrypto(key, False, salt).decrypt(bad)


def test_aes11_nonce_unique_and_same_plaintext_differs():
    _, _, a, _ = make_pair()
    blobs = [a.encrypt(b"giong nhau") for _ in range(2000)]
    assert len({x[8:20] for x in blobs}) == 2000
    assert len({x[20:] for x in blobs}) == 2000


def test_aes12_ciphertext_does_not_contain_plaintext():
    _, _, a, _ = make_pair()
    plain = b"BI-MAT-" * 100
    assert b"BI-MAT" not in a.encrypt(plain)


def test_aes13_wrong_key_and_wrong_salt_rejected():
    key, salt, a, _ = make_pair()
    blob = a.encrypt(b"abc")
    with pytest.raises(DecryptError):
        SessionCrypto(new_session_key(), False, salt).decrypt(blob)
    with pytest.raises(DecryptError):
        SessionCrypto(key, False, b"salt-khac").decrypt(blob)


@pytest.mark.parametrize("length", [0, 16, 24, 31, 33, 64])
def test_aes14_session_key_must_be_32_bytes(length):
    with pytest.raises(ValueError):
        SessionCrypto(os.urandom(length), True)


def test_aes15_rsa_oaep_wraps_session_key_correctly():
    pair = KeyPair.generate()
    seen = set()
    for _ in range(10):
        key = new_session_key()
        wrapped = encrypt_session_key(pair.public_pem(), key)
        assert pair.decrypt_session_key(wrapped) == key
        seen.add(wrapped)
    assert len(seen) == 10                       # OAEP ngau nhien: cung khoa nhung ban ma khac nhau


def test_aes16_session_keys_are_random():
    assert len({new_session_key() for _ in range(1000)}) == 1000