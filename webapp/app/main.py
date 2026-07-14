"""FastAPI application factory for the Methodex public website.

PUBLIC-ONLY: `app.config` is imported FIRST here, which sets
METHODEX_PUBLIC_ONLY=1 before the methodex_mcp corpus loads. Every route serves
ONLY the 957-doc public-domain layer.

TELEMETRY: the Carson telemetry ASGI middleware (Layer-3 of the Carson Telemetry
Standard) is attached with service="methodex" — it auto-emits one usage_events
row per request (surface="download" for /download/*, else "rest"), with a hashed
client id, status, latency, and bytes. Privacy-first: no raw IP, no PII.

Usage:
    uvicorn app.main:app --reload --port 8080
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import config as C  # MUST be first project import (forces public-only)
from app import chrome  # Arcanum Site Kit (ASK) v1 — shared-chrome context processor

logger = logging.getLogger(__name__)


def _load_manifest_at_startup(app: FastAPI) -> None:
    """Load site_manifest.json into app.state. Non-fatal if not yet built."""
    mp = C.get_manifest_path()
    if mp.exists():
        try:
            with open(mp, encoding="utf-8") as f:
                app.state.manifest = json.load(f)
            cov = app.state.manifest.get("coverage", {})
            logger.info("Manifest loaded: %d docs, %d events, %d statistics",
                        cov.get("documents", 0), cov.get("events", 0),
                        cov.get("statistic_entities", 0))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load manifest: %s", exc)
            app.state.manifest = {}
    else:
        logger.info("site_manifest.json not found — run data_pipeline/build_cache.py")
        app.state.manifest = {}


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _load_manifest_at_startup(app)
    yield


def _asset_ver(static_dir) -> str:
    """Short content hash of the vendored kit (_shared) + site css/js — changes
    whenever any of those change, so ?v=<hash> busts the CDN cache on deploy."""
    import hashlib
    from pathlib import Path
    h = hashlib.md5()
    root = Path(static_dir)
    for sub in ("_shared", "css", "js"):
        d = root / sub
        if not d.exists():
            continue
        for p in sorted(d.rglob("*")):
            if p.is_file():
                try:
                    h.update(p.read_bytes())
                except Exception:  # noqa: BLE001
                    pass
    return h.hexdigest()[:8]


def _attach_telemetry(app: FastAPI) -> None:
    """Attach the Carson Layer-3 telemetry middleware (deploy gate). Non-fatal if
    the package is absent in a dev environment — the site still runs, but a clear
    warning is logged so the deploy gate is never silently skipped."""
    try:
        from carson_telemetry import telemetry
        app.add_middleware(telemetry.ASGIMiddleware, service=C.TELEMETRY_SERVICE)
        logger.info("carson-telemetry ASGIMiddleware attached (service=%s)", C.TELEMETRY_SERVICE)
    except Exception as exc:  # noqa: BLE001
        logger.warning("carson-telemetry NOT attached (%s) — install "
                       "'carson-telemetry[fastapi]' before deploy (telemetry is a deploy gate).", exc)


def create_app() -> FastAPI:
    C.ensure_dirs()

    app = FastAPI(
        title=f"{C.SITE_TITLE} — {C.SITE_TAGLINE}",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=_lifespan,
    )

    # Telemetry first (outermost middleware) so it times the whole request.
    _attach_telemetry(app)

    # Jinja2 templates
    # context_processors=[chrome.ark_context] injects the Arcanum Site Kit
    # shared-chrome vars (site_key, site_title, site_home, dpr_url, ecosystem,
    # nav) into EVERY TemplateResponse — no per-route changes needed.
    templates = Jinja2Templates(
        directory=str(C.TEMPLATES_DIR),
        context_processors=[chrome.ark_context],
    )
    templates.env.globals["site_title"] = C.SITE_TITLE
    templates.env.globals["tagline"] = C.SITE_TAGLINE
    templates.env.globals["umami_src"] = C.UMAMI_SRC
    templates.env.globals["umami_website_id"] = C.UMAMI_WEBSITE_ID
    # asset_ver: short content-hash of the vendored kit + site static, stamped as
    # ?v=<hash> on asset URLs so a kit/CSS/JS change busts the Cloudflare cache
    # automatically (the box has no CF purge token; kit assets are cached 4h).
    templates.env.globals["asset_ver"] = _asset_ver(C.STATIC_DIR)
    app.state.templates = templates

    # Static files
    app.mount("/static", StaticFiles(directory=str(C.STATIC_DIR)), name="static")

    # Routers (guarded so the app boots even if a router has an import issue)
    try:
        from app.routers import pages as pages_router
        app.include_router(pages_router.router)
    except Exception as exc:  # noqa: BLE001
        logger.warning("pages router unavailable: %s", exc)

    try:
        from app.routers import downloads as downloads_router
        app.include_router(downloads_router.router)
    except Exception as exc:  # noqa: BLE001
        logger.warning("downloads router unavailable: %s", exc)

    try:
        from app.routers import api as api_router
        app.include_router(api_router.router)
    except Exception as exc:  # noqa: BLE001
        logger.warning("api router unavailable: %s", exc)

    try:
        from app.routers import meta as meta_router
        app.include_router(meta_router.router)
    except Exception as exc:  # noqa: BLE001
        logger.warning("meta router unavailable: %s", exc)

    @app.get("/healthz", tags=["ops"])
    async def healthz(request: Request):  # noqa: ANN201
        manifest = getattr(request.app.state, "manifest", {})
        cov = manifest.get("coverage", {})
        # Fall back to live corpus counts if the manifest has not been loaded
        # (e.g. lifespan startup not run, or build_cache not yet executed).
        if not cov:
            from app.services import methodex_service as S
            st = S.status()
            cov = {
                "documents": st["documents"],
                "events": st["events"],
                "statistic_entities": st["statistic_entities"],
            }
        return JSONResponse({
            "status": "ok",
            "site": C.SITE_TITLE,
            "public_only": True,
            "manifest_present": bool(manifest),
            "documents": cov.get("documents", 0),
            "events": cov.get("events", 0),
            "statistics": cov.get("statistic_entities", 0),
        })

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8080, reload=False)
