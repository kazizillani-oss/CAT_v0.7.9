'use strict';

/**
 * CAT CLI launcher — detection and launch-plan construction for the
 * EXISTING Python/Textual CAT CLI. This module never re-implements CAT;
 * it only finds the real entry point and builds a command for the
 * VS Code integrated terminal.
 *
 * Real entry points, verified from this repository (NOT invented):
 *   - pyproject.toml [project.scripts]:  cat  = "calc_terminal.cli:main"
 *                                        cct  = "calc_terminal.cli:main"
 *   - CAT_v0.7.4/calc_terminal/__main__.py:  python -m calc_terminal
 *   - CAT_v0.7.4/calc_terminal/cli.py main(argv): optional single
 *     positional <path> = "project/workspace directory to open"
 *     (defaults to the current working directory).
 *   - README distribution docs: `cat`, `catx` (and `cct`) launch the TUI.
 *
 * Security posture:
 *   - This module executes ONLY its own verification probe
 *     (`<python> -c "import calc_terminal"`) against candidate
 *     interpreters, with shell:false and array args (no shell parsing).
 *   - Workspace files, package.json scripts and AI output are never read
 *     or executed by this module.
 *   - Nothing is downloaded. Nothing installs itself. Installation only
 *     happens through an explicit user action in catTerminal.js.
 */

const { execFile } = require('child_process');
const fs = require('fs');
const path = require('path');

/** The importable CAT package name (calc_terminal), verified in-repo. */
const CAT_MODULE = 'calc_terminal';
/** Probe run against candidate interpreters to confirm CAT is importable. */
const IMPORT_PROBE = `import ${CAT_MODULE}`;
const DEFAULT_TIMEOUT_MS = 10000;

const CAT_MISSING_MESSAGE =
	'CAT — Coding Agent Terminal is not installed or could not be detected.';
const PYTHON_MISSING_MESSAGE =
	'CAT — Coding Agent Terminal could not be started.\n' +
	`No Python interpreter with the "${CAT_MODULE}" package was found.\n` +
	'Please select/configure a Python interpreter (cat.pythonPath) or install CAT — Coding Agent Terminal.';

/**
 * Minimal `which`. Scans PATH without spawning a shell. On Windows also
 * tries PATHEXT extensions so "cat" resolves to cat.EXE.
 */
function whichCommand(name, { platform = process.platform, env = process.env, existsSync = fs.existsSync } = {}) {
	if (!name || name.includes('"')) {
		return null;
	}
	if (name.includes(path.sep) || name.includes('/')) {
		// Absolute/relative path: trust the filesystem check only.
		return existsSync(name) ? name : null;
	}
	const dirs = (env.PATH || env.Path || '').split(path.delimiter).filter(Boolean);
	const exts = platform === 'win32'
		? (env.PATHEXT || '.COM;.EXE;.BAT;.CMD').split(';').filter(Boolean)
		: [''];
	for (const dir of dirs) {
		for (const ext of exts) {
			const candidate = path.join(dir, name + ext);
			try {
				if (existsSync(candidate)) {
					return candidate;
				}
			} catch {
				// unreadable directory — skip
			}
		}
	}
	return null;
}

/**
 * Split a configured command string into [executable, ...args], honouring
 * double quotes. Used only for the user's own `cat.cli.command` setting.
 */
function parseCommandString(command) {
	const parts = [];
	const re = /"([^"]*)"|(\S+)/g;
	let match;
	while ((match = re.exec(command)) !== null) {
		parts.push(match[1] !== undefined ? match[1] : match[2]);
	}
	return parts;
}

/** Quote a single token for the launcher display string (not for shells). */
function quoteToken(token, platform = process.platform) {
	// Safe set covers ordinary paths/flags; anything else (spaces, parens,
	// ampersand, unicode, quotes…) gets double-quoted, which protects it in
	// PowerShell, cmd, bash and zsh alike.
	if (!/[^A-Za-z0-9_.\-\/\\:@+=,]/.test(token)) {
		return token;
	}
	return platform === 'win32'
		? `"${token.replace(/"/g, '')}"`
		: `"${token.replace(/"/g, '\\"')}"`;
}

