// [SIGN2MV] Score the take with RMVPE, the same model the song reference was built with.
// The browser's own detector (YIN) still draws the live pitch line; the score comes from the
// recorded dry vocal, sent to the local server a couple of seconds at a time while singing.
// Gridding follows workers/sing_reference.py exactly: one value per 100 ms reference cell, the
// median of the 9 RMVPE frames (10 ms) around it when more than half are 65–1000 Hz, then only
// stable runs (an isolated cell is dropped; a cell between two voiced cells takes their median).
// Timing follows the saved recording: song time = recorded time − the recording delay correction.
import { ScoringTake } from './scoring.mjs';

const HOP = .01, CORE = 2, CONTEXT = 1, WINDOW = 4, MIN = 65, MAX = 1000;
let tokenPromise = null;
async function token() {
  tokenPromise ||= fetch('/sr/session', { cache: 'no-store' }).then(r => r.json()).then(v => v.token).catch(e => { tokenPromise = null; throw e; });
  return tokenPromise;
}
export async function warmRmvpe() {
  try { await fetch('/sr/live-pitch/warm', { method: 'POST', headers: { 'X-Karaoke-Token': await token() } }); } catch { /* scored with the browser detector then */ }
}
function int16(samples) {
  const out = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) { const x = Math.max(-1, Math.min(1, samples[i])); out[i] = Math.round(x * (x < 0 ? 32768 : 32767)); }
  return out;
}
async function pitchPiece(samples, rate, signal) {
  const r = await fetch(`/sr/live-pitch?rate=${Math.round(rate)}`, { method: 'POST', body: int16(samples).buffer, signal,
    headers: { 'X-Karaoke-Token': await token(), 'Content-Type': 'application/octet-stream' } });
  const v = await r.json().catch(() => ({}));
  if (!r.ok || !Array.isArray(v.f0)) throw new Error(v.error || `RMVPE ${r.status}`);
  return v;
}
function median(values) { const v = [...values].sort((a, b) => a - b), n = v.length; return n % 2 ? v[n >> 1] : (v[n / 2 - 1] + v[n / 2]) / 2; }
// RMVPE value of one reference cell, centred on recorded time r (seconds); undefined = not analysed yet
function cellValue(f0, r) {
  const center = Math.round(r / HOP), values = [];
  let count = 0;
  for (let j = center - 4; j <= center + 4; j++) {
    if (j < 0) continue;
    const v = f0[j];
    if (v === undefined) return undefined;
    count++;
    if (Number.isFinite(v) && v >= MIN && v <= MAX) values.push(v);
  }
  if (!count) return null;
  return values.length > count / 2 ? Math.round(median(values) * 100) / 100 : null;
}
// stable runs only (same rule as the reference): value of cell i from cells i-1, i, i+1
function stable(prev, cur, next) {
  if (cur == null) return null;
  const n = [prev, cur, next].filter(v => v != null);
  if (n.length < 2) return null;
  return n.length === 3 ? Math.round(median(n) * 100) / 100 : cur;
}
function segmentEnd(segments, index, recordedSeconds) {
  const s = segments[index];
  return s.duration || index < segments.length - 1 ? s.offset + s.duration : recordedSeconds;
}
// Feed every reference cell whose recorded time (and its neighbours) is analysed into `take`.
// cursor: per segment, the next song cell index to settle. Returns true if anything changed.
function settle(take, reference, segments, f0, shift, analysedUntil, recordedSeconds, cursor, final) {
  const step = reference.step;
  let changed = false;
  segments.forEach((s, k) => {
    const songStart = s.songTime, recEnd = segmentEnd(segments, k, recordedSeconds);
    const songEnd = songStart + Math.max(0, recEnd - s.offset);
    let i = cursor.get(k) ?? Math.ceil(songStart / step - 1e-9);
    const recOf = cell => s.offset + cell * step - songStart + shift;   // recorded time of a song cell
    const inSeg = cell => cell * step >= songStart - 1e-9 && cell * step < songEnd;
    for (; i < reference.frames.length && inSeg(i); i++) {
      const r = recOf(i);
      if (!final && r + step + .05 > analysedUntil) break;
      if (r < 0) { take.sample(i * step + 1e-6, null); changed = true; continue; }
      const val = c => (inSeg(c) && recOf(c) >= 0 ? cellValue(f0, recOf(c)) : null);
      const cur = val(i);
      if (cur === undefined && !final) break;
      const prev = val(i - 1), next = val(i + 1);
      take.sample(i * step + 1e-6, stable(prev ?? null, cur ?? null, next ?? null));
      changed = true;
    }
    cursor.set(k, i);
  });
  return changed;
}
function resultIn(take, start, end) {
  const keep = [take.startIndex, take.endIndex];
  take.startIndex = start; take.endIndex = Math.max(start, end);
  const r = take.result(true);
  [take.startIndex, take.endIndex] = keep;
  return r;
}

