// Offline, opt-in processing of the dry singer only. No clock or length changes.
// Pitch synthesis follows TD-PSOLA: https://praat.org/manual/overlap-add.html
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const midi=hz=>69+12*Math.log2(hz/440),frequency=note=>440*2**((note-69)/12);
export function repairSettings(value={}){
  const number=(x,d,a,b,label)=>{const v=x===undefined?d:x;if(!Number.isFinite(v)||v<a||v>b)throw Error(`${label}需介於 ${a} 與 ${b}。`);return v;};
  const c=value.cleanup??{},p=value.pitchCorrection??{};
  const cleanup={noise:number(c.noise,0,0,100,'降噪強度'),deess:number(c.deess,0,0,100,'齒音抑制'),deessHz:number(c.deessHz,6000,3000,10000,'齒音頻率'),breath:number(c.breath,0,0,100,'呼吸聲降低')};
  const pitchCorrection={amount:number(p.amount,0,0,100,'音準修正'),target:p.target??'chromatic',speedMs:number(p.speedMs,120,20,500,'音準修正速度'),preserveVibrato:p.preserveVibrato??true};
  if(!['chromatic','reference'].includes(pitchCorrection.target)||typeof pitchCorrection.preserveVibrato!=='boolean')throw Error('無效的音準修正設定。');
  return {cleanup,pitchCorrection};
}
export function savedRepairSettings(value){
  const {cleanup:c,pitchCorrection:p}=repairSettings(value);
  return {...(c.noise||c.deess||c.breath||c.deessHz!==6000?{cleanup:c}:{}),...(p.amount||p.target!=='chromatic'||p.speedMs!==120||!p.preserveVibrato?{pitchCorrection:p}:{})};
}
export function repairEnabled(value){const {cleanup:c,pitchCorrection:p}=repairSettings(value);return !!(c.noise||c.deess||c.breath||p.amount);}

// In-place radix-2 transform; shared twiddles avoid per-frame trig/allocation.
class FFT{
  constructor(n){this.n=n;this.reverse=new Uint32Array(n);this.cos=new Float64Array(n/2);this.sin=new Float64Array(n/2);const bits=Math.log2(n);for(let i=0;i<n;i++){let x=i,r=0;for(let b=0;b<bits;b++){r=(r<<1)|(x&1);x>>=1;}this.reverse[i]=r;}for(let i=0;i<n/2;i++){this.cos[i]=Math.cos(2*Math.PI*i/n);this.sin[i]=Math.sin(2*Math.PI*i/n);}}
  run(re,im,inverse=false){const n=this.n;for(let i=0;i<n;i++){const j=this.reverse[i];if(j>i){[re[i],re[j]]=[re[j],re[i]];[im[i],im[j]]=[im[j],im[i]];}}for(let size=2;size<=n;size*=2){const half=size/2,step=n/size;for(let base=0;base<n;base+=size)for(let j=0;j<half;j++){const k=j*step,c=this.cos[k],s=this.sin[k]*(inverse?1:-1),b=base+j+half,a=base+j,tr=c*re[b]-s*im[b],ti=s*re[b]+c*im[b];re[b]=re[a]-tr;im[b]=im[a]-ti;re[a]+=tr;im[a]+=ti;}}if(inverse)for(let i=0;i<n;i++){re[i]/=n;im[i]/=n;}}
}
function lowpass(data,rate,hz){
  const w=2*Math.PI*Math.min(hz,rate*.4)/rate,c=Math.cos(w),s=Math.sin(w)/Math.SQRT2,a=1+s,b0=(1-c)/(2*a),b1=(1-c)/a,a1=-2*c/a,a2=(1-s)/a,out=new Float32Array(data.length);
  let x1=0,x2=0,y1=0,y2=0;for(let i=0;i<data.length;i++){const x=data[i],y=b0*x+b1*x1+b0*x2-a1*y1-a2*y2;out[i]=y;x2=x1;x1=x;y2=y1;y1=y;}return out;
}
function median(values){if(!values.length)return 0;const sorted=Array.from(values).sort((a,b)=>a-b);return sorted[Math.floor(sorted.length/2)];}
function sample(values,position){const i=Math.floor(position),f=position-i;return (values[i]??0)*(1-f)+(values[i+1]??0)*f;}
function dominantChannel(channels){let best=0,energy=-1;for(let c=0;c<channels.length;c++){let sum=0;for(let i=0;i<channels[c].length;i+=32)sum+=channels[c][i]**2;if(sum>energy){energy=sum;best=c;}}return channels[best];}

