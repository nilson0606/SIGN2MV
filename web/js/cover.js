// AI cover workspace: convert a library song with an RVC voice model, mix it,
// keep versions (each one is a render the MV workspace can use), quick remix,
// vocal sections, volume envelopes, voice models and training.
import { api } from './api.js';
import { t, errorText, onLanguageChange, applyTranslations } from './i18n.js';
import { $, el, toast, confirmDialog, fmtDate, fmtTime, fmtBytes } from './ui.js';
import { bus, registerPage, state, goto, mediaUrl, songById, reloadJobs } from './app-state.js';
import { jobBox } from './jobview.js';

const page = $('#page-cover');
let status = null;          // /api/cover/status
let songId = null;
let songState = null;       // /api/cover/songs/<id>
let masks = [];
let vsegs = [];
let lastAudio = null;       // the player whose time "set from player" uses
let busyJob = null;
let saveTimer = null;
const bindings = new Map(); // param path -> {get, set}

// ------------------------------------------------------------------ small widgets
function getPath(obj, path) { return path.split('.').reduce((o, k) => (o == null ? undefined : o[k]), obj); }
function setPath(obj, path, value) {
  const keys = path.split('.');
  let o = obj;
  keys.slice(0, -1).forEach((k) => { if (o[k] == null || typeof o[k] !== 'object') o[k] = {}; o = o[k]; });
  o[keys[keys.length - 1]] = value;
}
function changed() { scheduleSave(); }

// slider + number box. scale: stored value = shown / scale (percent sliders use scale 100)
function slider(path, min, max, step, scale = 1, onInput) {
  const range = el('input', { type: 'range', min, max, step });
  const num = el('input', { type: 'number', min, max, step, style: 'width:76px' });
  const sync = (src, dst) => { dst.value = src.value; changed(); if (onInput) onInput(); };
  range.addEventListener('input', () => sync(range, num));
  num.addEventListener('change', () => {
    const v = Math.min(max, Math.max(min, Number(num.value) || 0));
    num.value = v; sync(num, range);
  });
  const ctl = {
    el: el('span', { class: 'row', style: 'gap:6px;flex-wrap:nowrap' }, range, num),
    get: () => Math.round((Number(num.value) / scale) * 1000) / 1000,
    set: (v) => { const x = Math.round(Number(v) * scale * 1000) / 1000; range.value = x; num.value = x; },
  };
  if (path) bindings.set(path, ctl);
  return ctl;
}
function select(path, options, onChange) {
  const s = el('select', {}, ...options.map(([v, label]) => el('option', { value: v }, label)));
  s.addEventListener('change', () => { changed(); if (onChange) onChange(); });
  const ctl = { el: s, get: () => (/^-?\d+$/.test(s.value) ? Number(s.value) : s.value), set: (v) => { s.value = String(v); } };
  if (path) bindings.set(path, ctl);
  return ctl;
}
function check(path, key, onChange) {
  const c = el('input', { type: 'checkbox' });
  c.addEventListener('change', () => { changed(); if (onChange) onChange(); });
  const ctl = { el: el('label', { class: 'check' }, c, el('span', { 'data-i18n': key })), box: c, get: () => c.checked, set: (v) => { c.checked = !!v; } };
  if (path) bindings.set(path, ctl);
  return ctl;
}
function field(label, ctl, hint) {
  return el('div', { class: 'cv-field' }, el('span', { class: 'cv-label' }, label), ctl.el || ctl,
    hint ? el('span', { class: 'muted small' }, hint) : null);
}
function details(title, ...children) {
  return el('details', { class: 'cv-details' }, el('summary', {}, title), el('div', { class: 'cv-body' }, ...children));
}
function pctText(v) { return `${Math.round(v * 100)}%`; }
function trackAudio(a) { a.addEventListener('play', () => { lastAudio = a; }); return a; }
function audioEl(src) { return trackAudio(el('audio', { src, controls: true, preload: 'none' })); }

// model choices: every model and its kept epoch versions
function modelOptions() {
  const out = [];
  for (const m of (status && status.models) || []) {
    out.push([m.name, m.name + (m.epochs.length ? ` (${t('cover.final')})` : '')]);
    for (const e of [...m.epochs].reverse()) out.push([`${m.name}__e${e.epoch}`, `  ↳ ${m.name} · ${t('cover.epoch_n', e.epoch)}`]);
  }
  return out;
}
function fillModelSelect(sel, keep) {
  const v = keep !== undefined ? keep : sel.value;
  const opts = modelOptions();
  sel.replaceChildren(...(opts.length ? opts : [['', t('cover.no_models')]]).map(([val, label]) => el('option', { value: val }, label)));
  if (v && !opts.some(([val]) => val === v)) sel.append(el('option', { value: v }, `${v} (${t('cover.missing')})`));
  if (v) sel.value = v;
}

// ------------------------------------------------------------------ layout
const songSel = el('select', { style: 'flex:1;min-width:200px' });
const songInfo = el('div', { class: 'muted small' });
const origPlayer = audioEl('');
const keyCtl = slider('key', -8, 8, 1);
const keyAudio = audioEl('');
const keyBtn = el('button', { class: 'btn small', onclick: () => keyPreview(), 'data-i18n': 'cover.key_preview' });

