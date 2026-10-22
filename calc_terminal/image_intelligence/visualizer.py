"""
CAT Image Intelligence — Visualizer & Terminal Overlay Renderer (v0.8.0).

Features:
- Visual bounding-box overlays for image previews in terminal and Textual UI
- Toggleable overlay modes (show/hide detection boxes)
- Unicode/ASCII box-drawing canvas for terminal preview grids
- Color-coded category tags and confidence badges
- Compact, expandable result formatting in CAT/Fatty Cat style
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

from .models import BoundingBox, DetectionResult, ImageAnalysisResult


class Visualizer:
    """Renders visual overlays, ASCII terminal boxes, and formatted cards."""

    @staticmethod
    def render_ascii_overlay(
        boxes: List[BoundingBox],
        width: int = 54,
        height: int = 16,
        show_labels: bool = True
    ) -> str:
        """Draws a clean Unicode grid with bounding box overlays for terminal previews."""
        # Create blank 2D canvas
        canvas = [[" " for _ in range(width)] for _ in range(height)]

        # Draw frame borders
        for x in range(width):
            canvas[0][x] = "·"
            canvas[height - 1][x] = "·"
        for y in range(height):
            canvas[y][0] = "·"
            canvas[y][width - 1] = "·"

        # Overlay bounding boxes
        for i, box in enumerate(boxes):
            # Scale to canvas coordinates
            x1 = max(1, min(width - 2, int(box.xmin * (width - 2)) + 1))
            y1 = max(1, min(height - 2, int(box.ymin * (height - 2)) + 1))
            x2 = max(x1 + 2, min(width - 2, int(box.xmax * (width - 2)) + 1))
            y2 = max(y1 + 1, min(height - 2, int(box.ymax * (height - 2)) + 1))

            # Horizontal box edges
            for x in range(x1, x2 + 1):
                canvas[y1][x] = "─"
                canvas[y2][x] = "─"
            # Vertical box edges
            for y in range(y1, y2 + 1):
                canvas[y][x1] = "│"
                canvas[y][x2] = "│"

            # Box corners
            canvas[y1][x1] = "┌"
            canvas[y1][x2] = "┐"
            canvas[y2][x1] = "└"
            canvas[y2][x2] = "┘"

            # Label on top edge
            if show_labels:
                conf_pct = int(box.confidence * 100)
                label_txt = f"[{box.label} {conf_pct}%]"
                avail_space = max(0, x2 - x1 - 2)
                if avail_space > 0:
                    truncated = label_txt[:avail_space]
                    for idx, ch in enumerate(truncated):
                        canvas[y1][x1 + 1 + idx] = ch

        return "\n".join("".join(row) for row in canvas)

    @staticmethod
    def format_terminal_card(res: ImageAnalysisResult, show_overlays: bool = True) -> str:
        """Format complete analysis into a premium CAT terminal panel."""
        lines = [
            f"  📷 [b cyan]{res.filename}[/] ({res.width}×{res.height} px · {res.format})",
            f"  [dim]Processing: {res.location.upper()} · Time: {res.total_time_ms:.1f}ms[/]",
            ""
        ]

        # Authenticity section
        if res.authenticity:
            prob_pct = int(res.authenticity.ai_probability * 100)
            conf_pct = int(res.authenticity.confidence_score * 100)
            if "AI-Generated" in res.authenticity.prediction:
                pred_color = "#f43f5e"  # Rose red
            elif "Authentic" in res.authenticity.prediction:
                pred_color = "#10b981"  # Emerald green
            else:
                pred_color = "#f59e0b"  # Amber

            lines.append(f"  [b]AI Detection:[/] [{pred_color}]{res.authenticity.prediction}[/]")
            lines.append(f"  [dim]Estimate: {prob_pct}% AI probability · Confidence: {conf_pct}%[/]")
            if res.authenticity.provenance_info.get("generator_metadata"):
                lines.append(f"  [cyan]✓ Provenance:[/] {res.authenticity.provenance_info['generator_metadata']}")
            if res.authenticity.limitations:
                lines.append(f"  [dim italic]Note: {res.authenticity.limitations[0]}[/]")
            lines.append("")

        # Object Detection section
        if res.detection:
            count = res.detection.count
            lines.append(f"  [b]Object Detection:[/] [cyan]{count} object(s) detected[/]")
            if res.detection.objects:
                for obj in res.detection.objects[:6]:
                    pct = int(obj.confidence * 100)
                    lines.append(f"    • [b {obj.color}]{obj.label}[/] [dim]({pct}% conf) [{obj.ymin:.2f}, {obj.xmin:.2f}, {obj.ymax:.2f}, {obj.xmax:.2f}][/]")
                if show_overlays:
                    lines.append("")
                    lines.append("  [dim]Detection Bounding Box Overlay:[/]")
                    overlay_str = Visualizer.render_ascii_overlay(res.detection.objects, width=54, height=12)
                    for ol in overlay_str.splitlines():
                        lines.append(f"    [dim cyan]{ol}[/]")
            lines.append("")

        # OCR section
        if res.ocr:
            lines.append(f"  [b]OCR Text Extracted:[/] [dim]({res.ocr.engine} · {res.ocr.word_count} words)[/]")
            if res.ocr.text.strip():
                preview_lines = res.ocr.lines[:8]
                for pl in preview_lines:
                    lines.append(f"    [dim]│[/] {pl}")
                if len(res.ocr.lines) > 8:
                    lines.append(f"    [dim]... and {len(res.ocr.lines) - 8} more lines[/]")
            else:
                lines.append("    [dim italic](No readable text layers detected)[/]")
            lines.append("")

        # Image Understanding section
        if res.understanding and res.understanding.summary:
            cloud_badge = "[#38bdf8]CLOUD AI[/]" if res.understanding.is_cloud else "[#a3e635]LOCAL[/]"
            lines.append(f"  [b]Image Understanding ({cloud_badge}):[/]")
            lines.append(f"  {res.understanding.detailed_analysis or res.understanding.summary}")
            lines.append("")

        return "\n".join(lines)
