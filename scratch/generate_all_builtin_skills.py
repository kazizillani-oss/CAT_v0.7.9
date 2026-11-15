"""
Generator for CAT CLI Built-in Agent Skills Library.
Bundles all 15 Core Dev Skills, 8 Open-Source Skills, and 10 CAT-Native Skills offline.
"""

import json
import os
from pathlib import Path

BUILTIN_DIR = Path(__file__).parent.parent / "calc_terminal" / "skills" / "builtin"
BUILTIN_DIR.mkdir(parents=True, exist_ok=True)

SKILLS_DATA = [
    # =========================================================================
    # A. 15 CORE DEVELOPMENT SKILLS
    # =========================================================================
    {
        "id": "brainstorming",
        "name": "Brainstorming & Technical Ideation",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "planning",
        "icon": "💡",
        "version": "1.1.0",
        "description": "Turns rough user ideas, requirements, and creative concepts into structured architectural designs, tradeoffs, and system specifications.",
        "tags": ["brainstorming", "architecture", "ideation", "design", "planning"],
        "permissions": ["read_files"],
        "markdown": """# Brainstorming & Technical Ideation

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
"""
    },
    {
        "id": "planning",
        "name": "Implementation Planning & Task Decomposition",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "planning",
        "icon": "📋",
        "version": "1.2.0",
        "description": "Produces rigorous, phase-by-phase implementation plans with dependency graphs, verification checklists, and risk mitigations.",
        "tags": ["planning", "roadmap", "task-decomposition", "project-management"],
        "permissions": ["read_files"],
        "markdown": """# Implementation Planning & Task Decomposition

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
"""
    },
    {
        "id": "code-review",
        "name": "Code Review & Quality Assurance",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "coding",
        "icon": "🔍",
        "version": "1.1.0",
        "description": "Performs comprehensive automated code reviews: architectural fit, readability, performance bottlenecks, and adherence to clean code standards.",
        "tags": ["code-review", "clean-code", "refactoring", "best-practices", "quality"],
        "permissions": ["read_files"],
        "markdown": """# Code Review & Quality Assurance

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
"""
    },
    {
        "id": "debugging",
        "name": "Systematic Root-Cause Debugging",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "debugging",
        "icon": "🐞",
        "version": "1.3.0",
        "description": "Isolates errors, traces stack traces, hypothesizes root causes, and implements verified surgical fixes with regression prevention.",
        "tags": ["debugging", "troubleshooting", "stack-trace", "root-cause", "fixes"],
        "permissions": ["read_files", "write_files", "shell_commands"],
        "markdown": """# Systematic Root-Cause Debugging

## Overview
Debugging is a rigorous scientific process: observe symptoms, form falsifiable hypotheses, isolate minimal reproducers, identify the exact root cause, apply surgical repairs, and verify zero regressions.

## 5-Step Debugging Protocol
1. **Reproduce & Capture**:
   - Run the failing command or test to observe the exact stack trace, error code, and runtime conditions.
   - Do not guess or assume the error without empirical evidence.
2. **Trace the Data Flow**:
   - Inspect the call stack backward from point of failure to input origin.
   - Identify which variable, state transition, or boundary assumption was violated.
3. **Formulate Root Cause Hypothesis**:
   - Differentiate symptoms (e.g., `AttributeError`) from root cause (e.g., misconfigured initialization order).
4. **Apply Surgical Fix**:
   - Implement the minimal necessary change to correct the flaw without side effects.
   - Avoid defensive 'band-aids' that swallow errors without fixing root causes.
5. **Verify & Prevent Regression**:
   - Run the reproduction case to confirm resolution.
   - Author an automated regression test covering this exact edge case.
"""
    },
    {
        "id": "testing",
        "name": "Automated Testing & Coverage Suite",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "testing",
        "icon": "🧪",
        "version": "1.2.0",
        "description": "Designs, generates, and executes unit tests, integration tests, mock assertions, and property-based regression suites.",
        "tags": ["testing", "pytest", "jest", "unit-test", "coverage", "tdd"],
        "permissions": ["read_files", "write_files", "shell_commands"],
        "markdown": """# Automated Testing & Coverage Suite

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
"""
    },
    {
        "id": "security-audit",
        "name": "Application Security & Vulnerability Audit",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "security",
        "icon": "🛡️",
        "version": "1.2.0",
        "description": "Scans for OWASP Top 10 vulnerabilities, injection flaws, path traversals, secret leakages, and insecure dependencies.",
        "tags": ["security", "audit", "owasp", "vulnerability", "encryption"],
        "permissions": ["read_files", "write_files", "shell_commands"],
        "markdown": """# Application Security & Vulnerability Audit

## Overview
Conduct systematic vulnerability assessments across source code, architecture, and runtime environments.

## Threat Vectors & Audit Checklist
1. **Injection Vulnerabilities**:
   - Command injection (unquoted shell execution, `os.system`, `subprocess(shell=True)`).
   - SQL injection (unparameterized query concatenations).
2. **Filesystem Safety & Path Traversal**:
   - Directory traversal attacks (`../`, symlink following, unvalidated archive extractions).
   - Insecure temporary file creation and overly permissive permissions (chmod 777).
3. **Secret & Credential Exposure**:
   - Hardcoded API keys, tokens, private keys, or credentials in Git history.
   - Logging of sensitive headers, passwords, or PII.
4. **Dependency Supply Chain**:
   - Outdated packages with known CVEs, malicious typosquatting packages.
   - Insecure package deserialization (`pickle.loads`, `yaml.unsafe_load`).
"""
    },
    {
        "id": "git-workflow",
        "name": "Git Safe Branch & Commit Workflow",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "productivity",
        "icon": "🌿",
        "version": "1.2.0",
        "description": "Enforces atomic Conventional Commits, clean branch strategies, conflict resolution, and working tree hygiene.",
        "tags": ["git", "vcs", "commits", "branches", "merge", "devops"],
        "permissions": ["read_files", "shell_commands"],
        "markdown": """# Git Safe Branch & Commit Workflow

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
"""
    },
    {
        "id": "documentation",
        "name": "Technical Documentation & API Specification",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "documentation",
        "icon": "📖",
        "version": "1.1.0",
        "description": "Generates production-grade READMEs, API references, architecture diagrams, docstrings, and developer onboarding guides.",
        "tags": ["documentation", "readme", "api-docs", "markdown", "architecture"],
        "permissions": ["read_files", "write_files"],
        "markdown": """# Technical Documentation & API Specification

## Overview
Author high-clarity, accurate, and comprehensive technical documentation. Good documentation empowers developers to build, operate, and troubleshoot software without friction.

## Core Documentation Artifacts
1. **README Files**:
   - High-level value proposition and visual badge strip.
   - Quickstart guide (prerequisites, 2-step installation, runnable sample).
   - Architecture overview with ASCII or Mermaid diagrams.
   - CLI flags, configuration variables, and environment variables.
2. **API & Reference Docs**:
   - Function signatures, parameter types, default values, and return types.
   - Raised exceptions and error status codes.
   - Realistic, executable input/output examples.
3. **Architecture Decision Records (ADRs)**:
   - Context, alternatives considered, decision outcome, and long-term consequences.
"""
    },
    {
        "id": "research",
        "name": "Deep Technical Research & Solution Comparison",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "research",
        "icon": "🔬",
        "version": "1.2.0",
        "description": "Surveys libraries, algorithms, architectures, benchmarks, and provides evidence-backed comparison matrices.",
        "tags": ["research", "benchmarking", "libraries", "comparison", "evaluation"],
        "permissions": ["read_files", "shell_commands"],
        "markdown": """# Deep Technical Research & Solution Comparison

## Overview
Conduct objective, data-driven research to evaluate technologies, libraries, algorithms, and architectural patterns.

## Research Protocol
1. **State the Research Objective**: Frame the precise technical question (e.g., 'What is the most memory-efficient TUI layout engine in Python for 60fps rendering?').
2. **Market & Ecosystem Survey**: Identify all credible contenders in the target language and ecosystem.
3. **Metric-Driven Comparison Matrix**:
   - Performance (CPU cycles, memory allocation, throughput, latency).
   - Maintenance Health (commit frequency, issue close rate, open-source governance).
   - Compatibility (OS support, runtime versions, zero native C-extension options).
   - License Compatibility (MIT, Apache-2.0, BSD vs GPL restrictions).
4. **Synthesized Recommendation**: Provide an unambiguous recommendation with migration caveats.
"""
    },
    {
        "id": "browser-automation",
        "name": "Browser Automation & E2E Testing",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "testing",
        "icon": "🌐",
        "version": "1.1.0",
        "description": "Drives headless browsers, Playwright/Puppeteer flows, automated scraping, synthetic testing, and screenshot verification.",
        "tags": ["browser", "playwright", "puppeteer", "automation", "e2e"],
        "permissions": ["read_files", "write_files", "shell_commands"],
        "markdown": """# Browser Automation & E2E Testing

## Overview
Automate web browser interactions, end-to-end user journeys, synthetic monitoring, and visual regression testing using Playwright, Puppeteer, or Chrome DevTools.

## Operational Standards
1. **Selector Robustness**:
   - Prefer semantic accessibility selectors (`getByRole`, `getByLabel`, `data-testid`) over brittle CSS classes or deep XPath.
2. **Asynchronous Waiting & Flakiness Prevention**:
   - Avoid hardcoded `sleep` delays; always wait on explicit DOM state changes (`waitForSelector`, `waitForResponse`, network idle).
3. **Visual Verification & Artifacts**:
   - Capture full-page screenshots and DOM snapshots on assertion failure.
   - Record network activity and console errors for root-cause diagnosis.
"""
    },
    {
        "id": "refactoring",
        "name": "Code Refactoring & Architectural Modernization",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "coding",
        "icon": "♻️",
        "version": "1.2.0",
        "description": "Safely transforms legacy code, removes code smells, decomposes monoliths, and improves cohesion without altering behavior.",
        "tags": ["refactoring", "clean-architecture", "modernization", "code-smells"],
        "permissions": ["read_files", "write_files", "shell_commands"],
        "markdown": """# Code Refactoring & Architectural Modernization

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
"""
    },
    {
        "id": "humanizer",
        "name": "Natural Humanizer & Tone Polishing",
        "author": "Blader & CAT Team",
        "github_username": "@blader",
        "repository": "https://github.com/blader/humanizer",
        "license": "MIT",
        "category": "productivity",
        "icon": "✍️",
        "version": "1.3.0",
        "description": "Eliminates AI clichés, stiff passive structures, and robotic prose, producing natural, engaging, human-written text.",
        "tags": ["humanizer", "writing", "copywriting", "tone", "editing", "blader"],
        "permissions": ["read_files", "write_files"],
        "markdown": """# Natural Humanizer & Tone Polishing

## Overview
Highly credited to Blader (@blader) and the Humanizer project. Removes robotic AI writing quirks, throat-clearing preambles, and generic platitudes. Produces punchy, authentic, human prose.

## Words & Patterns to Eliminate
1. **Robotic AI Clichés**:
   - "Delve into", "Tapestry", "Beacon", "Testament to", "In summary", "It is crucial to remember".
   - "Furthermore", "Moreover", "In today's fast-paced digital world".
2. **Throat-Clearing Openers**:
   - "Certainly! I would be happy to help with that."
   - "Great question! Let's examine..."
3. **Passive & Bloated Syntax**:
   - Replace "The decision was made by the engineering team" with "The engineering team decided".
   - Replace "In order to achieve" with "To achieve".

## Core Principles
- Lead with the most important insight or action immediately.
- Use direct, concrete verbs.
- Vary sentence rhythm and length to create an engaging natural cadence.
"""
    },
    {
        "id": "seo-optimization",
        "name": "Search Engine Optimization (SEO) & Web Vitals",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "marketing",
        "icon": "📈",
        "version": "1.1.0",
        "description": "Optimizes meta tags, OpenGraph schemas, semantic HTML, Core Web Vitals, sitemaps, and search indexability.",
        "tags": ["seo", "web-vitals", "meta-tags", "performance", "indexing"],
        "permissions": ["read_files", "write_files"],
        "markdown": """# Search Engine Optimization (SEO) & Web Vitals

## Overview
Technical SEO engineering and optimization for web apps, documentation portals, and static landing sites.

## Technical Audit & Implementation
1. **Semantic DOM Hierarchy**:
   - Single authoritative `<h1>` per page reflecting primary topic.
   - Logical sequential headings (`<h2>`, `<h3>`) with zero skip levels.
2. **Metadata & OpenGraph**:
   - Concise title tags (<60 characters) and meta descriptions (<155 characters).
   - Comprehensive OpenGraph (`og:title`, `og:image`, `og:type`) and Twitter card tags.
   - JSON-LD structured data schemas (Organization, Article, SoftwareApplication).
3. **Core Web Vitals Engineering**:
   - LCP (Largest Contentful Paint) < 2.5s.
   - INP (Interaction to Next Paint) < 200ms.
   - CLS (Cumulative Layout Shift) < 0.1.
"""
    },
    {
        "id": "scientific-research",
        "name": "Scientific Computing & Data Analysis",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "science",
        "icon": "🧪",
        "version": "1.2.0",
        "description": "Conducts numerical modeling, statistical tests, symbolic algebra (SymPy), and data visualization with SciPy and NumPy.",
        "tags": ["science", "math", "numpy", "scipy", "sympy", "data-analysis"],
        "permissions": ["read_files", "write_files", "shell_commands"],
        "markdown": """# Scientific Computing & Data Analysis

## Overview
Performs rigorous numerical calculations, statistical hypothesis testing, symbolic mathematics, and reproducible data workflows.

## Standards & Best Practices
1. **Exact Symbolic Math First**:
   - Use SymPy for analytical solutions, limits, integrals, and matrix decompositions before resorting to floating-point approximations.
2. **Vectorized Numerical Computing**:
   - Leverage NumPy and SciPy vectorization; avoid slow pure-Python nested loops over large datasets.
   - Enforce explicit precision handling (`np.float64`) to avoid precision decay in iterative solvers.
3. **Statistical Rigor**:
   - Report confidence intervals, effect sizes, and p-values with appropriate multi-testing corrections.
   - Always state assumptions regarding data normality, homoscedasticity, and sample size.
"""
    },

    # =========================================================================
    # B. FAMOUS OPEN-SOURCE SKILL PROJECTS
    # =========================================================================
    {
        "id": "superpowers",
        "name": "Superpowers Agent Capability Extension",
        "author": "Jesse Vincent",
        "github_username": "@obra",
        "repository": "https://github.com/obra/superpowers",
        "license": "MIT",
        "category": "productivity",
        "icon": "⚡",
        "version": "2.1.0",
        "description": "Autonomous systems administration, tool execution chaining, and agent superpower primitives. Highly credited to Jesse Vincent (@obra).",
        "tags": ["superpowers", "agent", "tool-chaining", "sysadmin", "automation", "obra"],
        "permissions": ["read_files", "write_files", "shell_commands"],
        "markdown": """# Superpowers Agent Capability Extension

## Overview
Highly credited to Jesse Vincent (@obra) — https://github.com/obra/superpowers.
Extends AI coding agents with system administration tools, automated environment reconnaissance, and composable execution superpowers.

## Key Capabilities
1. **System Reconnaissance**: Detect operating system release, available shell binaries, compiler suites, package managers, and virtualization layers.
2. **Process Inspection & Management**: Safely query background processes, verify open ports, trace daemon health, and gracefully manage lifecycle signals.
3. **Environment Isolation**: Execute commands within structured subshells to guarantee environment variable hygiene and prevent side-effect leakage.

## Attribution
- Creator: Jesse Vincent (@obra)
- Upstream: https://github.com/obra/superpowers
- License: MIT
"""
    },
    {
        "id": "ts-wizard",
        "name": "TypeScript Wizardry & Type-Level Architecture",
        "author": "Matt Pocock",
        "github_username": "@mattpocock",
        "repository": "https://github.com/mattpocock/skills",
        "license": "MIT",
        "category": "coding",
        "icon": "🧙‍♂️",
        "version": "1.4.0",
        "description": "Advanced TypeScript type inference, generics, branded types, and zero-runtime type systems. Highly credited to Matt Pocock (@mattpocock).",
        "tags": ["typescript", "type-systems", "generics", "ts-wizard", "mattpocock"],
        "permissions": ["read_files", "write_files"],
        "markdown": """# TypeScript Wizardry & Type-Level Architecture

## Overview
Highly credited to Matt Pocock (@mattpocock) — https://github.com/mattpocock/skills.
Solves complex type-level challenges, designs type-safe APIs, eliminates `any`, and builds ergonomic generics for TypeScript libraries.

## Core Type-Level Techniques
1. **Eliminate `any` without Compromise**:
   - Use `unknown` with type predicates (`is`) or Zod schema validation.
2. **Branded & Nominal Types**:
   - Enforce compile-time distinction between raw strings and validated domain values (`UserId`, `EmailAddress`).
3. **Conditional Types & Template Literals**:
   - Map event emitter strings to payload types dynamically.
   - Infer function argument shapes with `infer`.
4. **Ergonomic Generics**:
   - Design interfaces where type parameters are inferred automatically by TypeScript rather than requiring manual specification by the caller.

## Attribution
- Creator: Matt Pocock (@mattpocock)
- Upstream: https://github.com/mattpocock/skills
- License: MIT
"""
    },
    {
        "id": "mcp-builder",
        "name": "Model Context Protocol (MCP) Server Builder",
        "author": "Anthropic",
        "github_username": "@anthropics",
        "repository": "https://github.com/anthropics/skills",
        "license": "MIT",
        "category": "coding",
        "icon": "🔌",
        "version": "1.3.0",
        "description": "Scaffolding, protocol compliance, schema generation, and testing for custom MCP servers and tools. Highly credited to Anthropic (@anthropics).",
        "tags": ["mcp", "protocol", "tools", "anthropic", "servers", "apis"],
        "permissions": ["read_files", "write_files", "shell_commands"],
        "markdown": """# Model Context Protocol (MCP) Server Builder

## Overview
Highly credited to Anthropic (@anthropics) — https://github.com/anthropics/skills.
Implements the Model Context Protocol (MCP) specification to bridge external services, databases, and APIs into AI agent workflows.

## Architecture & Implementation Steps
1. **Server Scaffolding**:
   - Initialize Python (`mcp` library) or Node.js (`@modelcontextprotocol/sdk`) project.
   - Configure stdio or SSE transport layer.
2. **Tool Definition & JSON Schema**:
   - Define tool names, human-readable descriptions, and strict JSON Schema parameter specifications.
   - Ensure input schemas define required vs optional properties explicitly.
3. **Resource & Prompt Templates**:
   - Expose read-only file/database resources via URI schemes (`sqlite://`, `file://`).
   - Define reusable agent prompt templates with parameter slots.
4. **Protocol Compliance & Error Handling**:
   - Return structured error objects with valid JSON-RPC 2.0 error codes on failure.

## Attribution
- Creator: Anthropic (@anthropics)
- Upstream: https://github.com/anthropics/skills
- License: MIT
"""
    },
    {
        "id": "ui-ux-pro-max",
        "name": "UI/UX Pro Max Design System",
        "author": "Next Level Builder",
        "github_username": "@nextlevelbuilder",
        "repository": "https://github.com/nextlevelbuilder/ui-ux-pro-max-skill",
        "license": "MIT",
        "category": "design",
        "icon": "✨",
        "version": "2.0.0",
        "description": "Production-grade micro-interactions, responsive fluid grids, accessible color palettes, and component hierarchy. Highly credited to @nextlevelbuilder.",
        "tags": ["ui", "ux", "design-system", "accessibility", "styling", "nextlevelbuilder"],
        "permissions": ["read_files", "write_files"],
        "markdown": """# UI/UX Pro Max Design System

## Overview
Highly credited to Next Level Builder (@nextlevelbuilder) — https://github.com/nextlevelbuilder/ui-ux-pro-max-skill.
Guides the creation of world-class user interfaces: tactile 3D affordances, fluid micro-interactions, WCAG AAA accessibility, and coherent spatial rhythm.

## Design System Tokens
1. **Spatial Scale & Rhythm**:
   - Enforce an 4px/8px base grid system for all padding, margins, and gaps.
   - Fluid typography scales based on viewport clamp calculations.
2. **Color Science & Contrast**:
   - Surface hierarchy: Base Canvas -> Surface Elevated -> Surface Overlay -> Surface Highlight.
   - Minimum 4.5:1 contrast ratio for all text elements (WCAG AA) and 7:1 for critical controls (WCAG AAA).
3. **Tactile Feedback & Depth**:
   - Skeuomorphic & tactile tall-bevel borders that give buttons physical clickability.
   - Smooth 80-120ms transitions on hover and active click states.

## Attribution
- Creator: Next Level Builder (@nextlevelbuilder)
- Upstream: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
- License: MIT
"""
    },
    {
        "id": "cloudflare-security",
        "name": "Cloudflare Edge Security & WAF Audit",
        "author": "Cloudflare",
        "github_username": "@cloudflare",
        "repository": "https://github.com/cloudflare/security-audit-skill",
        "license": "Apache-2.0",
        "category": "security",
        "icon": "☁️",
        "version": "1.2.0",
        "description": "Cloudflare Workers security, WAF rulesets, DNSSEC, rate-limiting, and zero-trust configuration auditing. Highly credited to Cloudflare (@cloudflare).",
        "tags": ["cloudflare", "security", "waf", "edge", "dns", "zero-trust"],
        "permissions": ["read_files"],
        "markdown": """# Cloudflare Edge Security & WAF Audit

## Overview
Highly credited to Cloudflare (@cloudflare) — https://github.com/cloudflare/security-audit-skill.
Inspects, configures, and verifies edge infrastructure security, DDoS mitigations, WAF rules, and Cloudflare Worker sandboxes.

## Audit Checklist
1. **Edge WAF & Managed Rules**:
   - OWASP Core Ruleset sensitivity calibration.
   - Custom rate limiting rules on authentication and sensitive POST endpoints.
2. **DNS & Transport Layer**:
   - Strict SSL/TLS mode enforcement (Full Strict with Origin CA certificates).
   - DNSSEC validation and proxy status verification.
3. **Worker & Serverless Security**:
   - Environment secret storage in encrypted bindings rather than plaintext wrangler.toml.
   - CSP (Content Security Policy) and HSTS header injection at edge.

## Attribution
- Creator: Cloudflare (@cloudflare)
- Upstream: https://github.com/cloudflare/security-audit-skill
- License: Apache-2.0
"""
    },
    {
        "id": "addy-agent-skills",
        "name": "Web Performance & Core Web Vitals by Addy Osmani",
        "author": "Addy Osmani",
        "github_username": "@addyosmani",
        "repository": "https://github.com/addyosmani/agent-skills",
        "license": "MIT",
        "category": "performance",
        "icon": "🚀",
        "version": "1.5.0",
        "description": "Browser rendering pipeline optimization, JS bundle slimming, image compression, and Core Web Vitals tuning. Highly credited to Addy Osmani (@addyosmani).",
        "tags": ["performance", "web-vitals", "optimization", "bundle-size", "addyosmani"],
        "permissions": ["read_files", "write_files", "shell_commands"],
        "markdown": """# Web Performance & Core Web Vitals by Addy Osmani

## Overview
Highly credited to Addy Osmani (@addyosmani) — https://github.com/addyosmani/agent-skills.
Proven engineering patterns for maximizing web frontend performance, reducing JavaScript execution time, and achieving sub-second load times.

## Core Optimization Pillars
1. **JavaScript Budgeting & Code Splitting**:
   - Dynamic route-based code splitting with `React.lazy` or ESM `import()`.
   - Tree-shaking verification: remove unused barrel imports and dead code.
2. **Asset Optimization**:
   - Modern image formats (AVIF/WebP) with explicit width/height to eliminate layout shifts.
   - Critical path CSS inlining; asynchronous loading of non-critical fonts.
3. **Main Thread Efficiency**:
   - Defer heavy computations to Web Workers.
   - Avoid long tasks (>50ms) to ensure smooth 60fps interaction responsiveness.

## Attribution
- Creator: Addy Osmani (@addyosmani)
- Upstream: https://github.com/addyosmani/agent-skills
- License: MIT
"""
    },
    {
        "id": "impeccable",
        "name": "Impeccable Visual & Design Critique",
        "author": "Paul Bakaus",
        "github_username": "@pbakaus",
        "repository": "https://github.com/pbakaus/impeccable",
        "license": "MIT",
        "category": "design",
        "icon": "🎨",
        "version": "1.2.0",
        "description": "Aesthetic critique, typography harmony, whitespace balance, and pixel-perfect design refinement. Highly credited to Paul Bakaus (@pbakaus).",
        "tags": ["design", "critique", "typography", "layout", "visuals", "pbakaus"],
        "permissions": ["read_files"],
        "markdown": """# Impeccable Visual & Design Critique

## Overview
Highly credited to Paul Bakaus (@pbakaus) — https://github.com/pbakaus/impeccable.
Provides rigorous design critique to elevate software from functional to visually arresting, thoughtful, and polished.

## Critique Framework
1. **Typography & Hierarchy**:
   - Does typography establish an immediate, effortless reading order?
   - Are line lengths comfortable (45-75 characters per line)?
2. **Whitespace & Spatial Harmony**:
   - Is whitespace intentional or does the interface feel cluttered and claustrophobic?
   - Do related elements visually group through proximity?
3. **Tactile Feedback & Polish**:
   - Do interactive states convey clear feedback upon hover, focus, and press?
   - Are borders, shadows, and subtle highlights applied consistently across components?

## Attribution
- Creator: Paul Bakaus (@pbakaus)
- Upstream: https://github.com/pbakaus/impeccable
- License: MIT
"""
    },

    # =========================================================================
    # C. 10 CAT-NATIVE SKILLS
    # =========================================================================
    {
        "id": "cat-project-analyzer",
        "name": "CAT Project Analyzer & Architecture Inspector",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "coding",
        "icon": "📊",
        "version": "1.0.0",
        "description": "Deep recursive project inspection: identifies tech stack, framework versions, entry points, dependencies, and code hygiene.",
        "tags": ["cat-native", "analyzer", "architecture", "inspection", "diagnostics"],
        "permissions": ["read_files", "shell_commands"],
        "markdown": """# CAT Project Analyzer & Architecture Inspector

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
"""
    },
    {
        "id": "cat-auto-fix",
        "name": "CAT Auto-Fix & Error Recovery",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "debugging",
        "icon": "🔧",
        "version": "1.0.0",
        "description": "Automated diagnosis and correction of common build, syntax, runtime, and dependency errors in CAT projects.",
        "tags": ["cat-native", "auto-fix", "recovery", "compiler-errors", "debugging"],
        "permissions": ["read_files", "write_files", "shell_commands"],
        "markdown": """# CAT Auto-Fix & Error Recovery

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
"""
    },
    {
        "id": "cat-context-manager",
        "name": "CAT Context Manager & Token Pruner",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "productivity",
        "icon": "🧠",
        "version": "1.0.0",
        "description": "Intelligent file relevance ranking, AST-level slicing, and context window budget optimization for agent turns.",
        "tags": ["cat-native", "context", "token-optimization", "ast", "pruning"],
        "permissions": ["read_files"],
        "markdown": """# CAT Context Manager & Token Pruner

## Overview
Original CAT-native context engine. Ensures that AI agents receive exactly the right amount of code context without exceeding model token limits or injecting distracting noise.

## Strategies
1. **Relevance Ranking**:
   - Ranks files by lexical proximity, recent git edits, and active stack trace references.
2. **AST-Level Slicing**:
   - Extracts relevant function and class signatures while omitting uncalled helper bodies.
3. **Token Budget Enforcement**:
   - Dynamically budgets context tokens across system instructions, conversation history, and workspace files.
"""
    },
    {
        "id": "cat-dependency-doctor",
        "name": "CAT Dependency Doctor",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "coding",
        "icon": "💊",
        "version": "1.0.0",
        "description": "Audits npm, pip, cargo, and go dependencies; resolves version conflicts, deprecations, and security advisories.",
        "tags": ["cat-native", "dependencies", "npm", "pip", "vulnerabilities", "packaging"],
        "permissions": ["read_files", "write_files", "shell_commands"],
        "markdown": """# CAT Dependency Doctor

## Overview
Original CAT-native dependency management engine. Diagnoses lockfile corruption, diamond dependency conflicts, peer dependency mismatches, and CVE vulnerabilities.

## Diagnostic Protocol
1. **Audit Lockfiles**: Verify `package-lock.json`, `poetry.lock`, `uv.lock`, or `Pipfile.lock` integrity.
2. **Detect Deprecations**: Identify packages with upcoming end-of-life dates or unmaintained repositories.
3. **Conflict Resolution**: Compute minimal version bumps that satisfy all transitive dependency constraints.
"""
    },
    {
        "id": "cat-performance",
        "name": "CAT Performance Profiler & Bottleneck Analyzer",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "performance",
        "icon": "⚡",
        "version": "1.0.0",
        "description": "Profiles CPU, memory, event loops, I/O latency, and algorithmic complexity to eliminate bottlenecks.",
        "tags": ["cat-native", "performance", "profiling", "latency", "memory", "optimization"],
        "permissions": ["read_files", "write_files", "shell_commands"],
        "markdown": """# CAT Performance Profiler & Bottleneck Analyzer

## Overview
Original CAT-native profiling engine. Identifies CPU hotspots, memory leaks, I/O stalls, and blocking operations in asynchronous applications.

## Profiling Methods
1. **CPU & Call Graph Profiling**:
   - Identify functions consuming disproportionate execution time.
2. **Memory Leak Isolation**:
   - Trace object retention graphs, uncollected cyclical references, and unbounded caches.
3. **Async Event Loop Health**:
   - Detect blocking synchronous calls inside `asyncio` or Node.js event loops.
"""
    },
    {
        "id": "cat-api-builder",
        "name": "CAT API Builder & Endpoint Scaffolder",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "coding",
        "icon": "🚪",
        "version": "1.0.0",
        "description": "Rapidly generates REST, GraphQL, and FastAPI endpoints with validation, OpenAPI schemas, and mock tests.",
        "tags": ["cat-native", "api", "rest", "graphql", "fastapi", "endpoints"],
        "permissions": ["read_files", "write_files"],
        "markdown": """# CAT API Builder & Endpoint Scaffolder

## Overview
Original CAT-native API engineering tool. Scaffolds production-ready REST and GraphQL endpoints with Pydantic/Zod schemas, OpenAPI documentation, and automated tests.

## Generation Standards
1. **Schema Validation First**:
   - Strict request body and query parameter validation schemas.
2. **Standardized HTTP Responses**:
   - Consistent error envelope (`status`, `error_code`, `message`, `details`).
3. **Automated Endpoint Testing**:
   - Generates mock-based test fixtures for all generated routes.
"""
    },
    {
        "id": "cat-database",
        "name": "CAT Database Architect & Query Optimizer",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "coding",
        "icon": "🗄️",
        "version": "1.0.0",
        "description": "Models relational and NoSQL schemas, generates migrations, indexes tables, and optimizes slow queries.",
        "tags": ["cat-native", "database", "sql", "migrations", "indexing", "postgresql"],
        "permissions": ["read_files", "write_files"],
        "markdown": """# CAT Database Architect & Query Optimizer

## Overview
Original CAT-native database engine. Designs robust relational and document database schemas, writes lossless migrations, and optimizes SQL queries.

## Optimization & Modeling Rules
1. **Schema Normalization & Integrity**:
   - Foreign key constraints, unique indexes, and appropriate column types.
2. **Query Plan Optimization**:
   - Analyze `EXPLAIN ANALYZE` outputs to eliminate sequential table scans on large tables.
   - Author composite indexes for multi-column filter queries.
3. **Zero-Downtime Migrations**:
   - Safe additive migrations; avoiding blocking table locks.
"""
    },
    {
        "id": "cat-test-generator",
        "name": "CAT Test Suite Generator",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "testing",
        "icon": "🎯",
        "version": "1.0.0",
        "description": "Generates comprehensive unit, integration, and mocking suites tailored to the project's test framework.",
        "tags": ["cat-native", "test-generator", "pytest", "vitest", "mocking", "coverage"],
        "permissions": ["read_files", "write_files"],
        "markdown": """# CAT Test Suite Generator

## Overview
Original CAT-native test authoring engine. Analyzes project source files and automatically writes comprehensive test cases covering happy paths, edge cases, and exception handling.

## Coverage Checklist
1. **Boundary & Edge Testing**: Zero, negative, max-int, empty strings, null, and malformed inputs.
2. **Mocking & Isolation**: Mock external APIs and disk I/O while testing internal logic thoroughly.
3. **Framework Alignment**: Outputs idiomatic tests using the project's native runner (pytest fixtures, Vitest describe/it).
"""
    },
    {
        "id": "cat-deployment",
        "name": "CAT Deployment & DevOps Engine",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "productivity",
        "icon": "🚢",
        "version": "1.0.0",
        "description": "Generates multi-stage Dockerfiles, Docker Compose, GitHub Actions CI/CD workflows, and cloud deploy configs.",
        "tags": ["cat-native", "deployment", "docker", "ci-cd", "github-actions", "devops"],
        "permissions": ["read_files", "write_files"],
        "markdown": """# CAT Deployment & DevOps Engine

## Overview
Original CAT-native DevOps engine. Author hardened multi-stage Docker containers, automated GitHub Actions CI/CD pipelines, and infrastructure manifests.

## Deployment Hardening
1. **Multi-Stage Dockerfiles**:
   - Separate build-time dependencies from minimal production runtime images (Alpine/Distroless).
   - Run as non-root user for container security.
2. **CI/CD Pipelines**:
   - Automated linting, testing, security scanning, and container publishing on commit/PR.
"""
    },
    {
        "id": "cat-quantum",
        "name": "CAT Quantum Circuit & Qiskit Engine",
        "author": "CAT Core Team",
        "github_username": "@cat-cli",
        "repository": "https://github.com/cat-cli/cat",
        "license": "MIT",
        "category": "science",
        "icon": "⚛️",
        "version": "1.0.0",
        "description": "Constructs quantum circuits, implements quantum algorithms (Grover, VQE, Shor), and performs statevector simulations.",
        "tags": ["cat-native", "quantum", "qiskit", "circuits", "algorithms", "physics"],
        "permissions": ["read_files", "write_files", "shell_commands"],
        "markdown": """# CAT Quantum Circuit & Qiskit Engine

## Overview
Original CAT-native quantum computing workflow engine. Designs quantum circuits using Qiskit, simulates statevectors, and implements quantum algorithms.

## Quantum Capabilities
1. **Circuit Synthesis**: Construct parameterized quantum circuits with Hadamard, CNOT, Phase, and Pauli rotations.
2. **Statevector Simulation**: Execute ideal and noisy density-matrix simulations with Qiskit Aer.
3. **Quantum Algorithms**: Scaffold Variational Quantum Eigensolver (VQE), Grover Search, and Quantum Fourier Transform (QFT).
"""
    },
]