const modelSel = select('model', []);
const pitchCtl = slider('pitch', -24, 24, 1);
const sepSel = select('sep_model', [['demucs', ''], ['bs_roformer', ''], ['mel_roformer', '']]);
const vmodeSel = select('vocal_mode', [['full', ''], ['lead_keep_backing', ''], ['lead_keep_backing_x2', '']], () => updateVis());
const refineSel = select('bgm_refine', [['none', ''], ['second_pass', '']]);
const backingCtl = check('backing_on', 'cover.backing_on');
const rvc = {
  protect: slider('rvc.protect', 0, 0.5, 0.01), index_rate: slider('rvc.index_rate', 0, 1, 0.01),
  envelope: slider('rvc.envelope', 0, 1, 0.01), f0: select('rvc.f0', [['rmvpe', ''], ['fcpe', ''], ['crepe', '']]),
  autotune: check('rvc.autotune', 'cover.autotune'), autotune_strength: slider('rvc.autotune_strength', 0, 1, 0.05),
  clean: check('rvc.clean', 'cover.clean'), clean_strength: slider('rvc.clean_strength', 0, 1, 0.05),
};
const mfOn = check(null, 'cover.mf_enable', () => updateVis());
const mfSep = select(null, [['aufr33', ''], ['sucial', '']]);
function sideControls(side) {
  const p = `mf.${side}`;
  const c = {
    keep: check(`${p}.keep`, 'cover.mf_keep', () => updateVis()), model: select(`${p}.model`, []),
    pitch: slider(`${p}.pitch`, -24, 24, 1), vol: slider(`${p}.vol`, 0, 200, 1, 100),
    protect: slider(`${p}.protect`, 0, 0.5, 0.01), index_rate: slider(`${p}.index_rate`, 0, 1, 0.01),
    envelope: slider(`${p}.envelope`, 0, 1, 0.01), f0: select(`${p}.f0`, [['rmvpe', 'rmvpe'], ['fcpe', 'fcpe'], ['crepe', 'crepe']]),
    autotune: check(`${p}.autotune`, 'cover.autotune'), autotune_strength: slider(`${p}.autotune_strength`, 0, 1, 0.05),
    clean: check(`${p}.clean`, 'cover.clean'), clean_strength: slider(`${p}.clean_strength`, 0, 1, 0.05),
  };
  c.box = el('div', { class: 'cv-side' });
  c.render = () => c.box.replaceChildren(el('h4', {}, t(`cover.mf_${side}`)), c.keep.el,
    el('div', { class: 'cv-side-body' },
      field(t('cover.model'), c.model), field(t('cover.pitch'), c.pitch), field(t('cover.volume'), c.vol),
      details(t('cover.rvc_tune'), field(t('cover.protect'), c.protect), field(t('cover.index_rate'), c.index_rate),
        field(t('cover.envelope'), c.envelope), field(t('cover.f0'), c.f0), el('div', { class: 'row' }, c.autotune.el, c.autotune_strength.el),
        el('div', { class: 'row' }, c.clean.el, c.clean_strength.el))));
  return c;
}
const male = sideControls('male');
const female = sideControls('female');
const mix = {
  vocal_vol: slider('mix.vocal_vol', 0, 200, 1, 100), bgm_vol: slider('mix.bgm_vol', 0, 200, 1, 100),
};
// The melody instrument track of the old program is not offered (its sound was not good enough);
// the mixer still supports it, the page always sends "no instrument".
const NO_INSTRUMENT = { instrument: 'none', inst_vol: 0 };

const runJob = jobBox();
const doneBox = el('div', { class: 'cv-done hidden' });
const runBtn = el('button', { class: 'btn primary', onclick: () => runCover(), 'data-i18n': 'cover.run' });
const versionsBox = el('div', { class: 'list cv-versions' });
const maskList = el('div', { class: 'list' });
const vsegList = el('div', { class: 'list' });

function sectionSong() {
  return el('div', { class: 'panel' },
    el('div', { class: 'row' }, el('h2', { style: 'margin:0' }, t('nav.cover')), songSel),
    songInfo,
    el('div', { class: 'track' }, el('span', {}, t('track.mix')), origPlayer),
    el('div', { class: 'section' },
      field(t('cover.key'), keyCtl, t('cover.key_hint')),
      el('div', { class: 'row' }, keyBtn, keyAudio)));
}

function sectionVoice() {
  return el('div', { class: 'panel' },
    el('h3', {}, t('cover.voice')),
    field(t('cover.model'), modelSel), field(t('cover.pitch'), pitchCtl, t('cover.pitch_hint')),
    details(t('cover.rvc_tune'),
      field(t('cover.protect'), rvc.protect, t('cover.protect_hint')),
      field(t('cover.index_rate'), rvc.index_rate, t('cover.index_hint')),
      field(t('cover.envelope'), rvc.envelope, t('cover.envelope_hint')),
      field(t('cover.f0'), rvc.f0),
      el('div', { class: 'row' }, rvc.autotune.el, rvc.autotune_strength.el),
      el('div', { class: 'row' }, rvc.clean.el, rvc.clean_strength.el)),
    details(t('cover.separation'),
      field(t('sep.model'), sepSel), field(t('cover.vocal_mode'), vmodeSel), field(t('cover.bgm_refine'), refineSel),
      el('div', { class: 'cv-backing' }, backingCtl.el), el('p', { class: 'muted small' }, t('cover.sep_hint'))),
    details(t('cover.mf'),
      el('p', { class: 'muted small' }, t('cover.mf_hint')),
      el('div', { class: 'row' }, mfOn.el, el('span', { class: 'muted' }, t('cover.mf_sep')), mfSep.el),
      el('p', { class: 'muted small cv-sucial-note' }, t('cover.sucial_note')),
      el('div', { class: 'cv-sides' }, (male.render(), male.box), (female.render(), female.box))));
}

function sectionMix() {
  return el('div', { class: 'panel' },
    el('h3', {}, t('cover.mix')),
    field(t('cover.vocal_vol'), mix.vocal_vol), field(t('cover.bgm_vol'), mix.bgm_vol),
    details(t('cover.masks'), el('p', { class: 'muted small' }, t('cover.masks_hint')), maskEditor(), maskList),
    details(t('cover.vsegs'), el('p', { class: 'muted small' }, t('cover.vsegs_hint')), vsegEditor(), vsegList),
    el('div', { class: 'row', style: 'margin-top:12px' }, runBtn),
    el('p', { class: 'muted small' }, t('cover.run_hint')),
    runJob.el, doneBox);
}

// ------------------------------------------------------------------ sections (masks)
function timeInput() {
  const i = el('input', { type: 'text', placeholder: '0:00.0', style: 'width:84px' });
  const set = el('button', { class: 'btn small', title: t('cover.from_player'), onclick: () => {
    if (!lastAudio) { toast(t('cover.play_first'), true); return; }
    i.value = fmtTime(lastAudio.currentTime);
  } }, '⏱');
  return { el: el('span', { class: 'row', style: 'gap:4px;flex-wrap:nowrap' }, i, set), get: () => parseTime(i.value), set: (v) => { i.value = v == null ? '' : fmtTime(v); } };
}
function parseTime(s) {
  s = String(s || '').trim();
  if (!s) return NaN;
  const parts = s.split(':').map(Number);
  if (parts.some((x) => !Number.isFinite(x))) return NaN;
  return parts.length === 2 ? parts[0] * 60 + parts[1] : parts[0];
}

