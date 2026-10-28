import { softenedVoice, vocalEffects, processedVoice, effectsDuration } from './recording-soften.mjs';
import { ScoringTake, validateReference } from './scoring.mjs';
import { balanceGains, createRecordingMix, recordingVolume } from './recording-mix.mjs';
import {repairAudio} from './recording-repair-client.mjs';
// Describe the audio that was actually rendered, never a pending score correction.
export function recordingDelaySuffix(meta) {
  const ms=meta.appliedDelayMs ?? (meta.parentId ? meta.delayMs : undefined);
  return Number.isFinite(ms) ? `${ms>=0?'+':''}${ms}ms` : '';
}
export function delaySeconds(ms) {
  if(!Number.isFinite(ms)||Math.abs(ms)>2000)throw new Error('延時需介於 −2000 與 +2000 ms。');
  return ms/1000;
}
// Ranges use the song clock, independent of microphone latency correction.
export function originalVocalRanges(value=[],duration) {
  if(!Array.isArray(value)||value.length>200)throw Error('原唱區間最多 200 段。');
  if(value.length&&(!Number.isFinite(duration)||duration<=0))throw Error('缺少原唱區間的歌曲長度。');
  const ranges=value.map(r=>({start:r.start,end:r.end,mode:r.mode})).sort((a,b)=>a.start-b.start);
  for(let i=0;i<ranges.length;i++){
    const r=ranges[i];
    if(!Number.isFinite(r.start)||!Number.isFinite(r.end)||r.start<0||r.end-r.start<.1||r.end>duration||!['duet','original'].includes(r.mode))throw Error('原唱區間需在歌曲內，至少 0.1 秒，並選擇播放方式。');
    if(i&&r.start<ranges[i-1].end)throw Error('原唱區間不可重疊，請調整起訖時間。');
  }
  return ranges;
}
export function originalVocalWindows(ranges,segments) {
  const windows=[];
  for(const s of segments)for(const r of ranges){
    const start=Math.max(s.songTime,r.start),end=Math.min(s.songTime+s.duration,r.end);
    if(end<=start)continue;
    const fade=Math.min(.012,(r.end-r.start)/2);
    const points=[start,...[r.start+fade,r.end-fade].filter(t=>t>start&&t<end),end];
    windows.push({source:start,when:s.offset+start-s.songTime,duration:end-start,mode:r.mode,
      envelope:points.map(t=>({time:s.offset+t-s.songTime,gain:Math.max(0,Math.min(1,(t-r.start)/fade,(r.end-t)/fade))}))});
  }
  return windows.sort((a,b)=>a.when-b.when);
}
export function recordedSongTime(segments, offset) {
  const segment=segments.find(s=>offset>=s.offset&&offset<s.offset+s.duration);
  return segment ? segment.songTime+offset-segment.offset : null;
}
export function referenceForRescore(post, current) {
  if (!current) throw new Error('請先載入這首歌的新基準；只更改音高選項還不算載入。');
  const original=post.reference;
  validateReference(current);
  if(current.videoId!==original.videoId)throw new Error('目前載入的是另一支影片，不能用來重評這筆錄音。');
  if((current.pitchShift||0)!==(original.pitchShift||0))throw new Error('請載入與這筆錄音相同 Key 的基準，避免用不同調重評。');
  const duration=ref=>ref.duration??ref.frames.length*ref.step;
  if((original.rangeSeconds!=null&&current.rangeSeconds!=null&&original.rangeSeconds!==current.rangeSeconds)||
    Math.abs(duration(current)-duration(original))>.15||Math.abs(current.frames.length*current.step-original.frames.length*original.step)>.15)
    throw new Error('請載入與錄音當時相同分析範圍的基準，避免改變計分範圍。');
  // Change only the melody. Preserve this take's masks and remix stem identity.
  const selected=structuredClone({...current,masks:original.masks||[]});
  validateReference(selected);
  return selected;
}
export function rescoreRecording(post, ms) {
  const shift=delaySeconds(ms), take=new ScoringTake(post.reference,post.scoring);
  take.begin(0);
  for(const segment of post.segments)take.advance(segment.songTime+segment.duration);
  const end=take.endIndex;
  if(post.audioAnalysis?.source==='decoded-voice-v1') {
    // Move the audio first, then map to the accompaniment timeline, just as remix does.
    for(const {offset,hz} of post.audioAnalysis.samples) {
      const time=recordedSongTime(post.segments,offset-shift);
      if(time!==null)take.sample(time,hz);
    }
  } else for(const {time,hz} of post.samples)take.sample(time-shift,hz);
  // Moving notes must not expand or shrink the performed interval denominator.
  take.endIndex=end;
  return take.result();
}
export function voicePlacement(duration, ms) {
  const shift=delaySeconds(ms), source=Math.max(0,shift), when=Math.max(0,-shift);
  return {source,when,duration:Math.max(0,duration-source)};
}
export function wavBlob(buffer) {
  const channels=buffer.numberOfChannels, frames=buffer.length, bytes=new ArrayBuffer(44+frames*channels*2), view=new DataView(bytes);
  const text=(offset,value)=>{for(let i=0;i<value.length;i++)view.setUint8(offset+i,value.charCodeAt(i));};
  text(0,'RIFF');view.setUint32(4,bytes.byteLength-8,true);text(8,'WAVEfmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,channels,true);view.setUint32(24,buffer.sampleRate,true);view.setUint32(28,buffer.sampleRate*channels*2,true);view.setUint16(32,channels*2,true);view.setUint16(34,16,true);text(36,'data');view.setUint32(40,bytes.byteLength-44,true);
  const data=Array.from({length:channels},(_,i)=>buffer.getChannelData(i));
  for(let i=0;i<frames;i++)for(let c=0;c<channels;c++){const x=Math.max(-1,Math.min(1,data[c][i]));view.setInt16(44+2*(i*channels+c),Math.round(x*(x<0?32768:32767)),true);}
  return new Blob([bytes],{type:'audio/wav'});
}
export function recordingEdit(value={},duration=3600){
  if(value.version!==undefined&&value.version!==1)throw Error('剪輯設定版本不支援。');
  const {start=0,end=null,fadeIn=0,fadeOut=0}=value;
  if(!Number.isFinite(duration)||duration<=0||!Number.isFinite(start)||start<0||start>=duration||
    (end!==null&&(!Number.isFinite(end)||end<=start||end>duration)))throw Error('剪輯起訖需在原始錄音範圍內，結束必須晚於開始。');
  const length=(end??duration)-start;
  if(![fadeIn,fadeOut].every(n=>Number.isFinite(n)&&n>=0&&n<=30)||fadeIn+fadeOut>length+1e-9)throw Error('淡入淡出各需介於 0 與 30 秒，合計不可超過保留長度。');
  return {version:1,start,end,fadeIn,fadeOut};
}
export function editRecordingAudio(buffer,value={}){
  const edit=recordingEdit(value,buffer.duration),rate=buffer.sampleRate;
  const start=Math.round(edit.start*rate),end=edit.end===null?buffer.length:Math.min(buffer.length,Math.round(edit.end*rate)),frames=end-start;
  if(frames<1)throw Error('剪輯範圍太短，至少需保留一個音訊取樣。');
  if(start===0&&end===buffer.length&&!edit.fadeIn&&!edit.fadeOut)return buffer;
  const result=new AudioBuffer({numberOfChannels:buffer.numberOfChannels,length:frames,sampleRate:rate});
  for(let c=0;c<buffer.numberOfChannels;c++){
    const source=buffer.getChannelData(c),out=result.getChannelData(c);
    for(let i=0;i<frames;i++)out[i]=source[start+i]*Math.min(1,edit.fadeIn?i/(edit.fadeIn*rate):1,edit.fadeOut?(frames-1-i)/(edit.fadeOut*rate):1);
  }
  return result;
}
function fixedRecordingMix(context,voice,meta,volume){
  const fixed=meta.fixedMixGains,trim=recordingVolume(volume);
  if(fixed.version!==1||![fixed.voice,fixed.backing].every(n=>Number.isFinite(n)&&n>=0&&n<=16))throw Error('保存的混音音量無效。');
  const input=context.createGain(),v=context.createGain(),b=context.createGain(),ceiling=context.createWaveShaper();
  v.gain.value=fixed.voice*trim.voice/100;b.gain.value=meta.mode==='mix'?fixed.backing*trim.backing/100:0;
  ceiling.curve=Float32Array.from({length:4097},(_,i)=>Math.max(-.98,Math.min(.98,i/2048-1)));
  voice.connect(v);input.connect(b);v.connect(ceiling);b.connect(ceiling);ceiling.connect(context.destination);
  return {input,disconnect(){for(const node of [input,v,b,ceiling])node.disconnect();}};
}
export async function remixRecording(raw, tracks, meta, ms, {softening='off',volume,effects,edit=meta.postEdit,progress}={}) {
  const shift=delaySeconds(ms), rate=raw.sampleRate;
  const sourceDuration=Math.max(raw.duration+Math.max(0,-shift),meta.sourceSeconds??meta.seconds);
  const recipe=vocalEffects(effects,sourceDuration),duration=sourceDuration+effectsDuration(recipe);
  const cuts=recordingEdit(edit,duration);
  if(duration>3600)throw new Error('後處理一次最多一小時。');
  // Analyze dry samples against raw time; placement and backing remain on their clocks.
  const repaired=await repairAudio(raw,recipe,meta,shift,progress);
  const context=new OfflineAudioContext(2,Math.ceil(duration*rate),rate), voice=context.createBufferSource();voice.buffer=repaired;
  const p=voicePlacement(raw.duration,ms);
  const singer=await softenedVoice(context,voice,voice.buffer,p,softening);
  const processed=processedVoice(context,singer,recipe);
  const original=meta.mode==='mix'?meta.post.originalVocals:null;
  const ranges=original?originalVocalRanges(original.ranges,meta.post.reference.duration):[];
  const originalIndex=original?meta.stems?.indexOf(original.stem):-1;
  if(original&&(!['vocals','lead'].includes(original.stem)||originalIndex<0||!tracks[originalIndex]))throw Error('缺少指定區間的原唱音軌，請補建歌曲音軌後重新試合。');
  const windows=originalVocalWindows(ranges,meta.post.segments);
  const voiceGate=context.createGain();processed.output.connect(voiceGate);
  voiceGate.gain.setValueAtTime(1,0);
  for(const w of windows.filter(w=>w.mode==='original')){
    w.envelope.forEach((p,i)=>voiceGate.gain[i?'linearRampToValueAtTime':'setValueAtTime'](1-p.gain,p.time));
    voiceGate.gain.setValueAtTime(1,w.when+w.duration);
  }
  const mix=meta.fixedMixGains?fixedRecordingMix(context,voiceGate,meta,volume):createRecordingMix(context,voiceGate,context.destination,{mode:meta.mode,settings:meta.balance,voiced:()=>false,volume});
  if(p.duration>0)voice.start(p.when,p.source,p.duration);
  const rms=(buffer,time)=>{
    const a=buffer.getChannelData(0),start=Math.max(0,Math.floor(time*rate)),end=Math.min(a.length,start+Math.floor(.1*rate));
    if(time<0||end<=start)return 0;let sum=0;for(let i=start;i<end;i++)sum+=a[i]*a[i];return Math.sqrt(sum/(end-start));
  };
  for(const w of windows){
    const node=context.createBufferSource(),gain=context.createGain();node.buffer=tracks[originalIndex];
    if(node.buffer.duration<w.source+w.duration-.001)throw Error('原唱音軌長度不足，請補建完整音軌。');
    node.connect(gain);gain.connect(mix.input);
    w.envelope.forEach((p,i)=>gain.gain[i?'linearRampToValueAtTime':'setValueAtTime'](p.gain,p.time));
    node.start(w.when,w.source,w.duration);
  }
  for(const segment of meta.post.segments)for(const [index,buffer] of tracks.entries()){
    if(index===originalIndex)continue;
    const length=Math.min(segment.duration,buffer.duration-segment.songTime);
    if(length<=0||segment.songTime<0)continue;
    const node=context.createBufferSource();node.buffer=buffer;node.connect(mix.input);node.start(segment.offset,segment.songTime,length);
  }
  // Automate the same two buses offline. Both accompaniment and harmony share one gain.
  let sampleIndex=0;
  for(let t=0;!meta.fixedMixGains&&t<duration;t+=.1){
    const sourceTime=t+shift, segment=meta.post.segments.find(s=>t>=s.offset&&t<s.offset+s.duration);
    while(sampleIndex+1<meta.post.samples.length&&meta.post.samples[sampleIndex+1].offset<=sourceTime)sampleIndex++;
    const sample=meta.post.samples[sampleIndex];
    const voiced=!!sample?.hz&&Math.abs(sample.offset-sourceTime)<.2;
    const backingRms=segment?Math.hypot(...tracks.map((b,i)=>i===originalIndex&&!windows.some(w=>t>=w.when&&t<w.when+w.duration)?0:rms(b,segment.songTime+t-segment.offset))):0;
    mix.setLevels(balanceGains({mode:meta.mode,settings:meta.balance,voiceRms:rms(raw,sourceTime),backingRms,voiced}),t);
    if(Math.round(t*10)%100===0)await new Promise(resolve=>setTimeout(resolve,0));
  }
  const rendered=await context.startRendering();mix.disconnect();voiceGate.disconnect();processed.disconnect();singer.disconnect();return editRecordingAudio(rendered,cuts);
}
