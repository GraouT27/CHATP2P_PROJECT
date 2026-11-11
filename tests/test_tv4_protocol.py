"""Kiểm tra giao thức TV4 bằng thư viện chuẩn, không cần pytest."""

import json
import socket
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "CODE"))

from p2p_node.discovery import listen_discovery, send_discovery
from p2p_node.peer_manager import PeerManager
from shared.protocol import (
    create_message,
    encode_message,
    recv_message,
    validate_message,
)


class ProtocolTests(unittest.TestCase):
    def test_text_and_emoji_over_one_socket(self):
        sender, receiver = socket.socketpair()
        self.addCleanup(sender.close)
        self.addCleanup(receiver.close)

        messages = [
            create_message("peer-A", "peer-B", "TEXT", {"text": "Xin chào"}),
            create_message("peer-A", "peer-B", "EMOJI", {"emoji": "😊"}),
        ]
        stream = b"".join(encode_message(message) for message in messages)
        for offset in range(0, len(stream), 3):
            sender.sendall(stream[offset:offset + 3])

        self.assertEqual(recv_message(receiver), messages[0])
        self.assertEqual(recv_message(receiver), messages[1])

    def test_rejects_missing_header_and_wrong_payload_type(self):
        message = create_message("peer-A", "peer-B", "TEXT", {"text": "ok"})
        del message["header"]["sender_id"]
        with self.assertRaises(ValueError):
            validate_message(message)

        message = create_message("peer-A", "peer-B", "EMOJI", {"emoji": "😊"})
        message["payload"]["emoji"] = 123
        with self.assertRaises(ValueError):
            encode_message(message)

    def test_rejects_bad_json_received_from_socket(self):
        sender, receiver = socket.socketpair()
        self.addCleanup(sender.close)
        self.addCleanup(receiver.close)
        body = b"{invalid"
        sender.sendall(struct.pack("!I", len(body)) + body)
        with self.assertRaises(ValueError):
            recv_message(receiver)

    def test_rejects_missing_header_received_from_socket(self):
        sender, receiver = socket.socketpair()
        self.addCleanup(sender.close)
        self.addCleanup(receiver.close)
        body = json.dumps({"payload": {"text": "hello"}}).encode("utf-8")
        sender.sendall(struct.pack("!I", len(body)) + body)
        with self.assertRaises(ValueError):
            recv_message(receiver)

    def test_peer_modules_import_and_lookup(self):
        self.assertTrue(callable(send_discovery))
        self.assertTrue(callable(listen_discovery))
        manager = PeerManager()
        manager.add_peer("peer-B", "127.0.0.1", 7000)
        self.assertEqual(manager.get_peer("peer-B")["tcp_port"], 7000)


if __name__ == "__main__":
    unittest.main()
