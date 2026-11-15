---
name: git-workflow
display_name: "Git Safe Branch & Commit Workflow"
version: "1.2.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "productivity"
description: "Enforces atomic Conventional Commits, clean branch strategies, conflict resolution, and working tree hygiene."
tags: ["git", "vcs", "commits", "branches", "merge", "devops"]
permissions: ["read_files", "shell_commands"]
compatibility: ">=0.9.0"
---

# Git Safe Branch & Commit Workflow

## Overview
Maintain pristine version control hygiene through atomic commits, structured branching, and conflict-free merges.

## Workflow Rules
1. **Status Inspection**: Always execute `git status --short` and `git diff` before staging.
2. **Atomic Commits**: Each commit must encapsulate exactly one logical change. Never bundle unrelated bug fixes with feature work.
3. **Conventional Commits Standard**:
   - `feat(scope): add new capability`
   - `fix(scope): resolve issue description`
   - `refactor(scope): modernize internals without behavior change`
   - `test(scope): add regression test cases`
   - `docs(scope): update documentation`
4. **Merge Conflict Resolution**:
   - Rebase on target main/trunk cleanly.
   - Resolve conflicts by understanding both sides of the change, authoring a verified synthetic resolution.