const mStart = timeInput();
const mEnd = timeInput();
const mMode = select(null, [['original', ''], ['mute', ''], ['rvc', ''], ['file', '']], () => updateMaskVis());
const mr = {
  model: select(null, []), pitch: slider(null, -24, 24, 1), protect: slider(null, 0, 0.5, 0.01),
  index_rate: slider(null, 0, 1, 0.01), envelope: slider(null, 0, 1, 0.01),
  f0: select(null, [['rmvpe', 'rmvpe'], ['fcpe', 'fcpe'], ['crepe', 'crepe']]),
  sep_on: check(null, 'cover.mask_sep_on', () => updateMaskVis()),
  sep_model: select(null, [['demucs', ''], ['bs_roformer', ''], ['mel_roformer', '']]),
  vocal_mode: select(null, [['full', ''], ['lead_keep_backing', ''], ['lead_keep_backing_x2', '']]),
  bgm_refine: select(null, [['none', ''], ['second_pass', '']]),
};
const mf_ = {
  file: el('input', { type: 'file', accept: 'audio/*,video/*' }), uploaded: null,
  info: el('span', { class: 'muted small' }), target: select(null, [['vocal', ''], ['mix', '']], () => updateMaskVis()),
  offset: el('input', { type: 'number', step: 0.01, value: 0, style: 'width:90px' }), to_ai: check(null, 'cover.mask_to_ai', () => updateMaskVis()),
};
mf_.file.addEventListener('change', async () => {
  const f = mf_.file.files && mf_.file.files[0];
  if (!f || !songId) return;
  mf_.info.textContent = t('lib.uploading', 0);
  const fd = new FormData();
  fd.append('file', f, f.name);
  try {
    const res = await api.upload(`/api/cover/songs/${songId}/patches`, fd);
    mf_.uploaded = res;
    mf_.info.textContent = `${res.name} · ${fmtTime(res.duration)}`;
  } catch (err) { mf_.info.textContent = ''; toast(errorText(err), true); }
});
let editingMask = -1;
const maskAdd = el('button', { class: 'btn small primary', onclick: () => addMask() }, t('cover.add'));
const maskCancel = el('button', { class: 'btn small hidden', onclick: () => { editingMask = -1; updateMaskVis(); }, 'data-i18n': 'common.cancel' });
const mSepBox = el('div', { class: 'cv-sub' });
const mFileBox = el('div', { class: 'cv-sub' });
const mRvcWrap = el('div', {});

function maskEditor() {
  mSepBox.replaceChildren(field(t('sep.model'), mr.sep_model), field(t('cover.vocal_mode'), mr.vocal_mode), field(t('cover.bgm_refine'), mr.bgm_refine));
  mFileBox.replaceChildren(el('div', { class: 'row' }, mf_.file, mf_.info),
    field(t('cover.mask_target'), mf_.target), field(t('cover.mask_offset'), mf_.offset, t('cover.mask_offset_hint')), mf_.to_ai.el);
  mRvcWrap.replaceChildren(el('div', { class: 'cv-sub' },
    field(t('cover.model'), mr.model), field(t('cover.pitch'), mr.pitch), field(t('cover.protect'), mr.protect),
    field(t('cover.index_rate'), mr.index_rate), field(t('cover.envelope'), mr.envelope), field(t('cover.f0'), mr.f0)), mr.sep_on.el, mSepBox);
  return el('div', { class: 'cv-editor' },
    el('div', { class: 'row' }, el('span', {}, t('cover.start')), mStart.el, el('span', {}, t('cover.end')), mEnd.el),
    field(t('cover.mask_mode'), mMode), mRvcWrap, mFileBox,
    el('div', { class: 'row' }, maskAdd, maskCancel));
}
function updateMaskVis() {
  const mode = mMode.get();
  mFileBox.classList.toggle('hidden', mode !== 'file');
  const rvcVisible = mode === 'rvc' || (mode === 'file' && mf_.to_ai.get() && mf_.target.get() === 'vocal');
  mRvcWrap.classList.toggle('hidden', !rvcVisible);
  mr.sep_on.el.classList.toggle('hidden', mode !== 'rvc');
  mSepBox.classList.toggle('hidden', mode !== 'rvc' || !mr.sep_on.get());
  mf_.to_ai.el.classList.toggle('hidden', mf_.target.get() !== 'vocal');
  maskAdd.textContent = editingMask >= 0 ? t('cover.update') : t('cover.add');
  maskCancel.classList.toggle('hidden', editingMask < 0);
}
function addMask() {
  const start = mStart.get();
  const end = mEnd.get();
  if (!(start >= 0) || !(end > start)) { toast(t('cover.bad_range'), true); return; }
  const m = { start, end, mode: mMode.get() };
  const rvcParams = () => ({ model: mr.model.get(), pitch: mr.pitch.get(), protect: mr.protect.get(), index_rate: mr.index_rate.get(),
    envelope: mr.envelope.get(), f0: mr.f0.get() });
  if (m.mode === 'rvc') {
    m.rvc = rvcParams();
    if (mr.sep_on.get()) m.sep = { sep_model: mr.sep_model.get(), vocal_mode: mr.vocal_mode.get(), bgm_refine: mr.bgm_refine.get() };
  } else if (m.mode === 'file') {
    const prev = editingMask >= 0 ? masks[editingMask] : null;
    const up = mf_.uploaded || (prev && prev.file ? { file: prev.file, name: prev.name } : null);
    if (!up) { toast(t('cover.pick_clip'), true); return; }
    Object.assign(m, { file: up.file, name: up.name, target: mf_.target.get(), offset: Number(mf_.offset.value) || 0 });
    m.to_ai = m.target === 'vocal' && mf_.to_ai.get();
    if (m.to_ai) m.rvc = rvcParams();
  }
  if (editingMask >= 0) masks[editingMask] = m; else masks.push(m);
  masks.sort((a, b) => a.start - b.start);
  editingMask = -1;
  mf_.uploaded = null; mf_.file.value = ''; mf_.info.textContent = '';
  renderMasks(); updateMaskVis(); changed();
}
function editMask(i) {
  const m = masks[i];
  editingMask = i;
  mStart.set(m.start); mEnd.set(m.end); mMode.set(m.mode);
  const r = m.rvc || {};
  const cur = readForm();
  mr.model.set(r.model || cur.model); mr.pitch.set(r.pitch ?? cur.pitch); mr.protect.set(r.protect ?? cur.rvc.protect);
  mr.index_rate.set(r.index_rate ?? cur.rvc.index_rate); mr.envelope.set(r.envelope ?? cur.rvc.envelope); mr.f0.set(r.f0 || cur.rvc.f0);
  mr.sep_on.set(!!m.sep);
  if (m.sep) { mr.sep_model.set(m.sep.sep_model); mr.vocal_mode.set(m.sep.vocal_mode); mr.bgm_refine.set(m.sep.bgm_refine); }
  if (m.mode === 'file') {
    mf_.target.set(m.target || 'vocal'); mf_.offset.value = m.offset || 0; mf_.to_ai.set(!!m.to_ai);
    mf_.info.textContent = m.name || m.file;
  }
  updateMaskVis();
}
function maskText(m) {
  let s = `${fmtTime(m.start)} – ${fmtTime(m.end)} · ${t(`cover.mask.${m.mode}`)}`;
  if (m.mode === 'rvc') s += ` · ${m.rvc.model} ${m.rvc.pitch > 0 ? '+' : ''}${m.rvc.pitch}${m.sep ? ' · ' + t('cover.mask_sep_on') : ''}`;
  if (m.mode === 'file') s += ` · ${m.name}${m.target === 'mix' ? ' · ' + t('cover.mask_target.mix') : ''}${m.to_ai ? ' · ' + t('cover.mask_to_ai') : ''}`;
  return s;
}
function renderMasks() {
  maskList.replaceChildren(...(masks.length ? masks.map((m, i) => el('div', { class: 'item' },
    el('div', { class: 'grow' }, maskText(m)),
    el('button', { class: 'btn small', onclick: () => editMask(i) }, t('cover.edit')),
    el('button', { class: 'btn small', onclick: () => { masks.splice(i, 1); editingMask = -1; renderMasks(); updateMaskVis(); changed(); } }, t('common.delete'))))
    : [el('div', { class: 'empty small' }, t('cover.no_masks'))]));
}

