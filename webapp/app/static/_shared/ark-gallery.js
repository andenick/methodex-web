/* =============================================================================
   Arcanum Site Kit — ark-gallery.js — v1.0  (curated featured-chart gallery)
   Renders a responsive grid of FEATURED-chart cards FROM an approved, human-curated
   gallery manifest. The standardized "Chart Gallery" section every site can mount.

   DNA by construction:
     - ONE chart per card (never side-by-side inside a card).
     - Each card reuses the SAME live chart embed the rest of the site uses
       (a `.chart-embed[data-chart=KEY]` div), so the site's existing hydration
       (app.js → /api/chart/KEY → ArkChart/ArkPlotly) themes it, gives it the
       legend-below + top-right Download-CSV + token tooltip — identical everywhere.
     - title + caption + a "View on page" link per card.

   This component does NOT decide what is featured. It only renders an APPROVED
   manifest. Proposing candidates + the human-approval gate live in the
   `gallery-construction` skill (Carson Web Framework). Nothing here auto-publishes.

   Dependency-free except the site's own chart hydration. Two ways to mount:

   (A) data-driven (preferred) — point a host element at a manifest URL:
         <section id="gallery" class="ark-gallery"
                  data-gallery-manifest="/site_data/gallery_manifest.json"></section>
         <script>ArkGallery.mount("#gallery");</script>
       ArkGallery fetches the manifest, builds the cards (each containing a
       `.chart-embed[data-chart=KEY]` div), then re-runs the site's hydration so
       the new embeds load. Works with Lewis's existing /gallery page.

   (B) explicit — pass an already-loaded manifest object:
         ArkGallery.render("#gallery", manifestObject);

   gallery_manifest.json shape (curated by a human; see the skill):
     {
       "site": "Lewis",
       "title": "Featured Charts",
       "intro": "The charts that tell the Lewis story...",     // optional
       "approved": true,                                          // gate: render only when true
       "charts": [
         { "chart_key": "us_return_reversal",
           "title": "The Return Differential",
           "caption": "Implied yield on U.S. assets abroad vs ...",
           "why": "tells the site's headline story (the exorbitant privilege)",  // editorial note, not shown
           "page": "/bop",                                       // where the chart lives (card link)
           "params": "?y0=1976&y1=2023" }                        // optional, forwarded to the embed
       ]
     }
   ============================================================================= */
(function () {
  "use strict";
  var DOC = document;

  function el(node) { return (typeof node === "string") ? DOC.querySelector(node) : node; }
  function txt(node, s) { node.textContent = (s == null ? "" : String(s)); return node; }

  // Re-run the site's chart hydration for embeds we just inserted. Sites expose
  // it as window.hydrateAllCharts(); if absent, fall back to a minimal fetcher so
  // the gallery still renders standalone (kit-only, no app.js).
  function hydrateEmbeds(root) {
    if (typeof window.hydrateAllCharts === "function") { window.hydrateAllCharts(root); return; }
    var embeds = (root || DOC).querySelectorAll(".chart-embed[data-chart]:not([data-ark-hydrated])");
    Array.prototype.forEach.call(embeds, function (em) {
      em.setAttribute("data-ark-hydrated", "1");
      var key = em.getAttribute("data-chart");
      var params = (em.getAttribute("data-params") || "");
      em.innerHTML = '<p class="ark-chart-loading">Loading chart…</p>';
      fetch("/api/chart/" + key + params)
        .then(function (r) { return r.json(); })
        .then(function (p) { drawFallback(em, p); })
        .catch(function () { em.innerHTML = '<p class="ark-chart-error">Failed to load chart.</p>'; });
    });
  }
  function drawFallback(em, payload) {
    var fig = (payload && payload.figure) || {};
    em.innerHTML = "";
    var holder = DOC.createElement("div");
    holder.style.width = "100%"; holder.style.minHeight = "360px";
    em.appendChild(holder);
    if (fig.data && fig.data.length && window.Plotly && window.ArkPlotly) {
      window.ArkPlotly.plot(holder, fig.data, fig.layout || {}, { filename: em.getAttribute("data-chart") });
    } else if (fig.data && fig.data.length && window.Plotly) {
      window.Plotly.newPlot(holder, fig.data, fig.layout || {}, { responsive: true, displaylogo: false });
    } else {
      holder.innerHTML = '<p class="ark-chart-error">' + ((payload && payload.caption) || "Chart unavailable.") + "</p>";
    }
  }

  function card(spec) {
    var fig = DOC.createElement("figure");
    fig.className = "ark-gallery-card";

    if (spec.title) {
      var h = DOC.createElement("h3");
      h.className = "ark-gallery-card-title";
      txt(h, spec.title);
      fig.appendChild(h);
    }

    // ONE chart per card — the site's standard live embed (hydrated downstream)
    var embed = DOC.createElement("div");
    embed.className = "chart-embed ark-gallery-chart";
    embed.setAttribute("data-chart", String(spec.chart_key || ""));
    if (spec.params) embed.setAttribute("data-params", String(spec.params).replace(/&/g, "&amp;"));
    fig.appendChild(embed);

    var cap = DOC.createElement("figcaption");
    cap.className = "ark-gallery-card-caption";
    if (spec.caption) {
      var c = DOC.createElement("span");
      txt(c, spec.caption);
      cap.appendChild(c);
    }
    if (spec.page) {
      var a = DOC.createElement("a");
      a.className = "ark-gallery-card-link";
      a.href = String(spec.page);
      txt(a, "View on page →");
      cap.appendChild(a);
    }
    fig.appendChild(cap);
    return fig;
  }

  function render(target, manifest) {
    var host = el(target);
    if (!host || !manifest) return host;
    // human-approval gate: a manifest is only rendered when explicitly approved.
    if (manifest.approved !== true) {
      host.innerHTML = '<p class="ark-gallery-pending">This gallery has not been approved for ' +
        'publication yet.</p>';
      return host;
    }
    host.classList.add("ark-gallery");
    host.innerHTML = "";

    if (manifest.title) {
      var h2 = DOC.createElement("h2");
      h2.className = "ark-gallery-heading";
      txt(h2, manifest.title);
      host.appendChild(h2);
    }
    if (manifest.intro) {
      var p = DOC.createElement("p");
      p.className = "ark-gallery-intro prose";
      txt(p, manifest.intro);
      host.appendChild(p);
    }

    var grid = DOC.createElement("div");
    grid.className = "ark-gallery-grid";
    var charts = manifest.charts || [];
    if (!charts.length) {
      var empty = DOC.createElement("p");
      empty.className = "ark-gallery-pending";
      txt(empty, "No featured charts have been curated yet.");
      host.appendChild(empty);
      return host;
    }
    charts.forEach(function (spec) { if (spec && spec.chart_key) grid.appendChild(card(spec)); });
    host.appendChild(grid);

    hydrateEmbeds(grid);
    return host;
  }

  function mount(target, opts) {
    opts = opts || {};
    var host = el(target);
    if (!host) return Promise.resolve(null);
    var url = opts.manifest || host.getAttribute("data-gallery-manifest");
    if (!url) { render(host, opts.data || {}); return Promise.resolve(host); }
    return fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (m) { return render(host, m); })
      .catch(function () {
        host.innerHTML = '<p class="ark-gallery-pending">Gallery manifest unavailable.</p>';
        return host;
      });
  }

  window.ArkGallery = { mount: mount, render: render };
})();
