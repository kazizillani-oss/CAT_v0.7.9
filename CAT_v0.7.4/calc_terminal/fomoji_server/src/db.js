// Real persistence layer (SQLite via better-sqlite3 — synchronous, no ORM
// magic, easy to read/audit). Swap the file path for a managed Postgres/etc.
// in production; the schema and query shapes below would carry over
// directly, this is not meant to be a toy that gets thrown away.
'use strict';

// NOTE: this used to run on better-sqlite3, a *native* addon that needs
// node-gyp to compile a C++ binding on install. That compile step can fail
// in sandboxed/managed hosting (no compiler, no network access to fetch
// Node headers, etc.) — when it does, `npm install` fails, the server never
// starts, and every /api/* call the frontend makes gets no real response,
// which is exactly why fomoji-auth.js's catch-all humanizeError() shows
// "Something went wrong. Try again." on literally everything, including
// registration, and why passkeys silently never work either (the WebAuthn
// routes never run). node:sqlite is Node's own built-in SQLite binding
// (stable since Node 22.5+, no compilation, no extra dependency) with a
// near-identical prepare/run/get/all API, so this file is the only one
// that needs to change — auth.js, webauthn.js, and oauth.js are untouched.
const path = require('path');
const fs = require('fs');
const { DatabaseSync } = require('node:sqlite');

const DATA_DIR = path.join(__dirname, '..', 'data');
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

const raw = new DatabaseSync(path.join(DATA_DIR, 'fomoji.sqlite'));

// Thin compatibility layer so every other file's `db.pragma(...)`,
// `db.prepare(...).run/get/all(...)`, and `db.transaction(fn)()` calls
// keep working exactly as they did against better-sqlite3.
const db = {
  exec: (sql) => raw.exec(sql),
  prepare: (sql) => raw.prepare(sql),
  pragma: (setting) => raw.exec(`PRAGMA ${setting}`),
  // better-sqlite3's db.transaction(fn) returns a function that runs fn
  // inside BEGIN/COMMIT, rolling back on throw. node:sqlite has no such
  // helper, so this reproduces it by hand — same call shape, same
  // atomicity, for the two callers (webauthn.js, oauth.js) that use it.
  transaction: (fn) => (...args) => {
    raw.exec('BEGIN');
    try {
      const result = fn(...args);
      raw.exec('COMMIT');
      return result;
    } catch (err) {
      raw.exec('ROLLBACK');
      throw err;
    }
  },
};

db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,      -- internal id, never shown publicly
  fomoji_id     TEXT UNIQUE NOT NULL,  -- public identifier, e.g. FJ-AB12CD34
  name          TEXT,
  username      TEXT UNIQUE,
  email         TEXT UNIQUE,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One row per registered authenticator (passkey / security key). A user can
