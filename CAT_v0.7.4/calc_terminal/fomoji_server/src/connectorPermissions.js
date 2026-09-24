'use strict';
// Canonical connector permission scopes + identity types, shared by
// routes/connector.js (and connector.py/connector.js on the client side
// mirror these same string values) so nothing silently invents a new
// scope string that the server doesn't recognize.

const PERMISSIONS = [
  'IDENTITY',
  'PROFILE',
  'GROUP',
  'PROJECT',
  'FILES',
  'CAT_ACCESS',
  'AI_PROVIDER',
  'WORKSPACE',
];

const IDENTITY_TYPES = ['PERSON', 'GROUP', 'STUDENT', 'GUEST', 'TEMPORARY'];

// GUEST and TEMPORARY identities can never be granted more than this
// floor, no matter what an application requests — enforced here, once,
// server-side, so a careless or compromised client can't just ask for
// more (spec: "never give temporary identities unrestricted access").
const RESTRICTED_IDENTITY_TYPES = new Set(['GUEST', 'TEMPORARY']);
const RESTRICTED_PERMISSION_CEILING = new Set(['IDENTITY', 'PROFILE', 'PROJECT']);

// Narrows `requested` down to (a) permissions that actually exist, and
// (b) permissions the requesting application is even allowed to ask for
// (its own `permissions_available`), and (c) the identity-type ceiling
// above. The result is always a subset — this function only ever removes.
function sanitizePermissions(requested, { identityType, appAvailable } = {}) {
  const list = Array.isArray(requested) ? requested : [];
  let valid = [...new Set(list)].filter((p) => PERMISSIONS.includes(p));
  if (Array.isArray(appAvailable)) {
    valid = valid.filter((p) => appAvailable.includes(p));
  }
  if (identityType && RESTRICTED_IDENTITY_TYPES.has(identityType)) {
    valid = valid.filter((p) => RESTRICTED_PERMISSION_CEILING.has(p));
  }
  return valid;
}

module.exports = {
  PERMISSIONS,
  IDENTITY_TYPES,
  RESTRICTED_IDENTITY_TYPES,
  RESTRICTED_PERMISSION_CEILING,
  sanitizePermissions,
};
