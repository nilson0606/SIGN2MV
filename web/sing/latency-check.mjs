// [SIGN2MV 2026-11-19] 「延遲校正」: the singer sings a song everyone knows (Twinkle Twinkle Little Star,
// public domain: a French tune printed in 1761, words of 1806), built into the page, so no song has to be
// prepared. The song is played the way a local song is (a media element) and recorded the way a take is
// (the same microphone and capture, the same PCM recorder, song time noted when playback starts), then
// scored with RMVPE and the take's own rhythm rule. Only 進拍 (rhythm) counts here: the singer moves the
// delay, scores again without singing again, and keeps the delay that suits; it becomes the saved input
// latency (the slider of the hidden 04 panel), used by every take after.
import { createPCMRecorders, pcmHeader, pcm16 } from './recording-pcm.mjs';
import { analyseRecordingRmvpe, rescoreRecordingRmvpe, warmRmvpe } from './rmvpe-score.mjs';
import { translateMessage } from './i18n.mjs';

const $ = id => document.getElementById(id);
export const STATE_KEY = 'sign2mv.latency-check.v1';   // 'done' or 'skipped': the guide asks once
const BPM = 96, BEAT = 60 / BPM, COUNT_IN = 5, LEAD = .4, STEP = .1;   // five count-in beats: 5 4 3 2 1
// C4 = 60. Each phrase: six quarter notes and a half note.
const PHRASES = [
  [60, 60, 67, 67, 69, 69, 67], [65, 65, 64, 64, 62, 62, 60],
  [67, 67, 65, 65, 64, 64, 62], [67, 67, 65, 65, 64, 64, 62],
  [60, 60, 67, 67, 69, 69, 67], [65, 65, 64, 64, 62, 62, 60],
];
// a chord root under every half bar (two beats), as children sing it
const CHORDS = [[60, 60, 65, 60], [65, 60, 67, 60], [60, 65, 60, 67], [60, 65, 60, 67], [60, 60, 65, 60], [65, 60, 67, 60]];
const SOLFEGE = { 60: 'Do', 62: 'Re', 64: 'Mi', 65: 'Fa', 67: 'Sol', 69: 'La' };
const hz = midi => 440 * 2 ** ((midi - 69) / 12);
export const SONG_START = LEAD + COUNT_IN * BEAT;
export const SONG_SECONDS = SONG_START + PHRASES.length * 8 * BEAT + 1.2;
// The first phrase is a warm-up: shown as such, not scored, and left out of 「自動找」. Scoring starts with phrase 2.
const WARM_UP = 1;
export const SCORED_FROM = SONG_START + WARM_UP * 8 * BEAT;
// A real song is scored against the original singer, and a sung note's pitch starts a little after the beat; the
// calibration tone starts right on it. Measured 2026-11-19 with one method for both (beats from the accompaniment's
// spectral flux, note starts from RMVPE): a studio vocal (one ballad, 187 note starts) +9 ms from the beat, the
// calibration tone -32 ms, so 41 ms apart. The reference (what the take is scored and 「自動找」 matched against) is
// therefore the melody 41 ms later than it is played: the singer still hears the tone on the beat, and the delay
// found compares like with like, as in a song.
export const HUMAN_ONSET_LAG = .041;

export function calibrationNotes() {
  const notes = [];
  PHRASES.forEach((phrase, p) => phrase.forEach((midi, k) => {
    const beats = k === 6 ? 2 : 1, start = SONG_START + (p * 8 + k) * BEAT;
    notes.push({ phrase: p, index: k, midi, name: SOLFEGE[midi], start, duration: beats * BEAT });
  }));
  return notes;
}

