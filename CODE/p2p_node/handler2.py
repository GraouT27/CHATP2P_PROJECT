
import base64
import binascii

from p2p_node.handler import MessageHandler
from shared.protocol import create_message


class FileMessageCallbacks:
    """Đăng ký và xử lý các message truyền file."""

    def __init__(self, storage, local_peer_id, remote_peer_id):
        self.storage = storage
        self.local_peer_id = local_peer_id
        self.remote_peer_id = remote_peer_id

        self.message_handler = MessageHandler()
        self.active_transfers = set()

        self._register_callbacks()

    def _register_callbacks(self):
        self.message_handler.register(
            "FILE_START",
            self._handle_file_start
        )

        self.message_handler.register(
            "FILE_CHUNK",
            self._handle_file_chunk
        )

        self.message_handler.register(
            "FILE_END",
            self._handle_file_end
        )

    def _send_message(self, message_type, payload, send_reply):
        message = create_message(
            sender_id=self.local_peer_id,
            receiver_id=self.remote_peer_id,
            message_type=message_type,
            payload=payload
        )

        send_reply(message)

    def _send_error(self, transfer_id, error, send_reply):
        self._send_message(
            "FILE_ERROR",
            {
                "action": "ERROR",
                "transfer_id": transfer_id or "",
                "error": str(error)
            },
            send_reply
        )

    def _handle_file_start(self, message, send_reply):
        payload = message["payload"]
        transfer_id = payload.get("transfer_id")

        try:
            if payload.get("action") != "START":
                raise ValueError("Action FILE_START không hợp lệ")

            self.storage.start_file(
                transfer_id=transfer_id,
                file_name=payload["file_name"],
                file_size=payload["file_size"],
                sha256=payload["sha256"]
            )

            self.active_transfers.add(transfer_id)

        except Exception as exc:
            self._send_error(transfer_id, exc, send_reply)

    def _handle_file_chunk(self, message, send_reply):
        payload = message["payload"]
        transfer_id = payload.get("transfer_id")

        try:
            if payload.get("action") != "CHUNK":
                raise ValueError("Action FILE_CHUNK không hợp lệ")

            encoded_data = payload["data"]

            if not isinstance(encoded_data, str):
                raise ValueError("Dữ liệu chunk không hợp lệ")

            chunk = base64.b64decode(
                encoded_data,
                validate=True
            )

            self.storage.write_chunk(
                transfer_id=transfer_id,
                chunk=chunk,
                chunk_index=payload["chunk_index"]
            )

        except (ValueError, KeyError, TypeError, binascii.Error) as exc:
            self.storage.abort_file(transfer_id)
            self.active_transfers.discard(transfer_id)
            self._send_error(transfer_id, exc, send_reply)

    def _handle_file_end(self, message, send_reply):
        payload = message["payload"]
        transfer_id = payload.get("transfer_id")

        try:
            if payload.get("action") != "END":
                raise ValueError("Action FILE_END không hợp lệ")

            saved_path = self.storage.finish_file(transfer_id)
            self.active_transfers.discard(transfer_id)

            self._send_message(
                "FILE_ACK",
                {
                    "action": "ACK",
                    "transfer_id": transfer_id,
                    "status": "COMPLETED",
                    "saved_path": saved_path
                },
                send_reply
            )

        except Exception as exc:
            self.storage.abort_file(transfer_id)
            self.active_transfers.discard(transfer_id)
            self._send_error(transfer_id, exc, send_reply)

    def handle_message(self, message, send_reply):
        """Chuyển message cho MessageHandler của TV4."""
        self.message_handler.handle_message(
            message,
            send_reply
        )

    def close(self):
        """Xóa các file tạm thuộc kết nối này."""
        for transfer_id in list(self.active_transfers):
            self.storage.abort_file(transfer_id)

        self.active_transfers.clear()
