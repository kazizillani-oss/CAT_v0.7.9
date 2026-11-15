---
name: cat-auto-fix
display_name: "CAT Auto-Fix & Error Recovery"
version: "1.0.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "debugging"
description: "Automated diagnosis and correction of common build, syntax, runtime, and dependency errors in CAT projects."
tags: ["cat-native", "auto-fix", "recovery", "compiler-errors", "debugging"]
permissions: ["read_files", "write_files", "shell_commands"]
compatibility: ">=0.9.0"
---

# CAT Auto-Fix & Error Recovery

## Overview
Original CAT-native error recovery engine. Parses compiler errors, missing import diagnostics, and stack traces to formulate immediate, verified repairs.

## Automated Fix Capabilities
1. **Missing Module & Dependency Resolution**:
   - Detects `ModuleNotFoundError` or `Cannot find module` and suggests or executes clean package installation.
2. **Syntax & Import Corrections**:
   - Resolves circular imports and malformed relative package paths.
   - Replaces deprecated API calls with supported modern replacements.
3. **Type Annotation Fixes**:
   - Fixes invalid TypeVar constraints and generic union mismatches.
