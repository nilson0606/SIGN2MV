import {recordingSceneSuffix,recordingEmotionSuffix} from './recording-scenes.mjs';
import {savedRepairSettings,repairSettings} from './recording-repair.mjs';
// Graded timbre effect on the singer bus: shelf + presence dip + high cut.
// This softens bright/breathy texture; it does not isolate or remove breath sounds.
const presets={off:{label:'關閉',maxDb:0},light:{label:'輕度',baseDb:2,maxDb:5,shelf:3500,presence:1,cutoff:12000},medium:{label:'中度',baseDb:5,maxDb:11,shelf:2800,presence:3,cutoff:7500},strong:{label:'強烈',baseDb:10,maxDb:18,shelf:2000,presence:6,cutoff:4500}};
export function softeningProfile(value='off') {
  if(!Object.hasOwn(presets,value))throw new Error('無效的歌聲柔化強度。');
  return {id:value,...presets[value]};
}
export function recordingSofteningSuffix(meta) {
  const id=meta?.vocalSoftening?.strength;
  return id&&id!=='off'&&Object.hasOwn(presets,id)?`_柔化${id==="strong"&&!(meta.vocalSoftening.version>=2)?"較強":presets[id].label}`:'';
}

// Derive labels from the saved recipe without changing the original song title.
export function recordingEffectsSuffix(meta) {
  const parts=[],effects=meta.vocalEffects||{},volume=meta.postVolume||{};
  const scene=recordingSceneSuffix(meta);if(scene)parts.push(scene);
  const emotion=recordingEmotionSuffix(meta);if(emotion)parts.push(emotion);
  const changed=x=>Number.isFinite(x)&&x!==0;
  const signed=x=>(x>0?'+':'')+x;
  if(Number.isFinite(volume.voice)&&volume.voice!==100)parts.push(`人聲${volume.voice}%`);
  if(meta.mode==='mix'&&Number.isFinite(volume.backing)&&volume.backing!==100)parts.push(`配樂${volume.backing}%`);
  const regions=Array.isArray(effects.regions)?effects.regions.filter(r=>Number.isFinite(r.volume)&&r.volume!==100):[];
  if(regions.length)parts.push(`局部音量${regions.length}段`);
  const eq=[['low','低'],['mid','中'],['high','高']].filter(([key])=>changed(effects.eq?.[key])).map(([key,label])=>label+signed(effects.eq[key])).join('');
  if(eq)parts.push('EQ'+eq);
  const compression={light:'輕度',medium:'中度'}[effects.compression];
  if(compression)parts.push('壓縮'+compression);
  const repair=repairSettings(effects);
  for(const [key,label] of [['noise','降噪'],['deess','齒音'],['breath','呼吸降低']])if(repair.cleanup[key])parts.push(`${label}${repair.cleanup[key]}%`);
  if(repair.pitchCorrection.amount)parts.push(`音準修正${repair.pitchCorrection.amount}%_${repair.pitchCorrection.target==='reference'?'原唱基準':'最近半音'}`);
  if(Number.isFinite(effects.reverb)&&effects.reverb>0)parts.push(`殘響${effects.reverb}%`);
  if(effects.reverb>0&&effects.reverbOptions){const r=reverbProfile(effects.reverbOptions);parts.push(`${reverbSpaces[r.space]}${r.decay}s`, `預延遲${r.preDelayMs}ms`);}
  if(effects.reverbTone?.brightness)parts.push(`殘響明亮${signed(effects.reverbTone.brightness)}`);
  if(effects.reverbTone&&effects.reverbTone.width!==100)parts.push(`殘響寬度${effects.reverbTone.width}%`);
  if(effects.echo?.amount)parts.push(`回聲${effects.echo.amount}%_${effects.echo.timeMs}ms_${effects.echo.repeats}次${effects.echo.pingPong?'左右交替':''}`);
  if(effects.effectRegions?.length)parts.push(`局部效果${effects.effectRegions.length}段`);
  const edit=meta.postEdit;
  if(edit?.start>0||edit?.end!=null)parts.push(`剪輯${edit.start||0}-${edit.end??'末尾'}秒`);
  if(edit?.fadeIn>0)parts.push(`淡入${edit.fadeIn}秒`);
  if(edit?.fadeOut>0)parts.push(`淡出${edit.fadeOut}秒`);
  if(!meta.parentId&&!parts.length&&!recordingSofteningSuffix(meta))return '';
  return '_人聲後製'+parts.map(part=>'_'+part).join('');
}

