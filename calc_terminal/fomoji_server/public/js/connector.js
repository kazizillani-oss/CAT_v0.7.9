/* ==========================================================================
   FOMOJI CONNECTOR (browser)
   Client for the connector system's REST API. Talks to /api/connector/*
   over the same httpOnly session cookie every other page already uses —
   this file never invents a second auth mechanism, it only ever calls
   endpoints that themselves require an existing Fomoji session.
   ========================================================================== */

const FomojiConnector = (() => {
  function humanizeError(code) {
    switch (code) {
      case 'not_authenticated': return 'Sign in to manage connections.';
      case 'unknown_application': return "That application isn't registered with Fomoji.";
      case 'not_found': return "That code doesn't match a pending request.";
      case 'expired_or_resolved': return 'That code has expired or was already used.';
      case 'already_resolved': return 'That request was already approved or denied.';
      case 'expired': return 'That request expired before it was approved.';
      case 'not_connected': return 'Not connected.';
      default: return 'Something went wrong. Try again.';
    }
  }

  async function request(method, url, body) {
    const res = await fetch(url, {
      method,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      credentials: 'same-origin',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.message || humanizeError(data.error));
    return data;
  }

  return {
    // ---- registry ----
    async listApplications() {
      const data = await request('GET', '/api/connector/applications');
      return data.applications;
    },

    // ---- this identity's connections ----
    async listConnections() {
      const data = await request('GET', '/api/connector/connections');
      return data.connections;
    },
    async status(applicationId) {
      const data = await request('GET', `/api/connector/status?applicationId=${encodeURIComponent(applicationId)}`);
      return data.status; // 'connected' | 'not_connected' | 'expired'
    },

    // ---- direct connect (browser already has a session) ----
    async connect(applicationId, permissions = [], connectionType = 'standard') {
      const data = await request('POST', '/api/connector/connect', { applicationId, permissions, connectionType });
      return data.connection;
    },
    async disconnect(applicationId) {
      await request('POST', '/api/connector/disconnect', { applicationId });
      return true;
    },
    // Alias matching the spec's requested surface (FomojiConnector.requestPermission).
    async requestPermission(applicationId, permissions = []) {
      return this.connect(applicationId, permissions);
    },

    // ---- device-authorization approval (for CAT / connector.py clients
    // pairing from outside the browser — connector.html's "Enter a code"
    // flow calls these) ----
    async lookupDeviceCode(userCode) {
      const data = await request('GET', `/api/connector/device/lookup?userCode=${encodeURIComponent(userCode)}`);
      return data; // { application, requestedPermissions }
    },
    async approveDeviceCode(userCode, permissions) {
      const data = await request('POST', '/api/connector/device/approve', { userCode, permissions });
      return data;
    },
    async denyDeviceCode(userCode) {
      await request('POST', '/api/connector/device/deny', { userCode });
      return true;
    },
  };
})();
