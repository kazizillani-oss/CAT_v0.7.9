---
name: skill-creator
description: Comprehensive guidelines, validation checks, and templates for designing, authoring, benchmarking, and packaging reusable Agent Skills with YAML frontmatter, execution constraints, and tool handoffs. Highly credited to Anthropic (@anthropic).
version: 1.0.0
author: Anthropic & Claude Quickstarts Team
license: MIT
repository: https://github.com/anthropics/skills/tree/main/skills/skill-creator
category: tools
icon: 🛠️
---

# Skill Creator — Agent Skill Authoring & Packaging

The **Skill Creator** equips coding agents with the official methodology for authoring, testing, and packaging production-grade Agent Skills.

## Attribution & Credit
- **Original Creator**: Anthropic (`@anthropic`) & Claude Quickstarts Team
- **Upstream Repository**: https://github.com/anthropics/skills/tree/main/skills/skill-creator
- **License**: MIT
- **Adapted For**: CAT CLI v0.9 Agent Skills Ecosystem

---

## 1. Skill Anatomy

Every production Agent Skill follows a standardized structure:
```text
<skill-directory>/
├── SKILL.md                 # Primary instruction file with YAML frontmatter
├── scripts/                 # Optional helper utilities & scripts
├── references/              # Optional extended documentation & API references
└── examples/                # Optional exemplar input/output workflows
```

## 2. YAML Frontmatter Specification

The top of every `SKILL.md` must contain strict YAML frontmatter delimited by `---`:
```yaml
---
name: your-skill-slug        # Lowercase, alphanumeric and hyphens only
description: Concise 1-2 sentence description of when and how to activate this skill.
version: 1.0.0               # Semantic versioning
author: Creator Name (@handle)
license: MIT
repository: https://github.com/owner/repo
category: coding | planning | tools | design | research
icon: ⚡
---
```

## 3. Core Authoring Rules

1. **Clear Trigger Conditions**:
   State explicitly when the agent should activate the skill and when it should defer to existing native tools or other agents.
2. **Deterministic Step-by-Step Execution**:
   Provide ordered, actionable execution steps (Phase 1: Inspection, Phase 2: Implementation, Phase 3: Verification).
3. **Progressive Disclosure**:
   Keep the initial description compact for low-token indexing; reserve detailed code samples and deep API references for when the skill is explicitly activated.
4. **Tool Safety & Permissions**:
   Explicitly declare file system, network, or process execution requirements.
5. **No Regressions Guarantee**:
   Always require running existing unit tests and checking for side-effects before completing work.
