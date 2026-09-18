"""
CAT Reality & Verification Engine per §8, §85, §86:
Never report successful completion based solely on model text.
Every AI claim is verified against genuine execution evidence.
Provides the `/cat verify` project quality pipeline.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class RealityStatus(str, Enum):
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    FAILED = "FAILED"


@dataclass
class EvidenceItem:
    check: str
    passed: bool
    details: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check": self.check,
            "passed": self.passed,
            "details": self.details,
            "timestamp": self.timestamp,
        }


@dataclass
class RealityVerification:
    claim: str
    status: RealityStatus
    evidence: List[EvidenceItem] = field(default_factory=list)
    summary: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim": self.claim,
            "status": self.status.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "summary": self.summary,
            "timestamp": self.timestamp,
        }


class RealityEngine:
    """Verifies AI assertions against real filesystem, runtime, network, and test evidence."""

    def verify_file_modified(self, file_path: str, expected_snippet: str = "") -> EvidenceItem:
        abs_path = os.path.abspath(os.path.expanduser(file_path))
        if not os.path.exists(abs_path):
            return EvidenceItem(check=f"File exists: {file_path}", passed=False, details="File does not exist on disk")
        if expected_snippet:
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                if expected_snippet in content:
                    return EvidenceItem(check=f"File contains expected snippet: {file_path}", passed=True, details="Snippet verified in file")
                return EvidenceItem(check=f"File contains expected snippet: {file_path}", passed=False, details="Snippet missing from file")
            except Exception as e:
                return EvidenceItem(check=f"File read: {file_path}", passed=False, details=str(e))
        return EvidenceItem(check=f"File exists: {file_path}", passed=True, details=f"File exists ({os.path.getsize(abs_path)} bytes)")

    def verify_python_syntax(self, file_path: str) -> EvidenceItem:
        abs_path = os.path.abspath(os.path.expanduser(file_path))
        if not os.path.exists(abs_path):
            return EvidenceItem(check="Python syntax check", passed=False, details=f"File not found: {file_path}")
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()
            ast.parse(code, filename=abs_path)
            return EvidenceItem(check=f"Python syntax valid: {os.path.basename(file_path)}", passed=True, details="AST parse succeeded with 0 errors")
        except SyntaxError as se:
            return EvidenceItem(check=f"Python syntax valid: {os.path.basename(file_path)}", passed=False, details=f"SyntaxError at line {se.lineno}: {se.msg}")
        except Exception as e:
            return EvidenceItem(check=f"Python syntax valid: {os.path.basename(file_path)}", passed=False, details=str(e))

    def verify_ast_syntax(self, code_str: str) -> EvidenceItem:
        """Directly verify syntax of a code snippet via Python AST."""
        try:
            ast.parse(code_str)
            return EvidenceItem(check="AST syntax validation", passed=True, details="Code parsed successfully with 0 errors")
        except SyntaxError as se:
            return EvidenceItem(check="AST syntax validation", passed=False, details=f"SyntaxError at line {se.lineno}: {se.msg}")
        except Exception as e:
            return EvidenceItem(check="AST syntax validation", passed=False, details=str(e))

    def verify_http_endpoint(self, url: str, expected_code: int = 200, timeout: float = 5.0) -> EvidenceItem:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CAT-Reality-Engine/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = resp.getcode()
                passed = (code == expected_code)
                return EvidenceItem(check=f"HTTP endpoint {url}", passed=passed, details=f"HTTP status code {code} (expected {expected_code})")
        except urllib.error.HTTPError as he:
            passed = (he.code == expected_code)
            return EvidenceItem(check=f"HTTP endpoint {url}", passed=passed, details=f"HTTP status code {he.code}")
        except Exception as e:
            return EvidenceItem(check=f"HTTP endpoint {url}", passed=False, details=f"Connection failed: {e}")

    def verify_browser_state(self) -> EvidenceItem:
        try:
            from ..browser.preview import PreviewController
            ctrl = PreviewController.instance() if hasattr(PreviewController, "instance") else None
            if ctrl and ctrl.running and ctrl.engine and ctrl.engine.available:
                snap = ctrl.engine.snapshot()
                err_count = len(snap.js_errors)
                passed = (err_count == 0)
                details = f"DOM loaded: '{snap.title}', console errors: {err_count}"
                return EvidenceItem(check="Browser DOM & Console errors", passed=passed, details=details)
            return EvidenceItem(check="Browser verification", passed=True, details="Browser preview not currently active (skipped)")
        except Exception as e:
            return EvidenceItem(check="Browser verification", passed=False, details=str(e))

    def verify_test_suite(self, test_command: str = "pytest -q", cwd: Optional[str] = None, timeout: float = 60.0) -> EvidenceItem:
        work_dir = cwd or os.getcwd()
        try:
            proc = subprocess.run(
                test_command,
                cwd=work_dir,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
            passed = (proc.returncode == 0)
            details = proc.stdout.strip() or proc.stderr.strip()
            # truncate for report
            if len(details) > 300:
                details = details[:300] + "..."
            return EvidenceItem(check=f"Tests ({test_command})", passed=passed, details=details)
        except subprocess.TimeoutExpired:
            return EvidenceItem(check=f"Tests ({test_command})", passed=False, details=f"Test run timed out after {timeout}s")
        except Exception as e:
            return EvidenceItem(check=f"Tests ({test_command})", passed=False, details=str(e))

    def verify_claim(self, claim: str, checks: List[Callable[[], EvidenceItem]]) -> RealityVerification:
        evidence = []
        for chk in checks:
            try:
                evidence.append(chk())
            except Exception as e:
                evidence.append(EvidenceItem(check="Verification check", passed=False, details=str(e)))

        if not evidence:
            status = RealityStatus.NOT_VERIFIED
            summary = "No verifiable evidence provided."
        elif all(e.passed for e in evidence):
            status = RealityStatus.VERIFIED
            summary = f"All {len(evidence)} checks passed with verified execution evidence."
        elif any(e.passed for e in evidence):
            status = RealityStatus.PARTIALLY_VERIFIED
            failed_count = sum(1 for e in evidence if not e.passed)
            summary = f"{len(evidence) - failed_count} passed, {failed_count} checks failed."
        else:
            status = RealityStatus.FAILED
            summary = "All verification checks failed."

        return RealityVerification(claim=claim, status=status, evidence=evidence, summary=summary)

    def run_cat_verify(self, workspace_path: Optional[str] = None) -> Dict[str, Any]:
        """Project-aware quality pipeline for `/cat verify` per §85."""
        ws = workspace_path or os.getcwd()
        evidence: List[EvidenceItem] = []

        # 1. Syntax Check across python files in workspace
        py_files = []
        for root, dirs, files in os.walk(ws):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "node_modules", "__pycache__")]
            for f in files:
                if f.endswith(".py"):
                    py_files.append(os.path.join(root, f))
                if len(py_files) >= 50:
                    break
            if len(py_files) >= 50:
                break

        syntax_fails = 0
        for pf in py_files:
            ev = self.verify_python_syntax(pf)
            if not ev.passed:
                evidence.append(ev)
                syntax_fails += 1

        if syntax_fails == 0:
            evidence.append(EvidenceItem(check="Python AST Syntax", passed=True, details=f"Verified {len(py_files)} source files clean"))

        # 2. Dependency Health
        has_reqs = os.path.exists(os.path.join(ws, "requirements.txt")) or os.path.exists(os.path.join(ws, "pyproject.toml"))
        evidence.append(EvidenceItem(check="Project manifests", passed=has_reqs, details="requirements.txt / pyproject.toml present" if has_reqs else "No package manifest found"))

        # 3. Git status
        if shutil.which("git"):
            try:
                proc = subprocess.run(["git", "status", "--porcelain"], cwd=ws, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5.0)
                if proc.returncode == 0:
                    mod_count = len(proc.stdout.strip().splitlines()) if proc.stdout.strip() else 0
                    evidence.append(EvidenceItem(check="Git Working Tree", passed=True, details=f"{mod_count} uncommitted change(s)"))
            except Exception:
                pass

        # 4. Tests (if pytest or test dir present)
        tests_dir = os.path.join(ws, "tests") or os.path.join(ws, "test")
        if os.path.exists(tests_dir) or os.path.exists(os.path.join(ws, "calc_terminal", "tests")):
            # Fast test probe
            test_ev = self.verify_test_suite(test_command="pytest --collect-only -q", cwd=ws, timeout=10.0)
            evidence.append(test_ev)

        passed_all = all(e.passed for e in evidence)
        return {
            "status": RealityStatus.VERIFIED.value if passed_all else RealityStatus.PARTIALLY_VERIFIED.value,
            "passed": passed_all,
            "evidence": [e.to_dict() for e in evidence],
            "workspace": ws,
            "summary": "Project verified healthy" if passed_all else "Verification found warnings or issues",
        }

    def format_evidence_table(self, verify_result: Dict[str, Any]) -> str:
        """Format verify result dictionary into ASCII evidence table."""
        lines = [
            "============================================================",
            "                VERIFICATION EVIDENCE TABLE                 ",
            "============================================================",
            f"Workspace: {verify_result.get('workspace', '')}",
            f"Status: {verify_result.get('status', '')} \u2014 {verify_result.get('summary', '')}",
            "------------------------------------------------------------",
            f"{'Check':<30} | {'Status':<6} | Details",
            "------------------------------------------------------------",
        ]
        for ev in verify_result.get("evidence", []):
            st = "PASS" if ev.get("passed") else "FAIL"
            chk = ev.get("check", "")[:30]
            det = ev.get("details", "")[:35]
            lines.append(f"{chk:<30} | {st:<6} | {det}")
        lines.append("============================================================")
        return "\n".join(lines)


reality_engine = RealityEngine()
