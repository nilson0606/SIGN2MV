// SIGN2MV glue for the sing & record page (runs inside the SIGN2MV window).
import {selectMediaSource} from './media-source.mjs';
import {setLanguage,translateMessage,userOption} from './i18n.mjs';
import {keyLabel} from './song-key.mjs';
const $=id=>document.getElementById(id);
const parentWindow=window.parent!==window?window.parent:null;
const post=message=>parentWindow?.postMessage(message,location.origin);

// Songs come only from the SIGN2MV library (local media). Whole songs only.
const kind=$('source-kind');
kind.querySelector('option[value="youtube"]')?.remove();
kind.value='local';
$('local-media-help').textContent='從 SIGN2MV 歌曲庫選歌；要新增歌曲請到「歌曲庫」頁匯入 YouTube 或本機檔案。';
document.querySelector('label[for="local-media-saved"]').textContent='歌曲（SIGN2MV 歌曲庫）';
$('local-media-load').textContent='載入歌曲';

async function token(){const r=await fetch('/sr/session',{cache:'no-store'});return (await r.json()).token;}
async function media(){
  const r=await fetch('/sr/local-media',{headers:{'X-Karaoke-Token':await token()},cache:'no-store'});
  return (await r.json()).media||[];
}
let wanted=null;
async function selectSong(songId){
  wanted=songId;
  const rows=await media(),row=rows.find(m=>m.songId===songId);
  if(!row){$('local-media-status').textContent='找不到這首歌，請到「歌曲庫」匯入。';return;}
  kind.dispatchEvent(new Event('change'));
  // wait for the list refresh started by the change event
  for(let i=0;i<50&&![...$('local-media-saved').options].some(o=>o.value===row.id);i++)await new Promise(r=>setTimeout(r,100));
  if(wanted!==songId)return;
  $('local-media-saved').value=row.id;
  selectMediaSource(row.id,document,row.kind);
  $('local-media-load').click();
  $('player-section').scrollIntoView({block:'start'});
}
// ---- [SIGN2MV] Key versions in the song menu: 「童話 · 降 4 Key」 for every Key that already has a
// reference. Loading a song (any Key) that has a reference loads it right away, through the page's own
// 「歌曲庫」 list button (it restores the exact separation settings, so nothing is rebuilt); without one,
// the song is loaded, the Key menu is set and a note asks to prepare it.
let refs=[],keyRevision=0,passThrough=false;
async function library(){
  try{const r=await fetch('/sr/library',{headers:{'X-Karaoke-Token':await token()},cache:'no-store'});return r.ok?((await r.json()).songs||[]):[];}catch{return [];}
}
function bestRef(vid,key){const c=refs.filter(r=>r.videoId===vid&&(r.pitchShift||0)===key);return c.find(r=>!r.seconds)||c[0]||null;}
async function addKeyOptions(){
  const sel=$('local-media-saved'),revision=++keyRevision;
  if([...sel.options].some(o=>o.value.includes('#key')))return;
  const rows=await library();if(revision!==keyRevision)return;refs=rows;
  const keep=sel.value;
  for(const o of [...sel.options]){
    if(!o.value||o.value.includes('#key'))continue;
    const keys=[...new Set(refs.filter(r=>r.videoId===o.value&&r.pitchShift).map(r=>r.pitchShift))].sort((a,b)=>a-b);
    let after=o;
    for(const k of keys){const n=userOption(`${o.textContent} · ${translateMessage(keyLabel(k))}`,`${o.value}#key${k}`);after.after(n);after=n;}
  }
  if(keep)sel.value=keep;
}
new MutationObserver(()=>{const sel=$('local-media-saved');if(sel.options.length>1&&![...sel.options].some(o=>o.value.includes('#key')))void addKeyOptions();})
  .observe($('local-media-saved'),{childList:true});
