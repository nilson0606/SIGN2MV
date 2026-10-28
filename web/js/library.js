// Library page: song list, import (YouTube / file), source preview, stems and key preview.
import { api } from './api.js';
import { t, errorText, onLanguageChange } from './i18n.js';
import { $, el, toast, confirmDialog, fmtDate, fmtTime, fmtBytes } from './ui.js';
import { bus, state, selectSong, songById, mediaUrl, reloadJobs } from './app-state.js';
import { jobBox } from './jobview.js';

let filter = '';
let sizes = {};   // song_id -> bytes on disk
const expanded = new Set();   // saved-stem rows whose children are shown

// Collapsible section; open/closed is remembered per section (not per song).
function fold(key, title, info, defaultOpen, ...children) {
  let v = null;
  try { v = localStorage.getItem(`sign2mv.lib.fold.${key}`); } catch { /* storage unavailable */ }
  const d = el('details', { class: 'section cv-fold lib-fold', open: v === null ? defaultOpen : v === '1' },
    el('summary', {}, el('h3', {}, title), info || null), ...children);
  d.addEventListener('toggle', () => {
    try { localStorage.setItem(`sign2mv.lib.fold.${key}`, d.open ? '1' : '0'); } catch { /* ignore */ }
  });
  return d;
}

async function loadSizes() {
  try {
    const res = await api.get('/api/storage');
    sizes = res.songs || {};
    $('#library-usage').textContent = t('storage.library', fmtBytes(res.total || 0), fmtBytes((res.disk || {}).free || 0));
    renderList();
  } catch { /* sizes are optional */ }
}

async function loadSongs() {
  try {
    const data = await api.get('/api/songs');
    bus.dispatchEvent(new CustomEvent('songs', { detail: data.songs || [] }));
    renderList();
    renderDetail();
    loadSizes();
  } catch (err) {
    $('#song-list').replaceChildren(el('div', { class: 'empty' }, errorText(err)));
  }
}
bus.addEventListener('reload-songs', loadSongs);
bus.addEventListener('job-finished', () => loadSizes());
bus.addEventListener('settings', (e) => { $('#library-path').textContent = t('lib.location', e.detail.library_dir || ''); });
bus.addEventListener('song-selected', () => { renderList(); renderDetail(); });
onLanguageChange(() => { renderList(); renderDetail(); });

export function sourceBadge(s) {
  if (!s.source) return el('span', { class: 'badge failed' }, t('lib.no_source'));
  return el('span', { class: 'badge' }, t(`lib.source.${s.source.type}`));
}

function renderList() {
  const list = $('#song-list');
  const songs = state.songs.filter((s) => !filter || s.title.toLowerCase().includes(filter));
  if (!songs.length) { list.replaceChildren(el('div', { class: 'empty' }, t('lib.empty'))); return; }
  list.replaceChildren(...songs.map((s) => el('div', {
    class: 'item' + (state.selectedSongId === s.song_id ? ' selected' : ''), style: 'cursor:pointer',
    onclick: () => selectSong(s.song_id),
  }, el('div', { class: 'grow' }, el('b', {}, s.title), el('div', { class: 'muted small' },
    s.source ? `${fmtTime(s.source.duration)} · ` : '', sizes[s.song_id] ? `${fmtBytes(sizes[s.song_id])} · ` : '',
    fmtDate(s.created_at))), sourceBadge(s))));
}

$('#song-search').addEventListener('input', (e) => { filter = e.target.value.trim().toLowerCase(); renderList(); });

$('#new-song-btn').addEventListener('click', async () => {
  const input = $('#new-song-title');
  try {
    const song = await api.post('/api/songs', { title: input.value });
    input.value = '';
    await loadSongs();
    selectSong(song.song_id);
  } catch (err) { toast(errorText(err), true); }
});
$('#new-song-title').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('#new-song-btn').click(); });

// ------------------------------------------------------------------ detail
const RECIPE_DEFAULT = { model: 'demucs', second_pass: false, lead: false };

