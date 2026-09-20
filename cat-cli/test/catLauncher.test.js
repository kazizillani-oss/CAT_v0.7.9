'use strict';

/**
 * Pure unit tests for catLauncher.js — run in plain Node, no VS Code
 * dependency. All filesystem/process access is injected as parameters.
 */

const assert = require('assert');
const path = require('path');
const {
	CAT_MODULE,
	findVerifiedPython,
	parseCommandString,
	pythonCandidates,
	quoteToken,
	resolveCatLauncher,
	runProbe,
	verifyInterpreter,
	whichCommand,
} = require('../catLauncher');

const win32 = process.platform === 'win32';

suite('catLauncher (pure)', () => {

	suite('whichCommand', () => {
		test('finds an executable on PATH (no shell)', () => {
			const dir = win32 ? 'C:\\tools\\bin' : '/usr/local/bin';
			const found = whichCommand('cat', {
				platform: win32 ? 'win32' : 'linux',
				env: { PATH: dir },
				existsSync: (p) => p === path.join(dir, win32 ? 'cat.EXE' : 'cat'),
			});
			assert.ok(found, 'expected to find cat');
			assert.ok(found.includes('tools'));
		});

		test('resolves .EXE extensions on Windows', () => {
			if (!win32) {
				return;
			}
			const dir = 'C:\\Python312\\Scripts';
			const found = whichCommand('cat', {
				platform: 'win32',
				env: { PATH: dir, PATHEXT: '.COM;.EXE;.BAT;.CMD' },
				existsSync: (p) => p === path.join(dir, 'cat.EXE'),
			});
			assert.strictEqual(found, path.join(dir, 'cat.EXE'));
		});

		test('returns null when not found and rejects quoted input', () => {
			assert.strictEqual(whichCommand('definitely-missing-tool-xyz', {
				env: { PATH: '' }, existsSync: () => false,
			}), null);
			assert.strictEqual(whichCommand('foo"bar', { env: { PATH: '' } }), null);
		});

		test('absolute path is checked directly', () => {
			const abs = win32 ? 'C:\\Program Files (x86)\\cat.exe' : '/opt/cat/bin/cat';
			const found = whichCommand(abs, { existsSync: (p) => p === abs });
			assert.strictEqual(found, abs);
		});
	});

	suite('quoteToken / parseCommandString', () => {
		test('quotes tokens with spaces, parentheses, ampersand, unicode', () => {
			for (const tricky of [
				'C:\\Users\\ADMIN\\My Stuff (dev)\\cat.exe',
				'/home/üsér/PR (тест)/bin/cat',
				'a&b.txt',
			]) {
				const q = quoteToken(tricky);
				assert.ok(q.startsWith('"') && q.endsWith('"'), `not quoted: ${q}`);
			}
		});

		test('leaves plain tokens unquoted', () => {
			assert.strictEqual(quoteToken('cat'), 'cat');
			assert.strictEqual(quoteToken('-m'), '-m');
		});

		test('parseCommandString honours double quotes', () => {
			assert.deepStrictEqual(
				parseCommandString('"C:\\My Tools\\py.exe" -m calc_terminal'),
				['C:\\My Tools\\py.exe', '-m', 'calc_terminal']
			);
			assert.deepStrictEqual(parseCommandString('cat --flag "some path"'), ['cat', '--flag', 'some path']);
		});
	});

	suite('pythonCandidates', () => {
		test('explicit pythonPath wins over everything', () => {
			const list = pythonCandidates({
				platform: 'win32',
				pythonPath: 'C:\\custom\\python.exe',
				vscodePython: 'C:\\vscode\\python.exe',
				workspaceRoot: 'C:\\proj',
				autoDetect: true,
				which: () => null,
				existsSync: () => false,
			});
			assert.strictEqual(list[0].kind, 'explicit');
			assert.strictEqual(list[0].command, 'C:\\custom\\python.exe');
		});

		test('autoDetect=false keeps only the explicit path', () => {
			const list = pythonCandidates({
				platform: 'win32',
				pythonPath: 'C:\\custom\\python.exe',
				vscodePython: 'C:\\vscode\\python.exe',
				workspaceRoot: 'C:\\proj',
				autoDetect: false,
				which: () => 'C:\\conda\\conda.exe',
				existsSync: () => true,
			});
			assert.strictEqual(list.length, 1);
			assert.strictEqual(list[0].kind, 'explicit');
		});

		test('workspace venv dirs are detected (.venv, venv, env)', () => {
			const dirs = new Set(['C:\\proj\\.venv\\Scripts\\python.exe', 'C:\\proj\\venv\\bin\\python']);
			const list = pythonCandidates({
				platform: 'win32',
				pythonPath: '',
				vscodePython: '',
				workspaceRoot: 'C:\\proj',
				autoDetect: true,
				which: () => null,
				existsSync: (p) => dirs.has(p),
			});
			const kinds = list.map((c) => c.kind);
			assert.ok(kinds.includes('venv:.venv'), `kinds=${kinds}`);
			assert.ok(kinds.includes('python'), `kinds=${kinds}`);
		});

		test('linux: python3 before python, venv uses bin/', () => {
			// Build the expected interpreter path with the SAME path.join
			// semantics the module uses (Windows host normalizes '/').
			const existing = path.join('/proj', 'venv', 'bin', 'python');
			const list = pythonCandidates({
				platform: 'linux',
				pythonPath: '',
				vscodePython: '',
				workspaceRoot: '/proj',
				autoDetect: true,
				which: () => null,
				existsSync: (p) => p === existing,
			});
			const pyIdx = list.findIndex((c) => c.kind === 'python3');
			const plainIdx = list.findIndex((c) => c.kind === 'python');
			assert.ok(pyIdx !== -1 && plainIdx !== -1 && pyIdx < plainIdx);
			const venv = list.find((c) => c.kind === 'venv:venv');
			assert.ok(venv && venv.command === existing, `expected ${existing}, got ${venv && venv.command}`);
		});

		test('conda candidate only when conda exists; carries run args', () => {
			const list = pythonCandidates({
				platform: 'linux',
				pythonPath: '',
				vscodePython: '',
				workspaceRoot: '/proj',
				autoDetect: true,
				which: (n) => (n === 'conda' ? '/opt/conda' : null),
				existsSync: () => true,
			});
			const conda = list.find((c) => c.kind === 'conda');
			assert.ok(conda && conda.args.join(' ').includes('run'));
		});
	});
	suite('runProbe / verifyInterpreter (live interpreter)', () => {
		test('probing a real interpreter works (shell:false array argv)', async () => {
			const probe = await runProbe(process.execPath, ['-e', 'process.stdout.write("ok")'], { timeoutMs: 8000 });
			assert.ok(probe.ok, `probe failed: ${probe.error}`);
			assert.strictEqual(probe.stdout.trim(), 'ok');
		});

		test('verifyInterpreter returns a boolean verdict', async () => {
			const bad = await runProbe(process.execPath, ['-e', 'require("definitely-not-a-real-module-xyz")'], { timeoutMs: 8000 });
			assert.strictEqual(bad.ok, false);
			const result = await verifyInterpreter({ kind: 'test', command: process.execPath, args: [] }, { timeoutMs: 8000 });
			// calc_terminal probably isn't importable from node; but if it is
			// (dev box with a .pth), accept it — the verdict logic is what
			// matters, not this machine's state.
			assert.strictEqual(typeof result.verified, 'boolean');
		});

		test('findVerifiedPython picks the first successful candidate', async () => {
			const candidates = [
				{ kind: 'bad', command: 'definitely-missing-xyz', args: [] },
				{ kind: 'good', command: process.execPath, args: ['-e', 'process.stdout.write("ok")'] },
			];
			// Real probe would run node with '-c IMPORT_PROBE' (wrong flag);
			// inject a verifier that mirrors what verifyInterpreter does.
			const verify = async (candidate) => {
				const probe = await runProbe(candidate.command, [...candidate.args], { timeoutMs: 8000 });
				return { verified: probe.ok, probe };
			};
			const found = await findVerifiedPython(candidates, { verify, timeoutMs: 8000 });
			assert.ok(found);
			assert.strictEqual(found.candidate.kind, 'good');
		});

		test('findVerifiedPython returns null when nothing verifies', async () => {
			const candidates = [
				{ kind: 'bad1', command: 'definitely-missing-xyz', args: [] },
				{ kind: 'bad2', command: 'also-missing-abc', args: [] },
			];
			assert.strictEqual(await findVerifiedPython(candidates, { timeoutMs: 5000 }), null);
		});
	});

	suite('resolveCatLauncher', () => {
		test('user-configured command takes precedence', () => {
			const out = resolveCatLauncher({
				command: '"C:\\My Tools\\cat.exe" --debug',
				workspaceRoot: 'C:\\proj',
				platform: 'win32',
				which: () => null,
				existsSync: () => true,
			});
			assert.strictEqual(out.kind, 'configured');
			assert.strictEqual(out.tokens[0], 'C:\\My Tools\\cat.exe');
			assert.ok(out.tokens.includes('--debug'));
		});

		test('venv Scripts/cat.exe wins over PATH on Windows', () => {
			const venvCat = 'C:\\proj\\.venv\\Scripts\\cat.exe';
			const out = resolveCatLauncher({
				command: 'cat', // bare default → auto-detect, not an override
				workspaceRoot: 'C:\\proj',
				platform: 'win32',
				which: () => 'C:\\PATH\\cat.EXE',
				existsSync: (p) => p === venvCat,
			});
			assert.strictEqual(out.kind, 'venv-script');
			assert.strictEqual(out.file, venvCat);
		});

		test('PATH cat is used on Windows', () => {
			const out = resolveCatLauncher({
				command: 'cat',
				workspaceRoot: 'C:\\proj',
				platform: 'win32',
				which: () => 'C:\\Python312\\Scripts\\cat.EXE',
				existsSync: () => false,
			});
			assert.strictEqual(out.kind, 'path');
			assert.ok(/cat\.EXE$/i.test(out.file));
		});

		test('POSIX: bare `cat` is NOT used (coreutils shadow), catx/cct are', () => {
			const out = resolveCatLauncher({
				command: 'cat',
				workspaceRoot: '/proj',
				platform: 'linux',
				which: (n) => (n === 'cat' ? '/usr/bin/cat' : n === 'catx' ? '/usr/local/bin/catx' : null),
				existsSync: () => false,
			});
			assert.strictEqual(out.kind, 'path');
			assert.strictEqual(out.file, '/usr/local/bin/catx');
		});

		test('null launcher when nothing available → python -m fallback', () => {
			const out = resolveCatLauncher({
				command: 'cat',
				workspaceRoot: '/proj',
				platform: 'linux',
				which: (n) => (n === 'cat' ? '/usr/bin/cat' : null),
				existsSync: () => false,
			});
			assert.strictEqual(out.kind, null);
			assert.strictEqual(out.tokens, null);
		});
	});

	test('CAT module name matches the real package (calc_terminal)', () => {
		assert.strictEqual(CAT_MODULE, 'calc_terminal');
	});
});

