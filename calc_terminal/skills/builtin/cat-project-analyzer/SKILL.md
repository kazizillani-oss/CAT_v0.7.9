---
name: cat-project-analyzer
display_name: "CAT Project Analyzer & Architecture Inspector"
version: "1.0.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "coding"
description: "Deep recursive project inspection: identifies tech stack, framework versions, entry points, dependencies, and code hygiene."
tags: ["cat-native", "analyzer", "architecture", "inspection", "diagnostics"]
permissions: ["read_files", "shell_commands"]
compatibility: ">=0.9.0"
---

# CAT Project Analyzer & Architecture Inspector

## Overview
Original CAT-native inspection engine. Scans workspaces to produce structured architectural dossiers: tech stacks, configuration files, test coverage, and dependency graphs.

## Inspection Checklist
1. **Stack & Runtime Detection**:
   - Language runtimes: Python, Node.js/TypeScript, Go, Rust, C++.
   - Framework detection: FastAPI, Django, React, Next.js, Textual, Express.
2. **Directory & Module Topology**:
   - Core library directories, entry points (`main.py`, `index.ts`, `app.py`).
   - Configuration files (`pyproject.toml`, `package.json`, `tsconfig.json`).
3. **Health & Maintenance Metrics**:
   - Test framework presence and configuration.
   - Linter and formatter setups (Ruff, ESLint, Prettier).
