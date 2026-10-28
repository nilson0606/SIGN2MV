// MV workspace: two kinds of MV.
//  - Quick MV: an audio-reactive title card made straight from the audio (sign_record's "製作 MV").
//  - Full MV: the MV Studio page (photos, lyrics, timeline) in an iframe (/mv/) using /api/mv.
import { api } from './api.js';
import { $, el, toast, confirmDialog, fmtBytes, fmtDate, fmtTime } from './ui.js';
import { t, language, onLanguageChange, errorText } from './i18n.js';
import { bus, registerPage, state, goto, mediaUrl } from './app-state.js';
import { jobBox } from './jobview.js';

const page = $('#page-mv');
const frame = el('iframe', { id: 'mv-frame', class: 'workspace-frame', title: 'mv', allow: 'autoplay; fullscreen', allowfullscreen: true });
const tabQuick = el('button', { class: 'cv-chip', onclick: () => setTab('quick') });
const tabFull = el('button', { class: 'cv-chip', onclick: () => setTab('full') });
const tabs = el('div', { class: 'mv-tabs' }, tabQuick, tabFull);
const quickPane = el('div', { class: 'mv-quick' });
const fullPane = el('div', { class: 'mv-full' }, frame);
page.replaceChildren(tabs, quickPane, fullPane);

let loaded = false;
let ready = false;
let pending = null;
let busy = false;
let tab = 'full';
try { tab = localStorage.getItem('sign2mv.mv.tab') === 'quick' ? 'quick' : 'full'; } catch { /* storage unavailable */ }

function setTab(name) {
  tab = name === 'quick' ? 'quick' : 'full';
  try { localStorage.setItem('sign2mv.mv.tab', tab); } catch { /* ignore */ }
  tabQuick.classList.toggle('active', tab === 'quick');
  tabFull.classList.toggle('active', tab === 'full');
  quickPane.classList.toggle('hidden', tab !== 'quick');
  fullPane.classList.toggle('hidden', tab !== 'full');
  if (tab === 'full') load();
  else quick.show();
}
function labelTabs() {
  tabQuick.textContent = t('mv.tab_quick');
  tabFull.textContent = t('mv.tab_full');
  tabQuick.title = t('qmv.hint');
  tabFull.title = t('mv.full_hint');
}

// ------------------------------------------------------------------ full MV (iframe)
function load() {
  if (loaded) return;
  loaded = true;
  frame.src = `/mv/index.html?lang=${language() === 'en' ? 'en' : 'zh-TW'}`;
}
function send(message) { frame.contentWindow?.postMessage(message, location.origin); }
function openSong(songId, renderId) {
  load();
  const msg = { type: 'sign2mv:mv-open', songId, renderId: renderId || '' };
  if (ready) send(msg); else pending = msg;
}

window.addEventListener('message', (event) => {
  if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
  const m = event.data || {};
  if (m.type === 'sign2mv:mv-ready') {
    ready = true;
    if (pending) { send(pending); pending = null; }
  }
});
frame.addEventListener('load', () => { ready = false; });