async function libraryButton(cacheId){
  const find=()=>document.querySelector(`#library-list button.song-choice[data-song-id="${CSS.escape(cacheId)}"]`);
  if(!find())$('library-refresh').click();
  for(let i=0;i<60&&!find();i++)await new Promise(r=>setTimeout(r,100));
  return find();
}
function keyNote(key){
  return key?`這首歌的「${keyLabel(key)}」還沒有歌唱基準：已幫你選好 Key，請按「準備歌曲基準」建立（會分離人聲並分析音高，需要幾分鐘）。`
    :'這首歌還沒有歌唱基準：請按「準備歌曲基準」建立（會分離人聲並分析音高，需要幾分鐘）。';
}
$('local-media-load').addEventListener('click',async e=>{
  if(passThrough)return;
  const value=$('local-media-saved').value;if(!value)return;
  e.stopImmediatePropagation();
  const [vid,keyPart]=value.split('#key'),key=keyPart?Number(keyPart):0;
  refs=await library();
  const ref=bestRef(vid,key);
  if(ref){
    const btn=await libraryButton(ref.id);
    if(btn){
      const note=$('local-media-status');note.textContent=`已有歌唱基準（${keyLabel(key)}），正在載入…`;btn.click();
      // replace the 「正在載入…」 once the reference is in (it used to stay)
      for(let i=0;i<300&&!$('prepare-status').textContent.startsWith('已就緒');i++)await new Promise(r=>setTimeout(r,100));
      if(note.textContent.startsWith('已有歌唱基準'))note.textContent=$('prepare-status').textContent.startsWith('已就緒')?`已載入歌唱基準（${keyLabel(key)}）。`:'';
      return;
    }
  }
  // no reference (or the list did not show it): load the song itself, then point at 「準備歌曲基準」
  $('local-media-status').textContent='';
  const sel=$('local-media-saved');sel.value=vid;
  passThrough=true;try{$('local-media-load').click();}finally{passThrough=false;}
  sel.value=value;
  $('song-key').value=String(key);$('song-key').dispatchEvent(new Event('change'));
  for(let i=0;i<100&&!$('player-status').textContent.includes('已載入');i++)await new Promise(r=>setTimeout(r,100));
  $('prepare-status').textContent=keyNote(key);
},true);
window.addEventListener('karaoke-language-change',()=>{keyRevision++;for(const o of [...$('local-media-saved').options])if(o.value.includes('#key'))o.remove();void addKeyOptions();});

function busyPhase(){
  try{const w=JSON.parse($('player-section').dataset.workflow||'{}');return !!(w.hasTake||w.busy||['singing','preparing','finishing','restarting'].includes(w.phase));}catch{return false;}
}
window.addEventListener('message',event=>{
  if(event.origin!==location.origin||event.source!==parentWindow)return;
  const m=event.data||{};
  if(m.type==='sign2mv:select-song'&&typeof m.songId==='string')void selectSong(m.songId);
  if(m.type==='sign2mv:refresh-songs')kind.dispatchEvent(new Event('change'));
  if(m.type==='sign2mv:takes-changed')refreshTakesSoon();
  // switch in place: a reload was skipped while a take was pending (almost always), so the page stayed in the old language
  if(m.type==='sign2mv:lang')setLanguage(m.lang==='en'?'en':'zh-Hant');
});
// Report the loaded song and busy state so the shell can warn before leaving.
new MutationObserver(()=>post({type:'sign2mv:sing-state',busy:busyPhase()})).observe($('player-section'),{attributes:true,attributeFilter:['data-workflow']});
window.addEventListener('load',()=>{
  $('local-check').click();
  kind.dispatchEvent(new Event('change'));
  post({type:'sign2mv:sing-ready'});
});

// ---- microphone permission: the browser's question can hide behind other windows and recording
// waits for it (playback starts only once the microphone is open). Say so plainly.
const micNote=document.createElement('div');
micNote.id='sign2mv-mic-note';micNote.className='sign2mv-note';micNote.hidden=true;micNote.setAttribute('role','alert');
document.body.prepend(micNote);
function showMicNote(text,kind){micNote.textContent=text;micNote.dataset.kind=kind;micNote.hidden=!text;}
if(navigator.mediaDevices?.getUserMedia){
  const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  navigator.mediaDevices.getUserMedia=function(constraints){
    const asking=setTimeout(()=>showMicNote('🎤 瀏覽器正在詢問「是否允許使用麥克風」：請找到那個視窗（通常在網址列下方，可能被其他視窗擋住）按「允許」。按下之前，錄音和播放都會等著。','wait'),2500);
    return original(constraints).then(stream=>{clearTimeout(asking);showMicNote('','');return stream;},error=>{
      clearTimeout(asking);
      if(error?.name==='NotAllowedError')showMicNote('🎤 麥克風被瀏覽器封鎖了：點網址列最左邊的圖示（網站設定），把「麥克風」改成「允許」，再按 F5 重新整理。','bad');
      else showMicNote('','');
      throw error;
    });
  };
}

