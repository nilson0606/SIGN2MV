import {keyShift} from './song-key.mjs';
// Experimental single-melody scoring. Raw audio never enters this module.
export function normalizeMasks(value = [], duration) {
  if (!Array.isArray(value) || value.length > 100 || !Number.isFinite(duration) || duration <= 0) throw new Error('遮罩資料無效，最多 100 段。');
  const sorted = value.map(range => {
    if (!range || !Number.isFinite(range.start) || !Number.isFinite(range.end) || range.start < 0 || range.end <= range.start || range.end > duration) throw new Error('遮罩需符合 0 ≤ 起點 < 終點 ≤ 歌曲基準長度。');
    return { start: range.start, end: Math.min(duration, range.end) };
  }).sort((a,b) => a.start - b.start);
  const merged = [];
  for (const range of sorted) {
    const last = merged.at(-1);
    if (last && range.start <= last.end) last.end = Math.max(last.end, range.end);
    else merged.push(range);
  }
  return merged;
}
export function maskedCells(reference) {
  return reference.frames.map((_, i) => (reference.masks || []).some(({start,end}) => start < (i + 1) * reference.step - 1e-8 && end > i * reference.step + 1e-8));
}
export function applyMasks(reference) {
  const excluded = maskedCells(reference);
  return { ...reference, frames: reference.frames.map((hz,i) => excluded[i] ? null : hz) };
}
export function validateReference(value) {
  if (!value || value.version !== 1 || typeof value.videoId !== 'string' || !/^(?:[\w-]{11}|local_[a-f0-9]{64})$/.test(value.videoId)) throw new Error('歌曲基準缺少有效影片 ID。');
  if (typeof value.title !== 'string' || value.title.length > 300) throw new Error('歌曲名稱無效。');
  if (!Number.isFinite(value.step) || value.step < .02 || value.step > .2) throw new Error('基準時間間隔必須介於 20–200 ms。');
  if (!Array.isArray(value.frames) || value.frames.length < 1 || value.frames.length > 90000) throw new Error('基準長度無效。');
  const shift=keyShift(value.pitchShift ?? 0), factor=2 ** (shift/12);
  let voiced = 0;
  for (const hz of value.frames) {
    if (hz === null) continue;
    if (!Number.isFinite(hz) || hz < 65 * factor - 1e-8 || hz > 1000 * factor + 1e-8) throw new Error('基準音高超出 65–1000 Hz。');
    voiced++;
  }
  if (voiced * value.step < 3) throw new Error('至少需要 3 秒可辨識的參考旋律。');
  return { version: 1, videoId: value.videoId, title: value.title, step: value.step, frames: [...value.frames], ...(shift ? {pitchShift:shift} : {}), masks: normalizeMasks(value.masks, value.duration ?? value.frames.length * value.step) };
}

export function pitchDifference(actual, expected, allowOctave = false) {
  const cents = 1200 * Math.log2(actual / expected);
  return allowOctave ? cents - Math.round(cents / 1200) * 1200 : cents;
}

// Difficulty, in musical terms (100 cents = one semitone). Full credit inside pitchFull, none from
// pitchZero; pitchSlack lets a note land a little early or late (phrasing) without losing pitch
// credit; an onset within rhythmFull is on time, and from rhythmFull + rhythmFade it earns nothing.
// The reference melody has one cell every 0.1 s, so onset timing resolves to 0.1 s.
// Measurement margin: the original vocal sung through the app (童話, original key, at its own delay)
// reached 100 on pitch only from +5 cents (RMVPE on the recorded take vs the reference differs a few
// cents in glides); standard and strict carry that +5 on both pitch limits. Rhythm needed none.
//   relaxed : right note within a quarter tone, wrong only past 1.5 semitones; ±0.2 s phrasing
//   standard: within 30 cents, a semitone plus 5 cents off (a neighbouring note) earns nothing; ±0.1 s
//   strict  : within 20 cents, 55 cents off earns nothing; no phrasing slack
export const SCORING_PROFILES = Object.freeze({
  standard: Object.freeze({ id: 'standard', label: '標準', pitchFull: 30, pitchZero: 105, pitchSlack: .1, rhythmFull: .10, rhythmFade: .20, rhythmWindow: .301 }),
  strict: Object.freeze({ id: 'strict', label: '嚴格', pitchFull: 20, pitchZero: 55, pitchSlack: 0, rhythmFull: .05, rhythmFade: .15, rhythmWindow: .201 }),
  relaxed: Object.freeze({ id: 'relaxed', label: '寬鬆', pitchFull: 50, pitchZero: 150, pitchSlack: .2, rhythmFull: .20, rhythmFade: .30, rhythmWindow: .501 }),
});
export function scoringProfile(difficulty = 'standard') {
  return Object.hasOwn(SCORING_PROFILES, difficulty) ? SCORING_PROFILES[difficulty] : SCORING_PROFILES.standard;
}

