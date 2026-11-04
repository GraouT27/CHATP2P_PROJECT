import socket


class TCPSender:

    def __init__(self):

        self.socket = None


    def connect(self, host, port):

        try:

            self.socket = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            )

            self.socket.connect(
                (host, port)
            )

            print(
                f"Đã kết nối tới "
                f"{host}:{port}"
            )

            return True

        except ConnectionRefusedError:

            print(
                "Peer chưa mở Listener"
            )

            return False

        except OSError as error:

            print(
                f"Lỗi kết nối: {error}"
            )

            return False


    def send(self, data):

        """
        Gửi dữ liệu qua TCP.
        """

        if not self.socket:

            raise ConnectionError(
                "Chưa kết nối Peer"
            )

        self.socket.sendall(data)


    def close(self):

        if self.socket:

            self.socket.close()

            self.socket = None