---
name: cat-deployment
display_name: "CAT Deployment & DevOps Engine"
version: "1.0.0"
author: "CAT Core Team"
github_username: "@cat-cli"
repository: "https://github.com/cat-cli/cat"
license: "MIT"
category: "productivity"
description: "Generates multi-stage Dockerfiles, Docker Compose, GitHub Actions CI/CD workflows, and cloud deploy configs."
tags: ["cat-native", "deployment", "docker", "ci-cd", "github-actions", "devops"]
permissions: ["read_files", "write_files"]
compatibility: ">=0.9.0"
---

# CAT Deployment & DevOps Engine

## Overview
Original CAT-native DevOps engine. Author hardened multi-stage Docker containers, automated GitHub Actions CI/CD pipelines, and infrastructure manifests.

## Deployment Hardening
1. **Multi-Stage Dockerfiles**:
   - Separate build-time dependencies from minimal production runtime images (Alpine/Distroless).
   - Run as non-root user for container security.
2. **CI/CD Pipelines**:
   - Automated linting, testing, security scanning, and container publishing on commit/PR.
