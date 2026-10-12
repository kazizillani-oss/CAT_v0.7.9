"""Privacy-conscious diagnostics for CAT Browser and Qt WebEngine."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import sys
import threading
import traceback
from datetime import datetime, timezone
from urllib.parse import urlsplit


_LOGGER_NAME = "calc_terminal.cat_browser"
_INSTALL_LOCK = threading.Lock()
_LOGGER_LOCK = threading.Lock()
_INSTALLED = False
_QT_HANDLER_INSTALLED = False
_URL_RE = re.compile(r"(?i)\bhttps?://[^\s\"'<>]+")


def _redact_url(match: re.Match[str]) -> str:
    raw = match.group(0).rstrip(",.;)]}")
    try:
        parsed = urlsplit(raw)
        host = parsed.hostname or "[host]"
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return f"{parsed.scheme}://{host}/[redacted]"
    except Exception:
        return "[url redacted]"


def _safe(value):
    if isinstance(value, str):
        return _URL_RE.sub(_redact_url, value)
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _URL_RE.sub(_redact_url, str(value))


def _logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    with _LOGGER_LOCK:
        if not logger.handlers:
            try:
                handler = RotatingFileHandler(
                    Path.home() / ".cat_browser_diagnostics.jsonl",
                    maxBytes=1_000_000,
                    backupCount=2,
                    encoding="utf-8",
                )
                handler.setFormatter(logging.Formatter("%(message)s"))
                logger.addHandler(handler)
                logger.setLevel(logging.INFO)
                logger.propagate = False
            except Exception:
                logger.addHandler(logging.NullHandler())
    return logger


def log_event(event: str, **fields) -> None:
    """Append one timestamped, URL-redacted JSON event; never disrupt the app."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "event": event,
        "pid": os.getpid(),
        **fields,
    }
    try:
        _logger().info(json.dumps(_safe(record), ensure_ascii=False, default=str))
    except Exception:
        pass


def log_exception(event: str, exc_info=None, **fields) -> None:
    if exc_info is None:
        exc_info = sys.exc_info()
    try:
        fields["exception_type"] = getattr(exc_info[0], "__name__", "Exception")
        # Keep the full frame trace without recording exception values that can
        # contain pasted prompts, tokens, or private page contents.
        fields["traceback"] = "".join(traceback.format_tb(exc_info[2]))
    except Exception:
        fields["traceback"] = "traceback formatting failed"
    log_event(event, **fields)


def install_diagnostics() -> None:
    """Install Python exception hooks before constructing Qt widgets."""
    global _INSTALLED
    with _INSTALL_LOCK:
        if _INSTALLED:
            return
        _INSTALLED = True
        previous_sys_hook = sys.excepthook

        def _sys_hook(exc_type, exc_value, exc_tb):
            log_exception(
                "uncaught_python_exception",
                (exc_type, exc_value, exc_tb),
                thread="main",
            )
            previous_sys_hook(exc_type, exc_value, exc_tb)

        sys.excepthook = _sys_hook

        if hasattr(threading, "excepthook"):
            previous_thread_hook = threading.excepthook

            def _thread_hook(args):
                log_exception(
                    "uncaught_thread_exception",
                    (args.exc_type, args.exc_value, args.exc_traceback),
                    thread=getattr(args.thread, "name", None),
                )
                previous_thread_hook(args)

            threading.excepthook = _thread_hook

        log_event("browser_process_started", python=sys.version.split()[0])


def install_qt_message_handler() -> None:
    """Record Qt warnings/errors without suppressing Qt's normal behavior."""
    global _QT_HANDLER_INSTALLED
    if _QT_HANDLER_INSTALLED:
        return
    try:
        try:
            from PySide6.QtCore import QtMsgType, qInstallMessageHandler
        except ImportError:
            from PyQt6.QtCore import QtMsgType, qInstallMessageHandler  # type: ignore

        error_types = {
            QtMsgType.QtWarningMsg,
            QtMsgType.QtCriticalMsg,
            QtMsgType.QtFatalMsg,
        }

        def _qt_handler(msg_type, context, message):
            if msg_type not in error_types:
                return
            log_event(
                "qt_message",
                severity=getattr(msg_type, "name", str(msg_type)),
                category=getattr(context, "category", None),
                source_file=getattr(context, "file", None),
                source_line=getattr(context, "line", None),
                message=message,
            )

        qInstallMessageHandler(_qt_handler)
        _QT_HANDLER_INSTALLED = True
    except Exception:
        log_exception("qt_message_handler_install_failed")
