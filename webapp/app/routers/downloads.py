"""Download routes for the Methodex public website.

All routes live under /download/* so the Carson telemetry middleware records
them as surface="download". Every payload is the PUBLIC-DOMAIN layer only.

GET /download/statistics.csv
GET /download/revision_events.csv      (optional ?statistic_id=US.BLS.CPI_U)
GET /download/documents.csv
GET /download/bundle.zip                        all three datasets + README
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse, Response

from app.services import download_service as DL

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/download", tags=["download"])


def _attach(raw: bytes, media: str, filename: str) -> Response:
    # no-store so the CDN revalidates against the origin: these payloads are
    # generated live from the store (and the bundle size is the on-page
    # `cdf.data.size` label), so a stale edge copy would silently disagree with
    # the manifest after a redeploy. Correctness over edge-caching for downloads.
    return Response(content=raw, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"',
                             "Cache-Control": "no-store"})


# /bundle.zip is declared BEFORE /{dataset}.{fmt} so "bundle.zip" is not parsed
# as dataset="bundle", fmt="zip" (which would 404). Starlette matches in
# declaration order.
@router.get("/bundle.zip")
def bundle() -> Response:
    """The full public-data ZIP bundle (all datasets, CSV, README)."""
    try:
        raw, media, filename = DL.export_bundle()
    except Exception as exc:  # noqa: BLE001
        logger.exception("bundle download failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _attach(raw, media, filename)


@router.get("/manifest.json")
def manifest() -> RedirectResponse:
    """The coverage manifest is metadata, not a dataset download — it moved to
    /metadata/manifest.json (DOWNLOAD_AND_FORMATS DNA: no JSON under /download/*).
    Permanent-redirect the old path so existing links keep working."""
    return RedirectResponse(url="/metadata/manifest.json", status_code=308)


@router.get("/site_repro.zip")
def site_repro() -> Response:
    """The real webapp + MCP source bundle (reproducible-from-disk)."""
    try:
        raw, media, filename = DL.export_site_repro()
    except Exception as exc:  # noqa: BLE001
        logger.exception("site_repro download failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _attach(raw, media, filename)


@router.get("/{dataset}.{fmt}")
def dataset_download(dataset: str, fmt: str,
                     statistic_id: str | None = Query(default=None)) -> Response:
    """Download a named public dataset (statistics | revision_events | documents)
    as csv. revision_events and statistics accept ?statistic_id= filter."""
    try:
        raw, media, filename = DL.export_dataset(dataset, fmt, statistic_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("dataset_download failed dataset=%r fmt=%r", dataset, fmt)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _attach(raw, media, filename)
