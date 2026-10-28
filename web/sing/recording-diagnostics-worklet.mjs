// Diagnostic branch only. Never connected to the speakers with audible gain.
class CaptureCompareProbe extends AudioWorkletProcessor {
  constructor(){
    super();this.size=Math.round(sampleRate/4);this.used=0;this.channels=[];this.blocks=[];
    this.port.onmessage=({data})=>{if(data==='finish'){this.flush();this.done=true;this.port.postMessage({flushed:true});}};
  }
  flush(){
    if(!this.used)return;
    const channels=this.channels.map(x=>x.slice(0,this.used));
    this.port.postMessage({start:this.start,frames:this.used,channels,blocks:this.blocks},channels.map(x=>x.buffer));
    this.used=0;this.channels=[];this.blocks=[];
  }
  process(inputs,outputs){
    if(this.done)return false;
    const channels=inputs[0]||[],frames=outputs[0][0].length;
    this.blocks.push({start:currentFrame,frames,channels:channels.length});
    for(let c=this.channels.length;c<Math.min(channels.length,8);c++)this.channels.push(new Float32Array(this.size));
    for(let i=0;i<frames;i++){
      if(!this.used)this.start=currentFrame+i;
      for(let c=0;c<this.channels.length;c++)this.channels[c][this.used]=channels[c]?.[i]??0;
      if(++this.used===this.size)this.flush();
      if(!this.used&&i+1<frames){
        for(let c=0;c<Math.min(channels.length,8);c++)this.channels.push(new Float32Array(this.size));
        this.blocks.push({start:currentFrame+i+1,frames:frames-i-1,channels:channels.length});
      }
    }
    return true;
  }
}
registerProcessor('recording-diagnostics',CaptureCompareProbe);
