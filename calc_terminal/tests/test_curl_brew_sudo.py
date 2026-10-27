"""
test_curl_brew_sudo.py — Comprehensive Unit Tests for CAT Curl, Brew, and Sudo.

Verifies:
1. CatCurl command parsing, methods, headers, JSON data, and execution.
2. CatBrew formula registry, doctor audit, search, info, list, and cellar management.
3. CatSudo privilege detection, validation, non-interactive mode, and command dispatch.
4. CAT CLI integration, get_command_safety contract, and command palette entries.
"""

import io
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from calc_terminal.cli import (
    SAFETY_READ_ONLY,
    SAFETY_STATE_CHANGING,
    get_command_safety,
    main as cat_cli_main,
)
from calc_terminal.commands.curl_cmd import CatCurl, run_curl
from calc_terminal.commands.brew_cmd import CatBrew, FORMULA_REGISTRY, run_brew
from calc_terminal.commands.sudo_cmd import CatSudo, is_admin, run_sudo
from calc_terminal.commands_data import COMMANDS, NATIVE_UI_COMMANDS
from calc_terminal.commands_registry import BUILTIN_COMMANDS


class TestCatCurl(unittest.TestCase):
    """Unit tests for CAT Curl."""

    def setUp(self):
        self.curl = CatCurl()

    def test_help_and_version(self):
        code, out, _ = self.curl.run(["curl", "--help"], capture_output=True)
        self.assertEqual(code, 0)
        self.assertIn("Usage: cat curl", out)

        code, out, _ = self.curl.run(["curl", "--version"], capture_output=True)
        self.assertEqual(code, 0)
        self.assertIn("CAT curl", out)

    def test_missing_url(self):
        code, _, err = self.curl.run(["curl"], capture_output=True)
        self.assertEqual(code, 2)
        self.assertIn("no URL specified", err)

    def test_argument_parsing(self):
        args, _ = self.curl.parse_args([
            "curl", "-X", "POST",
            "-H", "Authorization: Bearer test1234",
            "-H", "X-Custom: header",
            "--json", '{"name": "CAT"}',
            "https://example.com/api"
        ])
        self.assertEqual(args.method, "POST")
        self.assertEqual(len(args.headers), 2)
        self.assertEqual(args.json_data, '{"name": "CAT"}')
        self.assertEqual(args.url, "https://example.com/api")

    @patch("urllib.request.build_opener")
    def test_mock_get_request(self, mock_opener_builder):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.getcode.return_value = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.read.return_value = b'{"status": "ok"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_resp
        mock_opener_builder.return_value = mock_opener

        code, out, _ = self.curl.run(["curl", "https://httpbin.org/get"], capture_output=True)
        self.assertEqual(code, 0)
        self.assertIn('"status": "ok"', out)

    @patch("urllib.request.build_opener")
    def test_include_headers(self, mock_opener_builder):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.getcode.return_value = 200
        mock_resp.headers = {"Content-Type": "text/plain", "Server": "CAT"}
        mock_resp.read.return_value = b"Hello World"
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_resp
        mock_opener_builder.return_value = mock_opener

        code, out, _ = self.curl.run(["curl", "-i", "https://example.com"], capture_output=True)
        self.assertEqual(code, 0)
        self.assertIn("HTTP/1.1 200", out)
        self.assertIn("Server: CAT", out)
        self.assertIn("Hello World", out)


class TestCatBrew(unittest.TestCase):
    """Unit tests for CAT Brew."""

    def setUp(self):
        self.brew = CatBrew()

    def test_help_and_version(self):
        code, out, _ = self.brew.run(["brew", "--help"], capture_output=True)
        self.assertEqual(code, 0)
        self.assertIn("Usage: cat brew", out)

        code, out, _ = self.brew.run(["brew", "--version"], capture_output=True)
        self.assertEqual(code, 0)
        self.assertIn("CAT Homebrew", out)

    def test_formula_registry(self):
        self.assertIn("node", FORMULA_REGISTRY)
        self.assertIn("python", FORMULA_REGISTRY)
        self.assertIn("git", FORMULA_REGISTRY)
        self.assertIn("ffmpeg", FORMULA_REGISTRY)
        self.assertIn("ripgrep", FORMULA_REGISTRY)
        self.assertEqual(FORMULA_REGISTRY["node"]["winget"], "OpenJS.NodeJS")
        self.assertEqual(FORMULA_REGISTRY["git"]["winget"], "Git.Git")

    def test_doctor(self):
        code, out, _ = self.brew.run(["brew", "doctor"], capture_output=True)
        self.assertEqual(code, 0)
        self.assertIn("CAT HOMEBREW SYSTEM DOCTOR", out)
        self.assertIn("Package Manager Roster:", out)

    def test_search_and_info(self):
        code, out, _ = self.brew.run(["brew", "search", "git"], capture_output=True)
        self.assertEqual(code, 0)
        self.assertIn("git", out)

        code, out, _ = self.brew.run(["brew", "info", "ffmpeg"], capture_output=True)
        self.assertEqual(code, 0)
        self.assertIn("ffmpeg", out)
        self.assertIn("Gyan.FFmpeg", out)

    def test_list_empty_or_detected(self):
        code, out, _ = self.brew.run(["brew", "list"], capture_output=True)
        self.assertEqual(code, 0)
        self.assertIn("Installed Formulae", out)


