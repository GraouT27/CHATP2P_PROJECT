"""
Crypto Manager Module - Quản lý bảo mật, mã hóa RSA-2048 & AES-256-GCM (TV6).

Chức năng:
1. Sinh cặp khóa RSA 2048-bit động trong RAM khi khởi tạo (không lưu cứng khóa bí mật).
2. Trao đổi khóa bảo mật: Sinh Khóa phiên AES-256 ngẫu nhiên, mã hóa bằng RSA Public Key của đối tác (OAEP-SHA256).
3. Mã hóa/giải mã toàn bộ luồng tin nhắn và từng chunk file bằng chuẩn AES-256-GCM (xác thực toàn vẹn AEAD).
4. Tính toán và đối chiếu mã băm SHA-256 cho từng mảnh dữ liệu và toàn bộ file.
5. Kiểm tra dữ liệu và chống lộ khóa bí mật trong traceback.
"""

import os
import base64
import hashlib
from typing import Optional, Tuple
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from security.logger import log


class CryptoManager:
    """Quản lý khóa RSA, khóa phiên đối xứng AES-256 và mã hóa/giải mã cho Peer."""

    def __init__(self):
        # 1. Sinh động cặp khóa RSA 2048-bit (e=65537)
        self._private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        self._public_key = self._private_key.public_key()

        # Quản lý khóa cho từng Peer: {peer_id: bytes}
        self._peer_session_keys: dict[str, bytes] = {}
        # Quản lý RSA Public Key của đối tác: {peer_id: RSAPublicKey}
        self._peer_public_keys: dict[str, object] = {}

    # ========================== RSA KEY MANAGEMENT ==========================

    def get_public_key_pem(self) -> str:
        """Xuất RSA Public Key dưới dạng chuỗi PEM để gửi qua mạng."""
        pem = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return pem.decode("utf-8")

    @staticmethod
    def _get_local_ips() -> set[str]:
        local_ips = {"127.0.0.1", "localhost", "::1"}
        try:
            import socket
            for l_ip in socket.gethostbyname_ex(socket.gethostname())[2]:
                local_ips.add(l_ip)
        except Exception:
            pass
        return local_ips

    def _alias_keys_for_peer(self, store: dict, peer_id: str, value) -> None:
        """Lưu giá trị khóa theo peer_id và các IP cục bộ nếu cùng port (tránh lệch 127.0.0.1 vs LAN IP)."""
        store[peer_id] = value
        ip, _, port = peer_id.partition(":")
        if port:
            local_ips = self._get_local_ips()
            if ip in local_ips:
                for l_ip in local_ips:
                    store[f"{l_ip}:{port}"] = value

    def register_peer_public_key(self, peer_id: str, pem_str: str) -> bool:
        """Đăng ký RSA Public Key của một Peer từ chuỗi PEM."""
        try:
            public_key = serialization.load_pem_public_key(pem_str.encode("utf-8"))
            self._alias_keys_for_peer(self._peer_public_keys, peer_id, public_key)
            return True
        except Exception as e:
            log.error(f"Lỗi nạp RSA Public Key từ {peer_id}: {e}")
            return False

    def generate_and_encrypt_session_key(self, peer_id: str) -> Optional[str]:
        """
        Sinh khóa phiên AES-256 (32 bytes ngẫu nhiên) và mã hóa bằng RSA Public Key của Peer.
        Trả về chuỗi Base64 đã mã hóa để truyền qua mạng.
        """
        peer_rsa_pub = self._find_public_key(peer_id)
        if not peer_rsa_pub:
            log.warning(f"Chưa có RSA Public Key của {peer_id} để tạo session key")
            return None

        # Sinh 32 bytes (256 bits) ngẫu nhiên bằng bộ sinh số ngẫu nhiên an toàn của OS
        session_key = os.urandom(32)
        self._alias_keys_for_peer(self._peer_session_keys, peer_id, session_key)

        encrypted_key = peer_rsa_pub.encrypt(
            session_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return base64.b64encode(encrypted_key).decode("utf-8")

    def receive_and_decrypt_session_key(self, peer_id: str, encrypted_key_b64: str) -> bool:
        """
        Nhận khóa phiên AES-256 từ Peer đối tác và giải mã bằng RSA Private Key của mình.
        """
        try:
            encrypted_data = base64.b64decode(encrypted_key_b64.encode("utf-8"))
            session_key = self._private_key.decrypt(
                encrypted_data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
            if len(session_key) == 32:
                self._alias_keys_for_peer(self._peer_session_keys, peer_id, session_key)
                return True
            return False
        except Exception as e:
            log.error(f"Không thể giải mã Session Key từ {peer_id}: {e}")
            return False

    def _find_in_store(self, store: dict, peer_id: str):
        """Tra cứu khóa chính xác theo IP:port (chỉ alias sang IP cục bộ khác nếu trùng đúng port)."""
        if peer_id in store:
            return store[peer_id]
        ip, _, port = peer_id.partition(":")
        if port:
            local_ips = self._get_local_ips()
            if ip in local_ips:
                for l_ip in local_ips:
                    cand = f"{l_ip}:{port}"
                    if cand in store:
                        return store[cand]
        return None

    def _find_public_key(self, peer_id: str):
        return self._find_in_store(self._peer_public_keys, peer_id)

    def _find_session_key(self, peer_id: str) -> Optional[bytes]:
        return self._find_in_store(self._peer_session_keys, peer_id)

    def has_session_key(self, peer_id: str) -> bool:
        """Kiểm tra xem đã thiết lập khóa phiên AES-256 với Peer chưa."""
        return self._find_session_key(peer_id) is not None

    def remove_peer_keys(self, peer_id: str):
        """Xóa toàn bộ khóa của Peer khi ngắt kết nối (chỉ xóa alias cùng host & cùng port)."""
        self._peer_session_keys.pop(peer_id, None)
        self._peer_public_keys.pop(peer_id, None)
        ip, _, port = peer_id.partition(":")
        if port:
            local_ips = self._get_local_ips()
            if ip in local_ips:
                for l_ip in local_ips:
                    self._peer_session_keys.pop(f"{l_ip}:{port}", None)
                    self._peer_public_keys.pop(f"{l_ip}:{port}", None)

    # ========================== AES-256-GCM ENCRYPTION ==========================

    def encrypt_bytes(self, peer_id: str, plaintext: bytes) -> Optional[Tuple[bytes, bytes]]:
        """
        Mã hóa dữ liệu nhị phân bằng AES-256-GCM.
        Trả về (ciphertext_with_tag, nonce).
        """
        key = self._find_session_key(peer_id)
        if not key:
            return None

        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # 96-bit nonce chuẩn cho GCM
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        return ciphertext, nonce

    def decrypt_bytes(self, peer_id: str, ciphertext: bytes, nonce: bytes) -> Optional[bytes]:
        """
        Giải mã dữ liệu nhị phân bằng AES-256-GCM và xác thực tag AEAD.
        Trả về plaintext bytes hoặc None nếu giải mã thất bại / bị giả mạo.
        """
        key = self._find_session_key(peer_id)
        if not key:
            return None

        try:
            aesgcm = AESGCM(key)
            return aesgcm.decrypt(nonce, ciphertext, None)
        except Exception:
            return None

    def encrypt_text(self, peer_id: str, text: str) -> Optional[Tuple[str, str]]:
        """
        Mã hóa chuỗi văn bản.
        Trả về (ciphertext_b64, nonce_b64).
        """
        res = self.encrypt_bytes(peer_id, text.encode("utf-8"))
        if res:
            ct, nonce = res
            return (
                base64.b64encode(ct).decode("utf-8"),
                base64.b64encode(nonce).decode("utf-8"),
            )
        return None

    def decrypt_text(self, peer_id: str, ciphertext_b64: str, nonce_b64: str) -> Optional[str]:
        """Giải mã văn bản từ Base64."""
        try:
            ct = base64.b64decode(ciphertext_b64.encode("utf-8"))
            nonce = base64.b64decode(nonce_b64.encode("utf-8"))
            dec_bytes = self.decrypt_bytes(peer_id, ct, nonce)
            if dec_bytes is not None:
                return dec_bytes.decode("utf-8")
        except Exception:
            pass
        return None

    # ========================== HASHING & INTEGRITY (SHA-256) ==========================

    @staticmethod
    def sha256_bytes(data: bytes) -> str:
        """Tính mã băm SHA-256 của chuỗi bytes."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def sha256_file(file_path: str) -> Optional[str]:
        """Tính mã băm SHA-256 của toàn bộ file."""
        if not os.path.exists(file_path):
            return None
        h = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return None

    @staticmethod
    def verify_sha256(data: bytes, expected_hash: str) -> bool:
        """Kiểm tra đối chiếu mã băm SHA-256."""
        if not expected_hash:
            return False
        return hashlib.sha256(data).hexdigest().lower() == expected_hash.lower()