// ------------------------------------------------------------------ volume sections
const vStart = timeInput();
const vEnd = timeInput();
const vTrack = select(null, [['vocal', ''], ['bgm', ''], ['backing', '']]);
const vGain = slider(null, 0, 200, 1, 100);
function vsegEditor() {
  return el('div', { class: 'cv-editor' },
    el('div', { class: 'row' }, el('span', {}, t('cover.start')), vStart.el, el('span', {}, t('cover.end')), vEnd.el),
    field(t('cover.vseg_track'), vTrack), field(t('cover.vseg_gain'), vGain),
    el('div', { class: 'row' },
      el('button', { class: 'btn small primary', onclick: () => {
        const start = vStart.get(); const end = vEnd.get();
        if (!(start >= 0) || !(end > start + 0.09)) { toast(t('cover.bad_range'), true); return; }
        vsegs.push({ track: vTrack.get(), start, end, gain: vGain.get() });
        vsegs.sort((a, b) => a.start - b.start);
        renderVsegs(); changed();
      } }, t('cover.add')),
      el('button', { class: 'btn small', onclick: () => { vsegs = []; renderVsegs(); changed(); } }, t('cover.vseg_reset'))));
}
function renderVsegs() {
  vsegList.replaceChildren(...(vsegs.length ? vsegs.map((s, i) => el('div', { class: 'item' },
    el('div', { class: 'grow' }, `${fmtTime(s.start)} – ${fmtTime(s.end)} · ${t(`cover.vseg.${s.track}`)} · ${pctText(s.gain)}`),
    el('button', { class: 'btn small', onclick: () => { vsegs.splice(i, 1); renderVsegs(); changed(); } }, t('common.delete'))))
    : [el('div', { class: 'empty small' }, t('cover.no_vsegs'))]));
}

// ------------------------------------------------------------------ form <-> params
function readForm() {
  const p = {};
  for (const [path, ctl] of bindings) if (!path.startsWith('mf.')) setPath(p, path, ctl.get());
  if (mfOn.get()) {
    p.mf = { sep_model: mfSep.get(), male: {}, female: {} };
    for (const [path, ctl] of bindings) if (path.startsWith('mf.')) setPath(p, path, ctl.get());
  } else p.mf = null;
  p.masks = masks.map((m) => ({ ...m }));
  p.vol_segments = vsegs.map((s) => ({ ...s }));
  p.mix = { ...p.mix, ...NO_INSTRUMENT };
  return p;
}
function writeForm(p) {
  const models = modelOptions().map(([v]) => v);
  fillModelSelect(modelSel.el, p.model || '');
  [male.model, female.model, mr.model].forEach((c) => fillModelSelect(c.el, c.el.value || p.model || models[0] || ''));
  for (const [path, ctl] of bindings) {
    if (path.startsWith('mf.')) continue;
    const v = getPath(p, path);
    if (v !== undefined && v !== null) ctl.set(v);
  }
  mfOn.set(!!p.mf);
  const mf = p.mf || { sep_model: 'aufr33', male: { model: p.model, pitch: p.pitch, vol: 1, keep: false, ...p.rvc }, female: { model: p.model, pitch: p.pitch, vol: 1, keep: false, ...p.rvc } };
  mfSep.set(mf.sep_model || 'aufr33');
  for (const [path, ctl] of bindings) {
    if (!path.startsWith('mf.')) continue;
    const v = getPath({ mf }, path);
    if (v !== undefined && v !== null) ctl.set(v);
  }
  masks = (p.masks || []).map((m) => ({ ...m }));
  vsegs = (p.vol_segments || []).map((s) => ({ ...s }));
  renderMasks(); renderVsegs();
  if (editingMask < 0) {   // keep a section that is being edited
    mr.model.set(p.model); mr.pitch.set(p.pitch); mr.protect.set(p.rvc.protect); mr.index_rate.set(p.rvc.index_rate);
    mr.envelope.set(p.rvc.envelope); mr.f0.set(p.rvc.f0);
  }
  updateVis(); updateMaskVis();
}
function scheduleSave() {
  if (!songId) return;
  clearTimeout(saveTimer);
  const id = songId;
  saveTimer = setTimeout(async () => {
    try { await api.put(`/api/cover/songs/${id}/settings`, { params: readForm() }); } catch { /* not important */ }
  }, 600);
}

function updateVis() {
  const mf = mfOn.get();
  backingCtl.el.classList.toggle('hidden', vmodeSel.get() === 'full' || mf);
  vmodeSel.el.disabled = mf;
  [male, female].forEach((s) => s.box.querySelector('.cv-side-body').classList.toggle('hidden', s.keep.get()));
  page.querySelectorAll('.cv-sides').forEach((n) => n.classList.toggle('hidden', !mf));
  modelSel.el.disabled = mf;
  pitchCtl.el.querySelectorAll('input').forEach((i) => { i.disabled = mf; });
  const seps = (status && status.separators) || {};
  [sepSel.el, mr.sep_model.el].forEach((s) => [...s.options].forEach((o) => { o.disabled = seps[o.value] === false; }));
  [...mfSep.el.options].forEach((o) => { o.disabled = seps[o.value] === false; });
  [vmodeSel.el, mr.vocal_mode.el].forEach((s) => [...s.options].forEach((o) => { o.disabled = o.value !== 'full' && seps.karaoke === false; }));
}

function translateOptions() {
  const lab = (sel, prefix) => [...sel.options].forEach((o) => { o.textContent = t(`${prefix}${o.value}`); });
  [sepSel.el, mr.sep_model.el].forEach((s) => lab(s, 'sep.model.'));
  [vmodeSel.el, mr.vocal_mode.el].forEach((s) => lab(s, 'cover.vmode.'));
  [refineSel.el, mr.bgm_refine.el].forEach((s) => lab(s, 'cover.refine.'));
  lab(rvc.f0.el, 'cover.f0.');
  lab(mfSep.el, 'cover.mfsep.');
  lab(mMode.el, 'cover.mask.');
  lab(mf_.target.el, 'cover.mask_target.');
  lab(vTrack.el, 'cover.vseg.');
}

