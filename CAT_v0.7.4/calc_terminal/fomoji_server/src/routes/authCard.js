'use strict';

// ---------------------------------------------------------------------
// Fomoji Authentication Card.
//
// What this actually is, precisely, because the feature only works if
// its promises are precise:
//
//   - Every identity gets a `pattern_seed`: 32 random bytes, generated
//     once server-side, stored in auth_cards, never derivable from the
//     user's name/username/email. It drives the card's visual pattern
//     (rendered client-side in fomoji-auth-card.js) — that's what makes
//     each user's card *look* unique.
//   - Every card fetch is signed: signature = HMAC-SHA256(CARD_SECRET,
//     fomojiId + patternSeed). That's what makes a card's *data*
//     verifiable — /verify below recomputes the HMAC and checks it
//     matches, so nobody can hand-craft a fake fomojiId+seed pair and
//     have it come back "verified" without knowing CARD_SECRET.
//
// What this is honestly NOT, because overclaiming here would be a
// security lie: a website cannot detect or block a screenshot — no
// browser API grants that, on any platform. What the signature scheme
// *does* guarantee is narrower and real: a screenshot only carries
// pixels, so it carries no signature to submit to /verify. A genuine
// download (or someone hand-typing the fomojiId/seed/signature shown on
// the card) carries the actual signed data, so it WILL verify — the same
// way photographing a passport's barcode still reads as genuine. The
// property this buys you is forgery-resistance (nobody can invent a
// fake card that verifies), not screenshot-prevention. Both fomoji-auth-
// card.js and security.html say this in the same words, on purpose —
// don't let it drift into a stronger claim in either place.
//
// Viewing or downloading the card requires a fresh "unlock" — a step-up
// re-proof of presence, separate from the login session, so a card can't
// be pulled just because a browser tab was left open:
//   - Passkey (preferred): a real WebAuthn assertion, userVerification
//     'required' — this is the standard way a website invokes Face ID /
//     Touch ID / Windows Hello / Android biometric / a security key.
//     There is no other web API that reaches into OS-level device auth.
//   - Password: re-enter the account password.
//   - Custom PIN: a separate secret set via /pin, for identities that
//     want a quick unlock without re-typing their full password.
// Any of the three sets a 5-minute unlock window on the session.
// ---------------------------------------------------------------------

const express = require('express');
const crypto = require('crypto');
const {
  generateAuthenticationOptions,
  verifyAuthenticationResponse,
} = require('@simplewebauthn/server');

const db = require('../db');
const { requireAuth } = require('./auth');
const { hashSecret, verifySecret, sha256Hex } = require('../password');
const { RP_ID, ORIGIN, CARD_SECRET } = require('../config');

const router = express.Router();

const UNLOCK_MS = 5 * 60 * 1000; // step-up unlock window, same order as WebAuthn's own challenge TTL
const CHALLENGE_TTL_MS = 5 * 60 * 1000;

function logEvent(userId, kind, detail) {
  db.prepare(`INSERT INTO auth_events (user_id, kind, detail) VALUES (?, ?, ?)`)
    .run(userId, kind, detail || null);
}

function getOrCreateCard(userId) {
  let row = db.prepare(`SELECT * FROM auth_cards WHERE user_id = ?`).get(userId);
  if (!row) {
    const seed = crypto.randomBytes(32).toString('hex');
    db.prepare(`INSERT INTO auth_cards (user_id, pattern_seed) VALUES (?, ?)`).run(userId, seed);
    row = db.prepare(`SELECT * FROM auth_cards WHERE user_id = ?`).get(userId);
  }
  return row;
}

function signCard(fomojiId, patternSeed) {
  return crypto.createHmac('sha256', CARD_SECRET).update(`${fomojiId}:${patternSeed}`).digest('hex');
}

// True only when the identity has NO way to unlock at all — no password,
// no card PIN, no passkey. Step-up unlock exists to re-prove "this is
// really you" against a secret you hold; if none exists, demanding one
// doesn't add security, it just permanently locks the owner out of their
// own card. In that specific case only, the card is treated as already
// unlocked. This is intentionally narrow: the moment ANY unlock method
// exists (a password, a PIN, or a single passkey), this stops applying
// and a real step-up is required again.
function hasAnyUnlockMethod(userId) {
  const user = db.prepare(`SELECT password_hash FROM users WHERE id = ?`).get(userId);
  if (user && user.password_hash) return true;
  const card = db.prepare(`SELECT pin_hash FROM auth_cards WHERE user_id = ?`).get(userId);
  if (card && card.pin_hash) return true;
  const credCount = db.prepare(`SELECT COUNT(*) AS n FROM credentials WHERE user_id = ?`).get(userId).n;
  return credCount > 0;
}

function requireCardUnlock(req, res, next) {
  if (req.session.cardUnlockedUntil && req.session.cardUnlockedUntil >= Date.now()) return next();
  if (!hasAnyUnlockMethod(req.session.userId)) {
    grantUnlock(req);
    logEvent(req.session.userId, 'auth_card_unlocked', 'no_unlock_method_configured');
    return next();
  }
  return res.status(403).json({ error: 'unlock_required' });
}

