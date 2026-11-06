import socket

from config.config_loader import load_config
from shared.protocol import(
    create_message,
    encode_message,
    recv_message
)

# HOST = "127.0.0.1"
# PORT = 5000


def main():
    config = load_config()
    HOST = config["listen_host"]
    PORT = config["listen_port"]
    MY_PEER_ID = config["peer_id"]


    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((HOST, PORT))
        server.listen(5)

        print(f"Server dang nghe tai:{HOST}:{PORT}")

        
        while True:
            conn, addr = server.accept()
            print("Server da ket noi voi:", addr)

        
            with conn: 
                while True:
                    try:
                        message = recv_message(conn)
                    except ConnectionError:
                        print("Client đã ngắt kết nối!") 
                        break

                    except OSError as e:
                        print("Lỗi mạng: ", e)
                        break



                    if not isinstance(message, dict):
                        print("Message không hợp lệ, bỏ qua!")
                        continue

                    payload = message.get("payload", {})
                    if not isinstance(payload, dict):
                        print("Payload không hợp lệ, bỏ qua!")
                        continue
                    
                    text = payload.get("text")
                    if not isinstance(text, str):
                        print("Message text không hợp lệ, bỏ qua!")
                        continue

                    if text is None:
                        print("Message không có payload text, bỏ qua!")
                        continue

                    if text == "exit":
                        print("Client yêu cầu thoát!")
                        break

                    print("Server nhận được:", text)

                    response = create_message(
                        sender_id=MY_PEER_ID,
                        receiver_id=message.get("header", {}).get("sender_id", "unknown"),
                        message_type="TEXT",
                        payload={"text": f"Server nhan duoc: {text}"}
                    )

                    try:
                        conn.sendall(encode_message(response))
                    except (ConnectionError, OSError) as e:
                        print("Lỗi khi gửi phản hồi:", e)
                        break
    finally:
        server.close()
        print("Server đã đóng.")


if __name__ == "__main__": 
    main()