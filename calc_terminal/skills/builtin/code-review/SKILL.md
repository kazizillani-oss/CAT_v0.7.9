---
name: code-review
display_name: "Code Review & Quality Assurance"
version: "1.1.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "coding"
description: "Performs comprehensive automated code reviews: architectural fit, readability, performance bottlenecks, and adherence to clean code standards."
tags: ["code-review", "clean-code", "refactoring", "best-practices", "quality"]
permissions: ["read_files"]
compatibility: ">=0.9.0"
---

# Code Review & Quality Assurance

## Overview
Perform deep, constructive, and uncompromising code reviews. Evaluates correctness, architectural integrity, efficiency, error resilience, and readability.

## Review Dimensions
1. **Correctness & Edge Cases**:
   - Off-by-one errors, null/undefined safety, race conditions, and unhandled exceptions.
   - Idempotency and transaction safety.
2. **Architectural & Design Consistency**:
   - Adherence to project directory structure, naming conventions, and layering rules.
   - Single Responsibility Principle (SRP) and separation of concerns.
3. **Performance & Resource Hygiene**:
   - Unnecessary disk I/O, N+1 query patterns, unindexed lookups, or unbounded memory growth.
   - Proper cleanup of file handles, sockets, and timers.
4. **Security & Input Validation**:
   - Sanitization of external inputs, escaping of shell/SQL arguments, credential safety.

## Review Output Format
- Categorize findings into **Blocker**, **Warning**, and **Suggestion**.
- Always provide concrete, copy-pasteable diffs or replacements for suggested fixes.
