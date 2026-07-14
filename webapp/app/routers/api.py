"""JSON API endpoints for the Methodex public website (the data-scientist surface).

All routes are public-domain-only (data flows through methodex_service).

GET /api/ping                          liveness
GET /api/resolve?q=                    free-text -> statistic_id matches
GET /api/statistic/{id}                statistic data card (status + governing docs)
GET /api/statistic/{id}/timeline       Plotly figure JSON for the revision timeline
GET /api/statistic/{id}/events         the public revision events (JSON)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.services import methodex_service as S

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["api"])


@router.get("/ping")
def ping() -> JSONResponse:
    return JSONResponse({"ok": True, "public_only": True})


@router.get("/coverage")
def coverage() -> JSONResponse:
    """Real corpus-coverage roll-ups for the landing default chart.

    Computed live from the public-only store (methodex_service), so the numbers
    always match what the rest of the site renders. Returns:
      - top_statistics: the statistics with the most cited revision events
      - by_family:      cited revision events summed per statistic family
      - n_total_events / n_statistics: headline totals
    Nothing is invented — every count is len()/sum() over real public events.
    """
    stats = S.statistics_with_events()
    by_family: dict[str, int] = {}
    for s in stats:
        by_family[s["family"]] = by_family.get(s["family"], 0) + s["n_events"]
    families = sorted(
        ({"family": f, "events": n} for f, n in by_family.items()),
        key=lambda x: (-x["events"], x["family"]),
    )
    top = sorted(stats, key=lambda s: (-s["n_events"], s["name"]))[:15]
    top_statistics = [
        {"name": s["name"], "statistic_id": s["statistic_id"],
         "family": s["family"], "n_events": s["n_events"]}
        for s in top
    ]
    return JSONResponse({
        "top_statistics": top_statistics,
        "by_family": families,
        "n_total_events": sum(s["n_events"] for s in stats),
        "n_statistics": len(stats),
    })


@router.get("/resolve")
def resolve(q: str = Query(default="")) -> JSONResponse:
    return JSONResponse(S.resolve_statistic(q))


@router.get("/statistic/{statistic_id}")
def statistic_card(statistic_id: str) -> JSONResponse:
    card = S.status(statistic_id)
    if not card.get("has_entity"):
        raise HTTPException(status_code=404, detail=f"no public statistic '{statistic_id}'")
    card["governing_documents"] = S.governing_documents(statistic_id)
    return JSONResponse(card)


@router.get("/statistic/{statistic_id}/timeline")
def statistic_timeline(statistic_id: str) -> JSONResponse:
    if not S.get_statistic(statistic_id):
        raise HTTPException(status_code=404, detail=f"no public statistic '{statistic_id}'")
    try:
        tl = S.timeline_figure(statistic_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("timeline build failed for %r", statistic_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse({"figure": tl["figure"], "name": tl["name"],
                         "n_dated": tl["n_dated"], "n_undated": tl["n_undated"]})


@router.get("/statistic/{statistic_id}/events")
def statistic_events(statistic_id: str) -> JSONResponse:
    if not S.get_statistic(statistic_id):
        raise HTTPException(status_code=404, detail=f"no public statistic '{statistic_id}'")
    return JSONResponse(S.get_revision_history(statistic_id))
