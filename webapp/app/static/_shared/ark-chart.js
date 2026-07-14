/* =============================================================================
   Arcanum Site Kit — ark-chart.js — v1.0  (single chart entry point)
   Makes the DNA Universal Graph Contract true BY CONSTRUCTION for every site:
     - a top-right "Download CSV" on every chart
     - the standardized client-side transform cluster (reindex / YoY / rolling /
       share-of-100 / log) — recomputed IN-BROWSER, never server compute
     - the uniform downloads row (CSV/XLSX/Parquet, no JSON) via ArkDownloads
     - legend-below + token tooltip + resize-debounce + Plotly.react (from ark-plotly.js)
   One implementation, reused by every stack (Jinja/static/Streamlit-embed/React-embed).

   Depends on: window.Plotly, ArkPlotly (ark-plotly.js), ArkDownloads (ark-downloads.js).
   Usage:
     ArkChart.render(elOrId, {
       traces: [...plotly traces...],
       layout: { yaxis:{title:"%"} },        // optional layout extras
       title: "U.S. Federal Revenue (% GDP)",
       downloads: { csv:"/api/x.csv", xlsx:"/api/x.xlsx", parquet:"/api/x.parquet" },
       transforms: ["reindex","yoy","rolling","share","log"],   // which to offer (optional)
       filename: "federal_revenue"
     });
   ============================================================================= */
(function () {
  "use strict";
  var DOC = document, SEQ = 0;

  var TRANSFORMS = {
    none:    { label: "Level" },
    reindex: { label: "Reindex (=100)" },
    yoy:     { label: "YoY growth %" },
    rolling: { label: "Rolling avg" },
    share:   { label: "Share of total %" },
    log:     { label: "Log scale" }
  };

  function el(node) { return (typeof node === "string") ? DOC.getElementById(node) : node; }
  function num(v) { var n = typeof v === "number" ? v : parseFloat(v); return isFinite(n) ? n : null; }

  // ---- client-side transforms over a copy of the original traces ----
  function firstFinite(ys) { for (var i = 0; i < ys.length; i++) if (num(ys[i]) !== null) return num(ys[i]); return null; }

  function applyTransform(traces, kind, opts) {
    opts = opts || {};
    var win = opts.window || 3;
    // deep-ish copy of y arrays so the original is preserved
    var out = traces.map(function (t) {
      var c = {}; for (var k in t) c[k] = t[k];
      c.y = (t.y || []).slice();
      return c;
    });
    if (kind === "reindex") {
      out.forEach(function (t) {
        var base = firstFinite(t.y); if (base === null || base === 0) return;
        t.y = t.y.map(function (v) { var n = num(v); return n === null ? null : (n / base) * 100; });
      });
    } else if (kind === "yoy") {
      out.forEach(function (t) {
        var src = t.y.slice();
        t.y = src.map(function (v, i) {
          var a = num(src[i - 1]), b = num(v);
          return (i === 0 || a === null || a === 0 || b === null) ? null : (b / a - 1) * 100;
        });
      });
    } else if (kind === "rolling") {
      out.forEach(function (t) {
        var src = t.y.slice();
        t.y = src.map(function (v, i) {
          var s = 0, n = 0;
          for (var j = Math.max(0, i - win + 1); j <= i; j++) { var x = num(src[j]); if (x !== null) { s += x; n++; } }
          return n ? s / n : null;
        });
      });
    } else if (kind === "share") {
      // share of total across traces at each x-index
      var len = out.reduce(function (m, t) { return Math.max(m, t.y.length); }, 0);
      for (var i = 0; i < len; i++) {
        var tot = 0;
        out.forEach(function (t) { var x = num(t.y[i]); if (x !== null) tot += x; });
        out.forEach(function (t) { var x = num(t.y[i]); t.y[i] = (tot && x !== null) ? (x / tot) * 100 : null; });
      }
    }
    return out;
  }

  function layoutFor(kind, layoutExtra) {
    var lay = {}; for (var k in (layoutExtra || {})) lay[k] = layoutExtra[k];
    // DNA Universal Graph Contract: legend ALWAYS below — drop any per-figure legend
    // override so the kit default (orientation:h, below the plot) wins everywhere.
    delete lay.legend;
    if (kind === "log") { lay.yaxis = Object.assign({}, lay.yaxis, { type: "log" }); }
    return lay;
  }

  function render(target, spec) {
    var host = el(target);
    if (!host || !window.Plotly || !window.ArkPlotly) return null;
    spec = spec || {};
    var orig = spec.traces || [];
    var transforms = (spec.transforms || []).filter(function (t) { return TRANSFORMS[t]; });

    // structure: <figure> head(title + controls) / plot / downloads
    host.classList.add("ark-chart-wrap");
    host.innerHTML = "";
    var head = DOC.createElement("div"); head.className = "ark-chart-head";
    if (spec.title) { var ti = DOC.createElement("span"); ti.className = "ark-chart-title"; ti.textContent = spec.title; head.appendChild(ti); }
    var controls = DOC.createElement("div"); controls.className = "ark-chart-controls"; head.appendChild(controls);
    var plot = DOC.createElement("div"); plot.className = "ark-chart";
    plot.id = (host.id || "ark") + "_plot_" + (++SEQ);   // unique id (multiple charts per page)
    var dlrow = DOC.createElement("div"); dlrow.className = "ark-chart-downloads";
    host.appendChild(head); host.appendChild(plot); host.appendChild(dlrow);

    var current = "none";
    function draw() {
      var traces = current === "none" || current === "log" ? orig : applyTransform(orig, current);
      ArkPlotly.plot(plot, traces, layoutFor(current, spec.layout), { filename: spec.filename || host.id });
    }

    // transform selector (left of the CSV button)
    if (transforms.length) {
      var sel = DOC.createElement("select"); sel.className = "ark-chart-transform ark-btn ark-btn-sm";
      sel.setAttribute("aria-label", "Transform");
      ["none"].concat(transforms).forEach(function (k) {
        var o = DOC.createElement("option"); o.value = k; o.textContent = TRANSFORMS[k].label; sel.appendChild(o);
      });
      sel.addEventListener("change", function () { current = sel.value; draw(); });
      controls.appendChild(sel);
    }

    // top-right Download CSV (always present, by construction)
    var csvBtn = DOC.createElement("button");
    csvBtn.type = "button"; csvBtn.className = "ark-btn ark-btn-sm ark-chart-csv"; csvBtn.textContent = "Download CSV";
    csvBtn.addEventListener("click", function () { ArkPlotly.downloadCsv(plot, spec.filename || host.id); });
    controls.appendChild(csvBtn);

    // full downloads row (CSV/XLSX/Parquet) when backend URLs provided — JSON dropped by ArkDownloads
    if (spec.downloads && window.ArkDownloads) {
      dlrow.appendChild(ArkDownloads.buttons(spec.downloads, { label: "Download:" }));
    }

    draw();
    return plot;
  }

  window.ArkChart = { render: render, applyTransform: applyTransform, TRANSFORMS: TRANSFORMS };
})();
