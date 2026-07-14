/* =============================================================================
   Arcanum Site Kit — ark-triad.js — v2.0  (the Research Triad + Action Footer)
   Dependency-free, no external calls (offline rule). Progressive enhancement.

   Hydrates the "Code & Data First" surfaces (CODE_DATA_FIRST_STANDARD.md):
     • every [data-ark-triad] row (hero triad + the compact triad in the footer)
     • the footer "Website source" button   ([data-cdf-repo])
     • the footer "Cite this site" button    ([data-cdf-cite])

   HOW IT IDENTIFIES "THIS SITE":
     Exactly like arcanum-chrome.js — reads window.ARK_CONFIG.site_key, then looks
     that key up in the ecosystem manifest (embedded object > inline
     <script id=ark-ecosystem> > same-origin fetch of ecosystem_url). It reuses
     window.ArcanumChrome.getEcosystem when arcanum-chrome.js is present; otherwise
     it falls back to an identical tiny loader so the triad works standalone.

   GRACEFUL NO-OP:
     If the manifest, the site entry, or its `cdf` block is absent, nothing is
     revealed and no button is wired — a not-yet-migrated site never breaks and
     never shows a dead "#" button. The triad markup starts [hidden]; this script
     removes [hidden] only after it fills all three targets.

   TELEMETRY:
     On any triad click it fires ONE first-party beacon REUSING the ark-track.js
     transport (keepalive fetch, credentials-omit → sendBeacon fallback, DNT-respecting,
     no cookies/PII). Payload adds the two Layer-2/3 fields this redesign exists to
     measure: { surface, endpoint: "triad:data|triad:code|triad:outputs" }, where
     surface is "download" for the Data/Code buttons (they ARE downloads) and "web"
     for the Outputs button (it is NAVIGATION to the results construct, not a download).
   ============================================================================= */
