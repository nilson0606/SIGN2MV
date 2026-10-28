import {repairEnabled,repairSettings} from './recording-repair.mjs';
const cached=new WeakMap();
export async function repairAudio(raw,settings,meta,shift,progress=()=>{}){
  if(!repairEnabled(settings))return raw;
  const normalized=repairSettings(settings),key=JSON.stringify([normalized,normalized.pitchCorrection.target==='reference'?{shift,reference:meta.post?.reference,segments:meta.post?.segments}:null]);
  let entries=cached.get(raw);if(!entries){entries=new Map();cached.set(raw,entries);}
  if(entries.has(key))return entries.get(key);
  const promise=new Promise((resolve,reject)=>{
    const worker=new Worker(new URL('./recording-repair-worker.mjs',import.meta.url),{type:'module'}),timer=setTimeout(()=>finish(Error('人聲處理逾時，請先用片段或降低處理強度。')),600000);
    function finish(error,result){clearTimeout(timer);worker.terminate();if(error){entries.delete(key);reject(error);}else resolve(result);}
    worker.onerror=()=>finish(Error('人聲處理無法啟動，請重新整理頁面。'));
    worker.onmessage=({data})=>{
      if(data.error)return finish(Error(data.error));
      if(data.result){const audio=new AudioBuffer({numberOfChannels:raw.numberOfChannels,length:raw.length,sampleRate:raw.sampleRate});data.result.channels.forEach((channel,i)=>audio.copyToChannel(channel,i));if(normalized.cleanup.noise&&!data.result.noiseLearned)progress('沒有足夠的無人聲底噪片段，降噪略過；其餘效果保留。');return finish(null,audio);}
      progress(`${data.phase} ${data.percent}%…`);
    };
    const channels=Array.from({length:raw.numberOfChannels},(_,i)=>raw.getChannelData(i).slice());
    worker.postMessage({channels,rate:raw.sampleRate,settings:normalized,meta:{post:{reference:meta.post?.reference,segments:meta.post?.segments}},shift},channels.map(x=>x.buffer));
  });
  // Only two full dry renders (A and B) are retained for each selected source.
  if(entries.size>=2)entries.delete(entries.keys().next().value);entries.set(key,promise);return promise;
}
