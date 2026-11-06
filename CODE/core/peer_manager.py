import threading
from datetime import datetime, timezone



class PeerManager:
    """Quản lý danh sách các peer đã kết nối (thread-safe)."""

    def __init__(self):
        self._peers = {}
        self._lock = threading.Lock()

    def add_peer(self, peer_id, ip, tcp_port):
        """Thêm hoặc cập nhật thông tin một peer."""

        now = datetime.now(timezone.utc).isoformat()


        with self._lock:

            if peer_id in self._peers:
                self._peers[peer_id]["ip"] = ip
                self._peers[peer_id]["tcp_port"] = tcp_port
                self._peers[peer_id]["last_seen"] = now

            else: 

                self._peers[peer_id] = {
                    "ip": ip,
                    "tcp_port": tcp_port,
                    "discovered_at": now,
                    "last_seen": now,
                }

    def remove_peer(self, peer_id):
        """Xóa một peer khỏi danh sách."""
        with self._lock:
            self._peers.pop(peer_id, None)

    def get_peer(self, peer_id):
        """Lấy thông tin của một peer theo ID. Trả về None nếu không tìm thấy."""
        with self._lock:
            peer = self._peers.get(peer_id)
            return peer.copy() if peer else None

    def get_all_peers(self):
        """Trả về bản sao của danh sách tất cả các peer (không bao gồm socket)."""
        with self._lock:
            return {
                peer_id: info.copy()
                for peer_id, info in self._peers.items()
            }

    def update_last_seen(self, peer_id):
        """Cập nhật thời gian peer hoạt động gần nhất."""
        with self._lock:
            if peer_id in self._peers:
                self._peers[peer_id]["last_seen"] = datetime.now().isoformat()

    def peer_count(self):
        """Trả về số lượng peer đang quản lý."""
        with self._lock:
            return len(self._peers)

    def get_all_peer_ids(self):
        """Trả về danh sách ID của tất cả peer."""
        with self._lock:
            return list(self._peers.keys())
