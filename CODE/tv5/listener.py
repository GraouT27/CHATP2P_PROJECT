import socket


class TCPListener:

    def __init__(self, host="0.0.0.0", port=5000):

        self.host = host
        self.port = port

        self.server_socket = None
        self.client_socket = None

        self.running = False


    def start(self):

        self.server_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        self.server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        self.server_socket.bind(
            (self.host, self.port)
        )

        self.server_socket.listen(5)

        self.running = True

        print(
            f"TCP Listener đang chạy tại "
            f"{self.host}:{self.port}"
        )


    def accept_peer(self):

        """
        Chờ một Peer kết nối.
        """

        client_socket, address = (
            self.server_socket.accept()
        )

        self.client_socket = client_socket

        print(
            f"Peer đã kết nối: {address}"
        )

        return client_socket, address


    def close(self):

        self.running = False

        if self.client_socket:

            self.client_socket.close()

        if self.server_socket:

            self.server_socket.close()

        print("Listener đã đóng")