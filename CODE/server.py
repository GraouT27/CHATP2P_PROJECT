import socket

from shared.protocol import(
    create_message,
    encode_message,
    recv_message
)

HOST = "127.0.0.1"
PORT = 5000


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((HOST, PORT))
        server.listen(1)

        print(f"Server dang nghe tai:{HOST}:{PORT}")

        conn, addr = server.accept()
        print("Server da ket noi voi:", addr)

    
        with conn: 
            while True:
                try:
                    message = recv_message(conn)
                except ConnectionError:
                    print("Client đã ngắt kết nối!") 
                    break
                text = message["payload"]["text"]

                if text == "exit":
                    print("Client yêu cầu thoát!")
                    break

                print("Server nhận được:", text)

                respone = create_message(
                    sender_id= "peer-B",
                    receiver_id= message["header"]["receiver_id"],
                    message_type= "TEXT",
                    payload= {"text": f"Server nhan duoc: {text}"}
                )

                conn.sendall(encode_message(respone))
    finally:
        server.close()
        print("Server đã đóng.")


if __name__ == "__main__": 
    main()