function renderDetail() {
  const box = $('#song-detail');
  const song = songById(state.selectedSongId);
  if (!song) { box.replaceChildren(el('div', { class: 'empty' }, t('lib.pick_song'))); return; }
  if (box.dataset.song === song.song_id && box.dataset.sourceKey === JSON.stringify(song.source || null) && box.dataset.title === song.title) return;
  box.dataset.song = song.song_id;
  box.dataset.sourceKey = JSON.stringify(song.source || null);
  box.dataset.title = song.title;

  const header = el('div', { class: 'row' },
    el('h2', { style: 'margin:0;flex:1' }, song.title),
    el('button', { class: 'btn small', onclick: () => rename(song) }, t('common.rename')),
    el('button', { class: 'btn small danger', onclick: () => remove(song) }, t('common.delete')));

  const parts = [header];
  if (song.source) {
    const go = (page) => () => bus.dispatchEvent(new CustomEvent('open-workspace', { detail: { page, songId: song.song_id } }));
    parts.push(el('div', { class: 'row workspace-actions' },
      el('button', { class: 'btn primary', onclick: go('sing') }, t('lib.go_sing')),
      el('button', { class: 'btn', onclick: go('mv') }, t('lib.go_mv')),
      el('button', { class: 'btn', onclick: go('cover') }, t('lib.go_cover'))));
  }
  parts.push(importSection(song));
  if (song.source) {
    parts.push(sourceSection(song));
    parts.push(stemsSection(song));
  }
  parts.push(storageSection(song));
  box.replaceChildren(...parts);
}

async function rename(song) {
  const title = prompt(t('lib.rename_prompt'), song.title);
  if (title === null) return;
  try { await api.patch(`/api/songs/${song.song_id}`, { title }); await loadSongs(); }
  catch (err) { toast(errorText(err), true); }
}

async function remove(song) {
  if (!(await confirmDialog(t('lib.delete_confirm', song.title), t('common.delete')))) return;
  try {
    await api.del(`/api/songs/${song.song_id}`);
    toast(t('lib.deleted', song.title));
    selectSong(null);
    await loadSongs();
  } catch (err) { toast(errorText(err), true); }
}

