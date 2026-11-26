
import unittest
from pathlib import Path
import sys

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "CODE")
)

from shared.protocol import (
    create_message,
    create_text_message,
    create_reply_message,
    create_forward_message,
    validate_message,
    encode_message,
    decode_message,
)


class ReplyForwardTests(unittest.TestCase):

    def test_reply_valid(self):
        original = create_text_message("A", "B", "Hello")
        reply = create_reply_message(
            "B", "A",
            original["header"]["message_id"],
            "Hi!"
        )
        self.assertIsNone(validate_message(reply))
        self.assertNotEqual(
            original["header"]["message_id"],
            reply["header"]["message_id"]
        )

    def test_reply_invalid_uuid(self):
        with self.assertRaises(ValueError):
            create_reply_message("B", "A", "message-123", "Hi!")

    def test_reply_missing_text(self):
        original = create_text_message("A", "B", "Hello")
        with self.assertRaises(ValueError):
            create_reply_message(
                "B", "A",
                original["header"]["message_id"],
                ""
            )

    def test_forward_valid(self):
        original = create_text_message("A", "B", "Hello")
        forward = create_forward_message(
            "B", "C", "A",
            original["header"]["message_id"],
            "TEXT",
            original["payload"]
        )
        self.assertIsNone(validate_message(forward))
        self.assertEqual(
            forward["payload"]["forwarded_from"], "A"
        )

    def test_forward_invalid_type(self):
        original = create_text_message("A", "B", "Hello")
        with self.assertRaises(ValueError):
            create_forward_message(
                "B", "C", "A",
                original["header"]["message_id"],
                "FILE",
                {"action": "OFFER"}
            )

    def test_reply_round_trip(self):
        original = create_text_message("A", "B", "Hello")
        reply = create_reply_message(
            "B", "A",
            original["header"]["message_id"],
            "Hi!"
        )
        encoded = encode_message(reply)
        decoded = decode_message(encoded[4:])
        self.assertEqual(reply, decoded)



    def test_forward_emoji_valid(self):
        original = create_message(
            "A", "B", "EMOJI", {"emoji": "😊"}
        )
        forward = create_forward_message(
            "B", "C", "A",
            original["header"]["message_id"],
            "EMOJI",
            original["payload"]
        )
        self.assertIsNone(validate_message(forward))
        self.assertEqual(
            forward["payload"]["original_payload"]["emoji"],
            "😊"
        )

    def test_forward_missing_sender(self):
        original = create_text_message("A", "B", "Hello")
        forward = create_forward_message(
            "B", "C", "A",
            original["header"]["message_id"],
            "TEXT",
            original["payload"]
        )

        del forward["payload"]["forwarded_from"]

        with self.assertRaises(ValueError):
            validate_message(forward)

    def test_forward_invalid_original_uuid(self):
        with self.assertRaises(ValueError):
            create_forward_message(
                "B", "C", "A",
                "invalid-uuid",
                "TEXT",
                {"text": "Hello"}
            )

    def test_forward_invalid_original_payload(self):
        original = create_text_message("A", "B", "Hello")

        with self.assertRaises(ValueError):
            create_forward_message(
                "B", "C", "A",
                original["header"]["message_id"],
                "TEXT",
                {"emoji": "😊"}
            )

    def test_forward_round_trip(self):
        original = create_text_message("A", "B", "Hello")
        forward = create_forward_message(
            "B", "C", "A",
            original["header"]["message_id"],
            "TEXT",
            original["payload"]
        )

        encoded = encode_message(forward)
        decoded = decode_message(encoded[4:])

        self.assertEqual(forward, decoded)

    def test_reply_self_reference_uppercase_uuid(self):
        original = create_text_message("A", "B", "Hello")
        reply = create_reply_message(
            "B", "A",
            original["header"]["message_id"],
            "Hi!"
        )

        reply["payload"]["reply_to"] = (
            reply["header"]["message_id"].upper()
        )

        with self.assertRaises(ValueError):
            validate_message(reply)



if __name__ == "__main__":
    unittest.main()