(function () {
  "use strict";

  var DOC = document;
  var CFG = (window.ARK_CONFIG = window.ARK_CONFIG || {});

  /* ---- ecosystem acquisition (identical policy to arcanum-chrome.js) ------ */
  function getEcosystem(cb) {
    // Reuse arcanum-chrome.js's loader when it is on the page (single source).
    if (window.ArcanumChrome && typeof window.ArcanumChrome.getEcosystem === "function") {
      return window.ArcanumChrome.getEcosystem(cb);
    }
    if (CFG.ecosystem && CFG.ecosystem.sites) return cb(CFG.ecosystem);
    var inline = DOC.getElementById("ark-ecosystem");
    if (inline && inline.textContent.trim()) {
      try { return cb(JSON.parse(inline.textContent)); } catch (e) { /* fall through */ }
    }
    var url = CFG.ecosystem_url || "/static/_shared/ecosystem.json";
    if (!window.fetch) return cb(null);
    fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { cb(j); })
      .catch(function () { cb(null); });
  }

  function currentSite(eco) {
    if (!eco || !eco.sites) return null;
    var key = CFG.site_key || (window.ARK_TRACK && window.ARK_TRACK.site);
    var hit = eco.sites.filter(function (s) { return s.key === key; })[0];
    return hit || null;
  }

  /* ---- telemetry: mirror the ark-track.js transport ---------------------- */
  // Same mechanism ark-track.js uses for its pageview beacon: keepalive fetch
  // (credentials-omit) first, sendBeacon fallback, honor DNT/GPC, never throw. We only add the
  // surface/endpoint fields the traffic layer keys on for triad clicks.
  function beacon(endpointTag) {
    try {
      var T = window.ARK_TRACK || {};
      var dnt = navigator.doNotTrack === "1" || window.doNotTrack === "1" || navigator.globalPrivacyControl === true;
      if (dnt) return;
      var site = T.site || CFG.site_key || location.hostname;
      var url = T.endpoint || "/__track";
      // Outputs is NAVIGATION (to Studies/Explorer/Gallery), not a download → surface=web.
      // Data/Code are genuine downloads → surface=download. (surface enum: mcp|rest|web|download.)
      var surface = (endpointTag === "triad:outputs") ? "web" : "download";
      var payload = JSON.stringify({
        site: site,
        surface: surface,
        endpoint: endpointTag,                 // "triad:data" | "triad:code" | "triad:outputs"
        path: location.pathname,
        ref: DOC.referrer ? new URL(DOC.referrer, location.href).hostname : "",
        ts: Math.floor(Date.now() / 1000)      // server re-stamps; client ts advisory
      });
      // v1.2 CORS fix (mirrors ark-track.js): prefer keepalive fetch with
      // credentials:"omit" + mode:"cors" so cross-origin triad beacons reach the
      // wildcard-CORS collector (sendBeacon always sends credentials → blocked by
      // ACAO *). sendBeacon stays only as the no-fetch fallback (same-origin OK).
      if (window.fetch) {
        fetch(url, { method: "POST", body: payload, headers: { "Content-Type": "application/json" }, keepalive: true, mode: "cors", credentials: "omit" }).catch(function () {});
      } else if (navigator.sendBeacon) {
        navigator.sendBeacon(url, new Blob([payload], { type: "application/json" }));
      }
    } catch (e) { /* telemetry must never break a page */ }
  }

  /* ---- sublabel formatting ----------------------------------------------- */
  var FORMAT_LABELS = { csv: "CSV", xlsx: "XLSX", parquet: "Parquet", zip: "ZIP" };
  var LANG_LABELS = { python: "Python", r: "R", typescript: "TypeScript", javascript: "JavaScript", sql: "SQL", stata: "Stata", julia: "Julia" };

  function fmtList(arr, map) {
    if (!arr || !arr.length) return "";
    return arr.map(function (x) { return map[String(x).toLowerCase()] || String(x); });
  }
  function dataSub(d) {
    if (!d) return "";
    var parts = [];
    var fmts = fmtList(d.formats, FORMAT_LABELS).join(", ");
    if (d.size) parts.push(fmts ? d.size + " · " + fmts : d.size);
    else if (fmts) parts.push(fmts);
    if (d.bulk && d.bulk.size) parts.push("bulk " + d.bulk.size + " →");   // freenic two-tier pattern
    return parts.join(" · ");
  }
  function codeSub(c) {
    if (!c) return "";
    var langs = fmtList(c.langs, LANG_LABELS).join(" + ");
    var bits = [];
    if (langs) bits.push(langs);
    if (c.license) bits.push(c.license);
    return bits.join(" · ");
  }

  /* ---- triad hydration ---------------------------------------------------- */
  function fillTriad(row, cdf) {
    if (!cdf) return false;
    var data = cdf.data, code = cdf.code, outputs = cdf.outputs;
    if (!data || !code || !outputs || !data.href || !code.href || !outputs.href) return false;

    function set(kind, href, sub) {
      var a = row.querySelector('[data-cdf="' + kind + '"]');
      if (!a) return;
      a.setAttribute("href", href);
      var s = row.querySelector('[data-cdf-sub="' + kind + '"]');
      if (s) s.textContent = sub || "";
      if (!a.__arkTriadWired) {
        a.__arkTriadWired = true;
        a.addEventListener("click", function () { beacon("triad:" + kind); });
      }
    }
    set("data", data.href, dataSub(data));
    set("code", code.href, codeSub(code));
    set("outputs", outputs.href, outputs.label || "");
    row.classList.remove("ark-triad--pending");
    row.hidden = false;
    return true;
  }

  /* ---- footer bits: Website source + Cite this site ---------------------- */
  function wireFooter(cdf) {
    // Website source — render ONLY when the site has a public repo (no dead button).
    DOC.querySelectorAll("[data-cdf-repo]").forEach(function (a) {
      var repo = cdf && cdf.site_repo;
      if (repo) { a.setAttribute("href", repo); a.hidden = false; a.removeAttribute("hidden"); }
      else { a.hidden = true; }
    });
    // Cite this site — copies the citation string from the cdf block.
    DOC.querySelectorAll("[data-cdf-cite]").forEach(function (btn) {
      var cite = cdf && cdf.citation;
      if (!cite) { btn.hidden = true; return; }
      btn.hidden = false; btn.removeAttribute("hidden");
      if (btn.__arkCiteWired) return;
      btn.__arkCiteWired = true;
      btn.addEventListener("click", function (ev) {
        if (btn.tagName === "A") ev.preventDefault();
        copyText(cite, btn);
      });
    });
  }

  function copyText(text, btn) {
    var done = function () {
      if (!btn) return;
      var o = btn.getAttribute("data-label") || btn.textContent;
      if (!btn.getAttribute("data-label")) btn.setAttribute("data-label", o);
      btn.textContent = "Citation copied";
      setTimeout(function () { btn.textContent = btn.getAttribute("data-label") || "Cite this site"; }, 1600);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text); done(); });
    } else { fallbackCopy(text); done(); }
  }
  function fallbackCopy(t) {
    var ta = DOC.createElement("textarea");
    ta.style.position = "fixed"; ta.style.opacity = "0"; ta.value = t;
    DOC.body.appendChild(ta); ta.select();
    try { DOC.execCommand("copy"); } catch (e) { }
    DOC.body.removeChild(ta);
  }

  /* ---- public API + auto-init -------------------------------------------- */
  function hydrate(eco) {
    var site = currentSite(eco);
    var cdf = site && site.cdf;                 // may be null/absent → graceful no-op
    DOC.querySelectorAll("[data-ark-triad]").forEach(function (row) { fillTriad(row, cdf); });
    wireFooter(cdf || {});
  }

  window.ArkTriad = {
    hydrate: function () { getEcosystem(function (eco) { hydrate(eco || (CFG.ecosystem || {})); }); },
    /** Explicit render from an already-loaded cdf block (SPA/React helper). */
    fill: function (cdf) {
      DOC.querySelectorAll("[data-ark-triad]").forEach(function (row) { fillTriad(row, cdf); });
      wireFooter(cdf || {});
    },
    /** Copy an arbitrary citation string (used by ArkTriad.tsx and adapters). */
    copyCitation: function (cite, btn) { if (cite) copyText(cite, btn); }
  };

  function init() { getEcosystem(function (eco) { hydrate(eco || (CFG.ecosystem || {})); }); }
  if (DOC.readyState === "loading") DOC.addEventListener("DOMContentLoaded", init);
  else init();
})();
