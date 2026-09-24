'use strict';
// Fomoji Group + Student identity endpoints (spec sections 7-13).
//
// A GROUP is just another row in `users` (identity_type='GROUP') — it has
// its own fomoji_id, name, avatar, description and card_style, exactly
// like a PERSON identity, so every existing "identity" concept (connector
// connections, auth cards) already works on it for free. `group_members`
// is the only truly group-specific table: who belongs, and with what role
// (owner | admin | member | guest). A group never signs itself in; a real
// person authenticates as themselves via the normal Fomoji session and
// then "continues as" a group they belong to — the group does not replace
// their personal identity (spec section 7).
//
// STUDENT is even simpler: it's a flag + optional institution on a
// person's own identity, set by that person, self-service, no
// institutional email required (spec section 9) unless a future
// institution-verification flow explicitly turns that on for itself.
const express = require('express');
const db = require('../db');
const { randomFomojiId, randomInternalId } = require('../id');
const { requireAuth } = require('./auth');
const { IDENTITY_TYPES } = require('../connectorPermissions');

const router = express.Router();

const ROLES = ['owner', 'admin', 'member', 'guest'];
const ROLE_RANK = { owner: 3, admin: 2, member: 1, guest: 0 };

function getUserById(id) {
  return db.prepare(`SELECT * FROM users WHERE id = ?`).get(id);
}

function getGroup(id) {
  const row = getUserById(id);
  return row && row.identity_type === 'GROUP' ? row : null;
}

function myRole(groupId, userId) {
  const row = db.prepare(`SELECT role FROM group_members WHERE group_id = ? AND member_id = ?`).get(groupId, userId);
  return row ? row.role : null;
}

function parseCardStyle(row) {
  try {
    return JSON.parse(row.card_style || '{}');
  } catch (e) {
    return {};
  }
}

function publicIdentity(row) {
  return {
    fomojiId: row.fomoji_id,
    name: row.name,
    identityType: row.identity_type,
    avatar: row.avatar || null,
    description: row.description || null,
    institution: row.institution || null,
    cardStyle: parseCardStyle(row),
  };
}

function publicGroup(row, viewerId) {
  const memberCount = db.prepare(`SELECT COUNT(*) AS c FROM group_members WHERE group_id = ?`).get(row.id).c;
  const role = viewerId ? myRole(row.id, viewerId) : null;
  return {
    ...publicIdentity(row),
    id: row.id,
    memberCount,
    myRole: role,
  };
}

function publicMember(memberRow, roleRow) {
  return {
    fomojiId: memberRow.fomoji_id,
    name: memberRow.name,
    identityType: memberRow.identity_type,
    avatar: memberRow.avatar || null,
    role: roleRow.role,
    joinedAt: roleRow.joined_at,
  };
}

// A group card can only ever show applications that identity has actually
// connected (same `connections` table every PERSON identity uses) — never
// invented data.
function groupConnections(groupId) {
  const rows = db
    .prepare(
      `SELECT c.*, a.name AS app_name, a.icon AS app_icon
       FROM connections c JOIN applications a ON a.application_id = c.application_id
       WHERE c.user_id = ? AND c.status = 'connected' ORDER BY c.created_at DESC`
    )
    .all(groupId);
  return rows.map((r) => ({ applicationId: r.application_id, name: r.app_name, icon: r.app_icon }));
}

function requireMember(req, res, next) {
  const group = getGroup(req.params.id);
  if (!group) return res.status(404).json({ error: 'group_not_found' });
  const role = myRole(group.id, req.session.userId);
  if (!role) return res.status(403).json({ error: 'not_a_member' });
  req.group = group;
  req.myGroupRole = role;
  next();
}

function requireAdmin(req, res, next) {
  if (ROLE_RANK[req.myGroupRole] < ROLE_RANK.admin) {
    return res.status(403).json({ error: 'admin_required' });
  }
  next();
}