// ------------------------------------------------------------------ song
function fillSongs() {
  const songs = state.songs.filter((s) => s.source);
  songSel.replaceChildren(el('option', { value: '' }, songs.length ? t('cover.pick_song') : t('cover.no_songs')),
    ...songs.map((s) => el('option', { value: s.song_id }, s.title)));
  if (songId) songSel.value = songId;
}
songSel.addEventListener('change', () => openSong(songSel.value || null));

async function openSong(id) {
  if (saveTimer) { clearTimeout(saveTimer); saveTimer = null; }
  songId = id;
  songSel.value = id || '';
  songState = null;
  editingMask = -1;
  doneBox.classList.add('hidden');
  mf_.uploaded = null; mf_.file.value = ''; mf_.info.textContent = '';
  keyAudio.removeAttribute('src');
  if (!id) { origPlayer.removeAttribute('src'); songInfo.textContent = ''; renderVersions(); return; }
  try {
    songState = await api.get(`/api/cover/songs/${id}`);
  } catch (err) { toast(errorText(err), true); return; }
  const song = songById(id);
  origPlayer.src = song && song.source ? mediaUrl(id, song.source.audio) : '';
  updateSongInfo();
  writeForm(songState.settings);
  renderVersions();
  if (songState.job) follow(songState.job);
}

function updateSongInfo() {
  const song = songId ? songById(songId) : null;
  songInfo.textContent = song && song.source ? `${fmtTime(song.source.duration)} · ${t(`lib.source.${song.source.type}`)}` : '';
}

async function keyPreview() {
  if (!songId) { toast(t('common.select_song'), true); return; }
  keyBtn.disabled = true;
  try {
    const res = await api.post(`/api/cover/songs/${songId}/key_preview`, { key: keyCtl.get() });
    keyAudio.src = mediaUrl(songId, res.path);
    keyAudio.play().catch(() => {});
  } catch (err) { toast(errorText(err), true); }
  keyBtn.disabled = false;
}

// ------------------------------------------------------------------ jobs
// a clear "finished" box under the button: what was made, play it, go to the version or the MV
function showDone(fin) {
  const vid = fin.result && fin.result.version_id;
  const v = ((songState && songState.versions) || []).find((x) => x.id === vid);
  if (fin.status !== 'succeeded' || !v) { doneBox.classList.add('hidden'); return; }
  runJob.hide();
  const item = () => versionsBox.querySelector(`[data-vid="${vid}"]`);
  doneBox.replaceChildren(
    el('div', { class: 'cv-done-title' }, `✅ ${t('cover.done_title', v.title)}${v.duration ? ` · ${fmtTime(v.duration)}` : ''}`),
    el('div', { class: 'muted small' }, t('cover.done_hint')),
    el('div', { class: 'row' },
      el('button', { class: 'btn primary', onclick: () => {
        const box = item();
        if (!box) return;
        box.scrollIntoView({ behavior: 'smooth', block: 'center' });
        const a = box.querySelector('audio');
        if (a) a.play().catch(() => {});
      } }, t('cover.done_play')),
      el('button', { class: 'btn', onclick: () => item()?.scrollIntoView({ behavior: 'smooth', block: 'center' }) }, t('cover.done_show')),
      el('button', { class: 'btn', onclick: () => {
        bus.dispatchEvent(new CustomEvent('mv-open', { detail: { songId, renderId: v.render_id } }));
        goto('mv');
      } }, t('cover.to_mv'))));
  doneBox.classList.remove('hidden');
}

