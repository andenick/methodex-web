"""Arcanum Site Kit (ASK) v1 — shared-chrome context processor (Methodex).

This is the single mechanism that injects the shared header/footer/switcher
variables into **every** Jinja template render, regardless of which route or
helper builds the per-route context. It is wired in ``main.py`` via::

    Jinja2Templates(directory=..., context_processors=[chrome.ark_context])

Starlette runs each context processor for every ``TemplateResponse`` (it
receives only the ``Request`` and returns a dict that is merged into the
context), so no per-route edits are needed and existing per-route variables are
preserved. The keys injected here (``ecosystem``, ``nav``, ``site_key``, …) do
not collide with methodex's page variables.

Adapted from the leontief reference recipe: copy of leontief/app/chrome.py with
``SITE_KEY`` / ``DPR_URL`` / ``NAV`` retargeted to methodex's real routes.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache

from starlette.requests import Request

from app import config as C

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-site identity (the only values another site changes)
# ---------------------------------------------------------------------------
SITE_KEY: str = "methodex"            # ecosystem.json site.key -> switcher "current"
SITE_HOME: str = "/"                  # what the site title links to
DPR_URL: str = "/methodology"         # methodex's provenance target (footer link).
                                      # The dedicated DPR / provenance page (Wave-3).
                                      # /about keeps the project context; /methodology
                                      # is the standard .ark-provenance panel.

# Blueprint nav vocabulary mapped to methodex's REAL routes (Wave-3 build-out).
# Each entry: (label, href). ``active`` is computed per request from the path.
# Explore + Docs are methodex's two browse surfaces; Data/Code/Methodology are the
# blueprint pages added in Wave-3 (real-data-bounded; see /methodology for limits).
NAV: list[tuple[str, str]] = [
    ("Explore",     "/explore"),
    ("Docs",        "/docs"),
    ("Data",        "/data"),
    ("Code",        "/code"),
    ("Methodology", "/methodology"),
    ("About",       "/about"),
]

# Vendored canonical manifest (served at /static/_shared/ecosystem.json).
_ECOSYSTEM_PATH = C.STATIC_DIR / "_shared" / "ecosystem.json"


@lru_cache(maxsize=1)
def load_ecosystem() -> dict:
    """Parse the vendored ecosystem.json once (cached). Non-fatal on error."""
    try:
        with open(_ECOSYSTEM_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # noqa: BLE001 — chrome must never break a render
        logger.warning("ecosystem.json not loaded (%s): %s", _ECOSYSTEM_PATH, exc)
        return {}


def _nav_for(path: str) -> list[dict]:
    """Build the nav list with ``active`` set from the current request path.

    Path-derived (not section-derived) so it is route-agnostic: any route under
    a section's prefix lights the right tab without the route having to remember
    to pass ``section``. A nav item is active when the path equals its href or
    sits beneath it (e.g. /statistic/... does not light Explore by default, but
    /explore/... would). External hrefs (http*) are never active.
    """
    items: list[dict] = []
    for label, href in NAV:
        if href.startswith("http"):
            active = False
        else:
            active = path == href or (href != "/" and path.startswith(href + "/"))
            # A statistic detail page (/statistic/{id}) is reached FROM Explore
            # and has no nav tab of its own, so light the Explore tab for it.
            if href == "/explore" and path.startswith("/statistic"):
                active = True
        items.append({"label": label, "href": href, "active": active})
    return items


def _site_cdf() -> dict:
    """This site's `cdf` block from the vendored ecosystem.json (kit schema v3).

    Drives the server-rendered Research Triad (adapters/jinja_triad → triad.html)
    and the methodex-specific "Agents: connect via MCP" landing card (cdf.mcp).
    Empty dict if absent — every consumer guards on it, so a missing block is a
    graceful no-op (the triad renders nothing rather than dead buttons)."""
    for s in load_ecosystem().get("sites", []):
        if s.get("key") == SITE_KEY:
            return s.get("cdf") or {}
    return {}


def ark_context(request: Request) -> dict:
    """Starlette context processor — runs for every TemplateResponse."""
    return {
        "site_key": SITE_KEY,
        "site_title": C.SITE_TITLE,   # "Methodex"
        "site_home": SITE_HOME,
        "dpr_url": DPR_URL,
        "ecosystem": load_ecosystem(),
        "cdf": _site_cdf(),
        "nav": _nav_for(request.url.path),
    }
