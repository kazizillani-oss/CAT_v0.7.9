'use strict';

/**
 * CAT terminal manager — creates/reuses the VS Code integrated terminal
 * that runs the EXISTING Python CAT CLI, and reports problems in plain
 * language with explicit user actions only.
 *
 * Guarantees:
 *   - terminal.cwd is the active VS Code workspace folder.
 *   - A "CAT" terminal is reused instead of opening new ones every click.
 *   - Unrelated user terminals are never touched.
 *   - Nothing installs or downloads without an explicit user click.
 *   - Notifications are rate-limited (no spam).
 */

const vscode = require('vscode');
const {
	CAT_MISSING_MESSAGE,
	findVerifiedPython,
	pythonCandidates,
	quoteToken,
	resolveCatLauncher,
} = require('./catLauncher');

const DOC_URL = 'https://github.com/kazizillani-oss/CAT_v0.7.9';
const SAME_ERROR_COOLDOWN_MS = 60000;

class CatTerminalManager {
	/**
	 * @param {vscode.ExtensionContext} context
	 * @param {import('vscode').OutputChannel} output
	 */
	constructor(context, output) {
		this.context = context;
		this.output = output;
		/** @type {Map<string, {terminal: vscode.Terminal, at: number}>} */
		this._terminals = new Map();
		this._disposable = vscode.window.onDidCloseTerminal((terminal) => {
			for (const [key, entry] of this._terminals) {
				if (entry.terminal === terminal) {
					this._terminals.delete(key);
				}
			}
		});
		context.subscriptions.push(this._disposable);
	}

	log(message) {
		this.output.appendLine(`[${new Date().toLocaleTimeString()}] ${message}`);
	}

	/** Configuration snapshot for one launch decision. */
	getConfig() {
		const cfg = vscode.workspace.getConfiguration('cat');
		return {
			executable: cfg.get('executable', 'cat'),
			launchArguments: cfg.get('launchArguments', []),
			pythonPath: cfg.get('pythonPath', ''),
			autoDetectPython: cfg.get('autoDetectPython', true),
			reuseTerminal: cfg.get('reuseTerminal', true),
			autoStart: cfg.get('autoStart', false),
			terminalName: 'CAT',
		};
	}

	/**
	 * Pick the cwd for the CAT terminal:
	 *  1. workspace folder containing the active editor's file
	 *  2. first workspace folder
	 *  3. undefined (VS Code then uses its own default cwd)
	 */
	resolveCwd() {
		const folders = vscode.workspace.workspaceFolders || [];
		if (!folders.length) {
			return undefined;
		}
		const activeUri = vscode.window.activeTextEditor && vscode.window.activeTextEditor.document.uri;
		if (activeUri && activeUri.scheme === 'file') {
			const folder = vscode.workspace.getWorkspaceFolder(activeUri);
			if (folder) {
				return folder.uri.fsPath;
			}
		}
		return folders[0].uri.fsPath;
	}

	/** VS Code Python extension's selected interpreter, when detectable. */
	getVscodePython() {
		try {
			const pyCfg = vscode.workspace.getConfiguration('python');
			const selected = pyCfg && pyCfg.get('defaultInterpreterPath');
			if (typeof selected === 'string') {
				return selected;
			}
		} catch {
			// Python extension not installed — fine.
		}
		return '';
	}

	terminalKey(name, cwd) {
		return cwd ? `${name}::${cwd}` : name;
	}

	reuseExisting(name, cwd) {
		if (!this.getConfig().reuseTerminal) {
			return null;
		}
		const key = this.terminalKey(name, cwd);
		const entry = this._terminals.get(key);
		if (!entry) {
			return null;
		}
		// Exit code 0 = clean exit (user quit CAT normally): terminal is
		// stale, so forget it. Other codes mean a crash we already reported.
		const cached = entry.terminal.exitStatus;
		if (typeof cached === 'object' && cached !== null && 'code' in cached && cached.code === 0) {
			this._terminals.delete(key);
			return null;
		}
		entry.at = Date.now();
		entry.terminal.show();
		return entry.terminal;
	}

	/**
	 * Build the exact argv used to launch CAT, given a verified Python.
	 */
	buildLaunchArgs(python, launcher, workspaceRoot) {
		const config = this.getConfig();
		// CAT's documented CLI argument for a project/workspace directory is
		// a bare positional path (see calc_terminal/cli.py --help).
		const args = workspaceRoot ? [workspaceRoot] : [];
		// Add user-specified launch arguments
		const extraArgs = Array.isArray(config.launchArguments) ? config.launchArguments : [];
		if (launcher && launcher.tokens) {
			return { command: launcher.tokens[0], args: [...launcher.tokens.slice(1), ...extraArgs, ...args] };
		}
		// python -m calc_terminal is the real documented fallback
		// (calc_terminal/__main__.py exists and delegates to cli:main).
		return { command: python.candidate.command, args: [...python.candidate.args, '-m', 'calc_terminal', ...extraArgs, ...args] };
	}

	/** Human-readable one-line summary of what will be executed. */
	describeLaunch(launch, python) {
		const tokens = [launch.command, ...launch.args].map((t) => quoteToken(t)).join(' ');
		const source = python && python.candidate ? ` (${python.candidate.kind})` : '';
		return `${tokens}${source}`;
	}

