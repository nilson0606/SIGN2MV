import {originalText,userOption} from './i18n.mjs';
import {nativeInputDevices,openNativeMicrophone} from './native-microphone.mjs';
import {isLocalMediaId,selectedMediaId,selectMediaSource} from './media-source.mjs';
import {localVideoPlayer} from './local-video-player.mjs';
import {initializeLocalMedia,mediaRequest,LOCAL_BASE} from './local-media-client.mjs';
import { youtubeId, noteOf, detectPitch, playerResponse, alignedTime } from './audio.mjs';
import { createCalibration } from './calibration.mjs';
import { createKaraokeSession } from './session.mjs';
import {initRecordingDiagnostics} from './recording-diagnostics.mjs';
initRecordingDiagnostics();
const $ = id => document.getElementById(id);
// Opt-in local troubleshooting: no audio, credentials, or full reference data are logged.
let playbackTraceEnabled=new URLSearchParams(location.search).get('tracePlayback')==='1';
let playbackTraceQueue=Promise.resolve();
function playbackTraceStatus(text) {
  let node=$('playback-trace-status');
  if(!node){node=document.createElement('p');node.id='playback-trace-status';node.className='status';node.setAttribute('role','status');$('mic-status').after(node);}
  node.textContent=text;
}
async function connectPlaybackTrace() {
  try {
    const session=await(await fetch('http://127.0.0.1:4274/session',{cache:'no-store',signal:AbortSignal.timeout(5000)})).json();
    if(session.playbackTraceActive)playbackTraceEnabled=true;
    if(playbackTraceEnabled){playbackTraceStatus('播放追蹤連線中…（只記錄狀態，不錄音）');tracePlayback('trace-connected');}
  } catch { if(playbackTraceEnabled)playbackTraceStatus('播放追蹤未連線：尚未收到紀錄，請確認本機工具與本機網路權限。'); }
}

function tracePlayback(stage, extra={}) {
  if(!playbackTraceEnabled)return;
  const read=fn=>{try{return fn()??null;}catch{return null;}};
  const reference=read(()=>singing.reference());
  const snapshot={stage,time:new Date().toISOString(),build:document.querySelector('meta[name="app-build"]')?.content,
    youtube:{videoId:read(()=>player.getVideoData().video_id),state:read(()=>player.getPlayerState()),time:read(()=>player.getCurrentTime()),muted:read(()=>player.isMuted()),volume:read(()=>player.getVolume())},
    reference:reference?{videoId:reference.videoId,cacheId:reference.cacheId,vocalMode:reference.vocalMode}:null,
    media:['stem-audio','recording-audio','post-audio'].map(id=>{const a=$(id);return{id,source:a?.getAttribute('src')||null,paused:a?.paused,muted:a?.muted,volume:a?.volume,time:a?.currentTime};}),
    preview:$('preview-status')?.textContent,input:read(()=>stream.getAudioTracks()[0].label),
    capture:read(()=>stream.getAudioTracks()[0].getSettings()),context:context?{state:context.state,sink:context.sinkId,sampleRate:context.sampleRate}:null,extra};
  // Browser-specific device IDs are unnecessary; keep only the visible input label and processing flags.
  if(snapshot.capture){delete snapshot.capture.deviceId;delete snapshot.capture.groupId;}
  playbackTraceQueue=playbackTraceQueue.catch(()=>{}).then(async()=>{
    const base='http://127.0.0.1:4274',session=await(await fetch(base+'/session',{signal:AbortSignal.timeout(5000)})).json();
    if(!session.features?.includes('playback-trace'))throw new Error('本機工具尚未支援追蹤');
    const response=await fetch(base+'/playback-trace',{method:'POST',headers:{'Content-Type':'application/json','X-Karaoke-Token':session.token},body:JSON.stringify(snapshot),signal:AbortSignal.timeout(5000)});
    if(!response.ok)throw new Error(`本機回應 ${response.status}`);
    playbackTraceStatus(`播放追蹤已連線 · 本機已收到 ${stage}（不錄音）`);
  }).catch(error=>playbackTraceStatus(`播放追蹤未送達：${error.message}。這次紀錄尚未收到。`));
}

