"""Khoa khong duoc lo trong Traceback / repr / log (Chang 6, TV1).

'Lo trong Traceback' = gia tri khoa xuat hien khi Traceback duoc in KEM GIA TRI BIEN CUC BO
(pytest --showlocals, traceback capture_locals=True, trang loi debug cua framework).
Cac test duoi day soi moi bien cuc bo va thuoc tinh doi tuong cua cac frame NAM TRONG CODE/.
"""
import base64
import copy
import pickle
import socket
import sys
import threading
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

TESTS = Path(__file__).resolve().parent
CODE = (TESTS.parent / "CODE").resolve()
sys.path.insert(0, str(CODE))

import security.handshake as handshake_module  # noqa: E402
from security.crypto import (  # noqa: E402
    CryptoError,
    KeyPair,
    SecretBytes,
    SessionCrypto,
    _derive,
    new_session_key,
)
from security.handshake import (  # noqa: E402
    HandshakeError,
    decode_message,
    encode_message,
    handshake_initiator,
    make_message,
    recv_frame,
    send_frame,
)


# ---------------------------------------------------------------- cong cu do
def app_locals_dump(exc, root=CODE):
    """Gom repr cua moi bien cuc bo (va thuoc tinh cua doi tuong) trong cac frame nam duoi `root`."""
    parts, seen, stack = [], set(), [exc]
    while stack:
        current = stack.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        stack += [current.__cause__, current.__context__]
        tb = current.__traceback__
        while tb is not None:
            frame = tb.tb_frame
            if Path(frame.f_code.co_filename).resolve().is_relative_to(root):
                for name, value in frame.f_locals.items():
                    parts.append(f"{frame.f_code.co_name}.{name} = {value!r}")
                    if hasattr(value, "__dict__"):
                        parts += [f"{frame.f_code.co_name}.{name}.{k} = {v!r}" for k, v in vars(value).items()]
            tb = tb.tb_next
    return "\n".join(parts)


def leak_forms(secret: bytes):
    raw = bytes(secret)
    return [repr(raw), raw.hex(), base64.b64encode(raw).decode(), repr(list(raw))]


def assert_no_leak(text, secret):
    hits = [f[:30] for f in leak_forms(secret) if f in text]
    assert hits == [], f"Khoa lo trong Traceback: {hits}"


# ---------------------------------------------------------------- SecretBytes
def test_hy01_secretbytes_hides_value_everywhere():
    key = new_session_key()
    raw = bytes(key)
    for shown in (repr(key), str(key), f"{key}", "%s" % key, "{}".format(key), f"{key!r}"):
        assert raw.hex() not in shown and repr(raw) not in shown and "len=32" in shown
    assert len(key) == 32


def test_hy02_secretbytes_behaves_like_bytes():
    key = new_session_key()
    assert key == bytes(key) and bytes(key) == key
    assert isinstance(key, bytes)
    assert AESGCM(key).decrypt(b"\x00" * 12, AESGCM(key).encrypt(b"\x00" * 12, b"abc", None), None) == b"abc"


def test_hy03_secretbytes_cannot_be_pickled_or_copied():
    key = new_session_key()
    with pytest.raises(TypeError):
        pickle.dumps(key)
    with pytest.raises(TypeError):
        copy.copy(key)
    with pytest.raises(TypeError):
        copy.deepcopy(key)


def test_hy04_every_key_source_returns_secretbytes():
    pair = KeyPair.generate()
    k = new_session_key()
    wrapped = __import__("security.crypto", fromlist=["x"]).encrypt_session_key(pair.public_pem(), k)
    assert isinstance(k, SecretBytes)
    assert isinstance(pair.decrypt_session_key(wrapped), SecretBytes)
    assert isinstance(_derive(k, b"s", b"info"), SecretBytes)


def test_hy05_objects_holding_keys_have_safe_repr():
    pair, session = KeyPair.generate(), SessionCrypto(new_session_key(), True, b"salt")
    chunk = session.chunk_crypto("t", 3, True)
    for obj in (pair, session, chunk):
        assert "PRIVATE" not in repr(obj) and len(repr(obj)) < 40


# ---------------------------------------------------------------- Traceback
def test_hy06_detector_catches_a_real_leak():
    """Doi chung: neu khoa nam o bien bytes thuong thi bo do PHAI bat duoc (de biet test co y nghia)."""
    secret = bytes(range(32))

    def leaky():
        plain_key = secret + b""
        raise RuntimeError("loi")

    with pytest.raises(RuntimeError) as info:
        leaky()
    assert any(f in app_locals_dump(info.value, root=TESTS) for f in leak_forms(secret))


def test_hy07_session_crypto_failure_does_not_leak_session_key():
    key = new_session_key()
    with pytest.raises(TypeError) as info:
        SessionCrypto(key, True, "salt sai kieu")
    assert_no_leak(app_locals_dump(info.value), key)


def test_hy08_wrong_length_unwrapped_key_does_not_leak():
    pair = KeyPair.generate()
    secret = bytes(range(100, 116))                    # 16 byte, khong phai 32
    public = serialization.load_pem_public_key(pair.public_pem().encode())

    def wrap():
        oaep = padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
        return base64.b64encode(public.encrypt(secret, oaep)).decode()

    with pytest.raises(CryptoError) as info:
        pair.decrypt_session_key(wrap())
    assert_no_leak(app_locals_dump(info.value), secret)


def test_hy09_chunk_crypto_failure_does_not_leak_file_key():
    key = new_session_key()
    session = SessionCrypto(key, True, b"salt")
    send_key = _derive(key, b"salt", b"p2p-chat a2b")
    file_key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"p2p-chat file t").derive(send_key)
    with pytest.raises(ValueError) as info:
        session.chunk_crypto("t", 0, True)             # total_chunks = 0 -> loi trong ChunkCrypto.__init__
    dump = app_locals_dump(info.value)
    assert_no_leak(dump, file_key)
    assert_no_leak(dump, send_key)
    assert_no_leak(dump, key)


def test_hy10_failed_handshake_does_not_leak_session_key(monkeypatch):
    """Peer dong ket noi sau khi nhan khoa phien: Traceback cua ben goi khong chua khoa phien."""
    captured = []
    real = handshake_module.new_session_key

    def spy():
        key = real()
        captured.append(bytes(key))
        return key

    monkeypatch.setattr(handshake_module, "new_session_key", spy)
    sa, sb = socket.socketpair()

    def hostile_responder():
        recv_frame(sb)                                  # PUBLIC_KEY cua ben goi
        send_frame(sb, encode_message(make_message("KEY_EXCHANGE", "hub", "peer-A", {
            "action": "PUBLIC_KEY", "algorithm": "RSA-2048", "key_id": "k",
            "public_key": KeyPair.generate().public_pem()})))
        recv_frame(sb)                                  # SESSION_KEY
        sb.close()                                      # roi bo di, khong gui KEY_CONFIRM

    threading.Thread(target=hostile_responder, daemon=True).start()
    try:
        with pytest.raises(HandshakeError) as info:
            handshake_initiator(sa, KeyPair.generate(), "peer-A", "hub", timeout=5)
    finally:
        sa.close()
    assert len(captured) == 1
    dump = app_locals_dump(info.value)
    assert "handshake_initiator.key" in dump             # chung minh co soi vao frame chua khoa
    assert_no_leak(dump, captured[0])