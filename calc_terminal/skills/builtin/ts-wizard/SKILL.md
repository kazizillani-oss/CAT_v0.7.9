---
name: ts-wizard
display_name: "TypeScript Wizardry & Type-Level Architecture"
version: "1.4.0"
author: "Matt Pocock"
github_username: "@mattpocock"
repository: "https://github.com/mattpocock/skills"
license: "MIT"
category: "coding"
description: "Advanced TypeScript type inference, generics, branded types, and zero-runtime type systems. Highly credited to Matt Pocock (@mattpocock)."
tags: ["typescript", "type-systems", "generics", "ts-wizard", "mattpocock"]
permissions: ["read_files", "write_files"]
compatibility: ">=0.9.0"
---

# TypeScript Wizardry & Type-Level Architecture

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
