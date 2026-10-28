// SIGN2MV: "製作 MV" hands the selected finished recording to the MV workspace.
// The recording is saved as a render of its song, then the shell switches tabs.
const BASE='/sr',$=id=>document.getElementById(id);
async function session(){
  const res=await fetch(BASE+'/session',{signal:AbortSignal.timeout(8000),cache:'no-store'});
  if(!res.ok)throw Error('SIGN2MV 伺服器未回應，請重新開啟。');return res.json();
}
export function createMV(){
  let busy=false;
  async function open({videoId,recordingId='',title,blob,mode='full'}){
    if(busy)return false;
    if(!(blob instanceof Blob)||!blob.size)throw Error('沒有可用的翻唱音檔。');
    if(!videoId)throw Error('找不到這筆錄音的歌曲，無法製作 MV。');
    busy=true;
    try{
      const {token}=await session();
      const res=await fetch(BASE+'/renders?'+new URLSearchParams({videoId,title,recordingId}),{method:'POST',headers:{'X-Karaoke-Token':token,'Content-Type':'application/octet-stream'},body:blob,signal:AbortSignal.timeout(180000)});
      const data=await res.json().catch(()=>({}));
      if(!res.ok)throw Error(data.error||'無法把錄音交給 MV 工作區。');
      window.parent?.postMessage({type:'sign2mv:open-mv',songId:data.song_id,renderId:data.id,mode:mode==='quick'?'quick':'full'},location.origin);
      return true;
    }finally{busy=false;}
  }
  return {open,pause(){}};
}
