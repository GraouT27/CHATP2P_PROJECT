"""
Safe Logger Module - Ghi log an toàn và bảo vệ bí mật cho Chat P2P (TV6).

Yêu cầu kỹ thuật sống còn:
- Ghi log các sự kiện quan trọng: Thời gian, Kết nối, Ngắt kết nối, Lỗi, Thao tác chính.
- Bảo mật: Tự động lọc bỏ (Sanitize/Redact) Private Key, Session Key, Secret, Token ra khỏi file log.
- Không bao giờ in khóa bí mật ra console hoặc traceback.
"""

import os
import re
import sys
import logging
from datetime import datetime

# Biểu thức chính quy phát hiện dữ liệu nhạy cảm
SENSITIVE_PATTERNS = [
    (r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----', '[REDACTED_RSA_PRIVATE_KEY]'),
    (r'("session_key":\s*")[^"]+(")', r'\1[REDACTED_SESSION_KEY]\2'),
    (r'("encrypted_key":\s*")[^"]+(")', r'\1[REDACTED_ENCRYPTED_KEY]\2'),
    (r'("nonce":\s*")[^"]+(")', r'\1[REDACTED_NONCE]\2'),
    (r'("password":\s*")[^"]+(")', r'\1[REDACTED_PASSWORD]\2'),
    (r'([a-fA-F0-9]{64})', r'[REDACTED_HEX_KEY_OR_HASH_64]'),
]


class SafeLogFilter(logging.Filter):
    """Bộ lọc tự động che giấu các khóa mật mã và dữ liệu bí mật trước khi ghi log."""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, repl in SENSITIVE_PATTERNS:
                record.msg = re.sub(pattern, repl, record.msg)
        return True


def get_logger(name: str = "P2PNode", log_dir: str = None) -> logging.Logger:
    """Tạo hoặc lấy logger đã được cấu hình bộ lọc an toàn."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    if not log_dir:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_dir = os.path.join(os.path.dirname(base_dir), "Extra", "logs_evidence")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "chat_p2p.log")

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    safe_filter = SafeLogFilter()

    # File Handler
    try:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(formatter)
        fh.addFilter(safe_filter)
        logger.addHandler(fh)
    except Exception as e:
        sys.stderr.write(f"Warning: Không thể mở file log: {e}\n")

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    ch.addFilter(safe_filter)
    logger.addHandler(ch)

    return logger


# Default logger
log = get_logger()
