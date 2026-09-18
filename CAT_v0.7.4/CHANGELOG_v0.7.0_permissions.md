# CCT v0.7.0 (partial) — Three-mode AI permissions (spec Section 2 only)

## Scope, stated plainly

The v0.7+ spec asked for a complete AI-powered Scientific IDE — a full
multi-language code editor with file explorer, project-wide indexing,
git integration, refactor/debug/optimize actions, and quantum-programming
assistance across Qiskit/QASM/CUDA/GLSL. That's a different scale of
software than a terminal app; building it isn't a matter of writing more
functions in `app.py`, it's a separate application. I didn't build it,
and didn't pretend to.

What IS in this codebase already and genuinely benefits from a real,
scoped feature: **Section 2, the three-mode AI permission system**
(Ask Every Time / Restricted / Full Access). `permissions.py` already
existed with a granular per-capability toggle system wired into one real
enforcement point (`execute_python`, gated in `ui/app.py`). This session
added the three-mode layer on top of it — reusing the existing toggles
and enforcement point rather than building parallel plumbing, per the
spec's own "avoid duplicate code" instruction.

## A real, live bug this fixed

`needs_prompt(key)` used to be `(not self.allowed(key))` — i.e. "prompt
only if the capability's toggle is OFF." But `execute_python` defaults to
**ON** in `PERMISSION_DEFS`. That means the app's one live permission
gate (in `ui/app.py`, guarding "simulate/run python/plot" requests) was
**never actually prompting**, by default, from day one — silently running
whatever the AI decided to execute. That's the opposite of "Ask Every
Time" being the default the spec (and this module's own docstring)
described. Caught by writing the test for the literal spec sentence
("Ask Every Time... whenever the AI wants to execute scripts... it must
display an approval dialog") and finding the old code failed it.

## What changed in `permissions.py`

- `PermissionManager.mode`: `"ask"` (default) | `"restricted"` | `"full"`.
- `MUTATING_KEYS = {"write_files", "execute_python", "shell_commands"}` —
  modes only change prompting behavior for these; read-only capabilities
  (`read_files`, `notebook`, `calculator`, `formula_library`) stay
  governed by their own toggle in every mode, since "ask before reading a
  file" isn't what the spec's examples ask for (they're all write/edit/
  execute/delete/install/commit).
- `needs_prompt(key)`: mode-aware now — `full` never prompts; `restricted`
  always requires review for mutating keys; `ask` always prompts for
  mutating keys unless that exact key was granted "Always Allow This
  Session" (this is the fix above).
- `restricted_review(key)`: flags when a prompt should use Restricted
  mode's Accept/Reject framing (spec Mode 2) instead of Allow-Once/
  Always-Allow/Deny (spec Mode 1). Not yet consumed by the actual
  `PermissionCard` widget's button labels — see Honest gaps below.
- `set_mode()` clears session-level "always allow" grants on switch, so
  going back to Ask mode doesn't silently inherit trust granted under a
  different mode.

## New: `/permissions` command (classic terminal)

`/permissions` shows the current mode and all three with descriptions;
`/permissions ask|restricted|full` switches, with the spec's required
visible warning shown when switching to Full Access.

## Honest gaps

- **`ui/app.py`'s `PermissionCard` widget still shows the same Allow-
  Once/Always-Allow/Deny buttons in every mode.** The `restricted_review()`
  flag exists and is correct, but nothing reads it yet to swap in
  Restricted mode's Accept/Reject wording. Because I can't run `textual`
  in this sandbox (same limitation as the earlier `_stream_worker` work),
  I didn't want to guess at widget-level changes I can't visually verify.
  The *behavioral* difference between modes is real and tested (Restricted
  always requires review, Full never does) — the *labeling* difference
  isn't wired yet.
- **No header-level mode selector control.** `BrandHeader`'s breadcrumb
  could show the current mode as a text field (it already accepts
  arbitrary fields), but I didn't wire that in this pass either, for the
  same reason — can't verify Textual rendering here.
- **Sections 1, 3-8 of the v0.7 spec (AI code editor, project indexing,
  code actions, quantum programming assistant, safe-execution previews)
  have no code from this session.** None of them have an existing
  foothold in the codebase the way permissions.py did.

## Verified

Direct unit tests against the spec's own wording for all three modes
(Ask/Restricted/Full), the Allow-Once vs Always-Allow-This-Session
distinction, Deny, the mode-switch trust-leak scenario, invalid mode
names, and `/permissions` end-to-end (view, switch, warning display, bad
input) — all pass. Full prior regression suite (39+ commands) re-run —
still passes.
