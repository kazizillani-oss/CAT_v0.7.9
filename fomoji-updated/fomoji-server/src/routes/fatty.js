'use strict';

const path = require('path');
const http = require('http');
const { spawn } = require('child_process');
const express = require('express');

const router = express.Router();

const FATTY_URL = process.env.FATTY_CAT_URL || 'http://localhost:8765';
const FATTY_PORT = 8765;
const FATTY_HOST = '127.0.0.1';

/**
 * Check if Fatty CAT server is responding on /health
 */
function checkFattyHealth(timeoutMs = 1500) {
  return new Promise((resolve) => {
    const req = http.get(
      {
        host: FATTY_HOST,
        port: FATTY_PORT,
        path: '/health',
        timeout: timeoutMs,
      },
      (res) => {
        let raw = '';
        res.on('data', (chunk) => { raw += chunk; });
        res.on('end', () => {
          if (res.statusCode === 200) {
            try {
              const data = JSON.parse(raw);
              return resolve({ running: true, data });
            } catch {
              return resolve({ running: true, data: { status: 'ok' } });
            }
          }
          resolve({ running: false });
        });
      }
    );

    req.on('error', () => resolve({ running: false }));
    req.on('timeout', () => {
      req.destroy();
      resolve({ running: false });
    });
  });
}

/**
 * Locate the CAT root directory where calc_terminal resides
 */
function findCatDir() {
  const fs = require('fs');
  const candidates = [
    process.env.CAT_DIR,
    path.resolve(__dirname, '../../../../CAT_v0.7.4'),
    path.resolve(__dirname, '../../../CAT_v0.7.4'),
    path.resolve(process.cwd(), '../CAT_v0.7.4'),
    path.resolve(process.cwd(), '../../CAT_v0.7.4'),
  ].filter(Boolean);

  for (const dir of candidates) {
    if (fs.existsSync(path.join(dir, 'calc_terminal', 'web', 'server.py'))) {
      return dir;
    }
  }
  return null;
}

/**
 * GET /api/fatty/status
 * Returns { running: boolean, url: string, ... }
 */
router.get('/status', async (req, res) => {
  try {
    const health = await checkFattyHealth(1200);
    res.json({
      running: health.running,
      url: FATTY_URL,
      info: health.data || null,
    });
  } catch (err) {
    res.status(500).json({ running: false, error: err.message });
  }
});

/**
 * POST /api/fatty/start
 * Starts the Fatty CAT server in the background if not already running
 */
router.post('/start', async (req, res) => {
  try {
    const initialCheck = await checkFattyHealth(1000);
    if (initialCheck.running) {
      return res.json({
        success: true,
        running: true,
        alreadyRunning: true,
        url: FATTY_URL,
      });
    }

    const catDir = findCatDir();
    if (!catDir) {
      return res.status(500).json({
        success: false,
        running: false,
        error: 'CAT directory not found on system',
      });
    }

    const pythonCmd = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');

    // Spawn server process detached
    const child = spawn(pythonCmd, ['-m', 'calc_terminal.web.server'], {
      cwd: catDir,
      detached: true,
      stdio: 'ignore',
      windowsHide: true,
    });

    child.unref();

    // Poll until /health is ready (up to 12s)
    const deadline = Date.now() + 12000;
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 400));
      const health = await checkFattyHealth(800);
      if (health.running) {
        return res.json({
          success: true,
          running: true,
          alreadyRunning: false,
          url: FATTY_URL,
          info: health.data || null,
        });
      }
    }

    res.status(504).json({
      success: false,
      running: false,
      error: 'Fatty CAT server start timed out',
    });
  } catch (err) {
    res.status(500).json({
      success: false,
      running: false,
      error: err.message,
    });
  }
});

module.exports = router;
