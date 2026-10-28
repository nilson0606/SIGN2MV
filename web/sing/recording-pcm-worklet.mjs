// Both lanes are sampled by the same render quantum; UI scheduling never stamps
// individual audio packets. Absolute sample positions survive delayed delivery.
class RecordingPCM extends AudioWorkletProcessor {
  constructor(){
    super();this.capacity=Math.round(sampleRate/4);this.used=0;this.start=null;
    this.voice=new Float32Array(this.capacity);this.mix=new Float32Array(this.capacity*2);
    this.port.onmessage=({data})=>{if(data==='stop'){this.flush();this.port.postMessage({stopped:true});this.done=true;}};
  }
  flush(){
    if(!this.used)return;
    const voice=this.voice.slice(0,this.used),mix=this.mix.slice(0,this.used*2);
    this.port.postMessage({start:this.start,frames:this.used,voice,mix},[voice.buffer,mix.buffer]);this.used=0;this.start=null;
  }
  process(inputs,outputs){
    if(this.done)return false;
    const frames=outputs[0]?.[0]?.length||128;
    for(let i=0;i<frames;i++){
      if(this.start===null)this.start=currentFrame+i;
      const mic=inputs[0]||[],mixed=inputs[1]||[];let voice=0;
      for(const channel of mic)voice+=channel[i]||0;
      this.voice[this.used]=mic.length?voice/mic.length:0;
      this.mix[this.used*2]=mixed[0]?.[i]||0;this.mix[this.used*2+1]=(mixed[1]||mixed[0])?.[i]||0;
      if(++this.used===this.capacity)this.flush();
    }
    return true;
  }
}
registerProcessor('recording-pcm',RecordingPCM);
