import {originalText,userText} from './i18n.mjs';
import {revealPlayerVideo} from './player-view.mjs';
import {selectedMediaId,selectMediaSource,isLocalMediaId} from './media-source.mjs';
import {keyLabel,keyShift} from './song-key.mjs';
import {recordingReviewKey} from './recording-review.mjs';
import {libraryRecordingCounts,updateLibraryRecordingBadges} from './library-recordings.mjs';
import {createLibrarySearch} from './library-search.mjs';
import {createKeyPlayback} from './key-playback.mjs';
import { youtubeId, noteOf } from './audio.mjs';
import { createSingerRecorder } from './recording.mjs';
import { createSegmentRecording } from './recording-segment-ui.mjs';
import { createMaskEditor } from './mask-editor.mjs';
import { ScoringTake, validateReference, savedResult, pitchDifference, scoringProfile, applyMasks, maskedCells } from './scoring.mjs';
const $ = id => document.getElementById(id);
const BASE = 'http://127.0.0.1:4274';
const HISTORY = 'karaoke.scores.v1';
export async function seekPlayerToStart(player, cancelled = () => false, timeoutMs = 10000) {
  player.pauseVideo();
  const deadline = performance.now() + timeoutMs;
  let requested = false;
  while (performance.now() < deadline) {
    if (cancelled()) throw new Error('同步已取消。');
    if (!requested && [0, 2, 5, -1].includes(player.getPlayerState())) { player.seekTo(0, true); requested = true; }
    if (requested && player.getCurrentTime() <= .05) return;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  throw new Error('播放器尚未確認回到開頭，請重試「從頭開始唱」。');
}

export function createKaraokeSession(options) {
  const preparationDefaults={'clip-seconds':'0','pitch-method':'rmvpe','separation-model':'demucs','separation-method':'single','vocal-mode':'all'};
  for(const [id,value]of Object.entries(preparationDefaults))$(id).value=value;
  $('keep-preview').checked=true;$('preparation-advanced').open=false;
  let reference = null, displayReference = null, excluded = [], maskBusy = false, masksSupported = false, take = null, jobId = null, token = null, generation = 0, timer;
  let requestedVocalMode = $('vocal-mode').value, requestedModel = $('separation-model').value, requestedPitch = $('pitch-method').value, requestedMethod = $('separation-method').value;
  const methodName = method => method === 'residual' ? '伴奏二次分離＋反向相減' : '單次分離';
  const modelName = model => ({ demucs: 'Demucs／htdemucs', 'bs-roformer': 'BS-RoFormer／Viperx 1297', 'mel-roformer': 'Mel-Band RoFormer／Kim 人聲' }[model] || 'Demucs／htdemucs');
  let phase = 'idle', loadedVideo = null, lastProgress = 0, rangeComplete = false;
  let libraryLocation = null, locationBusy = false;
  let libraryCounts=new Map();
  const librarySearch=createLibrarySearch({input:$('library-search'),clear:$('library-search-clear'),status:$('library-search-status'),list:$('library-list')});
  function recordingInventoryChanged(rows){
    libraryCounts=libraryRecordingCounts(rows);
    updateLibraryRecordingBadges($('library-list'),libraryCounts);
  }
  const segmentLocks=new Map();
  let previewUrl = null, previewRequest = null, previewSerial = 0, restartToken = 0, segmented = null;
  let wholeGuide = null, requestedKey=0;
  function pauseGuide(c = wholeGuide) {
    for (const node of c?.nodes || []) { try { node.stop(); } catch {} node.disconnect(); }
    if (c) c.nodes = [];
  }
  function stopGuide() {
    const c = wholeGuide; wholeGuide = null;
    if (!c) return;
    c.armed = false; pauseGuide(c); c.context?.close().catch(() => {});
    if (c.wasMuted) c.player.mute?.(); else c.player.unMute?.();
  }
  async function prepareGuide(ref, player, mode, cancelled) {
    stopGuide(); player.pauseVideo();
    const c = wholeGuide = { player, mode, wasMuted: !!player.isMuted?.(), armed: false, nodes: [], buffers: [] };
    if (ref.pitchShift || mode !== 'backing') return;
    if (!ref.hasPreview) throw Error('只有伴樂需要已保存的分離音軌，請先補建試聽音軌，或改選「原唱＋伴樂」。');
    c.context = new AudioContext(); await c.context.resume();
    for (const stem of ['accompaniment', ...(ref.vocalMode === 'lead' ? ['backing'] : [])]) {
      const bytes = await loadRecordingStem(ref, stem);
      if (cancelled() || wholeGuide !== c) return;
      const buffer = await c.context.decodeAudioData(bytes);
      if (cancelled() || wholeGuide !== c) return;
      if (buffer.duration < ref.duration - .2) throw Error('伴樂音軌長度不足，請補建試聽音軌。');
      c.buffers.push(buffer);
    }
  }
  function syncGuide(state, time) {
    const c = wholeGuide;
    if (!c?.armed || !c.context) return;
    if (state !== 1) { pauseGuide(c); return; }
    const rate = Number(c.player.getPlaybackRate?.()) || 1;
    if (c.nodes.length && c.rate === rate && Math.abs(c.anchorTime + (c.context.currentTime - c.anchorClock) * rate - time) < .12) return;
    pauseGuide(c); c.anchorTime = time; c.anchorClock = c.context.currentTime; c.rate = rate;
    for (const buffer of c.buffers) {
      if (time >= buffer.duration) continue;
      const node = c.context.createBufferSource(); node.buffer = buffer; node.playbackRate.value = rate;
      node.connect(c.context.destination); node.start(c.anchorClock, Math.max(0, time)); c.nodes.push(node);
    }
  }
  async function loadRecordingStem(ref,stem){
    if(!token)await ensureSession();
    const response=await fetch(BASE+`/library/${ref.cacheId}/${stem}`,{headers:{'X-Karaoke-Token':token},credentials:'omit',cache:'no-store',signal:AbortSignal.timeout(30000)});
    if(!response.ok)throw Error('無法讀取已保存的伴樂／和音，請確認本機工具與歌曲庫。');return response.arrayBuffer();
  }
  const recording = createSingerRecorder({reference:()=>phase==='preparing'?null:reference, voiced: options.voiced, context: options.context, stream: options.stream, inputSource:options.inputSource, player: options.player, loadStem:loadRecordingStem, onInventoryChanged:recordingInventoryChanged, pausePlayer: () => { options.player()?.pauseVideo?.(); stopPreview(); }});
  segmented = createSegmentRecording({recording, reference:()=>reference, player:options.player, micReady:options.micReady, startMic:options.startMic,
    canEnter:()=>!take&&!maskBusy&&!['preparing','finishing','restarting'].includes(phase), changed:()=>controls(),
    pauseOther:()=>{stopPreview();recording.clearPreview();options.cancelCalibration?.();},
    loadStem:loadRecordingStem,
  });
  const message = text => { $('score-status').textContent = text; };
  const keyPlayback=createKeyPlayback({player:options.player,loadStem:loadRecordingStem,mode:()=>$(segmented?.enabled()?'segment-guide-mode':'sing-guide-mode').value,status:text=>{$('song-key-status').textContent=text;}});
  for(const id of ['sing-guide-mode','segment-guide-mode'])$(id).addEventListener('change',()=>keyPlayback.sync());
  function updateMaskView() { displayReference = reference ? applyMasks(reference) : null; excluded = reference ? maskedCells(reference) : []; }
  const maskEditor = createMaskEditor({
    reference: () => reference, supported: () => masksSupported,
    canEdit: () => !!reference && masksSupported && !maskBusy && !take && !segmented?.busy() && !['preparing','finishing','restarting'].includes(phase),
    time: () => options.player()?.getCurrentTime?.(),
    seek(time) { options.player()?.pauseVideo?.(); options.player()?.seekTo?.(time,true); },
    async save(masks) {
      const current = generation, id = reference.cacheId;
      maskBusy = true; controls();
      try {
        const saved = await api(`/library/${id}/masks`, {method:'POST',body:JSON.stringify({masks})});
        if (current === generation && reference?.cacheId === id) { reference.masks = saved.masks; updateMaskView(); }
      } finally { maskBusy = false; controls(); }
    },
  });
  function difficultyHelp() {
    const profile = scoringProfile($('score-difficulty').value);
    $('difficulty-help').textContent = `${profile.label}：音高誤差 ${profile.pitchFull} 音分內、進拍誤差 ${Math.round(profile.rhythmFull * 1000)} 毫秒內給滿分，超過逐步扣分。100 音分＝1 個半音；難度與八度、評分範圍分開設定。`;
  }
  $('score-difficulty').addEventListener('change', difficultyHelp); difficultyHelp();
  function showTakeDifficulty() { $('take-difficulty').textContent = `本輪評分難度：${take.profile.label}（本輪固定）`; }

  function controls() {
    $('preparation-fields').disabled=!!take||segmented?.busy()||['preparing','finishing','restarting'].includes(phase);
    $('preparation-summary').textContent=['clip-seconds','separation-model','separation-method','vocal-mode','pitch-method'].map(id=>originalText($(id).selectedOptions[0])).join(' · ')+($('keep-preview').checked?' · 保留音軌':' · 不保留音軌');
    $('preparation-reset').disabled=!!take||['preparing','finishing','restarting'].includes(phase);
    for(const [element,disabled]of segmentLocks)element.disabled=disabled;segmentLocks.clear();
    if (phase === 'finishing') { $('mic-start').disabled = true; $('mic-stop').disabled = true; }
    for(const id of ['source-kind','local-media-file','local-media-saved','local-media-load','local-media-refresh'])if($(id))$(id).disabled=maskBusy||locationBusy||['preparing','finishing','restarting','singing'].includes(phase)||!!segmented?.busy()||$('local-media-controls')?.dataset.importing==='true';
    $('prepare-song').disabled = maskBusy || locationBusy || libraryLocation?.configured === false || ['preparing', 'finishing', 'restarting'].includes(phase);
    for (const id of ['library-path','library-choose','library-use-path']) $(id).disabled = locationBusy || !!reference || ['preparing','finishing','restarting'].includes(phase);
    $('rebuild-song').textContent=reference?.pitchShift?'重新建立此 Key':'重新分離並覆蓋';
    $('rebuild-song').disabled = maskBusy || !reference || !!take || ['preparing','finishing','restarting'].includes(phase);
    $('separation-model').disabled = !!take || ['preparing', 'finishing', 'restarting'].includes(phase);
    $('separation-method').disabled = !!take || ['preparing','finishing','restarting'].includes(phase);
    $('pitch-method').disabled = !!take || ['preparing','finishing','restarting'].includes(phase);
    $('vocal-mode').disabled = !!take || ['preparing', 'finishing', 'restarting'].includes(phase);
    $('keep-preview').disabled = ['preparing', 'finishing', 'restarting'].includes(phase);
    for (const stem of ['vocals','accompaniment','lead','backing']) $('preview-' + stem).disabled = !reference?.hasPreview || (['lead','backing'].includes(stem) && reference?.vocalMode !== 'lead') || previewSelectionChanged() || ['preparing','finishing','restarting'].includes(phase);
    $('library-list').querySelectorAll('button').forEach(button => { button.disabled = maskBusy || ['preparing','finishing','restarting'].includes(phase); if (button.dataset.songId) { if (button.dataset.songId === reference?.cacheId) button.setAttribute('aria-current', 'true'); else button.removeAttribute('aria-current'); } });
    previewAvailability();
    $('score-difficulty').disabled = !!take || ['preparing','finishing','restarting'].includes(phase);
    $('pitch-mode').disabled = !!take; $('score-range').disabled = !!take;
    $('url').disabled = ['preparing', 'finishing', 'restarting'].includes(phase);
    $('clip-seconds').disabled = ['preparing', 'finishing', 'restarting'].includes(phase);
    $('cancel-song').disabled = maskBusy || phase === 'finishing' || (!jobId && phase !== 'preparing' && !reference);
    $('song-key').disabled=!!take||segmented?.busy()||['preparing','finishing','restarting'].includes(phase);
    $('song-key-apply').disabled=!reference||!!take||segmented?.busy()||['preparing','finishing','restarting'].includes(phase);
    $('sing-start').disabled = maskBusy || !reference || (reference.pitchShift&&!keyPlayback.ready()) || ['finishing','restarting'].includes(phase);
    $('sing-guide-mode').disabled = !!wholeGuide || ['preparing','finishing','restarting'].includes(phase);
    $('finish-song').disabled = !take || ['result', 'finishing', 'restarting'].includes(phase);
    $('song-form').querySelector('button').disabled = maskBusy || ['preparing', 'finishing', 'restarting'].includes(phase);
    maskEditor.controls(); recording.referenceChanged(); segmented?.referenceChanged();
    if(segmented?.busy()){
      document.querySelectorAll('#recording-post button,#recording-post input,#recording-post select,#recordings-panel button').forEach(element=>{segmentLocks.set(element,element.disabled);element.disabled=true;});
      for(const id of ['sing-start','finish-song','prepare-song','cancel-song','rebuild-song','preview-build','url','capture-mode','input-device','recording-delete-all','selected-recording-delete','post-remix'])if($(id))$(id).disabled=true;
      $('song-form').querySelector('button').disabled=true;
      $('library-list').querySelectorAll('button').forEach(b=>b.disabled=true);
      for(const stem of ['vocals','accompaniment','lead','backing'])$('preview-'+stem).disabled=true;
    }else{ $('capture-mode').disabled=false;$('input-device').disabled=false;$('recording-delete-all').disabled=false; }
    if($('local-media-controls')?.dataset.importing==='true'){
      for(const id of ['prepare-song','song-key-apply','sing-start','segment-record','segment-open','library-path','library-choose','library-use-path','rebuild-song','preview-build'])if($(id))$(id).disabled=true;
      $('library-list').querySelectorAll('button').forEach(button=>{button.disabled=true;});
    }
    // Read-only UI snapshot; the navigation never controls capture or playback.
    const guideState=JSON.stringify({phase,hasTake:!!take&&phase!=='result',pitchShift:reference?.pitchShift||0,mediaId:loadedVideo,reference:reference?.cacheId||'',
      prepared:!!reference&&reference.videoId===selectedMediaId()&&!previewSelectionChanged()&&Number($('song-key').value)===(reference.pitchShift||0)&&(!reference.pitchShift||keyPlayback.ready()),
      micReady:options.micReady(),segmented:!!segmented?.enabled(),busy:!!segmented?.busy()});
    if($('player-section').dataset.workflow!==guideState)$('player-section').dataset.workflow=guideState;
  }
  window.addEventListener('karaoke-media-import-state',controls);
  async function api(url, init = {}, timeoutMs = 10000) {
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(BASE + url, { ...init, signal: controller.signal, credentials: 'omit', cache: 'no-store', headers: { ...(token ? { 'X-Karaoke-Token': token } : {}), ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...init.headers } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '本機工具連線失敗。');
      return data;
    } finally { clearTimeout(timeout); }
  }
  async function removeJob(id) {
    if (!id || !token) return true;
    try { await api(`/jobs/${id}`, { method: 'DELETE' }); return true; } catch { return false; }
  }
  function beatReset() {
    $('beat-toggle').disabled = false; $('bpm').disabled = false;
    $('beat-note').textContent = '手動節拍燈，沒有歌曲基準時不代表實際歌曲拍點。';
    [...$('beats').children].forEach(dot => dot.classList.remove('active'));
  }
  async function clear(text = '已取消／卸載本次工作；已保存的歌曲仍在本機歌曲庫。', finishing = false) {
    generation++; restartToken++; clearTimeout(timer); stopPreview(); stopGuide(); keyPlayback.clear();
    const recordingEnd = segmented?.enabled() ? segmented.stop() : recording.stop();
    const id = jobId; jobId = null; reference = null; updateMaskView(); maskEditor.render();
    options.player()?.pauseVideo?.(); $('prepare-progress-panel').hidden = true;
    take?.clear(); take = null; $('take-difficulty').textContent = '尚未開始演唱；每輪開始後固定難度。'; rangeComplete = false; phase = finishing ? 'finishing' : 'idle';
    beatReset(); $('live-feedback').textContent = '等待歌曲基準'; $('target-note').textContent = '—'; $('prepare-status').textContent = text;
    message('準備歌曲並開啟麥克風後，按播放就開始評分。'); controls();
    await recordingEnd;
    if (!await removeJob(id)) $('prepare-status').textContent = text + ' 本機工具未回覆清除結果；閒置工作會於約 15 分鐘後自動清理。';
  }
  async function ensureSession() {
    const response = await fetch(BASE + '/session', { credentials: 'omit', signal: AbortSignal.timeout(10000) });
    if (!response.ok) throw new Error('請先啟動本機工具。');
    const data = await response.json();
    if (!data.token || !data.features?.includes('separation-progress')) throw new Error('本機工具需要更新，請重新下載工具包，停止舊工具後再執行 start-local.ps1。');
    token = data.token; masksSupported = data.features?.includes('score-masks') === true;
    renderLocation(await api('/library/location'));
    return data;
  }
  function renderLocation(value) {
    libraryLocation = value;
    $('library-cancel-pick').hidden = !value.selectionPending;
    if (document.activeElement !== $('library-path')) $('library-path').value = value.path || value.suggestedPath || '';
    $('library-location-status').textContent = value.configured ? `歌曲庫位置：${value.path}。已記住這台電腦的設定。` : value.existingLibrary ? '找到原有歌曲庫。請按「使用此位置」保留現有位置，或另外選擇。' : '第一次使用請先選擇或指定歌曲庫資料夾，再準備歌曲。';
    if (value.selectionPending) $('library-location-status').textContent = '資料夾選擇仍在等待。可完成 Windows 選擇視窗，或按「取消資料夾選擇」。';
    controls();
  }
  async function chooseLocation(picker) {
    if (locationBusy || reference || ['preparing','finishing','restarting'].includes(phase)) return;
    const entered = $('library-path').value;
    locationBusy = true; controls();
    try {
      await ensureSession();
      $('library-location-status').textContent = picker ? '請在這台電腦開啟的視窗中選擇資料夾…' : '正在保存歌曲庫位置…';
      if (picker) $('library-cancel-pick').hidden = false;
      const value = await api(picker ? '/library/location/pick' : '/library/location', { method: 'POST', body: JSON.stringify(picker ? {} : { path: entered }) }, picker ? 70000 : 10000);
      renderLocation(value);
      if (value.cancelled) $('library-location-status').textContent = '已取消選擇，歌曲庫位置未變更。';
      if (value.configured) await refreshLibrary();
    } catch (error) { $('library-location-status').textContent = '無法設定歌曲庫：' + error.message; }
    finally { locationBusy = false; controls(); }
  }
  $('library-cancel-pick').addEventListener('click', async () => {
    $('library-cancel-pick').disabled = true;
    try {
      if (!token) await ensureSession();
      await api('/library/location/cancel', { method: 'POST', body: '{}' });
      $('library-cancel-pick').hidden = true;
      $('library-location-status').textContent = '已取消資料夾選擇；原歌曲庫與歌曲都保留，可重新選擇。';
    } catch (error) { $('library-location-status').textContent = error.message; }
    finally { $('library-cancel-pick').disabled = false; }
  });
  $('library-choose').addEventListener('click', () => chooseLocation(true));
  $('library-use-path').addEventListener('click', () => chooseLocation(false));
  for(const id of [...Object.keys(preparationDefaults),'keep-preview'])$(id).addEventListener('change',controls);
  $('preparation-reset').addEventListener('click',()=>{for(const [id,value]of Object.entries(preparationDefaults))$(id).value=value;$('keep-preview').checked=true;stopPreview();controls();$('prepare-status').textContent='已還原分離預設；按「準備歌曲基準」才會套用，已保存版本保留。';});
  $('pitch-method').addEventListener('change', () => {
    if (reference && $('pitch-method').value !== reference.pitchMethod) $('prepare-status').textContent = '音高擷取方式已變更，尚未套用。請按「準備歌曲基準」。有保存相同分離版本的音軌時會直接重用，不需重新分離。';
  });
  $('vocal-mode').addEventListener('change', () => {
    stopPreview(); controls();
    if (reference && $('vocal-mode').value !== reference.vocalMode) $('prepare-status').textContent = '分離模式已變更，尚未套用。請按「準備歌曲基準」載入或建立所選模式；目前仍是' + (reference.vocalMode === 'lead' ? '主唱／和音模式。' : '一般人聲模式。');
  });
  $('separation-model').addEventListener('change', () => {
    stopPreview(); controls();
    if (reference && $('separation-model').value !== reference.separationModel) $('prepare-status').textContent = `分離模型已變更，尚未套用。請按「準備歌曲基準」載入或建立所選模型；目前仍是 ${modelName(reference.separationModel)}。`;
  });
  $('separation-method').addEventListener('change', () => {
    stopPreview(); controls();
    if (reference && $('separation-method').value !== reference.separationMethod) $('prepare-status').textContent = '處理流程已變更，尚未套用。請按「準備歌曲基準」建立或載入所選流程；兩種流程分開保存，遮罩共用。';
  });
  function previewSelectionChanged() {
    return !!reference && ($('separation-model').value !== reference.separationModel || $('vocal-mode').value !== reference.vocalMode || $('separation-method').value !== reference.separationMethod);
  }
  function previewAvailability() {
    $('preview-source').textContent = reference ? `目前已載入：${reference.title} · ${modelName(reference.separationModel)} · ${methodName(reference.separationMethod)} · ${reference.vocalMode === 'lead' ? '主唱／和音模式' : '一般人聲模式'}` : '尚未載入試聽版本。';
    $('lead-preview-buttons').hidden = reference?.vocalMode !== 'lead';
    const busy = ['preparing','finishing','restarting'].includes(phase);
    $('preview-build').hidden = !reference || !!reference.hasPreview;
    $('preview-build').disabled = busy || !!take || previewSelectionChanged();
    if (phase === 'preparing') $('preview-status').textContent = '正在準備歌曲，完成後才可試聽。';
    else if (!reference) $('preview-status').textContent = '請先載入歌曲，才能查看試聽音軌。';
    else if (previewSelectionChanged()) $('preview-status').textContent = '所選分離模型／模式／流程尚未套用，試聽已暫停。請按「準備歌曲基準」並等到已就緒，或從歌單載入對應版本。';
    else if (!reference.hasPreview) $('preview-status').textContent = '這首歌只有評分基準，未保留人聲／伴奏音檔。' + (take ? '請先結束並結算，再補建試聽音軌。' : '可按「補建試聽音軌」重新分離一次並保存在本機；之後可直接試聽。');
    else if (!previewUrl && !previewRequest) $('preview-status').textContent = (reference.vocalMode === 'lead' ? '人聲、伴奏、主唱與和音音軌已就緒，請選擇試聽。' : '人聲與伴奏音軌已就緒，請選擇試聽。');
  }
  $('rebuild-song').addEventListener('click', () => {
    if (!reference || take || ['preparing','finishing','restarting'].includes(phase)) return;
    selectMediaSource(reference.videoId);
    $('clip-seconds').value = String(reference.rangeSeconds);
    $('song-key').value=String(reference.pitchShift || 0);
    $('vocal-mode').value=reference.vocalMode||'all';$('separation-model').value=reference.separationModel||'demucs';$('pitch-method').value=reference.pitchMethod||'yin';$('separation-method').value=reference.separationMethod||'single';
    prepareSong(true, true);
  });
  $('preview-build').addEventListener('click', () => {
    if (!reference || reference.hasPreview || take || ['preparing','finishing','restarting'].includes(phase)) return;
    selectMediaSource(reference.videoId);
    $('clip-seconds').value = String(reference.rangeSeconds);
    $('vocal-mode').value = reference.vocalMode || 'all';
    $('song-key').value=String(reference.pitchShift || 0);
    $('separation-model').value = reference.separationModel || 'demucs';
    $('pitch-method').value = reference.pitchMethod || 'yin';
    $('separation-method').value = reference.separationMethod || 'single';
    $('keep-preview').checked = true;
    prepareSong(false, true);
  });
  function stopPreview() {
    previewSerial++; previewRequest?.abort(); previewRequest = null;
    const audio = $('stem-audio'); audio.hidden = true; audio.pause(); audio.removeAttribute('src'); audio.load();
    if (previewUrl) URL.revokeObjectURL(previewUrl); previewUrl = null;
    previewAvailability();
  }
  async function playPreview(stem) {
    if (!reference?.hasPreview || !reference.cacheId || previewSelectionChanged()) return;
    const id = reference.cacheId;
    stopPreview(); const serial = previewSerial;
    options.player()?.pauseVideo?.(); options.cancelCalibration?.();
    const controller = new AbortController(); previewRequest = controller;
    const timeout = setTimeout(() => controller.abort(), 30000);
    $('preview-status').textContent = '正在從本機載入音軌…';
    try {
      const response = await fetch(`${BASE}/library/${id}/${stem}`, { headers: { 'X-Karaoke-Token': token }, credentials: 'omit', cache: 'no-store', signal: controller.signal });
      if (!response.ok) throw new Error('音軌不存在或已刪除，請勾選保留試聽後重新準備。');
      const blob = await response.blob(); if (serial !== previewSerial) return;
      previewUrl = URL.createObjectURL(blob); $('stem-audio').src = previewUrl; $('stem-audio').hidden = false;
      $('preview-status').textContent = ({vocals:'全部人聲',accompaniment:'伴奏',lead:'主唱',backing:'和音'}[stem]) + '試聽 · ' + modelName(reference.separationModel) + ' · ' + methodName(reference.separationMethod) + ' · 本機音檔';
      await $('stem-audio').play();
    } catch (error) {
      if (serial === previewSerial) $('preview-status').textContent = error.name === 'NotAllowedError' ? '音軌已載入，請點音訊播放器的播放鍵。' : error.message;
    } finally { clearTimeout(timeout); }
  }
  $('stem-audio').addEventListener('play', () => { options.player()?.pauseVideo?.(); options.cancelCalibration?.(); });
  for (const stem of ['vocals','accompaniment','lead','backing']) $('preview-' + stem).addEventListener('click', () => playPreview(stem));
  async function refreshLibrary() {
    $('library-refresh').disabled = true;
    try {
      await ensureSession();
      if (!libraryLocation.configured) { $('library-list').replaceChildren(); librarySearch.update([]); $('library-status').textContent = '請先指定歌曲庫資料夾。'; return; }
      const [{songs}]=await Promise.all([api('/library'),recording.store.list().then(recordingInventoryChanged)]);
      if (!Array.isArray(songs)) throw new Error('本機工具回應不相容，請重新啟動。');
      const list = $('library-list'), searchRows=[]; list.replaceChildren();
      const keyVideos=new Set(songs.filter(song=>song.pitchShift).map(song=>song.videoId)),groups=new Map();
      for (const song of songs) {
        const li = document.createElement('li'), title = document.createElement('strong'), detail = document.createElement('small');
        title.dataset.i18nUser=''; title.textContent = song.title;
        detail.textContent = `${keyLabel(song.pitchShift || 0)} · ${modelName(song.separationModel)} · ${methodName(song.separationMethod)} · ${(song.pitchMethod || 'yin').toUpperCase()} 音高 · ${song.seconds ? '前 ' + song.seconds + ' 秒' : '完整歌曲'} · ${song.vocalMode === 'lead' ? '主唱模式' : '一般人聲'} · ${(song.bytes / 1024 / 1024).toFixed(2)} MB · ${song.hasPreview ? (song.vocalMode === 'lead' ? '含主唱／和音等 4 軌試聽' : '含人聲／伴奏試聽') : '只有旋律基準'}`;
        const load = document.createElement('button'), remove = document.createElement('button');
        load.type = remove.type = 'button'; load.className = 'song-choice'; remove.className = 'secondary song-delete'; remove.textContent = '刪除';
        load.dataset.songId = song.id; load.setAttribute('aria-label', '載入 ' + song.title); load.append(title, detail);
        load.dataset.reviewKey=recordingReviewKey({cacheId:song.id,videoId:song.videoId,pitchShift:song.pitchShift??0});
        if (reference?.cacheId === song.id) load.setAttribute('aria-current', 'true');
        load.addEventListener('click', () => {
          if (['preparing','finishing','restarting'].includes(phase)) return;
          window.dispatchEvent(new CustomEvent('karaoke-library-selected',{detail:{cacheId:song.id,videoId:song.videoId,vocalMode:song.vocalMode}}));
          if (reference?.cacheId === song.id) {
            $('song-key').value=String(reference.pitchShift || 0);
            $('separation-model').value = reference.separationModel;
            $('vocal-mode').value = reference.vocalMode;
            $('pitch-method').value = reference.pitchMethod;
            $('separation-method').value = reference.separationMethod;
            controls(); $('prepare-status').textContent = `已就緒：${reference.title} · ${modelName(reference.separationModel)} · ${methodName(reference.separationMethod)} · ${reference.pitchMethod.toUpperCase()} 音高。`;
            message('這首歌已載入，可直接試聽或按「從頭開始唱」。'); return;
          }
          selectMediaSource(song.videoId);
          $('separation-model').value = song.separationModel || 'demucs';
          $('pitch-method').value = song.pitchMethod || 'yin';
          $('separation-method').value = song.separationMethod || 'single';
          $('song-key').value=String(song.pitchShift || 0);
          $('clip-seconds').value = String(song.seconds); $('vocal-mode').value = song.vocalMode || 'all';
          prepareSong(false, true);
        });
        remove.addEventListener('click', async () => {
          if (['preparing','finishing','restarting'].includes(phase)) return;
          remove.disabled = load.disabled = true;
          try {
            if (reference?.cacheId === song.id) { options.player()?.pauseVideo?.(); await clear('已卸載這首歌，正在刪除本機檔案…'); }
            await api('/library/' + song.id, { method: 'DELETE' });
            await refreshLibrary(); $('library-status').textContent = '已刪除：' + song.title + '（基準與試聽音軌）。';
          } catch (error) { $('library-status').textContent = '刪除失敗：' + error.message; remove.disabled = load.disabled = false; }
        });
        li.append(load, remove);
        searchRows.push({row:li,song});
        if(keyVideos.has(song.videoId)){
          if(!groups.has(song.videoId)){const group=document.createElement('li'),fold=document.createElement('details'),heading=document.createElement('summary'),versions=document.createElement('ul');group.className='song-key-group';fold.open=true;heading.dataset.i18nUser='';heading.textContent=song.baseTitle || song.title;versions.className='library-list key-versions';fold.append(heading,versions);group.append(fold);list.append(group);groups.set(song.videoId,versions);}
          groups.get(song.videoId).append(li);
        }else list.append(li);
      }
      updateLibraryRecordingBadges(list,libraryCounts);
      librarySearch.update(searchRows);
      $('library-status').textContent = `這台電腦已保存 ${songs.length} 個歌曲基準。金色標記表示有整首待確認或分段錄音。`; controls();
    } catch (error) { $('library-status').textContent = '無法讀取歌曲庫：' + error.message; }
    finally { $('library-refresh').disabled = false; }
  }
  $('library-refresh').addEventListener('click', refreshLibrary);
  window.addEventListener('local-tools-ready', refreshLibrary);
  function historyRows() {
    try {
      const values = JSON.parse(localStorage.getItem(HISTORY) || '[]');
      return Array.isArray(values) ? values.slice(-100).map(x => savedResult(x.title, x.score)) : [];
    } catch { return []; }
  }
  let renderedHistory = [];
  function historySelection() {
    const checks = [...$('score-history').querySelectorAll('input[type=checkbox]')], count = checks.filter(x=>x.checked).length;
    $('delete-history-selected').disabled = count === 0;
    $('history-select-all').disabled = checks.length === 0;
    $('clear-history').disabled = checks.length === 0;
    $('history-select-all').checked = checks.length > 0 && count === checks.length;
    $('history-select-all').indeterminate = count > 0 && count < checks.length;
  }
  function renderHistory() {
    const list = $('score-history'); list.replaceChildren();
    renderedHistory = historyRows();
    if (!renderedHistory.length) { const li = document.createElement('li'); li.textContent = '還沒有演唱紀錄。'; list.append(li); }
    renderedHistory.map((row,index)=>({...row,index})).reverse().forEach(row => {
      const li = document.createElement('li'), label = document.createElement('label'), check = document.createElement('input'), title = document.createElement('span'), score = document.createElement('b');
      label.className = 'check-option'; check.type = 'checkbox'; check.value = row.index; check.setAttribute('aria-label', `選取 ${row.title} ${row.score} 分`);
      check.addEventListener('change',historySelection); title.dataset.i18nUser=''; title.textContent = row.title; score.textContent = `${row.score} 分`;
      label.append(check,title); li.append(label,score); list.append(li);
    });
    historySelection();
  }
  $('history-select-all').addEventListener('change',()=>{ $('score-history').querySelectorAll('input[type=checkbox]').forEach(check=>{check.checked=$('history-select-all').checked;}); historySelection(); });
  $('delete-history-selected').addEventListener('click',()=>{
    try {
      if (JSON.stringify(historyRows()) !== JSON.stringify(renderedHistory)) { renderHistory(); $('history-status').textContent = '紀錄已在另一個分頁變更，請重新勾選。'; return; }
      const selected = new Set([...$('score-history').querySelectorAll('input:checked')].map(x=>Number(x.value)));
      localStorage.setItem(HISTORY,JSON.stringify(renderedHistory.filter((row,index)=>!selected.has(index))));
      renderHistory(); $('history-status').textContent = `已清除 ${selected.size} 筆分數紀錄；演唱錄音與歌曲仍保留。`;
    } catch { $('history-status').textContent = '無法清除瀏覽器紀錄。'; }
  });
  window.addEventListener('storage',event=>{if(event.key===HISTORY || event.key===null)renderHistory();});
  async function finish() {
    if (!take || !reference || ['result', 'finishing'].includes(phase)) return;
    restartToken++; stopGuide(); phase = 'finishing'; controls();
    if (options.micReady() && options.player()?.getPlayerState?.() === 1) take.advance(options.player().getCurrentTime());
    const result = take.result(), title = reference.title;
    $('take-difficulty').textContent = `本輪已結算 · 評分難度：${take.profile.label}`;
    $('total-score').textContent = result.score === null ? '—' : String(result.score);
    $('pitch-score').textContent = String(result.pitch); $('rhythm-score').textContent = String(result.rhythm); $('coverage-score').textContent = String(result.coverage);
    $('result-title').replaceChildren(userText(title));
    let saved = true;
    if (result.score !== null) { try { localStorage.setItem(HISTORY, JSON.stringify([...historyRows(), savedResult(title, result.score)].slice(-100))); } catch { saved = false; } }
    options.player()?.pauseVideo?.();
    await options.stopMic();
    take.clear(); take = null; rangeComplete = false;
    $('live-feedback').textContent = '本輪已結束，歌曲已保留'; $('target-note').textContent = '—';
    $('prepare-status').textContent = `已就緒：${reference.title} · 基準已保留，直接按「從頭開始唱」即可再唱。`;
    phase = 'result'; $('mic-start').disabled = false;
    message(result.score === null ? '這段沒有可評分的原唱人聲（休息或已遮罩），未保存分數。歌曲已保留，可直接重新開始。' : saved ? '已結算，分數紀錄已保存；錄音結果請看錄音狀態。歌曲已保留，可直接按「從頭開始唱」。' : '已結算，但瀏覽器不允許儲存紀錄；分數仍顯示在這裡。');
    renderHistory(); controls();
  }
  function renderPreparation(state) {
    const panel = $('prepare-progress-panel'), bar = $('prepare-progress');
    panel.hidden = false;
    $('prepare-device').textContent = state.cached ? '本機快取' : state.device === 'cuda' ? `GPU · ${state.deviceName || 'NVIDIA CUDA'}` : state.device === 'cpu' ? (state.fallback ? 'CPU · GPU 失敗後重試' : 'CPU · 本機處理') : '本機處理';
    const steps = ['download', 'separating', 'accompaniment_separating', 'subtracting', 'lead_separating', 'reference', 'ready'];
    for (const id of ['residual-step','subtract-step']) $(id).hidden = (state.separationMethod || $('separation-method').value) !== 'residual';
    $('lead-step').hidden = (state.vocalMode || $('vocal-mode').value) !== 'lead';
    const stage = state.ready ? 'ready' : ['validated','residual_preparing'].includes(state.stage) ? 'download' : state.stage === 'stem_validated' ? (state.progressStage || 'separating') : state.stage;
    const index = steps.indexOf(stage);
    [...$('prepare-steps').children].forEach((item, i) => { item.classList.toggle('done', i < index); item.classList.toggle('active', i === index); });
    if (state.ready) { bar.value = 100; $('prepare-progress-label').textContent = state.cached ? '已從歌曲庫載入' : '歌曲準備完成'; }
    else if (state.stage === 'stem_validated') { bar.removeAttribute('value'); $('prepare-progress-label').textContent = '分離音軌驗證中；還需建立基準及保存，尚未就緒。'; }
    else if (['separating','accompaniment_separating','lead_separating'].includes(stage) && Number.isFinite(state.progress)) {
      const subject = stage === 'lead_separating' ? '主唱／和音' : stage === 'accompaniment_separating' ? '第二輪伴奏' : '人聲／伴奏';
      if (state.progress >= 100) { bar.removeAttribute('value'); $('prepare-progress-label').textContent = `${subject}推論 100%；正在完成音軌，尚未就緒。`; }
      else { bar.value = state.progress; $('prepare-progress-label').textContent = `${subject}分離 ${Math.round(state.progress)}%（本階段）`; }
    }
    else if (stage === 'reference' && Number.isFinite(state.progress)) { bar.value = state.progress; $('prepare-progress-label').textContent = `${state.message} ${Math.round(state.progress)}%（尚需驗證及保存）`; }
    else { bar.removeAttribute('value'); $('prepare-progress-label').textContent = state.message || '正在準備…'; }
  }
  async function poll(id, current) {
    if (current !== generation || jobId !== id) return;
    try {
      const state = await api(`/jobs/${id}`);
      if (current !== generation) return;
      $('prepare-status').textContent = state.message; renderPreparation(state);
      if(requestedKey)$('song-key-status').textContent=state.message || '正在載入變調版本…';
      if (state.stage === 'failed') throw new Error(state.message);
      if (state.ready) {
        const data = await api(`/jobs/${id}/reference`);
        if (current !== generation) return;
        reference = { ...validateReference(data), duration: data.duration, beats: data.beats || [], bpm: data.bpm, cacheId: data.cacheId, pitchShift:data.pitchShift || 0, baseTitle:data.baseTitle || data.title, sourceCacheId:data.sourceCacheId, hasPreview: data.hasPreview, separationModel: data.separationModel || 'demucs', pitchMethod: data.pitchMethod || 'yin', separationMethod: data.separationMethod || 'single', vocalMode: data.vocalMode || 'all', rangeSeconds: data.rangeSeconds ?? Number($('clip-seconds').value) };
        if(reference.pitchShift!==requestedKey)throw Error('本機回傳的 Key 與選定版本不同，請重新載入。');
        if (reference.separationMethod !== requestedMethod || reference.pitchMethod !== requestedPitch || reference.separationModel !== requestedModel || reference.vocalMode !== requestedVocalMode) throw new Error('本機回傳的分離模式與所選模式不符，請更新頁面與本機工具後重試。');
        if (reference.videoId !== loadedVideo) throw new Error('影片已切換，請重新準備歌曲。');
        updateMaskView(); maskEditor.render();
        $('song-key').value=String(reference.pitchShift);
        $('song-key-status').textContent=keyLabel(reference.pitchShift)+' · 已隨歌曲版本保存。';
        await keyPlayback.load(reference);if(current!==generation)return;
        phase = 'ready';
        $('prepare-status').textContent = `已就緒：${reference.title} · ${modelName(reference.separationModel)} · ${methodName(reference.separationMethod)} · ${reference.pitchMethod.toUpperCase()} 音高 · ${reference.vocalMode === 'lead' ? '主唱／和音模式' : '一般人聲模式'} · ${Math.round(reference.duration)} 秒 · ${state.cached ? '直接載入本機基準' : '已保存到本機'}${reference.hasPreview ? '，可試聽分離結果' : '，音檔已清除'}。`;
        $('result-title').replaceChildren(userText(reference.title),document.createTextNode(reference.vocalMode === 'lead' ? ' · 以主唱評分' : ''));
        for (const id of ['total-score','pitch-score','rhythm-score','coverage-score']) $(id).textContent = '—';
        if (reference.beats.length && reference.bpm) {
          options.stopBeats(); $('bpm').value = reference.bpm; $('bpm').disabled = true; $('beat-toggle').disabled = true;
          $('beat-note').textContent = `自動估計約 ${reference.bpm} BPM；播放時顯示拍點，可能出現半速／倍速誤差。`;
        }
        message('基準就緒。開啟麥克風後，按「從頭開始唱」或影片播放按鈕。'); controls();
        if (options.player()?.getPlayerState?.() === 1) playerState(1);
        refreshLibrary().catch(() => {});
        return;
      }
      timer = setTimeout(() => poll(id, current), 1500);
    } catch (error) {
      if (current !== generation) return;
      await clear('準備失敗：' + (error instanceof TypeError ? '無法連線到本機工具。請確認啟動與本機網路權限。' : error.message));
      $('install-guide').open = true;
    }
  }
  async function prepareSong(force = false, preserveVersion = false) {
    if($('local-media-controls')?.dataset.importing==='true'){$('prepare-status').textContent='請等本機 MV 匯入完成，再準備歌曲。';return;}
    const id = selectedMediaId();
    if (maskBusy) return;
    if (!id) { $('prepare-status').textContent = '請先載入 YouTube 影片或選擇本機 MV。'; return; }
    // Normal preparations honor the visible controls; library/rebuild actions
    // supply the saved version and retain audio for preview and backing-only playback.
    if(preserveVersion)$('keep-preview').checked = true;
    requestedKey=keyShift(Number($('song-key').value));
    requestedVocalMode = $('vocal-mode').value; requestedModel = $('separation-model').value; requestedPitch = $('pitch-method').value; requestedMethod = $('separation-method').value;
    const clearing = clear('正在連接本機工具…');
    const current = generation; loadedVideo = id;
    $('song-key-status').textContent='正在準備 '+keyLabel(requestedKey)+'，完成後會保存到歌曲庫…';
    phase = 'preparing'; renderPreparation({ stage: 'starting', message: '正在連接本機工具…' }); controls();
    await clearing;
    if (current !== generation) return;
    try {
      const helper = await ensureSession();
      if(isLocalMediaId(id)&&!helper.features?.includes('local-media'))throw Error('請更新並重新啟動本機工具，才能使用本機 MV。');
      if(requestedKey&&!helper.features?.includes('song-key-versions'))throw Error('請更新並重新啟動本機工具，才能建立 Key 版本。');
      if (requestedMethod !== 'single' && !helper.features?.includes('residual-separation')) throw new Error('本機工具需要更新才能使用伴奏二次分離＋反向相減，請更新並重新啟動工具。');
      if (requestedPitch !== 'yin' && !helper.features?.includes('pitch-methods')) throw new Error('本機工具需要更新才能使用 RMVPE，請更新並重新啟動工具。');
      if (requestedModel === 'mel-roformer' && !helper.features?.includes('mel-roformer')) throw new Error('本機工具需要更新才能使用 Mel-Band RoFormer 人聲模型，請更新工具程式碼並重新啟動。');
      if (requestedModel !== 'demucs' && !helper.features?.includes('separation-models')) throw new Error('本機工具需要更新才能使用 RoFormer 分離模型，請更新工具包並重新啟動；缺少套件時再執行 setup-local.ps1。');
      if (requestedVocalMode === 'lead' && !helper.features?.includes('lead-vocals')) throw new Error('本機工具需要更新才能使用主唱／和音分離，請更新工具包並重新執行 setup-local.ps1。');
      if (force && !helper.features?.includes('rebuild-song')) throw new Error('本機工具需要更新才能重新分離，請更新工具包並重新啟動。');
      if (!libraryLocation.configured) throw new Error('請先指定歌曲庫資料夾，再準備歌曲。');
      if (!await options.loadVideo()) throw new Error('播放器未就緒：' + $('player-status').textContent);
      if (current !== generation) return;
      options.player()?.pauseVideo?.();
      await ensureSession();
      if (current !== generation) return;
      const created = await api('/jobs', { method: 'POST', body: JSON.stringify({ videoId: id, pitchShift:requestedKey, seconds: Number($('clip-seconds').value), preview: $('keep-preview').checked, ...(requestedMethod !== 'single' ? {separationMethod:requestedMethod} : {}), ...(requestedPitch !== 'yin' ? {pitchMethod:requestedPitch} : {}), ...(requestedModel !== 'demucs' ? { separationModel: requestedModel } : {}), ...(requestedVocalMode === 'lead' ? {vocalMode:'lead'} : {}), ...(force ? { force: true } : {}) }) });
      if (current !== generation) { await removeJob(created.id); return; }
      jobId = created.id; controls(); await poll(jobId, current);
    } catch (error) {
      if (current !== generation) return;
      phase = 'idle'; $('prepare-progress-panel').hidden = true; $('prepare-status').textContent = '無法準備歌曲：' + (error instanceof TypeError || error.name === 'TimeoutError' ? '請先啟動本機工具，並允許本機網路存取。' : error.message);
      controls();
    }
  }
  $('song-key').addEventListener('change',()=>{$('song-key-status').textContent=`已選 ${keyLabel(Number($('song-key').value))}，尚未套用。${reference?'目前播放 '+keyLabel(reference.pitchShift)+'；請按「建立／載入此 Key」。':'請按「準備歌曲基準」。'}`;});
  $('song-key-apply').addEventListener('click',()=>{try{keyShift(Number($('song-key').value));if(reference){selectMediaSource(reference.videoId);prepareSong(false,true);}}catch(error){$('song-key-status').textContent=error.message;}});
  $('prepare-song').addEventListener('click', () => prepareSong());
  $('cancel-song').addEventListener('click', () => { options.player()?.pauseVideo?.(); clear(); });
  $('sing-start').addEventListener('click', async () => {
    if (!reference || maskBusy || phase === 'restarting') return;
    if(segmented?.busy()||!segmented?.leave())return;
    stopPreview(); stopGuide(); options.cancelCalibration?.();
    const request = ++restartToken, p = options.player();
    phase = 'restarting'; message(options.micReady() ? '正在同步影片到 0 秒…' : '正在開啟麥克風，請允許瀏覽器的收音授權…'); controls();
    try {
      if (!options.micReady()) await options.startMic();
      if (request !== restartToken || !reference || !options.micReady()) { if (request === restartToken) { phase = take ? 'paused' : 'ready'; message('未開始演唱：麥克風尚未就緒，請查看「收音」區的狀態，再按「從頭開始唱」。'); controls(); } return; }
      await recording.prepare(reference, async stem => {
        const response = await fetch(BASE + `/library/${reference.cacheId}/${stem}`, {headers: {'X-Karaoke-Token':token}, credentials:'omit', cache:'no-store', signal:AbortSignal.timeout(30000)});
        if (!response.ok) throw new Error('無法取得錄音所需的配樂／和音，請補建試聽音軌或改選歌唱者。');
        return response.arrayBuffer();
      }, {allowOctave:$('pitch-mode').value==='octave',rangeMode:$('score-range').value,difficulty:$('score-difficulty').value});
      if (request !== restartToken || !reference || !options.micReady()) { await recording.stop(); return; }
      message('正在準備演唱時帶唱…');
      await prepareGuide(reference, p, $('sing-guide-mode').value, () => request !== restartToken || !reference || !options.micReady());
      if (request !== restartToken || !reference || !options.micReady()) return;
      message('正在同步影片到 0 秒…');
      await seekPlayerToStart(p, () => request !== restartToken || !reference || !options.micReady());
      if (request !== restartToken || !reference || !options.micReady()) return;
      take?.clear(); take = new ScoringTake(reference, { allowOctave: $('pitch-mode').value === 'octave', rangeMode: $('score-range').value, difficulty: $('score-difficulty').value });
      showTakeDifficulty(); take.begin(0); lastProgress = 0; rangeComplete = false; phase = 'paused';
      $('total-score').textContent = '…'; $('pitch-score').textContent = '—'; $('rhythm-score').textContent = '—'; $('coverage-score').textContent = '—';
      message('影片已回到開頭，等待播放開始。'); controls();
      revealPlayerVideo();
      if (wholeGuide) { wholeGuide.armed = true; if (reference.pitchShift || wholeGuide.mode === 'backing') p.mute?.(); else p.unMute?.(); }
      p.playVideo();
      if (p.getPlayerState() === 1) playerState(1);
    } catch (error) {
      if (request !== restartToken) return;
      stopGuide(); await recording.stop(); phase = 'paused'; p?.pauseVideo?.(); message(error.message); controls();
    }
  });
  $('finish-song').addEventListener('click', finish);
  $('clear-history').addEventListener('click', () => { try { localStorage.removeItem(HISTORY); renderHistory(); $('history-status').textContent = '分數紀錄已全部清除；演唱錄音與歌曲仍保留。'; } catch { message('無法清除瀏覽器紀錄。'); } });
  function playerState(state) {
    keyPlayback.sync(state);
    if(segmented?.enabled()){
      if(state===1){stopPreview();options.cancelCalibration?.();}
      segmented.playerState(state);return;
    }
    syncGuide(state, options.player()?.getCurrentTime?.() || 0);
    if (phase !== 'restarting' || state !== 1) recording.playerState(state, options.player()?.getCurrentTime?.() || 0);
    if (state === 1) recording.clearPreview();
    if (maskBusy) return;
    if (state === 1) { stopPreview(); options.cancelCalibration?.(); }
    if (!reference || ['finishing','result','restarting'].includes(phase)) return;
    if (state === 1 && options.micReady() && phase !== 'preparing' && phase !== 'result') {
      if (!take && options.player()?.getCurrentTime?.() >= reference.duration) { message('目前播放位置超出分析範圍，請按「從頭開始唱」。'); controls(); return; }
      if (!take) { take = new ScoringTake(reference, { allowOctave: $('pitch-mode').value === 'octave', rangeMode: $('score-range').value, difficulty: $('score-difficulty').value }); showTakeDifficulty(); take.begin(options.player()?.getCurrentTime?.() || 0); $('total-score').textContent = '…'; }
      take.advance(options.player()?.getCurrentTime?.() || 0); phase = 'singing'; message('演唱中。跳過的段落會計入漏唱，重播不會重複加分。');
    } else if ([2, 3, -1].includes(state) && take) { if (phase === 'singing' && options.micReady()) take.advance(options.player()?.getCurrentTime?.() || 0); phase = 'paused'; message(state === 3 ? '影片緩衝中，評分暫停。' : '播放已暫停，評分同步暫停。'); }
    else if (state === 0 && take && options.micReady()) { take.advance(options.player()?.getCurrentTime?.() || 0); finish(); }
    else if (state === 1 && !options.micReady()) message('影片可以播放，但麥克風尚未開啟。請先開啟收音，再從頭開始唱。');
    controls();
  }
  function sample(time, hz) {
    if(segmented?.enabled())return;
    if (!reference || !take || phase !== 'singing' || options.player()?.getPlayerState?.() !== 1) return;
    recording.sample(time + Number($('offset').value)/1000, hz);
    if (time >= reference.duration) {
      if (!rangeComplete) message('已到本次分析範圍結尾。資料已保留，可停止收音後按「結束並結算」。');
      rangeComplete = true; $('target-note').textContent = '—'; $('live-feedback').textContent = '超出分析範圍，不再計分';
      return;
    }
    if (rangeComplete) message('繼續評分中。停止收音後可按「結束並結算」。');
    rangeComplete = false; take.sample(time, hz);
    const cell = Math.floor(time / reference.step), expected = displayReference.frames[cell];
    const target = noteOf(expected); $('target-note').textContent = target ? `${target.name} · ${expected.toFixed(1)} Hz` : '休息';
    if (excluded[cell]) { $('target-note').textContent = '休息'; $('live-feedback').textContent = '遮罩區間，不計分'; }
    else if (expected && hz) { const cents = Math.round(pitchDifference(hz, expected, take.allowOctave)); $('live-feedback').textContent = Math.abs(cents) <= take.profile.pitchFull ? (take.allowOctave ? '音準吻合（允許八度差）' : '音準吻合') : `${cents > 0 ? '偏高' : '偏低'} ${Math.abs(cents)} cents`; }
    else $('live-feedback').textContent = expected ? '等待歌聲' : '前奏／間奏，不計分';
    if (performance.now() - lastProgress > 500) {
      lastProgress = performance.now(); const result = take.result(false);
      $('pitch-score').textContent = result.pitch; $('coverage-score').textContent = result.coverage;
    }
  }
  const heartbeat = setInterval(() => {
    keyPlayback.sync();
    if(segmented?.enabled())return;
    const p = options.player(); if (!reference || !p?.getCurrentTime) return;
    const t = p.getCurrentTime();
    syncGuide(p.getPlayerState?.(), t);
    if (!take || phase !== 'singing') {
      const cell = Math.floor((t - Number($('offset').value) / 1000) / reference.step);
      const expected = displayReference?.frames[cell], note = noteOf(expected);
      $('target-note').textContent = excluded[cell] ? '休息' : note ? `${note.name} · ${expected.toFixed(1)} Hz` : '休息';
      $('live-feedback').textContent = excluded[cell] ? '遮罩區間，不計分' : expected ? '歌曲基準已就緒' : '前奏／間奏，不計分';
    }
    if (!take && phase === 'ready' && options.micReady() && p.getPlayerState?.() === 1 && t < reference.duration) playerState(1);
    if (take && phase === 'singing' && options.micReady() && p.getPlayerState?.() === 1) take.advance(t);
    if (reference.beats.length) {
      let index = -1;
      for (let i = 0; i < reference.beats.length && reference.beats[i] <= t; i++) index = i;
      [...$('beats').children].forEach((dot, i) => dot.classList.toggle('active', phase === 'singing' && index >= 0 && i === index % 4));
    }
  }, 100);
  // Keep active reference available while the user is setting up or singing.
  const keepalive = setInterval(() => { if (jobId && reference) api(`/jobs/${jobId}`).catch(() => {}); }, 60000);
  window.addEventListener('pagehide', () => {
    generation++; restartToken++; clearTimeout(timer); stopPreview(); stopGuide(); keyPlayback.clear(); clearInterval(heartbeat); clearInterval(keepalive);
    if (jobId && token) fetch(BASE + `/jobs/${jobId}`, { method: 'DELETE', headers: { 'X-Karaoke-Token': token }, keepalive: true, credentials: 'omit' }).catch(() => {});
    reference = null; take?.clear(); take = null;
  });
  renderHistory(); controls();
  return {
    reference: () => displayReference, sample, playerState, stopRecording: error=>{stopGuide();return segmented?.enabled()?segmented.stop(error):recording.stop(error);},
    pauseForCalibration() { if (phase === 'restarting') { stopGuide(); recording.stop(); restartToken++; phase = take ? 'paused' : 'ready'; } options.player()?.pauseVideo?.(); stopPreview(); controls(); },
    async changeSong(id) { if (loadedVideo !== id) { await clear(); loadedVideo = id; controls(); } },
    micStarted() {
      if (reference && options.player()?.getPlayerState?.() === 1) playerState(1);
      controls();
    },
    micStopped({ rewind = false, reason = '收音已停止。' } = {}) {
      stopGuide();
      const interruptedRestart = phase === 'restarting';
      if (interruptedRestart) { restartToken++; phase = take ? 'paused' : 'ready'; message(`未開始演唱：${reason}${take ? ' 上次演唱資料已保留，可先結算。' : ''}`); }
      if (phase === 'singing') { take?.advance(options.player()?.getCurrentTime?.() || 0); phase = 'paused'; options.player()?.pauseVideo?.(); }
      if (take && phase === 'paused' && !interruptedRestart) message('收音已停止，本次演唱資料已保留。可按「結束並結算」，或「從頭開始唱」重新計分。');
      if (rewind && options.player()?.seekTo && !['preparing','finishing','result'].includes(phase)) {
        const request = ++restartToken;
        seekPlayerToStart(options.player(), () => request !== restartToken).then(() => {
          if (request === restartToken && take) message('收音已停止，播放器已回到 0 秒。可結算本次演唱，或按「從頭開始唱」重新計分。');
        }).catch(error => { if (request === restartToken) message(error.message + ' 本次演唱資料仍保留，可先結算。'); });
      }
      controls();
    },
  };
}
