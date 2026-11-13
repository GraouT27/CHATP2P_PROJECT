
import base64
import hashlib
import os
import socket
import time
import uuid

from shared.protocol import (
    create_message,
    create_text_message,
    encode_message,
    recv_message
)

from p2p_node.speed_meter import SpeedMeter


CHUNK_SIZE = 48 * 1024
SOCKET_TIMEOUT = 30


class TCPSender:
    """Gửi text và file đến một peer qua TCP."""

    def __init__(self, sender_id, receiver_id, ip, tcp_port):
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.ip = ip
        self.tcp_port = tcp_port

        self.sock = None
        self.speed_meter = SpeedMeter()

    def connect(self):
        if self.sock is not None:
            return

        self.sock = socket.create_connection(
            (self.ip, self.tcp_port),
            timeout=SOCKET_TIMEOUT
        )
        self.sock.settimeout(SOCKET_TIMEOUT)

    def close(self):
        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            self.sock.close()
            self.sock = None

    def _send_message(self, message):
        if self.sock is None:
            raise ConnectionError("Chưa kết nối đến peer")

        self.sock.sendall(encode_message(message))

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

    def _check_cancelled(self, cancel_event):
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("Tác vụ truyền file đã bị hủy")

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

        sent_size = 0
        chunk_index = 0

        try:
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

            # Chờ bên nhận xác nhận lưu file.
            response = recv_message(self.sock)

            response_type = response["header"]["message_type"]
            response_payload = response["payload"]

            if response_payload.get("transfer_id") != transfer_id:
                raise ValueError("ACK không khớp transfer_id")

            if response_type == "FILE_ERROR":
                raise RuntimeError(
                    response_payload.get("error", "Bên nhận báo lỗi")
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

        except Exception:
            raise
