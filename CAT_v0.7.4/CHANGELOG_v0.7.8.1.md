# v0.7.8.1 — Critical Bug-Fix + Attachment Pipeline + UI Stability

The v0.7.8.1 build is the bug-fix follow-up to v0.7.8. It fixes the
three reported critical behaviors — typing changing your AI mode,
interrupting a long generation being unreliable, and attachments never
really reaching the model — and hardens the panels so nothing dead-ends
or freezes.

- Attachment Pipeline: attachments are now first-class citizens of
  every Turn — selected → validated → read → type-detected → extracted →
  normalized → embedded in the model context (or sent as native
  payloads when the provider supports it). The chip, the session Turn
  and the provider request share the same attachment objects.
- Mode Lockdown: typing in any mode no longer silently re-routes CCT to
  Notebook. The selected mode is persistent; Notebook is only entered
  by an explicit user action.
- Interruption: STOP / ESC / Ctrl+C now cancel on every layer (worker,
  provider request, UI state), keep the partial output, and return the
  UI to an interactive state.
- Long-task visibility: Agent/Build runs stream live step lines, status
  lines ("Reading: path", "Editing: path") and an Activity panel.
- CLI fallback parity: the classic terminal no longer auto-switches
  modes either — same persistent-mode rule.

Backward compatibility: no v0.7.8 behavior was removed; the welcome
modal, panels, themes and workspace management are unchanged.

---

## 1. Attachment Pipeline

New `calc_terminal/attachments.py` — the single source of truth for how
a file becomes model context:

- `Attachment` — normalized object: `id`, `name`, `path`, `extension`,
  `mime_type`, `size`, `kind`, `content`, `metadata`,
  `extraction_status`, `error`.
- `AttachmentManager` — verify (stat + size sanity), read (bounded,
  text-first), type detect, extract (text/code formats), and
  `build_context()` which renders the honest text block embedded in the
  request:
  `--- ATTACHMENT <name> (<kind>, <size>) --- <content> --- END ---`
- `ProviderCapabilities` / `load_provider_capabilities()` — the
  capability layer: native image/PDF payloads only for providers that
  declare them; everything else degrades to the text context block,
  never to silence.
- Verify-before-show: a chip never claims "Attached" unless extraction
  succeeded; failures carry the real reason.

`calc_terminal/aicore.py` — `_prepare_attachments()` is the ONE
attachment→request path: it verifies, builds the context block (and the
native payloads when supported) and raises `AttachFailure` with a
user-readable reason otherwise. `stream_ai()` and `query_ai()` accept
`attachments=` and pass them through untouched.

Session: `Turn.attachments` records the real objects on every user turn,
and `as_prompt_history(include_attachment_context=True)` rebuilds the
notebook continuation with the same context blocks (uses
`AttachmentManager.build_context`, never re-derives from paths).

Agent: `agent.run_agent()` accepts `attachments`, exposes
`set_attachments` / `get_attachments` / `clear_attachments` tools, and
injects the extracted content into the loop context via
`read_attachment`.

UI:

- `ui/attachments.py` — composer chips with honest stage badges
  (Selecting / Validating / Reading / Parsing / Ready / Failed) that
  update as the pipeline runs; `pop_attachment_objects()` hands the real
  normalized objects to the message event; pasted/dropped paths are
  detected (`paths_from_paste`) instead of being dumped into the prompt
  text.
- `ui/attach_panel.py` — redesigned popup: File / Folder / Recent tool
  cards with a live-validating path entry and an honest AI-stage
  preview; files picked from the panel flow straight into the chips and
  the Turn. The old full-width text-field flow is gone.
- Build mode shows the attachment in the user bubble; agent mode keeps
  the attachment list on the agent.

## 2. Mode Switching Bug — Fixed at the Cause

- `ui/app.py` no longer calls `mode_detection.suggest_mode_change()` in
  any input path. `on_message_submitted` / `_maybe_gate_then_run` run
  in the user's selected mode, period (mode lockdown).
- Notebook is only reached via the explicit `/mode` / palette /
  `/notebook` commands (`_set_ai_mode`).
- Mode persists across messages, retries and rewrites.
- The classic fallback (`calc_terminal/app.py`) got the same fix:
  `handle_question` no longer auto-switches `_ai_mode`. Install /
  pipeline / deep-research *workflow routing* still runs (those are
  dedicated flows, not persona switches); only the heuristic persona
  change was removed. `suggest_mode_change` is now dead code kept for
  reference.

## 3. AI Response Interruption

- STOP button in the composer while generating; ESC and Ctrl+C both
  route to `action_cancel_streaming()`.
- Cancellation is layered: the Textual worker is cancelled, the
  provider request's `cancel_event` (threading.Event) is set so the
  stream aborts between chunks, and `_is_streaming` clears immediately.
- Partial output is kept; a "Generation stopped." note closes the turn;
  the composer returns to an interactive state (no ghost "generating"
  state).
- Retry after a stopped turn starts a fresh generation (the old
  "already generating" dead-end was removed).

## 4. Long Task Visibility

- Agent/Build turns stream live step lines ("◌ Planning…",
  "◌ Inspecting project…") and status lines ("Reading: path",
  "Editing: path") through `_on_agent_step`.
- The Activity panel (Ctrl+T) shows the in-flight request, live token
  counter, duration and last status.
- Build-mode output stays professional: the visible answer is the step
  summary — raw implementation code is not dumped into the answer
  unless the user explicitly asks for it.

## 5. Panels — No Dead Ends, No Freezes

- MCP panel: Test Connection runs in a background thread and reports
  via `call_from_thread` (never blocks the UI); the Add form's
  Remote/Local toggle shows/hides the right fields; Save validates
  before writing; Cancel/Escape dismiss.
- Backup panel: Add/Move Up/Move Down/Test all wired; provider config
  round-trips through the JSON dotfile; test runs off the UI thread.
- Attach panel, NavPanel and Settings screens Escape-close; nothing
  dead-ends.

---

## Files

- new: `calc_terminal/attachments.py`
- rebuilt: `calc_terminal/ui/attachments.py` (honest chips +
  `pop_attachment_objects`), `calc_terminal/ui/attach_panel.py`
- extended: `calc_terminal/aicore.py` (`_prepare_attachments`,
  `stream_ai`/`query_ai` attachments, `_log_attachment`),
  `calc_terminal/session.py` (Turn.attachments, attachment-aware
  history), `calc_terminal/agent.py` (attachment tools),
  `calc_terminal/ui/app.py` (mode lockdown, layered cancel, worker
  cleanup, agent step streaming), `calc_terminal/ui/composer.py`
  (STOP/generating state), `calc_terminal/ui/conversation.py`
  (attachment bubbles), `calc_terminal/ui/mcp_panel.py`,
  `calc_terminal/ui/backup_panel.py` (thread-safe tests),
  `calc_terminal/app.py` (CLI mode lockdown)

## Verified

- `python -m compileall calc_terminal` — clean across all modules.
- Headless pilot tests (120×40): app mounts; attachment pipeline runs
  end-to-end (chip → normalized object → message → `_augment_prompt`
  embeds the content → Turn.attachments recorded); mode persists
  across messages; STOP wiring resets UI state; MCP panel opens, Add
  form toggles STDIO fields, cancels cleanly; Backup panel opens, add
  form opens/cancels; Attach panel opens, browser lists files,
  attach → chip extracts to Ready; NavPanel opens with workspace
  commands removed.
- Classic CLI: typing "what is the derivative…" and a general question
  with mode pre-set to build/research leaves the mode unchanged.
- No pre-existing behavior removed; no new dependencies.
