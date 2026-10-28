import {youtubeId} from './audio.mjs';
export const isLocalMediaId=id=>typeof id==='string'&&/^local_[a-f0-9]{64}$/.test(id);
export const isMediaId=id=>typeof id==='string'&&(/^[\w-]{11}$/.test(id)||isLocalMediaId(id));
export function selectedMediaId(doc=document){return ['local','audio'].includes(doc.getElementById('source-kind')?.value)?doc.getElementById('local-media-id').value:youtubeId(doc.getElementById('url').value.trim());}
export function selectMediaSource(id,doc=document,mediaKind){
  const local=isLocalMediaId(id),kind=doc.getElementById('source-kind');
  if(kind)kind.value=local?(mediaKind==='audio'||(!mediaKind&&doc.getElementById('local-media-id').value===id&&kind.value==='audio')?'audio':'local'):'youtube';
  if(local)doc.getElementById('local-media-id').value=id;else doc.getElementById('url').value=`https://www.youtube.com/watch?v=${id}`;
  showMediaSource(doc);
}
export function showMediaSource(doc=document){
  const kind=doc.getElementById('source-kind')?.value,local=['local','audio'].includes(kind),audio=kind==='audio';
  if(!doc.getElementById('local-media-controls'))return;
  doc.getElementById('local-media-controls').hidden=!local;doc.getElementById('song-form').hidden=local;
  doc.getElementById('source-description').textContent=local?(audio?'本機音檔 · 預設聲波畫面':'本機 MV · 影片留在本機'):'YouTube 原生播放';
  doc.querySelector('label[for="local-media-file"]').textContent=audio?'選擇本機音檔':'選擇本機 MV';
  doc.getElementById('local-media-file').accept=audio?'.mp3,.wav':'.mp4,.m4v,.mov,.mkv,.webm';
  doc.querySelector('label[for="local-media-saved"]').textContent=audio?'已匯入的音檔':'已匯入的 MV';
  doc.getElementById('local-media-load').textContent=audio?'載入音檔':'載入 MV';
  doc.getElementById('local-media-help').textContent=(audio?'MP3／WAV 音檔，使用預設聲波畫面。':'MP4／MOV／MKV／WebM 影片。')+'最多 2 GB、15 分鐘。工作副本保存在歌曲庫的 .local-mv 資料夾，原檔保留，不上傳雲端。';
}