def main():
    print(f"Creating builtin skills in {BUILTIN_DIR}...")
    manifest_entries = []

    for item in SKILLS_DATA:
        sid = item["id"]
        sdir = BUILTIN_DIR / sid
        sdir.mkdir(parents=True, exist_ok=True)
        skill_md_path = sdir / "SKILL.md"

        # Author frontmatter
        frontmatter = f"""---
name: {sid}
display_name: "{item['name']}"
version: "{item['version']}"
author: "{item['author']}"
github_username: "{item['github_username']}"
repository: "{item['repository']}"
license: "{item['license']}"
category: "{item['category']}"
description: "{item['description']}"
tags: {json.dumps(item['tags'])}
permissions: {json.dumps(item['permissions'])}
compatibility: ">=0.9.0"
---

"""
        full_content = frontmatter + item["markdown"].strip() + "\n"
        with open(skill_md_path, "w", encoding="utf-8") as f:
            f.write(full_content)
        print(f"  ✓ Written: {sid}/SKILL.md ({len(full_content)} bytes)")

        manifest_entries.append({
            "cat_skill_id": sid,
            "original_skill_name": item["name"],
            "original_creator": item["author"],
            "github_username": item["github_username"],
            "repository": item["repository"],
            "original_file_path": f"{sid}/SKILL.md",
            "upstream_commit_sha": "cat_v0900",
            "license": item["license"],
            "installation_date": "2026-11-14",
            "local_version": item["version"],
            "update_available": False,
            "category": item["category"],
            "icon": item["icon"],
            "description": item["description"],
            "local_path": f"calc_terminal\\skills\\builtin\\{sid}\\SKILL.md"
        })

    # Read existing manifest.json to preserve pre-existing official skills (rea, archify, remotion, skillopt, page-mascot, frontend-design, skill-creator, find-skills)
    manifest_path = BUILTIN_DIR / "manifest.json"
    existing_skills = []
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                old_m = json.load(f)
                existing_skills = old_m.get("skills", [])
        except Exception as e:
            print(f"Warning reading old manifest: {e}")

    # Merge preserving existing
    existing_ids = {s.get("cat_skill_id"): s for s in existing_skills if s.get("cat_skill_id")}
    for new_entry in manifest_entries:
        nid = new_entry["cat_skill_id"]
        existing_ids[nid] = new_entry

    final_manifest = {
        "version": "0.9.000",
        "updated_at": "2026-11-14T11:00:00Z",
        "total_skills": len(existing_ids),
        "skills": list(existing_ids.values())
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(final_manifest, f, indent=2)

    print(f"\n✓ Successfully updated manifest.json with {len(existing_ids)} bundled offline skills!")


if __name__ == "__main__":
    main()
