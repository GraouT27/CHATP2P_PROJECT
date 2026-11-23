"""Ra soat bao mat ma nguon (Chang 6, TV1): kiem tra chinh cong cu ra soat va ap dung len CODE/."""
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
CODE = TESTS.parent / "CODE"
sys.path.insert(0, str(TESTS))

from audit_source import is_sensitive_name, scan_path, scan_source  # noqa: E402

PEM_MARK = "BEGIN " + "RSA PRIVATE KEY"      # ghep chuoi de chinh file test nay khong bi coi la vi pham

BAD_SNIPPETS = [
    ("hardcoded-private-key", f'KEY = "-----{PEM_MARK}-----"'),
    ("dangerous-call", "eval(user_input)"),
    ("dangerous-call", "import pickle\npickle.loads(data)"),
    ("dangerous-call", "import os\nos.system('dir')"),
    ("dangerous-call", "breakpoint()"),
    ("shell-true", "import subprocess\nsubprocess.run('ls', shell=True)"),
    ("capture-locals", "import traceback\ntraceback.TracebackException(e, capture_locals=True)"),
    ("secret-in-log", "session_key = 1\nprint(session_key)"),
    ("secret-in-log", "log_event('X', private_key=k)"),
    ("secret-in-log", "logger.info('khoa: %s', self.aes_key)"),
    ("secret-in-raise", "raise ValueError(f'sai khoa {session_key}')"),
    ("bare-except", "try:\n    pass\nexcept:\n    pass"),
    ("swallowed-exception", "try:\n    f()\nexcept Exception:\n    pass"),
    ("unclosed-resource", "import socket\ndef f():\n    s = socket.socket()\n    s.connect(('a', 1))"),
    ("unclosed-resource", "def f():\n    data = open('x').read()"),
]

CLEAN_SNIPPETS = [
    "import socket\ndef f():\n    with socket.socket() as s:\n        s.connect(('a', 1))",
    "import socket\ndef f():\n    s = socket.socket()\n    try:\n        s.connect(('a', 1))\n    finally:\n        s.close()",
    "try:\n    f()\nexcept Exception:  # noqa: BLE001\n    pass",
    "try:\n    f()\nexcept ValueError:\n    pass",
    "log_event('X', peer=keypair.short_id(), key_id='k1', public_key=pem)",
    "print('Ket noi toi', host)",
    "raise ValueError('Khoa phien phai dai 32 byte')",
]


@pytest.mark.parametrize("rule,code", BAD_SNIPPETS, ids=[f"{r}-{i}" for i, (r, _) in enumerate(BAD_SNIPPETS)])
def test_auditor_detects_bad_pattern(rule, code):
    assert rule in {f.rule for f in scan_source(code)}, code


@pytest.mark.parametrize("code", CLEAN_SNIPPETS)
def test_auditor_accepts_clean_code(code):
    assert [f for f in scan_source(code) if f.severity in {"HIGH", "MEDIUM"}] == []


def test_weak_random_flagged_only_in_security_modules():
    assert "weak-random" in {f.rule for f in scan_source("import random", strict_random=True)}
    assert "weak-random" not in {f.rule for f in scan_source("import random", strict_random=False)}


def test_sensitive_name_rules():
    for name in ("session_key", "private_key", "aes_key", "file_key", "password", "key", "SECRET_TOKEN_secret"):
        assert is_sensitive_name(name), name
    for name in ("public_key", "key_id", "peer_key_id", "keypair", "fingerprint", "short_id", "monkey"):
        assert not is_sensitive_name(name), name


def test_security_modules_have_no_high_or_medium_findings():
    findings = [f for f in scan_path(CODE / "security") + scan_path(CODE / "logger.py")
                if f.severity in {"HIGH", "MEDIUM"}]
    assert findings == [], "\n".join(f"{f.severity} {f.rule} {f.path}:{f.line} {f.message}" for f in findings)


def test_whole_code_has_no_high_findings():
    findings = [f for f in scan_path(CODE) if f.severity == "HIGH"]
    assert findings == [], "\n".join(f"{f.rule} {f.path}:{f.line} {f.message}" for f in findings)


def test_no_key_files_in_repo():
    root = TESTS.parent
    bad = [p for p in root.rglob("*") if p.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
           and "venv" not in p.parts and ".git" not in p.parts]
    assert bad == [], bad