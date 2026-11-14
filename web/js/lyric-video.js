// Library: the lyric picture of a song. Paste the lyrics, time them (the quick MV's editor and saved
// lines), make a picture with the lines as subtitles and use it as the song's picture, so that sing &
// record shows the words. The audio is not touched; the original picture is kept and can be put back.
import { api } from './api.js';
import { el, toast } from './ui.js';
import { t, errorText } from './i18n.js';
import { bus, mediaUrl } from './app-state.js';
import { jobBox } from './jobview.js';
import { lyricsEditor } from './qmv-lyrics.js';

const pref = (k, d) => { try { return localStorage.getItem(`sign2mv.lyricvideo.${k}`) || d; } catch { return d; } };
const keep = (k, v) => { try { localStorage.setItem(`sign2mv.lyricvideo.${k}`, v); } catch { /* ignore */ } };

// What the section's summary line says about the song's picture.
export function lyricVideoInfo(song) {
  const s = song.source || {};
  if (s.lyric_video) return t('lv.info_on');
  return s.video ? '' : t('lv.info_none');
}

export function lyricVideoBody(song) {
  const sid = song.song_id;
  const s = song.source;
  const now = el('p', { class: 'small' });
  const editor = lyricsEditor({ title: 'lv.step_lyrics', hint: 'lv.lyrics_hint' });
  const jb = jobBox();
  const plain = el('input', { type: 'radio', name: `lv-style-${sid}`, value: 'plain' });
  const overlay = el('input', { type: 'radio', name: `lv-style-${sid}`, value: 'overlay' });
  const overlayNote = el('span', { class: 'muted small' });
  const lead = el('input', { type: 'number', min: '0', max: '3', step: '0.1', style: 'width:72px' });
  const makeBtn = el('button', { class: 'btn primary' }, t('lv.make'));
  const offBtn = el('button', { class: 'btn' });
  const onBtn = el('button', { class: 'btn' }, t('lv.use_again'));
  const buttons = [makeBtn, offBtn, onBtn];
  let st = null;

  function show() {
    if (!st) return;
    const cur = st.current;
    now.textContent = cur
      ? t('lv.now_on', t(`lv.style_${cur.style}`), cur.lines, cur.lead)
      : t(st.has_picture ? 'lv.now_original' : 'lv.now_none');
    overlay.disabled = !st.has_picture;
    overlayNote.textContent = st.has_picture ? '' : t('lv.overlay_needs_picture');
    const want = pref('style', 'plain');
    (want === 'overlay' && st.has_picture ? overlay : plain).checked = true;
    offBtn.textContent = t(st.has_picture ? 'lv.restore' : 'lv.remove');
    offBtn.classList.toggle('hidden', !st.active);
    onBtn.classList.toggle('hidden', st.active || !st.made);
    makeBtn.textContent = t(st.active || st.made ? 'lv.make_again' : 'lv.make');
  }

  async function load() {
    try {
      st = await api.get(`/api/songs/${sid}/lyric-video`);
      const saved = Number(pref('lead', ''));
      lead.value = String(st.current ? st.current.lead : (pref('lead', '') !== '' && saved >= 0 && saved <= st.lead_max ? saved : st.lead_default));
      show();
    } catch (err) { now.textContent = errorText(err); }
  }

  const busy = (on) => buttons.forEach((b) => { b.disabled = on; });

  makeBtn.addEventListener('click', async () => {
    const lines = editor.lines();
    if (!lines.length) { toast(t('lv.need_lines'), true); return; }
    const sec = Number(lead.value);
    if (lead.value.trim() === '' || !Number.isFinite(sec) || sec < 0 || sec > (st ? st.lead_max : 3)) { toast(t('err.lyricvideo_lead'), true); return; }
    busy(true);
    try {
      await editor.save();
      const style = overlay.checked && !overlay.disabled ? 'overlay' : 'plain';
      keep('style', style);
      keep('lead', String(sec));
      const res = await api.post(`/api/songs/${sid}/lyric-video`, { lines, style, lead: sec });
      const fin = await jb.follow(res.job);
      if (fin.status === 'succeeded') {
        toast(t('lv.done'));
        bus.dispatchEvent(new CustomEvent('reload-songs'));   // the panel is drawn again for the new picture
      }
    } catch (err) { toast(errorText(err), true); }
    finally { busy(false); }
  });

  async function use(on) {
    busy(true);
    try {
      st = await api.post(`/api/songs/${sid}/lyric-video/use`, { on });
      toast(t(on ? 'lv.done' : (st.has_picture ? 'lv.restored' : 'lv.removed')));
      bus.dispatchEvent(new CustomEvent('reload-songs'));
    } catch (err) { toast(errorText(err), true); }
    finally { busy(false); }
  }
  offBtn.addEventListener('click', () => use(false));
  onBtn.addEventListener('click', () => use(true));
  [plain, overlay].forEach((r) => r.addEventListener('change', () => keep('style', overlay.checked ? 'overlay' : 'plain')));

  editor.load(sid, 'original', mediaUrl(sid, s.audio));
  load();
  return [
    el('p', { class: 'muted small' }, t('lv.note')),
    now,
    editor.el,
    el('h4', { style: 'margin:10px 0 6px' }, t('lv.step_picture')),
    el('div', { class: 'row', style: 'flex-wrap:wrap;gap:14px;align-items:center' },
      el('label', {}, plain, ' ', t('lv.style_plain')),
      el('label', {}, overlay, ' ', t('lv.style_overlay')), overlayNote),
    el('div', { class: 'row', style: 'align-items:center;gap:6px' },
      el('span', {}, t('lv.lead_before')), lead, el('span', {}, t('lv.lead_after'))),
    el('div', { class: 'row', style: 'flex-wrap:wrap' }, makeBtn, onBtn, offBtn),
    jb.el,
  ];
}
