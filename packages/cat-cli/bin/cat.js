#!/usr/bin/env node
/**
 * @cat/cli — Launcher for CAT (Coding Agent Terminal)
 * Compatible with Node.js and Bun runtime.
 */

const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

function findPython() {
  // Check virtual environment or custom override first
  if (process.env.CAT_PYTHON && fs.existsSync(process.env.CAT_PYTHON)) {
    return process.env.CAT_PYTHON;
  }

  const candidates = process.platform === 'win32'
    ? ['python', 'py', 'python3']
    : ['python3', 'python'];

  for (const cmd of candidates) {
    try {
      const ver = execSync(`${cmd} -c "import sys; print(sys.version_info.major)"`, {
        stdio: ['ignore', 'pipe', 'ignore'],
        encoding: 'utf-8'
      }).trim();
      if (ver === '3') {
        return cmd;
      }
    } catch (e) {
      // Continue search
    }
  }
  return null;
}

function isCatInstalled(pythonCmd) {
  try {
    execSync(`${pythonCmd} -c "import calc_terminal"`, {
      stdio: ['ignore', 'ignore', 'ignore']
    });
    return true;
  } catch (e) {
    return false;
  }
}

function installCat(pythonCmd) {
  console.log('\x1b[36m🐾 @cat/cli: Installing core CAT terminal runtime...\x1b[0m');
  try {
    execSync(`${pythonCmd} -m pip install --upgrade cct-cli`, {
      stdio: 'inherit'
    });
    return true;
  } catch (e) {
    console.error('\x1b[31m❌ Failed to automatically install cct-cli via pip.\x1b[0m');
    console.error(`Please run: ${pythonCmd} -m pip install cct-cli`);
    return false;
  }
}

function main() {
  const pythonCmd = findPython();
  if (!pythonCmd) {
    console.error('\x1b[31m❌ Python 3 was not found on your system PATH.\x1b[0m');
    console.error('CAT CLI requires Python 3.10+ (https://www.python.org/downloads/).');
    process.exit(1);
  }

  // Check if calc_terminal is ready
  if (!isCatInstalled(pythonCmd)) {
    // If running in development repo, check if current directory or parent contains calc_terminal
    const localDir = path.resolve(__dirname, '../../');
    const hasLocal = fs.existsSync(path.join(localDir, 'calc_terminal'));
    if (hasLocal) {
      process.env.PYTHONPATH = localDir + (process.env.PYTHONPATH ? path.delimiter + process.env.PYTHONPATH : '');
    } else {
      const ok = installCat(pythonCmd);
      if (!ok) process.exit(1);
    }
  }

  const args = ['-m', 'calc_terminal', ...process.argv.slice(2)];

  // Spawn Python CAT process with inherited stdio for full interactive TUI support
  const child = spawn(pythonCmd, args, {
    stdio: 'inherit',
    env: process.env,
    shell: false
  });

  // Forward termination signals seamlessly
  const forwardSignal = (signal) => {
    if (child && !child.killed) {
      try {
        child.kill(signal);
      } catch (err) {}
    }
  };

  process.on('SIGINT', () => forwardSignal('SIGINT'));
  process.on('SIGTERM', () => forwardSignal('SIGTERM'));

  child.on('error', (err) => {
    console.error(`\x1b[31m❌ Failed to launch CAT process: ${err.message}\x1b[0m`);
    process.exit(1);
  });

  child.on('close', (code) => {
    process.exit(code ?? 0);
  });
}

main();

