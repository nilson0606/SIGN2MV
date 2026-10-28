// MV workspace: the MV Studio page runs in an iframe (/mv/) and talks to /api/mv.
import { $, el } from './ui.js';
import { t, language, onLanguageChange } from './i18n.js';
import { bus, registerPage, state, goto } from './app-state.js';

const page = $('#page-mv');
const frame = el('iframe', { id: 'mv-frame', class: 'workspace-frame', title: 'mv', allow: 'autoplay' });
page.replaceChildren(frame);
let loaded = false;
let ready = false;
let pending = null;
let busy = false;

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

bus.addEventListener('mv-open', (e) => { goto('mv'); openSong(e.detail.songId, e.detail.renderId); });
bus.addEventListener('open-workspace', (e) => {
  if (e.detail.page !== 'mv') return;
  goto('mv');
  openSong(e.detail.songId, '');
});
bus.addEventListener('songs', () => { if (ready) send({ type: 'sign2mv:refresh' }); });
bus.addEventListener('jobs', (e) => {
  busy = (e.detail || []).some((j) => ['mv_render', 'mv_whisper'].includes(j.kind) && ['queued', 'running'].includes(j.status));
});
onLanguageChange(() => { if (loaded && !busy) { loaded = false; ready = false; load(); } });

registerPage('mv', {
  onShow() {
    if (!loaded) {
      load();
      if (state.selectedSongId && !pending) pending = { type: 'sign2mv:mv-open', songId: state.selectedSongId, renderId: '' };
    }
  },
  busy: () => false,
  busyText: () => t('mv.busy'),
});
