#!/usr/bin/env python3
"""
Methodex MCP server (T1.6 — MVP vertical slice).

Serves the construction-and-revision history of economic statistics to an LLM.
Pure-Python tool functions over the canonical state (registry + events + text dumps);
exposed as MCP tools if the `mcp` package is installed, else importable directly and
runnable as a CLI demo (`python Methodex_mcp.py demo`).

Killer tool: get_methodology(statistic_id, as_of_date) — what governed the statistic THEN.
Every response carries provenance (governing doc md5 + page citation).
"""
import csv, json, math, os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Technical", "campaign", "state"))
DOCS = os.path.join(ROOT, "methodology_documents.json")
EVENTS = os.path.join(ROOT, "revision_events.json")
STATS = os.path.join(ROOT, "statistics.json")
CLASSIFIED = os.path.normpath(os.path.join(ROOT, "..", "classified", "corpus_classified.csv"))


# ---------------------------------------------------------------------------
# PUBLIC-ONLY serving mode (deliverable M2).
#
# When enabled, EVERY tool sees ONLY public-domain US-federal-government material
# (documents whose provenance.license == PUBLIC_DOMAIN_LICENSE) and the events /
# measures derived from them. No INTL / academic / UNKNOWN content can appear in
# ANY tool output. This is the posture the HOSTED public instance runs in.
#
#   - Default (env unset / flag absent): full corpus — the internal/research tool.
#   - Enabled: env METHODEX_PUBLIC_ONLY=1 (the hosted instance sets this) OR the
#     `--public-only` CLI flag.
#
# Implementation: filter the canonical in-memory stores ONCE at load time so the
# whole module — every tool, every index, the semantic index, demo, CLI — is
# physically restricted. There is no per-tool opt-in to forget; a tool cannot
# leak a non-public doc because the non-public docs are not in memory.
# ---------------------------------------------------------------------------
PUBLIC_DOMAIN_LICENSE = "US-Gov public domain"


def _public_only_enabled(argv=None):
    """True iff public-only serving mode is on (env METHODEX_PUBLIC_ONLY=1 or --public-only)."""
    if os.environ.get("METHODEX_PUBLIC_ONLY", "").strip() in ("1", "true", "True", "yes", "on"):
        return True
    av = sys.argv if argv is None else argv
    return "--public-only" in av


def _doc_is_public(d):
    return ((d.get("provenance") or {}).get("license")) == PUBLIC_DOMAIN_LICENSE


def _load():
    docs = json.load(open(DOCS, encoding="utf-8")) if os.path.exists(DOCS) else []
    events = json.load(open(EVENTS, encoding="utf-8")) if os.path.exists(EVENTS) else []
    stats = json.load(open(STATS, encoding="utf-8")) if os.path.exists(STATS) else []
    return docs, events, stats


def _apply_public_filter(docs, events, stats, measures):
    """Restrict every store to public-domain US-gov material.

    A document is kept iff its license == PUBLIC_DOMAIN_LICENSE. An event is kept
    iff its governing document is a kept (public) document — events with no
    governing doc, or governed by a non-public doc, are dropped so no in-copyright
    content surfaces. Measures are kept iff they reference a statistic that still
    has at least one public document or public event; line_item_history rows that
    point at a dropped event are pruned. Statistics are kept iff they retain a
    public document or event.
    """
    pub_docs = [d for d in docs if _doc_is_public(d)]
    pub_md5 = {d["md5"] for d in pub_docs}

    pub_events = [e for e in events if e.get("governing_document_md5") in pub_md5]
    pub_event_ids = {e["event_id"] for e in pub_events}

    # statistic_ids that still have public documents or public events
    live_stat_ids = set()
    for d in pub_docs:
        live_stat_ids.update(d.get("statistic_ids") or [])
    for e in pub_events:
        live_stat_ids.add(e.get("statistic_id"))

    pub_stats = [s for s in stats if s.get("statistic_id") in live_stat_ids]

    pub_measures = []
    for m in measures:
        # keep a measure only if it ties to a live statistic
        if not (set(m.get("statistic_ids") or []) & live_stat_ids):
            continue
        m = dict(m)
        m["line_item_history"] = [h for h in m.get("line_item_history", [])
                                  if (h.get("revision_event_id") in pub_event_ids
                                      or h.get("revision_event_id") is None)]
        pub_measures.append(m)

    return pub_docs, pub_events, pub_stats, pub_measures


