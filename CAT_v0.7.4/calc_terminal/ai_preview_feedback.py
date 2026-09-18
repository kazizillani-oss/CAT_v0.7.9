"""
CCT — ai_preview_feedback.py: AI + Web Preview Feedback Loop (v0.7.10 spec #35).

Enables the AI to:
1. See the current preview state (DOM snapshot, console errors)
2. Take screenshots of the preview
3. Interact with the preview (click, type, navigate)
4. Get feedback on changes made

Architecture:
    AI Agent -> FeedbackController -> PreviewController -> BrowserEngine
                                 <- FeedbackController <- PreviewState
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os
import threading
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class PreviewFeedback:
    """Feedback from the preview about the current state."""
    url: str = ""
    title: str = ""
    dom_snapshot: str = ""
    console_errors: List[str] = field(default_factory=list)
    console_logs: List[str] = field(default_factory=list)
    screenshot_path: str = ""
    is_loading: bool = False
    load_error: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class AIAction:
    """An action the AI wants to perform on the preview."""
    action_type: str  # "navigate", "click", "type", "screenshot", "evaluate"
    target: str = ""  # CSS selector, URL, or JS code
    value: str = ""   # Text to type, URL to navigate, etc.
    callback: Optional[callable] = None


class AIPreviewFeedbackController:
    """Controls the AI + Web Preview feedback loop.

    This controller:
    - Monitors preview state and provides feedback to the AI
    - Executes AI actions on the preview
    - Manages the feedback cycle
    """

    def __init__(self, preview_controller=None):
        self.preview_controller = preview_controller
        self._action_queue = []
        self._feedback_history = []
        self._lock = threading.Lock()
        self._max_history = 50

    def get_preview_state(self) -> PreviewFeedback:
        """Get the current state of the preview for AI consumption."""
        feedback = PreviewFeedback()

        if not self.preview_controller:
            feedback.load_error = "No preview controller available"
            return feedback

        try:
            # Get URL and title
            feedback.url = self.preview_controller.url or ""
            if hasattr(self.preview_controller, 'engine'):
                engine = self.preview_controller.engine
                if hasattr(engine, 'current_title'):
                    feedback.title = engine.current_title or ""

            # Get DOM snapshot
            if hasattr(self.preview_controller, 'engine'):
                engine = self.preview_controller.engine
                if hasattr(engine, 'get_snapshot'):
                    snapshot = engine.get_snapshot()
                    if snapshot:
                        feedback.dom_snapshot = getattr(snapshot, 'text', '')

            # Get console errors
            if hasattr(self.preview_controller, 'engine'):
                engine = self.preview_controller.engine
                if hasattr(engine, 'console_errors'):
                    feedback.console_errors = list(engine.console_errors[-10:])

            # Check loading state
            if hasattr(self.preview_controller, 'preview_state'):
                from .browser.state import PreviewState
                feedback.is_loading = (
                    self.preview_controller.preview_state == PreviewState.STARTING
                )

        except Exception as e:
            feedback.load_error = str(e)

        return feedback

    def execute_action(self, action: AIAction) -> bool:
        """Execute an AI action on the preview."""
        if not self.preview_controller:
            return False

        try:
            if action.action_type == "navigate":
                return self._navigate(action.target)
            elif action.action_type == "click":
                return self._click(action.target)
            elif action.action_type == "type":
                return self._type(action.target, action.value)
            elif action.action_type == "screenshot":
                return self._screenshot(action.target)
            elif action.action_type == "evaluate":
                return self._evaluate(action.target)
            else:
                return False
        except Exception:
            return False

    def _navigate(self, url: str) -> bool:
        """Navigate the preview to a URL."""
        if not url.startswith("http"):
            # Relative URL - make absolute
            base = self.preview_controller.base_url or ""
            url = base.rstrip("/") + "/" + url.lstrip("/")
        self.preview_controller.navigate(url)
        return True

    def _click(self, selector: str) -> bool:
        """Click an element in the preview."""
        if hasattr(self.preview_controller, 'engine'):
            engine = self.preview_controller.engine
            if hasattr(engine, 'click'):
                engine.click(selector)
                return True
        return False

    def _type(self, selector: str, text: str) -> bool:
        """Type text into an element in the preview."""
        if hasattr(self.preview_controller, 'engine'):
            engine = self.preview_controller.engine
            if hasattr(engine, 'type'):
                engine.type(selector, text)
                return True
        return False

    def _screenshot(self, path: str) -> bool:
        """Take a screenshot of the preview."""
        if hasattr(self.preview_controller, 'engine'):
            engine = self.preview_controller.engine
            if hasattr(engine, 'screenshot'):
                engine.screenshot(path)
                return True
        return False

    def _evaluate(self, js_code: str) -> bool:
        """Evaluate JavaScript in the preview."""
        if hasattr(self.preview_controller, 'engine'):
            engine = self.preview_controller.engine
            if hasattr(engine, 'evaluate'):
                engine.evaluate(js_code)
                return True
        return False

    def record_feedback(self, feedback: PreviewFeedback):
        """Record feedback for history."""
        with self._lock:
            self._feedback_history.append(feedback)
            if len(self._feedback_history) > self._max_history:
                self._feedback_history = self._feedback_history[-self._max_history:]

    def get_feedback_summary(self) -> str:
        """Get a summary of recent feedback for AI consumption."""
        with self._lock:
            if not self._feedback_history:
                return "No preview feedback available."

            recent = self._feedback_history[-5:]  # Last 5 feedback items
            summary = []
            for fb in recent:
                if fb.url:
                    summary.append(f"URL: {fb.url}")
                if fb.title:
                    summary.append(f"Title: {fb.title}")
                if fb.console_errors:
                    summary.append(f"Console errors: {len(fb.console_errors)}")
                if fb.load_error:
                    summary.append(f"Error: {fb.load_error}")

            return "\n".join(summary) if summary else "Preview state unknown."


# Global instance
_ai_feedback_controller = None


def get_ai_feedback_controller(preview_controller=None) -> AIPreviewFeedbackController:
    """Get or create the global AI feedback controller."""
    global _ai_feedback_controller
    if _ai_feedback_controller is None:
        _ai_feedback_controller = AIPreviewFeedbackController(preview_controller)
    elif preview_controller and _ai_feedback_controller.preview_controller is None:
        _ai_feedback_controller.preview_controller = preview_controller
    return _ai_feedback_controller
