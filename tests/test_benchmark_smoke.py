"""Kiem tra script benchmark_stress.py chay duoc va bao dung (Chang 7, TV1).

Chay ban rat nho (--smoke: 2 peer, 20 tin/giay, file 1 MB) de kiem tra quy trinh, khong thay cho
viec chay day du 'python tests/benchmark_stress.py' de lay so lieu nop bai.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
SCRIPT = TESTS / "benchmark_stress.py"
sys.path.insert(0, str(TESTS))

from benchmark_stress import percentile  # noqa: E402


def run_script(tmp_path, *extra, timeout=240):
    return subprocess.run([sys.executable, str(SCRIPT), "--out", str(tmp_path), *extra],
                          capture_output=True, text=True, encoding="utf-8", timeout=timeout)


def load_report(tmp_path):
    files = sorted(tmp_path.glob("benchmark_*.json"))
    assert files, "khong co file bao cao JSON"
    return json.loads(files[-1].read_text(encoding="utf-8")), sorted(tmp_path.glob("benchmark_*.md"))[-1].read_text(encoding="utf-8")


def test_percentile():
    assert percentile([], 95) == 0.0
    assert percentile([5.0], 99) == 5.0
    assert percentile([1, 2, 3, 4, 5], 50) == 3
    assert percentile([1, 2, 3, 4, 5], 100) == 5
    assert percentile([0, 10], 50) == 5.0
    assert percentile(list(range(101)), 95) == pytest.approx(95)


def test_smoke_run_passes_and_writes_report(tmp_path):
    result = run_script(tmp_path, "--smoke", "--skip-aes")
    assert result.returncode == 0, result.stdout + result.stderr
    data, markdown = load_report(tmp_path)
    level = data["levels"][0]
    assert level["status"] == "PASS" and all(level["checks"].values())
    assert level["messages"]["sent"] > 0 and level["messages"]["lost"] == 0
    assert level["file"]["sha256_ok"] and level["file"]["transfers"] >= 1
    assert level["resources"]["hub_rss_peak_mib"] > 0
    assert "PASS" in markdown and "SHA-256" in markdown


def test_script_reports_failure_when_threshold_impossible(tmp_path):
    result = run_script(tmp_path, "--smoke", "--skip-aes", "--max-p95-ms", "0.0001")
    assert result.returncode == 1, result.stdout
    data, markdown = load_report(tmp_path)
    assert data["levels"][0]["status"] == "FAIL"
    assert data["levels"][0]["checks"]["tre_p95_dat"] is False
    assert "KHÔNG ĐẠT" in markdown


def test_aes_only_reports_positive_speeds(tmp_path):
    result = run_script(tmp_path, "--aes-only", "--quick", timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    data, markdown = load_report(tmp_path)
    layers = {row["layer"] for row in data["aes"]}
    assert {"SessionCrypto (tin nhan)", "ChunkCrypto (chunk file)", "AESGCM tho (doi chung)"} <= layers
    assert all(row["enc_mib_s"] > 0 and row["dec_mib_s"] > 0 and row["ops"] > 0 for row in data["aes"])
    assert data["aes_file"] and data["handshake"]["handshake_ms_median"] > 0
    assert "levels" not in data
    assert "AES-256-GCM" in markdown