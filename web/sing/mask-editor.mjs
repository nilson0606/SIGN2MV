import { normalizeMasks } from './scoring.mjs';
const $ = id => document.getElementById(id);
export function parseMaskTime(text) {
  const value = String(text).trim();
  if (/^\d+(?:\.\d+)?$/.test(value)) return Number(value);
  const match = /^(\d+):([0-5]?\d(?:\.\d+)?)$/.exec(value);
  if (match) return Number(match[1]) * 60 + Number(match[2]);
  throw new Error('時間請輸入秒數或 分:秒，例如 32.5 或 1:02.5。');
}
export function formatMaskTime(time) {
  const tenths = Math.round(time * 10), minutes = Math.floor(tenths / 600);
  return `${minutes}:${((tenths % 600) / 10).toFixed(1).padStart(4,'0')}`;
}
export function createMaskEditor(options) {
  function controls() {
    const enabled = options.canEdit(), reference = options.reference();
    for (const id of ['mask-start','mask-end','mask-mark-start','mask-mark-end','mask-add']) $(id).disabled = !enabled;
    $('mask-clear').disabled = !enabled || !reference?.masks?.length;
    $('mask-list').querySelectorAll('button').forEach(button => { button.disabled = !enabled; });
  }
  function render() {
    const reference = options.reference();
    $('mask-list').replaceChildren();
    $('mask-start').value = ''; $('mask-end').value = '';
    $('mask-song').textContent = reference ? `${reference.title} · ${({'bs-roformer':'BS-RoFormer','mel-roformer':'Mel-Band RoFormer'}[reference.separationModel] || 'Demucs')} · ${reference.vocalMode === 'lead' ? '主唱模式' : '一般人聲'} · ${(reference.pitchMethod || 'yin').toUpperCase()} · 基準長度 ${formatMaskTime(reference.duration)}` : '尚未載入歌曲基準。';
    for (const [index, range] of (reference?.masks || []).entries()) {
      const row = document.createElement('li'), label = document.createElement('span'), jump = document.createElement('button'), remove = document.createElement('button');
      label.textContent = `${formatMaskTime(range.start)} → ${formatMaskTime(range.end)}`;
      jump.type = remove.type = 'button'; jump.className = remove.className = 'secondary';
      jump.textContent = '跳到起點'; remove.textContent = '刪除';
      jump.addEventListener('click', () => { if (options.canEdit()) options.seek(range.start); });
      remove.addEventListener('click', () => commit(reference.masks.filter((_,i) => i !== index)));
      row.append(label,jump,remove); $('mask-list').append(row);
    }
    $('mask-status').textContent = !reference ? '請先載入歌曲基準。' : !options.supported() ? '本機工具需要更新並重新啟動，才能保存遮罩。' : reference.masks?.length ? `已保存 ${reference.masks.length} 段不計分區間。` : '目前沒有遮罩，依原本歌曲基準評分。';
    controls();
  }
  async function commit(intervals) {
    if (!options.canEdit()) return;
    try {
      const masks = normalizeMasks(intervals, options.reference().duration);
      $('mask-status').textContent = '正在保存遮罩…';
      await options.save(masks);
      render();
    } catch (error) { $('mask-status').textContent = '未保存：' + error.message; }
    finally { controls(); }
  }
  for (const part of ['start','end']) $('mask-mark-'+part).addEventListener('click', () => {
    if (!options.canEdit()) return;
    const time = options.time();
    if (!Number.isFinite(time)) { $('mask-status').textContent = '播放器尚未就緒。'; return; }
    $('mask-'+part).value = String(Math.min(options.reference().duration, Math.max(0, Math.round(time * 10) / 10)));
  });
  $('mask-add').addEventListener('click', () => {
    if (!options.canEdit()) return;
    try { commit([...(options.reference().masks || []), {start:parseMaskTime($('mask-start').value),end:parseMaskTime($('mask-end').value)}]); }
    catch (error) { $('mask-status').textContent = error.message; }
  });
  $('mask-clear').addEventListener('click', () => commit([]));
  render();
  return {render,controls};
}
