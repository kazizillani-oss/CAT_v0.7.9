---
name: security-audit
display_name: "Application Security & Vulnerability Audit"
version: "1.2.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "security"
description: "Scans for OWASP Top 10 vulnerabilities, injection flaws, path traversals, secret leakages, and insecure dependencies."
tags: ["security", "audit", "owasp", "vulnerability", "encryption"]
permissions: ["read_files", "write_files", "shell_commands"]
compatibility: ">=0.9.0"
---

# Application Security & Vulnerability Audit

## Overview
Conduct systematic vulnerability assessments across source code, architecture, and runtime environments.

## Threat Vectors & Audit Checklist
1. **Injection Vulnerabilities**:
   - Command injection (unquoted shell execution, `os.system`, `subprocess(shell=True)`).
   - SQL injection (unparameterized query concatenations).
2. **Filesystem Safety & Path Traversal**:
   - Directory traversal attacks (`../`, symlink following, unvalidated archive extractions).
   - Insecure temporary file creation and overly permissive permissions (chmod 777).
3. **Secret & Credential Exposure**:
   - Hardcoded API keys, tokens, private keys, or credentials in Git history.
   - Logging of sensitive headers, passwords, or PII.
4. **Dependency Supply Chain**:
   - Outdated packages with known CVEs, malicious typosquatting packages.
   - Insecure package deserialization (`pickle.loads`, `yaml.unsafe_load`).
