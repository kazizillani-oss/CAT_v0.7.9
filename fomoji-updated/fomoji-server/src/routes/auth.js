'use strict';

const express = require('express');
const db = require('../db');
const { randomFomojiId, randomInternalId } = require('../id');
const { hashSecret, verifySecret, sha256Hex, randomRecoveryCode } = require('../password');

const router = express.Router();

// A TEMPORARY identity past its expires_at is treated as signed out
// everywhere — checked here (every authenticated route) and in
// GET /session, so an expired guest never keeps acting on an identity
// the spec says must expire.
function isExpired(user) {
  return user.identity_type === 'TEMPORARY' && user.expires_at && new Date(user.expires_at).getTime() < Date.now();
}

function requireAuth(req, res, next) {
  if (!req.session.userId) return res.status(401).json({ error: 'not_authenticated' });
  const user = db.prepare(`SELECT identity_type, expires_at FROM users WHERE id = ?`).get(req.session.userId);
  if (!user) {
    req.session.destroy(() => {});
    return res.status(401).json({ error: 'not_authenticated' });
  }
  if (isExpired(user)) {
    req.session.destroy(() => {});
    return res.status(401).json({ error: 'expired' });
  }
  next();
}

function publicUser(user) {
  return {
    fomojiId: user.fomoji_id,
    name: user.name,
    username: user.username,
    email: user.email,
    hasPassword: !!user.password_hash,
    identityType: user.identity_type,
    expiresAt: user.expires_at || null,
  };
}

function logEvent(userId, kind, detail) {
  db.prepare(`INSERT INTO auth_events (user_id, kind, detail) VALUES (?, ?, ?)`)
    .run(userId, kind, detail || null);
}

// ---------------------------------------------------------------------
// Login-attempt lockout for password auth. In-memory and per-process —
// fine for a single dev/small deployment; resets on restart. A real
// multi-instance deployment should move this to the DB or a shared store
// (same caveat as express-session's MemoryStore in server.js).
// ---------------------------------------------------------------------
const LOCKOUT_THRESHOLD = 5;
const LOCKOUT_MS = 60 * 1000;
const loginAttempts = new Map();

function lockoutKey(identifier) {
  return identifier.trim().toLowerCase();
}

function checkLockout(identifier) {
  const rec = loginAttempts.get(lockoutKey(identifier));
  if (!rec) return { locked: false };
  if (rec.count >= LOCKOUT_THRESHOLD) {
    const remaining = rec.lockedAt + LOCKOUT_MS - Date.now();
    if (remaining > 0) return { locked: true };
    loginAttempts.delete(lockoutKey(identifier));
  }
  return { locked: false };
}

function recordFailure(identifier) {
  const key = lockoutKey(identifier);
  const rec = loginAttempts.get(key) || { count: 0, lockedAt: 0 };
  rec.count++;
  if (rec.count >= LOCKOUT_THRESHOLD) rec.lockedAt = Date.now();
  loginAttempts.set(key, rec);
}

function clearFailures(identifier) {
  loginAttempts.delete(lockoutKey(identifier));
}

function publicCredential(row) {
  return {
    id: row.credential_id,
    nickname: row.nickname || 'Passkey',
    deviceType: row.device_type,       // 'singleDevice' | 'multiDevice'
    backedUp: !!row.backed_up,
    createdAt: row.created_at,
    lastUsedAt: row.last_used_at,
  };
}

// Who am I, if anyone
router.get('/session', (req, res) => {
  if (!req.session.userId) return res.json({ user: null });
  const user = db.prepare(`SELECT * FROM users WHERE id = ?`).get(req.session.userId);
  if (!user || isExpired(user)) {
    req.session.destroy(() => {});
    return res.json({ user: null });
  }
  res.json({ user: publicUser(user), sessionExpiresAt: req.session.cookie.expires });
});

