import socket

from config.config_loader import load_config
from shared.protocol import (
    create_message,
    encode_message,
    recv_message,
)

# HOST = "127.0.0.1"
# PORT = 5000



def main():

    config = load_config()
    HOST = config["peer_host"]
    PORT = config["peer_port"]
    

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(10)

        try:
            client.connect((HOST, PORT))

        
        except ConnectionRefusedError:
            print("Server từ chối kết nối!")
            return

        except socket.timeout:
            print("Kết nối Server quá thời gian chờ!")
            return

        except OSError as e: 
            print("Lỗi kết nối:", e)
            return
    
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

            try: 
                client.sendall(encode_message(message))
                print("Client đã gửi tin nhắn.")

                response = recv_message(client)

            except socket.timeout:
                print("Server phản hồi quá thời gian chờ !")
                break

            except ConnectionError:
                print("Server đã bị ngắt kết nối!")
                break

            except OSError as e:
                print("Lỗi mạng:", e)
                break

                
            print("Peer B: ", response["payload"]["text"])



if __name__ == "__main__":
    main()