// ---------------------------------------------------------------------
// POST /api/groups — create a group. Creator becomes owner. The group's
// permissions/connections start empty; it's a distinct identity that
// connects to applications on its own, same flow as a person.
// ---------------------------------------------------------------------
router.post('/', requireAuth, (req, res) => {
  const { name, avatar, description } = req.body || {};
  if (!name || typeof name !== 'string' || !name.trim()) {
    return res.status(400).json({ error: 'name_required' });
  }
  const id = randomInternalId();
  const fomojiId = randomFomojiId();
  db.prepare(
    `INSERT INTO users (id, fomoji_id, name, identity_type, avatar, description) VALUES (?, ?, ?, 'GROUP', ?, ?)`
  ).run(id, fomojiId, name.trim(), avatar || null, description || null);
  db.prepare(`INSERT INTO group_members (group_id, member_id, role) VALUES (?, ?, 'owner')`).run(id, req.session.userId);
  res.status(201).json({ group: publicGroup(getGroup(id), req.session.userId) });
});

// ---------------------------------------------------------------------
// GET /api/groups — groups I belong to, with my role in each.
// ---------------------------------------------------------------------
router.get('/', requireAuth, (req, res) => {
  const rows = db
    .prepare(
      `SELECT u.* FROM users u JOIN group_members gm ON gm.group_id = u.id
       WHERE gm.member_id = ? AND u.identity_type = 'GROUP' ORDER BY u.created_at DESC`
    )
    .all(req.session.userId);
  res.json({ groups: rows.map((r) => publicGroup(r, req.session.userId)) });
});

// ---------------------------------------------------------------------
// GET /api/groups/:id — full group card: identity, members, connections.
// Members-only, same principle as any other private profile data.
// ---------------------------------------------------------------------
router.get('/:id', requireAuth, requireMember, (req, res) => {
  const members = db
    .prepare(`SELECT gm.*, u.* FROM group_members gm JOIN users u ON u.id = gm.member_id WHERE gm.group_id = ? ORDER BY gm.joined_at ASC`)
    .all(req.group.id);
  res.json({
    group: publicGroup(req.group, req.session.userId),
    members: members.map((m) => publicMember(m, m)),
    connections: groupConnections(req.group.id),
  });
});

// ---------------------------------------------------------------------
// PATCH /api/groups/:id — update group profile / card customization.
// Owner/admin only.
// ---------------------------------------------------------------------
router.patch('/:id', requireAuth, requireMember, requireAdmin, (req, res) => {
  const { name, avatar, description, cardStyle } = req.body || {};
  const current = req.group;
  const nextName = typeof name === 'string' && name.trim() ? name.trim() : current.name;
  const nextAvatar = avatar !== undefined ? avatar : current.avatar;
  const nextDescription = description !== undefined ? description : current.description;
  let nextCardStyle = current.card_style;
  if (cardStyle && typeof cardStyle === 'object') {
    const merged = { ...parseCardStyle(current), ...cardStyle };
    nextCardStyle = JSON.stringify(merged);
  }
  db.prepare(`UPDATE users SET name = ?, avatar = ?, description = ?, card_style = ? WHERE id = ?`).run(
    nextName,
    nextAvatar,
    nextDescription,
    nextCardStyle,
    current.id
  );
  res.json({ group: publicGroup(getGroup(current.id), req.session.userId) });
});

// ---------------------------------------------------------------------
// POST /api/groups/:id/members — add an existing Fomoji identity by its
// public fomoji_id. Owner/admin only. Never creates an account on
// someone else's behalf — the person must already exist.
// ---------------------------------------------------------------------
router.post('/:id/members', requireAuth, requireMember, requireAdmin, (req, res) => {
  const { fomojiId, role } = req.body || {};
  if (!fomojiId) return res.status(400).json({ error: 'fomoji_id_required' });
  const person = db.prepare(`SELECT * FROM users WHERE fomoji_id = ?`).get(String(fomojiId).trim());
  if (!person || person.identity_type === 'GROUP') return res.status(404).json({ error: 'identity_not_found' });
  const wantRole = ROLES.includes(role) ? role : 'member';
  // Only an owner can hand out the owner role.
  const grantRole = wantRole === 'owner' && req.myGroupRole !== 'owner' ? 'admin' : wantRole;
  db.prepare(
    `INSERT INTO group_members (group_id, member_id, role) VALUES (?, ?, ?)
     ON CONFLICT(group_id, member_id) DO UPDATE SET role = excluded.role`
  ).run(req.group.id, person.id, grantRole);
  res.status(201).json({ member: publicMember(person, { role: grantRole, joined_at: new Date().toISOString() }) });
});

