import socket

from shared.protocol import (
    create_message,
    encode_message,
    recv_message,
)

HOST = "127.0.0.1"
PORT = 5000

def main():

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.connect((HOST, PORT))
    
        while True: 
            text = input("Bạn: ")

            if text == "exit":
                break

            message = create_message(
                sender_id= "peer-A",
                receiver_id= "peer-B",
                message_type= "TEXT",
                payload= {"text": text}
            )

            client.sendall(encode_message(message))
            print("Client đã gửi tin nhắn.")

            try:    
                response = recv_message(client)
            except ConnectionError:
                print("Server đã bị ngắt kết nối!")
                break
                
            print("Peer B: ", response["payload"]["text"])



if __name__ == "__main__":
    main()