// a quick remix shows its progress and its result inside the version card that was remixed
function showRemixDone(fin, asNew) {
  const vid = fin.result && fin.result.version_id;
  const card = vid && versionsBox.querySelector(`[data-vid="${vid}"]`);
  const v = ((songState && songState.versions) || []).find((x) => x.id === vid);
  if (!card || !v) return;
  card.querySelector('.cv-vjob').replaceChildren(el('div', { class: 'cv-done' },
    el('div', { class: 'cv-done-title' }, `✅ ${asNew ? t('cover.remix_done_new', v.title) : t('cover.remix_done')}`),
    el('div', { class: 'row' }, el('button', { class: 'btn primary', onclick: () => {
      const a = card.querySelector('audio');
      if (a) a.play().catch(() => {});
    } }, t('cover.done_play')))));
  card.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

async function follow(job, remixCard = null, asNew = false) {
  if (busyJob && busyJob.id === job.id) return;   // already followed
  busyJob = job;
  doneBox.classList.add('hidden');
  runBtn.disabled = true;
  let box = runJob;
  if (remixCard) {
    const a = remixCard.querySelector('audio');   // let go of the file that is about to be replaced
    if (a) { a.pause(); a.removeAttribute('src'); a.load(); }
    box = jobBox();
    remixCard.querySelector('.cv-vjob').replaceChildren(box.el);
    remixCard.querySelectorAll('button').forEach((b) => { b.disabled = true; });
  }
  const fin = await box.follow(job);
  busyJob = null;
  runBtn.disabled = false;
  reloadJobs();
  if (fin.status === 'succeeded') toast(t(remixCard ? 'cover.remix_toast' : 'cover.done'));
  if (songId) {
    try { songState = await api.get(`/api/cover/songs/${songId}`); } catch { /* ignore */ }
    if (remixCard && fin.status !== 'succeeded') {
      remixCard.querySelectorAll('button').forEach((b) => { b.disabled = false; });   // keep the error visible
    } else {
      renderVersions(fin.result && fin.result.version_id);
      if (remixCard) showRemixDone(fin, asNew); else showDone(fin);
    }
  }
  bus.dispatchEvent(new Event('renders-changed'));
}

async function runCover() {
  if (!songId) { toast(t('common.select_song'), true); return; }
  try {
    const res = await api.post(`/api/cover/songs/${songId}/run`, { params: readForm() });
    follow(res.job);
  } catch (err) { toast(errorText(err), true); }
}

async function remix(v, asNew) {
  const p = readForm();
  const body = { mix: p.mix, masks: p.masks, vol_segments: p.vol_segments, backing_on: p.backing_on, save_as_new: asNew };
  if (p.mf) body.mf_vols = { male: p.mf.male.vol, female: p.mf.female.vol };
  try {
    const res = await api.post(`/api/cover/songs/${songId}/versions/${v.id}/remix`, body);
    follow(res.job, versionsBox.querySelector(`[data-vid="${v.id}"]`), asNew);
  } catch (err) { toast(errorText(err), true); }
}

// ------------------------------------------------------------------ versions
function renderVersions(highlight) {
  const vs = (songState && songState.versions) || [];
  if (!songId) { versionsBox.replaceChildren(el('div', { class: 'empty' }, t('cover.pick_song'))); return; }
  if (!vs.length) { versionsBox.replaceChildren(el('div', { class: 'empty' }, t('cover.no_versions'))); return; }
  versionsBox.replaceChildren(...vs.map((v) => versionItem(v, v.id === highlight)));
}
// Switch a player to another file and continue from the same second (A/B with the original, stems)
function switchSource(player, url, chips, active) {
  const at = player.currentTime || 0;
  const wasPlaying = !player.paused;
  player.src = url;
  player.load();
  player.addEventListener('loadedmetadata', () => {
    try { player.currentTime = Math.min(at, player.duration || at); } catch { /* ignore */ }
    if (wasPlaying) player.play().catch(() => {});
  }, { once: true });
  chips.forEach((c) => c.classList.toggle('on', c === active));
}

function versionItem(v, hi) {
  const tracksBox = el('div', { class: 'cv-chips hidden' });
  // ?v= makes the browser fetch the audio again after a remix replaced it under the same name
  const src = v.audio ? `${mediaUrl(songId, v.audio)}?v=${Math.round(v.updated_at || v.created_at || 0)}` : '';
  const song = songById(songId);
  const origUrl = song && song.source ? mediaUrl(songId, song.source.audio) : '';
  const player = src ? audioEl(src) : null;
  const chips = [];
  const chip = (label, url) => {
    const b = el('button', { class: 'cv-chip', onclick: () => switchSource(player, url, chips, b) }, label);
    chips.push(b);
    return b;
  };
  const abRow = player && origUrl ? el('div', { class: 'cv-ab' },
    chip(t('cover.ab_cover'), src), chip(t('cover.ab_original'), origUrl),
    el('span', { class: 'muted small' }, t('cover.ab_hint'))) : null;
  if (chips[0]) chips[0].classList.add('on');
  const box = el('div', { class: 'cv-version' + (hi ? ' selected cv-new' : ''), dataset: { vid: v.id } },
    el('div', { class: 'row' },
      el('b', { class: 'grow' }, v.title),
      el('span', { class: 'muted small' }, `${fmtDate(v.updated_at || v.created_at)}${v.duration ? ' · ' + fmtTime(v.duration) : ''}`)),
    el('div', { class: 'muted small' }, v.label + (v.source_version ? ` · ${t('cover.remixed')}` : '')),
    abRow,
    player || el('div', { class: 'muted' }, t('cover.audio_missing')),
    el('div', { class: 'row' },
      el('button', { class: 'btn small', title: t('cover.use_settings_hint'), onclick: () => { writeForm(v.params); changed(); toast(t('cover.settings_loaded')); } }, t('cover.use_settings')),
      el('button', { class: 'btn small', title: t('cover.remix_hint'), onclick: () => remix(v, false) }, t('cover.remix')),
      el('button', { class: 'btn small', onclick: () => remix(v, true) }, t('cover.remix_new')),
      el('button', { class: 'btn small primary', onclick: () => {
        bus.dispatchEvent(new CustomEvent('mv-open', { detail: { songId, renderId: v.render_id } }));
        goto('mv');
      } }, t('cover.to_mv')),
      src ? el('a', { class: 'btn small', href: src, download: `${v.title}.mp3` }, t('common.download')) : null,
      el('button', { class: 'btn small', onclick: async () => {
        if (!tracksBox.classList.contains('hidden')) { tracksBox.classList.add('hidden'); return; }
        try {
          const res = await api.get(`/api/cover/songs/${songId}/versions/${v.id}/tracks`);
          chips.splice(2);   // keep the cover / original chips, rebuild the stems
          tracksBox.replaceChildren(el('span', { class: 'muted small' }, t('cover.stems_hint')),
            ...res.tracks.filter((tr) => tr.key !== 'mix').map((tr) => chip(t(`cover.track.${tr.key}`), mediaUrl(songId, tr.path))));
          tracksBox.classList.remove('hidden');
        } catch (err) { toast(errorText(err), true); }
      } }, t('cover.tracks')),
      el('button', { class: 'btn small', onclick: async () => {
        const title = prompt(t('cover.rename_prompt'), v.title);
        if (!title) return;
        try { await api.patch(`/api/cover/songs/${songId}/versions/${v.id}`, { title }); await openSong(songId); }
        catch (err) { toast(errorText(err), true); }
      } }, t('common.rename')),
      el('button', { class: 'btn small danger', onclick: async () => {
        if (!(await confirmDialog(t('cover.delete_confirm', v.title), t('common.delete')))) return;
        try {
          const res = await api.del(`/api/cover/songs/${songId}/versions/${v.id}`);
          toast(t('cover.deleted', fmtBytes(res.freed || 0)));
          await openSong(songId);
          bus.dispatchEvent(new Event('renders-changed'));
        } catch (err) { toast(errorText(err), true); }
      } }, t('common.delete'))),
    tracksBox,
    el('div', { class: 'cv-vjob' }));
  return box;
}

// ------------------------------------------------------------------ models
const modelsList = el('div', { class: 'list' });
const lossBox = el('div', { class: 'cv-loss' });
const importPath = el('input', { type: 'text', style: 'flex:1;min-width:220px', placeholder: 'D:\\AI_COVER_MV\\models' });
const upName = el('input', { type: 'text', placeholder: 'My_Voice', style: 'width:140px' });
const upPth = el('input', { type: 'file', accept: '.pth' });
const upIdx = el('input', { type: 'file', accept: '.index' });

function lossChart(data, title) {
  const ep = data.epoch || [];
  const series = [['mel', '#3dd9f5'], ['total', '#f5c84c'], ['d_adv', '#c9a7ff']].filter(([k]) => (data[k] || []).some((v) => v != null));
  if (!ep.length || !series.length) return el('div', { class: 'muted small' }, t('cover.no_loss'));
  const W = 520; const H = 180; const P = 30;
  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.setAttribute('class', 'cv-chart');
  const xmin = Math.min(...ep); const xmax = Math.max(...ep, xmin + 1);
  const add = (tag, attrs, text) => { const n = document.createElementNS(svgNS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); if (text) n.textContent = text; svg.append(n); return n; };
  add('line', { x1: P, y1: H - P, x2: W - 8, y2: H - P, stroke: '#2c3945' });
  add('text', { x: P, y: H - 8, fill: '#8a9aa8', 'font-size': 11 }, `${xmin}`);
  add('text', { x: W - 40, y: H - 8, fill: '#8a9aa8', 'font-size': 11 }, `${xmax} ep`);
  series.forEach(([k, color], si) => {
    const vals = data[k].map((v, i) => [ep[i], v]).filter(([, v]) => v != null);
    const ys = vals.map(([, v]) => v);
    const ymin = Math.min(...ys); const ymax = Math.max(...ys, ymin + 1e-6);
    const pts = vals.map(([x, y]) => `${P + (x - xmin) / (xmax - xmin) * (W - P - 10)},${8 + (1 - (y - ymin) / (ymax - ymin)) * (H - P - 16)}`);
    add('polyline', { points: pts.join(' '), fill: 'none', stroke: color, 'stroke-width': 1.6 });
    add('text', { x: P + 4 + si * 150, y: 14, fill: color, 'font-size': 11 }, `${t(`cover.loss.${k}`)} ${ys[ys.length - 1].toFixed(2)}`);
  });
  (data.kept_epochs || []).forEach((e) => {
    const x = P + (e - xmin) / (xmax - xmin) * (W - P - 10);
    add('line', { x1: x, y1: 8, x2: x, y2: H - P, stroke: '#4fd18b', 'stroke-dasharray': '3 3' });
  });
  return el('div', {}, el('div', { class: 'muted small' }, title), svg);
}

async function showLoss(name) {
  try {
    const d = await api.get(`/api/cover/models/${encodeURIComponent(name)}/loss`);
    lossBox.replaceChildren(lossChart(d, t('cover.loss_title', name)));
  } catch (err) { lossBox.replaceChildren(el('div', { class: 'muted small' }, errorText(err))); }
}

function renderModels() {
  const ms = (status && status.models) || [];
  modelsCount.textContent = t('cover.models_n', ms.length);
  const fd = folds.models;
  if (fd && status && foldPref('models') === null && fd.open !== !ms.length) {   // open only while there is no model yet
    fd.dataset.auto = '1';
    fd.open = !ms.length;
  }
  modelsList.replaceChildren(...(ms.length ? ms.map((m) => el('div', { class: 'cv-model' },
    el('div', { class: 'row' },
      el('b', { class: 'grow' }, m.name),
      el('span', { class: 'muted small' }, `${fmtBytes(m.size)}${m.index ? '' : ' · ' + t('cover.no_index')}`),
      m.has_loss ? el('button', { class: 'btn small', onclick: () => showLoss(m.name) }, t('cover.loss')) : null,
      el('button', { class: 'btn small danger', onclick: async () => {
        if (!(await confirmDialog(t('cover.model_delete_confirm', m.name), t('common.delete')))) return;
        try { await api.del(`/api/cover/models/${encodeURIComponent(m.name)}`); await loadStatus(); } catch (err) { toast(errorText(err), true); }
      } }, t('common.delete'))),
    m.epochs.length ? el('div', { class: 'row small' }, el('span', { class: 'muted' }, t('cover.epochs')),
      ...m.epochs.map((e) => el('span', { class: 'tag' }, t('cover.epoch_n', e.epoch), ' ',
        el('a', { href: '#', title: t('common.delete'), onclick: async (ev) => {
          ev.preventDefault();
          if (!(await confirmDialog(t('cover.epoch_delete_confirm', m.name, e.epoch), t('common.delete')))) return;
          try { await api.del(`/api/cover/models/${encodeURIComponent(m.name)}/epochs/${e.epoch}`); await loadStatus(); } catch (err) { toast(errorText(err), true); }
        } }, '✕')))) : null))
    : [el('div', { class: 'empty' }, t('cover.no_models_hint'))]));
}

// management panels fold away; whether each one is open is remembered in this browser
const modelsCount = el('span', { class: 'muted small' });
const folds = {};
function foldPref(key) {
  try { return localStorage.getItem(`sign2mv.cover.fold.${key}`); } catch { return null; }
}
function foldPanel(key, title, extra, ...children) {
  let open = null;
  try { open = localStorage.getItem(`sign2mv.cover.fold.${key}`); } catch { /* storage unavailable */ }
  const d = el('details', { class: 'panel cv-fold', open: open === '1' },
    el('summary', {}, el('h3', {}, title), extra || null), ...children);
  d.addEventListener('toggle', () => {
    if (d.dataset.auto) { delete d.dataset.auto; return; }   // opened by the page, not by the user
    try { localStorage.setItem(`sign2mv.cover.fold.${key}`, d.open ? '1' : '0'); } catch { /* ignore */ }
  });
  folds[key] = d;
  return d;
}

function sectionModels() {
  return foldPanel('models', t('cover.models'), modelsCount,
    el('p', { class: 'muted small' }, t('cover.models_hint')),
    modelsList, lossBox,
    el('div', { class: 'section' },
      el('div', { class: 'cv-label' }, t('cover.import_folder')),
      el('div', { class: 'row' }, importPath, el('button', { class: 'btn', onclick: async () => {
        try {
          const res = await api.post('/api/cover/models/import', { path: importPath.value });
          const skipped = res.skipped.map((s) => `${s.source}: ${errorText({ code: s.reason })}`).join('\n');
          toast(t('cover.imported', res.imported.length) + (skipped ? `\n${skipped}` : ''), !res.imported.length, 9000);
          await loadStatus();
        } catch (err) { toast(errorText(err), true); }
      } }, t('cover.import'))),
      el('p', { class: 'muted small' }, t('cover.import_hint'))),
    el('div', { class: 'section' },
      el('div', { class: 'cv-label' }, t('cover.upload_model')),
      el('div', { class: 'row' }, upName),
      el('div', { class: 'row' }, el('span', { class: 'small muted', style: 'width:52px' }, '.pth'), upPth),
      el('div', { class: 'row' }, el('span', { class: 'small muted', style: 'width:52px' }, '.index'), upIdx,
        el('button', { class: 'btn', onclick: async () => {
          const f = upPth.files && upPth.files[0];
          if (!f) { toast(t('lib.pick_file'), true); return; }
          const fd = new FormData();
          fd.append('name', upName.value || f.name.replace(/\.pth$/i, ''));
          fd.append('pth', f, f.name);
          if (upIdx.files && upIdx.files[0]) fd.append('index', upIdx.files[0], upIdx.files[0].name);
          try { const res = await api.upload('/api/cover/models/upload', fd); toast(t('cover.uploaded', res.name)); await loadStatus(); }
          catch (err) { toast(errorText(err), true); }
        } }, t('cover.upload')))));
}

// ------------------------------------------------------------------ training
const trName = el('input', { type: 'text', placeholder: 'My_Voice_Ver1', style: 'width:180px' });
const trFiles = el('input', { type: 'file', multiple: true, accept: 'audio/*,video/*' });
const trFileInfo = el('span', { class: 'muted small' });
const trPaths = el('textarea', { placeholder: 'D:\\recordings\\my_voice', style: 'min-height:54px' });
const trEpochs = el('input', { type: 'number', value: 100, min: 1, max: 2000, style: 'width:90px' });
const trBatch = el('select', {}, ...[4, 8, 16].map((b) => el('option', { value: b, selected: b === 8 }, String(b))));
const trSave = el('input', { type: 'number', value: 10, min: 1, max: 500, style: 'width:80px' });
const trRate = el('select', {}, ...[32000, 40000, 48000].map((r) => el('option', { value: r, selected: r === 40000 }, `${r / 1000} kHz`)));
const trJob = jobBox();
const trLoss = el('div', { class: 'cv-loss' });
const trStart = el('button', { class: 'btn primary', 'data-i18n': 'cover.train_start' });
const trStop = el('button', { class: 'btn danger hidden', 'data-i18n': 'cover.train_stop' });
let trToken = '';
let trJobId = null;

trFiles.addEventListener('change', async () => {
  const files = [...(trFiles.files || [])];
  if (!files.length) return;
  const fd = new FormData();
  files.forEach((f) => fd.append('files', f, f.name));
  if (trToken) fd.append('token', trToken);
  trFileInfo.textContent = t('lib.uploading', 0);
  try {
    const res = await api.upload('/api/cover/train/files', fd);
    trToken = res.token;
    trFileInfo.textContent = t('cover.train_files_n', res.files.length, fmtBytes(res.files.reduce((a, f) => a + f.size, 0)));
  } catch (err) { trFileInfo.textContent = ''; toast(errorText(err), true); }
  trFiles.value = '';
});

async function followTraining(job, name) {
  trJobId = job.id;
  if (folds.train && !folds.train.open) { folds.train.dataset.auto = '1'; folds.train.open = true; }   // show the progress
  trStart.disabled = true;
  trStop.classList.remove('hidden');
  const timer = setInterval(async () => {
    try { trLoss.replaceChildren(lossChart(await api.get(`/api/cover/models/${encodeURIComponent(name)}/loss`), t('cover.loss_title', name))); } catch { /* ignore */ }
  }, 15000);
  const fin = await trJob.follow(job);
  clearInterval(timer);
  trJobId = null;
  trStart.disabled = false;
  trStop.classList.add('hidden');
  if (fin.status === 'succeeded') { toast(t('cover.train_done', name)); trToken = ''; trFileInfo.textContent = ''; showLoss(name); }
  await loadStatus();
}

trStart.addEventListener('click', async () => {
  const name = trName.value.trim();
  if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,59}$/.test(name)) { toast(t('err.invalid_model_name'), true); return; }
  const body = { name, token: trToken, paths: trPaths.value.split('\n').map((s) => s.trim()).filter(Boolean),
    epochs: Number(trEpochs.value), batch_size: Number(trBatch.value), save_every: Number(trSave.value), sample_rate: Number(trRate.value) };
  if (((status && status.models) || []).some((m) => m.name.toLowerCase() === name.toLowerCase())) {
    if (!(await confirmDialog(t('cover.train_overwrite', name), t('cover.train_start')))) return;
    body.overwrite = true;
  }
  try { const res = await api.post('/api/cover/train', body); followTraining(res.job, name); }
  catch (err) { toast(errorText(err), true); }
});
trStop.addEventListener('click', async () => {
  if (!trJobId || !(await confirmDialog(t('cover.train_stop_confirm'), t('cover.train_stop')))) return;
  try { await api.post(`/api/jobs/${trJobId}/cancel`); } catch (err) { toast(errorText(err), true); }
});