let player, playerReady, playerAttempt, apiPromise, stream, context, analyser, samples, micTimer;
let calibration, micStartPromise, micPitch = null, nativeCapture = null, micAbort = null;
try{if(localStorage.getItem('karaoke.capture-mode.v1')==='native')$('capture-mode').value='native';}catch{}
let generation = 0, history = [], beatTimer, beatStart, probeController;
const supported = window.isSecureContext && !!navigator.mediaDevices?.getUserMedia;
$('environment').textContent = supported ? '桌機收音環境就緒。可測試麥克風與播放器；未取得歌曲基準前不計分。' : '無法開啟麥克風。請用桌機 Chrome／Edge 開啟 HTTPS 網址，並確認瀏覽器有收音權限。';
$('environment').classList.toggle('error', !supported);
$('mic-start').disabled = !supported;
const status = text => { $('player-status').textContent = text; };
const voiceOutput = createVoiceOutput();
function createVoiceOutput() {
  const toggle=$('voice-output-enabled'), device=$('voice-output-device');
  const volume=$('voice-output-volume'), message=$('voice-output-status');
  let input=null, nativeInput=null, request=0, deviceRequest=0, output=null;
  const canChoose=typeof AudioContext.prototype.setSinkId==='function';
  device.disabled=!canChoose;
  function release(session){
    if(!session)return;
    if(session.speaker){session.speaker.disconnect();return;}
    session.context.onstatechange=null;
    session.nativeSource?.disconnect();session.source?.disconnect();session.gain?.disconnect();
    if(session.context.state!=='closed')session.context.close().catch(()=>{});
  }
  function detach(){const previous=output;output=null;release(previous);}
  function setVolume(){
    output?.speaker?.setVolume(Number(volume.value)/100);
    if(output?.gain)output.gain.gain.setTargetAtTime(Number(volume.value)/100,output.context.currentTime,.005);
    $('voice-output-volume-value').textContent=volume.value+'%';
  }
  function silence(text){
    request++;detach();toggle.checked=false;
    message.textContent=text|| (input?'歌聲輸出已關閉，麥克風仍持續收音。':'請先開啟麥克風，再勾選歌聲輸出。');
  }
  async function play(){
    const current=++request, source=input, native=nativeInput, sinkId=device.value;
    detach();
    if(!toggle.checked||!source||source.getAudioTracks().every(t=>t.readyState!=='live'))return silence();
    message.textContent='正在啟動低延遲歌聲輸出…';
    let session;
    try{
      if(native?.createSpeakerMonitor){
        session={speaker:native.createSpeakerMonitor({deviceId:sinkId,volume:Number(volume.value)/100,onError:error=>{if(current===request)silence('歌聲輸出中斷：'+error.message);}})};
        output=session;
        await session.speaker.ready;
        if(current!==request||source!==input||!toggle.checked){release(session);return;}
        message.textContent='本機歌聲直送喇叭中 · '+originalText(device.selectedOptions[0]);
        return;
      }
      const context=new AudioContext({latencyHint:'interactive',...(native?.createMonitorSource?{sampleRate:native.monitorSampleRate}:{})});
      session={context,source:null,gain:null};output=session;
      await Promise.all([context.resume(),canChoose?context.setSinkId(sinkId):Promise.resolve()]);
      if(current!==request||source!==input||!toggle.checked){release(session);return;}
      if(native?.createMonitorSource){
        session.nativeSource=await native.createMonitorSource(context,error=>{if(current===request)silence('歌聲輸出中斷：'+error.message);});
        if(current!==request||source!==input||!toggle.checked){release(session);return;}
        session.source=session.nativeSource.node;
      }else session.source=context.createMediaStreamSource(source);
      session.gain=context.createGain();
      session.gain.gain.value=Number(volume.value)/100;
      session.source.connect(session.gain);session.gain.connect(context.destination);
      context.onstatechange=()=>{if(output===session&&context.state!=='running')silence('歌聲輸出已暫停，請確認喇叭後重新開啟。');};
      message.textContent='低延遲歌聲輸出中 · '+originalText(device.selectedOptions[0]);
    }catch(error){
      release(session);
      if(current!==request)return;
      silence(error.name==='NotAllowedError'?'歌聲輸出未獲允許，請確認瀏覽器的音訊播放與輸出裝置權限後重試。':error.name==='NotFoundError'?'找不到選取的喇叭，請重新整理並選擇輸出裝置。':'歌聲輸出失敗：'+error.message);
    }
  }
  async function refreshDevices(){
    const current=++deviceRequest, previous=device.value, native=nativeInput;
    try{
      const devices=native?.speakerDevices?await native.speakerDevices():await navigator.mediaDevices?.enumerateDevices();
      if(current!==deviceRequest)return;
      device.disabled=!(native?.speakerDevices||canChoose);
      device.replaceChildren(new Option('系統預設喇叭',''));
      if(native?.speakerDevices||canChoose)for(const [i,d] of (devices||[]).filter(d=>d.kind==='audiooutput'&&d.deviceId&&d.deviceId!=='default').entries())device.append(d.label?userOption(d.label,d.deviceId):new Option('喇叭 '+(i+1),d.deviceId));
      if([...device.options].some(o=>o.value===previous))device.value=previous;
      else if(toggle.checked)silence('原輸出裝置已離線，請重新選擇喇叭並開啟歌聲輸出。');
      if(!native?.speakerDevices&&!canChoose&&!toggle.checked)message.textContent='此瀏覽器使用系統預設喇叭；開啟麥克風後可勾選歌聲輸出。';
    }catch{if(current===deviceRequest&&!toggle.checked)message.textContent='無法取得喇叭清單；可先使用系統預設喇叭。';}
  }
  toggle.addEventListener('change',()=>{if(toggle.checked)play();else silence();});
  device.addEventListener('change',()=>{if(toggle.checked)play();});
  volume.addEventListener('input',setVolume);
  $('voice-output-refresh').addEventListener('click',refreshDevices);
  setVolume();refreshDevices();
  return {
    attach(source,native=null){input=source;nativeInput=native;device.value='';toggle.disabled=false;refreshDevices();},
    stop(){input=null;nativeInput=null;toggle.disabled=true;silence();refreshDevices();},
    refreshDevices
  };
}

