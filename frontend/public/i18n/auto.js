/* AI Advocate — auto-translate for static pages (landing + guides). Uses the same dictionaries as the app. */
(function () {
  var SUPPORTED = ["en-GB", "es-ES", "fr-FR", "ar-IQ", "pl-PL", "de-DE", "hi-IN", "ur-PK", "it-IT", "pt-PT", "zh-CN"];
  var RTL = ["ar-IQ", "ur-PK"];
  var SKIP = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, INPUT: 1, CODE: 1, PRE: 1, NOSCRIPT: 1, SELECT: 1, OPTION: 1 };
  var ATTRS = ["placeholder", "title", "aria-label", "alt"];
  var dict = null;

  function pickLang() {
    try {
      var q = new URLSearchParams(location.search).get("lang");
      if (q && SUPPORTED.indexOf(q) >= 0) { localStorage.setItem("aa_lang", q); return q; }
      var s = localStorage.getItem("aa_lang");
      if (s && SUPPORTED.indexOf(s) >= 0) return s;
    } catch (e) { /* storage blocked */ }
    var nav = (navigator.language || "en").slice(0, 2).toLowerCase();
    for (var i = 0; i < SUPPORTED.length; i++) if (SUPPORTED[i].slice(0, 2) === nav) return SUPPORTED[i];
    return "en-GB";
  }

  function skipped(el) {
    for (var n = el; n && n !== document.body; n = n.parentElement) {
      if (SKIP[n.tagName] || (n.hasAttribute && n.hasAttribute("data-no-translate"))) return true;
    }
    return false;
  }

  function tText(node) {
    var raw = node.nodeValue;
    if (!raw || !/[A-Za-z]/.test(raw)) return;
    var key = raw.replace(/\s+/g, " ").trim();
    var hit = dict[key];
    if (!hit) { var m = key.match(/^([.,;:·—–\-)\s]+)(.+)$/); if (m && dict[m[2]]) hit = m[1] + dict[m[2]]; }
    if (!hit || (node.parentElement && skipped(node.parentElement))) return;
    node.nodeValue = raw.match(/^\s*/)[0] + hit + raw.match(/\s*$/)[0];
  }

  function tAttrs(el) {
    for (var i = 0; i < ATTRS.length; i++) {
      var v = el.getAttribute && el.getAttribute(ATTRS[i]);
      var hit = v && dict[v.replace(/\s+/g, " ").trim()];
      if (hit && !(el.parentElement && skipped(el.parentElement))) el.setAttribute(ATTRS[i], hit);
    }
  }

  function walk(root) {
    if (root.nodeType === 3) return tText(root);
    if (root.nodeType !== 1) return;
    tAttrs(root);
    if (SKIP[root.tagName]) return;
    var tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    for (var n = tw.nextNode(); n; n = tw.nextNode()) { if (n.nodeType === 3) tText(n); else tAttrs(n); }
  }

  function wirePicker(lang) {
    var sel = document.getElementById("aa-lang-picker");
    if (!sel) return;
    sel.value = lang;
    sel.addEventListener("change", function () {
      try { localStorage.setItem("aa_lang", sel.value); } catch (e) { /* ignore */ }
      location.reload();
    });
  }

  function start() {
    var lang = pickLang();
    wirePicker(lang);
    if (lang === "en-GB") return;
    document.documentElement.lang = lang;
    if (RTL.indexOf(lang) >= 0) document.documentElement.dir = "rtl";
    fetch("/i18n/" + lang + ".json").then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) return;
        dict = d;
        walk(document.body);
        new MutationObserver(function (muts) {
          muts.forEach(function (m) { m.addedNodes.forEach(walk); });
        }).observe(document.body, { childList: true, subtree: true });
      }).catch(function () { /* stay in English */ });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