function sectionTrain() {
  return foldPanel('train', t('cover.train'), null,
    el('p', { class: 'muted small' }, t('cover.train_hint')),
    field(t('cover.train_name'), trName, t('cover.train_name_hint')),
    field(t('cover.train_files'), el('span', { class: 'row' }, trFiles, trFileInfo)),
    field(t('cover.train_paths'), trPaths),
    el('div', { class: 'row' }, el('span', {}, t('cover.train_epochs')), trEpochs, el('span', {}, t('cover.train_batch')), trBatch,
      el('span', {}, t('cover.train_save')), trSave, el('span', {}, t('cover.train_rate')), trRate),
    el('div', { class: 'row', style: 'margin-top:10px' }, trStart, trStop,
      el('button', { class: 'btn small', onclick: async () => {
        try { const res = await api.post('/api/cover/train/cleanup'); toast(t('cover.cleaned', fmtBytes(res.freed))); }
        catch (err) { toast(errorText(err), true); }
      } }, t('cover.train_cleanup'))),
    trJob.el, trLoss);
}

// ------------------------------------------------------------------ status / page
const banner = el('div', { class: 'banner warn hidden' });
async function loadStatus() {
  try { status = await api.get('/api/cover/status'); } catch (err) { toast(errorText(err), true); return; }
  const a = status.applio || {};
  banner.textContent = a.ready ? '' : t('cover.applio_missing', (a.missing || []).join(', '));
  banner.classList.toggle('hidden', !!a.ready);
  const keep = songId ? readForm() : null;
  translateOptions();
  // no song yet: show the defaults so every number box has a value
  writeForm(keep || status.defaults);
  renderModels();
  updateVis();
  if (status.training && !trJobId) followTraining(status.training, (status.training.title || '').replace(/^train: /, ''));
}

