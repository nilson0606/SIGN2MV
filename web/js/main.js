// SIGN2MV web app shell: navigation, language, status, library, jobs, settings.
import { api } from './api.js';
import { t, setLanguage, language, errorText, onLanguageChange } from './i18n.js';
import { $, $$, el, toast, confirmDialog, fmtBytes } from './ui.js';
import { bus, pages, registerPage } from './app-state.js';

const WEB_API_LEVEL = 1;
let status = null;

// ---------------- navigation ----------------
function showPage(name) {
  if (!$(`#page-${name}`)) name = 'home';
  $$('section.page').forEach((s) => s.classList.toggle('active', s.id === `page-${name}`));
  $$('#tabs button').forEach((b) => b.classList.toggle('active', b.dataset.page === name));
  try { localStorage.setItem('sign2mv.page', name); } catch { /* storage may be unavailable */ }
  const page = pages.get(name);
  if (page && page.onShow) page.onShow();
}
$$('#tabs button').forEach((b) => b.addEventListener('click', () => showPage(b.dataset.page)));
$$('[data-goto]').forEach((b) => b.addEventListener('click', () => showPage(b.dataset.goto)));
bus.addEventListener('goto', (e) => showPage(e.detail));

// ---------------- language ----------------
function updateManualLink() {
  $('#manual-link').href = `/manual/manual.${language()}.html`;
  $('#lang-select').value = language();
}
onLanguageChange(() => { updateManualLink(); renderStatus(); renderJobs(); });
$('#lang-select').addEventListener('change', async (e) => {
  setLanguage(e.target.value);
  try { await api.put('/api/settings', { language: e.target.value }); } catch (err) { toast(errorText(err), true); }
});

// ---------------- status ----------------
function renderStatus() {
  const kv = $('#status-kv');
  if (!status) { kv.replaceChildren(); return; }
  const ins = status.install || {};
  const rows = [
    [t('home.version'), `${status.version} (API ${status.api_level})`],
    [t('home.folder'), status.root],
    [t('home.install'), ins.completed ? t('home.install_ok') : t('home.install_missing')],
    [t('home.device'), ins.device === 'cuda' ? `GPU · ${ins.gpu_name || ''}` : (ins.device ? t('home.cpu_mode') : '-')],
  ];
  if (ins.c_drive_delta_bytes !== null && ins.c_drive_delta_bytes !== undefined) {
    rows.push([t('home.c_delta'), fmtBytes(ins.c_drive_delta_bytes)]);
  }
  const checks = ins.checks || {};
  for (const [name, ok] of Object.entries(checks)) {
    rows.push([t('home.check', name), ok ? '✅' : '❌']);
  }
  kv.replaceChildren(...rows.flatMap(([k, v]) => [el('dt', {}, k), el('dd', {}, v)]));
}

async function loadStatus(first = false) {
  try {
    status = await api.get('/api/system/status');
    window.SIGN2MV_STATUS = status;
    if (first) {
      setLanguage(status.language);
      updateManualLink();
    }
    const banner = $('#version-banner');
    if (status.api_level > WEB_API_LEVEL) {
      banner.textContent = t('banner.reload_page');
      banner.classList.remove('hidden');
    } else if (status.api_level < WEB_API_LEVEL) {
      banner.textContent = t('banner.restart_server');
      banner.classList.remove('hidden');
    } else {
      banner.classList.add('hidden');
    }
    renderStatus();
  } catch (err) {
    if (first) setLanguage('zh-TW');
  }
}

// ---------------- shutdown ----------------
$('#shutdown-btn').addEventListener('click', async () => {
  const busyPages = [...pages.values()].filter((p) => p.busy && p.busy());
  const message = busyPages.length ? `${busyPages.map((p) => p.busyText()).join('\n')}\n\n${t('shutdown.confirm')}` : t('shutdown.confirm');
  if (!(await confirmDialog(message, t('nav.shutdown')))) return;
  let force = false;
  try {
    await api.post('/api/system/shutdown', { force: false });
  } catch (err) {
    if (err.code === 'jobs_running') {
      const n = (err.data && err.data.jobs || []).length;
      if (!(await confirmDialog(t('shutdown.jobs_running', n), t('shutdown.force')))) return;
      force = true;
      try { await api.post('/api/system/shutdown', { force: true }); } catch (e2) { toast(errorText(e2), true); return; }
    } else if (err.code !== 'server_unreachable') {
      toast(errorText(err), true); return;
    }
  }
  bus.dispatchEvent(new CustomEvent('shutdown', { detail: { force } }));
  document.body.append(el('div', { class: 'shutdown-screen' }, t('shutdown.done')));
});

// ---------------- jobs ----------------
let jobs = [];

