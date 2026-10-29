// SIGN2MV glue for the MV workspace page (the MV Studio page of AI_COVER_MV).
// Loaded before the page script: patches fetch, provides branding helpers and
// handles "make an MV of this song / this take" requests from the SIGN2MV shell.
(function () {
  'use strict';
  // Every request that changes something carries the SIGN2MV control header.
  const nativeFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    init = init || {};
    const method = String(init.method || (input && input.method) || 'GET').toUpperCase();
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const sameOrigin = url.startsWith('/') || url.startsWith(location.origin);
    if (method !== 'GET' && method !== 'HEAD' && sameOrigin) {
      const headers = new Headers(init.headers || (input && input.headers) || {});
      headers.set('X-SIGN2MV', '1');
      init = Object.assign({}, init, { headers });
    }
    return nativeFetch(input, init);
  };
})();

var MV_BRAND = {};
var MV_SONGS = [];
var sign2mvPending = null;   // {songId, audio} waiting for a new project

const SIGN2MV_LABELS = {
  zh: { lyricist: '作詞：', composer: '作曲：', original: '原唱：', cover: '翻唱者：' },
  en: { lyricist: 'Lyrics: ', composer: 'Music: ', original: 'Original: ', cover: 'Cover: ' },
};

function sign2mvLabel(p, key) {
  const lang = (p && p.credit_lang) || MV_BRAND.lang || 'zh';
  return (SIGN2MV_LABELS[lang] || SIGN2MV_LABELS.zh)[key] || '';
}

// Same rule as the server (core.sanitize_no_ai): the MV never shows "AI".
function sign2mvNoAI(v) {
  const singer = MV_BRAND.singer || '';
  const coverWord = singer ? `${singer} 翻唱` : '翻唱';
  let t = String(v || '').replace(/AI\s*翻唱/gi, coverWord).replace(/AI\s*Cover/gi, coverWord)
    .replace(/(?<![a-zA-Z])AI(?![a-zA-Z])/gi, singer);
  if (!singer) t = t.replace(/\s{2,}/g, ' ');
  return t;
}

function sign2mvFillAudioSelect() {
  const sel = document.getElementById('selAudioQuick');
  if (!sel || typeof availableAudios === 'undefined') return;
  const songId = currentProject ? currentProject.song_id : null;
  sel.innerHTML = '<option value="">-- 選擇這首歌的音檔 --</option>';
  availableAudios.filter(a => !songId || a.song_id === songId).forEach(a => {
    const opt = document.createElement('option');
    opt.value = a.path;
    opt.textContent = `${a.name} (${a.size_mb} MB)`;
    sel.appendChild(opt);
  });
  if (currentProject && currentProject.audio_file) sel.value = currentProject.audio_file;
}

function sign2mvFillModalSongs(preselect) {
  const sel = document.getElementById('modSong');
  if (!sel) return;
  sel.innerHTML = '';
  sel.appendChild(new Option(MV_SONGS.length ? '-- 選擇歌曲 --' : '（歌曲庫還沒有歌曲，請先到「歌曲庫」匯入）', ''));
  MV_SONGS.forEach(s => sel.appendChild(new Option(s.title, s.song_id)));
  const want = preselect || (sign2mvPending && sign2mvPending.songId) || (currentProject && currentProject.song_id) || '';
  if (want) sel.value = want;
  sign2mvModalSongChanged();
}

function sign2mvModalSongChanged() {
  const sel = document.getElementById('modSong');
  const title = document.getElementById('modTitle');
  const song = MV_SONGS.find(s => s.song_id === sel.value);
  if (song && title && (!title.value || title.dataset.auto === 'true')) {
    title.value = song.title;
    title.dataset.auto = 'true';
    if (typeof onModalTitleInput === 'function') onModalTitleInput(song.title);
  }
}

function sign2mvTakePendingAudio(songId) {
  if (sign2mvPending && sign2mvPending.songId === songId) {
    const audio = sign2mvPending.audio || '';
    sign2mvPending = null;
    return audio;
  }
  return '';
}

async function sign2mvOpenForSong(songId, renderId, explicit) {
  await initStudio();
  const audio = renderId ? availableAudios.find(a => a.render_id === renderId) : null;
  const projects = allProjects.filter(p => p.song_id === songId).sort((a, b) => (b.mtime || 0) - (a.mtime || 0));
  if (projects.length) {
    await loadProject(projects[0].slug);
    if (audio && currentProject && currentProject.audio_file !== audio.path) {
      document.getElementById('inpAudioFile').value = audio.path;
      await bindAndProbeAudioPath(audio.path);
    }
    return;
  }
  sign2mvPending = { songId, audio: audio ? audio.path : '' };
  // only a 完整 MV button asks for a new project; just opening the page does not pop up a dialog
  if (explicit) openNewProjectModal();
}

window.addEventListener('message', (event) => {
  if (event.origin !== location.origin || event.source !== window.parent) return;
  const m = event.data || {};
  if (m.type === 'sign2mv:mv-open' && typeof m.songId === 'string') {
    sign2mvOpenForSong(m.songId, m.renderId || '', m.explicit !== false).catch(e => showToast(`❌ ${e.message}`, true));
  } else if (m.type === 'sign2mv:refresh') {
    initStudio();
  }
});

window.sign2mvReady = function () {
  // no project yet: the project bar says how to start (no dialog popping up on its own)
  if (window.parent !== window) window.parent.postMessage({ type: 'sign2mv:mv-ready' }, location.origin);
};