// ---- while singing ----
export function createRmvpeScoring({ onUpdate = () => {} } = {}) {
  let session = null;
  function cancel() {
    if (!session) return;
    session.stopped = true; clearInterval(session.timer); session.unobserve?.(); session.abort.abort();
    session = null;
  }
  function start(reference, scoring, live) {
    cancel();
    if (!live) return false;
    const s = session = { reference, live, take: new ScoringTake(reference, scoring), f0: [], chunks: [], received: 0,
      analysedUntil: 0, coreStart: 0, busy: false, failed: false, stopped: false, cursor: new Map(), abort: new AbortController(),
      shift: (live.delayMs || 0) / 1000, rate: live.sampleRate, lastShown: -1 };
    s.take.begin(0);
    s.unobserve = live.observe(({ recordedFrame, voice }) => {
      if (s.stopped) return;
      s.chunks.push({ frame: recordedFrame, data: voice.slice() });
      s.received = Math.max(s.received, recordedFrame + voice.length);
    });
    s.timer = setInterval(() => { void pump(s, false); }, 500);
    return true;
  }
  // audio between two recorded times (seconds), from the kept chunks
  function audio(s, from, to) {
    const a = Math.max(0, Math.round(from * s.rate)), b = Math.round(to * s.rate), out = new Float32Array(Math.max(0, b - a));
    for (const c of s.chunks) {
      const lo = Math.max(a, c.frame), hi = Math.min(b, c.frame + c.data.length);
      if (hi > lo) out.set(c.data.subarray(lo - c.frame, hi - c.frame), lo - a);
    }
    // drop what no future piece needs (the left context of the next core)
    const keep = Math.round((s.coreStart - CONTEXT - .5) * s.rate);
    s.chunks = s.chunks.filter(c => c.frame + c.data.length > keep);
    return out;
  }
  async function pump(s, final) {
    if (s.busy || s.stopped || s.failed) return;
    const available = s.received / s.rate;
    const coreEnd = final ? available : Math.min(available - CONTEXT, s.coreStart + WINDOW);
    if (coreEnd - s.coreStart < (final ? HOP : CORE)) { if (final) settleAndShow(s, true); return; }
    s.busy = true;
    const from = Math.max(0, s.coreStart - CONTEXT), to = Math.min(available, coreEnd + CONTEXT);
    try {
      const v = await pitchPiece(audio(s, from, to), s.rate, s.abort.signal);
      if (s.stopped) return;
      const first = Math.round(from / HOP);
      for (let j = 0; j < v.f0.length; j++) {
        const t = from + j * HOP;
        if (t >= s.coreStart - 1e-9 && t < coreEnd) s.f0[first + j] = v.f0[j];
      }
      s.coreStart = coreEnd; s.analysedUntil = coreEnd; s.device = v.device;
      settleAndShow(s, final && coreEnd >= available - 1e-6);
    } catch (e) {
      if (!s.stopped) { s.failed = true; s.error = e.message; }
    } finally { s.busy = false; }
  }
  function settleAndShow(s, final) {
    settle(s.take, s.reference, s.live.segments, s.f0, s.shift, s.analysedUntil, s.received / s.rate, s.cursor, final);
    s.settledAll = final;
    const done = Math.max(...s.cursor.values(), 0);
    if (done !== s.lastShown) { s.lastShown = done; onUpdate(s); }
  }
  return {
    start, cancel,
    running: () => !!session && !session.failed,
    // live display: only the cells already settled, within the performed range so far
    result(liveTake) {
      const s = session; if (!s || s.failed) return null;
      const settled = Math.max(...s.cursor.values(), 0);
      return resultIn(s.take, liveTake.startIndex, Math.min(liveTake.endIndex, settled));
    },
    // final score: analyse what is left, then score the whole performed range; null = not available
    async finish(liveTake, timeoutMs = 20000) {
      const s = session; if (!s) return null;
      clearInterval(s.timer);
      const until = Date.now() + timeoutMs;
      while (!s.failed && !s.stopped && Date.now() < until) {
        if (!s.busy) {
          if (s.settledAll) break;
          await pump(s, true);
        } else await new Promise(r => setTimeout(r, 50));
      }
      const ok = s.settledAll && !s.failed;
      const r = ok ? resultIn(s.take, liveTake.startIndex, liveTake.endIndex) : null;
      if (ok) r.device = s.device;
      cancel();
      return r;
    },
    error: () => session?.error || '',
  };
}

// ---- saved recordings (post-production rescoring) ----
// f0 of the whole saved voice: 8 s cores with 1 s context, like the reference
export async function analyseRecordingRmvpe(blob, progress = () => {}) {
  const ctx = new OfflineAudioContext(1, 1, 48000);
  const buffer = await ctx.decodeAudioData(await blob.arrayBuffer());
  const rate = buffer.sampleRate, n = buffer.length, mono = new Float32Array(n);
  for (let c = 0; c < buffer.numberOfChannels; c++) { const d = buffer.getChannelData(c); for (let i = 0; i < n; i++) mono[i] += d[i] / buffer.numberOfChannels; }
  const duration = n / rate, f0 = [];
  for (let core = 0; core < duration; core += 8) {
    const end = Math.min(duration, core + 8), from = Math.max(0, core - 1), to = Math.min(duration, end + 1);
    const v = await pitchPiece(mono.subarray(Math.round(from * rate), Math.round(to * rate)), rate);
    const first = Math.round(from / HOP);
    for (let j = 0; j < v.f0.length; j++) { const t = from + j * HOP; if (t >= core - 1e-9 && t < end) f0[first + j] = v.f0[j]; }
    progress(Math.round(end / duration * 100));
  }
  for (let j = 0; j < f0.length; j++) if (f0[j] === undefined) f0[j] = 0;
  return { version: 1, source: 'rmvpe-v1', hop: HOP, duration, f0 };
}
export function rescoreRecordingRmvpe(post, analysis, ms) {
  const take = new ScoringTake(post.reference, post.scoring);
  take.begin(0);
  for (const s of post.segments) take.advance(s.songTime + s.duration);
  const end = take.endIndex;
  settle(take, take.reference, post.segments, analysis.f0, ms / 1000, analysis.duration, analysis.duration, new Map(), true);
  take.endIndex = end;
  return take.result();
}
