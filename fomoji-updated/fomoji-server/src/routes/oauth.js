'use strict';

const express = require('express');
const crypto = require('crypto');

const db = require('../db');
const { randomFomojiId, randomInternalId } = require('../id');
const { ORIGIN } = require('../config');
const { PROVIDERS, isConfigured, credentials, credentialSource, setRegistryCredentials, clearRegistryCredentials } = require('../oauthProviders');

const router = express.Router();

const STATE_TTL_MS = 10 * 60 * 1000; // 10 minutes to complete the redirect round-trip

function redirectUri(providerKey) {
  return `${ORIGIN}/api/oauth/${providerKey}/callback`;
}

function deleteExpiredStates() {
  db.prepare(`DELETE FROM oauth_states WHERE expires_at < datetime('now')`).run();
}

function logEvent(userId, kind, detail) {
  db.prepare(`INSERT INTO auth_events (user_id, kind, detail) VALUES (?, ?, ?)`).run(userId, kind, detail || null);
}

// base64url helpers — PKCE (RFC 7636) needs these, and Apple's id_token is
// a standard base64url-encoded JWT. Both are just encoding, not crypto.
function b64url(buf) {
  return buf.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function decodeJwtPayload(jwt) {
  const parts = jwt.split('.');
  if (parts.length < 2) throw new Error('malformed_id_token');
  return JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf8'));
}

// ---------------------------------------------------------------------
// GET /api/oauth/providers — which providers are actually configured, so
// the frontend can show "Not configured" instead of a button that 400s.
// ---------------------------------------------------------------------
router.get('/oauth/providers', (req, res) => {
  const status = {};
  for (const key of Object.keys(PROVIDERS)) {
    status[key] = { label: PROVIDERS[key].label, configured: isConfigured(key) };
  }
  res.json({ providers: status });
});

// ---------------------------------------------------------------------
// Config Registry (Security → Provider Config) — lets Client ID/Secret be
// entered from the app itself instead of hand-editing .env. Gated behind
// requireAuth: any signed-in Fomoji identity can read/write this right
// now, which is fine for a single-owner dev deployment but is NOT a real
// admin-role check — tighten this before this app has more than one user.
// Secrets are never echoed back once saved, only whether one is set.
// ---------------------------------------------------------------------
function requireAuth(req, res, next) {
  if (!req.session.userId) return res.status(401).json({ error: 'not_authenticated' });
  next();
}

router.get('/admin/oauth-config', requireAuth, (req, res) => {
  const providers = Object.entries(PROVIDERS).map(([key, p]) => {
    const { clientId } = credentials(key);
    const source = credentialSource(key);
    return {
      key,
      label: p.label,
      source,                                  // 'env' | 'registry' | 'none'
      clientId: source === 'env' ? clientId : (source === 'registry' ? clientId : ''),
      secretSet: source !== 'none',
      editable: source !== 'env',              // env vars always win; don't pretend editing does anything
      redirectUri: `${ORIGIN}/api/oauth/${key}/callback`,
    };
  });
  res.json({ providers });
});

router.post('/admin/oauth-config/:provider', requireAuth, (req, res) => {
  const providerKey = req.params.provider;
  const provider = PROVIDERS[providerKey];
  if (!provider) return res.status(404).json({ error: 'unknown_provider' });
  if (credentialSource(providerKey) === 'env') {
    return res.status(409).json({ error: 'env_managed', message: 'This provider is configured via .env on the server — remove those env vars first to edit it here.' });
  }

  const { clientId, clientSecret } = req.body || {};
  if (!clientId || typeof clientId !== 'string' || !clientSecret || typeof clientSecret !== 'string') {
    return res.status(400).json({ error: 'invalid_credentials' });
  }

  setRegistryCredentials(providerKey, clientId.trim(), clientSecret.trim());
  logEvent(req.session.userId, 'oauth_config_saved', providerKey);
  console.log('[fomoji:oauth] config registry updated for %s (value not logged)', providerKey);
  res.json({ ok: true });
});

router.delete('/admin/oauth-config/:provider', requireAuth, (req, res) => {
  const providerKey = req.params.provider;
  if (!PROVIDERS[providerKey]) return res.status(404).json({ error: 'unknown_provider' });
  if (credentialSource(providerKey) === 'env') {
    return res.status(409).json({ error: 'env_managed', message: 'This provider is configured via .env on the server.' });
  }
  clearRegistryCredentials(providerKey);
  logEvent(req.session.userId, 'oauth_config_cleared', providerKey);
  res.json({ ok: true });
});

// ---------------------------------------------------------------------
// GET /api/oauth/:provider/start — begin the ceremony. Works identically
// whether the user is currently signed in (→ "link this provider to my
// existing Fomoji identity") or signed out (→ "sign me in, creating a new
// identity only if no link exists yet").
// ---------------------------------------------------------------------
router.get('/oauth/:provider/start', (req, res) => {
  deleteExpiredStates();

  const providerKey = req.params.provider;
  const provider = PROVIDERS[providerKey];
  if (!provider) return res.status(404).json({ error: 'unknown_provider' });
  if (!isConfigured(providerKey)) return res.status(503).json({ error: 'provider_not_configured' });

  const { clientId } = credentials(providerKey);
  const state = b64url(crypto.randomBytes(24));
  const codeVerifier = b64url(crypto.randomBytes(32));
  const codeChallenge = b64url(crypto.createHash('sha256').update(codeVerifier).digest());

  const mode = req.session.userId ? 'link' : 'login';
  const expiresAt = new Date(Date.now() + STATE_TTL_MS).toISOString();
  db.prepare(
    `INSERT INTO oauth_states (state, provider, code_verifier, mode, user_id, expires_at) VALUES (?, ?, ?, ?, ?, ?)`
  ).run(state, providerKey, codeVerifier, mode, mode === 'link' ? req.session.userId : null, expiresAt);

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri(providerKey),
    response_type: 'code',
    scope: provider.scope,
    state,
    code_challenge: codeChallenge,
    code_challenge_method: 'S256',
  });
  if (provider.responseMode) params.set('response_mode', provider.responseMode);

  console.log('[fomoji:oauth] %s/start ok — mode=%s', providerKey, mode);
  res.redirect(`${provider.authorizeUrl}?${params.toString()}`);
});

