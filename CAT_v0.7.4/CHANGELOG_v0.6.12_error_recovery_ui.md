# CCT v0.6.12 — Error Recovery reconciled onto the AI Modes branch,
# extended to the primary Textual UI

## Context: two branches had diverged

This project had been worked on in two places at once: this branch
(v0.6.11, "ai_modes_fixed") built the whole AI Modes system (Section 3)
against the primary Textual UI, while a separate chat session kept
extending `calc_terminal/errors.py`'s recovery-card system (Section 19)
against the classic fallback terminal — specifically, generalizing
`error_card()` to support extra named actions (Reconnect / Switch
Provider) and wiring that into `cmd_ai`/`cmd_agent`'s AI-provider-
unavailable case. That work existed only in the other session and had
never been packaged into a zip handed back — so this branch's
`errors.py` was still the older retry-only version.

This pass reconciles the two: ports the newer `errors.py` and
`aicore.is_error_response()` onto this branch, and re-applies the
`cmd_ai`/`cmd_agent` wiring. Verified byte-for-byte: after porting,
`calc_terminal/app.py` diffed **identical** against the other session's
copy — confirming this branch's `app.py` genuinely hadn't diverged in
that area (the AI Modes work only touched `calc_terminal/ui/`), so this
was a safe, mechanical port, not a guess.

## New — `calc_terminal/aicore.py`

`is_error_response(text)` — checks a response string against the exact
prefixes `query_ai()`/`stream_ai()` themselves return on every known
failure path (missing `requests`, unconfigured provider, unsupported
provider, connection error, timeout, generic connection exception).
Lets callers tell a real provider failure apart from an actual model
answer, since `query_ai()` returns these as plain strings rather than
raising.

## Changed — `calc_terminal/errors.py`

`error_card()` gained `extra_actions` — a list of `(label, callback)`
pairs shown as additional numbered options between Retry and View
Details. Used for Reconnect (`aicore.setup_ai()`) / Switch Provider
(`cmd_model()`) on an AI-unavailable card. If `retry` was also given,
picking an extra action automatically attempts the retry afterward
(reconnecting and not retrying the actual request would be a dead end).

## Changed — `calc_terminal/app.py` (classic fallback terminal)

`cmd_ai()` / `cmd_agent()`: after `agent.run_agent()` returns, check
`aicore.is_error_response(final_text)`. If it's a real failure (and no
tool steps ran, so a coincidental phrase match inside a genuine tool-
assisted answer isn't misread as a failure), show the recovery card
with Retry / Reconnect / Switch Provider instead of rendering the
failure text as if it were a normal chat reply. A bug caught by testing
before this shipped: the first draft called the card and then
unconditionally `continue`d, silently discarding a *successful* retry's
answer instead of rendering it — fixed by capturing the retry's result
and rendering it exactly like a normal reply when the card reports
success.

## New — `calc_terminal/ui/app.py` (primary Textual UI), `_stream_worker`

The primary UI can't reuse `error_card()` directly — it blocks on
`input()`, which cannot run on a Textual worker thread while the
reactive app is live. Added `_mark_ai_failure(text, title=...)`: wraps
a failure message with a clear `⚠` marker and actionable guidance
("Resend to retry, or run `/model` to switch providers") instead of
letting it stream into the conversation looking like a genuine answer.
Wired into all three failure surfaces in `_stream_worker`:
- Agent mode: checked before the single chunk is posted (the full
  answer is already known at that point, so this is a clean catch).
- Notebook/Build/Plan (streamed) mode: checked against only the
  *first* streamed piece — `stream_ai()`'s failure paths yield the
  entire message as one piece before any real network streaming
  begins, so a first-piece match means "this is a failure," not real
  content starting to arrive.
- The outer exception handler (anything `stream_ai`/`run_agent` didn't
  turn into a returned/yielded string) — marked with a more neutral
  "Something went wrong" title since it isn't necessarily a
  connectivity issue.

## Honest limitations of the Textual UI piece — disclosed, not hidden

- This is **text marking**, not a clickable card. `errors.py`'s
  Retry/Reconnect/Switch Provider buttons don't exist here yet — that
  would mean a new interactive widget (the codebase already has a
  precedent for this: the existing permission cards for Allow Once/
  Always Allow/Deny), wiring button presses back across the worker-
  thread boundary, and is real, separate follow-up work, not done in
  this pass.
- A failure that happens **mid-stream** — real tokens already arrived,
  then the connection drops — isn't caught by the first-piece check.
  That's a genuine gap, not a silently dropped case.
- **This specific change was not verified with `App.run_test()`**, unlike
  the rest of this branch's UI work. `textual` isn't installed in the
  sandbox this pass ran in (no network access to install it), so full
  headless integration testing wasn't possible here. What *was*
  verified: the file parses correctly, `_mark_ai_failure()` (a pure
  function with no Textual dependency) behaves correctly under direct
  unit tests, `aicore.is_error_response()`'s signatures still match
  exactly, and the control flow was confirmed correct by careful static
  review — but that's a lower bar than actually running the worker
  against a live (headless) app instance. Flagging this explicitly
  rather than implying the same verification rigor as the rest of the
  branch.

## Verified

- `errors.py`: full prior test suite (retry success/failure, View
  Details, extra_actions with and without retry) re-run against this
  branch's copy — passes unchanged.
- `aicore.is_error_response()`: all 7 known signature cases plus one
  real-looking answer (correctly NOT flagged) — passes.
- Classic terminal: `cmd_ai` and `cmd_agent`, each tested with a forced
  first-call failure — confirmed the card appears, Retry re-invokes the
  request, and a successful retry's real answer is what actually
  renders (not silence, not the stale failure text).
- Full 41-command classic-`app.py` dispatch regression suite (from
  prior passes) re-run on this branch — passes.
- `calc_terminal/ui/app.py`: syntax-parses correctly; imports cleanly
  even with `textual` absent (confirms `_mark_ai_failure` sits outside
  the Textual-dependent class, so it degrades safely); `CCTApp` is
  correctly `None` in this environment as expected, which is *why*
  `_stream_worker` itself couldn't be directly exercised here.
