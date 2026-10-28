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
