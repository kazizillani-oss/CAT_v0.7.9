---
name: testing
display_name: "Automated Testing & Coverage Suite"
version: "1.2.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "testing"
description: "Designs, generates, and executes unit tests, integration tests, mock assertions, and property-based regression suites."
tags: ["testing", "pytest", "jest", "unit-test", "coverage", "tdd"]
permissions: ["read_files", "write_files", "shell_commands"]
compatibility: ">=0.9.0"
---

# Automated Testing & Coverage Suite

## Overview
Architect and execute robust automated test suites across Python (pytest, unittest), JavaScript/TypeScript (Vitest, Jest), and Go/Rust platforms.

## Core Testing Methodologies
1. **Test-Driven Development (TDD)**:
   - Red: Write a failing test capturing the intended behavior or edge case.
   - Green: Write minimal implementation code to pass the test.
   - Refactor: Clean up structure while preserving green test state.
2. **Test Pyramid Alignment**:
   - **Unit Tests (70%)**: Fast, isolated, deterministic logic verification with mocks for external I/O.
   - **Integration Tests (20%)**: Component boundary, database, and filesystem contract validation.
   - **End-to-End Tests (10%)**: Full CLI/UI lifecycle scenarios.
3. **Mocking Standards**:
   - Mock external networks, slow hardware devices, and nondeterministic clocks.
   - Verify both positive paths and negative failure modes (timeouts, exceptions).
