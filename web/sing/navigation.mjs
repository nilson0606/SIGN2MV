// Navigation and guidance only observe state; they never start or stop audio.
const $ = id => document.getElementById(id);
const nav = document.querySelector('.section-nav');
const links = [...nav.querySelectorAll('.nav-links a[href^="#"]')];
let preferredHash = '', scrollFrame = 0;
function visible(node) { return !!node?.getClientRects().length; }
function highlight() {
  scrollFrame = 0;
  const line = nav.getBoundingClientRect().bottom + 24;
  const candidates = links.map(link => ({link, node:$(link.hash.slice(1))}))
    .filter(item => visible(item.node)).map(item => ({...item, box:item.node.getBoundingClientRect()}));
  const covering = candidates.filter(item => item.box.top <= line && item.box.bottom > line);
  // Nested sections take precedence; side-by-side cards retain the last chosen side.
  covering.sort((a,b) => b.box.top-a.box.top || Number(b.link.hash===preferredHash)-Number(a.link.hash===preferredHash));
  const next = candidates.filter(item => item.box.top > line && item.box.top < innerHeight)
    .sort((a,b) => a.box.top-b.box.top)[0];
  const active = covering[0] || next;
  for (const link of links) {
    if (link===active?.link) link.setAttribute('aria-current','location');
    else link.removeAttribute('aria-current');
  }
}
function scheduleHighlight() { if (!scrollFrame) scrollFrame=requestAnimationFrame(highlight); }
new ResizeObserver(() => {
  document.documentElement.style.setProperty('--nav-offset',`${nav.offsetHeight+16}px`);
  scheduleHighlight();
}).observe(nav);
window.addEventListener('scroll',scheduleHighlight,{passive:true});
window.addEventListener('resize',scheduleHighlight);
document.addEventListener('toggle',scheduleHighlight,true);
function visit(hash, behavior) {
  if (!hash.startsWith('#')) return;
  const target=$(hash.slice(1)); if (!target) return;
  for (let node=target;node;node=node.parentElement) if (node instanceof HTMLDetailsElement) node.open=true;
  if (!visible(target)) return;
  preferredHash=hash;
  if (!target.hasAttribute('tabindex')) target.tabIndex=-1;
  target.focus({preventScroll:true});target.scrollIntoView({block:'start',...(behavior?{behavior}:{})});
  scheduleHighlight();
}
nav.addEventListener('click',event=>{
  const link=event.target.closest('a');
  if (!link||!link.hash||link.target==='_blank'||event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey) return;
  event.preventDefault();history.replaceState(null,'',link.hash);visit(link.hash);
});
window.addEventListener('hashchange',()=>visit(location.hash));
const reloaded=performance.getEntriesByType('navigation')[0]?.type==='reload';
if (reloaded) {
  // A fresh recording session starts at microphone setup, not the last bookmark.
  history.scrollRestoration='manual';
  history.replaceState(history.state,'',location.pathname+location.search+'#voice-settings');
  const startAtMic=()=>requestAnimationFrame(()=>{
    document.documentElement.style.setProperty('--nav-offset',`${nav.offsetHeight+16}px`);
    visit('#voice-settings','instant');
  });
  if (document.readyState==='complete') startAtMic();
  else window.addEventListener('pageshow',startAtMic,{once:true});
} else if (location.hash) requestAnimationFrame(()=>visit(location.hash));
scheduleHighlight();

