import { pitchDifference } from './scoring.mjs';
export const SOLFEGE = ['Do', 'Re', 'Mi', 'Fa', 'Sol'];
export const FIVE_NOTES = [261.6256, 293.6648, 329.6276, 349.2282, 391.9954];
const median = values => { const sorted = [...values].sort((a, b) => a - b), i = Math.floor(sorted.length / 2); return sorted.length % 2 ? sorted[i] : (sorted[i - 1] + sorted[i]) / 2; };

export class FiveNoteMeasurement {
  constructor(start, octave = 0) {
    this.notes = FIVE_NOTES.map((hz, i) => ({ hz: hz * 2 ** octave, time: start + i * 1.2, candidate: null, hit: null }));
  }
  sample(time, hz) {
    if (!Number.isFinite(hz) || hz < 65 || hz > 1000) return;
    for (const note of this.notes) {
      if (note.hit !== null || time < note.time - .25 || time > note.time + .95) continue;
      if (Math.abs(pitchDifference(hz, note.hz, true)) > 45) { note.candidate = null; continue; }
      if (note.candidate !== null && time - note.candidate >= .04 && time - note.candidate <= .18) note.hit = note.candidate - note.time;
      else note.candidate = time;
    }
  }
  result() {
    const hits = this.notes.filter(n => n.hit !== null).map(n => n.hit);
    if (hits.length < 4) return { ok: false, count: hits.length, reason: '至少需要辨識到 4 個穩定音符，請檢查收音後重試。' };
    const delay = median(hits), spread = Math.max(...hits) - Math.min(...hits);
    if (spread > .25) return { ok: false, count: hits.length, reason: '五個音的時間差太分散，暫不建議套用。請保持同一節奏再試。' };
    const ms = Math.round(delay * 1000 / 10) * 10;
    return { ok: true, count: hits.length, ms, spreadMs: Math.round(spread * 1000) };
  }
}

export function createCalibration(options) {
  const $ = id => document.getElementById(id);
  let measurement = null, ticker, nodes = [], suggestion = null, epoch = 0;
  let playbackContext = null, outputQueue = Promise.resolve();
  function output(context, sinkId) {
    outputQueue = outputQueue.catch(() => {}).then(() => context.state !== 'closed' ? context.setSinkId(sinkId) : undefined);
    return outputQueue;
  }
  function stop(message) {
    epoch++; clearInterval(ticker); measurement = null;
    for (const oscillator of nodes) { try { oscillator.stop(); oscillator.disconnect(); } catch {} }
    nodes = [];
    if (playbackContext) { const previous=playbackContext; playbackContext=null; output(previous,{type:'none'}).catch(() => {}); } $('cal-start').disabled = false; $('cal-stop').disabled = true;
    $('cal-mode').disabled = false; $('cal-octave').disabled = false;
    [...$('cal-notes').children].forEach(n => n.classList.remove('active'));
    if (message) { suggestion = null; $('cal-apply').disabled = true; $('cal-status').textContent = message; }
  }
  $('cal-start').addEventListener('click', async () => {
    stop(); suggestion = null; $('cal-apply').disabled = true;
    if (!options.micReady()) { $('cal-status').textContent = '請先開啟麥克風，再開始五音測試。'; return; }
    options.beforeStart();
    const context = options.context(), current = epoch;
    $('cal-start').disabled = true; $('cal-stop').disabled = false; $('cal-mode').disabled = true; $('cal-octave').disabled = true;
    try {
      await outputQueue.catch(() => {}); if (current !== epoch) return;
      if (typeof context.setSinkId === 'function' && context.sinkId?.type === 'none') {
        playbackContext=context; await output(context,'');
      }
      if (current !== epoch) return;
      await context.resume(); if (current !== epoch) return;
      const start = context.currentTime + 1.5, wallStart = performance.now() / 1000 + 1.5;
      measurement = new FiveNoteMeasurement(wallStart, Number($('cal-octave').value));
      for (const [i, note] of measurement.notes.entries()) {
        const oscillator = context.createOscillator(), gain = context.createGain(), at = start + i * 1.2;
        oscillator.type = 'sine'; oscillator.frequency.value = note.hz;
        gain.gain.setValueAtTime(0, at); gain.gain.linearRampToValueAtTime(.12, at + .025);
        gain.gain.setValueAtTime(.12, at + .55); gain.gain.linearRampToValueAtTime(0, at + .6);
        oscillator.connect(gain); gain.connect(context.destination); oscillator.start(at); oscillator.stop(at + .65);
        oscillator.onended = () => { gain.disconnect(); oscillator.disconnect(); }; nodes.push(oscillator);
      }
      const mode = $('cal-mode').value;
      $('cal-status').textContent = mode === 'sing' ? '準備…跟著 Do Re Mi Fa Sol 唱，可高／低八度。' : '準備…讓麥克風收到五個測試音，不用唱。';
      ticker = setInterval(() => {
        if (!measurement) return;
        const time = performance.now() / 1000;
        [...$('cal-notes').children].forEach((node, i) => {
          node.classList.toggle('active', time >= measurement.notes[i].time && time < measurement.notes[i].time + .65);
          node.classList.toggle('matched', measurement.notes[i].hit !== null);
        });
        if (time >= wallStart + 5 * 1.2) {
          const result = measurement.result(); stop();
          if (!result.ok) { $('cal-status').textContent = result.reason; return; }
          suggestion = result.ms; $('cal-apply').disabled = false;
          $('cal-status').textContent = `辨識 ${result.count}/5 音，建議補償 ${result.ms >= 0 ? '+' : ''}${result.ms} ms，時間差散布 ${result.spreadMs} ms。${mode === 'sing' ? '包含跟唱反應時間。' : '包含播放到收音的往返延遲。'}與 YouTube 播放路徑可能不同，套用後可再手動微調。`;
        }
      }, 40);
    } catch { stop('測試音無法播放，請重新開啟麥克風後再試。'); }
  });
  for (const id of ['cal-mode', 'cal-octave']) $(id).addEventListener('change', () => stop('測試設定已變更，請重新測試。'));
  $('cal-stop').addEventListener('click', () => stop('已停止五音測試，未改動補償。'));
  $('cal-apply').addEventListener('click', () => {
    if (suggestion === null) return;
    $('offset').value = String(suggestion); $('offset').dispatchEvent(new Event('input'));
    $('cal-status').textContent += ' 已套用到時間補償。'; $('cal-apply').disabled = true;
  });
  return { sample: (time, hz) => measurement?.sample(time, hz), cancel: () => stop('五音測試已停止；需要時可重新測試。'), active: () => measurement !== null };
}
