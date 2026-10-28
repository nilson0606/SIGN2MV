// Exposes the transport used by scoring, recording, segments and shifted audio.
export function localVideoPlayer(video,id,onState,onError){
  let state=5,destroyed=false;
  const listeners=[];
  const change=value=>{if(!destroyed&&state!==value){state=value;onState(value);}};
  const listen=(name,fn)=>{video.addEventListener(name,fn);listeners.push([name,fn]);};
  listen('playing',()=>change(1));listen('pause',()=>change(video.ended?0:2));listen('ended',()=>change(0));
  listen('waiting',()=>{if(!video.paused)change(3);});listen('seeking',()=>change(3));
  listen('seeked',()=>change(video.paused?2:1));
  listen('error',()=>{change(2);onError('本機媒體無法播放，請重新載入；若已手動刪除檔案，請重新匯入。');});
  return {sourceKind:'local',getVideoData:()=>({video_id:id,title:video.dataset.title||''}),getDuration:()=>video.duration||0,
    getCurrentTime:()=>video.currentTime||0,getPlayerState:()=>state,
    playVideo(){void video.play().catch(error=>{if(!destroyed&&error.name!=='AbortError'){change(2);onError('請按播放器的播放按鈕：'+error.message);}});},
    pauseVideo(){video.pause();if(state!==0)change(2);},seekTo(time){video.currentTime=Math.max(0,Math.min(time,video.duration||time));},
    mute(){video.muted=true;},unMute(){video.muted=false;},isMuted:()=>video.muted,
    getVolume:()=>video.volume*100,setVolume:value=>{video.volume=Math.max(0,Math.min(1,value/100));},
    getPlaybackRate:()=>video.playbackRate,setPlaybackRate:value=>{video.playbackRate=value;},getIframe:()=>video,
    destroy(){destroyed=true;for(const [name,fn]of listeners)video.removeEventListener(name,fn);video.pause();video.removeAttribute('src');video.load();video.hidden=true;}};
}
