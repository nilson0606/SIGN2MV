// Gain planning is independent of microphone pitch/scoring data.
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
export function recordingVolume(value = {}) {
  const level = x => Number.isFinite(x) ? clamp(x, 0, 200) : 100;
  return { voice: level(value.voice), backing: level(value.backing) };
}
export function mixSettings(value = {}) {
  const level = (x, fallback) => Number.isFinite(x) ? clamp(x, 0, 200) : fallback;
  return { manual: value.manual === true, voice: level(value.voice, 70), backing: level(value.backing, 30) };
}
export function balanceGains({ voiceRms = 0, backingRms = 0, voiced = false, mode = 'mix', settings = {} } = {}) {
  const setup = mixSettings(settings), limit = setup.manual ? 3 : 6;
  // Avoid compensating silence/noise; return smoothly to the chosen base gain.
  const correction = (rms, eligible) => eligible && Number.isFinite(rms) && rms > .008 ? clamp(20*Math.log10(.18/rms), -limit, limit) : 0;
  const voiceDb = correction(voiceRms, voiced), backingDb = correction(backingRms, true);
  const voiceBase = setup.manual ? setup.voice/100 : mode === 'mix' ? .75 : 1;
  const backingBase = mode !== 'mix' ? 0 : setup.manual ? setup.backing/100 : .45;
  return { voice: voiceBase * 10**(voiceDb/20), backing: backingBase * 10**(backingDb/20), voiceDb, backingDb };
}
export function createRecordingMix(context, mic, destination, { mode, settings, voiced, volume }) {
  const trim = recordingVolume(volume);
  const config = mixSettings(settings), voiceMeter = context.createAnalyser(), backingMeter = context.createAnalyser();
  voiceMeter.fftSize = backingMeter.fftSize = 2048;
  const voiceGain = context.createGain(), backingGain = context.createGain(), compressor = context.createDynamicsCompressor(), ceiling = context.createWaveShaper();
  compressor.threshold.value = -2; compressor.knee.value = 0; compressor.ratio.value = 20; compressor.attack.value = .003; compressor.release.value = .15;
  // Compressor handles sustained peaks; the final ceiling catches brief overshoots.
  ceiling.curve = Float32Array.from({length:4097},(_,i)=>clamp(i/2048-1,-.98,.98));
  mic.connect(voiceMeter); voiceMeter.connect(voiceGain); voiceGain.connect(compressor);
  backingMeter.connect(backingGain); backingGain.connect(compressor); compressor.connect(ceiling); ceiling.connect(destination);
  const initial = balanceGains({mode,settings:config}); voiceGain.gain.value=initial.voice*trim.voice/100; backingGain.gain.value=initial.backing*trim.backing/100;
  const voiceSamples = new Float32Array(2048), backingSamples = new Float32Array(2048);
  const rms = (meter, samples) => { meter.getFloatTimeDomainData(samples); return Math.sqrt(samples.reduce((sum,x)=>sum+x*x,0)/samples.length); };
  function update() {
    const levels=balanceGains({voiceRms:rms(voiceMeter,voiceSamples),backingRms:rms(backingMeter,backingSamples),voiced:voiced(),mode,settings:config});
    for(const [node,target] of [[voiceGain,levels.voice*trim.voice/100],[backingGain,levels.backing*trim.backing/100]]) {
      node.gain.setTargetAtTime(target,context.currentTime,target < node.gain.value ? .3 : .8);
    }
    return levels;
  }
  return { input:backingMeter, update, settings:config, setLevels(levels,time) {
    voiceGain.gain.setTargetAtTime(levels.voice*trim.voice/100,time,.3);
    backingGain.gain.setTargetAtTime(levels.backing*trim.backing/100,time,.3);
  }, disconnect() {
    mic.disconnect(voiceMeter);
    for(const node of [voiceMeter,backingMeter,voiceGain,backingGain,compressor,ceiling])node.disconnect();
  }};
}
