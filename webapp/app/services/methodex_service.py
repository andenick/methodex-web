"""Methodex query-logic bridge.

REUSES the canonical query logic from src/methodex_mcp.py rather than
re-implementing it. We import app.config FIRST (which forces
METHODEX_PUBLIC_ONLY=1), then add src/ to sys.path and import the MCP module.
Because methodex_mcp filters its in-memory stores ONCE at import time based on
that env var, every function it exposes (resolve_statistic, get_methodology,
get_revision_history, get_methodology_timeline, methodex_status, …) is
physically restricted to the 957-doc public-domain layer.

This module is the ONLY place the webapp touches the corpus, so the public-only
guarantee has a single chokepoint.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from typing import Any

from app import config as C  # noqa: F401  (import-for-side-effect: forces public-only)

# Make src/methodex_mcp.py importable.
if str(C.SRC_DIR) not in sys.path:
    sys.path.insert(0, str(C.SRC_DIR))

import methodex_mcp as M  # noqa: E402

# Hard assertion: the bridge must be in public-only mode. If this ever fails,
# the import order is wrong and we would risk serving in-copyright content.
assert M.PUBLIC_ONLY, (
    "methodex_mcp loaded WITHOUT public-only mode — refusing to serve. "
    "app.config must be imported before methodex_mcp."
)
assert all(
    (d.get("provenance") or {}).get("license") == C.PUBLIC_DOMAIN_LICENSE
    for d in M.DOCSL
), "Non-public document found in the loaded store — public carve breached."


# ---------------------------------------------------------------------------
# Thin pass-throughs to the canonical query logic
# ---------------------------------------------------------------------------

def resolve_statistic(query: str) -> dict[str, Any]:
    return M.resolve_statistic(query)


def get_methodology(statistic_id: str, as_of_date: Any) -> dict[str, Any]:
    return M.get_methodology(statistic_id, as_of_date)


def get_revision_history(statistic_id: str, from_year=None, to_year=None,
                         verified_only: bool = False) -> dict[str, Any]:
    return M.get_revision_history(statistic_id, from_year, to_year, verified_only)


def get_methodology_timeline(statistic_id: str, fmt: str = "markdown") -> dict[str, Any]:
    return M.get_methodology_timeline(statistic_id, fmt)


def get_document(md5: str) -> dict[str, Any]:
    return M.get_document(md5)


def status(statistic_id: str | None = None) -> dict[str, Any]:
    return M.methodex_status(statistic_id)


# ---------------------------------------------------------------------------
# Higher-level helpers for the website
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def all_statistics() -> list[dict[str, Any]]:
    """Every public statistic ENTITY that has at least one public event, sorted
    by event count desc then name. (Statistics with zero public events are still
    in M.STATSL but are not browsable, so we surface the ones that have history.)"""
    counts: dict[str, int] = {}
    for e in M.EVENTSL:
        counts[e["statistic_id"]] = counts.get(e["statistic_id"], 0) + 1
    out = []
    for s in M.STATSL:
        sid = s["statistic_id"]
        n = counts.get(sid, 0)
        out.append({
            "statistic_id": sid,
            "name": s.get("name", sid),
            "family": s.get("family", "other"),
            "producer_id": s.get("producer_id"),
            "geography": s.get("geography"),
            "aliases": s.get("aliases", []),
            "first_published": s.get("first_published"),
            "data_vintage_source": s.get("data_vintage_source"),
            "n_events": n,
        })
    out.sort(key=lambda x: (-x["n_events"], x["name"]))
    return out


def statistics_with_events() -> list[dict[str, Any]]:
    """Only the statistics that have >=1 public revision event (browsable)."""
    return [s for s in all_statistics() if s["n_events"] > 0]


def families() -> list[dict[str, Any]]:
    """Distinct statistic families with counts (for the explorer facets)."""
    by_fam: dict[str, int] = {}
    for s in statistics_with_events():
        by_fam[s["family"]] = by_fam.get(s["family"], 0) + 1
    return sorted(
        ({"family": f, "n": n} for f, n in by_fam.items()),
        key=lambda x: (-x["n"], x["family"]),
    )


def get_statistic(statistic_id: str) -> dict[str, Any] | None:
    for s in all_statistics():
        if s["statistic_id"] == statistic_id:
            return s
    return None


def governing_documents(statistic_id: str) -> list[dict[str, Any]]:
    """Public governing/handbook/manual documents tied to a statistic, newest first."""
    out = []
    for d in M.DOCSL:
        if statistic_id not in (d.get("statistic_ids") or []) and not M._doc_matches_stat(d, statistic_id):
            continue
        out.append(M._doc_view(d))
    out.sort(key=lambda d: (d.get("publication_date") or ""), reverse=True)
    return out


def timeline_figure(statistic_id: str) -> dict[str, Any]:
    """Build a Plotly figure dict (server-side) for a statistic's revision
    timeline. Each public revision event becomes a point on a horizontal time
    axis, colored by event type, with the governing-document citation in the
    hover. Returns {"figure": <plotly json>, "events": [...], "name": str}.
    """
    import plotly.graph_objects as go

    hist = get_revision_history(statistic_id)
    events = hist["events"]
    stat = get_statistic(statistic_id)
    name = stat["name"] if stat else statistic_id

    # Only dated events can be placed on the time axis.
    dated = [e for e in events if e.get("effective_year")]
    undated = [e for e in events if not e.get("effective_year")]

    # One trace per event type. v1.1: NO per-trace colors — each type is its own
    # trace, so the Arcanum Site Kit colorway (ark-plotly.js, accent-led and
    # dark-aware) colors them distinctly and re-themes on the light/dark toggle.
    types = sorted({e["type"] for e in dated})

    fig = go.Figure()
    for t in types:
        pts = [e for e in dated if e["type"] == t]
        fig.add_trace(go.Scatter(
            x=[e["effective_year"] for e in pts],
            y=[t for _ in pts],
            mode="markers",
            name=t,
            marker=dict(size=12),
            customdata=[[
                e["event_id"],
                (e.get("description") or "")[:240],
                (e.get("citation") or {}).get("document", ""),
                "verified" if e.get("verified") else "unverified",
            ] for e in pts],
            hovertemplate=(
                "<b>%{x}</b> · " + t +
                "<br>%{customdata[1]}"
                "<br><i>src: %{customdata[2]}</i>"
                "<br>(%{customdata[3]})<extra></extra>"
            ),
        ))

    # THEME-NEUTRAL layout: transparent backgrounds, NO imposed font/grid color.
    # ark-plotly.js (client-side) supplies font/grid/colorway from the --ark-*
    # tokens and re-themes live on the toggle. We only fix structure here.
    fig.update_layout(
        title=f"Methodology revision timeline — {name}",
        xaxis=dict(title="Effective year", tickformat="d", showgrid=True),
        yaxis=dict(title="", automargin=True),
        height=max(280, 90 + 46 * max(1, len(types))),
        margin=dict(l=20, r=20, t=48, b=64),
        # legend BELOW the plot (DNA Universal Graph Contract) — was y=1.02 (on top)
        legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="left", x=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(align="left"),
    )

    return {
        "figure": fig.to_plotly_json(),
        "events": events,
        "name": name,
        "n_dated": len(dated),
        "n_undated": len(undated),
    }
