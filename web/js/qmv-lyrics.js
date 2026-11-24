// Lyric subtitles for the quick MV studio look: the old AI cover "dynamic lyric MV" and its
// per-line timing panel (▶ this line, ±0.5 s on the start and on the end, start = player time, delete, add a line, save).
// A line can be anchored (🔒, as on the MV page): its time is kept when the lines are timed again, the
// lines between two anchors are matched only to what was heard between them, and a stretch between
// anchors where lines were not heard at all is listened to again by Whisper (app/relisten.py).
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

// keys: other heading / hint texts (the library's lyric picture uses the same editor and the same saved lines).
// The per-line panel (player, buttons, lines) starts folded under a one-line summary.
export function lyricsEditor(keys = {}) {
  let songId = null;
  let source = null;
  let fileName = '';
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
  // [2026-11-18] 「重新辨識」: Whisper listens to the whole song again and then, with the lyrics as they are now, to
  // the stretches whose lines are not placed. The user changed the lyrics and wanted a way to make it listen
  // again; 「自動對時間」 keeps what was heard and only listens again where lines are not placed.
  const forceBtn = el('button', { class: 'btn small', onclick: () => { if (confirm(t('qmvl.force_ask'))) align(false, 0, true, true); } });
  const addBtn = el('button', { class: 'btn small', onclick: () => {
    const at = r2(player.currentTime || (lines.length ? lines[lines.length - 1].end : 0));
    lines.push({ start: at, end: r2(at + 3), text: t('qmvl.new_line') });
    lines.sort((a, b) => a.start - b.start);
    render();
  } });
  const saveBtn = el('button', { class: 'btn small', onclick: () => save(true) });
  const clearBtn = el('button', { class: 'btn small danger', onclick: () => { lines = []; render(); } });
  // the timed lines as an LRC file ([mm:ss.xx] text; a last empty stamp marks where the last line ends)
  const lrcBtn = el('button', { class: 'btn small', onclick: () => {
    if (!lines.length) { toast(t('qmvl.lrc_empty'), true); return; }
    const stamp = (sec) => { const v = Math.max(0, Number(sec) || 0), m = Math.floor(v / 60); return `[${String(m).padStart(2, '0')}:${(v - m * 60).toFixed(2).padStart(5, '0')}]`; };
    const sorted = [...lines].sort((a, b) => a.start - b.start);
    const body = sorted.map((x) => `${stamp(x.start)}${x.text}`).concat([stamp(sorted[sorted.length - 1].end)]).join('\r\n') + '\r\n';
    const a = el('a', { href: URL.createObjectURL(new Blob(['\ufeff' + body], { type: 'text/plain;charset=utf-8' })),
      download: `${(fileName || 'lyrics').replace(/[\\/:*?"<>|]+/g, '_').trim() || 'lyrics'}.lrc` });
    document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  } });
  const unlockBtn = el('button', { class: 'btn small', onclick: () => { lines.forEach((x) => { delete x.locked; }); render(); save(false); } });
  const anchorHint = el('p', { class: 'muted small', style: 'margin:4px 0' });
  const adjust = [anchorHint, player, el('div', { class: 'row' }, addBtn, saveBtn, lrcBtn, unlockBtn, clearBtn), table];
  const foldTitle = el('span', {});
  const box = el('div', { class: 'qmv-lyrics' },
    head, hint,
    el('div', { class: 'row' }, pasteBtn, alignBtn, evenBtn, forceBtn), area, status, jb.el,
    el('details', { class: 'qmv-adjust' }, el('summary', { style: 'cursor:pointer;margin:6px 0' }, foldTitle), ...adjust));

  function texts() {
    head.textContent = t(keys.title || 'qmvl.title');
    hint.textContent = t(keys.hint || 'qmvl.hint');
    area.placeholder = t('qmvl.placeholder');
    pasteBtn.textContent = t('qmvl.paste');
    alignBtn.textContent = t('qmvl.align');
    evenBtn.textContent = t('qmvl.even');
    forceBtn.textContent = t('qmvl.force');
    forceBtn.title = t('qmvl.force_tip');
    addBtn.textContent = t('qmvl.add');
    saveBtn.textContent = t('qmvl.save');
    clearBtn.textContent = t('qmvl.clear');
    unlockBtn.textContent = t('qmvl.unlock_all');
    lrcBtn.textContent = t('qmvl.download_lrc');
    lrcBtn.title = t('qmvl.download_lrc_tip');
    anchorHint.textContent = t('qmvl.anchor_hint');
    render();
  }

  function render() {
    foldTitle.textContent = t('qmvl.adjust', lines.length);
    unlockBtn.disabled = !lines.some((x) => x.locked);
    if (!lines.length) { table.replaceChildren(el('div', { class: 'empty small' }, t('qmvl.none'))); return; }
    table.replaceChildren(...lines.map((ln, i) => {
      const lk = !!ln.locked;
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
      // the start and the end are tuned on their own: each pair of buttons moves only its side, stopping
      // 0.3 s from the other side (never pushing it) and the start at 0
      const nudgeStart = (d) => () => {
        ln.start = r2(d < 0 ? Math.max(0, ln.start + d) : Math.min(ln.start + d, Math.max(ln.start, ln.end - 0.3)));
        render();
      };
      const nudgeEnd = (d) => () => {
        ln.end = r2(d > 0 ? ln.end + d : Math.max(ln.end + d, Math.min(ln.end, ln.start + 0.3)));
        render();
      };
      const lockBtn = el('button', {
        class: 'btn small', title: t(lk ? 'qmvl.locked_tip' : 'qmvl.lock_tip'),
        style: lk ? 'border-color:#86efac;color:#86efac;background:rgba(34,197,94,0.18);font-weight:700' : '',
        onclick: () => { if (ln.locked) delete ln.locked; else ln.locked = true; render(); save(false); },
      }, t(lk ? 'qmvl.locked' : 'qmvl.lock'));
      const row = el('div', { class: 'item', style: 'flex-wrap:wrap;gap:6px' + (lk ? ';border-color:rgba(34,197,94,0.65);background:rgba(34,197,94,0.06)' : '') },
        el('span', { class: 'muted small', style: 'width:26px' }, String(i + 1)),
        el('button', { class: 'btn small', title: t('qmvl.play_line'), onclick: () => {
          if (!player.src) return;
          player.currentTime = ln.start; stopAt = ln.end; player.play().catch(() => {});
        } }, '▶'),
        st,
        el('button', { class: 'btn small', title: t('qmvl.start_earlier'), onclick: nudgeStart(-0.5) }, '−0.5'),
        el('button', { class: 'btn small', title: t('qmvl.start_later'), onclick: nudgeStart(0.5) }, '+0.5'),
        el('button', { class: 'btn small', title: t('qmvl.set_start'), onclick: () => {
          const d = ln.end - ln.start; ln.start = r2(player.currentTime || 0); ln.end = r2(ln.start + d); lines.sort((a, b) => a.start - b.start); render();
        } }, '📍'),
        en,
        el('button', { class: 'btn small', title: t('qmvl.end_earlier'), onclick: nudgeEnd(-0.5) }, '−0.5'),
        el('button', { class: 'btn small', title: t('qmvl.end_later'), onclick: nudgeEnd(0.5) }, '+0.5'),
        lockBtn, tx,
        el('button', { class: 'btn small danger', title: t('common.delete'), onclick: () => { lines.splice(i, 1); render(); } }, '🗑'));
      if (lk) {      // an anchor: nothing about its time can be changed until it is freed
        [st, en].forEach((x) => { x.readOnly = true; x.title = t('qmvl.locked_tip'); });
        row.querySelectorAll('button').forEach((b) => { if (b !== lockBtn && b.textContent !== '▶') b.disabled = true; });
      }
      return row;
    }));
  }

  // round: how many Whisper jobs this press has waited for (the first listening, then one listening again)
  async function align(even, round = 0, again = true, fresh = false) {
    if (!songId) return;
    if (!area.value.trim()) { toast(t('qmvl.need_text'), true); return; }
    // keys.beforeAlign: a last question before Whisper is asked (it separates the vocals first); LRC lines
    // carry their own times and "even" only spreads the lines, so neither separates anything
    if (!even && !round && keys.beforeAlign && !/^\s*\[\d{1,3}:\d{2}/m.test(area.value) && !(await keys.beforeAlign())) return;
    alignBtn.disabled = evenBtn.disabled = forceBtn.disabled = true;
    try {
      const res = await api.post(`/api/songs/${songId}/quickmv/lyrics/align`,
        { text: area.value, even, lines: lines.map((x) => ({ ...x })), relisten: again, refresh: fresh && !round });
      if (res.job && round < 3) {
        status.textContent = res.relisten ? t('qmvl.relisten_running', res.relisten) : t('qmvl.whisper_running');
        const fin = await jb.follow(res.job);
        if (fin.status !== 'succeeded') {
          if (!res.relisten) { status.textContent = t('qmvl.whisper_failed'); return; }
          toast(t('qmvl.relisten_failed'), true);
          alignBtn.disabled = evenBtn.disabled = forceBtn.disabled = false;
          await align(false, round + 1, false);      // place the lines by what was heard before
          return;
        }
        alignBtn.disabled = evenBtn.disabled = forceBtn.disabled = false;
        await align(false, round + 1, again);
        return;
      }
      lines = res.lines || [];
      status.textContent = t(`qmvl.mode_${res.mode}`, res.matched ?? lines.length, res.total || lines.length, res.anchors || 0);
      const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
      if (res.relistened) status.textContent += ' ' + t('qmvl.relistened', res.relistened);
      if (res.missing && res.missing.length) {
        status.textContent += ' ' + t('qmvl.missing', res.missing.map((u) => `${mmss(u.start)}–${mmss(u.end)}`).join(', '));
      }
      if (res.unsung && res.unsung.length) {
        status.textContent += ' ' + t('qmvl.unsung', res.unsung.map((u) => `${mmss(u.start)}–${mmss(u.end)}`).join(', '));
      }
      render();
      await save(false);
    } catch (err) { toast(errorText(err), true); }
    finally { alignBtn.disabled = evenBtn.disabled = forceBtn.disabled = false; }
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

  async function load(sid, src, audioUrl, name = '') {
    fileName = name || fileName;
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
