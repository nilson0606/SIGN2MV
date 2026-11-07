// [SIGN2MV] Headphone mono: the guide audio (the song itself, backing-only, key versions, the segment
// monitor) plays as the same sound in both ears, for singing with one ear uncovered. Off = stereo,
// exactly as before: the song element is only routed through Web Audio once mono has been turned on.
const KEY='sign2mv.sing.mono';
let on=false;
try{on=localStorage.getItem(KEY)==='1';}catch{/* storage blocked: stays stereo */}
const outs=new Set();
let mediaContext=null;
const routed=new WeakSet();

export const monoOn=()=>on;

function shape(gain){
  // one channel, then the destination spreads it to both speakers ('speakers' mixes L and R evenly)
  gain.channelCount=on?1:2;gain.channelCountMode=on?'explicit':'max';gain.channelInterpretation='speakers';
}

// Where guide audio of this context should connect, instead of context.destination.
export function guideOut(context){
  if(!context.__sign2mvGuide){
    const gain=context.createGain();shape(gain);gain.connect(context.destination);
    context.__sign2mvGuide=gain;outs.add(new WeakRef(gain));
  }
  return context.__sign2mvGuide;
}

function routeMedia(element){
  if(!element||routed.has(element))return;
  try{
    mediaContext??=new AudioContext();
    mediaContext.createMediaElementSource(element).connect(guideOut(mediaContext));
    routed.add(element);
    element.addEventListener('play',()=>{mediaContext.resume().catch(()=>{});});
  }catch{/* not routable: it stays stereo */}
}
const mediaElements=()=>['local-video','local-audio'].map(id=>document.getElementById(id));

export function setMono(value){
  on=!!value;
  try{localStorage.setItem(KEY,on?'1':'0');}catch{/* this session only */}
  for(const ref of [...outs]){const gain=ref.deref();if(gain)shape(gain);else outs.delete(ref);}
  if(on)mediaElements().forEach(routeMedia);
  mediaContext?.resume().catch(()=>{});
}

export function initMono(checkbox){
  if(on)mediaElements().forEach(routeMedia);
  if(!checkbox)return;
  checkbox.checked=on;
  checkbox.addEventListener('change',()=>setMono(checkbox.checked));
}
