"""HTML page routes (server-rendered Jinja2) for the Methodex public website.

Routes
------
GET /                       landing — what Methodex is + the killer query
GET /explore               methodology explorer — search/pick a statistic
GET /statistic/{id}        one statistic: Plotly revision timeline + governing docs
GET /docs                  the public-domain methodology documents catalogue
GET /about                 project + public-only guarantee + telemetry note

Every data view links to a download and a view-the-code link.
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse

from app import config as C
from app.services import methodex_service as S

router = APIRouter(tags=["pages"])


def _t(request: Request):
    return request.app.state.templates


def _ctx(request: Request, **kw) -> dict:
    base = {"request": request, "site_title": C.SITE_TITLE, "tagline": C.SITE_TAGLINE}
    base.update(kw)
    return base


def _served_status(statistic_id: str | None = None) -> dict:
    """methodex_status(), but with `statistics_with_events` reconciled to the
    SERVED/browsable count (MXD-1).

    The raw MCP `methodex_status` counts distinct statistic_ids referenced by
    events (= 59): 7 of those have events but no statistic-entity record, so they
    are NOT enumerated, browsable, or downloadable on this site. Every served
    surface (Explore rows, statistics.csv, the manifest `statistics[]`) shows the
    52 statistics that DO have an entity record. We display those two honest
    denominators — "52 with served data · 80 catalogued" — and never surface the
    59 event-id tally (which remains the MCP tool's own documented denominator)."""
    st = dict(S.status(statistic_id))
    st["statistics_with_events"] = len(S.statistics_with_events())
    return st


# ---------------------------------------------------------------------------
# Landing
# ---------------------------------------------------------------------------
@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    st = _served_status()
    return _t(request).TemplateResponse(
        request, "home.html",
        _ctx(request, section="Home",
             n_documents=st["documents"], n_events=st["events"],
             n_statistics=st["statistic_entities"],
             n_statistics_live=st["statistics_with_events"],
             n_verified=st["verified_events"]),
    )


# ---------------------------------------------------------------------------
# Methodology explorer
# ---------------------------------------------------------------------------
@router.get("/explore", response_class=HTMLResponse)
def explore(request: Request, q: str = Query(default=""), family: str = Query(default="")):
    stats = S.statistics_with_events()
    if family:
        stats = [s for s in stats if s["family"] == family]
    if q:
        ql = q.lower().strip()
        stats = [s for s in stats
                 if ql in s["name"].lower()
                 or ql in s["statistic_id"].lower()
                 or any(ql in a.lower() for a in s.get("aliases", []))]
    return _t(request).TemplateResponse(
        request, "explore.html",
        _ctx(request, section="Explore", statistics=stats,
             families=S.families(), q=q, active_family=family,
             n_total=len(S.statistics_with_events())),
    )


# ---------------------------------------------------------------------------
# Statistic detail — timeline + governing documents
# ---------------------------------------------------------------------------
@router.get("/statistic/{statistic_id}", response_class=HTMLResponse)
def statistic(request: Request, statistic_id: str):
    stat = S.get_statistic(statistic_id)
    if not stat:
        return _t(request).TemplateResponse(
            request, "not_found.html",
            _ctx(request, section="Explore",
                 message=f"No public statistic '{statistic_id}'."),
            status_code=404,
        )
    tl = S.timeline_figure(statistic_id)
    govs = S.governing_documents(statistic_id)
    return _t(request).TemplateResponse(
        request, "statistic.html",
        _ctx(request, section="Explore", stat=stat,
             figure=tl["figure"], events=tl["events"],
             n_dated=tl["n_dated"], n_undated=tl["n_undated"],
             governing_documents=govs,
             timeline_md=S.get_methodology_timeline(statistic_id, "markdown")["timeline"]),
    )


# ---------------------------------------------------------------------------
# Documents catalogue (public-domain only)
# ---------------------------------------------------------------------------
_DOCS_PAGE_SIZE = 100


@router.get("/docs", response_class=HTMLResponse)
def docs(request: Request, q: str = Query(default=""),
         producer: str = Query(default=""), page: int = Query(default=1, ge=1)):
    import methodex_mcp as M
    rows = []
    for d in M.DOCSL:
        rows.append(M._doc_view(d))
    producers = sorted({(r.get("producer") or "?") for r in rows})
    n_corpus = len(rows)
    if producer:
        rows = [r for r in rows if (r.get("producer") or "?") == producer]
    if q:
        ql = q.lower().strip()
        rows = [r for r in rows if ql in (r.get("title") or "").lower()]
    rows.sort(key=lambda r: (r.get("publication_date") or ""), reverse=True)

    n_matched = len(rows)
    n_pages = max(1, -(-n_matched // _DOCS_PAGE_SIZE))  # ceil
    page = min(page, n_pages)
    start = (page - 1) * _DOCS_PAGE_SIZE
    page_rows = rows[start:start + _DOCS_PAGE_SIZE]

    return _t(request).TemplateResponse(
        request, "docs.html",
        _ctx(request, section="Docs", documents=page_rows,
             n_shown=len(page_rows), n_total=n_matched, n_corpus=n_corpus,
             producers=producers, q=q, active_producer=producer,
             page=page, n_pages=n_pages, page_size=_DOCS_PAGE_SIZE,
             page_first=start + 1 if page_rows else 0,
             page_last=start + len(page_rows)),
    )


# ---------------------------------------------------------------------------
# Data — downloads landing over the real public corpus (schema notes + manifest)
# ---------------------------------------------------------------------------
# Field-level schema notes for the three real public datasets. Every field name
# below is exactly what download_service emits (see _statistics_frame /
# _events_frame / _documents_frame) — no invented columns.
_DATASETS = [
    {
        "id": "statistics", "title": "Statistics",
        "desc": "One row per public statistic entity that has at least one cited "
                "revision event.",
        "csv": "/download/statistics.csv",
        "filter": "?statistic_id=US.BLS.CPI_U",
        "fields": [
            ("statistic_id", "Canonical id, e.g. US.BLS.CPI_U"),
            ("name", "Human-readable statistic name"),
            ("family", "Subject family (prices, labor, national_accounts, …)"),
            ("producer_id", "Issuing agency (BLS, BEA, Census, FederalReserve, …)"),
            ("geography", "Geographic scope where recorded"),
            ("first_published", "Year/date first published, where known"),
            ("data_vintage_source", "ALFRED/FRED real-time vintage pointer, where linked"),
            ("aliases", "Semicolon-separated alternate names"),
            ("n_events", "Count of cited revision events for this statistic"),
        ],
    },
    {
        "id": "revision_events", "title": "Revision events",
        "desc": "One row per cited methodology change, each tied to a governing "
                "document + page citation.",
        "csv": "/download/revision_events.csv",
        "filter": "?statistic_id=US.BEA.GDP.REAL",
        "fields": [
            ("event_id", "Stable event identifier"),
            ("statistic_id", "Statistic this change applies to"),
            ("effective_date", "Date the change took effect, where known"),
            ("effective_year", "Effective year (used for the timeline axis)"),
            ("type", "Change type (definition, classification, coverage, base-year, …)"),
            ("description", "What changed, transcribed from the governing document"),
            ("magnitude", "Qualitative/quantitative size, where stated"),
            ("direction", "Direction of the change, where stated"),
            ("concept_ids", "Semicolon-separated affected concept ids"),
            ("governing_document", "Title of the manual/handbook edition in force"),
            ("governing_document_md5", "MD5 of that governing document"),
            ("page", "Page citation within the governing document"),
            ("verified", "True where adversarially verified"),
        ],
    },
    {
        "id": "documents", "title": "Governing documents",
        "desc": "One row per public-domain governing manual, handbook, or release "
                "in the served layer.",
        "csv": "/download/documents.csv",
        "filter": None,
        "fields": [
            ("md5", "Content hash (document identity + citation key)"),
            ("title", "Document title"),
            ("producer_id", "Issuing US-federal agency"),
            ("doc_type", "Manual, handbook, release, …"),
            ("edition", "Edition / vintage label"),
            ("publication_date", "Publication date, where known"),
            ("geography", "Geographic scope"),
            ("statistic_ids", "Semicolon-separated statistics this document governs"),
            ("license", "Always 'US-Gov public domain' (17 U.S.C. §105)"),
        ],
    },
]


@router.get("/data", response_class=HTMLResponse)
def data_page(request: Request):
    st = _served_status()
    return _t(request).TemplateResponse(
        request, "data.html",
        _ctx(request, section="Data", datasets=_DATASETS, status=st),
    )


# ---------------------------------------------------------------------------
# Code — the real site + MCP source, with copy buttons + a repro bundle
# ---------------------------------------------------------------------------
@router.get("/code", response_class=HTMLResponse)
def code_page(request: Request):
    st = _served_status()
    return _t(request).TemplateResponse(
        request, "code.html",
        _ctx(request, section="Code", status=st),
    )


# ---------------------------------------------------------------------------
# Methodology — the standard DPR / provenance panel (footer dpr_url target)
# ---------------------------------------------------------------------------
def _read_dpr() -> str:
    """The on-disk Deployment Provenance Record (deploy/methodex/DPR.md), verbatim."""
    p = C.PROJECT_ROOT / "DPR.md"
    try:
        return p.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001 — methodology page must render even without it
        return ""


@lru_cache(maxsize=1)
def _render_dpr_html() -> str:
    """Render the DPR markdown -> HTML (server-side) so the page NEVER shows
    literal ``##``/``|tables|``/``**`` markup (kit v1.1 markdown-safety rule).
    Uses markdown-it-py (the kit-standard renderer, as in leontief/mdata's
    narrative_service). If the renderer is unavailable, returns "" so the
    template's ``{% if dpr_html %}`` guard simply omits the block — no literal
    markdown ever reaches the page."""
    text = _read_dpr()
    if not text.strip():
        return ""
    try:
        from markdown_it import MarkdownIt
    except Exception:  # noqa: BLE001 — render must degrade, never crash
        return ""
    md = MarkdownIt("commonmark", {"html": False, "typographer": True}).enable(["table"])
    return md.render(text)


@router.get("/methodology", response_class=HTMLResponse)
def methodology(request: Request):
    st = _served_status()
    return _t(request).TemplateResponse(
        request, "methodology.html",
        _ctx(request, section="Methodology", status=st,
             families=S.families(), dpr_html=_render_dpr_html()),
    )


# ---------------------------------------------------------------------------
# About
# ---------------------------------------------------------------------------
@router.get("/about", response_class=HTMLResponse)
def about(request: Request):
    st = _served_status()
    return _t(request).TemplateResponse(
        request, "about.html",
        _ctx(request, section="About", status=st),
    )
