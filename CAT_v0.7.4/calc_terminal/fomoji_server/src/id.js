// Fomoji identity identifiers.
//
// FJ-XXXXXXXX is a PUBLIC identifier — safe to print on a passport PDF, put
// in a QR code, log in an activity feed, etc. It is not a secret and proves
// nothing on its own; it just names an account so the server knows whose
// credential to challenge next. All real proof-of-identity happens via
// WebAuthn signatures (see webauthn.js), never via this string.
'use strict';

const crypto = require('crypto');

// Uppercase alphanumeric, excluding visually-ambiguous characters
// (0/O, 1/I/L) so a printed passport is easy to type back in by hand.
const ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';

function randomFomojiId() {
  const bytes = crypto.randomBytes(8);
  let out = '';
  for (let i = 0; i < 8; i++) {
    out += ALPHABET[bytes[i] % ALPHABET.length];
  }
  return `FJ-${out}`;
}

// Internal, unguessable primary key for DB rows / session subjects.
// Separate from the Fomoji ID on purpose: the Fomoji ID is meant to be
// shown publicly, this one never is.
function randomInternalId() {
  return crypto.randomUUID();
}

module.exports = { randomFomojiId, randomInternalId };
