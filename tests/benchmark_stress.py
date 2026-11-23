"""benchmark_stress.py - Stress Test & Performance Test 2 muc tai va do toc do AES-256 (TV1, Chang 7).

Chay (trong venv, o thu muc goc repo):
    python tests/benchmark_stress.py                  # AES + ca 2 muc tai (day du, vai phut)
    python tests/benchmark_stress.py --level 1        # chi Muc 1
    python tests/benchmark_stress.py --level 2        # chi Muc 2
    python tests/benchmark_stress.py --aes-only       # chi do toc do AES-256
    python tests/benchmark_stress.py --quick          # ban thu nho (vai chuc giay) de kiem tra script chay duoc

Muc 1: 5 peer, 50 tin/giay (tong), file 10 MB.   Muc 2: 15 peer, 200 tin/giay (tong), file 100 MB.

Mo hinh: 1 may chu mau + N tien trinh peer (moi peer 1 tien trinh Python rieng, bat tay RSA that,
tin nhan ma hoa AES-256-GCM qua SessionCrypto) + 1 ket noi rieng truyen file (tung chunk 64 KB ma hoa
bang ChunkCrypto) LAP LAI lien tuc trong suot thoi gian chiu tai tin nhan. Do: do tre khu hoi (echo), ti le mat tin, toc do truyen file
(kem SHA-256), toc do ma hoa/giai ma that, CPU va RAM (psutil).

Luu y: toan bo chay tren MOT may qua loopback, dung kenh bao mat cua TV1 va dinh dang chunk rieng cua script,
khong phai giao thuc truyen file cua ung dung. Dung de do hieu nang cua lop bao mat, khong thay cho
do tren mang LAN that voi ung dung that.
"""
import argparse
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import psutil

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1] / "CODE"))

from security.crypto import KeyPair, SessionCrypto, new_session_key  # noqa: E402
from security.handshake import (  # noqa: E402
    handshake_initiator,
    handshake_responder,
    make_message,
    recv_frame,
    recv_secure,
    send_frame,
    send_secure,
)

CHUNK_SIZE = 64 * 1024
LEVELS = {
    1: {"name": "Muc 1", "peers": 5, "rate": 50, "file_mb": 10},
    2: {"name": "Muc 2", "peers": 15, "rate": 200, "file_mb": 100},
}
QUICK_FILE_MB = {1: 1, 2: 5}


