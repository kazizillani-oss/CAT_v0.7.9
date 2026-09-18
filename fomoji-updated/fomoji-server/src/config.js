'use strict';
require('dotenv').config();

// WebAuthn ties every credential to an exact Relying Party ID + origin.
// "localhost" is a browser-recognized secure context on its own, so this
// runs with real passkeys with zero extra setup in dev. In production,
// RP_ID must be your real domain (e.g. "fomoji.app") and ORIGIN must be
// the exact https:// URL users load the site from — get either wrong and
// every ceremony will correctly fail (that's WebAuthn doing its job, not
// a bug).
const PORT = process.env.PORT || 3000;
const RP_ID = process.env.RP_ID || 'localhost';
const RP_NAME = process.env.RP_NAME || 'Fomoji';
const ORIGIN = process.env.ORIGIN || `http://localhost:${PORT}`;
const SESSION_SECRET = process.env.SESSION_SECRET || 'dev-only-secret-change-me';
// Signs Fomoji Authentication Cards (src/routes/authCard.js) so a card's
// data can be verified as genuinely issued by this server. Separate from
// SESSION_SECRET so rotating one doesn't silently invalidate the other,
// but falls back to it in dev so this doesn't need its own env var to
// just try the feature out.
const CARD_SECRET = process.env.CARD_SECRET || SESSION_SECRET;
// Gates POST /api/connector/applications/register — a server-to-server
// secret so only trusted deployers (never a browser, never connector.js)
// can register a new connector application. Unset by default: with no
// secret configured, registration is refused outright rather than
// silently open.
const CONNECTOR_REGISTRATION_SECRET = process.env.CONNECTOR_REGISTRATION_SECRET || '';

if (SESSION_SECRET === 'dev-only-secret-change-me' && process.env.NODE_ENV === 'production') {
  throw new Error('Set a real SESSION_SECRET env var before running in production.');
}

module.exports = { PORT, RP_ID, RP_NAME, ORIGIN, SESSION_SECRET, CARD_SECRET, CONNECTOR_REGISTRATION_SECRET };