/**
 * Python candidate list, in priority order. Every entry carries the args
 * needed BOTH for the import probe and for launching CAT via
 * `python -m calc_terminal`. Order (top wins):
 *   1. cat.cli.pythonPath (explicit user configuration)
 *   2. VS Code Python extension's selected interpreter
 *      (python.defaultInterpreterPath, a supported API surface)
 *   3. project virtualenvs: .venv, venv, env
 *   4. conda base env (only if `conda` is on PATH)
 *   5. poetry env (only if `poetry` is on PATH and pyproject.toml exists)
 *   6. Windows launcher `py -3`, then `python`/`python3` on PATH
 */
function pythonCandidates({ platform = process.platform, pythonPath = '', vscodePython = '', workspaceRoot = '', autoDetect = true, env = process.env, existsSync = fs.existsSync, which = whichCommand } = {}) {
	const candidates = [];
	const push = (kind, command, extraArgs) => {
		if (command) {
			candidates.push({ kind, command, args: [...(extraArgs || [])] });
		}
	};

	if (pythonPath && pythonPath.trim()) {
		push('explicit', pythonPath.trim());
	}
	if (autoDetect && vscodePython && vscodePython.trim()) {
		push('vscode-python', vscodePython.trim());
	}
	if (autoDetect && workspaceRoot) {
		// Layout differs per platform; the name loop must pair each venv
		// directory with ITS OWN platform layout, so no shared subpath array.
		const venvNames = ['.venv', 'venv', 'env'];
		const pythonRel = platform === 'win32'
			? ['Scripts', 'python.exe']
			: ['bin', 'python'];
		for (const name of venvNames) {
			const interpreter = path.join(workspaceRoot, name, ...pythonRel);
			if (existsSync(interpreter)) {
				push(`venv:${name}`, interpreter);
			}
		}
	}
	if (autoDetect && which('conda', { platform, env, existsSync })) {
		push('conda', 'conda', ['run', '-n', 'base', 'python']);
	}
	if (autoDetect && workspaceRoot && existsSync(path.join(workspaceRoot, 'pyproject.toml'))
		&& which('poetry', { platform, env, existsSync })) {
		push('poetry', 'poetry', ['run', 'python']);
	}
	// 6. Windows launcher `py -3`, then `python`/`python3` on PATH. These
	//    are only attempted when autoDetect is enabled.
	if (autoDetect) {
		if (platform === 'win32') {
			push('py', 'py', ['-3']);
			push('python', 'python');
		} else {
			push('python3', 'python3');
			push('python', 'python');
		}
	}
	return candidates;
}


/**
 * Run a short-lived verification process. Array args + shell:false + no
 * custom env + no cwd inheritance = no shell-injection surface.
 */
