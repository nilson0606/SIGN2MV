import {localizedConfirm} from './i18n.mjs';
import {remixRecording,wavBlob} from './recording-process.mjs';

export function recordingReviewKey(ref){
  if(!ref)return null;
  if(ref.cacheId)return JSON.stringify(['cache',ref.cacheId,ref.pitchShift??0]);
  return ref.videoId?JSON.stringify(['video',ref.videoId,ref.pitchShift??0]):null;
}
const songKey=row=>recordingReviewKey(row?.post?.reference);

// Pending whole-song takes stay durable, but are not offered to post-processing.
export function createRecordingReview({store,pause,loadStem,onChanged,isRecording,reference=()=>null}) {
  const $=id=>document.getElementById('recording-review-'+id);
  let allRows=[],rows=[],selected=null,working=false,loading=false,url=null,request=0,scope=null;
  const currentKey=()=>songKey({post:{reference:reference()}});
  const currentSelection=()=>selected&&songKey(selected)===currentKey();
  const status=text=>{$('status').textContent=document.getElementById('recording-status').textContent=text;$('status').hidden=!text;};
  function clear(){
    request++;loading=false;$('audio').pause();$('audio').removeAttribute('src');$('audio').load();$('audio').hidden=true;
    if(url)URL.revokeObjectURL(url);url=null;
  }
  function controls(){
    const locked=working||isRecording()||!currentSelection();
    $('take').disabled=$('mode').disabled=locked;
    $('listen').disabled=locked||loading||!selected?.rawBytes;
    $('save').disabled=locked||!selected?.complete;
    $('delete').disabled=locked||!selected;
    $('delete-song').disabled=locked||!songKey(selected);
  }
  function refresh(all,savedId){
    allRows=all;const nextScope=currentKey();
    if(nextScope!==scope){clear();status('');selected=null;scope=nextScope;}
    rows=scope?all.filter(row=>row.postPending&&!row.segmentTake&&songKey(row)===scope):[];
    const id=rows.some(row=>row.id===savedId)?savedId:selected?.id;
    const next=rows.find(row=>row.id===id)||rows[0]||null;
    if(next?.id!==selected?.id){clear();status('');}selected=next;
    $('take').replaceChildren(...rows.map(row=>new Option(`${row.title} · ${new Date(row.created).toLocaleString()} · ${row.seconds.toFixed(1)} 秒${row.complete?'':' · 未完整結束'}${row.diagnostics?.status==='incomplete'?' · 診斷未完整保存：'+row.diagnostics.error:row.diagnostics?.status==='saved'?' · 診斷已保存':''}`,row.id)));
    if(selected)$('take').value=selected.id;
    document.getElementById('recording-review').hidden=!rows.length;
    controls();
  }
  function referenceChanged(){if(currentKey()!==scope)refresh(allRows);else controls();}
  async function listen(){
    if(working||loading||isRecording()||!currentSelection())return;
    // Legacy takes without a stored correction retain their original 200 ms default.
    const row=selected,mode=$('mode').value,delay=row.recordingDelayMs??200,ref=row.post.reference;
    if(mode==='mix'&&!ref.hasPreview)throw Error('沒有已保存的伴樂，請補建音軌或選「純人聲」。');
    clear();pause();const token=request,cancelled=()=>token!==request||isRecording()||songKey(row)!==currentKey();loading=true;controls();status('正在準備試聽…');
    let context;
    try{
      const blob=await store.blob(row,'voice');if(cancelled())return;
      if(!blob.size)throw Error('無法讀取人聲錄音。');
      if(mode==='voice'){
        url=URL.createObjectURL(blob);$('audio').src=url;$('audio').hidden=false;await $('audio').play();
        if(!cancelled())status('正在播放原始人聲錄音，不加入伴樂、不套用音量平衡或延時校正。滿意後按「存到錄音後處理」。');
        return;
      }
      context=new AudioContext({sampleRate:48000,sinkId:{type:'none'}});
      const raw=await context.decodeAudioData(await blob.arrayBuffer()),tracks=[];if(cancelled())return;
      if(mode==='mix')for(const stem of ['accompaniment',...(ref.vocalMode==='lead'?['backing']:[])]){
        const bytes=await loadStem(ref,stem);if(cancelled())return;
        const buffer=await context.decodeAudioData(bytes);if(cancelled())return;
        if(buffer.duration<Math.max(...row.post.segments.map(s=>s.songTime+s.duration))-.15)throw Error('伴樂長度不足，請補建完整音軌。');
        tracks.push(buffer);
      }
      const audio=await remixRecording(raw,tracks,{...row,mode},delay);if(cancelled())return;
      url=URL.createObjectURL(wavBlob(audio));$('audio').src=url;$('audio').hidden=false;await $('audio').play();
      if(!cancelled())status(`正在試聽${mode==='mix'?'人聲＋伴樂／和音':'純人聲'} · 校正 ${delay} ms。滿意後按「存到錄音後處理」。`);
    }catch(e){if(token===request){clear();throw e;}}
    finally{if(context)await context.close().catch(()=>{});if(token===request)loading=false;controls();}
  }
  async function save(){
    if(working||isRecording()||!currentSelection()||!selected.complete)return;
    const row=selected;working=true;clear();controls();
    try{await store.save({...row,postPending:false});await onChanged(row.id);status('已存到錄音後處理。');window.dispatchEvent(new CustomEvent('karaoke-recording-saved',{detail:{cacheId:row.post.reference.cacheId}}));}
    finally{working=false;controls();}
  }
  async function remove(){
    if(working||isRecording()||!currentSelection())return;
    const row=selected;
    if(!localizedConfirm(`刪除待確認錄音「${row.title} · ${new Date(row.created).toLocaleString()}」？此版錄音與人聲將刪除，無法復原。`))return;
    working=true;clear();pause();controls();
    try{await store.delete(row.id);await onChanged();status('已刪除此版待確認錄音。');}
    finally{working=false;controls();}
  }
  async function removeSong(){
    if(working||isRecording()||!currentSelection())return;
    const row=selected,key=songKey(row);if(!key)return;
    working=true;controls();status('正在讀取要清除的待確認錄音清單…');
    let removed=0,failed=0,processed=0;
    try{
      const targets=(await store.list()).filter(r=>r.postPending&&!r.segmentTake&&songKey(r)===key);
      if(isRecording()||key!==currentKey())return;
      if(!targets.length){await onChanged();status('這首歌已沒有待確認錄音。');return;}
      if(!localizedConfirm(`刪除「${row.title}」同一 Key 的全部 ${targets.length} 筆待確認錄音？\n\n只刪除這首的待確認整首錄音與人聲；其他歌曲、其他 Key、分段錄音及已存到錄音後處理的成品都保留。\n刪除後無法復原。`)){status('已取消清除，錄音保留。');return;}
      clear();pause();
      status(`正在清除這首的 ${targets.length} 筆待確認錄音…`);
      for(const target of targets){
        if(isRecording())break;
        try{await store.delete(target.id);removed++;}catch{failed++;}
        status(`正在清除待確認錄音：${++processed}／${targets.length} 筆，已刪除 ${removed} 筆${failed?`，${failed} 筆失敗`:''}…`);
      }
      status(`已處理 ${processed}／${targets.length} 筆，正在更新錄音清單…`);await onChanged();
      const remaining=targets.length-removed;
      status(`已刪除這首的 ${removed} 筆待確認錄音。${remaining?`尚有 ${remaining} 筆${failed?'未能刪除，請重試':'因開始錄音而保留'}。`:'清除完成，這首此 Key 的待確認整首錄音已全部清空。'}`);
    }finally{working=false;controls();}
  }
  for(const [id,fn]of [['listen',listen],['save',save],['delete',remove],['delete-song',removeSong]])$(id).onclick=()=>Promise.resolve().then(fn).catch(e=>status(e.message));
  $('take').onchange=()=>{clear();selected=rows.find(row=>row.id===$('take').value)||null;controls();status('已選取待確認錄音，可先試聽。');};
  $('mode').onchange=()=>{clear();controls();status('試聽內容已變更，請按「試聽這一版」。');};
  $('audio').onplay=()=>{if(isRecording()||working){clear();controls();return;}pause();for(const media of document.querySelectorAll('audio,video'))if(media!==$('audio'))media.pause();};
  document.addEventListener('play',event=>{if(event.target instanceof HTMLMediaElement&&event.target!==$('audio')){clear();controls();}},true);
  window.addEventListener('pagehide',clear);
  return {refresh,controls,clear,referenceChanged};
}
