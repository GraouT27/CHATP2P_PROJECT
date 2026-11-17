"""Phân loại message đã đọc đủ; callback sở hữu xử lý và phản hồi."""

from collections.abc import Callable

from shared.protocol import validate_message


class MessageHandler:
    """Đăng ký callback theo header.message_type, không đọc socket."""

    def __init__(self):
        self._callbacks = {}

    def register(self, message_type: str, callback: Callable) -> None:
        if not isinstance(message_type, str) or not message_type.strip():
            raise ValueError("message_type không hợp lệ")
        if not callable(callback):
            raise TypeError("callback phải gọi được")
        if message_type in self._callbacks:
            raise ValueError(f"Đã đăng ký {message_type}")
        self._callbacks[message_type] = callback

    def handle_message(self, message: dict, send_reply: Callable) -> None:
        validate_message(message)
        if not callable(send_reply):
            raise TypeError("send_reply phải gọi được")

        message_type = message["header"]["message_type"]
        callback = self._callbacks.get(message_type)
        if callback is None:
            raise ValueError(f"Chưa có handler cho {message_type}")

        callback(message, send_reply)
