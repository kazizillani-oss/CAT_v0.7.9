# CCT v0.6.11 — AI Modes (Spec Section 3, plus the tied-in half of Section 1)

Implements `3. AI Modes` from the "v0.6.2 Quantum Edition" spec against
the primary chat UI: four themed personas — Notebook (blue), Agent
(purple), Build (yellow, new), Plan (green, new) — replacing the old
two-stop NOTEBOOK/AGENT footer toggle. Also closes the actual bug
behind Section 1's "remove /agent and /ai" instruction.

## What was already there before this pass

An audit against the full spec doc turned up more already-shipped than
the doc assumed — v0.6.10 already has: inline permission cards (Allow
Once / Always Allow / Deny — Section 4, partial), the full response
animation system (Section 25/prior pass), and quantum/chemistry
specialization threaded through most modules (Section 12, largely
satisfied already). What did NOT exist: any notion of Build or Plan
mode, mode-driven theming, or mode-driven system prompts — the footer
badge just flipped a label between "Notebook" and "Agent" with no
behavioral or visual difference behind either one.

## New — `calc_terminal/ai_modes.py`

Single source of truth for the four modes: `MODE_META` (label, icon,
accent RGB, one-line purpose per the spec), `current_mode()` /
`set_mode()` / `next_mode()` for state, and `system_prompt_for(mode)`
routing Build/Plan to their own new system prompts (software
development; project planning/roadmaps) and Notebook to the existing
`aicore.DEFAULT_SYSTEM_PROMPT` unchanged. Agent mode does NOT go
through this — see below.

## Changed — `calc_terminal/ui/theme_css.py`

`css_variables()` now overrides `accent` / `accent-highlight` /
`border-active` with `ai_modes.accent_hex()` on top of the existing
dark/light base palette from `theme.py`. This is the actual mechanism
behind "changes logo color / header / borders / accent color / status
indicators" — one repaint hook, reused by every widget that already
reads those three CSS variables (BrandHeader's mark, focused-panel
borders, footer badges), not a second hand-maintained palette.

## Changed — `calc_terminal/ui/footer.py`

`ComposerFooter.notebook_mode` (reactive, name kept for event
compatibility) now holds an `ai_modes` key and cycles all 4 stops
instead of 2; the badge renders itself in its own mode's accent color
via `_mode_badge_markup()`.

## Changed — `calc_terminal/ui/composer.py`

New `StickyComposer.set_ai_mode(mode_key)` syncs the footer badge after
a typed `/mode`-family command, so the clickable badge and the typed
command can't drift out of sync.

## Changed — `calc_terminal/ui/app.py`

- `_current_notebook_mode` (a display string) replaced with
  `_current_ai_mode` (an `ai_modes` key). New `_set_ai_mode()` is the
  one place that updates state, the breadcrumb, and triggers a CSS
  repaint (`refresh_css`) — same pattern `/theme` already uses.
- New native commands: `/mode` (bare = cycle, `/mode <name>` = jump),
  `/notebook`, `/build`, `/plan`.
- `/agent` and `/ai` now call the same mode-switch path instead of
  falling through to `_run_in_suspended_terminal` — **this is the real
  fix for Section 1's removal note.** The spec's stated reason for
  removing them was "both modes are now directly accessible from Chat
  UI"; the actual bug was that typing `/agent` or `/ai` suspended to
  the old print()/input() terminal, which is explicitly one of the
  removal criteria ("open the old UI"). Repurposing them into aliases
  for the new mode switch fixes that bug and keeps the muscle-memory
  command working, rather than deleting it outright — a deliberate
  interpretation, flagged here rather than silently substituted.
  `/ai` maps to Notebook (its original quick-chat persona); `/agent`
  maps to Agent.
- `_stream_worker` now branches on the active mode: Notebook/Build/Plan
  still call `aicore.stream_ai(prompt, system_prompt=..., history=...)`
  exactly as before, just with the mode's system prompt. **Agent mode
  now calls `agent.run_agent(prompt, mode="agent")`** — CCT's real
  tool-executing loop (solve/plot/simulate for real) — which the
  primary chat UI never invoked before this pass; only the classic
  fallback terminal did. Honest limitation: `run_agent()` is a
  blocking call that returns one finished answer, not a token
  generator, so Agent mode delivers its reply as a single chunk
  instead of faking a per-character typing effect over text that's
  already fully computed. Documented in-line, not hidden.
- `_begin_assistant_turn` now checks `aicore.load_config().get("provider")`
  before starting a turn. Needed because `aicore`'s own "AI not
  configured" messages say "Run /ai or /agent to configure your
  provider" — true in the classic terminal, no longer true here now
  that both are mode switches. Caught before it could reach the
  conversation; the real path (`/model`, bare, still suspends to the
  actual setup wizard) is what the new message points to.
- Welcome-banner hint text updated from "/agent for full notebooks" to
  mention `/mode`.

## Changed — `calc_terminal/commands_data.py` / `calc_terminal/registry.py`

`/agent` and `/ai`'s descriptions updated to describe the new
mode-switch behavior instead of the old "[BETA] ... opens old UI"
text; added `/mode`, `/notebook`, `/build`, `/plan` to `COMMANDS` and
`NATIVE_UI_COMMANDS` (so they never suspend), and gave all six
mode-related commands real `RICH_METADATA` (icon, examples,
autocomplete keywords) per Section 2's "every command should include
description/category/icon/examples" ask — for these six only, not a
full pass over the other ~35 commands (see Still Open).

## Verified

Headless, via `App.run_test()`:
- `/build`, `/mode` (bare cycle), `/agent`, `/ai`, and `/mode bogus`
  (rejected, mode unchanged) all produce the expected
  `_current_ai_mode` transitions and the expected `accent` CSS
  variable change.
- Sending a message in each of the 4 modes with no AI provider
  configured produces the corrected, accurate guidance message (not
  the stale "run /ai or /agent" text) and does not crash the worker
  thread or leave `_is_streaming` stuck `True`.

## Still open from the v0.6.2 spec

Not touched this pass — tracked, not hidden:
- **Section 1** — no full command-by-command audit of the other ~35
  commands for broken/duplicate/placeholder status; only `/agent`/`/ai`
  (explicitly named) were addressed.
- **Section 2** — rich command metadata (icon/shortcut/examples/etc.)
  only added for the 6 mode-related commands above, on top of the 6
  the previous pass (`registry.py`) already had; most commands still
  only have name + one-line description.
- **Section 4** — permission cards still only offer Allow Once / Always
  Allow / Deny; Preview Changes / View Diff / Cancel aren't there yet.
- **Section 5** — no interactive reply action buttons (`[Explain More]`,
  `[Continue]`, etc.) on AI responses yet.
- **Section 6** — only `/` is a live command prefix; `@ # ! $ % * + _ \`
  aren't wired up.
- **Section 7** — autocomplete (`ui/palette.py`'s `SuggestionEngine`)
  still only covers commands, not history/calculations/notebooks/
  constants/formulas.
- **Section 8** — histories are still one combined `/history`, not
  separated into chat/code/calculation/simulation/export.
- **Section 9** — `workspace.py` organizes generated *files* by
  category; it doesn't yet make one AI request fan out into multiple
  output types (code + report + diagram description, etc.) the way
  the spec describes.
- **Section 10** — no feedback/bug-report/feature-request UI exists.
