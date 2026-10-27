"""
CAT CLI Commands Package — Built-in Command Line Tools.

Provides native command-line implementations for:
- curl: High-performance HTTP/REST request client with JSON coloring & streaming.
- brew: Cross-platform Homebrew formula bridge and package manager.
- sudo: Cross-platform administrative privilege elevator.
"""

from __future__ import annotations

from .curl_cmd import main as curl_main, run_curl, CatCurl
from .brew_cmd import main as brew_main, run_brew, CatBrew
from .sudo_cmd import main as sudo_main, run_sudo, is_admin, CatSudo

__all__ = [
    "curl_main",
    "run_curl",
    "CatCurl",
    "brew_main",
    "run_brew",
    "CatBrew",
    "sudo_main",
    "run_sudo",
    "is_admin",
    "CatSudo",
]