def emit(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * pct / 100.0
    low, high = int(pos), min(int(pos) + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def mib(num_bytes) -> float:
    return num_bytes / (1024 * 1024)


# =========================================================================== vai tro: may chu mau
def hub_receive_file(conn, session, header, offer):
    tid, total = offer["transfer_id"], offer["total_chunks"]
    crypto = session.chunk_crypto(tid, total, sending=False)
    digest, received, decrypt_seconds = hashlib.sha256(), 0, 0.0
    for expected in range(total):
        frame = recv_frame(conn)
        index = int.from_bytes(frame[:4], "big")
        if index != expected:
            raise ValueError("chunk sai thu tu")
        started = time.perf_counter()
        plain = crypto.decrypt_chunk(index, frame[4:])
        decrypt_seconds += time.perf_counter() - started
        digest.update(plain)
        received += len(plain)
    done = recv_secure(conn, session)
    ok = done["payload"].get("sha256") == digest.hexdigest() and received == offer["file_size"]
    send_secure(conn, session, make_message("FILE", "hub", header.get("sender_id", "?"), {
        "action": "COMPLETE", "transfer_id": tid, "ok": ok, "bytes": received,
        "decrypt_seconds": decrypt_seconds}))


def hub_connection(conn, keypair):
    try:
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        session = handshake_responder(conn, keypair, "hub", timeout=60).session
        while True:
            message = recv_secure(conn, session)
            header, payload = message["header"], message["payload"]
            kind = header.get("message_type")
            if kind == "TEXT":
                send_secure(conn, session, make_message("TEXT", "hub", header.get("sender_id", "?"),
                                                        {"text": payload.get("text", "")}))
            elif kind == "FILE" and payload.get("action") == "OFFER":
                hub_receive_file(conn, session, header, payload)
    except Exception:  # noqa: BLE001 - ket noi dong/hong: ket thuc luong nay, may chu van chay
        pass
    finally:
        conn.close()


def role_hub():
    keypair = KeyPair.generate()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.bind(("127.0.0.1", 0))
        server.listen(128)
        emit(f"PORT {server.getsockname()[1]}")
        while True:
            conn, _ = server.accept()
            threading.Thread(target=hub_connection, args=(conn, keypair), daemon=True).start()
    finally:
        server.close()


# =========================================================================== vai tro: peer gui tin
def connect_and_handshake(args, name):
    keypair = KeyPair.generate()
    started = time.perf_counter()
    sock = socket.create_connection(("127.0.0.1", args.port), timeout=60)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    session = handshake_initiator(sock, keypair, name, "hub", timeout=60).session
    sock.settimeout(None)
    return sock, session, (time.perf_counter() - started) * 1000


def wait_for_go():
    return sys.stdin.readline().strip() == "GO"


def role_peer(args):
    sock, session, handshake_ms = connect_and_handshake(args, f"peer-{args.index}")
    emit(f"READY {handshake_ms:.1f}")
    if not wait_for_go():
        return
    stop, closing = threading.Event(), threading.Event()
    latencies, errors = [], []

    def reader():
        while True:
            try:
                text = recv_secure(sock, session)["payload"]["text"]
                latencies.append((time.perf_counter() - float(text.split("|", 1)[0])) * 1000)
            except Exception as exc:  # noqa: BLE001
                if not closing.is_set():
                    errors.append(type(exc).__name__)
                return

    def watch_stdin():
        for line in sys.stdin:
            if line.strip() == "STOP":
                stop.set()
                return
        stop.set()

    threading.Thread(target=reader, daemon=True).start()
    threading.Thread(target=watch_stdin, daemon=True).start()

    interval = 1.0 / args.rate
    padding = "x" * max(0, args.payload - 24)
    deadline = time.perf_counter() + args.max_seconds
    first = time.perf_counter()
    next_at = first + interval * (args.index / max(1, args.peers))      # lech pha giua cac peer
    sent = 0
    try:
        while not stop.is_set() and time.perf_counter() < deadline:
            delay = next_at - time.perf_counter()
            if delay > 0:
                stop.wait(delay)
                continue
            send_secure(sock, session, make_message(
                "TEXT", f"peer-{args.index}", "hub", {"text": f"{time.perf_counter():.6f}|{sent}|{padding}"}))
            sent += 1
            next_at += interval
            if time.perf_counter() - next_at > 1.0:                      # tre qua 1 s: khong co gang bu
                next_at = time.perf_counter()
    except Exception as exc:  # noqa: BLE001
        errors.append("send:" + type(exc).__name__)
    send_seconds = time.perf_counter() - first
    drain_until = time.time() + 3.0
    while len(latencies) < sent and time.time() < drain_until and not errors:
        time.sleep(0.02)
    closing.set()
    sock.close()
    emit("RESULT " + json.dumps({
        "index": args.index, "sent": sent, "received": len(latencies), "send_seconds": send_seconds,
        "latencies_ms": [round(v, 2) for v in latencies], "errors": errors}, separators=(",", ":")))


# =========================================================================== vai tro: truyen file
def role_file(args):
    sock, session, handshake_ms = connect_and_handshake(args, "peer-file")
    emit(f"READY {handshake_ms:.1f}")
    if not wait_for_go():
        return
    stop = threading.Event()

    def watch_stdin():
        for line in sys.stdin:
            if line.strip() == "STOP":
                break
        stop.set()

    threading.Thread(target=watch_stdin, daemon=True).start()
    size = int(args.size_mb * 1024 * 1024)
    total = max(1, -(-size // CHUNK_SIZE))
    base = os.urandom(CHUNK_SIZE)

    def plain_chunk(i):
        length = CHUNK_SIZE if i < total - 1 else size - CHUNK_SIZE * (total - 1)
        return (i.to_bytes(8, "big") + base)[:length]

    def one_transfer(pool):
        tid = str(uuid.uuid4())
        crypto = session.chunk_crypto(tid, total, sending=True)
        digest = hashlib.sha256()
        started = time.perf_counter()
        send_secure(sock, session, make_message("FILE", "peer-file", "hub", {
            "action": "OFFER", "transfer_id": tid, "file_name": "benchmark.bin", "file_size": size,
            "chunk_size": CHUNK_SIZE, "total_chunks": total}))
        encrypt_s = send_s = 0.0
        for first in range(0, total, 64):
            indexes = list(range(first, min(first + 64, total)))
            plains = [plain_chunk(i) for i in indexes]
            t0 = time.perf_counter()
            blobs = list(pool.map(lambda pair: crypto.encrypt_chunk(pair[0], pair[1]), zip(indexes, plains)))
            encrypt_s += time.perf_counter() - t0
            for plain in plains:
                digest.update(plain)
            t0 = time.perf_counter()
            for index, blob in zip(indexes, blobs):
                send_frame(sock, index.to_bytes(4, "big") + blob)
            send_s += time.perf_counter() - t0
        send_secure(sock, session, make_message("FILE", "peer-file", "hub", {
            "action": "DONE", "transfer_id": tid, "sha256": digest.hexdigest()}))
        reply = recv_secure(sock, session)["payload"]
        return {"elapsed": time.perf_counter() - started, "encrypt": encrypt_s, "send": send_s,
                "hub_decrypt": reply.get("decrypt_seconds", 0.0), "ok": bool(reply.get("ok"))}

    runs, error = [], None
    try:
        with ThreadPoolExecutor(args.threads) as pool:
            while True:                                   # lap lai cho den khi nhan STOP (it nhat 1 lan)
                runs.append(one_transfer(pool))
                emit(f"TRANSFER {len(runs)} {runs[-1]['elapsed']:.3f}")
                if stop.is_set() or not runs[-1]["ok"]:
                    break
    except Exception as exc:  # noqa: BLE001
        error = type(exc).__name__
    sock.close()
    done = [r for r in runs]
    n = len(done)
    sum_of = lambda key: sum(r[key] for r in done)  # noqa: E731
    emit("RESULT " + json.dumps({
        "bytes": size, "transfers": n, "error": error,
        "elapsed_s": sum_of("elapsed") / n if n else 0,
        "throughput_mib_s": mib(size * n) / sum_of("elapsed") if n and sum_of("elapsed") else 0,
        "throughput_min_mib_s": min((mib(size) / r["elapsed"] for r in done), default=0),
        "encrypt_seconds": sum_of("encrypt"),
        "encrypt_mib_s": mib(size * n) / sum_of("encrypt") if n and sum_of("encrypt") else 0,
        "hub_decrypt_seconds": sum_of("hub_decrypt"),
        "hub_decrypt_mib_s": mib(size * n) / sum_of("hub_decrypt") if n and sum_of("hub_decrypt") else 0,
        "sha256_ok": bool(n) and all(r["ok"] for r in done) and error is None, "threads": args.threads},
        separators=(",", ":")))


# =========================================================================== dieu phoi
class Child:
    """Mot tien trinh con (hub/peer/file): doc stdout vao danh sach, gui lenh qua stdin."""

    def __init__(self, role_args):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        self.proc = subprocess.Popen([sys.executable, str(HERE), *map(str, role_args)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env,
                                     encoding="utf-8")
        self.lines = []
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            self.lines.append(line.rstrip("\n"))

    def wait_line(self, prefix, timeout):
        end, seen = time.time() + timeout, 0
        while time.time() < end:
            while seen < len(self.lines):
                line = self.lines[seen]
                seen += 1
                if line.startswith(prefix):
                    return line
            if self.proc.poll() is not None and seen >= len(self.lines):
                return None
            time.sleep(0.02)
        return None

    def result(self, timeout):
        line = self.wait_line("RESULT ", timeout)
        return json.loads(line[7:]) if line else None

    def send(self, text):
        try:
            self.proc.stdin.write(text + "\n")
            self.proc.stdin.flush()
        except OSError:
            pass

    def alive(self):
        return self.proc.poll() is None

    def tail(self):
        return " | ".join(self.lines[-4:])

    def kill(self):
        if self.alive():
            self.proc.kill()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            pass


class Sampler(threading.Thread):
    """Lay mau CPU (% cua 1 nhan) va RAM cua may chu va cac peer moi 0,5 giay."""

    def __init__(self, hub_pid, peer_pids):
        super().__init__(daemon=True)
        self.hub = psutil.Process(hub_pid)
        self.peers = [psutil.Process(pid) for pid in peer_pids]
        self.stop_event = threading.Event()
        self.hub_cpu, self.hub_rss, self.peers_rss, self.system_cpu = [], [], [], []
        self.hub.cpu_percent(None)
        psutil.cpu_percent(None)

    def run(self):
        while not self.stop_event.wait(0.5):
            try:
                self.hub_cpu.append(self.hub.cpu_percent(None))
                self.hub_rss.append(self.hub.memory_info().rss)
                total = 0
                for peer in self.peers:
                    try:
                        total += peer.memory_info().rss
                    except psutil.Error:
                        pass
                self.peers_rss.append(total)
                self.system_cpu.append(psutil.cpu_percent(None))
            except psutil.Error:
                return

    def summary(self):
        avg = lambda values: sum(values) / len(values) if values else 0.0  # noqa: E731
        return {
            "hub_cpu_avg_percent": avg(self.hub_cpu), "hub_cpu_max_percent": max(self.hub_cpu, default=0.0),
            "hub_rss_peak_mib": mib(max(self.hub_rss, default=0)),
            "peers_rss_peak_mib": mib(max(self.peers_rss, default=0)),
            "system_cpu_avg_percent": avg(self.system_cpu), "system_cpu_max_percent": max(self.system_cpu, default=0.0)}


def run_level(config, opts):
    name, peers, rate = config["name"], config["peers"], config["rate"]
    out = {"level": name, "peers": peers, "target_rate": rate, "file_mb": config["file_mb"], "problems": []}
    children = []
    hub = Child(["--role", "hub"])
    children.append(hub)
    try:
        line = hub.wait_line("PORT ", 30)
        if not line:
            raise RuntimeError("may chu mau khong khoi dong: " + hub.tail())
        port = int(line.split()[1])
        peer_procs = [Child(["--role", "peer", "--port", port, "--index", i, "--peers", peers,
                             "--rate", rate / peers, "--payload", opts.payload,
                             "--max-seconds", opts.max_seconds]) for i in range(peers)]
        file_proc = Child(["--role", "file", "--port", port, "--size-mb", config["file_mb"], "--threads", opts.threads])
        children += peer_procs + [file_proc]

        handshakes = []
        for label, child in [(f"peer-{i}", c) for i, c in enumerate(peer_procs)] + [("file", file_proc)]:
            ready = child.wait_line("READY ", opts.ready_timeout)
            if not ready:
                out["problems"].append(f"{label} khong san sang: {child.tail()}")
            else:
                handshakes.append(float(ready.split()[1]))
        if out["problems"]:
            raise RuntimeError("; ".join(out["problems"]))
        out["handshake_ms_avg"] = sum(handshakes) / len(handshakes)
        out["handshake_ms_max"] = max(handshakes)

        sampler = Sampler(hub.proc.pid, [c.proc.pid for c in peer_procs + [file_proc]])
        sampler.start()
        started = time.perf_counter()
        for child in peer_procs + [file_proc]:
            child.send("GO")
        if file_proc.wait_line("TRANSFER ", opts.max_seconds) is None:       # it nhat 1 lan truyen file xong
            out["problems"].append("truyen file khong hoan tat: " + file_proc.tail())
        remaining = opts.min_duration - (time.perf_counter() - started)
        if remaining > 0:
            time.sleep(remaining)
        for child in peer_procs + [file_proc]:
            child.send("STOP")
        file_result = file_proc.result(opts.max_seconds)
        if file_result is None:
            out["problems"].append("khong nhan duoc ket qua truyen file: " + file_proc.tail())
        elif file_result.get("error"):
            out["problems"].append("loi truyen file: " + file_result["error"])
        results = [peer.result(60) for peer in peer_procs]
        out["load_seconds"] = time.perf_counter() - started
        hub_alive = hub.alive()
        sampler.stop_event.set()
        sampler.join(5)
    finally:
        for child in children:
            child.kill()

    results_ok = [r for r in results if r]
    out["problems"] += [f"peer-{i} khong tra ket qua" for i, r in enumerate(results) if not r]
    sent = sum(r["sent"] for r in results_ok)
    received = sum(r["received"] for r in results_ok)
    latencies = [v for r in results_ok for v in r["latencies_ms"]]
    send_window = max((r["send_seconds"] for r in results_ok), default=0) or 1
    errors = [e for r in results_ok for e in r["errors"]]
    out["messages"] = {
        "sent": sent, "received": received, "lost": sent - received,
        "loss_percent": 100.0 * (sent - received) / sent if sent else 100.0,
        "achieved_rate": sent / send_window, "errors": errors,
        "latency_ms": {"p50": percentile(latencies, 50), "p95": percentile(latencies, 95),
                       "p99": percentile(latencies, 99), "max": max(latencies, default=0.0)}}
    out["file"] = file_result
    out["resources"] = sampler.summary()
    out["checks"] = {
        "khong_loi_ket_noi": not errors and not out["problems"] and hub_alive,
        "khong_mat_tin": out["messages"]["loss_percent"] <= opts.max_loss_percent,
        "tre_p95_dat": out["messages"]["latency_ms"]["p95"] <= opts.max_p95_ms,
        "dat_toc_do_gui": out["messages"]["achieved_rate"] >= 0.9 * rate,
        "file_sha256_dung": bool(file_result and file_result["sha256_ok"])}
    out["status"] = "PASS" if all(out["checks"].values()) else "FAIL"
    return out


# =========================================================================== do toc do AES-256
def _timed(operation, budget, max_bytes, size):
    """Chay operation lien tuc trong `budget` giay (hoac toi max_bytes). Tra ve (so lan, giay, ket qua)."""
    outputs, started, count = [], time.perf_counter(), 0
    while time.perf_counter() - started < budget and count * size < max_bytes:
        outputs.append(operation(count))
        count += 1
    return count, time.perf_counter() - started, outputs


def bench_aes(quick):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    budget, cap = (0.15, 16 << 20) if quick else (0.5, 64 << 20)
    rows = []
    for size in (64, 1024, 16 * 1024, 64 * 1024, 1024 * 1024):
        key = new_session_key()
        sender, receiver = SessionCrypto(key, True, b"bench"), SessionCrypto(key, False, b"bench")
        data = os.urandom(size)
        count, enc_s, blobs = _timed(lambda _: sender.encrypt(data), budget, cap, size)
        started = time.perf_counter()
        for blob in blobs:
            receiver.decrypt(blob)
        dec_s = time.perf_counter() - started
        rows.append({"layer": "SessionCrypto (tin nhan)", "size": size, "ops": count,
                     "enc_mib_s": mib(count * size) / enc_s, "dec_mib_s": mib(count * size) / dec_s,
                     "enc_us": enc_s / count * 1e6, "dec_us": dec_s / count * 1e6})
    chunk_size = CHUNK_SIZE
    total = 10 ** 7
    key = new_session_key()
    sender, receiver = SessionCrypto(key, True, b"bench"), SessionCrypto(key, False, b"bench")
    enc, dec = sender.chunk_crypto("bench", total, True), receiver.chunk_crypto("bench", total, False)
    data = os.urandom(chunk_size)
    count, enc_s, blobs = _timed(lambda i: enc.encrypt_chunk(i, data), budget, cap, chunk_size)
    started = time.perf_counter()
    for i, blob in enumerate(blobs):
        dec.decrypt_chunk(i, blob)
    dec_s = time.perf_counter() - started
    rows.append({"layer": "ChunkCrypto (chunk file)", "size": chunk_size, "ops": count,
                 "enc_mib_s": mib(count * chunk_size) / enc_s, "dec_mib_s": mib(count * chunk_size) / dec_s,
                 "enc_us": enc_s / count * 1e6, "dec_us": dec_s / count * 1e6})
    raw = AESGCM(os.urandom(32))
    count, enc_s, blobs = _timed(lambda _: (lambda n: (n, raw.encrypt(n, data, None)))(os.urandom(12)), budget, cap, chunk_size)
    started = time.perf_counter()
    for nonce, blob in blobs:
        raw.decrypt(nonce, blob, None)
    dec_s = time.perf_counter() - started
    rows.append({"layer": "AESGCM tho (doi chung)", "size": chunk_size, "ops": count,
                 "enc_mib_s": mib(count * chunk_size) / enc_s, "dec_mib_s": mib(count * chunk_size) / dec_s,
                 "enc_us": enc_s / count * 1e6, "dec_us": dec_s / count * 1e6})
    return rows


def bench_file_crypto(size_mb, threads, quick):
    """Ma hoa roi giai ma ca file (chia chunk 64 KB) mot luong va nhieu luong."""
    size = int(size_mb * 1024 * 1024)
    total = max(1, -(-size // CHUNK_SIZE))
    results = {}
    for workers in sorted({1, max(1, threads)}):
        label = f"{workers} luong"
        key = new_session_key()
        sender, receiver = SessionCrypto(key, True, b"bench"), SessionCrypto(key, False, b"bench")
        enc, dec = sender.chunk_crypto("file", total, True), receiver.chunk_crypto("file", total, False)
        data = os.urandom(CHUNK_SIZE)
        enc_s = dec_s = 0.0
        with ThreadPoolExecutor(workers) as pool:
            for first in range(0, total, 64):
                indexes = list(range(first, min(first + 64, total)))
                t0 = time.perf_counter()
                blobs = list(pool.map(lambda i: enc.encrypt_chunk(i, data), indexes))
                enc_s += time.perf_counter() - t0
                t0 = time.perf_counter()
                list(pool.map(lambda pair: dec.decrypt_chunk(pair[0], pair[1]), zip(indexes, blobs)))
                dec_s += time.perf_counter() - t0
        results[label] = {"enc_mib_s": mib(size) / enc_s, "dec_mib_s": mib(size) / dec_s,
                          "enc_seconds": enc_s, "dec_seconds": dec_s}
    return {"size_mb": size_mb, "results": results}


def bench_handshake(quick):
    import statistics
    keygen, handshake = [], []
    for _ in range(3 if quick else 5):
        t0 = time.perf_counter()
        KeyPair.generate()
        keygen.append((time.perf_counter() - t0) * 1000)
    key_a, key_b = KeyPair.generate(), KeyPair.generate()
    for _ in range(5 if quick else 10):
        sock_a, sock_b = socket.socketpair()
        worker = threading.Thread(target=lambda: handshake_responder(sock_b, key_b, "b"), daemon=True)
        worker.start()
        t0 = time.perf_counter()
        handshake_initiator(sock_a, key_a, "a", "b")
        handshake.append((time.perf_counter() - t0) * 1000)
        worker.join(10)
        sock_a.close()
        sock_b.close()
    return {"keygen_ms_median": statistics.median(keygen), "handshake_ms_median": statistics.median(handshake)}


# =========================================================================== bao cao
def environment():
    return {"os": f"{platform.system()} {platform.release()}", "python": platform.python_version(),
            "cpu": platform.processor() or platform.machine(), "logical_cores": psutil.cpu_count(),
            "ram_gib": round(psutil.virtual_memory().total / 2 ** 30, 1),
            "cryptography": __import__("cryptography").__version__, "time": datetime.now().isoformat(timespec="seconds")}


def render_report(data):
    env = data["environment"]
    lines = ["# Báo cáo kiểm thử hiệu năng (Stress Test & Performance Test)", "",
             f"Thời gian: {env['time']} | Hệ điều hành: {env['os']} | Python {env['python']} | "
             f"{env['logical_cores']} nhân logic, {env['ram_gib']} GiB RAM | cryptography {env['cryptography']}", ""]
    if "aes" in data:
        lines += ["## 1. Tốc độ AES-256-GCM", "",
                  "| Lớp | Kích thước | Mã hóa (MiB/s) | Giải mã (MiB/s) | Mã hóa (µs/lần) | Giải mã (µs/lần) |", "|---|---|---|---|---|---|"]
        for r in data["aes"]:
            size = f"{r['size']} B" if r["size"] < 1024 else f"{r['size'] // 1024} KiB"
            lines.append(f"| {r['layer']} | {size} | {r['enc_mib_s']:.0f} | {r['dec_mib_s']:.0f} | {r['enc_us']:.1f} | {r['dec_us']:.1f} |")
        lines += ["", "Mã hóa và giải mã cả file (chunk 64 KiB):", "", "| File | Số luồng | Mã hóa (MiB/s) | Giải mã (MiB/s) |", "|---|---|---|---|"]
        for entry in data.get("aes_file", []):
            for label, r in entry["results"].items():
                lines.append(f"| {entry['size_mb']} MB | {label} | {r['enc_mib_s']:.0f} | {r['dec_mib_s']:.0f} |")
        hs = data.get("handshake")
        if hs:
            lines += ["", f"RSA-2048: sinh khóa trung vị {hs['keygen_ms_median']:.0f} ms; bắt tay đầy đủ trung vị {hs['handshake_ms_median']:.1f} ms.", ""]
    for n, level in enumerate(data.get("levels", []), start=2):
        m, res, f = level["messages"], level["resources"], level.get("file")
        lines += [f"## {n}. {level['level']}: {level['peers']} peer, {level['target_rate']} tin/giây, file {level['file_mb']} MB: **{level['status']}**", ""]
        if level["problems"]:
            lines += ["Vấn đề: " + "; ".join(level["problems"]), ""]
        lines += ["| Chỉ số | Giá trị |", "|---|---|",
                  f"| Tin gửi / nhận / mất | {m['sent']} / {m['received']} / {m['lost']} ({m['loss_percent']:.2f}%) |",
                  f"| Tốc độ gửi đạt được | {m['achieved_rate']:.1f} tin/giây (mục tiêu {level['target_rate']}) |",
                  f"| Độ trễ khứ hồi p50 / p95 / p99 / max | {m['latency_ms']['p50']:.1f} / {m['latency_ms']['p95']:.1f} / {m['latency_ms']['p99']:.1f} / {m['latency_ms']['max']:.1f} ms |"]
        if f:
            lines += [f"| Truyền file {level['file_mb']} MB (lặp {f['transfers']} lần suốt thời gian chịu tải) | trung bình {f['elapsed_s']:.2f} s/lần, {f['throughput_mib_s']:.1f} MiB/s (chậm nhất {f['throughput_min_mib_s']:.1f}), SHA-256 {'đúng cả' if f['sha256_ok'] else 'CÓ LẦN SAI'} |",
                      f"| Tốc độ mã hóa thực (bên gửi) / giải mã thực (máy chủ) | {f['encrypt_mib_s']:.0f} / {f['hub_decrypt_mib_s']:.0f} MiB/s ({f['threads']} luồng mã hóa) |"]
        lines += [f"| Bắt tay (kết nối + RSA) trung bình / lớn nhất | {level.get('handshake_ms_avg', 0):.0f} / {level.get('handshake_ms_max', 0):.0f} ms |",
                  f"| CPU máy chủ trung bình / cao nhất | {res['hub_cpu_avg_percent']:.0f}% / {res['hub_cpu_max_percent']:.0f}% (của 1 nhân) |",
                  f"| RAM đỉnh máy chủ / tổng các peer | {res['hub_rss_peak_mib']:.0f} MiB / {res['peers_rss_peak_mib']:.0f} MiB |",
                  f"| CPU toàn máy trung bình / cao nhất | {res['system_cpu_avg_percent']:.0f}% / {res['system_cpu_max_percent']:.0f}% |", "",
                  "Tiêu chí: " + ", ".join(f"{k}: {'đạt' if v else 'KHÔNG ĐẠT'}" for k, v in level["checks"].items()), ""]
    return "\n".join(lines)


def print_summary(data):
    if "aes" in data:
        emit("\n== AES-256-GCM (MiB/s: ma hoa / giai ma) ==")
        for r in data["aes"]:
            emit(f"  {r['layer']:28} {r['size']:>8} B  {r['enc_mib_s']:8.0f} / {r['dec_mib_s']:8.0f}")
        for entry in data.get("aes_file", []):
            for label, r in entry["results"].items():
                emit(f"  file {entry['size_mb']} MB, {label:8}        {r['enc_mib_s']:8.0f} / {r['dec_mib_s']:8.0f}")
    for level in data.get("levels", []):
        m, f, res = level["messages"], level.get("file"), level["resources"]
        emit(f"\n== {level['level']}: {level['peers']} peer, {level['target_rate']} tin/s, file {level['file_mb']} MB -> {level['status']} ==")
        emit(f"  tin: gui {m['sent']}, nhan {m['received']}, mat {m['lost']} ({m['loss_percent']:.2f}%), toc do {m['achieved_rate']:.1f}/s")
        emit(f"  tre khu hoi ms: p50 {m['latency_ms']['p50']:.1f}  p95 {m['latency_ms']['p95']:.1f}  p99 {m['latency_ms']['p99']:.1f}  max {m['latency_ms']['max']:.1f}")
        if f:
            emit(f"  file: {f['transfers']} lan x {level['file_mb']} MB, {f['elapsed_s']:.2f} s/lan, {f['throughput_mib_s']:.1f} MiB/s (cham nhat {f['throughput_min_mib_s']:.1f}), ma hoa {f['encrypt_mib_s']:.0f} / giai ma {f['hub_decrypt_mib_s']:.0f} MiB/s, sha256 {'OK' if f['sha256_ok'] else 'SAI'}")
        emit(f"  hub CPU {res['hub_cpu_avg_percent']:.0f}%/{res['hub_cpu_max_percent']:.0f}% (1 nhan), RAM hub {res['hub_rss_peak_mib']:.0f} MiB, peers {res['peers_rss_peak_mib']:.0f} MiB")
        for key, ok in level["checks"].items():
            emit(f"    [{'dat' if ok else 'KHONG DAT'}] {key}")
        for problem in level["problems"]:
            emit("    ! " + problem)


# =========================================================================== main
def build_parser():
    p = argparse.ArgumentParser(description="Stress Test & Performance Test 2 muc tai + toc do AES-256")
    p.add_argument("--role", choices=["hub", "peer", "file"], help=argparse.SUPPRESS)
    p.add_argument("--port", type=int, help=argparse.SUPPRESS)
    p.add_argument("--index", type=int, default=0, help=argparse.SUPPRESS)
    p.add_argument("--peers", type=int, default=1, help=argparse.SUPPRESS)
    p.add_argument("--rate", type=float, default=10.0, help=argparse.SUPPRESS)
    p.add_argument("--size-mb", type=float, default=1.0, help=argparse.SUPPRESS)
    p.add_argument("--level", choices=["1", "2", "all"], default="all")
    p.add_argument("--aes-only", action="store_true", help="chi do toc do AES-256")
    p.add_argument("--skip-aes", action="store_true", help="bo qua phan do AES")
    p.add_argument("--quick", action="store_true", help="ban thu nho de kiem tra script (file nho, ngan)")
    p.add_argument("--smoke", action="store_true", help="ban rat nho dung cho test tu dong")
    p.add_argument("--min-duration", type=float, default=15.0, help="so giay toi thieu duy tri tai tin nhan moi muc")
    p.add_argument("--payload", type=int, default=128, help="kich thuoc moi tin (ky tu)")
    p.add_argument("--threads", type=int, default=min(4, os.cpu_count() or 1), help="so luong ma hoa chunk")
    p.add_argument("--max-p95-ms", type=float, default=500.0, help="nguong do tre p95 de DAT")
    p.add_argument("--max-loss-percent", type=float, default=0.0, help="ti le mat tin toi da de DAT")
    p.add_argument("--max-seconds", type=float, default=900.0)
    p.add_argument("--ready-timeout", type=float, default=180.0)
    p.add_argument("--out", default="benchmark_results", help="thu muc luu bao cao")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.role == "hub":
        return role_hub()
    if args.role == "peer":
        return role_peer(args)
    if args.role == "file":
        return role_file(args)

    quick = args.quick or args.smoke
    if args.quick:
        args.min_duration = min(args.min_duration, 3.0)
    if args.smoke:
        args.min_duration = 2.0
    data = {"environment": environment(), "settings": {k: v for k, v in vars(args).items() if k != "role"}}
    emit(f"Moi truong: {data['environment']['os']}, Python {data['environment']['python']}, "
         f"{data['environment']['logical_cores']} nhan, {data['environment']['ram_gib']} GiB RAM")

    if not args.skip_aes:
        emit("Do toc do AES-256 ...")
        data["aes"] = bench_aes(quick)
        data["aes_file"] = [bench_file_crypto(size, args.threads, quick) for size in ((1, 4) if quick else (10, 100))]
        data["handshake"] = bench_handshake(quick)

    if not args.aes_only:
        if args.smoke:
            configs = [{"name": "Smoke", "peers": 2, "rate": 20, "file_mb": 1}]
        else:
            chosen = [1, 2] if args.level == "all" else [int(args.level)]
            configs = [dict(LEVELS[n], file_mb=QUICK_FILE_MB[n] if args.quick else LEVELS[n]["file_mb"]) for n in chosen]
        data["levels"] = []
        for config in configs:
            emit(f"\nChay {config['name']}: {config['peers']} peer, {config['rate']} tin/giay, file {config['file_mb']} MB ...")
            data["levels"].append(run_level(config, args))

    print_summary(data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    (out_dir / f"benchmark_{stamp}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / f"benchmark_{stamp}.md").write_text(render_report(data), encoding="utf-8")
    emit(f"\nDa luu bao cao: {out_dir / f'benchmark_{stamp}.md'} (va .json)")
    failed = [lv["level"] for lv in data.get("levels", []) if lv["status"] != "PASS"]
    if failed:
        emit("KHONG DAT: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())