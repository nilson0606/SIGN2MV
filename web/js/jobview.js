// A small inline progress display for one job.
import { t, errorText } from './i18n.js';
import { el, toast } from './ui.js';
import { waitJob } from './app-state.js';
import { api } from './api.js';
import { logView, logOpenByDefault } from './joblog.js';
import { srvText } from './srvtext.js';

// workers that report their own words as the stage (MV Whisper) show them as they are;
// "lead:load" = the step "load" of the stage "lead" (a step without a percentage)
export function stageText(stage) {
  const [base, sub] = String(stage || '').split(':');
  const k = `stage.${base}`; const v = t(k);
  const name = v === k ? srvText(base) : v;
  return sub ? `${name} · ${t(`stage.sub.${sub}`)}` : name;
}
// a queued job says which job it is waiting for
export function queuedText(job) {
  return t('jobs.queued_pos', job.position || 1) + (job.waiting_for ? ' · ' + t('jobs.waiting_for', srvText(job.waiting_for)) : '');
}
export function elapsedText(job) {
  if (!job.started_at) return '';
  const took = Math.max(0, Math.round(Date.now() / 1000 - job.started_at));
  return took >= 60 ? `${Math.floor(took / 60)}:${String(took % 60).padStart(2, '0')}` : t('jobs.seconds', took);
}

export function jobBox({ cancel = true, onUpdate = null } = {}) {
  const label = el('div', { class: 'small grow' });
  const fill = el('div');
  const bar = el('div', { class: 'bar' }, fill);
  let current = null;
  const stop = el('button', { class: 'btn small hidden', onclick: async () => {
    if (!current) return;
    stop.disabled = true;
    try { await api.post(`/api/jobs/${current}/cancel`, {}); } catch (err) { toast(errorText(err), true); }
    stop.disabled = false;
  } }, t('common.cancel'));
  const log = logView();
  const logArrow = el('span', {}, logOpenByDefault() ? '▾ ' : '▸ ');
  const logBtn = el('button', { class: 'btn small', onclick: () => { logArrow.textContent = log.toggle() ? '▾ ' : '▸ '; } },
    logArrow, el('span', { 'data-i18n': 'joblog.title' }, t('joblog.title')));
  if (logOpenByDefault()) log.toggle(true);
  const box = el('div', { class: 'jobbox hidden' }, el('div', { class: 'row', style: 'align-items:center' }, label, logBtn, stop), bar, log.el);
  function show(job) {
    box.classList.remove('hidden');
    current = job.id;
    log.follow(job.id);
    if (onUpdate) onUpdate(job);
    stop.textContent = t('common.cancel');
    stop.classList.toggle('hidden', !cancel || !['queued', 'running'].includes(job.status));
    const pct = job.percent;
    let text;
    if (job.status === 'queued') text = queuedText(job);
    else if (job.status === 'running') {
      const took = elapsedText(job);   // old progress showed the seconds
      text = `${t('jobs.status.running')}${job.stage ? ' · ' + stageText(job.stage) : ''}${pct != null ? ` ${pct.toFixed(0)}%` : ''}${job.message ? ' · ' + srvText(job.message) : ''}${took ? ` （${took}）` : ''}`;
    }
    else if (job.status === 'succeeded') text = t('jobs.status.succeeded');
    else if (job.status === 'cancelled' && !job.error_code) text = t('jobs.status.cancelled');   // was "cancelled: error [object Object]"
    else text = `${t(`jobs.status.${job.status}`)}: ${errorText({ code: job.error_code })}${job.error_message ? ' — ' + srvText(job.error_message.slice(-300)) : ''}`;
    label.textContent = text;
    bar.classList.toggle('indet', job.status === 'running' && pct == null);
    fill.style.width = `${job.status === 'succeeded' ? 100 : (pct || 0)}%`;
    bar.classList.toggle('hidden', !['queued', 'running'].includes(job.status));
  }
  return {
    el: box,
    hide() { box.classList.add('hidden'); },
    async follow(job) { show(job); const fin = await waitJob(job.id, show); show(fin); return fin; },
  };
}