// ------------------------------------------------------------------ quick MV
const quick = (() => {
  const songSel = el('select', { onchange: () => loadSong(songSel.value) });
  const srcSel = el('select', { onchange: () => fillStudio(true) });
  // look (sign_record card / AI_COVER_MV studio card) and size (old 1080p / 720p buttons); remembered
  const pref = (k, d) => { try { return localStorage.getItem(`sign2mv.qmv.${k}`) || d; } catch { return d; } };
  const keep = (k, v) => { try { localStorage.setItem(`sign2mv.qmv.${k}`, v); } catch { /* ignore */ } };
  const styleSel = el('select', { onchange: () => { keep('style', styleSel.value); studioBox.classList.toggle('hidden', styleSel.value !== 'studio'); texts(); } });
  const resSel = el('select', { onchange: () => keep('res', resSel.value) });
  const studioIn = {
    subtitle: el('input', { type: 'text', maxlength: 80, style: 'flex:1;min-width:240px' }),
    badge: el('input', { type: 'text', maxlength: 30, style: 'min-width:180px' }),
    credits: el('input', { type: 'text', maxlength: 120, style: 'flex:1;min-width:240px' }),
  };
  Object.values(studioIn).forEach((i) => i.addEventListener('input', () => { i.dataset.edited = '1'; }));
  const studioLabels = { subtitle: el('span'), badge: el('span'), credits: el('span'), style: el('span'), res: el('span') };
  const studioNote = el('p', { class: 'muted small' });
  const studioReset = el('button', { class: 'btn small', onclick: () => fillStudio(true, true) });
  const studioBox = el('div', { class: 'hidden' },
    el('div', { class: 'row' }, el('label', { style: 'flex:1;display:flex;gap:6px;align-items:center' }, studioLabels.subtitle, studioIn.subtitle)),
    el('div', { class: 'row' }, el('label', { style: 'display:flex;gap:6px;align-items:center' }, studioLabels.badge, studioIn.badge), studioReset),
    el('div', { class: 'row' }, el('label', { style: 'flex:1;display:flex;gap:6px;align-items:center' }, studioLabels.credits, studioIn.credits)),
    studioNote);
  function fillStudio(_sourceChanged, force) {
    const src = data && data.sources.find((x) => x.id === srcSel.value);
    const d = (src && src.studio) || {};
    for (const [k, inp] of Object.entries(studioIn)) {
      if (force || !inp.dataset.edited) { inp.value = d[k] || ''; delete inp.dataset.edited; }   // keep what the user typed
    }
  }
  const title = el('input', { type: 'text', maxlength: 60, style: 'flex:1;min-width:240px' });
  const artist = el('input', { type: 'text', maxlength: 50, style: 'min-width:180px' });
  const labelSpan = el('span', { class: 'muted' });
  const singerHint = el('p', { class: 'muted small hidden' });
  const fontWarn = el('p', { class: 'small hidden', style: 'color:var(--bad, #f87171)' });
  const jb = jobBox();
  const makeBtn = el('button', { class: 'btn primary', onclick: () => make() });
  const list = el('div', { class: 'list' });
  // list scope: this song or every song (sign_record's saved-MV panel: search, select, delete, clear all)
  let scope = 'song';
  try { scope = localStorage.getItem('sign2mv.qmv.scope') === 'all' ? 'all' : 'song'; } catch { /* ignore */ }
  const scopeSong = el('button', { class: 'cv-chip', onclick: () => setScope('song') });
  const scopeAll = el('button', { class: 'cv-chip', onclick: () => setScope('all') });
  const search = el('input', { type: 'search', style: 'min-width:200px', oninput: () => renderList() });
  const selAll = el('input', { type: 'checkbox', onchange: () => { list.querySelectorAll('input.qmv-pick').forEach((c) => { c.checked = selAll.checked; }); } });
  const selAllLabel = el('label', { class: 'check' }, selAll, el('span'));
  const delSel = el('button', { class: 'btn small danger', onclick: () => deleteSelected() });
  const clearAll = el('button', { class: 'btn small danger', onclick: () => deleteAll() });
  const folder = el('div', { class: 'muted small' });
  const tools = el('div', { class: 'row', style: 'align-items:center;gap:8px' }, scopeSong, scopeAll, search, selAllLabel, delSel, clearAll);
  let allData = null;
  const head = el('h2', { style: 'margin:0' });
  const hint = el('p', { class: 'muted small' });
  const labels = { song: el('span'), source: el('span'), title: el('span'), artist: el('span'), list: el('h3') };
  quickPane.append(el('div', { class: 'panel' },
    head, hint,
    el('div', { class: 'row' }, el('label', {}, labels.song, ' ', songSel), el('label', {}, labels.source, ' ', srcSel)),
    el('div', { class: 'row' }, el('label', {}, studioLabels.style, ' ', styleSel), el('label', {}, studioLabels.res, ' ', resSel)),
    el('div', { class: 'row' }, el('label', { style: 'flex:1;display:flex;gap:6px;align-items:center' }, labels.title, title)),
    el('div', { class: 'row' }, el('label', { style: 'display:flex;gap:6px;align-items:center' }, labels.artist, labelSpan, artist)),
    studioBox, singerHint, fontWarn,
    el('div', { class: 'row' }, makeBtn), jb.el,
    labels.list, tools, folder, list));
  let songId = null;
  let data = null;
  let wantSource = null;

  function texts() {
    head.textContent = t('qmv.title');
    hint.textContent = t('qmv.hint');
    labels.song.textContent = t('qmv.song');
    labels.source.textContent = t('qmv.source');
    labels.title.textContent = t('qmv.mv_title');
    labels.artist.textContent = t('qmv.artist');
    labels.list.textContent = t(scope === 'all' ? 'qmv.list_all' : 'qmv.list');
    makeBtn.textContent = t('qmv.make');
    const sv = styleSel.value || pref('style', 'card');
    styleSel.replaceChildren(el('option', { value: 'card' }, t('qmv.style_card')), el('option', { value: 'studio' }, t('qmv.style_studio')));
    styleSel.value = sv;
    const rv = resSel.value || pref('res', '1080p');
    resSel.replaceChildren(el('option', { value: '1080p' }, t('qmv.res_1080')), el('option', { value: '720p' }, t('qmv.res_720')));
    resSel.value = rv;
    studioBox.classList.toggle('hidden', sv !== 'studio');
    studioLabels.style.textContent = t('qmv.style');
    studioLabels.res.textContent = t('qmv.res');
    studioLabels.subtitle.textContent = t('qmv.subtitle');
    studioLabels.badge.textContent = t('qmv.badge');
    studioLabels.credits.textContent = t('qmv.credits');
    studioReset.textContent = t('qmv.studio_reset');
    studioNote.textContent = t('qmv.studio_note');
    singerHint.textContent = t('qmv.singer_hint');
    fontWarn.textContent = t('qmv.font_missing');
    scopeSong.textContent = t('qmv.scope_song');
    scopeAll.textContent = t('qmv.scope_all');
    search.placeholder = t('qmv.search');
    selAllLabel.lastChild.textContent = t('qmv.select_all');
    delSel.textContent = t('qmv.delete_selected');
    clearAll.textContent = t('qmv.clear_all');
    scopeSong.classList.toggle('active', scope === 'song');
    scopeAll.classList.toggle('active', scope === 'all');
  }

  async function setScope(v) {
    scope = v === 'all' ? 'all' : 'song';
    try { localStorage.setItem('sign2mv.qmv.scope', scope); } catch { /* ignore */ }
    texts();
    if (scope === 'all') await loadAll(); else renderList();
  }

  async function loadAll() {
    try { allData = await api.get('/api/quickmv'); } catch (err) { toast(errorText(err), true); return; }
    renderList();
  }

  function picked() {
    return [...list.querySelectorAll('input.qmv-pick:checked')].map((c) => ({ song_id: c.dataset.song, id: c.dataset.id }));
  }

  async function deleteSelected() {
    const items = picked();
    if (!items.length) { toast(t('qmv.pick_some'), true); return; }
    if (!(await confirmDialog(t('qmv.delete_n', items.length), t('common.delete')))) return;
    list.querySelectorAll('video').forEach((v) => v.remove());   // release files first (Windows locks open files)
    try { const r = await api.post('/api/quickmv/delete', { items }); toast(t('qmv.deleted_n', r.deleted)); } catch (err) { toast(errorText(err), true); }
    selAll.checked = false;
    await refreshAfterDelete();
  }

  async function deleteAll() {
    const n = scope === 'all' ? ((allData && allData.items) || []).length : ((data && data.items) || []).length;
    if (!n) return;
    const items = scope === 'all' ? null : data.items.map((it) => ({ song_id: songId, id: it.id }));
    const msg = scope === 'all' ? t('qmv.clear_all_confirm', n) : t('qmv.clear_song_confirm', n);
    if (!(await confirmDialog(msg, t('qmv.clear_all')))) return;
    list.querySelectorAll('video').forEach((v) => v.remove());
    try {
      const r = await api.post('/api/quickmv/delete', items ? { items } : { all: true });
      toast(t('qmv.deleted_n', r.deleted));
    } catch (err) { toast(errorText(err), true); }
    await refreshAfterDelete();
  }

  async function refreshAfterDelete() {
    if (songId) await loadSong(songId);
    if (scope === 'all') await loadAll();
    bus.dispatchEvent(new CustomEvent('storage-changed'));
  }

  function fillSongs() {
    const songs = state.songs.filter((s) => s.source);
    const keep = songId || state.selectedSongId || '';
    songSel.replaceChildren(el('option', { value: '' }, t('qmv.pick_song')),
      ...songs.map((s) => el('option', { value: s.song_id, selected: s.song_id === keep }, s.title)));
    if (keep && songs.some((s) => s.song_id === keep) && keep !== songId) loadSong(keep);
  }

  function sourceLabel(s) {
    if (s.kind === 'original') return t('qmv.src_original');
    const d = s.duration ? ` · ${fmtTime(s.duration)}` : '';
    return `${t(`qmv.src_${s.kind}`)}：${s.title}${d}`;
  }

  async function loadSong(id, source) {
    songId = id || null;
    if (source !== undefined) wantSource = source;
    if (!songId) { data = null; srcSel.replaceChildren(); list.replaceChildren(); return; }
    songSel.value = songId;
    try {
      data = await api.get(`/api/songs/${songId}/quickmv`);
    } catch (err) { toast(errorText(err), true); return; }
    const prev = srcSel.value;
    srcSel.replaceChildren(...data.sources.map((s) => el('option', { value: s.id }, sourceLabel(s))));
    const pick = [wantSource, prev].find((v) => v && data.sources.some((s) => s.id === v));
    if (pick) srcSel.value = pick;
    wantSource = null;
    fillStudio(true);
    if (!title.dataset.song || title.dataset.song !== songId) {
      title.value = data.defaults.title;
      title.dataset.song = songId;
    }
    if (!artist.value) artist.value = data.defaults.artist || '';
    labelSpan.textContent = data.defaults.label;
    singerHint.classList.toggle('hidden', !!data.defaults.artist);
    fontWarn.classList.toggle('hidden', !!data.font_ok);
    renderList();
  }

  function renderList(highlight) {
    texts();
    const all = scope === 'all';
    let items = all ? ((allData && allData.items) || []) : ((data && data.items) || []).map((it) => ({ ...it, song_id: songId }));
    folder.textContent = all && allData ? t('qmv.folder', allData.folder, fmtBytes(allData.bytes || 0)) : '';
    const q = search.value.trim().toLowerCase();
    if (q) items = items.filter((it) => [it.title, it.artist_line, it.song_title, it.source_title].some((v) => (v || '').toLowerCase().includes(q)));
    if (!items.length) { list.replaceChildren(el('div', { class: 'empty' }, t(q ? 'qmv.no_match' : 'qmv.none'))); return; }
    list.replaceChildren(...items.map((it) => {
      const sid = it.song_id;
      const holder = el('div', {});
      const play = el('button', { class: 'btn small primary', onclick: () => {
        if (holder.firstChild) { holder.replaceChildren(); return; }
        const v = el('video', { src: mediaUrl(sid, it.path), controls: true, playsinline: true, preload: 'metadata',
          style: 'width:100%;max-width:960px;aspect-ratio:16/9;background:#101d2c;border-radius:10px;margin-top:8px' });
        holder.replaceChildren(v);
        v.play().catch(() => {});
      } }, t('qmv.play'));
      const look = [it.style === 'studio' ? t('qmv.style_studio_short') : '', it.resolution && it.resolution !== '1080p' ? it.resolution : ''].filter(Boolean).join(' ');
      const meta = [all ? it.song_title : '', look, it.artist_line, it.source_title ? `${t('qmv.from')} ${it.source_title}` : '', it.duration ? fmtTime(it.duration) : '',
        it.bytes ? fmtBytes(it.bytes) : '', fmtDate(it.created_at)].filter(Boolean).join(' · ');
      const row = el('div', { class: 'item' + (it.id === highlight ? ' cv-new' : ''), style: 'display:block' },
        el('div', { class: 'row', style: 'align-items:center' },
          el('input', { type: 'checkbox', class: 'qmv-pick', 'data-song': sid, 'data-id': it.id }),
          el('div', { class: 'grow', style: 'white-space:normal' }, el('b', {}, it.title || it.id), el('div', { class: 'muted small' }, meta)),
          play,
          el('a', { class: 'btn small', href: `/api/songs/${sid}/quickmv/${it.id}/download` }, t('common.download')),
          el('button', { class: 'btn small danger', onclick: async () => {
            if (!(await confirmDialog(t('qmv.delete_confirm', it.title || it.id), t('common.delete')))) return;
            holder.replaceChildren();   // release the video file first (Windows keeps open files locked)
            try { await api.del(`/api/songs/${sid}/quickmv/${it.id}`); toast(t('qmv.deleted')); } catch (err) { toast(errorText(err), true); }
            await refreshAfterDelete();
          } }, t('common.delete'))),
        holder);
      if (it.id === highlight) setTimeout(() => { row.scrollIntoView({ behavior: 'smooth', block: 'center' }); play.click(); }, 50);
      return row;
    }));
  }

  async function make() {
    if (!songId) { toast(t('qmv.pick_song'), true); return; }
    makeBtn.disabled = true;
    try {
      const body = { source: srcSel.value, title: title.value, artist: artist.value, style: styleSel.value, resolution: resSel.value };
      if (styleSel.value === 'studio') Object.entries(studioIn).forEach(([k, i]) => { body[k] = i.value; });
      const res = await api.post(`/api/songs/${songId}/quickmv`, body);
      const fin = await jb.follow(res.job);
      if (fin.status === 'succeeded') {
        toast(t('qmv.done'));
        await loadSong(songId);
        if (scope === 'all') await loadAll();
        renderList(fin.result && fin.result.id);
        bus.dispatchEvent(new CustomEvent('storage-changed'));
      }
    } catch (err) { toast(errorText(err), true); }
    makeBtn.disabled = false;
  }

  texts();
  return {
    show() { fillSongs(); if (scope === 'all') loadAll(); },
    open(id, renderId) { loadSong(id, renderId || 'original'); fillSongs(); },
    refreshSongs() { fillSongs(); },
    reload() { if (songId) loadSong(songId); },
    relabel() { texts(); fillSongs(); if (data) { renderList(); } },
  };
})();