DOCSL, EVENTSL, STATSL = _load()
_MEAS_PATH = os.path.join(ROOT, "measures.json")
MEASURES = json.load(open(_MEAS_PATH, encoding="utf-8")) if os.path.exists(_MEAS_PATH) else []

PUBLIC_ONLY = _public_only_enabled()
if PUBLIC_ONLY:
    DOCSL, EVENTSL, STATSL, MEASURES = _apply_public_filter(DOCSL, EVENTSL, STATSL, MEASURES)

_DOC_BY_MD5 = {d["md5"]: d for d in DOCSL}
_EVENT_BY_ID = {e["event_id"]: e for e in EVENTSL}


def _year(s):
    m = re.search(r"(1[89]\d{2}|20[0-3]\d)", str(s or ""))
    return int(m.group(1)) if m else None


# ---------- tool functions ----------
def resolve_statistic(query: str):
    """Resolve a free-text query to canonical statistic_id(s)."""
    q = query.lower().strip()
    hits = []
    for s in STATSL:
        hay = " ".join([s["statistic_id"], s["name"]] + s.get("aliases", [])).lower()
        if q in hay or any(q in a.lower() or a.lower() in q for a in [s["name"]] + s.get("aliases", [])):
            hits.append({"statistic_id": s["statistic_id"], "name": s["name"], "family": s["family"]})
    return {"query": query, "matches": hits}


def get_revision_history(statistic_id: str, from_year=None, to_year=None, verified_only: bool = False):
    """Ordered methodology RevisionEvents for a statistic, optionally bounded by year.
    Set verified_only=True to return only adversarially-verified events."""
    fy, ty = _year(from_year) or -9999, _year(to_year) or 9999
    bounded = fy != -9999 or ty != 9999
    out = []
    for e in EVENTSL:
        if e["statistic_id"] != statistic_id:
            continue
        if verified_only and not _is_verified(e):
            continue
        ey = _year(e["effective_date"])
        # undated events have no place inside a requested year window; include
        # them only when the caller asked for the full (unbounded) history.
        if ey is None:
            if not bounded:
                out.append(_event_view(e))
            continue
        if fy <= ey <= ty:
            out.append(_event_view(e))
    out.sort(key=lambda e: (e["effective_year"] or 9999, e["type"]))
    return {"statistic_id": statistic_id, "from": fy if fy != -9999 else None,
            "to": ty if ty != 9999 else None, "n": len(out), "events": out}


def get_methodology(statistic_id: str, as_of_date):
    """THE killer tool: what methodology governed `statistic_id` as of `as_of_date`?
    Returns the governing handbook/manual in force then + all revision events up to that date."""
    yr = _year(as_of_date)
    stat = next((s for s in STATSL if s["statistic_id"] == statistic_id), None)
    # governing documents: manuals/handbooks for this statistic published on/before the date
    govs = []
    for d in DOCSL:
        if statistic_id not in (d.get("statistic_ids") or []) and not _doc_matches_stat(d, statistic_id):
            continue
        if d["doc_type"] not in ("manual", "handbook"):
            continue
        py = _year(d.get("publication_date"))
        if py and yr and py <= yr:
            govs.append((py, d))
    govs.sort(key=lambda x: x[0], reverse=True)
    governing = [_doc_view(d) for _, d in govs[:3]]
    prior = get_revision_history(statistic_id, None, yr)["events"]
    return {
        "statistic_id": statistic_id,
        "as_of_date": as_of_date,
        "name": stat["name"] if stat else statistic_id,
        "data_vintage_source": stat.get("data_vintage_source") if stat else None,
        "governing_documents_in_force": governing,
        "methodology_changes_up_to_date": prior,
        "summary": f"As of {as_of_date}, {len(prior)} methodology changes had taken effect for "
                   f"{stat['name'] if stat else statistic_id}.",
    }


