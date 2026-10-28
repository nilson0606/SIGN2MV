export function pcmHeader(frames,channels,rate){
  const bytes=new ArrayBuffer(44),v=new DataView(bytes),text=(at,s)=>{for(let i=0;i<s.length;i++)v.setUint8(at+i,s.charCodeAt(i));};
  text(0,'RIFF');v.setUint32(4,36+frames*channels*2,true);text(8,'WAVEfmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,channels,true);v.setUint32(24,rate,true);v.setUint32(28,rate*channels*2,true);v.setUint16(32,channels*2,true);v.setUint16(34,16,true);text(36,'data');v.setUint32(40,frames*channels*2,true);return new Blob([bytes],{type:'audio/wav'});
}
export function pcm16(values,from,to){
  const bytes=new ArrayBuffer((to-from)*2),view=new DataView(bytes);
  for(let i=from;i<to;i++){const x=Math.max(-1,Math.min(1,values[i]));view.setInt16((i-from)*2,Math.round(x*(x<0?32768:32767)),true);}
  return new Blob([bytes],{type:'audio/wav'});
}
export class RecordingSampleClock {
  constructor(rate){this.rate=rate;this.ranges=[];}
  frame(time){return Math.round(time*this.rate);}
  resume(time){if(this.ranges.at(-1)?.end===null)return;this.ranges.push({start:this.frame(time),end:null});}
  pause(time){const last=this.ranges.at(-1);if(last?.end===null)last.end=Math.max(last.start,this.frame(time));}
  frames(time){const end=this.frame(time);return this.ranges.reduce((n,r)=>n+Math.max(0,(r.end??end)-r.start),0);}
  portions(start,frames){return this.ranges.flatMap(r=>{const from=Math.max(start,r.start),to=Math.min(start+frames,r.end??Infinity);return to>from?[{from:from-start,to:to-start}]:[];});}
}
export async function createPCMRecorders(context,mic,mixed){
  await context.audioWorklet.addModule(new URL('./recording-pcm-worklet.mjs',import.meta.url));
  const clock=new RecordingSampleClock(context.sampleRate),node=new AudioWorkletNode(context,'recording-pcm',{numberOfInputs:2,numberOfOutputs:1,outputChannelCount:[1]});
  const silent=context.createGain();silent.gain.value=0;node.connect(silent);silent.connect(context.destination);
  mic.connect(node,0,0);mixed.connect(node,0,1);
  let state='inactive',started=false,stopping=false,total=0,previousEnd=null,timeout,disposed=false;
  const observers=new Set();
  const raw={mimeType:'audio/wav',get state(){return state;},start(){},resume(){},pause(){},stop(){}};
  function disconnect(){if(disposed)return;disposed=true;observers.clear();clearTimeout(timeout);mic.disconnect(node);mixed.disconnect(node);node.disconnect();silent.disconnect();node.port.close();}
  function emit(recorder,data){recorder.ondataavailable?.({data});}
  function error(message){mix.onerror?.({error:new Error(message)});}
  const mix={observeSamples(fn){observers.add(fn);return()=>observers.delete(fn);},mimeType:'audio/wav',get state(){return state;},clock,
    start(){if(started)return;started=true;state='recording';clock.resume(context.currentTime);emit(raw,pcmHeader(0,1,context.sampleRate));emit(mix,pcmHeader(0,2,context.sampleRate));},
    resume(){if(stopping)return;state='recording';clock.resume(context.currentTime);},
    pause(){clock.pause(context.currentTime);state='paused';},
    stop(){
      if(stopping)return;stopping=true;clock.pause(context.currentTime);state='inactive';node.port.postMessage('stop');
      timeout=setTimeout(()=>{error('錄音音訊執行緒未回應，已保留接收到的錄音片段。');finish();},5000);
    },
    dispose:disconnect,
    header:()=>pcmHeader(total,2,context.sampleRate),
    voiceHeader:()=>pcmHeader(total,1,context.sampleRate),
    get frames(){return total;}
  };
  let finished=false;
  function finish(){if(finished)return;finished=true;disconnect();mix.onstop?.();raw.onstop?.();}
  node.onprocessorerror=()=>{error('錄音音訊執行緒中斷，已停止錄音。');finish();};
  node.port.onmessage=({data})=>{
    if(data.stopped){
      const expected=clock.frames(context.currentTime);
      if(started&&total!==expected)error(`錄音取樣不連續（${Math.abs(total-expected)} 個取樣），已保留錄音，請重新開啟收音。`);
      finish();return;
    }
    if(previousEnd!==null&&data.start!==previousEnd){error('錄音取樣時間軸中斷，已停止，避免繼續產生錯位。');return;}
    previousEnd=data.start+data.frames;
    for(const {from,to} of clock.portions(data.start,data.frames)){
      for(const observe of observers){try{observe({start:data.start+from,recordedFrame:total,voice:data.voice.slice(from,to)});}catch{/* Diagnostic observers never interrupt recording. */}}
      total+=to-from;emit(raw,pcm16(data.voice,from,to));emit(mix,pcm16(data.mix,from*2,to*2));
    }
    if(total/context.sampleRate>1800&&!stopping)error('單次錄音已達 30 分鐘，已停止並保留錄音。');
  };
  return {recorder:mix,rawRecorder:raw};
}