	/**
	 * Launch CAT. This is the only place the extension starts a process,
	 * and it does so through VS Code's terminal API (visible to the user).
	 * @returns {Promise<'launched'|'reused'|'cancelled'|'failed'>}
	 */
	async launch({ forceNew = false } = {}) {
		const config = this.getConfig();
		const cwd = this.resolveCwd();

		// 1. Reuse an existing CAT terminal when enabled.
		if (!forceNew) {
			const existing = this.reuseExisting(config.terminalName, cwd);
			if (existing) {
				this.log('reused existing CAT terminal');
				return 'reused';
			}
		}

		// 2. Verify Python + CAT availability. This is the ONLY place we
		//    execute anything, and it's just `python -c "import calc_terminal"`.
		const workspaceRoot = cwd;
		const candidates = pythonCandidates({
			platform: process.platform,
			pythonPath: config.pythonPath,
			vscodePython: this.getVscodePython(),
			workspaceRoot,
			autoDetect: config.autoDetectPython,
		});
		const python = await findVerifiedPython(candidates);
		if (!python) {
			this.log('no verified Python interpreter with calc_terminal found');
			await this.handleMissingPython();
			return 'failed';
		}

		// 3. Prefer the real `cat`/`catx`/`cct` launcher, fall back to
		//    `python -m calc_terminal` (both are the project's own entry points).
		//    {workspace} in the configured command expands to the cwd so a
		//    custom command can pin the project path explicitly.
		let commandOverride = config.executable;
		if (commandOverride && commandOverride.includes('{workspace}')) {
			commandOverride = commandOverride.split('{workspace}').join(workspaceRoot || '.');
		}
		const launcher = resolveCatLauncher({
			command: commandOverride,
			workspaceRoot,
			platform: process.platform,
		});
		const launch = this.buildLaunchArgs(python, launcher, workspaceRoot);
		this.log(`launching CAT: ${this.describeLaunch(launch, python)}`);

		// 4. Create the terminal. VS Code runs argv through the user's
		//    default shell profile with proper argument quoting — we never
		//    interpolate into a shell string ourselves.
		const terminal = vscode.window.createTerminal({
			name: config.terminalName,
			cwd: cwd || undefined,
			env: { CAT_VSCODE_LAUNCH: '1' },
			isTransient: false,
		});
		terminal.show();
		terminal.sendText([launch.command, ...launch.args].map((t) => quoteToken(t)).join(' '), true);

		const key = this.terminalKey(config.terminalName, cwd);
		this._terminals.set(key, { terminal, at: Date.now() });

		// 5. Watch for crashes; a clean exit (code 0) means the user quit
		//    CAT normally and needs no message.
		this.context.subscriptions.push(
			vscode.window.onDidCloseTerminal((closed) => {
				if (closed !== terminal) {
					return;
				}
				const status = closed.exitStatus;
				if (status && typeof status.code === 'number' && status.code !== 0) {
					this.notifyError(
						`CAT CLI exited with code ${status.code}. Check the terminal output above for details.`
					);
				}
			})
		);
		return 'launched';
	}

	/** Rate-limited error notification (prevents notification spam). */
	notifyError(message) {
		const now = Date.now();
		if (this._lastError && this._lastError.message === message
			&& now - this._lastError.at < SAME_ERROR_COOLDOWN_MS) {
			return;
		}
		this._lastError = { message, at: now };
		this.output.appendLine(`ERROR: ${message}`);
		vscode.window.showErrorMessage(message);
	}

	/**
	 * CAT is missing (no verified Python/env). Explains what is missing and
	 * offers safe, user-initiated actions only.
	 */
	async handleMissingPython() {
		const action = await vscode.window.showErrorMessage(
			CAT_MISSING_MESSAGE,
			'Install CAT',
			'Open Documentation',
			'Cancel'
		);
		if (action === 'Install CAT') {
			// User asked for it. Open a terminal at the workspace and type
			// the install command VISIBLY — the user sees and can edit it
			// before it runs. No background process, no silent download.
			const cwd = this.resolveCwd();
			const terminal = vscode.window.createTerminal({
				name: 'CAT CLI — install',
				cwd: cwd || undefined,
			});
			terminal.show();
			const pip = process.platform === 'win32' ? 'pip' : 'pip3';
			terminal.sendText(`${pip} install cct-ai-ide`, true);
			this.output.appendLine('user chose Install CAT: typed pip command into a visible terminal');
		} else if (action === 'Open Documentation') {
			vscode.env.openExternal(vscode.Uri.parse(DOC_URL));
		}
		// 'Cancel' / dismiss → do nothing.
	}

	/**
	 * Close the CAT terminal if it exists.
	 */
	async closeTerminal() {
		const config = this.getConfig();
		const cwd = this.resolveCwd();
		const key = this.terminalKey(config.terminalName, cwd);
		const entry = this._terminals.get(key);
		if (entry && entry.terminal) {
			entry.terminal.dispose();
			this._terminals.delete(key);
			this.log('CAT terminal closed');
		}
	}

	/**
	 * Check if CAT is properly installed and show status.
	 */
	async checkInstallation() {
		const config = this.getConfig();
		const cwd = this.resolveCwd();
		const workspaceRoot = cwd;

		this.log('Checking CAT installation...');

		const candidates = pythonCandidates({
			platform: process.platform,
			pythonPath: config.pythonPath,
			vscodePython: this.getVscodePython(),
			workspaceRoot,
			autoDetect: config.autoDetectPython,
		});
		const python = await findVerifiedPython(candidates);

		if (!python) {
			await this.handleMissingPython();
			return;
		}

		const launcher = resolveCatLauncher({
			command: config.executable,
			workspaceRoot,
			platform: process.platform,
		});

		const describe = launcher.tokens
			? launcher.tokens.join(' ')
			: `${python.candidate.command} ${python.candidate.args.join(' ')} -m calc_terminal`;

		vscode.window.showInformationMessage(
			`CAT is installed (${python.candidate.kind}). Command: ${describe}`
		);
		this.log(`CAT check passed: ${describe}`);
	}

	dispose() {
		this._disposable.dispose();
		this._terminals.clear();
	}
}

module.exports = { CatTerminalManager, DOC_URL };