// FFT autocorrelation + cumulative-normalized difference. Silence/noise is unvoiced.
export function analyzeRepairVoice(channels,rate,progress=()=>{}){
  const raw=dominantChannel(channels),stride=Math.max(1,Math.floor(rate/8000)),analysisRate=rate/stride,filtered=lowpass(raw,rate,3000),mono=new Float32Array(Math.ceil(raw.length/stride));
  for(let i=0;i<mono.length;i++)mono[i]=filtered[i*stride];
  const size=1024,n=2048,hop=Math.round(analysisRate*.02),fft=new FFT(n),re=new Float64Array(n),im=new Float64Array(n),energy=new Float64Array(size+1),diff=new Float64Array(Math.ceil(analysisRate/65)+2),frames=[];
  const bandLow=lowpass(raw,rate,1000),bandHigh=lowpass(raw,rate,5000);
  for(let center=0;center<mono.length;center+=hop){
    re.fill(0);im.fill(0);let mean=0;const start=center-size/2;for(let i=0;i<size;i++){const x=mono[start+i]??0;re[i]=x;mean+=x;}mean/=size;
    energy[0]=0;for(let i=0;i<size;i++){re[i]-=mean;energy[i+1]=energy[i]+re[i]**2;}
    const rms=Math.sqrt(energy[size]/size);let hz=null,confidence=0;
    if(rms>.002){fft.run(re,im);for(let i=0;i<n;i++){re[i]=re[i]**2+im[i]**2;im[i]=0;}fft.run(re,im,true);
      let sum=0;const min=Math.max(2,Math.floor(analysisRate/1100)),max=Math.min(diff.length-2,size/2);
      for(let lag=1;lag<=max;lag++){const d=Math.max(0,energy[size-lag]+energy[size]-energy[lag]-2*re[lag]);sum+=d;diff[lag]=sum?d*lag/sum:1;}
      for(let lag=min;lag<max-1;lag++)if(diff[lag]<.18){while(lag+1<max&&diff[lag+1]<diff[lag])lag++;const den=2*(2*diff[lag]-diff[lag-1]-diff[lag+1]),period=lag+(den?(diff[lag+1]-diff[lag-1])/den:0);hz=analysisRate/period;confidence=1-diff[lag];break;}
    }
    const at=center*stride,half=Math.round(rate*.01);let total=0,mid=0,high=0,count=0;
    for(let i=Math.max(0,at-half);i<Math.min(raw.length,at+half);i++){total+=raw[i]**2;mid+=(bandHigh[i]-bandLow[i])**2;high+=(raw[i]-bandHigh[i])**2;count++;}
    const localRms=Math.sqrt(total/Math.max(1,count));if(localRms<.002){hz=null;confidence=0;}
    frames.push({time:at/rate,hz,confidence,rms:localRms,mid:mid/Math.max(total,1e-20),high:high/Math.max(total,1e-20)});
    if(frames.length%250===0)progress('分析人聲',Math.round(at/raw.length*100));
  }
  return {frames,hop:hop*stride/rate};
}
function referenceNote(meta,offset,shift,actual){
  const ref=meta.post?.reference;if(!Array.isArray(ref?.frames)||!Number.isFinite(ref.step)||ref.step<=0)throw Error('這筆錄音沒有原唱音高基準，請改選「最近半音」。');
  const outputTime=offset-shift,segment=meta.post.segments?.find(s=>outputTime>=s.offset&&outputTime<s.offset+s.duration);if(!segment)return null;
  const time=segment.songTime+outputTime-segment.offset;
  if((ref.masks??[]).some(r=>time>=r.start&&time<r.end))return null;
  const hz=ref.frames[Math.round(time/ref.step)];if(!Number.isFinite(hz)||hz<=0)return null;
  const note=midi(hz);return note+12*Math.round((actual-note)/12);
}
export function correctionCurve(analysis,settings,meta={},shift=0){
  const {frames,hop}=analysis,{amount,target,speedMs,preserveVibrato}=settings,curve=new Float32Array(frames.length);let base=null,note=null,correction=0;
  if(amount&&target==='reference')referenceNote(meta,0,shift,69);
  for(let i=0;i<frames.length;i++){
    const f=frames[i];if(!f.hz||f.confidence<.82){base=null;note=null;correction=0;continue;}
    const actual=midi(f.hz);
    if(base===null||Math.abs(actual-base)>.8)base=actual;else base+=(actual-base)*(1-Math.exp(-hop/.22));
    const detected=preserveVibrato?base:actual;
    if(note===null||Math.abs(detected-note)>.65)note=Math.round(detected);
    const wanted=target==='reference'?referenceNote(meta,f.time,shift,actual):note;
    if(wanted===null){correction=0;continue;}
    const difference=(wanted-detected)*100;
    // Correct drift, never infer an octave or turn a different melody into this one.
    if(Math.abs(difference)>(target==='reference'?200:65)){correction=0;continue;}
    const desired=difference*amount/100;
    correction+=(desired-correction)*(1-Math.exp(-hop/(speedMs/1000)));
    curve[i]=correction;
  }
  return curve;
}
function correctPitch(channels,rate,analysis,settings,meta,shift,progress){
  const curve=correctionCurve(analysis,settings,meta,shift),{frames,hop}=analysis,n=channels[0].length;
  if(!curve.some(x=>Math.abs(x)>1))return channels;
  const guide=lowpass(dominantChannel(channels),rate,1500),marks=[];let at=0;
  while(at<n){const f=frames[Math.min(frames.length-1,Math.round(at/rate/hop))];if(!f?.hz){at+=Math.round(hop*rate);continue;}const period=rate/f.hz,radius=period*.3;let peak=Math.max(0,Math.round(at-radius)),max=-Infinity;for(let i=peak;i<Math.min(n,at+radius);i++)if(guide[i]>max){max=guide[i];peak=i;}if(!marks.length||peak>marks.at(-1).at)marks.push({at:peak,period});at=Math.max(at+period,peak+period);}
  if(marks.length<3)return channels;
  const out=channels.map(()=>new Float32Array(n)),weights=new Float32Array(n);let cursor=0,position=marks[0].at,grains=0;
  while(position<n){
    while(cursor+1<marks.length&&Math.abs(marks[cursor+1].at-position)<Math.abs(marks[cursor].at-position))cursor++;
    const mark=marks[cursor],fi=position/rate/hop,index=clamp(Math.round(fi),0,frames.length-1),f=frames[index],cents=sample(curve,fi);
    if(!f?.hz||Math.abs(mark.at-position)>mark.period*2){position+=Math.round(hop*rate);continue;}
    const radius=Math.round(mark.period),center=Math.round(position);
    for(let j=-radius;j<=radius;j++){const dest=center+j,src=mark.at+j;if(dest<0||dest>=n||src<0||src>=n)continue;const w=.5+.5*Math.cos(Math.PI*j/radius);weights[dest]+=w;for(let c=0;c<channels.length;c++)out[c][dest]+=channels[c][src]*w;}
    position+=rate/frequency(midi(f.hz)+cents/100);
    if(++grains%20000===0)progress('修正音準',Math.round(position/n*100));
  }
  const active=Float32Array.from(curve,(x,i)=>Math.abs(x)>1&&frames[i].hz?1:0),smooth=new Float32Array(n);let blend=0;const alpha=1-Math.exp(-1/(rate*.012));
  for(let i=0;i<n;i++){blend+=(sample(active,i/rate/hop)-blend)*alpha;smooth[i]=weights[i]>.15?blend:0;}
  for(let c=0;c<out.length;c++)for(let i=0;i<n;i++)out[c][i]=channels[c][i]*(1-smooth[i])+(weights[i]>.15?out[c][i]/weights[i]:0)*smooth[i];
  return out;
}
function breathCurve(analysis,amount){
  const {frames,hop}=analysis,curve=new Float32Array(frames.length).fill(1),typical=median(frames.filter(f=>f.hz).map(f=>f.rms));
  if(!typical)return curve;
  for(let i=0;i<frames.length;){if(frames[i].hz||frames[i].rms<.002){i++;continue;}const start=i;while(i<frames.length&&!frames[i].hz&&frames[i].rms>=.002)i++;const end=i,duration=(end-start)*hop,part=frames.slice(start,end),nearby=frames.slice(Math.max(0,start-Math.ceil(.35/hop)),Math.min(frames.length,end+Math.ceil(.35/hop))).some(f=>f.hz);
    if(duration<.08||duration>.9||!nearby||median(part.map(f=>f.rms))>typical*1.5||median(part.map(f=>f.mid))<.35||median(part.map(f=>f.high))>.8)continue;
    const gain=10**(-18*amount/100/20);for(let j=start;j<end;j++)curve[j]=gain;
  }
  return curve;
}
function reduceBreaths(channels,rate,analysis,amount){
  const curve=breathCurve(analysis,amount),out=channels.map(()=>new Float32Array(channels[0].length));let gain=1;
  for(let i=0;i<out[0].length;i++){const target=sample(curve,Math.min(curve.length-1,i/rate/analysis.hop)),tau=target<gain?.015:.07;gain+=(target-gain)*(1-Math.exp(-1/(rate*tau)));for(let c=0;c<out.length;c++)out[c][i]=channels[c][i]*gain;}return out;
}
function spectralCleanup(channels,rate,analysis,settings,progress){
  const n=2048,hop=512,bins=n/2+1,fft=new FFT(n),win=Float64Array.from({length:n},(_,i)=>Math.sin(Math.PI*(i+.5)/n)),re=channels.map(()=>new Float64Array(n)),im=channels.map(()=>new Float64Array(n)),power=new Float64Array(bins),noise=new Float64Array(bins),gain=new Float64Array(bins).fill(1),length=channels[0].length;
  const frameAt=center=>{power.fill(0);for(let c=0;c<channels.length;c++){im[c].fill(0);for(let j=0;j<n;j++)re[c][j]=(channels[c][center+j-n/2]??0)*win[j];fft.run(re[c],im[c]);for(let k=0;k<bins;k++)power[k]+=(re[c][k]**2+im[c][k]**2)/channels.length;}};
  const voiceLevel=median(analysis.frames.filter(f=>f.hz).map(f=>f.rms));
  let candidates=analysis.frames.filter(f=>!f.hz&&f.rms>.000001&&(!voiceLevel||f.rms<voiceLevel*.35)).sort((a,b)=>a.rms-b.rms);
  candidates=candidates.slice(0,Math.min(128,Math.max(1,Math.ceil(candidates.length*.2))));
  if(!candidates.length&&!settings.deess)return {channels,noiseLearned:false};
  if(settings.noise)for(const f of candidates){frameAt(Math.round(f.time*rate));for(let k=0;k<bins;k++)noise[k]+=power[k]/candidates.length;}
  const out=channels.map(()=>new Float32Array(length)),weights=new Float32Array(length),floor=10**(-18*settings.noise/100/20),deessHz=Math.min(settings.deessHz,rate*.42);let highGain=1,count=0;
  for(let center=0;center<length+n/2;center+=hop){
    frameAt(center);let total=0,high=0;for(let k=1;k<bins;k++){total+=power[k];if(k*rate/n>=deessHz*.7)high+=power[k];}
    const activity=clamp((high/Math.max(total,1e-20)-.18)/.5,0,1),target=total>1e-5?10**(-15*settings.deess/100*activity/20):1;
    highGain+=(target-highGain)*(1-Math.exp(-hop/rate/(target<highGain?.008:.07)));
    for(let k=0;k<bins;k++){
      const estimate=(noise[Math.max(0,k-1)]+2*noise[k]+noise[Math.min(bins-1,k+1)])/4,clean=settings.noise&&candidates.length?Math.max(floor,Math.sqrt(Math.max(0,1-(1+settings.noise/100)*estimate/Math.max(power[k],1e-20)))):1;
      gain[k]+=(clean-gain[k])*.35;const band=clamp((k*rate/n-deessHz*.55)/(deessHz*.45),0,1),mask=gain[k]*(1-band+band*highGain);
      for(let c=0;c<channels.length;c++){re[c][k]*=mask;im[c][k]*=mask;if(k>0&&k<n/2){re[c][n-k]*=mask;im[c][n-k]*=mask;}}
    }
    for(let c=0;c<channels.length;c++){fft.run(re[c],im[c],true);for(let j=0;j<n;j++){const at=center+j-n/2;if(at<0||at>=length)continue;out[c][at]+=re[c][j]*win[j];if(c===0)weights[at]+=win[j]**2;}}
    if(++count%250===0)progress('降噪／齒音處理',Math.round(Math.min(1,center/length)*100));
  }
  for(const data of out)for(let i=0;i<length;i++)data[i]/=weights[i]||1;
  return {channels:out,noiseLearned:!!candidates.length};
}
export function repairChannels(channels,rate,value,meta={},shift=0,progress=()=>{}){
  const settings=repairSettings(value);if(!repairEnabled(value))return {channels,noiseLearned:false};
  if(!Array.isArray(channels)||!channels.length||channels.some(x=>!(x instanceof Float32Array)||x.length!==channels[0].length)||!Number.isFinite(rate)||rate<8000||rate>192000)throw Error('無效的人聲音訊。');
  if(channels.some(x=>x.some(v=>!Number.isFinite(v))))throw Error('原始歌聲含有無效取樣，無法處理。');
  if(!channels[0].length)return {channels,noiseLearned:false};
  progress('分析人聲',0);let analysis=analyzeRepairVoice(channels,rate,progress),noiseLearned=false;
  if(settings.cleanup.noise||settings.cleanup.deess){const result=spectralCleanup(channels,rate,analysis,settings.cleanup,progress);channels=result.channels;noiseLearned=result.noiseLearned;}
  if(settings.cleanup.breath){progress('降低呼吸聲',0);channels=reduceBreaths(channels,rate,analysis,settings.cleanup.breath);}
  if(settings.pitchCorrection.amount){progress('修正音準',0);if(settings.cleanup.noise)analysis=analyzeRepairVoice(channels,rate,progress);channels=correctPitch(channels,rate,analysis,settings.pitchCorrection,meta,shift,progress);}
  progress('人聲處理完成',100);return {channels,noiseLearned};
}
