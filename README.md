# Methodex

**The construction-and-revision history of every economic statistic.**

Methodex answers a question most data portals ignore: *what methodology
governed a statistic at a given point in time, and how did it change?* It is
both a **public website** and an **MCP server** ("Context7 for economic
methodology") that serves the documented lineage of how official economic
statistics are constructed and revised.

## Public-domain-only posture

This repository and both services serve **only the public-domain
US-federal-government layer** of the Methodex corpus:

- **957 documents / 392 revision events / 80 statistics / 14 measures.**
- Enforced two ways: (1) `METHODEX_PUBLIC_ONLY=1` is forced *at import time*
  (`webapp/app/config.py`, `src/methodex_mcp.py`) so the in-memory stores are
  physically filtered to `license == "US-Gov public domain"` before any tool or
  page can read them; and (2) the corpus state shipped in this repo
  (`Technical/campaign/state/*.json`) is **already pre-filtered to the
  public-domain subset** — no in-copyright, international, academic, or
  unclassified material is present on disk. The internal data-construction
  campaign (wishlists, discovery logs, event shards, build scripts) is **not**
  included.

## Architecture

Two services share one query layer:

| Service | Port | What it is |
|---|---|---|
| **methodex-web** | 8080 | FastAPI + Jinja2 + Plotly public website (`webapp/`). |
| **methodex-mcp** | 8000 | The 13 methodology tools over the **Streamable-HTTP** MCP transport at path `/mcp` (`src/methodex_mcp_http.py`). |

- The canonical tool logic lives once in **`src/methodex_mcp.py`**; the website
  services (`webapp/app/services/methodex_service.py`) and the MCP HTTP
  entrypoint both reuse it, so web and MCP answer identically.
- The website reads pre-built public-domain caches from
  `webapp/site_data/cache/*.parquet` and offers the packaged data at
  `webapp/site_data/downloads/methodex_public_data.zip`.
- Shared chrome under `*/static/_shared/` is **vendored from the Arcanum Site
  Kit** (see `VENDORED_FROM.txt`), included so the site builds standalone.
- Telemetry (Carson first-party analytics) is **optional** and not bundled; the
  app attaches it only if `carson-telemetry` is importable.

## The 13 MCP tools

| Tool | Purpose |
|---|---|
| `resolve_statistic(query)` | Resolve free text to canonical `statistic_id`(s). |
| `get_methodology(statistic_id, as_of_date)` | **The killer tool** — what methodology governed the statistic *then*. |
| `get_revision_history(statistic_id, from_year, to_year, verified_only)` | Ordered methodology revision events, optionally year-bounded. |
| `diff_methodology(statistic_id, date_a, date_b, verified_only)` | What changed in methodology between two dates. |
| `search_methodology(query, statistic_id, limit)` | Keyword search over event descriptions + document titles. |
| `get_document(md5)` | Full methodology-document record + provenance by md5. |
| `get_concept_history(concept)` | Every event touching a concept (e.g. `owners_equivalent_rent`, `hedonic`). |
| `get_table_history(table_id)` | How a published output table was defined over time (e.g. `BEA.NIPA.T1.1.5` = GDP). |
| `list_measures(statistic_id, section)` | List published tables/measures, optionally filtered. |
| `get_vintage_data(statistic_id, as_of_date)` | Cross-link methodology to the underlying data vintage (ALFRED/FRED). |
| `get_methodology_timeline(statistic_id, fmt)` | Render a statistic's methodology history oldest→newest. |
| `methodex_status(statistic_id)` | Coverage + quality snapshot of the graph, or a per-statistic data card. |
| `semantic_search(query, limit, statistic_id)` | TF-IDF cosine ranking over events + document titles. |

Every response carries provenance (governing-document md5 + page citation).

## Endpoints

- **Website** (methodex-web, `:8080`): `/` home, `/explore`, `/statistic/{id}`,
  `/methodology`, `/data`, `/docs`, `/code`, `/about`, plus a JSON API under
  `/api/*`, downloads under `/downloads/*`, and `/static/llms.txt`.
- **MCP** (methodex-mcp, `:8000`): Streamable-HTTP at **`/mcp`**. No live API
  keys; public-domain US-Gov data only.

## Run it

```bash
docker compose up --build
# website:  http://localhost:8080
# MCP:      http://localhost:8000/mcp  (streamable-http)
```

Locally (Python 3.13):

```bash
# website
pip install -r webapp/requirements.txt
PYTHONPATH="webapp:src" METHODEX_PUBLIC_ONLY=1 \
  gunicorn app.main:app --chdir webapp -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8080

# MCP server
pip install -r webapp/requirements.txt "mcp>=1.9.0"
PYTHONPATH="src" METHODEX_PUBLIC_ONLY=1 python src/methodex_mcp_http.py

# CLI demo (no server)
METHODEX_PUBLIC_ONLY=1 python src/methodex_mcp.py demo
```

## License

MIT (provisional — final license pending decision **E-3**). See `LICENSE`.
