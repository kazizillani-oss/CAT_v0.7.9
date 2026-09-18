"""
Browser Capabilities Adapter per §68:
- browser.navigate
- browser.click
- browser.type
- browser.screenshot
- browser.inspect
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from ..schema import (
    AvailabilityStatus,
    Capability,
    CapabilityCategory,
    CapabilitySpec,
    ExecutionResult,
)


def _check_browser_health() -> Tuple[AvailabilityStatus, str]:
    try:
        from ...browser.engine import PLAYWRIGHT_AVAILABLE
        if PLAYWRIGHT_AVAILABLE:
            return AvailabilityStatus.AVAILABLE, "Playwright Chromium engine available"
        return AvailabilityStatus.SOFTWARE_NOT_FOUND, "playwright package not installed (run: pip install playwright && playwright install chromium)"
    except Exception as e:
        return AvailabilityStatus.UNAVAILABLE, str(e)


def _navigate_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    url = args.get("url", "")
    if not url:
        return ExecutionResult(success=False, error="url argument is required")

    try:
        from ...browser.preview import PreviewController
        ctrl = PreviewController.instance() if hasattr(PreviewController, "instance") else None
        if ctrl and ctrl.running:
            res = ctrl.navigate(url)
            return ExecutionResult(success=True, output=f"Navigated to {url}", metadata={"url": url})
        # If preview controller not actively running, check standalone Playwright
        from ...browser.engine import BrowserEngine
        engine = BrowserEngine(headless=True)
        engine.start()
        snap = engine.navigate(url)
        engine.stop()
        return ExecutionResult(
            success=True,
            output=f"Successfully loaded {snap.url} (HTTP {snap.status_code}) - Title: '{snap.title}'",
            metadata={"title": snap.title, "url": snap.url, "status_code": snap.status_code},
        )
    except Exception as e:
        return ExecutionResult(success=False, error=f"Navigation failed: {e}")


def _click_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    target = args.get("target") or args.get("selector", "")
    if not target:
        return ExecutionResult(success=False, error="target or selector argument is required")

    try:
        from ...browser.preview import PreviewController
        ctrl = PreviewController.instance() if hasattr(PreviewController, "instance") else None
        if ctrl and ctrl.engine and ctrl.engine.available:
            ok = ctrl.engine.click(target)
            return ExecutionResult(success=ok, output=f"Clicked element '{target}'" if ok else f"Could not find element '{target}'")
        return ExecutionResult(success=False, error="Browser engine is not currently running")
    except Exception as e:
        return ExecutionResult(success=False, error=f"Browser click failed: {e}")


def _type_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    target = args.get("target") or args.get("selector", "")
    text = args.get("text", "")
    if not target:
        return ExecutionResult(success=False, error="target argument is required")

    try:
        from ...browser.preview import PreviewController
        ctrl = PreviewController.instance() if hasattr(PreviewController, "instance") else None
        if ctrl and ctrl.engine and ctrl.engine.available:
            ok = ctrl.engine.type_text(target, text)
            return ExecutionResult(success=ok, output=f"Typed text into '{target}'" if ok else f"Could not type into '{target}'")
        return ExecutionResult(success=False, error="Browser engine is not currently running")
    except Exception as e:
        return ExecutionResult(success=False, error=f"Browser type failed: {e}")


def _screenshot_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    dest = args.get("destination", "screenshot.png")
    dest = os.path.abspath(os.path.expanduser(dest))
    try:
        from ...browser.preview import PreviewController
        ctrl = PreviewController.instance() if hasattr(PreviewController, "instance") else None
        if ctrl and ctrl.engine and ctrl.engine.available:
            snap_path = ctrl.engine.screenshot(dest)
            return ExecutionResult(success=True, output=f"Screenshot saved to {dest}", metadata={"path": dest})
        return ExecutionResult(success=False, error="Browser engine is not running to take screenshot")
    except Exception as e:
        return ExecutionResult(success=False, error=f"Screenshot failed: {e}")


def _inspect_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    try:
        from ...browser.preview import PreviewController
        ctrl = PreviewController.instance() if hasattr(PreviewController, "instance") else None
        if ctrl and ctrl.engine and ctrl.engine.available:
            snap = ctrl.engine.snapshot()
            return ExecutionResult(
                success=True,
                output={
                    "title": snap.title,
                    "url": snap.url,
                    "status_code": snap.status_code,
                    "headings": snap.headings,
                    "links_count": len(snap.links),
                    "buttons_count": len(snap.buttons),
                    "console_errors": snap.js_errors,
                },
                metadata={"title": snap.title, "url": snap.url},
            )
        return ExecutionResult(success=False, error="Browser engine is not currently running")
    except Exception as e:
        return ExecutionResult(success=False, error=f"Inspect failed: {e}")


def register_browser_capabilities(bus):
    bus.register(Capability(
        spec=CapabilitySpec(
            name="browser.navigate",
            version="1.0.0",
            category=CapabilityCategory.BROWSER,
            description="Navigate to a URL using the real embedded Chromium engine.",
            input_schema={"url": "string"},
            output_schema={"output": "string"},
            permissions=["browser_automation"],
            documentation="Loads a webpage in Chromium and waits for network idle.",
        ),
        handler=_navigate_handler,
        health_checker=_check_browser_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="browser.click",
            version="1.0.0",
            category=CapabilityCategory.BROWSER,
            description="Click on an interactive element by selector or visible text.",
            input_schema={"target": "string"},
            output_schema={"output": "string"},
            permissions=["browser_automation"],
            documentation="Clicks an element in the active browser page.",
        ),
        handler=_click_handler,
        health_checker=_check_browser_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="browser.type",
            version="1.0.0",
            category=CapabilityCategory.BROWSER,
            description="Type text into an input field in the active browser page.",
            input_schema={"target": "string", "text": "string"},
            output_schema={"output": "string"},
            permissions=["browser_automation"],
            documentation="Focuses and types into an input/textarea.",
        ),
        handler=_type_handler,
        health_checker=_check_browser_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="browser.screenshot",
            version="1.0.0",
            category=CapabilityCategory.BROWSER,
            description="Capture a screenshot of the current browser page to disk.",
            input_schema={"destination": "string?"},
            output_schema={"output": "string"},
            permissions=["browser_automation"],
            documentation="Saves a PNG screenshot of the viewport.",
        ),
        handler=_screenshot_handler,
        health_checker=_check_browser_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="browser.inspect",
            version="1.0.0",
            category=CapabilityCategory.BROWSER,
            description="Inspect the current page DOM structure, interactive elements, and console errors.",
            input_schema={},
            output_schema={"output": "object"},
            permissions=["browser_automation"],
            documentation="Extracts headings, links, buttons, and console output.",
        ),
        handler=_inspect_handler,
        health_checker=_check_browser_health,
    ))
