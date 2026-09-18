# v0.7.8.2 — Attachments Truly Reach the Model + Mode Persistence

v0.7.8.2 closes the two remaining gaps behind the v0.7.8.1 pipeline
work. The pipeline itself was verified sound; the *payloads* it built
were not, and the mode lockdown was per-session only. Both are fixed at
the data layer, with a headless verification matrix exercising every
format the extractor knows about.

- Provider-native image payloads: image attachments are now sent in the
  shape each provider's API actually requires — OpenAI `image_url`,
  Anthropic `image`/`source`, Gemini `inline_data`. Before this fix,
  every provider received the OpenAI shape, so Anthropic and Gemini
  vision models silently never saw the image.
- Mode persistence: the selected AI mode now survives restarts. The
  saved mode is read back from the config file at startup and re-saved
  whenever you switch — no more silently resetting to Notebook on the
  next launch.
- Dead code removed: the old `_AttachPrompt` path-typing dialog (never
  referenced since the Attach panel redesign) is gone.

Backward compatibility: no v0.7.8.1 behavior was removed; text
attachments, the chip pipeline, panels and the mode lockdown are
unchanged.

---

## 1. Attachments Actually Reach the Model

v0.7.8.1 built the full pipeline (chip → validation → extraction →
context block), but `_user_content` in `aicore.py` constructed OpenAI-
shaped image parts for *every* provider. Anthropic expects
`{"type": "image", "source": {"type": "base64", ...}}` and Gemini
expects `{"inline_data": {"mime_type": ..., "data": ...}}` — both got a
payload their schema rejected, so the image never arrived and vision
models had nothing to look at.

- `_user_content` now takes the provider's `api_style` and emits the
  native shape per provider; text-only providers keep the text path.
- All three request builders (`_openai_messages`, `_anthropic_messages`,
  `_gemini_contents`) pass their style through, so both `stream_ai` and
  `query_ai` produce valid bodies for every supported provider.
- This matches the shape `query_ai_with_image` already used, so the
  whole codebase speaks one payload dialect per provider.
- Weak/non-vision models still degrade to the honest text context block
  ("The image was noted by name only, not actually sent") — never to
  silence.

## 2. Mode Persists Across Restarts

v0.7.8.1 locked the mode during a session, but `CCTApp.__init__` and
the module default both hard-coded `"notebook"` and the config field
`default_ai_mode` was never read — every restart silently reset the
mode. Now:

- `ai_modes._restore_saved_mode()` reads `default_ai_mode` from the
  central config at import time (validated against the known mode set).
- `set_mode()` persists the new mode on every switch (best-effort — a
  failed config write never breaks the switch).
- The UI starts in the restored mode and syncs the composer badge at
  mount.

## 3. Housekeeping

- `_AttachPrompt` (the old manual path-typing dialog, unreferenced
  since v0.7.8.1) removed from `ui/app.py`; unused `Label`/`Input`
  imports trimmed.
- Nothing else touched: Open Folder, the panels, and all working v0.7.8
  behavior are unchanged.

---

## Verified

- `python -m compileall calc_terminal` — clean.
- Format matrix (headless): `.py .js .json .md .txt .csv .html .css
  .yaml .log` all extract real content; CSV/JSON parsed; PDF honest;
  DOCX honest ("content not readable as text"); unknown binary honest;
  missing file fails honestly; oversized file capped; folder listing
  works — all PASS.
- Fix tests: provider-native payload shapes asserted per
  api_style (openai/anthropic/gemini) and mode persistence round-trip
  (saved mode restored on import, switch persisted) — all PASS.
- UI pilot: real `CCTApp` with stubbed `stream_ai` — attach → chip →
  prompt contains the file content → real `Attachment` objects reach
  the model layer → mode unchanged — all PASS.
- Mode matrix: notebook/research/plan/build/debugger/agent — extraction
  ready, mode unchanged after send and after typing; agent loop prompt
  contains the attachment content; attachments registered on the agent
  — all PASS.
- Panel pilot: Attach, MCP (+Add form field toggles), Backup
  (+Add provider), Settings and Open Workspace all mount, interact and
  Escape-close — all PASS.
- No pre-existing behavior removed; no new dependencies.

## Files

- fixed: `calc_terminal/aicore.py` (`_user_content` provider-native
  payloads; `_openai_messages`/`_anthropic_messages`/`_gemini_contents`
  pass `api_style`)
- fixed: `calc_terminal/ai_modes.py` (`_restore_saved_mode`,
  `_persist_current`; `set_mode` persists)
- fixed: `calc_terminal/ui/app.py` (startup honors saved mode; composer
  badge synced at mount; dead `_AttachPrompt` removed)