// ---- segment panel: messages go to the status line under the record buttons, which is far from
// the version panel on a narrow window. Repeat the answer under the button that was pressed.
const segStatus=$('segment-status');
let echoTarget=null,echoUntil=0;
const echo=document.createElement('p');echo.className='status sign2mv-echo';echo.setAttribute('role','status');echo.hidden=true;
document.addEventListener('click',event=>{
  const b=event.target.closest?.('#segment-side button, #segment-section button');
  if(!b||!segStatus)return;
  const row=b.closest('.button-row')||b;
  // only where the status line is out of the way (the version and trial panels)
  if(b.closest('#segment-side')){echoTarget=row;echoUntil=Date.now()+60000;row.after(echo);echo.hidden=true;}
  else{echoTarget=null;echo.hidden=true;}
},true);
if(segStatus)new MutationObserver(()=>{
  if(!echoTarget||Date.now()>echoUntil)return;
  echo.textContent=segStatus.textContent;echo.hidden=!segStatus.textContent;
}).observe(segStatus,{childList:true,characterData:true,subtree:true});

// ---- [SIGN2MV] 「測試原唱分數」: one whole-song take where the separated original vocal stands in for
// the microphone. Everything after the input is the user's own path: 「從頭開始唱且評分」, live pitch
// detection with the time compensation, scoring, the recording with its delay correction, the
// score history. The vocal is played inside the recording's own audio context, placed on the
// recording timeline (see followRecording), and never reaches the speakers.
const originalTest={active:false};
window.sign2mvOriginalTest=originalTest;
window.sign2mvTakeTitle=title=>originalTest.active?`${title} · ${translateMessage('原唱測試')}`:title;
const testButton=document.createElement('button');
testButton.type='button';testButton.id='sign2mv-original-test';testButton.className='secondary';testButton.textContent='🧪 測試原唱分數';
testButton.title='用分離出的原唱人聲代替麥克風，跑一次跟你演唱完全相同的評分與錄音流程';
$('finish-song').after(testButton);
// The original vocal is placed on the song time directly, so it skips the speaker / hearing part of the
// latency loop that a singer has (hear the song, sing along); only the microphone part is replaced.
// It is therefore placed this much later than the song time (default 200 ms, adjustable, remembered).
const DELAY_KEY='sign2mv.original-test-delay.v1';
const testDelay=document.createElement('input');
testDelay.type='number';testDelay.id='sign2mv-original-delay';testDelay.min='0';testDelay.max='1000';testDelay.step='10';testDelay.value='200';
try{const v=localStorage.getItem(DELAY_KEY);if(v!==null&&Number.isFinite(+v)&&+v>=0&&+v<=1000)testDelay.value=String(+v);}catch{}
testDelay.addEventListener('change',()=>{const v=Math.max(0,Math.min(1000,Math.round(+testDelay.value||0)));testDelay.value=String(v);try{localStorage.setItem(DELAY_KEY,String(v));}catch{}});
const testDelayLabel=document.createElement('label');testDelayLabel.className='sign2mv-original-delay';
testDelayLabel.title='原唱少了「喇叭放出來、聽到再跟唱」那段延遲；這裡讓它晚這麼多才進來，模擬真人';
testDelayLabel.append('原唱延後',testDelay,'ms');
testButton.after(testDelayLabel);
const testStatus=document.createElement('p');
testStatus.id='sign2mv-original-test-status';testStatus.className='status';testStatus.setAttribute('role','status');testStatus.hidden=true;
const testHint=document.createElement('p');testHint.className='sign2mv-original-hint';
testHint.textContent='原唱延後＝原唱晚多少進來。結算用收音延遲往回扣；改評分延遲後，這首歌接著唱就用新值，換歌或重新整理回到收音延遲的設定（原唱測試那次不改）。';
$('finish-song').parentElement.after(testHint);testHint.after(testStatus);
function testSay(text){testStatus.textContent=text;testStatus.hidden=!text;}
// 「重新評分」: score the take just sung again at another delay (no singing again). Uses the RMVPE
// pitch kept from that take; each rescore is added to the score history as its own row.
const rescoreDelay=document.createElement('input');
rescoreDelay.type='number';rescoreDelay.id='sign2mv-rescore-delay';rescoreDelay.min='-1000';rescoreDelay.max='2000';rescoreDelay.step='10';rescoreDelay.value='400';
const rescoreLabel=document.createElement('label');rescoreLabel.className='sign2mv-original-delay';
rescoreLabel.title='唱完一次（用 RMVPE 結算）後，用不同的延遲重算剛唱完的那次，不用重唱；每次重算另存一筆分數紀錄。改了之後這首歌接著唱就用新值，換歌或重新整理回到收音延遲的設定（原唱測試那次不改）';
rescoreLabel.append('評分延遲',rescoreDelay,'ms');
const rescoreButton=document.createElement('button');
rescoreButton.type='button';rescoreButton.id='sign2mv-rescore';rescoreButton.className='secondary';rescoreButton.textContent='重新評分';
rescoreButton.title=rescoreLabel.title;
// what to rescore: the take just sung (kept in memory), or a saved whole-song recording of this song and
// key, so a reload does not mean singing again
const rescoreTake=document.createElement('select');rescoreTake.id='sign2mv-rescore-take';
const rescoreTakeLabel=document.createElement('label');rescoreTakeLabel.className='sign2mv-rescore-take';
rescoreTakeLabel.title='剛唱完的這次、這首歌這個 Key 已存的整首錄音（待確認與已存到錄音後處理的都列），或這首歌這個 Key 的 AI 翻唱版本。已存的錄音第一次重新評分要先用 RMVPE 分析幾秒，結果存回那筆錄音；AI 翻唱每次開啟頁面分析一次，不寫進翻唱檔案，評分延遲從 0 開始，版本自己的音高（例如 −12）評分時補回';
rescoreTakeLabel.append('評分對象',rescoreTake);
testDelayLabel.after(rescoreTakeLabel);rescoreTakeLabel.after(rescoreButton);rescoreButton.after(rescoreLabel);
const rescoreStatus=document.createElement('p');
rescoreStatus.id='sign2mv-rescore-status';rescoreStatus.className='status';rescoreStatus.setAttribute('role','status');rescoreStatus.hidden=true;
testStatus.after(rescoreStatus);
function rescoreSay(...parts){parts=parts.filter(Boolean);rescoreStatus.replaceChildren(...parts.flatMap((p,i)=>{const s=document.createElement('span');s.textContent=p;return i?[' ',s]:[s];}));rescoreStatus.hidden=!parts.length;}
// The delay found here is used for the next takes of this song, except after an original-vocal test
// (that take has no speaker path, so its best delay is not the singer's). It is temporary: the slider is
// only moved, not saved, so another song or a reload goes back to the saved input latency (the default).
let lastTakeTest=false,tempSong=null;
function savedLatency(){try{const v=localStorage.getItem('karaoke.input-latency.v1');if(v!==null&&Number.isFinite(+v))return +v;}catch{}return +$('offset').defaultValue;}
function showLatency(ms,temporary){const offset=$('offset');offset.value=String(ms);$('offset-value').textContent=temporary?`${ms} ms（這首歌暫用）`:`${ms} ms`;}
function syncLatency(ms){
  if(lastTakeTest)return '這次是原唱測試，收音延遲不跟著改。';
  const offset=$('offset');if(ms<+offset.min||ms>+offset.max)return `收音延遲只能設 ${offset.min}～${offset.max} ms，這次沒有跟著改。`;
  const saved=savedLatency();
  if(ms===saved){tempSong=null;showLatency(saved,false);return `下次演唱用收音延遲的設定 ${saved} ms。`;}
  tempSong=workflow().mediaId||'';showLatency(ms,true);
  return `這首歌下次演唱的延遲暫時改成 ${ms} ms；換歌或重新整理後回到收音延遲的設定 ${saved} ms。`;
}
// another song: back to the saved input latency
new MutationObserver(()=>{if(tempSong!==null&&(workflow().mediaId||'')!==tempSong){tempSong=null;showLatency(savedLatency(),false);rescoreSay();}})
  .observe($('player-section'),{attributes:true,attributeFilter:['data-workflow']});
