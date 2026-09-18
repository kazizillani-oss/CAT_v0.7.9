"""Quick live smoke test for the browser subsystem (dev only)."""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from calc_terminal.browser import PreviewController  # noqa: E402

root = tempfile.mkdtemp(prefix="cat_site_")
with open(os.path.join(root, "index.html"), "w", encoding="utf-8") as f:
    f.write('<html><head><link rel="stylesheet" href="style.css"></head>'
            '<body><h1>CAT Live</h1><p id="p">before</p>'
            '<script>document.getElementById("p").textContent = "js-ran";'
            "</script></body></html>")
with open(os.path.join(root, "style.css"), "w", encoding="utf-8") as f:
    f.write("body{background:#123;color:#fff} h1{color:lime}")

ctrl = PreviewController(root)
events = []
ctrl.on_event = lambda kind, **kw: events.append((kind, kw.get("text", "") or kw.get("state", "")))
ok = ctrl.start_for_file(os.path.join(root, "index.html"))
print("start ok:", ok, "| state:", ctrl.preview_state, "| url:", ctrl.url)
assert ok and ctrl.url.startswith("http://127.0.0.1:")

snap = ctrl.engine.reload()
print("title:", repr(snap.title), "| elements:", snap.elements,
      "| status:", snap.status_code)
assert any("CAT Live" in l for l in snap.outline_lines), list(snap.outline_lines)
assert any("js-ran" in l for l in snap.outline_lines), list(snap.outline_lines)

# CSS-only hot path
with open(os.path.join(root, "style.css"), "a", encoding="utf-8") as f:
    f.write("\nh1{letter-spacing:2px}")
ctrl.on_files_changed([os.path.join(root, "style.css")])
time.sleep(0.8)

# AI-write full reload path (debounced ~150 ms → one update)
with open(os.path.join(root, "index.html"), "a", encoding="utf-8") as f:
    f.write("\n<!-- ai edit -->")
ctrl.notify_ai_wrote(os.path.join(root, "index.html"))
time.sleep(0.8)

acts = [t for kind, t in events if kind == "activity"]
print("activity sample:", acts[:6])
assert any("Writing index.html" in a for a in acts), acts
assert any("Preview synchronized" in a or "CSS updated" in a for a in acts), acts

# navigation history
nav = ctrl.history
assert nav.current and nav.can_back() is False  # single entry so far
ctrl.navigate(ctrl.server.url.rstrip("/") + "/missing.html")
assert nav.can_back()
snap3 = ctrl.back()
print("back to:", ctrl.history.current)
ctrl.stop_preview()
assert not ctrl.server.running
assert not ctrl.engine.available
print("LIVE SMOKE TEST PASS")
