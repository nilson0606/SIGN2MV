export function youtubeId(value) {
  try {
    const u = new URL(value);
    if (u.protocol !== 'https:' && u.protocol !== 'http:') return null;
    const host = u.hostname.toLowerCase();
    let id;
    if (host === 'youtu.be') id = u.pathname.split('/')[1];
    else if (['youtube.com', 'www.youtube.com', 'm.youtube.com'].includes(host)) {
      id = u.pathname === '/watch' ? u.searchParams.get('v') : /^(?:\/shorts\/|\/embed\/)([^/]+)/.exec(u.pathname)?.[1];
    }
    return /^[\w-]{11}$/.test(id || '') ? id : null;
  } catch { return null; }
}

export function noteOf(hz) {
  if (!(hz > 0) || !Number.isFinite(hz)) return null;
  const midi = 69 + 12 * Math.log2(hz / 440);
  const rounded = Math.round(midi);
  const name = ['C', 'C♯', 'D', 'D♯', 'E', 'F', 'F♯', 'G', 'G♯', 'A', 'A♯', 'B'][((rounded % 12) + 12) % 12];
  return { midi, name: name + (Math.floor(rounded / 12) - 1), cents: Math.round((midi - rounded) * 100) };
}

// Bump when detector behavior changes so an explicit rescore refreshes its cache.
export const PITCH_DETECTOR_VERSION = 2;

// Single melodic source only. Keep confident YIN results; recover breathy or
// changing-amplitude voices with a band-limited, energy-normalized second pass.
export function detectPitch(input, sampleRate) {
  if (!input.length || !Number.isFinite(sampleRate) || !(sampleRate > 0)) return { hz: null, rms: 0, confidence: 0 };
  const result = yinPitch(input, sampleRate);
  if (result.hz !== null || !(result.rms >= 0.006)) return result;
  return correlatedPitch(input, sampleRate, result.rms);
}

// YIN-style cumulative normalized difference.
function yinPitch(input, sampleRate) {
  const stride = Math.max(1, Math.floor(sampleRate / 16000));
  const n = Math.min(2048, Math.floor(input.length / stride));
  const data = new Float32Array(n);
  let mean = 0;
  for (let i = 0; i < n; i++) { data[i] = input[i * stride]; mean += data[i]; }
  mean /= n;
  let energy = 0;
  for (let i = 0; i < n; i++) { data[i] -= mean; energy += data[i] * data[i]; }
  const rms = Math.sqrt(energy / n);
  const rate = sampleRate / stride;
  const maxLag = Math.min(Math.ceil(rate / 65), Math.floor(n / 2));
  const minLag = Math.max(2, Math.floor(rate / 1000));
  if (rms < 0.006 || maxLag <= minLag) return { hz: null, rms, confidence: 0 };
  const diff = new Float32Array(maxLag + 1);
  const window = n - maxLag;
  let cumulative = 0;
  diff[0] = 1;
  for (let tau = 1; tau <= maxLag; tau++) {
    let d = 0;
    for (let j = 0; j < window; j++) { const v = data[j] - data[j + tau]; d += v * v; }
    cumulative += d;
    diff[tau] = cumulative ? d * tau / cumulative : 1;
  }
  let tau = minLag;
  for (; tau < maxLag; tau++) {
    if (diff[tau] < 0.15) {
      while (tau + 1 <= maxLag && diff[tau + 1] < diff[tau]) tau++;
      break;
    }
  }
  if (tau >= maxLag) return { hz: null, rms, confidence: 0 };
  const denominator = 2 * (2 * diff[tau] - diff[tau - 1] - diff[tau + 1]);
  const refined = tau + (denominator ? (diff[tau + 1] - diff[tau - 1]) / denominator : 0);
  const hz = rate / refined;
  return { hz: hz >= 65 && hz <= 1000 ? hz : null, rms, confidence: Math.max(0, 1 - diff[tau]) };
}

