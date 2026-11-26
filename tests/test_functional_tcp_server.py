"""
File kiểm thử chức năng TCP Server (TC01 - TC06)
Đáp ứng Bảng 4.1 / Mục 4: Các trường hợp kiểm thử chức năng của hệ thống TCP Server & Load Generator.
"""

import socket
import struct
import json
import time
import threading
import sys
import os
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from src.server.tcp_server import TCPEchoBenchmarkServer
except ImportError:
    try:
        from src.tcp_server import TCPEchoBenchmarkServer
    except ImportError:
        from scripts.benchmark.tcp_server import TCPEchoBenchmarkServer


def pack_msg(data_dict: dict) -> bytes:
    body = json.dumps(data_dict).encode("utf-8")
    header = struct.pack("!I", len(body))
    return header + body


def unpack_msg(sock: socket.socket, timeout=5.0) -> dict:
    sock.settimeout(timeout)
    # Đọc 4 byte header
    hdr = bytearray()
    while len(hdr) < 4:
        chunk = sock.recv(4 - len(hdr))
        if not chunk:
            return None
        hdr.extend(chunk)
    payload_len = struct.unpack("!I", hdr)[0]

    # Đọc body
    body = bytearray()
    while len(body) < payload_len:
        chunk = sock.recv(payload_len - len(body))
        if not chunk:
            return None
        body.extend(chunk)
    return json.loads(body.decode("utf-8"))


@pytest.fixture(scope="module")
def tcp_server():
    """Khởi động TCP Server trên port kiểm thử độc lập 9998."""
    host = "127.0.0.1"
    port = 9998
    server = TCPEchoBenchmarkServer(host=host, port=port)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    time.sleep(0.3)
    yield host, port
    server.stop()
    server_thread.join(timeout=1.0)


def test_tc01_single_client_connect_and_exchange(tcp_server):
    """TC01: Một client kết nối - Kết nối và trao đổi dữ liệu thành công."""
    host, port = tcp_server
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    
    req = {"requestId": "tc01-req-001", "payload": "Test ping single client"}
    s.sendall(pack_msg(req))
    
    resp = unpack_msg(s)
    assert resp is not None
    assert resp.get("status") == "OK"
    assert resp.get("requestId") == "tc01-req-001"
    assert resp.get("payload") == "Test ping single client"
    s.close()


def test_tc02_concurrent_multiple_clients(tcp_server):
    """TC02: Nhiều client đồng thời - Server phục vụ các kết nối đồng thời mượt mà."""
    host, port = tcp_server
    num_clients = 10
    results = [None] * num_clients

    def client_worker(idx):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            req = {"requestId": f"tc02-client-{idx}", "payload": f"Concurrent data from {idx}"}
            s.sendall(pack_msg(req))
            resp = unpack_msg(s)
            results[idx] = (resp is not None and resp.get("status") == "OK")
            s.close()
        except Exception as e:
            results[idx] = False

    threads = [threading.Thread(target=client_worker, args=(i,)) for i in range(num_clients)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(results), "Tất cả 10 client đồng thời phải được phục vụ thành công"


def test_tc03_response_validation(tcp_server):
    """TC03: Kiểm tra response - requestId và payload khớp 100% request."""
    host, port = tcp_server
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))

    for i in range(5):
        payload_1kb = "X" * 1024
        req_id = f"tc03-seq-{i}"
        req = {"requestId": req_id, "payload": payload_1kb}
        s.sendall(pack_msg(req))

        resp = unpack_msg(s)
        assert resp is not None
        assert resp.get("requestId") == req_id
        assert resp.get("payload") == payload_1kb
        assert resp.get("status") == "OK"

    s.close()


def test_tc04_abrupt_client_disconnect(tcp_server):
    """TC04: Client ngắt bất thường - Server xử lý kết nối, không crash và dọn dẹp tài nguyên."""
    host, port = tcp_server
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    
    # Gửi header rồi đóng socket đột ngột (RST/FIN) mà không gửi đủ body
    s.sendall(struct.pack("!I", 1024))
    s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0)) # Ngắt nóng RST
    s.close()
    time.sleep(0.1)

    # Kiểm tra Server vẫn sống và phục vụ client mới bình thường
    s_new = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s_new.connect((host, port))
    req = {"requestId": "tc04-recovery", "payload": "Server alive check"}
    s_new.sendall(pack_msg(req))
    resp = unpack_msg(s_new)
    assert resp is not None and resp.get("status") == "OK"
    s_new.close()


def test_tc05_invalid_data_handling(tcp_server):
    """TC05: Dữ liệu không hợp lệ hoặc quá giới hạn - Server xử lý lỗi theo protocol."""
    host, port = tcp_server
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))

    # Gửi dữ liệu không phải JSON hợp lệ (chuỗi rác nhị phân)
    corrupted_bytes = b"CORRUPTED_NON_JSON_DATA_BUFFER"
    hdr = struct.pack("!I", len(corrupted_bytes))
    s.sendall(hdr + corrupted_bytes)

    # Server sẽ đóng kết nối vi phạm an toàn
    time.sleep(0.05)
    chunk = s.recv(1024)
    # Server đã ngắt kết nối (chunk rỗng)
    assert len(chunk) == 0
    s.close()


def test_tc06_faulty_client_isolation(tcp_server):
    """TC06: Client gặp lỗi - Server vẫn phục vụ client khác ổn định."""
    host, port = tcp_server
    
    # Client A: Kết nối và gửi dữ liệu hỏng / ngắt đột ngột
    s_bad = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s_bad.connect((host, port))
    s_bad.sendall(struct.pack("!I", 99999999)) # Length header khổng lồ / bất thường (>10MB)
    s_bad.close()

    # Client B: Kết nối đồng thời, gửi request chuẩn
    s_good = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s_good.connect((host, port))
    req = {"requestId": "tc06-good-client", "payload": "Normal operation"}
    s_good.sendall(pack_msg(req))
    resp = unpack_msg(s_good)

    assert resp is not None
    assert resp.get("status") == "OK"
    assert resp.get("requestId") == "tc06-good-client"
    s_good.close()