// ---------------------------------------------------------------------
// PATCH /api/groups/:id/members/:memberId — change a member's role.
// Owner/admin only; only an owner can promote/demote another owner.
// ---------------------------------------------------------------------
router.patch('/:id/members/:memberId', requireAuth, requireMember, requireAdmin, (req, res) => {
  const { role } = req.body || {};
  if (!ROLES.includes(role)) return res.status(400).json({ error: 'invalid_role' });
  const targetRow = db.prepare(`SELECT * FROM group_members WHERE group_id = ? AND member_id = ?`).get(req.group.id, req.params.memberId);
  if (!targetRow) return res.status(404).json({ error: 'not_a_member' });
  if ((targetRow.role === 'owner' || role === 'owner') && req.myGroupRole !== 'owner') {
    return res.status(403).json({ error: 'owner_required' });
  }
  db.prepare(`UPDATE group_members SET role = ? WHERE group_id = ? AND member_id = ?`).run(role, req.group.id, req.params.memberId);
  res.json({ ok: true });
});

// ---------------------------------------------------------------------
// DELETE /api/groups/:id/members/:memberId — remove a member, or leave
// (a member removing themselves). The last owner can never be removed —
// a group must always keep at least one owner.
// ---------------------------------------------------------------------
router.delete('/:id/members/:memberId', requireAuth, requireMember, (req, res) => {
  const isSelf = req.params.memberId === req.session.userId;
  if (!isSelf && ROLE_RANK[req.myGroupRole] < ROLE_RANK.admin) {
    return res.status(403).json({ error: 'admin_required' });
  }
  const targetRow = db.prepare(`SELECT * FROM group_members WHERE group_id = ? AND member_id = ?`).get(req.group.id, req.params.memberId);
  if (!targetRow) return res.status(404).json({ error: 'not_a_member' });
  if (targetRow.role === 'owner') {
    const ownerCount = db.prepare(`SELECT COUNT(*) AS c FROM group_members WHERE group_id = ? AND role = 'owner'`).get(req.group.id).c;
    if (ownerCount <= 1) return res.status(400).json({ error: 'last_owner' });
  }
  db.prepare(`DELETE FROM group_members WHERE group_id = ? AND member_id = ?`).run(req.group.id, req.params.memberId);
  res.json({ ok: true });
});

// ---------------------------------------------------------------------
// POST /api/groups/:id/continue — "Continue as Group" (spec section 8).
// Purely a UI-scoping convenience: stores which group card the person is
// currently viewing/acting through in their own session. It never
// replaces req.session.userId — every write anywhere still runs as the
// real, individually-authenticated person; group-owned data (like
// connections) just gets filtered/created against req.group.id instead
// of req.session.userId within group.* routes.
// ---------------------------------------------------------------------
router.post('/:id/continue', requireAuth, requireMember, (req, res) => {
  req.session.activeGroupId = req.group.id;
  res.json({ ok: true, group: publicGroup(req.group, req.session.userId) });
});

router.post('/exit', requireAuth, (req, res) => {
  delete req.session.activeGroupId;
  res.json({ ok: true });
});

// ---------------------------------------------------------------------
// Student identity (spec section 9) — self-service, on the caller's own
// account only. institution is always optional; nothing here ever
// requires or verifies an institutional email.
// ---------------------------------------------------------------------
router.post('/student/enroll', requireAuth, (req, res) => {
  const { institution } = req.body || {};
  db.prepare(`UPDATE users SET identity_type = 'STUDENT', institution = ? WHERE id = ?`).run(
    institution ? String(institution).trim() : null,
    req.session.userId
  );
  res.json({ user: publicIdentity(getUserById(req.session.userId)) });
});

router.post('/student/leave', requireAuth, (req, res) => {
  const current = getUserById(req.session.userId);
  if (current.identity_type === 'STUDENT') {
    db.prepare(`UPDATE users SET identity_type = 'PERSON', institution = NULL WHERE id = ?`).run(req.session.userId);
  }
  res.json({ user: publicIdentity(getUserById(req.session.userId)) });
});

module.exports = { router, IDENTITY_TYPES };
