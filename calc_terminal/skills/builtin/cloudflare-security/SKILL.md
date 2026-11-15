---
name: cloudflare-security
display_name: "Cloudflare Edge Security & WAF Audit"
version: "1.2.0"
author: "Cloudflare"
github_username: "@cloudflare"
repository: "https://github.com/cloudflare/security-audit-skill"
license: "Apache-2.0"
category: "security"
description: "Cloudflare Workers security, WAF rulesets, DNSSEC, rate-limiting, and zero-trust configuration auditing. Highly credited to Cloudflare (@cloudflare)."
tags: ["cloudflare", "security", "waf", "edge", "dns", "zero-trust"]
permissions: ["read_files"]
compatibility: ">=0.9.0"
---

# Cloudflare Edge Security & WAF Audit

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
