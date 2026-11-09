// A key version changes pitch only; all song-time coordinates remain unchanged.
export function keyShift(value = 0) {
  if (!Number.isInteger(value) || value < -12 || value > 12) throw Error('Key 請選擇 −12～＋12 的整數半音。');
  return value;
}
export function keyLabel(value = 0) {
  const shift = keyShift(value);
  return shift ? `${shift > 0 ? '升' : '降'} ${Math.abs(shift)} Key` : '原調';
}
// label of a key version; formant: the voice keeps the singer's timbre (a separate version);
// legacy: one made with the older method (R2, 2026-11-07), kept for the recordings made on it
export function keyText(value = 0, formant = false, legacy = false) {
  return keyLabel(value) + (value && formant ? (legacy ? ' · 保留原唱音色（舊做法）' : ' · 保留原唱音色') : '');
}
export function transposeReference(source, value) {
  const shift = keyShift(value), factor = 2 ** (shift / 12);
  if (source.pitchShift) throw Error('請從原調音軌建立 Key 版本，避免重複變調。');
  return {...source, pitchShift:shift, baseTitle:source.baseTitle || source.title,
    sourceCacheId:source.cacheId, title:shift ? `${source.title.slice(0,280)} · ${keyLabel(shift)}` : source.title,
    frames:source.frames.map(hz=>hz === null ? null : hz * factor)};
}
// guide modes: original = the whole vocals (lead singer and backing vocals) with the accompaniment; lead = the lead
// singer without the backing vocals (lead/backing versions only); backing = the accompaniment and backing vocals
export function guideStems(reference, mode) {
  if (mode === 'lead' && reference.vocalMode === 'lead') return ['accompaniment','lead'];
  return mode === 'original' || mode === 'lead' ? ['accompaniment','vocals'] : ['accompaniment',...(reference.vocalMode === 'lead' ? ['backing'] : [])];
}
// the "how the song guides you" choices for the loaded version: "without backing vocals" only exists when the
// backing vocals are a separate track; the default's label says the backing vocals are in it when they are
export function syncGuideSelect(select, reference) {
  const lead = reference?.vocalMode === 'lead', option = value => select.querySelector(`option[value="${value}"]`);
  const noBacking = option('lead');
  if (noBacking) { noBacking.hidden = noBacking.disabled = !lead; }
  if (!lead && select.value === 'lead') select.value = 'original';
  option('original').textContent = lead ? '原唱＋和音＋伴樂（預設）' : '原唱＋伴樂（預設）';
}
export function guideModeLabel(mode, reference) {
  if (mode === 'lead') return '原唱＋伴樂（不含和音）';
  if (mode === 'backing') return '只有伴樂／和音';
  return reference?.vocalMode === 'lead' ? '原唱＋和音＋伴樂' : '原唱＋伴樂';
}
