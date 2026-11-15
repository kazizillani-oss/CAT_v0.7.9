---
name: addy-agent-skills
display_name: "Web Performance & Core Web Vitals by Addy Osmani"
version: "1.5.0"
author: "Addy Osmani"
github_username: "@addyosmani"
repository: "https://github.com/addyosmani/agent-skills"
license: "MIT"
category: "performance"
description: "Browser rendering pipeline optimization, JS bundle slimming, image compression, and Core Web Vitals tuning. Highly credited to Addy Osmani (@addyosmani)."
tags: ["performance", "web-vitals", "optimization", "bundle-size", "addyosmani"]
permissions: ["read_files", "write_files", "shell_commands"]
compatibility: ">=0.9.0"
---

# Web Performance & Core Web Vitals by Addy Osmani

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