// Versioned, repeatable recipe. Times refer to the rendered recording, not YouTube.
export function vocalEffects(value={},duration=3600) {
  if(value.version!==undefined&&value.version!==1)throw new Error('這筆人聲效果版本較新，請更新網頁後再編輯。');
  const number=(x,fallback,min,max,label)=>{
    const v=x===undefined?fallback:x;
    if(!Number.isFinite(v)||v<min||v>max)throw new Error(`${label}需介於 ${min} 與 ${max}。`);
    return v;
  };
  const eq=Object.fromEntries(['low','mid','high'].map(band=>[band,number(value.eq?.[band],0,-12,12,'EQ（dB）')]));
  const compression=value.compression??'off';
  if(!['off','light','medium'].includes(compression))throw new Error('無效的動態壓縮強度。');
  const reverb=number(value.reverb,0,0,100,'殘響（%）');
  if(!Array.isArray(value.regions??[])||(value.regions?.length??0)>100)throw new Error('局部音量最多 100 個區段。');
  const regions=(value.regions??[]).map(r=>({start:number(r.start,NaN,0,duration,'區段開始秒數'),end:number(r.end,NaN,0,duration,'區段結束秒數'),volume:number(r.volume,100,0,200,'區段音量（%）')})).sort((a,b)=>a.start-b.start);
  for(let i=0;i<regions.length;i++){
    if(regions[i].end<=regions[i].start)throw new Error('局部音量的結束時間必須晚於開始時間。');
    if(i&&regions[i].start<regions[i-1].end)throw new Error('局部音量區段不可重疊，請調整開始／結束時間。');
  }
  const profile=reverbProfile(value.reverbOptions);
  const custom=profile.space!=='classic'||profile.decay!==.8||profile.preDelayMs!==15;
  const tone={brightness:number(value.reverbTone?.brightness,0,-100,100,'殘響明亮度'),width:number(value.reverbTone?.width,100,0,100,'殘響寬度（%）')};
  const echo={amount:number(value.echo?.amount,0,0,100,'回聲音量（%）'),timeMs:number(value.echo?.timeMs,300,80,1000,'回聲間隔（ms）'),repeats:number(value.echo?.repeats,3,1,8,'回聲次數'),feedback:number(value.echo?.feedback,40,0,80,'回聲保留比例（%）'),pingPong:value.echo?.pingPong??false};
  if(!Number.isInteger(echo.repeats)||typeof echo.pingPong!=='boolean')throw Error('回聲次數需為整數，左右交替需為開關。');
  if(!Array.isArray(value.effectRegions??[])||(value.effectRegions?.length??0)>20)throw Error('局部效果最多 20 個區段。');
  const effectRegions=(value.effectRegions??[]).map(r=>({start:number(r.start,NaN,0,duration,'效果開始秒數'),end:number(r.end,NaN,0,duration,'效果結束秒數'),reverb:number(r.reverb,reverb,0,100,'區段殘響（%）'),echo:number(r.echo,echo.amount,0,100,'區段回聲（%）'),decay:number(r.decay,profile.decay,.2,10,'區段尾音（秒）')})).sort((a,b)=>a.start-b.start);
  for(let i=0;i<effectRegions.length;i++)if(effectRegions[i].end<=effectRegions[i].start||(i&&effectRegions[i].start<effectRegions[i-1].end))throw Error('局部效果結束需晚於開始，且區段不可重疊。');
  return {version:1,eq,compression,reverb,regions,...savedRepairSettings(value),...(custom?{reverbOptions:profile}:{}),...(tone.brightness||tone.width!==100?{reverbTone:tone}:{}),...(value.echo||effectRegions.some(r=>r.echo)?{echo}:{}),...(effectRegions.length?{effectRegions}:{})};
}