function resetOffset() { $('offset').value = $('offset').defaultValue; $('offset-value').textContent = `${$('offset').value} ms`; }
function loadAPI() {
  if (window.YT?.Player) return Promise.resolve();
  if (apiPromise) return apiPromise;
  apiPromise = new Promise((resolve, reject) => {
    // iframe_api sets YT.loading before it fetches www-widgetapi. If the latter
    // fails, loading iframe_api again is a no-op. Retry the observed official
    // widget URL instead; do not mutate YouTube's private loading flags.
    const previous = document.getElementById('www-widgetapi-script');
    const widgetUrl = previous?.src;
    const retryWidget = !!widgetUrl && /^https:\/\/www\.youtube\.com\/s\/player\/[a-zA-Z0-9_./-]+\/www-widgetapi\.js$/.test(widgetUrl);
    const script = document.createElement('script');
    let settled = false;
    const cleanup = () => {
      clearTimeout(timer); window.removeEventListener('error', resourceError, true);
      script.onerror = null;
      if (window.onYouTubeIframeAPIReady === ready) window.onYouTubeIframeAPIReady = undefined;
    };
    const fail = text => {
      if (settled) return;
      settled = true; cleanup();
      // Keep the failed widget element's URL for the next explicit retry.
      if (!retryWidget) script.remove();
      apiPromise = null; reject(new Error(text));
    };
    const ready = () => {
      if (settled || !window.YT?.Player) return;
      settled = true; cleanup(); resolve();
    };
    const resourceError = event => {
      if (event.target?.id === 'www-widgetapi-script') fail('YouTube 播放器程式（第二段）載入失敗，請按「載入影片」重試。歌曲基準仍保留在本機。');
    };
    const timer = setTimeout(() => fail('YouTube 播放器程式載入逾時，請按「載入影片」重試。這不是本機歌曲基準或安裝失敗。'), 15000);
    window.onYouTubeIframeAPIReady = ready;
    window.addEventListener('error', resourceError, true);
    script.src = retryWidget ? widgetUrl : 'https://www.youtube.com/iframe_api';
    script.onerror = () => fail('YouTube 播放器入口程式連線失敗，請按「載入影片」重試。歌曲基準仍保留在本機。');
    if (retryWidget) { script.id = 'www-widgetapi-script'; previous.replaceWith(script); }
    else document.head.append(script);
  });
  return apiPromise;
}
function initializePlayer(id) {
  if (playerReady) return playerReady;
  const attempt = { active: true, ready: false, instance: null };
  playerAttempt=attempt;
  let readyTimeout;
  playerReady = new Promise((resolve, reject) => {
    readyTimeout = setTimeout(() => reject(new Error('YouTube 播放器初始化逾時，請按「載入影片」重試；不需要重新安裝本機工具。')), 20000);
    attempt.instance = player = new YT.Player('player', { width: '100%', height: '100%', videoId: id,
      playerVars: { playsinline: 1, origin: location.origin, autoplay: 0 },
      events: {
        onReady: () => {
          if (!attempt.active) return;
          attempt.ready = true; clearTimeout(readyTimeout); resolve();
          $('video-placeholder').style.display = 'none'; status('請按影片上的播放按鈕。');
        },
        onStateChange: e => {
          if (!attempt.active) return;
          tracePlayback('youtube-state',{state:e.data});
          status(({ '-1': '尚未開始', 0: '影片結束', 1: '播放中', 2: '暫停', 3: '緩衝中', 5: '已就緒' }[e.data] || '播放器狀態變更'));
          if (e.data === 1) calibration?.cancel(); singing.playerState(e.data);
        },
        onAutoplayBlocked: () => { if (attempt.active) status('請直接點影片上的播放按鈕。'); },
        onError: e => {
          if (!attempt.active) return;
          clearTimeout(readyTimeout);
          const text = `影片無法播放（${e.data}）。可能禁止嵌入、已移除或需登入；請換影片。`;
          if (!attempt.ready) reject(new Error(text));
          status(text); singing.playerState(2);
        }
      }
    });
  }).catch(error => {
    // A failed iframe cannot be reused. Ignore its late callbacks and restore
    // the mount so the next user request starts a fresh player.
    attempt.active = false; clearTimeout(readyTimeout);
    try { attempt.instance?.destroy?.(); } catch {}
    player = null; playerReady = null;
    const mount = document.createElement('div'); mount.id = 'player';
    if ($('player')) $('player').replaceWith(mount);
    else $('video-placeholder').after(mount);
    $('video-placeholder').style.display = '';
    throw error;
  });
  return playerReady;
}
let autoLoadTimer=0, videoLoading=false;
async function loadVideo(e) {
  e?.preventDefault(); clearTimeout(autoLoadTimer);
  const id = selectedMediaId();
  if (!id) return status('請輸入有效的 YouTube 網址，或先選擇本機 MV／音檔。');
  const button = $('song-form').querySelector('button'); button.disabled = true; videoLoading = true;
  status(isLocalMediaId(id)?'正在載入本機媒體…':'正在載入 YouTube 播放器…');
  try {
    tracePlayback('load-video-request',{videoId:id});
    await singing.changeSong(id);
    if(isLocalMediaId(id)){
      if(player?.sourceKind==='local'&&player.getVideoData().video_id===id&&player.getIframe().readyState>=1){selectMediaSource(id,document,player.getIframe().tagName==='AUDIO'?'audio':'video');return true;}
      const media=await mediaRequest('/local-media/'+id);resetPlayer();
      const audioOnly=media.kind==='audio';selectMediaSource(id,document,media.kind);
      const video=$(audioOnly?'local-audio':'local-video');video.hidden=false;video.dataset.title=media.title;$('player').hidden=true;
      $('local-audio-panel').hidden=!audioOnly;$('local-audio-title').textContent=media.title;
      player=localVideoPlayer(video,id,state=>{if(state===1)calibration?.cancel();singing.playerState(state);},status);
      await new Promise((resolve,reject)=>{
        const cleanup=()=>{clearTimeout(timer);video.removeEventListener('loadedmetadata',ready);video.removeEventListener('error',fail);};
        const ready=()=>{cleanup();resolve();},fail=()=>{cleanup();reject(Error('本機媒體載入失敗，請重新載入。'));};
        const timer=setTimeout(fail,20000);video.addEventListener('loadedmetadata',ready);video.addEventListener('error',fail);video.src=LOCAL_BASE+media.playbackPath;video.load();
      });
      $('video-placeholder').style.display='none';status(`已載入${audioOnly?'本機音檔':'本機 MV'}：${media.title}。請按播放，或準備歌曲基準。`);return true;
    }
    if(player?.sourceKind==='local')resetPlayer();
    await loadAPI();
    const existing = !!playerReady;
    await initializePlayer(id);
    if (existing) { player.cueVideoById(id); status('影片已切換，請在播放器內按播放。'); }
    tracePlayback('load-video-ready',{videoId:id}); return true;
  } catch (err) { status(err.message); return false; } finally { button.disabled = false; videoLoading = false; }
}
$('song-form').addEventListener('submit', loadVideo);
// 貼上或打完 YouTube 網址約 0.5 秒後自動載入；同一部影片不重載；唱歌、錄音、準備中只提示不切換。
function autoLoadBlocked(){
  let w={};try{w=JSON.parse($('player-section').dataset.workflow||'{}');}catch{}
  return !!(w.hasTake||w.busy||['singing','preparing','finishing','restarting'].includes(w.phase)||$('url').disabled||$('song-form').querySelector('button').disabled);
}
function loadedYoutubeId(){try{return player&&player.sourceKind!=='local'?player.getVideoData?.()?.video_id||null:null;}catch{return null;}}
$('url').addEventListener('input',()=>{
  clearTimeout(autoLoadTimer);
  autoLoadTimer=setTimeout(()=>{
    const id=youtubeId($('url').value.trim());
    if(!id||videoLoading||id===loadedYoutubeId())return;
    if(autoLoadBlocked())return status('正在唱歌、錄音或準備歌曲，網址不會自動切換；結束後請按「載入影片」。');
    void loadVideo();
  },500);
});
function resetPlayer(){
  if(playerAttempt)playerAttempt.active=false;playerAttempt=null;
  player?.destroy?.();player=null;playerReady=null;
  const mount=document.createElement('div');mount.id='player';if($('player'))$('player').replaceWith(mount);else $('video-placeholder').after(mount);
  $('local-video').hidden=true;$('local-audio-panel').hidden=true;
}
initializeLocalMedia(loadVideo);
function log(text, cls = '') { const li = document.createElement('li'); li.textContent = text; li.className = cls; $('probe-log').append(li); }
async function readLimited(response, max, partial = false) {
  if (!response.body) throw new Error('瀏覽器未提供可讀取的串流。');
  const reader = response.body.getReader(); let length = 0; const parts = [];
  try {
    while (true) {
      const { done, value } = await reader.read(); if (done) break;
      if (value.length > max - length && !partial) throw new Error('回應超過測試大小上限。');
      const part = value.subarray(0, max - length); parts.push(part); length += part.length;
      if (length >= max) break;
    }
  } finally { await reader.cancel().catch(() => {}); }
  const bytes = new Uint8Array(length); let offset = 0;
  for (const part of parts) { bytes.set(part, offset); offset += part.length; }
  return bytes;
}
$('probe').addEventListener('click', async () => {
  const id = youtubeId($('url').value.trim()); $('probe-log').replaceChildren();
  if (!id) return log('請先填入有效的 YouTube 影片網址。', 'fail');
  $('probe').disabled = true;
  const controller = new AbortController(); probeController = controller;
  const timer = setTimeout(() => controller.abort(), 15000); let stage = '影片頁面';
  try {
    log('本機瀏覽器直接讀取 YouTube 頁面…');
    const response = await fetch(`https://www.youtube.com/watch?v=${id}`, { mode: 'cors', credentials: 'omit', signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = playerResponse(new TextDecoder().decode(await readLimited(response, 3 * 1024 * 1024)));
    log('影片頁面可讀取。', 'pass');
    const formats = [...(data?.streamingData?.adaptiveFormats || []), ...(data?.streamingData?.formats || [])];
    const format = formats.find(f => /^audio\//.test(f.mimeType || '') && f.url);
    if (!format) { log('未找到可直接讀取的音訊 URL。可能需要播放器簽章、登入或頁面結構不同；原型未實作這些處理。', 'fail'); return; }
    const url = new URL(format.url);
    if (url.protocol !== 'https:' || !url.hostname.endsWith('.googlevideo.com')) throw new Error('不是預期的 HTTPS YouTube 媒體來源。');
    stage = '音訊串流'; log('讀取最多 128 KiB 音訊串流…');
    const response2 = await fetch(url, { mode: 'cors', credentials: 'omit', signal: controller.signal });
    if (!response2.ok) throw new Error(`HTTP ${response2.status}`);
    const bytes = await readLimited(response2, 128 * 1024, true);
    if (!bytes.length) throw new Error('音訊回應為空。');
    log(`讀取成功：${bytes.length.toLocaleString()} bytes，只在本機記憶體中，未保存。`, 'pass');
    log('這只證明串流可讀取；尚未解碼、人聲分離或建立基準。');
  } catch (err) {
    const reason = err.name === 'AbortError' ? '逾時或測試已中止。' : err instanceof TypeError ? '瀏覽器拒絕讀取；可能是 CORS、網路或內容阻擋，此訊息無法區分原因。' : err.message;
    log(`${stage}測試未通過：${reason}`, 'fail');
    log('未取得可分析音訊，不能建立基準或評分。嵌入播放仍可獨立測試。', 'fail');
  } finally { clearTimeout(timer); if (probeController === controller) probeController = null; $('probe').disabled = false; }
});
function latency(x) { return Number.isFinite(x) ? `${Math.round(x * 1000)} ms（估計）` : '未提供，不能當作 0 ms'; }
$('offset').addEventListener('input', () => { $('offset-value').textContent = `${$('offset').value} ms`; });
async function stopMic(message = '收音已停止，麥克風已釋放；錄音結果請查看下方錄音狀態。', rewind = false, captureError = null) {
  generation++; clearInterval(micTimer); calibration?.cancel(); voiceOutput.stop();
  const recordingEnd = singing.stopRecording(captureError);
  micAbort?.abort(); micAbort=null; nativeCapture?.stop(); nativeCapture=null;
  const oldStream = stream, oldContext = context;
  stream = context = analyser = samples = null; micPitch = null; history = [];
  oldStream?.getTracks().forEach(t => t.stop());
  if (oldContext) oldContext.onstatechange = null;
  $('mic-start').disabled = !supported; $('mic-stop').disabled = true;
  $('mic-badge').textContent = '麥克風未開啟'; $('mic-status').textContent = message;
  $('note').textContent = '—'; $('frequency').textContent = '等待收音'; $('cents').textContent = '單音音高 · 65–1000 Hz';
  $('level').value = 0; $('level-text').textContent = '— dBFS'; $('device').textContent = '收音已停止。'; singing.micStopped({ rewind, reason: message }); draw();
  await recordingEnd;
  if (oldContext) await oldContext.close().catch(() => {});
}
function startMic() {
  if (stream && context?.state === 'running') return Promise.resolve(true);
  if (!micStartPromise) micStartPromise = activateMic().finally(() => { micStartPromise = null; });
  return micStartPromise;
}
async function activateMic() {
  const token = ++generation; let pendingStream, pendingContext, pendingNative;
  const native=$('capture-mode').value==='native', controller=new AbortController();micAbort=controller;
  tracePlayback('mic-before');
  $('mic-start').disabled = true; $('mic-stop').disabled = false; $('mic-status').textContent = native?'正在啟動本機麥克風，請允許 Python 收音…':'請允許網站使用麥克風…';
  try {
    pendingContext = new AudioContext({ latencyHint: 'interactive', ...(native?{sampleRate:48000}:{}), sinkId: { type: 'none' } });
    const resumed = pendingContext.resume().catch(() => {});
    tracePlayback('mic-context-created',{sink:pendingContext.sinkId});
    if(native){pendingNative=await openNativeMicrophone(pendingContext,{deviceId:$('input-device').value,signal:controller.signal,onError:error=>{if(token===generation)stopMic(error.message,false,error);}});pendingStream=pendingNative.stream;}
    else pendingStream = await navigator.mediaDevices.getUserMedia({ audio: { ...($('input-device').value ? { deviceId: { exact: $('input-device').value } } : {}), echoCancellation: false, noiseSuppression: false, autoGainControl: false }, video: false });
    tracePlayback('mic-stream-acquired',{input:pendingStream.getAudioTracks()[0]?.label});
    await resumed;
    if (token !== generation) { pendingNative?.stop(); pendingStream.getTracks().forEach(t => t.stop()); await pendingContext.close(); return; }
    stream = pendingStream; context = pendingContext; nativeCapture=pendingNative;
    const source = nativeCapture?.source || context.createMediaStreamSource(stream);
    analyser = context.createAnalyser(); analyser.fftSize = 4096; source.connect(analyser);
    samples = new Float32Array(analyser.fftSize);
    const track = stream.getAudioTracks()[0], settings = track.getSettings();
    await refreshInputs();
    if (token !== generation) return;
    $('device').textContent = `輸入：${pendingNative?.label || track.label || '瀏覽器預設麥克風'}${native?'（本機相容收音）':''}\n取樣率：${context.sampleRate} Hz\n輸入延遲：${latency(settings.latency)}\nWeb Audio 輸出延遲：${latency(context.outputLatency)}\n分析輸出：${context.sinkId?.type === 'none' ? '僅分析，不開啟喇叭輸出' : '瀏覽器預設（不支援分析專用輸出）'}\n回音消除：${String(settings.echoCancellation ?? '未知')}\n\n輸出估計屬於本頁 AudioContext，不代表 YouTube 的延遲；不會自動填入補償值。`;
    track.onended = () => stopMic('麥克風中斷，請重新開啟。');
    track.onmute = () => { $('mic-status').textContent = '收音暫時中斷，目前音高不可用。'; };
    track.onunmute = () => { $('mic-status').textContent = '收音已恢復。'; };
    context.onstatechange = () => { if (context?.state !== 'running') $('mic-status').textContent = '音訊處理暫停，請停止後重新開啟。'; };
    $('mic-badge').textContent = '● 收音中'; $('mic-status').textContent = '持續唱「啊」試試。單獨測試麥克風不保存；按「從頭開始唱」依錄音選項保存。';
    voiceOutput.attach(stream,nativeCapture);
    micTimer = setInterval(readMic, 65); tracePlayback('mic-before-session'); singing.micStarted(); tracePlayback('mic-after-session');
    setTimeout(()=>{if(token===generation)tracePlayback('mic-after-1s');},1000); return true;
  } catch (err) {
    pendingNative?.stop();
    pendingStream?.getTracks().forEach(t => t.stop());
    if (pendingContext && pendingContext.state !== 'closed') await pendingContext.close().catch(() => {});
    if (token !== generation) return;
    await stopMic(err.name === 'NotAllowedError' ? '麥克風未獲允許。請點網址列的網站權限圖示，允許麥克風後再重試。' : err.name === 'NotFoundError' ? '找不到麥克風，請檢查裝置。' : `收音失敗：${err.message}`);
  }
}
$('mic-start').addEventListener('click', startMic);
for(const id of ['stem-audio','recording-audio','post-audio'])for(const event of ['play','pause','volumechange','emptied'])$(id).addEventListener(event,()=>tracePlayback('media-event',{id,event}));
window.addEventListener('karaoke-library-selected',e=>tracePlayback('library-selected',e.detail));
$('mic-stop').addEventListener('click', () => stopMic(undefined, true));
function readMic() {
  if (!analyser || !samples || context?.state !== 'running') return;
  analyser.getFloatTimeDomainData(samples);
  const result = stream.getAudioTracks()[0]?.muted ? { hz: null, rms: 0 } : detectPitch(samples, context.sampleRate / (2 ** ((singing.reference()?.pitchShift || 0) / 12)));
  if(result.hz!==null)result.hz*=2 ** ((singing.reference()?.pitchShift || 0) / 12);
  micPitch = result.hz;
  const note = noteOf(result.hz), now = performance.now() / 1000;
  history.push({ time: now, midi: note?.midi ?? null }); history = history.filter(p => now - p.time <= 8);
  calibration?.sample(now - analyser.fftSize / (2 * context.sampleRate), result.hz);
  if (player?.getCurrentTime) singing.sample(player.getCurrentTime() - Number($('offset').value) / 1000 - analyser.fftSize / (2 * context.sampleRate), result.hz);
  $('note').textContent = note?.name ?? '—'; $('frequency').textContent = result.hz ? `${result.hz.toFixed(1)} Hz` : '未偵測到穩定音高';
  $('cents').textContent = note ? `${note.cents >= 0 ? '+' : ''}${note.cents} cents · 相對最近音名，非歌曲分數` : '單音音高 · 65–1000 Hz';
  $('level').value = Math.min(1, result.rms * 4); $('level-text').textContent = result.rms > 0 ? `${Math.max(-90, 20 * Math.log10(result.rms)).toFixed(0)} dBFS` : '— dBFS'; draw();
}
let chartPalette;
function draw() {
  if (!chartPalette) {
    const style = getComputedStyle(document.documentElement);
    chartPalette = { grid: style.getPropertyValue('--chart-grid').trim(), label: style.getPropertyValue('--chart-label').trim(), voice: style.getPropertyValue('--accent').trim() };
  }
  const canvas = $('pitch-chart'), rect = canvas.getBoundingClientRect(), scale = window.devicePixelRatio || 1;
  canvas.width = Math.round(rect.width * scale); canvas.height = Math.round(rect.height * scale);
  const ctx = canvas.getContext('2d'); ctx.scale(scale, scale);
  const w = rect.width, h = rect.height, y = midi => 12 + (84 - midi) / 48 * (h - 24);
  ctx.font = '10px system-ui';
  for (let m = 36; m <= 84; m += 12) { ctx.strokeStyle = chartPalette.grid; ctx.beginPath(); ctx.moveTo(28, y(m)); ctx.lineTo(w, y(m)); ctx.stroke(); ctx.fillStyle = chartPalette.label; ctx.fillText(`C${m / 12 - 1}`, 0, y(m) + 3); }
  const now = performance.now() / 1000; ctx.strokeStyle = chartPalette.voice; ctx.lineWidth = 2; ctx.beginPath();
  let connected = false, last = 0;
  for (const p of history) {
    if (p.midi === null || now - p.time > 8) { connected = false; continue; }
    const x = 28 + (1 - (now - p.time) / 8) * (w - 28), py = Math.max(12, Math.min(h - 12, y(p.midi)));
    if (connected && p.time - last < .2) ctx.lineTo(x, py); else ctx.moveTo(x, py); connected = true; last = p.time;
  }
  ctx.stroke();
  const reference = singing.reference();
  if (reference && player?.getCurrentTime) {
    const time = player.getCurrentTime() - Number($('offset').value) / 1000;
    ctx.strokeStyle = '#90cbef'; ctx.lineWidth = 1.5; ctx.beginPath(); let linked = false;
    for (let x = 28; x <= w; x += 2) {
      const t = time - 8 * (1 - (x - 28) / (w - 28));
      const note = noteOf(reference.frames[Math.floor(t / reference.step)]);
      if (!note) { linked = false; continue; }
      const py = Math.max(12, Math.min(h - 12, y(note.midi)));
      if (linked) ctx.lineTo(x, py); else ctx.moveTo(x, py); linked = true;
    }
    ctx.stroke();
  }
}
window.addEventListener('karaoke-theme-change', () => { chartPalette = null; draw(); });
new ResizeObserver(draw).observe($('pitch-chart'));
function stopBeats() { clearInterval(beatTimer); beatTimer = null; $('beat-toggle').textContent = '啟動節拍燈'; [...$('beats').children].forEach(d => d.classList.remove('active')); }
function updateBeat() {
  const bpm = Number($('bpm').value); if (bpm < 40 || bpm > 220 || !Number.isFinite(bpm)) return stopBeats();
  const beat = Math.floor((performance.now() - beatStart) / (60000 / bpm)) % 4;
  [...$('beats').children].forEach((d, i) => d.classList.toggle('active', i === beat));
}
$('beat-toggle').addEventListener('click', () => {
  if (beatTimer) return stopBeats(); if (!$('bpm').reportValidity() || !$('bpm').value) return;
  beatStart = performance.now(); $('beat-toggle').textContent = '停止節拍燈'; beatTimer = setInterval(updateBeat, 35); updateBeat();
});
$('bpm').addEventListener('input', () => { if (beatTimer) { beatStart = performance.now(); updateBeat(); } });
setInterval(() => {
  if (!player?.getCurrentTime) return; const t = player.getCurrentTime(); if (!Number.isFinite(t)) return;
  $('player-time').textContent = `${t.toFixed(2)} s`; $('aligned-time').textContent = `${alignedTime(t, Number($('offset').value)).toFixed(2)} s`;
}, 100);
navigator.mediaDevices?.addEventListener('devicechange', () => { voiceOutput.refreshDevices(); resetOffset(); if (stream) stopMic('裝置已變更，補償已回到預設＋200 ms。請重新開啟收音並校正。'); });
function cleanup() { probeController?.abort(); stopBeats(); stopMic('頁面已離開前景，收音已停止。請重新開啟。'); }
document.addEventListener('visibilitychange', () => { if (document.hidden) cleanup(); }); window.addEventListener('pagehide', cleanup);

let inputRefreshGeneration=0;
async function refreshInputs() {
  const request=++inputRefreshGeneration, mode=$('capture-mode').value;
  const select = $('input-device'), previous = select.value;
  try {
    const devices = mode==='native'?await nativeInputDevices():await navigator.mediaDevices.enumerateDevices();
    if(request!==inputRefreshGeneration||mode!==$('capture-mode').value)return;
    select.replaceChildren(new Option('系統預設麥克風', ''));
    for (const [i, d] of devices.filter(d => d.kind === 'audioinput').entries()) {
      if (d.deviceId && d.deviceId !== 'default') select.append(d.label?userOption(d.label,d.deviceId):new Option(`麥克風 ${i + 1}`,d.deviceId));
    }
    if ([...select.options].some(o => o.value === previous)) select.value = previous;
  } catch(error) { if(request===inputRefreshGeneration&&mode===$('capture-mode').value&&mode==='native')$('mic-status').textContent=error.message; }
}
$('capture-mode').addEventListener('change',async()=>{await stopMic('已切換收音方式，請重新選擇麥克風並開啟。');$('input-device').replaceChildren(new Option('系統預設麥克風',''));try{localStorage.setItem('karaoke.capture-mode.v1',$('capture-mode').value);}catch{}await refreshInputs();});
$('input-device').addEventListener('change', () => {
  resetOffset(); stopMic('已切換麥克風，補償已回到預設＋200 ms。請按開啟麥克風使用新裝置。');
});

const localToolNames = { python: 'Python 環境', node: 'Node.js 22+', ffmpeg: 'FFmpeg', ffprobe: 'ffprobe', ytDlp: 'yt-dlp', demucs: 'Demucs', torch: 'PyTorch', torchaudio: 'TorchAudio', soundfile: 'SoundFile' };
$('local-check').addEventListener('click', async () => {
  const button = $('local-check'), panel = document.querySelector('.local-tools');
  button.disabled = true; panel.dataset.state = 'checking';
  $('local-status').textContent = '正在檢查這台電腦的本機工具…';
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch('http://127.0.0.1:4274/health', { signal: controller.signal, cache: 'no-store', credentials: 'omit' });
    if (!response.ok) throw new Error('本機工具回應失敗。');
    const result = await response.json();
    if (result.app !== 'karaoke-local-helper' || result.version !== 1 || typeof result.checks !== 'object' || !result.checks) throw new Error('本機工具版本不相容，請重新下載工具包。');
    if (!result.features?.includes('separation-progress')) throw new Error('本機工具需要更新，請重新下載工具包，停止舊工具後再啟動。');
    const missing = Object.entries(localToolNames).filter(([key]) => result.checks[key] !== true).map(([, name]) => name);
    if (missing.length || !result.ready) {
      panel.dataset.state = 'warning'; $('install-guide').open = true;
      $('local-status').textContent = '已連線，但本機安裝尚未完整。';
      $('local-detail').textContent = '缺少或無法使用：' + (missing.join('、') || '請重新執行安裝腳本') + '。請參考下方安裝指引。';
    } else {
      panel.dataset.state = 'ready';
      window.dispatchEvent(new Event('local-tools-ready'));
      $('local-status').textContent = '✓ 本機工具已啟動，音訊處理環境已就緒。';
      $('local-detail').textContent = 'yt-dlp、FFmpeg 與 Demucs 已找到。音訊在你的電腦處理；目前此按鈕只檢查環境，不會下載或錄音。';
    }
  } catch (error) {
    panel.dataset.state = 'warning'; $('install-guide').open = true;
    $('local-status').textContent = '尚未連上本機工具，無法判定是否已安裝。';
    $('local-detail').textContent = error.name === 'AbortError' ? '連線逾時。若工具已安裝，請啟動 start-local.ps1，並允許瀏覽器的本機網路存取後重試。' : error instanceof TypeError ? '可能尚未啟動、尚未安裝，或瀏覽器阻擋本機連線。已安裝者請先執行 start-local.ps1；首次使用請看安裝指引。' : error.message;
  } finally { clearTimeout(timer); button.disabled = false; }
});

const singing = createKaraokeSession({ voiced: () => micPitch !== null, context: () => context, stream: () => stream, inputSource: () => nativeCapture?.source, player: () => player, micReady: () => !!stream && context?.state === 'running', stopMic: () => stopMic(), startMic, stopBeats, loadVideo: () => loadVideo(), cancelCalibration: () => calibration?.cancel() });

calibration = createCalibration({ context: () => context, micReady: () => !!stream && context?.state === 'running', beforeStart: () => singing.pauseForCalibration() });

window.addEventListener('pageshow', e => { if (e.persisted) location.reload(); });

window.addEventListener('local-tools-ready',connectPlaybackTrace);
connectPlaybackTrace();

// Restore device choices after reload/helper startup without opening the microphone.
function refreshNativeChoices(){if($('capture-mode').value==='native')refreshInputs();}
window.addEventListener('local-tools-ready',refreshNativeChoices);
refreshNativeChoices();
