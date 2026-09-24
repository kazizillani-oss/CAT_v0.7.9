'use strict';
// Fomoji Connector System (spec: "connector.py + connector.js + connector.html").
//
// Fomoji owns identity + authentication. This file never touches a
// password or a passkey — it only ever hands a *scoped, revocable*
// connector_token to an application (CAT, a future project) once a real
// Fomoji identity has explicitly approved that application's permission
// request. A CLI/desktop/Python client has no browser of its own, so it
// can't just redirect through the normal login page the way a web app
// would — the device-authorization flow below (/device/start,
// /device/poll, /device/approve, /device/deny) is the standard shape for
// that case (the same pattern `gh auth login`/`docker login` use), and it
// is the ONLY path a non-browser client goes through. A browser client
// that already has a Fomoji session uses the simpler direct /connect.
//
// Nothing here re-implements login, registration, or credential checks —
// every route below either requires an existing Fomoji session
// (requireAuth) or a previously-issued connector_token, never a
// password.
const express = require('express');
const crypto = require('crypto');
const db = require('../db');
const { sha256Hex } = require('../password');
const { PERMISSIONS, sanitizePermissions } = require('../connectorPermissions');
const { CONNECTOR_REGISTRATION_SECRET } = require('../config');

const router = express.Router();

const DEVICE_CODE_TTL_MS = 5 * 60 * 1000; // 5 minutes to approve, same order as a typical OAuth device flow
const USER_CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'; // no 0/O/1/I — typed by hand

function randomToken(prefix, bytes = 32) {
  return `${prefix}_${crypto.randomBytes(bytes).toString('base64url')}`;
}

function randomUserCode() {
  const bytes = crypto.randomBytes(8);
  let out = '';
  for (let i = 0; i < 8; i++) out += USER_CODE_ALPHABET[bytes[i] % USER_CODE_ALPHABET.length];
  return `${out.slice(0, 4)}-${out.slice(4)}`;
}

function requireAuth(req, res, next) {
  if (!req.session.userId) return res.status(401).json({ error: 'not_authenticated' });
  next();
}

function getUser(userId) {
  return db.prepare(`SELECT * FROM users WHERE id = ?`).get(userId);
}

function getApp(applicationId) {
  return db.prepare(`SELECT * FROM applications WHERE application_id = ?`).get(applicationId);
}

function publicApp(app) {
  return {
    applicationId: app.application_id,
    name: app.name,
    description: app.description,
    icon: app.icon,
    permissionsAvailable: JSON.parse(app.permissions_available || '[]'),
    environment: app.environment,
    isFirstParty: !!app.is_first_party,
  };
}

function publicConnection(row, app) {
  return {
    id: row.id,
    applicationId: row.application_id,
    applicationName: app ? app.name : row.application_id,
    applicationIcon: app ? app.icon : null,
    status: row.status,
    permissions: JSON.parse(row.permissions_granted || '[]'),
    connectionType: row.connection_type,
    environment: row.environment,
    createdAt: row.created_at,
    lastUsedAt: row.last_used_at,
    expiresAt: row.expires_at,
  };
}

// Resolve either a Bearer connector_token or an active browser session
// into { userId, connectionId? }. Used by the status endpoint so both a
// Python client (token) and connector.html (session) can ask "am I
// connected" the same way.
function resolveConnectorAuth(req) {
  const authHeader = req.get('authorization') || '';
  const match = /^Bearer\s+(fct_[A-Za-z0-9_-]+)$/.exec(authHeader.trim());
  if (match) {
    const tokenHash = sha256Hex(match[1]);
    const row = db
      .prepare(`SELECT * FROM connections WHERE connector_token_hash = ? AND status = 'connected'`)
      .get(tokenHash);
    if (row) return { userId: row.user_id, connectionId: row.id, connectionRow: row };
    return null;
  }
  if (req.session.userId) return { userId: req.session.userId };
  return null;
}

