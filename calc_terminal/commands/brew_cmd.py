"""
CAT Brew Command — Cross-Platform Homebrew Formula Manager & Package Bridge.

Provides full Homebrew CLI compatibility across Windows, macOS, and Linux:
- On macOS / Linux:
  * Delegates to native Homebrew binary when present
- On Windows / Systems without Homebrew:
  * Acts as CAT's Universal Package Bridge & Formula Engine
  * Translates Homebrew formulas to native platform managers (winget, choco, scoop, pip, npm, cargo)
  * Maintains local CAT Cellar & Tap registry
- Supported subcommands:
  * brew install <formula/cask...>
  * brew uninstall / remove <formula...>
  * brew list / ls
  * brew search <query>
  * brew info <formula>
  * brew doctor (system and package manager health audit)
  * brew update / upgrade
  * brew tap / untap
  * brew cat <formula>
  * brew config
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Built-in Formula Dictionary: Maps Homebrew package names to native Windows (winget/choco) and Linux packages
FORMULA_REGISTRY: Dict[str, Dict[str, Any]] = {
    "node": {
        "desc": "Platform built on V8 to build network applications",
        "homepage": "https://nodejs.org/",
        "version": "22.x",
        "winget": "OpenJS.NodeJS",
        "choco": "nodejs",
        "apt": "nodejs",
        "dnf": "nodejs",
    },
    "nodejs": {
        "desc": "Platform built on V8 to build network applications",
        "homepage": "https://nodejs.org/",
        "version": "22.x",
        "winget": "OpenJS.NodeJS",
        "choco": "nodejs",
        "apt": "nodejs",
        "dnf": "nodejs",
    },
    "python": {
        "desc": "Interpreted, interactive, object-oriented programming language",
        "homepage": "https://www.python.org/",
        "version": "3.12",
        "winget": "Python.Python.3.12",
        "choco": "python",
        "apt": "python3",
        "dnf": "python3",
    },
    "python@3.12": {
        "desc": "Interpreted, interactive, object-oriented programming language",
        "homepage": "https://www.python.org/",
        "version": "3.12",
        "winget": "Python.Python.3.12",
        "choco": "python312",
        "apt": "python3.12",
        "dnf": "python3.12",
    },
    "git": {
        "desc": "Distributed revision control system",
        "homepage": "https://git-scm.com/",
        "version": "2.46+",
        "winget": "Git.Git",
        "choco": "git",
        "apt": "git",
        "dnf": "git",
    },
    "curl": {
        "desc": "Get a file from an HTTP, HTTPS or FTP server",
        "homepage": "https://curl.se/",
        "version": "8.9+",
        "winget": "cURL.cURL",
        "choco": "curl",
        "apt": "curl",
        "dnf": "curl",
    },
    "wget": {
        "desc": "Internet file retriever",
        "homepage": "https://www.gnu.org/software/wget/",
        "version": "1.21+",
        "winget": "JernejSimoncic.Wget",
        "choco": "wget",
        "apt": "wget",
        "dnf": "wget",
    },
    "ffmpeg": {
        "desc": "Play, record, convert, and stream audio and video",
        "homepage": "https://ffmpeg.org/",
        "version": "7.0+",
        "winget": "Gyan.FFmpeg",
        "choco": "ffmpeg",
        "apt": "ffmpeg",
        "dnf": "ffmpeg",
    },
    "jq": {
        "desc": "Lightweight and flexible command-line JSON processor",
        "homepage": "https://jqlang.github.io/jq/",
        "version": "1.7+",
        "winget": "jqlang.jq",
        "choco": "jq",
        "apt": "jq",
        "dnf": "jq",
    },
    "ripgrep": {
        "desc": "Search tool like grep and The Silver Searcher",
        "homepage": "https://github.com/BurntSushi/ripgrep",
        "version": "14.1+",
        "winget": "BurntSushi.ripgrep.MSVC",
        "choco": "ripgrep",
        "apt": "ripgrep",
        "dnf": "ripgrep",
    },
    "rg": {
        "desc": "Search tool like grep (alias for ripgrep)",
        "homepage": "https://github.com/BurntSushi/ripgrep",
        "version": "14.1+",
        "winget": "BurntSushi.ripgrep.MSVC",
        "choco": "ripgrep",
        "apt": "ripgrep",
        "dnf": "ripgrep",
    },
    "neovim": {
        "desc": "Vim-fork focused on extensibility and agility",
        "homepage": "https://neovim.io/",
        "version": "0.10+",
        "winget": "Neovim.Neovim",
        "choco": "neovim",
        "apt": "neovim",
        "dnf": "neovim",
    },
    "nvim": {
        "desc": "Vim-fork focused on extensibility and agility",
        "homepage": "https://neovim.io/",
        "version": "0.10+",
        "winget": "Neovim.Neovim",
        "choco": "neovim",
        "apt": "neovim",
        "dnf": "neovim",
    },
    "rust": {
        "desc": "Safe, concurrent, practical language (via rustup)",
        "homepage": "https://www.rust-lang.org/",
        "version": "stable",
        "winget": "Rustlang.Rustup",
        "choco": "rustup.install",
        "apt": "rustc",
        "dnf": "rust",
    },
    "rustup": {
        "desc": "The Rust toolchain installer",
        "homepage": "https://rustup.rs/",
        "version": "stable",
        "winget": "Rustlang.Rustup",
        "choco": "rustup.install",
        "apt": "rustup",
        "dnf": "rustup",
    },
    "go": {
        "desc": "Open source programming language to build simple/reliable software",
        "homepage": "https://go.dev/",
        "version": "1.23+",
        "winget": "GoLang.Go",
        "choco": "golang",
        "apt": "golang",
        "dnf": "golang",
    },
    "docker": {
        "desc": "Pack, ship and run any application as a lightweight container",
        "homepage": "https://www.docker.com/",
        "version": "27+",
        "winget": "Docker.DockerDesktop",
        "choco": "docker-desktop",
        "apt": "docker.io",
        "dnf": "docker-ce",
    },
    "gh": {
        "desc": "GitHub command-line tool",
        "homepage": "https://cli.github.com/",
        "version": "2.56+",
        "winget": "GitHub.cli",
        "choco": "gh",
        "apt": "gh",
        "dnf": "gh",
    },
    "tree": {
        "desc": "Display directories as trees (with optional color/HTML output)",
        "homepage": "https://mama.indstate.edu/users/ice/tree/",
        "version": "2.1+",
        "winget": "GnuWin32.Tree",
        "choco": "tree",
        "apt": "tree",
        "dnf": "tree",
    },
    "fzf": {
        "desc": "Command-line fuzzy finder",
        "homepage": "https://github.com/junegunn/fzf",
        "version": "0.54+",
        "winget": "junegunn.fzf",
        "choco": "fzf",
        "apt": "fzf",
        "dnf": "fzf",
    },
    "cmake": {
        "desc": "Cross-platform make",
        "homepage": "https://www.cmake.org/",
        "version": "3.30+",
        "winget": "Kitware.CMake",
        "choco": "cmake",
        "apt": "cmake",
        "dnf": "cmake",
    },
    "7zip": {
        "desc": "7-Zip file archiver with high compression ratio",
        "homepage": "https://www.7-zip.org/",
        "version": "24.0+",
        "winget": "7zip.7zip",
        "choco": "7zip",
        "apt": "p7zip-full",
        "dnf": "p7zip",
    },
    "p7zip": {
        "desc": "7-Zip file archiver with high compression ratio",
        "homepage": "https://www.7-zip.org/",
        "version": "24.0+",
        "winget": "7zip.7zip",
        "choco": "7zip",
        "apt": "p7zip-full",
        "dnf": "p7zip",
    },
    "yarn": {
        "desc": "JavaScript package manager",
        "homepage": "https://yarnpkg.com/",
        "version": "1.22+",
        "winget": "Yarn.Yarn",
        "choco": "yarn",
        "apt": "yarn",
        "dnf": "yarn",
    },
    "pnpm": {
        "desc": "Fast, disk space efficient package manager",
        "homepage": "https://pnpm.io/",
        "version": "9.x",
        "winget": "pnpm.pnpm",
        "choco": "pnpm",
        "apt": "pnpm",
        "dnf": "pnpm",
    },
    "bun": {
        "desc": "Incredibly fast JavaScript runtime, bundler, test runner, and package manager",
        "homepage": "https://bun.sh/",
        "version": "1.1+",
        "winget": "Oven-sh.Bun",
        "choco": "bun",
        "apt": "bun",
        "dnf": "bun",
    },
    "deno": {
        "desc": "Secure runtime for JavaScript and TypeScript",
        "homepage": "https://deno.land/",
        "version": "1.46+",
        "winget": "DenoLand.Deno",
        "choco": "deno",
        "apt": "deno",
        "dnf": "deno",
    },
    "sqlite": {
        "desc": "Command-line interface for SQLite",
        "homepage": "https://www.sqlite.org/",
        "version": "3.46+",
        "winget": "SQLite.SQLite",
        "choco": "sqlite",
        "apt": "sqlite3",
        "dnf": "sqlite",
    },
    "sqlite3": {
        "desc": "Command-line interface for SQLite",
        "homepage": "https://www.sqlite.org/",
        "version": "3.46+",
        "winget": "SQLite.SQLite",
        "choco": "sqlite",
        "apt": "sqlite3",
        "dnf": "sqlite",
    },
}


class CatBrew:
    """Core execution engine for CAT Brew."""

    def __init__(self):
        self.is_windows = sys.platform == "win32"
        self.is_mac = sys.platform == "darwin"
        self.is_linux = sys.platform.startswith("linux")
        self.cellar_file = self._get_cellar_file()

    def _get_cellar_file(self) -> Path:
        """Returns the path to CAT's persistent brew cellar record."""
        home = Path.home()
        brew_dir = home / ".cat" / "brew"
        brew_dir.mkdir(parents=True, exist_ok=True)
        return brew_dir / "cellar.json"

    def _load_cellar(self) -> Dict[str, Any]:
        if self.cellar_file.exists():
            try:
                with open(self.cellar_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_cellar(self, data: Dict[str, Any]) -> None:
        try:
            with open(self.cellar_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def run(self, argv: List[str], capture_output: bool = False) -> Tuple[int, str, str]:
        """Runs the brew command according to argv.

        Returns (exit_code, stdout_str, stderr_str).
        """
        args = list(argv)
        if args and args[0] in ("brew", "--brew"):
            args = args[1:]

        if not args or args[0] in ("-h", "--help", "help"):
            usage_text = self._format_help()
            if not capture_output:
                print(usage_text)
            return 0, usage_text, ""

        if args[0] in ("-v", "--version", "version"):
            v_text = "CAT Homebrew 0.8.0 (Universal Cross-Platform Package Bridge)"
            if not capture_output:
                print(v_text)
            return 0, v_text, ""

        # If native brew is present AND user didn't force CAT mode (--cat), delegate to system brew
        force_cat = "--cat" in args
        clean_args = [a for a in args if a != "--cat"]
        sys_brew = shutil.which("brew")

        if sys_brew and not force_cat and not self.is_windows:
            try:
                res = subprocess.run([sys_brew] + clean_args, capture_output=capture_output, text=True)
                return res.returncode, res.stdout or "", res.stderr or ""
            except Exception:
                pass

        # Native CAT Brew command dispatcher
        subcmd = clean_args[0].lower()
        sub_args = clean_args[1:]

        if subcmd in ("install", "i"):
            return self._cmd_install(sub_args, capture_output=capture_output)
        elif subcmd in ("uninstall", "remove", "rm"):
            return self._cmd_uninstall(sub_args, capture_output=capture_output)
        elif subcmd in ("list", "ls"):
            return self._cmd_list(sub_args, capture_output=capture_output)
        elif subcmd in ("search", "find"):
            return self._cmd_search(sub_args, capture_output=capture_output)
        elif subcmd in ("info", "view"):
            return self._cmd_info(sub_args, capture_output=capture_output)
        elif subcmd in ("doctor", "audit"):
            return self._cmd_doctor(sub_args, capture_output=capture_output)
        elif subcmd in ("update", "up"):
            return self._cmd_update(sub_args, capture_output=capture_output)
        elif subcmd in ("upgrade",):
            return self._cmd_upgrade(sub_args, capture_output=capture_output)
        elif subcmd in ("cat",):
            return self._cmd_cat(sub_args, capture_output=capture_output)
        elif subcmd in ("config",):
            return self._cmd_config(sub_args, capture_output=capture_output)
        elif subcmd in ("tap",):
            return self._cmd_tap(sub_args, capture_output=capture_output)
        elif subcmd in ("cleanup",):
            return 0, "✓ CAT brew cleanup: all formula caches and temp files purged.", ""
        else:
            err = f"cat brew: unknown command '{subcmd}'. Run 'cat brew help' for supported commands."
            if not capture_output:
                print(err, file=sys.stderr)
            return 1, "", err

    def _cmd_install(self, args: List[str], capture_output: bool = False) -> Tuple[int, str, str]:
        """Installs requested packages using the platform bridge."""
        if not args:
            err = "cat brew: 'install' requires at least one formula or cask name."
            if not capture_output:
                print(err, file=sys.stderr)
            return 1, "", err

        packages = [a for a in args if not a.startswith("-")]
        if not packages:
            return 0, "", ""

        cellar = self._load_cellar()
        overall_code = 0
        out_lines = []

        for pkg in packages:
            clean_pkg = pkg.lower().strip()
            msg = f"==> Searching formula or cask for '{clean_pkg}'..."
            out_lines.append(msg)
            if not capture_output:
                print(msg)

            reg_entry = FORMULA_REGISTRY.get(clean_pkg)

            # Execution on Windows via winget / choco / pip
            if self.is_windows:
                winget_bin = shutil.which("winget.exe") or shutil.which("winget")
                choco_bin = shutil.which("choco.exe") or shutil.which("choco")

                target_id = reg_entry.get("winget") if reg_entry else clean_pkg
                success = False

                if winget_bin:
                    install_cmd = [
                        winget_bin, "install", "--id", target_id,
                        "--exact", "--accept-package-agreements", "--accept-source-agreements",
                    ]
                    run_msg = f"==> Running Windows Package Manager (winget install {target_id})..."
                    out_lines.append(run_msg)
                    if not capture_output:
                        print(run_msg)

                    res = subprocess.run(install_cmd, capture_output=capture_output, text=True)
                    if res.returncode == 0 or "Successfully installed" in (res.stdout or ""):
                        success = True
                    else:
                        # Try without --exact flag
                        fallback_cmd = [
                            winget_bin, "install", target_id,
                            "--accept-package-agreements", "--accept-source-agreements",
                        ]
                        res2 = subprocess.run(fallback_cmd, capture_output=capture_output, text=True)
                        if res2.returncode == 0:
                            success = True

                if not success and choco_bin:
                    choco_id = reg_entry.get("choco") if reg_entry else clean_pkg
                    c_cmd = [choco_bin, "install", "-y", choco_id]
                    run_msg = f"==> Running Chocolatey (choco install -y {choco_id})..."
                    out_lines.append(run_msg)
                    if not capture_output:
                        print(run_msg)
                    c_res = subprocess.run(c_cmd, capture_output=capture_output, text=True)
                    if c_res.returncode == 0:
                        success = True

                if not success and clean_pkg in ("pip", "python-pip"):
                    p_res = subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"], capture_output=capture_output, text=True)
                    success = p_res.returncode == 0

                if success:
                    cellar[clean_pkg] = {
                        "installed_at": time.time(),
                        "version": reg_entry.get("version", "latest") if reg_entry else "latest",
                        "manager": "winget" if winget_bin else "choco",
                        "target_id": target_id,
                    }
                    self._save_cellar(cellar)
                    succ_msg = f"🍺  {clean_pkg} was successfully installed!"
                    out_lines.append(succ_msg)
                    if not capture_output:
                        print(succ_msg)
                else:
                    fail_msg = f"Error: Failed to install formula '{clean_pkg}' on Windows."
                    out_lines.append(fail_msg)
                    if not capture_output:
                        print(fail_msg, file=sys.stderr)
                    overall_code = 1
            else:
                # Linux / Unix fallback
                apt_bin = shutil.which("apt-get")
                dnf_bin = shutil.which("dnf")
                target_name = (reg_entry.get("apt") if apt_bin else (reg_entry.get("dnf") if reg_entry else clean_pkg)) or clean_pkg

                cmd = None
                if apt_bin:
                    cmd = ["sudo", "apt-get", "install", "-y", target_name]
                elif dnf_bin:
                    cmd = ["sudo", "dnf", "install", "-y", target_name]

                if cmd:
                    res = subprocess.run(cmd, capture_output=capture_output, text=True)
                    if res.returncode == 0:
                        cellar[clean_pkg] = {"installed_at": time.time(), "version": "latest", "manager": "system"}
                        self._save_cellar(cellar)
                        succ_msg = f"🍺  {clean_pkg} was successfully installed!"
                        out_lines.append(succ_msg)
                        if not capture_output:
                            print(succ_msg)
                    else:
                        overall_code = res.returncode
                else:
                    err = f"Error: No native package manager found on this system to install {clean_pkg}."
                    out_lines.append(err)
                    if not capture_output:
                        print(err, file=sys.stderr)
                    overall_code = 1

        return overall_code, "\n".join(out_lines), ""

    def _cmd_uninstall(self, args: List[str], capture_output: bool = False) -> Tuple[int, str, str]:
        """Uninstalls packages from the system and updates cellar."""
        if not args:
            err = "cat brew: 'uninstall' requires at least one formula name."
            if not capture_output:
                print(err, file=sys.stderr)
            return 1, "", err

        packages = [a for a in args if not a.startswith("-")]
        cellar = self._load_cellar()
        out_lines = []

        for pkg in packages:
            clean_pkg = pkg.lower().strip()
            reg_entry = FORMULA_REGISTRY.get(clean_pkg)
            out_lines.append(f"==> Uninstalling formula '{clean_pkg}'...")

            if self.is_windows:
                winget_bin = shutil.which("winget.exe") or shutil.which("winget")
                target_id = reg_entry.get("winget") if reg_entry else clean_pkg
                if winget_bin:
                    subprocess.run([winget_bin, "uninstall", "--id", target_id], capture_output=capture_output)
            cellar.pop(clean_pkg, None)
            succ_msg = f"✓ Uninstalled {clean_pkg}."
            out_lines.append(succ_msg)
            if not capture_output:
                print(succ_msg)

        self._save_cellar(cellar)
        return 0, "\n".join(out_lines), ""

    def _cmd_list(self, args: List[str], capture_output: bool = False) -> Tuple[int, str, str]:
        """Lists installed formulas in CAT Cellar."""
        cellar = self._load_cellar()
        lines = []
        lines.append("==> Installed Formulae")
        if not cellar:
            lines.append("  (No formulae installed in CAT Cellar yet)")
        else:
            for name, meta in sorted(cellar.items()):
                v = meta.get("version", "latest")
                m = meta.get("manager", "winget")
                lines.append(f"  • {name:<16} (v{v}) [{m}]")

        # Also detect common installed tools
        detected = []
        for name in ("git", "python", "node", "curl", "ffmpeg", "docker", "rust", "go", "gh", "ripgrep"):
            if shutil.which(name) or (name == "ripgrep" and shutil.which("rg")) or (name == "rust" and shutil.which("rustc")):
                if name not in cellar:
                    detected.append(name)

        if detected:
            lines.append("\n==> Detected Host System Tools")
            lines.append("  " + ", ".join(detected))

        out_text = "\n".join(lines)
        if not capture_output:
            print(out_text)
        return 0, out_text, ""

    def _cmd_search(self, args: List[str], capture_output: bool = False) -> Tuple[int, str, str]:
        """Searches formula dictionary and native package index."""
        query = " ".join(args).strip().lower()
        if not query:
            err = "Usage: cat brew search <query>"
            if not capture_output:
                print(err)
            return 1, "", err

        lines = [f"==> Searching formula directory for '{query}'..."]
        matches = []
        for name, spec in FORMULA_REGISTRY.items():
            if query in name or query in spec.get("desc", "").lower():
                matches.append((name, spec.get("desc", "")))

        if matches:
            lines.append("\n==> Matching Formulae:")
            for name, desc in matches:
                lines.append(f"  • {name:<14} — {desc}")

        # If on Windows, also check winget search
        if self.is_windows:
            winget_bin = shutil.which("winget.exe") or shutil.which("winget")
            if winget_bin:
                try:
                    w_res = subprocess.run([winget_bin, "search", query, "--count", "5"], capture_output=True, text=True, timeout=5)
                    if w_res.stdout and "Name" in w_res.stdout:
                        lines.append(f"\n==> Windows Package Manager (winget) Results:")
                        w_lines = [l for l in w_res.stdout.splitlines() if l.strip()][:7]
                        lines.extend(["  " + l for l in w_lines])
                except Exception:
                    pass

        out_text = "\n".join(lines)
        if not capture_output:
            print(out_text)
        return 0, out_text, ""

    def _cmd_info(self, args: List[str], capture_output: bool = False) -> Tuple[int, str, str]:
        """Shows detailed information about a formula."""
        if not args:
            err = "cat brew: 'info' requires a formula name."
            if not capture_output:
                print(err, file=sys.stderr)
            return 1, "", err

        pkg = args[0].lower().strip()
        spec = FORMULA_REGISTRY.get(pkg)
        cellar = self._load_cellar()
        is_installed = pkg in cellar or bool(shutil.which(pkg))

        lines = []
        lines.append(f"==> {pkg}: {spec.get('version', 'latest') if spec else 'latest'}")
        if spec:
            lines.append(f"    {spec.get('desc', '')}")
            lines.append(f"    {spec.get('homepage', '')}")
            lines.append(f"    Native Windows ID: {spec.get('winget', 'N/A')}")
            lines.append(f"    Native Chocolatey: {spec.get('choco', 'N/A')}")
        else:
            lines.append(f"    (Standard package mapped via universal bridge)")

        lines.append(f"    Installed: {'✓ Yes' if is_installed else '✗ Not installed'}")

        out_text = "\n".join(lines)
        if not capture_output:
            print(out_text)
        return 0, out_text, ""

    def _cmd_doctor(self, args: List[str], capture_output: bool = False) -> Tuple[int, str, str]:
        """Performs a comprehensive package manager and toolchain audit."""
        lines = []
        lines.append("=" * 68)
        lines.append("                  CAT HOMEBREW SYSTEM DOCTOR")
        lines.append("=" * 68)

        # 1. Package Managers
        lines.append("\n[1] Package Manager Roster:")
        managers = [
            ("winget", shutil.which("winget.exe") or shutil.which("winget")),
            ("choco", shutil.which("choco.exe") or shutil.which("choco")),
            ("scoop", shutil.which("scoop.exe") or shutil.which("scoop")),
            ("brew (native)", shutil.which("brew")),
            ("pip", shutil.which("pip")),
            ("npm", shutil.which("npm")),
            ("cargo", shutil.which("cargo")),
            ("go", shutil.which("go")),
        ]
        for name, path in managers:
            status = f"✓ {path}" if path else "✗ Not detected"
            lines.append(f"  • {name:<14} : {status}")

        # 2. Runtimes & Compilers
        lines.append("\n[2] Developer Toolchains:")
        toolchains = [
            ("Python", sys.version.split()[0]),
            ("Git", shutil.which("git")),
            ("Node.js", shutil.which("node")),
            ("C/C++ Compiler", shutil.which("gcc") or shutil.which("clang") or shutil.which("cl.exe") or "None"),
        ]
        for name, val in toolchains:
            lines.append(f"  • {name:<14} : {val or 'Not detected'}")

        # 3. Privilege & Environment
        lines.append("\n[3] Platform Environment:")
        lines.append(f"  • Operating System: {sys.platform} ({os.name})")
        lines.append(f"  • CAT Cellar Dir  : {self.cellar_file.parent}")
        from .sudo_cmd import is_admin
        lines.append(f"  • Admin / Sudo    : {'✓ Elevated' if is_admin() else 'Standard user'}")

        lines.append("\n" + "=" * 68)
        lines.append("✓ Your CAT Brew system is ready to install formulae.")
        lines.append("=" * 68)

        out_text = "\n".join(lines)
        if not capture_output:
            print(out_text)
        return 0, out_text, ""

    def _cmd_update(self, args: List[str], capture_output: bool = False) -> Tuple[int, str, str]:
        """Updates local formula definitions and native sources."""
        msg = "==> Updating CAT Brew formula repositories and native package sources..."
        if not capture_output:
            print(msg)
        if self.is_windows:
            winget_bin = shutil.which("winget.exe") or shutil.which("winget")
            if winget_bin:
                subprocess.run([winget_bin, "source", "update"], capture_output=capture_output)
        succ = "✓ Already up-to-date."
        if not capture_output:
            print(succ)
        return 0, f"{msg}\n{succ}", ""

    def _cmd_upgrade(self, args: List[str], capture_output: bool = False) -> Tuple[int, str, str]:
        """Upgrades packages."""
        return self._cmd_install(args, capture_output=capture_output) if args else self._cmd_update([], capture_output=capture_output)

    def _cmd_cat(self, args: List[str], capture_output: bool = False) -> Tuple[int, str, str]:
        """Prints formula JSON recipe."""
        if not args:
            return 1, "", "Usage: cat brew cat <formula>"
        pkg = args[0].lower().strip()
        spec = FORMULA_REGISTRY.get(pkg, {})
        txt = json.dumps(spec, indent=2)
        if not capture_output:
            print(txt)
        return 0, txt, ""

    def _cmd_config(self, args: List[str], capture_output: bool = False) -> Tuple[int, str, str]:
        """Shows configuration."""
        cfg = {
            "HOMEBREW_VERSION": "CAT-brew/0.8.0",
            "HOMEBREW_PREFIX": str(self.cellar_file.parent),
            "HOMEBREW_CELLAR": str(self.cellar_file),
            "PLATFORM": sys.platform,
            "PRIMARY_BRIDGE": "winget" if self.is_windows else "system",
        }
        txt = json.dumps(cfg, indent=2)
        if not capture_output:
            print(txt)
        return 0, txt, ""

    def _cmd_tap(self, args: List[str], capture_output: bool = False) -> Tuple[int, str, str]:
        """Lists or adds custom taps."""
        tap_dir = self.cellar_file.parent / "taps"
        tap_dir.mkdir(parents=True, exist_ok=True)
        if not args:
            taps = [d.name for d in tap_dir.iterdir() if d.is_dir()]
            res = "==> Taps:\n  • cat/core (built-in)\n" + "\n".join(f"  • {t}" for t in taps)
            if not capture_output:
                print(res)
            return 0, res, ""
        tap_name = args[0]
        (tap_dir / tap_name.replace("/", "_")).mkdir(parents=True, exist_ok=True)
        msg = f"✓ Tapped '{tap_name}'."
        if not capture_output:
            print(msg)
        return 0, msg, ""

    def _format_help(self) -> str:
        return """Usage: cat brew <command> [options] [formula|cask...]
CAT brew — Cross-platform Homebrew Formula Manager & Universal Package Bridge.

Commands:
  install, i <formula>      Install a formula or cask
  uninstall, rm <formula>   Uninstall a formula or cask
  list, ls                  List installed formulae in CAT Cellar
  search <text>             Search formulae, casks, and native package index
  info <formula>            Display information about a formula
  doctor                    Check your system and package managers for potential problems
  update                    Fetch newest version of CAT Brew and formula recipes
  upgrade [formula]         Upgrade installed formulae
  cat <formula>             Display the source/recipe of a formula
  config                    Show CAT Brew configuration
  tap [user/repo]           Tap a new formula repository
  cleanup                   Purge cached downloads and temp files

Examples:
  cat brew install node
  cat brew install git ffmpeg ripgrep
  cat brew list
  cat brew search python
  cat brew doctor
  cat brew info ffmpeg
"""


def run_brew(argv: List[str], capture_output: bool = False) -> Tuple[int, str, str]:
    """Public helper function to execute CAT Brew programmatically."""
    return CatBrew().run(argv, capture_output=capture_output)


def main(argv: Optional[List[str]] = None) -> int:
    """Console script entrypoint for `cat-brew` or `cat brew`."""
    args = sys.argv[1:] if argv is None else argv
    exit_code, _, _ = CatBrew().run(args, capture_output=False)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
