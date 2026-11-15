---
name: refactoring
display_name: "Code Refactoring & Architectural Modernization"
version: "1.2.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "coding"
description: "Safely transforms legacy code, removes code smells, decomposes monoliths, and improves cohesion without altering behavior."
tags: ["refactoring", "clean-architecture", "modernization", "code-smells"]
permissions: ["read_files", "write_files", "shell_commands"]
compatibility: ">=0.9.0"
---

# Code Refactoring & Architectural Modernization

## Overview
Refactor code to maximize clarity, reduce cognitive complexity, and eliminate duplication while strictly preserving external runtime behavior.

## Core Refactoring Patterns
1. **Decompose Monoliths**:
   - Extract large multi-thousand-line modules into cohesive, decoupled submodules with explicit public interfaces.
2. **Eliminate Code Smells**:
   - Long parameter lists -> Parameter objects / Dataclasses.
   - Deep nested conditionals -> Guard clauses & early returns.
   - Magic numbers and hardcoded strings -> Named constants and configuration models.
3. **Behavior Preservation Guarantee**:
   - Run the existing test suite before initiating refactoring.
   - Make small, incremental refactorings, verifying tests pass at every step.
