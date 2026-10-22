"""
CAT UI — Attachment Intelligence & Vision Modal (v0.8.0).

Interactive modal for:
- Image Preview (dimensions, format, palette, theme)
- AI-Generated Image Authenticity Detection
- Object Detection with toggleable bounding-box overlays
- Local OCR Text Extraction with copyable output
- Multimodal Image Understanding (Local vs Cloud AI)
- Hybrid Analysis Workflows
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

TEXTUAL_AVAILABLE = True
try:
    from textual.screen import Screen
    from textual.containers import Vertical, Horizontal, VerticalScroll, ScrollableContainer
    from textual.widgets import Static, Button, Input, Label
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False

if TEXTUAL_AVAILABLE:
    from . import theme_css
    from ..image_intelligence import (
        get_orchestrator,
        AnalysisMode,
        ProcessingLocation,
        ImageAnalysisResult,
        Visualizer,
    )

    class AttachmentAnalysisModal(Screen):
        """Interactive Attachment Intelligence & Vision Modal."""

        CSS = """
        AttachmentAnalysisModal {
            align: center middle;
            background: $app-background 75%;
        }

        #aim-box {
            width: 86;
            height: auto;
            max-height: 94%;
            background: $surface;
            border-top: tall $surface-highlight;
            border-bottom: tall $surface-dark;
            border-left: tall $surface-highlight;
            border-right: tall $surface-dark;
            padding: 1 2;
            layout: vertical;
        }

        #aim-titlebar {
            height: 3;
            layout: horizontal;
            border-bottom: solid $border;
            margin-bottom: 1;
        }

        #aim-title {
            width: 1fr;
            text-style: bold;
            color: $accent;
        }

        #aim-location-badge {
            width: auto;
            padding: 0 1;
            background: $accent 15%;
            color: $accent;
            text-style: bold;
        }

        #aim-meta-row {
            height: 2;
            color: $text-muted;
            margin-bottom: 1;
        }

        #aim-modes-row {
            height: 3;
            layout: horizontal;
            margin-bottom: 1;
        }

        #aim-modes-row Button {
            margin-right: 1;
            min-width: 14;
            height: 3;
        }

        #aim-modes-row Button.is-active {
            border: round $accent;
            color: $accent;
            text-style: bold;
            background: $accent 20%;
        }

        #aim-preview-box {
            height: auto;
            min-height: 8;
            max-height: 14;
            border: solid $border;
            background: $app-background;
            padding: 1;
            overflow-y: auto;
            margin-bottom: 1;
        }

        #aim-results-scroll {
            height: auto;
            min-height: 8;
            max-height: 16;
            border: solid $border;
            padding: 1;
            overflow-y: auto;
            scrollbar-gutter: stable;
            background: $surface-alt;
            margin-bottom: 1;
        }

        #aim-actions {
            height: 3;
            layout: horizontal;
            border-top: solid $border;
            padding-top: 1;
        }

        #aim-actions Button {
            margin-right: 1;
        }
        """

        BINDINGS = [
            Binding("escape", "dismiss_modal", "Close"),
            Binding("r", "run_analysis", "Run Analysis"),
            Binding("o", "toggle_overlays", "Toggle Overlays"),
        ]

        def __init__(self, attachment, on_remove=None):
            super().__init__()
            self.attachment = attachment
            self.on_remove = on_remove
            self.active_mode = AnalysisMode.HYBRID.value
            self.location = ProcessingLocation.LOCAL.value
            self.show_overlays = True
            self.analysis_result: Optional[ImageAnalysisResult] = getattr(attachment, "analysis", None)

        def compose(self):
            with Vertical(id="aim-box"):
                # Titlebar
                with Horizontal(id="aim-titlebar"):
                    yield Static(f"🐱 Vision Intelligence: {self.attachment.name}", id="aim-title")
                    yield Static(f"[{self.location.upper()}]", id="aim-location-badge")

                # Meta row
                yield Static(
                    f"File: {self.attachment.path}  ·  Kind: {self.attachment.kind.upper()}  ·  "
                    f"Size: {getattr(self.attachment, 'size', 0):,} bytes",
                    id="aim-meta-row"
                )

                # Mode selection buttons
                with Horizontal(id="aim-modes-row"):
                    yield Button("⚡ Hybrid", id="aim-mode-hybrid", classes="is-active cct-btn-sm")
                    yield Button("🛡 AI Detect", id="aim-mode-ai", classes="cct-btn-sm")
                    yield Button("📦 Objects", id="aim-mode-obj", classes="cct-btn-sm")
                    yield Button("📄 OCR Text", id="aim-mode-ocr", classes="cct-btn-sm")
                    yield Button("👁 Describe", id="aim-mode-und", classes="cct-btn-sm")

                # Preview Box (ASCII Overlays when enabled)
                with Vertical(id="aim-preview-box"):
                    yield Static("Loading visual preview...", id="aim-preview-content")

                # Results Scroll
                with VerticalScroll(id="aim-results-scroll"):
                    yield Static("Click 'Run Analysis' to process this image.", id="aim-results-content")

                # Action toolbar
                with Horizontal(id="aim-actions"):
                    yield Button("Run Analysis", id="aim-btn-run", variant="primary", classes="cct-btn-sm")
                    yield Button("Toggle Overlays", id="aim-btn-overlay", classes="cct-btn-sm")
                    yield Button("Toggle Cloud/Local", id="aim-btn-loc", classes="cct-btn-sm")
                    yield Button("Remove Attachment", id="aim-btn-remove", variant="error", classes="cct-btn-sm")
                    yield Button("Close (Esc)", id="aim-btn-close", classes="cct-btn-sm")

        def on_mount(self):
            if self.analysis_result:
                self._update_display(self.analysis_result)
            else:
                self._run_analysis()

        def action_dismiss_modal(self):
            self.dismiss()

        def action_toggle_overlays(self):
            self.show_overlays = not self.show_overlays
            if self.analysis_result:
                self._update_display(self.analysis_result)

        def action_run_analysis(self):
            self._run_analysis()

        def _set_mode(self, mode: str):
            self.active_mode = mode
            for bid in ("aim-mode-hybrid", "aim-mode-ai", "aim-mode-obj", "aim-mode-ocr", "aim-mode-und"):
                try:
                    self.query_one(f"#{bid}", Button).remove_class("is-active")
                except Exception:
                    pass
            active_btn_map = {
                AnalysisMode.HYBRID.value: "aim-mode-hybrid",
                AnalysisMode.AI_DETECTION.value: "aim-mode-ai",
                AnalysisMode.OBJECT_DETECTION.value: "aim-mode-obj",
                AnalysisMode.OCR.value: "aim-mode-ocr",
                AnalysisMode.UNDERSTANDING.value: "aim-mode-und",
            }
            if mode in active_btn_map:
                try:
                    self.query_one(f"#{active_btn_map[mode]}", Button).add_class("is-active")
                except Exception:
                    pass
            if self.analysis_result:
                self._update_display(self.analysis_result)

        def on_button_pressed(self, event: Button.Pressed):
            bid = event.button.id
            if bid == "aim-mode-hybrid":
                self._set_mode(AnalysisMode.HYBRID.value)
            elif bid == "aim-mode-ai":
                self._set_mode(AnalysisMode.AI_DETECTION.value)
            elif bid == "aim-mode-obj":
                self._set_mode(AnalysisMode.OBJECT_DETECTION.value)
            elif bid == "aim-mode-ocr":
                self._set_mode(AnalysisMode.OCR.value)
            elif bid == "aim-mode-und":
                self._set_mode(AnalysisMode.UNDERSTANDING.value)
            elif bid == "aim-btn-run":
                self._run_analysis()
            elif bid == "aim-btn-overlay":
                self.action_toggle_overlays()
            elif bid == "aim-btn-loc":
                self.location = ProcessingLocation.CLOUD.value if self.location == ProcessingLocation.LOCAL.value else ProcessingLocation.LOCAL.value
                try:
                    self.query_one("#aim-location-badge", Static).update(f"[{self.location.upper()}]")
                except Exception:
                    pass
            elif bid == "aim-btn-remove":
                if self.on_remove:
                    self.on_remove(self.attachment.id)
                self.dismiss("removed")
            elif bid == "aim-btn-close":
                self.dismiss()

        def _run_analysis(self):
            try:
                self.query_one("#aim-results-content", Static).update(
                    f"[b cyan]Running {self.active_mode.upper()} ({self.location.upper()})...[/]"
                )
            except Exception:
                pass
            self.run_worker(self._async_analysis(), group="vision")

        async def _async_analysis(self):
            import asyncio
            orch = get_orchestrator()
            modes = [self.active_mode] if self.active_mode != AnalysisMode.HYBRID.value else ["hybrid"]
            res = await asyncio.to_thread(
                orch.analyze_sync,
                self.attachment.path,
                modes=modes,
                location=self.location
            )
            self.analysis_result = res
            self.attachment.analysis = res
            self._update_display(res)

        def _update_display(self, res: ImageAnalysisResult):
            # 1. Update Preview Canvas
            preview_lines = [
                f"Image: {res.width}×{res.height} px · Format: {res.format} · Time: {res.total_time_ms:.1f}ms"
            ]
            if res.detection and res.detection.objects and self.show_overlays:
                overlay_grid = Visualizer.render_ascii_overlay(res.detection.objects, width=64, height=10)
                preview_lines.append("\n" + overlay_grid)
            elif not self.show_overlays:
                preview_lines.append("\n(Bounding box overlays hidden - click 'Toggle Overlays' to show)")
            try:
                self.query_one("#aim-preview-content", Static).update("\n".join(preview_lines))
            except Exception:
                pass

            # 2. Update Results Panel
            formatted = Visualizer.format_terminal_card(res, show_overlays=self.show_overlays)
            try:
                self.query_one("#aim-results-content", Static).update(formatted)
            except Exception:
                pass
else:
    class AttachmentAnalysisModal:
        pass
