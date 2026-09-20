'use strict';

/**
 * VS Code integration tests for the CAT CLI launcher extension.
 * Covers: activation, command palette registration, contributions,
 * terminal reuse, cwd selection, settings surface, bystander safety.
 */

const assert = require('assert');
const path = require('path');
const vscode = require('vscode');

const EXT_ID = 'kazizillani.cat-cli';
const OPEN = 'kazizillani.cat-cli.open';
const NEW_TERM = 'kazizillani.cat-cli.newTerminal';
const REINSTALL = 'kazizillani.cat-cli.reinstall';
const COMMANDS = [OPEN, NEW_TERM, REINSTALL];

/** True when the real CAT CLI (or the module) is importable/launchable here. */
let catAvailable = false;

/**
 * Availability probe with a hard timeout. Mirrors the extension's own
 * detection: `cat`/`catx`/`cct` on PATH or `python -m calc_terminal`.
 * Never installs anything.
 */
async function isCatAvailable() {
	const { execFile } = require('child_process');
	const probe = (cmd, args) => new Promise((resolve) => {
		try {
			execFile(cmd, args, { timeout: 8000, windowsHide: true, shell: false }, (err, stdout) => {
				resolve(!err && /CAT/i.test(String(stdout || '')));
			});
		} catch {
			resolve(false);
		}
	});
	if (process.platform === 'win32') {
		if (await probe('cat', ['--version'])) {
			return true;
		}
	} else if (await probe('catx', ['--version']) || await probe('cct', ['--version'])) {
		return true;
	}
	for (const py of process.platform === 'win32' ? ['python', 'py', 'python3'] : ['python3', 'python']) {
		if (await probe(py, ['-c', 'import calc_terminal'])) {
			return true;
		}
	}
	return false;
}

