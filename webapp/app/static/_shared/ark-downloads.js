/* =============================================================================
   Arcanum Site Kit — ark-downloads.js — v1.1
   ONE download-button renderer for every site. Renders a uniform row of links
   for whatever formats a chart/table exposes: csv, xlsx, json, parquet, bundle.
   Fixes the class of bug where a `bundle` (or any non-csv) key rendered no link.

   Usage:
     container.appendChild(ArkDownloads.buttons({csv:"/api/x.csv", json:"/api/x.json", bundle:"/api/x.zip"}));
     // or client-side data -> CSV button (no backend needed, e.g. React/Streamlit-injected):
     container.appendChild(ArkDownloads.csvButton(rows, "myfile"));   // rows = array of objects
   ============================================================================= */
(function () {
  "use strict";
  var DOC = document;
  // JSON intentionally absent — DNA DOWNLOAD_AND_FORMATS_STANDARD allows CSV/XLSX/Parquet only.
  var LABEL = { csv: "CSV", xlsx: "XLSX", parquet: "Parquet", bundle: "Bundle (.zip)", zip: ".zip", code: "Code", data: "Data" };
  var ORDER = ["csv", "xlsx", "parquet", "bundle", "zip", "data", "code"];

  function buttons(map, opts) {
    opts = opts || {};
    var wrap = DOC.createElement("div");
    wrap.className = "ark-download" + (opts.className ? " " + opts.className : "");
    if (opts.label !== false) {
      var lab = DOC.createElement("span"); lab.className = "ark-download-label";
      lab.textContent = opts.label || "Download:"; wrap.appendChild(lab);
    }
    var keys = Object.keys(map || {}).sort(function (a, b) {
      var ia = ORDER.indexOf(a), ib = ORDER.indexOf(b); return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    });
    keys.forEach(function (k) {
      if (!map[k] || k === "json") return;  // JSON is not an allowed download format (DNA standard)
      var a = DOC.createElement("a");
      a.className = "ark-btn ark-btn-sm"; a.href = map[k];
      a.setAttribute("download", ""); a.textContent = LABEL[k] || k.toUpperCase();
      wrap.appendChild(a);
    });
    return wrap;
  }

  // Build a CSV download button from in-memory rows (array of objects or array-of-arrays).
  function csvButton(rows, filename, label) {
    var btn = DOC.createElement("button");
    btn.type = "button"; btn.className = "ark-btn ark-btn-sm"; btn.textContent = label || "Download CSV";
    btn.addEventListener("click", function () { downloadCsv(rows, filename); });
    return btn;
  }
  function toCsv(rows) {
    if (!rows || !rows.length) return "";
    var out = [];
    if (Array.isArray(rows[0])) { rows.forEach(function (r) { out.push(r.map(cell).join(",")); }); return out.join("\n"); }
    var cols = Object.keys(rows[0]);
    out.push(cols.map(cell).join(","));
    rows.forEach(function (r) { out.push(cols.map(function (c) { return cell(r[c]); }).join(",")); });
    return out.join("\n");
  }
  function cell(v) { v = (v == null ? "" : String(v)); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
  function downloadCsv(rows, filename) {
    var blob = new Blob([toCsv(rows)], { type: "text/csv;charset=utf-8" });
    var a = DOC.createElement("a"); a.href = URL.createObjectURL(blob);
    a.download = (filename || "data") + ".csv"; DOC.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  window.ArkDownloads = { buttons: buttons, csvButton: csvButton, toCsv: toCsv, downloadCsv: downloadCsv };
})();
