
import time
import threading


class SpeedMeter:
    """Theo dõi tốc độ truyền dữ liệu."""

    def __init__(self):
        self._start_time = None
        self._last_time = None
        self._last_bytes = 0
        self._total_bytes = 0
        self._speed = 0.0
        self._lock = threading.Lock()

    def start(self):
        """Bắt đầu đo tốc độ."""
        now = time.monotonic()

        with self._lock:
            self._start_time = now
            self._last_time = now
            self._last_bytes = 0
            self._total_bytes = 0
            self._speed = 0.0

    def update(self, bytes_count):
        """Cập nhật số byte vừa truyền."""
        if bytes_count < 0:
            raise ValueError("bytes_count không được âm")

        now = time.monotonic()

        with self._lock:
            if self._start_time is None:
                self._start_time = now
                self._last_time = now

            self._total_bytes += bytes_count

            elapsed = now - self._last_time

            if elapsed > 0:
                new_bytes = self._total_bytes - self._last_bytes
                self._speed = new_bytes / elapsed

                self._last_bytes = self._total_bytes
                self._last_time = now

            return self._speed

    def get_speed(self):
        with self._lock:
            return self._speed

    def get_total_bytes(self):
        with self._lock:
            return self._total_bytes

    def get_average_speed(self):
        with self._lock:
            if self._start_time is None:
                return 0.0

            elapsed = time.monotonic() - self._start_time

            if elapsed <= 0:
                return 0.0

            return self._total_bytes / elapsed

    def reset(self):
        with self._lock:
            self._start_time = None
            self._last_time = None
            self._last_bytes = 0
            self._total_bytes = 0
            self._speed = 0.0
