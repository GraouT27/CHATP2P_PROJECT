"""Ra soat bao mat tinh ma nguon Python bang AST (TV1, Chang 6).

Chay:  python tests/audit_source.py [thu_muc_hoac_file]      (mac dinh: CODE)
Thoat voi ma 1 neu co phat hien muc HIGH.

Muc do: HIGH (phai sua), MEDIUM (nen sua), LOW (thong tin).
"""
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
DANGEROUS_CALLS = {"eval", "exec", "pickle.load", "pickle.loads", "marshal.load", "marshal.loads",
                   "os.system", "os.popen", "pdb.set_trace", "breakpoint"}
MESSAGE_NAMES = {"text", "message", "payload", "plaintext", "body", "content"}
_SENSITIVE = re.compile(
    r"(private|secret|passw|session_key|aes_key|file_key|send_key|recv_key|a2b_key|b2a_key|master|_key$|^key$)",
    re.I)
_PRIVATE_PEM = re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")


@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    path: str
    line: int
    message: str


def is_sensitive_name(name: str) -> bool:
    low = name.lower()
    if "public" in low or low.endswith("_id"):
        return False
    return bool(_SENSITIVE.search(name))


def _call_name(node: ast.Call) -> str:
    func, parts = node.func, []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
    return ".".join(reversed(parts))


def _names_in(node):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            yield sub.id
        elif isinstance(sub, ast.Attribute):
            yield sub.attr
        elif isinstance(sub, ast.keyword) and sub.arg:
            yield sub.arg


def _is_log_call(node: ast.Call) -> bool:
    name = _call_name(node)
    if name in {"print", "log_event"}:
        return True
    return isinstance(node.func, ast.Attribute) and node.func.attr in LOG_METHODS and "log" in name.lower()


def _enclosing_scope(node, parents):
    while node in parents:
        node = parents[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            return node
    return node


def scan_source(source: str, path: str = "<string>", strict_random: bool = False):
    tree = ast.parse(source)
    lines = source.splitlines()
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    out = []

    def add(severity, rule, node, message):
        out.append(Finding(severity, rule, path, getattr(node, "lineno", 0), message))

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and _PRIVATE_PEM.search(node.value):
            add("HIGH", "hardcoded-private-key", node, "Khoa rieng nam cung trong ma nguon")

        elif isinstance(node, ast.Call):
            name = _call_name(node)
            if name in DANGEROUS_CALLS:
                add("HIGH", "dangerous-call", node, f"Goi ham nguy hiem: {name}")
            if name.startswith("subprocess.") and any(
                    k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True
                    for k in node.keywords):
                add("HIGH", "shell-true", node, "subprocess voi shell=True")
            if any(k.arg == "capture_locals" and isinstance(k.value, ast.Constant) and k.value.value is True
                   for k in node.keywords):
                add("HIGH", "capture-locals", node, "capture_locals=True dua gia tri bien (co the la khoa) vao Traceback")
            if _is_log_call(node):
                names = [n for sub in (*node.args, *node.keywords) for n in _names_in(sub)]
                bad = sorted({n for n in names if is_sensitive_name(n)})
                if bad:
                    add("HIGH", "secret-in-log", node, f"Dua bien nhay cam vao print/log: {bad}")
                if name == "print" and MESSAGE_NAMES & {n.lower() for n in names}:
                    add("LOW", "message-in-console", node, "In noi dung tin nhan ra man hinh")
            if name in {"socket.socket", "open", "socket.create_connection"}:
                parent = parents.get(node)
                managed = isinstance(parent, ast.withitem)
                scope = _enclosing_scope(node, parents)
                has_close = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                                and n.func.attr == "close" for n in ast.walk(scope))
                if not managed and not has_close:
                    add("MEDIUM", "unclosed-resource", node, f"{name}() khong dung with va khong co close()")

        elif isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            bad = sorted({n for n in _names_in(node.exc) if is_sensitive_name(n)})
            if bad:
                add("HIGH", "secret-in-raise", node, f"Bien nhay cam trong thong bao loi: {bad}")

        elif isinstance(node, ast.ExceptHandler):
            if node.type is None:
                add("MEDIUM", "bare-except", node, "except: tran (nuot ca KeyboardInterrupt)")
            elif isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"}:
                only_pass = all(isinstance(b, ast.Pass) or (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))
                                for b in node.body)
                marked = any("noqa" in lines[i - 1] for i in (node.lineno, node.body[0].lineno) if 0 < i <= len(lines))
                if only_pass and not marked:
                    add("MEDIUM", "swallowed-exception", node, "Nuot loi im lang (them noqa neu co chu y)")

        elif isinstance(node, ast.Import) and strict_random and any(a.name == "random" for a in node.names):
            add("MEDIUM", "weak-random", node, "Dung random trong module bao mat (dung secrets/os.urandom)")
        elif isinstance(node, ast.ImportFrom) and strict_random and node.module == "random":
            add("MEDIUM", "weak-random", node, "Dung random trong module bao mat (dung secrets/os.urandom)")
        elif isinstance(node, ast.Assert):
            add("LOW", "assert-in-code", node, "assert bi bo qua khi chay python -O, khong dung de kiem tra bao mat")
    return sorted(out, key=lambda f: (f.path, f.line, f.rule))


def scan_path(target) -> list:
    target = Path(target)
    files = [target] if target.is_file() else sorted(p for p in target.rglob("*.py") if "__pycache__" not in p.parts)
    found = []
    for file in files:
        source = file.read_text(encoding="utf-8", errors="ignore")
        found += scan_source(source, str(file), strict_random="security" in file.parts)
    return found


def main(argv) -> int:
    target = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[1] / "CODE"
    findings = scan_path(target)
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    for f in sorted(findings, key=lambda f: (order[f.severity], f.path, f.line)):
        print(f"{f.severity:6} {f.rule:22} {f.path}:{f.line}  {f.message}")
    counts = {s: sum(1 for f in findings if f.severity == s) for s in order}
    print(f"\nTong: HIGH={counts['HIGH']} MEDIUM={counts['MEDIUM']} LOW={counts['LOW']}")
    return 1 if counts["HIGH"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))