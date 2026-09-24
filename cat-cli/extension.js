'use strict';

/**
 * CAT — Coding Agent Terminal — VS Code extension entry point.
 *
 * This extension is a LAUNCHER/INTEGRATION BRIDGE only. The real CAT
 * application is the existing Python/Textual CLI (calc_terminal), which
 * runs inside the VS Code integrated terminal. Nothing here reimplements
 * CAT, opens a fake webview UI, or executes anything without user action.
 *
 * Commands:
 *   - CAT: Open      — Opens CAT in a real VS Code integrated terminal
 *   - CAT: Restart   — Closes and reopens CAT terminal
 *   - CAT: Close     — Closes the CAT terminal
 *   - CAT: Check Installation — Verifies CAT is properly installed
 */

const vscode = require('vscode');
const { CatTerminalManager } = require('./catTerminal');

/** @param {vscode.ExtensionContext} context */
function activate(context) {
	const output = vscode.window.createOutputChannel('CAT — Coding Agent Terminal');
	output.appendLine('CAT — Coding Agent Terminal extension activating…');

	const manager = new CatTerminalManager(context, output);

	const disposable = vscode.Disposable.from(
		// CAT: Open — reuse the CAT terminal if one exists.
		vscode.commands.registerCommand('kazizillani.cat.open', async () => {
			const result = await manager.launch();
			if (result === 'failed') {
				vscode.window.showErrorMessage('Failed to start CAT — Coding Agent Terminal. Check the output for details.');
			}
		}),

		// CAT: Restart — force close and reopen CAT terminal.
		vscode.commands.registerCommand('kazizillani.cat.restart', async () => {
			await manager.closeTerminal();
			const result = await manager.launch({ forceNew: true });
			if (result === 'failed') {
				vscode.window.showErrorMessage('Failed to restart CAT — Coding Agent Terminal. Check the output for details.');
			}
		}),

		// CAT: Close — close the CAT terminal.
		vscode.commands.registerCommand('kazizillani.cat.close', async () => {
			await manager.closeTerminal();
		}),

		// CAT: Check Installation — verify CAT is properly installed.
		vscode.commands.registerCommand('kazizillani.cat.checkInstallation', async () => {
			await manager.checkInstallation();
		}),

		// Status bar: one native item that opens CAT.
		(() => {
			const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 90);
			status.command = 'kazizillani.cat.open';
			status.text = '$(terminal) CAT';
			status.tooltip = 'Open CAT — Coding Agent Terminal in the integrated terminal';
			status.show();
			return status;
		})()
	);

	context.subscriptions.push(disposable);
	output.appendLine('CAT — Coding Agent Terminal extension activated (launcher bridge; real CAT runs in the integrated terminal).');
}

function deactivate() {
	// CAT runs in the user's terminal; nothing to tear down.
}

module.exports = {
	activate,
	deactivate,
};