def diff_methodology(statistic_id: str, date_a, date_b, verified_only: bool = False):
    """What changed in methodology between two dates (events with date_a < effective <= date_b).
    Set verified_only=True to count only adversarially-verified changes."""
    ya, yb = _year(date_a), _year(date_b)
    lo, hi = sorted([ya or -9999, yb or 9999])
    changes = [_event_view(e) for e in EVENTSL
               if e["statistic_id"] == statistic_id and (_year(e["effective_date"]) or -1) > lo
               and (_year(e["effective_date"]) or 99999) <= hi
               and (not verified_only or _is_verified(e))]
    changes.sort(key=lambda e: e["effective_year"] or 9999)
    return {"statistic_id": statistic_id, "from": date_a, "to": date_b,
            "n_changes": len(changes), "changes": changes}


def search_methodology(query: str, statistic_id=None, limit=15):
    """Keyword search across revision-event descriptions and document titles."""
    q = query.lower()
    res = []
    for e in EVENTSL:
        if statistic_id and e["statistic_id"] != statistic_id:
            continue
        if q in (e.get("description", "") + " " + " ".join(e.get("concept_ids", []))).lower():
            res.append({"kind": "event", **_event_view(e)})
    for d in DOCSL:
        if statistic_id and not _doc_matches_stat(d, statistic_id):
            continue
        if q in d.get("title", "").lower():
            res.append({"kind": "document", **_doc_view(d)})
    return {"query": query, "n": len(res), "results": res[:limit]}


def get_document(md5: str):
    """Full MethodologyDocument record + provenance by md5."""
    d = _DOC_BY_MD5.get(md5)
    return _doc_view(d) if d else {"error": f"no document with md5 {md5}"}


def get_concept_history(concept: str):
    """All revision events touching a concept (e.g. 'owners_equivalent_rent', 'hedonic')."""
    c = concept.lower()
    hits = [_event_view(e) for e in EVENTSL
            if any(c in cid.lower() for cid in e.get("concept_ids", [])) or c in e.get("description", "").lower()]
    hits.sort(key=lambda e: e["effective_year"] or 9999)
    return {"concept": concept, "n": len(hits), "events": hits}


def get_table_history(table_id: str):
    """How a published output TABLE was defined over time (e.g. 'BEA.NIPA.T1.1.5' = GDP):
    the table + its line-item lineage across comprehensive revisions, with linked revision events."""
    q = table_id.strip().upper().replace(" ", "")
    m = next((x for x in MEASURES if x["table_id"].upper().replace(" ", "") == q), None)
    if not m:
        cands = [x["table_id"] for x in MEASURES if q in x["table_id"].upper() or q in x["title"].upper()][:10]
        return {"error": f"no table {table_id}", "did_you_mean": cands}
    hist = []
    for h in sorted(m.get("line_item_history", []), key=lambda h: str(h.get("effective_date", ""))):
        ev = _EVENT_BY_ID.get(h.get("revision_event_id"))
        hist.append({"effective_date": h["effective_date"], "change": h["change"],
                     "linked_event": ev["event_id"] if ev else None,
                     "governing_document": (_DOC_BY_MD5.get(ev.get("governing_document_md5"), {}).get("title")
                                            if ev else None)})
    return {"table_id": m["table_id"], "title": m["title"], "section": m.get("section"),
            "presents": m.get("presents"), "key_series": m.get("key_series", []),
            "statistic_ids": m.get("statistic_ids", []), "n_changes": len(hist), "line_item_history": hist}


def list_measures(statistic_id: str = None, section: str = None):
    """List published tables/measures, optionally filtered by statistic_id or NIPA section."""
    out = []
    for m in MEASURES:
        if statistic_id and statistic_id not in m.get("statistic_ids", []):
            continue
        if section and section.lower() not in (m.get("section") or "").lower():
            continue
        out.append({"table_id": m["table_id"], "title": m["title"], "section": m.get("section"),
                    "n_line_item_changes": len(m.get("line_item_history", []))})
    return {"statistic_id": statistic_id, "section": section, "n": len(out), "measures": out}


