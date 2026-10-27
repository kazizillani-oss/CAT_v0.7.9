#!/usr/bin/env python3
"""
CAT — Windows Installer Executable Builder.
Compiles setup.cs into CAT-Setup.exe and catsetup.exe using Microsoft csc.exe.
Places artifacts in repo root, dist/, and release/.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CSC_PATH = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
if not CSC_PATH.exists():
    CSC_PATH = Path(r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe")

SETUP_CS = REPO_ROOT / "installer" / "windows" / "setup.cs"
ICO_PATH = REPO_ROOT / "calc_terminal" / "cat.ico"
DIST_DIR = REPO_ROOT / "dist"
RELEASE_DIR = REPO_ROOT / "release"

def build():
    if not CSC_PATH.exists():
        print(f"[ERROR] Microsoft C# compiler (csc.exe) not found at: {CSC_PATH}")
        sys.exit(1)

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    installer_dir = REPO_ROOT / "installer" / "windows"
    out_exe = installer_dir / "CAT-Setup.exe"

    cmd = [
        str(CSC_PATH),
        "/nologo",
        "/target:exe",
        "/optimize+",
        f"/out:{out_exe}",
    ]

    if ICO_PATH.exists():
        cmd.append(f"/win32icon:{ICO_PATH}")

    cmd.append(str(SETUP_CS))

    print(f"Compiling Windows Installer with: {CSC_PATH}")
    print(f"Command: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[ERROR] Compilation failed:\n{res.stderr}\n{res.stdout}")
        sys.exit(res.returncode)

    print(f"Successfully compiled: {out_exe} ({out_exe.stat().st_size:,} bytes)")

    # Copy to required destinations:
    # 1. installer/windows/catsetup.exe
    installer_catsetup = installer_dir / "catsetup.exe"
    shutil.copy2(out_exe, installer_catsetup)

    # 2. repo root: CAT-Setup.exe and catsetup.exe
    root_catsetup_upper = REPO_ROOT / "CAT-Setup.exe"
    root_catsetup_lower = REPO_ROOT / "catsetup.exe"
    shutil.copy2(out_exe, root_catsetup_upper)
    shutil.copy2(out_exe, root_catsetup_lower)
    print(f"Copied to repo root: {root_catsetup_upper} and {root_catsetup_lower}")

    # 3. release/CAT-Setup.exe and release/catsetup.exe
    release_exe = RELEASE_DIR / "CAT-Setup.exe"
    release_lower = RELEASE_DIR / "catsetup.exe"
    shutil.copy2(out_exe, release_exe)
    shutil.copy2(out_exe, release_lower)
    print(f"Copied to: {release_exe} and {release_lower}")

    print("\n[SUCCESS] Windows installer binaries CAT-Setup.exe and catsetup.exe are ready!")

if __name__ == "__main__":
    build()
