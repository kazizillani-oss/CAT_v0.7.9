---
name: find-skills
description: Search, discover, inspect, compare, and safely install relevant agent skills and MCP servers from GitHub repositories, packages, registries, and community catalogues. Highly credited to Vercel Labs (@vercel-labs).
version: 1.0.0
author: Vercel Labs (@vercel-labs)
license: MIT
repository: https://github.com/vercel-labs/skills/blob/main/skills/find-skills/SKILL.md
category: tools
icon: 🔍
---

# Find Skills — Agent Skills Discovery & Registry Search

The **Find Skills** system enables agents and users to search, evaluate, and install skills across public GitHub repositories, verified registries, and community packages.

## Attribution & Credit
- **Original Creator**: Vercel Labs (`@vercel-labs`) & Contributors
- **Upstream Repository**: https://github.com/vercel-labs/skills/blob/main/skills/find-skills/SKILL.md
- **License**: MIT
- **Adapted For**: CAT CLI v0.9 Agent Skills & MCP Ecosystem

---

## 1. Discovery Methodology

When a user requests a capability not present in the local runtime:
1. **Catalog Search**:
   Scan local manifest and remote repositories for relevant `SKILL.md` or MCP server manifests.
2. **Quality Evaluation**:
   Inspect the skill repository for:
   - Clear YAML frontmatter with valid name and description
   - Absence of path traversal or destructive command executions
   - Proper license declaration (MIT, Apache 2.0, BSD)
   - Creator attribution and verified provenance
3. **Safe Progressive Installation**:
   - Inspect files before mounting.
   - Install into local sandbox directory (`.cat/skills/` or `calc_terminal/skills/imported/`).
   - Register in runtime catalog without restarting the host CLI.

## 2. Recommendation Protocol

When presenting skills to the user:
- Present the skill name, creator, repository link, and concise purpose.
- Highlight required permissions (e.g., file read/write, network access).
- Allow 1-click install or terminal CLI installation (`cat skill install <id>`).
