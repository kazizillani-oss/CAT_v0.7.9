'use strict';

const path = require('path');
const express = require('express');
const session = require('express-session');

const { PORT, SESSION_SECRET, RP_ID, ORIGIN } = require('./config');
const webauthnRouter = require('./routes/webauthn');
const { router: authRouter } = require('./routes/auth');
const oauthRouter = require('./routes/oauth');
const authCardRouter = require('./routes/authCard');
const connectorRouter = require('./routes/connector');
const { router: groupsRouter } = require('./routes/groups');
const fattyRouter = require('./routes/fatty');

const app = express();

app.use(express.json());
// Apple's OAuth callback arrives as a cross-site form POST
// (response_mode=form_post) rather than a query-string GET like every
// other provider — this is what lets routes/oauth.js read req.body for it.
app.use(express.urlencoded({ extended: false }));

// NOTE: express-session defaults to MemoryStore, which is fine for local
// dev (this whole thing resets on restart, same as before) but is NOT
// safe for a real multi-instance deployment — swap in connect-sqlite3,
// connect-redis, or similar before this goes further than your laptop.
app.use(
  session({
    name: 'fomoji.sid',
    secret: SESSION_SECRET,
    resave: false,
    saveUninitialized: false,
    cookie: {
      httpOnly: true,
      sameSite: 'lax',
      secure: ORIGIN.startsWith('https://'),
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

// Launch real OS browser (Edge/Chrome on Windows) for WebAuthn passkey ceremony
app.all('/api/open-system-browser', (req, res) => {
  const target = (req.body && req.body.url) || req.query.url || `${ORIGIN}/passkey.html`;
  try {
    const { exec } = require('child_process');
    const safeTarget = String(target).replace(/["`$;]/g, '');
    if (process.platform === 'win32') {
      exec(`start "" "${safeTarget}"`);
    } else if (process.platform === 'darwin') {
      exec(`open "${safeTarget}"`);
    } else {
      exec(`xdg-open "${safeTarget}"`);
    }
    return res.json({ ok: true, opened: safeTarget });
  } catch (err) {
    return res.status(500).json({ error: 'failed_to_open', message: err.message });
  }
});

// The existing Fomoji static front-end (the zip you already have) — drop
// its contents into /public and every page + the passkey JS below load
// from the same origin as the API, which WebAuthn requires anyway.
app.use(express.static(path.join(__dirname, '..', 'public')));

// Safety net for /api/* only: Express 5 auto-forwards thrown/rejected
// route errors here, but with no handler at all it falls through to
// Express's default HTML error page. fomoji-auth.js's request() does
// `res.json().catch(() => ({}))`, so an HTML response silently becomes
// `{}` client-side and every such failure shows the same generic
// "Something went wrong" — even when the real cause (and a specific,
// useful error code) is available. This turns any future uncaught /api
// error into real JSON instead of a swallowed one.
app.use('/api', (err, req, res, next) => {
  console.error('[fomoji:api] unhandled error on %s %s —', req.method, req.originalUrl, err);
  if (res.headersSent) return next(err);
  res.status(500).json({ error: 'server_error' });
});

app.listen(PORT, () => {
  console.log(`Fomoji server running at ${ORIGIN}`);
  console.log(`WebAuthn RP ID: ${RP_ID}`);
});
