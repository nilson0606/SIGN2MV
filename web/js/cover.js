// AI cover workspace: convert a library song with an RVC voice model, mix it,
// keep versions (each one is a render the MV workspace can use), quick remix,
// vocal sections, volume envelopes, voice models and training.
import { api } from './api.js';
import { t, errorText, onLanguageChange, applyTranslations } from './i18n.js';
import { $, el, toast, confirmDialog, fmtDate, fmtTime, fmtBytes } from './ui.js';
import { bus, registerPage, state, goto, mediaUrl, songById, reloadJobs } from './app-state.js';
import { jobBox } from './jobview.js';
import { spectrum } from './spectrum.js';

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

const modelSel = select('model', [], () => updateSummary());
const pitchCtl = slider('pitch', -24, 24, 1);
pitchCtl.el.addEventListener('input', () => updateSummary());
pitchCtl.el.addEventListener('change', () => updateSummary());
const pitchPresets = el('div', { class: 'row', style: 'gap:6px' },
  ...[[0, 'cover.pitch_p0'], [-12, 'cover.pitch_m12'], [12, 'cover.pitch_p12']].map(([v, k]) =>
    el('button', { class: 'btn small', onclick: () => { pitchCtl.set(v); changed(); updateSummary(); } }, t(k))));
const sepSel = select('sep_model', [['demucs', ''], ['bs_roformer', ''], ['mel_roformer', '']]);
const vmodeSel = select('vocal_mode', [['full', ''], ['lead_keep_backing', ''], ['lead_keep_backing_x2', '']], () => updateVis());
const refineSel = select('bgm_refine', [['none', ''], ['second_pass', '']]);
// old 卡拉OK（拆主唱）模型: aufr33/viperx (default) or becruily (downloaded by hand)
const karaokeSel = select('karaoke_model', [['aufr33', ''], ['becruily', '']], () => updateVis());
const karaokeNote = el('p', { class: 'small hidden' });
const backingCtl = check('backing_on', 'cover.backing_on', () => updateVis());
const rvc = {
  protect: slider('rvc.protect', 0, 0.5, 0.01), index_rate: slider('rvc.index_rate', 0, 1, 0.01),
  envelope: slider('rvc.envelope', 0, 1, 0.01), f0: select('rvc.f0', [['rmvpe', ''], ['fcpe', ''], ['crepe', '']]),
  autotune: check('rvc.autotune', 'cover.autotune', () => updateVis()), autotune_strength: slider('rvc.autotune_strength', 0, 1, 0.01),
  clean: check('rvc.clean', 'cover.clean', () => updateVis()), clean_strength: slider('rvc.clean_strength', 0, 1, 0.01),
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
    autotune: check(`${p}.autotune`, 'cover.autotune', () => updateVis()), autotune_strength: slider(`${p}.autotune_strength`, 0, 1, 0.01),
    clean: check(`${p}.clean`, 'cover.clean', () => updateVis()), clean_strength: slider(`${p}.clean_strength`, 0, 1, 0.01),
  };
  c.box = el('div', { class: 'cv-side' });
  c.render = () => c.box.replaceChildren(el('div', { class: 'row', style: 'align-items:center' }, el('h4', { class: 'grow', style: 'margin:0' }, t(`cover.mf_${side}`)),
    el('button', { class: 'btn small', onclick: () => {
      const d = (status && status.defaults && status.defaults.rvc) || {};
      ['protect', 'index_rate', 'envelope', 'f0', 'autotune', 'autotune_strength', 'clean', 'clean_strength'].forEach((k) => { if (d[k] !== undefined) c[k].set(d[k]); });
      c.pitch.set(side === 'male' ? -12 : 0); c.vol.set(1); c.keep.set(false); updateVis(); changed();
    } }, t('cover.restore_defaults'))), c.keep.el,
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
const specCanvas = spectrum(versionsBox);   // old 頻譜動畫 while a version plays
const maskList = el('div', { class: 'list' });
const vsegList = el('div', { class: 'list' });

// key: the value as words, preview in the original's player from the same second (old 試聽升降後 / 原調)
const keyBadge = el('span', { class: 'cv-keybadge' });
const keyOrigBtn = el('button', { class: 'btn small', onclick: () => keyListen(false) });
const keyNow = el('span', { class: 'muted small' });
function keyWords(k) { return k ? t(k > 0 ? 'cover.key_up' : 'cover.key_down', Math.abs(k)) : t('cover.key_orig'); }
function updateKeyUi() {
  const k = keyCtl.get();
  keyBadge.textContent = keyWords(k);
  keyBadge.classList.toggle('on', !!k);
  keyBtn.textContent = k ? t('cover.key_preview_n', keyWords(k)) : t('cover.key_preview');
  keyBtn.disabled = !k || (status && status.rubberband === false);
  keyOrigBtn.textContent = t('cover.key_listen_orig');
  keyCtl.el.querySelectorAll('input').forEach((i) => { i.disabled = !!(status && status.rubberband === false); });
  updateSummary();
}
keyCtl.el.addEventListener('input', updateKeyUi);
keyCtl.el.addEventListener('change', updateKeyUi);

function sectionSong() {
  return el('div', { class: 'panel' },
    el('div', { class: 'row' }, el('h2', { style: 'margin:0' }, t('nav.cover')), songSel),
    songInfo,
    el('div', { class: 'track' }, el('span', {}, t('track.mix')), origPlayer),
    el('div', { class: 'section' },
      el('div', { class: 'row', style: 'align-items:center' }, el('span', {}, t('cover.key')), keyBadge),
      field('', keyCtl, t('cover.key_hint')),
      el('div', { class: 'row' }, keyBtn, keyOrigBtn,
        el('button', { class: 'btn small', onclick: () => { keyCtl.set(0); updateKeyUi(); changed(); } }, t('cover.key_reset')), keyNow),
      rubberNote));
}
const rubberNote = el('p', { class: 'small cv-warn hidden' });

const mfActiveNote = el('p', { class: 'small cv-note hidden' });
const mfStatus = el('span', { class: 'cv-mfstatus hidden' });
const mfCapNote = el('p', { class: 'small cv-warn hidden' });
const mfKeepWarn = el('p', { class: 'small cv-warn hidden' });
const backingHint = el('p', { class: 'muted small' });
const sepStatus = el('p', { class: 'small' });
let mfDetails = null;
function sectionVoice() {
  return el('div', { class: 'panel' },
    el('h3', {}, t('cover.voice')),
    mfActiveNote,
    field(t('cover.model'), modelSel), field(t('cover.pitch'), pitchCtl, t('cover.pitch_hint')), pitchPresets,
    details(t('cover.rvc_tune'),
      el('div', { class: 'row' }, el('button', { class: 'btn small', onclick: () => {
        const d = (status && status.defaults && status.defaults.rvc) || {};
        Object.entries(rvc).forEach(([k, c]) => { if (d[k] !== undefined) c.set(d[k]); });
        updateVis(); changed();
      } }, t('cover.restore_defaults'))),
      field(t('cover.protect'), rvc.protect, t('cover.protect_hint')),
      field(t('cover.index_rate'), rvc.index_rate, t('cover.index_hint')),
      field(t('cover.envelope'), rvc.envelope, t('cover.envelope_hint')),
      field(t('cover.f0'), rvc.f0),
      el('div', { class: 'row' }, rvc.autotune.el, rvc.autotune_strength.el),
      el('div', { class: 'row' }, rvc.clean.el, rvc.clean_strength.el)),
    details(t('cover.separation'),
      field(t('sep.model'), sepSel), field(t('cover.vocal_mode'), vmodeSel), field(t('cover.karaoke_model'), karaokeSel), karaokeNote,
      field(t('cover.bgm_refine'), refineSel),
      el('div', { class: 'cv-backing' }, backingCtl.el), backingHint, sepStatus, el('p', { class: 'muted small' }, t('cover.sep_hint'))),
    mfDetails = details(t('cover.mf'),
      el('p', { class: 'muted small' }, t('cover.mf_hint')),
      el('div', { class: 'row' }, mfOn.el, el('span', { class: 'muted' }, t('cover.mf_sep')), mfSep.el),
      el('p', { class: 'muted small cv-sucial-note' }, t('cover.sucial_note')), mfCapNote, mfKeepWarn,
      el('div', { class: 'cv-sides' }, (male.render(), male.box), (female.render(), female.box))));
}

let masksDetails = null;
let vsegsDetails = null;
// "這次會用" (what this run will use) above the button; the key highlighted when the song is shifted
const runSummary = el('div', { class: 'cv-summary' });
const freshBox = el('input', { type: 'checkbox', onchange: () => updateSummary() });
const freshCtl = el('label', { class: 'check small', title: '' }, freshBox, el('span', { 'data-i18n': 'cover.fresh_sep' }));
function sg(n) { return `${n > 0 ? '+' : ''}${n}`; }
function updateSummary() {
  if (!runSummary.isConnected && !songId) return;
  const k = keyCtl.get();
  const pitch = pitchCtl.get();
  const keyTxt = k ? t('cover.sum_key', k > 0 ? t('cover.up') : t('cover.down'), Math.abs(k)) : t('cover.sum_key0');
  const parts = [el('b', {}, t('cover.sum_label'))];
  if (mfOn.get()) {
    const side = (c) => (c.keep.get() ? t('cover.mf_keep_short') : `${(c.model.el.selectedOptions[0] || {}).textContent || c.model.get()}（${sg(c.pitch.get())}）`);
    parts.push(el('span', {}, t('cover.sum_mf', side(male), side(female))));
    if (k) parts.push('｜', el('span', {}, t('cover.sum_voice_key', sg(k))));
  } else {
    const opt = modelSel.el.selectedOptions[0];
    const model = opt ? opt.textContent.trim() : '—';
    const pName = pitch === -12 ? t('cover.pn_f2m') : pitch === 12 ? t('cover.pn_m2f') : pitch === 0 ? t('cover.pn_orig') : '';
    const voice = k ? t('cover.sum_voice_k', sg(pitch), pName, sg(k), sg(pitch + k)) : t('cover.sum_voice', sg(pitch), pName);
    parts.push(el('span', {}, `🎤 ${model}`), '｜', el('span', {}, voice));
  }
  parts.push('｜', el('span', { class: 'cv-sumkey' }, keyTxt));
  if (freshBox.checked) parts.push('｜', el('span', { class: 'cv-sumfresh' }, t('cover.sum_fresh')));
  parts.push(el('button', { class: 'btn small', onclick: () => { keyCtl.set(0); updateKeyUi(); changed(); } }, t('cover.key_back')));
  runSummary.replaceChildren(...parts);
  runSummary.classList.toggle('key-on', !!k);
  runSummary.classList.toggle('fresh-on', freshBox.checked);
}

function sectionMix() {
  return el('div', { class: 'panel' },
    el('div', { class: 'row', style: 'align-items:center' }, el('h3', { class: 'grow', style: 'margin:0' }, t('cover.mix')),
      ...[['cover.vol_vocal', 1.05, 0.8], ['cover.vol_golden', 0.95, 0.85], ['cover.vol_bgm', 0.85, 0.95]].map(([k, v, b]) =>
        el('button', { class: 'btn small', onclick: () => { mix.vocal_vol.set(v); mix.bgm_vol.set(b); changed(); } }, t(k)))),
    field(t('cover.vocal_vol'), mix.vocal_vol), field(t('cover.bgm_vol'), mix.bgm_vol),
    masksDetails = details(t('cover.masks'), el('p', { class: 'muted small' }, t('cover.masks_hint')), maskEditor(), maskList),
    vsegsDetails = details(t('cover.vsegs'), el('p', { class: 'muted small' }, t('cover.vsegs_hint')), vsegEditor(), vsegList),
    runSummary,
    el('div', { class: 'row', style: 'margin-top:12px;align-items:center' }, runBtn, freshCtl),
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
  s = String(s || '').trim().replace(/：/g, ':');
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
  autotune: check(null, 'cover.autotune', () => updateMaskVis()), autotune_strength: slider(null, 0, 1, 0.01),
  clean: check(null, 'cover.clean', () => updateMaskVis()), clean_strength: slider(null, 0, 1, 0.01),
  sep_on: check(null, 'cover.mask_sep_on', () => updateMaskVis()),
  sep_model: select(null, [['demucs', ''], ['bs_roformer', ''], ['mel_roformer', '']]),
  vocal_mode: select(null, [['full', ''], ['lead_keep_backing', ''], ['lead_keep_backing_x2', '']], () => updateMaskVis()),
  karaoke_model: select(null, [['aufr33', ''], ['becruily', '']]),
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
  mSepBox.replaceChildren(field(t('sep.model'), mr.sep_model), field(t('cover.vocal_mode'), mr.vocal_mode),
    field(t('cover.karaoke_model'), mr.karaoke_model), field(t('cover.bgm_refine'), mr.bgm_refine));
  mFileBox.replaceChildren(el('div', { class: 'row' }, mf_.file, mf_.info),
    field(t('cover.mask_target'), mf_.target), field(t('cover.mask_offset'), mf_.offset, t('cover.mask_offset_hint')), mf_.to_ai.el);
  mRvcWrap.replaceChildren(el('div', { class: 'cv-sub' },
    field(t('cover.model'), mr.model), field(t('cover.pitch'), mr.pitch), field(t('cover.protect'), mr.protect),
    field(t('cover.index_rate'), mr.index_rate), field(t('cover.envelope'), mr.envelope), field(t('cover.f0'), mr.f0),
    el('div', { class: 'row' }, mr.autotune.el, mr.autotune_strength.el), el('div', { class: 'row' }, mr.clean.el, mr.clean_strength.el)), mr.sep_on.el, mSepBox);
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
  mr.karaoke_model.el.closest('.cv-field')?.classList.toggle('hidden', mr.vocal_mode.get() === 'full');
  mf_.to_ai.el.classList.toggle('hidden', mf_.target.get() !== 'vocal');
  maskAdd.textContent = editingMask >= 0 ? t('cover.update') : t('cover.add');
  maskCancel.classList.toggle('hidden', editingMask < 0);
  mr.autotune_strength.el.querySelectorAll('input').forEach((i) => { i.disabled = !mr.autotune.get(); });
  mr.clean_strength.el.querySelectorAll('input').forEach((i) => { i.disabled = !mr.clean.get(); });
}
function addMask() {
  const start = mStart.get();
  let end = mEnd.get();
  // an outside clip without an end: it lasts as long as the clip (old behaviour)
  if (mMode.get() === 'file' && !(end > start) && mf_.uploaded && mf_.uploaded.duration && start >= 0) {
    end = Math.round((start + mf_.uploaded.duration) * 1000) / 1000;
    mEnd.set(end);
  }
  if (!(start >= 0) || !(end > start)) { toast(t('cover.bad_range'), true); return; }
  const m = { start, end, mode: mMode.get() };
  const rvcParams = () => ({ model: mr.model.get(), pitch: mr.pitch.get(), protect: mr.protect.get(), index_rate: mr.index_rate.get(),
    envelope: mr.envelope.get(), f0: mr.f0.get(), autotune: mr.autotune.get(), autotune_strength: mr.autotune_strength.get(),
    clean: mr.clean.get(), clean_strength: mr.clean_strength.get() });
  if (m.mode === 'rvc') {
    m.rvc = rvcParams();
    if (mr.sep_on.get()) {
      m.sep = { sep_model: mr.sep_model.get(), vocal_mode: mr.vocal_mode.get(), bgm_refine: mr.bgm_refine.get() };
      if (m.sep.vocal_mode !== 'full' && mr.karaoke_model.get() === 'becruily') m.sep.karaoke_model = 'becruily';
    }
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
  mr.autotune.set(r.autotune ?? cur.rvc.autotune); mr.autotune_strength.set(r.autotune_strength ?? cur.rvc.autotune_strength);
  mr.clean.set(r.clean ?? cur.rvc.clean); mr.clean_strength.set(r.clean_strength ?? cur.rvc.clean_strength);
  mr.sep_on.set(!!m.sep);
  if (m.sep) { mr.sep_model.set(m.sep.sep_model); mr.vocal_mode.set(m.sep.vocal_mode); mr.bgm_refine.set(m.sep.bgm_refine); mr.karaoke_model.set(m.sep.karaoke_model || 'aufr33'); }
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
// ▶ on a section: play from 1.5 s before it in the player last used (or the original)
function previewAt(start) {
  const a = lastAudio || origPlayer;
  if (!a || !a.src) { toast(t('cover.play_first'), true); return; }
  const go = () => { try { a.currentTime = Math.max(0, start - 1.5); } catch { /* ignore */ } a.play().catch(() => {}); };
  if (a.readyState >= 1) go(); else { a.addEventListener('loadedmetadata', go, { once: true }); a.load(); }
  a.scrollIntoView({ behavior: 'smooth', block: 'center' });
}
function renderMasks() {
  updateCounts();
  maskList.replaceChildren(...(masks.length ? masks.map((m, i) => el('div', { class: 'item' },
    el('button', { class: 'btn small', title: t('cover.preview_section'), onclick: () => previewAt(m.start) }, '▶'),
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
vGain.set(0.7);   // old default for a volume section
let editingVseg = -1;
const vsegAdd = el('button', { class: 'btn small primary', onclick: () => {
  const start = vStart.get(); const end = vEnd.get();
  if (!(start >= 0) || !(end > start + 0.09)) { toast(t('cover.bad_range'), true); return; }
  const seg = { track: vTrack.get(), start, end, gain: vGain.get() };
  if (editingVseg >= 0) vsegs[editingVseg] = seg; else vsegs.push(seg);
  editingVseg = -1;
  vsegs.sort((a, b) => a.start - b.start);
  renderVsegs(); changed();
} });
const vsegCancel = el('button', { class: 'btn small hidden', onclick: () => { editingVseg = -1; renderVsegs(); } });
function vsegEditor() {
  return el('div', { class: 'cv-editor' },
    el('div', { class: 'row' }, el('span', {}, t('cover.start')), vStart.el, el('span', {}, t('cover.end')), vEnd.el),
    field(t('cover.vseg_track'), vTrack), field(t('cover.vseg_gain'), vGain),
    el('div', { class: 'row' }, vsegAdd, vsegCancel,
      el('button', { class: 'btn small', onclick: () => { vsegs = []; editingVseg = -1; renderVsegs(); changed(); } }, t('cover.vseg_reset'))));
}
function renderVsegs() {
  updateCounts();
  vsegAdd.textContent = editingVseg >= 0 ? t('cover.update') : t('cover.add');
  vsegCancel.textContent = t('common.cancel');
  vsegCancel.classList.toggle('hidden', editingVseg < 0);
  vsegList.replaceChildren(...(vsegs.length ? vsegs.map((s, i) => el('div', { class: 'item' + (i === editingVseg ? ' selected' : '') },
    el('button', { class: 'btn small', title: t('cover.preview_section'), onclick: () => previewAt(s.start) }, '▶'),
    el('div', { class: 'grow' }, `${fmtTime(s.start)} – ${fmtTime(s.end)} · ${t(`cover.vseg.${s.track}`)} · ${pctText(s.gain)}`),
    el('button', { class: 'btn small', title: t('cover.edit'), onclick: () => {
      editingVseg = i; vStart.set(s.start); vEnd.set(s.end); vTrack.set(s.track); vGain.set(s.gain); renderVsegs();
    } }, '✏️'),
    el('button', { class: 'btn small', onclick: () => { vsegs.splice(i, 1); editingVseg = -1; renderVsegs(); changed(); } }, t('common.delete'))))
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
  karaokeSel.set(p.karaoke_model || 'aufr33');   // only stored when it is becruily
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
  [karaokeSel.el, mr.karaoke_model.el].forEach((s) => { const b = [...s.options].find((o) => o.value === 'becruily'); if (b) b.disabled = !seps.becruily; });
  karaokeSel.el.closest('.cv-field')?.classList.toggle('hidden', mf || vmodeSel.get() === 'full');
  mr.karaoke_model.el.closest('.cv-field')?.classList.toggle('hidden', mr.vocal_mode.get() === 'full');
  const becPath = status && status.becruily ? status.becruily.path : '';
  const becUrl = status && status.becruily ? status.becruily.url : '';
  karaokeNote.replaceChildren(seps.becruily ? '' : t('cover.becruily_missing', becPath),
    !seps.becruily && becUrl ? el('a', { href: becUrl, target: '_blank', rel: 'noopener', style: 'margin-left:6px' }, t('cover.becruily_link')) : '');
  karaokeNote.className = `small muted ${seps.becruily || mf || vmodeSel.get() === 'full' ? 'hidden' : ''}`;
  // strength boxes only count when their switch is on
  [rvc, male, female].forEach((c) => {
    c.autotune_strength.el.querySelectorAll('input').forEach((i) => { i.disabled = !c.autotune.get(); });
    c.clean_strength.el.querySelectorAll('input').forEach((i) => { i.disabled = !c.clean.get(); });
  });
  // separation availability (old "分離模型就緒／不可用")
  const missing = Object.entries(seps).filter(([k, ok]) => ok === false && k !== 'becruily').map(([k]) => t(`sep.name.${k}`));
  sepStatus.textContent = missing.length ? t('cover.sep_missing', missing.join('、')) : t('cover.sep_ready');
  sepStatus.className = `small ${missing.length ? 'cv-warn' : 'cv-ok'}`;
  // what the original backing does in this mode
  const vm = vmodeSel.get();
  backingHint.textContent = mf ? '' : (vm === 'full' ? t('cover.backing_hint_full') : (backingCtl.get() ? t('cover.backing_hint_on') : t('cover.backing_hint_off')));
  // duet: status chip, note above the model, both-kept warning, model availability
  mfActiveNote.classList.toggle('hidden', !mf);
  mfActiveNote.textContent = t('cover.mf_active_note');
  const side = (c) => (c.keep.get() ? t('cover.mf_keep_short') : `${c.model.get()}（${sg(c.pitch.get())}）`);
  mfStatus.textContent = mf ? t('cover.mf_status', side(male), side(female)) : '';
  mfStatus.classList.toggle('hidden', !mf);
  if (mfDetails && !mfStatus.isConnected) mfDetails.querySelector('summary').append(' ', mfStatus);
  mfKeepWarn.textContent = t('cover.mf_both_kept');
  mfKeepWarn.classList.toggle('hidden', !(mf && male.keep.get() && female.keep.get()));
  const mfAvail = ['aufr33', 'sucial'].filter((k) => seps[k] !== false);
  mfCapNote.textContent = t('cover.mf_unavailable');
  mfCapNote.classList.toggle('hidden', mfAvail.length > 0);
  // volume sections: "original backing" only when this mode keeps a backing track
  [...vTrack.el.options].forEach((o) => { if (o.value === 'backing') o.disabled = mf || vm === 'full' || !backingCtl.get(); });
  rubberNote.textContent = t('cover.no_rubberband');
  rubberNote.classList.toggle('hidden', !(status && status.rubberband === false));
  updateKeyUi();
  updateCounts();
}
function updateCounts() {
  const setCount = (d, n) => { if (!d) return; const sm = d.querySelector('summary'); sm.dataset.count = n ? t('cover.n_sections', n) : ''; };
  setCount(masksDetails, masks.length);
  setCount(vsegsDetails, vsegs.length);
}

function translateOptions() {
  const lab = (sel, prefix) => [...sel.options].forEach((o) => { o.textContent = t(`${prefix}${o.value}`); });
  [sepSel.el, mr.sep_model.el].forEach((s) => lab(s, 'sep.model.'));
  [vmodeSel.el, mr.vocal_mode.el].forEach((s) => lab(s, 'cover.vmode.'));
  [karaokeSel.el, mr.karaoke_model.el].forEach((s) => lab(s, 'cover.karaoke.'));
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

async function keyPreview() { return keyListen(true); }
// switch the original's player between the key-changed preview and the original, same second
async function keyListen(shifted) {
  if (!songId) { toast(t('common.select_song'), true); return; }
  const song = songById(songId);
  let url = song && song.source ? mediaUrl(songId, song.source.audio) : '';
  if (shifted) {
    keyBtn.disabled = true;
    const old = keyBtn.textContent;
    keyBtn.textContent = t('cover.key_making');
    try {
      const res = await api.post(`/api/cover/songs/${songId}/key_preview`, { key: keyCtl.get() });
      url = mediaUrl(songId, res.path);
    } catch (err) { toast(errorText(err), true); keyBtn.textContent = old; keyBtn.disabled = false; return; }
    keyBtn.textContent = old;
    keyBtn.disabled = false;
  }
  if (!url) return;
  switchSource(origPlayer, url, [], null);
  origPlayer.play().catch(() => {});
  keyNow.textContent = t('cover.key_now', shifted ? keyWords(keyCtl.get()) : t('cover.key_orig'));
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
    v.stats ? el('div', { class: 'small', title: statsTitle(v.stats) }, statsText(v.stats)) : null,
    el('div', { class: 'row' },
      el('button', { class: 'btn primary', onclick: () => {
        const box = item();
        if (!box) return;
        box.scrollIntoView({ behavior: 'smooth', block: 'center' });
        const a = box.querySelector('audio');
        if (a) a.play().catch(() => {});
      } }, t('cover.done_play')),
      el('button', { class: 'btn', onclick: () => item()?.scrollIntoView({ behavior: 'smooth', block: 'center' }) }, t('cover.done_show')),
      ...mvButtons(v, 'btn')));
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
    remixCard.querySelector('.cv-vjob').replaceChildren(el('div', { class: 'small cv-note' }, t('cover.busy_track')), box.el);
    remixCard.querySelectorAll('button').forEach((b) => { b.disabled = true; });
  }
  const fin = await box.follow(job);
  busyJob = null;
  runBtn.disabled = false;
  reloadJobs();
  if (fin.status === 'succeeded') { toast(t(remixCard ? 'cover.remix_toast' : 'cover.done')); flashTitle(t('cover.tab_done')); }
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

// the old "🎉 製作完成！" in the tab title while the window is in the background (up to ~3 minutes)
function flashTitle(text) {
  if (!document.hidden) return;
  const orig = document.title;
  let n = 0;
  const timer = setInterval(() => {
    document.title = n % 2 ? orig : text;
    n += 1;
    if (!document.hidden || n > 180) { clearInterval(timer); document.title = orig; }
  }, 1000);
}

async function runCover() {
  if (!songId) { toast(t('common.select_song'), true); return; }
  try {
    const body = { params: readForm() };
    if (freshBox.checked) body.fresh = true;
    const res = await api.post(`/api/cover/songs/${songId}/run`, body);
    freshBox.checked = false;   // like the old switch: only for this run
    updateSummary();
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

// how long the last make / remix took and where the voice was converted
// Quick MV (audio-reactive card) or full MV (MV workspace) with this version as the audio
function mvButtons(v, cls) {
  const open = (mode) => () => {
    bus.dispatchEvent(new CustomEvent('mv-open', { detail: { songId, renderId: v.render_id, mode } }));
    goto('mv');
  };
  return [
    el('button', { class: `${cls} primary`, title: t('cover.quick_mv_hint'), onclick: open('quick') }, t('cover.quick_mv')),
    el('button', { class: cls, title: t('cover.full_mv_hint'), onclick: open('full') }, t('cover.full_mv')),
  ];
}
function dur(sec) {
  const s = Math.round(sec);
  return s >= 60 ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}` : `${s} ${t('common.seconds')}`;
}
// Hover text: the mix broken down by step
function statsTitle(st) {
  const m = (st && st.mix_steps) || {};
  return Object.entries(m).filter(([k]) => k !== 'mix_start' || m[k] >= 1)
    .map(([k, v]) => `${k === 'mix_start' ? t('stage.mix') : t(`stage.${k}`)}: ${dur(v)}`).join('\n');
}
function statsText(st) {
  if (!st || st.total_s == null) return '';
  const parts = [];
  if (st.separate_s >= 1) parts.push(`${t('cover.st_separate')} ${dur(st.separate_s)}`);
  if (st.prepare_s >= 1) parts.push(`${t('cover.st_prepare')} ${dur(st.prepare_s)}`);
  let rvc = st.rvc_device ? `${t('cover.st_rvc')} ${dur(st.rvc_s)}` : t('cover.st_rvc_cached');
  if (st.rvc_device && st.rvc_load_s != null && st.rvc_convert_s != null) {
    rvc += `［${t('cover.st_rvc_load')} ${dur(st.rvc_load_s)}＋${t('cover.st_rvc_convert')} ${dur(st.rvc_convert_s)}］`;
  }
  parts.push(rvc);
  parts.push(`${t('cover.st_mix')} ${dur(st.mix_s)}`);
  let text = `${t('cover.st_total', dur(st.total_s))}（${parts.join(' · ')}）`;
  if (st.rvc_device) text += ` · ${st.rvc_device.startsWith('cuda') ? `GPU ${st.rvc_gpu || ''}`.trim() : 'CPU'}`;
  return text;
}

// ------------------------------------------------------------------ versions
// batch bar (old 批次刪除): select all (with the half state), count, delete selected
const vSelAll = el('input', { type: 'checkbox', onchange: () => { versionsBox.querySelectorAll('input.cv-pick').forEach((c) => { c.checked = vSelAll.checked; }); updateBatch(); } });
const vSelCount = el('span', { class: 'muted small' });
const vDelSel = el('button', { class: 'btn small danger', onclick: async () => {
  const ids = [...versionsBox.querySelectorAll('input.cv-pick:checked')].map((c) => c.dataset.vid);
  if (!ids.length) return;
  const used = ((songState && songState.versions) || []).filter((v) => ids.includes(v.id)).flatMap((v) => v.mv_projects || []);
  if (!(await confirmDialog(t('cover.delete_n_confirm', ids.length) + mvUseWarning(used), t('common.delete')))) return;
  versionsBox.querySelectorAll('audio, video').forEach((a) => { a.pause(); a.removeAttribute('src'); a.load(); });   // release files
  try {
    const res = await api.post(`/api/cover/songs/${songId}/versions/delete`, { ids });
    toast(t('cover.deleted_n', res.deleted, fmtBytes(res.freed || 0)));
  } catch (err) { toast(errorText(err), true); }
  await openSong(songId);
  bus.dispatchEvent(new Event('renders-changed'));
} });
// old 🧹 清理中間檔: list what is unused first (kind, count, size), delete after confirming
const cleanBtn = el('button', { class: 'btn small', 'data-i18n': 'cover.cleanup', onclick: async () => {
  if (!songId) return;
  let res;
  try { res = await api.get(`/api/cover/songs/${songId}/cleanup`); } catch (err) { toast(errorText(err), true); return; }
  const kinds = Object.entries(res.kinds || {});
  if (!kinds.length) { toast(t('cover.cleanup_nothing')); return; }
  const lines = kinds.map(([k, v]) => `• ${t(`cover.garbage.${k}`)}：${t('cover.n_files', v.files)}，${fmtBytes(v.bytes)}`);
  if (!(await confirmDialog(`${t('cover.cleanup_confirm', fmtBytes(res.total))}\n\n${lines.join('\n')}`, t('cover.cleanup')))) return;
  try {
    const done = await api.post(`/api/cover/songs/${songId}/cleanup`, {});
    const disks = (done.disks || []).map((d) => t('cover.disk_free', d.drive, fmtBytes(d.free))).join('　');
    toast(t('cover.cleaned', fmtBytes(done.freed)) + (disks ? `\n${disks}` : ''), false, 8000);
    bus.dispatchEvent(new CustomEvent('storage-changed'));
  } catch (err) { toast(errorText(err), true); }
} });
const vBatch = el('div', { class: 'row cv-batch', style: 'align-items:center;gap:8px' },
  el('label', { class: 'check small' }, vSelAll, el('span', { 'data-i18n': 'qmv.select_all' })), vSelCount, vDelSel);
// MV projects that play this version: deleting it leaves them without music (finished videos are kept)
function mvUseWarning(projects) {
  const names = [...new Set((projects || []).map((p) => `「${p.title}」`))];
  return names.length ? '\n\n' + t('cover.delete_used_by_mv', names.join('、')) : '';
}
function updateBatch() {
  const all = [...versionsBox.querySelectorAll('input.cv-pick')];
  const n = all.filter((c) => c.checked).length;
  vSelAll.checked = n > 0 && n === all.length;
  vSelAll.indeterminate = n > 0 && n < all.length;
  vSelCount.textContent = n ? t('cover.selected_n', n) : '';
  vDelSel.textContent = t('qmv.delete_selected');
  vDelSel.disabled = !n;
  vBatch.classList.toggle('hidden', all.length < 2);
}
// every song's versions in one list (old 成品庫 table): search, play, size, open that song
const allSearch = el('input', { type: 'search', style: 'min-width:220px', oninput: () => renderAll() });
const allList = el('div', { class: 'list' });
const allInfo = el('div', { class: 'muted small' });
let allData = null;
const allBox = el('details', { class: 'cv-details cv-all' },
  el('summary', { 'data-i18n': 'cover.all_versions' }),
  el('div', { class: 'cv-body' }, el('div', { class: 'row', style: 'align-items:center' }, allSearch, allInfo), allList));
allBox.addEventListener('toggle', () => { if (allBox.open) loadAll(); });
async function loadAll() {
  try { allData = await api.get('/api/cover/versions'); } catch (err) { toast(errorText(err), true); return; }
  renderAll();
}
function renderAll() {
  allSearch.placeholder = t('qmv.search');
  if (!allData) return;
  const q = allSearch.value.trim().toLowerCase();
  const items = allData.items.filter((v) => !q || [v.song_title, v.title, v.label].some((x) => (x || '').toLowerCase().includes(q)));
  allInfo.textContent = t('cover.all_info', allData.items.length, fmtBytes(allData.bytes || 0));
  if (!items.length) { allList.replaceChildren(el('div', { class: 'empty' }, t(q ? 'qmv.no_match' : 'cover.no_versions'))); return; }
  allList.replaceChildren(...items.map((v) => {
    const holder = el('div');
    const meta = [v.label, v.format, v.bytes ? fmtBytes(v.bytes) : '', v.duration ? fmtTime(v.duration) : '', fmtDate(v.updated_at || v.created_at)]
      .filter(Boolean).join(' · ');
    return el('div', { class: 'item', style: 'display:block' },
      el('div', { class: 'row', style: 'align-items:center' },
        el('div', { class: 'grow', style: 'white-space:normal' }, el('b', {}, v.song_title), ' — ', v.title || v.label,
          el('div', { class: 'muted small' }, meta)),
        v.audio ? el('button', { class: 'btn small primary', onclick: () => {
          if (holder.firstChild) { holder.replaceChildren(); return; }
          const a = el('audio', { src: mediaUrl(v.song_id, v.audio), controls: true, preload: 'none', style: 'width:100%' });
          holder.replaceChildren(a);
          a.play().catch(() => {});
        } }, '▶') : null,
        el('button', { class: 'btn small', onclick: () => { openSong(v.song_id); window.scrollTo({ top: 0, behavior: 'smooth' }); } }, t('cover.open_song'))),
      holder);
  }));
}
function renderVersions(highlight) {
  const vs = (songState && songState.versions) || [];
  if (!songId) { versionsBox.replaceChildren(el('div', { class: 'empty' }, t('cover.pick_song'))); updateBatch(); return; }
  if (!vs.length) { versionsBox.replaceChildren(el('div', { class: 'empty' }, t('cover.no_versions'))); updateBatch(); return; }
  versionsBox.replaceChildren(...vs.map((v) => versionItem(v, v.id === highlight)));
  if (allBox.open) loadAll();
  vSelAll.checked = false;
  updateBatch();
}
async function openFolder(rel) {
  try { await api.post('/api/open-folder', { song_id: songId, rel }); toast(t('common.opened_folder')); }
  catch (err) { toast(errorText(err), true); }
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
  const now = player.parentElement && player.parentElement.querySelector('.cv-now');
  if (now && active) now.textContent = t('cover.now_playing', active.textContent);
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
  const mvBox = el('div', {});
  const mvRow = (v.mvs || []).length ? el('div', { class: 'cv-mvbanner' }, ...(v.mvs || []).map((m) =>
    el('button', { class: 'btn small primary', onclick: () => {
      if (mvBox.firstChild) { mvBox.replaceChildren(); return; }
      const vid = el('video', { src: mediaUrl(songId, m.path), controls: true, playsinline: true, style: 'width:100%;aspect-ratio:16/9;background:#000;border-radius:8px;margin-top:6px' });
      mvBox.replaceChildren(vid);
      vid.play().catch(() => {});
    } }, t(m.kind === 'quick' ? 'cover.watch_quick_mv' : 'cover.watch_full_mv', m.title || '')))) : null;
  const pick = el('input', { type: 'checkbox', class: 'cv-pick', 'data-vid': v.id, onchange: () => updateBatch() });
  const box = el('div', { class: 'cv-version' + (hi ? ' selected cv-new' : ''), dataset: { vid: v.id } },
    el('div', { class: 'row' },
      pick,
      el('b', { class: 'grow' }, v.title),
      el('span', { class: 'muted small' }, [fmtDate(v.updated_at || v.created_at), v.duration ? fmtTime(v.duration) : '',
        v.format || '', v.bytes ? fmtBytes(v.bytes) : ''].filter(Boolean).join(' · '))),
    el('div', { class: 'muted small' }, v.label + (v.source_version ? ` · ${t('cover.remixed')}` : '')),
    v.stats ? el('div', { class: 'muted small', title: statsTitle(v.stats) }, statsText(v.stats)) : null,
    abRow,
    player ? el('div', {}, player, el('div', { class: 'muted small cv-now' })) : el('div', { class: 'muted' }, t('cover.audio_missing')),
    mvRow, mvBox,
    el('div', { class: 'row' },
      el('button', { class: 'btn small', title: t('cover.use_settings_hint'), onclick: () => { writeForm(v.params); changed(); toast(t('cover.settings_loaded')); } }, t('cover.use_settings')),
      el('button', { class: 'btn small', title: t('cover.remix_hint'), onclick: () => remix(v, false) }, t('cover.remix')),
      el('button', { class: 'btn small', onclick: () => remix(v, true) }, t('cover.remix_new')),
      ...mvButtons(v, 'btn small'),
      src ? el('a', { class: 'btn small', href: src, download: `${v.title}.${(v.format || 'mp3').toLowerCase()}` }, t('common.download')) : null,
      v.audio ? el('button', { class: 'btn small', title: t('common.open_folder'), onclick: () => openFolder(v.audio) }, '📂') : null,
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
        if (!(await confirmDialog(t('cover.delete_confirm', v.title) + mvUseWarning(v.mv_projects), t('common.delete')))) return;
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
const importPath = el('input', { type: 'text', style: 'flex:1;min-width:220px', placeholder: 'D:\\AI_COVER_MV\\models' });
const upName = el('input', { type: 'text', placeholder: 'My_Voice', style: 'width:140px' });
const importName = el('input', { type: 'text', style: 'width:150px', 'data-i18n-placeholder': 'cover.import_name' });
const upPth = el('input', { type: 'file', accept: '.pth' });
const upIdx = el('input', { type: 'file', accept: '.index' });

// ---------------- convergence (the old "收斂曲線與中間版本" panel)
// mel loss: thin line per epoch, thick 5-epoch average, kept versions dashed, values on hover
function lossChart(data) {
  const ep = data.epoch || []; const mel = data.mel || [];
  if (!ep.length || !mel.some((v) => v != null)) return el('div', { class: 'muted small cv-loss-empty' }, t('cover.no_loss'));
  const W = 640; const H = 220; const L = 44; const R = 12; const T = 12; const B = 28;
  const vals = mel.filter((v) => v != null);
  let lo = Math.min(...vals); let hi = Math.max(...vals);
  const pad = (hi - lo) * 0.08 || 1; lo -= pad; hi += pad;
  const x0 = ep[0]; const x1 = Math.max(ep[ep.length - 1], data.total_epochs || 0, x0 + 1);
  const X = (e) => L + (e - x0) / (x1 - x0) * (W - L - R);
  const Y = (v) => T + (hi - v) / (hi - lo) * (H - T - B);
  const avg = mel.map((_, i) => { const w = mel.slice(Math.max(0, i - 4), i + 1).filter((v) => v != null); return w.length ? w.reduce((a, b) => a + b, 0) / w.length : null; });
  const path = (arr) => arr.map((v, i) => (v == null ? '' : `${i && arr[i - 1] != null ? 'L' : 'M'}${X(ep[i]).toFixed(1)},${Y(v).toFixed(1)}`)).join('');
  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.setAttribute('class', 'cv-chart');
  const add = (tag, attrs, text) => { const n = document.createElementNS(svgNS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); if (text != null) n.textContent = text; svg.append(n); return n; };
  for (let k = 0; k <= 4; k++) {
    const v = lo + (hi - lo) * k / 4; const y = Y(v);
    add('line', { x1: L, x2: W - R, y1: y, y2: y, stroke: '#2c3945', 'stroke-width': 0.6 });
    add('text', { x: L - 6, y: y + 3, 'text-anchor': 'end', 'font-size': 10, fill: '#94a3b8' }, v.toFixed(1));
  }
  const stepX = Math.max(1, Math.round((x1 - x0) / 6 / 10) * 10 || 10);
  for (let e = Math.ceil(x0 / stepX) * stepX; e <= x1; e += stepX) add('text', { x: X(e), y: H - 8, 'text-anchor': 'middle', 'font-size': 10, fill: '#94a3b8' }, String(e));
  (data.kept_epochs || []).forEach((e) => {
    if (e < x0 || e > x1) return;
    add('line', { x1: X(e), x2: X(e), y1: T, y2: H - B, stroke: '#a78bfa', 'stroke-dasharray': '3 3', opacity: 0.8 });
    add('text', { x: X(e), y: T + 9, 'text-anchor': 'middle', 'font-size': 9, fill: '#c4b5fd' }, String(e));
  });
  add('path', { d: path(mel), fill: 'none', stroke: '#34d399', 'stroke-width': 1, opacity: 0.35 });
  add('path', { d: path(avg), fill: 'none', stroke: '#34d399', 'stroke-width': 2.2 });
  add('text', { x: L, y: H - 8, 'font-size': 10, fill: '#64748b' }, t('cover.loss_axis'));
  mel.forEach((v, i) => {
    if (v == null) return;
    const c = add('circle', { cx: X(ep[i]).toFixed(1), cy: Y(v).toFixed(1), r: 5, fill: 'transparent' });
    const tt = document.createElementNS(svgNS, 'title');
    tt.textContent = t('cover.loss_point', ep[i], v.toFixed(2), avg[i].toFixed(2));
    c.append(tt);
  });
  return svg;
}

// trend of the last 20 epochs (old lossVerdict)
function lossVerdict(ep, mel) {
  const pts = ep.map((e, i) => [e, mel[i]]).filter((q) => q[1] != null);
  if (pts.length < 15) return { text: t('cover.loss_few'), cls: 'muted' };
  const tail = pts.slice(-20); const n = tail.length;
  const mx = tail.reduce((a, q) => a + q[0], 0) / n; const my = tail.reduce((a, q) => a + q[1], 0) / n;
  const slope = tail.reduce((a, q) => a + (q[0] - mx) * (q[1] - my), 0) / Math.max(1e-9, tail.reduce((a, q) => a + (q[0] - mx) ** 2, 0));
  if (slope < -0.03) return { text: t('cover.loss_down', slope.toFixed(3)), cls: 'cv-v-down' };
  if (slope > 0.03) return { text: t('cover.loss_up', slope.toFixed(3)), cls: 'cv-v-up' };
  return { text: t('cover.loss_flat', `${slope >= 0 ? '+' : ''}${slope.toFixed(3)}`), cls: 'cv-v-flat' };
}

const lossSel = el('select', { onchange: () => loadLoss() });
const lossBadge = el('span', { class: 'cv-live hidden' });
const lossChartBox = el('div', { class: 'cv-loss-chart' });
const lossSummary = el('div', { class: 'small' });
const epochList = el('div', { class: 'cv-epochs' });
const lossBox = el('div', { class: 'cv-loss' },
  el('div', { class: 'row', style: 'align-items:center' }, el('b', { class: 'grow' }, el('span', { 'data-i18n': 'cover.loss_panel' }), ' ', lossBadge),
    lossSel, el('button', { class: 'btn small', onclick: () => loadLoss(), 'data-i18n': 'common.refresh' })),
  lossChartBox, lossSummary, epochList, el('p', { class: 'muted small', 'data-i18n': 'cover.loss_note' }));
let lossWanted = '';

function lossModels() {
  const names = ((status && status.models) || []).map((m) => m.name);
  if (trName.dataset.training && !names.includes(trName.dataset.training)) names.unshift(trName.dataset.training);
  return names;
}
function fillLossSelect(preferred) {
  const names = lossModels();
  const keep = preferred || lossSel.value || lossWanted;
  lossSel.replaceChildren(...names.map((n) => el('option', { value: n }, n)));
  if (keep && names.includes(keep)) lossSel.value = keep;
}

function useEpoch(name, epoch) {
  fillModelSelect(modelSel.el, epoch ? `${name}__e${epoch}` : name);
  modelSel.el.dispatchEvent(new Event('change'));
  modelSel.el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  modelSel.el.classList.add('cv-flash');
  setTimeout(() => modelSel.el.classList.remove('cv-flash'), 2400);
  toast(t('cover.using_version', epoch ? `${name} · ${t('cover.epoch_n', epoch)}` : `${name} (${t('cover.final')})`));
}

function renderEpochs(name) {
  const m = ((status && status.models) || []).find((x) => x.name === name);
  if (!m) { epochList.replaceChildren(); return; }
  const row = (label, size, epoch) => el('div', { class: 'cv-epoch' },
    el('span', { class: 'grow' }, label, el('span', { class: 'muted' }, ` · ${fmtBytes(size)}`)),
    el('button', { class: 'btn small primary', onclick: () => useEpoch(name, epoch) }, t('cover.use_this_version')),
    epoch ? el('button', { class: 'btn small danger', onclick: async () => {
      if (!(await confirmDialog(t('cover.epoch_delete_confirm', name, epoch), t('common.delete')))) return;
      try { await api.del(`/api/cover/models/${encodeURIComponent(name)}/epochs/${epoch}`); await loadStatus(); } catch (err) { toast(errorText(err), true); }
    } }, '🗑') : null);
  epochList.replaceChildren(row(t('cover.final_version'), m.size, 0),
    ...[...m.epochs].sort((a, b) => b.epoch - a.epoch).map((e) => row(t('cover.epoch_n', e.epoch), e.size, e.epoch)));
}

async function loadLoss(preferred) {
  fillLossSelect(preferred);
  const name = lossSel.value;
  if (!name) { lossChartBox.replaceChildren(el('div', { class: 'muted small' }, t('cover.no_models'))); lossSummary.textContent = ''; epochList.replaceChildren(); return; }
  lossWanted = name;
  let d = { epoch: [] };
  try { d = await api.get(`/api/cover/models/${encodeURIComponent(name)}/loss`); } catch { /* keep empty */ }
  lossChartBox.replaceChildren(lossChart(d));
  lossBadge.textContent = t('cover.loss_live');
  lossBadge.classList.toggle('hidden', d.source !== 'live');
  if (d.epoch && d.epoch.length) {
    const v = lossVerdict(d.epoch, d.mel || []);
    const tail = (d.mel || []).filter((x) => x != null).slice(-5);
    const avg = tail.length ? (tail.reduce((a, b) => a + b, 0) / tail.length).toFixed(2) : '-';
    lossSummary.replaceChildren(el('span', { class: v.cls }, v.text), '　',
      t('cover.loss_now', d.epoch[d.epoch.length - 1], d.total_epochs ? ` / ${d.total_epochs}` : '', avg),
      d.partial ? el('span', { class: 'muted' }, '　' + t('cover.loss_partial')) : '');
  } else lossSummary.textContent = '';
  renderEpochs(name);
}
async function showLoss(name) {
  if (folds.train && !folds.train.open) { folds.train.dataset.auto = '1'; folds.train.open = true; }
  await loadLoss(name);
  lossBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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
    modelsList,
    el('div', { class: 'section' },
      el('div', { class: 'cv-label' }, t('cover.import_folder')),
      el('div', { class: 'row' }, importPath, importName, el('button', { class: 'btn', onclick: async () => {
        try {
          const body = { path: importPath.value };
          if (importName.value.trim()) body.name = importName.value.trim();
          const res = await api.post('/api/cover/models/import', body);
          const skipped = res.skipped.map((s) => `${s.source}: ${errorText({ code: s.reason })}`).join('\n');
          toast(t('cover.imported', res.imported.length) + (skipped ? `\n${skipped}` : ''), !res.imported.length, 9000);
          await loadStatus();
          if (res.imported.length) { importName.value = ''; useEpoch(res.imported[0], 0); }
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
          try { const res = await api.upload('/api/cover/models/upload', fd); toast(t('cover.uploaded', res.name)); await loadStatus(); useEpoch(res.name, 0); }
          catch (err) { toast(errorText(err), true); }
        } }, t('cover.upload')))));
}

// ------------------------------------------------------------------ training
const trName = el('input', { type: 'text', value: 'My_Voice_Ver1', placeholder: 'My_Voice_Ver1', style: 'width:180px' });
const trFiles = el('input', { type: 'file', multiple: true, accept: 'audio/*,video/*' });
const trFileInfo = el('span', { class: 'muted small' });
const trPaths = el('textarea', { placeholder: 'D:\\recordings\\my_voice', style: 'min-height:54px' });
const trEpochs = el('input', { type: 'number', value: 100, min: 1, max: 2000, style: 'width:90px' });
const trBatch = el('select', {}, ...[4, 8, 16].map((b) => el('option', { value: b, selected: b === 8 }, String(b))));
const trSave = el('input', { type: 'number', value: 10, min: 1, max: 500, style: 'width:80px' });
const trRate = el('select', {}, ...[32000, 40000, 48000].map((r) => el('option', { value: r, selected: r === 40000 }, `${r / 1000} kHz`)));
// the old training dashboard: 6-step pipeline, status light, Epoch / Step / best loss / progress cards
const TR_STEPS = ['train_import', 'train_slice', 'train_features', 'train_epochs', 'train_index', 'train_install'];
const trNodes = TR_STEPS.map((st, i) => el('div', { class: 'cv-step' }, el('span', { class: 'cv-step-n' }, String(i + 1)), el('span', { 'data-i18n': `cover.tstep.${i + 1}` })));
const trDot = el('span', { class: 'cv-dot' });
const trStateText = el('span', { class: 'small' });
const trCard = (key) => { const v = el('b', {}, '–'); return { v, el: el('div', { class: 'cv-card' }, el('span', { class: 'muted small', 'data-i18n': key }), v) }; };
const trCards = { epoch: trCard('cover.tcard.epoch'), step: trCard('cover.tcard.step'), loss: trCard('cover.tcard.loss'), pct: trCard('cover.tcard.pct') };
const trDash = el('div', { class: 'cv-train-dash hidden' },
  el('div', { class: 'row', style: 'align-items:center;gap:8px' }, trDot, trStateText),
  el('div', { class: 'cv-steps' }, ...trNodes),
  el('div', { class: 'cv-cards' }, ...Object.values(trCards).map((c) => c.el)));
function trUpdate(job) {
  trDash.classList.remove('hidden');
  const idx = job.stage === 'done' || job.status === 'succeeded' ? TR_STEPS.length : TR_STEPS.indexOf(job.stage);
  trNodes.forEach((n, i) => {
    n.classList.toggle('done', i < idx || job.status === 'succeeded');
    n.classList.toggle('active', i === idx && job.status === 'running');
  });
  trDot.className = `cv-dot ${job.status}`;
  trStateText.textContent = job.status === 'running' && job.stage ? `${t('jobs.status.running')} · ${t(`stage.${job.stage}`)}` : t(`jobs.status.${job.status}`);
  const m = /(\d+)\/(\d+)(?: · step (\d+))?(?: · best ([\d.]+))?/.exec(job.message || '');
  if (m) {
    trCards.epoch.v.textContent = `${m[1]} / ${m[2]}`;
    if (m[3]) trCards.step.v.textContent = m[3];
    if (m[4]) trCards.loss.v.textContent = Number(m[4]).toFixed(3);
  }
  trCards.pct.v.textContent = job.percent != null ? `${Math.round(job.percent)}%` : (job.status === 'succeeded' ? '100%' : '–');
}
const trJob = jobBox({ onUpdate: trUpdate });
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
  trName.dataset.training = name;
  Object.values(trCards).forEach((c) => { c.v.textContent = '–'; });
  if (folds.train && !folds.train.open) { folds.train.dataset.auto = '1'; folds.train.open = true; }   // show the progress
  trStart.disabled = true;
  trStop.classList.remove('hidden');
  loadLoss(name);
  const timer = setInterval(() => { if (lossSel.value === name) loadLoss(name); }, 15000);   // live curve while training
  const fin = await trJob.follow(job);
  clearInterval(timer);
  trJobId = null;
  trStart.disabled = false;
  trStop.classList.add('hidden');
  delete trName.dataset.training;
  await loadStatus();
  if (fin.status === 'succeeded') {
    toast(t('cover.train_done', name)); trToken = ''; trFileInfo.textContent = '';
    showLoss(name);
    useEpoch(name, 0);   // the new model is selected for the next cover
  }
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
    el('div', { class: 'row' }, el('button', { class: 'btn small', onclick: async () => {
      if (!songId) { toast(t('cover.pick_song'), true); return; }
      try {
        const r = await api.get(`/api/cover/songs/${songId}/train-source`);
        const lines = trPaths.value.split('\n').map((x) => x.trim()).filter(Boolean);
        if (!lines.includes(r.path)) lines.push(r.path);
        trPaths.value = lines.join('\n');
        toast(t('cover.train_from_song_done', t(`track.${r.track}`)));
      } catch (err) { toast(errorText(err), true); }
    } }, t('cover.train_from_song')), el('span', { class: 'muted small' }, t('cover.train_from_song_hint'))),
    el('div', { class: 'row' }, el('span', {}, t('cover.train_epochs')), trEpochs,
      ...[30, 100, 200].map((n) => el('button', { class: 'btn small', onclick: () => { trEpochs.value = n; } }, String(n))),
      el('span', {}, t('cover.train_batch')), trBatch,
      el('span', {}, t('cover.train_save')), trSave, el('span', {}, t('cover.train_rate')), trRate),
    el('div', { class: 'row', style: 'margin-top:10px' }, trStart, trStop,
      el('button', { class: 'btn small', onclick: async () => {
        try {
          const res = await api.post('/api/cover/train/cleanup');
          const disks = (res.disks || []).map((d) => t('cover.disk_free', d.drive, fmtBytes(d.free))).join('　');
          toast(t('cover.cleaned', fmtBytes(res.freed)) + (disks ? `\n${disks}` : ''), false, 8000);
          trJob.el.querySelector('.joblog')?.append(el('div', { class: 'jl-ok' }, `🧹 ${t('cover.cleaned', fmtBytes(res.freed))} ${disks}`));
        }
        catch (err) { toast(errorText(err), true); }
      } }, t('cover.train_cleanup'))),
    trDash, trJob.el, lossBox);
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
        el('div', { class: 'panel' }, el('div', { class: 'row', style: 'align-items:center' }, el('h3', { class: 'grow' }, t('cover.versions')), cleanBtn),
          el('p', { class: 'muted small' }, t('cover.versions_hint')), specCanvas, vBatch, versionsBox, allBox),
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
