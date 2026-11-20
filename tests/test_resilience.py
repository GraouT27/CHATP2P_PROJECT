"""Chiu loi: du lieu rac, ngat ket noi dot ngot, kill process, giai phong tai nguyen (Chang 6, TV1).

Chay may chu mau (tests/resilience_hub.py) o mot TIEN TRINH RIENG roi tan cong no bang cac cach
that su xay ra: kill -9 giua luc truyen, dong ngay khi vua noi, gui byte ngau nhien, RST,
do dai khung khong lo. Sau moi tinh huong: may chu con song, khong in Traceback, ket noi dong
sach, va con phuc vu duoc ket noi moi.
"""
import os
import queue
import re
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
import pytest

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / "CODE"))

from security.crypto import KeyPair  # noqa: E402
from security.handshake import (  # noqa: E402
    handshake_initiator,
    make_message,
    recv_secure,
    send_frame,
    send_secure,
)
from security.netutil import enable_keepalive  # noqa: E402

CLIENT_KEY = KeyPair.generate()


class Hub:
    def __init__(self, handshake_timeout=1.5):
        self.proc = subprocess.Popen(
            [sys.executable, str(TESTS / "resilience_hub.py"), str(handshake_timeout)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.lines, self._closed, self._ps = [], queue.Queue(), psutil.Process(self.proc.pid)
        threading.Thread(target=self._read, daemon=True).start()
        self.port = int(self._first_line().split()[1])

    def _read(self):
        for line in self.proc.stdout:
            line = line.strip()
            self.lines.append(line)
            for reason in re.findall(r"CLOSED reason=([a-z_]+)", line):
                self._closed.put(reason)

    def _first_line(self, timeout=15):
        end = time.time() + timeout
        while time.time() < end:
            if self.lines:
                return self.lines[0]
            time.sleep(0.02)
        raise TimeoutError("may chu mau khong khoi dong duoc: " + " | ".join(self.lines))

    def wait_closed(self, timeout=10):
        return self._closed.get(timeout=timeout)

    def alive(self):
        return self.proc.poll() is None

    def stats(self):
        handles = self._ps.num_handles() if hasattr(self._ps, "num_handles") else self._ps.num_fds()
        conns = self._ps.net_connections(kind="tcp") if hasattr(self._ps, "net_connections") \
            else self._ps.connections(kind="tcp")
        established = sum(1 for c in conns if c.status == psutil.CONN_ESTABLISHED)
        return handles, self._ps.num_threads(), established

    def settle(self, timeout=5):
        """Cho cho den khi khong con ket noi ESTABLISHED nao."""
        end = time.time() + timeout
        while time.time() < end:
            if self.stats()[2] == 0:
                return True
            time.sleep(0.05)
        return False

    def connect(self):
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=10)
        return sock

    def echo_ok(self, text="xin chao"):
        """Mot ket noi moi, day du: bat tay roi gui TEXT va nhan echo."""
        with self.connect() as sock:
            result = handshake_initiator(sock, CLIENT_KEY, "peer-X", "hub")
            send_secure(sock, result.session, make_message("TEXT", "peer-X", "hub", {"text": text}))
            return recv_secure(sock, result.session)["payload"]["text"] == "echo: " + text

    def stop(self):
        if self.alive():
            self.proc.kill()
        self.proc.wait(10)


@pytest.fixture
def hub():
    h = Hub()
    yield h
    survived = h.alive()
    h.stop()
    assert survived, "may chu da chet: " + " | ".join(h.lines)
    assert not any("Traceback" in line for line in h.lines), "\n".join(h.lines)


def abrupt_close(sock):
    """Dong bang RST (nhu mat dien/kill), khong qua FIN."""
    fmt = "HH" if sys.platform == "win32" else "ii"
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack(fmt, 1, 0))
    sock.close()


def logged_in(hub):
    sock = hub.connect()
    return sock, handshake_initiator(sock, CLIENT_KEY, "peer-X", "hub")


# ---------------------------------------------------------------- kill / ngat dot ngot
def test_rs01_peer_killed_mid_transfer(hub):
    peer = subprocess.Popen([sys.executable, str(TESTS / "resilience_peer.py"), str(hub.port)],
                            stdout=subprocess.PIPE, text=True)
    try:
        assert peer.stdout.readline().strip() == "READY"
        time.sleep(0.4)                                 # dang giua luc gui du lieu
        peer.kill()                                     # kill -9 / TerminateProcess
        peer.wait(10)
    finally:
        if peer.poll() is None:
            peer.kill()
    assert hub.wait_closed() == "peer_disconnected"
    assert hub.alive() and hub.settle()
    assert hub.echo_ok()                                # van phuc vu duoc ket noi moi


def test_rs02_connect_then_close_immediately(hub):
    hub.connect().close()
    assert hub.wait_closed() == "handshake_failed"
    assert hub.echo_ok()


def test_rs03_reset_during_handshake(hub):
    abrupt_close(hub.connect())
    assert hub.wait_closed() == "handshake_failed"
    assert hub.echo_ok()


