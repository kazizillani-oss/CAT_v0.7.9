"""
CCT UI — WelcomeModal (v0.7.8.61 rebuild: ASCII CCT identity).

A one-time, dismissible welcome screen shown on first launch of each
version. v0.7.8.61 changes:

  * the CCT ASCII logo (the same box-drawing "CCT" mark the main app
    shows on launch) is the hero — color-pulsed between the active
    mode's gradient stops;
  * a short staged boot animation plays on mount ("Initializing CCT…
    ██░░" progress bar → "✓ CCT ready") and is interruptible — any
    key, click, or button press dismisses immediately;
  * the highlights list is kept honest (only features this build
    actually shipped) and scrolls when the terminal is short;
  * "Let's Go  →" is the primary call-to-action.

Shown at most once per version: a tiny marker file (~/.cct_welcome_seen)
remembers the last version the user dismisses. Dismissing marks today's
version; reopening mid-version is possible from the Main Menu's
Dashboard without re-flagging anything.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Vertical, Horizontal
    from textual.screen import Screen
    from textual.widgets import Static, Button
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False

_MARKER = os.path.join(os.path.expanduser("~"), ".cct_welcome_seen")


def _version():
    """The welcome marker is keyed to the app's real version so a new
    build automatically shows its once-per-version notice — the old
    hardcoded '0.7.8.45' here could drift out of sync with
    calc_terminal/app.py.VERSION (which is exactly the 'welcome screen
    appears every launch' failure mode: marker written for 0.7.8.45
    while the app reports a higher version, so has_seen_version()
    never matched)."""
    try:
        from .. import app as _backend_app
        v = getattr(_backend_app, "VERSION", None)
        if v:
            return v
    except Exception:
        pass
    return "0.7.9.0"


_VERSION = _version()
def _safe_int(s):
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0

_VERSION_TUPLE = tuple(_safe_int(p) for p in _VERSION.split("."))

_HIGHLIGHTS = ()


def has_seen_version() -> bool:
    try:
        if os.path.exists(_MARKER):
            with open(_MARKER, "r", encoding="utf-8") as f:
                seen = f.read().strip()
            return tuple(int(p) for p in seen.split(".")) >= _VERSION_TUPLE
    except Exception:
        pass
    return False


def mark_seen():
    try:
        with open(_MARKER, "w", encoding="utf-8") as f:
            f.write(_VERSION)
    except Exception:
        pass


if TEXTUAL_AVAILABLE:
    from . import theme_css


    def _logo_lines():
        """The app's own ASCII CCT mark (same source the dashboard and
        the conversation welcome banner use). Imported lazily — the
        backend app module is heavy and must not load at ui import."""
        try:
            from ..app import LOGO
            if LOGO:
                return list(LOGO)
        except Exception:
            pass
        try:
            from ..model import CCT_LOGO
            if CCT_LOGO:
                return list(CCT_LOGO)
        except Exception:
            pass
        return ["CAT"]


    class WelcomeModal(Screen):
        """Once-per-version welcome dialog. Displays the CCT ASCII mark,
        a brief interruptible boot animation, version highlights, and a
        call-to-action. Dismissing any way marks the version seen."""

        CSS = """
        WelcomeModal { align: center middle; background: $app-background 70%; }
        #wm-box {
            width: 82; height: auto; max-height: 94%;
            background: $surface; border: tall $border-active $border; padding: 0 2;
            opacity: 0; offset-y: 1;
            transition: opacity 150ms, offset 180ms;
        }
        #wm-box.open { opacity: 1; offset-y: 0; }
        #wm-titlebar { height: 3; padding: 1 0 0 0; border-bottom: solid $border; }
        #wm-title { text-style: bold; width: 1fr; }
        #wm-logo { height: auto; content-align: center top; padding-top: 1; }
        #wm-boot { height: 2; padding: 1 0 0 0; }
        #wm-countdown { height: 1; text-align: center; color: $text-faint; }
        #wm-subtitle { color: $text-muted; height: 2; padding-top: 1; }
        #wm-hardware { height: 2; color: $text-muted; padding: 0; }
        .wm-h2 { color: $text-faint; height: 2; padding: 1 0 0 0; }
        #wm-body { height: auto; padding-bottom: 1; overflow-y: auto;
                   scrollbar-gutter: stable; scrollbar-size-vertical: 1;
                   scrollbar-size-horizontal: 0; scrollbar-color: $border $surface; }
        .wm-row { height: 3; color: $text-muted; }
        .wm-icon { width: 4; }
        .wm-name { text-style: bold; width: 16; }
        #wm-actions { height: 5; padding: 1 0 1 0; border-top: solid $border;
                      align-horizontal: center; }
        #wm-actions Button {
            border: tall #c4b5fd #4c1d95;
            background: #7c3aed;
            color: #ffffff;
            text-style: bold;
            min-width: 22;
        }
        #wm-actions Button:hover {
            border: tall #ddd6fe #5b21b6;
            background: #8b5cf6;
        }
        #wm-actions Button.-active {
            border: tall #4c1d95 #c4b5fd;
            offset-y: 1;
        }
        .wm-hint { color: $text-faint; padding-top: 1; height: 2; }
        """

        BINDINGS = [Binding("escape", "cancel", "Close")]

        _BOOT_STEPS = 14
        _BOOT_INTERVAL = 0.09   # ~1.3s total
        _PULSE_INTERVAL = 0.65

        def compose(self):
            self._logo_lines = _logo_lines()
            with Vertical(id="wm-box"):
                with Horizontal(id="wm-titlebar"):
                    yield Static(f"\U0001f680  Welcome to CAT v{_VERSION}", id="wm-title")
                yield Static("", id="wm-logo")
                yield Static("", id="wm-boot")
                yield Static("", id="wm-countdown")
                yield Static("Creator: Kazi Zillani \u00b7 Coding \u00b7 Agents \u00b7 Intelligence \u2014 the terminal for builders.",
                             id="wm-subtitle")
                try:
                    from ..hardware_analyzer import HardwareAnalyzer
                    prof = HardwareAnalyzer.analyze()
                    gpu_str = f"{prof.gpu_name[:22]} ({prof.vram_gb:.1f}GB {prof.gpu_backend})" if prof.has_gpu else "CPU"
                    hw_line = f"⚡ [{theme_css.current_hex('accent')} b]Device Profile:[/] {prof.cpu_model[:26]} \u00b7 {prof.ram_total_gb:.0f}GB RAM \u00b7 {gpu_str} \u00b7 [{theme_css.current_hex('success')} b]Tier: {prof.local_ai_tier.value}[/]"
                    yield Static(hw_line, id="wm-hardware")
                except Exception:
                    pass
                if _HIGHLIGHTS:
                    yield Static("What's new in this build:", classes="wm-h2")
                    with Vertical(id="wm-body"):
                        for icon, name, desc in _HIGHLIGHTS:
                            yield Static(
                                f"[{theme_css.current_hex('accent')}]{icon}[/] "
                                f"[{theme_css.current_hex('text')}]{name}[/]  \u00b7  {desc}",
                                classes="wm-row")
                yield Static("Auto-continuing to Dashboard — press Esc/Enter to skip",
                             classes="wm-hint")

        def _accent_hex(self, role="accent"):
            try:
                return theme_css.current_hex(role)
            except Exception:
                return "#888888"

        def _logo_colors(self):
            """Alternating gradient stops give the logo a slow
            shimmer; the boot bar uses the flat accent."""
            try:
                start, end = theme_css.gradient_hex()
            except Exception:
                start = end = self._accent_hex()
            if getattr(self, "_pulse_step", 0) % 2 == 0:
                return start, end
            return end, start

        def _draw_logo(self):
            start, _end = self._logo_colors()
            try:
                logo = "\n".join(f"[{start} b]{line}[/]" for line in self._logo_lines)
                self.query_one("#wm-logo", Static).update(logo)
            except Exception:
                pass

        def _update_boot(self):
            filled = getattr(self, "_boot_step", 0)
            bar = "\u2588" * filled + "\u2591" * (self._BOOT_STEPS - filled)
            try:
                self.query_one("#wm-boot", Static).update(
                    f"[{self._accent_hex()} b]Initializing CAT\u2026[/]  {bar}")
            except Exception:
                pass

        def _tick_boot(self):
            self._boot_step = getattr(self, "_boot_step", 0) + 1
            if self._boot_step >= self._BOOT_STEPS:
                try:
                    self._boot_timer.stop()
                except Exception:
                    pass
                try:
                    self.query_one("#wm-boot", Static).update(
                        f"[{self._accent_hex()} b]\u2713 CAT ready[/]"
                        f"  [{self._accent_hex('text-faint')}]Opening "
                        f"Dashboard\u2026[/]")
                except Exception:
                    pass
                # Animated countdown to close (shows time remaining)
                self._countdown = 5
                self._update_countdown()
                try:
                    self._countdown_timer = self.set_interval(1.0, self._tick_countdown)
                except Exception:
                    pass
                self.set_timer(5.0, self._auto_continue)
                return
            self._update_boot()

        def _update_countdown(self):
            try:
                c = getattr(self, "_countdown", 0)
                # Pulsing dot animation + time
                dot = "●" if c % 2 == 0 else "○"
                self.query_one("#wm-countdown", Static).update(
                    f"[{self._accent_hex()}]{dot}[/] Closing in {c}s — press Esc to stay \u2026 [{self._accent_hex('text-faint')}]{'█' * c + '░' * (5 - c)}[/]")
            except Exception:
                pass

        def _tick_countdown(self):
            c = getattr(self, "_countdown", 0) - 1
            self._countdown = max(0, c)
            self._update_countdown()
            if c <= 0:
                try:
                    self._countdown_timer.stop()
                except Exception:
                    pass

        def _auto_continue(self):
            try:
                if self.is_running:
                    self.dismiss("auto")
            except Exception:
                pass

        def _tick_pulse(self):
            self._pulse_step = getattr(self, "_pulse_step", 0) + 1
            self._draw_logo()

        def on_mount(self):
            self.call_after_refresh(lambda: self.query_one("#wm-box").add_class("open"))
            self.call_after_refresh(self._fit)
            self._pulse_step = 0
            self._boot_step = 0
            self._draw_logo()
            self._update_boot()
            self._boot_timer = self.set_interval(self._BOOT_INTERVAL, self._tick_boot)
            self._pulse_timer = self.set_interval(self._PULSE_INTERVAL, self._tick_pulse)
            # v0.7.8.65: mark the version as seen the moment the modal is
            # SHOWN, not only when it is dismissed. Quitting the app with
            # Ctrl+Q (or closing the terminal) while the modal was up used
            # to skip the dismiss handler, so the marker was never written
            # and the welcome screen reappeared on every single launch.
            mark_seen()

        def on_unmount(self):
            for timer in ("_boot_timer", "_pulse_timer", "_countdown_timer"):
                t = getattr(self, timer, None)
                if t is not None:
                    try:
                        t.stop()
                    except Exception:
                        pass

        def on_resize(self, event):
            self._fit()

        def _fit(self):
            try:
                self.call_after_refresh(
                    lambda: theme_css.fit_dialog(self, "wm-box", "wm-body"))
            except Exception:
                pass

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

        def action_cancel(self):
            self.dismiss(None)

        def on_button_pressed(self, event):
            self.dismiss(None)

        def on_click(self, event):
            if getattr(event, "widget", None) in (self, None):
                self.dismiss(None)

        def dismiss(self, result=None):
            """Any dismissal counts as 'seen this version' — the modal
            is a once-per-version notice, not a persistent dialog."""
            mark_seen()
            return super().dismiss(result)

else:
    WelcomeModal = None
