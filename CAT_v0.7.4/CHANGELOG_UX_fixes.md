# UX fixes — composer deploy behavior, compact layout, persistent branding

Addresses the two requests in this pass:

## 1. Composer "deploy" behavior 

`calc_terminal/ui/composer.py`:
- **Enter now submits** the message (previously only Ctrl+Enter did;
  plain Enter inserted a newline). **Shift+Enter inserts a newline**
  instead. Ctrl+Enter still submits too, for muscle memory.
- Fixed a bug uncovered by this change: `TextArea` has its own built-in
  key binding that inserts a newline on Enter. Calling `event.stop()`
  alone didn't suppress it — `event.prevent_default()` is also
  required (the file's existing `_on_paste` handler already did this;
  `_on_key` now does too). Without this fix, Enter would both submit
  *and* leave a stray newline behind in the (now empty) composer.
- After submit, the editor is explicitly refocused so keyboard focus
  and the cursor never leave the composer.
- The keyboard hint row was updated to say
  `Enter send   Shift+Enter newline   ...`.

`calc_terminal/ui/conversation.py`:
- `ConversationItem` now plays a short fade + slide-up "deploy"
  animation (opacity 0→1, margin-top 1→0 over ~0.2s) the moment a
  **user** turn mounts into the conversation — the visual effect of
  the message leaving the composer and landing in the history.
  Assistant/system turns mount plain.
- `ConversationView.add_complete` now scrolls to the newest message
  with a brief animated scroll instead of an instant jump.

The composer and the conversation were already two separate Textual
widgets (`StickyComposer` docked at the bottom, `ConversationView` as
the scrollable region) — the composer never becomes part of the
conversation itself, which was already correct; this pass fixes the
*feel* of the handoff between them.

## 2. Compact layout + persistent CCT branding

`calc_terminal/ui/header.py` (new):
- `BrandHeader`: a small, permanent widget showing the CCT block-art
  mark plus "Chemistry Calc Terminal", docked to the top of the
  screen. It is mounted once by `CCTApp` and never removed — unlike
  `WelcomeBanner` (still in `conversation.py`), which is a one-time
  empty-state tip that disappears after the first message.

`calc_terminal/ui/app.py`:
- `BrandHeader` is now the first thing `CCTApp.compose()` yields,
  docked `top`, fixed at 4 rows tall, with a bottom border separating
  it from the scrolling conversation below.
- Refreshes its colors (not content) on `/theme` toggle.
- Denser spacing: `#cct-conversation` padding 1 2 → 0 2, `.cct-item`
  margin 0 0 1 0 → 0 (assistant turns keep a 1-row bottom margin so
  Markdown blocks don't run together), welcome-banner padding 4 2 →
  2 2, composer bottom margin 1 → 0.

Verified headlessly with `App.run_test()`: the header mounts, Enter
submits and clears the composer while keeping focus, Shift+Enter
inserts a newline without submitting, and the deploy animation runs
without raising.