function build() {
  page.replaceChildren(banner,
    el('div', { class: 'cv-grid' },
      el('div', { class: 'cv-col' }, sectionSong(), sectionVoice(), sectionMix()),
      el('div', { class: 'cv-col' },
        el('div', { class: 'panel' }, el('h3', {}, t('cover.versions')), el('p', { class: 'muted small' }, t('cover.versions_hint')), versionsBox),
        sectionModels(), sectionTrain())));
}

let built = false;
function ensureBuilt() {
  if (built) return;
  built = true;
  rebuild();
}
function rebuild() {
  build();
  translateOptions();
  applyTranslations(page);
  fillSongs();
  renderMasks(); renderVsegs(); renderVersions(); renderModels(); updateMaskVis();
}

bus.addEventListener('songs', () => { if (built) fillSongs(); });
bus.addEventListener('open-workspace', (e) => {
  if (e.detail.page !== 'cover') return;
  goto('cover');
  ensureBuilt();
  loadStatus().then(() => openSong(e.detail.songId));
});
onLanguageChange(() => {
  if (!built) return;
  const p = songId ? readForm() : null;
  rebuild();
  if (p) writeForm(p);
  updateSongInfo();
  runJob.hide();
  loadStatus();
});

registerPage('cover', {
  onShow() {
    const first = !built;
    ensureBuilt();
    loadStatus().then(() => {
      if (first && !songId && state.selectedSongId && songById(state.selectedSongId)?.source) openSong(state.selectedSongId);
    });
  },
  busy: () => !!busyJob || !!trJobId,
  busyText: () => t('cover.busy'),
});