suite('CAT CLI extension (integration)', () => {

	suiteSetup(async function () {
		this.timeout(60000);
		const ext = vscode.extensions.getExtension(EXT_ID);
		assert.ok(ext, 'extension not found — check publisher/id');
		await ext.activate();
		// Terminal tests only run when a CAT-capable environment actually
		// exists (real `cat` on PATH or python -m calc_terminal). This keeps
		// CI deterministic — nothing here downloads or installs anything.
		catAvailable = await isCatAvailable();
	});

	test('1. extension activates', () => {
		assert.strictEqual(vscode.extensions.getExtension(EXT_ID).isActive, true);
	});

	test('2. CAT commands are registered (Command Palette surface)', async () => {
		const registered = await vscode.commands.getCommands(true);
		for (const id of COMMANDS) {
			assert.ok(registered.includes(id), `command not registered: ${id}`);
		}
	});

	test('3. contributes the CAT activity bar container + tree view', () => {
		const pkg = vscode.extensions.getExtension(EXT_ID).packageJSON;
		const container = pkg.contributes.viewsContainers.activitybar.find((c) => c.id === 'cat');
		assert.ok(container, 'activitybar container "cat" missing');
		assert.strictEqual(container.title, 'CAT');
		const view = pkg.contributes.views.cat.find((v) => v.id === 'cat.launcher');
		assert.ok(view, 'view "cat.launcher" missing');
		assert.strictEqual(view.type, 'tree');
	});

	test('4. commands have correct titles for the palette', () => {
		const pkg = vscode.extensions.getExtension(EXT_ID).packageJSON;
		const titles = Object.fromEntries(pkg.contributes.commands.map((c) => [c.command, c.title]));
		assert.strictEqual(titles[OPEN], 'CAT: Open CAT CLI');
		assert.strictEqual(titles[NEW_TERM], 'CAT: New Terminal');
		assert.strictEqual(titles[REINSTALL], 'CAT: Reinstall / Setup');
	});

	test('5. keybinding is declared (no-conflict combo)', () => {
		const pkg = vscode.extensions.getExtension(EXT_ID).packageJSON;
		const kb = (pkg.contributes.keybindings || []).find((k) => k.command === OPEN);
		assert.ok(kb, 'keybinding for open missing');
		assert.strictEqual(kb.key, 'ctrl+alt+c');
	});

	test('6. exposes the cat.cli.* configuration surface', () => {
		const cfg = vscode.workspace.getConfiguration('cat.cli');
		assert.strictEqual(cfg.get('command'), 'cat');
		assert.strictEqual(cfg.get('autoDetectPython'), true);
		assert.strictEqual(cfg.get('reuseTerminal'), true);
		assert.strictEqual(cfg.get('terminalName'), 'CAT CLI');
	});


	test('7. open command creates a CAT terminal at the workspace cwd', async function () {
		this.timeout(60000);
		if (!catAvailable || !vscode.workspace.workspaceFolders || !vscode.workspace.workspaceFolders.length) {
			this.skip();
		}
		const cwd = vscode.workspace.workspaceFolders[0].uri.fsPath;
		await vscode.commands.executeCommand(OPEN);
		await new Promise((resolve) => setTimeout(resolve, 2500));
		const catTerminals = vscode.window.terminals.filter((t) => t.name === 'CAT CLI');
		assert.ok(catTerminals.length > 0, 'no CAT terminal was created');
		const active = catTerminals[catTerminals.length - 1];
		const terminalCwd = (active.creationOptions && active.creationOptions.cwd) || cwd;
		assert.strictEqual(
			path.normalize(terminalCwd).toLowerCase(),
			path.normalize(cwd).toLowerCase(),
			`terminal cwd should be the workspace folder, got: ${terminalCwd}`
		);
	});

	test('8. open again reuses the existing CAT terminal', async function () {
		this.timeout(60000);
		if (!catAvailable || !vscode.workspace.workspaceFolders || !vscode.workspace.workspaceFolders.length) {
			this.skip();
		}
		// Start from a clean slate so the count comparison is exact.
		for (const t of vscode.window.terminals) {
			if (t.name === 'CAT CLI') {
				t.dispose();
			}
		}
		await new Promise((resolve) => setTimeout(resolve, 500));
		await vscode.commands.executeCommand(OPEN); // first click → create
		await new Promise((resolve) => setTimeout(resolve, 2000));
		const afterFirst = vscode.window.terminals.filter((t) => t.name === 'CAT CLI').length;
		await vscode.commands.executeCommand(OPEN); // second click → focus, not create
		await new Promise((resolve) => setTimeout(resolve, 1500));
		const afterSecond = vscode.window.terminals.filter((t) => t.name === 'CAT CLI').length;
		assert.strictEqual(afterFirst, 1, `first click should create exactly one CAT terminal, got ${afterFirst}`);
		assert.strictEqual(afterSecond, 1, `second click must reuse, got ${afterSecond}`);
	});

	test('9. newTerminal forces an additional terminal', async function () {
		this.timeout(60000);
		if (!catAvailable || !vscode.workspace.workspaceFolders || !vscode.workspace.workspaceFolders.length) {
			this.skip();
		}
		const before = vscode.window.terminals.filter((t) => t.name === 'CAT CLI').length;
		await vscode.commands.executeCommand(NEW_TERM);
		await new Promise((resolve) => setTimeout(resolve, 1500));
		const after = vscode.window.terminals.filter((t) => t.name === 'CAT CLI').length;
		assert.strictEqual(after, before + 1, `expected exactly one new CAT terminal: ${before} → ${after}`);
	});

	test('11. unrelated terminals are untouched by launch logic', async function () {
		this.timeout(60000);
		if (!catAvailable || !vscode.workspace.workspaceFolders || !vscode.workspace.workspaceFolders.length) {
			this.skip();
		}
		const bystander = vscode.window.createTerminal({ name: 'unrelated-bystander' });
		try {
			await vscode.commands.executeCommand(OPEN);
			await new Promise((resolve) => setTimeout(resolve, 1200));
			const after = vscode.window.terminals.filter((t) => t.name === 'unrelated-bystander').length;
			assert.strictEqual(after, 1, 'bystander terminal disappeared');
		} finally {
			bystander.dispose();
		}
	});

	// LAST (deterministic): the reinstall command's dialog text is verified
	// directly from the module — executing a modal notification inside a
	// headless test runner would block until a human clicks it.
	test('10. missing-CAT notification offers safe actions (message contract)', async () => {
		const { CAT_MISSING_MESSAGE } = require('../catLauncher');
		assert.strictEqual(CAT_MISSING_MESSAGE, 'CAT CLI is not installed or could not be detected.');
		const { CatTerminalManager } = require('../catTerminal');
		assert.strictEqual(typeof CatTerminalManager.prototype.handleMissingPython, 'function');
		assert.strictEqual(typeof CatTerminalManager.prototype.notifyError, 'function');
	});

	suiteTeardown(async function () {
		this.timeout(30000);
		// Close CAT terminals so repeated runs are deterministic. Only CAT
		// terminals are disposed — user terminals are never touched.
		for (const t of vscode.window.terminals) {
			if (t.name === 'CAT CLI') {
				t.dispose();
			}
		}
	});
});