router.post('/logout', (req, res) => {
  req.session.destroy((err) => {
    // Destroying the session removes it server-side, but express-session
    // does NOT send a Set-Cookie to expire the cookie itself unless we
    // ask it to — without this, the browser keeps holding onto the old
    // (now-meaningless) fomoji.sid cookie. Harmless on its own since the
    // server no longer recognizes it, but clearing it explicitly is what
    // makes "signed out" true client-side too, immediately, rather than
    // relying on every caller to also drop local state correctly.
    res.clearCookie('fomoji.sid');
    if (err) return res.status(500).json({ error: 'server_error' });
    res.json({ ok: true });
  });
});

// ---------------------------------------------------------------------
// Password auth (spec section 1). Real, server-side, hashed with scrypt
// (src/password.js) — never plaintext, never sent anywhere but this
// request. This is a weaker recovery path than a passkey (a password can
// be phished/reused; a passkey can't), which is exactly why the account-
// linking rule below still requires *some* other method before either can
// be removed as your last one.
// ---------------------------------------------------------------------

router.post('/password/register', (req, res) => {
  const { name, username, email, password } = req.body || {};
  if (!username || typeof username !== 'string' || username.length < 3) {
    return res.status(400).json({ error: 'invalid_username' });
  }
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ error: 'invalid_email' });
  }
  if (!password || typeof password !== 'string' || password.length < 8) {
    return res.status(400).json({ error: 'invalid_password' });
  }
  if (db.prepare(`SELECT 1 FROM users WHERE username = ?`).get(username)) {
    return res.status(409).json({ error: 'username_taken' });
  }
  if (email && db.prepare(`SELECT 1 FROM users WHERE email = ?`).get(email)) {
    return res.status(409).json({ error: 'email_taken' });
  }

  let fomojiId;
  do {
    fomojiId = randomFomojiId();
  } while (db.prepare(`SELECT 1 FROM users WHERE fomoji_id = ?`).get(fomojiId));

  const internalId = randomInternalId();
  const passwordHash = hashSecret(password);
  const recoveryCode = randomRecoveryCode();
  const recoveryCodeHash = sha256Hex(recoveryCode);

  db.prepare(
    `INSERT INTO users (id, fomoji_id, name, username, email, password_hash, recovery_code_hash)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  ).run(internalId, fomojiId, (name || '').trim() || username, username, email || null, passwordHash, recoveryCodeHash);

  req.session.userId = internalId;
  logEvent(internalId, 'account_created', 'password');

  const user = db.prepare(`SELECT * FROM users WHERE id = ?`).get(internalId);
  res.json({ user: publicUser(user), recoveryCode, sessionExpiresAt: req.session.cookie.expires });
});

// ---------------------------------------------------------------------
// Temporary / guest identities (spec sections 11-12). No email, no
// password — just a Fomoji ID and an expiration. Session-authenticated
// immediately, same as any other new identity, but every connector
// permission grant for a TEMPORARY identity is additionally capped
// server-side (see connectorPermissions.RESTRICTED_IDENTITY_TYPES) no
// matter what an application asks for, and the account itself expires.
// ---------------------------------------------------------------------
const TEMP_MAX_HOURS = 24 * 7; // one week ceiling, whatever the caller requests
const TEMP_DEFAULT_HOURS = 24;

router.post('/temporary/create', (req, res) => {
  const { name, hours } = req.body || {};
  const ttlHours = Math.min(Math.max(Number(hours) || TEMP_DEFAULT_HOURS, 1), TEMP_MAX_HOURS);
  const expiresAt = new Date(Date.now() + ttlHours * 60 * 60 * 1000).toISOString();

  let fomojiId;
  do {
    fomojiId = randomFomojiId();
  } while (db.prepare(`SELECT 1 FROM users WHERE fomoji_id = ?`).get(fomojiId));

  const internalId = randomInternalId();
  db.prepare(
    `INSERT INTO users (id, fomoji_id, name, identity_type, expires_at) VALUES (?, ?, ?, 'TEMPORARY', ?)`
  ).run(internalId, fomojiId, (name || '').trim() || 'Guest', expiresAt);

  req.session.userId = internalId;
  logEvent(internalId, 'account_created', 'temporary');

  const user = db.prepare(`SELECT * FROM users WHERE id = ?`).get(internalId);
  res.json({ user: publicUser(user), sessionExpiresAt: req.session.cookie.expires });
});

// Upgrade the CURRENT session's temporary identity to a permanent
// password account. Keeps the same fomoji_id, connections and activity
// log — only identity_type/expires_at and the credential change.
router.post('/temporary/upgrade', requireAuth, (req, res) => {
  const current = db.prepare(`SELECT * FROM users WHERE id = ?`).get(req.session.userId);
  if (!current || current.identity_type !== 'TEMPORARY') {
    return res.status(400).json({ error: 'not_a_temporary_identity' });
  }
  const { username, email, password } = req.body || {};
  if (!username || typeof username !== 'string' || username.length < 3) {
    return res.status(400).json({ error: 'invalid_username' });
  }
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ error: 'invalid_email' });
  }
  if (!password || typeof password !== 'string' || password.length < 8) {
    return res.status(400).json({ error: 'invalid_password' });
  }
  if (db.prepare(`SELECT 1 FROM users WHERE username = ? AND id != ?`).get(username, current.id)) {
    return res.status(409).json({ error: 'username_taken' });
  }
  const passwordHash = hashSecret(password);
  const recoveryCode = randomRecoveryCode();
  const recoveryCodeHash = sha256Hex(recoveryCode);
  db.prepare(
    `UPDATE users SET username = ?, email = ?, password_hash = ?, recovery_code_hash = ?,
       identity_type = 'PERSON', expires_at = NULL WHERE id = ?`
  ).run(username, email || null, passwordHash, recoveryCodeHash, current.id);
  logEvent(current.id, 'account_upgraded', 'temporary_to_password');
  const user = db.prepare(`SELECT * FROM users WHERE id = ?`).get(current.id);
  res.json({ user: publicUser(user), recoveryCode });
});

router.post('/password/login', (req, res) => {
  const { identifier, password } = req.body || {};
  if (!identifier || !password) return res.status(400).json({ error: 'invalid_credentials' });

  if (checkLockout(identifier).locked) {
    return res.status(429).json({ error: 'locked' });
  }

  const id = identifier.trim().toLowerCase();
  const user = db.prepare(
    `SELECT * FROM users WHERE lower(username) = ? OR lower(email) = ?`
  ).get(id, id);

  // Deliberately generic on every failure path (spec section 15) — don't
  // reveal whether the account exists, or whether it just has no password
  // set (e.g. a passkey-only identity).
  if (!user || !verifySecret(password, user.password_hash)) {
    recordFailure(identifier);
    return res.status(401).json({ error: 'invalid_credentials' });
  }

  clearFailures(identifier);
  req.session.userId = user.id;
  logEvent(user.id, 'login', 'password');
  res.json({ user: publicUser(user), sessionExpiresAt: req.session.cookie.expires });
});

router.post('/password/reset', (req, res) => {
  const { identifier, recoveryCode, newPassword } = req.body || {};
  if (!identifier || !recoveryCode || !newPassword) {
    return res.status(400).json({ error: 'invalid_recovery' });
  }
  if (checkLockout(identifier).locked) {
    return res.status(429).json({ error: 'locked' });
  }
  if (newPassword.length < 8) return res.status(400).json({ error: 'invalid_password' });

  const id = identifier.trim().toLowerCase();
  const user = db.prepare(
    `SELECT * FROM users WHERE lower(username) = ? OR lower(email) = ?`
  ).get(id, id);

  const codeHash = sha256Hex(recoveryCode.trim().toUpperCase());
  if (!user || !user.recovery_code_hash || codeHash !== user.recovery_code_hash) {
    recordFailure(identifier);
    return res.status(401).json({ error: 'invalid_recovery' });
  }

  clearFailures(identifier);
  const newPasswordHash = hashSecret(newPassword);
  const newRecoveryCode = randomRecoveryCode();
  const newRecoveryCodeHash = sha256Hex(newRecoveryCode);
  db.prepare(`UPDATE users SET password_hash = ?, recovery_code_hash = ? WHERE id = ?`)
    .run(newPasswordHash, newRecoveryCodeHash, user.id);
  logEvent(user.id, 'password_reset', null);

  res.json({ newRecoveryCode });
});

router.post('/password/change', requireAuth, (req, res) => {
  const { currentPassword, newPassword } = req.body || {};
  const user = db.prepare(`SELECT * FROM users WHERE id = ?`).get(req.session.userId);
  if (!user) return res.status(401).json({ error: 'not_authenticated' });

  if (user.password_hash) {
    if (!currentPassword || !verifySecret(currentPassword, user.password_hash)) {
      return res.status(401).json({ error: 'invalid_credentials' });
    }
  }
  if (!newPassword || newPassword.length < 8) {
    return res.status(400).json({ error: 'invalid_password' });
  }

  const newPasswordHash = hashSecret(newPassword);
  // First password ever set on a passkey-only identity also needs a
  // recovery code, same as registration — there's otherwise no backup
  // door for a password this account never had one for.
  let newRecoveryCode = null;
  if (!user.recovery_code_hash) {
    newRecoveryCode = randomRecoveryCode();
    db.prepare(`UPDATE users SET password_hash = ?, recovery_code_hash = ? WHERE id = ?`)
      .run(newPasswordHash, sha256Hex(newRecoveryCode), user.id);
  } else {
    db.prepare(`UPDATE users SET password_hash = ? WHERE id = ?`).run(newPasswordHash, user.id);
  }
  logEvent(user.id, 'password_changed', null);
  res.json({ ok: true, recoveryCode: newRecoveryCode });
});

router.patch('/profile', requireAuth, (req, res) => {
  const { name } = req.body || {};
  if (!name || typeof name !== 'string' || name.trim().length < 2) {
    return res.status(400).json({ error: 'invalid_name' });
  }
  db.prepare(`UPDATE users SET name = ? WHERE id = ?`).run(name.trim(), req.session.userId);
  const user = db.prepare(`SELECT * FROM users WHERE id = ?`).get(req.session.userId);
  res.json({ user: publicUser(user) });
});

// ---- Account Linking Center: list / rename / remove passkeys ----

router.get('/credentials', requireAuth, (req, res) => {
  const rows = db.prepare(`SELECT * FROM credentials WHERE user_id = ? ORDER BY created_at ASC`).all(req.session.userId);
  res.json({ credentials: rows.map(publicCredential) });
});

router.patch('/credentials/:id', requireAuth, (req, res) => {
  const { nickname } = req.body || {};
  if (!nickname || typeof nickname !== 'string' || nickname.length > 60) {
    return res.status(400).json({ error: 'invalid_nickname' });
  }
  const row = db.prepare(`SELECT * FROM credentials WHERE credential_id = ? AND user_id = ?`)
    .get(req.params.id, req.session.userId);
  if (!row) return res.status(404).json({ error: 'not_found' });

  db.prepare(`UPDATE credentials SET nickname = ? WHERE credential_id = ?`).run(nickname, req.params.id);
  res.json({ ok: true });
});

router.delete('/credentials/:id', requireAuth, (req, res) => {
  const all = db.prepare(`SELECT * FROM credentials WHERE user_id = ?`).all(req.session.userId);
  const target = all.find((c) => c.credential_id === req.params.id);
  if (!target) return res.status(404).json({ error: 'not_found' });

  // Spec section 3: never let this be the user's last authentication
  // method. A password now counts as "another method" too — only block
  // the removal if this passkey is both the last one AND there's no
  // password set on the account. Once OAuth providers exist, they should
  // widen this same check further.
  const user = db.prepare(`SELECT password_hash FROM users WHERE id = ?`).get(req.session.userId);
  if (all.length <= 1 && !user.password_hash) {
    return res.status(409).json({
      error: 'last_method',
      message: 'This is your only sign-in method. Add another before removing it.',
    });
  }

  db.prepare(`DELETE FROM credentials WHERE credential_id = ?`).run(req.params.id);
  logEvent(req.session.userId, 'passkey_removed', target.nickname);
  res.json({ ok: true });
});

// ---- Authentication Activity (spec section 24) ----

router.get('/activity', requireAuth, (req, res) => {
  const rows = db.prepare(
    `SELECT kind, detail, created_at FROM auth_events WHERE user_id = ? ORDER BY created_at DESC LIMIT 50`
  ).all(req.session.userId);
  res.json({ events: rows });
});

module.exports = { router, requireAuth };
