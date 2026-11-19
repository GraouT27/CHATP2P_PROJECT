"""
Listener Module - QThread mở TCP Socket lắng nghe kết nối đến từ các Peer khác (TV4 & TV5).

Đặc tả:
- Thuần túy P2P: Không dùng Server trung tâm.
- Lắng nghe kết nối TCP trên luồng nền (QThread) để đảm bảo không treo GUI.
- Bắt gọn ngoại lệ (ConnectionResetError, socket.timeout).
"""

import socket
import threading
from PyQt6.QtCore import QThread, pyqtSignal
from shared.protocol import (
    read_message,
    encode_message,
    recv_message,

from p2p_node.file_handler import FileMessageCallbacks
from p2p_node.storage import FileStorage

from security.handshake import (
    handshake_responder,
    send_secure,
    recv_secure
)
from p2p_node.handler import MessageHandler
from security.logger import log


class P2PListener(QThread):
    """Luồng nền TCP Server chấp nhận kết nối từ các Peer khác cho GUI PyQt6."""
    server_started = pyqtSignal(int)          # (actual_port)
    server_error = pyqtSignal(str)            # (error_message)
    peer_connected = pyqtSignal(str, str, int)# (peer_id, ip, port)
    peer_disconnected = pyqtSignal(str)       # (peer_id)

    # Giới hạn tối đa số kết nối đồng thời để chống tấn công DoS làm cạn kiệt luồng (Thread Exhaustion).
    MAX_ACTIVE_CONNECTIONS = 100

    def __init__(self, port: int, handler: MessageHandler, parent=None):
        super().__init__(parent)
        self.port = port
        self.handler = handler
        self._is_running = True
        self.server_sock: socket.socket = None
        self._active_connections: dict[str, socket.socket] = {}
        self._lock = threading.Lock()

    def stop(self):
        """Dừng server và đóng tất cả socket an toàn trước khi thoát ứng dụng."""
        self._is_running = False
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
        with self._lock:
            for pid, sock in list(self._active_connections.items()):
                try:
                    sock.close()
                except Exception:
                    pass
            self._active_connections.clear()
        if self.isRunning():
            self.wait(1500)

    def run(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.settimeout(1.0)

        try:
            self.server_sock.bind(("0.0.0.0", self.port))
            self.server_sock.listen(128)
            actual_port = self.server_sock.getsockname()[1]
            self.port = actual_port
            log.info(f"[P2P_LISTENER] Đang lắng nghe kết nối TCP P2P trên cổng {actual_port}")
            self.server_started.emit(actual_port)
        except Exception as e:
            log.error(f"[P2P_LISTENER] Không thể bind port {self.port}: {e}")
            self.server_error.emit(str(e))
            return

        while self._is_running:
            try:
                client_sock, client_addr = self.server_sock.accept()
                ip = client_addr[0]
                port = client_addr[1]
                peer_id = f"{ip}:{port}"

                with self._lock:
                    if len(self._active_connections) >= self.MAX_ACTIVE_CONNECTIONS:
                        log.warning(f"[SECURITY] Từ chối kết nối từ {peer_id}: Vượt quá giới hạn {self.MAX_ACTIVE_CONNECTIONS} kết nối")
                        try:
                            client_sock.close()
                        except Exception:
                            pass
                        continue
                    self._active_connections[peer_id] = client_sock

                self.peer_connected.emit(peer_id, ip, port)

                t = threading.Thread(
                    target=self._handle_client_stream,
                    args=(peer_id, ip, client_sock),
                    daemon=True,
                )
                t.start()

            except (socket.timeout, BlockingIOError):
                continue
            except Exception:
                if self._is_running:
                    break

        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass

    def _handle_client_stream(self, peer_id: str, ip: str, sock: socket.socket):
        """Vòng lặp đọc các bản tin framed từ kết nối của Peer."""
        sock.settimeout(15.0)
        try:
            while self._is_running:
                header, payload = read_message(sock)
                self.handler.process_incoming(peer_id, header, payload)
        except (ConnectionResetError, BrokenPipeError, EOFError):
            log.warning(f"Peer {peer_id} đã ngắt kết nối đột ngột")
        except socket.timeout:
            log.warning(f"Timeout kết nối với Peer {peer_id}")
        except Exception as e:
            log.error(f"Lỗi đọc dữ liệu từ {peer_id}: {e}")
        finally:
            try:
                sock.close()
            except Exception:
                pass
            with self._lock:
                self._active_connections.pop(peer_id, None)
            self.peer_disconnected.emit(peer_id)

from security.crypto import CryptoError

# ===================== CLI COMPATIBLE PEER LISTENER =====================

class PeerListener:
    """TCP server nhận message và file từ peer (CLI)."""

    def __init__(
        self,
        local_peer_id,
        host="0.0.0.0",
        port=5000,
        storage=None,
        keypair=None
    ):
        self.local_peer_id = local_peer_id
        self.host = host
        self.port = port
        from p2p_node.storage import FileStorage
        self.keypair = keypair

        self.storage = storage or FileStorage()
        self.server_socket = None
        self.running = False
        self._accept_thread = None
        self._client_threads = set()
        self._lock = threading.Lock()

    def start(self):
        if self.running:
            return

        if self.keypair is None:
            raise ValueError("Chưa cung cấp KeyPair")

        self.server_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )
        self.server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        self.running = True

        self._accept_thread = threading.Thread(
            target=self._accept_loop,
            daemon=True
        )

        self._accept_thread.start()

    def _accept_loop(self):
        while self.running:
            try:
                conn, address = self.server_socket.accept()
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(conn, address),
                    daemon=True
                )
                with self._lock:
                    self._client_threads.add(thread)
                thread.start()
            except OSError:
                if self.running:
                    raise
                break

    def _handle_client(self, conn, address):
        callbacks = None
        try:
            conn.settimeout(60)
            first_message = recv_message(conn)
            remote_peer_id = first_message["header"]["sender_id"]

            handshake_result = handshake_responder(
                conn,
                self.keypair,
                self.local_peer_id
            )

            session = handshake_result.session
            remote_peer_id = handshake_result.peer_id

            peer_fingerprint = handshake_result.peer_fingerprint

            print(
                f"[LISTENER] Đã kết nối với {remote_peer_id}"
            )

            print(
                f"[LISTENER] Fingerprint: {peer_fingerprint}"
            )

            conn.settimeout(None)

            send_lock = threading.Lock()

            from p2p_node.file_handler import FileMessageCallbacks
            callbacks = FileMessageCallbacks(
                storage=self.storage,
                local_peer_id=self.local_peer_id,
                remote_peer_id=remote_peer_id
            )

            def send_reply(message):
                with send_lock:
                    send_secure(
                        conn,
                        session,
                        message
                    )

            while self.running:
                try:
                    message = recv_message(conn)
                except socket.timeout:
                    continue
                message = recv_secure(
                    conn,
                    session
                )

                if message is None:
                    break

                callbacks.handle_message(
                    message,
                    send_reply
                )

        except (ConnectionError, OSError, ValueError):
            pass
        except (
            ConnectionError,
            OSError,
            ValueError,
            CryptoError
        ) as exc:
            print(f"[LISTENER] Lỗi kết nối: {exc}")

        finally:
            if callbacks is not None:
                callbacks.close()
            try:
                conn.close()
            except OSError:
                pass
            with self._lock:
                self._client_threads.discard(
                    threading.current_thread()
                )

    def stop(self):
        self.running = False
        if self.server_socket is not None:
            try:
                self.server_socket.close()
            except OSError:
                pass
            self.server_socket = None

        if self._accept_thread is not None:
            self._accept_thread.join(timeout=2)

        with self._lock:
            threads = list(self._client_threads)
        for thread in threads:
            thread.join(timeout=2)
