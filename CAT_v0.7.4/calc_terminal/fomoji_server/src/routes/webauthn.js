'use strict';

const express = require('express');
const crypto = require('crypto');
const {
  generateRegistrationOptions,
  verifyRegistrationResponse,
  generateAuthenticationOptions,
  verifyAuthenticationResponse,
} = require('@simplewebauthn/server');

const db = require('../db');
const { randomFomojiId, randomInternalId } = require('../id');
const { RP_ID, RP_NAME, ORIGIN, PORT } = require('../config');

const router = express.Router();

const CHALLENGE_TTL_MS = 5 * 60 * 1000; // 5 minutes to complete a ceremony

function getAllowedOrigins(req) {
  const list = new Set([
    ORIGIN,
    `http://localhost:${PORT || 3000}`,
    `http://127.0.0.1:${PORT || 3000}`,
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:8765',
    'http://127.0.0.1:8765',
  ]);
  const reqOrigin = req.get('origin');
  if (reqOrigin) {
    list.add(reqOrigin);
  }
  return Array.from(list);
}

function expiryFromNow() {
  return new Date(Date.now() + CHALLENGE_TTL_MS).toISOString();
}

function deleteExpiredChallenges() {
  db.prepare(`DELETE FROM challenges WHERE expires_at < datetime('now')`).run();
}

function logEvent(userId, kind, detail) {
  db.prepare(`INSERT INTO auth_events (user_id, kind, detail) VALUES (?, ?, ?)`)
    .run(userId, kind, detail || null);
}

function userCredentials(userId) {
  return db.prepare(`SELECT * FROM credentials WHERE user_id = ?`).all(userId);
}

function toWebAuthnCredential(row) {
  return {
    id: row.credential_id,
    publicKey: Buffer.from(row.public_key, 'base64url'),
    counter: row.counter,
    transports: row.transports ? JSON.parse(row.transports) : undefined,
  };
}

// ---------------------------------------------------------------------
// REGISTRATION — new Fomoji identity + first passkey, or an additional
// passkey added to an already-signed-in identity (Account Linking Center).
// ---------------------------------------------------------------------

router.post('/register/start', async (req, res) => {
  deleteExpiredChallenges();

  const existingUserId = req.session.userId || null;

  let payload;
  let excludeCredentials = [];

  if (existingUserId) {
    // Adding an additional passkey to an already-authenticated identity.
    const user = db.prepare(`SELECT * FROM users WHERE id = ?`).get(existingUserId);
    if (!user) return res.status(401).json({ error: 'not_authenticated' });
    payload = { mode: 'add', userId: user.id };
    excludeCredentials = userCredentials(user.id).map((c) => ({
      id: c.credential_id,
      transports: c.transports ? JSON.parse(c.transports) : undefined,
    }));
    var displayName = user.name || user.username || user.fomoji_id;
    var accountName = user.username || user.fomoji_id;
  } else {
    // Brand new identity. Nothing is written to `users` yet — see the
    // comment on `challenges.payload` in db.js for why.
    const { name, username, email } = req.body || {};
    if (!username || typeof username !== 'string' || username.length < 3) {
      return res.status(400).json({ error: 'invalid_username' });
    }
    const usernameTaken = db.prepare(`SELECT 1 FROM users WHERE username = ?`).get(username);
    if (usernameTaken) return res.status(409).json({ error: 'username_taken' });
    if (email) {
      const emailTaken = db.prepare(`SELECT 1 FROM users WHERE email = ?`).get(email);
      if (emailTaken) return res.status(409).json({ error: 'email_taken' });
    }

    let fomojiId;
    do {
      fomojiId = randomFomojiId();
    } while (db.prepare(`SELECT 1 FROM users WHERE fomoji_id = ?`).get(fomojiId));

    payload = {
      mode: 'new',
      internalId: randomInternalId(),
      fomojiId,
      name: name || '',
      username,
      email: email || null,
    };
    displayName = name || username;
    accountName = username;
  }

  const options = await generateRegistrationOptions({
    rpName: RP_NAME,
    rpID: RP_ID,
    userName: accountName,
    userDisplayName: displayName,
    attestationType: 'none', // we don't need attestation, only proof-of-possession going forward
    excludeCredentials,
    authenticatorSelection: {
      residentKey: 'preferred',   // discoverable credential -> enables usernameless login
      userVerification: 'preferred',
    },
  });

  const challengeId = crypto.randomUUID();
  db.prepare(
    `INSERT INTO challenges (id, user_id, challenge, type, payload, expires_at) VALUES (?, ?, ?, 'registration', ?, ?)`
  ).run(challengeId, existingUserId, options.challenge, JSON.stringify(payload), expiryFromNow());

  req.session.pendingChallengeId = challengeId;
  console.log('[fomoji:webauthn] register/start ok — mode=%s rpID=%s challengeId=%s', payload.mode, RP_ID, challengeId);
  res.json({ options, challengeId });
});

