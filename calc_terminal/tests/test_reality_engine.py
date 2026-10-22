"""
Tests for Reality / Verification Engine per §8, §85, §86.
"""

import os
import pytest
from calc_terminal.core.verification import reality_engine, RealityStatus, EvidenceItem


class TestRealityEngine:
    def test_verify_file_modified_success(self, tmp_path):
        f = tmp_path / "hello.py"
        f.write_text("def hello(): return 'world'\n", encoding="utf-8")

        ev = reality_engine.verify_file_modified(str(f), expected_snippet="def hello()")
        assert ev.passed is True
        assert "verified" in ev.details.lower()

    def test_verify_file_modified_missing_snippet(self, tmp_path):
        f = tmp_path / "hello.py"
        f.write_text("x = 42\n", encoding="utf-8")

        ev = reality_engine.verify_file_modified(str(f), expected_snippet="def non_existent()")
        assert ev.passed is False
        assert "missing" in ev.details.lower()

    def test_verify_python_syntax_valid(self, tmp_path):
        f = tmp_path / "valid.py"
        f.write_text("import sys\n\ndef add(a, b):\n    return a + b\n", encoding="utf-8")

        ev = reality_engine.verify_python_syntax(str(f))
        assert ev.passed is True
        assert "AST parse succeeded" in ev.details

    def test_verify_python_syntax_invalid(self, tmp_path):
        f = tmp_path / "invalid.py"
        f.write_text("def broken_syntax(\n", encoding="utf-8")

        ev = reality_engine.verify_python_syntax(str(f))
        assert ev.passed is False
        assert "SyntaxError" in ev.details

    def test_verify_claim_multi_check(self, tmp_path):
        f = tmp_path / "app.py"
        f.write_text("print('server started')\n", encoding="utf-8")

        ver = reality_engine.verify_claim(
            claim="Added server entry point and valid syntax",
            checks=[
                lambda: reality_engine.verify_file_modified(str(f), expected_snippet="server started"),
                lambda: reality_engine.verify_python_syntax(str(f)),
            ]
        )
        assert ver.status == RealityStatus.VERIFIED
        assert len(ver.evidence) == 2
        assert all(e.passed for e in ver.evidence)

    def test_run_cat_verify_pipeline(self, tmp_path):
        # Create small test project
        f = tmp_path / "main.py"
        f.write_text("print('healthy')\n", encoding="utf-8")
        req = tmp_path / "requirements.txt"
        req.write_text("rich\n", encoding="utf-8")

        rep = reality_engine.run_cat_verify(str(tmp_path))
        assert "status" in rep
        assert "evidence" in rep
        assert rep["passed"] is True