// The reference: the melody itself, one value per 100 ms cell (the same grid as a prepared song)
export function calibrationReference() {
  const notes = calibrationNotes(), cells = Math.ceil(SONG_SECONDS / STEP), frames = new Array(cells).fill(null);
  for (let i = 0; i < cells; i++) {
    const t = i * STEP - HUMAN_ONSET_LAG, n = notes.find(x => t >= x.start - 1e-9 && t < x.start + x.duration - .05);
    if (n) frames[i] = Math.round(hz(n.midi) * 100) / 100;
  }
  return { version: 1, videoId: 'local_' + '0'.repeat(63) + '1', title: translateMessage('延遲校正 · 小星星'), step: STEP, frames: dropWarmUp(frames), masks: [], duration: SONG_SECONDS };
}
// The warm-up has no reference: its cells are emptied up to the first cell on the first scored note. Emptying by
// time alone would leave the tail of the warm-up's last (held) note standing alone, which the rhythm rule would
// read as a note start of its own; emptied this way, the first scored note starts after silence, as after a rest.
function dropWarmUp(frames) {
  const first = hz(PHRASES[WARM_UP][0]), near = f => f != null && Math.abs(1200 * Math.log2(f / first)) < 100;
  let i = 0;
  while (i < frames.length && (i * STEP < SCORED_FROM - .25 || (!near(frames[i]) && i * STEP < SCORED_FROM + .3))) i++;
  return frames.map((f, k) => (k < i ? null : f));
}

// The song, rendered here from the notes: count-in clicks, a soft beat, the chord roots and (optionally)
// the melody to sing along with. Clicks are above the pitch range scored, so a speaker leaking into the
// microphone does not pass for the singer (headphones are still asked for).
// lag: seconds the melody is moved later (only the melody rendered for the reference uses HUMAN_ONSET_LAG)
export async function renderCalibrationSong(guide = true, rate = 44100, melodyOnly = false, lag = 0) {
  const ctx = new OfflineAudioContext(1, Math.ceil(SONG_SECONDS * rate), rate);
  const out = ctx.createGain(); out.gain.value = .9; out.connect(ctx.destination);
  const tone = (freq, start, duration, level, type = 'sine', attack = .012, release = .08) => {
    const g = ctx.createGain(), o = ctx.createOscillator();
    o.type = type; o.frequency.value = freq; o.connect(g); g.connect(out);
    g.gain.setValueAtTime(0, start); g.gain.linearRampToValueAtTime(level, start + attack);
    g.gain.exponentialRampToValueAtTime(level * .55, start + Math.max(attack + .01, duration * .6));
    g.gain.setValueAtTime(level * .55, start + Math.max(attack + .02, duration - release));
    g.gain.linearRampToValueAtTime(0, start + duration);
    o.start(start); o.stop(start + duration + .01);
  };
  if (!melodyOnly) {
  for (let b = 0; b < COUNT_IN; b++) tone(b ? 1760 : 2093, LEAD + b * BEAT, .07, .5, 'sine', .002, .05);
  const beats = PHRASES.length * 8;
  for (let b = 0; b < beats; b++) tone(1760, SONG_START + b * BEAT, .04, .12, 'sine', .002, .03);
  CHORDS.forEach((roots, p) => roots.forEach((root, h) => {
    const at = SONG_START + (p * 8 + h * 2) * BEAT;
    tone(hz(root - 24), at, BEAT * 2 - .04, .22, 'triangle', .02, .15);
    tone(hz(root - 17), at, BEAT * 2 - .04, .08, 'triangle', .02, .15);   // the fifth below
  }));
  }
  if (guide) for (const n of calibrationNotes()) {
    tone(hz(n.midi), n.start + lag, n.duration - .06, .22);
    tone(hz(n.midi) * 2, n.start + lag, n.duration - .06, .05);
  }
  const buffer = await ctx.startRendering(), data = buffer.getChannelData(0);
  return new Blob([pcmHeader(data.length, 1, rate), pcm16(data, 0, data.length)], { type: 'audio/wav' });
}

