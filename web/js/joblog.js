// Job log viewer (the old "terminal"): fetches new lines of a job's log while it is open,
// colours them by content, auto-scrolls, copies and clears.
import { t } from './i18n.js';
import { el, toast } from './ui.js';
import { api } from './api.js';

function lineClass(text) {
  if (/✖|Traceback|\b(error|failed|exception)\b|錯誤|失敗|⚠/i.test(text)) return 'jl-err';
  if (/✔|✅|\bsucceeded\b|完成/.test(text)) return 'jl-ok';
  if (/▶/.test(text)) return 'jl-stage';
  if (/\b(warning|warn)\b|注意/i.test(text)) return 'jl-warn';
  return '';
}

export function logView() {
  const pre = el('pre', { class: 'joblog' });
  const auto = el('input', { type: 'checkbox', checked: true });
  const autoLabel = el('label', { class: 'check small' }, auto, el('span', {}, t('joblog.autoscroll')));
  const copy = el('button', { class: 'btn small', onclick: async () => {
    try { await navigator.clipboard.writeText(pre.textContent); toast(t('joblog.copied')); }
    catch { toast(t('joblog.copy_failed'), true); }
  } }, t('joblog.copy'));
  const clear = el('button', { class: 'btn small', onclick: () => { pre.replaceChildren(); } }, t('joblog.clear'));
  const panel = el('div', { class: 'joblog-panel hidden' }, el('div', { class: 'row', style: 'gap:8px;align-items:center' }, autoLabel, copy, clear), pre);
  let jobId = null;
  let next = 0;
  let timer = null;
  let busy = false;

  function append(lines) {
    if (!lines.length) return;
    const frag = document.createDocumentFragment();
    for (const line of lines) frag.append(el('div', { class: lineClass(line) }, line));
    pre.append(frag);
    while (pre.childElementCount > 3000) pre.firstElementChild.remove();
    if (auto.checked) pre.scrollTop = pre.scrollHeight;
  }

  async function poll() {
    if (!jobId || busy || panel.classList.contains('hidden')) return;
    busy = true;
    try {
      const res = await api.get(`/api/jobs/${jobId}/log?after=${next}`);
      if (res.skipped) append([t('joblog.skipped', res.skipped)]);
      append(res.lines || []);
      next = res.next;
      if (!['queued', 'running'].includes(res.status)) stop();
    } catch { /* the job may be gone; keep what is shown */ }
    busy = false;
  }
  function start() { if (!timer) timer = setInterval(poll, 1000); poll(); }
  function stop() { clearInterval(timer); timer = null; }

  return {
    el: panel,
    get open() { return !panel.classList.contains('hidden'); },
    follow(id) {
      if (id !== jobId) { jobId = id; next = 0; pre.replaceChildren(); }
      if (this.open) start();
    },
    toggle(force) {
      const show = force === undefined ? panel.classList.contains('hidden') : !!force;
      panel.classList.toggle('hidden', !show);
      try { localStorage.setItem('sign2mv.joblog.open', show ? '1' : '0'); } catch { /* ignore */ }
      if (show && jobId) start(); else stop();
      return show;
    },
  };
}

export function logOpenByDefault() {
  try { return localStorage.getItem('sign2mv.joblog.open') === '1'; } catch { return false; }
}
