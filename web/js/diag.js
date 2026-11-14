// TEMPORARY (11-12): find a freeze of the SIGN2MV window (Edge app) during the audio-shift preview and
// apply. While running it notes media events and timings; when the page's timer or its frames stop for
// more than a second it sends what happened just before to the server, which writes it to
// logs\server.log ("diag: ..."). Remove once the cause is found.
//
// TEMPORARY (11-14), same question, whole app: Nilson saw the window stutter again on the MV page and in the
// library, outside the audio-shift preview, where nothing was being recorded. diagWatch() runs all the
// time in the top window: when its timer or its frames stop for more than 0.3 s it writes one line
// ("kind":"jank") with the page in front, media that is playing (also inside the sing and MV frames)
// and the jobs that are running. At most one line per 5 s (the worst gap and how many there were) and
// 300 lines per page load. Remove together with the rest of this file.
import { bus } from './app-state.js';

const RING = 40;
let active = null;

function send(kind, data) {
  try {
    fetch('/api/diag', {
      method: 'POST', headers: { 'X-SIGN2MV': '1', 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind, at: new Date().toISOString(), ua: navigator.userAgent.slice(-60), ...data }),
      keepalive: true,
    }).catch(() => {});
  } catch { /* never let the diagnosis break the page */ }
}

function memory() {
  const m = performance.memory;
  return m ? Math.round(m.usedJSHeapSize / 1e6) : null;
}

export function diagStart(phase, video) {
  diagStop();
  const t0 = performance.now();
  const s = () => +((performance.now() - t0) / 1000).toFixed(2);
  const ring = [];
  const note = (text) => { ring.push(`${s()} ${text}`); if (ring.length > RING) ring.shift(); };
  const state = () => (video && video.isConnected
    ? { t: +video.currentTime.toFixed(2), paused: video.paused, seeking: video.seeking, rs: video.readyState }
    : { video: 'gone' });
  const report = (what, gapMs) => send('stall', { phase, what, gapMs: Math.round(gapMs), atS: s(), mbJs: memory(),
    hidden: document.hidden, focus: document.hasFocus(), video: state(), recent: ring.slice() });
  // a window that is covered or not in front may stop drawing: note it, so such gaps are not taken for freezes
  const onWin = (e) => note(`window ${e.type} hidden=${document.hidden} focus=${document.hasFocus()}`);
  const winEvents = ['visibilitychange', 'focus', 'blur'];
  for (const ev of winEvents) (ev === 'visibilitychange' ? document : window).addEventListener(ev, onWin);
  const events = ['play', 'playing', 'pause', 'seeking', 'seeked', 'waiting', 'stalled', 'emptied', 'error'];
  const onEvent = (e) => note(`video ${e.type} t=${video.currentTime.toFixed(2)} rs=${video.readyState}`);
  if (video) for (const ev of events) video.addEventListener(ev, onEvent);
  let tick = performance.now();
  const timer = setInterval(() => {
    const now = performance.now();
    // the page itself was stuck (a covered or hidden window only gets its timer once a second: not a stall)
    if (now - tick > 1000 && !document.hidden) report('timer', now - tick);
    tick = now;
  }, 100);
  let frame = performance.now(), raf = 0;
  const loop = () => {
    const now = performance.now();
    if (now - frame > 1000 && !document.hidden) report('frames', now - frame);   // drawing stopped
    frame = now;
    raf = requestAnimationFrame(loop);
  };
  raf = requestAnimationFrame(loop);
  active = { note, stop() {
    clearInterval(timer); cancelAnimationFrame(raf);
    if (video) for (const ev of events) video.removeEventListener(ev, onEvent);
    for (const ev of winEvents) (ev === 'visibilitychange' ? document : window).removeEventListener(ev, onWin);
  } };
  note(`start ${phase} mbJs=${memory()}`);
  send('start', { phase, mbJs: memory(), video: state() });
}

export function diagNote(text, report = false) {
  if (active) active.note(text);
  if (report) send('note', { text, mbJs: memory() });
}

export function diagStop() {
  if (active) { active.stop(); active = null; }
}

const JANK_MS = 300;
const JANK_EVERY_MS = 5000;
const JANK_MAX = 300;
let watching = false;

function playingMedia() {
  const out = [];
  const docs = [document];
  for (const f of document.querySelectorAll('iframe')) {
    try { if (f.contentDocument) docs.push(f.contentDocument); } catch { /* another origin */ }
  }
  for (const d of docs) {
    for (const m of d.querySelectorAll('video, audio')) {
      if (m.paused || m.ended) continue;
      out.push({ tag: m.tagName.toLowerCase(), src: String(m.currentSrc || m.src || '').split('?')[0].split('/').slice(-2).join('/'),
        t: +m.currentTime.toFixed(1), w: m.videoWidth || undefined, muted: m.muted || undefined,
        shown: m.checkVisibility ? m.checkVisibility() : undefined });
    }
  }
  return out.slice(0, 6);
}

export function diagWatch() {
  if (watching) return;
  watching = true;
  let jobs = [];
  bus.addEventListener('jobs', (e) => {
    jobs = (e.detail || []).filter((j) => j.status === 'running' || j.status === 'queued')
      .map((j) => ({ kind: j.kind, lane: j.lane, status: j.status, stage: j.stage || '', pct: j.percent == null ? null : Math.round(j.percent) }));
  });
  const recent = [];
  const note = (text) => { recent.push(`${new Date().toISOString().slice(11, 23)} ${text}`); if (recent.length > 12) recent.shift(); };
  for (const ev of ['focus', 'blur']) window.addEventListener(ev, () => note(`window ${ev}`));
  document.addEventListener('visibilitychange', () => note(`hidden=${document.hidden}`));
  bus.addEventListener('goto', (e) => note(`goto ${e.detail}`));
  document.addEventListener('click', (e) => {
    const b = e.target && e.target.closest ? e.target.closest('button, summary, #tabs button') : null;
    if (b) note(`click ${(b.dataset && b.dataset.page) || (b.textContent || '').trim().slice(0, 16)}`);
  }, true);

  let sent = 0;
  let bucket = null;   // gaps since the last line
  const add = (what, gap) => {
    if (!bucket) {
      bucket = { timer: 0, frames: 0, worst: 0, total: 0, first: new Date().toISOString() };
      setTimeout(flush, JANK_EVERY_MS);
    }
    bucket[what] += 1;
    bucket.worst = Math.max(bucket.worst, Math.round(gap));
    bucket.total += Math.round(gap);
  };
  function flush() {
    const b = bucket;
    bucket = null;
    if (!b || sent >= JANK_MAX) return;
    sent += 1;
    const tab = document.querySelector('#tabs button.active');
    const mvTab = document.querySelector('.mv-tabs .active');
    send('jank', { first: b.first, worstMs: b.worst, totalMs: b.total, timerGaps: b.timer, frameGaps: b.frames,
      page: tab ? tab.dataset.page : '', mvTab: mvTab ? mvTab.textContent.trim() : undefined,
      focus: document.hasFocus(), mbJs: memory(), media: playingMedia(), jobs, recent: recent.slice(), n: sent });
  }
  let tick = performance.now();
  setInterval(() => {
    const now = performance.now();
    if (now - tick > JANK_MS && !document.hidden) add('timer', now - tick);   // the page's own code was stuck
    tick = now;
  }, 50);
  let frame = performance.now();
  const loop = () => {
    const now = performance.now();
    if (now - frame > JANK_MS && !document.hidden) add('frames', now - frame);   // drawing stopped
    frame = now;
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
  send('watch', { mbJs: memory() });
}
