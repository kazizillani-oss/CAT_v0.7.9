# CHANGELOG — CAT v0.7.10

**Live Web Preview, Embedded Browser & 3-Pane Workspace Upgrade**

CAT gains a professional, terminal-first **Live Web Preview**: a real local
development server + REAL Chromium (Playwright) embedded in the right
workspace pane, with debounced live reload driven by the file watcher and
CAT's own AI writes — while the File Pane, Chat Area, editor, themes,
shortcuts and every existing feature stay exactly as they were.

---

## Architecture — new `calc_terminal/browser/` package

```
calc_terminal/browser/
├── state.py         WorkspaceMode · PaneMode · PreviewState ·
│                    ServerState · EditorState   (spec §22 state model)
├── server.py        LiveServer — threaded HTTP dev server + WebSocket channel
├── engine.py        BrowserEngine — Playwright Chromium on a worker thread
├── watcher.py       PreviewFileWatcher (150 ms debounce) + Debouncer
├── navigation.py    NavigationHistory — back / forward / reload stack
├── preview_entry.py entry-point detection + workspace-relative URLs
└── preview.py       PreviewController — the ONE lifecycle owner

calc_terminal/ui/
├── preview_panel.py NEW — browser chrome bar + live DOM viewport +
│                    CAT BUILD ACTIVITY strip
├── workspace.py     three-pane architecture: chat column ⇄ right pane
├── resizers.py      NEW RightPaneResizeHandle (+ persisted width)
├── editor.py        ▷ Preview pill on HTML tabs
└── events.py        PreviewRequested · PreviewClosed · BuildActivity
```

## Right pane: CODE ⇄ WEB PREVIEW (spec §2)

`WorkspaceShell` now composes THREE independent multitasking sections:

```
┌──────────────┬─┬───────────────────┬─┬──────────────────┐
│ FILE EXPLORER│║│ CHAT + COMPOSER   ║│ EDITOR ⇄ PREVIEW │
│  (resizable) │║│  (own column!)    ║│  (resizable)     │
└──────────────┴─┴───────────────────┴─┴──────────────────┘
```

* The composer lives INSIDE its own chat column — it is geometrically
  impossible for the chat box to overlap the Code Editor or Preview any
  more (**spec §26 fixed at the layout level**, verified by a geometry
  assertion in the probe).
* Editor and Preview are both permanently mounted; switching modes only
  flips `display`, so **editor tabs/cursor/unsaved state AND preview
  navigation/history all survive every switch**, and the right pane keeps
  its exact width across switches.
* Narrow terminals keep the historical stacked Chat/Files switcher.

## ▷ Preview button (spec §3)

The editor toolbar grows a `▷ Preview` pill, visible only while an HTML
tab is active. Clicking it runs the full chain off the UI thread:
detect project/web root → find entry (`index.html`, walking up from the
open file; shallowest index within depth 3 otherwise) → start
`LiveServer` on an OS-assigned port → launch Chromium → navigate → flip
the right pane to PREVIEW — editor state intact throughout.

## Local live server (spec §4, §19, §20)

`LiveServer` binds **127.0.0.1 only**, picks a free port via the OS
(`:0`) — never hard-coded — and serves the CURRENT WORKSPACE only:

* correct MIME types for html/css/js/json/svg/png/jpg/gif/webp/woff2/
  ttf/mp4/wasm/… ; directory → `index.html` resolution; relative paths
  work because everything is served from the web root;
* path resolution is normcase-normalized and verified UNDER the root —
  no `..` traversal can make it a file-sharing server;
* `no-cache` headers everywhere so Chromium always revalidates against
  files the AI is actively rewriting;
* hot-reload snippet injected into HTML responses;
* `stop()` is idempotent and joins all threads; controllers are also
  registered with `atexit` — **no orphan sockets or Chromium processes**
  survive CAT exit, crashes included.

## Real browser engine (spec §5–6)

