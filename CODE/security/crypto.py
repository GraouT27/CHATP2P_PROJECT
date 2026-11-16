"""RSA-2048 sinh dong (trao khoa) + AES-256-GCM (ma hoa du lieu).

Quy tac:
- Khoa rieng RSA chi nam trong RAM, khong ghi ra ddia, khong co trong code.
- Moi ket noi mot khoa phien K (32 byte ngau nhien). HKDF tach 2 khoa theo chieu.
- Khung ma hoa: seq(8) | nonce(12) | ciphertext | tag(16). AAD = seq.
- KHONG ghi log khoa, plaintext hay ciphertext day du.

Luu y cho nguoi dung SessionCrypto: encrypt() tang so seq, nen viec goi
encrypt() va sendall() phai nam trong cung mot lock neu nhieu luong cung gui,
neu khong goi se toi noi nhan sai thu tu va bi coi la phat lai (ReplayError).
"""
import base64
import binascii
import hashlib
import os
import secrets
import threading

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

KEY_SIZE = 32          # AES-256
NONCE_SIZE = 12
TAG_SIZE = 16
SEQ_SIZE = 8
OVERHEAD = SEQ_SIZE + NONCE_SIZE + TAG_SIZE  # 36 byte them vao moi goi

_OAEP = padding.OAEP(
    mgf=padding.MGF1(algorithm=hashes.SHA256()),
    algorithm=hashes.SHA256(),
    label=None,
)


class CryptoError(Exception):
    """Loi chung cua module bao mat."""


class DecryptError(CryptoError):
    """Giai ma that bai: sai khoa, goi bi sua hoac sai dinh dang."""


class ReplayError(DecryptError):
    """Goi co so thu tu cu (nghi bi phat lai)."""


