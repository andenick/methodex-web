"""Download exporters for the Methodex public website.

Serves the PUBLIC revision events, statistics, and documents as CSV, plus
a single combined ZIP bundle. All data flows through methodex_service (which is
public-only), so no in-copyright content can be exported.

Each exporter returns (raw_bytes, media_type, filename).
"""
from __future__ import annotations

import io
import json
import zipfile

import pandas as pd

from app import config as C  # noqa: F401  (forces public-only)
from app.services import methodex_service as S
import methodex_mcp as M


_CSV = "text/csv; charset=utf-8"
_JSON = "application/json; charset=utf-8"


# ---------------------------------------------------------------------------
# Frame builders (mirror build_cache, but live so a fresh export is always
# consistent with what the site renders even if the cache is stale).
# ---------------------------------------------------------------------------
def _statistics_frame(statistic_id: str | None = None) -> pd.DataFrame:
    rows = []
    for s in S.statistics_with_events():
        if statistic_id and s["statistic_id"] != statistic_id:
            continue
        rows.append({
            "statistic_id": s["statistic_id"], "name": s["name"], "family": s["family"],
            "producer_id": s.get("producer_id"), "geography": s.get("geography"),
            "first_published": s.get("first_published"),
            "data_vintage_source": s.get("data_vintage_source"),
            "aliases": "; ".join(s.get("aliases", [])), "n_events": s["n_events"],
        })
    return pd.DataFrame(rows)