# ---------- views (attach provenance) ----------
def _event_view(e):
    gov = _DOC_BY_MD5.get(e.get("governing_document_md5", ""), {})
    return {
        "event_id": e["event_id"], "statistic_id": e["statistic_id"],
        "effective_date": e["effective_date"], "effective_year": _year(e["effective_date"]),
        "type": e["type"], "description": e["description"], "magnitude": e.get("magnitude"),
        "direction": e.get("direction"), "concept_ids": e.get("concept_ids", []),
        "citation": {"document": gov.get("title", e.get("governing_document_md5", ""))[:80],
                     "md5": e.get("governing_document_md5", ""),
                     "page": (e.get("citation") or {}).get("page"),
                     "n_sources": len(e.get("supporting_documents", []) or [1])},
        "data_vintage_link": e.get("data_vintage_link"),
        "verified": (e.get("verification") or {}).get("verified"),
    }


def _is_verified(e):
    return (e.get("verification") or {}).get("verified") is True


def _doc_view(d):
    return {"md5": d["md5"], "title": d["title"], "producer": d.get("producer_id"),
            "doc_type": d.get("doc_type"), "publication_date": d.get("publication_date"),
            "geography": d.get("geography"), "provenance": d.get("provenance", {})}


def _doc_matches_stat(d, statistic_id):
    fam = {"US.BLS.CPI_U": "prices", "US.BEA.GDP.REAL": "national_accounts", "US.BEA.IO": "input_output"}.get(statistic_id)
    prod = {"US.BLS.CPI_U": "BLS", "US.BEA.GDP.REAL": "BEA", "US.BEA.IO": "BEA"}.get(statistic_id)
    # heuristic: same producer + title hints (MVP; real binding via statistic_ids comes in Stage C)
    title = d.get("title", "").lower()
    if statistic_id == "US.BLS.CPI_U":
        return "consumer price" in title or "cpi" in title
    if statistic_id == "US.BEA.GDP.REAL":
        return "national income" in title or "nipa" in title or "gross domestic" in title
    if statistic_id == "US.BEA.IO":
        return "input-output" in title or "input output" in title
    return False


def get_vintage_data(statistic_id: str, as_of_date=None):
    """Cross-link methodology to the underlying DATA vintage (ALFRED/FRED): returns the vintage
    series + an ALFRED real-time URL so you can see the data AS IT STOOD on `as_of_date`.
    (Returns the pointer/URL; does not fetch over the network.)"""
    stat = next((s for s in STATSL if s["statistic_id"] == statistic_id), None)
    src = (stat or {}).get("data_vintage_source")
    if not src:
        ev = next((e for e in EVENTSL if e["statistic_id"] == statistic_id and e.get("data_vintage_link")), None)
        if ev:
            src = "ALFRED:" + ev["data_vintage_link"]["series_id"]
    if not src or not str(src).startswith("ALFRED:"):
        return {"statistic_id": statistic_id, "data_vintage_source": src,
                "note": "no ALFRED/FRED vintage series mapped for this statistic"}
    series = src.split(":", 1)[1]
    yr = _year(as_of_date)
    vintage = f"{yr}-12-31" if yr else None
    url = f"https://alfred.stlouisfed.org/series?seid={series}" + (f"&vintage_date={vintage}" if vintage else "")
    return {"statistic_id": statistic_id, "series_id": series, "as_of_date": as_of_date,
            "vintage_date": vintage, "alfred_url": url,
            "fred_url": f"https://fred.stlouisfed.org/series/{series}",
            "note": "ALFRED vintage_date shows the data as published at as_of_date; methodology that governed it is from get_methodology()."}


