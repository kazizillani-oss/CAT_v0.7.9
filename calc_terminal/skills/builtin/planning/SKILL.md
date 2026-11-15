---
name: planning
display_name: "Implementation Planning & Task Decomposition"
version: "1.2.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "planning"
description: "Produces rigorous, phase-by-phase implementation plans with dependency graphs, verification checklists, and risk mitigations."
tags: ["planning", "roadmap", "task-decomposition", "project-management"]
permissions: ["read_files"]
compatibility: ">=0.9.0"
---

# Implementation Planning & Task Decomposition

## Overview
The planning skill produces surgical, phased engineering execution blueprints. It breaks down large initiatives into verifiable, testable milestones with zero ambiguity.

## Protocol & Execution Phases
1. **Scope Definition & Boundary Setting**:
   - Establish strict acceptance criteria (what constitutes 'done').
   - Identify non-goals and out-of-scope items to prevent scope creep.
2. **Dependency Mapping**:
   - Trace upstream dependencies (data contracts, schema migrations, third-party APIs).
   - Order tasks topologically so prerequisite foundations precede downstream consumers.
3. **Phased Task Breakdown**:
   - Phase 1: Foundation & Data Contracts.
   - Phase 2: Core Logic & Services.
   - Phase 3: Integration & UI/CLI surfaces.
   - Phase 4: Automated Verification, Benchmarks & Hardening.
4. **Verification & Rollback Strategy**:
   - Specify automated unit/integration tests for each phase.
   - Document rollback criteria and zero-downtime deployment paths.

## Key Rules
- Every task must have an explicit verification check (e.g., test command, log output, or assertion).
- Atomic step sizing: Tasks should represent cohesive, reviewable units of work.
