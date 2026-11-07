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
export function guideStems(reference, mode) {
  return mode === 'original' ? ['accompaniment','vocals'] : ['accompaniment',...(reference.vocalMode === 'lead' ? ['backing'] : [])];
}
