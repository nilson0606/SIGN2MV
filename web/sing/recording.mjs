import {localizedConfirm} from './i18n.mjs';
import {prepareRecordingDiagnostics} from './recording-diagnostics.mjs';
import { recordingTuningSuffix } from './recording-tune.mjs';
import { recordingSofteningSuffix, recordingEffectsSuffix } from './recording-soften.mjs';
import {remixRecording,wavBlob,delaySeconds,recordingDelaySuffix} from './recording-process.mjs';
import { createRecordingPost } from './recording-post.mjs';
import { createRecordingMix, mixSettings } from './recording-mix.mjs';
import { RecordingStore, isPostRecording } from './recording-store.mjs';
import {createRecordingReview} from './recording-review.mjs';
import { createPCMRecorders } from './recording-pcm.mjs';
import { recordingSceneDefaultsVersion } from './recording-scenes.mjs';
const $ = id => document.getElementById(id);
export function createSingerRecorder(options) {
  const store = new RecordingStore({status:text=>{$('recording-storage-status').textContent=text;}});
  try { const saved = localStorage.getItem('karaoke.recording-mode.v1'); if (['voice','mix','off'].includes(saved)) $('recording-mode').value = saved; } catch {}
  let active = null, operation = 0, stopping = Promise.resolve(), previewURL = null;
  try {
    const saved = mixSettings(JSON.parse(localStorage.getItem('karaoke.recording-balance.v1') || '{}'));
    $('recording-manual').checked = saved.manual; $('recording-voice-level').value = saved.voice; $('recording-backing-level').value = saved.backing;
  } catch {}
  function balanceSettings() { return mixSettings({manual:$('recording-manual').checked,voice:Number($('recording-voice-level').value),backing:Number($('recording-backing-level').value)}); }
  function setBalanceSettings(value) {
    if(active)return;
    const settings=mixSettings(value);
    $('recording-manual').checked=settings.manual;$('recording-voice-level').value=settings.voice;$('recording-backing-level').value=settings.backing;
    controls();try{localStorage.setItem('karaoke.recording-balance.v1',JSON.stringify(settings));}catch{}
    window.dispatchEvent(new Event('recording-balance-changed'));
  }
  const post = createRecordingPost({store, stop:()=>stop(), isRecording:()=>!!active, reference:options.reference, pause:()=>{options.pausePlayer();$('recording-audio').pause();}, download, onDelete:async()=>{clearPreview();await render();}});
  const review=createRecordingReview({store,reference:options.reference,isRecording:()=>!!active,loadStem:options.loadStem,onChanged:render,pause:()=>{options.pausePlayer();post.clearAudio();$('recording-audio').pause();}});
  const status = text => { $('recording-status').textContent = text; };
  function controls() {
    review.controls();
    const mode=$('recording-mode').value, manual=$('recording-manual').checked;
    $('recording-mode').disabled = !!active;
    $('recording-delay').disabled=!!active||mode==='off';
    $('recording-manual').disabled = !!active || mode==='off';
    $('recording-voice-level').disabled = !!active || mode==='off' || !manual;
    $('recording-backing-level').disabled = !!active || mode!=='mix' || !manual;
    $('recording-voice-value').textContent = $('recording-voice-level').value+'%';
    $('recording-backing-value').textContent = $('recording-backing-level').value+'%';
    if (!active) $('recording-balance-status').textContent = mode==='off' ? '不保存錄音，音量平衡不啟動。' : `${manual ? '手動＋自動微調' : '自動平衡'} · 只影響錄音，不影響評分；每輪開始前設定。`;
    $('recording-balance-help').textContent = mode==='off' ? '已關閉錄音，音量平衡不啟動。' : manual ? '手動＋自動：音量可調 0–200%，兩路各自最多微調 ±3 dB。0% 保持靜音；每輪開始後固定設定。' : '自動平衡：依歌唱者及配樂／和音音量平滑調整，各自最多修正 ±6 dB。下方手動音量不參與；每輪開始後固定設定。';
  }
  function clearPreview() {
    review.clear();review.controls();
    post.clearAudio();
    const audio = $('recording-audio'); audio.pause(); audio.removeAttribute('src'); audio.load(); audio.hidden = true;
    if (previewURL) URL.revokeObjectURL(previewURL); previewURL = null;
  }
  async function render(savedId = null) {
    const all=await store.list(),rows=all.filter(isPostRecording), list = $('recording-list'); list.replaceChildren(); review.refresh(all,savedId);post.refresh(rows);
    options.onInventoryChanged?.(all);
    if(savedId && rows.some(row=>row.id===savedId&&row.complete)){
      post.select(savedId,{scroll:false});
      $('post-status').textContent='已選取最新錄音，可試聽、下載或後處理。';
    }
    if (!rows.length) { const li = document.createElement('li'); li.textContent = '尚無演唱錄音。'; list.append(li); }
    for (const row of rows) {
      const li = document.createElement('li'), label = document.createElement('strong'), info = document.createElement('small'), buttons = document.createElement('div');
      label.dataset.i18nUser=''; label.textContent = row.title + recordingEffectsSuffix(row)+recordingSofteningSuffix(row)+recordingTuningSuffix(row) + (recordingDelaySuffix(row) ? ' '+recordingDelaySuffix(row) : '');
      info.textContent = `${new Date(row.created).toLocaleString()} · ${row.mode === 'mix' ? (row.stems?.includes('backing') ? '歌唱者＋配樂／和音' : '歌唱者＋配樂（無獨立和音）') : '歌唱者'}${row.balance ? (row.balance.manual ? ' · 手動＋自動' : ' · 自動平衡') : ''} · ${row._archiveRoot?'歌曲庫錄音目錄':'瀏覽器待搬存'} · ${Math.round(row.seconds)} 秒${Number.isFinite(row.appliedDelayMs)?' · 歌聲校正 '+row.appliedDelayMs+' ms':''}${row.complete ? '' : ' · 未正常結束，保留已儲存片段'}`;
      buttons.className = 'button-row';
      for (const [text, action] of [
        ['試聽', async () => { await stop(); options.pausePlayer(); clearPreview(); previewURL = URL.createObjectURL(await store.blob(row)); $('recording-audio').src = previewURL; $('recording-audio').hidden = false; await $('recording-audio').play(); }],
        ['後處理', async () => { await stop(); post.select(row.id); }],
        ['下載', async () => download(await store.blob(row), row)],
        ['刪除', async () => { if(!localizedConfirm('刪除這筆錄音、原始歌聲及其後處理資料？此操作無法復原。'))return; clearPreview();post.clearAudio(); await store.delete(row.id); await render(); }],
      ]) {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'secondary'; button.textContent = text;
        button.addEventListener('click', async () => { button.disabled = true; try { await action(); } catch (error) { status(error.message); } finally { button.disabled = false; } }); buttons.append(button);
      }
      li.append(label, info, buttons); list.append(li);
    }
  }
  function download(blob, meta) {
    const url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href = url; link.download = `${meta.title.replace(/[\\/:*?"<>|]/g,'_').slice(0,80)}-${new Date(meta.created).toISOString().replace(/[:.]/g,'-')}${recordingEffectsSuffix(meta)}${recordingSofteningSuffix(meta)}${recordingTuningSuffix(meta)}${recordingDelaySuffix(meta)}.${meta.mime.includes('wav') ? 'wav' : meta.mime.includes('mp4') ? 'm4a' : 'webm'}`;
    link.click(); setTimeout(() => URL.revokeObjectURL(url), 60000);
  }
  function stopBacking(a) {
    for (const node of a.backing) { try { node.stop(); } catch {} node.disconnect(); }
    a.backing = [];
  }
  function syncBacking(a, time) {
    if (!a.buffers.length || a.recorder.state !== 'recording') return;
    if (!Number.isFinite(time) || time < 0 || a.buffers.every(buffer => time >= buffer.duration)) { stopBacking(a); return; }
    const expected = a.anchorTime + a.context.currentTime - a.anchorContext;
    if (a.backing.length && Math.abs(expected - time) < .15) return;
    stopBacking(a);
    const when = a.context.currentTime;
    // Start accompaniment and harmony on the same audio clock; both follow seeks/pauses.
    for (const buffer of a.buffers) {
      if (time >= buffer.duration) continue;
      const node = a.context.createBufferSource(); node.buffer = buffer; node.connect(a.mix.input); node.start(when,time);
      a.backing.push(node);
    }
    a.anchorTime = time; a.anchorContext = when;
  }
  async function prepare(reference, loadStem, scoring = {}, capture = {}) {
    await stop(); clearPreview();
    const mode = capture.mode ?? $('recording-mode').value;
    if (mode === 'off') { status('本輪不保存錄音。'); return; }
    const recordingDelayMs=capture.delayMs ?? Number($('recording-delay').value);delaySeconds(recordingDelayMs);
    const request = ++operation;
    if (!window.AudioWorkletNode) throw new Error('瀏覽器不支援同步錄音，請使用桌機 Chrome／Edge，或選不保存錄音。');
    status(mode === 'mix' ? '正在準備錄音配樂／和音…' : '正在準備演唱錄音…');
    const context = options.context(), stream = options.stream();
    if (!context || !stream) throw new Error('麥克風尚未就緒，無法開始錄音。');
    await store.open();
    const stems = [], buffers = [];
    if (mode === 'mix') {
      if (!reference.hasPreview) throw new Error('混音錄音需要已保存的分離音軌；請先補建試聽音軌，或改選歌唱者。');
      // hasPreview is verified by the local library against every required file.
      // Never substitute vocals/lead: that would put the original singer back in.
      stems.push('accompaniment');
      if (reference.vocalMode === 'lead') stems.push('backing');
      for (const stem of stems) {
        buffers.push(await context.decodeAudioData(await loadStem(stem)));
        if (request !== operation || options.context() !== context) throw new Error('錄音準備已取消。');
      }
      if (buffers.some(buffer => Math.abs(buffer.duration - buffers[0].duration) > .15)) throw new Error('配樂與和音長度不一致，請補建音軌後再錄音。');
    }
    if (request !== operation || options.context() !== context) throw new Error('錄音準備已取消。');
    const destination = context.createGain(), direct = options.inputSource?.(), mic = direct || context.createMediaStreamSource(stream);
    // This separate recording branch never changes the input used for pitch scoring.
    const mix = createRecordingMix(context,mic,destination,{mode,settings:balanceSettings(),voiced:()=>options.voiced?.() === true});
    let recorder, rawRecorder;
    try { ({recorder,rawRecorder}=await createPCMRecorders(context,mic,destination)); }
    catch (error) { mix.disconnect(); destination.disconnect(); throw error; }
    if(request!==operation||options.context()!==context){recorder.dispose();mix.disconnect();destination.disconnect();throw new Error('錄音準備已取消。');}
    const meta = { id: crypto.randomUUID(), title: reference.title, videoId: reference.videoId, mode, mime: recorder.mimeType, rawMime:rawRecorder.mimeType, appliedDelayMs:0, recordingDelayMs, created: Date.now(), seconds: 0, bytes: 0, complete: false, balance: mix.settings, stems, rawBytes:0, post:{version:1, reference:structuredClone(reference), scoring, offsetMs:recordingDelayMs, liveOffsetMs:Number($('offset').value), segments:[], samples:[]} };
    // Only new recordings opt into the new editing defaults; saved audio stays dry.
    meta.postDefaults=recordingSceneDefaultsVersion;
    if(capture.segmentTake)meta.segmentTake=structuredClone(capture.segmentTake);else meta.postPending=true;
    meta.captureClock={version:1,source:'audio-worklet-pcm',sampleRate:context.sampleRate,input:direct?'native-worklet-v2':'browser-media-stream'};
    if(direct?.nativeCapturePolicy)meta.captureClock.nativeCapturePolicy=direct.nativeCapturePolicy;
    if(direct?.nativeCaptureId)meta.captureClock.nativeCaptureId=direct.nativeCaptureId;
    let diagnostics;
    try{diagnostics=await prepareRecordingDiagnostics({context,mic,stream,recorder,meta,native:!!direct});}
    catch(error){recorder.dispose();mix.disconnect();destination.disconnect();throw error;}
    if(request!==operation||options.context()!==context){await diagnostics?.finish();recorder.dispose();mix.disconnect();destination.disconnect();throw new Error('錄音準備已取消。');}
    const a = { diagnostics, recorder, rawRecorder, rawCount:0, segment:null, context, mic, mix, destination, buffers, meta, chunks: [], queue: Promise.resolve(), count: 0, backing: [], error: null };
    active = a; controls();
    rawRecorder.ondataavailable = event => {
      if (!event.data.size) return;
      meta.rawBytes += event.data.size;
      const index=a.rawCount++, snapshot=structuredClone(meta),header=recorder.voiceHeader();
      a.queue=a.queue.then(async()=>{await store.save(snapshot,event.data,index,'voice');if(index>0)await store.save(snapshot,header,0,'voice');}).catch(error=>{a.storageFailed=true;a.error=error;status('乾淨歌聲保存失敗：'+error.message);});
    };
    rawRecorder.onerror = event => { a.error ||= event.error || new Error('乾淨歌聲錄音中斷'); stop(); };
    recorder.ondataavailable = event => {
      if (!event.data.size) return;
      a.chunks.push(event.data);meta.bytes+=event.data.size;meta.seconds=recorder.frames/context.sampleRate;
      const index=a.count++,snapshot=structuredClone(meta),header=recorder.header();a.chunks[0]=header;
      a.queue=a.queue.then(async()=>{await store.save(snapshot,event.data,index);if(index>0)await store.save(snapshot,header,0);}).catch(error=>{a.storageFailed=true;a.error=error;status('自動保存失敗，停止後請下載備份：'+error.message);});
    };
    recorder.onerror = event => { a.error ||= event.error || new Error('錄音中斷'); stop(); };
    status(`錄音已就緒${mode === 'mix' ? (stems.includes('backing') ? ' · 已載入伴奏＋和音' : ' · 已載入伴奏（此版本無獨立和音）') : ''}，影片開始播放時同步錄製。`);
  }
  function closeSegment(a) {
    if (a.segment) { a.segment.duration=Math.max(0,elapsed(a)-a.segment.offset); a.segment=null; }
  }
  function syncTimeline(a,time) {
    const offset=elapsed(a);
    if (a.segment && Math.abs(a.segment.songTime+offset-a.segment.offset-time)<.15) return;
    closeSegment(a); a.segment={offset,songTime:time,duration:0}; a.meta.post.segments.push(a.segment);
  }
  function sample(time,hz) {
    const a=active; if(!a || a.recorder.state!=='recording')return;
    a.meta.post.samples.push({time,hz,offset:elapsed(a)});
  }
  function elapsed(a) { return a.recorder.clock.frames(a.context.currentTime)/a.context.sampleRate; }
  function playerState(state, time) {
    if(state===1){review.clear();review.controls();}
    const a = active; if (!a) return;
    if (state === 1) {
      a.diagnostics?.start();
      if (a.recorder.state === 'inactive') { a.recorder.start(1000); a.rawRecorder.start(1000); }
      else if (a.recorder.state === 'paused') { a.recorder.resume(); a.rawRecorder.resume(); }
      syncTimeline(a,time); syncBacking(a,time); status(`● 錄音中 · ${a.meta.mode === 'mix' ? (a.meta.stems.includes('backing') ? '歌唱者＋配樂／和音' : '歌唱者＋配樂（無獨立和音）') : '歌唱者'}（錄製中暫存，停止後存入歌曲庫）`);
    } else if (state === 0) { stop(); }
    else {
      a.diagnostics?.pause();
      if (a.recorder.state === 'recording') { a.recorder.pause(); a.rawRecorder.pause(); }
      closeSegment(a);
      stopBacking(a); status(a.recorder.state === 'inactive' ? '錄音已就緒，等待影片播放。' : '錄音暫停，會隨影片續播。');
    }
  }
  function stop(captureError = null) {
    operation++;
    const a = active; if (!a) return stopping;
    if(captureError instanceof Error){a.error=captureError;a.meta.captureError=captureError.message;}
    a.diagnostics?.pause();
    if(a.recorder.state==='recording')a.recorder.pause();
    closeSegment(a); active = null; stopBacking(a); controls();
    const wasStarted = a.recorder.state !== 'inactive' || a.count > 0;
    const ended = Promise.all([a.recorder,a.rawRecorder].map(recorder=>new Promise(resolve=>{
      if(recorder.state==='inactive')resolve();else {recorder.onstop=resolve;recorder.stop();}
    })));
    stopping = (async () => {
      await ended;
      // PCM observers must drain before finishing diagnostics, and their result
      // must be part of the final durable recording metadata.
      await a.diagnostics?.finish();
      await a.queue;
      a.recorder.dispose();a.mix.disconnect();a.destination.disconnect();
      if (!wasStarted || !a.meta.bytes) { status('未開始播放，沒有保存空白錄音。'); return; }
      // Rewrite only the fixed-size WAV headers; PCM chunks stay intact in IDB.
      a.meta.seconds=a.recorder.frames/a.context.sampleRate;
      a.meta.captureClock.frames=a.recorder.frames;
      a.chunks[0]=a.recorder.header();
      let savedId=null,partialSaved=false,completionStatus='';
      try {
        await store.save(a.meta,a.recorder.header(),0);
        await store.save(a.meta,a.recorder.voiceHeader(),0,'voice');
        partialSaved=true;
        if (a.error) throw a.error;
        let correctionError='';
        if(a.meta.recordingDelayMs!==0){
          status(`正在將錄音歌聲校正 ${a.meta.recordingDelayMs} ms 並保存…`);
          const decoder=new AudioContext({sinkId:{type:'none'}});
          try{
            const raw=await decoder.decodeAudioData(await(await store.blob(a.meta,'voice')).arrayBuffer());
            const audio=await remixRecording(raw,a.buffers,a.meta,a.meta.recordingDelayMs),blob=wavBlob(audio);
            const corrected={...a.meta,mime:'audio/wav',bytes:blob.size,seconds:audio.duration,appliedDelayMs:a.meta.recordingDelayMs};
            await store.replaceMix(corrected,blob);Object.assign(a.meta,corrected);
          }catch(error){correctionError=error.message;}finally{await decoder.close().catch(()=>{});}
        }
        a.meta.complete=true;await store.save(a.meta);savedId=a.meta.id;
        const diagnosticWarning=a.meta.diagnostics?.status==='incomplete'?` 診斷未完整保存：${a.meta.diagnostics.error}。`:a.meta.diagnostics?.status==='saved'?' 診斷已確認保存。':'';
        completionStatus=(correctionError?'延時校正未完成，已保留待確認錄音：'+correctionError:a.meta.segmentTake?'分段錄音已保存於分段區。':`錄音已保留為待確認版本 · 歌聲校正 ${a.meta.appliedDelayMs} ms。請先試聽，滿意再存到錄音後處理。`)+diagnosticWarning;
      } catch (error) {
        const panel = $('recording-rescue'); panel.hidden = false;
        const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob(a.chunks,{type:a.recorder.mimeType})); link.download = '演唱錄音.wav';
        const retained=partialSaved&&!a.storageFailed&&captureError instanceof Error&&a.error===captureError;
        link.textContent = `${retained?'下載錄音片段':'下載未保存錄音'}：${a.meta.title}（${new Date(a.meta.created).toLocaleTimeString()}）`; panel.append(link);
        status(retained?'收音中斷，已保留錄音片段，可下載備份：'+error.message:'錄音未完整保存，請先按「下載未保存錄音」備份：'+error.message);
      }
      await render(savedId).catch(error=>status('無法讀取錄音清單：'+error.message));
      if(completionStatus)status(completionStatus);
      if(a.meta.segmentTake)window.dispatchEvent(new CustomEvent('segment-capture-stopped',{detail:{captureId:a.meta.segmentTake.captureId}}));
      return savedId ? a.meta : null;
    })();
    return stopping;
  }
  const timer = setInterval(() => {
    const a = active; if (!a || a.recorder.state !== 'recording') return;
    const p = options.player();
    if (p?.getPlayerState?.() === 1) {
      syncTimeline(a,p.getCurrentTime()); syncBacking(a,p.getCurrentTime());
      const levels = a.mix.update();
      $('recording-balance-status').textContent = `${a.meta.balance.manual ? '手動＋自動微調' : '自動平衡'} · 人聲修正 ${levels.voiceDb.toFixed(1)} dB${a.meta.mode==='mix' ? ` · 配樂／和音修正 ${levels.backingDb.toFixed(1)} dB` : ''} · 輸出峰值保護開啟`;
    }
  }, 100);
  window.addEventListener('recording-post-saved',()=>render().catch(error=>status(error.message)));
  $('recording-delete-all').addEventListener('click',async()=>{
    if(active){status('請先停止收音，再刪除全部錄音。');return;}
    if(!localizedConfirm('刪除此清單中的整首錄音、已保存成品及其後處理資料？待確認錄音、分段素材、歌曲基準與分離音軌保留。此操作無法復原。'))return;
    const button=$('recording-delete-all');button.disabled=true;
    try{await stop();options.pausePlayer();clearPreview();post.clearAudio();const rows=(await store.list()).filter(isPostRecording);let deleted=0;for(const row of rows){await store.delete(row.id);status(`正在清除後處理錄音：${++deleted}／${rows.length} 筆…`);}await render();status(`已刪除 ${rows.length} 筆錄音及其後處理資料；待確認錄音與分段素材保留。`);}catch(error){status('未全部刪除：'+error.message);}finally{button.disabled=false;}
  });
  $('recording-refresh').addEventListener('click',()=>render().catch(error=>status(error.message)));
  $('recording-mode').addEventListener('change',()=>{ controls(); try { localStorage.setItem('karaoke.recording-mode.v1',$('recording-mode').value); } catch {} status($('recording-mode').value === 'off' ? '不保存錄音；從頭開始唱只收音評分。' : '按「從頭開始唱」後自動錄製；停止收音、結算或播完時保存。'); });
  for(const id of ['recording-manual','recording-voice-level','recording-backing-level']) $(id).addEventListener('input',()=>{
    setBalanceSettings(balanceSettings());
    $('recording-balance-status').textContent = $('recording-manual').checked ? '下一輪使用手動比例＋自動微調；只影響錄音。' : '下一輪使用自動平衡；只影響錄音。';
  });
  controls();
  window.addEventListener('pagehide',()=>{stop();clearInterval(timer);clearPreview();});
  render().catch(error=>status('瀏覽器錄音儲存不可用：'+error.message));
  return { prepare, stop, playerState, clearPreview, sample, referenceChanged(){post.controls();review.referenceChanged();}, store, refresh:render, balanceSettings, setBalanceSettings };
}
