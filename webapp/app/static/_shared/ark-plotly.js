/* =============================================================================
   Arcanum Site Kit — ark-plotly.js — v1.2
   ONE shared Plotly standard for every site: transparent backgrounds, fonts +
   grid + colorway driven by the kit `--ark-*` tokens, fully dark/light aware,
   re-themes live on the `ark:themechange` event (from the kit theme toggle),
   and a trimmed modebar with PNG export + a custom "Download data (CSV)" button.

   Dependency-free except window.Plotly (load plotly.min.js BEFORE this file).
   Usage:
     ArkPlotly.plot("chart_id", traces, {xaxis:{title:"%"}});   // preferred
     // or, for hand-rolled Plotly.newPlot calls, theme them:
     Plotly.newPlot(id, traces, ArkPlotly.layout(extra), ArkPlotly.config());
   All plotted divs auto-re-theme when the user toggles light/dark.
   ============================================================================= */
(function () {
  "use strict";
  var DOC = document, REG = []; // registry of {id, getRows} for re-theme + CSV

  function isDark() {
    var t = DOC.documentElement.dataset.theme;
    if (t === "dark") return true;
    if (t === "light") return false;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  function tok(name, fallback) {
    var v = getComputedStyle(DOC.documentElement).getPropertyValue(name);
    return (v && v.trim()) || fallback;
  }
  function palette() {
    var accent = tok("--ark-accent", "#1565c0");
    return {
      fg: tok("--ark-fg", isDark() ? "#e7edf3" : "#14181d"),
      dim: tok("--ark-fg-dim", isDark() ? "#9aa7b4" : "#5a6673"),
      line: tok("--ark-line", isDark() ? "#2a313b" : "#dde3ea"),
      accent: accent,
      // a small accent-led categorical colorway (accent first, then neutral-distinct hues)
      colorway: [accent, "#6b7280", "#0d9488", "#b8860b", "#7c4dff", "#dc2626", "#15803d", "#0891b2"]
    };
  }

  // Broken-/dual-axis y-title de-dup (F-9B-05). A broken-axis chart stacks two
  // cartesian subplots (yaxis + yaxis2, on separate `domain`s) for series on very
  // different scales. Plotly gives each subplot its own y-title; when both carry the
  // SAME string they render stacked/overlapping in the left margin as garbled doubled
  // text. Fix: keep the shared y-title on ONE axis only and blank the duplicates, so a
  // single legible label remains. Distinct short per-panel titles are left untouched.
  function titleText(t) {
    if (t == null) return "";
    return String(typeof t === "object" ? (t.text || "") : t).trim();
  }
  function dedupeAxisTitles(lay) {
    if (!lay) return lay;
    var keys = Object.keys(lay).filter(function (k) { return /^yaxis\d*$/.test(k); });
    if (keys.length < 2) return lay;   // single-panel chart — nothing to de-dup
    var seen = {};
    keys.forEach(function (k) {
      var ax = lay[k]; if (!ax || typeof ax !== "object") return;
      var txt = titleText(ax.title);
      if (!txt) return;
      if (seen[txt]) {                 // a prior axis already owns this exact title -> blank this one
        ax.title = (ax.title && typeof ax.title === "object") ? Object.assign({}, ax.title, { text: "" }) : "";
      } else { seen[txt] = true; }
    });
    return lay;
  }

  function layout(extra) {
    var p = palette();
    var base = {
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: "system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif", size: 13, color: p.fg },
      colorway: p.colorway,
      margin: { l: 60, r: 20, t: 16, b: 44 },
      xaxis: { gridcolor: p.line, zerolinecolor: p.line, linecolor: p.line, tickfont: { color: p.dim }, title: { font: { color: p.dim } } },
      yaxis: { gridcolor: p.line, zerolinecolor: p.line, linecolor: p.line, tickfont: { color: p.dim }, title: { font: { color: p.dim } } },
      // DNA Universal Graph Contract: legend ALWAYS below the plot (never on top / overlapping the axis)
      legend: { orientation: "h", x: 0, xanchor: "left", y: -0.18, yanchor: "top", font: { color: p.fg } },
      // tooltip colors from --ark-* tokens (fixes the white-box / white-on-white hover bug)
      hoverlabel: { bgcolor: tok("--ark-bg-soft", isDark() ? "#161b22" : "#ffffff"), bordercolor: p.line, font: { family: "system-ui,sans-serif", color: p.fg } }
    };
    return dedupeAxisTitles(deepMerge(base, extra || {}));
  }

  // CSV export of a chart's traces (the "download data" affordance).
  function tracesToCsv(div) {
    var data = (div && div.data) || [];
    if (!data.length) return "";
    var rows = [], header = ["series", "x", "y"];
    rows.push(header.join(","));
    data.forEach(function (t) {
      var name = (t.name || t.type || "series");
      var xs = t.x || t.labels || [], ys = t.y || t.values || [];
      var n = Math.max(xs.length, ys.length);
      for (var i = 0; i < n; i++) rows.push([csv(name), csv(xs[i]), csv(ys[i])].join(","));
    });
    return rows.join("\n");
  }
  function csv(v) { v = (v == null ? "" : String(v)); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
  function downloadCsv(div, filename) {
    var text = tracesToCsv(div); if (!text) return;
    var blob = new Blob([text], { type: "text/csv;charset=utf-8" });
    var a = DOC.createElement("a"); a.href = URL.createObjectURL(blob);
    a.download = (filename || div.id || "chart") + ".csv"; DOC.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  function config(opts) {
    opts = opts || {};
    return {
      responsive: true, displaylogo: false, displayModeBar: opts.modeBar === false ? false : "hover",
      modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
      modeBarButtonsToAdd: [{
        name: "Download data (CSV)", icon: (window.Plotly && Plotly.Icons && Plotly.Icons.disk) || undefined,
        click: function (gd) { downloadCsv(gd, opts.filename); }
      }],
      toImageButtonOptions: { format: "png", scale: 2 }
    };
  }

  function debounce(fn, ms) {
    var t; return function () { clearTimeout(t); t = setTimeout(fn, ms || 120); };
  }
  // DNA Universal Graph Contract: a chart title must fit its box at every width and
  // never truncate/overflow. Plotly titles don't wrap, so we wrap long titles at word
  // boundaries and scale the font to the container width (and restore the full title
  // when the box is wide again). Width-aware so desktop keeps its one-line title.
  function wrapText(s, max) {
    var words = String(s).split(/\s+/), lines = [], cur = "";
    words.forEach(function (w) {
      if (cur && (cur + " " + w).length > max) { lines.push(cur); cur = w; }
      else { cur = cur ? cur + " " + w : w; }
    });
    if (cur) lines.push(cur);
    return lines.join("<br>");
  }
  function responsiveTitle(div) {
    if (!div || !div.layout || !div.layout.title) return;
    if (div._arkTitleText == null) div._arkTitleText = (div.layout.title.text || "");
    var full = div._arkTitleText;
    if (!full) return;
    var plain = full.replace(/<br>/g, " ");
    var w = div.clientWidth || 600;
    var perLine = Math.max(16, Math.floor(w / 9.5));   // approx chars that fit one line
    var size = w < 480 ? 14 : (w < 640 ? 16 : 18);
    var wrapped = plain.length > perLine ? wrapText(plain, perLine) : plain;
    var t = div.layout.title;
    var changed = (t.text || "") !== wrapped || !t.font || t.font.size !== size;
    if (changed) {
      try { Plotly.relayout(div, { "title.text": wrapped, "title.font.size": size,
        "margin.t": wrapped.indexOf("<br>") >= 0 ? 70 : 52 }); } catch (e) {}
    }
  }
  function plot(id, traces, extra, opts) {
    var div = (typeof id === "string") ? DOC.getElementById(id) : id;
    if (!div || !window.Plotly) return Promise.resolve(div);
    return Plotly.newPlot(div, traces, layout(extra), config(opts)).then(function () {
      register(div, extra, opts);
      responsiveTitle(div);
      // re-fit on container resize (debounced) — prevents clipped / off-graph renders on relayout
      if (window.ResizeObserver && !div._arkRO) {
        div._arkRO = new ResizeObserver(debounce(function () {
          try { Plotly.Plots.resize(div); responsiveTitle(div); } catch (e) {}
        }, 120));
        div._arkRO.observe(div);
      }
      return div;
    });
  }
  function register(div, extra, opts) {
    if (!div) return;
    if (!REG.some(function (r) { return r.div === div; })) REG.push({ div: div, extra: extra, opts: opts });
  }
  function reThemeAll() {
    if (!window.Plotly) return;
    REG.forEach(function (r) {
      if (!DOC.body.contains(r.div)) return;
      // Plotly.react diffs against the current data — no ghost/phantom trace that relayout(full-layout) caused
      try { Plotly.react(r.div, r.div.data, layout(r.extra), config(r.opts)); } catch (e) {}
    });
  }

  function deepMerge(a, b) {
    var out = {}, k;
    for (k in a) out[k] = a[k];
    for (k in b) out[k] = (b[k] && typeof b[k] === "object" && !Array.isArray(b[k]) && a[k]) ? deepMerge(a[k], b[k]) : b[k];
    return out;
  }

  window.ArkPlotly = { isDark: isDark, palette: palette, layout: layout, config: config, plot: plot, register: register, reThemeAll: reThemeAll, downloadCsv: downloadCsv };
  DOC.addEventListener("ark:themechange", reThemeAll);
})();
