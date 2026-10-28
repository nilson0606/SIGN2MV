// Editing starting points, never effects applied during capture or archive migration.
export const recordingSceneDefaultsVersion='hall-echo-v1';
const sceneFilenameLabels={intimate:'貼近耳邊',acoustic:'木吉他',hall:'大廳一般流行',pop:'明亮流行',ballad:'大廳慢板抒情',sacred:'教堂',concert:'演唱會',dream:'夢幻',custom:'自訂'};
export function recordingSceneSuffix(meta){
  // Only explicitly saved new metadata opts in; old names are never inferred retroactively.
  const saved=meta.postScene;
  return saved?.version===1&&Object.hasOwn(sceneFilenameLabels,saved.id)?`情境_${sceneFilenameLabels[saved.id]}`:'';
}
const echo=(amount=0,timeMs=300,repeats=3,feedback=40,pingPong=false)=>({amount,timeMs,repeats,feedback,pingPong});
const scene=(label,space,reverb,decay,preDelayMs,brightness,width,delay=echo())=>({label,effects:{reverb,reverbOptions:{space,decay,preDelayMs},reverbTone:{brightness,width},echo:delay}});
export const recordingScenes={
  intimate:scene('貼近耳邊 · 清楚自然','studio',10,.4,10,-10,50),
  acoustic:scene('木吉他 · 輕聲演唱','room',15,.6,15,-5,70),
  hall:scene('大廳 · 一般流行（預設）','hall',20,1.8,25,0,100,echo(10)),
  pop:scene('明亮流行 · 人聲突出','plate',18,1.2,35,10,90),
  ballad:scene('大廳 · 慢板抒情','hall',25,2.6,50,-10,100,echo(10)),
  sacred:scene('教堂 · 莊嚴長尾','church',25,4.2,60,-20,100),
  concert:scene('演唱會 · 寬大舞台','arena',25,3.2,65,-10,100),
  dream:scene('夢幻 · 空靈回聲','dream',30,3.6,80,5,100,echo(12,600,3,30,true)),
};
export function initialRecordingEffects(row){
  if(row?.vocalEffects)return structuredClone(row.vocalEffects);
  if(row?.postDefaults===recordingSceneDefaultsVersion)return structuredClone(recordingScenes.hall.effects);
  // Keep the previous editor defaults for existing recordings, regardless of date.
  return {reverb:20,reverbOptions:{space:'hall',decay:1.8,preDelayMs:25}};
}
export function matchingRecordingScene(value){
  return Object.entries(recordingScenes).find(([,s])=>{
    const p=s.effects;
    return value.reverb===p.reverb
      &&['space','decay','preDelayMs'].every(k=>value.reverbOptions?.[k]===p.reverbOptions[k])
      &&(value.reverbTone?.brightness??0)===p.reverbTone.brightness
      &&(value.reverbTone?.width??100)===p.reverbTone.width
      &&Object.entries(p.echo).every(([k,v])=>(value.echo?.[k]??echo()[k])===v);
  })?.[0]??'';
}

// Timbre starting points, independent of space, timing, capture and scoring.
// All parameters remain visible/editable; selecting repeatedly never stacks effects.
const emotion=(label,help,low,mid,high,compression='off',softening='off')=>({label,help,eq:{low,mid,high},compression,softening});
export const recordingEmotions={
  original:emotion('原音','不額外調整音色：EQ 歸零、柔化與壓縮關閉；空間效果仍保留。',0,0,0),
  intimate:emotion('溫柔親密','柔和、貼近耳邊，收斂尖亮感；可搭配「貼近耳邊」情境。',1,-1,-2,'off','light'),
  sweet:emotion('甜蜜幸福','輕盈明亮、帶微笑感，輕度壓縮讓輕聲較穩定。',-1,1,2,'light'),
  sincere:emotion('深情真摯','溫暖厚實，保留較多演唱起伏；可搭配大廳。',2,1,0,'light'),
  nostalgic:emotion('思念懷舊','柔暗溫暖，收斂高頻，烘托回憶感。',1,-1,-3,'off','light'),
  lonely:emotion('孤單落寞','音色清瘦、稍微退後，保留原有強弱；可搭配寬廣空間。',-2,-1,-1),
  fragile:emotion('悲傷脆弱','保留氣息、細節與大小聲起伏，不加柔化或壓縮。',-1,0,1),
  calm:emotion('釋懷平靜','自然平順，稍微收斂中高頻，保留演唱動態。',0,-1,-1),
  resolute:emotion('堅定振奮','增加清晰度與存在感，用輕度壓縮穩住人聲。',1,2,1,'light'),
  passionate:emotion('激昂奔放','突出咬字與明亮度，中度壓縮控制較大的音量落差。',-1,3,2,'medium'),
  dreamy:emotion('夢幻迷離','柔和、朦朧，降低直接感；可搭配夢幻空間與回聲。',0,-2,-2,'off','light'),
};
export function matchingRecordingEmotion({effects={},softening='off'}={}){
  return Object.entries(recordingEmotions).find(([,p])=>p.softening===softening
    &&p.compression===(effects.compression??'off')
    &&['low','mid','high'].every(k=>p.eq[k]===(effects.eq?.[k]??0)))?.[0]??'custom';
}
export function recordingEmotionLabel(settings){
  return recordingEmotions[matchingRecordingEmotion(settings)]?.label??'自訂音色';
}
export function recordingEmotionSuffix(meta){
  const saved=meta.postEmotion;
  if(saved?.version!==1||saved.id==='original')return '';
  const label=saved.id==='custom'?'自訂音色':recordingEmotions[saved.id]?.label;
  return label?`情緒_${label}`:'';
}
