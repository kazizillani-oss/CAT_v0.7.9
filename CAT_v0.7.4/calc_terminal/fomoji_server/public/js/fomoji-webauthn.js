/* ==========================================================================
   FOMOJI — real passkey client (talks to the actual Node/WebAuthn backend
   in src/, NOT the localStorage mock in fomoji-auth.js). Requires:
     <script src="vendor/simplewebauthn-browser.min.js"></script>
   loaded first, which exposes window.SimpleWebAuthnBrowser.
   ========================================================================== */
// WebAuthn requires hostname 'localhost', not '127.0.0.1' (IP addresses are rejected by navigator.credentials)
if (typeof window !== 'undefined' && window.location.hostname === '127.0.0.1') {
  try {
    const newUrl = new URL(window.location.href);
    newUrl.hostname = 'localhost';
    window.location.replace(newUrl.toString());
  } catch (_) {}
}

const FomojiWebAuthn = (() => {
  async function postJSON(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new FomojiWebAuthnError(data.message || humanizeError(data.error), data.error);
    return data;
  }

  function humanizeError(code) {
    switch (code) {
      case 'invalid_username': return 'Choose a username at least 3 characters long.';
      case 'username_taken': return 'That username is already taken.';
      case 'email_taken': return 'An account with that email already exists.';
      case 'authentication_failed': return 'Could not verify that passkey. Please try again.';
      case 'last_method': return 'This is your only sign-in method — add another before removing it.';
      case 'not_authenticated': return 'You need to be signed in to do that.';
      default: return 'Something went wrong. Please try again.';
    }
  }

  return {
    // Create a brand-new Fomoji identity + its first passkey in one ceremony.
    async createIdentity({ name, username, email }) {
      const { options, challengeId } = await postJSON('/api/webauthn/register/start', { name, username, email });
      let attResp;
      try {
        attResp = await SimpleWebAuthnBrowser.startRegistration({ optionsJSON: options });
      } catch (err) {
        throw new FomojiWebAuthnError(browserErrorMessage(err), 'browser_error');
      }
      return postJSON('/api/webauthn/register/finish', { ...attResp, challengeId });
    },

    // Add an additional passkey to the currently signed-in identity.
    async addPasskey() {
      const { options, challengeId } = await postJSON('/api/webauthn/register/start', null);
      let attResp;
      try {
        attResp = await SimpleWebAuthnBrowser.startRegistration({ optionsJSON: options });
      } catch (err) {
        throw new FomojiWebAuthnError(browserErrorMessage(err), 'browser_error');
      }
      return postJSON('/api/webauthn/register/finish', { ...attResp, challengeId });
    },

    // Usernameless sign-in — the browser's own passkey picker does the work.
    async login() {
      const { options, challengeId } = await postJSON('/api/webauthn/login/start', null);
      let asseResp;
      try {
        asseResp = await SimpleWebAuthnBrowser.startAuthentication({ optionsJSON: options });
      } catch (err) {
        throw new FomojiWebAuthnError(browserErrorMessage(err), 'browser_error');
      }
      return postJSON('/api/webauthn/login/finish', { ...asseResp, challengeId });
    },

    async session() {
      const res = await fetch('/api/session', { credentials: 'same-origin' });
      const data = await res.json();
      return data.user; // null if signed out
    },

    async logout() {
      await fetch('/api/logout', { method: 'POST', credentials: 'same-origin' });
    },

    async listCredentials() {
      const res = await fetch('/api/credentials', { credentials: 'same-origin' });
      if (!res.ok) throw new FomojiWebAuthnError('Could not load sign-in methods.', 'error');
      const data = await res.json();
      return data.credentials;
    },

    async renameCredential(id, nickname) {
      const res = await fetch(`/api/credentials/${encodeURIComponent(id)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ nickname }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new FomojiWebAuthnError(data.message || humanizeError(data.error), data.error);
      return data;
    },

    async removeCredential(id) {
      const res = await fetch(`/api/credentials/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        credentials: 'same-origin',
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new FomojiWebAuthnError(data.message || humanizeError(data.error), data.error);
      return data;
    },

    async activity() {
      const res = await fetch('/api/activity', { credentials: 'same-origin' });
      const data = await res.json();
      return data.events;
    },
  };

  function browserErrorMessage(err) {
    // Surfaced in full to the console (not the UI) so a report of "passkey
    // doesn't work" can include the actual DOMException name/message —
    // the friendly strings below collapse several distinct causes into one
    // line on purpose, which is exactly what makes them hard to debug blind.
    console.error('[fomoji:webauthn] browser threw during ceremony —', err && err.name, err && err.message, err);
    if (err && err.name === 'NotAllowedError') return 'Cancelled, or your device did not respond in time.';
    if (err && err.name === 'InvalidStateError') return 'This device already has a passkey for Fomoji.';
    if (err && err.name === 'SecurityError') return 'The page origin does not match what this passkey was registered for.';
    return (err && err.message) || 'Your browser could not complete that passkey request.';
  }
})();

class FomojiWebAuthnError extends Error {
  constructor(message, code) {
    super(message);
    this.name = 'FomojiWebAuthnError';
    this.code = code;
  }
}
