---
name: cat-test-generator
display_name: "CAT Test Suite Generator"
version: "1.0.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "testing"
description: "Generates comprehensive unit, integration, and mocking suites tailored to the project's test framework."
tags: ["cat-native", "test-generator", "pytest", "vitest", "mocking", "coverage"]
permissions: ["read_files", "write_files"]
compatibility: ">=0.9.0"
---

# CAT Test Suite Generator

## Overview
Original CAT-native test authoring engine. Analyzes project source files and automatically writes comprehensive test cases covering happy paths, edge cases, and exception handling.

## Coverage Checklist
1. **Boundary & Edge Testing**: Zero, negative, max-int, empty strings, null, and malformed inputs.
2. **Mocking & Isolation**: Mock external APIs and disk I/O while testing internal logic thoroughly.
3. **Framework Alignment**: Outputs idiomatic tests using the project's native runner (pytest fixtures, Vitest describe/it).
