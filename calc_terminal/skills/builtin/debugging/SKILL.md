---
name: debugging
display_name: "Systematic Root-Cause Debugging"
version: "1.3.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "debugging"
description: "Isolates errors, traces stack traces, hypothesizes root causes, and implements verified surgical fixes with regression prevention."
tags: ["debugging", "troubleshooting", "stack-trace", "root-cause", "fixes"]
permissions: ["read_files", "write_files", "shell_commands"]
compatibility: ">=0.9.0"
---

# Systematic Root-Cause Debugging

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
