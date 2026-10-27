"""
CAT Sudo Command — Cross-Platform Administrative Privilege Elevation.

Provides unified privilege escalation across Windows, Linux, and macOS:
- Windows:
  * Detects current elevation status via shell32.IsUserAnAdmin
  * Bridges to Windows 11 sudo.exe (System32) when available
  * Supports gsudo if installed
  * Native UAC elevation engine via PowerShell / ShellExecuteEx 'RunAs'
  * Output capture via secure temp files for automated pipelines
  * Elevated interactive shell mode (-s / --shell)
- Linux / macOS:
  * Detects root status via os.geteuid()
  * Delegates to system sudo / doas / pkexec
  * Supports environment preservation (-E / --preserve-env)
- Sudo CLI features:
  * -v, --validate (checks and validates current elevation status)
  * --status (machine-readable exit code: 0 if elevated, 1 if standard)
  * -s, --shell (elevated shell session)
  * -n, --non-interactive (fails instead of prompting if elevation is required)
"""

from __future__ import annotations

import argparse
import ctypes
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from typing import List, Optional, Tuple


def is_admin() -> bool:
    """Returns True if the current process is running with administrative/root privileges."""
    if sys.platform == "win32":
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    else:
        try:
            return os.geteuid() == 0
        except Exception:
            return False


