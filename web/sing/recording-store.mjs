// Audio stays in IndexedDB on this browser; each chunk commits separately.
export const isPostRecording=row=>!row.segmentTake&&!row.postPending;
export class BrowserRecordingStore {
  constructor() { this.db = null; }
  async open() {
    if (!this.db) this.db = new Promise((resolve, reject) => {
      const request = indexedDB.open('karaoke.recordings.v1', 1);
      request.onupgradeneeded = () => {
        request.result.createObjectStore('takes', { keyPath: 'id' });
        request.result.createObjectStore('chunks', { keyPath: ['id', 'index'] });
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => { this.db = null; reject(request.error); };
      request.onblocked = () => { this.db = null; reject(new Error('錄音資料庫被其他分頁占用。')); };
    });
    return this.db;
  }
  async transaction(mode, work) {
    const db = await this.open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(['takes', 'chunks'], mode); let result;
      tx.oncomplete = () => resolve(result);
      tx.onabort = tx.onerror = () => reject(tx.error || new Error('錄音儲存失敗。'));
      work(tx, value => { result = value; });
    });
  }
  save(meta, chunk, index, track = 'mix') {
    return this.transaction('readwrite', tx => {
      tx.objectStore('takes').put(meta);
      if (chunk) tx.objectStore('chunks').put({ id: track === 'voice' ? meta.id + ':voice' : meta.id, index, blob: chunk });
    });
  }
  replaceMix(meta,blob) {
    return this.transaction('readwrite',tx=>{
      tx.objectStore('chunks').delete(IDBKeyRange.bound([meta.id,0],[meta.id,Number.MAX_SAFE_INTEGER]));
      tx.objectStore('chunks').put({id:meta.id,index:0,blob});tx.objectStore('takes').put(meta);
    });
  }
  saveRemix(meta,mix,voice) {
    return this.transaction('readwrite',tx=>{
      tx.objectStore('takes').put(meta);
      tx.objectStore('chunks').put({id:meta.id,index:0,blob:mix});
      tx.objectStore('chunks').put({id:meta.id+':voice',index:0,blob:voice});
    });
  }
  list() {
    return this.transaction('readonly', (tx, done) => {
      tx.objectStore('takes').getAll().onsuccess = event => done(event.target.result.filter(x => x.bytes > 0).sort((a,b) => b.created - a.created));
    });
  }
  blob(meta, track = 'mix') {
    const id = track === 'voice' ? meta.id + ':voice' : meta.id;
    return this.transaction('readonly', (tx, done) => {
      tx.objectStore('chunks').getAll(IDBKeyRange.bound([id,0],[id,Number.MAX_SAFE_INTEGER])).onsuccess = event => done(new Blob(event.target.result.map(x => x.blob), { type: track==='voice'?(meta.rawMime||meta.mime):meta.mime }));
    });
  }
  delete(id) {
    return this.transaction('readwrite', tx => {
      tx.objectStore('takes').delete(id);
      tx.objectStore('chunks').delete(IDBKeyRange.bound([id,0],[id,Number.MAX_SAFE_INTEGER]));
      tx.objectStore('chunks').delete(IDBKeyRange.bound([id+':voice',0],[id+':voice',Number.MAX_SAFE_INTEGER]));
    });
  }
}


