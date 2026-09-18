"""
CAT Host — Terminal Embed

Provides the terminal pane inside the graphical CAT Host window.

The host window is a real OS window (Qt/QWebEngine on Windows). This module
gives it a terminal surface that preserves existing CAT CLI behaviour:

  PowerShell
    ↓
  cat  (launcher detects Windows, launches CAT Host)
    ↓
  CAT Host OS Window
    ├── [Terminal]  ← this widget (CAT REPL preserved)
    ├── [Browser]   ← real QWebEngineView (WebView2/Chromium)
    ├── [IDE]
    └── ...

Design decisions:
* The widget is a plain Qt widget (no external PTY, no xterm.js dependency)
  so it works with only PySide6 installed.
* It hosts the existing calc_terminal.app.App REPL logic — the same
  handle()/handle_question() dispatch the Textual and fallback CLI use.
  Input from the GUI line edit is fed to App.handle(); output (print())
  is captured and appended to the read-only log view.
* ANSI escape sequences from calc_terminal.theme are stripped for the
  QPlainTextEdit (Qt handles rich text separately). The behaviour and
  command set are 100% identical to the classic terminal.
* If the REPL raises, the widget stays alive — the error is shown inline
  and the prompt returns (same contract as the fallback terminal).

Fomoji: the REPL instance passed in is the same one cli.bootstrap()
created, so `cat --auth` state is shared.
"""

from __future__ import annotations

import io
import re
import sys
import contextlib
import threading
import traceback

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\].*?\x07|\x1b\(B")

def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s)


# ---------------------------------------------------------------------------
# Fallback when Qt not installed — import-time safe so the host package
# can be imported on headless CI.
# ---------------------------------------------------------------------------
try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
        QLineEdit, QLabel, QPushButton
    )
    from PySide6.QtCore import Qt, Signal, Slot
    from PySide6.QtGui import QFont, QTextCursor
    _QT_AVAILABLE = True
except ImportError:
    try:
        from PyQt6.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
            QLineEdit, QLabel, QPushButton
        )
        from PyQt6.QtCore import Qt, pyqtSignal as Signal, pyqtSlot as Slot
        from PyQt6.QtGui import QFont, QTextCursor
        _QT_AVAILABLE = True
    except ImportError:
        _QT_AVAILABLE = False
        QWidget = object  # type: ignore
        Signal = lambda *a, **k: None  # type: ignore


