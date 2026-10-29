// Server and worker messages from the sing & record and MV parts are written in Chinese (as in the
// old systems). In the English UI they are looked up in the two workspaces' own dictionaries:
// /sing/i18n-catalog.mjs (messages + templates) and /mv/i18n.en.json (exact + patterns).
import { language } from './i18n.js';

const HAN = /[㐀-鿿]/;
const exact = new Map();
let patterns = [];
let ready = false;
const waiters = new Set();

function compile(zh, en, translate) {
  const parts = zh.split(/\{(\d+)\}/);
  let src = '^';
  const order = [];
  parts.forEach((part, i) => {
    if (i % 2) { src += '([\\s\\S]*?)'; order.push(Number(part)); }
    else src += part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  });
  return { re: new RegExp(src + '$'), order, en, translate, fixed: zh.replace(/\{\d+\}/g, '').length };
}

async function load() {
  const [mv, sing] = await Promise.all([
    fetch('/mv/i18n.en.json').then((r) => (r.ok ? r.json() : null)).catch(() => null),
    import('/sing/i18n-catalog.mjs').catch(() => null),
  ]);
  const pats = [];
  if (sing) {
    for (const [k, v] of Object.entries(sing.messages || {})) exact.set(k, v);
    for (const [zh, en, tr = []] of sing.templates || []) pats.push(compile(zh, en, tr));
  }
  if (mv) {
    for (const [k, v] of Object.entries(mv.exact || {})) if (!exact.has(k)) exact.set(k, v);
    for (const p of mv.patterns || []) if (p && p.zh && p.en) pats.push(compile(p.zh, p.en, null));
  }
  patterns = pats.sort((a, b) => b.fixed - a.fixed);
  ready = true;
  waiters.forEach((fn) => fn());
}
load();

// Call fn once the dictionaries are in (to re-render text shown before that).
export function onServerTextReady(fn) { if (ready) fn(); else waiters.add(fn); }

export function srvText(text, depth = 0) {
  if (typeof text !== 'string' || language() !== 'en' || !ready || !HAN.test(text) || depth > 4) return text;
  const m = text.match(/^(\s*)([\s\S]*?)(\s*)$/);
  const core = m[2];
  let out = exact.get(core);
  if (out === undefined) {
    for (const p of patterns) {
      const r = core.match(p.re);
      if (!r) continue;
      const vals = {};
      p.order.forEach((n, i) => { vals[n] = r[i + 1]; });
      // MV patterns translate every value; sing templates only the listed slots
      out = p.en.replace(/\{(\d+)\}/g, (_, n) => {
        const v = vals[n] ?? '';
        return !p.translate || p.translate.includes(Number(n)) ? srvText(v, depth + 1) : v;
      });
      break;
    }
  }
  if (out === undefined && core.includes('\n')) {
    const joined = core.split('\n').map((l) => srvText(l, depth + 1)).join('\n');
    if (joined !== core) out = joined;
  }
  return out === undefined ? text : m[1] + out + m[3];
}
