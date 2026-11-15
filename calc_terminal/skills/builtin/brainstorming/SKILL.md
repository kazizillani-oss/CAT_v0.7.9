---
name: brainstorming
display_name: "Brainstorming & Technical Ideation"
version: "1.1.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "planning"
description: "Turns rough user ideas, requirements, and creative concepts into structured architectural designs, tradeoffs, and system specifications."
tags: ["brainstorming", "architecture", "ideation", "design", "planning"]
permissions: ["read_files"]
compatibility: ">=0.9.0"
---

# Brainstorming & Technical Ideation

## Overview
Transform ambiguous concepts, feature requests, or product ideas into structured, actionable technical proposals. Use this skill before committing to code or irreversible architectural decisions.

## Protocol & Step-by-Step Workflow
1. **Clarify Problem Statement**: Define the underlying user problem rather than jumping straight to the implementation details.
2. **Context Discovery**: Survey existing workspace files, configurations, conventions, and dependencies to ground ideation in reality.
3. **Explore Architectural Options**: Formulate at least 2-3 distinct implementation paths (e.g., minimal footprint vs. extensible architecture vs. performance-optimized).
4. **Evaluate Tradeoffs**:
   - Time to implement & developer complexity.
   - Runtime performance, latency, and resource footprint.
   - Maintainability, tech debt, and future extensibility.
   - Breaking changes or backward compatibility impacts.
5. **Formulate Recommendation**: Clearly recommend the optimal approach with rationale. Present structured specifications including component responsibilities, data flow, and failure recovery.

## Heuristics & Quality Gates
- Never present an idea without analyzing its failure modes.
- Avoid buzzword-driven architecture; prefer the simplest architecture that solves the problem robustly.
- Explicitly check compatibility with the project's current language runtime and libraries.