if _QT_AVAILABLE:

    class CATTerminalWidget(QWidget):
        """
        Graphical terminal pane for CAT Host.

        Hosts calc_terminal.app.App (the REPL/product logic) and exposes
        it through a Qt input line + scrollback. The host window owns the
        layout; this widget owns only the terminal chrome.

        Usage:
            repl = App()  # from calc_terminal.app
            term = CATTerminalWidget(repl)
            stacked.addWidget(term)
        """

        # Emitted on every command so the host can mirror to status bar
        commandEntered = Signal(str)

        def __init__(self, repl=None, parent=None):
            super().__init__(parent)
            self.repl = repl
            self._history: list[str] = []
            self._history_idx: int = -1
            self._setup_ui()
            self._print_boot()

        def _setup_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(6, 6, 6, 6)
            layout.setSpacing(6)

            # Header — shows we are the real CAT terminal, not a plain shell
            header = QLabel("CAT TERMINAL  —  type /help  ·  /browser  ·  /agent  ·  Ctrl+Shift+B → Browser")
            header.setStyleSheet("color: #878caf; font-size: 11px; padding: 2px 4px;")
            layout.addWidget(header)

            # Scrollback — read-only, selectable
            self.log = QPlainTextEdit()
            self.log.setReadOnly(True)
            self.log.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
            font = QFont("Consolas" if sys.platform == "win32" else "Monospace", 10)
            font.setStyleHint(QFont.StyleHint.Monospace)
            self.log.setFont(font)
            # Dark terminal palette matching CAT themes
            self.log.setStyleSheet(
                "QPlainTextEdit { background: #1a1b26; color: #e8ebfa; "
                "border: 1px solid #2a2e48; border-radius: 6px; padding: 6px; "
                "selection-background-color: #82aaff; }"
            )
            layout.addWidget(self.log, 1)

            # Input row — glyph + line edit + send
            row = QHBoxLayout()
            row.setSpacing(6)
            glyph = QLabel("❯")
            glyph.setStyleSheet("color: #82aaff; font-weight: bold; font-size: 14px; padding-left: 4px;")
            glyph.setFixedWidth(22)
            row.addWidget(glyph)

            self.input = QLineEdit()
            self.input.setPlaceholderText("Type a command or question…  (/help for list)")
            self.input.setStyleSheet(
                "QLineEdit { background: #1e2030; color: #e8ebfa; "
                "border: 1px solid #2a2e48; border-radius: 999px; padding: 6px 12px; "
                "selection-background-color: #82aaff; }"
                "QLineEdit:focus { border: 1px solid #82aaff; }"
            )
            self.input.returnPressed.connect(self._on_submit)
            row.addWidget(self.input, 1)

            send = QPushButton("↵")
            send.setFixedSize(32, 28)
            send.setToolTip("Send (Enter)")
            send.setStyleSheet(
                "QPushButton { background: #82aaff; color: #1a1b26; border: none; "
                "border-radius: 14px; font-weight: bold; }"
                "QPushButton:hover { background: #9ab8ff; }"
            )
            send.clicked.connect(self._on_submit)
            row.addWidget(send)

            layout.addLayout(row)
            self.input.setFocus()

        # --------------------------------------------------------------- I/O --

        def _append(self, text: str):
            """Append text to scrollback, stripping ANSI for Qt."""
            if not text:
                return
            clean = _strip_ansi(text)
            # QPlainTextEdit.appendPlainText adds a newline; for multi-line
            # captures we insert as single block to preserve formatting.
            self.log.appendPlainText(clean.rstrip("\n"))
            # Autoscroll
            cursor = self.log.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log.setTextCursor(cursor)

        def _print_boot(self):
            if self.repl is None:
                self._append("CAT terminal ready — no REPL attached (UI preview mode).")
                self._append("Run `cat` from PowerShell to attach the real session.")
                return
            # Capture the classic boot/home output (same as fallback CLI)
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    # theme.enable_windows_ansi + load_saved_theme are already
                    # done by cli.bootstrap(); just print home.
                    try:
                        self.repl.print_home()
                    except Exception:
                        # Fallback if print_home fails early
                        print(f"CAT v{getattr(self.repl, 'VERSION', '?')} — ready", file=buf)
            except Exception as e:
                buf.write(f"[boot warning: {e}]\n")
            out = buf.getvalue()
            if out.strip():
                self._append(out)
            else:
                self._append(f"CAT v{getattr(self.repl, 'VERSION', '0.7.9')} — ready. Type /help")

        def _on_submit(self):
            raw = self.input.text()
            if raw is None:
                return
            raw = raw.strip()
            if not raw:
                return
            # History
            self._history.append(raw)
            del self._history[:-200]
            self._history_idx = len(self._history)
            self.input.clear()
            self._append(f"\n❯ {raw}")
            self.commandEntered.emit(raw)

            if self.repl is None:
                self._append("(no REPL — echo only)")
                return

            # Special: clear
            if raw.lower() in ("/clear", "/home", "clear", "cls"):
                self.log.clear()
                self._print_boot()
                return

            # Dispatch to the real REPL, capturing its print() output
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    self.repl.handle(raw)
            except SystemExit:
                # /exit /quit — don't kill host window, just note it
                self._append("\n[Use the window close button or Ctrl+Q to quit CAT Host]")
                # Still show any buffered output
            except Exception as e:
                buf.write(f"\n[error: {type(e).__name__}: {e}]\n")
                traceback.print_exc(file=buf)
            out = buf.getvalue()
            if out:
                self._append(out)

        # --------------------------------------------------------- public API --

        def focus_input(self):
            self.input.setFocus()
            self.input.selectAll()

        def execute(self, raw: str):
            """Programmatic entry — used by host for /browser shortcuts."""
            self.input.setText(raw)
            self._on_submit()

        def keyPressEvent(self, event):
            # History navigation with Up/Down when input is focused
            try:
                if event.key() == Qt.Key.Key_Up:
                    if self.input.hasFocus() and self._history:
                        self._history_idx = max(0, self._history_idx - 1)
                        self.input.setText(self._history[self._history_idx])
                        return
                elif event.key() == Qt.Key.Key_Down:
                    if self.input.hasFocus() and self._history:
                        if self._history_idx >= len(self._history) - 1:
                            self._history_idx = len(self._history)
                            self.input.clear()
                        else:
                            self._history_idx += 1
                            self.input.setText(self._history[self._history_idx])
                        return
            except Exception:
                pass
            super().keyPressEvent(event)

else:
    # Stub so `from .terminal import CATTerminalWidget` never crashes
    class CATTerminalWidget:  # type: ignore
        def __init__(self, *a, **k):
            raise ImportError("Qt not installed — CAT Host requires PySide6 (pip install PySide6)")