export function pitchCredit(actual, expected, allowOctave = false, difficulty = 'standard') {
  if (!Number.isFinite(actual) || actual < 65 || actual > 1000) return 0;
  const cents = Math.abs(pitchDifference(actual, expected, allowOctave));
  const profile = scoringProfile(difficulty);
  return Math.max(0, Math.min(1, 1 - (cents - profile.pitchFull) / (profile.pitchZero - profile.pitchFull)));
}

function onsets(frames, step) {
  const notes = []; let last = null, silence = 2;
  for (let i = 0; i < frames.length - 1; i++) {
    const hz = frames[i], next = frames[i + 1];
    if (hz == null) { silence++; continue; }
    const midi = 69 + 12 * Math.log2(hz / 440);
    if (next != null && Math.abs(12 * Math.log2(next / hz)) < .75 && (last === null || silence >= 2 || Math.abs(midi - last) >= .75)) {
      notes.push({ time: i * step, hz }); last = midi;
    }
    silence = 0;
  }
  return notes;
}
// Rhythm: every note start of the reference melody, timed the same way on both sides. The sung line is
// not cut into notes of its own (two independent cuts flip on a few cents near the 0.75-semitone line,
// and the original vocal itself then lost up to 10 points). Around each reference note start, both the
// reference and the take are searched for the cell where the voice arrives on that note: closer to it
// than to the reference note just before it (a one-cell break, a consonant, is not silence), within
// 150 cents; after silence, where the voice starts within 150 cents. A voice that is already on the note
// through the lead-in (a small step sung legato) counts as arriving before the window, on both sides
// alike. The timing error is the difference between the two arrivals.
export function rhythmCredit(reference, actual, step, allowOctave, profile, excluded = []) {
  const expected = onsets(reference, step);
  if (!expected.length) return 0;
  const window = Math.round(profile.rhythmWindow / step - 1e-6);
  const cents = (a, b) => Math.abs(pitchDifference(a, b, allowOctave));
  let total = 0;
  for (const note of expected) {
    const c = Math.round(note.time / step), before = reference[c - 1] ?? reference[c - 2] ?? null;
    const onNote = hz => hz != null && cents(hz, note.hz) <= 150 && (before == null || cents(hz, note.hz) < cents(hz, before));
    const arrival = frames => {
      const on = j => j >= 0 && j < frames.length && onNote(frames[j]);
      let best = null;
      for (let j = c - window; j <= c + window; j++) {
        if (!on(j) || on(j - 1) || excluded.slice(Math.min(j, c), Math.max(j, c) + 1).some(Boolean)) continue;
        if (best === null || Math.abs(j - c) < Math.abs(best - c)) best = j;
      }
      if (best === null) {
        let held = true;
        for (let j = c - window; j <= c && held; j++) held = on(j);
        if (held) best = c - window - 1;
      }
      return best;
    };
    const expectedAt = arrival(reference), sungAt = arrival(actual);
    if (expectedAt === null || sungAt === null) continue;
    const error = Math.abs(sungAt - expectedAt) * step;
    total += Math.max(0, Math.min(1, 1 - (error - profile.rhythmFull) / profile.rhythmFade));
  }
  return total / expected.length;
}