// ------------------------------------------------------------------ routing
bus.addEventListener('mv-open', (e) => {
  const d = e.detail || {};
  goto('mv');
  if (d.mode === 'quick') { setTab('quick'); quick.open(d.songId, d.renderId); }
  else { setTab('full'); openSong(d.songId, d.renderId); }
});
bus.addEventListener('open-workspace', (e) => {
  if (e.detail.page !== 'mv') return;
  goto('mv');
  if (tab === 'quick') quick.open(e.detail.songId, 'original');
  else openSong(e.detail.songId, '');
});
bus.addEventListener('songs', () => { if (ready) send({ type: 'sign2mv:refresh' }); quick.refreshSongs(); });
bus.addEventListener('renders-changed', () => { if (ready) send({ type: 'sign2mv:refresh' }); quick.reload(); });
bus.addEventListener('jobs', (e) => {
  busy = (e.detail || []).some((j) => ['mv_render', 'mv_whisper'].includes(j.kind) && ['queued', 'running'].includes(j.status));
});
onLanguageChange(() => {
  labelTabs();
  quick.relabel();
  if (loaded && !busy) { loaded = false; ready = false; if (tab === 'full') load(); }
});

labelTabs();
registerPage('mv', {
  onShow() {
    const first = !loaded;
    setTab(tab);
    if (tab === 'full' && first && !pending && state.selectedSongId) {
      pending = { type: 'sign2mv:mv-open', songId: state.selectedSongId, renderId: '' };
    }
  },
  busy: () => busy,
  busyText: () => t('mv.busy'),
});
