import {guideStems,keyLabel} from './song-key.mjs';

// Owns shifted audio for every video transport: native Play, whole-song start,
// segment preview/loop/recording, pause, buffering and seeking.
export function createKeyPlayback({player,loadStem,mode,status}) {
  let current=null,serial=0;
  function pause(c=current){for(const node of c?.nodes||[]){try{node.stop();}catch{}node.disconnect();}if(c)c.nodes=[];}
  function clear(){
    serial++;const c=current;current=null;if(!c)return;pause(c);c.context?.close().catch(()=>{});
    if(c.wasMuted)c.player.mute?.();else c.player.unMute?.();
  }
  async function load(reference){
    clear();if(!reference?.pitchShift)return;
    const request=serial,p=player(),c=current={player:p,reference,wasMuted:!!p?.isMuted?.(),nodes:[],buffers:new Map(),ready:false};
    p?.pauseVideo?.();p?.mute?.();
    try{
      c.context=new AudioContext();c.gain=c.context.createGain();c.gain.connect(c.context.destination);
      for(const stem of ['accompaniment','vocals',...(reference.vocalMode==='lead'?['backing']:[])]){
        const bytes=await loadStem(reference,stem);if(request!==serial)return;
        const buffer=await c.context.decodeAudioData(bytes);if(request!==serial)return;
        if(buffer.duration<reference.duration-.15)throw Error('變調音軌長度不足，請重新建立此 Key 版本。');
        c.buffers.set(stem,buffer);
      }
      c.ready=true;status(`${keyLabel(reference.pitchShift)} · 影片原聲靜音，播放同步變調音軌。`);
    }catch(error){if(request===serial){pause(c);p?.pauseVideo?.();p?.mute?.();throw error;}}
  }
  function sync(state=player()?.getPlayerState?.(),time=player()?.getCurrentTime?.()||0){
    const c=current;if(!c)return;
    // A click on the native YouTube speaker cannot mix the original key back in.
    if(!c.player.isMuted?.())c.player.mute?.();
    if(state!==1){pause(c);return;}
    if(!c.ready){c.player.pauseVideo?.();status('變調音軌尚未就緒，請等待載入完成。');return;}
    if(c.context.state!=='running'){
      if(!c.resuming)c.resuming=c.context.resume().then(()=>{c.resuming=null;if(current===c)sync();}).catch(()=>{c.resuming=null;status('請再按播放，允許變調音軌播放。');});
      return;
    }
    if(c.player.getPlaybackRate?.()!==undefined&&c.player.getPlaybackRate()!==1)c.player.setPlaybackRate?.(1);
    c.gain.gain.value=Math.max(0,Math.min(1,(c.player.getVolume?.()??100)/100));
    const selected=mode();
    if(c.nodes.length&&c.mode===selected&&Math.abs(c.time+c.context.currentTime-c.clock-time)<.12)return;
    pause(c);c.mode=selected;c.time=time;c.clock=c.context.currentTime;
    for(const stem of guideStems(c.reference,selected)){
      const buffer=c.buffers.get(stem);if(time>=buffer.duration)continue;
      const node=c.context.createBufferSource();node.buffer=buffer;node.connect(c.gain);node.start(c.clock,Math.max(0,time));c.nodes.push(node);
    }
  }
  return {load,clear,sync,active:()=>!!current,ready:()=>!!current?.ready};
}
