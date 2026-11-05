"""Test co ban cho CODE/security/crypto.py (Chang 2, TV1)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "CODE"))

from security.crypto import (  # noqa: E402
    OVERHEAD,
    CryptoError,
    DecryptError,
    KeyPair,
    ReplayError,
    SessionCrypto,
    encrypt_session_key,
    fingerprint_of_pem,
    handshake_salt,
    new_session_key,
)


@pytest.fixture(scope="module")
def keys():
    return KeyPair.generate(), KeyPair.generate()


def make_pair():
    key = new_session_key()
    return SessionCrypto(key, True), SessionCrypto(key, False)


def test_sec01_roundtrip():
    a, b = make_pair()
    assert b.decrypt(a.encrypt("Xin chào 😀".encode())) == "Xin chào 😀".encode()
    assert a.decrypt(b.encrypt(b"tra loi")) == b"tra loi"


def test_empty_plaintext_ok():
    a, b = make_pair()
    assert b.decrypt(a.encrypt(b"")) == b""


def test_sec02_tampered_ciphertext_rejected():
    a, b = make_pair()
    blob = bytearray(a.encrypt(b"hello"))
    blob[-1] ^= 0x01
    with pytest.raises(DecryptError):
        b.decrypt(bytes(blob))


def test_tampered_seq_rejected():
    a, b = make_pair()
    blob = bytearray(a.encrypt(b"hello"))
    blob[7] ^= 0x01
    with pytest.raises(DecryptError):
        b.decrypt(bytes(blob))


def test_sec03_wrong_key_rejected():
    a, _ = make_pair()
    _, other = make_pair()
    with pytest.raises(DecryptError):
        other.decrypt(a.encrypt(b"secret"))


def test_sec04_replay_rejected():
    a, b = make_pair()
    blob = a.encrypt(b"once")
    assert b.decrypt(blob) == b"once"
    with pytest.raises(ReplayError):
        b.decrypt(blob)


def test_short_blob_rejected():
    _, b = make_pair()
    with pytest.raises(DecryptError):
        b.decrypt(b"x" * (OVERHEAD - 1))


def test_reflection_rejected():
    a, _ = make_pair()
    with pytest.raises(DecryptError):
        a.decrypt(a.encrypt(b"phan hoi chinh minh"))


def test_seq_increases_and_nonce_unique():
    a, _ = make_pair()
    b1, b2 = a.encrypt(b"x"), a.encrypt(b"x")
    assert b1[:8] != b2[:8] and b1[8:20] != b2[8:20]
    assert int.from_bytes(b2[:8], "big") == int.from_bytes(b1[:8], "big") + 1


def test_keypair_unique_and_fingerprint(keys):
    k1, k2 = keys
    assert k1.public_pem().startswith("-----BEGIN PUBLIC KEY-----")
    assert k1.fingerprint() != k2.fingerprint()
    assert k1.fingerprint() == fingerprint_of_pem(k1.public_pem())
    assert len(k1.short_id()) == 8


def test_private_key_not_in_repr(keys):
    assert "PRIVATE" not in repr(keys[0])


def test_sec05_full_handshake_simulation(keys):
    ka, kb = keys
    k = new_session_key()
    wrapped = encrypt_session_key(kb.public_pem(), k)
    k_at_b = kb.decrypt_session_key(wrapped)
    assert k_at_b == k
    salt = handshake_salt(ka.public_pem(), kb.public_pem())
    a = SessionCrypto(k, True, salt)
    b = SessionCrypto(k_at_b, False, salt)
    assert b.decrypt(a.encrypt(b"KEY_CONFIRM")) == b"KEY_CONFIRM"
    assert a.decrypt(b.encrypt(b"TEXT")) == b"TEXT"


def test_wrong_private_key_cannot_unwrap(keys):
    ka, kb = keys
    wrapped = encrypt_session_key(kb.public_pem(), new_session_key())
    with pytest.raises(CryptoError):
        ka.decrypt_session_key(wrapped)


def test_bad_inputs():
    with pytest.raises(ValueError):
        SessionCrypto(b"short", True)
    with pytest.raises(CryptoError):
        fingerprint_of_pem("khong phai pem")
    with pytest.raises(CryptoError):
        KeyPair.generate().decrypt_session_key("@@@khong-phai-base64@@@")


def test_no_hardcoded_private_key_in_code():
    marker = "-----BEGIN" + " " + "RSA PRIVATE KEY"
    marker2 = "-----BEGIN" + " " + "PRIVATE KEY"
    code_dir = ROOT / "CODE"
    for path in code_dir.rglob("*"):
        assert path.suffix.lower() != ".pem", f"Co file khoa trong repo: {path}"
        if path.suffix == ".py":
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert marker not in text and marker2 not in text, f"Khoa cung trong {path}"
