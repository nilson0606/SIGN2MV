const base='http://127.0.0.1:4274';
async function session(signal){
 const r=await fetch(base+'/session',{cache:'no-store',signal});if(!r.ok)throw Error('無法連線本機工具。');
 const s=await r.json();if(!s.features?.includes('native-microphone'))throw Error('請先更新並重新啟動本機工具，才能使用本機相容收音。');return s;
}
export async function nativeInputDevices(){
 const signal=AbortSignal.timeout(25000),s=await session(signal);
 const r=await fetch(base+'/microphone/devices',{headers:{'X-Karaoke-Token':s.token},signal});
 const data=await r.json();if(!r.ok)throw Error(data.error||'無法取得本機麥克風清單。');return data.devices;
}
export async function openNativeMicrophone(context,{deviceId='',signal,onError}){
 const controller=new AbortController();const abort=()=>controller.abort();signal.addEventListener('abort',abort,{once:true});if(signal.aborted)abort();
 let worker,node,destination,silent,stopped=false,started=false,resolveReady,rejectReady,resolveMeta,rejectMeta;
 const monitors=new Set();let speaker=null,speakerSequence=0;
 const ready=new Promise((resolve,reject)=>{resolveReady=resolve;rejectReady=reject;});
 const metadata=new Promise((resolve,reject)=>{resolveMeta=resolve;rejectMeta=reject;});metadata.catch(()=>{});
 // Attach a handler immediately: setup can fail before the ready promise is awaited.
 ready.catch(()=>{});
 const timer=setTimeout(()=>{rejectReady(Error('本機收音啟動逾時。'));controller.abort();},30000);
 // Recording owns its connections and must flush before releasing them.
 // Stop only this capture's compatibility stream and silent render branch.
 const stop=()=>{if(stopped)return;stopped=true;speaker?.disconnect();clearTimeout(timer);controller.abort();signal.removeEventListener('abort',abort);for(const monitor of [...monitors])monitor.disconnect();worker?.terminate();if(node){node.port.onmessage=null;node.port.close();if(destination)node.disconnect(destination);if(silent)node.disconnect(silent);}silent?.disconnect();destination?.stream.getTracks().forEach(t=>t.stop());};
 const fail=error=>{rejectReady(error);rejectMeta(error);const notify=started&&!stopped;stop();if(notify)onError(error);};
 controller.signal.addEventListener('abort',()=>fail(new DOMException('已取消','AbortError')),{once:true});
 try{
  const s=await session(controller.signal);
  await context.audioWorklet.addModule(new URL('./native-mic-worklet.mjs',import.meta.url));
  node=new AudioWorkletNode(context,'local-microphone',{numberOfInputs:0,numberOfOutputs:1,outputChannelCount:[1]});
  destination=context.createMediaStreamDestination();node.connect(destination);
  // Keep the worklet on this render clock, even before the analysis/recording
  // consumers attach. The MediaStream is only for legacy track/monitor APIs.
  silent=context.createGain();silent.gain.value=0;node.connect(silent);silent.connect(context.destination);
  node.port.onmessage=({data})=>{if(data.error)fail(Error(data.error));if(data.ready)resolveReady();};
  node.onprocessorerror=()=>fail(Error('本機收音音訊執行緒中斷，請重新開啟收音。'));
  worker=new Worker(new URL('./native-microphone.mjs',import.meta.url),{type:'module'});
  worker.onmessage=({data})=>{if(data.meta)resolveMeta(data.meta);if(data.error)fail(Error(data.error));};
  worker.onerror=()=>fail(Error('本機音訊背景傳輸中斷，請重新開啟收音。'));
  const channel=new MessageChannel();node.port.postMessage({streamPort:channel.port2},[channel.port2]);
  worker.postMessage({type:'start',token:s.token,deviceId,port:channel.port1},[channel.port1]);
  const meta=await metadata;
  if(meta.sampleRate!==context.sampleRate||meta.channels!==1)throw Error('本機收音取樣率不相容。');
  if(typeof meta.capturePolicy==='string')node.nativeCapturePolicy=meta.capturePolicy;
  if(typeof meta.captureId==='string')node.nativeCaptureId=meta.captureId;
  await ready;clearTimeout(timer);if(controller.signal.aborted)throw new DOMException('已取消','AbortError');started=true;
  async function createMonitorSource(outputContext,onMonitorError){
   if(stopped)throw Error('本機收音已停止。');
   if(outputContext.sampleRate!==meta.sampleRate)throw Error('歌聲輸出取樣率不相容。');
   await outputContext.audioWorklet.addModule(new URL('./native-mic-worklet.mjs',import.meta.url));
   if(stopped||outputContext.state==='closed')throw Error('本機收音已停止。');
   // Legacy browser monitoring also needs two packets of jitter headroom.
   // Modern helpers use createSpeakerMonitor and bypass this browser buffer.
   const monitorNode=new AudioWorkletNode(outputContext,'local-microphone',{numberOfInputs:0,numberOfOutputs:1,outputChannelCount:[1],processorOptions:{prebufferFrames:1920}});
   const id=crypto.randomUUID(),channel=new MessageChannel();monitorNode.port.postMessage({streamPort:channel.port2},[channel.port2]);
   worker.postMessage({type:'attach',id,port:channel.port1},[channel.port1]);
   const monitor={node:monitorNode,disconnect(){monitors.delete(monitor);worker.postMessage({type:'detach',id});monitorNode.port.onmessage=null;monitorNode.disconnect();monitorNode.port.close();}};
   monitorNode.port.onmessage=({data})=>{if(data.error){monitor.disconnect();onMonitorError(Error(data.error));}};
   monitors.add(monitor);return monitor;
  }
  async function speakerCommand(value){
   const response=await fetch(base+'/microphone/monitor',{method:'POST',headers:{'Content-Type':'application/json','X-Karaoke-Token':s.token},body:JSON.stringify({...value,captureId:meta.captureId}),signal:AbortSignal.timeout(6500),keepalive:true});
   const result=await response.json();if(!response.ok)throw Error(result.error||'本機喇叭控制失敗。');return result;
  }
  async function speakerDevices(){
   const response=await fetch(base+'/microphone/outputs',{headers:{'X-Karaoke-Token':s.token},signal:AbortSignal.any([controller.signal,AbortSignal.timeout(25000)])});
   const result=await response.json();if(!response.ok)throw Error(result.error||'無法取得喇叭清單。');return result.devices;
  }
  function createSpeakerMonitor({deviceId,volume,onError}){
   if(stopped)throw Error('本機收音已停止。');
   speaker?.disconnect();
   let closed=false,opened=false,heartbeatTimer,volumeTimer,latestVolume=volume,revision=0,busy=false;
   const set=enabled=>speakerCommand({action:'set',sequence:++speakerSequence,enabled,deviceId,volume:latestVolume});
   const failed=error=>{if(!closed){handle.disconnect();onError(error);}};
   const handle={
    disconnect(){
     if(closed)return;closed=true;clearTimeout(heartbeatTimer);clearTimeout(volumeTimer);
     if(speaker===handle){speaker=null;set(false).catch(()=>{});}
    },
    setVolume(value){
     latestVolume=value;clearTimeout(volumeTimer);
     if(!opened||closed)return;
     const current=++revision;
     volumeTimer=setTimeout(async()=>{
      busy=true;
      try{await set(true);}catch(error){if(current===revision)failed(error);}
      finally{if(current===revision)busy=false;}
     },80);
    },
    ready:null
   };
   speaker=handle;
   async function heartbeat(){
    if(closed)return;
    if(!busy){
     const sequence=speakerSequence;
     try{
      const status=await speakerCommand({action:'keepalive',sequence});
      if(!closed&&sequence===speakerSequence&&status.state!=='running')throw Error(status.error||'本機喇叭已停止。');
     }catch(error){if(!closed&&sequence===speakerSequence)failed(error);}
    }
    if(!closed)heartbeatTimer=setTimeout(heartbeat,1000);
   }
   handle.ready=set(true).then(()=>{
    if(closed||stopped)return;
    opened=true;if(latestVolume!==volume)handle.setVolume(latestVolume);
    heartbeatTimer=setTimeout(heartbeat,1000);
   });
   return handle;
  }
  return{stream:destination.stream,source:node,label:meta.label,stop,createMonitorSource,monitorSampleRate:meta.sampleRate,
   ...(s.features?.includes('native-speaker-output')&&typeof meta.captureId==='string'?{createSpeakerMonitor,speakerDevices}:{})};
 }catch(error){stop();throw error;}
}

