# v0.7.5 — Permission Popup Anchoring & Syntax Highlighting Root Cause

Both issues in the "marsEdition" spec were investigated against the real
codebase before writing any code, per that spec's own "Root Cause
Analysis" section. Neither turned out to need the rewrite the spec
assumed — both had a specific, narrow bug once traced.

## Problem 2 (syntax highlighting) — root cause: a missing optional dependency, not a code bug

`calc_terminal/ui/editor.py` already builds every open file with Textual's
real `TextArea.code_editor()` (tree-sitter-backed highlighting, native
line numbers, native current-line highlight, native bracket matching,
native undo/redo) under a full Tokyo Night theme with an explicit
capture-name → color mapping for keywords/functions/classes/strings/
numbers/comments/etc. That part of the spec's own "IMPORTANT" section —
"do NOT use simple regex-only coloring if a parser-based approach
already exists" — was already true going in.

The actual bug: `requirements.txt` pinned plain `textual>=0.60`, not the
`textual[syntax]` extra. Textual's own `_tree_sitter.get_language()`
returns `None` with **no exception and no log line** when the
`tree_sitter` package (and the per-language `tree_sitter_<lang>`
grammar packages) aren't installed — so the app still starts fine, the
editor still shows line numbers/gutter/cursor/tabs/find-replace, and it
just silently renders every token in the same plain foreground color.
That's what "looks like Notepad" / "white text everywhere" actually was.

Confirmed with a headless Textual test opening a real `.py` file:
- **Before** (`textual` only): `TextArea._highlights` — 0 highlighted
  spans on any line.
- **After** (`textual[syntax]` installed): 7 lines of real captures —
  `keyword.function`, `variable`, `function`, `comment`, `keyword.return`,
  `operator`, `number`, `keyword`, `type`, `type.class`, etc.

### Fix
- `requirements.txt`: `textual>=0.60` → `textual[syntax]>=0.60`, with an
  inline comment explaining why this extra is required, not optional.
- `calc_terminal/ui/editor.py`: added an explicit `HIGHLIGHTING_AVAILABLE`
  check (real `import tree_sitter`, not a private Textual internal) and a
  one-time, dismissible in-editor banner — *"Syntax highlighting isn't
  installed — run: pip install "textual[syntax]""* — so if this ever
  regresses in some environment (e.g. a build without a C compiler for
  the grammar wheels), the user sees an honest message instead of a
  silently plain editor. This does not touch the highlighting/theme code
  itself, which was already correct.

## Problem 1 (permission popup) — root cause: fixed centered position, no real anchoring

`calc_terminal/ui/header.py`'s `PermissionModeMenu` was a Textual `Screen`
with `align: center top` and a fixed `margin-top: 3` — it never read the
Permission pill's actual on-screen position, so it always rendered
centered under the header rather than anchored to the button, with no
edge-collision handling and no resize awareness.

### Fix
- `PermissionModeMenu` now takes the triggering `PermissionPill` widget as
  an `anchor` and, on mount **and again on every terminal resize while
  open** (`on_resize`), reads that widget's live `region` (screen-absolute
  coordinates) to place the popup directly under it via `styles.offset`.
- Edge collision: horizontally clamped to the terminal width; vertically,
  flips to open *above* the pill when there isn't room below, then clamps
  to the terminal height either way — verified with a headless test that
  shrinks the terminal to 20×6 mid-open and asserts the popup's offset
  stays within `(0,0)`–`(width,height)`.
- ESC-to-close, click-outside-to-close, arrow-key navigation, Enter to
  select, mouse selection, and the open/close opacity transition were
  already implemented and are unchanged.
- `PermissionPill.on_click` now passes `anchor=self` when pushing the menu.

### Verified
Headless Textual `run_test()`:
1. Normal case — popup offset lands directly under the pill's region,
   fully inside the terminal bounds.
2. Resize-while-open case — popup re-clamps into a 20×6 terminal with no
   out-of-bounds offset.
3. Editor — before/after tree-sitter token counts on a real `.py` file.

### Left alone
The Tokyo Night editor theme (not the VS Code Dark+ palette hex values
from the spec) and the inline `PermissionCard`/`PermissionsSettingsPanel`
conversation-stream permission UI — both already match this project's
established design direction and weren't part of either root cause, so
they weren't touched.
