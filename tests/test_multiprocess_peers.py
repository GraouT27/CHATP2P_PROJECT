"""Kiem thu nhieu tien trinh Peer Python chay CUNG LUC: bat tay, emoji, avatar (Chang 4, TV1)."""
import json
import os
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path

WORKER = str(Path(__file__).resolve().parent / "peer_worker.py")
PAIRS = 4          # 4 cap = 8 tien trinh cung luc


def _read_line(proc, timeout):
    box = queue.Queue()
    threading.Thread(target=lambda: box.put(proc.stdout.readline()), daemon=True).start()
    try:
        return box.get(timeout=timeout)
    except queue.Empty:
        return ""


def _spawn(*args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.Popen([sys.executable, WORKER, *args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8", env=env)


def _result(out):
    lines = [x for x in out.splitlines() if x.startswith("RESULT ")]
    assert lines, f"khong co RESULT: {out!r}"
    return json.loads(lines[-1][len("RESULT "):])


def test_many_peer_processes_exchange_emoji_and_avatar(tmp_path):
    listeners, connectors = [], []
    try:
        for n in range(PAIRS):
            lis = _spawn("listen", f"peer-{n}-L", str(tmp_path / f"L{n}"))
            listeners.append(lis)
            line = _read_line(lis, 20)
            assert line.startswith("PORT "), f"listener {n} khong len: {line!r}"
            connectors.append(_spawn("connect", f"peer-{n}-C", str(tmp_path / f"C{n}"), line.split()[1]))

        results = []
        for proc in listeners + connectors:
            out, err = proc.communicate(timeout=60)
            assert proc.returncode == 0, f"tien trinh loi: {err}\n{out}"
            results.append(_result(out))
    finally:
        for proc in listeners + connectors:
            if proc.poll() is None:
                proc.kill()

    assert len(results) == 2 * PAIRS
    assert all(r["emoji_ok"] and r["avatar_ok"] for r in results)
    assert all(r["avatar_bytes"] > 5000 for r in results)
    by_id = {r["id"]: r for r in results}
    for n in range(PAIRS):
        lis, con = by_id[f"peer-{n}-L"], by_id[f"peer-{n}-C"]
        assert lis["peer_id"] == f"peer-{n}-C" and con["peer_id"] == f"peer-{n}-L"
        assert lis["peer_fingerprint"] == con["fingerprint"]
        assert con["peer_fingerprint"] == lis["fingerprint"]
    assert len({r["fingerprint"] for r in results}) == 2 * PAIRS     # moi tien trinh co khoa rieng


def test_logs_of_all_processes_have_no_secrets(tmp_path):
    test_many_peer_processes_exchange_emoji_and_avatar(tmp_path)
    files = list(tmp_path.rglob("app.log"))
    assert len(files) == 2 * PAIRS
    for path in files:
        content = path.read_text(encoding="utf-8")
        assert "HANDSHAKE_OK" in content
        assert "BEGIN" not in content
        assert not re.search(r"[A-Za-z0-9+/]{40,}", content)
        assert not re.search(r"\b[0-9a-fA-F]{32,}\b", content)
        for line in content.splitlines():
            json.loads(line)