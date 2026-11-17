"""Bo ghi log an toan (TV1, Chang 3).

- Moi dong log la 1 JSON (JSON Lines): ts, level, event, msg + cac truong them.
- Tu dong loc: khoa PEM, chuoi hex/base64 dai, bytes, va cac truong nhay cam
  (text, payload, *_key, password...) truoc khi ghi ra file.
- Ghi file xoay vong (1 MB x 5), thu muc logs/ da nam trong .gitignore.
- log_event() khong bao gio nem loi: loi ghi log khong duoc lam sap ung dung.

Cach dung:
    from logger import setup_logging, log_event, Event
    setup_logging("logs")                       # goi 1 lan luc khoi dong
    log_event(Event.PEER_CONNECTED, peer="ab12cd34", addr=mask_ip("192.168.1.23"))
    log_event(Event.ERROR, "ERROR", reason="timeout")
"""
import json
import logging
import os
import re
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

LOGGER_NAME = "p2p"


class Event:
    """Ma su kien co dinh."""
    APP_START = "APP_START"
    APP_STOP = "APP_STOP"
    KEYPAIR_GENERATED = "KEYPAIR_GENERATED"
    PEER_CONNECTED = "PEER_CONNECTED"
    PEER_DISCONNECTED = "PEER_DISCONNECTED"
    HANDSHAKE_START = "HANDSHAKE_START"
    HANDSHAKE_OK = "HANDSHAKE_OK"
    HANDSHAKE_FAIL = "HANDSHAKE_FAIL"
    DECRYPT_FAIL = "DECRYPT_FAIL"
    REPLAY_DETECTED = "REPLAY_DETECTED"
    SOCKET_ERROR = "SOCKET_ERROR"
    ERROR = "ERROR"


# ---------------------------------------------------------------- loc du lieu
_PEM_FULL = re.compile(r"-----BEGIN [A-Z ]+-----.*?-----END [A-Z ]+-----", re.DOTALL)
_PEM_EDGE = re.compile(r"-----(?:BEGIN|END) [A-Z ]+-----")
_HEX = re.compile(r"\b[0-9a-fA-F]{32,}\b")
_B64 = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")

_SENSITIVE_EXACT = {
    "key", "session_key", "private_key", "public_key", "aes_key", "rsa_key",
    "plaintext", "ciphertext", "text", "content", "payload", "original_payload",
    "data", "blob", "body", "message", "encrypted_session_key",
}
_SENSITIVE_PARTS = ("password", "passwd", "secret", "token", "private")
_MAX_DEPTH = 5


def is_sensitive_key(name: str) -> bool:
    lowered = str(name).lower()
    return (
        lowered in _SENSITIVE_EXACT
        or lowered.endswith("_key")
        or any(part in lowered for part in _SENSITIVE_PARTS)
    )


def sanitize_text(text: str) -> str:
    text = _PEM_FULL.sub("[REDACTED:PEM]", text)
    text = _PEM_EDGE.sub("[REDACTED:PEM]", text)
    text = _HEX.sub("[REDACTED:HEX]", text)
    return _B64.sub("[REDACTED:B64]", text)


def sanitize_value(value, key=None, depth=0):
    if key is not None and is_sensitive_key(key):
        return "[REDACTED]"
    if depth > _MAX_DEPTH:
        return "[...]"
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"[REDACTED:bytes len={len(value)}]"
    if isinstance(value, str):
        return sanitize_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, dict):
        return {str(k): sanitize_value(v, str(k), depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize_value(v, None, depth + 1) for v in value]
    return sanitize_text(str(value))


def mask_ip(ip: str) -> str:
    """192.168.1.23 -> 192.168.1.x (khong ghi IP day du)."""
    parts = str(ip).split(".")
    if len(parts) == 4:
        return ".".join(parts[:3] + ["x"])
    return "[masked]"


# ------------------------------------------------------------------ dinh dang
class SecureJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        stamp = datetime.fromtimestamp(record.created, timezone.utc)
        data = {
            "ts": stamp.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "event": getattr(record, "p2p_event", "LOG"),
        }
        fields = getattr(record, "p2p_fields", None) or {}
        for name, value in fields.items():
            if name not in data:
                data[name] = sanitize_value(value, name)
        data["msg"] = sanitize_text(record.getMessage())
        if record.exc_info and record.exc_info[0] is not None:
            data["exc_type"] = record.exc_info[0].__name__
            data["exc_msg"] = sanitize_text(str(record.exc_info[1]))
        return json.dumps(data, ensure_ascii=False, default=str)


# ------------------------------------------------------------------ cau hinh
logging.getLogger(LOGGER_NAME).addHandler(logging.NullHandler())


def shutdown_logging() -> None:
    log = logging.getLogger(LOGGER_NAME)
    for handler in list(log.handlers):
        if getattr(handler, "_p2p_handler", False):
            handler.close()
            log.removeHandler(handler)


def setup_logging(log_dir: str = "logs", level="INFO", console: bool = False,
                  max_bytes: int = 1_000_000, backup_count: int = 5) -> logging.Logger:
    """Cau hinh bo ghi log. Goi nhieu lan van an toan (khong nhan doi handler)."""
    shutdown_logging()
    os.makedirs(log_dir, exist_ok=True)
    log = logging.getLogger(LOGGER_NAME)
    log.setLevel(_to_level(level))
    log.propagate = False
    formatter = SecureJsonFormatter()
    handlers = [RotatingFileHandler(
        os.path.join(log_dir, "app.log"), maxBytes=max_bytes,
        backupCount=backup_count, encoding="utf-8")]
    if console:
        handlers.append(logging.StreamHandler())
    for handler in handlers:
        handler.setFormatter(formatter)
        handler._p2p_handler = True
        log.addHandler(handler)
    return log


def _to_level(level) -> int:
    if isinstance(level, int):
        return level
    return logging.getLevelName(str(level).upper()) if str(level).upper() in (
        "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL") else logging.INFO


def log_event(event: str, level="INFO", msg: str = "", session=None, peer=None, **fields) -> None:
    """Ghi 1 su kien. Khong bao gio nem loi."""
    try:
        extra_fields = dict(fields)
        if session is not None:
            extra_fields["session"] = session
        if peer is not None:
            extra_fields["peer"] = peer
        logging.getLogger(LOGGER_NAME).log(
            _to_level(level), "%s", msg,
            extra={"p2p_event": event, "p2p_fields": extra_fields},
        )
    except Exception:  # noqa: BLE001 - log loi khong duoc lam sap ung dung
        pass
