import {userOption} from './i18n.mjs';
import {selectMediaSource,showMediaSource} from './media-source.mjs';
export const LOCAL_BASE='http://127.0.0.1:4274';
export async function mediaRequest(path,init={}){
  const response=await fetch(LOCAL_BASE+'/session',{signal:AbortSignal.timeout(8000),cache:'no-store'});
  if(!response.ok)throw Error('本機工具未連線。');const session=await response.json();
  if(path.startsWith('/local-media/imports?')&&path.includes('kind=audio')&&!session.features?.includes('local-audio'))throw Error('請更新並重新啟動本機工具，才能匯入 MP3／WAV 音檔。');
  if(!session.features?.includes('local-media'))throw Error('請更新並重新啟動本機工具，才能匯入本機 MV。');
  const r=await fetch(LOCAL_BASE+path,{...init,headers:{...init.headers,'X-Karaoke-Token':session.token},cache:'no-store'});
  const value=await r.json();if(!r.ok)throw Error(value.error||'本機 MV 處理失敗。');return value;
}
export function initializeLocalMedia(load){
  const $=id=>document.getElementById(id);let importing=false,cancelled=false,job=null,controller=null,refreshRevision=0;
  const message=text=>{$('local-media-status').textContent=text;};
  function controls(){for(const id of ['source-kind','local-media-file','local-media-saved','local-media-load','local-media-refresh'])$(id).disabled=importing;$('local-media-cancel').hidden=!importing;$('local-media-controls').dataset.importing=String(importing);window.dispatchEvent(new Event('karaoke-media-import-state'));}
  async function refresh(){const revision=++refreshRevision,kind=$('source-kind').value,value=await mediaRequest('/local-media');if(revision!==refreshRevision||kind!==$('source-kind').value)return;const selected=$('local-media-id').value,rows=value.media.filter(m=>(m.kind==='audio')===(kind==='audio'));$('local-media-saved').replaceChildren(new Option(kind==='audio'?'選擇已匯入的音檔':'選擇已匯入的 MV',''));for(const m of rows)$('local-media-saved').add(userOption(m.title,m.id));if(rows.some(m=>m.id===selected))$('local-media-saved').value=selected;}
  $('source-kind').addEventListener('change',()=>{refreshRevision++;showMediaSource();$('local-media-saved').replaceChildren(new Option('正在讀取…',''));if(['local','audio'].includes($('source-kind').value))void refresh().catch(e=>message(e.message));});
  $('local-media-refresh').addEventListener('click',()=>void refresh().catch(e=>message(e.message)));
  $('local-media-load').addEventListener('click',async()=>{const id=$('local-media-saved').value;if(!id)return message('請先選擇已匯入的檔案。');selectMediaSource(id,document,$('source-kind').value==='audio'?'audio':'video');await load();});
  $('local-media-cancel').addEventListener('click',()=>{cancelled=true;controller?.abort();if(job)void mediaRequest('/local-media/imports/'+job,{method:'DELETE'}).catch(()=>{});message('正在取消匯入…');});
  $('local-media-file').addEventListener('change',async()=>{
    const file=$('local-media-file').files[0];if(!file||importing)return;
    const kind=$('source-kind').value==='audio'?'audio':'video';
    if(!(kind==='audio'?/\.(mp3|wav)$/i:/\.(mp4|m4v|mov|mkv|webm)$/i).test(file.name)){message('檔案格式與所選來源不符，請重新選擇。');$('local-media-file').value='';return;}
    if(file.size>2*1024**3){message('檔案上限 2 GB。');$('local-media-file').value='';return;}
    importing=true;cancelled=false;job=null;controller=new AbortController();controls();
    try{
      message('正在將檔案傳到這台電腦的歌曲庫，請稍候；不會上傳雲端…');
      const created=await mediaRequest('/local-media/imports?'+new URLSearchParams({name:file.name,kind}),{method:'POST',body:file,signal:controller.signal});job=created.id;
      while(true){
        if(cancelled){await mediaRequest('/local-media/imports/'+job,{method:'DELETE'});throw Error('已取消匯入。');}
        const state=await mediaRequest('/local-media/imports/'+job);message(state.message);
        if(state.stage==='ready'){selectMediaSource(state.media.id,document,state.media.kind);await refresh();if(await load())message(`已匯入「${state.media.title}」。可直接播放，或按「準備歌曲基準」使用錄音、評分與分段。`);break;}
        if(['failed','cancelled'].includes(state.stage))throw Error(state.message);
        await new Promise(r=>setTimeout(r,1000));
      }
    }catch(error){message(cancelled?'已取消匯入；原檔保留。':error.message);}
    finally{importing=false;job=null;controller=null;$('local-media-file').value='';controls();}
  });
  showMediaSource();controls();
}