// ---------------------------------------------------------------------
// GET /api/connector/applications — public registry listing. No auth
// needed: this is "what could I connect", not "what am I connected to".
// ---------------------------------------------------------------------
router.get('/applications', (req, res) => {
  const rows = db.prepare(`SELECT * FROM applications ORDER BY is_first_party DESC, name ASC`).all();
  res.json({ applications: rows.map(publicApp) });
});

// ---------------------------------------------------------------------
// POST /api/connector/applications/register — how "future applications"
// register themselves (spec section 6), gated by a server-to-server
// secret so a browser can never mint a new connectable application on
// its own. Never exposed to connector.js/connector.html.
// ---------------------------------------------------------------------
router.post('/applications/register', (req, res) => {
  if (!CONNECTOR_REGISTRATION_SECRET || req.get('x-connector-registration-secret') !== CONNECTOR_REGISTRATION_SECRET) {
    return res.status(403).json({ error: 'forbidden' });
  }
  const { applicationId, name, description, icon, permissions, environment } = req.body || {};
  if (!applicationId || !/^[a-z0-9][a-z0-9-_]{1,63}$/.test(applicationId)) {
    return res.status(400).json({ error: 'invalid_application_id' });
  }
  if (!name || typeof name !== 'string') return res.status(400).json({ error: 'name_required' });
  const perms = (Array.isArray(permissions) ? permissions : []).filter((p) => PERMISSIONS.includes(p));
  db.prepare(
    `INSERT INTO applications (application_id, name, description, icon, permissions_available, environment, is_first_party)
     VALUES (?, ?, ?, ?, ?, ?, 0)
     ON CONFLICT(application_id) DO UPDATE SET
       name = excluded.name, description = excluded.description, icon = excluded.icon,
       permissions_available = excluded.permissions_available, environment = excluded.environment`
  ).run(applicationId, name, description || null, icon || null, JSON.stringify(perms), environment || 'production');
  res.json({ application: publicApp(getApp(applicationId)) });
});

// ---------------------------------------------------------------------
// GET /api/connector/connections — this identity's connections (auth required)
// ---------------------------------------------------------------------
router.get('/connections', requireAuth, (req, res) => {
  const rows = db.prepare(`SELECT * FROM connections WHERE user_id = ? ORDER BY created_at DESC`).all(req.session.userId);
  res.json({ connections: rows.map((r) => publicConnection(r, getApp(r.application_id))) });
});

// ---------------------------------------------------------------------
// GET /api/connector/status?applicationId=... — status for one app,
// usable by either a signed-in browser or a connected Python client
// (Bearer connector_token). This is the "am I still connected" check
// connector.py/connector.js poll casually, not the approval flow itself.
// ---------------------------------------------------------------------
router.get('/status', (req, res) => {
  const auth = resolveConnectorAuth(req);
  if (!auth) return res.status(401).json({ error: 'not_authenticated' });
  const { applicationId } = req.query;
  if (!applicationId) return res.status(400).json({ error: 'application_id_required' });
  const row = db.prepare(`SELECT * FROM connections WHERE user_id = ? AND application_id = ?`).get(auth.userId, applicationId);
  if (!row) return res.json({ status: 'not_connected' });
  if (row.expires_at && new Date(row.expires_at).getTime() < Date.now()) {
    return res.json({ status: 'expired' });
  }
  res.json({ status: row.status === 'connected' ? 'connected' : 'not_connected', connection: publicConnection(row, getApp(row.application_id)) });
});

