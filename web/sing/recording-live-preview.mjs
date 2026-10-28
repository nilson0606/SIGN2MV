import {mixSettings} from './recording-mix.mjs';
import {remixRecording,wavBlob} from './recording-process.mjs';

// Playback always uses a complete WAV. Coalesce slider changes and serialize
// offline renders; an obsolete render must never replace the current selection.
export function createRenderedRecordingPreview(audio,{settings,onError=()=>{}}) {
  let preview=null,timer=null,running=false,pending=null,serial=0,url=null;
  const updating=value=>{audio.dataset.previewUpdating=String(value);};
  function clear(){
    serial++;preview=null;pending=null;clearTimeout(timer);timer=null;updating(false);
    if(url)URL.revokeObjectURL(url);url=null;
  }
  async function render(){
    if(running||!pending)return;
    running=true;
    const job=pending;pending=null;
    try{
      const {raw,tracks,meta,ms}=job.preview;
      const buffer=await remixRecording(raw,tracks,{...meta,balance:job.balance},ms,{edit:meta.postEdit});
      if(job.serial!==serial)return;
      const next=URL.createObjectURL(wavBlob(buffer)),previous=url;
      const position=Math.min(audio.currentTime,buffer.duration),playing=!audio.paused&&!audio.ended,rate=audio.playbackRate;
      url=next;audio.src=next;audio.currentTime=position;audio.playbackRate=rate;
      // Request play now, rather than in a later loadedmetadata callback: a user
      // pause/selection change during loading can then cancel it normally.
      if(playing)void audio.play().catch(error=>{if(job.serial===serial&&error.name!=='AbortError')onError(error);});
      if(previous)URL.revokeObjectURL(previous);
    }catch(error){if(job.serial===serial)onError(error);}
    finally{
      running=false;
      if(pending&&!timer)void render();
      else if(!pending&&!timer)updating(false);
    }
  }
  function update(){
    if(!preview)return;
    serial++;pending={serial,preview,balance:mixSettings(settings())};updating(true);
    clearTimeout(timer);timer=setTimeout(()=>{timer=null;void render();},180);
  }
  return {set(value){clear();preview=value;},clear,update,dispose:clear};
}
