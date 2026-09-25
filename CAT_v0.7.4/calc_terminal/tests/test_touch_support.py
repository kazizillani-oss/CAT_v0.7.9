"""Automated test suite for CAT CLI Windows Touchscreen & Touch Interaction Support.

Covers:
- Input capability detection (Win32 API integration, form factor classification, override)
- TouchTapRecognizer (fuzziness/jitter tolerance, down!=up widget recovery, double-tap, long-press)
- TouchScrollHandler (vertical drag threshold, natural drag scroll, click suppression, kinetic flick)
- TouchHitZone (expanded hit margins for narrow resizers)
- TouchFocusManager (focus preservation & restoration)
- GestureBridge integration
- Mouse/keyboard zero-regression guarantees
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from textual import events

from calc_terminal.input.capabilities import (
    InputCapabilities,
    DeviceType,
    detect_capabilities,
    get_input_capabilities,
    set_touch_mode,
    toggle_touch_mode,
)
from calc_terminal.input.touch import (
    TouchTapRecognizer,
    TouchScrollHandler,
    TAP_MAX_DISTANCE,
    LONG_PRESS_DURATION,
)
from calc_terminal.input.pointer import TouchHitZone
from calc_terminal.input.focus import TouchFocusManager
from calc_terminal.input.gestures import GestureBridge


def make_mouse_down(widget, x, y, button=1):
    return events.MouseDown(
        widget=widget,
        x=x,
        y=y,
        delta_x=0,
        delta_y=0,
        button=button,
        shift=False,
        meta=False,
        ctrl=False,
        screen_x=x,
        screen_y=y,
    )


def make_mouse_move(widget, x, y, delta_x=0, delta_y=0, button=1):
    return events.MouseMove(
        widget=widget,
        x=x,
        y=y,
        delta_x=delta_x,
        delta_y=delta_y,
        button=button,
        shift=False,
        meta=False,
        ctrl=False,
        screen_x=x,
        screen_y=y,
    )


def make_mouse_up(widget, x, y, button=1):
    return events.MouseUp(
        widget=widget,
        x=x,
        y=y,
        delta_x=0,
        delta_y=0,
        button=button,
        shift=False,
        meta=False,
        ctrl=False,
        screen_x=x,
        screen_y=y,
    )


class TestInputCapabilities(unittest.TestCase):
    """Test suite for hardware & input capability detection."""

    def test_detection_returns_capabilities_instance(self):
        caps = detect_capabilities()
        self.assertIsInstance(caps, InputCapabilities)
        self.assertIsInstance(caps.touchscreen_available, bool)
        self.assertIsInstance(caps.device_type, DeviceType)
        self.assertIsInstance(caps.touch_mode_enabled, bool)

    def test_mock_win32_touchscreen_detected(self):
        """Simulate a Windows 2-in-1 touchscreen with 10 touch points."""
        with patch("sys.platform", "win32"), \
             patch("calc_terminal.input.capabilities.os.environ.get", return_value=""), \
             patch("calc_terminal.input.capabilities._read_config_touch_mode", return_value=None):
            
            mock_user32 = MagicMock()
            def side_effect(n):
                if n == 94:  # SM_DIGITIZER
                    return 0x00000080 | 0x00000001 | 0x00000040  # Ready + Integrated + Multi
                elif n == 95:  # SM_MAXIMUMTOUCHES
                    return 10
                elif n == 86:  # SM_TABLETPC
                    return 1
                elif n == 19:  # SM_MOUSEPRESENT
                    return 1
                elif n == 0x2003:  # SM_CONVERTIBLESLATEMODE (laptop mode)
                    return 0
                return 0

            mock_user32.GetSystemMetrics.side_effect = side_effect
            mock_user32.GetDpiForSystem.return_value = 96

            with patch("ctypes.windll.user32", mock_user32):
                caps = detect_capabilities()

                self.assertTrue(caps.touchscreen_available)
                self.assertEqual(caps.max_touch_points, 10)
                self.assertEqual(caps.device_type, DeviceType.CONVERTIBLE_2IN1)
                self.assertTrue(caps.touch_mode_enabled)

    def test_mock_desktop_no_touch(self):
        """Simulate a traditional desktop PC with only mouse and keyboard."""
        with patch("sys.platform", "win32"), \
             patch("calc_terminal.input.capabilities.os.environ.get", return_value=""), \
             patch("calc_terminal.input.capabilities._read_config_touch_mode", return_value=None):
            
            mock_user32 = MagicMock()
            def side_effect(n):
                if n == 94:  # SM_DIGITIZER
                    return 0
                elif n == 95:  # SM_MAXIMUMTOUCHES
                    return 0
                elif n == 86:  # SM_TABLETPC
                    return 0
                elif n == 19:  # SM_MOUSEPRESENT
                    return 1
                return 0

            mock_user32.GetSystemMetrics.side_effect = side_effect
            mock_user32.GetDpiForSystem.return_value = 96

            with patch("ctypes.windll.user32", mock_user32):
                caps = detect_capabilities()

                self.assertFalse(caps.touchscreen_available)
                self.assertEqual(caps.max_touch_points, 0)
                self.assertEqual(caps.device_type, DeviceType.DESKTOP)
                self.assertFalse(caps.touch_mode_enabled)

    def test_manual_set_and_toggle_touch_mode(self):
        """Verify that user can force touch mode on or off via set_touch_mode / toggle_touch_mode."""
        set_touch_mode(True, persist=False)
        caps = get_input_capabilities()
        self.assertTrue(caps.touch_mode_enabled)

        toggle_touch_mode(persist=False)
        caps = get_input_capabilities()
        self.assertFalse(caps.touch_mode_enabled)

        set_touch_mode(True, persist=False)
        self.assertTrue(get_input_capabilities().touch_mode_enabled)


class TestTouchTapRecognizer(unittest.TestCase):
    """Test suite for touch tap recognition, jitter tolerance, and double/long press."""

    def setUp(self):
        self.taps_recorded = []
        self.long_presses_recorded = []

        def on_tap(widget, evt, chain):
            self.taps_recorded.append((widget, evt, chain))

        def on_long_press(widget, pos):
            self.long_presses_recorded.append((widget, pos))

        self.recognizer = TouchTapRecognizer(
            on_tap=on_tap,
            on_long_press=on_long_press,
        )

    def tearDown(self):
        self.recognizer.cancel()

    def test_exact_tap_recognized(self):
        """A tap that lands on the exact same coordinate must be valid."""
        w1 = MagicMock()
        down_evt = make_mouse_down(w1, 10, 10)
        self.recognizer.on_mouse_down(w1, down_evt)

        up_evt = make_mouse_up(w1, 10, 10)
        is_tap, chain, resolved = self.recognizer.on_mouse_up(w1, up_evt)

        self.assertTrue(is_tap)
        self.assertEqual(chain, 1)
        self.assertEqual(resolved, w1)
        self.assertEqual(len(self.taps_recorded), 1)

    def test_finger_jitter_tolerance_recovers_down_widget(self):
        """
        CRITICAL ROOT CAUSE TEST:
        When a finger lands on w1 at (10, 10) and drifts 1 cell to (11, 10) on release
        hitting adjacent widget w2, Textual drops the click.
        TouchTapRecognizer must catch this and resolve back to w1!
        """
        from textual.widgets import Button
        w1 = Button("TestButton")
        w2 = MagicMock(name="BackgroundWidget")

        down_evt = make_mouse_down(w1, 10, 10)
        self.recognizer.on_mouse_down(w1, down_evt)

        # Move slightly (1 cell)
        move_evt = make_mouse_move(w1, 11, 10)
        self.recognizer.on_mouse_move(move_evt)

        # Up on w2
        up_evt = make_mouse_up(w2, 11, 10)
        is_tap, chain, resolved = self.recognizer.on_mouse_up(w2, up_evt)

        self.assertTrue(is_tap, "Must recognize as tap within 2-cell tolerance")
        self.assertEqual(resolved, w1, "Must resolve back to down_widget w1 across jitter!")
        self.assertEqual(len(self.taps_recorded), 1)

    def test_large_movement_rejected_as_tap(self):
        """Dragging 8 cells exceeds tap_slop and must NOT be recognized as tap."""
        w1 = MagicMock()
        down_evt = make_mouse_down(w1, 10, 10)
        self.recognizer.on_mouse_down(w1, down_evt)

        # Drag 8 cells down
        move_evt = make_mouse_move(w1, 10, 18)
        still_tap = self.recognizer.on_mouse_move(move_evt)
        self.assertFalse(still_tap)

        up_evt = make_mouse_up(w1, 10, 18)
        is_tap, chain, resolved = self.recognizer.on_mouse_up(w1, up_evt)

        self.assertFalse(is_tap)
        self.assertEqual(len(self.taps_recorded), 0)

    def test_double_tap_recognition(self):
        """Two quick taps in close proximity must register chain=2."""
        w = MagicMock()
        # Tap 1
        d1 = make_mouse_down(w, 15, 15)
        self.recognizer.on_mouse_down(w, d1)
        u1 = make_mouse_up(w, 15, 15)
        is_tap1, chain1, res1 = self.recognizer.on_mouse_up(w, u1)
        self.assertTrue(is_tap1)
        self.assertEqual(chain1, 1)

        # Tap 2 (50ms later, 1 cell away)
        time.sleep(0.05)
        d2 = make_mouse_down(w, 16, 15)
        self.recognizer.on_mouse_down(w, d2)
        u2 = make_mouse_up(w, 16, 15)
        is_tap2, chain2, res2 = self.recognizer.on_mouse_up(w, u2)

        self.assertTrue(is_tap2)
        self.assertEqual(chain2, 2, "Must detect chained double-tap")

    def test_long_press_fires_callback(self):
        """Holding past LONG_PRESS_DURATION triggers long press and suppresses tap."""
        w = MagicMock()
        d = make_mouse_down(w, 20, 20)
        self.recognizer.on_mouse_down(w, d)

        # Manually advance down_time into the past to trigger long press check
        self.recognizer._down_time -= (LONG_PRESS_DURATION + 0.1)

        triggered = self.recognizer.check_long_press()
        self.assertTrue(triggered)
        self.assertEqual(len(self.long_presses_recorded), 1)
        self.assertEqual(self.long_presses_recorded[0][0], w)

        # Releasing after long press should NOT fire normal tap
        u = make_mouse_up(w, 20, 20)
        is_tap, chain, res = self.recognizer.on_mouse_up(w, u)
        self.assertFalse(is_tap, "Normal tap must be suppressed after long press")
        self.assertEqual(len(self.taps_recorded), 0)


class TestTouchScrollHandler(unittest.TestCase):
    """Test suite for natural drag-to-scroll and click suppression."""

    def setUp(self):
        self.handler = TouchScrollHandler()

    def test_drag_starts_after_threshold(self):
        """Dragging finger vertically past SCROLL_DRAG_THRESHOLD initiates drag scrolling."""
        from textual.containers import VerticalScroll
        class MockVerticalScroll(VerticalScroll):
            max_scroll_y = 100
        container = MockVerticalScroll()
        container.scroll_to = MagicMock()
        container.scroll_relative = MagicMock()
        container.scroll_y = 10

        down_evt = make_mouse_down(container, 20, 20)
        self.handler.on_mouse_down(container, down_evt)
        self.assertFalse(self.handler.is_scrolling)

        # Move 0.5 cell: below threshold
        move1 = make_mouse_move(container, 20, 20)
        scrolled1 = self.handler.on_mouse_move(move1)
        self.assertFalse(self.handler.is_scrolling)
        self.assertFalse(scrolled1)

        # Move 3 cells: clearly past threshold (delta Y = 3)
        move2 = make_mouse_move(container, 20, 23)
        scrolled2 = self.handler.on_mouse_move(move2)

        self.assertTrue(self.handler.is_scrolling)
        self.assertTrue(scrolled2)

    def test_drag_release_finishes_and_returns_true(self):
        """When an active drag finishes, on_mouse_up returns True (signaling click suppression)."""
        from textual.containers import VerticalScroll
        class MockVerticalScroll(VerticalScroll):
            max_scroll_y = 100
        container = MockVerticalScroll()
        container.scroll_to = MagicMock()
        container.scroll_relative = MagicMock()
        container.scroll_y = 50

        down_evt = make_mouse_down(container, 20, 20)
        self.handler.on_mouse_down(container, down_evt)

        # Drag 10 cells
        move_evt = make_mouse_move(container, 20, 30)
        self.handler.on_mouse_move(move_evt)
        self.assertTrue(self.handler.is_scrolling)

        # MouseUp finishes drag
        up_evt = make_mouse_up(container, 20, 30)
        was_scrolling = self.handler.on_mouse_up(up_evt)

        self.assertTrue(was_scrolling, "Must report that drag scroll occurred to suppress click")
        self.assertFalse(self.handler.is_scrolling)


class TestTouchHitZone(unittest.TestCase):
    """Test suite for expanding hit areas for narrow 1-column resizers."""

    def test_find_resizer_within_margin(self):
        """A touch 1 or 2 cells away from a 1-column resizer should hit the resizer."""
        app = MagicMock()
        screen = MagicMock()
        app.screen = screen

        resizer = MagicMock()
        resizer.is_attached = True
        resizer.visible = True
        resizer.region.x = 25
        resizer.region.y = 0
        resizer.region.width = 1
        resizer.region.height = 40

        # Query mock returns resizer for #cct-explorer-resizer
        def mock_query(selector):
            if selector == "#cct-explorer-resizer":
                return [resizer]
            return []

        screen.query.side_effect = mock_query

        # Touch at (26, 15) -> 1 cell to the right of the 1-column handle
        found = TouchHitZone.find_nearby_resizer(app, 26, 15, tolerance=2)
        self.assertEqual(found, resizer)

        # Touch at (27, 15) -> 2 cells away (at margin boundary)
        found2 = TouchHitZone.find_nearby_resizer(app, 27, 15, tolerance=2)
        self.assertEqual(found2, resizer)

        # Touch at (30, 15) -> 5 cells away (outside margin)
        found3 = TouchHitZone.find_nearby_resizer(app, 30, 15, tolerance=2)
        self.assertIsNone(found3)


class TestTouchFocusManager(unittest.TestCase):
    """Test suite for focus stability on touch screens."""

    def test_save_and_restore_focus(self):
        widget = MagicMock()
        widget.is_attached = True
        widget.can_focus = True

        manager = TouchFocusManager()
        manager.save_focus(widget)
        self.assertEqual(manager._previous_screen_focus, widget)

        manager.restore_focus()
        widget.focus.assert_called_once()

    def test_on_touch_tap_input_widget(self):
        from textual.widgets import Input
        inp = Input()
        inp.focus = MagicMock()
        inp.has_focus = False

        manager = TouchFocusManager()
        manager.on_touch_tap_widget(inp)
        inp.focus.assert_called_once()


class TestGestureBridge(unittest.TestCase):
    """Test suite for gesture recognition routing into CAT CLI gesture manager."""

    def test_dispatch_touch_gesture_maps_double_tap(self):
        with patch("calc_terminal.gestures.manager.handle_gesture") as mock_handle:
            mock_handle.return_value = True
            app = MagicMock()

            res = GestureBridge.dispatch_touch_gesture("double_tap", "file", app=app)
            self.assertTrue(res)
            mock_handle.assert_called_once_with("double_click", "file", app=app, context={})

    def test_resolve_target_surface(self):
        from textual.widgets import TextArea
        editor = TextArea()
        editor.id = "cct-editor"
        surface = GestureBridge.resolve_target_surface(editor)
        self.assertEqual(surface, "editor")


class TestMouseKeyboardZeroRegression(unittest.TestCase):
    """Verify that traditional mouse and keyboard behavior is completely preserved."""

    def test_exact_mouse_click_behavior(self):
        """When user clicks with mouse, resolved_widget matches exact widget."""
        recognizer = TouchTapRecognizer()
        w = MagicMock()

        down_evt = make_mouse_down(w, 5, 5)
        recognizer.on_mouse_down(w, down_evt)

        up_evt = make_mouse_up(w, 5, 5)
        is_tap, chain, resolved = recognizer.on_mouse_up(w, up_evt)

        self.assertTrue(is_tap)
        self.assertEqual(resolved, w)
        self.assertEqual(chain, 1)

    def test_right_mouse_click_ignores_tap_handler(self):
        """Right click (button=2) is completely untouched by tap handler."""
        recognizer = TouchTapRecognizer()
        w = MagicMock()

        down_evt = make_mouse_down(w, 5, 5, button=2)
        recognizer.on_mouse_down(w, down_evt)

        self.assertFalse(recognizer._active)


class TestTouchAutoPromotionAndRecovery(unittest.TestCase):
    """Test suite for runtime auto-promotion and robust button tap recovery."""

    def test_auto_promote_touch_mode(self):
        from calc_terminal.input.capabilities import auto_promote_touch_mode, set_touch_mode, get_input_capabilities
        set_touch_mode(False, persist=False)
        caps = get_input_capabilities()
        self.assertFalse(caps.touch_mode_enabled)

        promoted = auto_promote_touch_mode()
        self.assertTrue(promoted)
        self.assertTrue(caps.touch_mode_enabled)
        self.assertTrue(caps.touchscreen_available)

    def test_finger_jitter_expanded_tolerance(self):
        """Finger moving 3.5 cells horizontally on high-DPI laptop screen must still be recognized as tap."""
        from textual.widgets import Button
        w1 = Button("TouchButton")
        w2 = MagicMock(name="Neighbor")
        recognizer = TouchTapRecognizer()

        down_evt = make_mouse_down(w1, 10, 10)
        recognizer.on_mouse_down(w1, down_evt)

        # Move 3.5 cells (within 4.0 allowance)
        move_evt = make_mouse_move(w1, 13, 10)
        self.assertTrue(recognizer.on_mouse_move(move_evt))

        # Release on w2
        up_evt = make_mouse_up(w2, 13, 10)
        is_tap, chain, resolved = recognizer.on_mouse_up(w2, up_evt)
        self.assertTrue(is_tap)
        self.assertEqual(resolved, w1)

    def test_startup_loading_overlay_lifecycle(self):
        """Test StartupLoadingOverlay progress rendering, advancement, and complete_and_dismiss."""
        from calc_terminal.ui.startup_loader import StartupLoadingOverlay
        overlay = StartupLoadingOverlay()
        self.assertIsNotNone(overlay)

        # Verify initial bar render
        bar_text = overlay._render_bar(0.50)
        self.assertIn("50%", bar_text)

        # Verify 100% completion render
        full_bar = overlay._render_bar(1.0)
        self.assertIn("100%", full_bar)

        # Verify complete_and_dismiss marks state as finishing
        overlay.complete_and_dismiss()
        self.assertTrue(overlay._is_finishing)


if __name__ == "__main__":
    unittest.main()
