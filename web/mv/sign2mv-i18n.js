// English for the MV workspace page (the MV Studio page is written in Chinese).
// With ?lang=en, every text node and placeholder/title shown on the page is
// looked up in /mv/i18n.en.json ("exact" strings and "patterns" with {0}, {1}…)
// and replaced; texts that are added later (status, toasts, server messages)
// are translated as they appear. Without ?lang=en this file does nothing.
(function () {
  'use strict';
  const lang = new URLSearchParams(location.search).get('lang') || '';
  if (!/^en/i.test(lang)) return;
  let table = { exact: {}, patterns: [] };
  try {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', '/mv/i18n.en.json', false);   // before the page script renders anything
    xhr.send();
    if (xhr.status === 200) table = JSON.parse(xhr.responseText);
  } catch (e) { /* keep Chinese */ }
  document.documentElement.lang = 'en';
  const exact = new Map(Object.entries(table.exact || {}));
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const patterns = (table.patterns || []).filter((p) => p && p.zh && p.en).map((p) => {
    const parts = p.zh.split(/\{(\d+)\}/);
    let src = '^';
    const order = [];
    parts.forEach((part, i) => {
      if (i % 2) { src += '([\\s\\S]*?)'; order.push(Number(part)); } else src += esc(part);
    });
    return { re: new RegExp(src + '$'), order, en: p.en, fixed: p.zh.replace(/\{\d+\}/g, '').length };
  }).sort((a, b) => b.fixed - a.fixed);
  const HAN = /[㐀-鿿]/;
  const cache = new Map();

  function tr(text) {
    if (!text || !HAN.test(text)) return text;
    if (cache.has(text)) return cache.get(text);
    const m = text.match(/^(\s*)([\s\S]*?)(\s*)$/);
    const core = m[2];
    let out = exact.get(core);
    if (out === undefined) {
      for (const p of patterns) {
        const r = core.match(p.re);
        if (!r) continue;
        const vals = {};
        p.order.forEach((n, i) => { vals[n] = r[i + 1]; });
        out = p.en.replace(/\{(\d+)\}/g, (_, n) => tr(vals[n] ?? ''));
        break;
      }
    }
    if (out === undefined) {
      // multi-line text: translate line by line
      if (core.includes('\n')) {
        const lines = core.split('\n').map((l) => tr(l));
        out = lines.join('\n');
        if (out === core) out = undefined;
      }
    }
    const res = out === undefined ? text : m[1] + out + m[3];
    if (cache.size > 5000) cache.clear();
    cache.set(text, res);
    return res;
  }
  window.sign2mvTr = tr;

  const ATTRS = ['placeholder', 'title', 'aria-label'];
  function fixNode(node) {
    if (node.nodeType === 3) {
      const p = node.parentNode;
      if (p && (p.nodeName === 'SCRIPT' || p.nodeName === 'STYLE' || p.nodeName === 'TEXTAREA')) return;
      const v = tr(node.nodeValue);
      if (v !== node.nodeValue) node.nodeValue = v;
      return;
    }
    if (node.nodeType !== 1) return;
    if (node.nodeName === 'SCRIPT' || node.nodeName === 'STYLE' || node.nodeName === 'TEXTAREA') return;
    for (const a of ATTRS) {
      const v = node.getAttribute(a);
      if (v && HAN.test(v)) { const t = tr(v); if (t !== v) node.setAttribute(a, t); }
    }
    if (node.nodeName === 'INPUT' && /^(button|submit)$/i.test(node.type) && HAN.test(node.value)) node.value = tr(node.value);
    for (const c of node.childNodes) fixNode(c);
  }
  const obs = new MutationObserver((list) => {
    for (const m of list) {
      if (m.type === 'characterData') fixNode(m.target);
      else if (m.type === 'attributes') fixNode(m.target);
      else m.addedNodes.forEach(fixNode);
    }
  });
  function start() {
    fixNode(document.documentElement);
    obs.observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true,
      attributeFilter: ATTRS });
  }
  if (document.documentElement) start();
  for (const fn of ['alert', 'confirm', 'prompt']) {
    const orig = window[fn].bind(window);
    window[fn] = (msg, ...rest) => orig(tr(String(msg ?? '')), ...rest);
  }
})();
