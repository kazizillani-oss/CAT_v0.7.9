# CHANGELOG — CAT v0.7.9.5

**Major Stability, UI, Theme & Response-Performance Fix**

Two goals drive every change below: **CAT must never appear frozen or leave
a permanent `...` response**, and **the UI must look stable and intentional
in both dark and light themes**. Fixes target root causes (request state
management), never superficial patches — no sleeps, no fake animations.

---

## 1. The `...` / no-response bug — request lifecycle rebuilt

`calc_terminal/aicore.py` + `calc_terminal/ui/app.py`:

* **Guaranteed finish.** `_stream_worker` now posts `MessageFinished` from a
  `finally` block. Success, provider failure, exception, cancel, even
  `call_from_thread` dying during app teardown — the loading state ALWAYS
  clears and the prompt always comes back.
* **Every failure surfaces as content or a real error.** A stream that ends
  with zero tokens is converted to `"No model response received."` (new
  error signature); all-providers-failed still yields the last real error
  string. The UI can never sit on an eternal `...`.
* **First token replaces `...` immediately** (unchanged streaming contract,
  verified end-to-end: fast question = exactly 1 transport call).
* **Mid-stream drops are honest**: tokens already delivered are kept and one
  line (`⚠ Connection lost mid-response`) discloses the loss — no silent
  truncation, no duplicated re-run of the answer from another provider.
* **Failover hook actually installed** (`set_failover_hook` was dead code):
  the UI drains provider-switch notes into the live bubble, so
  "⚠ Provider issue (x). Switching to Backup Provider..." is visible in the
  right turn instead of happening silently.
* **Ctrl+C / Stop cancels for real.** Every in-flight HTTP response is
  registered; `aicore.cancel_active_requests()` closes the sockets so a
  request blocked inside a socket read stops immediately (previously Esc
  appeared dead until the next chunk or idle timeout). Cancellation within
  a short window produces a clean stop, not a scary error card.

## 2. Model timeout + safe recovery (configurable)

New `config.py` fields (persisted in `~/.cct_config.json`, consumed via
`aicore.request_timeouts()`):

```
timeout_simple            30 s   trivial / fast-path prompts
timeout_normal            60 s   regular chat turns
timeout_large            300 s   agent / build / pipeline work
model_idle_timeout        45 s   max silence between stream chunks
```

* All five HTTP call sites use `(connect, idle)` timeout tuples; the TOTAL
  deadline is enforced between chunks (`_TotalTimeout`), so an actively
  streaming model is never misclassified as frozen while a silent one can't
  hold the turn open forever. Ollama's old unconditional 120 s is gone.
* Agent-loop, planner, vision calls pass `size_class="large"`; the farewell
  generator uses `"simple"`. Router decisions pick the class automatically.

## 3. Fallback system — bounded, cooled-down, backed-off

* Walk order: primary → enabled backups (priority order). Providers that
  failed recently sit in a **cooldown** (`model_provider_cooldown`, 20 s)
  demoted to the end of the walk so a dead primary stops taxing every turn.
* **Retries per provider are bounded** (`model_max_retries_per_provider`,
  default 1) with **exponential backoff** (`model_retry_backoff_base`,
  0.6 s ×2ⁿ capped at 4 s) and only for TRANSIENT failures — quota/429/config
  errors skip straight to the next provider. No endless hammering.
* Backup success marks the entry used (`mark_backup_used`) exactly as before.

## 4–5. Fast path + request classification

* `model_router.complexity_class()` maps every request to
  `TRIVIAL / SIMPLE / NORMAL / COMPLEX / AGENT / RESEARCH`; the decision's
  new `size_class` field drives BOTH the execution path and the timeout
  budget. Genuinely trivial prompts (`hi`, `12*7`, ≤25 chars small-talk)
  take the fast path outright — no memory scan, no summarization, no agents,
  no tools, one model call (verified headless).

## 6–7. Main menu hover — glitch-free by construction

* All selectable rows (`NavPanel`, permission menu, recent-workspace rows,
  command palette rows, attach/profile panels) now reserve their selection
  rail in EVERY state: base rules carry `border-left: thick transparent`
  (or solid transparent where hover uses solid), so hover/selection changes
  color only and text can never shift horizontally mid-hover.
* Hover remains a subtle foreground change; keyboard-selected rows add the
  accent rail + bold without moving neighboring items. No background fills,
  no full redraws — Textual's native per-row `:hover` resolution only.

## 8–9. Ctrl+P — light mode + real lifecycle fix

* **Root cause found:** Textual 8 ships its own built-in command palette on
  Ctrl+P. It intercepted the keypress before CAT's binding, pushing a
  foreign, differently-styled screen (the "black blocks / broken controls"
  screenshot symptom) that left stale widgets behind. Fixed by rebinding the
  built-in away (`COMMAND_PALETTE_BINDING = ""`, `use_command_palette =
  False`) — CAT's own variable-driven "/" palette owns Ctrl+P in every theme.
* **Draft preservation:** Ctrl+P over an unsent draft stashes it; Escape
  restores it, accepting a command replaces it deliberately.
* Palette row colors resolve through `theme.role_hex` at draw time; open
  palettes repaint on theme switches; the dependency-free Tokyo-Night
  fallback hex table is gone (neutral gray fallback readable on any surface).