// moving the slider by hand sets the default again (app.mjs saves it)
$('offset').addEventListener('input',()=>{tempSong=null;});
let savedTakes=[],coverTakes=[],takeListing=0,rescoreBusy=false;
const takeOption=row=>new Option([row.title,new Date(row.created).toLocaleString(),translateMessage(`${Math.round(row.seconds)} 秒`),
  ...(row.delayMs!==null?[translateMessage(`錄音時 ${row.delayMs} ms`)]:[]),...(row.pending?[translateMessage('待確認')]:[])].join(' · '),row.id);
const coverOption=v=>new Option([`${translateMessage('AI 翻唱')} ${v.title}`,...(v.created?[new Date(v.created).toLocaleString()]:[]),
  ...(v.pitch?[translateMessage(`音高 ${v.pitch>0?'+':''}${v.pitch}（評分時補回）`)]:[]),...(v.split?[translateMessage('男女分開轉換')]:[])].join(' · '),'cover:'+v.id);
function group(label,options){const g=document.createElement('optgroup');g.label=translateMessage(label);g.append(...options);return g;}
async function refreshTakes(pick=null){
  // never while a take starts or runs: listing the saved recordings is heavy for the server
  const w=workflow();if(['restarting','singing'].includes(w.phase)||w.hasTake)return;
  const serial=++takeListing;let rows=[],covers=[];
  try{rows=await window.sign2mvRescore?.saved?.()||[];}catch{rows=[];}
  try{covers=await window.sign2mvRescore?.covers?.()||[];}catch{covers=[];}
  if(serial!==takeListing)return;
  savedTakes=rows;coverTakes=covers;const keep=pick??rescoreTake.value;
  const last=window.sign2mvRescore?.delayMs?.()!=null?[new Option(translateMessage('剛唱完的這次'),'last')]:[];
  rescoreTake.replaceChildren(...last,...(rows.length?[group('已存的錄音',rows.map(takeOption))]:[]),...(covers.length?[group('AI 翻唱',covers.map(coverOption))]:[]));
  if([...rescoreTake.options].some(o=>o.value===keep))rescoreTake.value=keep;
  if(rescoreTake.value!==keep)takeChosen();
  rescoreControls();
}
function chosenSaved(){return savedTakes.find(row=>row.id===rescoreTake.value)||null;}
function chosenCover(){return rescoreTake.value.startsWith('cover:')?coverTakes.find(v=>'cover:'+v.id===rescoreTake.value)||null:null;}
// the delay field starts from the delay that take was recorded with; an AI cover is on the song's own timeline
function takeChosen(){
  const row=chosenSaved();
  if(row){lastTakeTest=row.originalTest;if(row.delayMs!==null)rescoreDelay.value=String(row.delayMs);}
  else if(chosenCover())rescoreDelay.value='0';
  else if(rescoreTake.value==='last'){lastTakeTest=lastSungTest;const last=window.sign2mvRescore?.delayMs?.()??null;if(last!==null)rescoreDelay.value=String(last);}
  rescoreSay();
}
function rescoreControls(){
  const last=window.sign2mvRescore?.delayMs?.()??null;
  const ready=rescoreTake.value==='last'?last!==null:!!(chosenSaved()||chosenCover());
  // not while a take runs: the live score uses the same RMVPE process
  const w=workflow(),working=rescoreBusy||['preparing','singing','finishing','restarting'].includes(w.phase)||!!w.busy;
  rescoreButton.disabled=rescoreDelay.disabled=working||!ready;rescoreTake.disabled=working||!rescoreTake.options.length;
  return last;
}
let lastSungTest=false;
window.addEventListener('sign2mv-rescore',()=>{lastSungTest=lastTakeTest=originalTest.active;const last=rescoreControls();if(last!==null)rescoreDelay.value=String(last);rescoreSay();
  // a take starting (no last take yet) only drops the 'just sung' entry; the list itself is refreshed after it
  if(last===null){rescoreTake.querySelector('option[value=last]')?.remove();rescoreControls();return;}
  void refreshTakes('last');setTimeout(()=>{void refreshTakes();},3000);});   // the take is archived a moment later
