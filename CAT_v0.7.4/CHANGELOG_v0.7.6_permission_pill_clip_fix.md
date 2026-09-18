# v0.7.6 — Permission Pill Was Being Clipped by Its Own Header Row

## Root cause

Reported as "the permission dropdown still shows as buggy" with a
screenshot of a blank rounded outline where the pill's label should be.
That's not the popup from v0.7.5 (which wasn't even open in the
screenshot) — it's the *trigger button itself* never rendering its text.

`calc_terminal/ui/app.py`'s `_COMPONENT_CSS` had:

```
#cct-header-top { height: 1; overflow: hidden; }
```

`PermissionPill` has `border: round` — any bordered Static needs 3 rows
(top border / label / bottom border), it can't render in 1. With the
container capped to `height: 1; overflow: hidden`, only the pill's top
border row survived; the label row and bottom border were clipped away
entirely. That's exactly the empty outline in the screenshot.

Confirmed with a headless Textual render: `PermissionPill.region` came
back `height=3` (what it actually needs) while `#cct-header-top.region`
came back `height=1` (what its parent allowed) — and a rendered
screenshot of the header showed the label text simply wasn't there.
`BrandHeader`'s own docstring even says "height 3", which no longer
matched the CSS — this was a real regression, not a misunderstanding.

## Fix

`#cct-header-top { height: 1; ... }` → `height: 3; ...`, keeping
`overflow: hidden` as the defensive clip against anything that measures
taller than that (the original hover-bug guard this rule existed for).
MenuButton, Logo, and the workspace-path Static already use
`content-align: * middle`, so they stay correctly centered on the
row now that the container is 3 rows tall instead of 1.

## Verified
- Headless render before the fix: pill region height=3, container
  region height=1 (clipped).
- Headless render after the fix: container region height=3 (matches),
  and an exported screenshot shows the full rounded pill with its mode
  label rendered inside it.
- Re-ran the v0.7.5 popup-anchoring test against the corrected 3-row
  header: the dropdown still opens directly under the pill and clamps
  correctly on resize — the two fixes compose cleanly.

---

# v0.7.6 Patch 1 — UI Preservation Patch (7 fixes, pixel-identical UI)

Rule of this patch: fix the listed bugs, never redesign. No layout,
color, or spacing changes; every fix renders through the existing
chrome (screens, panels, chips, bubbles).

## Fix 1 — Recent Projects: delete & clear

`recent` rows in the sidebar could not be removed individually, and
removing the "Clear recent" button left no way to prune the list.

- `calc_terminal/projects.py`: added `remove_recent(path)` (removes
  from `recent[]`, preserves `pinned[]`).
- `calc_terminal/ui/sidebar.py`: `_ProjectRow` is now a `Horizontal`
  whose ✕ delete chip only mounts when `on_delete` is supplied — the
  legacy single-`Static` row form is preserved for callers that don't
  need deletion. Recent rows mount with the delete handler and
  `_delete_recent()` re-renders in place via the existing
  `_ClearRecentRow` pattern.
- `calc_terminal/ui/app.py`: `.cct-sidebar-project-row` /
  `.cct-sidebar-project-del` CSS (reuses existing `$surface`/`$error`
  variables — no new colors).

## Fix 2 — Folder menu item

Choosing "Open Folder" from the hamburger menu toggled the explorer
sidebar closed and the menu shut, so you never saw the folder picker.

- `CCTApp.on_nav_action("open_folder")` now always pushes
  `OpenWorkspaceScreen` (the same real folder picker the sidebar
  uses) and returns; the menu panel stays open behind it.

## Fix 3 — Header bugs

- Hamburger glyph `☰` (renders as tofu on some fonts) → `≡`
  (U+2261), via `_MENU_GLYPH`/`_CLOSE_GLYPH` class constants on
  `MenuButton`.
- The 1.6s placeholder/idle tick forced `refresh_right()` on the
  header even when the workspace path hadn't changed, repainting the
  breadcrumb and glitching the header. `refresh_right()` now
  short-circuits when the text is identical (tracks
  `self._workspace_path`).
- `#cct-brandheader` height pinned to `4` (3 content rows + 1px
  border in border-box) instead of `auto`, so the header row count
  can never drift with content.
- Duplicate logo: the dashboard hero no longer renders its ASCII
  `LOGO` block under the wordmark (only wordmark + version + GPU +
  model remain) — one `⬡ CCT` logo per screen.

## Fix 4 — Merged Settings window

Settings were a read-only snapshot panel, and this build's
`/settings` suspended to the print()-based CLI menu — inconsistent
with every other UI setting.

- `calc_terminal/ui/events.py`: new `SettingChanged(category, value)`
  message.
