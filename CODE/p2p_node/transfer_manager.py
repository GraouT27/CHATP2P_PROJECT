
from concurrent.futures import ThreadPoolExecutor
import threading

from p2p_node.sender import TCPSender


class TransferManager:
    """Quản lý các tác vụ gửi file tới peer."""

    def __init__(
        self,
        sender_id,
        peer_manager,
        max_workers=3,
    ):
        self.sender_id = sender_id
        self.peer_manager = peer_manager

        self.executor = ThreadPoolExecutor(
            max_workers=max_workers
        )

        self.tasks = {}
        self.lock = threading.Lock()

    def create_sender(self, receiver_id):
        peer = self.peer_manager.get_peer(receiver_id)

        if peer is None:
            raise ValueError(
                f"Không tìm thấy peer {receiver_id}"
            )

        return TCPSender(
            sender_id=self.sender_id,
            receiver_id=receiver_id,
            host=peer["ip"],
            port=peer["tcp_port"],
        )

    def send_file(self, receiver_id, file_path, progress_callback=None):
        def worker():
            sender = self.create_sender(receiver_id)

            try:
                sender.connect()
                return sender.send_file(
                    file_path,
                    progress_callback=progress_callback,
                )
            finally:
                sender.close()

        return self.executor.submit(worker)

    def shutdown(self):
        self.executor.shutdown(
            wait=True,
            cancel_futures=True,
        )
