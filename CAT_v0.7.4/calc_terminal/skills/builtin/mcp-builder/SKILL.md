---
name: mcp-builder
display_name: "Model Context Protocol (MCP) Server Builder"
version: "1.3.0"
author: "Anthropic"
github_username: "@anthropics"
repository: "https://github.com/anthropics/skills"
license: "MIT"
category: "coding"
description: "Scaffolding, protocol compliance, schema generation, and testing for custom MCP servers and tools. Highly credited to Anthropic (@anthropics)."
tags: ["mcp", "protocol", "tools", "anthropic", "servers", "apis"]
permissions: ["read_files", "write_files", "shell_commands"]
compatibility: ">=0.9.0"
---

# Model Context Protocol (MCP) Server Builder

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