- `calc_terminal/ui/nav_screens.py`: `SettingsPanel` is now the real
  merged settings window in the standard centered rounded-box chrome:
  Permission Mode (Ask Every Time / Restricted / Full Access),
  Theme (Dark / Light), AI Mode (Notebook / Agent / Build / Plan),
  Model (→ provider setup screen), Workspace (→ folder picker),
  Preferences (auto-save, sound, animated responses, animation
  speed, decimal precision, clear history). Rows are choice /
  toggle / cycle / action shapes; the window never reads app state
  itself — CCTApp supplies a `get_values` callable and calls
  `refresh_rows()` after every change, so ✓ marks and readouts are
  always live. Section headers + a scrollable box keep all 22 rows
  from clipping on short terminals.
- `calc_terminal/ui/app.py`: `on_setting_changed` is the one place a
  change gets applied (theme switch, permission mode, AI mode, model
  picker, workspace picker, autosave, sound, animation, anim speed
  cycle, precision cycle, clear history), then the panel re-renders
  in place. NavPanel "Settings", the `/settings` command, and the
  dashboard Settings quick-action all open the same window.

## Fix 5 — Attachments: browse / drag & drop / paste

- Browse already existed (`📎` → `_AttachPrompt`); its hint line now
  points at the other two paths.
- Textual 8.2.8 has no OS file-drop event (verified against the
  installed site-packages), but dragging a file into a Windows
  terminal inserts its path into the input buffer as a paste — so
  drag & drop is realized as path-paste detection. `paths_from_paste`
  (`ui/attachments.py`) recognizes single paths, quoted paths, and
  Explorer's NUL-separated multi-file lists (real existence check on
  every segment; prose that merely mentions a path is never
  hijacked) and turns them into attachment chips instead of editor
  text.

## Fix 6 — Attachment cards in chat bubbles

- `ui/conversation.py`: bubbles now render one small rounded card
  per attachment (icon by file type + filename + real size), inside
  the bubble, above the timestamp — via Rich, no new widget chrome.
  Follows edits: `set_text(..., attachments=...)` repaints the
  cards.

## Fix 7 — AI file analysis for attachments

- `calc_terminal/aicore.py`: new `attachment_context_for(path)` —
  one honest, real context block per file type, fed into the prompt
  and the agent's `read_attachment` tool:
  - text / code / markdown / config: actual content (existing
    reader, truncated at 20k chars);
  - CSV: real header + row count (capped at 5000) + first rows;
  - zip / tar: real listings, counts, uncompressed size (stdlib);
  - PDF: page count + Info metadata + best-effort text-layer
    extraction (stdlib zlib; no pypdf in this environment) — never
    fabricated, honest when there's no text layer;
  - audio / video: size + ext, and a clear note that tag/duration
    parsing needs `mutagen` (not installed);
  - binary / rar / 7z / missing files: honest notes.
  - images keep the existing vision path
    (`query_ai_with_image`), now also reporting real dimensions via
    Pillow.
- Also fixes a pre-existing bug found while wiring this: the old
  `_augment_prompt` concatenated `read_text_file_for_context`'s
  `(content, truncated)` tuple into a string → TypeError → every
  non-image attachment failed with "[Could not read attachment]".
  Non-image attachments now actually reach the AI.

## Verified

All four headless probes pass (`probe_header.py`, `probe_settings.py`,
`probe_attach.py`, `probe_cards.py`, `probe_fix7.py`): header geometry
and glyph morph, the 19 settings-window checks, 15 path-paste/chip
checks, 24 bubble-card checks, and 29 attachment-context checks, plus
full-module import of `calc_terminal.ui.app` / `aicore` / `agent`.

## Patch 1 follow-up — popup click crash (`ScreenStackError`)

User-reported runtime crash on the pill/NavPanel popups (Python 3.14.5,
Textual 8.2.8): clicking the permission pill (or double-clicking it)
raised `ScreenStackError: Can't pop screen` from
`PermissionModeMenu.on_click` → "CCTApp.run() returned normally".

Root cause: a mouse click is delivered twice to a popup screen — once
when it's still the active screen (dismiss #1 pops it), and again after
it has already been popped (dismiss #2 pops the default screen → empty
stack → `ScreenStackError`). This is a delivery quirk of the real
terminal driver (the opening click can be re-delivered to the freshly
pushed screen's backdrop, and chained/double clicks deliver a second
`Click` to the popped screen); it never reproduced headlessly.

Fix, in `calc_terminal/ui/header.py`:
- `PermissionPill.on_click` / `MenuButton.on_click`: `event.stop()`
  before opening/closing, so the opening click never bubbles back to
  the new screen's backdrop and instantly closes it;
- `PermissionModeMenu.on_click` / `NavPanel.on_click` /
  `_PermMenuRow.on_click` / `_NavRow.on_click`: dismiss (and row
  actions) now require `self.app.screen is self` — a click delivered
  to an already-popped screen is a no-op instead of a second pop.

Verified headless by `probe_doubledismiss.py` (14/14): open-close cycle
for both popups, raw-driver-style backdrop clicks, re-delivered clicks
(including `chain=2`) against already-popped screens are no-ops, row
click closes NavPanel, default screen restored, zero exceptions.
