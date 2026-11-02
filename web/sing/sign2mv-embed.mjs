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
    // 「測試原唱分數」: the original vocal is the microphone for this one take
    if(window.sign2mvOriginalTest?.active&&window.sign2mvOriginalTest.dest&&constraints?.audio&&!constraints.video)
      return Promise.resolve(window.sign2mvOriginalTest.dest.stream);
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
// the microphone. Everything after the input is the user's own path: 「從頭開始唱」, live pitch
// detection with the time compensation, scoring, the recording with its delay correction, the
// score history. The vocal follows the song player (play, pause, seek) through its own audio graph
// that never reaches the speakers; the page asks for a microphone and gets this stream instead.
const originalTest={active:false};
window.sign2mvOriginalTest=originalTest;
window.sign2mvTakeTitle=title=>originalTest.active?`${title} · ${translateMessage('原唱測試')}`:title;
const testButton=document.createElement('button');
testButton.type='button';testButton.id='sign2mv-original-test';testButton.className='secondary';testButton.textContent='🧪 測試原唱分數';
testButton.title='用分離出的原唱人聲代替麥克風，跑一次跟你演唱完全相同的評分與錄音流程';
$('finish-song').after(testButton);
// The original vocal follows the video directly, so it skips the speaker / hearing part of the
// latency loop that a singer has (hear the song, sing along); only the microphone part is replaced.
// It is therefore played this much later than the video (default 200 ms, adjustable, remembered).
const DELAY_KEY='sign2mv.original-test-delay.v1';
const testDelay=document.createElement('input');
testDelay.type='number';testDelay.id='sign2mv-original-delay';testDelay.min='0';testDelay.max='1000';testDelay.step='10';testDelay.value='200';
try{const v=localStorage.getItem(DELAY_KEY);if(v!==null&&Number.isFinite(+v)&&+v>=0&&+v<=1000)testDelay.value=String(+v);}catch{}
testDelay.addEventListener('change',()=>{const v=Math.max(0,Math.min(1000,Math.round(+testDelay.value||0)));testDelay.value=String(v);try{localStorage.setItem(DELAY_KEY,String(v));}catch{}});
const testDelayLabel=document.createElement('label');testDelayLabel.className='sign2mv-original-delay';
testDelayLabel.title='原唱直接跟著影片，少了「喇叭放出來、聽到再跟唱」那段延遲；這裡補上，讓它跟真人一樣晚到';
testDelayLabel.append('原唱延後',testDelay,'ms');
testButton.after(testDelayLabel);
const testStatus=document.createElement('p');
testStatus.id='sign2mv-original-test-status';testStatus.className='status';testStatus.setAttribute('role','status');testStatus.hidden=true;
$('finish-song').parentElement.after(testStatus);
function testSay(text){testStatus.textContent=text;testStatus.hidden=!text;}
function workflow(){try{return JSON.parse($('player-section').dataset.workflow||'{}');}catch{return {};}}
// the button follows 「從頭開始唱」 (same conditions) and is off while a test runs
function testControls(){testButton.disabled=originalTest.active||$('sing-start').disabled||!workflow().reference;testDelay.disabled=originalTest.active;}
new MutationObserver(testControls).observe($('sing-start'),{attributes:true,attributeFilter:['disabled']});
new MutationObserver(testControls).observe($('player-section'),{attributes:true,attributeFilter:['data-workflow']});
testControls();
function songPlayer(){
  for(const id of ['local-video','local-audio']){const el=$(id);if(el&&!el.hidden&&el.currentSrc)return el;}
  return null;
}
const waitFor=async(test,ms)=>{for(let i=0;i<ms/100&&!test();i++)await new Promise(r=>setTimeout(r,100));return test();};
function stopVoice(){try{originalTest.source?.stop();}catch{}originalTest.source?.disconnect();originalTest.source=null;}
function startVoice(at,rate){
  stopVoice();
  const s=originalTest.ctx.createBufferSource();s.buffer=originalTest.buffer;s.playbackRate.value=rate;s.connect(originalTest.dest);
  s.start(0,Math.max(0,Math.min(at,originalTest.buffer.duration)));
  originalTest.source=s;originalTest.startedAt=originalTest.ctx.currentTime;originalTest.offset=at;originalTest.rate=rate;originalTest.resyncs++;
}
// keep the vocal on the song clock; restart it only when it is clearly off (a seek, a pause, drift)
function followPlayer(){
  const p=songPlayer();
  if(p&&!p.paused&&!p.ended&&p.readyState>=2){
    const want=p.currentTime-originalTest.delay;   // where the vocal should be now
    const at=originalTest.source?originalTest.offset+(originalTest.ctx.currentTime-originalTest.startedAt)*originalTest.rate:null;
    if(want<0){if(originalTest.source)stopVoice();}
    else if(at===null||originalTest.rate!==p.playbackRate||Math.abs(at-want)>.08)startVoice(want,p.playbackRate);
  }else if(originalTest.source)stopVoice();
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
  await originalTest.ctx?.close().catch(()=>{});
  if(originalTest.captureMode)$('capture-mode').value=originalTest.captureMode;
  const total=$('total-score').textContent.trim();
  Object.assign(originalTest,{active:false,ending:false,ctx:null,buffer:null,dest:null});
  testSay(finished&&/^\d+$/.test(total)
    ?`原唱測試完成（原唱延後 ${Math.round(originalTest.delay*1000)} ms）：總分 ${total}（音準 ${$('pitch-score').textContent}、節奏 ${$('rhythm-score').textContent}、完整度 ${$('coverage-score').textContent}）。錄音已保存並標成「原唱測試」；存到錄音後處理後按「錄音重新評分」，可看到套用歌聲延時校正後的分數。下次按「從頭開始唱」會改回你的麥克風。`
    :'原唱測試沒有完成，下次按「從頭開始唱」會使用你的麥克風。');
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
    ctx=new AudioContext({latencyHint:'interactive'});
    const buffer=await ctx.decodeAudioData(await r.arrayBuffer());
    // a microphone that is already open is closed first, so 「從頭開始唱」 opens this one
    if(!$('mic-stop').disabled){$('mic-stop').click();if(!await waitFor(()=>$('mic-stop').disabled,5000))throw Error('麥克風沒有關閉，請先按「停止收音」再試。');}
    Object.assign(originalTest,{active:true,cacheId,seen:false,ending:false,began:Date.now(),ctx,buffer,dest:ctx.createMediaStreamDestination(),
      source:null,resyncs:0,captureMode:$('capture-mode').value,delay:Math.max(0,Math.min(1000,+testDelay.value||0))/1000});
    $('capture-mode').value='browser';   // the stand-in arrives through the browser path; restored afterwards
    await ctx.resume().catch(()=>{});
    originalTest.timer=setInterval(followPlayer,40);
    testSay('原唱測試進行中：用原唱人聲代替麥克風，從頭唱完整首（跟你演唱時一樣，約一首歌的時間）。可按「結束並結算」提早結束。');
    $('sing-start').click();
  }catch(error){
    if(!originalTest.active)await ctx?.close().catch(()=>{});
    else await endOriginalTest(false);
    testSay(error.message);testControls();
  }
});
