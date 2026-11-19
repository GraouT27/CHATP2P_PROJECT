
import base64
import hashlib
import os
import socket
import threading
import uuid

from shared.protocol import create_message, create_text_message
from p2p_node.speed_meter import SpeedMeter

from security.handshake import (
    handshake_initiator,
    send_secure,
    recv_secure
)

from security.crypto import KeyPair


CHUNK_SIZE = 48 * 1024
SOCKET_TIMEOUT = 30


class TCPSender:
    def __init__(
        self,
        sender_id,
        receiver_id,
        ip,
        tcp_port,
        keypair
    ):
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.ip = ip
        self.tcp_port = tcp_port
        self.keypair = keypair

        self.sock = None
        self.session = None
        self.peer_fingerprint = None

        self.speed_meter = SpeedMeter()

        self._send_lock = threading.Lock()
        self._connect_lock = threading.Lock()
        self._receive_lock = threading.Lock()

    def connect(self):
        with self._connect_lock:
            if self.sock is not None and self.session is not None:
                return

            self.sock = socket.create_connection(
                (self.ip, self.tcp_port),
                timeout=SOCKET_TIMEOUT
            )

            try:
                result = handshake_initiator(
                    self.sock,
                    self.keypair,
                    self.sender_id,
                    self.receiver_id
                )

                self.session = result.session
                self.peer_fingerprint = result.peer_fingerprint

                print(
                    f"[SENDER] Đã kết nối với {result.peer_id}"
                )

                print(
                    f"[SENDER] Fingerprint: {self.peer_fingerprint}"
                )

                self.sock.settimeout(SOCKET_TIMEOUT)

            except Exception:
                self.sock.close()
                self.sock = None
                self.session = None
                raise

    def close(self):
        with self._connect_lock:
            if self.sock is not None:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

                try:
                    self.sock.close()
                except OSError:
                    pass

            self.sock = None
            self.session = None

    def _send_message(self, message):
        if self.sock is None or self.session is None:
            raise ConnectionError("Chưa kết nối đến peer")

        with self._send_lock:
            send_secure(
                self.sock,
                self.session,
                message
            )

    def _recv_message(self):
        if self.sock is None or self.session is None:
            raise ConnectionError("Chưa kết nối đến peer")

        with self._receive_lock:
            return recv_secure(
                self.sock,
                self.session
            )

    def send_text(self, text):
        self.connect()

        message = create_text_message(
            self.sender_id,
            self.receiver_id,
            text
        )

        self._send_message(message)

    @staticmethod
    def _calculate_sha256(file_path):
        digest = hashlib.sha256()

        with open(file_path, "rb") as file:
            while True:
                chunk = file.read(CHUNK_SIZE)

                if not chunk:
                    break

                digest.update(chunk)

        return digest.hexdigest()

    @staticmethod
    def _check_cancelled(cancel_event):
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("Tác vụ truyền file đã bị hủy")

    def _send_cancel(self, transfer_id):
        message = create_message(
            self.sender_id,
            self.receiver_id,
            "FILE_CANCEL",
            {
                "action": "CANCEL",
                "transfer_id": transfer_id
            }
        )

        self._send_message(message)

    def send_file(
        self,
        file_path,
        progress_callback=None,
        cancel_event=None
    ):
        if not os.path.isfile(file_path):
            raise FileNotFoundError(file_path)

        self.connect()

        transfer_id = str(uuid.uuid4())
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        sha256 = self._calculate_sha256(file_path)

        self.speed_meter.start()

        started = False

        try:
            self._check_cancelled(cancel_event)

            start_message = create_message(
                self.sender_id,
                self.receiver_id,
                "FILE_START",
                {
                    "action": "START",
                    "transfer_id": transfer_id,
                    "file_name": file_name,
                    "file_size": file_size,
                    "sha256": sha256
                }
            )

            self._send_message(start_message)
            started = True

            sent_size = 0
            chunk_index = 0

            with open(file_path, "rb") as file:
                while True:
                    self._check_cancelled(cancel_event)

                    chunk = file.read(CHUNK_SIZE)

                    if not chunk:
                        break

                    encoded_chunk = base64.b64encode(
                        chunk
                    ).decode("ascii")

                    chunk_message = create_message(
                        self.sender_id,
                        self.receiver_id,
                        "FILE_CHUNK",
                        {
                            "action": "CHUNK",
                            "transfer_id": transfer_id,
                            "chunk_index": chunk_index,
                            "data": encoded_chunk
                        }
                    )

                    self._send_message(chunk_message)

                    sent_size += len(chunk)
                    chunk_index += 1

                    speed = self.speed_meter.update(len(chunk))

                    progress = (
                        sent_size / file_size * 100
                        if file_size > 0
                        else 100.0
                    )

                    if progress_callback:
                        progress_callback(progress, speed)

            self._check_cancelled(cancel_event)

            end_message = create_message(
                self.sender_id,
                self.receiver_id,
                "FILE_END",
                {
                    "action": "END",
                    "transfer_id": transfer_id
                }
            )

            self._send_message(end_message)

            response = self._recv_message()

            response_type = response["header"]["message_type"]
            response_payload = response["payload"]

            if response_payload.get("transfer_id") != transfer_id:
                raise ValueError("ACK không khớp transfer_id")

            if response_type == "FILE_ERROR":
                raise RuntimeError(
                    response_payload.get(
                        "error",
                        "Bên nhận báo lỗi"
                    )
                )

            if response_type != "FILE_ACK":
                raise ValueError("Phản hồi từ peer không hợp lệ")

            if response_payload.get("action") != "ACK":
                raise ValueError("FILE_ACK không hợp lệ")

            if response_payload.get("status") != "COMPLETED":
                raise RuntimeError("Bên nhận chưa hoàn tất lưu file")

            if progress_callback:
                progress_callback(
                    100.0,
                    self.speed_meter.get_average_speed()
                )

            return transfer_id

        except InterruptedError:
            if started:
                try:
                    self._send_cancel(transfer_id)
                except (OSError, ConnectionError, CryptoError):
                    pass

            raise

        except Exception:
            raise