// YouTube video id from the usual link shapes (watch, youtu.be, shorts, embed, music)
function youtubeId(text) {
  const m = String(text || '').match(/(?:youtube\.com\/(?:watch\?(?:.*&)?v=|shorts\/|embed\/|live\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/);
  return m ? m[1] : '';
}

function importSection(song) {
  const jb = jobBox();
  const url = el('input', { type: 'url', placeholder: 'https://www.youtube.com/watch?v=...', style: 'flex:1;min-width:240px' });
  const file = el('input', { type: 'file', accept: 'audio/*,video/*,.mkv,.flac,.m4a,.wav,.mp3,.mp4,.mov,.webm' });
  async function afterJob(job) {
    const fin = await jb.follow(job);
    if (fin.status === 'succeeded') toast(t('lib.import_done'));
    await loadSongs();
  }
  const ytBtn = el('button', { class: 'btn primary', onclick: async () => {
    try { await afterJob(await api.post(`/api/songs/${song.song_id}/import/youtube`, { url: url.value })); }
    catch (err) { toast(errorText(err), true); }
  } }, t('lib.import_youtube'));
  // old 📋 貼上
  const pasteBtn = el('button', { class: 'btn', title: t('lib.paste'), onclick: async () => {
    try { url.value = (await navigator.clipboard.readText()).trim(); preview(); }
    catch { toast(t('lib.paste_denied'), true); url.focus(); }
  } }, '📋');
  // preview card before importing (old YouTube preview: thumbnail, title, id, link, player)
  const card = el('div', { class: 'yt-card hidden' });
  let previewTimer = null;
  let previewFor = '';
  function preview() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(showPreview, 500);
  }
  async function showPreview() {
    const u = url.value.trim();
    if (u === previewFor) return;
    previewFor = u;
    if (!/^https?:\/\/\S+$/.test(u)) { card.classList.add('hidden'); card.replaceChildren(); return; }
    const id = youtubeId(u);
    const title = el('b', {}, t('lib.yt_reading'));
    const meta = el('div', { class: 'muted small' }, id ? `ID: ${id}` : '');
    const player = el('div', {});
    const thumb = id ? el('img', { class: 'yt-thumb', src: `https://i.ytimg.com/vi/${id}/hqdefault.jpg`, alt: '',
      onerror: (e) => { e.target.style.visibility = 'hidden'; } }) : el('div');
    const links = el('div', { class: 'row', style: 'gap:6px' },
      el('a', { class: 'btn small', href: u, target: '_blank', rel: 'noopener' }, t('lib.yt_open')),
      id ? el('button', { class: 'btn small', onclick: () => {
        if (player.firstChild) { player.replaceChildren(); return; }
        player.replaceChildren(el('iframe', { class: 'yt-frame', src: `https://www.youtube-nocookie.com/embed/${id}?autoplay=1`,
          allow: 'autoplay; encrypted-media; fullscreen', allowfullscreen: true, referrerpolicy: 'strict-origin-when-cross-origin' }));
      } }, t('lib.yt_play')) : null);
    card.replaceChildren(el('div', { class: 'row', style: 'align-items:flex-start;gap:12px' },
      thumb, el('div', { class: 'grow' }, title, meta, links)), player);
    card.classList.remove('hidden');
    try {
      const info = await api.get(`/api/youtube/info?url=${encodeURIComponent(u)}`);
      if (previewFor !== u) return;
      title.textContent = info.title || u;
      meta.textContent = [info.uploader, info.duration ? fmtTime(info.duration) : '', info.id ? `ID: ${info.id}` : ''].filter(Boolean).join(' · ');
      if (!id && info.thumbnail) thumb.replaceWith(el('img', { class: 'yt-thumb', src: info.thumbnail, alt: '', onerror: (e) => { e.target.style.visibility = 'hidden'; } }));
    } catch {
      if (previewFor !== u) return;
      title.textContent = t('lib.yt_no_info');
    }
  }
  url.addEventListener('input', preview);
  url.addEventListener('paste', () => setTimeout(preview, 0));
  // local file: pick or drop (old 拖檔進來即上傳), with a progress bar and the file name
  const bar = el('progress', { max: 100, value: 0, class: 'hidden', style: 'width:160px' });
  const progress = el('span', { class: 'muted small' });
  function upload(f) {
    if (!f) { toast(t('lib.pick_file'), true); return; }
    const fd = new FormData();
    fd.append('file', f, f.name);
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `/api/songs/${song.song_id}/import/file`);
    xhr.setRequestHeader('X-SIGN2MV', '1');
    bar.value = 0;
    bar.classList.remove('hidden');
    progress.className = 'muted small';
    progress.textContent = `${f.name} · ${fmtBytes(f.size)}`;
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      bar.value = Math.round(e.loaded * 100 / e.total);
      progress.textContent = `${f.name} · ${t('lib.uploading', bar.value)}`;
    };
    xhr.onload = async () => {
      bar.classList.add('hidden');
      let data = null;
      try { data = JSON.parse(xhr.responseText); } catch { /* ignore */ }
      if (xhr.status >= 400) {
        const msg = errorText({ code: (data && data.error) || `http_${xhr.status}` });
        progress.className = 'small cv-warn';
        progress.textContent = `${f.name}：${msg}`;   // the reason stays in the box
        toast(msg, true);
        return;
      }
      progress.textContent = f.name;
      await afterJob(data);
    };
    xhr.onerror = () => {
      bar.classList.add('hidden');
      progress.className = 'small cv-warn';
      progress.textContent = `${f.name}：${errorText({ code: 'server_unreachable' })}`;
      toast(errorText({ code: 'server_unreachable' }), true);
    };
    xhr.send(fd);
  }
  const fileBtn = el('button', { class: 'btn', onclick: () => upload(file.files && file.files[0]) }, t('lib.import_file'));
  const drop = el('div', { class: 'dropzone' },
    el('div', { class: 'row' }, file, fileBtn, bar, progress),
    el('div', { class: 'muted small' }, t('lib.drop_hint')));
  drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('over'));
  drop.addEventListener('drop', (e) => {
    e.preventDefault();
    drop.classList.remove('over');
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) upload(f);
  });
  const sec = el('div', { class: 'section' },
    el('h3', {}, song.source ? t('lib.reimport') : t('lib.import')),
    el('div', { class: 'row' }, url, pasteBtn, ytBtn),
    card,
    drop,
    el('p', { class: 'muted small' }, t('lib.import_hint')),
    jb.el);
  if (song.source) {
    const det = el('details', {}, el('summary', { class: 'muted' }, t('lib.reimport')), ...[...sec.childNodes].slice(1));
    return el('div', { class: 'section' }, det);
  }
  return sec;
}

