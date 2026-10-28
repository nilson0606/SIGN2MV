// A small inline progress display for one job.
import { t, errorText } from './i18n.js';
import { el, toast } from './ui.js';
import { waitJob } from './app-state.js';
import { api } from './api.js';
import { logView, logOpenByDefault } from './joblog.js';

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
  const logBtn = el('button', { class: 'btn small', onclick: () => { logBtn.textContent = (log.toggle() ? '▾ ' : '▸ ') + t('joblog.title'); } },
    (logOpenByDefault() ? '▾ ' : '▸ ') + t('joblog.title'));
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
    if (job.status === 'queued') text = t('jobs.queued_pos', job.position || 1);
    else if (job.status === 'running') {
      const took = job.started_at ? Math.max(0, Math.round(Date.now() / 1000 - job.started_at)) : null;   // old progress showed the seconds
      text = `${t('jobs.status.running')}${job.stage ? ' · ' + t(`stage.${job.stage}`) : ''}${pct != null ? ` ${pct.toFixed(0)}%` : ''}${job.message ? ' · ' + job.message : ''}${took != null ? ` （${took >= 60 ? `${Math.floor(took / 60)}:${String(took % 60).padStart(2, '0')}` : t('jobs.seconds', took)}）` : ''}`;
    }
    else if (job.status === 'succeeded') text = t('jobs.status.succeeded');
    else text = `${t(`jobs.status.${job.status}`)}: ${errorText({ code: job.error_code })}${job.error_message ? ' — ' + job.error_message.slice(-300) : ''}`;
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
