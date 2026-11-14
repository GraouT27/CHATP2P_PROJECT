
import socket
import threading

from shared.protocol import (
    encode_message,
    recv_message
)

from p2p_node.handler import FileMessageCallbacks
from p2p_node.storage import FileStorage


class PeerListener:
    """TCP server nhận message và file từ peer."""

    def __init__(
        self,
        local_peer_id,
        host="0.0.0.0",
        port=5000,
        storage=None
    ):
        self.local_peer_id = local_peer_id
        self.host = host
        self.port = port

        self.storage = storage or FileStorage()

        self.server_socket = None
        self.running = False

        self._accept_thread = None
        self._client_threads = set()
        self._lock = threading.Lock()

    def start(self):
        if self.running:
            return

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

            # Nhận message đầu tiên để xác định peer gửi.
            first_message = recv_message(conn)

            remote_peer_id = first_message["header"]["sender_id"]

            callbacks = FileMessageCallbacks(
                storage=self.storage,
                local_peer_id=self.local_peer_id,
                remote_peer_id=remote_peer_id
            )

            def send_reply(message):
                conn.sendall(encode_message(message))

            callbacks.handle_message(
                first_message,
                send_reply
            )

            while self.running:
                try:
                    message = recv_message(conn)

                except socket.timeout:
                    continue

                callbacks.handle_message(
                    message,
                    send_reply
                )

        except (ConnectionError, OSError, ValueError):
            pass

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