let micChecked=false, nativeConfigured=false, settingsConfirmed=false, scope='', saved=false, listened='', segmentMode=false;
let confirmAction=null, guideFrame=0;
const state=()=>{try{return JSON.parse($('player-section').dataset.workflow||'{}');}catch{return {};}};
function reviewKey(s) {
  return s.segmented ? `segment:${$('segment-take').value}:${$('segment-audio').getAttribute('src')||''}` : `whole:${$('recording-review-take').value}`;
}
function showStep(number,title,message,target,navTarget,actionLabel='',action=null) {
  const key=JSON.stringify([number,title,message,target,navTarget,actionLabel]);
  if ($('workflow-message').dataset.content===key) return;
  $('workflow-message').dataset.content=key;
  $('workflow-message').dataset.step=number;
  const strong=document.createElement('strong');strong.textContent=`下一步 ${number}／8 · ${title}`;
  const span=document.createElement('span');span.textContent=message;
  $('workflow-message').replaceChildren(strong,span);
  const go=$('workflow-go');go.setAttribute('href','#'+target);go.textContent='前往'+title;
  $('workflow-confirm').hidden=!actionLabel;$('workflow-confirm').textContent=actionLabel;confirmAction=action;
  for (const link of links) link.toggleAttribute('data-next',link.hash==='#'+navTarget);
}
function updateGuide() {
  guideFrame=0;
  const s=state(), localReady=$('local-section').dataset.state==='ready';
  const nextScope=s.reference||s.mediaId||'';
  if (scope!==nextScope) {scope=nextScope;settingsConfirmed=false;saved=false;listened='';}
  if (segmentMode!==!!s.segmented) {segmentMode=!!s.segmented;settingsConfirmed=false;saved=false;listened='';}
  if (s.micReady) micChecked=true;
  if (s.busy||s.hasTake||['restarting','finishing'].includes(s.phase)) {
    settingsConfirmed=true;
    const working=s.segmented&&$('segment-stop').disabled;
    showStep(6,'錄唱',s.phase==='finishing'||working?'正在處理錄音，請等待完成。':'錄唱進行中；完成後停止並保存，再試聽。',s.segmented?(working?'segment-status':'segment-stop'):'finish-song','player-section');return;
  }
  if (saved) {showStep(8,'錄音後處理','已存入後處理，可調整效果、輸出音檔或 MV。','recording-post','recording-post');return;}
  const pending=s.segmented ? !!$('segment-take').value : !$('recording-review').hidden;
  if (pending&&(settingsConfirmed||s.phase==='result')) {
    const heard=listened===reviewKey(s);
    if (heard) {
      showStep(8,'滿意後保存',s.segmented?'分段需先試合完整一版；滿意後按「存到錄音後處理」。':'滿意後按「存到錄音後處理」；也可以重錄。',s.segmented?'segment-output-panel':'recording-review-save',s.segmented?'player-section':'score-section');
    } else showStep(7,'試聽',s.segmented?'挑選各段版本並試聽，再試合完整一版。':'先試聽這次錄音，確認是否滿意。',s.segmented?'segment-versions-panel':'recording-review',s.segmented?'player-section':'score-section');
    return;
  }
  if (!micChecked && !nativeConfigured) {
    const native=$('capture-mode').value==='native';
    showStep(1,'確認收音',native&&!localReady?'先選收音方式與裝置；本機相容收音須先連上本機工具，才能試聲。':'先確認收音方式與麥克風，再開麥試聲；單獨試聲不保存錄音。',native&&!localReady?'voice-settings':'mic-start','voice-settings',native&&!localReady?'收音方式已確認':'',()=>{nativeConfigured=true;updateGuide();});return;
  }
  if (!localReady) {showStep(2,'本機工具','確認本機工具已啟動、歌曲庫可用，再開始選歌。','local-section','local-section');return;}
  if (!micChecked) {showStep(1,'確認收音','本機工具已就緒，現在開麥試聲，確認收音。','mic-start','voice-settings');return;}
  if (!s.mediaId&&!s.reference) {showStep(3,'選歌','從歌曲庫選歌，或在播放器載入 YouTube／本機 MV。','library-panel','library-panel');return;}
  if (!s.prepared || Number($('song-key').value)!==s.pitchShift) {
    showStep(4,'歌曲準備與 Key',s.phase==='preparing'?'正在準備，完成後會繼續下一步。':'確認歌曲 Key；新版本需建立基準，已有版本可直接載入。','prepare-section','prepare-section');return;
  }
  if (!settingsConfirmed) {
    showStep(5,'演唱設定','確認帶唱方式、人聲／伴樂比例；沿用上次設定也可以。',s.segmented?'segment-guide-mode':'sing-guide-mode','player-section','設定已確認',()=>{settingsConfirmed=true;updateGuide();});return;
  }
  showStep(6,'開始錄唱',s.segmented?'選好段落，按「錄這一段」。循環練唱不會錄音。':'按「從頭開始唱」開始整首錄音；也可切換分段模式。',s.segmented?'segment-record':'sing-start','player-section');
}
function scheduleGuide() {if (!guideFrame) guideFrame=requestAnimationFrame(updateGuide);}
$('workflow-confirm').addEventListener('click',()=>confirmAction?.());
for (const id of ['capture-mode','input-device']) $(id).addEventListener('change',()=>{micChecked=false;nativeConfigured=false;scheduleGuide();});
for (const id of ['sing-guide-mode','segment-guide-mode','recording-manual','recording-voice-level','recording-backing-level','segment-manual','segment-voice-level','segment-backing-level','song-key']) $(id).addEventListener('change',()=>{settingsConfirmed=false;saved=false;scheduleGuide();});
for (const id of ['recording-review-take','segment-take','recording-review-mode','segment-take-mode-selected']) $(id).addEventListener('change',()=>{saved=false;listened='';scheduleGuide();});
for (const id of ['recording-review-audio','segment-take-audio','segment-audio']) $(id).addEventListener('playing',()=>{listened=reviewKey(state());settingsConfirmed=true;scheduleGuide();});
window.addEventListener('karaoke-recording-saved',event=>{if(event.detail.cacheId===state().reference){saved=true;scheduleGuide();}});
for (const id of ['sing-start','segment-record']) $(id).addEventListener('click',()=>{saved=false;listened='';scheduleGuide();});
// Observe only state and review controls, never the high-frequency pitch graph/clock.
const observer=new MutationObserver(scheduleGuide);
for (const id of ['player-section','local-section','recording-review','segment-take','recording-review-take','segment-audio']) observer.observe($(id),{attributes:true,attributeFilter:['data-workflow','data-state','hidden','src'],childList:id.endsWith('take'),subtree:false});
updateGuide();
