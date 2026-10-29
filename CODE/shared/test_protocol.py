import struct
from protocol import create_message, encode_message, decode_message 


test_messages = [{
    "type": "TEXT",
    "payload": {"text": "Xin chào nhaa~"}
},
{
    "type":"EMOJI",
    "payload": {"emoji":"😊"}
},
{
    "type": "REPLY",
    "payload": {
        "reply_to_message_id": "message-123",
        "text": "Xin chào~ Khỏe không ?"
    }
}]

for item in test_messages: 
    message = create_message (
        sender_id= "peer-A",
        receiver_id= "peer-B",
        message_type= item["type"],
        payload = item["payload"]
    )

    frame = encode_message(message)
    received = decode_message(frame[4:])

    print(item["type"], message == received)
