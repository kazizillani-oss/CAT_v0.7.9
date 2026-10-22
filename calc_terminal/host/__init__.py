"""
CAT Browser subsystem — embedded QWebEngineView renderer owned by CAT.

When CAT needs to render a real webpage (HTML/CSS/JavaScript), it uses
this subsystem to create a browser window with QWebEngineView (Chromium).

The browser is NOT a separate application. It is created by CAT on demand
and destroyed when closed.

Usage:
  from calc_terminal.host import launch_cat_host, can_launch_host
  if can_launch_host():
      launch_cat_host(start_browser_url="http://localhost:3000/connector.html")
"""

from __future__ import annotations

def launch_cat_host(*args, **kwargs):
    from .launcher import launch_cat_host as _impl
    return _impl(*args, **kwargs)

def can_launch_host(*args, **kwargs):
    from .launcher import can_launch_host as _impl
    return _impl(*args, **kwargs)

def get_host_status(*args, **kwargs):
    from .launcher import get_host_status as _impl
    return _impl(*args, **kwargs)

__all__ = ["launch_cat_host", "can_launch_host", "get_host_status"]
