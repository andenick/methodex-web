/* Methodex — minimal progressive enhancement.
 * Plotly timelines are hydrated inline per page (see statistic.html).
 * This file adds a couple of small niceties; the site works without JS. */
(function () {
  "use strict";

  // Submit the explorer search form on Enter without requiring the button.
  // (Native form behavior already does this; kept as a hook for future JS.)

  // Make any element with [data-copy] copy its target's text to clipboard.
  document.addEventListener("click", function (ev) {
    var el = ev.target.closest("[data-copy]");
    if (!el) return;
    var sel = el.getAttribute("data-copy");
    var src = document.querySelector(sel);
    if (src && navigator.clipboard) {
      navigator.clipboard.writeText(src.textContent || "").then(function () {
        var old = el.textContent;
        el.textContent = "copied";
        setTimeout(function () { el.textContent = old; }, 1200);
      });
    }
  });
})();
