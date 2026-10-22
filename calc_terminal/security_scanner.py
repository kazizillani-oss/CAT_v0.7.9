"""
CCT Security Scanner — real static analysis (Python `ast` module, not
regex guessing) over code before it's run from /codepad, flagging
patterns that can escape the sandbox, touch the filesystem/network, or
are otherwise risky to execute automatically. This does not "fix" code
or pretend to catch everything static analysis fundamentally can't
catch (e.g. cleverly obfuscated payloads) — it's a real first pass, the
same category of check `bandit` does, sized for this app.
"""

import ast

HIGH = "high"
MEDIUM = "medium"
LOW = "low"

_DANGEROUS_CALLS = {
    "eval": HIGH, "exec": HIGH, "compile": MEDIUM,
    "__import__": MEDIUM,
}
_DANGEROUS_MODULES = {
    "os": MEDIUM, "subprocess": HIGH, "shutil": MEDIUM,
    "socket": HIGH, "ctypes": HIGH, "multiprocessing": MEDIUM,
    "pickle": HIGH, "marshal": HIGH, "importlib": MEDIUM,
    "sys": LOW,
}
_DANGEROUS_ATTRS = {
    "system": HIGH, "popen": HIGH, "spawn": HIGH, "remove": MEDIUM,
    "rmtree": HIGH, "unlink": MEDIUM, "chmod": MEDIUM, "kill": HIGH,
    "fork": HIGH, "loads": MEDIUM,  # pickle.loads / marshal.loads
}


class Finding:
    __slots__ = ("severity", "line", "message")

    def __init__(self, severity, line, message):
        self.severity = severity
        self.line = line
        self.message = message

    def __repr__(self):
        return f"[{self.severity.upper()}] line {self.line}: {self.message}"


def scan_code(code):
    """Return a list of Finding objects. Never raises on syntactically
    broken code — a SyntaxError just becomes a single LOW finding, since
    code that doesn't parse can't be analysed further (and will fail to
    run anyway, which is not a security issue by itself)."""
    findings = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [Finding(LOW, getattr(e, "lineno", 0) or 0, f"Syntax error: {e.msg}")]

    imported_names = {}  # local name -> real module

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                imported_names[alias.asname or alias.name] = mod
                if mod in _DANGEROUS_MODULES:
                    findings.append(Finding(
                        _DANGEROUS_MODULES[mod], node.lineno,
                        f"imports '{mod}' — can affect the host system if misused"))
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            for alias in node.names:
                imported_names[alias.asname or alias.name] = mod
            if mod in _DANGEROUS_MODULES:
                findings.append(Finding(
                    _DANGEROUS_MODULES[mod], node.lineno,
                    f"imports from '{mod}' — can affect the host system if misused"))
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in _DANGEROUS_CALLS:
                findings.append(Finding(
                    _DANGEROUS_CALLS[fn.id], node.lineno,
                    f"calls {fn.id}(...) — dynamic code execution"))
            elif isinstance(fn, ast.Attribute) and fn.attr in _DANGEROUS_ATTRS:
                base = fn.value.id if isinstance(fn.value, ast.Name) else "?"
                findings.append(Finding(
                    _DANGEROUS_ATTRS[fn.attr], node.lineno,
                    f"calls {base}.{fn.attr}(...) — potentially dangerous operation"))
        elif isinstance(node, ast.Attribute) and node.attr in ("__globals__", "__subclasses__", "__bases__"):
            findings.append(Finding(
                MEDIUM, node.lineno,
                f"accesses {node.attr} — a classic sandbox-escape technique"))

    # open(..., mode with 'w'/'a') — filesystem writes
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            mode = None
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            if mode and any(c in str(mode) for c in "wax+"):
                findings.append(Finding(
                    MEDIUM, node.lineno, f"opens a file for writing (mode='{mode}')"))

    return findings


def risk_level(findings):
    if any(f.severity == HIGH for f in findings):
        return HIGH
    if any(f.severity == MEDIUM for f in findings):
        return MEDIUM
    if findings:
        return LOW
    return "none"


def summarize(findings):
    """Short human-readable summary line for a permission card."""
    if not findings:
        return "No risky patterns detected."
    counts = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    parts = [f"{counts[s]} {s}" for s in (HIGH, MEDIUM, LOW) if s in counts]
    return ", ".join(parts) + " finding(s)"
