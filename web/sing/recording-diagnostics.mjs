import {localizedConfirm} from './i18n.mjs';
const base='http://127.0.0.1:4274',key='karaoke.recording-diagnostics.v1';
let enabled=true,busy=0,tokenPromise;
try{enabled=localStorage.getItem(key)!=='off';}catch{}
const $=id=>document.getElementById(id);
const status=text=>{if($('diagnostics-status'))$('diagnostics-status').textContent=text;};
function controls(){if($('diagnostics-enabled'))$('diagnostics-enabled').disabled=busy>0;if($('diagnostics-clear'))$('diagnostics-clear').disabled=busy>0;}
async function request(route,method='GET',data,retry=true){
  tokenPromise??=fetch(base+'/diagnostics/session',{signal:AbortSignal.timeout(4000)}).then(async r=>{if(!r.ok)throw Error('請啟動新版本機工具');return (await r.json()).token;}).catch(e=>{tokenPromise=null;throw e;});
  const token=await tokenPromise;
  const r=await fetch(base+route,{method,headers:{'Content-Type':'application/json','X-Diagnostic-Token':token},body:data===undefined?undefined:JSON.stringify(data),signal:AbortSignal.timeout(8000)});
  if(!r.ok){if(r.status===403){tokenPromise=null;if(retry)return request(route,method,data,false);}let detail;try{detail=(await r.json()).error;}catch{}throw Error(detail||`診斷服務回應 ${r.status}`);}return r.json();
}
export async function refreshDiagnostics(){
  try{const info=await request('/diagnostics');if($('diagnostics-storage'))$('diagnostics-storage').textContent=`本機保留 ${info.count} 次 · ${(info.bytes/1024**2).toFixed(1)} MB · ${info.path}`;}
  catch(e){if($('diagnostics-storage'))$('diagnostics-storage').textContent='診斷未連線：'+e.message;}
}
export function initRecordingDiagnostics(){
  const toggle=$('diagnostics-enabled');if(!toggle)return;toggle.checked=enabled;
  toggle.addEventListener('change',()=>{enabled=toggle.checked;try{localStorage.setItem(key,enabled?'on':'off');}catch{}status(enabled?'待命：只在演唱錄音時收集。':'診斷已關閉，已保存資料仍保留。');});
  $('diagnostics-refresh').addEventListener('click',refreshDiagnostics);
  $('diagnostics-clear').addEventListener('click',async()=>{
    if(busy)return;if(!localizedConfirm('清除所有錄音診斷資料？歌曲、演唱錄音與後處理成品都會保留。'))return;
    busy++;controls();try{const r=await request('/diagnostics','DELETE');status(`已清除 ${r.cleared} 次診斷；錄音與歌曲保留。`);}catch(e){status('未清除：'+e.message);}finally{busy--;controls();await refreshDiagnostics();}
  });
  status(enabled?'待命：只在演唱錄音時收集。':'診斷已關閉，已保存資料仍保留。');refreshDiagnostics();
}
function encode(buffer){const bytes=new Uint8Array(buffer);let s='';for(let i=0;i<bytes.length;i+=8192)s+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(s);}

