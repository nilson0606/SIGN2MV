// A key version changes pitch only; all song-time coordinates remain unchanged.
export function keyShift(value = 0) {
  if (!Number.isInteger(value) || value < -12 || value > 12) throw Error('Key 請選擇 −12～＋12 的整數半音。');
  return value;
}
export function keyLabel(value = 0) {
  const shift = keyShift(value);
  return shift ? `${shift > 0 ? '升' : '降'} ${Math.abs(shift)} Key` : '原調';
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
