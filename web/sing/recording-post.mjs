import {localizedConfirm} from './i18n.mjs';
import { recordingTuningSuffix } from './recording-tune.mjs';
import {isPostRecording} from './recording-store.mjs';
import {createMV} from './mv-client.mjs';
import {createMVLibrary} from './mv-library-client.mjs';
import { createRecordingAudition } from './recording-audition.mjs';
import { recordingScenes, initialRecordingEffects, matchingRecordingScene, recordingEmotions, matchingRecordingEmotion } from './recording-scenes.mjs';
import { PITCH_DETECTOR_VERSION } from './audio.mjs';
import { softeningProfile, recordingSofteningSuffix, recordingEffectsSuffix, vocalEffects, reverbProfile, reverbSpacePresets } from './recording-soften.mjs';
import { scoringProfile } from './scoring.mjs';
import { recordingVolume } from './recording-mix.mjs';
import {repairSettings} from './recording-repair.mjs';
import { rescoreRecording, remixRecording, wavBlob, delaySeconds, referenceForRescore, recordingDelaySuffix, recordingEdit } from './recording-process.mjs';
const $=id=>document.getElementById(id), BASE='http://127.0.0.1:4274';
async function localRequest(path,body) {
  let response;
  try {
    const session=await fetch(BASE+'/session',{signal:AbortSignal.timeout(8000)});
    if(!session.ok)throw new Error();const info=await session.json();
    if(body&&!info.features?.includes('recording-mp3'))throw new Error('請更新並重新啟動本機工具，才能轉 MP3。');
    response=await fetch(BASE+path,{method:body?'POST':'GET',headers:{'X-Karaoke-Token':info.token,...(body?{'Content-Type':'application/octet-stream'}:{})},body,signal:AbortSignal.timeout(body?180000:30000)});
  }catch(error){throw new Error(error.message.includes('MP3')?error.message:'無法連接本機工具，請啟動後再試。');}
  if(!response.ok){const error=await response.json().catch(()=>({}));throw new Error(error.error||'所需音軌不存在，請還原相同版本的歌曲音軌。');}
  return response;
}
async function recordedAnalysis(blob, progress, pitchShift=0) {
  const context=new AudioContext({sampleRate:16000,sinkId:{type:'none'}});
  let audio,sampleRate;
  try {
    const decoded=await context.decodeAudioData(await blob.arrayBuffer());sampleRate=decoded.sampleRate;
    audio=new Float32Array(decoded.length);
    for(let c=0;c<decoded.numberOfChannels;c++){const channel=decoded.getChannelData(c);for(let i=0;i<audio.length;i++)audio[i]+=channel[i]/decoded.numberOfChannels;}
  } finally {await context.close();}
  return new Promise((resolve,reject)=>{
    const worker=new Worker(new URL('./recording-analysis.mjs',import.meta.url),{type:'module'});
    const timer=setTimeout(()=>{worker.terminate();reject(new Error('歌聲分析逾時，請重試。'));},600000);
    const done=(error,value)=>{clearTimeout(timer);worker.terminate();error?reject(error):resolve(value);};
    worker.onerror=()=>done(new Error('歌聲分析無法啟動，請更新頁面後重試。'));
    worker.onmessage=({data})=>{if(data.error)done(new Error(data.error));else if(data.result)done(null,data.result);else progress(data.progress);};
    worker.postMessage({audio,sampleRate,pitchShift},[audio.buffer]);
  });
}
export function createRecordingPost({store,stop,pause,download,onDelete,reference=()=>null,isRecording=()=>false}) {
  let rows=[],selected=null,busy=false,url=null,statusTarget='post-status',audition=null,previewSources=null;
  const backingRoute=(row,stem)=>`/library/${row.post.reference.cacheId}/${stem}`;
  const mv=createMV({beforePlay:()=>{clearAudio();pause();mvLibrary?.stopPreview();}});
  const mvLibrary=createMVLibrary({beforePlay:()=>{clearAudio();mv.pause();pause();}});
  const status=text=>{$(statusTarget).textContent=text;};
  function clearAudio(){audition?.stop();const a=$('post-audio');a.pause();a.removeAttribute('src');a.load();a.hidden=true;if(url)URL.revokeObjectURL(url);url=null;}
  function effectLabels(){
    emotionLabels();
    for(const id of ['noise','deess','breath','pitch-correction']){const value=$('post-'+id).value;$('post-'+id+'-value').textContent=value==='0'?'0%（關閉）':value+'%';}
    const activeRepair=[['noise','降噪'],['deess','齒音'],['breath','呼吸'],['pitch-correction','音準']].filter(([id])=>Number($('post-'+id).value)>0).map(([id,label])=>`${label} ${$('post-'+id).value}%`);
    $('post-repair-summary').textContent=activeRepair.length?activeRepair.join(' · '):'降噪 · 齒音 · 呼吸聲 · 音準（全部關閉）';
    $('post-deess-hz-value').textContent=$('post-deess-hz').value+' Hz';$('post-pitch-speed-value').textContent=$('post-pitch-speed').value+' ms';
    $('post-reverb-space-help').textContent=reverbSpacePresets[$('post-reverb-space').value].help;
    for(const band of ['low','mid','high'])$('post-eq-'+band+'-value').textContent=$('post-eq-'+band).value+' dB';
    $('post-reverb-value').textContent=$('post-reverb').value+'%';
    $('post-reverb-decay-value').textContent=$('post-reverb-decay').value+' 秒';
    $('post-reverb-predelay-value').textContent=$('post-reverb-predelay').value+' ms';
    for(const [id,unit] of [['reverb-brightness',''],['reverb-width','%'],['echo-amount','%'],['echo-time',' ms'],['echo-repeats',' 次'],['echo-feedback','%']])$('post-'+id+'-value').textContent=$('post-'+id).value+unit;
    const spatial=readSpatialEffects(),key=matchingRecordingScene(spatial),r=spatial.reverbOptions,t=spatial.reverbTone,e=spatial.echo;
    $('post-scene').value=key;
    $('post-scene-status').textContent=`${key?recordingScenes[key].label:'自訂空間效果'} · 殘響 ${spatial.reverb}% · ${reverbSpacePresets[r.space].label} · 尾音 ${r.decay} 秒 · 預延遲 ${r.preDelayMs} ms · 明亮 ${t.brightness} · 寬度 ${t.width}% · 回聲 ${e.amount}%${e.amount?`／${e.timeMs} ms／${e.repeats} 次／每次保留 ${e.feedback}%／${e.pingPong?'左右交替':'中央'}`:''}。`;
  }
  function readEmotionSettings(){return {softening:$('post-softening').value,effects:{eq:Object.fromEntries(['low','mid','high'].map(b=>[b,Number($('post-eq-'+b).value)])),compression:$('post-compression').value}};}
  function emotionLabels(){
    const settings=readEmotionSettings(),key=matchingRecordingEmotion(settings),preset=recordingEmotions[key];
    $('post-emotion').value=key;
    const strength={off:'關閉',light:'輕度',medium:'中度',strong:'強烈'};
    $('post-emotion-status').textContent=`${preset?.help??'已自行微調音色，可繼續調整或重新選擇情緒。'} EQ 低／中／高：${['low','mid','high'].map(b=>settings.effects.eq[b]).join('／')} dB · 柔化：${strength[settings.softening]} · 壓縮：${strength[settings.effects.compression]}。`;
  }
  function readSpatialEffects(){
    return {reverb:Number($('post-reverb').value),reverbOptions:{space:$('post-reverb-space').value,decay:Number($('post-reverb-decay').value),preDelayMs:Number($('post-reverb-predelay').value)},reverbTone:{brightness:Number($('post-reverb-brightness').value),width:Number($('post-reverb-width').value)},echo:{amount:Number($('post-echo-amount').value),timeMs:Number($('post-echo-time').value),repeats:Number($('post-echo-repeats').value),feedback:Number($('post-echo-feedback').value),pingPong:$('post-echo-pingpong').value==='on'}};
  }
  function setSpatialEffects(recipe){
    $('post-reverb').value=recipe.reverb;
    const reverb=reverbProfile(recipe.reverbOptions);
    $('post-reverb-space').value=reverb.space;$('post-reverb-decay').value=reverb.decay;$('post-reverb-predelay').value=reverb.preDelayMs;
    $('post-reverb-brightness').value=recipe.reverbTone?.brightness??0;$('post-reverb-width').value=recipe.reverbTone?.width??100;
    for(const [id,key,fallback] of [['amount','amount',0],['time','timeMs',300],['repeats','repeats',3],['feedback','feedback',40]])$('post-echo-'+id).value=recipe.echo?.[key]??fallback;
    $('post-echo-pingpong').value=recipe.echo?.pingPong?'on':'off';
    effectLabels();
  }
  for(const [key,scene] of Object.entries(recordingScenes)){
    const option=document.createElement('option');option.value=key;option.textContent=scene.label;$('post-scene').append(option);
  }
  for(const [key,preset] of Object.entries(recordingEmotions)){
    const option=document.createElement('option');option.value=key;option.textContent=preset.label+(key==='original'?'（預設，不額外調整音色）':'');$('post-emotion').append(option);
  }
  function addRegion(value){
    const row=document.createElement('div');row.className='post-region-row';
    for(const [key,label,min,max,step] of [['start','開始（秒）',0,3600,.01],['end','結束（秒）',0,3600,.01],['volume','人聲音量（%）',0,200,5]]){
      const field=document.createElement('label'),input=document.createElement('input');field.textContent=label;input.type='number';input.dataset.field=key;input.min=min;input.max=max;input.step=step;input.value=value[key];field.append(input);row.append(field);
    }
    const remove=document.createElement('button');remove.type='button';remove.className='secondary';remove.textContent='移除區段';remove.addEventListener('click',()=>row.remove());row.append(remove);$('post-regions').append(row);
  }
  function setEffects(value){
    const recipe=vocalEffects(value);
    const {cleanup:c,pitchCorrection:p}=repairSettings(recipe);
    for(const [id,key] of [['noise','noise'],['deess','deess'],['deess-hz','deessHz'],['breath','breath']])$('post-'+id).value=c[key];
    $('post-pitch-correction').value=p.amount;$('post-pitch-target').value=p.target;$('post-pitch-speed').value=p.speedMs;$('post-pitch-vibrato').value=p.preserveVibrato?'on':'off';
    for(const band of ['low','mid','high'])$('post-eq-'+band).value=recipe.eq[band];
    $('post-compression').value=recipe.compression;setSpatialEffects(recipe);
    $('post-effect-regions').replaceChildren();(recipe.effectRegions??[]).forEach(addEffectRegion);
    $('post-regions').replaceChildren();recipe.regions.forEach(addRegion);effectLabels();
  }
  function addEffectRegion(value){
    const row=document.createElement('div');row.className='post-effect-region-row';
    for(const [key,label,min,max,step] of [['start','開始（秒）',0,3600,.01],['end','結束（秒）',0,3600,.01],['reverb','殘響（%）',0,100,1],['decay','尾音（秒）',.2,10,.1],['echo','回聲（%）',0,100,1]]){
      const field=document.createElement('label'),input=document.createElement('input');field.textContent=label;input.type='number';input.dataset.field=key;input.min=min;input.max=max;input.step=step;input.value=value[key];field.append(input);row.append(field);
    }const remove=document.createElement('button');remove.type='button';remove.className='secondary';remove.textContent='移除區段';remove.addEventListener('click',()=>row.remove());row.append(remove);$('post-effect-regions').append(row);
  }
  function readEffects(){
    const repair=repairSettings({cleanup:{noise:Number($('post-noise').value),deess:Number($('post-deess').value),deessHz:Number($('post-deess-hz').value),breath:Number($('post-breath').value)},pitchCorrection:{amount:Number($('post-pitch-correction').value),target:$('post-pitch-target').value,speedMs:Number($('post-pitch-speed').value),preserveVibrato:$('post-pitch-vibrato').value==='on'}});
    const regions=Array.from($('post-regions').children,row=>Object.fromEntries(Array.from(row.querySelectorAll('input'),input=>[input.dataset.field,input.value===''?NaN:Number(input.value)])));
    const effectRegions=Array.from($('post-effect-regions').children,row=>Object.fromEntries(Array.from(row.querySelectorAll('input'),input=>[input.dataset.field,input.value===''?NaN:Number(input.value)])));
    const echo={amount:Number($('post-echo-amount').value),timeMs:Number($('post-echo-time').value),repeats:Number($('post-echo-repeats').value),feedback:Number($('post-echo-feedback').value),pingPong:$('post-echo-pingpong').value==='on'};
    const customEcho=echo.amount||echo.timeMs!==300||echo.repeats!==3||echo.feedback!==40||echo.pingPong;
    return vocalEffects({...repair,eq:Object.fromEntries(['low','mid','high'].map(band=>[band,Number($('post-eq-'+band).value)])),compression:$('post-compression').value,reverb:Number($('post-reverb').value),reverbOptions:{space:$('post-reverb-space').value,decay:Number($('post-reverb-decay').value),preDelayMs:Number($('post-reverb-predelay').value)},reverbTone:{brightness:Number($('post-reverb-brightness').value),width:Number($('post-reverb-width').value)},...(customEcho?{echo}:{}),effectRegions,regions});
  }
  function setEdit(value){
    const edit=recordingEdit(value);
    for(const key of ['start','end','fadeIn','fadeOut'])$('post-edit-'+key).value=edit[key]??'';
  }
  function readEdit(){return recordingEdit(Object.fromEntries(['start','end','fadeIn','fadeOut'].map(key=>{const value=$('post-edit-'+key).value;return [key,value===''?(key==='end'?null:NaN):Number(value)];})));}
  function originalPlayhead(){return Math.round((audition?.position()??(($('post-audio').currentTime||0)+(selected?.postEdit?.start||0)))*100)/100;}
  function referenceName(ref) {
    if(!ref)return '尚未載入';
    return `${(ref.pitchMethod||'yin').toUpperCase()} · ${({demucs:'Demucs','bs-roformer':'BS-RoFormer','mel-roformer':'Mel-Band RoFormer'})[ref.separationModel]||'Demucs'} · ${ref.separationMethod==='residual'?'二次分離＋相減':'單次分離'} · ${ref.vocalMode==='lead'?'主唱':'人聲'} · ${Math.round(ref.duration??ref.frames.length*ref.step)} 秒`;
  }
  function controls(){
    audition?.controls(busy);
    const editable=!!(selected?.complete&&selected.rawBytes&&selected.post?.segments?.length);
    $('post-diagnostic').disabled=busy||!editable;
    for(const action of ['preview','download','delete'])$('selected-recording-'+action).disabled=busy||!selected;
    $('selected-recording-mv').disabled=busy||!selected?.complete;
    $('post-delete-all').disabled=busy||!rows.length||isRecording();
    $('selected-recording-edit').disabled=busy||!editable;
    $('selected-recording-voice').disabled=busy||!selected||!(selected.mode==='voice'||editable);
    $('selected-recording-voice').title=selected&&selected.mode!=='voice'&&!editable?'這筆錄音未保留獨立歌聲，無法只聽人聲。':'';
    $('post-recording').disabled=busy;$('score-recording').disabled=busy;
    $('post-delay').disabled=busy||!editable;$('remix-delay').disabled=busy||!editable;
    $('post-reference-source').disabled=busy||!editable;
    $('post-difficulty').disabled=busy||!editable;
    $('post-softening').disabled=busy||!editable;
    $('post-effects-fields').disabled=busy||!editable;
    $('post-edit-fields').disabled=busy||!editable;
    for(const key of ['start','end'])$('post-edit-'+key+'-now').disabled=busy||!editable||(!$('post-audio').getAttribute('src')&&!audition?.playing());
    $('post-voice-level').disabled=busy||!editable;
    $('post-backing-level').disabled=busy||!editable||selected?.mode!=='mix';
    const current=reference();let referenceError='';
    if(editable&&$('post-reference-source').value==='current')try{referenceForRescore(selected.post,current);}catch(error){referenceError=error.message;}
    $('post-reference-info').textContent=editable?`錄音原始基準：${referenceName(selected.post.reference)}。目前已載入：${referenceName(current)}。${referenceError||($('post-reference-source').value==='current'?'這次使用目前已載入基準，保留錄音當時的遮罩、八度與評分範圍，難度使用「評分設定」中的重新評分難度。':'這次使用錄音當時的基準；換歌曲庫版本不會自動套用。')}`:'';
    $('post-rescore').disabled=busy||!editable||!!referenceError;$('post-remix').disabled=busy||!editable;$('post-mp3').disabled=busy||!selected;
    $('post-audition-quick').disabled=busy||!editable;
  }
  function choose({preserveComparison=false}={}){
    if(preserveComparison)audition?.remember();
    clearAudio();previewSources=null;selected=rows.find(x=>x.id===$('post-recording').value)||null;
    $('score-recording').value=$('post-recording').value;
    $('rescore-status').textContent=selected?'已選取錄音，可調整設定後重新評分。':'請先保存一段演唱錄音。';
    $('post-reference-source').value='original';
    $('post-softening').value=selected?.vocalSoftening?.strength||'off';
    // Both drafts agree; only newly captured recordings opt into the new default.
    setEffects(initialRecordingEffects(selected));
    setEdit(selected?.postEdit);
    $('post-edit-info').textContent=selected?`原始錄音約 ${(selected.sourceSeconds??selected.seconds).toFixed(2)} 秒；目前成品 ${selected.seconds.toFixed(2)} 秒。剪輯秒數以套用延時後、尚未裁切的完整錄音為準。${selected.postEdit?.start?`目前播放器 0 秒對應原始錄音 ${selected.postEdit.start} 秒。`:''}`:'';
    const volume=recordingVolume(selected?.postVolume);
    $('post-voice-level').value=volume.voice;$('post-backing-level').value=volume.backing;
    volumeLabels();
    $('post-difficulty').value='relaxed';
    $('post-delay').value=selected?.postResult?.delayMs??selected?.post?.offsetMs??0;
    $('remix-delay').value=$('post-delay').value;
    $('post-info').textContent=selected?(selected.post&&selected.rawBytes?'已保存乾淨歌聲、播放位置與當次基準，可重評／重合成。':'此錄音未保存後處理來源，可轉 MP3 下載。'): '請先保存一段演唱錄音。';
    audition?.reset(selected,{preserve:preserveComparison});
    showScore();controls();
  }
  function showScore(){const r=selected?.postResult;$('post-score').textContent=r?`${r.source==='decoded-voice-v1'?'音檔重評':'舊版即時資料重評'} · ${r.referenceSource==='current'?'改用已載入基準':'錄音當時基準'} ${(r.reference?.pitchMethod||selected.post?.reference?.pitchMethod||'yin').toUpperCase()} · ${scoringProfile(r.scoring?.difficulty??selected.post?.scoring?.difficulty).label} · 校正 ${r.delayMs} ms · 總分 ${r.score??'—'} · 音準 ${r.pitch} · 進拍 ${r.rhythm} · 完整度 ${r.coverage} · 可計分旋律 ${r.referenceSeconds} 秒${r.baseline ? ` · 同音檔 0 ms 進拍 ${r.baseline.rhythm}` : ''}`:'';}
  function refresh(value){rows=value.filter(isPostRecording);const old=$('post-recording').value;const options=rows.map(row=>{const o=document.createElement('option');o.value=row.id;o.textContent=`${row.title}${recordingEffectsSuffix(row)}${recordingSofteningSuffix(row)}${recordingTuningSuffix(row)}${recordingDelaySuffix(row)?" "+recordingDelaySuffix(row):""} · ${new Date(row.created).toLocaleString()}`;return o;});$('post-recording').replaceChildren(...options);$('score-recording').replaceChildren(...options.map(o=>o.cloneNode(true)));if(rows.some(r=>r.id===old))$('post-recording').value=old;if(selected?.id===old&&rows.some(r=>r.id===old)){selected=rows.find(r=>r.id===old);$('score-recording').value=old;controls();}else if(!busy)choose();}
  function select(id,{scroll=true}={}){if(!rows.some(row=>row.id===id))return;$('post-recording').value=id;choose();if(scroll)$('recording-post').scrollIntoView({block:'start'});}
  async function run(action,target='post-status'){if(busy||!selected)return;statusTarget=target;busy=true;controls();try{const row=selected;await stop();pause();if(row)await action(row);}catch(error){status(error.message);}finally{busy=false;controls();statusTarget='post-status';}}
  $('selected-recording-preview').addEventListener('click',()=>run(async row=>{
    clearAudio();url=URL.createObjectURL(await store.blob(row));
    $('post-audio').src=url;$('post-audio').hidden=false;await $('post-audio').play();
    status('正在試聽：'+row.title+recordingEffectsSuffix(row)+recordingSofteningSuffix(row)+recordingDelaySuffix(row));
  }));
  $('selected-recording-voice').addEventListener('click',()=>run(async row=>{
    clearAudio();status('正在準備人聲試聽…');
    let blob;
    if(row.mode==='voice')blob=await store.blob(row);
    else{
      const context=new AudioContext({sinkId:{type:'none'}});
      try{
        const source=await store.blob(row,'voice');
        if(!source.size||source.size!==row.rawBytes)throw new Error('原始歌聲不完整，無法只聽人聲。');
        const raw=await context.decodeAudioData(await source.arrayBuffer());
        // Audition the saved recipe, never pending edits or a re-scoring offset.
        const delayMs=row.appliedDelayMs??(row.parentId?row.delayMs:0)??0;
        // Original-singer replacement belongs to the full mix. Solo needs only
        // the recorded singer; retain the mix mode so saved gain stays identical.
        const singerOnly={...row,post:{...row.post,originalVocals:null}};
        blob=wavBlob(await remixRecording(raw,[],singerOnly,delayMs,{softening:row.vocalSoftening?.strength||'off',volume:row.postVolume,effects:row.vocalEffects,progress:status}));
      }finally{await context.close();}
    }
    url=URL.createObjectURL(blob);$('post-audio').src=url;$('post-audio').hidden=false;await $('post-audio').play();
    status('只聽人聲：'+row.title+recordingEffectsSuffix(row)+recordingSofteningSuffix(row)+recordingDelaySuffix(row)+'（已保存的效果）');
  }));
  $('selected-recording-download').addEventListener('click',()=>run(async row=>{
    download(await store.blob(row),row);status('已開始下載選取的錄音。');
  }));
  $('selected-recording-mv').addEventListener('click',()=>run(async row=>{
    clearAudio();
    const blob=await store.blob(row);
    if(mv.open({title:row.title,blob,label:`${row.title} · 已保存後處理成品 · ${new Date(row.created).toLocaleString()}`}))status('已帶入選取的成品製作 MV；使用已保存的音量、效果與剪輯，尚未重新合成的調整不會套用。');
  }));
  $('selected-recording-edit').addEventListener('click',()=>{
    if(busy||!selected)return;
    $('remix-delay').scrollIntoView({block:'center'});$('remix-delay').focus({preventScroll:true});
  });
  $('selected-recording-delete').addEventListener('click',()=>{
    if(busy||!selected)return;
    if(!localizedConfirm('刪除這筆錄音、原始歌聲及其後處理資料？此操作無法復原。\n'+selected.title+' · '+new Date(selected.created).toLocaleString()))return;
    run(async row=>{clearAudio();await store.delete(row.id);await onDelete();choose();status('已刪除選取的錄音。');});
  });
  $('post-delete-all').addEventListener('click',()=>{
    if(busy||!rows.length)return;
    const receipt=$('post-clear-result'),report=text=>{receipt.hidden=false;receipt.textContent=text;};
    if(isRecording()){report('請先結束錄音，再清除後處理清單。');return;}
    const targets=[...rows];
    if(!localizedConfirm(`清除錄音後處理清單的全部 ${targets.length} 筆？包含所有歌曲的已保存錄音與後製成品，以及各筆附帶的人聲和後處理資料。\n待確認錄音、分段素材及歌曲庫保留。此操作無法復原。`))return;
    run(async()=>{
      clearAudio();let deleted=0;const errors=[];
      report(`正在清除：0／${targets.length} 筆…`);
      for(const row of targets){
        try{await store.delete(row.id);deleted++;}catch(error){errors.push(error.message);}
        report(`正在清除：${deleted+errors.length}／${targets.length} 筆，已刪除 ${deleted} 筆${errors.length?`，失敗 ${errors.length} 筆`:''}…`);
      }
      try{await onDelete();choose();report(`已刪除 ${deleted} 筆；後處理清單剩餘 ${rows.length} 筆。${errors.length?`${errors.length} 筆未刪除，可重試：${errors[0]}`:'待確認錄音與分段素材保留。'}`);}
      catch(error){report(`已刪除 ${deleted} 筆；清單更新失敗，請重新整理確認：${error.message}`);}
    });
  });
  $('post-audio').addEventListener('play',()=>{audition?.stop();pause();});
  $('post-recording').addEventListener('change',choose);
  $('score-recording').addEventListener('change',()=>{$('post-recording').value=$('score-recording').value;choose();});
  $('post-delay').addEventListener('input',()=>{$('remix-delay').value=$('post-delay').value;});
  $('remix-delay').addEventListener('input',()=>{$('post-delay').value=$('remix-delay').value;});
  $('post-reference-source').addEventListener('change',controls);
  function volumeLabels(){
    $('post-voice-value').textContent=$('post-voice-level').value+'%';
    $('post-backing-value').textContent=$('post-backing-level').value+'%';
  }
  for(const id of ['post-voice-level','post-backing-level'])$(id).addEventListener('input',volumeLabels);
  for(const id of ['noise','deess','deess-hz','breath','pitch-correction','pitch-speed'])$('post-'+id).addEventListener('input',effectLabels);
  for(const id of ['pitch-target','pitch-vibrato'])$('post-'+id).addEventListener('change',effectLabels);
  for(const id of ['post-eq-low','post-eq-mid','post-eq-high','post-reverb','post-reverb-decay','post-reverb-predelay','post-reverb-brightness','post-reverb-width','post-echo-amount','post-echo-time','post-echo-repeats','post-echo-feedback'])$(id).addEventListener('input',effectLabels);
  $('post-reverb-space').addEventListener('change',()=>{
    const preset=reverbSpacePresets[$('post-reverb-space').value];
    $('post-reverb-decay').value=preset.decay;$('post-reverb-predelay').value=preset.preDelayMs;effectLabels();
  });
  $('post-echo-pingpong').addEventListener('change',effectLabels);
  for(const id of ['post-softening','post-compression'])$(id).addEventListener('change',emotionLabels);
  $('post-emotion').addEventListener('change',()=>{
    const preset=recordingEmotions[$('post-emotion').value];if(!preset)return;
    audition?.stop();
    $('post-softening').value=preset.softening;
    for(const band of ['low','mid','high'])$('post-eq-'+band).value=preset.eq[band];
    $('post-compression').value=preset.compression;effectLabels();
    $('post-audition-status').textContent=`已套用 ${$('post-ab-editor').dataset.slot.toUpperCase()} 組「${preset.label}」音色，空間設定保留；按試聽聽取新效果，滿意後重新合成另存。`;
  });
  $('post-scene').addEventListener('change',()=>{
    const scene=recordingScenes[$('post-scene').value];if(!scene)return;
    audition?.stop();setSpatialEffects(scene.effects);
    $('post-audition-status').textContent=`已套用${$('post-ab-editor').dataset.slot.toUpperCase()} 組「${scene.label}」，按試聽聽取新效果；滿意後重新合成另存。`;
  });
  $('post-effects-reset').addEventListener('click',()=>setEffects());
  $('post-audition-quick').addEventListener('click',()=>{$('post-audition-panel').open=true;void audition?.playCurrent();$('post-audition-panel').scrollIntoView({block:'start'});});
  $('post-edit-reset').addEventListener('click',()=>setEdit());
  for(const key of ['start','end'])$('post-edit-'+key+'-now').addEventListener('click',()=>{$('post-edit-'+key).value=originalPlayhead();});
  $('post-region-add').addEventListener('click',()=>{
    if($('post-regions').children.length>=100){status('局部音量最多 100 個區段。');return;}
    const endLimit=selected?.sourceSeconds??selected?.seconds??0;
    const start=Math.min(Math.max(0,endLimit-.1),originalPlayhead());
    addRegion({start,end:Math.min(endLimit,start+5),volume:100});
  });
  $('post-effect-region-add').addEventListener('click',()=>{
    if($('post-effect-regions').children.length>=20){status('局部效果最多 20 個區段。');return;}
    const limit=selected?.sourceSeconds??selected?.seconds??0,start=Math.min(Math.max(0,limit-.1),originalPlayhead());
    addEffectRegion({start,end:Math.min(limit,start+5),reverb:Number($('post-reverb').value),decay:Number($('post-reverb-decay').value),echo:Number($('post-echo-amount').value)});
  });
  $('post-rescore').addEventListener('click',()=>run(async row=>{
    const delayMs=Number($('post-delay').value);delaySeconds(delayMs);
    const referenceSource=$('post-reference-source').value;
    const scoringReference=referenceSource==='current'?referenceForRescore(row.post,reference()):structuredClone(row.post.reference);
    status(`正在以 ${referenceName(scoringReference)} 重新評分…`);
    if(row.post.audioAnalysis?.source!=='decoded-voice-v1'||row.post.audioAnalysis.detectorVersion!==PITCH_DETECTOR_VERSION||(row.post.audioAnalysis.pitchShift||0)!==(row.post.reference.pitchShift||0)) {
      status('正在從保存的乾淨歌聲重新擷取音高…');
      row.post.audioAnalysis=await recordedAnalysis(await store.blob(row,'voice'),percent=>status(`正在分析乾淨歌聲 ${percent}%…`),row.post.reference.pitchShift || 0);
    }
    const scoring={...row.post.scoring,difficulty:scoringProfile($('post-difficulty').value).id};
    const scoringPost={...row.post,reference:scoringReference,scoring};
    row.postResult={...rescoreRecording(scoringPost,delayMs),delayMs,scoring,source:'decoded-voice-v1',referenceSource,reference:scoringReference,baseline:rescoreRecording(scoringPost,0)};await store.save(row);showScore();status('重評完成：直接分析保存的歌聲，使用與重混相同的時間軸；結果、難度與所用基準已保存，錄音原始基準及成績紀錄保留。');
  },'rescore-status'));
  $('post-remix').addEventListener('click',()=>run(async row=>{
    const delayMs=Number($('remix-delay').value);delaySeconds(delayMs);
    const softening=softeningProfile($('post-softening').value);
    const effects=readEffects();
    const edit=readEdit();
    const volume=recordingVolume({voice:Number($('post-voice-level').value),backing:Number($('post-backing-level').value)});
    status('正在載入乾淨歌聲與配樂／和音…');
    const context=new AudioContext({sinkId:{type:'none'}});
    try{
      const rawBlob=await store.blob(row,'voice');
      if(!rawBlob.size||rawBlob.size!==row.rawBytes)throw new Error('原始歌聲不完整，無法另存可繼續後製的成品。');
      const raw=await context.decodeAudioData(await rawBlob.arrayBuffer()),tracks=[];
      if(row.mode==='mix')for(const stem of row.stems){const response=await localRequest(backingRoute(row,stem));tracks.push(await context.decodeAudioData(await response.arrayBuffer()));}
      status(softening.id==='off'?'正在校正歌聲位置並合成…':`正在套用${softening.label}歌聲柔化並合成…`);
      const audio=await remixRecording(raw,tracks,row,delayMs,{softening:softening.id,volume,effects,edit,progress:status}),blob=wavBlob(audio);
      const result={id:crypto.randomUUID(),title:row.title,videoId:row.videoId,mode:row.mode,stems:row.stems,mime:'audio/wav',created:Date.now(),seconds:audio.duration,bytes:blob.size,complete:true,parentId:row.id,delayMs,appliedDelayMs:delayMs,vocalSoftening:{version:2,strength:softening.id}};
      result.postVolume=volume;
      result.vocalEffects=effects;
      result.postScene={version:1,id:matchingRecordingScene(effects)||'custom'};
      result.postEmotion={version:1,id:matchingRecordingEmotion({effects,softening:softening.id})};
      result.postEdit=edit;
      result.rawBytes=rawBlob.size;result.rawMime=row.rawMime||rawBlob.type||row.mime;
      result.post=structuredClone(row.post);result.post.offsetMs=delayMs;
      result.balance=structuredClone(row.balance);
      if(row.fixedMixGains)result.fixedMixGains=structuredClone(row.fixedMixGains);
      result.sourceSeconds=row.sourceSeconds??row.seconds;
      await store.saveRemix(result,blob,rawBlob);refresh(await store.list());$('post-recording').value=result.id;choose({preserveComparison:true});clearAudio();url=URL.createObjectURL(blob);$('post-audio').src=url;$('post-audio').hidden=false;
      status(`已另存校正後錄音${softening.id==='off'?'':`（歌聲柔化：${softening.label}）`} · 歌唱者 ${volume.voice}%${row.mode==='mix'?` · 配樂／和音 ${volume.backing}%`:''}，請按播放器試聽；可轉 MP3。原錄音保留，這筆成品也可繼續後製。`);
      window.dispatchEvent(new Event('recording-post-saved'));
    }finally{await context.close();}
  }));
  $('post-diagnostic').addEventListener('click',()=>run(async row=>{
    status('正在打包這筆錄音的本機診斷資料…');
    async function audioPart(track){
      const blob=await store.blob(row,track);
      if(blob.size>128*1024*1024)throw new Error('這筆錄音超過診斷匯出大小限制，請改用較短錄音。');
      const bytes=new Uint8Array(await blob.arrayBuffer()),parts=[];
      for(let i=0;i<bytes.length;i+=32768)parts.push(String.fromCharCode(...bytes.subarray(i,i+32768)));
      return {mime:blob.type,base64:btoa(parts.join(''))};
    }
    const value={format:'karaoke-recording-diagnostic',version:1,exportedAt:new Date().toISOString(),appBuild:document.querySelector('meta[name="app-build"]')?.content,recording:row,audio:{voice:await audioPart('voice'),mix:await audioPart('mix')}};
    const blob=new Blob([JSON.stringify(value)],{type:'application/json'}),href=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=href;a.download=`karaoke-diagnostic-${row.id}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(href),60000);
    status('診斷檔已下載到本機。這份檔案含本次歌聲，請提供此檔或其本機路徑以檢查，不需重唱。');
  },'rescore-status'));
  $('post-mp3').addEventListener('click',()=>run(async row=>{
    status('正在本機轉成 MP3…');const blob=await store.blob(row),response=await localRequest('/recordings/mp3',blob),mp3=await response.blob();
    let savedPath='',saveError='';try{savedPath=(await store.saveMp3(row,mp3)).path;}catch(error){saveError=error.message;}
    const href=URL.createObjectURL(mp3),a=document.createElement('a');a.href=href;a.download=row.title.replace(/[\\/:*?"<>|]/g,'_').slice(0,100)+recordingEffectsSuffix(row)+recordingSofteningSuffix(row)+recordingTuningSuffix(row)+recordingDelaySuffix(row)+'.mp3';a.click();setTimeout(()=>URL.revokeObjectURL(href),60000);status(savedPath?'MP3 已轉換並開始下載，同時保存至 '+savedPath+'。':'MP3 已轉換並開始下載，但尚未存入錄音目錄：'+saveError);
  }));
  audition=createRecordingAudition({run,getPosition:originalPlayhead,beforePlay:()=>{$('post-audio').pause();pause();},
    defaults:row=>({delayMs:300,softening:'off',volume:recordingVolume(),effects:vocalEffects(recordingScenes.hall.effects)}),
    onEditor:name=>{const panel=$('post-ab-editor'),label=name.toUpperCase();panel.dataset.slot=name;panel.className='audition-slot-'+name;$('post-ab-editor-heading').textContent=`正在調整 ${label} 組`;$('post-audition-quick').textContent=`片段試聽目前 ${label} 設定`;$('post-remix').textContent=`重新合成 ${label}（音量／延時／音色／剪輯）`;},
    read:()=>{const delayMs=Number($('remix-delay').value);delaySeconds(delayMs);return {delayMs,softening:$('post-softening').value,volume:recordingVolume({voice:Number($('post-voice-level').value),backing:Number($('post-backing-level').value)}),effects:readEffects()};},
    apply:s=>{$('post-softening').value=s.softening;setEffects(s.effects);$('remix-delay').value=s.delayMs;$('post-delay').value=s.delayMs;$('post-voice-level').value=s.volume.voice;$('post-backing-level').value=s.volume.backing;volumeLabels();},
    render:async(row,settings,interval,solo)=>{
      if(!previewSources){const c=new AudioContext({sinkId:{type:'none'}});try{
        const blob=await store.blob(row,'voice');if(!blob.size||blob.size!==row.rawBytes)throw Error('原始歌聲不完整，無法比較。');
        previewSources={raw:await c.decodeAudioData(await blob.arrayBuffer()),tracks:null};
      }finally{await c.close();}}
      if(!solo&&row.mode==='mix'&&!previewSources.tracks){const c=new AudioContext({sampleRate:previewSources.raw.sampleRate,sinkId:{type:'none'}});try{
        const tracks=[];for(const stem of row.stems){const response=await localRequest(backingRoute(row,stem));tracks.push(await c.decodeAudioData(await response.arrayBuffer()));}previewSources.tracks=tracks;
      }finally{await c.close();}}
      const fade=Math.min(.003,(interval.end-interval.start)/4);
      return remixRecording(previewSources.raw,solo?[]:previewSources.tracks??[],solo?{...row,mode:'voice'}:row,settings.delayMs,{...settings,edit:{...interval,fadeIn:fade,fadeOut:fade},progress:status});
    }
  });
  window.addEventListener('pagehide',clearAudio);
  return {refresh,select,controls,clearAudio};
}