`BrowserEngine` runs genuine Chromium through Playwright on its own
worker thread (the sync API's only safe home); every call marshals a job
and waits, so callers never cross threads and the UI never blocks.
HTML/CSS/JS/animations/responsive layout/images/SVG/fonts/fetch/
WebSockets all execute for real. The terminal-first contract is kept by
rendering a structured snapshot of the LIVE DOM into the preview panel
(title, headings, links, buttons, images ✓/✗, element counts, browser
console + JS errors) — no external browser window is ever opened. A
screenshot hook exists so a graphical embedded surface can slot in later
without touching callers.

If playwright/chromium isn't installed, start() raises a precise,
actionable error which the panel renders as an isolated card — chat,
files, editor and the agent keep working.

## Browser controls (spec §7–8, §24)

```
← → ⟳ [ http://127.0.0.1:<port>/          ] ⏻ ⿻
```

All controls live at the TOP of the pane. Back/Forward walk a real
history stack (duplicate-push suppressed, forward branch truncated);
⟳ reloads; the URL field navigates local-project paths first
(`missing.html` → same origin) and absolute http(s) URLs; **⏻** stops
server+browser+watcher and returns the pane to the editor without
touching open tabs; **⿻** toggles FULLSCREEN over whatever the right
pane shows (Code OR Preview — one control, both modes) and restores the
exact previous configuration on exit (header/status hidden during).

## Resizable right pane (spec §9)

New `RightPaneResizeHandle` — a 1-column drag divider between the chat
column and the right pane, clamped to `[24px, 60%]`, persisted to
`~/.cct_ui_layout.json` (`rightpane_width`) and re-clamped on window
resize. Explorer resizing untouched (probe-verified).

## File tabs independence (spec §10–11)

Tabs behave as before (open/focus/close, ✕ zones, Welcome placeholder
when empty). Closing ALL tabs shows the empty editor and **never touches
a running preview** — the server belongs to the workspace session.
Opening a file while previewing drops the tab in underneath instead of
yanking the user out of the site.

## AI live website preview (spec §12–14)

Three refresh paths, all debounced:

1. **AI write tools** (`write_file` etc.) notify the controller directly
   the moment each tool finishes — the user watches the site evolve
   WHILE the agent streams, never waiting for the reply to finish;
2. the OS watcher (`PreviewFileWatcher`, watchdog or poll fallback)
   catches external edits, filtered to web extensions;
3. bursts coalesce: direct notifications go through a 150 ms
   trailing-edge `Debouncer`, watcher batches already arrive coalesced —
   probe-verified **12 rapid writes → ≤3 reload signals**.

CSS-only changes take the HOT path: stylesheet links are cache-busted
in-page (via the injected WebSocket channel, falling back to direct
re-injection) — no full reload, state preserved. HTML/JS changes do a
safe full reload. Failures here are contained (`on_files_changed`
never raises into CAT).

## AI activity visualization + code out of chat (spec §15–16)

A bounded **CAT BUILD ACTIVITY** strip at the bottom of the preview panel
shows the real feed:

```
● Starting local server…
● Writing style.css
✓ CSS updated (1 file(s))
● Writing index.html
✓ Preview synchronized
```

Build lines render in the activity strip and preview status bar — never
dumped into the conversation (Build mode's existing `_hide_build_code`
already strips raw source from chat; unchanged). Errors render as
isolated cards (`WEB PREVIEW ERROR … Chat / Files / Editor / AI remain
unaffected.`), JS errors surface as `PREVIEW CONSOLE …`.

## Error handling & performance (spec §18, §21)

Server bind failures, missing engines, bad URLs, broken pages and wedged
browsers each map to an explicit `PreviewState.ERROR` with a useful
message; a single failing page never kills the stack (`restart_engine()`
available); every controller→UI crossing goes through a thread-safe
event queue drained by a 0.2 s interval — zero widget access from
background threads.

---

## Testing (spec §28)

* **NEW** `calc_terminal/test_browser.py` — 25 hermetic tests: real HTTP
  requests against the live server (MIME/index/no-cache/traversal/404/
  clean stop), navigation semantics, entry detection, debounce
  coalescing timing, controller state machine, CSS-hot vs full-reload
  paths, AI-write debounce, error isolation, idempotent shutdown.
* **NEW** `_probe_web_preview.py` — **27/27 end-to-end checks with REAL
  Chromium** through the actual UI: ▷ click → server+browser up → JS
  executed (`javascript-ran` read back from the live page) → images
  loaded → CSS hot-update → 12-write burst coalesced → URL nav + error
  isolation → back → ⟳ → ⿻ fullscreen + exact restore → resize +
  persistence → close-all-tabs keeps preview → ⏻ returns to CODE →
  composer/editor geometry non-overlap → exit leaves nothing running.
* Full regression sweep green: **203 unit tests** + fixes/formats suites
  + 32/32 layout · 12/12 drag · 19/19 empty-state · 17/17 startup ·
  21/21 light-mode · 24/24 goodbye · 12/12 theme-preview · 50/50 palette
  · 13/13 final probes.

## Dependencies

`playwright>=1.40` added to requirements.txt as the (documented)
optional extra powering the preview; CAT runs fully without it and the
preview panel prints the exact install steps when absent.
