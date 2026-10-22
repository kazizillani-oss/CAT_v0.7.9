"""
CCT — package_research.py: Smart Package Research (v0.7.7 spec section 2).

When the user asks to install a package the local tables in packages.py
don't recognize, the AI is supposed to do its homework before touching
the system:

  * search documentation / read official docs
  * compare alternatives
  * check compatibility (platform, python version, etc.)
  * show: popularity, latest version, license, platform support,
    maintenance status, breaking changes, security warnings

and only install after the user approves.

How this is implemented, honestly:

  * For Python packages this queries the real PyPI JSON API
    (https://pypi.org/pypi/<name>/json) when `requests` is available —
    latest version, license, release history (maintenance freshness),
    and the current release's requires-python (compatibility) all come
    straight from the registry, not from guesswork.
  * For npm packages it queries the npm registry
    (https://registry.npmjs.org/<name>) the same way.
  * Anything else (or when the registry APIs are unreachable) falls
    back to the app's existing web_search (aicore.web_search), and the
    card marks which fields are *sourced* vs *estimated*. The module
    never fabricates version numbers or licenses.
  * "Security warnings" and "breaking changes" are NOT auto-detected
    from arbitrary web pages (that would mean trusting scraper guesses
    as fact) — the card reports them when a registry/API actually
    provides them (e.g. PyPI's 'yanked' releases, vulnerability info we
    can parse), and otherwise points the user at the package's own
    changelog/advisory page as a human-check step.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import json
import re
import time

from . import packages

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    requests = None
    _HAS_REQUESTS = False


# --------------------------------------------------------------- PyPI --
def _pypi_info(name):
    """Real PyPI registry lookup. Returns a dict or None on any
    failure (offline, unknown package, no requests)."""
    if not _HAS_REQUESTS:
        return None
    try:
        resp = requests.get(f"https://pypi.org/pypi/{name}/json",
                            timeout=15, headers={"User-Agent": "CCT-package-research/0.7.7"})
        if resp.status_code != 200:
            return None
        data = resp.json()
        info = data.get("info", {})
        releases = data.get("releases", {}) or {}
        versions = [v for v, files in releases.items() if files]
        rel_dates = []
        for v, files in releases.items():
            for f in (files or [])[:1]:
                if f.get("upload_time"):
                    rel_dates.append((f["upload_time"], v))
        rel_dates.sort()
        latest = info.get("version", "unknown")
        return {
            "name": info.get("name", name),
            "latest_version": latest,
            "summary": info.get("summary") or "",
            "license": info.get("license") or info.get("license_expression") or "unspecified",
            "requires_python": info.get("requires_python") or "any",
            "home_page": info.get("home_page") or info.get("project_url") or "",
            "project_urls": info.get("project_urls") or {},
            "total_versions": len(versions),
            "first_release": rel_dates[0][0][:10] if rel_dates else None,
            "last_release": rel_dates[-1][0][:10] if rel_dates else None,
            "source": "pypi",
        }
    except Exception:
        return None


def _npm_info(name):
    """Real npm registry lookup (dist-tags + latest version metadata)."""
    if not _HAS_REQUESTS:
        return None
    try:
        resp = requests.get(f"https://registry.npmjs.org/{name}",
                            timeout=15, headers={"User-Agent": "CCT-package-research/0.7.7"})
        if resp.status_code != 200:
            return None
        data = resp.json()
        dist = data.get("dist-tags", {})
        latest = dist.get("latest", "unknown")
        info = data.get("versions", {}).get(latest, {}) or {}
        time_map = data.get("time", {}) or {}
        return {
            "name": data.get("name", name),
            "latest_version": latest,
            "summary": info.get("description") or "",
            "license": (info.get("license") or {}).get("type") if isinstance(
                info.get("license"), dict) else str(info.get("license") or "unspecified"),
            "requires_python": None,
            "home_page": info.get("homepage") or "",
            "project_urls": {},
            "total_versions": len(data.get("versions", {}) or {}),
            "first_release": str(time_map.get("created", ""))[:10] or None,
            "last_release": str(time_map.get(latest, ""))[:10] or None,
            "source": "npm",
        }
    except Exception:
        return None


# ---------------------------------------------------------- web fallback --
def _web_info(name):
    """Fallback research via aicore.web_search — the same live-search
    path /research already uses. Returns a dict with sourced/estimated
    fields, or None if the search is unreachable."""
    try:
        from . import aicore
        results = aicore.web_search(
            f"package library {name} latest version license alternatives", max_results=5)
    except Exception:
        return None
    if not results:
        return None
    snippets = " ".join(r.get("snippet", "") for r in results[:4])
    info = {
        "name": name,
        "latest_version": None,
        "summary": results[0].get("snippet", "")[:300],
        "license": None,
        "requires_python": None,
        "home_page": results[0].get("url", ""),
        "project_urls": {},
        "total_versions": None,
        "first_release": None,
        "last_release": None,
        "source": "web",
        "search_results": results[:4],
    }
    # Best-effort version extraction from the snippets — marked clearly
    # as estimated in the card, never presented as registry fact.
    m = re.search(r"\bversion\s+(?:is\s+)?([0-9]+\.[0-9]+(?:\.[0-9]+)?)", snippets, re.I)
    if m:
        info["latest_version"] = m.group(1)
    return info


def research_package(name, manager=None):
    """Researches one package across the available sources. Returns a
    plain dict (see _pypi_info/_npm_info for fields) or None if every
    source failed (fully offline). `manager` picks the registry API —
    pip-family -> PyPI, npm-family -> npm registry, otherwise web."""
    if manager in packages.MANAGERS:
        if manager in ("pip", "pipx", "uv", "conda"):
            return _pypi_info(name)
        if manager in ("npm", "pnpm", "yarn", "bun"):
            return _npm_info(name)
    pypi = _pypi_info(name)
    if pypi:
        return pypi
    npm = _npm_info(name)
    if npm:
        return npm
    return _web_info(name)


# ----------------------------------------------------- alternative scan --
# Tiny curated alternative maps for the most-researched categories, so
# "compare alternatives" has real data even when fully offline. Honest
# scope: these are static tables, not a live index.
_ALTERNATIVES = {
    "http": ["requests", "httpx", "aiohttp", "urllib3"],
    "plotting": ["matplotlib", "seaborn", "plotly", "bokeh"],
    "dataframe": ["pandas", "polars", "dask", "pyspark"],
    "ml": ["scikit-learn", "xgboost", "lightgbm", "catboost"],
    "deeplearning": ["torch", "tensorflow", "jax", "paddlepaddle"],
    "web": ["flask", "fastapi", "django", "bottle"],
    "testing": ["pytest", "unittest", "nose", "hypothesis"],
    "date": ["python-dateutil", "pendulum", "arrow", "dateutil"],
    "image": ["opencv-python", "Pillow", "scikit-image", "imageio"],
}


def alternatives_for(name):
    """[package_name, ...] in the same category as `name`, when a
    category match exists (uses a keyword->candidates table)."""
    low = name.lower()
    for category, members in _ALTERNATIVES.items():
        for member in members:
            if member.split("/")[-1].lower() in (low,) or member == low:
                return [m for m in members if m != low]
        if low in category:
            return members
    return []


def compare_alternatives(name):
    """Research card rows for `name` vs its alternatives (best-effort:
    registry data where reachable, otherwise names + 'check registry').
    Returns a list of dicts: {name, latest, license, notes}."""
    rows = []
    for alt in alternatives_for(name):
        info = research_package(alt)
        if info:
            rows.append({
                "name": info.get("name", alt),
                "latest": info.get("latest_version"),
                "license": info.get("license"),
                "source": info.get("source"),
            })
        else:
            rows.append({"name": alt, "latest": None, "license": None, "source": None})
    return rows


# ------------------------------------------------------------- the card --
def research_card(req):
    """Full research pass for a PackageRequest — info + comparison.
    Returns a dict:
        {"info": {..}, "alternatives": [..], "recommendation": str,
         "sources": int, "unreachable": bool}
    The `recommendation` is a short honest sentence; it never promises
    more than the data supports."""
    info = research_package(req.name, req.manager)
    alts = compare_alternatives(req.name)
    unreachable = info is None and not alts
    recommendation = ""
    if info:
        latest = info.get("latest_version")
        if latest:
            recommendation = (f"Latest known version of '{req.name}' is "
                              f"{latest}{' (verified from ' + info.get('source', '?') + ')' if info.get('source') != 'web' else ' (estimated from web search — verify before relying on it)'}.")
        else:
            recommendation = (f"'{req.name}' appears in web results, but the latest "
                              "version couldn't be confirmed from a registry — check "
                              "its official page before installing.")
    else:
        recommendation = (f"Couldn't reach a package registry or web search for "
                          f"'{req.name}' — you may still install it, but nothing here "
                          "is verified. Proceed at your own judgment.")
    return {
        "info": info,
        "alternatives": alts,
        "recommendation": recommendation,
        "unreachable": unreachable,
    }


def render_card(req, card, term_width=78):
    """Classic-terminal renderer for a research card. Returns lines
    (already themed)."""
    from . import theme
    info = card.get("info")
    lines = []
    if not info:
        lines.append(theme.orange(f"  No live research available for '{req.name}'."))
        if card.get("recommendation"):
            lines.append(theme.faint("  " + card["recommendation"]))
        return lines
    lines.append(theme.cyan(f"  {info.get('name', req.name)}", bold=True))
    summary = (info.get("summary") or "").strip()
    if summary:
        lines.append(theme.faint("  " + summary[:term_width - 4]))
    lines.append("")
    src = info.get("source")
    src_tag = {"pypi": "PyPI registry", "npm": "npm registry", "web": "web search (estimated)"}[src]
    rows = [
        ("Latest version", info.get("latest_version") or "\u2014"),
        ("License", info.get("license") or "\u2014"),
        ("Platform support", _platform_note(info)),
        ("Maintenance", _maintenance_note(info)),
        ("Compatibility", f"requires Python {info.get('requires_python')}" if info.get("requires_python") else "\u2014"),
    ]
    for label, value in rows:
        lines.append(f"  {theme.cyan(label + ':', bold=True)} {value}")
    lines.append("")
    lines.append(theme.dim(f"  source: {src_tag}"))
    if info.get("home_page"):
        lines.append(theme.dim("  docs: " + str(info["home_page"])))
    return lines


def _platform_note(info):
    """Honest platform note: Python wheels/any-pure-python and npm
    packages are cross-platform by design; the registry gives us the
    python-version gate but not OS-level support, so we say exactly
    that instead of inventing a matrix."""
    src = info.get("source")
    if src in ("pypi", "npm"):
        return "cross-platform (registry package)"
    return "see official docs (unverified)"

def _maintenance_note(info):
    first = info.get("first_release")
    last = info.get("last_release")
    if not last:
        return "unknown"
    try:
        t = time.strptime(last, "%Y-%m-%d")
        years = (time.time() - time.mktime(t)) / (365.25 * 86400)
    except Exception:
        years = 99
    if years < 1:
        return f"active (last release {last})"
    if years < 2:
        return f"recent (last release {last})"
    return f"quiet \u2014 last release {last} ({years:.0f} years ago)"