def _events_frame(statistic_id: str | None = None) -> pd.DataFrame:
    rows = []
    for e in M.EVENTSL:
        if statistic_id and e["statistic_id"] != statistic_id:
            continue
        ev = M._event_view(e)
        cite = ev.get("citation") or {}
        rows.append({
            "event_id": ev["event_id"], "statistic_id": ev["statistic_id"],
            "effective_date": ev.get("effective_date"),
            "effective_year": ev.get("effective_year"), "type": ev.get("type"),
            "description": ev.get("description"), "magnitude": ev.get("magnitude"),
            "direction": ev.get("direction"),
            "concept_ids": "; ".join(ev.get("concept_ids", [])),
            "governing_document": cite.get("document"),
            "governing_document_md5": cite.get("md5"), "page": cite.get("page"),
            "verified": bool(ev.get("verified")),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["statistic_id", "effective_year"], na_position="last")
    return df


def _documents_frame() -> pd.DataFrame:
    rows = []
    for d in M.DOCSL:
        prov = d.get("provenance") or {}
        rows.append({
            "md5": d["md5"], "title": d.get("title"), "producer_id": d.get("producer_id"),
            "doc_type": d.get("doc_type"), "edition": d.get("edition"),
            "publication_date": d.get("publication_date"), "geography": d.get("geography"),
            "statistic_ids": "; ".join(d.get("statistic_ids") or []),
            "license": prov.get("license"),
        })
    return pd.DataFrame(rows)


_FRAMES = {
    "statistics": _statistics_frame,
    "revision_events": _events_frame,
    "documents": _documents_frame,
}


def export_dataset(name: str, fmt: str, statistic_id: str | None = None):
    """Export a named public dataset as csv. Raises KeyError/ValueError.

    DNA: CSV only for user-facing downloads — JSON is not a published format.
    """
    if name not in _FRAMES:
        raise KeyError(f"unknown dataset '{name}' (have: {sorted(_FRAMES)})")
    if fmt != "csv":
        raise ValueError(f"unsupported format '{fmt}' (csv)")

    builder = _FRAMES[name]
    df = builder(statistic_id) if name in ("statistics", "revision_events") else builder()

    suffix = f"_{statistic_id}" if statistic_id else ""
    raw = df.to_csv(index=False).encode("utf-8")
    return raw, _CSV, f"methodex_{name}{suffix}.csv"


def export_bundle():
    """The public-data ZIP bundle.

    Prefers the prebuilt, reproducible artifact at
    site_data/downloads/methodex_public_data.zip (built by the kit make_bundles.py:
    the three datasets + data dictionary + provenance + license, with a
    BUNDLE_MANIFEST.csv whose TOTAL size is the on-page `cdf.data.size` label).
    Falls back to a live-packaged zip if the artifact is absent, so the route
    never 404s in a fresh dev checkout."""
    prebuilt = C.DOWNLOADS_DIR / "methodex_public_data.zip"
    if prebuilt.exists():
        return prebuilt.read_bytes(), "application/zip", "methodex_public_data.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in _FRAMES:
            for fmt in ("csv",):
                raw, _media, fn = export_dataset(name, fmt)
                z.writestr(fn, raw)
        readme = (
            "Methodex — public-domain methodology data bundle\n"
            "=================================================\n\n"
            f"License of all contents: {C.PUBLIC_DOMAIN_LICENSE} (17 U.S.C. sec.105).\n"
            "Scope: ONLY the public-domain US-federal-government layer of the Methodex\n"
            "corpus (957 documents / 392 revision events / 80 statistics). No\n"
            "in-copyright, international, academic, or UNKNOWN-producer material is\n"
            "included.\n\n"
            "Files:\n"
            "  methodex_statistics.csv       one row per statistic\n"
            "  methodex_revision_events.csv  one row per methodology change\n"
            "  methodex_documents.csv        one row per governing document\n\n"
            "Code: https://github.com/andenick/methodex-web\n"
            "Site: https://methodex.fyi   MCP: mcp.methodex.fyi (13 tools)\n"
        )
        z.writestr("README.txt", readme.encode("utf-8"))
    return buf.getvalue(), "application/zip", "methodex_public_data.zip"


# ---------------------------------------------------------------------------
# Machine-readable manifest (the public coverage descriptor the /data page links)
# ---------------------------------------------------------------------------
def export_manifest():
    """Return the public site manifest as JSON bytes (the machine-readable
    descriptor of what the public layer contains). Served verbatim from disk
    when ``site_manifest.json`` exists; otherwise rebuilt live from the public
    store so the endpoint never 404s. Public-domain coverage metadata only."""
    mp = C.get_manifest_path()
    if mp.exists():
        raw = mp.read_bytes()
        return raw, _JSON, "methodex_manifest.json"
    # Live fallback (manifest not yet built) — coverage + statistics index.
    st = S.status()
    stats = S.statistics_with_events()
    manifest = {
        "public_only": True,
        "license": C.PUBLIC_DOMAIN_LICENSE,
        "coverage": {
            "documents": st["documents"],
            "events": st["events"],
            "statistic_entities": st["statistic_entities"],
            "statistics_with_events": st["statistics_with_events"],
            "measures": st.get("measures", 0),
            "verified_events": st.get("verified_events", 0),
            "families": S.families(),
        },
        "statistics": [
            {"statistic_id": s["statistic_id"], "name": s["name"],
             "family": s["family"], "producer_id": s.get("producer_id"),
             "n_events": s["n_events"]}
            for s in stats
        ],
    }
    raw = json.dumps(manifest, indent=1, ensure_ascii=False).encode("utf-8")
    return raw, _JSON, "methodex_manifest.json"


# ---------------------------------------------------------------------------
# Site reproduction bundle — the actual webapp + MCP source (so the public site
# is reproducible from disk). Real source files only; no data secrets.
# ---------------------------------------------------------------------------
_REPRO_README = """Methodex — public site reproduction bundle
==========================================

This is the actual source of the methodex.fyi public website: a FastAPI + Jinja +
(vendored) Plotly app that serves ONLY the public-domain US-federal layer of the
Methodex corpus (957 docs / 392 revision events / 80 statistics), plus the
canonical query module (src/methodex_mcp.py) that powers both the site and the
sibling MCP server.

Run the website
---------------
    pip install -r webapp/requirements.txt
    cd webapp && uvicorn app.main:app --port 8080
    # then open http://localhost:8080

Run the MCP server (same corpus, 13 tools)
------------------------------------------
    pip install mcp
    python src/methodex_mcp_http.py        # streamable-HTTP MCP on /mcp

Public-only guarantee
---------------------
app/config.py sets METHODEX_PUBLIC_ONLY=1 at import time BEFORE methodex_mcp loads,
so the in-memory stores are physically filtered to public-domain documents and
their events. methodex_service.py asserts every loaded doc is "US-Gov public
domain" and fails closed otherwise. There is no per-tool opt-out.

Run-it / get-identical-output
-----------------------------
Every /download/* payload and every /api/* response is computed deterministically
from the canonical state under Technical/campaign/state/ — no network call, no
random seed. The site_manifest.json coverage descriptor (served at
/metadata/manifest.json) and the CSV exports regenerate byte-for-byte from the same
store. NOT included in this bundle: the raw campaign corpus and any in-copyright
material (digest-only, never served).
"""

# Real source files that constitute the reproducible site (relative to WEBAPP_ROOT).
_REPRO_SOURCES = [
    "requirements.txt",
    "app/__init__.py",
    "app/main.py",
    "app/config.py",
    "app/chrome.py",
    "app/routers/__init__.py",
    "app/routers/pages.py",
    "app/routers/downloads.py",
    "app/routers/api.py",
    "app/services/__init__.py",
    "app/services/methodex_service.py",
    "app/services/download_service.py",
    "app/templates/base.html",
    "app/templates/home.html",
    "app/templates/explore.html",
    "app/templates/statistic.html",
    "app/templates/docs.html",
    "app/templates/about.html",
    "app/templates/data.html",
    "app/templates/code.html",
    "app/templates/methodology.html",
    "app/templates/not_found.html",
    "app/templates/_shared/header.html",
    "app/templates/_shared/footer.html",
]


def export_site_repro():
    """Zip the REAL app + MCP source so the public site is reproducible from disk."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in _REPRO_SOURCES:
            p = C.WEBAPP_ROOT / rel
            if p.exists():
                z.write(p, f"webapp/{rel}")
        # The canonical query module shared by the site + the MCP server.
        for rel in ("methodex_mcp.py", "methodex_mcp_http.py"):
            p = C.PROJECT_ROOT / "src" / rel
            if p.exists():
                z.write(p, f"src/{rel}")
        z.writestr("README.txt", _REPRO_README.encode("utf-8"))
    return buf.getvalue(), "application/zip", "methodex_site_repro.zip"
