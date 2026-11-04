// Auto-translates every piece of the app's own UI text into the selected language.
// Only text that exists in the pre-built dictionary (/i18n/{lang}.json, generated from the app's
// source code) is ever replaced, so customers' own content is never sent anywhere or altered.
const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "TEXTAREA", "INPUT", "CODE", "PRE", "NOSCRIPT", "SELECT"]);
const ATTRS = ["placeholder", "title", "aria-label", "alt"];
const state = { lang: "en-GB", dict: null, observer: null, orig: new WeakMap(), origAttr: new WeakMap() };
const cache = {};

const skipped = (el) => {
  for (let n = el; n && n !== document.body; n = n.parentElement) {
    if (SKIP_TAGS.has(n.tagName) || n.isContentEditable) return true;
    if (n.hasAttribute && (n.hasAttribute("data-no-translate") || n.getAttribute("translate") === "no")) return true;
  }
  return false;
};

const PUNCT_PREFIX = /^([.,;:·—–\-)\s]+)(.+)$/;
const lookup = (key) => {
  if (state.dict[key]) return state.dict[key];
  const m = key.match(PUNCT_PREFIX);
  return m && state.dict[m[2]] ? m[1] + state.dict[m[2]] : null;
};

function translateText(node) {
  const raw = node.nodeValue;
  if (!raw || !/[A-Za-z]/.test(raw)) return;
  const key = raw.replace(/\s+/g, " ").trim();
  const prev = state.orig.get(node);
  if (prev && raw === prev.out) return;
  const hit = lookup(key);
  if (!hit) return;
  if (node.parentElement && skipped(node.parentElement)) return;
  const lead = raw.match(/^\s*/)[0], trail = raw.match(/\s*$/)[0];
  const out = lead + hit + trail;
  state.orig.set(node, { src: raw, out });
  node.nodeValue = out;
}

function translateAttrs(el) {
  for (const a of ATTRS) {
    const v = el.getAttribute && el.getAttribute(a);
    if (!v) continue;
    const saved = state.origAttr.get(el) || {};
    if (saved[a] && saved[a].out === v) continue;
    const hit = state.dict[v.replace(/\s+/g, " ").trim()];
    if (!hit || (el.parentElement && skipped(el.parentElement)) || el.hasAttribute("data-no-translate")) continue;
    saved[a] = { src: v, out: hit };
    state.origAttr.set(el, saved);
    el.setAttribute(a, hit);
  }
}

function walk(root) {
  if (!state.dict || !root) return;
  if (root.nodeType === 3) return translateText(root);
  if (root.nodeType !== 1) return;
  translateAttrs(root);
  if (SKIP_TAGS.has(root.tagName)) return;
  const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  for (let n = tw.nextNode(); n; n = tw.nextNode()) {
    if (n.nodeType === 3) translateText(n); else translateAttrs(n);
  }
}

function restoreAll() {
  const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  for (let n = tw.nextNode(); n; n = tw.nextNode()) {
    if (n.nodeType === 3) {
      const o = state.orig.get(n);
      if (o && n.nodeValue === o.out) n.nodeValue = o.src;
    } else {
      const saved = state.origAttr.get(n);
      if (saved) Object.entries(saved).forEach(([a, o]) => { if (n.getAttribute(a) === o.out) n.setAttribute(a, o.src); });
    }
  }
}

async function loadDict(lang) {
  if (cache[lang]) return cache[lang];
  const res = await fetch(`/i18n/${lang}.json`);
  if (!res.ok) return null;
  cache[lang] = await res.json();
  return cache[lang];
}

export async function setAutoTranslateLang(lang) {
  if (!lang || lang === state.lang) return;
  if (state.dict) restoreAll();
  state.lang = lang;
  state.dict = null;
  if (lang.startsWith("en")) return;
  try {
    const dict = await loadDict(lang);
    if (state.lang !== lang || !dict) return;
    state.dict = dict;
    walk(document.body);
  } catch { /* dictionary unavailable — leave English */ }
  if (!state.observer) {
    state.observer = new MutationObserver((muts) => {
      if (!state.dict) return;
      for (const m of muts) {
        if (m.type === "characterData") translateText(m.target);
        else if (m.type === "attributes") translateAttrs(m.target);
        else m.addedNodes.forEach(walk);
      }
    });
    state.observer.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  }
}