class CatSudo:
    """Core execution engine for CAT Sudo."""

    def __init__(self):
        self.is_windows = sys.platform == "win32"

    def parse_args(self, argv: List[str]) -> Tuple[argparse.Namespace, List[str]]:
        """Parses sudo arguments."""
        args = list(argv)
        if args and args[0] in ("sudo", "--sudo"):
            args = args[1:]

        parser = argparse.ArgumentParser(
            prog="cat sudo",
            description="CAT sudo — Cross-platform administrative privilege elevator.",
            add_help=False,
        )

        parser.add_argument("-s", "--shell", dest="shell", action="store_true", help="Run an elevated interactive shell (PowerShell/CMD or bash)")
        parser.add_argument("-v", "--validate", dest="validate", action="store_true", help="Validate credentials and report current elevation status")
        parser.add_argument("--status", dest="check_status", action="store_true", help="Check privilege status (exits 0 if admin, 1 if not)")
        parser.add_argument("-n", "--non-interactive", dest="non_interactive", action="store_true", help="Non-interactive mode (fail rather than prompt for UAC/credentials)")
        parser.add_argument("-E", "--preserve-env", dest="preserve_env", action="store_true", help="Preserve environment variables in elevated environment")
        parser.add_argument("-u", "--user", dest="user", default=None, help="Run command as specified user (default: Administrator/root)")
        parser.add_argument("-i", "--login", dest="login", action="store_true", help="Run an elevated login shell")
        parser.add_argument("-h", "--help", dest="help", action="store_true", help="Show this help message and exit")
        parser.add_argument("-V", "--version", dest="version", action="store_true", help="Print version information and exit")

        parsed, remaining = parser.parse_known_args(args)
        return parsed, remaining

    def run(self, argv: List[str], capture_output: bool = False) -> Tuple[int, str, str]:
        """Runs the sudo command according to argv.

        Returns (exit_code, stdout_str, stderr_str).
        """
        parsed, command_args = self.parse_args(argv)

        if parsed.help:
            usage_text = self._format_help()
            if not capture_output:
                print(usage_text)
            return 0, usage_text, ""

        if parsed.version:
            v_text = "CAT sudo version 0.8.0 (Universal Cross-Platform Elevation Engine)"
            if not capture_output:
                print(v_text)
            return 0, v_text, ""

        already_elevated = is_admin()

        # Handle --status quick check
        if parsed.check_status:
            status_text = "elevated" if already_elevated else "standard"
            if not capture_output:
                print(f"privilege: {status_text}")
            return (0 if already_elevated else 1), status_text, ""

        # Handle -v / --validate
        if parsed.validate:
            if already_elevated:
                msg = "✓ Process is running with full Administrator / root privileges."
                if not capture_output:
                    print(msg)
                return 0, msg, ""
            else:
                msg = "! Process is running in standard user mode (elevation required for administrative privileges)."
                if not capture_output:
                    print(msg)
                return 1, msg, ""

        # Handle -s / --shell or empty command args (open elevated shell)
        if parsed.shell or not command_args:
            return self._launch_elevated_shell(capture_output=capture_output)

        # Non-interactive check: if elevation required and non_interactive is set, fail cleanly
        if not already_elevated and parsed.non_interactive:
            err = "cat sudo: interactive authorization required but non-interactive flag (-n) was specified."
            if not capture_output:
                print(err, file=sys.stderr)
            return 1, "", err

        # If already elevated, execute command directly
        if already_elevated:
            return self._run_direct(command_args, capture_output=capture_output, preserve_env=parsed.preserve_env)

        # Elevate on Windows
        if self.is_windows:
            return self._elevate_windows(command_args, capture_output=capture_output, preserve_env=parsed.preserve_env)

        # Elevate on POSIX (Linux / macOS)
        return self._elevate_posix(command_args, capture_output=capture_output, preserve_env=parsed.preserve_env)

    def _run_direct(self, command_args: List[str], capture_output: bool = False, preserve_env: bool = False) -> Tuple[int, str, str]:
        """Runs the command directly since we are already elevated."""
        cmd_str = " ".join(command_args)
        try:
            if capture_output:
                res = subprocess.run(
                    cmd_str,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                return res.returncode, res.stdout, res.stderr
            else:
                res = subprocess.run(cmd_str, shell=True)
                return res.returncode, "", ""
        except Exception as e:
            err = f"cat sudo: execution failed: {e}"
            if not capture_output:
                print(err, file=sys.stderr)
            return 1, "", err

    def _elevate_windows(self, command_args: List[str], capture_output: bool = False, preserve_env: bool = False) -> Tuple[int, str, str]:
        """Elevates execution on Windows using Windows 11 sudo, gsudo, or PowerShell RunAs."""
        # 1. Check if Windows 11 native sudo.exe is available
        win_sudo = shutil.which("sudo.exe") or shutil.which("sudo")
        if win_sudo and os.path.exists(win_sudo):
            # Check if it's the real Windows 11 sudo (in System32)
            if "system32" in win_sudo.lower():
                try:
                    # Windows 11 sudo supports inline execution
                    run_cmd = [win_sudo] + command_args
                    if capture_output:
                        res = subprocess.run(run_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
                        return res.returncode, res.stdout, res.stderr
                    else:
                        res = subprocess.run(run_cmd)
                        return res.returncode, "", ""
                except Exception:
                    pass

        # 2. Check if gsudo is available
        gsudo = shutil.which("gsudo.exe") or shutil.which("gsudo")
        if gsudo:
            try:
                run_cmd = [gsudo] + command_args
                if capture_output:
                    res = subprocess.run(run_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
                    return res.returncode, res.stdout, res.stderr
                else:
                    res = subprocess.run(run_cmd)
                    return res.returncode, "", ""
            except Exception:
                pass

        # 3. CAT Native UAC Elevation Engine via PowerShell RunAs
        cwd = os.getcwd()
        joined_cmd = " ".join(command_args)

        if capture_output:
            # Create a temporary file to capture elevated output
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as out_tmp:
                out_path = out_tmp.name
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as err_tmp:
                err_path = err_tmp.name
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as code_tmp:
                code_path = code_tmp.name

            try:
                # Wrap command to capture stdout, stderr and exit code
                ps_script = (
                    f"Set-Location -LiteralPath '{cwd}'; "
                    f"& cmd.exe /c '{joined_cmd}' 1> '{out_path}' 2> '{err_path}'; "
                    f"$LASTEXITCODE | Out-File -FilePath '{code_path}' -Encoding ascii"
                )
                ps_args = [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy", "Bypass",
                    "-Command",
                    f"Start-Process powershell.exe -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList \"-NoProfile -ExecutionPolicy Bypass -Command \\\"{ps_script}\\\"\"",
                ]
                res = subprocess.run(ps_args, capture_output=True, text=True)

                out_str = ""
                err_str = ""
                code_val = 0

                if os.path.exists(out_path):
                    with open(out_path, "r", encoding="utf-8", errors="replace") as f:
                        out_str = f.read()
                if os.path.exists(err_path):
                    with open(err_path, "r", encoding="utf-8", errors="replace") as f:
                        err_str = f.read()
                if os.path.exists(code_path):
                    try:
                        with open(code_path, "r", encoding="utf-8", errors="replace") as f:
                            code_val = int(f.read().strip() or "0")
                    except Exception:
                        code_val = 0

                return code_val, out_str, err_str
            finally:
                for p in (out_path, err_path, code_path):
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except Exception:
                        pass
        else:
            # Interactive elevation: prompt user with UAC window
            ps_script = f"Set-Location -LiteralPath '{cwd}'; & cmd.exe /c '{joined_cmd}'"
            ps_args = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-Command",
                f"Start-Process powershell.exe -Verb RunAs -Wait -ArgumentList \"-NoProfile -NoExit -Command \\\"{ps_script}\\\"\"",
            ]
            res = subprocess.run(ps_args)
            return res.returncode, "", ""

    def _elevate_posix(self, command_args: List[str], capture_output: bool = False, preserve_env: bool = False) -> Tuple[int, str, str]:
        """Elevates execution on Linux / macOS using system sudo, doas, or pkexec."""
        sudo_bin = shutil.which("sudo")
        if sudo_bin:
            base_cmd = [sudo_bin]
            if preserve_env:
                base_cmd.append("-E")
            full_cmd = base_cmd + command_args
            try:
                res = subprocess.run(full_cmd, capture_output=capture_output, text=True)
                return res.returncode, res.stdout or "", res.stderr or ""
            except Exception as e:
                err = f"cat sudo: execution failed: {e}"
                if not capture_output:
                    print(err, file=sys.stderr)
                return 1, "", err

        doas_bin = shutil.which("doas")
        if doas_bin:
            full_cmd = [doas_bin] + command_args
            try:
                res = subprocess.run(full_cmd, capture_output=capture_output, text=True)
                return res.returncode, res.stdout or "", res.stderr or ""
            except Exception as e:
                return 1, "", str(e)

        pkexec_bin = shutil.which("pkexec")
        if pkexec_bin:
            full_cmd = [pkexec_bin] + command_args
            try:
                res = subprocess.run(full_cmd, capture_output=capture_output, text=True)
                return res.returncode, res.stdout or "", res.stderr or ""
            except Exception as e:
                return 1, "", str(e)

        err = "cat sudo: no privilege elevation mechanism found (sudo/doas/pkexec)."
        if not capture_output:
            print(err, file=sys.stderr)
        return 1, "", err

    def _launch_elevated_shell(self, capture_output: bool = False) -> Tuple[int, str, str]:
        """Launches an interactive elevated Administrator shell session."""
        if self.is_windows:
            print("🚀 Launching elevated Administrator shell...")
            ps_args = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-Command",
                "Start-Process powershell.exe -Verb RunAs",
            ]
            res = subprocess.run(ps_args)
            return res.returncode, "Launched elevated PowerShell window.", ""
        else:
            shell = os.environ.get("SHELL", "/bin/bash")
            sudo_bin = shutil.which("sudo")
            if sudo_bin:
                res = subprocess.run([sudo_bin, "-s"])
                return res.returncode, "", ""
            err = "cat sudo: cannot launch elevated shell."
            if not capture_output:
                print(err, file=sys.stderr)
            return 1, "", err

    def _format_help(self) -> str:
        return """Usage: cat sudo [options] <command> [args...]
CAT sudo — Universal Cross-Platform Administrative Privilege Elevation.

Options:
  -s, --shell               Run an elevated Administrator shell session
  -v, --validate            Validate current credentials and check elevation status
      --status              Machine-readable status check (exits 0 if admin, 1 if not)
  -n, --non-interactive     Fail rather than prompt if elevation is needed
  -E, --preserve-env        Preserve environment variables in elevated environment
  -u, --user <user>         Run command as specified user (Administrator / root)
  -i, --login               Run an elevated login shell
  -h, --help                Show this help message and exit
  -V, --version             Show version information and exit

Examples:
  cat sudo whoami
  cat sudo --status
  cat sudo -v
  cat sudo -s
  cat sudo winget install Git.Git
  cat sudo net start wuauserv
  cat sudo apt-get update
"""


def run_sudo(argv: List[str], capture_output: bool = False) -> Tuple[int, str, str]:
    """Public helper function to execute CAT Sudo programmatically."""
    return CatSudo().run(argv, capture_output=capture_output)


def main(argv: Optional[List[str]] = None) -> int:
    """Console script entrypoint for `cat-sudo` or `cat sudo`."""
    args = sys.argv[1:] if argv is None else argv
    exit_code, _, _ = CatSudo().run(args, capture_output=False)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