function sourceSection(song) {
  const s = song.source;
  const info = [
    t(`lib.source.${s.type}`), fmtTime(s.duration),
    s.video_size && s.video_size[0] ? `${s.video_size[0]}×${s.video_size[1]}` : t('lib.no_video'),
  ];
  if (s.original_name) info.push(s.original_name);
  const media = s.video
    ? el('video', { src: mediaUrl(song.song_id, s.video), controls: true, muted: true, style: 'max-height:240px' })
    : null;
  const link = s.url && /^https?:\/\//.test(s.url)
    ? el('a', { href: s.url, target: '_blank', rel: 'noopener', class: 'small', onclick: (e) => e.stopPropagation() }, s.url) : null;   // old 前往 YouTube 原站
  return fold('source', t('lib.source_title'), el('span', { class: 'muted small' }, info.join(' · '), link ? ' · ' : '', link), false,
    el('audio', { src: mediaUrl(song.song_id, s.audio), controls: true, preload: 'none' }),
    media);
}

function stemsSection(song) {
  const model = el('select', {},
    ...['demucs', 'bs_roformer', 'mel_roformer'].map((m) => el('option', { value: m }, t(`sep.model.${m}`))));
  const second = el('input', { type: 'checkbox' });
  const lead = el('input', { type: 'checkbox' });
  const key = el('select', {}, ...Array.from({ length: 25 }, (_, i) => i - 12).map((k) =>
    el('option', { value: k, selected: k === 0 }, k === 0 ? t('key.original') : (k > 0 ? `+${k}` : `${k}`))));
  const tracksBox = el('div', { class: 'tracks' });
  const jb = jobBox();

  function recipe() { return { ...RECIPE_DEFAULT, model: model.value, second_pass: second.checked, lead: lead.checked }; }

  function showTracks(tracks, title) {
    const order = ['mix', 'vocals', 'instrumental', 'residual_vocals', 'lead', 'backing', 'male', 'female'];
    tracksBox.replaceChildren(el('div', { class: 'muted small' }, title),
      ...order.filter((n) => tracks[n]).map((n) => el('div', { class: 'track' },
        el('span', {}, t(`track.${n}`)),
        el('audio', { src: mediaUrl(song.song_id, tracks[n]), controls: true, preload: 'none' }))));
  }

  async function prepare() {
    try {
      const res = await api.post(`/api/songs/${song.song_id}/stems`, { recipe: recipe() });
      if (!res.ready) {
        const fin = await jb.follow(res.job);
        if (fin.status !== 'succeeded') return;
      }
      const k = Number(key.value);
      if (k === 0) { showTracks(res.tracks, t('key.original')); return; }
      const names = ['instrumental', 'vocals'].concat(lead.checked ? ['lead', 'backing'] : []);
      const kr = await api.post(`/api/songs/${song.song_id}/key`, { recipe: recipe(), semitones: k, tracks: names });
      if (!kr.ready) {
        const fin = await jb.follow(kr.job);
        if (fin.status !== 'succeeded') return;
      }
      showTracks(kr.tracks, `${t('key.label')} ${k > 0 ? '+' : ''}${k}`);
    } catch (err) { toast(errorText(err), true); }
    reloadJobs();
    stored.load();
  }

  const stored = storedCopies(song);

  return fold('stems', t('sep.title'), null, true,
    el('p', { class: 'muted small' }, t('sep.hint')),
    el('div', { class: 'row' },
      el('label', {}, t('sep.model'), ' ', model),
      el('label', { class: 'check' }, second, t('sep.second_pass')),
      el('label', { class: 'check' }, lead, t('sep.lead')),
      el('label', {}, t('key.label'), ' ', key),
      el('button', { class: 'btn primary', onclick: prepare }, t('sep.prepare'))),
    jb.el, tracksBox, stored.el);
}

// ------------------------------------------------------------------ storage overview
const STORAGE_ROWS = [
  ['source', null], ['stems', null], ['cover', 'cover_versions'], ['cover_cache', null],
  ['sing', 'sing_takes'], ['mv', 'mv_projects'], ['other', null],
];

