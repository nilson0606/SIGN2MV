// [SIGN2MV] Headphone options for the guide audio (the song itself, backing-only, key versions, the segment
// monitor): mono (the same sound in both ears) and a mute switch per ear, for singing with one ear uncovered.
// Default = stereo, both ears on, exactly as before: the song element is only routed through Web Audio once
// one of the options has been changed.
const KEY='sign2mv.sing.mono';
let mono=false;
try{mono=localStorage.getItem(KEY)==='1';}catch{/* storage blocked: stays stereo */}
const ears={left:true,right:true};   // not remembered: a muted ear after a restart would look like a fault
const outs=new Set();
let mediaContext=null;
const routed=new WeakSet();

export const monoOn=()=>mono;
const changed=()=>mono||!ears.left||!ears.right;

function apply(o){
  // input: one channel when mono ('speakers' mixes L and R evenly), else as the source is
  o.input.channelCount=mono?1:2;o.input.channelCountMode=mono?'explicit':'max';o.input.channelInterpretation='speakers';
  o.left.gain.value=ears.left?1:0;o.right.gain.value=ears.right?1:0;
}

// Where guide audio of this context should connect, instead of context.destination.
// input -> (always two channels, mono copied to both) -> split -> left/right gain -> merge -> speakers
export function guideOut(context){
  if(!context.__sign2mvGuide){
    const input=context.createGain(),two=context.createGain(),split=context.createChannelSplitter(2),
      merge=context.createChannelMerger(2),left=context.createGain(),right=context.createGain();
    two.channelCount=2;two.channelCountMode='explicit';two.channelInterpretation='speakers';
    input.connect(two);two.connect(split);split.connect(left,0);split.connect(right,1);
    left.connect(merge,0,0);right.connect(merge,0,1);merge.connect(context.destination);
    const o={input,left,right};apply(o);context.__sign2mvGuide=o;outs.add(new WeakRef(o));
  }
  return context.__sign2mvGuide.input;
}

function routeMedia(element){
  if(!element||routed.has(element))return;
  try{
    mediaContext??=new AudioContext();
    mediaContext.createMediaElementSource(element).connect(guideOut(mediaContext));
    routed.add(element);
    element.addEventListener('play',()=>{mediaContext.resume().catch(()=>{});});
  }catch{/* not routable: it plays as before */}
}
const mediaElements=()=>['local-video','local-audio'].map(id=>document.getElementById(id));

function update(){
  for(const ref of [...outs]){const o=ref.deref();if(o)apply(o);else outs.delete(ref);}
  if(changed())mediaElements().forEach(routeMedia);
  mediaContext?.resume().catch(()=>{});
}

export function setMono(value){
  mono=!!value;
  try{localStorage.setItem(KEY,mono?'1':'0');}catch{/* this session only */}
  update();
}
export function setEar(side,on){if(side in ears){ears[side]=!!on;update();}}

export function initMono(checkbox,left,right){
  if(changed())mediaElements().forEach(routeMedia);
  if(checkbox){checkbox.checked=mono;checkbox.addEventListener('change',()=>setMono(checkbox.checked));}
  for(const [side,box] of [['left',left],['right',right]]){
    if(!box)continue;box.checked=ears[side];box.addEventListener('change',()=>setEar(side,box.checked));
  }
}
