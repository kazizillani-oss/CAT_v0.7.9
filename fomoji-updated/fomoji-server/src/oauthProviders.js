'use strict';

const db = require('./db');

// One entry per identity provider. Every value here is either a public,
// documented provider endpoint or a credential (env var or Config Registry
// row) — nothing hard-coded that shouldn't be. `userinfo` tells the
// callback how to turn a token response into { providerUserId, email, name };
// providers without a REST userinfo endpoint (Apple) are read from the
// id_token payload instead, decoded (NOT signature-verified — see the
// comment in routes/oauth.js) since it comes straight from a server-to-
// server call to Apple's own token endpoint, not from anything the browser
// could tamper with in transit.
const PROVIDERS = {
  google: {
    label: 'Google',
    authorizeUrl: 'https://accounts.google.com/o/oauth2/v2/auth',
    tokenUrl: 'https://oauth2.googleapis.com/token',
    userinfoUrl: 'https://openidconnect.googleapis.com/v1/userinfo',
    scope: 'openid email profile',
    clientIdEnv: 'GOOGLE_CLIENT_ID',
    clientSecretEnv: 'GOOGLE_CLIENT_SECRET',
    userinfoAuth: 'bearer',
    map: (u) => ({ providerUserId: u.sub, email: u.email, name: u.name }),
  },
  microsoft: {
    label: 'Microsoft',
    authorizeUrl: 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
    tokenUrl: 'https://login.microsoftonline.com/common/oauth2/v2.0/token',
    userinfoUrl: 'https://graph.microsoft.com/oidc/userinfo',
    scope: 'openid email profile',
    clientIdEnv: 'MICROSOFT_CLIENT_ID',
    clientSecretEnv: 'MICROSOFT_CLIENT_SECRET',
    userinfoAuth: 'bearer',
    map: (u) => ({ providerUserId: u.sub, email: u.email, name: u.name }),
  },
  github: {
    label: 'GitHub',
    authorizeUrl: 'https://github.com/login/oauth/authorize',
    tokenUrl: 'https://github.com/login/oauth/access_token',
    userinfoUrl: 'https://api.github.com/user',
    scope: 'read:user user:email',
    clientIdEnv: 'GITHUB_CLIENT_ID',
    clientSecretEnv: 'GITHUB_CLIENT_SECRET',
    userinfoAuth: 'bearer',
    extraHeaders: { 'User-Agent': 'fomoji-server' },
    // GitHub's /user doesn't always include a public email; a second call
    // to /user/emails is needed when it's null (handled in routes/oauth.js).
    map: (u) => ({ providerUserId: String(u.id), email: u.email || null, name: u.name || u.login }),
  },
  facebook: {
    label: 'Facebook',
    authorizeUrl: 'https://www.facebook.com/v19.0/dialog/oauth',
    tokenUrl: 'https://graph.facebook.com/v19.0/oauth/access_token',
    userinfoUrl: 'https://graph.facebook.com/me',
    userinfoQuery: { fields: 'id,name,email' },
    scope: 'email public_profile',
    clientIdEnv: 'FACEBOOK_CLIENT_ID',
    clientSecretEnv: 'FACEBOOK_CLIENT_SECRET',
    userinfoAuth: 'query', // Facebook expects ?access_token=... rather than a Bearer header
    map: (u) => ({ providerUserId: String(u.id), email: u.email || null, name: u.name }),
  },
  apple: {
    label: 'Apple',
    authorizeUrl: 'https://appleid.apple.com/auth/authorize',
    tokenUrl: 'https://appleid.apple.com/auth/token',
    scope: 'name email',
    clientIdEnv: 'APPLE_CLIENT_ID',
    // Apple's "client secret" is itself a signed JWT you generate offline
    // from your Sign in with Apple private key (.p8) — see .env.example.
    // It's still just an opaque string from this server's point of view.
    clientSecretEnv: 'APPLE_CLIENT_SECRET',
    responseMode: 'form_post', // Apple POSTs the callback, everyone else GETs it
    idTokenOnly: true,         // no userinfo endpoint — read the id_token instead
    map: (u) => ({ providerUserId: u.sub, email: u.email, name: null }),
  },
};

// ---------------------------------------------------------------------
// Config Registry — Client ID/Secret can come from either source below.
// Env vars always win when set, so a real deployment's env config can
// never be silently overridden by a Config Registry row left over from
// testing. When an env var is absent, fall back to app_settings (the
// Config Registry UI at /oauth-config.html writes there).
// ---------------------------------------------------------------------
function dbSetting(key) {
  const row = db.prepare(`SELECT value FROM app_settings WHERE key = ?`).get(key);
  return row ? row.value : null;
}

function settingKey(providerKey, field) {
  return `oauth:${providerKey}:${field}`;
}

function credentials(providerKey) {
  const p = PROVIDERS[providerKey];
  const clientId = process.env[p.clientIdEnv] || dbSetting(settingKey(providerKey, 'clientId')) || null;
  const clientSecret = process.env[p.clientSecretEnv] || dbSetting(settingKey(providerKey, 'clientSecret')) || null;
  return { clientId, clientSecret };
}

function credentialSource(providerKey) {
  const p = PROVIDERS[providerKey];
  if (process.env[p.clientIdEnv] && process.env[p.clientSecretEnv]) return 'env';
  if (dbSetting(settingKey(providerKey, 'clientId')) && dbSetting(settingKey(providerKey, 'clientSecret'))) return 'registry';
  return 'none';
}

function isConfigured(providerKey) {
  const { clientId, clientSecret } = credentials(providerKey);
  return Boolean(clientId && clientSecret);
}

function setRegistryCredentials(providerKey, clientId, clientSecret) {
  const now = new Date().toISOString();
  const upsert = db.prepare(
    `INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)
     ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at`
  );
  upsert.run(settingKey(providerKey, 'clientId'), clientId, now);
  upsert.run(settingKey(providerKey, 'clientSecret'), clientSecret, now);
}

function clearRegistryCredentials(providerKey) {
  db.prepare(`DELETE FROM app_settings WHERE key IN (?, ?)`).run(
    settingKey(providerKey, 'clientId'),
    settingKey(providerKey, 'clientSecret')
  );
}

module.exports = {
  PROVIDERS,
  isConfigured,
  credentials,
  credentialSource,
  setRegistryCredentials,
  clearRegistryCredentials,
};