function storageSection(song) {
  const info = el('span', { class: 'muted small' });
  const body = el('div', {}, el('div', { class: 'muted small' }, t('common.loading')));
  async function load() {
    try {
      const res = await api.get(`/api/songs/${song.song_id}/storage`);
      const cats = res.categories || {};
      const max = Math.max(1, ...Object.values(cats));
      const rows = STORAGE_ROWS.filter(([c]) => cats[c] > 0 || c === 'source').map(([c, countKey]) => {
        let count = countKey ? t(`storage.count.${countKey}`, (res.counts || {})[countKey] || 0) : '';
        if (c === 'mv' && (res.counts || {}).quick_mvs) count += ' ' + t('storage.count.quick_mvs', res.counts.quick_mvs);
        return el('div', { class: 'storage-row' },
          el('div', { class: 'storage-name' }, el('b', {}, t(`storage.cat.${c}`)), count ? el('span', { class: 'muted small' }, ' ' + count) : null),
          el('div', { class: 'storage-bar' }, el('span', { style: `width:${Math.max(1, Math.round(cats[c] * 100 / max))}%` })),
          el('div', { class: 'storage-size' }, fmtBytes(cats[c] || 0)),
          el('div', { class: 'muted small storage-hint' }, t(`storage.hint.${c}`)));
      });
      info.textContent = fmtBytes(res.total || 0);
      body.replaceChildren(
        el('div', { class: 'muted small' }, t('storage.song_total', fmtBytes(res.total || 0), fmtBytes((res.disk || {}).free || 0))),
        ...rows);
    } catch (err) { body.replaceChildren(el('div', { class: 'muted small' }, errorText(err))); }
  }
  const sec = fold('storage', t('storage.title'), info, false,
    el('div', { class: 'row', style: 'justify-content:flex-end' },
      el('button', { class: 'btn small', onclick: () => { load(); loadSizes(); } }, t('common.refresh'))),
    body);
  const onJob = () => {
    if (sec.isConnected) { load(); return; }
    bus.removeEventListener('job-finished', onJob);
    bus.removeEventListener('storage-changed', onJob);
  };
  bus.addEventListener('job-finished', onJob);
  bus.addEventListener('storage-changed', onJob);
  load();
  return sec;
}

// ------------------------------------------------------------------ stored copies
const MODEL_NAME = { demucs: 'Demucs', bs_roformer: 'BS-RoFormer', mel_roformer: 'Mel-RoFormer',
  karaoke: 'Karaoke', karaoke_becruily: 'Karaoke becruily', aufr33: 'aufr33', sucial: 'Sucial' };

function trackName(n) {
  const key = `track.${n}`;
  const s = t(key);
  return s === key ? n : s;
}

function copyLabel(it, byDir) {
  const model = MODEL_NAME[it.model] || it.model || '';
  if (it.type === 'incomplete') return t('stored.incomplete');
  if (it.type === 'key') {
    const k = Number(it.semitones) || 0;
    return t('stored.key', `${k > 0 ? '+' : ''}${k}`, (it.tracks || []).map(trackName).join('、'));
  }
  if (it.kind === 'lead') {
    const parent = byDir[(it.parents || [])[0]];
    return parent && parent.kind === 'lead' ? t('stored.lead2') : t('stored.lead');
  }
  const clip = /^sing\/clips\/clip_(\d+)s\.wav$/.exec(it.input || '');
  return t(`stored.${it.kind}`, model) + (clip ? t('stored.clip', clip[1]) : '');
}

function dependentsOf(items, target) {
  const gone = [target];
  let changed = true;
  while (changed) {
    changed = false;
    for (const it of items) {
      if (!gone.includes(it.dir) && (it.parents || []).some((p) => gone.includes(p))) { gone.push(it.dir); changed = true; }
    }
  }
  return gone;
}