// Own fetch, byte framing and worklet delivery off the UI thread. A long page
// task must not hold up microphone packets. Ports go straight to AudioWorklets.
export function installNativeTransport(scope) {
 let controller;const ports=new Map();
 const close=()=>{controller?.abort();for(const port of ports.values())port.close();ports.clear();};
 scope.onmessage=({data})=>{
  if(data.type==='stop'){close();return;}
  if(data.type==='attach'){ports.set(data.id,data.port);return;}
  if(data.type==='detach'){ports.get(data.id)?.close();ports.delete(data.id);return;}
  if(data.type!=='start'||controller)return;
  controller=new AbortController();ports.set('capture',data.port);
  (async()=>{
   const response=await fetch(base+'/microphone/stream',{method:'POST',headers:{'Content-Type':'application/json','X-Karaoke-Token':data.token},body:JSON.stringify({deviceId:data.deviceId}),signal:controller.signal});
   if(!response.ok){const e=await response.json();throw Error(e.error||'本機收音無法啟動。');}
   const reader=response.body.getReader();let pending=new Uint8Array(0),meta;
   while(true){
    const {done,value}=await reader.read();if(done)throw Error('本機收音連線已中斷。');
    const bytes=new Uint8Array(pending.length+value.length);bytes.set(pending);bytes.set(value,pending.length);pending=bytes;
    if(!meta){
     const newline=pending.indexOf(10);
     if(newline<0){if(pending.length>4096)throw Error('本機收音回應過大。');continue;}
     if(newline>4096)throw Error('本機收音回應過大。');
     meta=JSON.parse(new TextDecoder().decode(pending.subarray(0,newline)));pending=pending.slice(newline+1);
     if(meta.sampleRate!==48000||meta.channels!==1||typeof meta.label!=='string')throw Error('本機收音格式不相容。');
     scope.postMessage({meta});
    }
    const size=pending.length-pending.length%4;
    if(size){
     const pcm=new Float32Array(pending.buffer.slice(pending.byteOffset,pending.byteOffset+size));pending=pending.slice(size);
     const consumers=[...ports.values()];
     for(let i=0;i<consumers.length;i++){const copy=i===consumers.length-1?pcm:pcm.slice();consumers[i].postMessage(copy,[copy.buffer]);}
    }
   }
  })().catch(error=>{if(!controller.signal.aborted)scope.postMessage({error:error.message});close();});
 };
}
if(typeof WorkerGlobalScope!=='undefined'&&self instanceof WorkerGlobalScope)installNativeTransport(self);