// Explicit recording lifecycle, not a global getUserMedia / AudioContext patch.
// Diagnostics may affect timing; these are comparison signals, never a repair.
export async function prepareRecordingDiagnostics({context,mic,stream,recorder,meta,native=false}){
  if(!enabled)return null;
  const id=meta.id,tasks=new Set(),cleanup=[],flushes=new Set();
  busy++;controls();status('正在確認診斷可保存…');
  let preparedMedia;
  try{
    await context.audioWorklet.addModule(new URL('./recording-diagnostics-worklet.mjs',import.meta.url));
    if(!native){
      const mime=['audio/webm;codecs=pcm','audio/webm;codecs=opus','audio/webm'].find(x=>MediaRecorder.isTypeSupported(x));
      preparedMedia=new MediaRecorder(stream,mime?{mimeType:mime}:{});
    }
    await request(`/diagnostics/${id}`,'POST',{title:meta.title,recordingId:id,videoId:meta.videoId,input:meta.captureClock?.input,sampleRate:context.sampleRate,formatVersion:2});
    meta.diagnostics={id,version:2,status:'ready'};
  }catch(e){busy--;controls();status('診斷無法準備，尚未開始錄音：'+e.message);throw Error('診斷無法保存，尚未開始錄音。請確認已更新並啟動本機工具：'+e.message);}
  let started=false,recording=false,finished=false,failed='',queue=Promise.resolve(),queuedBytes=0,media,index=0,probeId=0,unsubscribe,probe,mediaDone=Promise.resolve(),finishing;
  function track(p){tasks.add(p);p.finally(()=>tasks.delete(p));return p;}
  let released=false;
  function release(){if(released)return;released=true;unsubscribe?.();cleanup.forEach(fn=>fn());busy--;controls();refreshDiagnostics();}
  function fail(e){if(failed)return;failed=e.message||String(e);meta.diagnostics={id,version:2,status:'incomplete',error:failed};recording=false;try{stopProbe();if(media&&media.state!=='inactive')media.stop();}catch{}status('診斷不完整，演唱錄音仍會繼續：'+failed);}
  function enqueue(route,data,size=0){
    if(failed)return;queuedBytes+=size;if(queuedBytes>16*1024**2){queuedBytes-=size;fail(Error('本機保存太慢，已停止診斷收集'));return;}
    queue=queue.then(()=>failed?undefined:request(route,'POST',data)).catch(fail).finally(()=>{queuedBytes-=size;});
  }
  function send(data,buffers=[]){if(!started||finished||failed)return;try{enqueue(`/diagnostics/${id}/events`,{...data,wall:Date.now(),contextFrame:Math.round(context.currentTime*context.sampleRate),buffers:buffers.map(encode)},buffers.reduce((n,b)=>n+b.byteLength,0));}catch(e){fail(e);}}
  function stopProbe(){
    const p=probe;if(!p)return;probe=null;
    // Disconnect the input immediately; flush only the already collected tail.
    try{mic.disconnect(p.node);}catch{}
    p.finish();
    flushes.add(p.done);p.done.finally(()=>flushes.delete(p.done));
  }
  function startProbe(){
    const current=++probeId,node=new AudioWorkletNode(context,'recording-diagnostics',{numberOfInputs:1,numberOfOutputs:1,outputChannelCount:[1],channelCountMode:'max'}),mute=context.createGain();mute.gain.value=0;
    let resolve,timer;const done=new Promise(r=>resolve=r);let disposed=false;
    const dispose=()=>{if(disposed)return;disposed=true;clearTimeout(timer);node.disconnect();mute.disconnect();node.port.close();resolve();};
    node.port.onmessage=({data})=>{if(data.flushed){dispose();return;}send({kind:'probe',probe:current,start:data.start,frames:data.frames,blocks:data.blocks},data.channels.map(x=>x.buffer));};
    node.onprocessorerror=()=>{dispose();fail(Error('診斷分析節點中斷'));};
    node.connect(mute).connect(context.destination);mic.connect(node);
    probe={node,done,finish(){node.port.postMessage('finish');timer=setTimeout(()=>{send({kind:'event',event:'probe-tail-unconfirmed',probe:current});dispose();fail(Error('診斷分析節點尾端未確認'));},1500);}};
  }
  function startMedia(){
    if(native){send({kind:'event',event:'direct-media-unavailable',reason:'native-input',captureId:meta.captureClock?.nativeCaptureId});return;}
    try{
      media=preparedMedia;mediaDone=new Promise(resolve=>media.addEventListener('stop',resolve,{once:true}));
      media.ondataavailable=e=>{const n=index++;track(e.data.arrayBuffer().then(b=>send({kind:'media',index:n,timecode:e.timecode,mime:media.mimeType},[b])).catch(fail));};
      media.onerror=e=>{send({kind:'event',event:'direct-media-error',message:e.error?.message});fail(Error('直接收音診斷中斷：'+(e.error?.message||'MediaRecorder error')));};media.start(1000);
      send({kind:'event',event:'direct-media-start',mime:media.mimeType});
    }catch(e){send({kind:'event',event:'direct-media-unavailable',reason:e.message});fail(e);}
  }
  const api={
    start(){
      if(recording||finished||failed)return;
      try{
        if(!started){
          started=true;meta.diagnostics.status='recording';
          unsubscribe=recorder.observeSamples(data=>send({kind:'pcm',start:data.start,frames:data.voice.length,recordedFrame:data.recordedFrame},[data.voice.buffer]));
          const state=()=>send({kind:'event',event:'context-state',state:context.state});context.addEventListener('statechange',state);cleanup.push(()=>context.removeEventListener('statechange',state));
          for(const t of stream.getAudioTracks())for(const name of ['mute','unmute','ended']){const fn=()=>send({kind:'event',event:'track-'+name});t.addEventListener(name,fn);cleanup.push(()=>t.removeEventListener(name,fn));}
          const settings=stream.getAudioTracks()[0]?.getSettings?.()||{};delete settings.deviceId;delete settings.groupId;
          send({kind:'event',event:'start',settings,recordingDelayMs:meta.recordingDelayMs});startMedia();
        }else if(media?.state==='paused')media.resume();
        if(failed)return;
        recording=true;startProbe();send({kind:'event',event:'resume'});status('● 錄音診斷中 · 停止錄音後確認保存');
      }catch(e){fail(e);}
    },
    pause(){if(!started||finished||!recording)return;recording=false;stopProbe();if(media?.state==='recording')media.pause();send({kind:'event',event:'pause'});status('錄音暫停，診斷暫停收集。');},
    finish(){if(!finishing)finishing=finish().catch(e=>{fail(e);finished=true;release();return meta.diagnostics;});return finishing;}
  };
  async function finish(){
      if(!started){
        finished=true;
        try{await request(`/diagnostics/${id}/finish`,'POST',{error:'錄音準備已取消',cancelled:true});}catch(e){fail(e);}
        finally{meta.diagnostics.status=failed?'incomplete':'cancelled';release();}return meta.diagnostics;
      }
      api.pause();if(media&&media.state!=='inactive')media.stop();
      let mediaTimer;
      await Promise.race([mediaDone,new Promise(resolve=>{mediaTimer=setTimeout(()=>{fail(Error('直接收音診斷尾端未確認'));resolve();},1500);})]);clearTimeout(mediaTimer);
      await Promise.allSettled([...flushes]);while(tasks.size)await Promise.allSettled([...tasks]);
      send({kind:'event',event:'finish',recordedFrames:recorder.frames,ranges:recorder.clock.ranges});unsubscribe?.();cleanup.forEach(fn=>fn());finished=true;
      await queue;
      try{
        const result=await request(`/diagnostics/${id}/finish`,'POST',{error:failed,recordedFrames:recorder.frames});
        if(!result.saved)fail(Error(result.error||'診斷資料未完整保存'));
        if(!failed)meta.diagnostics={id,version:2,status:'saved',frames:result.frames,finished:Date.now()};
        status(failed?'診斷不完整：'+failed:'診斷已保存 · 待命，不再收集音訊');
      }catch(e){fail(e);status('診斷未完整保存：'+e.message);}finally{release();}
      return meta.diagnostics;
  }
  return api;
}