// The reference a take is scored against comes from RMVPE, and RMVPE (a ~64 ms window) hears a note start a little
// early. So the calibration reference is not written from the notes: the melody alone is rendered and analysed
// with the same RMVPE, then put on 100 ms cells the way a prepared song is (median of the 9 frames around a cell
// when more than half are 65–1000 Hz; only stable runs). Both sides then carry the same analysis, as with a song.
export function cellsFromF0(analysis, seconds = SONG_SECONDS) {
  const f0 = analysis.f0, hop = analysis.hop, cells = Math.ceil(seconds / STEP), raw = [];
  const median = v => { const a = [...v].sort((x, y) => x - y), n = a.length; return n % 2 ? a[n >> 1] : (a[n / 2 - 1] + a[n / 2]) / 2; };
  for (let i = 0; i < cells; i++) {
    const c = Math.round(i * STEP / hop), v = [];
    let n = 0;
    for (let j = c - 4; j <= c + 4; j++) { if (j < 0 || j >= f0.length) continue; n++; if (f0[j] >= 65 && f0[j] <= 1000) v.push(f0[j]); }
    raw.push(n && v.length > n / 2 ? Math.round(median(v) * 100) / 100 : null);
  }
  return raw.map((cur, i) => {
    if (cur == null) return null;
    const near = [raw[i - 1], cur, raw[i + 1]].filter(x => x != null);
    return near.length < 2 ? null : near.length === 3 ? Math.round(median(near) * 100) / 100 : cur;
  });
}
export function referenceFrom(analysis) {
  return { ...calibrationReference(), frames: dropWarmUp(cellsFromF0(analysis)) };
}
// Rhythm at a delay: what the singer sees, and what 「自動找」 scans
export function rhythmAt(post, analysis, ms, difficulty = 'standard') {
  return rescoreRecordingRmvpe({ ...post, scoring: { ...post.scoring, difficulty } }, analysis, ms).rhythm;
}
// 「自動找」 (run by itself when a calibration has been analysed): the rhythm score every 10 ms over 100-500 ms,
// and the middle of the widest stretch at the top score (the user's choice, 2026-11-20: rhythm full marks span about
// 100 ms either side, so the middle of that plateau is where the note starts sit best inside it)
export const SCAN_FROM = 100, SCAN_TO = 500, SCAN_STEP = 10;
export function scanDelays(post, analysis, from = SCAN_FROM, to = SCAN_TO, step = SCAN_STEP) {
  const rows = [];
  for (let ms = from; ms <= to; ms += step) rows.push({ ms, rhythm: rhythmAt(post, analysis, ms) });
  const top = Math.max(...rows.map(r => r.rhythm));
  let best = null, run = null;
  for (const r of rows) {
    if (r.rhythm >= top) { run ||= { from: r.ms, to: r.ms }; run.to = r.ms; }
    if (run && (r.rhythm < top || r === rows.at(-1))) { if (!best || run.to - run.from > best.to - best.from) best = run; run = null; }
  }
  return { rows, best: Math.round((best.from + best.to) / 2 / step) * step, top, from: best.from, to: best.to };
}

