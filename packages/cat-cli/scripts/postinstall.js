#!/usr/bin/env node
/**
 * @cat/cli — Post-installation diagnostic and setup notice
 */

const { execSync } = require('child_process');

function banner() {
  const isBun = typeof Bun !== 'undefined';
  const runtime = isBun ? `Bun v${Bun.version}` : `Node.js ${process.version}`;

  console.log(`
\x1b[35m┌────────────────────────────────────────────────────────┐\x1b[0m
\x1b[35m│\x1b[0m   \x1b[1m\x1b[36m🐾 CAT CLI (Coding Agent Terminal) Installed!\x1b[0m         \x1b[35m│\x1b[0m
\x1b[35m│\x1b[0m   Runtime: \x1b[33m${runtime.padEnd(41)}\x1b[0m\x1b[35m│\x1b[0m
\x1b[35m│\x1b[0m                                                        \x1b[35m│\x1b[0m
\x1b[35m│\x1b[0m   Usage:                                               \x1b[35m│\x1b[0m
\x1b[35m│\x1b[0m     \x1b[32mcat\x1b[0m           Launch autonomous CAT TUI interface   \x1b[35m│\x1b[0m
\x1b[35m│\x1b[0m     \x1b[32mcatx\x1b[0m          Safe alias (guaranteed no PS conflict)\x1b[35m│\x1b[0m
\x1b[35m│\x1b[0m     \x1b[32mcat --help\x1b[0m    Inspect command-line options & flags  \x1b[35m│\x1b[0m
\x1b[35m│\x1b[0m     \x1b[32mcat /mode\x1b[0m     Select active AI Kitties & agents     \x1b[35m│\x1b[0m
\x1b[35m└────────────────────────────────────────────────────────┘\x1b[0m
`);

  if (process.platform === 'win32') {
    try {
      execSync('powershell -NoProfile -NonInteractive -Command "if (Test-Path Alias:cat) { Remove-Item Alias:cat -Force -ErrorAction SilentlyContinue }"', {
        stdio: 'ignore'
      });
    } catch (e) {}
  }
}

try {
  banner();
} catch (e) {
  // Silent fail during CI / headless
}