// IndexedDB buffers an active take. Completed recordings move to the local helper.
export class RecordingStore {
  constructor({status=()=>{}}={}){this.browser=new BrowserRecordingStore();this.status=status;this.pending=Promise.resolve();this.diskRows=[];this.session=null;this.listRequest=null;}
  open(){return this.browser.open();}
  serial(work){this.listRequest=null;const result=this.pending.then(work);this.pending=result.catch(()=>{});return result;}
  async request(route,{method='GET',body,root}={}){
    const base='http://127.0.0.1:4274';
    if(!this.session||Date.now()-this.session.time>5000){const r=await fetch(base+'/session',{signal:AbortSignal.timeout(5000)});if(!r.ok)throw new Error('本機工具無法連接。');this.session={...await r.json(),time:Date.now()};}
    if(!this.session.features?.includes('recording-library'))throw new Error('請更新並重新啟動本機工具，才能搬存錄音。');
    const url=base+route+(root?'?root='+encodeURIComponent(root):'');
    const r=await fetch(url,{method,headers:{'X-Karaoke-Token':this.session.token,...(body?{'Content-Type':'application/octet-stream'}:{})},body,signal:AbortSignal.timeout(body?180000:30000)});
    if(!r.ok){if(r.status===403)this.session=null;const value=await r.json().catch(()=>({}));throw new Error(value.error||'錄音資料夾操作失敗。');}return r;
  }
  replaceMix(meta,blob){return this.serial(()=>this.browser.replaceMix(meta,blob));}
  async info(){return (await this.request('/recordings')).json();}
  async move(meta,info){
    if(info.deleted.includes(meta.id)){await this.browser.delete(meta.id);return null;}
    let stored=info.records.find(r=>r.id===meta.id);
    if(!stored){
      if(meta.rawBytes&&meta.rawMime&&meta.rawMime!==meta.mime&&!this.session?.features?.includes('recording-raw-mime'))throw new Error('請重新啟動新版本機工具，才能保存校正成品與原始歌聲。');
      const mix=await this.browser.blob(meta),voice=meta.rawBytes?await this.browser.blob(meta,'voice'):new Blob();
      if(mix.size!==meta.bytes||voice.size!==(meta.rawBytes||0))throw new Error('瀏覽器原始音檔不完整，未搬存也未刪除。');
      const bytes=new TextEncoder().encode(JSON.stringify(meta)),prefix=new Uint8Array(4);new DataView(prefix.buffer).setUint32(0,bytes.length,true);
      stored=await(await this.request('/recordings/'+meta.id,{method:'POST',body:new Blob([prefix,bytes,mix,voice]),root:info.path})).json();
    }
    if(stored.bytes!==meta.bytes||(stored.rawBytes||0)!==(meta.rawBytes||0))throw new Error('本機錄音大小與瀏覽器副本不符，保留原檔。');
    // Server commits and re-reads the complete manifest/audio sizes before replying.
    await this.browser.delete(meta.id);
    return stored;
  }
  save(meta,chunk,index,track='mix'){
    this.listRequest=null;
    if(chunk&&!meta.complete)return this.browser.save(meta,chunk,index,track);
    return this.serial(async()=>{
      if(meta._archiveRoot&&!chunk){
        const stored=await(await this.request('/recordings/'+meta.id+'/metadata',{method:'POST',body:new Blob([JSON.stringify(meta)]),root:meta._archiveRoot})).json();
        this.diskRows=this.diskRows.map(r=>r.id===meta.id?stored:r);return;
      }
      await this.browser.save(meta,chunk,index,track);
      await this.archiveCompleted(meta);
    });
  }
  async archiveCompleted(meta){
    if(meta.complete&&meta.bytes){try{const info=await this.info(),stored=await this.move(meta,info);if(stored){Object.assign(meta,stored);this.diskRows=[stored,...this.diskRows.filter(r=>r.id!==meta.id)];}this.status('已保存至 '+info.path+'。');}catch(error){this.status('暫存在此瀏覽器，尚未搬存：'+error.message);}}
  }
  saveRemix(meta,mix,voice){
    return this.serial(async()=>{
      await this.browser.saveRemix(meta,mix,voice);
      await this.archiveCompleted(meta);
    });
  }
  list(){
    // Share overlapping readers only. A queued mutation invalidates this request,
    // so a subsequent reader still waits for the write and gets a fresh inventory.
    if(this.listRequest)return this.listRequest;
    const request=this.serial(async()=>{
    const local=await this.browser.list();let info;
    try{info=await this.info();}catch(error){this.status('本機錄音目錄未連線；瀏覽器待搬存資料仍保留。'+error.message);return [...local,...this.diskRows.filter(r=>!local.some(l=>l.id===r.id))].sort((a,b)=>b.created-a.created);}
    const records=new Map(info.records.map(row=>[row.id,row]));let moved=0;const errors=[];
    for(const row of local){
      if(info.deleted.includes(row.id)){await this.browser.delete(row.id);continue;}
      if(row.complete){try{this.status(`正在搬存錄音 ${moved+1}：${row.title}…`);const stored=await this.move(row,info);if(stored)records.set(row.id,stored);moved++;continue;}catch(error){errors.push(error.message);}}
      if(!records.has(row.id))records.set(row.id,row);
    }
    this.diskRows=[...records.values()].filter(r=>r._archiveRoot);
    this.status(`錄音位置：${info.path}。${moved?'已搬存 '+moved+' 筆，瀏覽器舊副本已清除。':''}${errors.length?'部分錄音仍留在瀏覽器：'+errors[0]:''}`);
    return [...records.values()].sort((a,b)=>b.created-a.created);
    });
    this.listRequest=request;
    const clear=()=>{if(this.listRequest===request)this.listRequest=null;};request.then(clear,clear);
    return request;
  }
  async blob(meta,track='mix'){
    if(meta._archiveRoot)return (await this.request('/recordings/'+meta.id+'/'+track,{root:meta._archiveRoot})).blob();
    const local=await this.browser.blob(meta,track);if(local.size)return local;
    const stored=this.diskRows.find(r=>r.id===meta.id);if(stored)return this.blob(stored,track);
    return local;
  }
  delete(id){return this.serial(async()=>{
    const known=this.diskRows.find(r=>r.id===id);let info;
    // A listed row already carries its archive root. DELETE validates that root
    // and the target on the server; rescanning every other recording adds no safety.
    if(!known)try{info=await this.info();}catch{/* Browser-only takes remain deletable offline. */}
    const disk=info?.records.find(r=>r.id===id)||known;
    if(disk){await this.request('/recordings/'+id,{method:'DELETE',root:disk._archiveRoot});}
    await this.browser.delete(id);this.diskRows=this.diskRows.filter(r=>r.id!==id);
  });}
  async deleteAll(){const rows=await this.list();for(const row of rows)await this.delete(row.id);return rows.length;}
  async saveMp3(meta,blob){
    const stored=this.diskRows.find(r=>r.id===meta.id)||(await this.info()).records.find(r=>r.id===meta.id);if(!stored)throw new Error('請先將這筆錄音搬存到歌曲庫。');
    return (await this.request('/recordings/'+meta.id+'/mp3',{method:'POST',body:blob,root:stored._archiveRoot})).json();
  }
}
