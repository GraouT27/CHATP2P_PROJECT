
import socket
import threading

from p2p_node.file_handler import FileMessageCallbacks
from p2p_node.storage import FileStorage

from security.handshake import (
    handshake_responder,
    send_secure,
    recv_secure
)

from security.crypto import CryptoError


class PeerListener:
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
