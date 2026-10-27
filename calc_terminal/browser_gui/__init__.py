"""CAT Browser GUI package — real embedded browser (Chromium/WebView2)."""

try:
    from .tab_bar import CATBrowserTabs, VerticalTabRow
    __all__ = ["CATBrowserTabs", "VerticalTabRow"]
except Exception:
    CATBrowserTabs = None  # type: ignore
    VerticalTabRow = None  # type: ignore
    __all__ = []

