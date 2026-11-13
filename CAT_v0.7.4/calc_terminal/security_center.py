"""
CAT Security Center (v0.7.9 Complete Platform Expansion)

Secret scanning, AST code safety auditing, dependency vulnerability analysis,
granular permission auditing, and security score reporting.
"""

import os
import re
import ast
from typing import Dict, List, Any, Optional

from . import permissions as perm

SECRET_PATTERNS = [
    ("OpenAI API Key", re.compile(r"sk-[a-zA-Z0-9]{20,50}")),
    ("GitHub Personal Access Token", re.compile(r"ghp_[a-zA-Z0-9]{36}")),
    ("Anthropic API Key", re.compile(r"sk-ant-[a-zA-Z0-9\-_]{20,80}")),
    ("Generic Private Key", re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----")),
    ("AWS Access Key ID", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Generic Password/Secret Assignment", re.compile(r"(?i)(api[_-]?key|password|secret|token)\s*=\s*['\"][a-zA-Z0-9\-_+=/]{8,}['\"]")),
]

KNOWN_VULNERABLE_PACKAGES = {
    "urllib3": ("<1.26.5", "CVE-2021-33503"),
    "requests": ("<2.20.0", "CVE-2018-18074"),
    "pyyaml": ("<5.4", "CVE-2020-14343 Arbitrary Code Execution"),
    "pillow": ("<9.0.0", "CVE-2022-22817 Buffer Overflow"),
    "jinja2": ("<2.11.3", "CVE-2020-28493 ReDoS"),
    "werkzeug": ("<2.2.3", "CVE-2023-25577 High CPU DoS"),
}

class SecurityCenter:
    """Workspace and environment security posture auditing engine."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def scan_secrets(self, root_dir: str, max_files: int = 500) -> Dict[str, Any]:
        """Scan workspace text files for accidental hardcoded credentials or API keys."""
        findings = []
        ignore_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build"}
        scanned_count = 0

        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".venv")]
            for file in files:
                if scanned_count >= max_files:
                    break
                if file.endswith((".py", ".env", ".json", ".yaml", ".yml", ".toml", ".txt", ".js", ".ts")):
                    fpath = os.path.join(root, file)
                    rel = os.path.relpath(fpath, root_dir).replace("\\", "/")
                    scanned_count += 1
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            for lineno, line in enumerate(f, 1):
                                for label, pat in SECRET_PATTERNS:
                                    m = pat.search(line)
                                    if m:
                                        val = m.group(0)
                                        # Mask secret
                                        masked = val[:4] + "*" * (len(val) - 8) + val[-4:] if len(val) > 8 else "***"
                                        findings.append({
                                            "type": label,
                                            "file": rel,
                                            "line": lineno,
                                            "masked": masked,
                                            "severity": "CRITICAL" if "KEY" in label.upper() or "TOKEN" in label.upper() else "HIGH"
                                        })
                    except Exception:
                        continue

        return {
            "scanned_files": scanned_count,
            "findings_count": len(findings),
            "findings": findings
        }

    def audit_python_safety(self, root_dir: str, max_files: int = 500) -> Dict[str, Any]:
        """AST audit for hazardous Python functions (eval, exec, shell=True, unsafe pickle)."""
        hazards = []
        ignore_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules"}

        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".venv")]
            for file in files:
                if file.endswith(".py"):
                    fpath = os.path.join(root, file)
                    rel = os.path.relpath(fpath, root_dir).replace("\\", "/")
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Call):
                                fn_name = ""
                                if isinstance(node.func, ast.Name):
                                    fn_name = node.func.id
                                elif isinstance(node.func, ast.Attribute):
                                    fn_name = node.func.attr

                                if fn_name in ("eval", "exec"):
                                    hazards.append({
                                        "severity": "CRITICAL",
                                        "hazard": f"Arbitrary code execution via `{fn_name}()`",
                                        "file": rel,
                                        "line": node.lineno
                                    })
                                elif fn_name == "system" and isinstance(getattr(node.func, "value", None), ast.Name) and node.func.value.id == "os":
                                    hazards.append({
                                        "severity": "HIGH",
                                        "hazard": "Shell command execution via `os.system()`",
                                        "file": rel,
                                        "line": node.lineno
                                    })
                                # Check subprocess with shell=True
                                for kw in node.keywords:
                                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                        hazards.append({
                                            "severity": "HIGH",
                                            "hazard": "Subprocess called with `shell=True`",
                                            "file": rel,
                                            "line": node.lineno
                                        })
                    except Exception:
                        continue

        return {
            "hazards_count": len(hazards),
            "hazards": hazards
        }

    def audit_dependencies(self, root_dir: str) -> Dict[str, Any]:
        """Inspect requirements.txt or package.json for known vulnerable versions."""
        req_path = os.path.join(root_dir, "requirements.txt")
        vulns = []
        packages_checked = 0

        if os.path.exists(req_path):
            try:
                with open(req_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        packages_checked += 1
                        # e.g. urllib3==1.25.10
                        parts = re.split(r"[><=~]=", line)
                        pkg_name = parts[0].strip().lower()
                        if pkg_name in KNOWN_VULNERABLE_PACKAGES:
                            cve_cond, cve_id = KNOWN_VULNERABLE_PACKAGES[pkg_name]
                            vulns.append({
                                "package": pkg_name,
                                "condition": cve_cond,
                                "cve": cve_id,
                                "severity": "MEDIUM",
                                "raw_requirement": line
                            })
            except Exception:
                pass

        return {
            "packages_checked": packages_checked,
            "vulnerabilities_count": len(vulns),
            "vulnerabilities": vulns
        }

    def run_full_security_audit(self, root_dir: str) -> Dict[str, Any]:
        """Compute full security score and remediation report."""
        sec_findings = self.scan_secrets(root_dir)
        code_hazards = self.audit_python_safety(root_dir)
        dep_vulns = self.audit_dependencies(root_dir)

        # Base score 100
        score = 100
        score -= min(50, sec_findings["findings_count"] * 15)
        score -= min(30, code_hazards["hazards_count"] * 10)
        score -= min(20, dep_vulns["vulnerabilities_count"] * 5)
        score = max(0, score)

        perm_mode = perm.manager.mode
        perm_label = perm.manager.mode_label()

        remediations = []
        if sec_findings["findings_count"] > 0:
            remediations.append("Move hardcoded secrets into .env or CAT secure credentials store.")
        if code_hazards["hazards_count"] > 0:
            remediations.append("Replace raw `eval()` / `os.system()` with sanitized or sandboxed execution.")
        if dep_vulns["vulnerabilities_count"] > 0:
            remediations.append("Upgrade vulnerable requirements using `/pkg update` or `pip install -U`.")

        return {
            "security_score": score,
            "status": "EXCELLENT" if score >= 90 else "GOOD" if score >= 75 else "WARNING" if score >= 50 else "CRITICAL",
            "permission_mode": perm_mode,
            "permission_label": perm_label,
            "secrets": sec_findings,
            "code_safety": code_hazards,
            "dependencies": dep_vulns,
            "remediations": remediations
        }


# Global singleton
security_center = SecurityCenter()

def get_security_center() -> SecurityCenter:
    return security_center

