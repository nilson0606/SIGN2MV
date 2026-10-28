// Library page: song list, import (YouTube / file), source preview, stems and key preview.
import { api } from './api.js';
import { t, errorText, onLanguageChange } from './i18n.js';
import { $, el, toast, confirmDialog, fmtDate, fmtTime } from './ui.js';
import { bus, state, selectSong, songById, mediaUrl, reloadJobs } from './app-state.js';
import { jobBox } from './jobview.js';

let filter = '';

async function loadSongs() {
  try {
    const data = await api.get('/api/songs');
    bus.dispatchEvent(new CustomEvent('songs', { detail: data.songs || [] }));
    renderList();
    renderDetail();
  } catch (err) {
    $('#song-list').replaceChildren(el('div', { class: 'empty' }, errorText(err)));
  }
}
bus.addEventListener('reload-songs', loadSongs);
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
    s.source ? `${fmtTime(s.source.duration)} · ` : '', fmtDate(s.created_at))), sourceBadge(s))));
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

function importSection(song) {
  const jb = jobBox();
  const url = el('input', { type: 'url', placeholder: 'https://www.youtube.com/watch?v=...', style: 'flex:1;min-width:240px' });
  const file = el('input', { type: 'file', accept: 'audio/*,video/*,.mkv,.flac,.m4a,.wav,.mp3,.mp4,.mov,.webm' });
  const progress = el('span', { class: 'muted small' });
  async function afterJob(job) {
    const fin = await jb.follow(job);
    if (fin.status === 'succeeded') toast(t('lib.import_done'));
    await loadSongs();
  }
  const ytBtn = el('button', { class: 'btn primary', onclick: async () => {
    try { await afterJob(await api.post(`/api/songs/${song.song_id}/import/youtube`, { url: url.value })); }
    catch (err) { toast(errorText(err), true); }
  } }, t('lib.import_youtube'));
  const fileBtn = el('button', { class: 'btn', onclick: () => {
    const f = file.files && file.files[0];
    if (!f) { toast(t('lib.pick_file'), true); return; }
    const fd = new FormData();
    fd.append('file', f, f.name);
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `/api/songs/${song.song_id}/import/file`);
    xhr.setRequestHeader('X-SIGN2MV', '1');
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) progress.textContent = t('lib.uploading', Math.round(e.loaded * 100 / e.total)); };
    xhr.onload = async () => {
      progress.textContent = '';
      let data = null;
      try { data = JSON.parse(xhr.responseText); } catch { /* ignore */ }
      if (xhr.status >= 400) { toast(errorText({ code: (data && data.error) || `http_${xhr.status}` }), true); return; }
      await afterJob(data);
    };
    xhr.onerror = () => { progress.textContent = ''; toast(errorText({ code: 'server_unreachable' }), true); };
    xhr.send(fd);
  } }, t('lib.import_file'));
  const sec = el('div', { class: 'section' },
    el('h3', {}, song.source ? t('lib.reimport') : t('lib.import')),
    el('div', { class: 'row' }, url, ytBtn),
    el('div', { class: 'row' }, file, fileBtn, progress),
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
  if (s.url) info.push(s.url);
  if (s.original_name) info.push(s.original_name);
  const media = s.video
    ? el('video', { src: mediaUrl(song.song_id, s.video), controls: true, muted: true, style: 'max-height:240px' })
    : null;
  return el('div', { class: 'section' },
    el('h3', {}, t('lib.source_title')),
    el('div', { class: 'muted small' }, info.join(' · ')),
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
  }

  return el('div', { class: 'section' },
    el('h3', {}, t('sep.title')),
    el('p', { class: 'muted small' }, t('sep.hint')),
    el('div', { class: 'row' },
      el('label', {}, t('sep.model'), ' ', model),
      el('label', { class: 'check' }, second, t('sep.second_pass')),
      el('label', { class: 'check' }, lead, t('sep.lead')),
      el('label', {}, t('key.label'), ' ', key),
      el('button', { class: 'btn primary', onclick: prepare }, t('sep.prepare'))),
    jb.el, tracksBox);
}

export { loadSongs };
