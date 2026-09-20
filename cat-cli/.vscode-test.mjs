import { defineConfig } from '@vscode/test-cli';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
// Stable scratch workspace so cwd/reuse tests exercise a real folder.
const ws = path.join(here, '.tmp-workspace');
fs.mkdirSync(ws, { recursive: true });

export default defineConfig([
	{
		files: 'test/**/*.test.js',
	},
	{
		// Same tests, now with a workspace folder — enables the terminal
		// cwd / reuse / bystander integration tests (they skip without one).
		files: 'test/**/*.test.js',
		launchArgs: [ws, '--disable-extensions'],
	},
]);
