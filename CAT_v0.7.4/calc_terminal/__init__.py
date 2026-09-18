__version__ = "0.7.8.45"


def _sync_version():
    """Keep __version__ in sync with calc_terminal.app.VERSION so package
    metadata and application version information never drift apart."""
    try:
        from .app import VERSION
        return VERSION
    except Exception:
        return __version__


__version__ = _sync_version()