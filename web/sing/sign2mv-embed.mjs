// SIGN2MV glue for the sing & record page (runs inside the SIGN2MV window).
import {selectMediaSource} from './media-source.mjs';
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
function busyPhase(){
  try{const w=JSON.parse($('player-section').dataset.workflow||'{}');return !!(w.hasTake||w.busy||['singing','preparing','finishing','restarting'].includes(w.phase));}catch{return false;}
}
window.addEventListener('message',event=>{
  if(event.origin!==location.origin||event.source!==parentWindow)return;
  const m=event.data||{};
  if(m.type==='sign2mv:select-song'&&typeof m.songId==='string')void selectSong(m.songId);
  if(m.type==='sign2mv:refresh-songs')kind.dispatchEvent(new Event('change'));
  if(m.type==='sign2mv:lang'){
    try{localStorage.setItem('karaoke.language.v1',m.lang==='en'?'en':'zh-Hant');}catch{}
    if(!busyPhase())location.reload();
  }
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
