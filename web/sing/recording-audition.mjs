// Temporary A/B renders share a source-time interval. They never write to the archive.
import {reverbSpaces} from './recording-soften.mjs';
import {recordingEmotionLabel} from './recording-scenes.mjs';
import {wavBlob} from './recording-process.mjs';
const $=id=>document.getElementById('post-audition-'+id);
// Compare displayed settings, including inactive effect parameters, without touching audio.
export function settingDifferences(a,b,{includeBacking=true}={}){
  const rows=[],add=(label,left,right,format=String)=>{if(left!==right)rows.push({label,a:left==null?'未設定':format(left),b:right==null?'未設定':format(right)});};
  const unit=suffix=>value=>`${value}${suffix}`,signed=suffix=>value=>`${value>0?'+':''}${value}${suffix}`;
  const strength=value=>({off:'關閉',light:'輕度',medium:'中度',strong:'強烈'})[value]??value;
  add('歌唱者音量',a.volume?.voice??100,b.volume?.voice??100,unit('%'));
  if(includeBacking)add('配樂／和音音量',a.volume?.backing??100,b.volume?.backing??100,unit('%'));
  add('歌聲延時校正',a.delayMs??0,b.delayMs??0,signed(' ms'));
  add('歌聲柔化',a.softening??'off',b.softening??'off',strength);
  add('人聲情緒',recordingEmotionLabel(a),recordingEmotionLabel(b));
  const x=a.effects??{},y=b.effects??{};
  for(const [key,label,fallback,suffix] of [['noise','降噪強度',0,'%'],['deess','齒音抑制',0,'%'],['deessHz','齒音偵測頻率',6000,' Hz'],['breath','呼吸聲降低',0,'%']])add(label,x.cleanup?.[key]??fallback,y.cleanup?.[key]??fallback,unit(suffix));
  const p=x.pitchCorrection??{},q=y.pitchCorrection??{};
  add('音準修正強度',p.amount??0,q.amount??0,unit('%'));
  add('音準修正目標',p.target??'chromatic',q.target??'chromatic',v=>v==='reference'?'原唱基準（保留八度）':'最近半音');
  add('音準修正速度',p.speedMs??120,q.speedMs??120,unit(' ms'));
  add('保留顫音',p.preserveVibrato??true,q.preserveVibrato??true,v=>v?'開啟':'關閉');
  for(const [key,label] of [['low','低頻'],['mid','中頻'],['high','高頻']])add(`EQ ${label}`,x.eq?.[key]??0,y.eq?.[key]??0,signed(' dB'));
  add('動態壓縮',x.compression??'off',y.compression??'off',strength);
  add('殘響音量',x.reverb??0,y.reverb??0,unit('%'));
  add('殘響空間',x.reverbOptions?.space??'classic',y.reverbOptions?.space??'classic',value=>reverbSpaces[value]??value);
  for(const [key,label,fallback,suffix] of [['decay','尾音長度',.8,' 秒'],['preDelayMs','預延遲',15,' ms']])add(label,x.reverbOptions?.[key]??fallback,y.reverbOptions?.[key]??fallback,unit(suffix));
  add('殘響明亮度',x.reverbTone?.brightness??0,y.reverbTone?.brightness??0,signed(''));
  add('殘響立體寬度',x.reverbTone?.width??100,y.reverbTone?.width??100,unit('%'));
  for(const [key,label,fallback,suffix] of [['amount','回聲音量',0,'%'],['timeMs','回聲重複間隔',300,' ms'],['repeats','回聲重複次數',3,' 次'],['feedback','回聲每次保留音量',40,'%']])add(label,x.echo?.[key]??fallback,y.echo?.[key]??fallback,unit(suffix));
  add('回聲位置',x.echo?.pingPong??false,y.echo?.pingPong??false,value=>value?'左右交替':'中央');
  for(const [key,label,fields] of [
    ['regions','局部音量',[['start','開始',' 秒'],['end','結束',' 秒'],['volume','音量','%']]],
    ['effectRegions','局部效果',[['start','開始',' 秒'],['end','結束',' 秒'],['reverb','殘響','%'],['decay','尾音',' 秒'],['echo','回聲','%']]]
  ]){
    const left=[...(x[key]??[])].sort((p,q)=>p.start-q.start),right=[...(y[key]??[])].sort((p,q)=>p.start-q.start);
    for(let i=0;i<Math.max(left.length,right.length);i++)for(const [field,title,suffix] of fields)add(`${label} 第 ${i+1} 段 · ${title}`,left[i]?.[field],right[i]?.[field],unit(suffix));
  }
  return rows;
}
export function comparisonLevels(buffers,matched=true){
  const rms=buffers.map(b=>{let sum=0;for(let c=0;c<b.numberOfChannels;c++)for(const x of b.getChannelData(c))sum+=x*x;return Math.sqrt(sum/(b.length*b.numberOfChannels));});
  const audible=rms.filter(x=>x>1e-6),target=audible.length?Math.min(...audible):0;
  return rms.map(x=>matched&&x>1e-6&&target?Math.min(1,target/x):1);
}
export function createRecordingAudition({read,defaults,apply,render,run,beforePlay,onEditor=()=>{},getPosition=()=>0}){
  let row=null,slots={},defaultSlots={},cache={},editor='b',busy=false,active=null,timer=null,generation=0,loading=null,url=null;
  const player=new Audio();player.loop=true;
  const say=text=>$('status').textContent=text;
  function showTab(name){editor=name;for(const key of ['a','b']){const current=key===name;$(key+'-tab').setAttribute('aria-selected',String(current));$(key+'-tab').tabIndex=current?0:-1;$(key+'-pane').hidden=!current;$(key+'-edit').setAttribute('aria-pressed',String(current));}$('reset').textContent=`還原 ${name.toUpperCase()} 預設設定`;onEditor(name);refreshDifferences();}
  function refreshDifferences(){
    $('differences-body').replaceChildren();$('differences-table').hidden=true;
    if(!slots.a||!slots.b){$('differences-count').textContent='選取錄音後顯示差異。';return;}
    try{
      const drafts={...slots,[editor]:read()},rows=settingDifferences(drafts.a,drafts.b,{includeBacking:row.mode!=='voice'});
      $('differences-count').textContent=rows.length?`${rows.length} 項不同`:'目前 A／B 設定相同';
      for(const difference of rows){const tr=document.createElement('tr');for(const key of ['label','a','b']){const cell=document.createElement(key==='label'?'th':'td');if(key==='label')cell.scope='row';else cell.className='audition-slot-'+key;cell.textContent=difference[key];tr.append(cell);}$('differences-body').append(tr);}
      $('differences-table').hidden=!rows.length;
    }catch(error){$('differences-count').textContent=`${editor.toUpperCase()} 組欄位尚未完成：${error.message} 補齊後會繼續顯示差異。`;}
  }
  // Read before switching so even dynamically added regions belong to their own draft.
  // Invalid fields must stay visible instead of being silently lost on a tab change.
  function remember(){if(!slots[editor])return;const next=structuredClone(read());if(JSON.stringify(next)!==JSON.stringify(slots[editor])){if(active)stop();delete cache[editor];slots[editor]=next;describe(editor);}}
  function selectTab(name){remember();if(slots[name])apply(structuredClone(slots[name]));showTab(name);}
  function switchEditor(name){try{selectTab(name);say(`正在調整 ${name.toUpperCase()}，兩組設定各自保留；按試聽才會播放新效果。`);return true;}catch(e){say(e.message);return false;}}
  function stop(){generation++;player.pause();player.removeAttribute('src');player.load();if(url)URL.revokeObjectURL(url);url=null;active=null;clearInterval(timer);timer=null;$('position').textContent='';controls(busy);}
  function invalidate(){stop();cache={};}
  function controls(value=busy){busy=value;const enabled=!!(row?.complete&&row.rawBytes&&row.post?.segments?.length);$('fields').disabled=busy||!enabled;
    for(const name of ['a','b'])$(name+'-edit').disabled=busy||!enabled;
    $('reset').disabled=busy||!enabled;
    for(const name of ['a','b'])for(const action of ['play','apply'])$(name+'-'+action).disabled=busy||!enabled||!slots[name];
    for(const name of ['a','b']){const button=$(name+'-play');button.setAttribute('aria-pressed',String(active===name));button.textContent=loading===name?`準備 ${name.toUpperCase()}…`:active===name?`● 正在聽 ${name.toUpperCase()}`:`▶ 試聽 ${name.toUpperCase()}`;}
    $('stop').disabled=!active&&!busy;$('mode').disabled=busy||!enabled||row?.mode==='voice';
  }
  function describe(name){const s=slots[name];$(name+'-info').textContent=s?`情緒 ${recordingEmotionLabel(s)} · 殘響 ${s.effects.reverb}% · 明亮 ${s.effects.reverbTone?.brightness??0} · 寬度 ${s.effects.reverbTone?.width??100}% · 回聲 ${s.effects.echo?.amount??0}% · ${s.effects.effectRegions?.length??0} 段局部效果 · 校正 ${s.delayMs} ms`:'尚未記住設定';}
  function reset(value,{preserve=false}={}){
    // A remix retains the same raw source and timeline: keep the editing session.
    const continuing=preserve&&value?.parentId===row?.id&&slots.a&&slots.b;
    invalidate();row=value;
    if(continuing){apply(structuredClone(slots[editor]));showTab(editor);say('已另存成品，A／B 設定與比較片段保留；還原會回到系統預設。');controls();return;}
    const settings=value?read():null,base=value?defaults(value):null;
    slots=value?{a:structuredClone(settings),b:structuredClone(settings)}:{};
    defaultSlots=value?{a:structuredClone(base),b:structuredClone(base)}:{};
    for(const name of ['a','b'])describe(name);showTab('b');$('start').value=0;$('end').value=Math.min(10,value?.sourceSeconds??value?.seconds??10).toFixed(2);$('mode').value=value?.mode==='voice'?'voice':'mix';say(value?'A、B 已帶入相同的錄音設定，可各自調整後比較。預設調整 B；還原按鈕回到系統預設。':'選取錄音後即可比較。');controls();
  }
  function restoreEditor(){
    if(busy||!defaultSlots[editor])return;
    // Skip reading the draft: restoring must also recover incomplete/invalid fields.
    stop();delete cache[editor];slots[editor]=structuredClone(defaultSlots[editor]);
    apply(structuredClone(slots[editor]));describe(editor);showTab(editor);controls();
    say(`已還原 ${editor.toUpperCase()} 系統預設：原音、大廳殘響 20%、回聲 10%、音量 100%、校正 ${slots[editor].delayMs} ms，清理與音準修正關閉；另一組保留。按試聽即可重新比較。`);
  }
  function range(){const start=$('start').value===''?NaN:Number($('start').value),end=$('end').value===''?NaN:Number($('end').value);
    if(!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<=start||end>3600||end-start>30)throw Error('試聽需設定有效起訖，每段最多 30 秒。');return {start,end};}
  function matchGain(){const names=Object.keys(cache),levels=comparisonLevels(names.map(n=>cache[n]),$('match').checked);return levels[names.indexOf(active)]??1;}
  function loadAudio(name,offset){
    active=name;
    // Bake volume matching into the file too; playback has no DSP graph.
    const buffer=cache[name],level=matchGain();
    let output=buffer;
    if(level!==1){output=new AudioBuffer({numberOfChannels:buffer.numberOfChannels,length:buffer.length,sampleRate:buffer.sampleRate});for(let c=0;c<buffer.numberOfChannels;c++){const input=buffer.getChannelData(c),data=output.getChannelData(c);for(let i=0;i<data.length;i++)data[i]=input[i]*level;}}
    const next=URL.createObjectURL(wavBlob(output)),previous=url;url=next;
    player.src=next;player.currentTime=offset%buffer.duration;
    if(previous)URL.revokeObjectURL(previous);
  }
  function play(name){return run(async selected=>{
    if(!slots[name])throw Error('請先記住這組設定。');
    selectTab(name);
    const interval=range(),token=generation;
    if(!cache[name]){say(`正在準備 ${name.toUpperCase()} 片段…`);loading=name;controls();try{const audio=await render(selected,slots[name],interval,$('mode').value==='voice');if(token!==generation)return;cache[name]=audio;}finally{loading=null;controls();}}
    beforePlay();
    if(token!==generation)return;
    const offset=active?player.currentTime:0;
    loadAudio(name,offset);
    try{await player.play();}catch(error){if(token!==generation||error.name==='AbortError')return;stop();throw error;}
    if(token!==generation)return;
    clearInterval(timer);timer=setInterval(()=>{if(active)$('position').textContent=`${active.toUpperCase()} · 原始錄音 ${(interval.start+player.currentTime).toFixed(2)} 秒 · 循環試聽中`;},100);
    say(`正在比較 ${name.toUpperCase()}：${interval.start}～${interval.end} 秒${$('match').checked?' · 近似音量匹配':''}。試聽不另存錄音。`);controls();
  },'post-audition-status');}
  for(const name of ['a','b']){
    $(name+'-tab').addEventListener('click',()=>switchEditor(name));
    $(name+'-edit').addEventListener('click',()=>switchEditor(name));
    $(name+'-tab').addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const next=event.key==='Home'?'a':event.key==='End'?'b':name==='a'?'b':'a';if(switchEditor(next))$(next+'-tab').focus();});
    $(name+'-play').addEventListener('click',()=>play(name));
    $(name+'-apply').addEventListener('click',()=>{if(switchEditor(name))document.getElementById('post-ab-editor').scrollIntoView({block:'start'});});
  }
  $('from-playhead').addEventListener('click',()=>{const limit=row.sourceSeconds??row.seconds,start=Math.max(0,Math.min(getPosition(),limit-.1));invalidate();$('start').value=start.toFixed(2);$('end').value=Math.min(limit,start+10).toFixed(2);say(`已選 ${$('start').value}～${$('end').value} 秒，可按 A／B 試聽。`);});
  $('stop').addEventListener('click',()=>{stop();say('比較已停止，A／B 設定仍保留。');});
  $('reset').addEventListener('click',restoreEditor);
  for(const id of ['start','end','mode'])$(id).addEventListener('change',invalidate);
  $('match').addEventListener('change',()=>{if(active){loadAudio(active,player.currentTime);void player.play().catch(error=>{if(error.name!=='AbortError'){stop();say(error.message);}});}});
  // Delegation includes added/removed regions and preset/reset buttons. Reading drafts
  // here must not invalidate a playing buffer or overwrite the other group's settings.
  for(const event of ['input','change','click'])document.getElementById('post-ab-editor').addEventListener(event,refreshDifferences);
  document.getElementById('post-delay').addEventListener('input',refreshDifferences);
  window.addEventListener('pagehide',stop);
  return {reset,remember,stop,controls,playCurrent:()=>play(editor),playing:()=>!!active,position:()=>active?Number($('start').value)+player.currentTime:null};
}
