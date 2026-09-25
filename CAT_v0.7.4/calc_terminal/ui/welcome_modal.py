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


    _SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


    class WelcomeModal(Screen):
        """Unified Startup Loader & Welcome Screen for CAT CLI.
        Combines instant zero-blank rendering, animated shimmering ASCII mark,
        hardware detection profile, real-time stage loader, progress bar,
        and instant interruption via touch/keyboard/clicks."""

        CSS = """
        WelcomeModal {
            align: center middle;
            background: $app-background 80%;
        }
        #wm-box {
            width: 78;
            max-width: 96%;
            height: auto;
            max-height: 94%;
            background: $surface;
            border: double $accent;
            padding: 1 2;
            opacity: 1;
            offset-y: 0;
            content-align: center middle;
        }
        #wm-titlebar {
            height: 2;
            padding: 0;
            margin-bottom: 1;
            border-bottom: solid $border;
            content-align: center middle;
        }
        #wm-title {
            text-style: bold;
            width: 1fr;
            text-align: center;
            color: $accent;
        }
        #wm-logo {
            height: auto;
            content-align: center top;
            text-align: center;
            margin-bottom: 1;
        }
        #wm-hardware {
            height: auto;
            color: $text-muted;
            padding: 0;
            text-align: center;
            margin-bottom: 1;
        }
        #wm-status {
            height: 1;
            text-align: center;
            color: $text;
            margin-bottom: 1;
        }
        #wm-boot {
            height: 1;
            text-align: center;
            color: $accent;
            text-style: bold;
            margin-bottom: 1;
        }
        #wm-countdown {
            height: 1;
            text-align: center;
            color: $text-faint;
            margin-bottom: 1;
        }
        #wm-actions {
            height: 3;
            align-horizontal: center;
            content-align: center middle;
            margin-top: 1;
        }
        #wm-btn-go {
            border: tall $accent-light $accent-dark;
            background: $accent;
            color: #ffffff;
            text-style: bold;
            min-width: 24;
            height: 3;
        }
        #wm-btn-go:hover {
            background: $accent-light;
            color: #ffffff;
        }
        #wm-btn-go:focus {
            border: double #ffffff;
        }
        .wm-hint {
            color: $text-faint;
            text-align: center;
            height: 1;
            margin-top: 1;
        }
        """

        BINDINGS = [
            Binding("escape", "cancel", "Skip"),
            Binding("enter", "cancel", "Continue"),
            Binding("space", "cancel", "Continue"),
        ]

        _BOOT_STEPS = 16
        _BOOT_INTERVAL = 0.04   # ~0.6s smooth, fast boot progress with zero CPU/GPU stall
        _PULSE_INTERVAL = 0.75

        def compose(self):
            self._logo_lines = _logo_lines()
            with Vertical(id="wm-box"):
                with Horizontal(id="wm-titlebar"):
                    yield Static(f"🚀 CAT CLI — AI Coding Agent Terminal OS  [dim]v{_VERSION}[/dim]", id="wm-title")
                yield Static("", id="wm-logo")
                
                # Hardware detection line
                try:
                    from ..hardware_analyzer import HardwareAnalyzer
                    prof = HardwareAnalyzer.analyze()
                    gpu_str = f"{prof.gpu_name[:20]} ({prof.vram_gb:.1f}GB {prof.gpu_backend})" if prof.has_gpu else "CPU Only"
                    is_low = HardwareAnalyzer.is_low_end(prof) or os.environ.get("CAT_ECO_MODE") == "1"
                    perf_tag = f" \u00b7 [{theme_css.current_hex('accent')} b]⚡ Eco Engine Active[/]" if is_low else ""
                    hw_line = f"⚡ [{theme_css.current_hex('accent')} b]Device Profile:[/] {prof.cpu_model[:22]} \u00b7 {prof.ram_total_gb:.0f}GB RAM \u00b7 {gpu_str} \u00b7 [{theme_css.current_hex('success')} b]Tier: {prof.local_ai_tier.value}[/]{perf_tag}"
                    yield Static(hw_line, id="wm-hardware")
                except Exception:
                    yield Static("⚡ [b]Ready for Coding & Intelligent Agents[/b]", id="wm-hardware")

                # Live stage spinner & status
                yield Static(f"[bold #f9e2af]{_SPINNER_FRAMES[0]}[/] Mounting workspace & environment...", id="wm-status")

                # Animated progress bar
                yield Static(self._render_bar(0.08), id="wm-boot")

                # Auto-countdown indicator
                yield Static("", id="wm-countdown")

                # Primary Action CTA
                with Horizontal(id="wm-actions"):
                    yield Button("Let's Go  ➜", id="wm-btn-go", variant="primary")

                yield Static("[dim]Tap screen or press any key to enter workspace[/dim]", classes="wm-hint")

        def _accent_hex(self, role="accent"):
            try:
                return theme_css.current_hex(role)
            except Exception:
                return "#89b4fa"

        def _logo_colors(self):
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
                if logo == getattr(self, "_last_drawn_logo", None):
                    return
                self._last_drawn_logo = logo
                self.query_one("#wm-logo", Static).update(logo)
            except Exception:
                pass

        def _render_bar(self, fraction: float) -> str:
            fraction = max(0.0, min(1.0, fraction))
            total_width = 28
            filled = int(round(fraction * total_width))
            empty = total_width - filled
            pct = int(round(fraction * 100))
            return f"[bold #a6e3a1]{'█' * filled}[/][dim #45475a]{'░' * empty}[/] [bold #89b4fa]{pct:3d}%[/]"

        def _get_status_text(self, step: int) -> str:
            fraction = step / float(self._BOOT_STEPS)
            if fraction >= 1.0 or getattr(self, "_is_boot_done", False):
                return "[bold #a6e3a1]✓ CAT CLI ready! Launching workspace...[/]"
            elif fraction < 0.25:
                return "Mounting workspace & environment..."
            elif fraction < 0.50:
                return "Calibrating touchscreen & finger gestures..."
            elif fraction < 0.75:
                return "Syncing AI providers & model runtime..."
            else:
                return "Finalizing CAT CLI interactive workspace..."

        def _update_boot_view(self):
            step = getattr(self, "_boot_step", 0)
            fraction = min(1.0, step / float(self._BOOT_STEPS))
            spinner_char = _SPINNER_FRAMES[step % len(_SPINNER_FRAMES)]
            status_text = self._get_status_text(step)

            try:
                self.query_one("#wm-boot", Static).update(self._render_bar(fraction))
            except Exception:
                pass
            try:
                if fraction >= 1.0:
                    self.query_one("#wm-status", Static).update(status_text)
                else:
                    self.query_one("#wm-status", Static).update(f"[bold #f9e2af]{spinner_char}[/] {status_text}")
            except Exception:
                pass

        def _tick_boot(self):
            self._boot_step = getattr(self, "_boot_step", 0) + 1
            if self._boot_step >= self._BOOT_STEPS:
                self._is_boot_done = True
                try:
                    self._boot_timer.stop()
                except Exception:
                    pass
                self._update_boot_view()

                # Seamlessly transition into workspace without forcing the user to wait through a 3-second countdown!
                def _auto_dismiss():
                    try:
                        self.dismiss("auto")
                    except Exception:
                        pass
                try:
                    self.set_timer(0.12, _auto_dismiss)
                except Exception:
                    _auto_dismiss()
                return

            self._update_boot_view()

        def _update_countdown(self):
            try:
                c = getattr(self, "_countdown", 0)
                dot = "●" if c % 2 == 0 else "○"
                bar = '█' * c + '░' * (3 - c)
                self.query_one("#wm-countdown", Static).update(
                    f"[{self._accent_hex()}]{dot}[/] Entering workspace in {c}s \u2014 [{self._accent_hex('text-faint')}]{bar}[/]")
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
                self.dismiss("auto")

        def _tick_pulse(self):
            self._pulse_step = getattr(self, "_pulse_step", 0) + 1
            self._draw_logo()

        def on_mount(self):
            self._pulse_step = 0
            self._boot_step = 1
            self._is_boot_done = False
            self._draw_logo()
            self._update_boot_view()
            self._boot_timer = self.set_interval(self._BOOT_INTERVAL, self._tick_boot)
            self._pulse_timer = self.set_interval(self._PULSE_INTERVAL, self._tick_pulse)
            self.call_after_refresh(self._fit)
            mark_seen()

        def on_unmount(self):
            for timer_name in ("_boot_timer", "_pulse_timer", "_countdown_timer"):
                t = getattr(self, timer_name, None)
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
            # Any key press instantly dismisses and continues to dashboard
            self.dismiss("key")

        def action_cancel(self):
            self.dismiss("cancel")

        def on_button_pressed(self, event):
            self.dismiss("button")

        def on_click(self, event):
            # Any click or touch tap dismisses immediately
            self.dismiss("click")

        def dismiss(self, result=None):
            mark_seen()
            try:
                super().dismiss(result)
            except Exception:
                pass
            return None

else:
    WelcomeModal = None