def test_rs04_peer_reset_after_handshake(hub):
    sock, _ = logged_in(hub)
    abrupt_close(sock)
    assert hub.wait_closed() == "peer_disconnected"
    assert hub.settle() and hub.echo_ok()


def test_rs05_silent_peer_does_not_hang_server(hub):
    start = time.time()
    with hub.connect():
        assert hub.wait_closed(timeout=8) == "handshake_failed"
    assert time.time() - start < 6                      # het thoi gian bat tay, khong cho vo han
    assert hub.echo_ok()


# ---------------------------------------------------------------- du lieu rac
def test_rs06_random_bytes_instead_of_handshake(hub):
    with hub.connect() as sock:
        sock.sendall(os.urandom(4096))
        assert hub.wait_closed(timeout=8) == "handshake_failed"
    assert hub.echo_ok()


def test_rs07_garbage_frame_after_handshake(hub):
    sock, _ = logged_in(hub)
    with sock:
        send_frame(sock, os.urandom(200))               # khung hop le ve do dai, noi dung rac
        assert hub.wait_closed() == "decrypt_fail"
    assert hub.echo_ok()


def test_rs08_absurd_frame_length(hub):
    sock, _ = logged_in(hub)
    with sock:
        sock.sendall(b"\xff\xff\xff\xff")               # tuyen bo khung 4 GB: khong duoc cap phat
        assert hub.wait_closed() == "protocol_error"
    assert hub.echo_ok()
    assert hub.stats()[0] < 400                         # khong phinh tai nguyen


def test_rs09_encrypted_but_not_json(hub):
    sock, result = logged_in(hub)
    with sock:
        send_frame(sock, result.session.encrypt(b"khong phai json"))
        assert hub.wait_closed() == "bad_message"
    assert hub.echo_ok()


def test_rs10_wrongly_shaped_messages_are_ignored_connection_survives(hub):
    sock, result = logged_in(hub)
    with sock:
        s = result.session
        for payload in ({}, {"text": 123}, {"text": None}, {"text": ["a"]}):
            send_secure(sock, s, make_message("TEXT", "peer-X", "hub", payload))
        send_secure(sock, s, make_message("VIDEO", "peer-X", "hub", {"x": 1}))   # loai la
        send_secure(sock, s, make_message("TEXT", "peer-X", "hub", {"text": "van song"}))
        assert recv_secure(sock, s)["payload"]["text"] == "echo: van song"


def test_rs11_replayed_packet_closes_only_that_connection(hub):
    sock, result = logged_in(hub)
    with sock:
        blob = result.session.encrypt(
            b'{"header": {"message_type": "TEXT"}, "payload": {"text": "mot lan"}}')
        send_frame(sock, blob)
        recv_secure(sock, result.session)               # echo cua lan dau
        send_frame(sock, blob)                          # gui lai y nguyen
        assert hub.wait_closed() == "decrypt_fail"
    assert hub.echo_ok()


# ---------------------------------------------------------------- giai phong tai nguyen
def test_rs12_many_abrupt_disconnects_do_not_leak_resources(hub):
    assert hub.echo_ok()                                # lam nong, khoi tao cac tai nguyen lazy
    hub.wait_closed()
    assert hub.settle()
    handles0, threads0, _ = hub.stats()
    for _ in range(40):
        sock, _ = logged_in(hub)
        abrupt_close(sock)
        hub.wait_closed()
    assert hub.settle(timeout=8)
    handles1, threads1, established = hub.stats()
    assert established == 0
    assert handles1 <= handles0 + 3, f"ro ri handle/fd: {handles0} -> {handles1}"
    assert threads1 <= threads0 + 2, f"ro ri luong: {threads0} -> {threads1}"


def test_rs13_parallel_hostile_clients_do_not_break_server(hub):
    def hostile(kind):
        with hub.connect() as sock:
            if kind == 0:
                sock.sendall(os.urandom(1000))
            elif kind == 1:
                abrupt_close(sock.dup())
            elif kind == 2:
                result = handshake_initiator(sock, CLIENT_KEY, "peer-X", "hub")
                send_frame(sock, os.urandom(100))
            else:
                result = handshake_initiator(sock, CLIENT_KEY, "peer-X", "hub")

    threads = [threading.Thread(target=hostile, args=(i % 4,)) for i in range(24)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert hub.alive()
    closed = [hub.wait_closed(timeout=10) for _ in range(24)]       # dung 24 ket noi, deu da dong
    assert len(closed) == 24
    assert hub.settle(timeout=8) and hub.echo_ok()


# ---------------------------------------------------------------- phat hien peer chet am tham
def test_rs14_keepalive_is_enabled():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        enable_keepalive(s, idle=10, interval=3, count=3)
        assert s.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) != 0
        if hasattr(socket, "TCP_KEEPIDLE") and sys.platform.startswith("linux"):
            assert s.getsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE) == 10
            assert s.getsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL) == 3
            assert s.getsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT) == 3