function jobLine(j) {
  const pct = j.percent;
  const bar = el('div', { class: 'bar' + (j.status === 'running' && (pct === null || pct === undefined) ? ' indet' : '') },
    el('div', { style: `width:${pct || 0}%` }));
  const statusText = j.status === 'queued' ? t('jobs.queued_pos', j.position) : t(`jobs.status.${j.status}`);
  const detail = j.error_code ? errorText({ code: j.error_code }) + (j.error_message ? ` (${j.error_message.slice(0, 160)})` : '') : (j.message || '');
  return el('div', { class: 'item' },
    el('div', { class: 'grow' },
      el('div', {}, el('span', { class: 'badge gpu' }, j.lane === 'gpu' ? t('jobs.lane_gpu') : t('jobs.lane_cpu')), ' ',
        el('b', {}, j.title || j.kind), ' ', el('span', { class: `badge ${j.status}` }, statusText),
        pct !== null && pct !== undefined && j.status === 'running' ? ` ${pct.toFixed(0)}%` : ''),
      el('div', { class: 'muted small' }, detail),
      j.status === 'running' ? bar : null),
    ['queued', 'running'].includes(j.status)
      ? el('button', { class: 'btn small', onclick: () => cancelJob(j) }, t('common.cancel')) : null);
}

function renderJobs() {
  const list = $('#job-list');
  const shown = [...jobs].reverse().slice(0, 60);
  list.replaceChildren(...(shown.length ? shown.map(jobLine) : [el('div', { class: 'empty' }, t('jobs.empty'))]));
  const active = jobs.filter((j) => ['queued', 'running'].includes(j.status)).length;
  const ind = $('#queue-indicator');
  ind.textContent = active ? t('jobs.active_n', active) : t('jobs.idle');
  ind.classList.toggle('running', active > 0);
}

async function cancelJob(j) {
  try { await api.post(`/api/jobs/${j.id}/cancel`); await loadJobs(); } catch (err) { toast(errorText(err), true); }
}

async function loadJobs() {
  try {
    const data = await api.get('/api/jobs');
    const before = new Map(jobs.map((j) => [j.id, j.status]));
    jobs = data.jobs || [];
    for (const j of jobs) {
      const prev = before.get(j.id);
      if (prev && prev !== j.status) bus.dispatchEvent(new CustomEvent('job-finished', { detail: j }));
    }
    bus.dispatchEvent(new CustomEvent('jobs', { detail: jobs }));
    renderJobs();
  } catch { /* server may be shutting down */ }
}
bus.addEventListener('reload-jobs', loadJobs);
$('#jobs-clear').addEventListener('click', async () => {
  try { const res = await api.post('/api/jobs/clear-finished'); toast(t('jobs.cleared', res.cleared)); await loadJobs(); }
  catch (err) { toast(errorText(err), true); }
});

async function addDemo(lane) {
  const seconds = Number($('#demo-seconds').value) || 10;
  try { await api.post('/api/jobs', { kind: 'demo', lane, seconds, title: t('jobs.demo_title') }); await loadJobs(); }
  catch (err) { toast(errorText(err), true); }
}
$('#demo-gpu').addEventListener('click', () => addDemo('gpu'));
$('#demo-cpu').addEventListener('click', () => addDemo('cpu'));

// ---------------- settings ----------------
async function loadSettings() {
  try {
    const s = await api.get('/api/settings');
    $('#set-library').value = s.library_dir || '';
    $('#set-singer').value = s.cover_singer_name || '';
    $('#set-studio').value = s.studio_name || '';
    bus.dispatchEvent(new CustomEvent('settings', { detail: s }));
  } catch (err) { toast(errorText(err), true); }
}
$('#set-library-save').addEventListener('click', async () => {
  try { await api.put('/api/settings', { library_dir: $('#set-library').value }); toast(t('common.saved')); await loadSettings(); bus.dispatchEvent(new Event('reload-songs')); }
  catch (err) { toast(errorText(err), true); }
});
$('#set-names-save').addEventListener('click', async () => {
  try { await api.put('/api/settings', { cover_singer_name: $('#set-singer').value, studio_name: $('#set-studio').value }); toast(t('common.saved')); }
  catch (err) { toast(errorText(err), true); }
});

registerPage('jobs', { onShow: loadJobs });
registerPage('settings', { onShow: loadSettings });
registerPage('home', { onShow: () => loadStatus() });

// ---------------- start ----------------
(async function start() {
  await loadStatus(true);
  await import('./library.js');
  await Promise.all([loadJobs(), loadSettings()]);
  bus.dispatchEvent(new Event('reload-songs'));
  let last = 'home';
  try { last = localStorage.getItem('sign2mv.page') || 'home'; } catch { /* ignore */ }
  // Later stages add their own pages; give their modules a chance to load first.
  await Promise.allSettled([import('./workspaces.js')]);
  showPage(last);
  setInterval(loadJobs, 1000);
  setInterval(() => loadStatus(), 15000);
})();
