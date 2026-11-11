// TEMPORARY (11-12): find a freeze of the SIGN2MV window (Edge app) during the audio-shift preview and
// apply. While running it notes media events and timings; when the page's timer or its frames stop for
// more than a second it sends what happened just before to the server, which writes it to
// logs\server.log ("diag: ..."). Remove once the cause is found.
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
    video: state(), recent: ring.slice() });
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
  active = { note, stop() { clearInterval(timer); cancelAnimationFrame(raf); if (video) for (const ev of events) video.removeEventListener(ev, onEvent); } };
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