function correlatedPitch(input, sampleRate, rms) {
  const stride = Math.max(1, Math.floor(sampleRate / 16000));
  const n = Math.min(2048, Math.floor(input.length / stride)), rate = sampleRate / stride;
  const minLag = Math.max(2, Math.floor(rate / 1000)), maxLag = Math.min(Math.ceil(rate / 65), Math.floor(n / 2));
  const missing = { hz: null, rms, confidence: 0 };
  if (maxLag <= minLag) return missing;

  // 1.5 kHz Butterworth low-pass BEFORE decimation. This is an analysis copy:
  // neither the recorded PCM, microphone volume nor the analysis clock changes.
  const w = 2 * Math.PI * Math.min(1500, sampleRate / 4) / sampleRate;
  const c = Math.cos(w), a = Math.sin(w) / Math.SQRT2, a0 = 1 + a;
  const b0 = (1 - c) / (2 * a0), b1 = 2 * b0, a1 = -2 * c / a0, a2 = (1 - a) / a0;
  const data = new Float32Array(n);
  let x1 = input[0], x2 = x1, y1 = x1, y2 = x1, mean = 0;
  for (let i = 0; i < n * stride; i++) {
    const x = input[i], y = b0 * x + b1 * x1 + b0 * x2 - a1 * y1 - a2 * y2;
    x2 = x1; x1 = x; y2 = y1; y1 = y;
    if (i % stride === 0) { data[i / stride] = y; mean += y; }
  }
  mean /= n;
  let energy = 0;
  for (let i = 0; i < n; i++) { data[i] -= mean; energy += data[i] * data[i]; }
  if (Math.sqrt(energy / n) < 0.006) return missing;

  const correlation = new Float32Array(maxLag + 2);
  for (let lag = 0; lag <= maxLag + 1; lag++) {
    let cross = 0, power = 0;
    for (let i = 0; i < n - lag; i++) {
      cross += data[i] * data[i + lag];
      power += data[i] * data[i] + data[i + lag] * data[i + lag];
    }
    correlation[lag] = power ? 2 * cross / power : 0;
  }
  // Skip the zero-lag lobe. A noise-shaped hump is not a repeating waveform.
  const peaks = []; let crossedZero = false, strongest = 0;
  for (let lag = 1; lag <= maxLag; lag++) {
    if (correlation[lag] < 0) crossedZero = true;
    if (crossedZero && lag >= minLag && correlation[lag] > 0 && correlation[lag] >= correlation[lag - 1] && correlation[lag] > correlation[lag + 1]) {
      peaks.push(lag); strongest = Math.max(strongest, correlation[lag]);
    }
  }
  // Require strong periodicity; choose the first near-best peak to avoid
  // mistaking two/three periods for the fundamental. No reference-note snapping.
  const lag = peaks.find(t => correlation[t] >= Math.max(0.85, strongest * 0.93));
  if (lag === undefined) return missing;
  const denominator = 2 * (2 * correlation[lag] - correlation[lag - 1] - correlation[lag + 1]);
  const refined = lag + (denominator ? (correlation[lag + 1] - correlation[lag - 1]) / denominator : 0);
  const hz = rate / refined;
  return { hz: hz >= 65 && hz <= 1000 ? hz : null, rms, confidence: correlation[lag] };
}

// Read a JSON object without evaluating any code received from another site.
export function playerResponse(html) {
  const marker = /(?:var\s+)?ytInitialPlayerResponse\s*=\s*/g.exec(html);
  if (!marker) return null;
  const start = marker.index + marker[0].length;
  if (html[start] !== '{') return null;
  let depth = 0, quoted = false, escaped = false;
  for (let i = start; i < html.length; i++) {
    const c = html[i];
    if (quoted) {
      if (escaped) escaped = false;
      else if (c === '\\') escaped = true;
      else if (c === '"') quoted = false;
    } else if (c === '"') quoted = true;
    else if (c === '{') depth++;
    else if (c === '}' && --depth === 0) {
      try { return JSON.parse(html.slice(start, i + 1)); } catch { return null; }
    }
  }
  return null;
}

export function alignedTime(playerSeconds, compensationMs) {
  return Math.max(0, playerSeconds - compensationMs / 1000);
}