def _load_public(pem: str):
    try:
        return serialization.load_pem_public_key(pem.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise CryptoError("Khoa cong khai khong hop le") from exc


def _fingerprint_raw(public_key) -> str:
    der = public_key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()


def _group(hex_str: str) -> str:
    return " ".join(hex_str[i:i + 4] for i in range(0, len(hex_str), 4)).upper()


def fingerprint_of_pem(pem: str) -> str:
    """Dau van tay cua khoa cong khai nhan duoc (de hien thi tren GUI)."""
    return _group(_fingerprint_raw(_load_public(pem)))


class KeyPair:
    """Cap khoa RSA-2048 sinh dong. Khoa rieng khong the xuat ra ngoai."""

    def __init__(self, _private_key):
        self.__private = _private_key

    @classmethod
    def generate(cls) -> "KeyPair":
        return cls(rsa.generate_private_key(public_exponent=65537, key_size=2048))

    def public_pem(self) -> str:
        pem = self.__private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return pem.decode("ascii")

    def fingerprint(self) -> str:
        return _group(_fingerprint_raw(self.__private.public_key()))

    def short_id(self) -> str:
        """8 ky tu dau cua fingerprint, dung trong log va key_id."""
        return _fingerprint_raw(self.__private.public_key())[:8]

    def decrypt_session_key(self, encrypted_b64: str) -> bytes:
        try:
            cipher = base64.b64decode(encrypted_b64, validate=True)
            key = self.__private.decrypt(cipher, _OAEP)
        except (binascii.Error, ValueError, TypeError) as exc:
            raise CryptoError("Khong giai ma duoc khoa phien") from exc
        if len(key) != KEY_SIZE:
            raise CryptoError("Khoa phien sai do dai")
        return key

    def __repr__(self) -> str:
        return f"<KeyPair {self.short_id()}>"


def new_session_key() -> bytes:
    return secrets.token_bytes(KEY_SIZE)


def encrypt_session_key(peer_public_pem: str, session_key: bytes) -> str:
    """Ma hoa K bang RSA-OAEP-SHA256, tra ve chuoi base64 de dat vao JSON."""
    if len(session_key) != KEY_SIZE:
        raise ValueError("Khoa phien phai dai 32 byte")
    cipher = _load_public(peer_public_pem).encrypt(session_key, _OAEP)
    return base64.b64encode(cipher).decode("ascii")


def handshake_salt(initiator_public_pem: str, responder_public_pem: str) -> bytes:
    """Salt cho HKDF = SHA-256(khoa cong khai ben goi || khoa cong khai ben nhan)."""
    data = initiator_public_pem.encode("ascii") + responder_public_pem.encode("ascii")
    return hashlib.sha256(data).digest()


def _derive(session_key: bytes, salt: bytes, info: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=KEY_SIZE, salt=salt, info=info).derive(session_key)


class SessionCrypto:
    """Ma hoa/giai ma moi goi tin cua mot ket noi bang AES-256-GCM."""

    def __init__(self, session_key: bytes, is_initiator: bool, salt: bytes = b""):
        if len(session_key) != KEY_SIZE:
            raise ValueError("Khoa phien phai dai 32 byte")
        a2b_key = _derive(session_key, salt, b"p2p-chat a2b")
        b2a_key = _derive(session_key, salt, b"p2p-chat b2a")
        self.__send_key, self.__recv_key = (a2b_key, b2a_key) if is_initiator else (b2a_key, a2b_key)
        self._send, self._recv = AESGCM(self.__send_key), AESGCM(self.__recv_key)
        self._send_seq = 0
        self._recv_seq = 0
        self._lock = threading.Lock()

    def encrypt(self, plaintext: bytes) -> bytes:
        if not isinstance(plaintext, (bytes, bytearray)):
            raise TypeError("plaintext phai la bytes")
        with self._lock:
            self._send_seq += 1
            seq = self._send_seq.to_bytes(SEQ_SIZE, "big")
        nonce = os.urandom(NONCE_SIZE)
        return seq + nonce + self._send.encrypt(nonce, bytes(plaintext), seq)

    def decrypt(self, blob: bytes) -> bytes:
        if len(blob) < OVERHEAD:
            raise DecryptError("Goi qua ngan")
        seq = blob[:SEQ_SIZE]
        nonce = blob[SEQ_SIZE:SEQ_SIZE + NONCE_SIZE]
        cipher = blob[SEQ_SIZE + NONCE_SIZE:]
        try:
            plain = self._recv.decrypt(nonce, cipher, seq)
        except InvalidTag as exc:
            raise DecryptError("Giai ma that bai") from exc
        number = int.from_bytes(seq, "big")
        with self._lock:
            if number <= self._recv_seq:
                raise ReplayError("Goi cu bi gui lai")
            self._recv_seq = number
        return plain

    def chunk_crypto(self, transfer_id: str, total_chunks: int, sending: bool) -> "ChunkCrypto":
        """Khoa rieng cho 1 lan truyen file. Ben gui dung sending=True, ben nhan sending=False
        (hai ben tu dan xuat ra cung mot khoa, khong can trao doi them)."""
        base = self.__send_key if sending else self.__recv_key
        file_key = HKDF(algorithm=hashes.SHA256(), length=KEY_SIZE, salt=None,
                        info=b"p2p-chat file " + transfer_id.encode("utf-8")).derive(base)
        return ChunkCrypto(file_key, total_chunks)

    def __repr__(self) -> str:
        return "<SessionCrypto>"


CHUNK_OVERHEAD = TAG_SIZE  # moi chunk chi them 16 byte (tag), khong can gui nonce


class ChunkCrypto:
    """Ma hoa/giai ma tung chunk file bang AES-256-GCM, doc lap thu tu va doc lap luong.

    - Nonce suy ra tu so thu tu chunk, AAD = (index, tong so chunk) nen chunk bi doi cho,
      bi sua, hoac thuoc file khac deu bi tu choi.
    - Giai ma duoc theo THU TU BAT KY (phu hop truyen da luong); an toan khi nhieu luong cung goi.
    - transfer_id phai KHONG TRUNG giua cac lan truyen trong cung phien (UUID). Gui lai mot chunk
      thi phai gui lai DUNG du lieu cu, khong ma hoa du lieu khac cung so thu tu.
    """

    def __init__(self, file_key: bytes, total_chunks: int):
        if len(file_key) != KEY_SIZE:
            raise ValueError("Khoa file phai dai 32 byte")
        if total_chunks < 1:
            raise ValueError("total_chunks phai >= 1")
        self._aead = AESGCM(file_key)
        self._total = total_chunks

    @staticmethod
    def _nonce(index: int) -> bytes:
        return b"\x00" * 4 + index.to_bytes(8, "big")

    def _aad(self, index: int) -> bytes:
        return index.to_bytes(8, "big") + self._total.to_bytes(8, "big")

    def encrypt_chunk(self, index: int, data: bytes) -> bytes:
        if not 0 <= index < self._total:
            raise ValueError("index ngoai khoang")
        return self._aead.encrypt(self._nonce(index), bytes(data), self._aad(index))

    def decrypt_chunk(self, index: int, blob: bytes) -> bytes:
        if not isinstance(index, int) or not 0 <= index < self._total:
            raise DecryptError("index chunk khong hop le")
        try:
            return self._aead.decrypt(self._nonce(index), bytes(blob), self._aad(index))
        except InvalidTag as exc:
            raise DecryptError("Giai ma chunk that bai") from exc

    def __repr__(self) -> str:
        return "<ChunkCrypto>"