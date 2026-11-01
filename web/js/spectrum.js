// Live frequency bars for whichever player inside `root` is playing (old AI cover "頻譜動畫").
// Each audio/video element is routed through Web Audio once, the first time it plays; the
// sound itself is unchanged. Bars use a log frequency scale (40 Hz – 16 kHz) with falling peaks.
const routed = new WeakMap();
let ctx = null;

function connect(media) {
  if (routed.has(media)) return routed.get(media);
  const AC = window.AudioContext || window.webkitAudioContext;
  try {
    const src = new URL(media.currentSrc || media.src, location.href);
    if (!AC || src.origin !== location.origin) return null;   // another site's audio would go silent
    ctx = ctx || new AC();
    const node = ctx.createMediaElementSource(media);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 4096;
    analyser.smoothingTimeConstant = 0.72;
    node.connect(analyser);
    analyser.connect(ctx.destination);
    const entry = { analyser, data: new Uint8Array(analyser.frequencyBinCount) };
    routed.set(media, entry);
    return entry;
  } catch (e) {
    routed.set(media, null);   // never try again for this player; playback is unaffected
    return null;
  }
}

export function spectrum(root, { bars = 72, height = 64 } = {}) {
  const canvas = document.createElement('canvas');
  canvas.className = 'spectrum';
  canvas.style.height = `${height}px`;
  canvas.setAttribute('aria-hidden', 'true');
  const peaks = new Array(bars).fill(0);
  let active = null;
  let raf = 0;

  function frame() {
    raf = 0;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight || height;
    if (!w) return;
    const dpr = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }
    const g = canvas.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    g.fillStyle = 'rgba(124, 230, 250, 0.07)';
    for (let i = 1; i < 10; i++) g.fillRect(Math.round(w * i / 10), 0, 1, h);
    for (let i = 1; i < 4; i++) g.fillRect(0, Math.round(h * i / 4), w, 1);
    const entry = active && routed.get(active);
    const live = !!(entry && active && !active.paused && !active.ended);
    if (live) entry.analyser.getByteFrequencyData(entry.data);
    const bins = entry ? entry.data.length : 0;
    const nyq = (ctx ? ctx.sampleRate : 44100) / 2;
    const grad = g.createLinearGradient(0, h, 0, 0);
    grad.addColorStop(0, '#0e9cc0');
    grad.addColorStop(1, '#7ce6fa');
    const bw = w / bars;
    let any = false;
    for (let i = 0; i < bars; i++) {
      let v = 0;
      if (live && bins) {
        const f0 = 40 * Math.pow(400, i / bars);
        const f1 = 40 * Math.pow(400, (i + 1) / bars);
        const b0 = Math.max(0, Math.floor(f0 / nyq * bins));
        const b1 = Math.min(bins - 1, Math.max(b0, Math.ceil(f1 / nyq * bins)));
        let m = 0;
        for (let b = b0; b <= b1; b++) if (entry.data[b] > m) m = entry.data[b];
        v = m / 255;
      }
      peaks[i] = v >= peaks[i] ? v : Math.max(0, peaks[i] - 0.012);
      if (v > 0.01 || peaks[i] > 0.01) any = true;
      const bh = v * (h - 6);
      const x = i * bw + 1;
      const ww = Math.max(1, bw - 2);
      if (bh > 0.5) { g.fillStyle = grad; g.fillRect(x, h - bh, ww, bh); }
      if (peaks[i] > 0.01) { g.fillStyle = '#f5b041'; g.fillRect(x, h - peaks[i] * (h - 6) - 3, ww, 2); }
    }
    if (live || any) raf = requestAnimationFrame(frame);   // let the bars fall after a pause, then stop
  }
  const start = () => { if (!raf) raf = requestAnimationFrame(frame); };

  root.addEventListener('play', (e) => {
    const m = e.target;
    if (!(m instanceof HTMLMediaElement)) return;
    if (connect(m)) {
      active = m;
      if (ctx && ctx.state === 'suspended') ctx.resume().catch(() => {});
    }
    start();
  }, true);
  root.addEventListener('pause', start, true);
  root.addEventListener('ended', start, true);
  // While its page is hidden the canvas has no width, so the loop stops (frame() returns early).
  // Start it again when the page shows (size changes) and while the player keeps playing.
  root.addEventListener('timeupdate', start, true);
  if (window.ResizeObserver) new ResizeObserver(start).observe(canvas);
  requestAnimationFrame(frame);
  return canvas;
}
