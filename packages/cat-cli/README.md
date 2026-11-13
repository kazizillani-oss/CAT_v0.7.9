# @cat/cli — Coding Agent Terminal

[![npm version](https://img.shields.io/npm/v/@cat/cli.svg?style=flat-square&color=89b4fa)](https://www.npmjs.com/package/@cat/cli)
[![Bun](https://img.shields.io/badge/Bun-Compatible-fbf0df?style=flat-square&logo=bun)](https://bun.sh)
[![License: MIT](https://img.shields.io/badge/License-MIT-a6e3a1.svg?style=flat-square)](LICENSE)

**CAT CLI** is an autonomous AI coding assistant, Model Context Protocol (MCP) client, and skeuomorphic terminal workstation designed for high-velocity software engineering, reasoning, and system design.

---

## 🚀 Quick Install

### Via npm
```bash
npm install -g @cat/cli
```

### Run instantly with npx
```bash
npx @cat/cli
```

### Via Bun (Ultra-Fast Startup)
```bash
bun install -g @cat/cli
```
or
```bash
bunx @cat/cli
```

### Via pnpm / yarn
```bash
pnpm add -g @cat/cli
# or
yarn global add @cat/cli
```

---

## ⚡ Quick Start

```bash
# Launch interactive terminal TUI
cat

# Open a specific folder directly into workspace
cat /path/to/project

# Run headless query or task
cat -p "Analyze the authentication architecture in src/"
```

---

## 🧠 Inbuilt MCP Skills & Extensions

CAT CLI comes pre-loaded with premier agent skills and full attribution to their creators:

- **REA — Reasoning & Execution Architecture**: Dual-track reasoning & hypothesis verification. Created by Morluto ([@morluto](https://github.com/morluto/rea)).
- **Archify — Architecture & Blueprinting**: Modular system mapping and structural constraints. Created by tt-a1i ([@tt-a1i](https://github.com/tt-a1i/archify)).
- **Remotion — Code-Driven Video Synthesis**: Programmatic video creation with React. Created by Jonny Burger & Remotion ([@remotion-dev](https://github.com/remotion-dev/skills)).
- **SkillOpt — Skill & Context Optimizer**: Token pruning and tool execution optimization. Created by Microsoft Research ([@microsoft](https://github.com/microsoft/skillopt)).
- **Page Mascot — Interactive Cursor Companion**: Real-time cursor-tracking companion mascot. Created by nilbuild ([@nilbuild](https://github.com/nilbuild/page-mascot)).
- **Frontend Design — Modern UI/UX Systems**: 3D skeuomorphic bevels, fluid responsive layouts, and contrast science. (Anthropic Quickstarts Standards [@anthropic](https://github.com/anthropics/anthropic-quickstarts)).

---

## 🔌 Model Context Protocol (MCP)

CAT CLI natively supports local and remote MCP servers:
```bash
/mcp list          # List active MCP servers
/mcp connect <id>  # Connect to an MCP server
/mcp tools <id>    # Inspect tools provided by the server
```

All connected MCP tools automatically integrate into CAT's Extensions & Component Manager.

---

## 📜 License

MIT © Kazi Zillani