export class ScoringTake {
  constructor(reference, { allowOctave = false, rangeMode = 'full', difficulty = 'standard' } = {}) {
    this.allowOctave = allowOctave;
    this.profile = scoringProfile(difficulty);
    this.difficulty = this.profile.id;
    this.rangeMode = rangeMode === 'performed' ? 'performed' : 'full';
    this.startIndex = 0; this.endIndex = 0;
    const validated = validateReference(reference);
    this.excluded = maskedCells(validated);
    this.reference = applyMasks(validated);
    this.pitchFactor=2 ** ((validated.pitchShift || 0)/12);
    this.observations = new Map();
    this.sampleDistances = new Map(); this.lastSampleIndex = null;
  }
  begin(time = 0) {
    const index = Math.max(0, Math.min(this.reference.frames.length, Math.floor((Number.isFinite(time) ? time : 0) / this.reference.step)));
    this.startIndex = this.endIndex = index;
  }
  advance(time) {
    if (!Number.isFinite(time) || time < 0) return;
    const length = this.reference.frames.length;
    this.startIndex = Math.min(this.startIndex, Math.min(length, Math.floor(time / this.reference.step)));
    this.endIndex = Math.max(this.endIndex, Math.min(length, Math.ceil(time / this.reference.step - 1e-8)));
  }
  sample(time, hz) {
    if (!Number.isFinite(time) || time < 0) return;
    const step=this.reference.step, cell=Math.floor(time/step), index=Math.round(time/step);
    if (index >= this.reference.frames.length || index < this.startIndex) return;
    // Reference frames describe the instant i*step, not the end of a 100 ms bin.
    // Pick by distance in time only, never by pitch quality. A new visit (rewind)
    // replaces that cell's previous performance rather than keeping a best score.
    if (index !== this.lastSampleIndex) this.sampleDistances.delete(index);
    this.lastSampleIndex=index;
    this.endIndex=Math.max(this.endIndex,Math.min(this.reference.frames.length,cell+1));
    if (this.excluded[index] || this.excluded[cell]) return;
    const distance=Math.abs(time-index*step);
    if (distance>(this.sampleDistances.get(index)??Infinity)+1e-9) return;
    this.sampleDistances.set(index,distance);
    this.observations.set(index, Number.isFinite(hz) && hz >= 65*this.pitchFactor && hz <= 1000*this.pitchFactor ? hz : null);
  }

  result(includeRhythm = true) {
    let expected = 0, voiced = 0, points = 0;
    const start = this.rangeMode === 'performed' ? this.startIndex : 0;
    const end = this.rangeMode === 'performed' ? this.endIndex : this.reference.frames.length;
    const frames = this.reference.frames.slice(start, end);
    for (let i = start; i < end; i++) {
      const target = this.reference.frames[i];
      if (target === null) continue;
      expected++;
      const actual = this.observations.get(i);
      if (actual !== null && actual !== undefined) voiced++;
      // best credit among the sung frames within the phrasing slack (coverage still counts this cell only)
      const slack = Math.round(this.profile.pitchSlack / this.reference.step);
      let best = 0;
      for (let j = i - slack; j <= i + slack; j++) {
        const hz = this.observations.get(j);
        if (hz !== null && hz !== undefined) best = Math.max(best, pitchCredit(hz/this.pitchFactor, target/this.pitchFactor, this.allowOctave, this.difficulty));
      }
      points += best;
    }
    if (!expected) return { score: null, pitch: 0, rhythm: 0, coverage: 0, referenceSeconds: 0, sampledSeconds: 0 };
    const actual = frames.map((_, i) => this.observations.get(i + start) ?? null);
    const rhythm = includeRhythm ? rhythmCredit(frames, actual, this.reference.step, this.allowOctave, this.profile, this.excluded.slice(start, end)) : 0;
    // Missing notes inside the selected interval stay in the denominator, including silence and skipped sections.
    return {
      score: Math.round(100 * (.6 * points / expected + .25 * rhythm + .15 * voiced / expected)),
      rhythm: Math.round(100 * rhythm),
      pitch: Math.round(100 * points / expected),
      coverage: Math.round(100 * voiced / expected),
      referenceSeconds: Math.round(expected * this.reference.step * 10) / 10,
      sampledSeconds: Math.round([...this.observations.keys()].filter(i => i >= start && i < end && this.reference.frames[i] !== null).length * this.reference.step * 10) / 10,
    };
  }
  clear() { this.observations.clear(); this.sampleDistances.clear(); this.lastSampleIndex=null; this.reference.frames = []; }
}

export function savedResult(title, score) {
  if (typeof title !== 'string' || !title.trim() || title.length > 300 || !Number.isFinite(score) || score < 0 || score > 100) throw new Error('演唱紀錄無效。');
  return { title: title.trim(), score: Math.round(score) };
}