// ---------------------------------------------------------------------
// POST /api/connector/connect — direct connect for a browser that
// already has a Fomoji session (connector.html's "Continue" flow, or the
// existing Connect-CAT modal). Immediately creates/refreshes a
// connection; no device code needed since the browser IS the identity
// owner already proving who they are via the session cookie.
// ---------------------------------------------------------------------
router.post('/connect', requireAuth, (req, res) => {
  const { applicationId, permissions, connectionType } = req.body || {};
  const app = getApp(applicationId);
  if (!app) return res.status(404).json({ error: 'unknown_application' });
  const user = getUser(req.session.userId);
  const granted = sanitizePermissions(permissions, {
    identityType: user.identity_type,
    appAvailable: JSON.parse(app.permissions_available || '[]'),
  });

  const token = randomToken('fct');
  const tokenHash = sha256Hex(token);
  const id = crypto.randomUUID();

  db.prepare(
    `INSERT INTO connections (id, user_id, application_id, permissions_granted, connection_type, environment, status, connector_token_hash, last_used_at)
     VALUES (?, ?, ?, ?, ?, ?, 'connected', ?, datetime('now'))
     ON CONFLICT(user_id, application_id) DO UPDATE SET
       permissions_granted = excluded.permissions_granted,
       connection_type = excluded.connection_type,
       status = 'connected',
       connector_token_hash = excluded.connector_token_hash,
       last_used_at = datetime('now'),
       expires_at = NULL`
  ).run(id, user.id, app.application_id, JSON.stringify(granted), connectionType || 'standard', app.environment, tokenHash);

  const row = db.prepare(`SELECT * FROM connections WHERE user_id = ? AND application_id = ?`).get(user.id, app.application_id);
  // The raw token is returned exactly once, here — only the hash is ever
  // persisted, same treatment as a recovery code.
  res.json({ connection: publicConnection(row, app), connectorToken: token });
});

// ---------------------------------------------------------------------
// POST /api/connector/guest — Create a 2-hour temporary guest connection.
// Grants immediate local access without credentials, strictly bounded to
// 2 hours (7200s), after which it auto-expires and CAT auto-signs out.
// ---------------------------------------------------------------------
router.post('/guest', (req, res) => {
  const { applicationId = 'cat' } = req.body || {};
  let app = getApp(applicationId);
  if (!app) {
    app = getApp('cat');
  }

  const guestId = randomToken('usr_gst', 16);
  const guestFomojiId = 'gst_' + crypto.randomBytes(4).toString('hex');
  const guestUsername = 'guest_' + crypto.randomBytes(4).toString('hex');
  const now = Date.now();
  const expiresAt = new Date(now + 2 * 60 * 60 * 1000).toISOString(); // 2 hours

  // Seed guest user
  db.prepare(`
    INSERT INTO users (id, fomoji_id, name, username, email, identity_type, expires_at)
    VALUES (?, ?, 'Guest User', ?, NULL, 'TEMPORARY', ?)
  `).run(guestId, guestFomojiId, guestUsername, expiresAt);

  const token = randomToken('fct_guest');
  const tokenHash = sha256Hex(token);
  const connId = crypto.randomUUID();
  const perms = ['IDENTITY', 'CAT_ACCESS'];

  db.prepare(`
    INSERT INTO connections (id, user_id, application_id, permissions_granted, connection_type, environment, status, connector_token_hash, last_used_at, expires_at)
    VALUES (?, ?, ?, ?, 'guest', 'production', 'connected', ?, datetime('now'), ?)
  `).run(connId, guestId, app ? app.application_id : 'cat', JSON.stringify(perms), tokenHash, expiresAt);

  req.session.userId = guestId;

  res.json({
    connectorToken: token,
    token,
    expiresAt,
    expiresInSeconds: 7200,
    identity: {
      fomojiId: guestFomojiId,
      name: 'Guest User',
      username: guestUsername,
      identityType: 'TEMPORARY',
      isGuest: true,
      expiresAt,
      expiresInSeconds: 7200,
      permissions: perms,
      applicationId: app ? app.application_id : 'cat',
    },
  });
});

// ---------------------------------------------------------------------
// POST /api/connector/disconnect — revoke a connection (browser session).
// ---------------------------------------------------------------------
router.post('/disconnect', requireAuth, (req, res) => {
  const { applicationId } = req.body || {};
  const result = db
    .prepare(`UPDATE connections SET status = 'revoked' WHERE user_id = ? AND application_id = ?`)
    .run(req.session.userId, applicationId);
  if (result.changes === 0) return res.status(404).json({ error: 'not_connected' });
  res.json({ ok: true });
});

