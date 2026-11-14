import socket

from config.config_loader import load_config
from shared.protocol import (
    create_message,
    encode_message,
    recv_message,
)

# HOST = "127.0.0.1"
# PORT = 5000



def main(peer_manager, target_peer_id):

    config = load_config()
    MY_PEER_ID = config["peer_id"]

    peer = peer_manager.get_peer(target_peer_id)

    if peer is None:
        print(f"Không tìm thấy peer với ID: {target_peer_id}")
        return
    

    HOST = peer["ip"]
    PORT = peer["tcp_port"]

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
                sender_id= MY_PEER_ID,
                receiver_id= target_peer_id,
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

            except ValueError as e:
                print("Lỗi giải mã phản hồi:", e)
                break

            if not isinstance(response, dict):
                print("Response từ server không hợp lệ!")
                continue

            payload = response.get("payload", {})

            if not isinstance(payload, dict):
                print("Payload từ server không hợp lệ!")
                continue

            text = payload.get("text")

            if not isinstance(text, str):
                print("Response từ server không phải là chuỗi!")
                continue

           
            print(f"Peer {target_peer_id}: {text}")



if __name__ == "__main__":
    print("Hãy chạy ứng dụng từ main.py")