class TestCatSudo(unittest.TestCase):
    """Unit tests for CAT Sudo."""

    def setUp(self):
        self.sudo = CatSudo()

    def test_help_and_version(self):
        code, out, _ = self.sudo.run(["sudo", "--help"], capture_output=True)
        self.assertEqual(code, 0)
        self.assertIn("Usage: cat sudo", out)

        code, out, _ = self.sudo.run(["sudo", "--version"], capture_output=True)
        self.assertEqual(code, 0)
        self.assertIn("CAT sudo version", out)

    def test_status_check(self):
        code, out, _ = self.sudo.run(["sudo", "--status"], capture_output=True)
        # Returns 0 if elevated, 1 if standard
        self.assertIn(code, (0, 1))
        self.assertIn(out.strip(), ("elevated", "standard"))

    def test_validate(self):
        code, out, err = self.sudo.run(["sudo", "-v"], capture_output=True)
        self.assertIn(code, (0, 1))
        combined = (out + " " + err).lower()
        self.assertTrue("privilege" in combined or "administrator" in combined or "root" in combined)

    def test_non_interactive_rejection_when_not_elevated(self):
        with patch("calc_terminal.commands.sudo_cmd.is_admin", return_value=False):
            code, _, err = self.sudo.run(["sudo", "-n", "whoami"], capture_output=True)
            self.assertEqual(code, 1)
            self.assertIn("non-interactive", err)


class TestCLIIntegration(unittest.TestCase):
    """Integration tests verifying CLI routing, safety contracts, and palettes."""

    def test_cli_curl_help(self):
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            exit_code = cat_cli_main(["curl", "--help"])
            self.assertEqual(exit_code, 0)
            self.assertIn("Usage: cat curl", fake_out.getvalue())

    def test_cli_brew_help(self):
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            exit_code = cat_cli_main(["brew", "--help"])
            self.assertEqual(exit_code, 0)
            self.assertIn("Usage: cat brew", fake_out.getvalue())

    def test_cli_sudo_help(self):
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            exit_code = cat_cli_main(["sudo", "--help"])
            self.assertEqual(exit_code, 0)
            self.assertIn("Usage: cat sudo", fake_out.getvalue())

    def test_command_safety_classifications(self):
        # Curl GET is read-only
        curl_ro = get_command_safety(["curl", "https://api.github.com/zen"])
        self.assertEqual(curl_ro["classification"], SAFETY_READ_ONLY)
        self.assertTrue(curl_ro["safe_to_automate"])

        # Curl POST is state-changing
        curl_sc = get_command_safety(["curl", "-X", "POST", "--json", "{}", "https://example.com"])
        self.assertEqual(curl_sc["classification"], SAFETY_STATE_CHANGING)
        self.assertFalse(curl_sc["safe_to_automate"])

        # Brew list / doctor is read-only
        brew_ro = get_command_safety(["brew", "doctor"])
        self.assertEqual(brew_ro["classification"], SAFETY_READ_ONLY)
        self.assertTrue(brew_ro["safe_to_automate"])

        # Brew install is state-changing
        brew_sc = get_command_safety(["brew", "install", "node"])
        self.assertEqual(brew_sc["classification"], SAFETY_STATE_CHANGING)
        self.assertFalse(brew_sc["safe_to_automate"])

        # Sudo status is read-only
        sudo_ro = get_command_safety(["sudo", "--status"])
        self.assertEqual(sudo_ro["classification"], SAFETY_READ_ONLY)
        self.assertTrue(sudo_ro["safe_to_automate"])

        # Sudo run command is state-changing
        sudo_sc = get_command_safety(["sudo", "apt-get", "update"])
        self.assertEqual(sudo_sc["classification"], SAFETY_STATE_CHANGING)
        self.assertFalse(sudo_sc["safe_to_automate"])

    def test_command_palette_and_builtin_registry(self):
        commands_dict = dict(COMMANDS)
        self.assertIn("/curl", commands_dict)
        self.assertIn("/brew", commands_dict)
        self.assertIn("/sudo", commands_dict)

        self.assertIn("/curl", NATIVE_UI_COMMANDS)
        self.assertIn("/brew", NATIVE_UI_COMMANDS)
        self.assertIn("/sudo", NATIVE_UI_COMMANDS)

        self.assertIn("curl", BUILTIN_COMMANDS)
        self.assertIn("brew", BUILTIN_COMMANDS)
        self.assertIn("sudo", BUILTIN_COMMANDS)


if __name__ == "__main__":
    unittest.main()
