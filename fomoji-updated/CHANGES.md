# Changes — Group/Student identity + 3D layer

This session built on an already-substantial existing implementation
(connector.py/js/html, device-authorization flow, permission scoping —
sections 1-6 of the spec were already done and untouched here).

## Backend

- **`src/db.js`** — new `group_members` table (role: owner/admin/member/
  guest); new columns on `users`: `institution`, `avatar`, `description`,
  `card_style`. (Fixed a stray backtick inside a template literal that
  would have crashed the server on boot — verified with a standalone
  script against `node:sqlite`.)
- **`src/routes/groups.js`** (new) — group CRUD, membership + roles,
  "continue as group," self-service student enrollment/leave. Mounted at
  `/api/groups` in `src/server.js`.
- **`src/routes/auth.js`** — `POST /api/temporary/create` and
  `/api/temporary/upgrade` (real, expiring, upgradeable identities,
  separate from the existing local-only guest mode). `requireAuth` and
  `GET /session` now also expire TEMPORARY identities server-side.

## Frontend

- **`public/identities.html`** (new) — Group Authentication Card (create,
  list, member management, role changes, surface picker, "continue as
  group"), Student Authentication Card (enroll/leave, optional
  institution), Temporary Account card (expiry countdown, upgrade flow).
  Linked from `settings.html` and the tab bar on `connector.html`.
- **`public/js/fomoji-groups.js`** (new) — client wrapper for
  `/api/groups/*`.
- **`public/js/fomoji-auth.js`** — added `createTemporary` /
  `upgradeTemporary` to `FomojiAPI`.
- **`public/welcome.html`** — added "Continue with temporary account" next
  to the existing (unrelated, local-only) guest option.
- **`public/css/fomoji-3d.css`** + **`public/js/fomoji-3d.js`** (new) —
  genuine perspective/tilt/elevation system (not just the existing 2D
  glass/liquid textures), LOW/MEDIUM/HIGH/OFF via `data-depth3d` on
  `<html>` (settings.html control added), all 13 spec-named surface
  textures via `data-surface`, pointer-tilt for opted-in cards,
  IntersectionObserver-based pausing, full `prefers-reduced-motion` /
  `.reduce-motion` respect.
- **`public/connector.html`** — panels retrofitted with `.card-3d` +
  `data-surface` to demonstrate the 3D layer on existing UI.

## Verified this session

- `node --check` on every new/edited `.js` file and every inline
  `<script>` block extracted from the touched `.html` files.
- `src/db.js` actually run standalone (against Node's built-in
  `node:sqlite`, no npm install needed) — table creation, group
  creation, and a join query all executed successfully. This is what
  caught the backtick bug above.

## Not done / known gaps

- No `npm install` / full server boot in this sandbox (no network
  access) — route-level (Express) behavior is reviewed but not
  execution-tested.
- `group_members`/student/temporary flows have no automated tests.
- The rest of the app's tab bars (home.html, security.html, etc.) were
  not all updated to link to `identities.html` — only `settings.html`
  and `connector.html` were, to keep the diff focused. Worth doing a
  pass if you want it reachable from everywhere.
- 3D "art"/illustration elements (floating decorative shapes beyond
  `.fx-float-el`) weren't added to any specific page — the CSS/JS
  primitives are there, but no page was redesigned around them.