export const vocalReverbTail=.8;
export const reverbSpacePresets={
  classic:{label:'原版',decay:.8,preDelayMs:15,damping:5000,help:'沿用舊版殘響，適合與既有成品比較。'},
  room:{label:'房間',decay:.6,preDelayMs:10,damping:6000,help:'緊密、短尾，帶少量近牆反射，增加自然空間感。'},
  hall:{label:'大廳',decay:1.8,preDelayMs:25,damping:4000,help:'寬廣、柔和，尾音逐漸鋪開，適合抒情歌。'},
  plate:{label:'板式',decay:1.2,preDelayMs:15,damping:7000,help:'明亮、密集，尾音較快出現，讓人聲多一層光澤。'},
  studio:{label:'錄音室',decay:.4,preDelayMs:4,damping:3500,attack:.002,reflections:[[.006,5],[.012,-3],[.019,2]],spread:.0007,help:'貼近、柔暗的短尾，空間感收斂，保留清楚咬字。'},
  chamber:{label:'小室',decay:1.1,preDelayMs:12,damping:5200,attack:.012,reflections:[[.017,3],[.031,-2.4],[.053,1.8],[.071,-1]],spread:.002,help:'溫暖、緊湊，密集反射讓歌聲較厚實。'},
  church:{label:'教堂',decay:4.2,preDelayMs:45,damping:3200,attack:.09,reflections:[[.065,1.5],[.113,-1.2],[.19,.8]],spread:.007,help:'柔暗、緩慢鋪開的長尾，適合拉長音與莊嚴感。'},
  arena:{label:'體育館',decay:3.2,preDelayMs:65,damping:4300,attack:.045,reflections:[[.06,4],[.12,-3],[.21,2.5],[.32,-1.8]],spread:.011,help:'開闊、遠距，較晚的反射群帶出大型場地感。'},
  tunnel:{label:'隧道',decay:2.6,preDelayMs:35,damping:4600,attack:.005,pulse:.11,reflections:[[.11,3],[.22,-2],[.33,1.4]],spread:.004,help:'規律的一波波反射，能聽到沿著長通道延伸的尾音。'},
  cave:{label:'洞穴',decay:3,preDelayMs:55,damping:2100,attack:.03,reflections:[[.035,3],[.098,-2.5],[.176,2],[.29,-1.6],[.42,1]],spread:.009,help:'低沉、幽暗，不規則反射帶出深處回應的感覺。'},
  bathroom:{label:'浴室',decay:.7,preDelayMs:5,damping:8500,attack:.001,reflections:[[.004,6],[.009,-5],[.016,4],[.022,-3],[.033,2]],spread:.0005,help:'明亮、貼近硬牆，短促反射密集，適合聽鮮明的空間效果。'},
  dream:{label:'夢幻空間',decay:3.6,preDelayMs:80,damping:6000,attack:.22,bloom:true,reflections:[],spread:0,help:'尾音慢慢浮起、綿長散開，營造漂浮感；不會改變音高。'}
};
export const reverbSpaces=Object.fromEntries(Object.entries(reverbSpacePresets).map(([key,value])=>[key,value.label]));
export function reverbProfile(value={}){
  const {space='classic',decay=.8,preDelayMs=15}=value;
  if(!Object.hasOwn(reverbSpaces,space))throw Error('無效的殘響空間類型。');
  if(!Number.isFinite(decay)||decay<.2||decay>10)throw Error('殘響尾音長度需介於 0.2 與 10 秒。');
  if(!Number.isFinite(preDelayMs)||preDelayMs<0||preDelayMs>500)throw Error('殘響預延遲需介於 0 與 500 ms。');
  return {space,decay,preDelayMs};
}
export function reverbDuration(recipe){const r=reverbProfile(recipe.reverbOptions);return recipe.reverb?(recipe.reverbOptions?r.decay+r.preDelayMs/1000:vocalReverbTail):0;}
export function effectsDuration(recipe){
  const echoes=recipe.echo;
  const echoTail=echoes&&(echoes.amount||recipe.effectRegions?.some(r=>r.echo))?echoes.timeMs/1000*echoes.repeats:0;
  return Math.max(reverbDuration(recipe),echoTail,...(recipe.effectRegions??[]).map(r=>r.reverb?r.decay+reverbProfile(recipe.reverbOptions).preDelayMs/1000:0));
}
export function reverbImpulse(context,recipe){
  const r=reverbProfile(recipe.reverbOptions),legacy=!recipe.reverbOptions;
  const character=reverbSpacePresets[r.space],extended=character.attack!==undefined;
  const impulse=context.createBuffer(2,Math.ceil(context.sampleRate*reverbDuration(recipe)),context.sampleRate);
  const first=Math.floor(context.sampleRate*r.preDelayMs/1000);let seed=19237;
  for(let c=0;c<2;c++){
    const data=impulse.getChannelData(c);let energy=0;
    for(let i=first;i<data.length;i++){
      seed=(Math.imul(seed,1664525)+1013904223)>>>0;
      const t=(i-first)/context.sampleRate;
      const attack=r.space==='hall'?1-Math.exp(-t/.025):r.space==='plate'?1-Math.exp(-t/.004):extended?1-Math.exp(-t/character.attack):1;
      data[i]=(seed/2147483648-1)*Math.exp(character.bloom?-7*(t/r.decay)**1.5:legacy?-7*i/data.length:-7*t/r.decay)*attack;
      if(character.pulse){const phase=t%(character.pulse+c*.006);data[i]*=.12+.88*Math.exp(-(((phase-.015)/.01)**2));}
    }
    if(r.space==='room')for(const [time,level] of [[.011,.65],[.027,-.4],[.043,.3]]){const at=first+Math.round((time+c*.002)*context.sampleRate);if(at<data.length)data[at]+=level*Math.sqrt(context.sampleRate/48000);}
    // New spaces use their own early reflection pattern and a smooth ending.
    // The existing four impulse paths above remain unchanged for saved recordings.
    if(extended){
      for(const [time,level] of character.reflections){const offset=time+c*character.spread;if(offset>=r.decay)continue;const at=first+Math.round(offset*context.sampleRate);if(at<data.length)data[at]+=level*Math.exp(-3*offset/r.decay)*Math.sqrt(context.sampleRate/48000);}
      const fade=Math.max(1,Math.round(Math.min(.02,r.decay/10)*context.sampleRate));
      for(let i=Math.max(first,data.length-fade);i<data.length;i++)data[i]*=Math.sin((data.length-1-i)/fade*Math.PI/2)**2;
    }
    for(const sample of data)energy+=sample*sample;
    const scale=.65/Math.sqrt(energy||1);for(let i=0;i<data.length;i++)data[i]*=scale;
  }
  const width=(recipe.reverbTone?.width??100)/100;
  if(width!==1){const left=impulse.getChannelData(0),right=impulse.getChannelData(1);for(let i=0;i<left.length;i++){const mid=(left[i]+right[i])/2,side=(left[i]-right[i])/2*width;left[i]=mid+side;right[i]=mid-side;}}
  return impulse;
}
export function processedVoice(context,source,recipe) {
  const nodes=[];let output=source;
  const append=node=>{output.connect(node);nodes.push(node);output=node;};
  for(const [band,type,frequency] of [['low','lowshelf',200],['mid','peaking',1500],['high','highshelf',5000]]){
    if(!recipe.eq[band])continue;
    const filter=context.createBiquadFilter();filter.type=type;filter.frequency.value=Math.min(frequency,context.sampleRate*.45);filter.Q.value=.8;filter.gain.value=recipe.eq[band];append(filter);
  }
  if(recipe.compression!=='off'){
    const compressor=context.createDynamicsCompressor(),medium=recipe.compression==='medium';
    compressor.threshold.value=medium?-24:-18;compressor.knee.value=12;compressor.ratio.value=medium?3:2;compressor.attack.value=.015;compressor.release.value=.18;append(compressor);
    const makeup=context.createGain();makeup.gain.value=10**((medium?3:2)/20);append(makeup);
  }
  if(recipe.regions.length){
    const local=context.createGain();local.gain.value=1;
    for(const r of recipe.regions){
      const fade=Math.min(.01,(r.end-r.start)/3),target=r.volume/100;
      local.gain.setValueAtTime(r.start===0?target:1,r.start);
      local.gain.linearRampToValueAtTime(target,r.start+fade);
      local.gain.setValueAtTime(target,r.end-fade);
      local.gain.linearRampToValueAtTime(1,r.end);
    }
    append(local);
  }
  const sections=recipe.effectRegions??[];
  if(recipe.reverb||recipe.echo?.amount||sections.some(r=>r.reverb||r.echo)){
    const dry=output,sum=context.createGain();dry.connect(sum);nodes.push(sum);
    // Gate sends, not returns: a phrase's tail continues naturally after its end.
    function send(region){
      if(!sections.length)return dry;
      const gain=context.createGain();gain.gain.value=region?0:1;dry.connect(gain);nodes.push(gain);
      for(const r of region?[region]:sections){const fade=Math.min(.01,(r.end-r.start)/3),inside=region?1:0,outside=1-inside;
        gain.gain.setValueAtTime(r.start===0?inside:outside,r.start);gain.gain.linearRampToValueAtTime(inside,r.start+fade);gain.gain.setValueAtTime(inside,r.end-fade);gain.gain.linearRampToValueAtTime(outside,r.end);
      }return gain;
    }
    function addEffects(input,settings){
      if(settings.reverb){
        const convolver=context.createConvolver(),wet=context.createGain(),damping=context.createBiquadFilter();
        convolver.normalize=false;convolver.buffer=reverbImpulse(context,settings);wet.gain.value=settings.reverb/100;
        const space=reverbProfile(settings.reverbOptions).space;
        damping.type='lowpass';damping.frequency.value=Math.min(reverbSpacePresets[space].damping*2**((settings.reverbTone?.brightness??0)/50),context.sampleRate*.45);
        input.connect(convolver);convolver.connect(damping);damping.connect(wet);wet.connect(sum);nodes.push(convolver,damping,wet);
      }
      const echo=settings.echo;
      if(echo?.amount)for(let k=1;k<=echo.repeats;k++){
        const delay=context.createDelay(8),gain=context.createGain();delay.delayTime.value=k*echo.timeMs/1000;gain.gain.value=echo.amount/100*(echo.feedback/100)**(k-1);
        input.connect(delay);delay.connect(gain);nodes.push(delay,gain);
        if(echo.pingPong){const pan=context.createStereoPanner();pan.pan.value=k%2?-.8:.8;gain.connect(pan);pan.connect(sum);nodes.push(pan);}else gain.connect(sum);
      }
    }
    if(recipe.reverb||recipe.echo?.amount)addEffects(send(),recipe);
    for(const r of sections)if(r.reverb||r.echo)addEffects(send(r),{...recipe,reverb:r.reverb,reverbOptions:{...reverbProfile(recipe.reverbOptions),decay:r.decay},echo:{...recipe.echo,amount:r.echo}});
    output=sum;
  }
  return {output,disconnect(){source.disconnect();for(const node of nodes)node.disconnect();}};
}
export async function softenedVoice(context,source,raw,placement,strength='off') {
  const profile=softeningProfile(strength);
  if(!profile.maxDb)return source;
  const shelf=context.createBiquadFilter();shelf.type='highshelf';shelf.frequency.value=profile.shelf;shelf.gain.value=-profile.baseDb;source.connect(shelf);
  const presence=context.createBiquadFilter();presence.type='peaking';presence.frequency.value=2500;presence.Q.value=1.1;presence.gain.value=-profile.presence;shelf.connect(presence);
  const cutoff=context.createBiquadFilter();cutoff.type='lowpass';cutoff.frequency.value=Math.min(profile.cutoff,raw.sampleRate*.45);cutoff.Q.value=Math.SQRT1_2;presence.connect(cutoff);
  const rate=raw.sampleRate,hop=Math.max(1,Math.round(rate*.02));
  const channels=Array.from({length:raw.numberOfChannels},(_,c)=>raw.getChannelData(c));
  const low=new Float64Array(channels.length),alpha=1-Math.exp(-2*Math.PI*2500/rate);
  const first=Math.floor(placement.source*rate),end=Math.min(raw.length,Math.ceil((placement.source+placement.duration)*rate));
  let reduction=-profile.baseDb,block=0;
  for(let start=first;start<end;start+=hop){
    let total=0,high=0;const stop=Math.min(end,start+hop);
    for(let i=start;i<stop;i++)for(let c=0;c<channels.length;c++){
      const x=channels[c][i];low[c]+=alpha*(x-low[c]);const h=x-low[c];total+=x*x;high+=h*h;
    }
    const rms=Math.sqrt(total/Math.max(1,(stop-start)*channels.length));
    const ratio=Math.sqrt(high/Math.max(total,1e-20));
    // A fixed tonal change makes the option audible even when the old dynamic
    // detector would stay inactive; extra attenuation follows bright passages.
    const activity=Math.min(1,Math.max(0,(20*Math.log10(Math.max(rms,1e-10))+60)/18));
    const target=-profile.baseDb-(profile.maxDb-profile.baseDb)*Math.min(1,Math.max(0,(ratio-.12)/.35))*activity;
    const seconds=(stop-start)/rate,tau=target < reduction ? .025 : .15;
    reduction+=(target-reduction)*(1-Math.exp(-seconds/tau));
    shelf.gain.linearRampToValueAtTime(reduction,placement.when+(stop-first)/rate);
    if(++block%100===0)await new Promise(resolve=>setTimeout(resolve,0));
  }
  return cutoff;
}