export function createLatencyCheck(options) {
  const say = text => { $('lc-status').textContent = translateMessage(text); };
  let songUrl = null, songGuide = null, run = null, last = null, busy = false;
  const audio = new Audio(); audio.preload = 'auto'; audio.id = 'lc-audio';
  const notes = calibrationNotes();
  let melody = null;   // RMVPE of the melody alone: the reference (analysed once per page)

  function showCurrent() {
    const text = $('offset-value')?.textContent || `${$('offset').value} ms`;
    $('lc-current').textContent = text;
  }
  new MutationObserver(showCurrent).observe($('offset-value'), { childList: true, characterData: true, subtree: true });
  showCurrent();

  // Two rows: the line being sung and, smaller, the next one, so what comes is always in sight. The next note
  // is announced (outline) half a beat early; it lights exactly on its beat, so the cue never pulls the singer
  // ahead of the music (that would make the delay found too small). The count-in shows 5 4 3 2 1 on its clicks.
  function rowOf(phrase, t) {
    const row = document.createElement('div'); row.className = 'lc-row';
    row.append(...notes.filter(n => n.phrase === phrase).map(n => {
      const s = document.createElement('span'); s.textContent = n.name;
      if (t >= n.start && t < n.start + n.duration - .03) s.className = 'on';
      else if (t >= n.start + n.duration - .03) s.className = 'done';
      else if (t >= n.start - BEAT / 2) s.className = 'next';
      return s;
    }));
    // after the notes, so this line's notes stay above the next line's
    if (phrase < WARM_UP) { const tag = document.createElement('em'); tag.className = 'lc-tag'; tag.textContent = translateMessage('暖身 · 不計分'); row.append(tag); }
    return row;
  }
  function drawNotes(t = -1) {
    const box = $('lc-notes'), last = PHRASES.length - 1;
    const counting = t >= 0 && t < SONG_START;
    let phrase = 0;
    if (t >= SONG_START) phrase = Math.min(last, Math.floor((t - SONG_START) / (8 * BEAT)));
    // the count line keeps its place (empty while singing), so the rows never jump
    const beat = Math.floor((t - LEAD) / BEAT), count = document.createElement('div');
    count.className = 'lc-count'; count.textContent = counting ? (beat >= 0 ? String(COUNT_IN - beat) : translateMessage('預備')) : '\u00a0';
    const parts = [count];
    parts.push(rowOf(phrase, t));
    if (phrase < last) { const next = rowOf(phrase + 1, -1); next.classList.add('lc-row-next'); parts.push(next); }
    box.replaceChildren(...parts);
  }
  drawNotes();

  function controls() {
    const ready = options.micReady();
    $('lc-start').disabled = busy || !!run;   // a closed microphone is opened by 開始校正 itself
    $('lc-stop').disabled = !run;
    $('lc-guide').disabled = !!run || busy;
    $('lc-skip').disabled = !!run || busy;
    for (const id of ['lc-rescore', 'lc-auto', 'lc-apply', 'lc-delay']) $(id).disabled = busy || !!run || !last;
    window.dispatchEvent(new Event('sign2mv-latency-check'));   // the step guide follows
    if (!run && !busy && !last) say(ready ? '戴上耳機，按「開始校正」。倒數 5、4、3、2、1 之後跟著提示唱。' : '戴上耳機，按「開始校正」（會自動開麥克風）。倒數 5、4、3、2、1 之後跟著提示唱。');
  }

  async function song() {
    const guide = $('lc-guide').checked;
    if (!songUrl || songGuide !== guide) {
      if (songUrl) URL.revokeObjectURL(songUrl);
      songUrl = URL.createObjectURL(await renderCalibrationSong(guide)); songGuide = guide;
    }
    return songUrl;
  }

  async function start() {
    if (run || busy) return;
    busy = true; controls();
    options.beforeStart?.();
    // the microphone is opened the way 03 and 「從頭開始唱且評分」 open it (same device and capture mode)
    if (!options.micReady()) {
      say('正在開麥克風…（第一次會請你允許使用麥克風）');
      try { await options.startMic?.(); } catch { /* the reason is shown by the microphone panel */ }
      if (!options.micReady()) {
        busy = false; controls();
        const why = options.micMessage?.() || '';
        say(why ? '沒有開始校正：' + why : '沒有開始校正：麥克風沒有開起來，請再按一次「開始校正」。');
        return;
      }
    }
    say('正在準備校正歌…');
    let mine = null;
    try {
      void warmRmvpe();
      // the song is rendered before the recorder is armed, so nothing heavy runs while the recorder is live
      const url = await song();
      if (!options.micReady()) throw new Error(translateMessage('麥克風已關閉，請再按一次「開始校正」。'));
      const context = options.context(), stream = options.stream();
      const mic = window.__latencyCheckInput?.(context, audio) || options.inputSource?.() || context.createMediaStreamSource(stream);
      const silent = context.createGain(); silent.gain.value = 0;
      const { recorder, rawRecorder } = await createPCMRecorders(context, mic, silent);
      const chunks = [];
      rawRecorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
      const done = new Promise(resolve => { rawRecorder.onstop = resolve; });
      const elapsed = () => recorder.clock.frames(context.currentTime) / context.sampleRate;
      mine = run = { context, recorder, rawRecorder, chunks, done, segments: [], segment: null, frame: 0, error: null, silent, mic, elapsed };
      const open = () => { run.segment = { offset: elapsed(), songTime: audio.currentTime, duration: 0 }; run.segments.push(run.segment); };
      const close = () => { if (run?.segment) { run.segment.duration = Math.max(0, elapsed() - run.segment.offset); run.segment = null; } };
      run.close = close;
      // everything stop() needs is in place before the recorder can report an error
      recorder.onerror = e => { if (run !== mine) return; run.error = e.error; stop(); };
      const follow = () => {
        if (run !== mine) return;
        const t = audio.currentTime;
        if (run.segment && Math.abs(run.segment.songTime + elapsed() - run.segment.offset - t) >= .15) close();
        if (!run.segment && !audio.paused && recorder.state === 'recording') open();
        drawNotes(t);
        run.frame = requestAnimationFrame(follow);
      };
      audio.src = url; audio.currentTime = 0;
      audio.onplaying = () => { if (run !== mine) return; if (recorder.state === 'inactive') recorder.start(); close(); open(); };
      audio.onended = () => stop();
      busy = false; controls(); say('● 校正中：跟著提示唱《小星星》（唱名或「啦」都可以）。');
      await audio.play();
      if (run === mine) run.frame = requestAnimationFrame(follow);
    } catch (error) {
      if (mine && run !== mine) return;   // already stopped, with its own message
      busy = false; cleanup(); controls(); say('沒有開始校正：' + (error.message || error));
    }
  }

  function cleanup() {
    if (!run) return;
    cancelAnimationFrame(run.frame);
    audio.onplaying = audio.onended = null; audio.pause();
    try { run.recorder.dispose(); } catch { /* already disconnected */ }
    run = null;
  }

  async function stop() {
    if (!run || run.stopping) return;
    const r = run; r.stopping = true;
    cancelAnimationFrame(r.frame); audio.pause(); r.close();
    const finished = audio.currentTime >= SONG_SECONDS - 1.5;
    if (r.recorder.state !== 'inactive') { r.recorder.stop(); await Promise.race([r.done, new Promise(res => setTimeout(res, 6000))]); }
    else { try { r.recorder.dispose(); } catch { /* already disconnected */ } }   // stopped before it started
    run = null; audio.onplaying = audio.onended = null; drawNotes();
    if (r.error) { controls(); say('收音中斷，請重新校正：' + r.error.message); return; }
    if (!r.segments.length || !r.chunks.length) { controls(); say('沒有錄到聲音，請確認麥克風後再試一次。'); return; }
    if (!finished && audio.currentTime < SCORED_FROM + 8 * BEAT * 2) { controls(); say('唱得太短，暖身之後至少再唱兩句才停止；請重新校正。'); return; }
    busy = true; controls(); say('正在分析歌聲（RMVPE）…');
    try {
      r.chunks[0] = r.recorder.voiceHeader();
      const blob = new Blob(r.chunks, { type: 'audio/wav' });
      const analysis = await analyseRecordingRmvpe(blob, p => say(`正在分析歌聲（RMVPE）… ${p}%`));
      const voiced = analysis.f0.filter(v => v > 0).length * analysis.hop;
      if (voiced < 4) throw new Error(translateMessage('幾乎沒有聽到歌聲，請靠近麥克風、戴耳機再唱一次。'));
      if (!melody) { say('正在分析校正歌的基準（RMVPE）…'); melody = await analyseRecordingRmvpe(await renderCalibrationSong(true, 16000, true, HUMAN_ONSET_LAG)); }
      last = { post: { reference: referenceFrom(melody), scoring: { allowOctave: true, rangeMode: 'full', difficulty: 'standard' }, segments: r.segments }, analysis, melody, scan: null };
      say('正在自動找延遲…');
      await new Promise(resolve => setTimeout(resolve, 30));   // let the status show before the scan
      busy = false;
      $('lc-result').hidden = false;
      auto();
    } catch (error) {
      busy = false; last = null; $('lc-result').hidden = true; controls(); say('分析失敗：' + (error.message || error));
    }
  }

  function score() {
    if (!last) return;
    const ms = Math.max(-500, Math.min(1000, Math.round(Number($('lc-delay').value) / 10) * 10 || 0));
    $('lc-delay').value = String(ms);
    const rhythm = rhythmAt(last.post, last.analysis, ms);
    $('lc-rhythm').textContent = String(rhythm);
    $('lc-at').textContent = translateMessage(`（延遲 ${ms} ms）`);
    if (last.scan) drawCurve(ms);
    controls();
    say(`延遲 ${ms} ms 的進拍是 ${rhythm} 分。可以改延遲再按「重新評分」，或按「自動找」；滿意就按「套用並結束」。`);
  }

  function auto() {
    if (!last) return;
    last.scan = scanDelays(last.post, last.analysis);
    const { best, top, from, to } = last.scan;
    $('lc-delay').value = String(best);
    score();
    if (best <= SCAN_FROM || best >= SCAN_TO || from <= SCAN_FROM || to >= SCAN_TO) say(`自動找到 ${best} ms，但最高分碰到掃描範圍（${SCAN_FROM}～${SCAN_TO} ms）的邊，真正的延遲可能在範圍外；請自己改延遲按「重新評分」比較。`);
    else say(`自動找到 ${best} ms：進拍最高 ${top} 分的範圍是 ${from}～${to} ms，取正中間。滿意就按「套用並結束」。`);
  }

  function drawCurve(at) {
    const { rows, best } = last.scan, W = 600, H = 120, x = ms => 30 + (ms - rows[0].ms) / (rows.at(-1).ms - rows[0].ms) * (W - 40), y = v => H - 18 - v / 100 * (H - 30);
    const ns = 'http://www.w3.org/2000/svg', el = (tag, attrs) => { const e = document.createElementNS(ns, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); return e; };
    const svg = $('lc-curve'); svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    const line = el('polyline', { points: rows.map(r => `${x(r.ms).toFixed(1)},${y(r.rhythm).toFixed(1)}`).join(' '), class: 'lc-line' });
    const parts = [el('line', { x1: 30, y1: y(0), x2: W - 10, y2: y(0), class: 'lc-axis' }), line];
    for (const ms of [100, 200, 300, 400, 500]) if (ms >= rows[0].ms && ms <= rows.at(-1).ms) {
      const t = el('text', { x: x(ms), y: H - 3, class: 'lc-tick' }); t.textContent = `${ms}`; parts.push(t);
    }
    parts.push(el('line', { x1: x(best), y1: 6, x2: x(best), y2: y(0), class: 'lc-best' }));
    if (Number.isFinite(at)) parts.push(el('circle', { cx: x(at), cy: y(rows.find(r => r.ms === at)?.rhythm ?? rhythmAt(last.post, last.analysis, at)), r: 4, class: 'lc-at' }));
    svg.replaceChildren(...parts);
  }

  function apply() {
    if (!last) return;
    const ms = Number($('lc-delay').value);
    options.apply(ms);
    try { localStorage.setItem(STATE_KEY, 'done'); } catch { /* private mode */ }
    window.dispatchEvent(new Event('sign2mv-latency-check'));
    say(`已套用：收音延遲 ${ms} ms，以後唱歌都用這個數字。要重新校正隨時可以再來。`);
    $('latency-check').open = false;
  }

  function skip() {
    if (run) return;
    try { if (localStorage.getItem(STATE_KEY) !== 'done') localStorage.setItem(STATE_KEY, 'skipped'); } catch { /* private mode */ }
    window.dispatchEvent(new Event('sign2mv-latency-check'));
    $('latency-check').open = false;
  }

  $('lc-start').addEventListener('click', () => void start());
  $('lc-stop').addEventListener('click', () => void stop());
  $('lc-rescore').addEventListener('click', score);
  $('lc-delay').addEventListener('keydown', e => { if (e.key === 'Enter') score(); });
  $('lc-auto').addEventListener('click', auto);
  $('lc-apply').addEventListener('click', apply);
  $('lc-skip').addEventListener('click', skip);
  controls();
  // the microphone is opened and closed elsewhere (03): follow it
  let wasReady = options.micReady();
  setInterval(() => { const ready = options.micReady(); if (ready !== wasReady) { wasReady = ready; if (!run && !busy) controls(); } }, 500);
  return {
    controls,
    cancel() { if (run) { cleanup(); drawNotes(); controls(); say('校正已停止（播放器開始播放）。'); } },
    get running() { return !!run || busy; },
    // test and support aid
    summary: () => last && { segments: last.post.segments, voicedSeconds: last.analysis.f0.filter(v => v > 0).length * last.analysis.hop, scan: last.scan && { best: last.scan.best, top: last.scan.top } },
  };
}
