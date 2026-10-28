import {detectPitch} from './audio.mjs';
import {mixSettings} from './recording-mix.mjs';
import {originalVocalRanges} from './recording-process.mjs';
// Non-destructive edit decisions use song seconds; source files are never changed.
export async function segmentMixMetadata(raw,meta,balance) {
  // Old segment takes did not collect pitch samples. Analyze only for gain gating;
  // this never creates a score or changes the saved source recording.
  const factor=2 ** ((meta.post?.reference?.pitchShift || 0)/12);
  const samples=[],data=raw.getChannelData(0),rate=raw.sampleRate,size=Math.round(rate*.128),window=new Float32Array(size);
  for(let i=0;i<raw.length;i+=Math.round(rate*.1)){
    window.fill(0);const start=i-Math.floor(size/2),from=Math.max(0,start),end=Math.min(data.length,start+size);
    window.set(data.subarray(from,end),from-start);
    const hz=detectPitch(window,rate/factor).hz;
    samples.push({offset:i/rate,hz:hz===null?null:hz*factor});
    if(samples.length%50===0)await new Promise(resolve=>setTimeout(resolve,0));
  }
  const result={...meta,balance:mixSettings(balance),post:{...meta.post,samples}};
  delete result.fixedMixGains;
  return result;
}
export function segmentDraft(reference) {
  const duration=reference.duration;
  if(!Number.isFinite(duration)||duration<=0||duration>1800)throw Error('分段錄音支援 30 分鐘內的歌曲。');
  return {version:1,key:reference.cacheId,duration,baseId:null,parts:[{id:crypto.randomUUID(),name:'第 1 段',autoName:true,start:0,end:duration,takeId:null}]};
}
export function normalizeSegmentNames(draft) {
  draft.parts.forEach((p,i)=>{
    // Recognize the default names emitted by older drafts, including nested splits.
    if(typeof p.autoName!=='boolean')p.autoName=/^第\s*\d+\s*段(?:（後段）)*$/.test(p.name);
    if(p.autoName)p.name=`第 ${i+1} 段`;
  });
  return draft;
}
export function validateSegmentDraft(draft) {
  if(draft?.version!==1||!Number.isFinite(draft.duration)||draft.duration<=0||draft.duration>1800||!Array.isArray(draft.parts)||!draft.parts.length||draft.parts.length>200)throw Error('分段草稿格式無效。');
  let end=0;const ids=new Set();
  for(const p of draft.parts){
    if(typeof p.id!=='string'||ids.has(p.id)||typeof p.name!=='string'||p.name.length>80||!Number.isFinite(p.start)||!Number.isFinite(p.end)||Math.abs(p.start-end)>1e-6||p.end-p.start<.099||p.end>draft.duration+1e-6)throw Error('段落需連續且不可重疊，每段至少 0.1 秒。');
    ids.add(p.id);end=p.end;
  }
  if(Math.abs(end-draft.duration)>1e-6)throw Error('段落需涵蓋完整歌曲。');
  originalVocalRanges(draft.originalVocalRanges,draft.duration);
  return draft;
}
export function splitSegment(draft,time) {
  validateSegmentDraft(draft);time=Math.round(time*1000)/1000;
  if(draft.parts.length>=200)throw Error('最多保留 200 段。');
  const i=draft.parts.findIndex(p=>time>=p.start+.1&&time<=p.end-.1);
  if(i<0)throw Error('分界需離相鄰分界至少 0.1 秒。');
  normalizeSegmentNames(draft);
  const p=draft.parts[i],next={...p,id:crypto.randomUUID(),name:p.name+'（後段）',start:time};
  next.name=next.name.slice(0,80);p.end=time;draft.parts.splice(i+1,0,next);normalizeSegmentNames(draft);return i+1;
}
export function moveBoundary(draft,index,time) {
  if(!Number.isInteger(index)||index<1||index>=draft.parts.length)throw Error('請選擇內部分界；歌曲起訖固定。');
  time=Math.round(time*1000)/1000;
  if(!Number.isFinite(time)||time<draft.parts[index-1].start+.1||time>draft.parts[index].end-.1)throw Error('分界不能越過相鄰段落，每段至少 0.1 秒。');
  draft.parts[index-1].end=time;draft.parts[index].start=time;return validateSegmentDraft(draft);
}
export function mergeBoundary(draft,index) {
  if(index<1||index>=draft.parts.length)throw Error('請選擇內部分界。');
  const prev=draft.parts[index-1],next=draft.parts[index];
  // A merged section has one source choice. Keep all recorded versions elsewhere.
  prev.end=next.end;if(prev.takeId!==next.takeId)prev.takeId=null;
  draft.parts.splice(index,1);return normalizeSegmentNames(validateSegmentDraft(draft));
}
export function formatSegmentTime(seconds){const ms=Math.round(Math.max(0,seconds)*1000);return `${String(Math.floor(ms/60000)).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}.${String(ms%1000).padStart(3,'0')}`;}
export function parseSegmentTime(value){if(!/^\d{1,3}:[0-5]\d(?:\.\d{1,3})?$/.test(value.trim()))throw Error('時間請輸入 mm:ss 或 mm:ss.sss。');const [m,s]=value.split(':');return Number(m)*60+Number(s);}
export function sourceOffset(meta,time) {
  const s=meta?.post?.segments?.find(s=>time>=s.songTime&&time<s.songTime+s.duration);
  return s?s.offset+time-s.songTime:null;
}
export function missingSegmentRanges(draft,rows,delayMs=300,useOriginal=false) {
  validateSegmentDraft(draft);const shift=delayMs/1000,result=[];
  const replaced=useOriginal?originalVocalRanges(draft.originalVocalRanges,draft.duration).filter(r=>r.mode==='original'):[];
  for(const p of draft.parts){
    let needed=[[p.start,p.end]];
    for(const r of replaced)needed=needed.flatMap(([a,b])=>r.end<=a||r.start>=b?[[a,b]]:[[a,Math.min(b,r.start)],[Math.max(a,r.end),b]].filter(([start,end])=>end>start));
    const row=rows.find(r=>r.id===(p.takeId||draft.baseId));
    for(const [start,until]of needed){
    const end=Math.min(draft.duration,until+shift);let cursor=Math.max(0,start+shift);
    // Player end notifications and the PCM clock can differ slightly at EOF.
    // Allow the same 150 ms clock tolerance as recording timeline sync only at
    // the song's end; missing sources and gaps inside the song still fail.
    const endTolerance=end===draft.duration ? .15 : .03;let covered=false;
    const intervals=(row?.rawBytes?row.post?.segments||[]:[]).map(s=>[s.songTime,s.songTime+Math.min(s.duration,Math.max(0,(row.seconds??Infinity)-s.offset))]).sort((a,b)=>a[0]-b[0]);
    for(const [a,b]of intervals){if(b<=cursor)continue;if(a>cursor+.03)break;covered=true;cursor=Math.max(cursor,b);if(cursor>=end-.03)break;}
    if(cursor<end-.03&&(!covered||cursor<end-endTolerance)){result.push(p.name);break;}
    }
  }
  return result;
}
export function composeSegmentVoice(draft,sources,{sampleRate=48000,delayMs=300,crossfade=.012}={}) {
  validateSegmentDraft(draft);
  if(!Number.isFinite(delayMs)||Math.abs(delayMs)>2000||!Number.isFinite(crossfade)||crossfade<0||crossfade>.1)throw Error('合成校正或交叉淡化設定無效。');
  const shift=delayMs/1000,length=Math.ceil((draft.duration+Math.max(0,shift))*sampleRate),out=new AudioBuffer({numberOfChannels:1,length,sampleRate}),data=out.getChannelData(0);
  const sample=(part,time)=>{
    const source=sources.get(part.takeId||draft.baseId);if(!source)return null;
    const at=sourceOffset(source.meta,time);if(at===null)return null;
    const index=at*source.audio.sampleRate,k=Math.floor(index),a=source.audio.getChannelData(0);if(k<0||k>=a.length)return null;
    return a[k]+((a[k+1]??a[k])-a[k])*(index-k);
  };
  let partIndex=0;
  for(let i=0;i<length;i++){
    const rawTime=i/sampleRate,t=rawTime-shift;
    while(partIndex<draft.parts.length-1&&t>=draft.parts[partIndex].end)partIndex++;
    const p=draft.parts[partIndex];let v=sample(p,rawTime)??0;
    // Cut on the corrected song clock; retain uncorrected raw PCM for post editing.
    // Crossfades use the recorded handles only when both sources actually exist.
    for(const j of [partIndex-1,partIndex]){
      if(j<0||j>=draft.parts.length-1)continue;
      const left=draft.parts[j],right=draft.parts[j+1],width=Math.min(crossfade,(left.end-left.start)/4,(right.end-right.start)/4),d=t-left.end;
      if(width>0&&Math.abs(d)<width){const a=sample(left,rawTime),b=sample(right,rawTime);if(a!==null&&b!==null){const weight=(d+width)/(2*width);v=a*(1-weight)+b*weight;}break;}
    }
    data[i]=v;
  }
  return out;
}