function grantUnlock(req) {
  req.session.cardUnlockedUntil = Date.now() + UNLOCK_MS;
}

// Lets the client know, BEFORE attempting an unlock, which methods this
// identity actually has — so the UI can show the right primary action
// instead of defaulting to "try passkey, then discover via an error that
// there isn't one." No unlock required to call this: it reveals only
// booleans, never secrets, and knowing "this account has a PIN" isn't
// sensitive on its own (same session already knows the identity).
router.get('/unlock-status', requireAuth, (req, res) => {
  const user = db.prepare(`SELECT password_hash, recovery_code_hash FROM users WHERE id = ?`).get(req.session.userId);
  const card = db.prepare(`SELECT pin_hash FROM auth_cards WHERE user_id = ?`).get(req.session.userId);
  const credCount = db.prepare(`SELECT COUNT(*) AS n FROM credentials WHERE user_id = ?`).get(req.session.userId).n;
  res.json({
    hasPasskey: credCount > 0,
    hasPassword: !!(user && user.password_hash),
    hasPin: !!(card && card.pin_hash),
    hasRecoveryCode: !!(user && user.recovery_code_hash),
    unlockRequired: hasAnyUnlockMethod(req.session.userId),
  });
});

// ---------------------------------------------------------------------
// Unlock — password or PIN (synchronous, single round trip)
// ---------------------------------------------------------------------

router.post('/unlock/password', requireAuth, (req, res) => {
  const { password } = req.body || {};
  const user = db.prepare(`SELECT * FROM users WHERE id = ?`).get(req.session.userId);
  if (!user || !password || !verifySecret(password, user.password_hash)) {
    return res.status(401).json({ error: 'invalid_credentials' });
  }
  grantUnlock(req);
  logEvent(user.id, 'auth_card_unlocked', 'password');
  res.json({ ok: true, unlockedUntil: req.session.cardUnlockedUntil });
});

// "Forgot passkey" (or forgot password/PIN) falls back to the account's
// recovery code — the same one shown once at registration/password-reset
// time (routes/auth.js). This never changes the password or touches
// credentials; it only proves account ownership well enough to open the
// card, same trust level as the password/PIN paths above.
router.post('/unlock/recovery', requireAuth, (req, res) => {
  const { recoveryCode } = req.body || {};
  const user = db.prepare(`SELECT * FROM users WHERE id = ?`).get(req.session.userId);
  if (!user || !user.recovery_code_hash || !recoveryCode) {
    return res.status(401).json({ error: 'invalid_recovery' });
  }
  const codeHash = sha256Hex(String(recoveryCode).trim().toUpperCase());
  if (codeHash !== user.recovery_code_hash) {
    return res.status(401).json({ error: 'invalid_recovery' });
  }
  grantUnlock(req);
  logEvent(user.id, 'auth_card_unlocked', 'recovery_code');
  res.json({ ok: true, unlockedUntil: req.session.cardUnlockedUntil });
});

router.post('/unlock/pin', requireAuth, (req, res) => {
  const { pin } = req.body || {};
  const card = db.prepare(`SELECT * FROM auth_cards WHERE user_id = ?`).get(req.session.userId);
  if (!card || !card.pin_hash || !pin || !verifySecret(pin, card.pin_hash)) {
    return res.status(401).json({ error: 'invalid_credentials' });
  }
  grantUnlock(req);
  logEvent(req.session.userId, 'auth_card_unlocked', 'pin');
  res.json({ ok: true, unlockedUntil: req.session.cardUnlockedUntil });
});

// Set or change the card PIN. Requires an existing unlock (password or
// passkey) so a stolen-but-still-open session can't silently plant a new
// PIN as a backdoor — this only ever *adds* a second unlock method to an
// already-proven-present session, never bootstraps trust from nothing.
router.post('/pin', requireAuth, requireCardUnlock, (req, res) => {
  const { pin } = req.body || {};
  if (!pin || typeof pin !== 'string' || pin.length < 4 || pin.length > 32) {
    return res.status(400).json({ error: 'invalid_pin' });
  }
  getOrCreateCard(req.session.userId);
  db.prepare(`UPDATE auth_cards SET pin_hash = ? WHERE user_id = ?`).run(hashSecret(pin), req.session.userId);
  logEvent(req.session.userId, 'auth_card_pin_set', null);
  res.json({ ok: true });
});

// ---------------------------------------------------------------------
// Unlock — passkey step-up (real WebAuthn ceremony, scoped to the
// signed-in identity's own credentials, userVerification: 'required' so
// a bare "tap present" security key isn't enough — this specifically
// wants the biometric/PIN gate on the device itself).
// ---------------------------------------------------------------------

