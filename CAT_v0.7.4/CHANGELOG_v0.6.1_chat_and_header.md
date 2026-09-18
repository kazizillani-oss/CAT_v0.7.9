# v0.6.0 — Chat layout + conversation memory

Addresses the two remaining issues from the last pass: broken layout and
zero conversation memory. Root cause for both was found and fixed rather
than patched around; each is verified with a headless test (details below).

## 1. Conversation memory (the important one)

**Root cause:** `calc_terminal/aicore.py`'s `query_ai()` and `stream_ai()`
never accepted or sent conversation history at all — every request was
built from just the single latest prompt string, for every provider
(OpenAI/OpenRouter/Groq, Anthropic, Gemini, Ollama). Meanwhile
`calc_terminal/session.py` already had a `ChatSession.as_prompt_history()`
method that tracked the full transcript — but nothing ever called it.
The primary UI (`ui/app.py`) called `aicore.stream_ai(prompt)` with just
the current message and threw the rest of the session away on every turn.

**Fix — `calc_terminal/aicore.py`:**
- `query_ai()` and `stream_ai()` both take a new `history` parameter: an
  ordered list of `(role, text)` pairs (or `{"role", "text"}` dicts).
- New helpers build the right shape per provider: `_openai_messages()`
  (OpenAI/OpenRouter/Groq/vLLM/Ollama-`/v1`), `_anthropic_messages()`,
  `_gemini_contents()` (maps `assistant` → Gemini's `model` role), and
  `_ollama_native_prompt()` for the native `/api/generate` endpoint,
  which has no messages array — history is folded into a plain
  transcript prefix there instead.
- `_sanitize_history()` normalizes whatever's passed in and drops empty
  turns (e.g. an in-progress streaming placeholder), so callers don't
  have to.
- Token-usage estimation (`estimate_tokens` fallback path) now accounts
  for history size too, not just the latest prompt.

**Fix — `calc_terminal/session.py`:**
- `ChatSession.as_prompt_history(limit=None, before_turn_id=None)`:
  `before_turn_id` cuts the transcript strictly before a given turn by
  *identity*, not position — needed because by the time a background
  worker reads session state, the current user turn usually already has
  an (empty, in-progress) assistant turn appended after it, so "drop the
  last entry" silently stops working. This was caught by an end-to-end
  test (see below) and fixed before shipping.
- **Context window management:** `needs_summarization()` /
  `summarize_older_turns()` — once the un-folded backlog exceeds
  `KEEP_VERBATIM (16) + FOLD_HEADROOM (8)` turns, everything older than
  the most recent 16 gets condensed via one summarization call (using
  `aicore.query_ai`) into a running `older_summary` string, which is
  then sent as a leading synthetic turn on every subsequent request.
  Best-effort: a failed/errored summarization call is a no-op, so
  verbatim turns are never silently dropped, only re-attempted later.
  UI scrollback (`self.turns`) is never touched by this — only what
  gets sent to the model changes.

**Fix — `calc_terminal/ui/app.py`:**
- `_begin_assistant_turn` now captures the current user turn's id
  *before* starting the assistant placeholder turn, and passes it
  through to `_stream_worker`.
- `_stream_worker` calls `session.summarize_older_turns(aicore.query_ai)`
  (off the UI thread — it's a network call) and builds
  `session.as_prompt_history(before_turn_id=...)`, then passes that as
  `history=` into `aicore.stream_ai(prompt, history=history)`.

**Verified with:**
- A direct `aicore.query_ai` test with a faked `requests.post` that
  reproduces the exact bug-report scenario (assistant sends "1 2 3 4 5",
  user replies "3") and asserts the outgoing payload contains all 4
  messages in order and the reply correctly resolves "3" using history.
- A full UI-pipeline test (`on_message_submitted` → `_stream_worker` →
  `stream_ai`) with a faked `aicore.stream_ai`, asserting the second
  turn's history contains the first turn's user+assistant pair exactly
  once, with no duplication of the current prompt.
- A summarization test: 30 user/assistant pairs → confirms
  `needs_summarization()` flips correctly, `older_summary` gets
  populated, and `as_prompt_history()` returns exactly
  `1 (summary) + KEEP_VERBATIM` entries afterward.

## 2. Chat layout

**Root cause:** `#cct-composer` in `calc_terminal/ui/app.py` was
`dock: bottom; width: 1fr; margin: 0 2 0 2;`. In Textual, a **docked**
widget's `width: 1fr` does not subtract its own horizontal margin — the
box was computed 4 columns wider than the space actually available, so
its right edge rendered past the screen boundary and got clipped. This
reproduces in isolation with a 2-line Textual app and is a real,
confirmed Textual quirk (`width: 100%` on the same widget correctly
subtracts the margin; `width: 1fr` does not — verified both ways with a
headless test before touching the real app).

**Fix:**
- `#cct-composer`: `width: 1fr` → `width: 100%`. No longer overflows the
  screen at any tested size (80×24, 100×30, 120×40, 160×50 — see test
  below). Also added `max-height: 60%` so a very tall composer (many
  attachment chips) can't push the conversation off-screen, and widened
  its margin slightly (`margin: 1 2`) for breathing room above/below.
- `#cct-conversation`: explicit `width: 100%; height: 1fr;`,
  `overflow-y: auto; overflow-x: hidden;`, `scrollbar-gutter: stable`
  (prevents the scrollbar from appearing/disappearing and shifting
  content width as messages are added), and slightly more padding.
- `.cct-item`: added `margin: 0 0 1 0` for consistent vertical spacing
  between turns (previously only assistant turns had a bottom margin).
- Audited every other docked widget (`#cct-brandheader`,
  `#cct-statusline`) and every other `width: 1fr` in the package for the
  same dock+fr+margin combination — neither has it, so this was the one
  instance of the bug, not a symptom of a wider pattern.

**Verified with:** a headless Textual test (`app.run_test`) asserting,
at four different terminal sizes, that the conversation view is exactly
full-width and the composer's right edge never exceeds the screen
width — both were failing before this fix (composer overflowed by
exactly the margin amount) and pass after it.

---

# v0.6.1 — Real chat bubbles + compact header

## 1. Chat bubble layout

**What was actually going on:** `calc_terminal/ui/conversation.py`
already had a full bubble implementation from an earlier pass —
`MessageRow` (aligns a bubble left/right/center), `ConversationItem`
rendering as a bordered, colored bubble with an optional timestamp, a
deploy animation on send, a streaming cursor, real Markdown for
assistant replies. None of it was visible, because the CSS those
classes need (`.cct-row*`, `.cct-bubble*`) was never added —
`calc_terminal/ui/app.py`'s `_COMPONENT_CSS` still only styled the old
flat `.cct-item*` selectors from before that pass, so every bubble
rendered with zero relevant styling: full width, no color, no
alignment. That's exactly what the screenshot showed. Fixed by adding
the missing CSS rather than rewriting the widgets, which were already
correct:

```
.cct-row-user       { align-horizontal: right; }
.cct-row-assistant  { align-horizontal: left; }
.cct-row-system     { align-horizontal: center; }
.cct-bubble-user      → width:auto, max-width 70%, solid $accent bg
.cct-bubble-assistant → width:1fr,  max-width 82%, $surface bg, wider padding
.cct-bubble-system    → no chrome, centered, dim italic
```

Also gave fenced code blocks a real syntax-highlighting theme tied to
CCT's own dark/light mode (`material` / `friendly` pygments themes)
instead of Rich's unrelated `monokai` default — `conversation.py`'s
`_code_theme_for_current_theme()`.

**Verified with:** an end-to-end test that submits a message through
the real `on_message_submitted` → streaming pipeline and asserts the
user bubble is flush against the row's right edge, the assistant bubble
is flush against the left edge, and the assistant bubble is
meaningfully wider than the user bubble — this was failing (both
full-width, no distinction) before the CSS was added.

## 2. Header clipping + compact redesign

**Root cause of the clipping bug:** `BrandHeader` rendered
`LOGO[:4]` — the first 4 rows of a 6-row block-art logo — inside a
CSS `height: 4` box. Each letter's block art needs all 6 rows to read
as an intact character; slicing to 4 cropped every glyph mid-stroke,
which is exactly the distorted/overlapping look in the bug report.

**Fix:** `calc_terminal/ui/header.py`'s `BrandHeader` is now a compact
two-line header instead of the multi-row block logo (which still shows
once, intact, on the pre-chat `WelcomeBanner` — that one wasn't
broken):
- Line 1: a single chemistry glyph mark + `CCT` + subtitle —
  `⚗ CCT   Chemistry Calc Terminal`.
- Line 2: a live breadcrumb — `Notebook · <provider model> · Workspace
  · Context <N>K`, matching the requested compact-header format.
- CSS height is `auto` instead of a fixed row count, so it can never
  drift out of sync with its own content again, and it wraps instead of
  clipping at very narrow terminal widths.

The breadcrumb is wired to live state via a new
`CCTApp._refresh_header_breadcrumb()`, called on mount and whenever
notebook mode, model, workspace, or context tokens change (previously
`NotebookChanged`/`WorkspaceChanged` were posted but nothing listened —
`on_notebook_changed`/`on_workspace_changed` handlers added).

**Verified with:** a headless test confirming the header renders
exactly `⚗ CCT   Chemistry Calc Terminal` / `Notebook · no model ·
Workspace · Context OK`, stays a fixed 3 rows tall (2 content rows +
border) at every tested width down to 40 columns, and never overlaps
the conversation area.
