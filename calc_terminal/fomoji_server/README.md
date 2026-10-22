# Fomoji — real backend + Passkey/WebAuthn + password auth (Phase 2 of the Identity Passport spec)

This is a genuine, working authentication backend — not a mock. It uses:

- **[@simplewebauthn/server](https://simplewebauthn.dev/)** — the standard, audited
  library for FIDO2/WebAuthn on Node. No hand-rolled cryptography.
- **Node's built-in `crypto.scrypt`** — for password hashing (see `src/password.js`).
  Also standard, also not hand-rolled.
- **better-sqlite3** — real persistence (`data/fomoji.sqlite`), survives restarts.
- **express-session** — real server-side sessions via an httpOnly cookie.

## What this delivers (spec sections 1–3, 15, 24 — real, not mocked)

- A real Fomoji Identity (`FJ-XXXXXXXX`) created via passkey registration OR
  password registration — never before either one actually succeeds server-side.
- Real passkey login (Face ID / Touch ID / Windows Hello / security keys),
  usernameless via discoverable credentials.
- Real password login: scrypt-hashed, never plaintext, with a login-attempt
  lockout and a one-time recovery code (SHA-256 hashed) as the only reset path.
- Multiple passkeys per identity ("Account Linking Center" foundation):
  list, rename, and remove — with a hard rule that you can never remove your
  last sign-in method (a passkey now also checks whether a password exists,
  and vice versa isn't needed since password is set-or-not, not removable
  on its own without leaving a passkey behind, at least until an explicit
  "remove password" endpoint exists).
- The existing Fomoji front-end (home, settings, security, login, signup,
  welcome, about, help, manual, cat-manual) now talks to this real backend
  instead of the old localStorage mock. Guest browsing and CAT
  connection-state remain intentionally local-only — the backend has no
  concept of either yet (that's a later phase per the spec).
- Real authentication activity log.
- Cloned-credential detection via the WebAuthn signature counter.

**Not yet built** (next phases, per your priority order): Google/Apple/
Microsoft/GitHub/Facebook OAuth, and the Fomoji Passport PDF + QR. Also
not yet built: a dedicated "Account Linking Center" UI panel (the backend
endpoints for listing/renaming/removing passkeys exist and are used by
passkey.html's ceremonies, but no page yet surfaces "here are all your
passkeys, manage them here" as its own view).

## Run it

```bash
npm install
cp .env.example .env      # defaults work as-is for local dev
npm start
```

Open **http://localhost:3000** — not `127.0.0.1`, and not a different port
than `ORIGIN` in `.env`. WebAuthn is strict about this: RP_ID + ORIGIN must
match exactly what's in the address bar, by design (that's what stops a
phishing site from replaying a passkey ceremony against a fake domain).

Try both real sign-up paths from the login/signup pages: "Create Fomoji
account" (password) and "Continue with Passkey" → "Create Fomoji ID"
(passkey). Then sign out and back in with whichever you used.

## Going to production

1. Deploy behind real HTTPS on your real domain.
2. Set `RP_ID` to that domain, `ORIGIN` to the exact `https://` URL, and a
   real random `SESSION_SECRET`.
3. Swap `express-session`'s default `MemoryStore` for a real store
   (`connect-sqlite3`, `connect-redis`, etc.) — MemoryStore is dev-only and
   will leak memory / lose sessions on restart under real traffic. The
   password-login lockout in `src/routes/auth.js` has the same caveat —
   it's an in-memory `Map`, move it to the DB or a shared store too.
4. Point `better-sqlite3` at a persistent volume, or swap it for Postgres —
   the schema in `src/db.js` was written to carry over directly.

## Project layout

```
src/
  config.js     RP ID / origin / session secret, from env
  db.js         SQLite schema — users, credentials, challenges, auth_events
  id.js         Fomoji ID generator (FJ-XXXXXXXX)
  password.js   scrypt password hashing + recovery-code generation
  server.js     Express app, sessions, static file serving
  routes/
    webauthn.js passkey registration + authentication ceremonies
    auth.js     session, password auth, profile, credential management, activity log
public/         the existing Fomoji front-end, now wired to the real backend +
                 passkey.html + js/fomoji-webauthn.js + vendored SimpleWebAuthn browser lib
```

