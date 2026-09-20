#!/usr/bin/env python3
"""
CAT — Release Manifest Generator.

Scans dist/ for platform runtime archives and installers,
computes SHA-256 hashes and file sizes, determines release channel,
and generates release/manifest/releases.json.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DIST = REPO_ROOT / "dist"
DEFAULT_OUTPUT = REPO_ROOT / "release" / "manifest" / "releases.json"
DEFAULT_REPO = "kazizillani-oss/CAT_v0.7.9"


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def detect_channel(version: str) -> str:
    v = version.lower()
    if "nightly" in v:
        return "nightly"
    if "alpha" in v or "-a" in v:
        return "alpha"
    if "beta" in v or "-b" in v or "rc" in v:
        return "beta"
    return "stable"


def generate_manifest(
    version: str,
    dist_dir: Path = DEFAULT_DIST,
    output_path: Path = DEFAULT_OUTPUT,
    repo: str = DEFAULT_REPO,
    dry_run: bool = False,
) -> dict:
    tag = f"v{version}"
    base_url = f"https://github.com/{repo}/releases/download/{tag}"
    channel = detect_channel(version)

    manifest = {
        "$schema": "./schema.json",
        "version": version,
        "channel": channel,
        "releaseDate": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "platforms": {},
        "installer": {},
        "notes": f"CAT {tag} production release",
    }

    platform_configs = {
        "windows-x64": ("cat-windows-x64.zip", "cat.exe", "zip", "10.0"),
        "windows-arm64": ("cat-windows-arm64.zip", "cat.exe", "zip", "10.0"),
        "linux-x64": ("cat-linux-x64.tar.gz", "cat", "tar.gz", "glibc-2.31"),
        "linux-arm64": ("cat-linux-arm64.tar.gz", "cat", "tar.gz", "glibc-2.31"),
        "macos-x64": ("cat-macos-x64.tar.gz", "cat", "tar.gz", "11.0"),
        "macos-arm64": ("cat-macos-arm64.tar.gz", "cat", "tar.gz", "11.0"),
    }

    for plat, (archive_name, exe, arch_type, min_os) in platform_configs.items():
        archive_file = dist_dir / archive_name
        if archive_file.exists():
            sha = compute_sha256(archive_file)
            sz = archive_file.stat().st_size
        else:
            # Fallback placeholder hash if dist not yet built
            sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            sz = 0

        manifest["platforms"][plat] = {
            "url": f"{base_url}/{archive_name}",
            "sha256": sha,
            "executable": exe,
            "archiveType": arch_type,
            "sizeBytes": sz,
            "minOsVersion": min_os,
        }

    # Check for Windows installer
    installer_path = dist_dir / "CAT-Setup.exe"
    if installer_path.exists():
        manifest["installer"]["windows"] = {
            "url": f"{base_url}/CAT-Setup.exe",
            "sha256": compute_sha256(installer_path),
            "sizeBytes": installer_path.stat().st_size,
        }
    else:
        manifest["installer"]["windows"] = {
            "url": f"{base_url}/CAT-Setup.exe",
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "sizeBytes": 0,
        }

    out_json = json.dumps(manifest, indent=2) + "\n"

    if dry_run:
        print("Generated Manifest (Dry Run):")
        print(out_json)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(out_json, encoding="utf-8")
        print(f"✓ Manifest successfully generated at: {output_path}")

    return manifest


def main():
    parser = argparse.ArgumentParser(description="Generate CAT release manifest")
    parser.add_argument("--version", help="Release version (defaults to canonical)")
    parser.add_argument("--dist-dir", type=Path, default=DEFAULT_DIST, help="Directory containing release archives")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output path for releases.json")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repository (owner/name)")
    parser.add_argument("--dry-run", action="store_true", help="Print manifest without writing to disk")
    args = parser.parse_args()

    # Get version
    if not args.version:
        sys.path.insert(0, str(REPO_ROOT / "release"))
        from version_manager import get_canonical_version
        version = get_canonical_version()
    else:
        version = args.version

    generate_manifest(
        version=version,
        dist_dir=args.dist_dir,
        output_path=args.output,
        repo=args.repo,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
