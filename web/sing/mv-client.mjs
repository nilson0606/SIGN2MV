const BASE='http://127.0.0.1:4274',$=id=>document.getElementById('mv-'+id);
async function request(route,options={}){
  let session;
  try{const res=await fetch(BASE+'/session',{signal:AbortSignal.timeout(8000)});if(!res.ok)throw Error();session=await res.json();}catch{throw Error('請先啟動本機唱錄工具，再製作 MV。');}
  const res=await fetch(BASE+route,{...options,headers:{'X-Karaoke-Token':session.token,...options.headers},signal:AbortSignal.timeout(options.body?180000:120000)});
  if(!res.ok){const data=await res.json().catch(()=>({}));throw Error(data.error||(res.status===404?'請更新並重新啟動本機工具，才能製作 MV。':'MV 請求失敗。'));}return res;
}
export function createMV({beforePlay=()=>{}}={}){
  let source=null,busy=false,active=null,url=null,filename='MV.mp4';
  const say=text=>{$('status').textContent=text;};
  function controls(){for(const id of ['title','artist'])$(id).disabled=busy;$('generate').disabled=busy||!source;$('cancel').disabled=!busy||!active;}
  function clearVideo(){$('video').pause();$('video').removeAttribute('src');$('video').load();$('result').hidden=true;if(url)URL.revokeObjectURL(url);url=null;}
  function open({title,blob,label=title}){
    $('panel').hidden=false;$('panel').open=true;$('panel').scrollIntoView({behavior:'smooth',block:'center'});
    if(busy){say('目前 MV 正在製作，請先完成或取消，再更換來源。');return false;}
    if(!(blob instanceof Blob)||!blob.size)throw Error('沒有可用的翻唱音檔。');
    source={blob,label};$('source').textContent='翻唱來源：'+label;$('title').value=[...title].slice(0,60).join('');clearVideo();$('progress').hidden=true;say('填寫歌名與翻唱者，再按「開始製作翻唱 MV」。');controls();return true;
  }
  $('generate').addEventListener('click',async()=>{
    if(busy||!source)return;
    const title=$('title').value.trim(),artist=$('artist').value.trim();
    if(!title||!artist){say('請填寫歌名與翻唱者。');$(title?'artist':'title').focus();return;}
    const snapshot=source;busy=true;active=null;clearVideo();controls();$('progress').hidden=false;$('progress').value=0;say('正在將選取音檔交給本機製作…');
    try{
      let state=await(await request('/mv/jobs?'+new URLSearchParams({title,artist}),{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:snapshot.blob})).json();active=state.id;controls();
      while(!['ready','failed','cancelled'].includes(state.stage)){
        say(`${state.message} ${state.progress??0}%`);$('progress').value=state.progress??0;
        await new Promise(r=>setTimeout(r,1000));state=await(await request('/mv/jobs/'+active)).json();
      }
      if(state.stage!=='ready'){say(state.message);return;}
      say('MV 已保存，正在載入預覽…');$('progress').value=100;
      const blob=await(await request('/mv/jobs/'+active+'/result')).blob();url=URL.createObjectURL(blob);filename=state.filename||'MV.mp4';$('video').src=url;$('result').hidden=false;say('MV 已完成。保存位置：'+state.path);
      window.dispatchEvent(new Event('mv-saved'));
    }catch(e){say(e.message);}finally{busy=false;active=null;controls();}
  });
  $('cancel').addEventListener('click',async()=>{if(!active)return;$('cancel').disabled=true;try{await request('/mv/jobs/'+active,{method:'DELETE'});say('已取消 MV 製作。');}catch(e){say(e.message);controls();}});
  $('download').addEventListener('click',()=>{if(url){const a=document.createElement('a');a.href=url;a.download=filename;a.click();}});
  $('video').addEventListener('play',beforePlay);
  window.addEventListener('mv-library-deleted',({detail})=>{if(detail.names.includes(filename)){clearVideo();say('這份 MV 已從本機刪除，可使用音檔重新製作。');}});
  $('panel').addEventListener('toggle',()=>{if(!$('panel').open)$('video').pause();});
  window.addEventListener('pagehide',()=>{clearVideo();});controls();
  return {open,pause:()=>$('video').pause()};
}