// ---------------------------------------------------------------------
// GET|POST /api/oauth/:provider/callback — every provider except Apple
// redirects here with a GET; Apple POSTs (response_mode=form_post), which
// is why server.js adds express.urlencoded() ahead of this router.
// ---------------------------------------------------------------------
router.all('/oauth/:provider/callback', async (req, res) => {
  deleteExpiredStates();

  const providerKey = req.params.provider;
  const provider = PROVIDERS[providerKey];
  if (!provider) return res.status(404).send('Unknown provider.');

  const params = req.method === 'POST' ? req.body : req.query;
  const { code, state, error: providerError } = params || {};

  if (providerError) {
    console.warn('[fomoji:oauth] %s/callback: provider returned error=%s', providerKey, providerError);
    return res.redirect(`/index.html?oauthError=${encodeURIComponent(providerKey)}`);
  }
  if (!code || !state) return res.status(400).send('Missing code or state.');

  const stateRow = db.prepare(`SELECT * FROM oauth_states WHERE state = ? AND provider = ?`).get(state, providerKey);
  // One-time use regardless of outcome below — never let a state be replayed.
  if (stateRow) db.prepare(`DELETE FROM oauth_states WHERE state = ?`).run(state);
  if (!stateRow) {
    console.warn('[fomoji:oauth] %s/callback: state not found (expired >10min, already used, or forged)', providerKey);
    return res.status(400).send('This sign-in link has expired. Please try again.');
  }

  const { clientId, clientSecret } = credentials(providerKey);

  let tokenRes, tokenBody;
  try {
    tokenRes = await fetch(provider.tokenUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', Accept: 'application/json' },
      body: new URLSearchParams({
        client_id: clientId,
        client_secret: clientSecret,
        grant_type: 'authorization_code',
        code,
        redirect_uri: redirectUri(providerKey),
        code_verifier: stateRow.code_verifier,
      }),
    });
    tokenBody = await tokenRes.json();
  } catch (err) {
    console.error('[fomoji:oauth] %s/callback: token exchange request failed — %s', providerKey, err.message);
    return res.status(502).send('Could not reach the identity provider. Please try again.');
  }
  if (!tokenRes.ok || !tokenBody.access_token && !tokenBody.id_token) {
    console.error('[fomoji:oauth] %s/callback: token exchange rejected — status=%s body_error=%s', providerKey, tokenRes.status, tokenBody.error);
    return res.status(400).send('Sign-in was not verified by the provider.');
  }

  let profile;
  try {
    if (provider.idTokenOnly) {
      // Apple: identity comes from the id_token issued directly by
      // appleid.apple.com over this server-to-server call. Production
      // should additionally verify its signature against Apple's published
      // JWKS (https://appleid.apple.com/auth/keys) before trusting it long
      // term; decoding-only is the minimal foundation here.
      const claims = decodeJwtPayload(tokenBody.id_token);
      profile = provider.map(claims);
    } else {
      const url = new URL(provider.userinfoUrl);
      if (provider.userinfoQuery) {
        for (const [k, v] of Object.entries(provider.userinfoQuery)) url.searchParams.set(k, v);
      }
      const headers = { Accept: 'application/json', ...(provider.extraHeaders || {}) };
      if (provider.userinfoAuth === 'bearer') headers.Authorization = `Bearer ${tokenBody.access_token}`;
      if (provider.userinfoAuth === 'query') url.searchParams.set('access_token', tokenBody.access_token);

      const infoRes = await fetch(url, { headers });
      const infoBody = await infoRes.json();
      if (!infoRes.ok) throw new Error(`userinfo_failed:${infoRes.status}`);
      profile = provider.map(infoBody);

      // GitHub often omits email from /user when it's private; fall back
      // to the dedicated emails endpoint and use the primary+verified one.
      if (providerKey === 'github' && !profile.email) {
        const emailsRes = await fetch('https://api.github.com/user/emails', {
          headers: { Authorization: `Bearer ${tokenBody.access_token}`, 'User-Agent': 'fomoji-server', Accept: 'application/json' },
        });
        const emails = await emailsRes.json().catch(() => []);
        const primary = Array.isArray(emails) ? emails.find((e) => e.primary && e.verified) : null;
        if (primary) profile.email = primary.email;
      }
    }
  } catch (err) {
    console.error('[fomoji:oauth] %s/callback: profile fetch failed — %s', providerKey, err.message);
    return res.status(502).send('Could not read your profile from the provider.');
  }

  if (!profile.providerUserId) {
    console.error('[fomoji:oauth] %s/callback: provider returned no stable subject id', providerKey);
    return res.status(502).send('The provider did not return a usable identity.');
  }

  const existingLink = db
    .prepare(`SELECT * FROM oauth_accounts WHERE provider = ? AND provider_user_id = ?`)
    .get(providerKey, profile.providerUserId);

  // ---- Linking an already-signed-in Fomoji identity ----
  if (stateRow.mode === 'link') {
    if (existingLink && existingLink.user_id !== stateRow.user_id) {
      console.warn('[fomoji:oauth] %s/callback: link blocked — already linked to a different Fomoji identity', providerKey);
      return res.redirect(`/security.html?linkError=${providerKey}_in_use`);
    }
    if (!existingLink) {
      db.prepare(
        `INSERT INTO oauth_accounts (provider, provider_user_id, user_id, email) VALUES (?, ?, ?, ?)`
      ).run(providerKey, profile.providerUserId, stateRow.user_id, profile.email || null);
      logEvent(stateRow.user_id, 'provider_linked', providerKey);
    }
    return res.redirect(`/security.html?linked=${providerKey}`);
  }

  // ---- Signing in (no active session) ----
  if (existingLink) {
    // Known link → this is a real login, not account creation.
    req.session.userId = existingLink.user_id;
    logEvent(existingLink.user_id, 'login', providerKey);
    console.log('[fomoji:oauth] %s/callback: login ok — userId=%s', providerKey, existingLink.user_id);
    return res.redirect('/home.html');
  }

  // No link yet. Per spec: NEVER silently merge onto an existing account
  // just because the email matches — only an authenticated "link" ceremony
  // (above) may attach a provider to an existing identity. If the email
  // does match something on file, send the person to sign in with what
  // they already have and link from there, instead of quietly creating a
  // second identity that fragments their history.
  if (profile.email) {
    const emailOwner = db.prepare(`SELECT id FROM users WHERE email = ?`).get(profile.email);
    if (emailOwner) {
      console.log('[fomoji:oauth] %s/callback: email matches an existing identity — declining auto-merge, sending to manual link', providerKey);
      return res.redirect(`/index.html?linkNeeded=${providerKey}`);
    }
  }

  let fomojiId;
  do {
    fomojiId = randomFomojiId();
  } while (db.prepare(`SELECT 1 FROM users WHERE fomoji_id = ?`).get(fomojiId));
  const internalId = randomInternalId();

  const tx = db.transaction(() => {
    db.prepare(
      `INSERT INTO users (id, fomoji_id, name, username, email) VALUES (?, ?, ?, NULL, ?)`
    ).run(internalId, fomojiId, profile.name || provider.label + ' user', profile.email || null);
    db.prepare(
      `INSERT INTO oauth_accounts (provider, provider_user_id, user_id, email) VALUES (?, ?, ?, ?)`
    ).run(providerKey, profile.providerUserId, internalId, profile.email || null);
    logEvent(internalId, 'account_created', providerKey);
  });
  tx();

  req.session.userId = internalId;
  console.log('[fomoji:oauth] %s/callback: new Fomoji identity created — userId=%s', providerKey, internalId);
  res.redirect('/home.html');
});