// after the take (result / ready), the list is refreshed once more
rescoreTake.addEventListener('change',()=>{takeChosen();rescoreControls();});
window.addEventListener('karaoke-recording-saved',()=>{void refreshTakes();});
new MutationObserver(()=>{const w=workflow(),key=`${w.reference||''}|${w.mediaId||''}`;if(key!==takesFor){takesFor=key;void refreshTakes();}else rescoreControls();})
  .observe($('player-section'),{attributes:true,attributeFilter:['data-workflow']});
let takesFor='';
// also when the page comes back (another app page, another window): a cover or a recording may be new.
// Never while a take starts or runs (refreshTakes checks), at most every 2 s.
let takesAt=0;
function refreshTakesSoon(){const now=Date.now();if(now-takesAt<2000)return;takesAt=now;void refreshTakes();}
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshTakesSoon();});
window.addEventListener('focus',refreshTakesSoon);
rescoreDelay.addEventListener('change',()=>{if(rescoreDelay.disabled)return;const ms=Math.max(-1000,Math.min(2000,Math.round(+rescoreDelay.value||0)));rescoreDelay.value=String(ms);rescoreSay(chosenCover()?'AI 翻唱的評分延遲不改收音延遲。':syncLatency(ms));});
rescoreButton.addEventListener('click',async()=>{
  const ms=Math.max(-1000,Math.min(2000,Math.round(+rescoreDelay.value||0)));rescoreDelay.value=String(ms);
  const cover=chosenCover();
  if(cover){
    rescoreBusy=true;rescoreControls();rescoreSay('正在讀取這個 AI 翻唱版本…');
    try{
      const r=await window.sign2mvRescore.runCover(cover.id,ms,percent=>rescoreSay(`正在用 RMVPE 分析 AI 翻唱人聲 ${percent}%…`));
      if(r.score===null)rescoreSay(`評分延遲 ${ms} ms 時沒有可評分的旋律。`);
      else rescoreSay(`重新評分（評分延遲 ${ms} ms）：總分 ${r.score}（音準 ${r.pitch}、節奏 ${r.rhythm}、完整度 ${r.coverage}）。${r.saved?'已另存一筆分數紀錄。':'瀏覽器不允許儲存紀錄，分數只顯示在這裡。'}`,
        `評分難度：${translateMessage(({standard:'標準',strict:'嚴格',relaxed:'寬鬆'})[r.difficulty]||'標準')}。`,'AI 翻唱的評分延遲不改收音延遲。');
    }catch(error){rescoreSay(`無法重新評分這個 AI 翻唱版本：${translateMessage(error.message)}`);void refreshTakes();}
    finally{rescoreBusy=false;rescoreControls();}
    return;
  }
  const row=chosenSaved();
  if(row){
    rescoreBusy=true;rescoreControls();rescoreSay('正在讀取這筆錄音…');
    try{
      const r=await window.sign2mvRescore.runSaved(row.id,ms,percent=>rescoreSay(`正在用 RMVPE 分析這筆錄音的乾淨歌聲 ${percent}%…`));
      const kept=r.kept?'':'分析結果沒能存回這筆錄音，下次重新評分要再分析一次。';
      if(r.score===null)rescoreSay(`評分延遲 ${ms} ms 時沒有可評分的旋律。`,kept);
      else rescoreSay(`重新評分（評分延遲 ${ms} ms）：總分 ${r.score}（音準 ${r.pitch}、節奏 ${r.rhythm}、完整度 ${r.coverage}）。${r.saved?'已另存一筆分數紀錄。':'瀏覽器不允許儲存紀錄，分數只顯示在這裡。'}`,
        `評分難度：${translateMessage(({standard:'標準',strict:'嚴格',relaxed:'寬鬆'})[r.difficulty]||'標準')}。`,kept,syncLatency(ms));
    }catch(error){rescoreSay(`無法重新評分這筆錄音：${translateMessage(error.message)}`);void refreshTakes();}
    finally{rescoreBusy=false;rescoreControls();}
    return;
  }
  const r=window.sign2mvRescore?.run?.(ms);
  if(!r){rescoreSay('沒有可以重新評分的演唱：請先唱完一次，並用 RMVPE 結算。');rescoreControls();return;}
  if(r.score===null){rescoreSay(`評分延遲 ${ms} ms 時沒有可評分的旋律。`);return;}
  rescoreSay(`重新評分（評分延遲 ${ms} ms）：總分 ${r.score}（音準 ${r.pitch}、節奏 ${r.rhythm}、完整度 ${r.coverage}）。${r.saved?'已另存一筆分數紀錄。':'瀏覽器不允許儲存紀錄，分數只顯示在這裡。'}`,syncLatency(ms));
});
rescoreControls();void refreshTakes();
function workflow(){try{return JSON.parse($('player-section').dataset.workflow||'{}');}catch{return {};}}
// the button follows 「從頭開始唱且評分」 (same conditions) and is off while a test runs
function testControls(){testButton.disabled=originalTest.active||$('sing-start').disabled||!workflow().reference;testDelay.disabled=originalTest.active;}
new MutationObserver(testControls).observe($('sing-start'),{attributes:true,attributeFilter:['disabled']});
new MutationObserver(testControls).observe($('player-section'),{attributes:true,attributeFilter:['data-workflow']});
testControls();
const waitFor=async(test,ms)=>{for(let i=0;i<ms/100&&!test();i++)await new Promise(r=>setTimeout(r,100));return test();};
function stopVoice(){try{originalTest.source?.stop();}catch{}originalTest.source?.disconnect();originalTest.source=null;}
// The stand-in microphone: built inside the context the recording and scoring use (app.mjs asks for it
// when the microphone opens), so the vocal never crosses into another audio context or stream.
window.sign2mvTestInput=null;
function testInput(context){
  const out=context.createGain(),dest=context.createMediaStreamDestination();out.connect(dest);
  originalTest.mic={context,out};
  return {stream:dest.stream,source:out,label:translateMessage('原唱人聲（測試）'),stop(){stopVoice();try{out.disconnect(dest);}catch{}dest.stream.getTracks().forEach(t=>t.stop());originalTest.mic=null;originalTest.segment=null;}};   // only our own link: the recorder disconnects its own meters from `out` afterwards
}
// Place the vocal on the recording's own timeline: while a recorded segment is open, recorded time r
// is song time segment.songTime + (r - segment.offset); the vocal there is the stem at that song time
// minus the 原唱延後 delay. Scheduled once per segment on the recording context's clock, so it is
// sample-exact and never chases the video.
function followRecording(){
  const live=window.sign2mvRecordingLive?.(),mic=originalTest.mic;
  const segment=live?.recording()?live.segments.at(-1):null;
  if(!mic||!live||live.context!==mic.context||!segment||segment.duration){if(originalTest.segment){stopVoice();originalTest.segment=null;}}
  else if(originalTest.segment!==segment){
    stopVoice();originalTest.segment=segment;
    const ctx=mic.context,t0=live.contextTimeOf(segment.offset);   // context time where this segment began
    if(t0!==null){
      const when=Math.max(ctx.currentTime+.05,t0+Math.max(0,originalTest.delay-segment.songTime));
      const at=segment.songTime-originalTest.delay+(when-t0);
      if(at<originalTest.buffer.duration){
        const s=ctx.createBufferSource();s.buffer=originalTest.buffer;s.connect(mic.out);s.start(when,Math.max(0,at));
        originalTest.source=s;originalTest.resyncs++;
      }
    }
  }
  const w=workflow();
  if(w.reference!==originalTest.cacheId){void endOriginalTest(false);return;}   // another song was loaded
  if(w.phase==='singing')originalTest.seen=true;
  // done once the take is settled (finish() has already closed the stand-in microphone and saved the take)
  if(originalTest.seen&&['result','ready','idle'].includes(w.phase))void endOriginalTest(true);
  else if(!originalTest.seen&&Date.now()-originalTest.began>60000)void endOriginalTest(false);
}
async function endOriginalTest(finished){
  if(!originalTest.active||originalTest.ending)return;
  originalTest.ending=true;
  clearInterval(originalTest.timer);stopVoice();
  if(!$('mic-stop').disabled){$('mic-stop').click();await waitFor(()=>$('mic-stop').disabled,5000);}
  window.sign2mvTestInput=null;
  if(originalTest.captureMode)$('capture-mode').value=originalTest.captureMode;
  const total=$('total-score').textContent.trim();
  Object.assign(originalTest,{active:false,ending:false,buffer:null,mic:null,segment:null});
  testSay(finished&&/^\d+$/.test(total)
    ?`原唱測試完成（原唱延後 ${Math.round(originalTest.delay*1000)} ms）：總分 ${total}（音準 ${$('pitch-score').textContent}、節奏 ${$('rhythm-score').textContent}、完整度 ${$('coverage-score').textContent}）。錄音已保存並標成「原唱測試」；存到錄音後處理後按「錄音重新評分」，可看到套用歌聲延時校正後的分數。下次按「從頭開始唱且評分」會改回你的麥克風。`
    :'原唱測試沒有完成，下次按「從頭開始唱且評分」會使用你的麥克風。');
  testControls();
}
testButton.addEventListener('click',async()=>{
  if(originalTest.active)return;
  const cacheId=workflow().reference;
  if(!cacheId){testSay('請先載入歌曲並準備好歌曲基準。');return;}
  testButton.disabled=true;testSay('正在讀取原唱人聲…');
  let ctx;
  try{
    const tk=await token(),headers={'X-Karaoke-Token':tk};
    const ref=await (await fetch(`/sr/library/${encodeURIComponent(cacheId)}/reference`,{headers,cache:'no-store'})).json();
    // the same vocal the reference melody was taken from (the lead line when the song was split that way)
    const stem=ref.vocalMode==='lead'?'lead':'vocals';
    const r=await fetch(`/sr/library/${encodeURIComponent(cacheId)}/${stem}`,{headers,cache:'no-store'});
    if(!r.ok)throw Error('這首歌沒有保留原唱人聲音軌，請先在「歌曲準備」按「補建試聽音軌」。');
    ctx=new AudioContext({latencyHint:'interactive',sinkId:{type:'none'}});   // only to decode; the buffer is played in the recording context
    const buffer=await ctx.decodeAudioData(await r.arrayBuffer());await ctx.close().catch(()=>{});ctx=null;
    // a microphone that is already open is closed first, so 「從頭開始唱且評分」 opens this one
    if(!$('mic-stop').disabled){$('mic-stop').click();if(!await waitFor(()=>$('mic-stop').disabled,5000))throw Error('麥克風沒有關閉，請先按「停止收音」再試。');}
    Object.assign(originalTest,{active:true,cacheId,seen:false,ending:false,began:Date.now(),buffer,mic:null,segment:null,
      source:null,resyncs:0,captureMode:$('capture-mode').value,delay:Math.max(0,Math.min(1000,+testDelay.value||0))/1000});
    $('capture-mode').value='browser';   // the test input replaces the browser microphone; restored afterwards
    window.sign2mvTestInput=testInput;
    originalTest.timer=setInterval(followRecording,20);
    testSay('原唱測試進行中：用原唱人聲代替麥克風，從頭唱完整首（跟你演唱時一樣，約一首歌的時間）。可按「結束並結算」提早結束。');
    $('sing-start').click();
  }catch(error){
    if(!originalTest.active)await ctx?.close().catch(()=>{});
    else await endOriginalTest(false);
    window.sign2mvTestInput=null;
    testSay(error.message);testControls();
  }
});
