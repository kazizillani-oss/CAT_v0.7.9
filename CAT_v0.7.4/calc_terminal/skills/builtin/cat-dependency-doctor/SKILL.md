---
name: cat-dependency-doctor
display_name: "CAT Dependency Doctor"
version: "1.0.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "coding"
description: "Audits npm, pip, cargo, and go dependencies; resolves version conflicts, deprecations, and security advisories."
tags: ["cat-native", "dependencies", "npm", "pip", "vulnerabilities", "packaging"]
permissions: ["read_files", "write_files", "shell_commands"]
compatibility: ">=0.9.0"
---

# CAT Dependency Doctor

## Overview
Original CAT-native dependency management engine. Diagnoses lockfile corruption, diamond dependency conflicts, peer dependency mismatches, and CVE vulnerabilities.

## Diagnostic Protocol
1. **Audit Lockfiles**: Verify `package-lock.json`, `poetry.lock`, `uv.lock`, or `Pipfile.lock` integrity.
2. **Detect Deprecations**: Identify packages with upcoming end-of-life dates or unmaintained repositories.
3. **Conflict Resolution**: Compute minimal version bumps that satisfy all transitive dependency constraints.
