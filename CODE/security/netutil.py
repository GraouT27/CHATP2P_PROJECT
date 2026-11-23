"""Tien ich socket: phat hien peer chet am tham (rut mang, tat nguon) bang TCP keepalive."""
import socket
import sys


def enable_keepalive(sock: socket.socket, idle: int = 10, interval: int = 3, count: int = 3) -> None:
    """Bat TCP keepalive tren socket da ket noi.

    Khi day mang bi rut hoac peer mat dien, KHONG co goi FIN/RST nao toi, recv() se cho vo han
    va tai nguyen (luong, socket) khong bao gio duoc giai phong. Keepalive de he dieu hanh tu
    thang tham do va bao loi sau khoang idle + interval * count giay (mac dinh ~19 giay);
    luc do recv() nem ConnectionError hoac TimeoutError. Windows co dinh so lan tham do
    (khong chinh duoc count). Neu he dieu hanh khong ho tro tinh chinh thi van giu SO_KEEPALIVE.
    """
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    try:
        if sys.platform == "win32":
            sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, idle * 1000, interval * 1000))
        elif sys.platform == "darwin":
            sock.setsockopt(socket.IPPROTO_TCP, getattr(socket, "TCP_KEEPALIVE", 0x10), idle)
        else:
            for name, value in (("TCP_KEEPIDLE", idle), ("TCP_KEEPINTVL", interval), ("TCP_KEEPCNT", count)):
                if hasattr(socket, name):
                    sock.setsockopt(socket.IPPROTO_TCP, getattr(socket, name), value)
    except (AttributeError, OSError, ValueError):
        pass