"""CAT Model Center — Native Ollama & Local/Cloud AI Model Manager.
Creator: Kazi Zillani (CAT Platform).

Features:
- Curated authentic models & dynamic local discovery
- Deep Hardware Analyzer integration (CPU, RAM, GPU VRAM, CUDA/ROCm/Metal)
- Model Compatibility Engine with 5 standard tiers:
  🟢 Excellent, 🟢 Recommended, 🟡 Usable, 🟠 Heavy, 🔴 Not Recommended
- CAT Benchmark System integration with transparent source attribution
- Category filtering: All, Popular, Coding, Reasoning, Vision, Small, Large, Installed
- Memory footprint visualizer (Weights, KV-Cache, VRAM usage, System RAM offload, TPS)
- Full action controls: Download, Run/Select, Remove, Benchmark
"""

if __name__ == "__main__":
    import sys
    sys.exit(1)

import time
import threading
from typing import Optional, Dict, Any, List

TEXTUAL_AVAILABLE = True
try:
    from textual.screen import Screen
    from textual.containers import Vertical, Horizontal, ScrollableContainer
    from textual.widgets import Static, Button, Input, Label
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False

if TEXTUAL_AVAILABLE:
    try:
        from ..ollama_catalog import all_models, search_models, get_model, categories as get_categories
        from ..hardware_analyzer import HardwareAnalyzer
        from ..compatibility_engine import ModelCompatibilityEngine
        from ..benchmark_system import CATBenchmarkSystem
        from ..ollama_download import (
            installed_models, pull_model, delete_model,
            estimate_minutes, is_ollama_running, ensure_ollama_running
        )
        from .. import config as cct_config
        from ..providers import provider_manager as pm
    except Exception:
        all_models = search_models = get_model = get_categories = None
        HardwareAnalyzer = ModelCompatibilityEngine = CATBenchmarkSystem = None
        installed_models = pull_model = delete_model = None
        estimate_minutes = is_ollama_running = ensure_ollama_running = None
        cct_config = pm = None

    try:
        from . import theme_css
    except Exception:
        theme_css = None

    _CATEGORIES = ["all", "popular", "coding", "reasoning", "vision", "small", "large", "installed"]

    def _hex(role):
        if theme_css:
            try:
                return theme_css.current_hex(role)
            except Exception:
                pass
        return "#888888"

    class _ModelRow(Horizontal):
        def __init__(self, m: Dict[str, Any], compat: Any, installed: bool = False):
            super().__init__(classes="ollama-row")
            self.m = m
            self.compat = compat
            self.installed = installed

        def compose(self):
            m = self.m
            inst_tag = "[✓]" if self.installed else "○"
            # Model name & tag
            yield Static(f"{inst_tag} {m['name']}", classes="ollama-name")
            yield Static(str(m.get("params", "?")), classes="ollama-params")
            yield Static(f"{m.get('size_gb', 0):.1f}G", classes="ollama-size")
            
            # Compatibility tier badge
            tier = getattr(self.compat, "tier", "USABLE")
            if tier in ("EXCELLENT", "RECOMMENDED"):
                badge_markup = f"[{_hex('success')}]● {getattr(self.compat, 'tier_label_ascii', '[GOOD]')}[/]"
            elif tier == "USABLE":
                badge_markup = f"[{_hex('warning')}]● {getattr(self.compat, 'tier_label_ascii', '[USABLE]')}[/]"
            else:
                badge_markup = f"[{_hex('error')}]● {getattr(self.compat, 'tier_label_ascii', '[HEAVY]')}[/]"
                
            yield Static(badge_markup, classes="ollama-compat")

    class OllamaPanel(Screen):
        """Dedicated CAT Model Center modal screen."""
        CSS = """
        OllamaPanel { align: center middle; background: $app-background 75%; }
        #ollama-box {
            width: 106; max-width: 98%; height: 46; max-height: 90%;
            background: $surface; border: round $border; padding: 0;
            layout: vertical;
        }
        #ollama-titlebar { height: 3; min-height: 3; padding: 0 2; border-bottom: solid $border; }
        #ollama-title { text-style: bold; width: 1fr; }
        #ollama-body { height: 1fr; min-height: 0; layout: horizontal; }
        #ollama-left { width: 62; min-width: 48; height: 100%; border-right: solid $border; layout: vertical; }
        #ollama-search { height: 3; min-height: 3; padding: 0 1; border-bottom: solid $border; }
        #ollama-search Input { width: 1fr; height: 1; background: transparent; border: none; }
        #ollama-filters { height: 3; min-height: 3; padding: 0 1; overflow-x: auto; }
        #ollama-filters Button { margin-right: 1; }
        #ollama-pcspec { height: auto; max-height: 4; padding: 1 1; border-bottom: solid $border; color: $text-faint; font-size: 85%; }
        #ollama-list { height: 1fr; min-height: 0; overflow-y: auto; scrollbar-gutter: stable; }
        .ollama-row { height: 1; min-height: 1; padding: 0 1; }
        .ollama-row:hover { background: $accent 8%; }
        .ollama-row.-selected { background: $accent 18%; color: $accent; }
        .ollama-name { width: 28; height: 1; overflow: hidden; }
        .ollama-params { width: 8; height: 1; color: $text-faint; text-align: center; }
        .ollama-size { width: 8; height: 1; color: $text-faint; text-align: right; }
        .ollama-compat { width: 16; height: 1; text-align: right; }
        #ollama-right { width: 44; min-width: 36; height: 100%; padding: 1 2; overflow-y: auto; }
        #ollama-detail-title { text-style: bold; color: $accent; height: 1; }
        #ollama-detail-desc { color: $text; height: auto; padding: 1 0; }
        #ollama-compat-card { height: auto; padding: 1 0; border-top: solid $border; }
        #ollama-benchmark-card { height: auto; padding: 1 0; border-top: solid $border; }
        #ollama-progress-wrap { height: 5; min-height: 5; padding: 1 0; display: none; }
        #ollama-progress-wrap.show { display: block; }
        #ollama-progress-bar { height: 1; color: $accent; }
        #ollama-progress-text { height: 1; color: $text-faint; text-align: center; }
        #ollama-progress-eta { height: 1; color: $warning; text-align: center; }
        #ollama-actions { height: 3; min-height: 3; padding: 1 0; border-top: solid $border; }
        #ollama-actions Button { margin-right: 1; }
        #ollama-hint { height: 1; color: $text-faint; padding: 0 2; }
        """

        BINDINGS = [Binding("escape", "close", "Close")]

        def __init__(self):
            super().__init__()
            self._catalog = []
            self._installed = set()
            self._filtered = []
            self._selected = None
            self._category = "all"
            self._query = ""
            self._hw = None
            self._engine = None
            self._bench = None
            self._downloading = None
            self._progress = {}
            # Generation counter for the 8s self-rearming installed-
            # models poll: opening the panel N times must not leave N
            # chains polling after close. on_unmount bumps the token so
            # stray chains stop re-arming.
            self._poll_token = 0

        def compose(self):
            with Vertical(id="ollama-box"):
                with Horizontal(id="ollama-titlebar"):
                    yield Static("⬢  CAT Model Center — Native Local AI & Model Platform", id="ollama-title")
                    yield Button("✕", id="ollama-close", classes="cct-popup-close")
                with Horizontal(id="ollama-body"):
                    with Vertical(id="ollama-left"):
                        with Horizontal(id="ollama-search"):
                            yield Input(placeholder="🔍 Search models… (qwen, llama, coding, 3b)", id="ollama-search-input")
                        with Horizontal(id="ollama-filters"):
                            for cat in _CATEGORIES:
                                yield Button(cat.title(), id=f"ollama-cat-{cat}", classes="cct-btn cct-btn-sm")
                        yield Static("Hardware Analyzer: Profiling system…", id="ollama-pcspec")
                        yield ScrollableContainer(id="ollama-list")
                    with Vertical(id="ollama-right"):
                        yield Static("Select a model", id="ollama-detail-title")
                        yield Static("Explore curated and dynamic models. Hardware badges reflect live device compatibility.", id="ollama-detail-desc")
                        yield Static("", id="ollama-compat-card")
                        yield Static("", id="ollama-benchmark-card")
                        with Vertical(id="ollama-progress-wrap"):
                            yield Static("", id="ollama-progress-bar")
                            yield Static("", id="ollama-progress-text")
                            yield Static("", id="ollama-progress-eta")
                        with Horizontal(id="ollama-actions"):
                            yield Button("⬇ Download", id="ollama-download", variant="primary", classes="cct-btn cct-btn-sm")
                            yield Button("▶ Run", id="ollama-use", classes="cct-btn cct-btn-sm")
                            yield Button("🗑 Remove", id="ollama-remove", classes="cct-btn cct-btn-sm")
                            yield Button("⚡ Bench", id="ollama-bench", classes="cct-btn cct-btn-sm")
                yield Static("Enter: run/select • Click: inspect • Esc: close", id="ollama-hint")

        def on_mount(self):
            self._init_systems()
            self._load_catalog()
            self.call_after_refresh(self._refresh_pcspec)
            self.call_after_refresh(self._refresh_list)
            self.call_after_refresh(self._poll_installed)

        def _init_systems(self):
            try:
                if HardwareAnalyzer:
                    self._hw = HardwareAnalyzer.analyze()
                if ModelCompatibilityEngine and self._hw:
                    self._engine = ModelCompatibilityEngine(hw=self._hw)
                if CATBenchmarkSystem:
                    self._bench = CATBenchmarkSystem()
            except Exception:
                pass

        def _load_catalog(self):
            try:
                self._catalog = all_models(include_dynamic=True) if all_models else []
            except Exception:
                self._catalog = []
            try:
                self._installed = set(installed_models()) if installed_models else set()
            except Exception:
                self._installed = set()
            self._filtered = list(self._catalog)

        def _refresh_pcspec(self):
            try:
                if self._hw:
                    cpu_txt = f"{self._hw.cpu_model} ({self._hw.cpu_threads}T)"
                    ram_txt = f"{self._hw.ram_total_gb:.1f}GB RAM"
                    gpu_txt = f"{self._hw.gpu_name} ({self._hw.vram_gb:.1f}GB VRAM via {self._hw.gpu_backend})" if self._hw.has_gpu else "CPU Only"
                    tier_txt = self._hw.local_ai_tier.value
                    txt = f"⚡ Device Profile: {gpu_txt} • {ram_txt} • {cpu_txt} • Tier: {tier_txt}"
                else:
                    txt = "⚡ Hardware profile unavailable"
                self.query_one("#ollama-pcspec", Static).update(txt)
            except Exception:
                pass

        def on_unmount(self):
            # Invalidate the poll chain: the in-flight callback (if
            # any) will see a stale token and stop re-arming.
            try:
                self._poll_token = getattr(self, "_poll_token", 0) + 1
            except Exception:
                pass

        def _poll_installed(self):
            token = getattr(self, "_poll_token", 0)
            try:
                if not self.is_running:
                    return
            except Exception:
                pass
            try:
                if installed_models:
                    self._installed = set(installed_models())
            except Exception:
                pass
            try:
                if getattr(self, "_poll_token", 0) != token:
                    return
                self.set_timer(8, self._poll_installed)
            except Exception:
                pass

        def _refresh_list(self):
            try:
                cont = self.query_one("#ollama-list", ScrollableContainer)
                cont.remove_children()
            except Exception:
                return

            q = self._query.lower().strip()
            cat = self._category.lower()

            filtered = []
            for m in self._catalog:
                is_inst = m["name"] in self._installed
                if cat == "installed" and not is_inst:
                    continue
                if cat not in ("all", "installed"):
                    m_cats = [c.lower() for c in m.get("categories", [])]
                    if cat not in m_cats and cat not in m.get("caps", []) and cat != m.get("family"):
                        continue
                if q:
                    n_match = q in m.get("name", "").lower()
                    d_match = q in m.get("desc", "").lower()
                    f_match = q in m.get("family", "").lower()
                    p_match = q in m.get("params", "").lower()
                    if not (n_match or d_match or f_match or p_match):
                        continue
                filtered.append(m)

            # Sort: Installed first, then higher compatibility, then smaller size
            def _sort_key(item):
                inst = item["name"] in self._installed
                compat = self._engine.evaluate(item) if self._engine else None
                tier_rank = {"EXCELLENT": 0, "RECOMMENDED": 1, "USABLE": 2, "HEAVY": 3, "NOT_RECOMMENDED": 4}
                t_val = tier_rank.get(getattr(compat, "tier", "USABLE"), 2)
                return (not inst, t_val, item.get("size_gb", 0))

            filtered.sort(key=_sort_key)
            self._filtered = filtered[:200]

            for m in self._filtered:
                compat = self._engine.evaluate(m) if self._engine else None
                is_inst = m["name"] in self._installed
                row = _ModelRow(m, compat=compat, installed=is_inst)
                if self._selected and self._selected.get("name") == m["name"]:
                    row.add_class("-selected")
                try:
                    cont.mount(row)
                except Exception:
                    pass

            if not self._filtered:
                try:
                    cont.mount(Static("No matching models found. Try another search.", classes="pc-empty-msg"))
                except Exception:
                    pass

        def _show_detail(self, m: Dict[str, Any]):
            self._selected = m
            try:
                name = m["name"]
                self.query_one("#ollama-detail-title", Static).update(
                    f"{name}  •  {m.get('params', '?')} • {m.get('size_gb', 0):.1f}GB"
                )
                self.query_one("#ollama-detail-desc", Static).update(m.get("desc", ""))

                # Compatibility Card
                compat = self._engine.evaluate(m) if self._engine else None
                if compat:
                    c_lines = [
                        f"[b]Device Compatibility: {compat.tier_label_ascii}[/b]",
                        f"  Memory: {compat.total_memory_gb:.1f}GB (Weights: {compat.weights_gb:.1f}GB, KV: {compat.kv_cache_gb:.1f}GB)",
                        f"  VRAM: {compat.vram_used_gb:.1f}GB  •  RAM Offload: {compat.ram_offload_gb:.1f}GB",
                        f"  Speed: ~{compat.estimated_tps:.1f} tps  •  {compat.summary}",
                    ]
                    self.query_one("#ollama-compat-card", Static).update("\n".join(c_lines))
                else:
                    self.query_one("#ollama-compat-card", Static).update("")

                # Benchmark Card
                bench_score = self._bench.get_score_for_model(name) if self._bench else None
                if bench_score:
                    src = bench_score.source.value if hasattr(bench_score.source, "value") else str(bench_score.source)
                    b_lines = [
                        f"[b]CAT Benchmark:[/] Score {bench_score.overall:.1f}/100 [{src}]",
                        f"  Coding: {bench_score.coding:.1f}  •  Reason: {bench_score.reasoning:.1f}  •  Tools: {bench_score.tool_use:.1f}",
                    ]
                    self.query_one("#ollama-benchmark-card", Static).update("\n".join(b_lines))
                else:
                    self.query_one("#ollama-benchmark-card", Static).update(
                        "[dim]No CAT benchmark recorded. Click [Bench] to evaluate.[/dim]"
                    )

                # Buttons
                is_inst = name in self._installed
                dl_btn = self.query_one("#ollama-download", Button)
                use_btn = self.query_one("#ollama-use", Button)
                rm_btn = self.query_one("#ollama-remove", Button)

                if is_inst:
                    dl_btn.label = "✓ Installed"
                    dl_btn.disabled = True
                    use_btn.disabled = False
                    rm_btn.disabled = False
                else:
                    dl_btn.label = "⬇ Download"
                    dl_btn.disabled = False
                    use_btn.disabled = True
                    rm_btn.disabled = True

                self._refresh_list()
            except Exception:
                pass

        def _start_download(self):
            if not self._selected or not pull_model:
                return
            name = self._selected["name"]
            if name in self._installed or self._downloading:
                return

            if ensure_ollama_running:
                ok, emsg = ensure_ollama_running(timeout=6, auto_start=True)
                if not ok:
                    self._show_progress_error(f"Cannot start Ollama: {emsg}")
                    return

            self._downloading = name
            try:
                wrap = self.query_one("#ollama-progress-wrap")
                wrap.add_class("show")
                self.query_one("#ollama-progress-bar", Static).update("⟳ Connecting…")
                self.query_one("#ollama-progress-text", Static).update("0%")
                dl_btn = self.query_one("#ollama-download", Button)
                dl_btn.label = "⏳ Pulling…"
                dl_btn.disabled = True
            except Exception:
                pass

            def on_prog(p):
                def _upd():
                    try:
                        pct = p.get("percent")
                        st = p.get("status", "")
                        speed = p.get("speed")
                        bar_w = 26
                        if pct is not None:
                            filled = int(bar_w * pct / 100)
                            bar = "█" * filled + "░" * (bar_w - filled)
                            self.query_one("#ollama-progress-bar", Static).update(f"[{bar}]")
                            self.query_one("#ollama-progress-text", Static).update(f"{pct}%  {st[:24]}")
                        else:
                            self.query_one("#ollama-progress-bar", Static).update(f"⟳ {st[:28]}")
                        if speed:
                            self.query_one("#ollama-progress-eta", Static).update(f"{speed/1024/1024:.1f} MB/s")
                    except Exception:
                        pass

                try:
                    self.app.call_from_thread(_upd)
                except Exception:
                    _upd()

            def on_done(ok, msg):
                def _done():
                    try:
                        wrap = self.query_one("#ollama-progress-wrap")
                        if ok:
                            wrap.remove_class("show")
                            self._installed.add(name)
                            self._downloading = None
                            self.query_one("#ollama-download", Button).label = "✓ Installed"
                            self.query_one("#ollama-use", Button).disabled = False
                            self.query_one("#ollama-remove", Button).disabled = False
                            self._use_model(name)
                        else:
                            self._show_progress_error(f"Download failed: {msg}")
                            self._downloading = None
                            dl = self.query_one("#ollama-download", Button)
                            dl.label = "⬇ Retry"
                            dl.disabled = False
                        self._refresh_list()
                    except Exception:
                        pass

                try:
                    self.app.call_from_thread(_done)
                except Exception:
                    _done()

            try:
                pull_model(name, on_progress=on_prog, on_done=on_done)
            except Exception as e:
                on_done(False, str(e))

        def _show_progress_error(self, err_text: str):
            try:
                wrap = self.query_one("#ollama-progress-wrap")
                wrap.add_class("show")
                self.query_one("#ollama-progress-bar", Static).update(f"✗ Error")
                self.query_one("#ollama-progress-text", Static).update(err_text[:36])
            except Exception:
                pass

        def _remove_model(self):
            if not self._selected or not delete_model:
                return
            name = self._selected["name"]
            ok, msg = delete_model(name)
            if ok:
                self._installed.discard(name)
                self._show_detail(self._selected)
                self._refresh_list()

        def _run_benchmark(self):
            if not self._selected or not self._bench:
                return
            name = self._selected["name"]
            score = self._bench.run_full_benchmark(name)
            self._show_detail(self._selected)

        def _use_model(self, name: str):
            try:
                if cct_config:
                    cc = cct_config.get_config()
                    cc.default_ai_provider = "ollama"
                    cc.default_model = name
                    cct_config.save_config(cc)

                if pm:
                    cfg = pm.load_config()
                    cfg["provider"] = "ollama"
                    cfg["model"] = name
                    pm.save_config(cfg)

                try:
                    self.app._system_note(f"✓ CAT Model activated: {name}")
                except Exception:
                    pass
                self.dismiss(name)
            except Exception:
                self.dismiss(name)

        def on_button_pressed(self, event):
            bid = event.button.id or ""
            if bid == "ollama-close":
                self.dismiss(None)
            elif bid.startswith("ollama-cat-"):
                self._category = bid.replace("ollama-cat-", "")
                for b in self.query(Button):
                    if b.id and b.id.startswith("ollama-cat-"):
                        b.variant = "primary" if b.id == bid else "default"
                self._refresh_list()
            elif bid == "ollama-download":
                self._start_download()
            elif bid == "ollama-use":
                if self._selected:
                    self._use_model(self._selected["name"])
            elif bid == "ollama-remove":
                self._remove_model()
            elif bid == "ollama-bench":
                self._run_benchmark()

        def on_input_changed(self, event):
            if event.input.id == "ollama-search-input":
                self._query = event.value
                self._refresh_list()

        def on_click(self, event):
            w = getattr(event, "widget", None)
            cur = w
            for _ in range(4):
                if cur is None:
                    break
                if isinstance(cur, _ModelRow):
                    self._show_detail(cur.m)
                    break
                cur = getattr(cur, "parent", None)

        def action_close(self):
            self.dismiss(None)

else:
    OllamaPanel = None