-- have many — this is what "Connected Login Methods" in the spec lists.
-- credential_id and public_key are stored as base64url TEXT (WebAuthn's own
-- wire format) so nothing here needs bespoke binary handling.
CREATE TABLE IF NOT EXISTS credentials (
  credential_id   TEXT PRIMARY KEY,      -- base64url, globally unique per WebAuthn spec
  user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  public_key      TEXT NOT NULL,         -- base64url COSE public key
  counter         INTEGER NOT NULL DEFAULT 0,
  device_type     TEXT,                  -- 'singleDevice' | 'multiDevice' (passkey sync status)
  backed_up       INTEGER NOT NULL DEFAULT 0,
  transports      TEXT,                  -- JSON array, e.g. ["internal","hybrid"]
  nickname        TEXT,                  -- user-editable label, e.g. "MacBook Touch ID"
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  last_used_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_credentials_user ON credentials(user_id);

-- Short-lived WebAuthn ceremony challenges. A row is deleted the moment it's
-- consumed (or expires), so a challenge can never be replayed — this is what
-- makes "possession of a copied passport PDF" alone insufficient to log in:
-- the PDF names an account, but every login still needs a *fresh* signed
-- challenge from a registered authenticator.
CREATE TABLE IF NOT EXISTS challenges (
  id          TEXT PRIMARY KEY,
  user_id     TEXT REFERENCES users(id) ON DELETE CASCADE, -- NULL for passkey "discoverable" login
  challenge   TEXT NOT NULL,
  type        TEXT NOT NULL,   -- 'registration' | 'authentication'
  -- For 'registration': JSON of the not-yet-real identity (name/username/
  -- email/internal id/fomoji id) the user typed in. Nothing is written to
  -- the users table until verifyRegistrationResponse() succeeds — an
  -- unauthenticated visitor can never mint a permanent Fomoji identity by
  -- just hitting an endpoint, only by completing a real WebAuthn ceremony.
  payload     TEXT,
  expires_at  TEXT NOT NULL
);

-- Authentication activity — section 24 of the spec ("Authentication Activity").
CREATE TABLE IF NOT EXISTS auth_events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind        TEXT NOT NULL,   -- 'login' | 'passkey_added' | 'passkey_removed' | ...
  detail      TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
`);

// ---------------------------------------------------------------------
// Migration: password auth (spec section 1's "Email/password where
// supported"). Added after the initial passkey-only schema above, so it's
// applied with ALTER TABLE rather than baked into the CREATE TABLE, to
// keep existing installs' data intact.
//
// password_hash is `scrypt:<salt-hex>:<hash-hex>` (see src/password.js) —
// Node's built-in, audited scrypt KDF. Never plaintext, never a
// homemade algorithm. recovery_code_hash is a plain SHA-256 of the
// one-time recovery code shown at registration/reset — it's a random,
// high-entropy secret (not a password users choose), so scrypt's
// brute-force resistance isn't needed there.
// ---------------------------------------------------------------------
const userColumns = db.prepare(`PRAGMA table_info(users)`).all().map((c) => c.name);
if (!userColumns.includes('password_hash')) {
  db.exec(`ALTER TABLE users ADD COLUMN password_hash TEXT`);
}
if (!userColumns.includes('recovery_code_hash')) {
  db.exec(`ALTER TABLE users ADD COLUMN recovery_code_hash TEXT`);
}

// ---------------------------------------------------------------------
// Migration: OAuth/OIDC identity providers (Google/Apple/Microsoft/
// GitHub/Facebook — spec doc 2, "Social Login / Identity Providers").
//
// oauth_accounts: one row per (provider, provider_user_id) EVER linked to
// a Fomoji identity. This is the only thing that establishes trust — an
// email match alone never links or logs in an account (spec rule: no
// silent merge-by-email).
//
// oauth_states: the PKCE `state`/`code_verifier` for an in-flight OAuth
// ceremony, keyed by the random `state` value itself rather than the
// session cookie. Apple's callback arrives as a cross-site POST
// (response_mode=form_post), which browsers can drop a SameSite=Lax
// session cookie on — looking the ceremony up by `state` instead sidesteps
// that entirely and works identically for every provider.
// ---------------------------------------------------------------------
db.exec(`
CREATE TABLE IF NOT EXISTS oauth_accounts (
  provider          TEXT NOT NULL,   -- 'google' | 'apple' | 'microsoft' | 'github' | 'facebook'
  provider_user_id  TEXT NOT NULL,   -- stable subject id from the provider, never the email
  user_id           TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  email             TEXT,            -- provider-reported email at link time, display only
  linked_at         TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (provider, provider_user_id)
);
CREATE INDEX IF NOT EXISTS idx_oauth_accounts_user ON oauth_accounts(user_id);

CREATE TABLE IF NOT EXISTS oauth_states (
  state          TEXT PRIMARY KEY,
  provider       TEXT NOT NULL,
  code_verifier  TEXT NOT NULL,
  mode           TEXT NOT NULL,   -- 'login' (new/existing identity) | 'link' (attach to signed-in user)
  user_id        TEXT,            -- set only when mode = 'link'
  created_at     TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at     TEXT NOT NULL
);

-- Config Registry (this doc's request): lets provider Client ID/Secret be
-- entered from the running app itself — Security → Provider Config — since
-- hand-editing .env from a phone is painful. Only used when the matching
-- env var isn't set; env always wins so a real deployment's env config
-- can't be silently overridden by whatever's in the DB. See
-- src/oauthProviders.js for the read order.
--
-- NOTE: secrets are stored in plaintext here, same trust level as this
-- app's other server-side secrets (SESSION_SECRET, password hashes' salt).
-- Anyone who can reach these endpoints can read them back — the routes in
-- routes/oauth.js gate this behind requireAuth (any signed-in Fomoji
-- identity) for now. A production/shared deployment needs a real
-- admin-role check here, not just "is someone logged in".
CREATE TABLE IF NOT EXISTS app_settings (
  key         TEXT PRIMARY KEY,
  value       TEXT NOT NULL,
  updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
`);

// ---------------------------------------------------------------------
// Migration: Fomoji Authentication Card (this doc's request).
//
// pattern_seed is generated ONCE per user, server-side, from crypto random
// bytes — never derived from the user's name/username/email (a derived
// seed could be recomputed by anyone who knew those public-ish facts,
// which would defeat the point). It's what makes the card's visual
// pattern unique per user; the signature below is what makes the card's
// *data* verifiable (see src/routes/authCard.js for how both are used).
// pin_hash is an optional secondary unlock (alongside a step-up passkey
// prompt) for viewing/downloading the card, hashed the same way as
// password_hash — never plaintext.
// ---------------------------------------------------------------------
db.exec(`
CREATE TABLE IF NOT EXISTS auth_cards (
  user_id       TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  pattern_seed  TEXT NOT NULL,
  pin_hash      TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
`);

// ---------------------------------------------------------------------
// Migration: Connector system + identity types (connector.py/js/html
// spec). Fomoji is the identity+auth+connection gateway; CAT and future
// projects are "connected applications" that never see a password or
// passkey — they get a scoped, revocable connector_token instead, minted
// only after a real Fomoji identity approves the request. This is the
// same shape as an OAuth Device Authorization Grant, which is what
// device_codes below implements: it's how a CLI/desktop/Python app with
// no browser of its own gets tied to a web identity without Fomoji ever
// handing out (or the client ever typing) a password.
//
// identity_type on users: PERSON | GROUP | STUDENT | GUEST | TEMPORARY —
// one identity architecture, not five unrelated auth systems (spec
// section 12). Real guest browsing still never touches this table at all
// (it's session-storage-only client state, unchanged); GUEST here is for
// a server-recognized guest identity a connector can be scoped to later.
// expires_at is only ever set for TEMPORARY identities.
// ---------------------------------------------------------------------
const userColumns2 = db.prepare(`PRAGMA table_info(users)`).all().map((c) => c.name);
if (!userColumns2.includes('identity_type')) {
  db.exec(`ALTER TABLE users ADD COLUMN identity_type TEXT NOT NULL DEFAULT 'PERSON'`);
}
if (!userColumns2.includes('expires_at')) {
  db.exec(`ALTER TABLE users ADD COLUMN expires_at TEXT`);
}
// institution: STUDENT-type identities only, always optional (spec section
// 9 — "do NOT require an institutional email unless the institution
// actually requires verification", and nothing here ever does).
if (!userColumns2.includes('institution')) {
  db.exec(`ALTER TABLE users ADD COLUMN institution TEXT`);
}
// avatar/description/accent/surface/depth: profile-card customization,
// shared by PERSON, GROUP and STUDENT identities alike (spec sections 8, 9,
// 16) rather than a separate table per identity type.
if (!userColumns2.includes('avatar')) {
  db.exec(`ALTER TABLE users ADD COLUMN avatar TEXT`);
}
if (!userColumns2.includes('description')) {
  db.exec(`ALTER TABLE users ADD COLUMN description TEXT`);
}
if (!userColumns2.includes('card_style')) {
  // JSON: { accent, surface, depth } — card_style.depth is a per-identity
  // override of the LOW/MEDIUM/HIGH/OFF 3D intensity (fomoji-3d.css); falls
  // back to the viewer's own site-wide appearance setting when null.
  db.exec(`ALTER TABLE users ADD COLUMN card_style TEXT NOT NULL DEFAULT '{}'`);
}

db.exec(`
-- A "connected application" (CAT, a future project, etc). Registered
-- server-side only — never something a browser client can mint itself.
CREATE TABLE IF NOT EXISTS applications (
  application_id          TEXT PRIMARY KEY,
  name                     TEXT NOT NULL,
  description              TEXT,
  icon                     TEXT,
  permissions_available    TEXT NOT NULL DEFAULT '[]',  -- JSON array, subset of connectorPermissions.PERMISSIONS
  environment              TEXT NOT NULL DEFAULT 'production',
  is_first_party           INTEGER NOT NULL DEFAULT 0,
  created_at               TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One row per pending/resolved device-authorization request. device_code
-- is the long, unguessable secret only the requesting client holds;
-- user_code is the short human-typeable code shown to the client and
-- entered (or approved via link) on connector.html. Both are single-use:
-- the row is consumed/expired, never replayed.
CREATE TABLE IF NOT EXISTS device_codes (
  device_code             TEXT PRIMARY KEY,
  user_code                TEXT UNIQUE NOT NULL,
  application_id           TEXT NOT NULL REFERENCES applications(application_id) ON DELETE CASCADE,
  requested_permissions     TEXT NOT NULL DEFAULT '[]', -- JSON array
  connection_type           TEXT NOT NULL DEFAULT 'standard',
  environment               TEXT NOT NULL DEFAULT 'production',
  status                    TEXT NOT NULL DEFAULT 'pending', -- pending | approved | denied | expired
  user_id                   TEXT REFERENCES users(id) ON DELETE CASCADE,
  connection_id             TEXT,
  created_at                TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at                TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_device_codes_user_code ON device_codes(user_code);

-- A live (or revoked) connection between one Fomoji identity and one
-- application. connector_token_hash is SHA-256 of the bearer token
-- handed to the client once at approval time — same treatment as
-- recovery codes in password.js, never stored or logged in plaintext.
CREATE TABLE IF NOT EXISTS connections (
  id                       TEXT PRIMARY KEY,
  user_id                   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  application_id            TEXT NOT NULL REFERENCES applications(application_id) ON DELETE CASCADE,
  permissions_granted       TEXT NOT NULL DEFAULT '[]', -- JSON array
  connection_type           TEXT NOT NULL DEFAULT 'standard',
  environment               TEXT NOT NULL DEFAULT 'production',
  status                    TEXT NOT NULL DEFAULT 'connected', -- connected | revoked
  connector_token_hash      TEXT NOT NULL,
  created_at                TEXT NOT NULL DEFAULT (datetime('now')),
  last_used_at              TEXT,
  expires_at                TEXT,
  UNIQUE(user_id, application_id)
);
CREATE INDEX IF NOT EXISTS idx_connections_user ON connections(user_id);

-- Membership of a PERSON (or STUDENT) identity in a GROUP identity. The
-- group itself is just another row in the users table with
-- identity_type='GROUP' (spec section 12: one identity architecture, not
-- five unrelated auth systems) — this table is the only thing that's
-- actually group-specific: who belongs, and with what role. A group never
-- authenticates on its own; every member still signs in as themselves via
-- the normal identity system and then "continues as" a group they belong
-- to (spec section 7: "the group does NOT replace their personal identity").
CREATE TABLE IF NOT EXISTS group_members (
  group_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  member_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role          TEXT NOT NULL DEFAULT 'member', -- owner | admin | member | guest
  joined_at     TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (group_id, member_id)
);
CREATE INDEX IF NOT EXISTS idx_group_members_member ON group_members(member_id);
`);

// Seed CAT as the first, first-party connector application. INSERT OR
// IGNORE keeps this idempotent across restarts without clobbering any
// permissions an admin later edits by hand.
db.prepare(
  `INSERT OR IGNORE INTO applications
     (application_id, name, description, icon, permissions_available, environment, is_first_party)
   VALUES (?, ?, ?, ?, ?, ?, ?)`
).run(
  'cat',
  'CAT Terminal',
  'Kazi\u2019s chemistry/scientific computing terminal — connect to sign in with your Fomoji identity instead of a separate CAT account.',
  'cat',
  JSON.stringify(['IDENTITY', 'PROFILE', 'CAT_ACCESS', 'PROJECT']),
  'production',
  1
);

module.exports = db;
