// Sing & record workspace: the sign_record page runs in an iframe (/sing/)
// and talks to the /sr compatibility API. This module only hosts it.
import { $, el } from './ui.js';
import { t, language, onLanguageChange } from './i18n.js';
import { bus, registerPage, state, goto } from './app-state.js';

const page = $('#page-sing');
const frame = el('iframe', { id: 'sing-frame', class: 'workspace-frame', title: 'sing', allow: 'microphone; autoplay; speaker-selection' });
page.replaceChildren(frame);
let loaded = false;
let ready = false;
let pendingSong = null;
let busy = false;

function langParam() { return language() === 'en' ? 'en' : 'zh-Hant'; }
function load() {
  if (loaded) return;
  loaded = true;
  frame.src = `/sing/index.html?lang=${langParam()}`;
}
function send(message) { frame.contentWindow?.postMessage(message, location.origin); }
function openSong(songId) {
  load();
  if (ready) send({ type: 'sign2mv:select-song', songId });
  else pendingSong = songId;
}

window.addEventListener('message', (event) => {
  if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
  const m = event.data || {};
  if (m.type === 'sign2mv:sing-ready') {
    ready = true;
    if (pendingSong) { send({ type: 'sign2mv:select-song', songId: pendingSong }); pendingSong = null; }
  } else if (m.type === 'sign2mv:sing-state') {
    busy = !!m.busy;
  } else if (m.type === 'sign2mv:open-mv' && typeof m.songId === 'string') {
    bus.dispatchEvent(new CustomEvent('mv-open', { detail: { songId: m.songId, renderId: m.renderId } }));
    goto('mv');
  }
});
frame.addEventListener('load', () => { ready = false; });

bus.addEventListener('open-workspace', (e) => {
  if (e.detail.page !== 'sing') return;
  goto('sing');
  openSong(e.detail.songId);
});
bus.addEventListener('songs', () => { if (ready) send({ type: 'sign2mv:refresh-songs' }); });
onLanguageChange(() => { if (loaded) send({ type: 'sign2mv:lang', lang: langParam() }); });

registerPage('sing', {
  onShow() {
    if (!loaded) {
      load();
      if (state.selectedSongId) pendingSong = state.selectedSongId;
    }
  },
  busy: () => busy,
  busyText: () => t('sing.busy'),
});
