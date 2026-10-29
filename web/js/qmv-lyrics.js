// Lyric subtitles for the quick MV studio look: the old AI cover "dynamic lyric MV" and its
// per-line timing panel (▶ this line, ±0.5 s, start = player time, delete, add a line, save).
import { api } from './api.js';
import { el, toast } from './ui.js';
import { t, errorText } from './i18n.js';
import { jobBox } from './jobview.js';

const r2 = (v) => Math.round(v * 100) / 100;
function fmt(sec) {
  const m = Math.floor(sec / 60);
  return `${m}:${(sec - m * 60).toFixed(2).padStart(5, '0')}`;
}
function parse(text) {   // 1:23.45, 83.45 or 1：23.45
  const s = String(text || '').trim().replace('：', ':');
  const m = s.match(/^(\d+):(\d+(?:\.\d+)?)$/);
  if (m) return Number(m[1]) * 60 + Number(m[2]);
  return /^\d+(\.\d+)?$/.test(s) ? Number(s) : NaN;
}

export function lyricsEditor() {
  let songId = null;
  let source = null;
  let lines = [];
  let stopAt = null;
  const area = el('textarea', { rows: 6, style: 'width:100%' });
  const player = el('audio', { controls: true, preload: 'none', style: 'width:100%' });
  player.addEventListener('timeupdate', () => { if (stopAt != null && player.currentTime >= stopAt) { player.pause(); stopAt = null; } });
  const status = el('div', { class: 'small muted' });
  const jb = jobBox();
  const table = el('div', { class: 'list qmv-lines' });
  const head = el('h4', { style: 'margin:6px 0' });
  const hint = el('p', { class: 'muted small' });
  const pasteBtn = el('button', { class: 'btn small', onclick: async () => {
    try { area.value = (await navigator.clipboard.readText()).replace(/\r\n?/g, '\n'); }
    catch { toast(t('lib.paste_denied'), true); area.focus(); }
  } });
  const alignBtn = el('button', { class: 'btn small primary', onclick: () => align(false) });
  const evenBtn = el('button', { class: 'btn small', onclick: () => align(true) });
  const addBtn = el('button', { class: 'btn small', onclick: () => {
    const at = r2(player.currentTime || (lines.length ? lines[lines.length - 1].end : 0));
    lines.push({ start: at, end: r2(at + 3), text: t('qmvl.new_line') });
    lines.sort((a, b) => a.start - b.start);
    render();
  } });
  const saveBtn = el('button', { class: 'btn small', onclick: () => save(true) });
  const clearBtn = el('button', { class: 'btn small danger', onclick: () => { lines = []; render(); } });
  const box = el('div', { class: 'qmv-lyrics' },
    head, hint,
    el('div', { class: 'row' }, pasteBtn, alignBtn, evenBtn), area, status, jb.el,
    player,
    el('div', { class: 'row' }, addBtn, saveBtn, clearBtn), table);

  function texts() {
    head.textContent = t('qmvl.title');
    hint.textContent = t('qmvl.hint');
    area.placeholder = t('qmvl.placeholder');
    pasteBtn.textContent = t('qmvl.paste');
    alignBtn.textContent = t('qmvl.align');
    evenBtn.textContent = t('qmvl.even');
    addBtn.textContent = t('qmvl.add');
    saveBtn.textContent = t('qmvl.save');
    clearBtn.textContent = t('qmvl.clear');
    render();
  }

  function render() {
    if (!lines.length) { table.replaceChildren(el('div', { class: 'empty small' }, t('qmvl.none'))); return; }
    table.replaceChildren(...lines.map((ln, i) => {
      const st = el('input', { type: 'text', value: fmt(ln.start), style: 'width:84px', onchange: () => {
        const v = parse(st.value);
        if (Number.isFinite(v) && v >= 0) { const d = ln.end - ln.start; ln.start = r2(v); if (ln.end <= ln.start) ln.end = r2(ln.start + Math.max(d, 0.5)); }
        else toast(t('qmvl.bad_time'), true);
        render();
      } });
      const en = el('input', { type: 'text', value: fmt(ln.end), style: 'width:84px', onchange: () => {
        const v = parse(en.value);
        if (Number.isFinite(v) && v > ln.start) ln.end = r2(v); else toast(t('qmvl.bad_time'), true);
        render();
      } });
      const tx = el('input', { type: 'text', value: ln.text, maxlength: 120, style: 'flex:1;min-width:160px', onchange: () => { ln.text = tx.value.trim() || ln.text; } });
      const nudge = (d) => () => { ln.start = r2(Math.max(0, ln.start + d)); ln.end = r2(Math.max(ln.start + 0.3, ln.end + d)); render(); };
      return el('div', { class: 'item', style: 'flex-wrap:wrap;gap:6px' },
        el('span', { class: 'muted small', style: 'width:26px' }, String(i + 1)),
        el('button', { class: 'btn small', title: t('qmvl.play_line'), onclick: () => {
          if (!player.src) return;
          player.currentTime = ln.start; stopAt = ln.end; player.play().catch(() => {});
        } }, '▶'),
        st,
        el('button', { class: 'btn small', onclick: nudge(-0.5) }, '−0.5'),
        el('button', { class: 'btn small', onclick: nudge(0.5) }, '+0.5'),
        el('button', { class: 'btn small', title: t('qmvl.set_start'), onclick: () => {
          const d = ln.end - ln.start; ln.start = r2(player.currentTime || 0); ln.end = r2(ln.start + d); lines.sort((a, b) => a.start - b.start); render();
        } }, '📍'),
        en, tx,
        el('button', { class: 'btn small danger', title: t('common.delete'), onclick: () => { lines.splice(i, 1); render(); } }, '🗑'));
    }));
  }

  async function align(even, retried = false) {
    if (!songId) return;
    if (!area.value.trim()) { toast(t('qmvl.need_text'), true); return; }
    alignBtn.disabled = evenBtn.disabled = true;
    try {
      const res = await api.post(`/api/songs/${songId}/quickmv/lyrics/align`, { text: area.value, even });
      if (res.job && !retried) {
        status.textContent = t('qmvl.whisper_running');
        const fin = await jb.follow(res.job);
        if (fin.status !== 'succeeded') { status.textContent = t('qmvl.whisper_failed'); return; }
        alignBtn.disabled = evenBtn.disabled = false;
        await align(false, true);
        return;
      }
      lines = res.lines || [];
      status.textContent = t(`qmvl.mode_${res.mode}`, lines.length, res.total || lines.length);
      render();
      await save(false);
    } catch (err) { toast(errorText(err), true); }
    finally { alignBtn.disabled = evenBtn.disabled = false; }
  }

  async function save(say) {
    if (!songId || !source) return;
    try {
      const res = await api.put(`/api/songs/${songId}/quickmv/lyrics`, { source, text: area.value, lines });
      lines = res.lines;
      render();
      if (say) toast(t('qmvl.saved'));
    } catch (err) { toast(errorText(err), true); }
  }

  async function load(sid, src, audioUrl) {
    if (sid === songId && src === source) return;
    songId = sid; source = src; lines = []; area.value = ''; status.textContent = '';
    player.src = audioUrl || '';
    if (!sid || !src) { render(); return; }
    try {
      let data = await api.get(`/api/songs/${sid}/quickmv/lyrics?source=${encodeURIComponent(src)}`);
      if (!data.lines.length && !data.text && src !== 'original') {
        // a cover or a take keeps the song's timing: start from the original's lyrics
        const orig = await api.get(`/api/songs/${sid}/quickmv/lyrics?source=original`);
        if (orig.lines.length || orig.text) { data = orig; status.textContent = t('qmvl.from_original'); }
      }
      area.value = data.text || '';
      lines = data.lines || [];
    } catch { /* nothing saved yet */ }
    render();
  }

  texts();
  return { el: box, texts, load, save: () => save(false), lines: () => lines.map((x) => ({ ...x })) };
}
