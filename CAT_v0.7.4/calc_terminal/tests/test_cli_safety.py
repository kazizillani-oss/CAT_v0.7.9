"""
test_cli_safety.py — Automated tests for the CAT/CCT CLI command-safety contract.

Verifies:
1. Centralized get_command_safety classifications (read-only, state-changing, interactive).
2. Read-only guarantees for --version, -v, version, --debug, debug, update --check.
3. State-changing classification & non-zero exit for update, rollback, repair.
4. update --check mocked network behavior, zero filesystem mutation, and error resilience.
5. --debug diagnostics format and non-destructive execution.
6. CLI help output documentation of the safety boundary.
"""

import io
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from calc_terminal.cli import (
    SAFETY_READ_ONLY,
    SAFETY_STATE_CHANGING,
    SAFETY_INTERACTIVE,
    get_command_safety,
    _usage,
    _parse_version_tuple,
    main,
)


class TestCLISafetyContract(unittest.TestCase):
    """Test suite for the centralized command-safety contract."""

    # -------------------------------------------------------------------------
    # A. READ-ONLY COMMANDS
    # -------------------------------------------------------------------------
    def test_read_only_commands_classification(self):
        """A: --version, -v, version, --debug, debug, update --check must all report
        classification == 'read-only', safe_to_automate == True, changes_state == False."""
        read_only_cases = [
            ["--version"],
            ["-v"],
            ["version"],
            ["--debug"],
            ["debug"],
            ["update", "--check"],
            ["--help"],
            ["-h"],
            ["help"],
        ]

        for cmd in read_only_cases:
            with self.subTest(cmd=cmd):
                info = get_command_safety(cmd)
                self.assertEqual(
                    info["classification"],
                    SAFETY_READ_ONLY,
                    f"{cmd} must be classified as {SAFETY_READ_ONLY}",
                )
                self.assertIs(
                    info["safe_to_automate"],
                    True,
                    f"{cmd} must be marked safe_to_automate=True",
                )
                self.assertIs(
                    info["changes_state"],
                    False,
                    f"{cmd} must be marked changes_state=False",
                )
                self.assertTrue(
                    isinstance(info["reason"], str) and len(info["reason"]) > 0,
                    f"{cmd} must provide a non-empty rationale string",
                )

    # -------------------------------------------------------------------------
    # B. STATE-CHANGING COMMANDS
    # -------------------------------------------------------------------------
    def test_state_changing_commands_classification(self):
        """B: update, rollback, repair must all report
        classification == 'state-changing', safe_to_automate == False, changes_state == True."""
        state_changing_cases = [
            ["update"],
            ["rollback"],
            ["repair"],
            ["--update"],
            ["--rollback"],
            ["--repair"],
        ]

        for cmd in state_changing_cases:
            with self.subTest(cmd=cmd):
                info = get_command_safety(cmd)
                self.assertEqual(
                    info["classification"],
                    SAFETY_STATE_CHANGING,
                    f"{cmd} must be classified as {SAFETY_STATE_CHANGING}",
                )
                self.assertIs(
                    info["safe_to_automate"],
                    False,
                    f"{cmd} must be marked safe_to_automate=False",
                )
                self.assertIs(
                    info["changes_state"],
                    True,
                    f"{cmd} must be marked changes_state=True",
                )
                self.assertTrue(
                    isinstance(info["reason"], str) and len(info["reason"]) > 0,
                    f"{cmd} must provide a non-empty rationale string",
                )

    # -------------------------------------------------------------------------
    # C. UNKNOWN / INTERACTIVE / WORKSPACE COMMANDS
    # -------------------------------------------------------------------------
    def test_interactive_and_unknown_commands_classification(self):
        """C: [], workspace paths, and unrelated commands must not be marked safe."""
        interactive_cases = [
            [],
            ["."],
            ["my-project"],
            ["/path/to/workspace"],
            ["unknown_subcommand"],
            ["models"],
            ["offline"],
        ]

        for cmd in interactive_cases:
            with self.subTest(cmd=cmd):
                info = get_command_safety(cmd)
                self.assertEqual(
                    info["classification"],
                    SAFETY_INTERACTIVE,
                    f"{cmd} must be classified as {SAFETY_INTERACTIVE}",
                )
                self.assertIs(
                    info["safe_to_automate"],
                    False,
                    f"{cmd} must NOT be marked safe to automate",
                )
                self.assertIsNone(
                    info["changes_state"],
                    f"{cmd} changes_state must be None for interactive/unknown commands",
                )

    # -------------------------------------------------------------------------
    # D. update --check READ-ONLY GUARANTEES & NETWORK ERROR HANDLING
    # -------------------------------------------------------------------------
    def test_update_check_success_zero_filesystem_mutation(self):
        """D1: update --check queries metadata, prints update status, and performs zero file mutations."""
        mock_payload = json.dumps({
            "tag_name": "v0.8.0.0",
            "html_url": "https://github.com/kazizillani-oss/CAT_v0.7.9/releases/tag/v0.8.0.0",
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_payload
        mock_resp.__enter__.return_value = mock_resp

        # Track directory snapshot before execution
        test_dir = os.path.dirname(os.path.abspath(__file__))
        snapshot_before = os.listdir(test_dir)

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen, \
             patch("sys.stdout", stdout_buf), \
             patch("sys.stderr", stderr_buf):
            rc = main(["update", "--check"])

        self.assertEqual(rc, 0)
        out = stdout_buf.getvalue()
        self.assertIn("CAT Release Check (Read-Only)", out)
        self.assertIn("Installed Version", out)
        self.assertIn("Latest Version", out)
        self.assertIn("Update Available  : YES", out)
        self.assertIn("no installation was performed", out)

        # Confirm no file creation or mutation occurred in test directory
        snapshot_after = os.listdir(test_dir)
        self.assertEqual(snapshot_before, snapshot_after)

    def test_update_check_http_error_handling(self):
        """D2: update --check handles HTTP errors with clean exit code 1 and stderr message."""
        mock_err = urllib.error.HTTPError(
            url="https://api.github.com/repos/kazizillani-oss/CAT_v0.7.9/releases/latest",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None,
        )

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch("urllib.request.urlopen", side_effect=mock_err), \
             patch("sys.stdout", stdout_buf), \
             patch("sys.stderr", stderr_buf):
            rc = main(["update", "--check"])

        self.assertEqual(rc, 1)
        err = stderr_buf.getvalue()
        self.assertIn("HTTP error 404", err)

    def test_update_check_network_error_handling(self):
        """D3: update --check handles network connection failures gracefully."""
        mock_err = urllib.error.URLError("Connection refused")

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch("urllib.request.urlopen", side_effect=mock_err), \
             patch("sys.stdout", stdout_buf), \
             patch("sys.stderr", stderr_buf):
            rc = main(["update", "--check"])

        self.assertEqual(rc, 1)
        err = stderr_buf.getvalue()
        self.assertIn("network error: Connection refused", err)

    def test_update_check_malformed_metadata_handling(self):
        """D4: update --check handles non-JSON or invalid responses cleanly."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html>Not JSON</html>"
        mock_resp.__enter__.return_value = mock_resp

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch("urllib.request.urlopen", return_value=mock_resp), \
             patch("sys.stdout", stdout_buf), \
             patch("sys.stderr", stderr_buf):
            rc = main(["update", "--check"])

        self.assertEqual(rc, 1)
        err = stderr_buf.getvalue()
        self.assertIn("malformed release metadata", err)

    def test_update_check_non_semver_handling(self):
        """D5: Version tuple parser rejects empty or invalid non-semver strings."""
        self.assertEqual(_parse_version_tuple("0.7.9.0"), (0, 7, 9, 0))
        self.assertEqual(_parse_version_tuple("v1.2.3"), (1, 2, 3))
        with self.assertRaises(ValueError):
            _parse_version_tuple("invalid-no-digits")

    # -------------------------------------------------------------------------
    # E. --debug / debug READ-ONLY DIAGNOSTICS GUARANTEES
    # -------------------------------------------------------------------------
    def test_debug_is_read_only_and_informative(self):
        """E: --debug must print deterministic diagnostic info and never run installer or repair."""
        stdout_buf = io.StringIO()
        with patch("sys.stdout", stdout_buf):
            rc = main(["--debug"])

        self.assertEqual(rc, 0)
        out = stdout_buf.getvalue()
        self.assertIn("CAT DIAGNOSTIC ENVIRONMENT & RUNTIME", out)
        self.assertIn("Automation Safety : read-only", out)
        self.assertIn("CAT Version", out)
        self.assertIn("Python Version", out)
        self.assertIn("Python Executable", out)
        self.assertIn("Platform", out)
        self.assertIn("Architecture", out)
        self.assertIn("Working Directory", out)
        self.assertIn("Available Scripts : cat (calc_terminal.cli:main), cct (calc_terminal.cli:main)", out)
        self.assertIn("Read-only diagnostics (no files, config, or state modified)", out)

    # -------------------------------------------------------------------------
    # F. STATE-CHANGING DISABLED OPERATION BEHAVIOR
    # -------------------------------------------------------------------------
    def test_state_changing_commands_fail_with_clear_guidance(self):
        """F: update, rollback, repair must return non-zero exit codes with explicit guidance."""
        commands = [
            ("update", "cat update --check"),
            ("rollback", "Automated rollbacks are disabled"),
            ("repair", "cat --doctor"),
        ]

        for cmd, expected_hint in commands:
            with self.subTest(cmd=cmd):
                stderr_buf = io.StringIO()
                with patch("sys.stderr", stderr_buf):
                    rc = main([cmd])

                self.assertEqual(rc, 1, f"Command '{cmd}' must return non-zero exit code")
                err = stderr_buf.getvalue()
                self.assertIn(f"state-changing operation '{cmd}' is not enabled in this public CLI build", err)
                self.assertIn(expected_hint, err)

    # -------------------------------------------------------------------------
    # G. CLI USAGE & AUTOMATION SAFETY HELP DOCUMENTATION
    # -------------------------------------------------------------------------
    def test_cli_help_documents_automation_safety_boundary(self):
        """G: _usage() output must document the Automation safety boundary for both cat and cct."""
        usage_cat = _usage("cat")
        self.assertIn("Automation safety:", usage_cat)
        self.assertIn("Read-only (safe to automate):", usage_cat)
        self.assertIn("cat --version", usage_cat)
        self.assertIn("cat --debug", usage_cat)
        self.assertIn("cat update --check", usage_cat)
        self.assertIn("State-changing (not safe for unattended automation):", usage_cat)
        self.assertIn("cat update", usage_cat)
        self.assertIn("cat rollback", usage_cat)
        self.assertIn("cat repair", usage_cat)

        usage_cct = _usage("cct")
        self.assertIn("cct --version", usage_cct)
        self.assertIn("cct --debug", usage_cct)
        self.assertIn("cct update --check", usage_cct)
        self.assertIn("cct update", usage_cct)
        self.assertIn("cct rollback", usage_cct)
        self.assertIn("cct repair", usage_cct)


if __name__ == "__main__":
    unittest.main()