// ---------------------------------------------------------------------
// Device-authorization flow — for CAT and any future non-browser client
// (connector.py). No password, no passkey, no session cookie on this
// side of the flow; only application_id + the permissions it's asking
// for. See file header for why this shape exists.
// ---------------------------------------------------------------------

// POST /api/connector/device/start — client (Python) begins pairing.
router.post('/device/start', (req, res) => {
  const { applicationId, permissions, connectionType, environment } = req.body || {};
  const app = getApp(applicationId);
  if (!app) return res.status(404).json({ error: 'unknown_application' });

  const deviceCode = randomToken('dc', 24);
  const userCode = randomUserCode();
  const requested = (Array.isArray(permissions) ? permissions : []).filter((p) =>
    JSON.parse(app.permissions_available || '[]').includes(p)
  );
  const expiresAt = new Date(Date.now() + DEVICE_CODE_TTL_MS).toISOString();

  db.prepare(
    `INSERT INTO device_codes (device_code, user_code, application_id, requested_permissions, connection_type, environment, expires_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  ).run(deviceCode, userCode, app.application_id, JSON.stringify(requested), connectionType || 'standard', environment || app.environment, expiresAt);

  res.json({
    deviceCode,
    userCode,
    verificationUrl: '/connector.html',
    expiresIn: Math.floor(DEVICE_CODE_TTL_MS / 1000),
    pollIntervalSeconds: 3,
  });
});

// GET /api/connector/device/lookup?userCode=... — connector.html shows
// the pending request's app name + requested permissions before the
// person approves, so they know what they're approving.
router.get('/device/lookup', (req, res) => {
  const { userCode } = req.query;
  const row = db.prepare(`SELECT * FROM device_codes WHERE user_code = ?`).get((userCode || '').toUpperCase());
  if (!row) return res.status(404).json({ error: 'not_found' });
  if (row.status !== 'pending' || new Date(row.expires_at).getTime() < Date.now()) {
    return res.status(410).json({ error: 'expired_or_resolved', status: row.status });
  }
  const app = getApp(row.application_id);
  res.json({
    application: publicApp(app),
    requestedPermissions: JSON.parse(row.requested_permissions || '[]'),
  });
});

// In-memory, single-delivery handoff of the raw connector token from
// /device/approve to /device/poll. Only the SHA-256 hash is ever
// persisted to the connections table (see /connect for the same
// pattern) — this map exists purely so the *one* legitimate poll that
// follows an approval can receive the raw value once. Process-local,
// same caveat as auth.js's in-memory lockout map: fine for a single
// instance, would need a shared store (Redis, etc.) multi-instance.
const issuedTokens = new Map(); // deviceCode -> raw token

// POST /api/connector/device/approve — the signed-in identity approves.
router.post('/device/approve', requireAuth, (req, res) => {
  const { userCode, permissions } = req.body || {};
  const row = db.prepare(`SELECT * FROM device_codes WHERE user_code = ?`).get((userCode || '').toUpperCase());
  if (!row) return res.status(404).json({ error: 'not_found' });
  if (row.status !== 'pending') return res.status(410).json({ error: 'already_resolved' });
  if (new Date(row.expires_at).getTime() < Date.now()) {
    db.prepare(`UPDATE device_codes SET status = 'expired' WHERE device_code = ?`).run(row.device_code);
    return res.status(410).json({ error: 'expired' });
  }

  const app = getApp(row.application_id);
  const user = getUser(req.session.userId);
  const requested = JSON.parse(row.requested_permissions || '[]');
  const chosen = Array.isArray(permissions) ? permissions.filter((p) => requested.includes(p)) : requested;
  const granted = sanitizePermissions(chosen, {
    identityType: user.identity_type,
    appAvailable: JSON.parse(app.permissions_available || '[]'),
  });

  const token = randomToken('fct');
  const tokenHash = sha256Hex(token);
  const connectionId = crypto.randomUUID();

  db.prepare(
    `INSERT INTO connections (id, user_id, application_id, permissions_granted, connection_type, environment, status, connector_token_hash, last_used_at)
     VALUES (?, ?, ?, ?, ?, ?, 'connected', ?, datetime('now'))
     ON CONFLICT(user_id, application_id) DO UPDATE SET
        permissions_granted = excluded.permissions_granted,
        connection_type = excluded.connection_type,
        status = 'connected',
        connector_token_hash = excluded.connector_token_hash,
        last_used_at = datetime('now'),
        expires_at = NULL`
  ).run(connectionId, user.id, app.application_id, JSON.stringify(granted), row.connection_type, row.environment, tokenHash);

  // The UPSERT above keeps the original row id when (user_id, application_id)
  // already existed (SQLite ON CONFLICT keeps the existing PK). So the
  // freshly-generated connectionId is NOT reliably the real PK — fetch the
  // actual row by (user_id, application_id) instead of assuming it.
  const actualConn = db.prepare(`SELECT * FROM connections WHERE user_id = ? AND application_id = ?`).get(user.id, app.application_id);
  const realConnectionId = actualConn ? actualConn.id : connectionId;

  // device_codes keeps connection_id/user_id only long enough for the
  // Python client's next poll to pick up the token; it is never reusable
  // after that (status flips to approved, and /device/poll only ever
  // returns the token once).
  db.prepare(`UPDATE device_codes SET status = 'approved', user_id = ?, connection_id = ? WHERE device_code = ?`).run(
    user.id,
    realConnectionId,
    row.device_code
  );
  issuedTokens.set(row.device_code, token);

  res.json({ ok: true, applicationName: app.name, permissions: granted });
});

// POST /api/connector/device/deny
router.post('/device/deny', requireAuth, (req, res) => {
  const { userCode } = req.body || {};
  const result = db
    .prepare(`UPDATE device_codes SET status = 'denied' WHERE user_code = ? AND status = 'pending'`)
    .run((userCode || '').toUpperCase());
  if (result.changes === 0) return res.status(404).json({ error: 'not_found_or_resolved' });
  res.json({ ok: true });
});

// POST /api/connector/device/poll — client (Python) polls this until it
// gets a terminal status. The connector_token is only ever included in
// the FIRST poll response after approval — it's removed from
// issuedTokens immediately after, so a leaked/replayed poll call later
// can't fetch the token a second time.
router.post('/device/poll', (req, res) => {
  const { deviceCode } = req.body || {};
  const row = db.prepare(`SELECT * FROM device_codes WHERE device_code = ?`).get(deviceCode);
  if (!row) return res.status(404).json({ error: 'not_found' });

  if (row.status === 'pending' && new Date(row.expires_at).getTime() < Date.now()) {
    db.prepare(`UPDATE device_codes SET status = 'expired' WHERE device_code = ?`).run(deviceCode);
    return res.json({ status: 'expired' });
  }

  if (row.status !== 'approved') {
    return res.json({ status: row.status }); // pending | denied | expired
  }

  // Robust lookup: prefer the stored id, but fall back to (user_id, application_id)
  // if the row was created via an UPSERT that kept a different PK (see fix in /device/approve).
  let conn = row.connection_id ? db.prepare(`SELECT * FROM connections WHERE id = ?`).get(row.connection_id) : null;
  if (!conn) {
    conn = db.prepare(`SELECT * FROM connections WHERE user_id = ? AND application_id = ?`).get(row.user_id, row.application_id);
  }
  const user = getUser(row.user_id);
  if (!conn || !user) return res.status(500).json({ error: 'connection_missing' });

  const token = issuedTokens.get(deviceCode);
  if (!token) {
    // Approved, but the one legitimate delivery already happened (or
    // this server restarted, which clears the in-memory map — the
    // client should re-run /device/start in that case).
    return res.status(410).json({ error: 'token_already_delivered' });
  }
  issuedTokens.delete(deviceCode);

  res.json({
    status: 'approved',
    connectorToken: token,
    fomojiId: user.fomoji_id,
    name: user.name,
    identityType: user.identity_type,
    permissions: JSON.parse(conn.permissions_granted || '[]'),
    applicationId: conn.application_id,
  });
});

module.exports = router;
