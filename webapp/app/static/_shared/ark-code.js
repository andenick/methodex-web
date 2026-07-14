/* =============================================================================
   Arcanum Site Kit — ark-code.js — v1.0  (dual-language code block)
   DNA CONTENT_RENDERING_STANDARD §3 (A6): every code chunk is a visible bordered
   box (.ark-code) with a COPY button (.ark-copy) and an R | Python TOGGLE — the
   reader switches language, both are provided, and either can be downloaded as a
   runnable .R / .py file. ONE component, reused on every site and every chunk.

   Enhances a single markup shape (idempotent, framework-free, self-initializing
   on DOMContentLoaded). It REUSES the existing .ark-code / .ark-copy CSS already
   in arcanum.css §12 and only adds the toggle chrome (.ark-code §12 extension).

   ---------------------------------------------------------------------------
   EMBEDDING API  (copy-paste this shape into a Jinja template)
   ---------------------------------------------------------------------------
   A dual-language chunk = one .ark-code box with a data-r and a data-python
   <pre><code> child, each tagged with data-lang. The path/title goes in the
   head; the toggle + copy + download buttons are injected by this script.

     <div class="ark-code" data-arkcode data-filename="us_debt_to_gdp">
       <div class="ark-code-head">
         <span class="ark-code-path">U.S. debt-to-GDP transform</span>
       </div>
       <pre data-lang="r"><code>{% filter forceescape %}{% raw %}# R source here{% endraw %}{% endfilter %}</code></pre>
       <pre data-lang="python"><code>{% filter forceescape %}{% raw %}# Python source here{% endraw %}{% endfilter %}</code></pre>
     </div>

   Notes for Jinja sites:
   - ALWAYS wrap the code in {% raw %}…{% endraw %} and pass through
     {% filter forceescape %}…{% endfilter %} so braces / < / & are literal and
     never parsed as Jinja or HTML (matches the existing gerhard code.html).
   - data-filename (optional) sets the download stem; it gets .R / .py appended.
     Falls back to .ark-code-path text, then "snippet".
   - data-default="python" (optional) picks which language shows first; otherwise
     the script honors the reader's remembered choice (localStorage "ark-code-lang"),
     else defaults to "r".
   - A single-language box (only one data-lang <pre>, or a plain .ark-code with one
     <pre> and no data-lang) still gets a Copy + Download button, just no toggle.
   - You can also feed source via attributes instead of <pre> children:
       <div class="ark-code" data-arkcode data-r="...escaped R..." data-python="...escaped py..."></div>
     (handy for short one-liners; <pre> children are preferred for real chunks.)

   Exposed as window.ArkCode = { enhance }.  Load anywhere after the body markup
   (defer is fine):  <script defer src="/static/_shared/ark-code.js?v={{ asset_ver }}"></script>
   ============================================================================= */