function storedCopies(song) {
  const info = el('span', { class: 'muted small' });
  const box = el('div', {});
  const wrap = fold('stored', t('stored.title'), info, false, box);
  wrap.classList.add('stored');
  let items = [];
  let loaded = false;

  async function load() {
    loaded = true;
    try {
      const res = await api.get(`/api/songs/${song.song_id}/stems`);
      items = res.items || [];
      render(res);
    } catch (err) { box.replaceChildren(el('div', { class: 'muted small' }, errorText(err))); }
  }

  function render(res) {
    info.textContent = items.length ? t('stored.summary', items.length, fmtBytes(res.total_bytes || 0)) : t('stored.empty');
    if (!items.length) { box.replaceChildren(el('div', { class: 'muted small' }, t('stored.empty'))); return; }
    const byDir = Object.fromEntries(items.map((i) => [i.dir, i]));
    const kids = {};
    const roots = [];
    for (const it of items) {
      const p = (it.parents || []).find((d) => byDir[d]);
      if (p) (kids[p] = kids[p] || []).push(it); else roots.push(it);
    }
    const order = (a, b) => (a.created_at || 0) - (b.created_at || 0);
    const rows = [];
    const count = (it) => (kids[it.dir] || []).reduce((n, c) => n + 1 + count(c), 0);
    const walk = (it, depth) => {
      const n = count(it);
      rows.push(row(it, depth, byDir, n));
      if (n && expanded.has(it.dir)) (kids[it.dir] || []).sort(order).forEach((c) => walk(c, depth + 1));
    };
    roots.sort((a, b) => (a.type === 'layer' ? 0 : 1) - (b.type === 'layer' ? 0 : 1) || order(a, b)).forEach((r) => walk(r, 0));
    box.replaceChildren(
      el('div', { class: 'muted small' }, t('stored.total', fmtBytes(res.total_bytes || 0)), res.busy ? ' · ' + t('stored.busy') : ''),
      ...rows);
    last = res;
  }
  let last = null;

  function row(it, depth, byDir, nKids) {
    const names = (it.used_by || []).map((u) => t(`stored.used.${u.type}`, u.label));
    const used = names.slice(0, 3).map((n) => el('span', { class: 'badge' }, n));
    if (names.length > 3) used.push(el('span', { class: 'badge', title: names.join('\n') }, t('stored.more', names.length - 3)));
    const files = (it.type === 'layer' ? (it.files || []).map((f) => trackName(f.replace(/\.wav$/, ''))).join('、') : '');
    const open = expanded.has(it.dir);
    const toggle = nKids ? el('button', { class: 'btn small', onclick: () => {
      if (open) expanded.delete(it.dir); else expanded.add(it.dir);
      if (last) render(last);
    } }, (open ? '▾ ' : '▸ ') + t('stored.children', nKids)) : null;
    return el('div', { class: 'item stored-row', style: `margin-left:${depth * 22}px` },
      el('div', { class: 'grow', style: 'white-space:normal' },
        el('b', {}, copyLabel(it, byDir)),
        el('div', { class: 'muted small' }, [files, fmtBytes(it.bytes), fmtDate(it.created_at)].filter(Boolean).join(' · ')),
        used.length ? el('div', { class: 'row', style: 'gap:4px;margin-top:4px' }, ...used) : null),
      toggle,
      el('button', { class: 'btn small danger', onclick: () => remove(it, byDir) }, t('common.delete')));
  }

  async function remove(it, byDir) {
    const gone = dependentsOf(items, it.dir);
    const bytes = gone.reduce((n, d) => n + ((byDir[d] && byDir[d].bytes) || 0), 0);
    const users = [];
    for (const d of gone) for (const u of (byDir[d] && byDir[d].used_by) || []) {
      const s = t(`stored.used.${u.type}`, u.label);
      if (!users.includes(s)) users.push(s);
    }
    let msg = t('stored.confirm', copyLabel(it, byDir), fmtBytes(bytes));
    if (gone.length > 1) msg += '\n' + t('stored.confirm_children', gone.length - 1);
    if (users.length) msg += '\n\n' + t('stored.confirm_used') + '\n' + users.map((u) => '• ' + u).join('\n');
    if (!(await confirmDialog(msg, t('common.delete')))) return;
    try {
      const res = await api.del(`/api/songs/${song.song_id}/${it.dir}`);
      toast(t('stored.deleted', fmtBytes(res.bytes || 0)));
    } catch (err) { toast(errorText(err), true); }
    load();
    loadSizes();
    bus.dispatchEvent(new CustomEvent('storage-changed'));
  }

  const onJob = (e) => {
    if (!box.isConnected && loaded) { bus.removeEventListener('job-finished', onJob); return; }
    if (box.isConnected) load();
  };
  bus.addEventListener('job-finished', onJob);
  load();
  return { el: wrap, load };
}

export { loadSongs };
