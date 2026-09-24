"""CAT web package (Fatty CAT server + web runtime).

This package ships the FastAPI server and the bundled PWA static assets
(``static/``). The directory previously had no ``__init__.py`` and only
worked by accident via namespace-package semantics; an explicit package
marker makes ``calc_terminal.web`` importable identically from a source
checkout and from an installed wheel.
"""
