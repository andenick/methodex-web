"""Central configuration for the Methodex public website.

Resolves project paths and site constants. All paths are computed relative to
this file so the app works regardless of where the venv lives.

Path hierarchy:
    webapp/app/config.py  ->  webapp/  ->  Methodex/  ->  Projects/  ->  Arcanum/

PUBLIC-ONLY GUARANTEE
---------------------
This webapp serves ONLY the public-domain US-federal-government layer of the
Methodex corpus (957 docs / 392 events / 80 statistics). It forces the
environment variable METHODEX_PUBLIC_ONLY=1 *at import time* (see force_public_only
below), BEFORE the methodex_mcp module is imported anywhere, so the canonical
in-memory stores are physically filtered to public-domain material. No
in-copyright / INTL / academic / UNKNOWN content can ever be served.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# PUBLIC-ONLY enforcement — set BEFORE any import of methodex_mcp.
# methodex_mcp filters its stores once at import time based on this env var, so
# it MUST be set before the first import. Importing this config module first
# (which app.main / build_cache / the services all do) guarantees that.
# ---------------------------------------------------------------------------
os.environ["METHODEX_PUBLIC_ONLY"] = "1"

# ---------------------------------------------------------------------------
# Root paths
# ---------------------------------------------------------------------------

# webapp/app/config.py -> webapp/ -> Methodex/
WEBAPP_ROOT: Path = Path(__file__).resolve().parent.parent
PROJECT_ROOT: Path = WEBAPP_ROOT.parent              # …/Methodex/
ARCANUM_ROOT: Path = PROJECT_ROOT.parent.parent      # …/Arcanum/  (Methodex -> Projects -> Arcanum)

# ---------------------------------------------------------------------------
# Project source directories (read-only; populated outside webapp)
# ---------------------------------------------------------------------------

SRC_DIR: Path = PROJECT_ROOT / "src"
STATE_DIR: Path = PROJECT_ROOT / "Technical" / "campaign" / "state"

# ---------------------------------------------------------------------------
# Webapp runtime directories (generated; gitignored)
# ---------------------------------------------------------------------------

SITE_DATA: Path = WEBAPP_ROOT / "site_data"
CACHE_DIR: Path = SITE_DATA / "cache"
DOWNLOADS_DIR: Path = SITE_DATA / "downloads"

# ---------------------------------------------------------------------------
# Template + static directories
# ---------------------------------------------------------------------------

TEMPLATES_DIR: Path = WEBAPP_ROOT / "app" / "templates"
STATIC_DIR: Path = WEBAPP_ROOT / "app" / "static"

# ---------------------------------------------------------------------------
# Site identity
# ---------------------------------------------------------------------------

SITE_TITLE: str = "Methodex"
SITE_TAGLINE: str = "The construction-and-revision history of every economic statistic"
SITE_HOST: str = os.environ.get("METHODEX_HOST", "methodex.fyi")

# The public-domain layer carved by Technical/campaign/classify_license.py.
PUBLIC_DOMAIN_LICENSE: str = "US-Gov public domain"

# Carson telemetry service name (registry name in usage_events.service).
TELEMETRY_SERVICE: str = "methodex"

# Umami (Layer-2 web analytics) placeholders — filled in at deploy time.
UMAMI_SRC: str = os.environ.get("METHODEX_UMAMI_SRC", "")
UMAMI_WEBSITE_ID: str = os.environ.get("METHODEX_UMAMI_WEBSITE_ID", "")


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------

def get_manifest_path() -> Path:
    """Return the path to site_manifest.json (may not exist before build_cache.py runs)."""
    return SITE_DATA / "site_manifest.json"


# ---------------------------------------------------------------------------
# Startup helper
# ---------------------------------------------------------------------------

def ensure_dirs() -> None:
    """Create runtime directories that must exist at startup."""
    for d in (SITE_DATA, CACHE_DIR, DOWNLOADS_DIR):
        d.mkdir(parents=True, exist_ok=True)
