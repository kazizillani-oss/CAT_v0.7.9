---
name: cat-context-manager
display_name: "CAT Context Manager & Token Pruner"
version: "1.0.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "productivity"
description: "Intelligent file relevance ranking, AST-level slicing, and context window budget optimization for agent turns."
tags: ["cat-native", "context", "token-optimization", "ast", "pruning"]
permissions: ["read_files"]
compatibility: ">=0.9.0"
---

# CAT Context Manager & Token Pruner

## Overview
Original CAT-native context engine. Ensures that AI agents receive exactly the right amount of code context without exceeding model token limits or injecting distracting noise.

## Strategies
1. **Relevance Ranking**:
   - Ranks files by lexical proximity, recent git edits, and active stack trace references.
2. **AST-Level Slicing**:
   - Extracts relevant function and class signatures while omitting uncalled helper bodies.
3. **Token Budget Enforcement**:
   - Dynamically budgets context tokens across system instructions, conversation history, and workspace files.
