import {keyShift} from './song-key.mjs';
import { detectPitch, PITCH_DETECTOR_VERSION } from './audio.mjs';
// Centered windows on the decoded recording clock, independent of live UI timestamps.
export function analyzeRecordedVoice(audio, sampleRate, progress=()=>{}, pitchShift=0) {
  if(!(audio instanceof Float32Array)||!Number.isFinite(sampleRate)||sampleRate<8000)throw new Error('錄音取樣資料無效。');
  const factor=2 ** (keyShift(pitchShift)/12);
  const hop=Math.round(sampleRate*.02),size=Math.round(sampleRate*.128),half=Math.floor(size/2),window=new Float32Array(size),samples=[];
  for(let center=0;center<audio.length;center+=hop){
    window.fill(0);const start=Math.max(0,center-half),end=Math.min(audio.length,center-half+size);
    window.set(audio.subarray(start,end),Math.max(0,half-center));
    const hz=detectPitch(window,sampleRate/factor).hz;
    samples.push({offset:center/sampleRate,hz:hz===null?null:hz*factor});
    if(samples.length%100===0)progress(Math.round(100*center/audio.length));
  }
  progress(100);return {version:1,source:'decoded-voice-v1',detectorVersion:PITCH_DETECTOR_VERSION,...(pitchShift?{pitchShift}:{}),duration:audio.length/sampleRate,samples};
}
if(typeof WorkerGlobalScope!=='undefined'&&self instanceof WorkerGlobalScope){
  self.onmessage=({data})=>{try{const result=analyzeRecordedVoice(data.audio,data.sampleRate,progress=>self.postMessage({progress}),data.pitchShift || 0);self.postMessage({result});}catch(error){self.postMessage({error:error.message});}};
}
