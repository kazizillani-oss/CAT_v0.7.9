'use strict';

const path = require('path');
const express = require('express');
const session = require('express-session');

const { PORT, SESSION_SECRET, RP_ID, ORIGIN, IS_PRODUCTION } = require('./config');
const {
  correlationIdMiddleware,
  securityHeadersMiddleware,
  corsMiddleware,
  errorHandler,
} = require('./security');

const webauthnRouter = require('./routes/webauthn');
const { router: authRouter } = require('./routes/auth');
const oauthRouter = require('./routes/oauth');
const authCardRouter = require('./routes/authCard');
const connectorRouter = require('./routes/connector');
const { router: groupsRouter } = require('./routes/groups');
const fattyRouter = require('./routes/fatty');

const app = express();

// Disable Express fingerprinting header
app.disable('x-powered-by');

// Security & Correlation ID Middlewares (applied to every response)
app.use(correlationIdMiddleware);
app.use(securityHeadersMiddleware);
app.use(corsMiddleware);

// Request parsing with body size limits to prevent DoS attacks
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: false, limit: '1mb' }));

// Session handling with strict cookie flags
app.use(
  session({
    name: 'fomoji.sid',
    secret: SESSION_SECRET,
    resave: false,
    saveUninitialized: false,
    cookie: {
      httpOnly: true,
      sameSite: 'lax',
      secure: IS_PRODUCTION || ORIGIN.startsWith('https://'),
      maxAge: 1000 * 60 * 60 * 24 * 30, // 30 days
    },
  })
);

app.use('/api/webauthn', webauthnRouter);
app.use('/api', authRouter);
app.use('/api', oauthRouter);
app.use('/api/auth-card', authCardRouter);
app.use('/api/connector', connectorRouter);
app.use('/api/groups', groupsRouter);
app.use('/api/fatty', fattyRouter);

// Launch real OS browser (Edge/Chrome on Windows) for local desktop CAT passkey ceremony.
// Strictly restricted to local development loopback and anchored to ORIGIN.
app.all('/api/open-system-browser', (req, res) => {
  if (IS_PRODUCTION) {
    return res.status(404).json({ error: 'not_found' });
  }

  const clientIp = req.ip || req.socket?.remoteAddress || '';
  const isLoopback = clientIp === '127.0.0.1' || clientIp === '::1' || clientIp === '::ffff:127.0.0.1';
  if (!isLoopback) {
    return res.status(403).json({ error: 'forbidden', correlationId: req.correlationId });
  }

  const rawTarget = (req.body && req.body.url) || req.query.url || `${ORIGIN}/passkey.html`;
  let parsedUrl;
  try {
    parsedUrl = new URL(String(rawTarget), ORIGIN);
  } catch {
    return res.status(400).json({ error: 'invalid_target_origin', correlationId: req.correlationId });
  }

  const expectedOrigin = new URL(ORIGIN).origin;
  if (parsedUrl.origin !== expectedOrigin) {
    return res.status(400).json({ error: 'invalid_target_origin', correlationId: req.correlationId });
  }

  const safeTarget = parsedUrl.href;
  try {
    const { spawn } = require('child_process');
    if (process.platform === 'win32') {
      spawn('cmd.exe', ['/c', 'start', '""', safeTarget], { windowsHide: true, windowsVerbatimArguments: true });
    } else if (process.platform === 'darwin') {
      spawn('open', [safeTarget]);
    } else {
      spawn('xdg-open', [safeTarget]);
    }
    return res.json({ ok: true, opened: safeTarget });
  } catch (err) {
    console.error(`[ERROR correlationId=${req.correlationId}] failed to open browser:`, err);
    return res.status(500).json({ error: 'failed_to_open', correlationId: req.correlationId });
  }
});

// Serve Archify interactive architecture & workflow diagrams
const archifyDir = path.resolve(__dirname, '../../../../.archify');
app.use('/archify', express.static(archifyDir, { dotfiles: 'allow' }));

// The Fomoji static front-end with dotfiles blocked
app.use(express.static(path.join(__dirname, '..', 'public'), { dotfiles: 'ignore', index: ['index.html'] }));

// Production-grade centralized error handler (sanitizes all 500 errors and includes correlationId)
app.use(errorHandler);

app.listen(PORT, () => {
  console.log(`Fomoji server running at ${ORIGIN} [mode: ${IS_PRODUCTION ? 'production' : 'development'}]`);
  console.log(`WebAuthn RP ID: ${RP_ID}`);
});