router.post('/register/finish', async (req, res) => {
  deleteExpiredChallenges();

  const challengeId = (req.body && req.body.challengeId) || req.session.pendingChallengeId;
  if (!challengeId) {
    console.warn('[fomoji:webauthn] register/finish: no pending challenge found on request or session');
    return res.status(400).json({ error: 'no_pending_challenge' });
  }

  const row = db.prepare(`SELECT * FROM challenges WHERE id = ? AND type = 'registration'`).get(challengeId);
  if (!row) {
    console.warn('[fomoji:webauthn] register/finish: challenge %s not found in DB (expired >5min, already consumed, or server restarted)', challengeId);
    return res.status(400).json({ error: 'challenge_expired_or_unknown' });
  }

  const payload = JSON.parse(row.payload);

  let verification;
  try {
    verification = await verifyRegistrationResponse({
      response: req.body,
      expectedChallenge: row.challenge,
      expectedOrigin: getAllowedOrigins(req),
      expectedRPID: RP_ID,
    });
  } catch (err) {
    console.error('[fomoji:webauthn] register/finish: verifyRegistrationResponse threw — expectedOrigin=%s expectedRPID=%s message=%s', ORIGIN, RP_ID, err.message);
    return res.status(400).json({ error: 'verification_failed', message: err.message });
  }

  if (!verification.verified || !verification.registrationInfo) {
    console.warn('[fomoji:webauthn] register/finish: verified=false with no thrown error');
    return res.status(400).json({ error: 'not_verified' });
  }
  console.log('[fomoji:webauthn] register/finish ok — userId set on session');

  // Consume the challenge immediately — one-time use, no replay.
  db.prepare(`DELETE FROM challenges WHERE id = ?`).run(challengeId);
  delete req.session.pendingChallengeId;

  const { credential, credentialDeviceType, credentialBackedUp } = verification.registrationInfo;

  const userId = payload.mode === 'add' ? payload.userId : payload.internalId;

  const tx = db.transaction(() => {
    if (payload.mode === 'new') {
      db.prepare(
        `INSERT INTO users (id, fomoji_id, name, username, email) VALUES (?, ?, ?, ?, ?)`
      ).run(payload.internalId, payload.fomojiId, payload.name, payload.username, payload.email);
    }
    db.prepare(
      `INSERT INTO credentials (credential_id, user_id, public_key, counter, device_type, backed_up, transports, nickname)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
    ).run(
      credential.id,
      userId,
      Buffer.from(credential.publicKey).toString('base64url'),
      credential.counter,
      credentialDeviceType,
      credentialBackedUp ? 1 : 0,
      credential.transports ? JSON.stringify(credential.transports) : null,
      guessNickname(req.headers['user-agent'])
    );
    logEvent(userId, 'passkey_added', guessNickname(req.headers['user-agent']));
  });
  tx();

  req.session.userId = userId;
  const user = db.prepare(`SELECT * FROM users WHERE id = ?`).get(userId);
  res.json({ verified: true, user: publicUser(user) });
});

// ---------------------------------------------------------------------
// AUTHENTICATION — usernameless / discoverable-credential login. The
// browser's own authenticator UI shows the user which passkey(s) it has
// for this site; the server never has to ask "who are you" first.
// ---------------------------------------------------------------------

router.post('/login/start', async (req, res) => {
  deleteExpiredChallenges();

  const options = await generateAuthenticationOptions({
    rpID: RP_ID,
    userVerification: 'preferred',
    // No allowCredentials -> discoverable/usernameless flow. If a specific
    // Fomoji ID was supplied (e.g. from a dropped Passport PDF, phase 5),
    // we could scope allowCredentials to just that user's credentials here.
  });

  const challengeId = crypto.randomUUID();
  db.prepare(
    `INSERT INTO challenges (id, user_id, challenge, type, expires_at) VALUES (?, NULL, ?, 'authentication', ?)`
  ).run(challengeId, options.challenge, expiryFromNow());

  req.session.pendingChallengeId = challengeId;
  console.log('[fomoji:webauthn] login/start ok — rpID=%s challengeId=%s', RP_ID, challengeId);
  res.json({ options, challengeId });
});

router.post('/login/finish', async (req, res) => {
  deleteExpiredChallenges();

  const challengeId = (req.body && req.body.challengeId) || req.session.pendingChallengeId;
  if (!challengeId) {
    console.warn('[fomoji:webauthn] login/finish: no pending challenge found on request or session');
    return res.status(400).json({ error: 'no_pending_challenge' });
  }

  const row = db.prepare(`SELECT * FROM challenges WHERE id = ? AND type = 'authentication'`).get(challengeId);
  if (!row) {
    console.warn('[fomoji:webauthn] login/finish: challenge %s not found (expired >5min, already consumed, or server restarted)', challengeId);
    return res.status(400).json({ error: 'challenge_expired_or_unknown' });
  }

  const credentialId = req.body && req.body.id;
  const credRow = credentialId
    ? db.prepare(`SELECT * FROM credentials WHERE credential_id = ?`).get(credentialId)
    : null;

  if (!credRow) {
    // Deliberately generic to the client — don't reveal whether the
    // credential ID is unknown vs. something else went wrong (spec
    // section 15). Server log is fine to be specific.
    console.warn('[fomoji:webauthn] login/finish: no credential row for id=%s (passkey not registered on THIS server/DB — e.g. wrong RP_ID at registration time, or DB was reset since)', credentialId);
    return res.status(400).json({ error: 'authentication_failed' });
  }

  let verification;
  try {
    verification = await verifyAuthenticationResponse({
      response: req.body,
      expectedChallenge: row.challenge,
      expectedOrigin: getAllowedOrigins(req),
      expectedRPID: RP_ID,
      credential: toWebAuthnCredential(credRow),
    });
  } catch (err) {
    console.error('[fomoji:webauthn] login/finish: verifyAuthenticationResponse threw — expectedOrigin=%s expectedRPID=%s message=%s', ORIGIN, RP_ID, err.message);
    return res.status(400).json({ error: 'authentication_failed' });
  }

  if (!verification.verified) {
    console.warn('[fomoji:webauthn] login/finish: verified=false with no thrown error, credentialId=%s', credentialId);
    return res.status(400).json({ error: 'authentication_failed' });
  }
  console.log('[fomoji:webauthn] login/finish ok — userId=%s', credRow.user_id);

  db.prepare(`DELETE FROM challenges WHERE id = ?`).run(challengeId);
  delete req.session.pendingChallengeId;

  // Counter must strictly increase — this is what detects a *cloned*
  // authenticator (two devices signing with the same key and diverging
  // counters). A non-increasing counter on a device that reports counters
  // at all is treated as a red flag, not silently accepted.
  const newCounter = verification.authenticationInfo.newCounter;
  if (credRow.counter !== 0 && newCounter !== 0 && newCounter <= credRow.counter) {
    logEvent(credRow.user_id, 'possible_cloned_credential', credentialId);
    return res.status(400).json({ error: 'authentication_failed' });
  }

  db.prepare(`UPDATE credentials SET counter = ?, last_used_at = datetime('now') WHERE credential_id = ?`)
    .run(newCounter, credentialId);

  req.session.userId = credRow.user_id;
  logEvent(credRow.user_id, 'login', 'passkey');

  const user = db.prepare(`SELECT * FROM users WHERE id = ?`).get(credRow.user_id);
  res.json({ verified: true, user: publicUser(user) });
});

function guessNickname(userAgent) {
  if (!userAgent) return 'Unknown device';
  if (/iPhone/.test(userAgent)) return 'iPhone';
  if (/iPad/.test(userAgent)) return 'iPad';
  if (/Macintosh/.test(userAgent)) return 'Mac';
  if (/Android/.test(userAgent)) return 'Android device';
  if (/Windows/.test(userAgent)) return 'Windows device';
  return 'Device';
}

function publicUser(user) {
  return {
    fomojiId: user.fomoji_id,
    name: user.name,
    username: user.username,
    email: user.email,
  };
}

module.exports = router;