* Verified 50/50 across tokyo-night, github-light, catppuccin-latte, nord,
  rose-pine-dawn: open → filter → navigate → Escape-restore → accept →
  close → restore, plus WCAG contrast on palette surfaces per theme.

## 10–11. Goodbye renders exactly once

Re-verified and hardened on the classic-terminal side: `/quit`, `/exit`,
`exit`, `quit` route through the ONE idempotent `goodbye.shutdown_session()`
(reason="task" when work completed, "exit" otherwise). The inline farewell
panel that could double-render alongside the animated goodbye is gone.
Probe: 24/24 including back-to-back exit commands rendering once.

## 12–17. Theme system — 22 normalized themes

* New `Theme` dataclass schema (`theme.py`): name, label, dark flag +
  background, surface, surface_hover, text, text_muted, text_faint, border,
  border_active, accent, accent_alt, accent_secondary, input_background,
  selection_background, selection_text, success, warning, error.
* Full catalog registered: ansi-dark, ansi-light, atom-one-dark,
  atom-one-light, catppuccin-frappe, catppuccin-latte, catppuccin-macchiato,
  catppuccin-mocha, dracula, flexoki, gruvbox, monokai, nord, rose-pine,
  rose-pine-dawn, rose-pine-moon, solarized-dark, solarized-light,
  textual-dark, textual-light, tokyo-night (+ github-light kept as the
  legacy light). Legacy aliases `dark` → tokyo-night and `light` →
  github-light keep old configs and muscle memory working byte-for-byte
  (both legacy palettes are pinned verbatim).
* Each Theme compiles into the same 30 module globals the classic terminal
  has always read — zero changes needed anywhere else — and
  `fit_contrast()` nudges any under-contrast accent automatically.
* **Binary gates removed:** `set_theme` no longer collapses every name to
  dark/light; `load_saved_theme` honors ANY registered name; unknown names
  fall back safely. Persistence writes BOTH stores (`~/.cct_theme.json` +
  config `default_theme`) on permanent switch, previews write neither.
* Light-mode component variables (selection washes, cursors, button labels,
  markdown headings, footer keys, blurred borders) are now DERIVED from the
  active Theme object instead of hardcoded GitHub-Light hexes — every light
  theme gets correct chrome; dark themes keep Textual defaults untouched.
* Contrast validated programmatically for all 22 themes: text ≥4.5:1 on
  background, ≥4:1 on surface, muted ≥2.5:1, accents/success/warning/error/
  selection ≥3:1. Zero violations.

### Live hover preview (13/15/16)

ThemesPanel + Settings→Theme rows: hovering a row applies that theme live
(`set_theme(..., persist=False, paint_bg=False)`); moving away restores the
saved theme; clicking applies + persists permanently and ends preview mode.
State machine is exactly `display = preview_theme or selected_theme`, fires
only when the hovered theme CHANGES (no rebuild-per-mouse-move), and rows
render `✓` (permanent), `›` (hovered), spaces otherwise — identical cell
widths, exactly one ✓, stable geometry, scrollable panel.

## 18–26. Performance architecture notes

* Metrics unchanged in shape but now include router size-class context;
  structured request logging added (below). Response caching stays limited
  to safe static data (fs_cache, capability registry TTL) — AI answers are
  never cached. Parallelism unchanged (reviewer fan-out already concurrent);
  dependent file operations remain sequential. Workers stay off the UI
  thread; cancel support above; error cards concise (tracebacks behind
  `CAT_DEBUG_TB=1`).
* **Structured request log** `~/.cct_requests.log` (JSONL, rotated ~512 KB):
  per-request start / first_token / retry / provider_exhausted /
  midstream_drop / finish / error events with provider, model, size_class,
  elapsed ms, chars, exception class. Never API keys, headers or prompts.

---

## Tests

* NEW `calc_terminal/test_stability.py` (38 tests): theme catalog/schema/
  contrast/persistence/fallback-safety, picker semantics, request lifecycle
  (simple, streaming, empty, timeout, exception, fallback, mid-stream drop,
  cancel socket registry, bounded retries, cooldown, size-class timeouts),
  router classes, shutdown idempotency. Hermetic — no network, no user
  config dependence.
* NEW `_probe_theme_preview.py` (12 checks): full hover→preview→leave→
  click→persist→restart chain headless.
* NEW `_probe_palette_lifecycle.py` (50 checks): Ctrl+P across five themes.
* UPDATED `_probe_light_mode.py`: component-variable assertions now check
  the derivation contract (any-theme correct) instead of one theme's hexes.
  `_probe_modals.py`: textual-8 `Region.contains` API fix.
* FULL SWEEP GREEN: 178 unit tests · 21/21 light-mode · 24/24 goodbye ·
  12/12 theme-preview · 50/50 palette · v079-e2e · 17/17 startup · 19/19
  empty-state · 32/32 layout · 12/12 drag · 13/13 final · 32/32 animation ·
  8/8 System32-launch.

## Manual verification checklist (all verified)

simple chat (fast path, 1 transport call) · slow model (total deadline
fires, error card, loading clears) · failed model (bounded retry → backup
note visible → success) · fallback exhaustion (final error, no `...`) ·
Ctrl+Q · /quit (single goodbye) · Ctrl+P in light mode · theme hover
preview · theme click persistence · restart restores theme.
