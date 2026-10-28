// A small inline progress display for one job.
import { t, errorText } from './i18n.js';
import { el, toast } from './ui.js';
import { waitJob } from './app-state.js';
import { api } from './api.js';

export function jobBox({ cancel = true } = {}) {
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
  const box = el('div', { class: 'jobbox hidden' }, el('div', { class: 'row', style: 'align-items:center' }, label, stop), bar);
  function show(job) {
    box.classList.remove('hidden');
    current = job.id;
    stop.textContent = t('common.cancel');
    stop.classList.toggle('hidden', !cancel || !['queued', 'running'].includes(job.status));
    const pct = job.percent;
    let text;
    if (job.status === 'queued') text = t('jobs.queued_pos', job.position || 1);
    else if (job.status === 'running') text = `${t('jobs.status.running')}${job.stage ? ' · ' + t(`stage.${job.stage}`) : ''}${pct != null ? ` ${pct.toFixed(0)}%` : ''}${job.message ? ' · ' + job.message : ''}`;
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
