"""
Configuration Module - Quản lý cấu hình động cho ứng dụng Chat P2P [UDM_09].
Tất cả các tham số mạng, thời gian chờ, kích thước chunk và giới hạn đồng thời
đều được cấu hình tập trung tại đây và có thể tùy biến linh hoạt qua GUI hoặc CLI.
"""

import os
import json

# === MẠNG VÀ CỔNG MẶC ĐỊNH ===
DEFAULT_HOST = "0.0.0.0"
DEFAULT_LISTEN_PORT = 9001
DEFAULT_DISCOVERY_PORT = 37020
DISCOVERY_BROADCAST_IP = "255.255.255.255"
DISCOVERY_INTERVAL = 3.0  # Giây giữa các lần phát UDP Broadcast

# === THỜI GIAN CHỜ & GIỚI HẠN TÀI NGUYÊN ===
SOCKET_TIMEOUT = 10.0      # Timeout cho các thao tác socket (giây)
CONNECT_TIMEOUT = 5.0      # Timeout khi chủ động kết nối tới Peer (giây)
HEARTBEAT_INTERVAL = 5.0   # Tần suất kiểm tra kết nối định kỳ (giây)
HEARTBEAT_TIMEOUT = 15.0   # Quá thời gian này không thấy Peer phản hồi thì coi là Offline

# === TRUYỀN FILE ĐA LUỒNG ===
CHUNK_SIZE = 64 * 1024     # 64 KB mỗi mảnh dữ liệu nhị phân
MAX_CONCURRENT_TRANSFERS = 3  # Giới hạn số file truyền/nhận song song (Semaphore)

# === THƯ MỤC LƯU TRỮ ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECEIVED_FILES_DIR = os.path.join(BASE_DIR, "received_files")
AVATAR_CACHE_DIR = os.path.join(RECEIVED_FILES_DIR, "avatars")
LOG_DIR = os.path.join(os.path.dirname(BASE_DIR), "EXTRA", "logs_evidence")

os.makedirs(RECEIVED_FILES_DIR, exist_ok=True)
os.makedirs(AVATAR_CACHE_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


class AppConfig:
    """Quản lý nạp và lưu cấu hình động từ file JSON."""
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(BASE_DIR, "config.json")
        self.username = "User"
        self.listen_port = DEFAULT_LISTEN_PORT
        self.discovery_enabled = True
        self.avatar_path = ""
        self.download_dir = RECEIVED_FILES_DIR
        self.chunk_size = CHUNK_SIZE
        self.max_concurrent = MAX_CONCURRENT_TRANSFERS
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.username = data.get("username", self.username)
                    self.listen_port = int(data.get("listen_port", self.listen_port))
                    self.discovery_enabled = bool(data.get("discovery_enabled", self.discovery_enabled))
                    self.avatar_path = data.get("avatar_path", self.avatar_path)
                    self.download_dir = data.get("download_dir", self.download_dir)
                    self.chunk_size = int(data.get("chunk_size", self.chunk_size))
                    self.max_concurrent = int(data.get("max_concurrent", self.max_concurrent))
            except Exception:
                pass

    def save(self):
        data = {
            "username": self.username,
            "listen_port": self.listen_port,
            "discovery_enabled": self.discovery_enabled,
            "avatar_path": self.avatar_path,
            "download_dir": self.download_dir,
            "chunk_size": self.chunk_size,
            "max_concurrent": self.max_concurrent,
        }
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


# Singleton instance
config = AppConfig()

try:
    from config.config_loader import load_config
except ImportError:
    pass

__all__ = [
    "config",
    "AppConfig",
    "DEFAULT_HOST",
    "DEFAULT_LISTEN_PORT",
    "DEFAULT_DISCOVERY_PORT",
    "DISCOVERY_BROADCAST_IP",
    "DISCOVERY_INTERVAL",
    "SOCKET_TIMEOUT",
    "CONNECT_TIMEOUT",
    "HEARTBEAT_INTERVAL",
    "HEARTBEAT_TIMEOUT",
    "CHUNK_SIZE",
    "MAX_CONCURRENT_TRANSFERS",
    "RECEIVED_FILES_DIR",
    "AVATAR_CACHE_DIR",
    "LOG_DIR",
    "load_config",
]