# ===================== GUI P2P DIRECT & PERSISTENT SENDER =====================

from typing import Tuple
from config import CONNECT_TIMEOUT, SOCKET_TIMEOUT
from shared.protocol import pack_message
from security.logger import log


def send_message_direct(ip: str, port: int, header: dict, payload: bytes = b"") -> Tuple[bool, str]:
    """
    Kết nối TCP tới Peer đích, gửi gói tin có framing và đóng kết nối (dành cho control packets).
    Trả về (thành_công, thông_báo_lỗi).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(CONNECT_TIMEOUT)

    try:
        sock.connect((ip, port))
        sock.settimeout(SOCKET_TIMEOUT)
        data = pack_message(header, payload)
        sock.sendall(data)
        return True, "OK"
    except (socket.timeout, TimeoutError):
        err = f"Hết thời gian chờ kết nối tới {ip}:{port}"
        log.warning(err)
        return False, err
    except ConnectionRefusedError:
        err = f"Peer tại {ip}:{port} từ chối kết nối (chưa mở hoặc đã tắt)"
        log.warning(err)
        return False, err
    except (ConnectionResetError, BrokenPipeError):
        err = f"Mất kết nối đột ngột với {ip}:{port}"
        log.error(err)
        return False, err
    except Exception as e:
        err = f"Lỗi không xác định khi gửi tới {ip}:{port}: {e}"
        log.error(err)
        return False, err
    finally:
        try:
            sock.close()
        except Exception:
            pass


class PeerSocketClient:
    """
    Giữ kết nối TCP lâu dài (Persistent Socket) tới một Peer để gửi streaming tin nhắn/chunks.
    """
    def __init__(self, ip: str, port: int):
        self.ip = ip
        self.port = port
        self.peer_id = f"{ip}:{port}"
        self.sock: socket.socket = None
        self.is_connected = False

    def connect(self) -> bool:
        """Mở kết nối TCP tới Peer."""
        if self.is_connected and self.sock:
            return True

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(CONNECT_TIMEOUT)
        try:
            self.sock.connect((self.ip, self.port))
            self.sock.settimeout(SOCKET_TIMEOUT)
            self.is_connected = True
            log.info(f"Đã mở kết nối TCP thành công tới {self.peer_id}")
            return True
        except Exception as e:
            log.error(f"Không thể kết nối tới {self.peer_id}: {e}")
            self.close()
            return False

    def send(self, header: dict, payload: bytes = b"") -> bool:
        """Gửi gói tin qua socket hiện hành."""
        if not self.is_connected or not self.sock:
            if not self.connect():
                return False

        try:
            data = pack_message(header, payload)
            self.sock.sendall(data)
            return True
        except Exception as e:
            log.error(f"Lỗi khi gửi dữ liệu tới {self.peer_id}: {e}")
            self.close()
            return False

    def close(self):
        """Đóng kết nối an toàn."""
        self.is_connected = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