def get_methodology_timeline(statistic_id: str, fmt: str = "markdown"):
    """Render a statistic's methodology history (revision events, oldest->newest) as a
    'markdown' bullet timeline or a 'mermaid' timeline diagram — ready to drop into a paper or site."""
    hist = get_revision_history(statistic_id)["events"]
    stat = next((s for s in STATSL if s["statistic_id"] == statistic_id), None)
    name = (stat or {}).get("name", statistic_id)
    if fmt == "mermaid":
        lines = ["timeline", f"  title Methodology timeline — {name}"]
        for e in hist:
            yr = e["effective_year"] or "?"
            desc = e["description"][:70].replace(":", ";").replace("\n", " ")
            lines.append(f"  {yr} : {e['type']}: {desc}")
        return {"statistic_id": statistic_id, "format": "mermaid", "n_events": len(hist),
                "diagram": "\n".join(lines)}
    md = [f"# Methodology timeline — {name} (`{statistic_id}`)", ""]
    for e in hist:
        yr = e["effective_year"] or "?"
        cite = e["citation"]["document"][:50]
        flag = " ✓" if e.get("verified") else ""
        md.append(f"- **{yr}** · `{e['type']}`{flag} — {e['description']}  _(src: {cite})_")
    return {"statistic_id": statistic_id, "format": "markdown", "n_events": len(hist),
            "timeline": "\n".join(md)}


_SEM_INDEX = None
_STOPWORDS = set("the a an and or of to in for on with by from as at is are was were be been "
                 "this that these those it its their have has had not new use used over per".split())


def _sem_tokens(t):
    return [w for w in re.findall(r"[a-z0-9]+", (t or "").lower()) if len(w) > 2 and w not in _STOPWORDS]


def _build_sem_index():
    """Dependency-free TF-IDF index over event descriptions (+concepts) and document titles."""
    rows = []  # (kind, ref, label, tokens)
    for e in EVENTSL:
        rows.append(("event", e["event_id"], e["statistic_id"],
                     _sem_tokens(e.get("description", "") + " " + " ".join(e.get("concept_ids", [])))))
    for d in DOCSL:
        rows.append(("document", d["md5"], d.get("title", ""), _sem_tokens(d.get("title", ""))))
    n = len(rows) or 1
    df = {}
    for *_h, toks in rows:
        for w in set(toks):
            df[w] = df.get(w, 0) + 1
    idf = {w: math.log(n / (1 + c)) for w, c in df.items()}
    vecs = []
    for kind, ref, label, toks in rows:
        tf = {}
        for w in toks:
            tf[w] = tf.get(w, 0) + 1
        v = {w: (tf[w] / len(toks)) * idf.get(w, 0.0) for w in tf} if toks else {}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append((kind, ref, label, {w: x / norm for w, x in v.items()}))
    return idf, vecs


def semantic_search(query: str, limit: int = 10, statistic_id: str = None):
    """Semantic (TF-IDF cosine) ranking over revision-event descriptions + document titles.
    Finds methodology relevant by MEANING, not just substring — no external API/model.
    Complements search_methodology (which is exact keyword); returns scored results with provenance."""
    global _SEM_INDEX
    if _SEM_INDEX is None:
        _SEM_INDEX = _build_sem_index()
    idf, vecs = _SEM_INDEX
    qtok = _sem_tokens(query)
    if not qtok:
        return {"query": query, "mode": "semantic_tfidf", "n": 0, "results": []}
    qtf = {}
    for w in qtok:
        qtf[w] = qtf.get(w, 0) + 1
    qv = {w: (qtf[w] / len(qtok)) * idf.get(w, 0.0) for w in qtf}
    qnorm = math.sqrt(sum(x * x for x in qv.values())) or 1.0
    qv = {w: x / qnorm for w, x in qv.items()}
    scored = []
    for kind, ref, label, v in vecs:
        s = sum(qv[w] * v.get(w, 0.0) for w in qv)
        if s > 0:
            scored.append((s, kind, ref))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for s, kind, ref in scored:
        if kind == "event":
            e = _EVENT_BY_ID.get(ref)
            if not e or (statistic_id and e["statistic_id"] != statistic_id):
                continue
            out.append({"score": round(s, 4), "kind": "event", **_event_view(e)})
        else:
            d = _DOC_BY_MD5.get(ref)
            if not d or (statistic_id and statistic_id not in (d.get("statistic_ids") or [])):
                continue
            out.append({"score": round(s, 4), "kind": "document", **_doc_view(d)})
        if len(out) >= limit:
            break
    return {"query": query, "mode": "semantic_tfidf", "n": len(out), "results": out}


