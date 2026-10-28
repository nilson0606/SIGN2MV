// Compatibility labels for already-rendered recordings. Synth generation was
// removed; keep identifying existing files accurately without modifying them.
const labels={light:'輕度',medium:'中度',strong:'強烈'};
export function recordingTuningSuffix(meta) {
  const id=meta?.vocalTuning?.strength;
  return id&&Object.hasOwn(labels,id)?`_${meta.vocalTuning.version>=3?'合成器':'修音'}${labels[id]}`:'';
}