// ---------------------------------------------------------------------
// GET /api/oauth/linked — which providers the signed-in identity has, for
// the Account Linking Center / Security page.
// ---------------------------------------------------------------------
router.get('/oauth/linked', (req, res) => {
  if (!req.session.userId) return res.status(401).json({ error: 'not_authenticated' });
  const rows = db.prepare(`SELECT provider, email, linked_at FROM oauth_accounts WHERE user_id = ?`).all(req.session.userId);
  res.json({ linked: rows });
});

// ---------------------------------------------------------------------
// DELETE /api/oauth/:provider — unlink, same "never remove your last
// sign-in method" rule as passkeys/password.
// ---------------------------------------------------------------------
router.delete('/oauth/:provider', (req, res) => {
  if (!req.session.userId) return res.status(401).json({ error: 'not_authenticated' });
  const providerKey = req.params.provider;

  const link = db
    .prepare(`SELECT * FROM oauth_accounts WHERE provider = ? AND user_id = ?`)
    .get(providerKey, req.session.userId);
  if (!link) return res.status(404).json({ error: 'not_found' });

  const passkeyCount = db.prepare(`SELECT COUNT(*) AS n FROM credentials WHERE user_id = ?`).get(req.session.userId).n;
  const otherProviderCount = db
    .prepare(`SELECT COUNT(*) AS n FROM oauth_accounts WHERE user_id = ? AND provider != ?`)
    .get(req.session.userId, providerKey).n;
  const user = db.prepare(`SELECT password_hash FROM users WHERE id = ?`).get(req.session.userId);

  if (passkeyCount === 0 && otherProviderCount === 0 && !user.password_hash) {
    return res.status(409).json({ error: 'last_method', message: 'This is your only sign-in method. Add another before removing it.' });
  }

  db.prepare(`DELETE FROM oauth_accounts WHERE provider = ? AND user_id = ?`).run(providerKey, req.session.userId);
  logEvent(req.session.userId, 'provider_unlinked', providerKey);
  res.json({ ok: true });
});

module.exports = router;