router.post('/unlock/webauthn/start', requireAuth, async (req, res) => {
  const creds = db.prepare(`SELECT credential_id, transports FROM credentials WHERE user_id = ?`).all(req.session.userId);
  if (!creds.length) return res.status(409).json({ error: 'no_passkey' });

  const options = await generateAuthenticationOptions({
    rpID: RP_ID,
    userVerification: 'required',
    allowCredentials: creds.map((c) => ({
      id: c.credential_id,
      transports: c.transports ? JSON.parse(c.transports) : undefined,
    })),
  });

  const challengeId = crypto.randomUUID();
  db.prepare(
    `INSERT INTO challenges (id, user_id, challenge, type, expires_at) VALUES (?, ?, ?, 'card_unlock', ?)`
  ).run(challengeId, req.session.userId, options.challenge, new Date(Date.now() + CHALLENGE_TTL_MS).toISOString());

  req.session.pendingCardChallengeId = challengeId;
  res.json({ options });
});

router.post('/unlock/webauthn/finish', requireAuth, async (req, res) => {
  const challengeId = req.session.pendingCardChallengeId;
  if (!challengeId) return res.status(400).json({ error: 'no_pending_challenge' });

  const row = db.prepare(`SELECT * FROM challenges WHERE id = ? AND type = 'card_unlock' AND user_id = ?`)
    .get(challengeId, req.session.userId);
  if (!row) return res.status(400).json({ error: 'challenge_expired_or_unknown' });

  const credentialId = req.body && req.body.id;
  const credRow = credentialId
    ? db.prepare(`SELECT * FROM credentials WHERE credential_id = ? AND user_id = ?`).get(credentialId, req.session.userId)
    : null;
  if (!credRow) return res.status(400).json({ error: 'authentication_failed' });

  let verification;
  try {
    verification = await verifyAuthenticationResponse({
      response: req.body,
      expectedChallenge: row.challenge,
      expectedOrigin: ORIGIN,
      expectedRPID: RP_ID,
      credential: {
        id: credRow.credential_id,
        publicKey: Buffer.from(credRow.public_key, 'base64url'),
        counter: credRow.counter,
        transports: credRow.transports ? JSON.parse(credRow.transports) : undefined,
      },
      requireUserVerification: true,
    });
  } catch (err) {
    console.error('[fomoji:authCard] unlock/webauthn/finish threw —', err.message);
    return res.status(400).json({ error: 'authentication_failed' });
  }
  if (!verification.verified) return res.status(400).json({ error: 'authentication_failed' });

  db.prepare(`DELETE FROM challenges WHERE id = ?`).run(challengeId);
  delete req.session.pendingCardChallengeId;

  const newCounter = verification.authenticationInfo.newCounter;
  db.prepare(`UPDATE credentials SET counter = ?, last_used_at = datetime('now') WHERE credential_id = ?`)
    .run(newCounter, credRow.credential_id);

  grantUnlock(req);
  logEvent(req.session.userId, 'auth_card_unlocked', 'passkey');
  res.json({ ok: true, unlockedUntil: req.session.cardUnlockedUntil });
});

// ---------------------------------------------------------------------
// The card itself — only once step-up unlocked.
// ---------------------------------------------------------------------

router.get('/', requireAuth, requireCardUnlock, (req, res) => {
  const user = db.prepare(`SELECT * FROM users WHERE id = ?`).get(req.session.userId);
  if (!user) return res.status(401).json({ error: 'not_authenticated' });

  const card = getOrCreateCard(user.id);
  const signature = signCard(user.fomoji_id, card.pattern_seed);

  logEvent(user.id, 'auth_card_viewed', null);
  res.json({
    fomojiId: user.fomoji_id,
    name: user.name,
    username: user.username,
    email: user.email,
    // The plaintext recovery code is never stored (see password.js) and
    // so can never be shown again here — only whether one exists.
    hasRecoveryCode: !!user.recovery_code_hash,
    hasPin: !!card.pin_hash,
    patternSeed: card.pattern_seed,
    signature,
    issuedAt: new Date().toISOString(),
  });
});

// Verify a card's data — recompute the HMAC server-side and compare. See
// the file header for exactly what "verified" does and doesn't mean.
router.post('/verify', requireAuth, (req, res) => {
  const { fomojiId, patternSeed, signature } = req.body || {};
  if (!fomojiId || !patternSeed || !signature) {
    return res.json({ verified: false, reason: 'incomplete' });
  }
  const owner = db.prepare(`SELECT id FROM users WHERE fomoji_id = ?`).get(fomojiId);
  if (!owner) return res.json({ verified: false, reason: 'unknown_identity' });

  const card = db.prepare(`SELECT pattern_seed FROM auth_cards WHERE user_id = ?`).get(owner.id);
  if (!card || card.pattern_seed !== patternSeed) return res.json({ verified: false, reason: 'seed_mismatch' });

  const expected = signCard(fomojiId, patternSeed);
  const a = Buffer.from(expected, 'hex');
  const b = Buffer.from(String(signature), 'hex');
  const verified = a.length === b.length && crypto.timingSafeEqual(a, b);
  res.json({ verified, reason: verified ? null : 'bad_signature' });
});

module.exports = router;
