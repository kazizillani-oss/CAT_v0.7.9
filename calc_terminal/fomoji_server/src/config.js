'use strict';
require('dotenv').config();

// WebAuthn ties every credential to an exact Relying Party ID + origin.
// "localhost" is a browser-recognized secure context on its own, so this
// runs with real passkeys with zero extra setup in dev. In production,
// RP_ID must be your real domain (e.g. "fomoji.app") and ORIGIN must be
// the exact https:// URL users load the site from — get either wrong and
// every ceremony will correctly fail (that's WebAuthn doing its job, not
// a bug).
const crypto = require('crypto');

const IS_PRODUCTION = process.env.NODE_ENV === 'production';
const PORT = parseInt(process.env.PORT, 10) || 3000;
const RP_ID = process.env.RP_ID || (IS_PRODUCTION ? '' : 'localhost');
const RP_NAME = process.env.RP_NAME || 'Fomoji';
const ORIGIN = process.env.ORIGIN || (IS_PRODUCTION ? '' : `http://localhost:${PORT}`);

// Production validation: Refuse to start if critical environment variables are missing
if (IS_PRODUCTION) {
  const missingVars = [];
  if (!process.env.SESSION_SECRET || process.env.SESSION_SECRET.length < 32) {
    missingVars.push('SESSION_SECRET (must be >= 32 characters)');
  }
  if (!process.env.RP_ID || process.env.RP_ID === 'localhost') {
    missingVars.push('RP_ID (cannot be localhost in production; must be your domain e.g. fomoji.app)');
  }
  if (!process.env.ORIGIN || !process.env.ORIGIN.startsWith('https://') || process.env.ORIGIN.includes('localhost')) {
    missingVars.push('ORIGIN (must be a secure https:// URL e.g. https://fomoji.app)');
  }
  if (missingVars.length > 0) {
    console.error('FATAL: Missing or invalid critical production environment variables:');
    missingVars.forEach((v) => console.error(`  - ${v}`));
    throw new Error(`Production startup aborted: missing required configuration: ${missingVars.join(', ')}`);
  }
}

// In development, if unset, generate an ephemeral, cryptographically secure random key.
let sessionSecret = process.env.SESSION_SECRET;
if (!sessionSecret) {
  sessionSecret = crypto.randomBytes(32).toString('hex');
}
const SESSION_SECRET = sessionSecret;

// Signs Fomoji Authentication Cards (src/routes/authCard.js)
const CARD_SECRET = process.env.CARD_SECRET || SESSION_SECRET;

// Gates POST /api/connector/applications/register — a server-to-server secret
const CONNECTOR_REGISTRATION_SECRET = process.env.CONNECTOR_REGISTRATION_SECRET || '';

module.exports = {
  IS_PRODUCTION,
  PORT,
  RP_ID,
  RP_NAME,
  ORIGIN,
  SESSION_SECRET,
  CARD_SECRET,
  CONNECTOR_REGISTRATION_SECRET,
};

