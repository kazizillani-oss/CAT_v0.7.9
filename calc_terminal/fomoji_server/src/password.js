// Password + recovery-code hashing, spec section 1 ("Email/password where
// supported"). Uses Node's own crypto.scrypt — a standard, audited KDF
// built into the runtime, not a hand-rolled algorithm — plus a
// constant-time comparison so verification isn't timing-attackable.
'use strict';

const crypto = require('crypto');

const KEYLEN = 64;

function hashSecret(secret) {
  const salt = crypto.randomBytes(16).toString('hex');
  const hash = crypto.scryptSync(secret, salt, KEYLEN).toString('hex');
  return `scrypt:${salt}:${hash}`;
}

function verifySecret(secret, stored) {
  if (!stored) return false;
  const parts = stored.split(':');
  if (parts.length !== 3 || parts[0] !== 'scrypt') return false;
  const [, salt, hashHex] = parts;
  const hashBuf = Buffer.from(hashHex, 'hex');
  const testBuf = crypto.scryptSync(secret, salt, KEYLEN);
  if (hashBuf.length !== testBuf.length) return false;
  return crypto.timingSafeEqual(hashBuf, testBuf);
}

// SHA-256 is fine here (unlike passwords, a recovery code is already a
// high-entropy random secret, not something to defend against brute force
// over a small guess-space).
function sha256Hex(text) {
  return crypto.createHash('sha256').update(text).digest('hex');
}

// Human-typeable one-time recovery code: 4 groups of 4, drawn from an
// unambiguous alphabet (no 0/O/1/I) so it can be read off a printout and
// typed back in without confusion.
function randomRecoveryCode() {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  const groups = [];
  for (let g = 0; g < 4; g++) {
    let group = '';
    const bytes = crypto.randomBytes(4);
    for (let i = 0; i < 4; i++) group += alphabet[bytes[i] % alphabet.length];
    groups.push(group);
  }
  return groups.join('-');
}

module.exports = { hashSecret, verifySecret, sha256Hex, randomRecoveryCode };
