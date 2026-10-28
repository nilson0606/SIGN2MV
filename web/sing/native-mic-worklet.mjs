class LocalMicProcessor extends AudioWorkletProcessor {
 constructor(options){
  super();const requested=options?.processorOptions?.prebufferFrames;
  // Recording needs reserve for delayed/batched 20 ms packets, not just
  // clock drift. Keep legacy monitoring's explicitly requested short buffer.
  this.prebufferFrames=[960,1920].includes(requested)?requested:5760;
  this.buffer=new Float32Array(48000);this.read=0;this.write=0;this.count=0;
  this.started=false;this.failed=false;this.phase=0;this.previous=0;this.rate=1;
  this.target=this.prebufferFrames-480;this.average=this.target;this.rendered=0;
  this.port.onmessage=({data})=>{
   if(data?.streamPort){this.streamPort=data.streamPort;this.streamPort.onmessage=({data})=>this.receive(data);}
   else this.receive(data);
  };
 }
 receive(a){
  if(this.failed||!(a instanceof Float32Array))return;
  if(this.count+a.length>12000){this.fail('本機收音累積延遲過大，已停止，請重新開啟。');return;}
  for(const sample of a){
   if(!Number.isFinite(sample)){this.fail('本機收音資料無效，已停止。');return;}
   this.buffer[this.write]=sample;this.write=(this.write+1)%this.buffer.length;
  }
  this.count+=a.length;
 }
 fail(message){
  if(this.failed)return;
  this.failed=true;this.streamPort?.close();this.port.postMessage({error:message});
 }
 process(inputs,outputs){
  const out=outputs[0]?.[0];if(!out)return true;
  if(!this.started&&this.count>=this.prebufferFrames){
   this.started=true;this.previous=this.buffer[this.read];this.port.postMessage({ready:true});
  }
  if(!this.started||this.failed){out.fill(0);return true;}
  // Ignore the normal 20 ms packet sawtooth. Independent device/render clocks
  // can differ even at nominally 48 kHz; keep the reservoir bounded by smoothly
  // resampling within 0.5%, rather than dropping/repeating whole samples.
  this.average+=(this.count-this.average)*.02;
  if(this.rendered>=48000){
   const error=this.average-this.target,deadband=64;
   const correction=Math.sign(error)*Math.max(0,Math.abs(error)-deadband)/48000;
   const desired=1+Math.max(-.005,Math.min(.005,correction));
   this.rate+=(desired-this.rate)*.02;
  }
  for(let i=0;i<out.length;i++){
   const exact=this.rate===1&&this.phase===0;
   if(this.count<(exact?1:4)){
    // A real stall must not silently insert zeros, resume late and shift all
    // following singing. Stop once and let the UI preserve an incomplete take.
    out.fill(0,i);this.fail('本機收音資料中斷，已停止並保留錄音片段；請重新開啟收音。');return true;
   }
   const b=this.buffer[this.read];
   if(exact)out[i]=b;
   else{
    const a=this.previous,c=this.buffer[(this.read+1)%this.buffer.length],d=this.buffer[(this.read+2)%this.buffer.length],t=this.phase;
    out[i]=b+.5*t*(c-a+t*(2*a-5*b+4*c-d+t*(3*(b-c)+d-a)));
   }
   this.phase+=this.rate;
   while(this.phase>=1){this.previous=this.buffer[this.read];this.read=(this.read+1)%this.buffer.length;this.count--;this.phase--;}
  }
  this.rendered+=out.length;
  return true;
 }
}
registerProcessor('local-microphone',LocalMicProcessor);