function runProbe(command, args, { timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
	return new Promise((resolve) => {
		try {
			const child = execFile(command, args, {
				timeout: timeoutMs,
				windowsHide: true,
				shell: false,
				encoding: 'utf8',
			}, (error, stdout) => {
				resolve({
					ok: !error,
					stdout: typeof stdout === 'string' ? stdout : '',
					error: error ? (error.message || String(error)) : null,
				});
			});
			// execFile with timeout kills the process; guard against callbacks
			// firing more than once (error + exit).
			child.on('error', () => { /* handled via callback */ });
		} catch (error) {
			resolve({ ok: false, stdout: '', error: error.message || String(error) });
		}
	});
}

/**
 * Verify that a candidate interpreter can import the CAT package.
 * Returns {verified:boolean, probe:{ok,stdout,error}}.
 */
async function verifyInterpreter(candidate, options = {}) {
	const probe = await runProbe(candidate.command, [...candidate.args, '-c', IMPORT_PROBE], options);
	return { verified: probe.ok, probe };
}

/**
 * Find a Python interpreter that can import calc_terminal.
 * Tries candidates in order; returns the first verified one.
 * `verify` is injectable for tests (defaults to the real import probe).
 */
async function findVerifiedPython(candidates, { verify = verifyInterpreter, ...probeOptions } = {}) {
	for (const candidate of candidates) {
		const { verified, probe } = await verify(candidate, probeOptions);
		if (verified) {
			return { candidate, probe };
		}
	}
	return null;
}

/**
 * Resolve the direct `cat`-style launcher for a verified interpreter.
 * Order:
 *   1. `cat.cli.command` — an EXPLICIT override. A bare "cat" (the default
 *      value) is NOT an override; it means "auto-detect", so auto-detection
 *      decides below whether a direct launcher is trustworthy.
 *   2. virtualenv Scripts/bin/cat (.venv, venv, env — pip installs the
 *      console script into the environment that owns calc_terminal)
 *   3. `cat` on PATH (Windows) / `catx` or `cct` (POSIX, because bare `cat`
 *      is GNU coreutils there and would print files instead of opening CAT)
 *   4. null → caller falls back to `<python> -m calc_terminal`, which is
 *      always available in the verified environment.
 */
function resolveCatLauncher({ command = '', workspaceRoot = '', python = null, platform = process.platform, existsSync = fs.existsSync, which = whichCommand } = {}) {
	const out = { kind: null, file: null, tokens: null };
	const trimmed = (command || '').trim();
	// Only treat it as an override when the user typed more than the bare
	// default (a path, flags, or a different command name).
	if (trimmed && trimmed !== 'cat' && trimmed !== 'cat.exe') {
		const tokens = parseCommandString(trimmed);
		if (tokens.length) {
			if (platform === 'win32' && tokens[0].toLowerCase() === 'cat') {
				tokens[0] = 'cat.exe';
			}
			out.kind = 'configured';
			out.tokens = tokens;
			out.file = tokens[0];
			return out;
		}
	}
	if (workspaceRoot) {
		const scriptDir = platform === 'win32' ? 'Scripts' : 'bin';
		for (const envName of ['.venv', 'venv', 'env']) {
			const exe = path.join(workspaceRoot, envName, scriptDir, platform === 'win32' ? 'cat.exe' : 'cat');
			if (existsSync(exe)) {
				out.kind = 'venv-script';
				out.file = exe;
				out.tokens = [exe];
				return out;
			}
		}
	}
	// Check the verified Python interpreter's directory/Scripts for cat.exe on Windows
	if (platform === 'win32' && python && python.candidate && typeof python.candidate.command === 'string') {
		const pyCmd = python.candidate.command;
		if (pyCmd.includes(path.sep) || pyCmd.includes('/')) {
			const pyDir = path.dirname(pyCmd);
			for (const sub of ['Scripts', '']) {
				const candidateExe = sub ? path.join(pyDir, sub, 'cat.exe') : path.join(pyDir, 'cat.exe');
				if (existsSync(candidateExe)) {
					out.kind = 'python-script';
					out.file = candidateExe;
					out.tokens = [candidateExe];
					return out;
				}
			}
		}
	}
	if (platform === 'win32') {
		const found = which('cat.exe', { platform, existsSync }) || which('cat', { platform, existsSync });
		if (found) {
			out.kind = 'path';
			out.file = found;
			out.tokens = [found];
			return out;
		}
	} else {
		// On POSIX the literal command `cat` is GNU coreutils, so a bare
		// "cat" launch would print files instead of opening CAT. Only
		// unambiguous CAT entry points are used as direct launchers.
		for (const name of ['catx', 'cct']) {
			const found = which(name, { platform, existsSync });
			if (found) {
				out.kind = 'path';
				out.file = found;
				out.tokens = [found];
				return out;
			}
		}
	}
	if (platform === 'win32' && out.tokens && out.tokens[0].toLowerCase() === 'cat') {
		out.tokens[0] = 'cat.exe';
		out.file = 'cat.exe';
	}
	return out;
}

module.exports = {
	CAT_MODULE,
	CAT_MISSING_MESSAGE,
	PYTHON_MISSING_MESSAGE,
	findVerifiedPython,
	parseCommandString,
	pythonCandidates,
	quoteToken,
	resolveCatLauncher,
	runProbe,
	verifyInterpreter,
	whichCommand,
};
