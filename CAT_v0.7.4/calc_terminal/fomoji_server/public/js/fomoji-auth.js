/* ==========================================================================
   FOMOJI — identity adapter (v3, real backend)

   This talks to the actual Node/WebAuthn/SQLite backend in src/ — nothing
   here fakes success or hashes anything client-side anymore. Two things on
   purpose remain LOCAL ONLY, and are clearly separated below, because the
   backend has no concept of them yet:

     - Guest browsing: never becomes a server account. It's a client-side
       "look around without signing up" mode, and it never claims to be
       secure identity — it just lasts up to 2 hours in this tab.
     - Connected-app state (e.g. "CAT connected"): spec section 31
       (CAT/authorization integration) hasn't been built server-side yet,
       so this is still recorded locally, scoped to the real Fomoji ID
       once you have one instead of a fake local account id.

   Passkey/WebAuthn ceremonies live in fomoji-webauthn.js (loaded on
   passkey.html). This file covers what every other page needs: checking
   who's signed in, password auth, profile/credential/activity management,
   and logout — all via real fetch() calls to /api/*.
   ========================================================================== */

const FomojiStore = (() => {
  const readJSON = (storage, key, fallback) => {
    try {
      const raw = storage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch { return fallback; }
  };
  const writeJSON = (storage, key, value) => storage.setItem(key, JSON.stringify(value));

  return {
    // Guest session — sessionStorage only. Ends with the tab, on purpose.
    getGuestSession: () => readJSON(sessionStorage, 'fomoji_guest_session_v3', null),
    setGuestSession: (s) => writeJSON(sessionStorage, 'fomoji_guest_session_v3', s),
    // Clears the guest identity itself AND every piece of state scoped to
    // it (connector connections, in-flight connect-modal state). This is
    // what "sign out" means for a guest — without it, a new guest session
    // started in the same tab silently inherits the previous guest's
    // connector connections, which is not actually signed out.
    clearGuestSession: () => {
      sessionStorage.removeItem('fomoji_guest_session_v3');
      sessionStorage.removeItem('fomoji_guest_connections_v3');
    },

    getPrefs: () => readJSON(localStorage, 'fomoji_prefs_v2', { reducedMotion: false }),
    savePrefs: (obj) => writeJSON(localStorage, 'fomoji_prefs_v2', obj),

    // App connections — local only until spec section 31 (CAT
    // authorization) has a real server endpoint. Keyed by Fomoji ID for
    // real accounts, so at least it's tied to the genuine identity.
    getAllConnections: () => readJSON(localStorage, 'fomoji_connections_v3', {}),
    saveAllConnections: (obj) => writeJSON(localStorage, 'fomoji_connections_v3', obj),
    getGuestConnections: () => readJSON(sessionStorage, 'fomoji_guest_connections_v3', {}),
    saveGuestConnections: (obj) => writeJSON(sessionStorage, 'fomoji_guest_connections_v3', obj),
  };
})();

// Client-side field validation for instant feedback — the real backend
// re-validates everything server-side too (never trust the client alone),
// this just avoids a round trip for obviously-invalid input.
const FomojiValidate = {
  name: (v) => v.trim().length >= 2 || 'Enter your full name.',
  username: (v) => /^[a-zA-Z0-9_]{3,20}$/.test(v) || 'Usernames are 3–20 characters: letters, numbers, underscore.',
  email: (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) || 'Enter a valid email address.',
  password: (v) => v.length >= 8 || 'Use at least 8 characters.',
  matches: (a, b) => a === b || 'Passwords don\u2019t match.',

  passwordStrength(v) {
    let score = 0;
    if (v.length >= 8) score++;
    if (v.length >= 12) score++;
    if (/[A-Z]/.test(v) && /[a-z]/.test(v)) score++;
    if (/[0-9]/.test(v) && /[^A-Za-z0-9]/.test(v)) score++;
    return Math.min(score, 4);
  },
};

class FomojiAuthError extends Error {}

const FomojiAPI = (() => {
  const GUEST_TTL_MS = 2 * 60 * 60 * 1000; // 2h — shorter than a real session, never "remembered"

  function humanizeError(code) {
    switch (code) {
      case 'invalid_username': return 'Usernames are at least 3 characters.';
      case 'invalid_email': return 'Enter a valid email address.';
      case 'invalid_password': return 'Use at least 8 characters.';
      case 'invalid_name': return 'Enter your full name.';
      case 'username_taken': return 'That username is already taken.';
      case 'email_taken': return 'An account with that email already exists.';
      case 'invalid_credentials': return 'That email/username or password is incorrect.';
      case 'invalid_recovery': return 'Enter your email/username and recovery code correctly.';
      case 'locked': return 'Too many attempts. Try again in a bit.';
      case 'not_authenticated': return 'You need to be signed in to do that.';
      case 'last_method': return 'This is your only sign-in method — add another before removing it.';
      default: return 'Something went wrong. Try again.';
    }
  }

  async function request(method, url, body) {
    const res = await fetch(url, {
      method,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      credentials: 'same-origin',
      // keepalive lets a fire-and-forget logout finish even if the page
      // navigates away immediately after — see logout() below.
      keepalive: method !== 'GET',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new FomojiAuthError(data.message || humanizeError(data.error));
    return data;
  }

  // Server sends { fomojiId, name, username, email, hasPassword }. Add an
  // `id` alias (= fomojiId) so existing UI code that reads `account.id`
  // keeps working without treating it as a secret — the Fomoji ID is
  // public by design (see src/id.js).
  function normalizeUser(user, sessionExpiresAt) {
    if (!user) return null;
    return { ...user, id: user.fomojiId, isGuest: false, expiresAt: sessionExpiresAt || null };
  }

  return {
    // ---- real session, backed by the httpOnly session cookie ----
    async fetchSession() {
      const data = await request('GET', '/api/session');
      return normalizeUser(data.user, data.sessionExpiresAt);
    },
    async logout() {
      FomojiStore.clearGuestSession();
      try { await request('POST', '/api/logout'); } catch { /* best effort */ }
    },

    // ---- real password auth ----
    async register({ name, username, email, password }) {
      const data = await request('POST', '/api/password/register', { name, username, email, password });
      return { account: normalizeUser(data.user, data.sessionExpiresAt), recoveryCode: data.recoveryCode };
    },
    async login({ identifier, password }) {
      const data = await request('POST', '/api/password/login', { identifier, password });
      return { account: normalizeUser(data.user, data.sessionExpiresAt) };
    },
    async resetPassword({ identifier, recoveryCode, newPassword }) {
      const data = await request('POST', '/api/password/reset', { identifier, recoveryCode, newPassword });
      return { newRecoveryCode: data.newRecoveryCode };
    },
    async changePassword({ currentPassword, newPassword }) {
      const data = await request('POST', '/api/password/change', { currentPassword, newPassword });
      return { recoveryCode: data.recoveryCode || null };
    },
    async updateProfile({ name }) {
      const data = await request('PATCH', '/api/profile', { name });
      return normalizeUser(data.user);
    },

    // ---- server-backed temporary identities (spec section 11) — distinct
    // from local-only guest browsing above: this is a real, expiring
    // Fomoji account that can hold connector connections and later be
    // upgraded to permanent. ----
    async createTemporary({ name, hours } = {}) {
      const data = await request('POST', '/api/temporary/create', { name, hours });
      return { account: normalizeUser(data.user, data.sessionExpiresAt) };
    },
    async upgradeTemporary({ username, email, password }) {
      const data = await request('POST', '/api/temporary/upgrade', { username, email, password });
      return { account: normalizeUser(data.user), recoveryCode: data.recoveryCode };
    },

    // ---- passkeys / credentials / activity — real, same endpoints
    // fomoji-webauthn.js uses for the registration/login ceremonies ----
    async listCredentials() { return (await request('GET', '/api/credentials')).credentials; },
    async renameCredential(id, nickname) { return request('PATCH', `/api/credentials/${encodeURIComponent(id)}`, { nickname }); },
    async removeCredential(id) { return request('DELETE', `/api/credentials/${encodeURIComponent(id)}`); },
    async listActivity() { return (await request('GET', '/api/activity')).events; },

    // ---- guest browsing: local only, never a real identity ----
    continueAsGuest() {
      const suffix = Array.from(crypto.getRandomValues(new Uint8Array(4))).map(b => b.toString(16).padStart(2, '0')).join('').slice(0, 6);
      const session = { username: `guest_${suffix}`, issuedAt: Date.now(), expiresAt: Date.now() + GUEST_TTL_MS };
      FomojiStore.setGuestSession(session);
      return { account: { id: null, name: 'Guest', username: session.username, email: null, isGuest: true, expiresAt: session.expiresAt } };
    },
    getGuestAccount() {
      const s = FomojiStore.getGuestSession();
      if (!s) return null;
      if (Date.now() > s.expiresAt) { FomojiStore.clearGuestSession(); return null; }
      return { id: null, name: 'Guest', username: s.username, email: null, isGuest: true, expiresAt: s.expiresAt };
    },

    // ---- app connections (local only — see FomojiStore note above) ----
    getConnections(account) {
      if (!account) return {};
      if (account.isGuest) return FomojiStore.getGuestConnections();
      if (!account.id) return {};
      return FomojiStore.getAllConnections()[account.id] || {};
    },
    async connectApp(account, appId) {
      if (!account) throw new FomojiAuthError('No identity to connect.');
      if (account.isGuest) {
        const conns = FomojiStore.getGuestConnections();
        conns[appId] = { connectedAt: new Date().toISOString() };
        FomojiStore.saveGuestConnections(conns);
        return conns[appId];
      }
      const all = FomojiStore.getAllConnections();
      all[account.id] = all[account.id] || {};
      all[account.id][appId] = { connectedAt: new Date().toISOString() };
      FomojiStore.saveAllConnections(all);
      return all[account.id][appId];
    },
    async disconnectApp(account, appId) {
      if (!account) return true;
      if (account.isGuest) {
        const conns = FomojiStore.getGuestConnections();
        delete conns[appId];
        FomojiStore.saveGuestConnections(conns);
        return true;
      }
      const all = FomojiStore.getAllConnections();
      if (all[account.id]) { delete all[account.id][appId]; FomojiStore.saveAllConnections(all); }
      return true;
    },
  };
})();

/* redirect handling — lets another app in the ecosystem (e.g. CAT) send a
   user here with ?redirect_uri=... the way "Login with Fomoji" is meant to
   work once those apps exist. Only same-app-relative or explicit https
   targets are honored — never an arbitrary javascript:/data: URI. */
function getSafeRedirect(fallback = 'home.html') {
  const params = new URLSearchParams(window.location.search);
  const target = params.get('redirect_uri');
  if (!target) return fallback;
  if (/^https:\/\//.test(target) || /^\.?\//.test(target)) return target;
  return fallback;
}

/* Async gate for any page that requires a signed-in session (real or
   guest). Checks the local guest session first (no network needed), then
   asks the server for a real one. Redirects to login if neither exists.
   Callers: `const account = await requireSession(); if (!account) return;` */
async function requireSession() {
  const guest = FomojiAPI.getGuestAccount();
  if (guest) return guest;

  let account = null;
  try { account = await FomojiAPI.fetchSession(); } catch { /* treat as signed out */ }

  if (!account) {
    // Preserve full path + query string so ?code=XXXX-XXXX survives the redirect
    const fullPage = encodeURIComponent(window.location.pathname.split('/').pop() + window.location.search);
    window.location.replace(`index.html?redirect_uri=${fullPage}`);
    return null;
  }
  return account;
}
