import socket
import struct
import json
import threading
import argparse
import sys
import os

class TCPEchoBenchmarkServer:
    def __init__(self, host="127.0.0.1", port=9999):
        self.host = host
        self.port = port
        self.is_running = False
        self.server_sock = None
        self.active_connections = 0
        self.lock = threading.Lock()

    def start(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Disable Nagle algorithm for latency measurement
        self.server_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(128)
        self.is_running = True
        print(f"[TCP_SERVER] Server started on {self.host}:{self.port} (Model: Multi-threaded Thread-per-Client)")

        try:
            while self.is_running:
                try:
                    conn, addr = self.server_sock.accept()
                    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    with self.lock:
                        self.active_connections += 1
                    t = threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True)
                    t.start()
                except socket.error:
                    break
        finally:
            self.stop()

    def _recv_exact(self, conn, n_bytes):
        data = bytearray()
        while len(data) < n_bytes:
            packet = conn.recv(n_bytes - len(data))
            if not packet:
                return None
            data.extend(packet)
        return bytes(data)

    def _handle_client(self, conn, addr):
        conn.settimeout(10.0) # 10s timeout
        try:
            while self.is_running:
                # 1. Read 4-byte header (Length-prefixed framing)
                header = self._recv_exact(conn, 4)
                if not header:
                    break
                payload_len = struct.unpack("!I", header)[0]

                # Protection against oversized frames
                if payload_len > 10 * 1024 * 1024: # 10MB limit
                    break

                # 2. Read exact payload body
                body = self._recv_exact(conn, payload_len)
                if not body:
                    break

                # 3. Parse JSON request
                try:
                    req_data = json.loads(body.decode("utf-8"))
                    req_id = req_data.get("requestId", "")
                    payload = req_data.get("payload", "")

                    # 4. Construct response with same requestId & payload
                    resp_dict = {
                        "requestId": req_id,
                        "payload": payload,
                        "status": "OK"
                    }
                    resp_bytes = json.dumps(resp_dict).encode("utf-8")
                    resp_header = struct.pack("!I", len(resp_bytes))
                    conn.sendall(resp_header + resp_bytes)
                except Exception as e:
                    # Malformed JSON handling
                    break
        except (socket.timeout, ConnectionResetError, BrokenPipeError):
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass
            with self.lock:
                self.active_connections -= 1

    def stop(self):
        self.is_running = False
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
            self.server_sock = None
        print("[TCP_SERVER] Server stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TCP Server for Client-Load Research Benchmark")
    parser.add_argument("--host", default="127.0.0.1", help="Binding host IP (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=9999, help="Binding port (default: 9999)")
    args = parser.parse_args()

    server = TCPEchoBenchmarkServer(host=args.host, port=args.port)
    server.start()