(function () {
  "use strict";
  var DOC = document;
  var SEL = ".ark-code[data-arkcode], .ark-code.ark-code-dual";
  var STORE_KEY = "ark-code-lang";
  var EXT = { r: "R", python: "py" };
  var NICE = { r: "R", python: "Python" };

  function readPref() {
    try { return window.localStorage.getItem(STORE_KEY) || ""; } catch (e) { return ""; }
  }
  function writePref(lang) {
    try { window.localStorage.setItem(STORE_KEY, lang); } catch (e) {}
  }

  // Collect {lang: codeText} for a box from its data-lang <pre> children and/or
  // data-r / data-python attributes. Preserves declared order; R first by convention.
  function sourcesFor(box) {
    var order = [];
    var map = {};
    function add(lang, text, node) {
      if (!lang || text == null) return;
      lang = lang.toLowerCase();
      if (lang === "py") lang = "python";
      if (!(lang in map)) order.push(lang);
      map[lang] = { text: text, node: node || null };
    }
    // 1. data-lang <pre> children (preferred shape)
    box.querySelectorAll("pre[data-lang]").forEach(function (pre) {
      var code = pre.querySelector("code") || pre;
      add(pre.getAttribute("data-lang"), code.textContent, pre);
    });
    // 2. attribute shape (data-r / data-python) — only for langs not already present
    if (box.hasAttribute("data-r") && !("r" in map)) add("r", box.getAttribute("data-r"), null);
    if (box.hasAttribute("data-python") && !("python" in map)) add("python", box.getAttribute("data-python"), null);
    // 3. fallback: a lone <pre> with no data-lang -> single-language box (no toggle)
    if (!order.length) {
      var lone = box.querySelector("pre");
      if (lone) { var c = lone.querySelector("code") || lone; add("text", c.textContent, lone); }
    }
    return { order: order, map: map };
  }

  function downloadText(text, filename) {
    var blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    var a = DOC.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    DOC.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  function slug(s) {
    return String(s || "snippet").trim().toLowerCase()
      .replace(/[^\w.\-]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 60) || "snippet";
  }

  function enhanceBox(box) {
    if (box._arkCode) return;
    box._arkCode = true;

    var src = sourcesFor(box);
    if (!src.order.length) return;            // nothing to enhance
    box.classList.add("ark-code");            // ensure the box style applies

    var multi = src.order.length > 1;
    var stem = box.getAttribute("data-filename") ||
      (box.querySelector(".ark-code-path") && box.querySelector(".ark-code-path").textContent) || "snippet";
    stem = slug(stem);

    // Head: reuse an existing .ark-code-head if present, else create one.
    var head = box.querySelector(".ark-code-head");
    if (!head) {
      head = DOC.createElement("div");
      head.className = "ark-code-head";
      box.insertBefore(head, box.firstChild);
    }

    // Toggle (only when 2+ languages). Buttons are grouped on the left of the head.
    var buttons = {};
    var current = null;
    if (multi) {
      var toggle = DOC.createElement("div");
      toggle.className = "ark-code-toggle";
      toggle.setAttribute("role", "tablist");
      toggle.setAttribute("aria-label", "Code language");
      src.order.forEach(function (lang) {
        var b = DOC.createElement("button");
        b.type = "button";
        b.className = "ark-code-lang";
        b.textContent = NICE[lang] || lang.toUpperCase();
        b.setAttribute("role", "tab");
        b.setAttribute("data-lang", lang);
        b.addEventListener("click", function () { show(lang, true); });
        toggle.appendChild(b);
        buttons[lang] = b;
      });
      // insert toggle at the start of the head (before any path label visually via CSS order)
      head.insertBefore(toggle, head.firstChild);
    }

    // Copy + Download controls (right side of head).
    var copyBtn = head.querySelector(".ark-copy");
    if (!copyBtn) {
      copyBtn = DOC.createElement("button");
      copyBtn.type = "button"; copyBtn.className = "ark-copy"; copyBtn.textContent = "Copy";
      head.appendChild(copyBtn);
    }
    // Claim this button so the legacy arcanum-chrome.js copy wiring skips it —
    // ITS handler copies the first <pre> (the hidden language); ours copies the
    // ACTIVE language. The shared flag is the documented opt-out.
    copyBtn.__arkWired = true;
    copyBtn.addEventListener("click", function () { copyCurrent(); });

    var dlBtn = DOC.createElement("button");
    dlBtn.type = "button"; dlBtn.className = "ark-copy ark-code-dl"; dlBtn.textContent = "Download";
    dlBtn.__arkWired = true;
    head.appendChild(dlBtn);
    dlBtn.addEventListener("click", function () {
      var s = src.map[current]; if (!s) return;
      var ext = EXT[current] || "txt";
      downloadText(s.text, stem + "." + ext);
    });

    function copyCurrent() {
      var s = src.map[current]; if (!s) return;
      var done = function () {
        var old = copyBtn.textContent; copyBtn.textContent = "Copied";
        copyBtn.disabled = true;
        setTimeout(function () { copyBtn.textContent = old; copyBtn.disabled = false; }, 1200);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(s.text).then(done, fallbackCopy);
      } else { fallbackCopy(); }
      function fallbackCopy() {
        var ta = DOC.createElement("textarea");
        ta.value = s.text; ta.style.position = "fixed"; ta.style.opacity = "0";
        DOC.body.appendChild(ta); ta.focus(); ta.select();
        try { DOC.execCommand("copy"); done(); } catch (e) {}
        ta.remove();
      }
    }

    function show(lang, remember) {
      if (!(lang in src.map)) return;
      current = lang;
      src.order.forEach(function (l) {
        var s = src.map[l];
        if (s.node) s.node.hidden = (l !== lang);
        if (buttons[l]) {
          var on = (l === lang);
          buttons[l].classList.toggle("is-active", on);
          buttons[l].setAttribute("aria-selected", on ? "true" : "false");
        }
      });
      var ext = EXT[lang];
      dlBtn.textContent = ext ? "Download ." + ext : "Download";
      if (remember && multi) writePref(lang);
    }

    // Initial language: data-default -> remembered pref -> first declared.
    var initial = (box.getAttribute("data-default") || "").toLowerCase();
    if (initial === "py") initial = "python";
    if (!(initial in src.map)) {
      var pref = readPref();
      initial = (multi && pref in src.map) ? pref : src.order[0];
    }
    show(initial, false);
  }

  function enhance(root) {
    (root || DOC).querySelectorAll(SEL).forEach(enhanceBox);
  }

  DOC.addEventListener("DOMContentLoaded", function () { enhance(DOC); });
  window.ArkCode = { enhance: enhance };
})();