def methodex_status(statistic_id: str = None):
    """Coverage + quality snapshot of the whole Methodex graph, OR a per-statistic 'data card'
    (events, documents, verification rate, year span, vintage link) when statistic_id is given."""
    import collections
    if statistic_id:
        evs = [e for e in EVENTSL if e["statistic_id"] == statistic_id]
        docs = [d for d in DOCSL if statistic_id in (d.get("statistic_ids") or [])]
        stat = next((s for s in STATSL if s["statistic_id"] == statistic_id), None)
        years = sorted(y for y in (_year(e["effective_date"]) for e in evs) if y)
        return {"statistic_id": statistic_id, "name": (stat or {}).get("name"),
                "family": (stat or {}).get("family"), "has_entity": bool(stat),
                "data_vintage_source": (stat or {}).get("data_vintage_source"),
                "n_events": len(evs), "n_documents": len(docs),
                "verified_events": sum(1 for e in evs if _is_verified(e)),
                "events_with_vintage_link": sum(1 for e in evs if e.get("data_vintage_link")),
                "year_span": [years[0], years[-1]] if years else None,
                "event_types": sorted({e["type"] for e in evs})}
    fam = collections.Counter()
    for e in EVENTSL:
        s = next((s for s in STATSL if s["statistic_id"] == e["statistic_id"]), None)
        fam[(s or {}).get("family", "uncategorized")] += 1
    return {"events": len(EVENTSL), "documents": len(DOCSL),
            "public_only_mode": PUBLIC_ONLY,
            "statistics_with_events": len({e["statistic_id"] for e in EVENTSL}),
            "statistic_entities": len(STATSL), "measures": len(MEASURES), "tools": len(TOOLS),
            "verified_events": sum(1 for e in EVENTSL if _is_verified(e)),
            "events_with_vintage_link": sum(1 for e in EVENTSL if e.get("data_vintage_link")),
            "edition_chains_docs_linked": sum(1 for d in DOCSL if d.get("supersedes_md5") or d.get("superseded_by_md5")),
            "events_by_family": dict(fam.most_common())}


TOOLS = [resolve_statistic, get_methodology, get_revision_history, diff_methodology,
         search_methodology, get_document, get_concept_history, get_table_history, list_measures,
         get_vintage_data, get_methodology_timeline, methodex_status, semantic_search]


def _serve_mcp():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print("[Methodex] `mcp` package not installed — run `pip install mcp` to serve over MCP.\n"
              "Tool functions are importable directly; try: python Methodex_mcp.py demo", file=sys.stderr)
        return 1
    mode = "PUBLIC-ONLY (US-Gov public domain)" if PUBLIC_ONLY else "FULL CORPUS (internal/research)"
    print(f"[Methodex] serving mode: {mode} — {len(DOCSL)} docs, {len(EVENTSL)} events.", file=sys.stderr)
    mcp = FastMCP("Methodex")
    for fn in TOOLS:
        mcp.tool()(fn)
    mcp.run()
    return 0


def _demo():
    import textwrap
    def show(title, obj):
        print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)
        print(json.dumps(obj, indent=1, ensure_ascii=False)[:2600])
    show("resolve_statistic('cost of living index')", resolve_statistic("cost of living index"))
    show("get_methodology('US.BLS.CPI_U', '1980')  [killer tool]", get_methodology("US.BLS.CPI_U", "1980"))
    show("diff_methodology('US.BLS.CPI_U', '1980', '2005')  [what changed]",
         diff_methodology("US.BLS.CPI_U", "1980", "2005"))
    show("get_concept_history('owners_equivalent_rent')", get_concept_history("owners_equivalent_rent"))
    show("diff_methodology('US.BEA.GDP.REAL', '1985', '2015')", diff_methodology("US.BEA.GDP.REAL", "1985", "2015"))


if __name__ == "__main__":
    # `--public-only` may appear anywhere; it is consumed at import time by
    # _public_only_enabled(). The remaining positional arg selects the action.
    _args = [a for a in sys.argv[1:] if a != "--public-only"]
    if _args and _args[0] == "demo":
        _demo()
    else:
        sys.exit(_serve_mcp())
