# Installing CAT CLI via Paru (Arch Linux AUR) & Bun

## 1. Arch Linux (Paru / Yay / AUR)

CAT CLI is packaged for Arch Linux and AUR helpers:

```bash
# Using paru
paru -S cat-cli

# Using yay
yay -S cat-cli

# Manual makepkg installation
cd packaging/paru
makepkg -si
```

### Launch CAT CLI
```bash
cat-cli
# Or using the short alias:
cat
```

---

## 2. Bun Package Execution & Global Install

CAT CLI can be installed and launched instantly with [Bun](https://bun.sh):

```bash
# Global install with Bun
bun install -g @cat/cli

# Run immediately without global installation
bunx @cat/cli
```

---

## 3. NPM Package Execution & Global Install

```bash
# Global install with npm
npm install -g @cat/cli

# Run immediately with npx
npx @cat/cli
```

---

## Inbuilt MCP Skills Included

CAT CLI v0.9.000 includes 6 high-performance built-in skills with full attribution:
- **REA skill**: Autonomous code execution and recursive task completion (Creator: Morluto, `@morluto`)
- **Archify**: Automated architectural pattern analysis and codebase mapping (Creator: tt-a1i, `@tt-a1i`)
- **Remotion**: Programmatic video creation in React and animated visual pipelines (Creator: Jonny Burger & Remotion Dev, `@remotion-dev`)
- **SkillOpt**: Autonomous prompt optimization and skill distillation (Creator: Microsoft Research, `@microsoft`)
- **Page-Mascot**: Responsive cursor-tracking interactive companion (Creator: nilbuild, `@nilbuild`)
- **Frontend-Design**: Production design system compliance and UI engineering (Creator: Anthropic Quickstarts, `@anthropic`)

