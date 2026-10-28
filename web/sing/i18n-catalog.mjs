// UI-only English catalog. Chinese source messages remain the canonical data.
// Templates: [source, English, UI-fragment slots, generated-segment-name slots].
// Other slots preserve user data. Unknown messages are displayed unchanged.
export const messages = {
  "請先選擇要錄製的段落。": "Choose a segment to record first.",
  "律動：開啟": "Motion: on",
  "律動：關閉": "Motion: off",
  "裝置已設定減少動態效果。": "Your device is set to reduce motion.",
  "開啟或關閉介面裝飾動畫": "Turn decorative interface animation on or off",
  "搜尋本機歌單": "Search local songs",
  "輸入歌名或歌手關鍵字": "Enter a song title or artist keyword",
  "清除搜尋": "Clear search",
  "找不到符合的歌曲，請換個關鍵字或清除搜尋。": "No matching songs. Try another keyword or clear the search.",
  "唱錄系統 · 桌機本機實驗室": "Sing & Record · Local Desktop Studio",
  "唱錄系統": "Sing & Record",
  "本機分析 · 錄音留在本機": "Local analysis · Recordings stay on your computer",
  "配色": "Theme",
  "控台": "Console",
  "科技藍": "Tech blue",
  "暖色調": "Warm",
  "收音設定": "Audio input",
  "本機工具": "Local tools",
  "歌曲庫": "Song library",
  "播放／錄音": "Playback / Recording",
  "歌曲準備／Key": "Song preparation / Key",
  "評分／結算": "Scoring / Results",
  "錄音後處理": "Recording post-production",
  "收音測試": "Input test",
  "延遲校正": "Latency calibration",
  "評分與錄音設定": "Scoring and recording settings",
  "說明 ↗": "Help ↗",
  "1／8 確認收音": "1/8 Check your input",
  "先選收音方式與麥克風，再開麥試聲。": "Choose an input mode and microphone, then enable the mic to test it.",
  "前往收音設定": "Go to audio input",
  "設定已確認": "Settings confirmed",
  "LOCAL AUDIO STUDIO / 本機聲音工作室": "LOCAL AUDIO STUDIO",
  "看著唱。": "Sing along.",
  "看見你的聲音。": "See your voice.",
  "從選歌、錄唱到後製，留下屬於你的版本。": "Choose a song, record your vocals, and make it your own.",
  "YouTube、本機 MV 與音檔都能唱，錄音留在你的電腦。": "Sing with YouTube, local videos, or audio files. Recordings stay on your computer.",
  "選歌": "Choose a song",
  "錄唱": "Record",
  "後製": "Produce",
  "收音方式 · 麥克風選擇": "Input mode · Microphone selection",
  "收音方式": "Input mode",
  "瀏覽器收音（原有方式）": "Browser capture (standard)",
  "本機相容收音（開麥後伴奏變小聲時使用）": "Native capture (if backing audio becomes quieter when the mic is enabled)",
  "本機相容模式由這台電腦的 Python 收音，需要啟動本機工具並允許 Python 麥克風權限。聲音只送回本機瀏覽器；仍依下方錄音選項決定是否保存。切換收音方式後請重新測試延遲。": "Native mode uses Python on this computer. Start local tools and allow Python microphone access. Audio returns only to the local browser; recording settings below control whether it is saved. Retest latency after switching input modes.",
  "收音麥克風": "Microphone",
  "系統預設麥克風": "System default microphone",
  "第一次允許收音後可選裝置。建議先用有線耳機或 USB 麥克風測試。": "Device names appear after microphone permission is granted. Use headphones to keep backing audio out of your recording.",
  "錄音診斷 · 自動保存問題線索": "Recording diagnostics · Automatically save troubleshooting data",
  "錄音時自動診斷": "Run diagnostics while recording",
  "開啟時，錄音前先確認本機工具可保存診斷；停止錄音後確認資料完整寫入。只在整首／分段錄音期間保存對照音訊，練唱與試聽不收集。診斷可能影響音訊時序，不代表斷音已修好。": "Checks that local tools can save diagnostics before recording and confirms complete writes afterward. Comparison audio is saved only during whole-song or segment recording, not practice or preview. Diagnostics may affect timing and do not mean audio dropouts are fixed.",
  "診斷待命。": "Diagnostics ready.",
  "重新整理診斷狀態": "Refresh diagnostic status",
  "清除所有診斷資料": "Clear all diagnostic data",
  "只存本機，重新整理後仍保留。最多 2 GB；容量不足時停止診斷並提示，演唱錄音繼續。清除診斷不會刪除歌曲、錄音或後處理成品。": "Stored locally across reloads, up to 2 GB. If space runs out, diagnostics stop with a warning while recording continues. Clearing diagnostics keeps songs, recordings, and production results.",
  "先確認本機工具": "Check the local tools first",
  "只在你的電腦處理音訊": "Audio is processed on your computer",
  "尚未檢查。第一次使用請安裝；已安裝則啟動本機工具。": "Not checked yet. Install the tools on first use, or start your existing installation.",
  "檢查本機工具": "Check local tools",
  "GitHub Pages 只提供網頁。下載、分離與後續評分在你的電腦執行。": "GitHub Pages hosts the interface. Audio processing requires the local tools running on your computer.",
  "安裝／啟動說明（Windows）": "Installation / Startup (Windows)",
  "下載本機工具包": "Download the local tools",
  "，解壓縮到固定資料夾。第一次需先備妥": "and extract them to a permanent folder. First install",
  "Node.js 22 以上": "Node.js 22 or later",
  "與": "and",
  "在該資料夾開啟 PowerShell，第一次執行：": "Open PowerShell in that folder and run this on first use:",
  "工具與模型會安裝在本機，不會上傳你的音訊。": "Tools and models are installed locally. Your audio is not uploaded.",
  "每次重開機後啟動：": "Start after each restart:",
  "回到此頁點「檢查本機工具」。如果瀏覽器詢問本機網路存取，請允許。": "Return here and click “Check local tools”. Allow local network access if your browser asks.",
  "重開機不會移除安裝。只有關閉本機工具、重開機後未啟動，或連線權限被拒絕時，需要重新連線。Windows 重設／重灌後可能需要重建。": "Restarting does not uninstall the tools. Reconnect after closing the tools, restarting, or changing permissions. Reinstalling Windows may require setup again.",
  "你的本機歌曲庫": "Your local song library",
  "設定一次，分析好的歌曲就留在這裡。": "Set it up once. Prepared songs stay here.",
  "只存在本機": "Stored locally",
  "儲存位置": "Storage location",
  "選擇資料夾": "Choose folder",
  "使用此位置": "Use this location",
  "第一次先選擇歌曲庫位置，這台電腦會記住設定。": "Choose a song library folder on first use. This computer will remember it.",
  "取消資料夾選擇": "Cancel folder selection",
  "換資料夾不會刪除原歌曲。歌曲載入中請先「取消／卸載」，再變更位置。": "Changing folders does not delete existing songs. If a song is loading, click “Cancel / Unload” before changing the location.",
  "聲曲分離優先使用 NVIDIA GPU，無法使用時改用 CPU。第一次需下載模型，之後重用；音訊不會上傳到雲端。": "Uses an NVIDIA GPU when available, otherwise the CPU. Models download once; your audio is not uploaded.",
  "歌曲影音": "Song media",
  "YouTube 原生播放": "YouTube playback",
  "影音來源": "Media source",
  "YouTube 網址": "YouTube URL",
  "本機 MV": "Local video",
  "本機音檔（MP3／WAV）": "Local audio (MP3 / WAV)",
  "歌曲影片網址": "Song video URL",
  "載入影片": "Load video",
  "選擇本機 MV": "Choose local video",
  "MP4／MOV／MKV／WebM，最多 2 GB、15 分鐘。影片副本保存在歌曲庫的 .local-mv 資料夾，原檔保留，不上傳雲端；必要時自動轉為 MP4。": "MP4 / MOV / MKV / WebM, up to 2 GB and 15 minutes. A copy is stored in .local-mv; your original is preserved. Nothing is uploaded. Videos are converted to MP4 when needed.",
  "已匯入的 MV": "Imported videos",
  "選擇已匯入的 MV": "Choose an imported video",
  "載入 MV": "Load video",
  "重新整理": "Refresh",
  "取消匯入": "Cancel import",
  "選擇檔案後，可用相同流程準備基準、評分、分段、錄音與升降 Key。": "Choose a file, then use the same preparation, scoring, segment recording, and key change workflow.",
  "貼上網址後，影片會在這裡播放。": "Paste a URL to play the video here.",
  "你的下一首歌": "Your next song",
  "播放器與麥克風分別啟動": "Start the player and microphone separately",
  "LOCAL AUDIO / 本機音檔": "LOCAL AUDIO",
  "預設聲波畫面 · 可整首演唱或分段錄製": "Waveform view · Record a whole song or individual segments",
  "播放器時間": "Player time",
  "補償後位置": "Adjusted position",
  "歌曲 Key · 每格半音，速度不變": "Song key · One semitone per step, same tempo",
  "降 12 Key": "Down 12 semitones",
  "降 11 Key": "Down 11 semitones",
  "降 10 Key": "Down 10 semitones",
  "降 9 Key": "Down 9 semitones",
  "降 8 Key": "Down 8 semitones",
  "降 7 Key": "Down 7 semitones",
  "降 6 Key": "Down 6 semitones",
  "降 5 Key": "Down 5 semitones",
  "降 4 Key": "Down 4 semitones",
  "降 3 Key": "Down 3 semitones",
  "降 2 Key": "Down 2 semitones",
  "降 1 Key": "Down 1 semitone",
  "原調（0）": "Original key (0)",
  "升 1 Key": "Up 1 semitone",
  "升 2 Key": "Up 2 semitones",
  "升 3 Key": "Up 3 semitones",
  "升 4 Key": "Up 4 semitones",
  "升 5 Key": "Up 5 semitones",
  "升 6 Key": "Up 6 semitones",
  "升 7 Key": "Up 7 semitones",
  "升 8 Key": "Up 8 semitones",
  "升 9 Key": "Up 9 semitones",
  "升 10 Key": "Up 10 semitones",
  "升 11 Key": "Up 11 semitones",
  "升 12 Key": "Up 12 semitones",
  "建立／載入此 Key": "Create / Load this key",
  "預設原調。準備歌曲前可選 Key；不同 Key 版本會一起保存在歌曲庫，錄音與分段草稿各自保留。": "Original key by default. Choose a key before preparing a song. Key versions are stored together in the library, with separate recordings and segment drafts.",
  "播放／暫停影片": "Play / Pause video",
  "在此分段": "Split here",
  "復原分界": "Undo split",
  "尚未選定歌曲": "No song selected",
  "演唱時帶唱": "Guide vocals while singing",
  "原唱＋伴樂（預設）": "Original vocals + backing (default)",
  "只有伴樂／和音": "Backing / harmonies only",
  "開始前選擇，按「從頭開始唱」套用。只有伴樂需已保存分離音軌；請戴耳機，避免原唱被麥克風收進錄音。": "Choose before clicking “Sing from the start”. Backing-only mode requires saved stems. Wear headphones to prevent the mic from picking up the original vocals.",
  "人聲／伴樂音量平衡 · 與分段錄音共用": "Vocal / backing balance · Shared with segment recording",
  "手動設定比例＋自動微調": "Manual levels + automatic fine-tuning",
  "未勾選：自動平衡歌唱者與配樂／和音。勾選後使用你設定的音量，系統只做小幅修正。": "Unchecked: automatically balance your vocals and backing / harmonies. Checked: use your levels with small automatic corrections.",
  "歌唱者音量": "Singer volume",
  "配樂／和音音量": "Backing / harmony volume",
  "自動平衡 · 平滑調整音量，低音量或未偵測到穩定歌聲時不自動增強麥克風。只影響錄音，不影響評分；每輪開始前設定。": "Automatic balance adjusts levels smoothly without boosting the mic when input is quiet or no stable singing is detected. Affects recordings only, not scoring. Set before each take.",
  "從頭開始唱": "Sing from the start",
  "結束並結算": "Finish and score",
  "錄音停止後存入本機歌曲庫的「錄音」目錄；不會上傳雲端。": "Stopped recordings are saved in the recording folder of your local song library. Nothing is uploaded.",
  "整首錄音 · 待確認": "Whole-song recordings · Pending review",
  "只顯示目前載入歌曲版本與 Key 的待確認錄音；切回其他歌曲即可查看該曲錄音。錄音已自動保留，重新整理後仍在。先試聽，滿意再加入錄音後處理；不滿意可刪除此版。": "Pending takes for the current song version and key are kept locally. Listen, approve, or delete them here.",
  "待確認版本": "Pending take",
  "試聽內容": "Preview content",
  "人聲＋伴樂／和音": "Vocals + backing / harmonies",
  "純人聲": "Vocals only",
  "純人聲直接播放這一版錄到的人聲原檔；加入伴樂時才套用混音比例與歌聲校正。": "Vocals-only preview uses the original vocal file. Mixed preview applies the balance and timing correction.",
  "試聽這一版": "Preview this take",
  "存到錄音後處理": "Save for post-production",
  "刪除此版": "Delete this take",
  "刪除這首全部待確認錄音": "Delete all pending takes for this song",
  "依上方選取的歌曲與 Key 清除；分段錄音與已存到錄音後處理的成品保留。": "Only affects pending takes for this song and key. Segment recordings and approved recordings are preserved.",
  "總分 / 100": "Total / 100",
  "音準 · 60%": "Pitch · 60%",
  "進拍 · 25%": "Timing · 25%",
  "完整度 · 15%": "Completeness · 15%",
  "尚未開始演唱；每輪開始後固定難度。": "Not singing yet. Difficulty is fixed for each round.",
  "準備歌曲並開啟麥克風後，按播放就開始評分。": "Prepare a song and enable your microphone, then play to start scoring.",
  "分段錄音／補唱": "Segment recording / Retakes",
  "整首評分模式": "Whole-song scoring mode",
  "開啟分段模式": "Enable segment mode",
  "回整首評分": "Back to whole-song scoring",
  "「從頭開始唱」保留原本錄音與整首評分。分段模式可邊播放邊加分界，不寫入整首分數。": "Whole-song mode records and scores the full song. In segment mode, add splits during playback and record individual sections without saving scores.",
  "合併為一段": "Merge into one segment",
  "復原保留最近 40 次調整；沒有更早紀錄時，繼續按會從最後一道分界往前移除，直到剩一整段。原始錄音保留；合併不同演唱版本後需重新挑選。": "Undo up to 40 recent changes, then remove splits from the end to return to one segment. Original recordings are preserved; reselect takes after merging sections with different takes.",
  "歌曲位置": "Song position",
  "要錄製或補唱的段落": "Segment to record or retake",
  "調整分界時間／段落名稱": "Edit boundaries / Segment names",
  "段落名稱": "Segment name",
  "分界微調": "Fine-tune boundary",
  "分界時間（mm:ss.sss）": "Boundary time (mm:ss.sss)",
  "調整步距": "Step size",
  "0.1 秒": "0.1 seconds",
  "1 秒": "1 second",
  "提前": "Earlier",
  "延後": "Later",
  "試聽分界 ±3 秒": "Preview ±3 seconds around boundary",
  "移除分界": "Remove boundary",
  "拖曳時間軸的分界線或輸入精確時間；相鄰兩段會一起更新。更改分界不會裁掉原始錄音。": "Drag a boundary or enter an exact time. Both neighboring segments update; original recordings are preserved.",
  "起唱與尾音設定 · 預設提前 5 秒／尾音 2 秒": "Start and tail · Default pre-roll 5 seconds / tail 2 seconds",
  "提前播放（秒，0～60）": "Pre-roll (seconds, 0–60)",
  "尾音餘量": "Tail allowance",
  "2 秒": "2 seconds",
  "3 秒": "3 seconds",
  "可輸入較長的準備秒數；若段落前不足指定時間，就從歌曲開頭播放。": "A longer pre-roll gives you more time to prepare. Playback starts no earlier than the beginning of the song.",
  "錄音時帶唱": "Guide vocals while recording",
  "循環練唱本段": "Loop this segment",
  "錄這一段": "Record this segment",
  "停止／保存本段": "Stop / Save segment",
  "載入歌曲後，可開啟分段模式。": "Load a song to enable segment mode.",
  "挑選版本與試合": "Choose takes and assemble",
  "分段成品": "Segment mix",
  "人聲／伴樂音量平衡 · 與從頭開始唱共用": "Vocal / backing balance · Shared with “Sing from the start”",
  "單段試聽與完整試合都先完成混音，再播放音檔。調整音量後會重新混音，完成後接續目前位置播放。滿意後按「存到錄音後處理」，不必重錄。純人聲原檔試聽不套用音量調整。": "Segment previews and full mixes are rendered completely before playback. Changing levels rebuilds the mix, then resumes at the current position. Save for post-production when satisfied; no need to record again. Raw vocal preview ignores level adjustments.",
  "挑選本段演唱版本": "Choose a take for this segment",
  "重新讀取錄音版本": "Reload takes",
  "保存草稿": "Save draft",
  "本段採用的演唱版本": "Selected take for this segment",
  "只列出本段錄音，可重錄多次，沒有三次上限。": "Takes are listed for this segment only. You can record as many as you need.",
  "試聽選用版本": "Preview selected take",
  "刪除此版錄音": "Delete this take",
  "試合完整一版／滿意後保存 · 預設人聲＋伴樂，300 ms": "Assemble a full mix / Save when satisfied · Default vocals + backing, 300 ms",
  "依每個段落目前選用的錄音版本試合；換選版本後，請重新試合。": "Assemble the selected takes into one mix. Reassemble after changing take selections.",
  "試合內容": "Mix content",
  "歌聲校正（ms）": "Vocal correction (ms)",
  "原唱加入區間": "Original vocal regions",
  "（未設定）": "(not set)",
  "用歌曲時間設定多個區間，每段可選一起唱或只用原唱。區間外保留你的錄音，伴奏照常；僅套用「人聲＋伴樂／和音」的完整試合，純人聲仍保留你的收音。": "Choose song-time regions for a duet or original vocals only. Outside these regions, your vocals are used. Backing continues throughout. Applies to mixed previews, not raw vocals.",
  "開始（分:秒）": "Start (min:sec)",
  "結束（分:秒）": "End (min:sec)",
  "區間人聲": "Region vocals",
  "原唱＋我的錄音": "Original + my recording",
  "只用原唱": "Original only",
  "填入目前段落時間": "Use current segment times",
  "新增原唱區間": "Add original vocal region",
  "設定隨本歌曲草稿保存；調整後請重新試合。": "Saved with this song’s draft. Reassemble after changing regions.",
  "允許未錄範圍保留靜音": "Allow silence in unrecorded regions",
  "試合完整一版": "Assemble full mix",
  "試合並聽本段接合": "Assemble and preview this join",
  "下載試合 WAV": "Download mix WAV",
  "單段錄音保存在分段區，試合只供暫存試聽，兩者都不加入錄音後處理。滿意後按「存到錄音後處理」，才保存完整成品供後製及 A/B。試合可加伴樂，校正預設 300 ms；原始分段錄音保留。": "Segments and previews stay here until you save the finished mix for post-production. Default vocal correction is 300 ms; original recordings are preserved.",
  "清除此歌曲的所有分段錄音": "Delete all segment recordings for this song",
  "只刪除目前歌曲的各段錄音版本。段落分界、其他歌曲、整首錄音與錄音後處理中的已存成品都保留。": "Deletes takes for this song only. Other songs, whole-song recordings, saved mixes, and boundaries are preserved.",
  "即時音高與收音": "Live pitch and input",
  "麥克風未開啟": "Microphone off",
  "等待收音": "Waiting for input",
  "單音音高 · 65–1000 Hz": "Monophonic pitch · 65–1000 Hz",
  "收音音量": "Input level",
  "你的音高 · 最近 8 秒": "Your pitch · Last 8 seconds",
  "即時音高": "Live pitch",
  "亮色線是你的音高；藍線是原唱旋律。允許八度差時，兩線不一定重疊。": "The bright line is your voice; blue is the reference melody. Octave differences may appear.",
  "原唱音符": "Original vocal notes",
  "等待歌曲基準": "Waiting for song reference",
  "開啟麥克風": "Enable microphone",
  "停止收音": "Stop input",
  "歌聲輸出到喇叭": "Vocal output to speakers",
  "即時播放我的歌聲": "Monitor my voice live",
  "歌聲輸出裝置": "Vocal output device",
  "系統預設喇叭": "System default speakers",
  "歌聲輸出音量": "Vocal output level",
  "請先開啟麥克風，再勾選歌聲輸出。": "Enable the microphone before turning on vocal monitoring.",
  "請先戴耳機，降低伴奏被麥克風收到的機會。": "Wear headphones to reduce backing audio picked up by the microphone.",
  "收音裝置與狀態": "Input device and status",
  "授權後才會顯示裝置資訊。": "Device information appears after permission is granted.",
  "聲曲分離與音高旋律擷取": "Stem separation and pitch extraction",
  "本機分析與歌曲庫": "Local analysis and song library",
  "分離與音高設定 · 遮罩與試聽": "Separation and pitch settings · Masks and previews",
  "新歌預設設定": "Defaults for new songs",
  "可展開進階設定調整": "Expand advanced settings to customize",
  "分析範圍": "Analysis range",
  "完整歌曲，最長 15 分鐘": "Full song, up to 15 minutes",
  "基準音高擷取": "Reference pitch extraction",
  "聲曲分離模型": "Separation model",
  "處理流程": "Processing workflow",
  "單次分離": "Single pass",
  "分離模式": "Separation mode",
  "人聲／伴奏分離": "Vocals / Instrumental",
  "分離音軌": "Separated stems",
  "保留人聲、伴奏，供本機試聽": "Keep vocals and instrumental for local preview",
  "未調整時沿用以上預設。按「準備歌曲基準」套用目前選項，變更模型／模式會另存歌曲版本；「重新分離並覆蓋」與「補建試聽音軌」沿用已載入版本。下方會顯示目前試聽來源。": "These defaults apply unless changed. “Prepare song reference” uses the current options; changing the model or mode saves another song version. “Separate again and overwrite” and “Rebuild preview stems” use the loaded version. The current preview source is shown below.",
  "進階分離設定 · 展開可調整": "Advanced separation settings · Expand to customize",
  "準備歌曲時使用": "Used when preparing songs",
  "完整歌曲（最長 15 分鐘，預設）": "Full song (up to 15 minutes, default)",
  "先試前 15 秒": "Try the first 15 seconds",
  "先試前 30 秒": "Try the first 30 seconds",
  "先試前 60 秒": "Try the first 60 seconds",
  "RMVPE（預設）": "RMVPE (default)",
  "YIN（原有方式）": "YIN (legacy)",
  "Demucs／htdemucs（預設）": "Demucs / htdemucs (default)",
  "Mel-Band RoFormer／Kim 人聲": "Mel-Band RoFormer / Kim vocals",
  "單次分離（預設）": "Single pass (default)",
  "伴奏二次分離＋反向相減": "Second instrumental pass + subtraction",
  "人聲／伴奏分離（預設）": "Vocals / Instrumental (default)",
  "主唱／和音分離（伴樂保留原唱和音）": "Lead / Harmony (backing keeps the original harmony)",
  "保留分離音軌（試聽、只有伴樂與錄音合成需要）": "Keep separated stems (required for previews, backing-only playback, and recording mixes)",
  "想在「只有伴樂」時保留原唱的和音，選「主唱／和音分離」並保留音軌，再按「準備歌曲基準」。只有人聲／伴奏的舊歌需要建立這個新版本；已有主唱／和音版本可直接載入。分離模型可能誤判，先試聽主唱與和音確認。": "To keep the original harmony vocals during “Backing only” playback, choose “Lead / Harmony” and keep stems, then prepare the song reference. Older vocal/instrumental songs need this new version; existing lead/harmony versions can be loaded directly. Separation may misclassify voices, so preview both stems first.",
  "還原分離預設": "Reset separation defaults",
  "分離結果試聽": "Preview separated stems",
  "尚未載入試聽版本。": "No preview version loaded.",
  "準備歌曲時會保留試聽音軌。試聽會暫停 YouTube，不參與評分；音檔只在本機。": "Preview stems are kept during song preparation. Previewing pauses YouTube and does not affect scoring. Files stay on your computer.",
  "試聽人聲": "Preview vocals",
  "試聽伴奏": "Preview instrumental",
  "試聽主唱": "Preview lead",
  "試聽和音": "Preview harmonies",
  "請先載入歌曲，才能查看試聽音軌。": "Load a song to view preview stems.",
  "補建試聽音軌": "Rebuild preview stems",
  "不計分區間遮罩（選用）": "Unscored region masks (optional)",
  "載入歌曲基準後，可用播放器定位樂器或誤判段落。遮罩內顯示「休息」，不計音準、進拍或完整度，也不會跳過或靜音影片。預設沒有遮罩。": "After loading a reference, locate instrumental or misidentified sections with the player. Masked regions show “Rest” and are excluded from pitch, timing, and completeness scores. Video is not skipped or muted. No masks are set by default.",
  "尚未載入歌曲基準。": "No song reference loaded.",
  "起點（秒或 分:秒）": "Start (seconds or min:sec)",
  "目前位置設為起點": "Use current position as start",
  "終點（秒或 分:秒）": "End (seconds or min:sec)",
  "目前位置設為終點": "Use current position as end",
  "新增並保存遮罩": "Add and save mask",
  "清除全部遮罩": "Clear all masks",
  "請先載入歌曲基準。": "Load a song reference first.",
  "遮罩自動保存於本機歌曲庫，不需重新分離；同一影片、同一分析範圍的所有模型共用。重疊或相連區間會合併，每輪演唱開始後固定。區間起點包含、終點不包含，以基準音高格判定（通常 0.1 秒）。": "Masks save automatically in your local library without separating again. All models for the same video and analysis range share them. Overlapping or adjacent regions merge. Masks are fixed for each singing round; start is inclusive and end exclusive, using reference pitch frames (usually 0.1 seconds).",
  "準備歌曲基準": "Prepare song reference",
  "重新分離並覆蓋": "Separate again and overwrite",
  "取消／卸載": "Cancel / Unload",
  "取得音訊": "Get audio",
  "聲曲分離": "Separate stems",
  "伴奏二次分離": "Second instrumental pass",
  "反向相減": "Subtract audio",
  "主唱／和音": "Lead / Harmony",
  "建立基準": "Build reference",
  "可開始唱": "Ready to sing",
  "正在準備…": "Preparing…",
  "本機處理": "Local processing",
  "進階：純瀏覽器音訊存取診斷": "Advanced: browser-only audio access diagnostics",
  "歌曲音訊存取診斷": "Song audio access diagnostics",
  "實際測試瀏覽器能否讀取 YouTube 頁面與音訊串流。不使用轉檔網站或代理伺服器。": "Tests whether the browser can read the YouTube page and audio stream. No conversion sites or proxy servers are used.",
  "測試此網址的音訊存取": "Test audio access for this URL",
  "尚未測試。可播放影片 ≠ 可讀取影片音訊。": "Not tested. Being able to play a video does not mean its audio can be read.",
  "通過存取測試仍不代表已完成音訊解碼、人聲分離或旋律擷取。": "Passing this test does not mean decoding, vocal separation, or melody extraction is complete.",
  "本機歌單 · 點一首就載入": "Local playlist · Click a song to load",
  "重新整理歌曲庫": "Refresh library",
  "啟動本機工具後可查看已保存歌曲。": "Start the local tools to view saved songs.",
  "刪除會移除這首歌的本機基準與試聽音軌，不影響演唱成績。完整歌曲與不同長度的片段分開保存。": "Deleting removes the song’s local reference and preview stems, but keeps scores. Full songs and clips of different lengths are stored separately.",
  "調整音量與延時，不必重唱": "Adjust levels and timing without recording again",
  "選擇已保存的錄音": "Choose a saved recording",
  "尚無錄音": "No recordings yet",
  "試聽": "Preview",
  "只聽人聲": "Vocals only",
  "製作 MV": "Create music video",
  "下載": "Download",
  "後處理": "Post-production",
  "刪除": "Delete",
  "清除全部": "Clear all",
  "清除全部 MV": "Clear all music videos",
  "「試聽」播放完整成品；「只聽人聲」播放歌唱者音軌，不加入配樂／和音，沿用這筆錄音已保存的音量、延時與柔化設定。更改後製設定後需先重新合成，才能試聽新效果。": "“Preview” plays the finished mix. “Vocals only” plays the singer’s track with its saved level, timing, and smoothing, without backing or harmonies. Render again after changing production settings to hear the new result.",
  "翻唱 MV｜歌名・翻唱者・節奏畫面": "Cover music video | Song title · Singer · Animated spectrum",
  "使用選取的已保存錄音製作 MV。": "Create a music video from the selected saved recording.",
  "歌名": "Song title",
  "翻唱者": "Cover singer",
  "使用帶入時的成品音檔，保留已保存的音量、效果與剪輯；若剛調整後製設定，請先重新合成並選取新成品。輸出 1080p、30 fps MP4，頻譜隨音樂跳動；支援 1 秒至 10 分鐘。影片另存歌曲庫的「vedio」資料夾。": "Uses the imported finished audio with its saved levels, effects, and edits. If you just changed production settings, render again and select the new result first. Exports 1080p, 30 fps MP4 with an animated spectrum, from 1 second to 10 minutes. Videos save separately in the library’s “vedio” folder.",
  "開始製作翻唱 MV": "Create cover music video",
  "取消製作": "Cancel creation",
  "選取已保存錄音後按「製作 MV」。": "Select a saved recording and click “Create music video”.",
  "下載翻唱 MV（MP4）": "Download music video (MP4)",
  "點此展開": "Expand",
  "收合設定": "Collapse settings",
  "進階分離設定": "Advanced separation settings",
  "人聲音量": "Vocal volume",
  "加入配樂": "Include backing",
  "循環試聽": "Loop preview",
  "片段試聽／A、B 比較": "Clip preview / A/B comparison",
  "同一句循環播放 · 先聽效果再另存": "Loop the same phrase · Listen before saving a copy",
  "▶ 試聽 A": "▶ Preview A",
  "▶ 試聽 B": "▶ Preview B",
  "停止比較": "Stop comparison",
  "選取錄音後即可比較。": "Select a recording to compare.",
  "A／B 設定差異": "A/B setting differences",
  "選取錄音後顯示差異。": "Select a recording to see differences.",
  "不同的參數": "Different parameters",
  "A 設定": "A settings",
  "B 設定": "B settings",
  "隨調整即時更新，只列不同項目，包含尚未開啟的效果參數。修改後再按試聽，即可聽到新設定；剪輯與淡入淡出由 A／B 共用。": "Updates as you adjust settings. Only differences are listed, including parameters of disabled effects. Preview again to hear changes. Trimming and fades are shared by A and B.",
  "選同一句 → 調整效果 → 試聽 B → 切換 A／B": "Choose a phrase → Adjust effects → Preview B → Switch A/B",
  "試聽開始（秒）": "Preview start (seconds)",
  "試聽結束（秒）": "Preview end (seconds)",
  "人聲＋配樂": "Vocals + backing",
  "從目前播放位置取 10 秒": "Use 10 seconds from current position",
  "近似音量匹配（只影響比較）": "Approximate loudness matching (comparison only)",
  "A（藍色）、B（紫色）從相同設定開始，之後各自調整比較；預設編輯 B。點標籤會帶出該組所有數值，切換時自動暫存各自的調整。用上方大按鈕試聽 A／B，播放位置會接續。": "A (blue) and B (purple) start with the same settings, then can be adjusted independently. B is selected initially. Click a tab to load all its values; switching temporarily keeps each set’s edits. Use the large A/B preview buttons above to continue playback from the same position.",
  "A 組設定": "A settings",
  "尚未選取錄音": "No recording selected",
  "前往 A 後製設定": "Go to A production settings",
  "B 組設定": "B settings",
  "尚未記住設定": "No settings stored yet",
  "前往 B 後製設定": "Go to B production settings",
  "試聽與另存說明": "Preview and save information",
  "試聽以剪輯前完整錄音時間為準，每段最多 30 秒，暫不套用剪輯與淡入淡出。近似音量匹配會降低較大聲的一組，只影響比較。選中喜歡的 A 或 B，再用下方「重新合成」另存目前這組。剪輯與淡入淡出共用一份設定。切換錄音或重整會清除兩組暫存；首次準備需合成，之後可直接切換。": "Previews use full, untrimmed recording time, up to 30 seconds, without trimming or fades. Loudness matching reduces the louder version for comparison only. Select A or B, then “Render again” to save that version. Trimming and fades are shared. Switching recordings or reloading clears both temporary sets. The first preview requires rendering; subsequent switches are immediate.",
  "請選擇一筆錄音。": "Choose a recording.",
  "連接本機錄音目錄中…": "Connecting to local recordings…",
  "正在調整 B 組": "Editing B",
  "另存保留 A／B 各自設定。還原只重設目前組：原音、大廳殘響 20%、回聲 10%、音量 100%、校正 300 ms；剪輯保留。": "Saving preserves each set’s settings. Reset affects only the current set: original tone, hall reverb 20%, delay 10%, volume 100%, correction 300 ms. Trimming is preserved.",
  "還原 B 預設設定": "Reset B to defaults",
  "100% 沿用錄音時的音量平衡；往左降低、往右提高，0% 靜音。配樂與和音一起調整；只錄歌唱者的錄音無配樂可調。按「重新合成」後才會套用，再播放成品試聽；成品會保留目前設定，可繼續後製，每次都從原始歌聲重新計算。": "100% uses the recorded balance. Lower to reduce, raise to boost; 0% mutes. Backing and harmonies adjust together. Vocal-only recordings have no backing level. Click “Render again” to apply, then preview. Results retain settings for further editing; every render starts from the original vocals.",
  "歌聲延時校正（毫秒）": "Vocal timing correction (milliseconds)",
  "正值：歌聲晚到，將歌聲提前；負值：歌聲太早，將歌聲延後。填入總校正量，不是累加；配樂與和音不移動。初始值沿用本輪錄音校正值；舊錄音沿用當時保存的時間補償。": "Positive: vocals arrived late, move them earlier. Negative: vocals were early, move them later. Enter the total correction; it does not accumulate. Backing and harmonies stay fixed. Starts with this recording’s correction; older recordings use their saved time compensation.",
  "歌聲柔化": "Vocal smoothing",
  "關閉（預設，保留原音色）": "Off (default, original tone)",
  "輕度（柔和一點）": "Light (slightly softer)",
  "中度（明顯溫潤）": "Medium (noticeably warmer)",
  "強烈（厚柔、較暗）": "Strong (thick, soft, darker)",
  "音色效果：輕度稍微柔和，中度明顯降低尖亮感，強烈做出厚柔、較暗的音色；不是修復原音或消除呼吸聲。只處理歌唱者，配樂與和音不套用。選好後按「重新合成」另存，原錄音及評分不變；強烈會犧牲一些明亮感與咬字清晰度。比較強度時保持相同音量與延時；選取成品可再調整，柔化不會重複疊加。": "A tonal effect: light gently softens, medium reduces sharp brightness, and strong makes a thick, dark tone. It does not restore damaged audio or remove breaths. Affects the singer only. Render again to save a copy; the original recording and score remain. Strong smoothing reduces brightness and articulation. Compare at the same volume and timing. Further edits recalculate without stacking smoothing.",
  "人聲進階後製": "Advanced vocal production",
  "局部音量 · EQ · 動態壓縮 · 殘響": "Region volume · EQ · Compression · Reverb",
  "只處理歌唱者": "Singer only",
  "新版錄製的音檔，A／B 後製起始設定皆為大廳殘響 20%＋回聲 10%；舊錄音沿用原有設定。可先用片段試聽比較，滿意後按「重新合成」另存；每次從原始歌聲重算，效果不會疊加。配樂／和音不套用這些效果。": "New recordings start A and B with hall reverb at 20% and delay at 10%; older recordings retain their settings. Compare a short clip, then render again to save a copy. Each render starts from original vocals so effects do not stack. Backing and harmonies are unaffected.",
  "人聲清理與音準修正": "Vocal cleanup and pitch correction",
  "降噪 · 齒音 · 呼吸聲 · 音準（全部關閉）": "Noise · Sibilance · Breaths · Pitch (all off)",
  "只處理原始歌聲，A／B 各自保存；情緒和空間情境不會更動這些設定。0% 關閉。先用同一小段比較，滿意再重新合成另存；處理時會顯示階段與進度。": "Processes original vocals only; A and B keep separate settings. Mood and space presets do not change these controls. 0% disables an effect. Compare a short clip, then render a copy. Processing stages and progress are shown.",
  "降噪強度": "Noise reduction",
  "0%（關閉）": "0% (off)",
  "自動從較安靜、無人聲的空檔估計底噪，降低風扇、冷氣等持續雜音。可先試 25～40%；太強可能出現水聲。若全段沒有可用空檔，會略過降噪。": "Estimates background noise from quiet, unvoiced gaps to reduce steady fans or air conditioning. Try 25–40%; high strength may create watery artifacts. Skipped if no usable gaps exist.",
  "齒音抑制": "De-esser",
  "在高頻齒音突出時動態降低該頻段，保留低頻歌聲。可先試 30%；太強會讓咬字變鈍。": "Dynamically reduces prominent high-frequency sibilance while keeping lower vocal frequencies. Try 30%; too much can dull articulation.",
  "齒音偵測頻率": "Sibilance detection frequency",
  "3～10 kHz；數字降低會處理較低的刺耳音，升高偏向細尖的「ㄙ」聲。強度 0% 時不處理。": "3–10 kHz. Lower values target lower harshness; higher values target thin “s” sounds. No processing at 0% strength.",
  "呼吸聲降低": "Breath reduction",
  "自動找演唱附近較短、無音高的換氣聲並降低音量，保留自然氣息。可先試 30%。屬聲學偵測，可能漏判或誤判氣音、子音；必要時用局部音量微調。": "Detects short, unpitched breaths near singing and lowers them while preserving natural breathing. Try 30%. Detection may miss or confuse breathy vocals and consonants; use region volume when needed.",
  "音準修正 · 保持時間位置": "Pitch correction · Preserve timing",
  "修正強度": "Correction strength",
  "只修正可辨識的有音高歌聲，不移動整首時間或配樂。先試 30～50%；100% 較貼近目標音高，仍受偵測、平滑與修正範圍限制。": "Corrects identifiable pitched vocals without moving the song or backing. Try 30–50%. 100% follows the target more closely, subject to detection, smoothing, and correction limits.",
  "修正目標": "Correction target",
  "最近半音（預設）": "Nearest semitone (default)",
  "原唱基準（保留演唱八度）": "Original vocal reference (preserve singing octave)",
  "最近半音修正小幅偏音，不知道歌曲旋律。原唱基準使用這次錄音保存的旋律及時間資料，保留高／低八度；休息、不計分區間和偏離超過 2 個半音的地方不強拉。": "Nearest-semitone mode fixes small pitch errors without knowing the melody. Reference mode uses the recording’s saved melody and timing while preserving octave differences. It avoids forcing rests, masked regions, or deviations over two semitones.",
  "修正速度": "Correction speed",
  "20～500 ms 是靠近目標音高的速度，不是播放延遲。小值修正更快，大值較緩。第一次可用 120 ms。": "20–500 ms controls how quickly pitch approaches the target, not playback latency. Lower is faster; higher is gentler. Try 120 ms first.",
  "保留顫音": "Preserve vibrato",
  "開啟（預設，保留自然起伏）": "On (default, preserve natural variation)",
  "關閉（較貼近目標）": "Off (closer to target)",
  "開啟時主要修正平均偏音，保留較快的音高起伏。滑音、氣音與複雜唱法仍需試聽；這是音訊修正，不會改寫原始演唱或評分。": "When enabled, mainly corrects average pitch drift while keeping faster variations. Listen carefully to slides, breathy vocals, and complex phrasing. Audio correction does not rewrite the original performance or score.",
  "人聲情緒 · 選取即套用目前組別": "Vocal mood · Applies to the current set",
  "自訂音色": "Custom tone",
  "預設「原音」，不額外調整音色。10 種情緒會帶入 EQ、柔化與壓縮，可再微調；不改變唱法與音高。殘響、回聲、音量、校正、剪輯及另一組設定保留。原音不等於關閉所有後製；想聽乾聲，另將殘響與回聲調為 0%。已有後製的錄音沿用保存的音色。按「試聽 A／B」比較，滿意後「重新合成」另存。": "Defaults to “Original” with no extra tonal changes. Ten moods set EQ, smoothing, and compression for further adjustment; they do not change phrasing or pitch. Reverb, delay, volume, timing, trim, and the other set are preserved. “Original” does not disable all effects; set reverb and delay to 0% for dry vocals. Existing recordings retain saved tone settings. Compare A/B, then render a copy.",
  "情境預設 · 選取即套用目前組別": "Space preset · Applies to the current set",
  "自訂空間效果": "Custom space effects",
  "一起帶入殘響音量、空間、尾音、預延遲、明亮度、寬度及回聲設定，之後可微調；另一組、EQ、壓縮、柔化、音量、校正與剪輯保留。局部區段的數值保留，空間音色與回聲間隔仍沿用上方。按「試聽 A／B」聽取新效果，按「重新合成」才另存。夢幻回聲以 600 ms 起步，可依歌曲節奏調整。": "Sets reverb level, space, decay, pre-delay, brightness, width, and delay, all adjustable afterward. Preserves the other set, EQ, compression, smoothing, levels, timing, and trim. Region values remain; space tone and delay interval still use the global settings. Preview A/B to listen, then render to save. Dreamy delay starts at 600 ms; adjust it to the song’s rhythm.",
  "局部音量": "Region volume",
  "以套用延時後、尚未剪輯的完整錄音秒數設定，不是 YouTube 時間。「從目前播放位置」會自動換算已剪輯成品的位置。100% 不變、0% 靜音，區段不可重疊。變更延時後請重新核對位置；殘響會自然延伸到區段外。": "Use full recording seconds after timing correction and before trimming, not YouTube time. “From current position” converts trimmed playback time automatically. 100% is unchanged; 0% mutes. Regions cannot overlap. Recheck positions after timing changes. Reverb tails may extend beyond regions.",
  "新增區段（從目前播放位置）": "Add region (from current position)",
  "EQ 音色": "EQ tone",
  "低頻 · 厚度": "Low · Body",
  "中頻 · 存在感": "Mid · Presence",
  "高頻 · 明亮度": "High · Brightness",
  "0 dB 不變；往左減少、往右增加。先從 ±2～3 dB 比較。": "0 dB is unchanged. Lower to cut, raise to boost. Start with ±2–3 dB.",
  "動態壓縮 · 穩定大小聲": "Compression · Balance dynamics",
  "關閉": "Off",
  "輕度 · 保留較多起伏": "Light · Keep more dynamics",
  "中度 · 更穩定": "Medium · More consistent",
  "殘響音量": "Reverb level",
  "新後製預設大廳 20%，已有設定則沿用；0% 關閉，最高 100%。可用 20%、40%、60% 比較效果。數字越高，加入的殘響越明顯；原本人聲仍保留。按「重新合成」另存後試聽。": "New production defaults to hall at 20%; existing settings are retained. 0% disables reverb, up to 100%. Compare 20%, 40%, and 60%. Higher values add more reverb while keeping the dry vocals. Render a copy, then preview.",
  "空間類型": "Space type",
  "原版（沿用舊殘響）": "Legacy (original reverb)",
  "房間 · 緊密、較短": "Room · Tight, short",
  "大廳 · 寬廣、較長": "Hall · Spacious, long",
  "板式 · 明亮、密集": "Plate · Bright, dense",
  "錄音室 · 貼近、短尾": "Studio · Close, short tail",
  "小室 · 溫暖、厚實": "Chamber · Warm, full",
  "教堂 · 柔暗、莊嚴長尾": "Church · Dark, solemn, long tail",
  "體育館 · 開闊、遠距": "Stadium · Open, distant",
  "隧道 · 規律、連續反射": "Tunnel · Regular repeated reflections",
  "洞穴 · 低沉、不規則反射": "Cave · Deep, irregular reflections",
  "浴室 · 明亮、近牆反射": "Bathroom · Bright, close reflections",
  "夢幻空間 · 漸起、漂浮長尾": "Dream space · Swelling, floating tail",
  "寬廣、柔和，尾音逐漸鋪開，適合抒情歌。": "Wide and soft with a gradually spreading tail, suitable for ballads.",
  "尾音長度": "Decay length",
  "1.8 秒": "1.8 seconds",
  "0.2～10 秒，控制殘響尾巴延續的長度。數字越大，唱完後的餘韻越長；越小則收得越快。可用 0.8、2、5 秒比較。想保留完整尾音，剪輯的「保留結束」請留白。": "0.2–10 seconds controls the reverb tail. Higher values sustain longer; lower values end sooner. Compare 0.8, 2, and 5 seconds. Leave “Keep until” blank to retain the full tail.",
  "預延遲": "Pre-delay",
  "0～500 ms，控制人聲發出後，隔多久開始出現殘響。0 ms 立即開始；數字越大，原聲與殘響的間隔越明顯。可用 15、80、200 ms 比較；500 ms 就是半秒。不會移動原本人聲或配樂，也不是歌聲延時校正。": "0–500 ms sets the gap between vocals and reverb. 0 ms starts immediately; higher values separate them more. Compare 15, 80, and 200 ms; 500 ms is half a second. Does not move dry vocals or backing and is separate from vocal timing correction.",
  "殘響明亮度": "Reverb brightness",
  "負值讓尾音柔暗、正值讓尾音明亮；0 沿用目前空間音色。只改殘響，不改原本人聲。": "Negative values darken the tail; positive values brighten it. 0 keeps the space’s tone. Affects reverb only, not dry vocals.",
  "殘響立體寬度": "Reverb stereo width",
  "0% 集中在中央，100% 保留完整左右空間感。戴耳機比較較明顯；原本人聲位置不變。": "0% centers the reverb; 100% keeps full stereo space. Headphones make the difference clearer. Dry vocal position stays unchanged.",
  "殘響音量大於 0% 時才會聽到這些效果。單換「空間類型」只帶入尾音與預延遲建議值，其餘數值保留；上方「情境預設」才會帶入整組空間與回聲設定。「原版」預設為 0.8 秒／15 ms。每次先改一項，再用片段試聽比較。": "These controls are audible only above 0% reverb. Changing the space type sets suggested decay and pre-delay only; the space preset above sets the whole reverb and delay group. Legacy defaults to 0.8 seconds / 15 ms. Change one control at a time and compare a clip.",
  "回聲 Delay": "Delay",
  "回聲音量": "Delay level",
  "0% 關閉；提高後，能聽到句子或字音重複出現。可從 15% 開始。": "0% disables delay. Raising it repeats phrases or syllables. Start around 15%.",
  "重複間隔": "Repeat interval",
  "80～1000 ms。小值像緊貼人聲的重影，大值像一句接一句的回應。": "80–1000 ms. Short intervals create a close double; long intervals create a phrase-like response.",
  "重複次數": "Repeat count",
  "3 次": "3 repeats",
  "最多 8 次；間隔和次數一起決定回聲延伸多長。": "Up to 8 repeats. Interval and count together determine how long the delay lasts.",
  "每次保留音量": "Level retained per repeat",
  "後一次是前一次的幾成。40% 會很快變小；80% 衰減較慢；0% 只留下第一次回聲。": "Each repeat’s level relative to the previous one. 40% fades quickly; 80% fades slowly; 0% leaves only the first echo.",
  "回聲位置": "Delay position",
  "中央": "Center",
  "左右交替": "Ping-pong",
  "左右交替讓每次回聲輪流出現在左右兩邊，原本人聲保持原位。": "Ping-pong alternates repeats between left and right. Dry vocals stay in place.",
  "局部效果": "Region effects",
  "區段內用指定的殘響音量、尾音長度與回聲音量，區段外沿用上方設定。可做主歌淡、副歌濃、最後一句長尾音。秒數以剪輯前完整錄音為準，區段不可重疊；已產生的尾音會自然延伸到區段外，其餘音色與回聲間隔沿用上方設定。": "Use region-specific reverb level, decay, and delay level; outside regions, global values apply. Try subtle verses, fuller choruses, or a long final tail. Times refer to the full untrimmed recording; regions cannot overlap. Existing tails continue naturally beyond boundaries. Other tone settings and delay interval remain global.",
  "新增效果區段（目前位置）": "Add effect region (current position)",
  "重設全部人聲效果": "Reset all vocal effects",
  "剪輯與淡入淡出": "Trim and fades",
  "A／B 共用 · 保留想要的段落 · 人聲與配樂一起平順收尾": "Shared by A/B · Keep the section you want · Fade vocals and backing together",
  "套用到完整混音成品": "Applies to the complete mix",
  "保留開始（秒）": "Keep from (seconds)",
  "用目前播放位置": "Use current position",
  "保留結束（秒，可留白）": "Keep until (seconds, optional)",
  "開頭淡入（秒）": "Fade in (seconds)",
  "結尾淡出（秒）": "Fade out (seconds)",
  "淡入從保留段落的開頭開始，淡出在結尾結束；0 秒關閉，兩者合計不可超過保留長度。指定結束點會一起裁掉其後的殘響。每次從完整來源重算，不累加剪輯；重設後可恢復全段。原始歌聲及評分資料保留，重新評分仍依完整原始演唱。": "Fade-in starts at the kept section’s beginning; fade-out ends at its end. 0 disables a fade. Their total cannot exceed the kept duration. An explicit end also cuts later reverb. Each edit starts from the full source; trimming does not accumulate. Reset to restore the full audio. Original vocals and scoring data remain; rescoring uses the complete original performance.",
  "重設剪輯與淡入淡出": "Reset trim and fades",
  "片段試聽目前設定": "Preview current settings on a clip",
  "重新合成（音量／延時／音色／剪輯）": "Render again (levels / timing / tone / trim)",
  "轉 MP3 並下載": "Convert to MP3 and download",
  "重新合成會另存一筆，並保存獨立的原始歌聲與後製資料，可再次編輯或轉 MP3；原錄音保留。配樂／和音需歌曲庫中的同版本音軌。舊成品或單獨匯出的 WAV／MP3 若沒有原始歌聲及時間資料，無法直接分軌後製。選「不保存錄音」時不保留後處理資料。": "Rendering saves a new recording with separate original vocals and production data for more editing or MP3 export. The original is kept. Backing and harmonies require matching library stems. Older mixes or standalone WAV / MP3 exports without original vocals and timing cannot be edited as separate tracks. “Do not save recordings” retains no production data.",
  "整首演唱與已保存成品": "Whole-song takes and saved results",
  "此清單顯示整首演唱與明確保存的完整成品；分段錄音請在分段區挑選、試聽或刪除。停止錄音後自動保存於歌曲庫下的「錄音」目錄；Chrome 與 Edge 連到同一本機工具即可共用。既有瀏覽器錄音會自動搬存，成功確認後才清除舊副本；未搬存成功仍保留在瀏覽器。直接按 YouTube 播放只評分；要錄音請按「從頭開始唱」。": "This list shows whole-song takes and explicitly saved finished mixes. Manage segment takes in the segment area. Recordings save locally under the library’s recording folder; Chrome and Edge share them through the same local tools. Existing browser recordings migrate automatically, and old copies are removed only after successful transfer. Failed transfers remain in the browser. Playing YouTube directly scores only; click “Sing from the start” to record.",
  "重新整理／搬存錄音": "Refresh / Migrate recordings",
  "刪除此清單錄音": "Delete recordings in this list",
  "看節拍，調延遲": "Watch the beat, adjust timing",
  "節拍燈 · 時間補償 · 五音測試": "Beat light · Time compensation · Five-note test",
  "手動節拍速度": "Manual tempo",
  "啟動節拍燈": "Start beat light",
  "手動節拍燈；基準建立後，若能辨識節奏，改用自動估計拍點。": "Manual beat light. After a reference is ready, automatically estimated beats are used when available.",
  "手動時間補償": "Manual time compensation",
  "預設＋200 ms：歌手聲音提前 200 ms 比對，例如 10.200 秒的歌聲對照 10.000 秒的歌曲基準。只調整評分時間，不改變播放器或錄音音檔；錄音校正在下方另設。": "Default +200 ms compares your voice 200 ms earlier: for example, vocals at 10.200 seconds against the reference at 10.000 seconds. Affects scoring time only, not playback or audio files. Recording correction is set separately below.",
  "Do Re Mi Fa Sol 五音延遲測試（選用）": "Do Re Mi Fa Sol latency test (optional)",
  "先開啟麥克風。測試會播放五個音，畫面同步提示；完成後可選擇套用建議值。": "Enable the microphone first. Five notes play with visual cues. Afterward, you can apply the suggested value.",
  "測試方式": "Test method",
  "跟著五音唱（包含人的反應時間）": "Sing along (includes human reaction time)",
  "耳機／喇叭靠近麥克風（不用唱）": "Headphones / speakers near the mic (no singing)",
  "跟唱時戴耳機；回收測試則讓麥克風聽到耳機或喇叭的聲音。回收結果是本頁播放到收音的往返延遲，不保證等於 YouTube 的延遲。": "Wear headphones when singing along. For loopback, let the microphone hear the headphones or speakers. The result is this page’s playback-to-input round-trip latency, which may differ from YouTube latency.",
  "測試音域": "Test range",
  "中音 C4–G4": "Mid C4–G4",
  "低音 C3–G3": "Low C3–G3",
  "播放五音並測試": "Play five notes and test",
  "停止測試": "Stop test",
  "套用建議補償": "Apply suggested compensation",
  "選用測試，不會錄音或保存聲音，也不會自動改動補償。": "Optional test. Does not record or save audio and does not change compensation automatically.",
  "藍牙、有線、USB 與電腦內建麥克風請分別測試。更換裝置後，補償值會回到預設＋200 ms；這是起始設定，並非裝置實測延遲。": "Test Bluetooth, wired, USB, and built-in microphones separately. Changing devices resets compensation to +200 ms. This is a starting value, not measured device latency.",
  "練習評分": "Practice scoring",
  "評分設定": "Scoring settings",
  "難度 · 音域比對 · 錄音重評": "Difficulty · Octave matching · Rescore recordings",
  "評分難度": "Scoring difficulty",
  "標準（原有規則）": "Standard (original rules)",
  "嚴格（精準練習）": "Strict (precision practice)",
  "寬鬆（輕鬆練唱，預設）": "Relaxed (casual practice, default)",
  "音域比對": "Octave matching",
  "允許高／低八度（適合不同音域）": "Allow octave differences (for different vocal ranges)",
  "嚴格原調（與原唱相同音高）": "Exact pitch (same pitch as original singer)",
  "放寬八度差不會改變 YouTube 伴奏。其他音高偏差仍會扣分；演唱開始後固定本次模式。": "Allowing octave differences does not change the YouTube backing. Other pitch errors still reduce the score. This mode is fixed once a round starts.",
  "評分範圍": "Scoring range",
  "只比已演唱範圍（開始到停止，預設）": "Performed range only (start to stop, default)",
  "整首歌曲（依已載入的分析範圍）": "Whole song (loaded analysis range)",
  "選「已演唱範圍」時，後面尚未唱到的部分不扣分；這段期間的漏唱、跳過仍計入。每輪開始後固定，重唱時可重新選擇。": "“Performed range” does not penalize the remainder you have not reached, but missed or skipped parts within the performed range still count. Fixed for each round; choose again before the next take.",
  "錄音重新評分": "Rescore recording",
  "重新評分使用的歌曲基準": "Reference for rescoring",
  "錄音當時的基準（預設）": "Reference saved with recording (default)",
  "目前已載入的歌曲基準（比較 RMVPE／其他版本）": "Currently loaded reference (compare RMVPE / other versions)",
  "重新評分難度": "Rescoring difficulty",
  "標準": "Standard",
  "嚴格": "Strict",
  "寬鬆（預設）": "Relaxed (default)",
  "選取錄音後預設為寬鬆；可在此調整，按下方「調延時重新評分」。遮罩、八度及評分範圍仍沿用錄音當時設定。": "Defaults to relaxed after selecting a recording. Adjust here, then click “Adjust timing and rescore”. Masks, octave matching, and scoring range use the recording’s original settings.",
  "調延時重新評分": "Adjust timing and rescore",
  "下載這筆評分診斷": "Download scoring diagnostics",
  "包含這筆原始錄音、乾淨歌聲、時間位置與評分基準；只下載到本機，供檢查對齊問題。": "Includes the original recording, clean vocals, timing, and scoring reference. Downloaded locally to inspect alignment issues.",
  "選擇已保存的錄音後，可調整基準與難度重新評分。": "Select a saved recording to change the reference and difficulty for rescoring.",
  "錄音設定": "Recording settings",
  "錄音內容 · 歌聲延時": "Recording content · Vocal timing",
  "演唱錄音儲存": "Save performance recordings",
  "歌唱者": "Singer",
  "歌唱者＋配樂／和音（預設）": "Singer + backing / harmonies (default)",
  "不保存錄音": "Do not save recordings",
  "新錄音使用同步無損 WAV，保留原始歌聲供後製，檔案會比壓縮錄音大；每輪最多 30 分鐘。": "New recordings use synchronized lossless WAV and retain original vocals for production. Files are larger than compressed audio. Maximum 30 minutes per take.",
  "按「從頭開始唱」，影片開始播放時同步錄音；停止收音、結束並結算或影片播完時保存。暫停／緩衝時暫停錄音。依已載入版本自動選軌：兩軌版本加入伴奏；四軌版本加入伴奏＋和音，不加入原唱主唱或全部人聲。超過音軌長度後只錄歌唱者。請戴耳機，避免原唱從喇叭漏入麥克風。": "Click “Sing from the start” to record when video playback starts. Saves when you stop input, finish scoring, or reach the end. Pausing or buffering pauses recording. Two-stem versions add instrumental; four-stem versions add instrumental and harmonies, excluding lead or full original vocals. Beyond the backing length, only the singer is recorded. Wear headphones to avoid leakage.",
  "錄音歌聲延時校正（毫秒）": "Recorded vocal timing correction (milliseconds)",
  "預設＋300 ms：停止錄音後，成品中的歌聲往前移 300 ms，配樂與和音不移動。填入總校正量，不會累加。原始歌聲保留供後處理；即時評分仍使用上方時間補償設定。": "Default +300 ms moves vocals 300 ms earlier in the finished recording after stopping; backing and harmonies stay fixed. Enter the total correction; it does not accumulate. Original vocals remain for production. Live scoring uses the separate time compensation setting above.",
  "暫停與緩衝不計分。漏唱與跳過的段落會降低分數；「整首歌曲」模式也會計入提前結束的剩餘段落。可在中途按「結束並結算」，或等影片播完自動結算。進拍分數依旋律起音估計，不是專業聲樂評鑑。": "Pauses and buffering are not scored. Missed or skipped sections reduce scores; whole-song mode also counts the remaining section when ending early. Finish manually or wait for automatic scoring at the end. Timing scores estimate melodic onsets and are not professional vocal assessments.",
  "分數紀錄 · 勾選清除": "Score history · Select to clear",
  "全選": "Select all",
  "清除勾選紀錄": "Clear selected scores",
  "全部清除": "Clear everything",
  "只清除分數，不刪除演唱錄音或歌曲。": "Clears scores only, not recordings or songs.",
  "本機測試用途 · 不得商用": "Local testing only · Non-commercial",
  "本工具僅供本機測試與個人非商業練習。請尊重著作權，只處理您有權使用或已取得授權的內容，不得未經授權下載、複製或散布。本工具不提供歌曲內容或使用授權；使用者應自行確認其使用符合相關法規與平台規範。自動分析與評分僅供測試參考，不保證準確性。": "This tool is for local testing and personal non-commercial practice only. Respect copyright and process only content you own or are authorized to use. Do not download, copy, or distribute without permission. This tool provides neither song content nor usage rights; you are responsible for compliance with applicable laws and platform rules. Automated analysis and scoring are experimental and may be inaccurate.",
  "唱錄系統 / Local-first experiment": "Sing & Record / Local-first experiment",
  "麥克風 → 本機音高分析 → 畫面": "Microphone → Local pitch analysis → Display",
  "頁面區段導覽": "Page sections",
  "錄唱下一步": "Next recording step",
  "選擇資料夾，或貼上完整路徑": "Choose a folder or paste its full path",
  "本機音檔播放器": "Local audio player",
  "影片播放與分段": "Video playback and segments",
  "演唱控制與分數": "Singing controls and score",
  "待確認整首錄音試聽": "Pending whole-song preview",
  "歌曲段落與可拖曳分界": "Song segments and draggable boundaries",
  "本段錄音試聽": "Segment recording preview",
  "麥克風音量": "Microphone level",
  "最近八秒的麥克風音高曲線": "Microphone pitch curve over the last eight seconds",
  "例如 0:32.5": "e.g. 0:32.5",
  "例如 0:48": "e.g. 0:48",
  "本機歌曲庫": "Local song library",
  "選取錄音的操作": "Selected recording actions",
  "輸入歌名": "Enter song title",
  "輸入翻唱者名稱": "Enter cover singer’s name",
  "翻唱 MV 製作進度": "Music video creation progress",
  "切換比較版本": "Switch comparison version",
  "A／B 設定": "A/B settings",
  "切換正在編輯的設定": "Switch settings being edited",
  "還原目前組別的系統預設音量、延時與效果；另一組、剪輯與已保存錄音保留": "Restore system default levels, timing, and effects for this set. Keep the other set, trim, and saved recordings.",
  "至末尾，含殘響尾音": "To the end, including reverb tail",
  "四拍節拍燈": "Four-beat light",
  "使用限制與免責聲明": "Usage restrictions and disclaimer",
  "播放追蹤連線中…（只記錄狀態，不錄音）": "Connecting playback tracking… (status only, no audio recording)",
  "播放追蹤未連線：尚未收到紀錄，請確認本機工具與本機網路權限。": "Playback tracking is offline: no logs received. Check local tools and local network permissions.",
  "本機工具尚未支援追蹤": "The local tools do not support tracking yet",
  "桌機收音環境就緒。可測試麥克風與播放器；未取得歌曲基準前不計分。": "Desktop input is ready. Test the microphone and player; scoring requires a song reference.",
  "無法開啟麥克風。請用桌機 Chrome／Edge 開啟 HTTPS 網址，並確認瀏覽器有收音權限。": "Cannot enable microphone. Use desktop Chrome / Edge over HTTPS and allow microphone access.",
  "歌聲輸出已關閉，麥克風仍持續收音。": "Vocal monitoring is off; microphone input continues.",
  "正在啟動低延遲歌聲輸出…": "Starting low-latency vocal monitoring…",
  "歌聲輸出中斷：": "Vocal monitoring interrupted:",
  "本機歌聲直送喇叭中 ·": "Native direct vocal monitoring ·",
  "歌聲輸出已暫停，請確認喇叭後重新開啟。": "Vocal monitoring paused. Check your speakers and enable it again.",
  "低延遲歌聲輸出中 ·": "Low-latency vocal monitoring ·",
  "歌聲輸出未獲允許，請確認瀏覽器的音訊播放與輸出裝置權限後重試。": "Vocal output was not allowed. Check browser playback and output-device permissions, then retry.",
  "找不到選取的喇叭，請重新整理並選擇輸出裝置。": "Selected speakers not found. Refresh and choose an output device.",
  "歌聲輸出失敗：": "Vocal monitoring failed:",
  "喇叭": "Speaker",
  "原輸出裝置已離線，請重新選擇喇叭並開啟歌聲輸出。": "The output device disconnected. Choose speakers again and enable monitoring.",
  "此瀏覽器使用系統預設喇叭；開啟麥克風後可勾選歌聲輸出。": "This browser uses the system default speakers. Enable the microphone, then turn on vocal monitoring.",
  "無法取得喇叭清單；可先使用系統預設喇叭。": "Cannot list speakers. Try the system default speakers.",
  "YouTube 播放器程式（第二段）載入失敗，請按「載入影片」重試。歌曲基準仍保留在本機。": "The second YouTube player script failed to load. Click “Load video” to retry. Your song reference is still stored locally.",
  "YouTube 播放器程式載入逾時，請按「載入影片」重試。這不是本機歌曲基準或安裝失敗。": "YouTube player script timed out. Click “Load video” to retry. Your local reference and installation are unaffected.",
  "YouTube 播放器入口程式連線失敗，請按「載入影片」重試。歌曲基準仍保留在本機。": "The YouTube player entry script failed to connect. Click “Load video” to retry. Your reference remains local.",
  "YouTube 播放器初始化逾時，請按「載入影片」重試；不需要重新安裝本機工具。": "YouTube player initialization timed out. Click “Load video” again; no need to reinstall local tools.",
  "請按影片上的播放按鈕。": "Click the play button on the video.",
  "尚未開始": "Not started",
  "影片結束": "Video ended",
  "播放中": "Playing",
  "暫停": "Paused",
  "緩衝中": "Buffering",
  "已就緒": "Ready",
  "播放器狀態變更": "Player state changed",
  "請直接點影片上的播放按鈕。": "Click the play button directly on the video.",
  "請輸入有效的 YouTube 網址，或先選擇本機 MV／音檔。": "Enter a valid YouTube URL, or choose a local video / audio file first.",
  "正在載入本機媒體…": "Loading local media…",
  "正在載入 YouTube 播放器…": "Loading YouTube player…",
  "本機媒體載入失敗，請重新載入。": "Local media failed to load. Please reload it.",
  "本機音檔": "Local audio",
  "影片已切換，請在播放器內按播放。": "Video changed. Press play inside the player.",
  "正在唱歌、錄音或準備歌曲，網址不會自動切換；結束後請按「載入影片」。": "Singing, recording, or song preparation is in progress, so the link will not switch automatically. Click “Load video” when you finish.",
  "瀏覽器未提供可讀取的串流。": "The browser did not provide a readable stream.",
  "回應超過測試大小上限。": "Response exceeds the test size limit.",
  "請先填入有效的 YouTube 影片網址。": "Enter a valid YouTube video URL first.",
  "影片頁面": "Video page",
  "本機瀏覽器直接讀取 YouTube 頁面…": "Reading the YouTube page directly in the local browser…",
  "影片頁面可讀取。": "Video page is readable.",
  "未找到可直接讀取的音訊 URL。可能需要播放器簽章、登入或頁面結構不同；原型未實作這些處理。": "No directly readable audio URL found. Player signatures, sign-in, or a different page structure may be required; this prototype does not handle these.",
  "不是預期的 HTTPS YouTube 媒體來源。": "Not an expected HTTPS YouTube media source.",
  "音訊串流": "Audio stream",
  "讀取最多 128 KiB 音訊串流…": "Reading up to 128 KiB of audio…",
  "音訊回應為空。": "Audio response is empty.",
  "這只證明串流可讀取；尚未解碼、人聲分離或建立基準。": "This confirms stream access only. Decoding, vocal separation, and reference building have not been done.",
  "逾時或測試已中止。": "Timed out or test canceled.",
  "瀏覽器拒絕讀取；可能是 CORS、網路或內容阻擋，此訊息無法區分原因。": "The browser refused access. CORS, network issues, or content blocking may be responsible; this message cannot distinguish them.",
  "未取得可分析音訊，不能建立基準或評分。嵌入播放仍可獨立測試。": "No analyzable audio was obtained, so a reference and scores cannot be created. Embedded playback can still be tested separately.",
  "未提供，不能當作 0 ms": "Unavailable; must not be treated as 0 ms",
  "收音已停止，麥克風已釋放；錄音結果請查看下方錄音狀態。": "Input stopped and microphone released. See the recording status below for saved results.",
  "收音已停止。": "Input stopped.",
  "正在啟動本機麥克風，請允許 Python 收音…": "Starting native microphone capture. Allow Python to access the mic…",
  "請允許網站使用麥克風…": "Allow this site to use your microphone…",
  "瀏覽器預設麥克風": "Browser default microphone",
  "（本機相容收音）": "(native capture)",
  "僅分析，不開啟喇叭輸出": "Analysis only; no speaker output",
  "瀏覽器預設（不支援分析專用輸出）": "Browser default (analysis-only output unavailable)",
  "未知": "Unknown",
  "麥克風中斷，請重新開啟。": "Microphone disconnected. Enable it again.",
  "收音暫時中斷，目前音高不可用。": "Input temporarily interrupted. Pitch is unavailable.",
  "收音已恢復。": "Input restored.",
  "音訊處理暫停，請停止後重新開啟。": "Audio processing suspended. Stop and enable input again.",
  "● 收音中": "● Microphone active",
  "持續唱「啊」試試。單獨測試麥克風不保存；按「從頭開始唱」依錄音選項保存。": "Try sustaining “ah”. Testing the mic alone does not save audio. “Sing from the start” saves according to your recording settings.",
  "麥克風未獲允許。請點網址列的網站權限圖示，允許麥克風後再重試。": "Microphone permission denied. Open site permissions in the address bar, allow the microphone, then retry.",
  "找不到麥克風，請檢查裝置。": "No microphone found. Check your device.",
  "未偵測到穩定音高": "No stable pitch detected",
  "停止節拍燈": "Stop beat light",
  "裝置已變更，補償已回到預設＋200 ms。請重新開啟收音並校正。": "Device changed. Compensation reset to +200 ms. Enable input again and calibrate.",
  "頁面已離開前景，收音已停止。請重新開啟。": "Page left the foreground; input stopped. Enable it again.",
  "已切換收音方式，請重新選擇麥克風並開啟。": "Input mode changed. Select a microphone and enable it again.",
  "已切換麥克風，補償已回到預設＋200 ms。請按開啟麥克風使用新裝置。": "Microphone changed. Compensation reset to +200 ms. Enable the microphone to use the new device.",
  "Python 環境": "Python environment",
  "正在檢查這台電腦的本機工具…": "Checking local tools on this computer…",
  "本機工具回應失敗。": "Local tools returned an error.",
  "本機工具版本不相容，請重新下載工具包。": "Local tools version is incompatible. Download the tools again.",
  "本機工具需要更新，請重新下載工具包，停止舊工具後再啟動。": "Local tools need updating. Download the new package, stop the old tools, then start the new ones.",
  "已連線，但本機安裝尚未完整。": "Connected, but local installation is incomplete.",
  "缺少或無法使用：": "Missing or unavailable:",
  "請重新執行安裝腳本": "Run the installation script again",
  "。請參考下方安裝指引。": ". See the installation guide below.",
  "✓ 本機工具已啟動，音訊處理環境已就緒。": "✓ Local tools running; audio processing is ready.",
  "yt-dlp、FFmpeg 與 Demucs 已找到。音訊在你的電腦處理；目前此按鈕只檢查環境，不會下載或錄音。": "yt-dlp, FFmpeg, and Demucs found. Audio is processed on your computer. This button only checks the environment; it does not download or record audio.",
  "尚未連上本機工具，無法判定是否已安裝。": "Not connected to local tools; installation status is unknown.",
  "連線逾時。若工具已安裝，請啟動 start-local.ps1，並允許瀏覽器的本機網路存取後重試。": "Connection timed out. If installed, run start-local.ps1 and allow local network access in your browser, then retry.",
  "可能尚未啟動、尚未安裝，或瀏覽器阻擋本機連線。已安裝者請先執行 start-local.ps1；首次使用請看安裝指引。": "Tools may not be started or installed, or the browser may block local access. If installed, run start-local.ps1. For first use, see the installation guide.",
  "無法連線本機工具。": "Cannot connect to local tools.",
  "請先更新並重新啟動本機工具，才能使用本機相容收音。": "Update and restart local tools to use native capture.",
  "無法取得本機麥克風清單。": "Cannot list local microphones.",
  "本機收音啟動逾時。": "Native capture startup timed out.",
  "已取消": "Canceled",
  "本機收音音訊執行緒中斷，請重新開啟收音。": "Native audio thread interrupted. Enable input again.",
  "本機音訊背景傳輸中斷，請重新開啟收音。": "Native audio background transfer interrupted. Enable input again.",
  "本機收音取樣率不相容。": "Native capture sample rate is incompatible.",
  "本機收音已停止。": "Native capture stopped.",
  "歌聲輸出取樣率不相容。": "Vocal output sample rate is incompatible.",
  "本機喇叭控制失敗。": "Native speaker control failed.",
  "無法取得喇叭清單。": "Cannot list speakers.",
  "本機喇叭已停止。": "Native speaker output stopped.",
  "本機收音無法啟動。": "Cannot start native capture.",
  "本機收音連線已中斷。": "Native capture connection lost.",
  "本機收音回應過大。": "Native capture response is too large.",
  "本機收音格式不相容。": "Native capture format is incompatible.",
  "本機收音累積延遲過大，已停止，請重新開啟。": "Native capture stopped because accumulated latency was too high. Enable it again.",
  "本機收音資料無效，已停止。": "Native capture stopped because audio data was invalid.",
  "本機收音資料中斷，已停止並保留錄音片段；請重新開啟收音。": "Native capture interrupted. Stopped and kept the recorded portion; enable input again.",
  "前往": "Go to",
  "正在處理錄音，請等待完成。": "Processing recording. Please wait.",
  "錄唱進行中；完成後停止並保存，再試聽。": "Recording in progress. Stop and save when finished, then preview.",
  "已存入後處理，可調整效果、輸出音檔或 MV。": "Saved for post-production. Adjust effects and export audio or a music video.",
  "滿意後保存": "Save when satisfied",
  "分段需先試合完整一版；滿意後按「存到錄音後處理」。": "Assemble a full segment mix first, then save it for post-production when satisfied.",
  "滿意後按「存到錄音後處理」；也可以重錄。": "Save for post-production when satisfied, or record another take.",
  "挑選各段版本並試聽，再試合完整一版。": "Choose and preview each segment’s take, then assemble the full mix.",
  "先試聽這次錄音，確認是否滿意。": "Preview this recording first to check it.",
  "確認收音": "Check input",
  "先選收音方式與裝置；本機相容收音須先連上本機工具，才能試聲。": "Choose input mode and device first. Native capture needs a local-tools connection before testing.",
  "先確認收音方式與麥克風，再開麥試聲；單獨試聲不保存錄音。": "Check the input mode and microphone, then enable the mic to test. Testing alone does not save audio.",
  "收音方式已確認": "Input mode confirmed",
  "確認本機工具已啟動、歌曲庫可用，再開始選歌。": "Check that local tools and the song library are ready, then choose a song.",
  "本機工具已就緒，現在開麥試聲，確認收音。": "Local tools ready. Enable the microphone and test input.",
  "從歌曲庫選歌，或在播放器載入 YouTube／本機 MV。": "Choose a library song, or load YouTube / local video in the player.",
  "歌曲準備與 Key": "Song preparation and key",
  "正在準備，完成後會繼續下一步。": "Preparing. The next step will be available when ready.",
  "確認歌曲 Key；新版本需建立基準，已有版本可直接載入。": "Check the song key. New versions need a reference; existing versions load directly.",
  "演唱設定": "Singing settings",
  "確認帶唱方式、人聲／伴樂比例；沿用上次設定也可以。": "Check guide vocals and vocal / backing levels, or keep your previous settings.",
  "開始錄唱": "Start recording",
  "選好段落，按「錄這一段」。循環練唱不會錄音。": "Choose a segment and click “Record this segment”. Loop practice does not record.",
  "按「從頭開始唱」開始整首錄音；也可切換分段模式。": "Click “Sing from the start” for a whole-song recording, or switch to segment mode.",
  "同步已取消。": "Synchronization canceled.",
  "播放器尚未確認回到開頭，請重試「從頭開始唱」。": "The player has not confirmed returning to the beginning. Try “Sing from the start” again.",
  "只有伴樂需要已保存的分離音軌，請先補建試聽音軌，或改選「原唱＋伴樂」。": "Backing-only playback needs saved stems. Rebuild preview stems or choose original vocals + backing.",
  "伴樂音軌長度不足，請補建試聽音軌。": "Backing track is too short. Rebuild preview stems.",
  "無法讀取已保存的伴樂／和音，請確認本機工具與歌曲庫。": "Cannot read saved backing / harmonies. Check local tools and the library.",
  "· 保留音軌": "· Keep stems",
  "· 不保留音軌": "· Discard stems",
  "重新建立此 Key": "Rebuild this key",
  "本機工具連線失敗。": "Local tools connection failed.",
  "手動節拍燈，沒有歌曲基準時不代表實際歌曲拍點。": "Manual beat light does not represent the song’s actual beats without a reference.",
  "已取消／卸載本次工作；已保存的歌曲仍在本機歌曲庫。": "Current work canceled / unloaded. Saved songs remain in the local library.",
  "本機工具未回覆清除結果；閒置工作會於約 15 分鐘後自動清理。": "Local tools did not confirm cleanup. Idle work is automatically cleared after about 15 minutes.",
  "請先啟動本機工具。": "Start local tools first.",
  "本機工具需要更新，請重新下載工具包，停止舊工具後再執行 start-local.ps1。": "Update local tools: download the new package, stop the old tools, then run start-local.ps1.",
  "找到原有歌曲庫。請按「使用此位置」保留現有位置，或另外選擇。": "Existing library found. Click “Use this location” to keep it, or choose another folder.",
  "第一次使用請先選擇或指定歌曲庫資料夾，再準備歌曲。": "Choose or enter a library folder before preparing your first song.",
  "資料夾選擇仍在等待。可完成 Windows 選擇視窗，或按「取消資料夾選擇」。": "Folder selection is still waiting. Complete the Windows dialog or cancel folder selection.",
  "請在這台電腦開啟的視窗中選擇資料夾…": "Choose a folder in the dialog opened on this computer…",
  "正在保存歌曲庫位置…": "Saving library location…",
  "已取消選擇，歌曲庫位置未變更。": "Selection canceled. Library location unchanged.",
  "無法設定歌曲庫：": "Cannot set library location:",
  "已取消資料夾選擇；原歌曲庫與歌曲都保留，可重新選擇。": "Folder selection canceled. Original library and songs are preserved; you can choose again.",
  "已還原分離預設；按「準備歌曲基準」才會套用，已保存版本保留。": "Separation defaults restored. They apply when preparing the reference; saved versions are preserved.",
  "音高擷取方式已變更，尚未套用。請按「準備歌曲基準」。有保存相同分離版本的音軌時會直接重用，不需重新分離。": "Pitch extraction changed but not applied. Prepare the song reference to apply it. Existing stems for the same separation version are reused without separating again.",
  "分離模式已變更，尚未套用。請按「準備歌曲基準」載入或建立所選模式；目前仍是": "Separation mode changed but not applied. Prepare the reference to load or create that mode. Currently still using",
  "主唱／和音模式。": "lead / harmony mode.",
  "一般人聲模式。": "standard vocal mode.",
  "處理流程已變更，尚未套用。請按「準備歌曲基準」建立或載入所選流程；兩種流程分開保存，遮罩共用。": "Workflow changed but not applied. Prepare the reference to create or load it. Workflows save separately and share masks.",
  "主唱／和音模式": "Lead / harmony mode",
  "一般人聲模式": "Standard vocal mode",
  "正在準備歌曲，完成後才可試聽。": "Preparing song. Preview is available when ready.",
  "所選分離模型／模式／流程尚未套用，試聽已暫停。請按「準備歌曲基準」並等到已就緒，或從歌單載入對應版本。": "Selected model / mode / workflow has not been applied, so preview is paused. Prepare the reference and wait until ready, or load the matching version from the playlist.",
  "這首歌只有評分基準，未保留人聲／伴奏音檔。": "This song has a scoring reference only, without saved vocal / instrumental audio.",
  "請先結束並結算，再補建試聽音軌。": "Finish and score before rebuilding preview stems.",
  "可按「補建試聽音軌」重新分離一次並保存在本機；之後可直接試聽。": "Rebuild preview stems to separate and save them locally once; later previews load directly.",
  "人聲、伴奏、主唱與和音音軌已就緒，請選擇試聽。": "Vocal, instrumental, lead, and harmony stems are ready. Choose one to preview.",
  "人聲與伴奏音軌已就緒，請選擇試聽。": "Vocal and instrumental stems are ready. Choose one to preview.",
  "正在從本機載入音軌…": "Loading local stem…",
  "音軌不存在或已刪除，請勾選保留試聽後重新準備。": "Stem missing or deleted. Enable “Keep separated stems” and prepare again.",
  "全部人聲": "All vocals",
  "伴奏": "Instrumental",
  "主唱": "Lead",
  "和音": "Harmonies",
  "試聽 ·": "Preview ·",
  "· 本機音檔": "· Local audio",
  "音軌已載入，請點音訊播放器的播放鍵。": "Stem loaded. Press play in the audio player.",
  "請先指定歌曲庫資料夾。": "Choose a library folder first.",
  "本機工具回應不相容，請重新啟動。": "Local tools response is incompatible. Restart them.",
  "前": "First",
  "秒": "seconds",
  "完整歌曲": "Full song",
  "主唱模式": "Lead mode",
  "一般人聲": "Standard vocals",
  "含主唱／和音等 4 軌試聽": "Four preview stems including lead / harmony",
  "含人聲／伴奏試聽": "Vocal / instrumental preview",
  "只有旋律基準": "Melody reference only",
  "載入": "Load",
  "這首歌已載入，可直接試聽或按「從頭開始唱」。": "This song is loaded. Preview it or click “Sing from the start”.",
  "已卸載這首歌，正在刪除本機檔案…": "Song unloaded. Deleting local files…",
  "已刪除：": "Deleted:",
  "（基準與試聽音軌）。": "(reference and preview stems).",
  "刪除失敗：": "Delete failed:",
  "無法讀取歌曲庫：": "Cannot read library:",
  "還沒有演唱紀錄。": "No performances yet.",
  "紀錄已在另一個分頁變更，請重新勾選。": "History changed in another tab. Select the entries again.",
  "無法清除瀏覽器紀錄。": "Cannot clear browser history data.",
  "本輪已結束，歌曲已保留": "Round finished; song retained",
  "這段沒有可評分的原唱人聲（休息或已遮罩），未保存分數。歌曲已保留，可直接重新開始。": "No scorable original vocals in this section (rest or masked), so no score was saved. The song is retained for another take.",
  "已結算，分數紀錄已保存；錄音結果請看錄音狀態。歌曲已保留，可直接按「從頭開始唱」。": "Scored and saved to history. See recording status for audio results. Song retained; click “Sing from the start” to try again.",
  "已結算，但瀏覽器不允許儲存紀錄；分數仍顯示在這裡。": "Scored, but browser storage is unavailable. The score remains visible here.",
  "本機快取": "Local cache",
  "CPU · GPU 失敗後重試": "CPU · Retrying after GPU failure",
  "CPU · 本機處理": "CPU · Local processing",
  "已從歌曲庫載入": "Loaded from library",
  "歌曲準備完成": "Song preparation complete",
  "分離音軌驗證中；還需建立基準及保存，尚未就緒。": "Validating stems. Reference building and saving are still required; not ready yet.",
  "第二輪伴奏": "Second instrumental pass",
  "人聲／伴奏": "Vocals / Instrumental",
  "正在載入變調版本…": "Loading transposed version…",
  "本機回傳的 Key 與選定版本不同，請重新載入。": "Returned key differs from the selected version. Reload it.",
  "本機回傳的分離模式與所選模式不符，請更新頁面與本機工具後重試。": "Returned separation mode differs from your selection. Update the page and local tools, then retry.",
  "影片已切換，請重新準備歌曲。": "Video changed. Prepare the song again.",
  "· 已隨歌曲版本保存。": "· Saved with this song version.",
  "直接載入本機基準": "Loaded local reference directly",
  "已保存到本機": "Saved locally",
  "，可試聽分離結果": ", separated stems available for preview",
  "，音檔已清除": ", audio files cleared",
  "· 以主唱評分": "· Scoring lead vocals",
  "基準就緒。開啟麥克風後，按「從頭開始唱」或影片播放按鈕。": "Reference ready. Enable the mic, then click “Sing from the start” or the video play button.",
  "準備失敗：": "Preparation failed:",
  "無法連線到本機工具。請確認啟動與本機網路權限。": "Cannot connect to local tools. Check that they are running and local network access is allowed.",
  "請等本機 MV 匯入完成，再準備歌曲。": "Wait for local video import to finish before preparing the song.",
  "請先載入 YouTube 影片或選擇本機 MV。": "Load a YouTube video or choose a local video first.",
  "正在連接本機工具…": "Connecting to local tools…",
  "正在準備": "Preparing",
  "，完成後會保存到歌曲庫…": "; it will be saved to the library when ready…",
  "請更新並重新啟動本機工具，才能使用本機 MV。": "Update and restart local tools to use local videos.",
  "請更新並重新啟動本機工具，才能建立 Key 版本。": "Update and restart local tools to create key versions.",
  "本機工具需要更新才能使用伴奏二次分離＋反向相減，請更新並重新啟動工具。": "Update and restart local tools to use the second instrumental pass and subtraction.",
  "本機工具需要更新才能使用 RMVPE，請更新並重新啟動工具。": "Update and restart local tools to use RMVPE.",
  "本機工具需要更新才能使用 Mel-Band RoFormer 人聲模型，請更新工具程式碼並重新啟動。": "Update local tool code and restart to use the Mel-Band RoFormer vocal model.",
  "本機工具需要更新才能使用 RoFormer 分離模型，請更新工具包並重新啟動；缺少套件時再執行 setup-local.ps1。": "Update and restart local tools to use RoFormer separation. Run setup-local.ps1 if dependencies are missing.",
  "本機工具需要更新才能使用主唱／和音分離，請更新工具包並重新執行 setup-local.ps1。": "Update local tools and run setup-local.ps1 again to use lead / harmony separation.",
  "本機工具需要更新才能重新分離，請更新工具包並重新啟動。": "Update and restart local tools to separate again.",
  "請先指定歌曲庫資料夾，再準備歌曲。": "Choose a library folder before preparing a song.",
  "播放器未就緒：": "Player not ready:",
  "無法準備歌曲：": "Cannot prepare song:",
  "請先啟動本機工具，並允許本機網路存取。": "Start local tools and allow local network access first.",
  "目前播放": "Playing",
  "；請按「建立／載入此 Key」。": "; click “Create / Load this key”.",
  "請按「準備歌曲基準」。": "Click “Prepare song reference”.",
  "正在同步影片到 0 秒…": "Synchronizing video to 0 seconds…",
  "正在開啟麥克風，請允許瀏覽器的收音授權…": "Enabling microphone. Allow microphone access in your browser…",
  "未開始演唱：麥克風尚未就緒，請查看「收音」區的狀態，再按「從頭開始唱」。": "Not started: microphone not ready. Check audio input status, then click “Sing from the start”.",
  "無法取得錄音所需的配樂／和音，請補建試聽音軌或改選歌唱者。": "Cannot get backing / harmonies for recording. Rebuild preview stems or choose singer only.",
  "正在準備演唱時帶唱…": "Preparing guide playback…",
  "影片已回到開頭，等待播放開始。": "Video returned to the beginning. Waiting for playback.",
  "分數紀錄已全部清除；演唱錄音與歌曲仍保留。": "All score history cleared. Recordings and songs are preserved.",
  "目前播放位置超出分析範圍，請按「從頭開始唱」。": "Playback is outside the analysis range. Click “Sing from the start”.",
  "演唱中。跳過的段落會計入漏唱，重播不會重複加分。": "Singing. Skipped sections count as missed; replaying does not add points twice.",
  "影片緩衝中，評分暫停。": "Video buffering. Scoring paused.",
  "播放已暫停，評分同步暫停。": "Playback paused. Scoring paused with it.",
  "影片可以播放，但麥克風尚未開啟。請先開啟收音，再從頭開始唱。": "Video can play, but the microphone is off. Enable input, then sing from the start.",
  "已到本次分析範圍結尾。資料已保留，可停止收音後按「結束並結算」。": "Reached the analysis range’s end. Data retained; stop input and finish scoring.",
  "超出分析範圍，不再計分": "Outside analysis range; scoring stopped",
  "繼續評分中。停止收音後可按「結束並結算」。": "Scoring continues. Stop input, then finish and score.",
  "休息": "Rest",
  "遮罩區間，不計分": "Masked region; not scored",
  "音準吻合（允許八度差）": "Pitch matched (octave differences allowed)",
  "音準吻合": "Pitch matched",
  "偏高": "Sharp",
  "偏低": "Flat",
  "等待歌聲": "Waiting for vocals",
  "前奏／間奏，不計分": "Intro / interlude; not scored",
  "歌曲基準已就緒": "Song reference ready",
  "上次演唱資料已保留，可先結算。": "Previous performance data retained. You can score it first.",
  "收音已停止，本次演唱資料已保留。可按「結束並結算」，或「從頭開始唱」重新計分。": "Input stopped; performance data retained. Finish and score, or sing from the start for a new round.",
  "收音已停止，播放器已回到 0 秒。可結算本次演唱，或按「從頭開始唱」重新計分。": "Input stopped and player returned to 0 seconds. Score this performance or sing from the start for a new round.",
  "本次演唱資料仍保留，可先結算。": "Performance data retained. You can score it first.",
  "遮罩資料無效，最多 100 段。": "Invalid mask data. Maximum 100 regions.",
  "遮罩需符合 0 ≤ 起點 < 終點 ≤ 歌曲基準長度。": "Masks require 0 ≤ start < end ≤ reference duration.",
  "歌曲基準缺少有效影片 ID。": "Song reference is missing a valid video ID.",
  "歌曲名稱無效。": "Invalid song name.",
  "基準時間間隔必須介於 20–200 ms。": "Reference interval must be 20–200 ms.",
  "基準長度無效。": "Invalid reference duration.",
  "基準音高超出 65–1000 Hz。": "Reference pitch is outside 65–1000 Hz.",
  "至少需要 3 秒可辨識的參考旋律。": "At least 3 seconds of identifiable reference melody are required.",
  "寬鬆": "Relaxed",
  "演唱紀錄無效。": "Invalid performance data.",
  "至少需要辨識到 4 個穩定音符，請檢查收音後重試。": "At least four stable notes must be detected. Check input and try again.",
  "五個音的時間差太分散，暫不建議套用。請保持同一節奏再試。": "Timing differences across the five notes vary too much to recommend applying them. Keep a steady rhythm and retry.",
  "請先開啟麥克風，再開始五音測試。": "Enable the microphone before starting the five-note test.",
  "準備…跟著 Do Re Mi Fa Sol 唱，可高／低八度。": "Get ready… Sing Do Re Mi Fa Sol, at any octave.",
  "準備…讓麥克風收到五個測試音，不用唱。": "Get ready… Let the microphone hear the five test notes. No singing needed.",
  "包含跟唱反應時間。": "Includes singing reaction time.",
  "包含播放到收音的往返延遲。": "Includes playback-to-input round-trip latency.",
  "測試音無法播放，請重新開啟麥克風後再試。": "Cannot play test notes. Enable the microphone again and retry.",
  "測試設定已變更，請重新測試。": "Test settings changed. Run the test again.",
  "已停止五音測試，未改動補償。": "Five-note test stopped. Compensation unchanged.",
  "已套用到時間補償。": "Applied to time compensation.",
  "五音測試已停止；需要時可重新測試。": "Five-note test stopped. Run it again when needed.",
  "時間請輸入秒數或 分:秒，例如 32.5 或 1:02.5。": "Enter seconds or min:sec, such as 32.5 or 1:02.5.",
  "跳到起點": "Jump to start",
  "本機工具需要更新並重新啟動，才能保存遮罩。": "Update and restart local tools to save masks.",
  "目前沒有遮罩，依原本歌曲基準評分。": "No masks set. Scoring uses the original song reference.",
  "正在保存遮罩…": "Saving masks…",
  "未保存：": "Not saved:",
  "播放器尚未就緒。": "Player not ready.",
  "不保存錄音，音量平衡不啟動。": "Recordings are not saved; volume balance is inactive.",
  "手動＋自動微調": "Manual + automatic fine-tuning",
  "自動平衡": "Automatic balance",
  "已關閉錄音，音量平衡不啟動。": "Recording disabled; volume balance is inactive.",
  "手動＋自動：音量可調 0–200%，兩路各自最多微調 ±3 dB。0% 保持靜音；每輪開始後固定設定。": "Manual + automatic: levels 0–200%, with up to ±3 dB correction per track. 0% stays muted. Settings are fixed once the round starts.",
  "自動平衡：依歌唱者及配樂／和音音量平滑調整，各自最多修正 ±6 dB。下方手動音量不參與；每輪開始後固定設定。": "Automatic balance smoothly adjusts vocals and backing / harmonies by up to ±6 dB each. Manual levels below are ignored. Settings are fixed once the round starts.",
  "已選取最新錄音，可試聽、下載或後處理。": "Latest recording selected. Preview, download, or edit it.",
  "尚無演唱錄音。": "No performance recordings yet.",
  "歌唱者＋配樂／和音": "Singer + backing / harmonies",
  "歌唱者＋配樂（無獨立和音）": "Singer + backing (no separate harmonies)",
  "· 手動＋自動": "· Manual + automatic",
  "· 自動平衡": "· Automatic balance",
  "歌曲庫錄音目錄": "Library recording folder",
  "瀏覽器待搬存": "Browser copy awaiting migration",
  "· 歌聲校正": "· Vocal correction",
  "· 未正常結束，保留已儲存片段": "· Ended unexpectedly; saved portion retained",
  "刪除這筆錄音、原始歌聲及其後處理資料？此操作無法復原。": "Delete this recording, original vocals, and production data? This cannot be undone.",
  "本輪不保存錄音。": "This round will not save a recording.",
  "瀏覽器不支援同步錄音，請使用桌機 Chrome／Edge，或選不保存錄音。": "Synchronized recording is unavailable in this browser. Use desktop Chrome / Edge, or disable recording.",
  "正在準備錄音配樂／和音…": "Preparing recording backing / harmonies…",
  "正在準備演唱錄音…": "Preparing performance recording…",
  "麥克風尚未就緒，無法開始錄音。": "Microphone not ready; cannot start recording.",
  "混音錄音需要已保存的分離音軌；請先補建試聽音軌，或改選歌唱者。": "Mixed recording needs saved stems. Rebuild preview stems or choose singer only.",
  "錄音準備已取消。": "Recording preparation canceled.",
  "配樂與和音長度不一致，請補建音軌後再錄音。": "Backing and harmony lengths differ. Rebuild stems before recording.",
  "乾淨歌聲保存失敗：": "Failed to save clean vocals:",
  "乾淨歌聲錄音中斷": "Clean vocal recording interrupted",
  "自動保存失敗，停止後請下載備份：": "Autosave failed. Download a backup after stopping:",
  "錄音中斷": "Recording interrupted",
  "· 已載入伴奏＋和音": "· Instrumental + harmonies loaded",
  "· 已載入伴奏（此版本無獨立和音）": "· Instrumental loaded (no separate harmonies in this version)",
  "錄音已就緒，等待影片播放。": "Recording ready. Waiting for video playback.",
  "錄音暫停，會隨影片續播。": "Recording paused; resumes with the video.",
  "未開始播放，沒有保存空白錄音。": "Playback never started; no empty recording saved.",
  "診斷已確認保存。": "Diagnostic save confirmed.",
  "延時校正未完成，已保留待確認錄音：": "Timing correction incomplete; pending take retained:",
  "分段錄音已保存於分段區。": "Segment recording saved in the segment area.",
  "演唱錄音.wav": "Performance.wav",
  "下載錄音片段": "Download recorded portion",
  "下載未保存錄音": "Download unsaved recording",
  "收音中斷，已保留錄音片段，可下載備份：": "Input interrupted; recorded portion retained. Download a backup:",
  "錄音未完整保存，請先按「下載未保存錄音」備份：": "Recording not fully saved. Download the unsaved recording as a backup first:",
  "無法讀取錄音清單：": "Cannot read recording list:",
  "請先停止收音，再刪除全部錄音。": "Stop input before deleting all recordings.",
  "刪除此清單中的整首錄音、已保存成品及其後處理資料？待確認錄音、分段素材、歌曲基準與分離音軌保留。此操作無法復原。": "Delete whole-song recordings, saved results, and their production data in this list? Pending takes, segment sources, song references, and stems will be kept. This cannot be undone.",
  "未全部刪除：": "Some items were not deleted:",
  "不保存錄音；從頭開始唱只收音評分。": "Recording disabled. Singing from the start captures input for scoring only.",
  "按「從頭開始唱」後自動錄製；停止收音、結算或播完時保存。": "Records automatically after “Sing from the start”; saves when input stops, scoring finishes, or playback ends.",
  "下一輪使用手動比例＋自動微調；只影響錄音。": "Next round uses manual levels + automatic fine-tuning. Recording only.",
  "下一輪使用自動平衡；只影響錄音。": "Next round uses automatic balance. Recording only.",
  "瀏覽器錄音儲存不可用：": "Browser recording storage unavailable:",
  "錄音資料庫被其他分頁占用。": "Another tab is using the recording database.",
  "錄音儲存失敗。": "Recording save failed.",
  "本機工具無法連接。": "Cannot connect to local tools.",
  "請更新並重新啟動本機工具，才能搬存錄音。": "Update and restart local tools to migrate recordings.",
  "錄音資料夾操作失敗。": "Recording folder operation failed.",
  "請重新啟動新版本機工具，才能保存校正成品與原始歌聲。": "Restart the updated local tools to save corrected mixes and original vocals.",
  "瀏覽器原始音檔不完整，未搬存也未刪除。": "Browser original audio is incomplete; not migrated or deleted.",
  "本機錄音大小與瀏覽器副本不符，保留原檔。": "Local recording size differs from the browser copy. Original retained.",
  "已保存至": "Saved to",
  "暫存在此瀏覽器，尚未搬存：": "Temporarily stored in this browser, not migrated:",
  "本機錄音目錄未連線；瀏覽器待搬存資料仍保留。": "Local recording folder disconnected. Browser copies awaiting migration are retained.",
  "已搬存": "Migrated",
  "筆，瀏覽器舊副本已清除。": "recordings; old browser copies removed.",
  "部分錄音仍留在瀏覽器：": "Some recordings remain in the browser:",
  "請先將這筆錄音搬存到歌曲庫。": "Migrate this recording to the library first.",
  "請更新並重新啟動本機工具，才能轉 MP3。": "Update and restart local tools to convert to MP3.",
  "無法連接本機工具，請啟動後再試。": "Cannot connect to local tools. Start them and retry.",
  "所需音軌不存在，請還原相同版本的歌曲音軌。": "Required stems are missing. Restore stems for the same song version.",
  "歌聲分析逾時，請重試。": "Vocal analysis timed out. Retry.",
  "歌聲分析無法啟動，請更新頁面後重試。": "Cannot start vocal analysis. Reload the page and retry.",
  "降噪": "Noise reduction",
  "齒音": "Sibilance",
  "呼吸": "Breaths",
  "音準": "Pitch",
  "次": "repeats",
  "輕度": "Light",
  "中度": "Medium",
  "強烈": "Strong",
  "已自行微調音色，可繼續調整或重新選擇情緒。": "Tone manually adjusted. Keep editing or choose another mood.",
  "（預設，不額外調整音色）": "(default, no extra tone adjustment)",
  "開始（秒）": "Start (seconds)",
  "結束（秒）": "End (seconds)",
  "人聲音量（%）": "Vocal level (%)",
  "移除區段": "Remove region",
  "殘響（%）": "Reverb (%)",
  "尾音（秒）": "Decay (seconds)",
  "回聲（%）": "Delay (%)",
  "尚未載入": "Not loaded",
  "二次分離＋相減": "Second pass + subtraction",
  "人聲": "Vocals",
  "這筆錄音未保留獨立歌聲，無法只聽人聲。": "This recording has no separate vocals for vocal-only preview.",
  "這次使用目前已載入基準，保留錄音當時的遮罩、八度與評分範圍，難度使用「評分設定」中的重新評分難度。": "Using the loaded reference with the recording’s original masks, octave matching, and scoring range. Difficulty comes from the rescoring setting.",
  "這次使用錄音當時的基準；換歌曲庫版本不會自動套用。": "Using the reference saved with this recording. Changing library versions does not apply automatically.",
  "已選取錄音，可調整設定後重新評分。": "Recording selected. Adjust settings and rescore.",
  "請先保存一段演唱錄音。": "Save a performance recording first.",
  "已保存乾淨歌聲、播放位置與當次基準，可重評／重合成。": "Clean vocals, playback positions, and reference are saved for rescoring / remixing.",
  "此錄音未保存後處理來源，可轉 MP3 下載。": "Production sources were not saved. This recording can be converted to MP3 for download.",
  "音檔重評": "Audio rescore",
  "舊版即時資料重評": "Legacy live-data rescore",
  "改用已載入基準": "Using loaded reference",
  "錄音當時基準": "Original recording reference",
  "正在試聽：": "Previewing:",
  "正在準備人聲試聽…": "Preparing vocal-only preview…",
  "原始歌聲不完整，無法只聽人聲。": "Original vocals are incomplete; vocal-only preview unavailable.",
  "只聽人聲：": "Vocals only:",
  "（已保存的效果）": "(saved effects)",
  "已開始下載選取的錄音。": "Download of selected recording started.",
  "已帶入選取的成品製作 MV；使用已保存的音量、效果與剪輯，尚未重新合成的調整不會套用。": "Selected result imported for video creation with its saved levels, effects, and trim. Changes not yet rendered will not apply.",
  "已刪除選取的錄音。": "Selected recording deleted.",
  "請先結束錄音，再清除後處理清單。": "Finish recording before clearing the production list.",
  "待確認錄音與分段素材保留。": "Pending takes and segment sources are preserved.",
  "局部音量最多 100 個區段。": "Maximum 100 volume regions.",
  "局部效果最多 20 個區段。": "Maximum 20 effect regions.",
  "正在從保存的乾淨歌聲重新擷取音高…": "Extracting pitch from saved clean vocals…",
  "重評完成：直接分析保存的歌聲，使用與重混相同的時間軸；結果、難度與所用基準已保存，錄音原始基準及成績紀錄保留。": "Rescoring complete. Saved vocals were analyzed on the same timeline as remixing. Results, difficulty, and reference saved; original reference and score history preserved.",
  "正在載入乾淨歌聲與配樂／和音…": "Loading clean vocals and backing / harmonies…",
  "原始歌聲不完整，無法另存可繼續後製的成品。": "Original vocals incomplete; cannot save an editable production result.",
  "正在校正歌聲位置並合成…": "Correcting vocal timing and rendering…",
  "正在打包這筆錄音的本機診斷資料…": "Packaging local diagnostics for this recording…",
  "這筆錄音超過診斷匯出大小限制，請改用較短錄音。": "Recording exceeds the diagnostic export size limit. Use a shorter recording.",
  "診斷檔已下載到本機。這份檔案含本次歌聲，請提供此檔或其本機路徑以檢查，不需重唱。": "Diagnostics downloaded locally. This file contains your vocals; share it or its local path for alignment checks without recording again.",
  "正在本機轉成 MP3…": "Converting to MP3 locally…",
  "MP3 已轉換並開始下載，同時保存至": "MP3 converted; download started and saved to",
  "MP3 已轉換並開始下載，但尚未存入錄音目錄：": "MP3 converted and downloading, but not yet saved in the recording folder:",
  "原始歌聲不完整，無法比較。": "Original vocals incomplete; comparison unavailable.",
  "保存至": "Saved to",
  "未設定": "Not set",
  "歌聲延時校正": "Vocal timing correction",
  "人聲情緒": "Vocal mood",
  "音準修正強度": "Pitch correction strength",
  "音準修正目標": "Pitch correction target",
  "原唱基準（保留八度）": "Original reference (preserve octave)",
  "最近半音": "Nearest semitone",
  "音準修正速度": "Pitch correction speed",
  "開啟": "On",
  "低頻": "Low",
  "中頻": "Mid",
  "高頻": "High",
  "動態壓縮": "Compression",
  "殘響空間": "Reverb space",
  "回聲重複間隔": "Delay interval",
  "回聲重複次數": "Delay repeats",
  "回聲每次保留音量": "Level retained per repeat",
  "開始": "Start",
  "結束": "End",
  "音量": "Volume",
  "殘響": "Reverb",
  "尾音": "Decay",
  "回聲": "Delay",
  "目前 A／B 設定相同": "A and B currently have the same settings",
  "已另存成品，A／B 設定與比較片段保留；還原會回到系統預設。": "Result saved. A/B settings and comparison range retained. Reset restores system defaults.",
  "A、B 已帶入相同的錄音設定，可各自調整後比較。預設調整 B；還原按鈕回到系統預設。": "A and B loaded the same recording settings; adjust each to compare. B is selected by default. Reset restores system defaults.",
  "試聽需設定有效起訖，每段最多 30 秒。": "Set a valid preview range, up to 30 seconds.",
  "請先記住這組設定。": "Store this set’s settings first.",
  "· 近似音量匹配": "· Approximate loudness matching",
  "比較已停止，A／B 設定仍保留。": "Comparison stopped. A/B settings retained.",
  "延時需介於 −2000 與 +2000 ms。": "Timing correction must be −2000 to +2000 ms.",
  "原唱區間最多 200 段。": "Maximum 200 original vocal regions.",
  "缺少原唱區間的歌曲長度。": "Missing song duration for original vocal regions.",
  "原唱區間需在歌曲內，至少 0.1 秒，並選擇播放方式。": "Original vocal regions must be within the song, at least 0.1 seconds long, with a playback mode selected.",
  "原唱區間不可重疊，請調整起訖時間。": "Original vocal regions cannot overlap. Adjust their start / end times.",
  "請先載入這首歌的新基準；只更改音高選項還不算載入。": "Load the song’s new reference first. Changing the pitch option alone does not load it.",
  "目前載入的是另一支影片，不能用來重評這筆錄音。": "A different video is loaded and cannot rescore this recording.",
  "請載入與這筆錄音相同 Key 的基準，避免用不同調重評。": "Load a reference in the recording’s key to avoid rescoring against a different key.",
  "請載入與錄音當時相同分析範圍的基準，避免改變計分範圍。": "Load a reference with the same analysis range to preserve scoring coverage.",
  "剪輯設定版本不支援。": "Unsupported trim settings version.",
  "剪輯起訖需在原始錄音範圍內，結束必須晚於開始。": "Trim points must be within the original recording, with end after start.",
  "淡入淡出各需介於 0 與 30 秒，合計不可超過保留長度。": "Each fade must be 0–30 seconds; their total cannot exceed the kept duration.",
  "剪輯範圍太短，至少需保留一個音訊取樣。": "Trim range too short. Keep at least one audio sample.",
  "保存的混音音量無效。": "Invalid saved mix levels.",
  "後處理一次最多一小時。": "Production is limited to one hour per operation.",
  "缺少指定區間的原唱音軌，請補建歌曲音軌後重新試合。": "Original vocals are missing for the selected region. Rebuild song stems and assemble again.",
  "原唱音軌長度不足，請補建完整音軌。": "Original vocal stem too short. Rebuild the full stem.",
  "錄音音訊執行緒未回應，已保留接收到的錄音片段。": "Recording audio thread did not respond. Received audio retained.",
  "錄音音訊執行緒中斷，已停止錄音。": "Recording audio thread interrupted. Recording stopped.",
  "錄音取樣時間軸中斷，已停止，避免繼續產生錯位。": "Recording timeline interrupted. Stopped to prevent further misalignment.",
  "單次錄音已達 30 分鐘，已停止並保留錄音。": "Recording reached 30 minutes. Stopped and retained.",
  "合成器": "Synthesizer",
  "修音": "Auto-tune",
  "無效的歌聲柔化強度。": "Invalid vocal smoothing strength.",
  "較強": "Stronger",
  "低": "Low",
  "中": "Mid",
  "高": "High",
  "壓縮": "Compression",
  "呼吸降低": "Breath reduction",
  "原唱基準": "Original reference",
  "末尾": "End",
  "_人聲後製": "_VocalProduction",
  "這筆人聲效果版本較新，請更新網頁後再編輯。": "These vocal effects use a newer version. Update the page before editing.",
  "無效的動態壓縮強度。": "Invalid compression strength.",
  "區段開始秒數": "Region start (seconds)",
  "區段結束秒數": "Region end (seconds)",
  "區段音量（%）": "Region volume (%)",
  "局部音量的結束時間必須晚於開始時間。": "Volume region end must be after start.",
  "局部音量區段不可重疊，請調整開始／結束時間。": "Volume regions cannot overlap. Adjust start / end times.",
  "殘響寬度（%）": "Reverb width (%)",
  "回聲音量（%）": "Delay level (%)",
  "回聲間隔（ms）": "Delay interval (ms)",
  "回聲次數": "Delay repeat count",
  "回聲保留比例（%）": "Delay retained level (%)",
  "回聲次數需為整數，左右交替需為開關。": "Repeat count must be an integer; ping-pong must be on or off.",
  "效果開始秒數": "Effect start (seconds)",
  "效果結束秒數": "Effect end (seconds)",
  "區段殘響（%）": "Region reverb (%)",
  "區段回聲（%）": "Region delay (%)",
  "區段尾音（秒）": "Region decay (seconds)",
  "局部效果結束需晚於開始，且區段不可重疊。": "Effect region end must follow start, and regions cannot overlap.",
  "原版": "Legacy",
  "沿用舊版殘響，適合與既有成品比較。": "Uses the old reverb for comparison with existing results.",
  "房間": "Room",
  "緊密、短尾，帶少量近牆反射，增加自然空間感。": "Tight, short tail with subtle nearby reflections for natural space.",
  "大廳": "Hall",
  "板式": "Plate",
  "明亮、密集，尾音較快出現，讓人聲多一層光澤。": "Bright, dense, quick onset, adding sheen to vocals.",
  "錄音室": "Studio",
  "貼近、柔暗的短尾，空間感收斂，保留清楚咬字。": "Close, dark short tail with restrained space and clear articulation.",
  "小室": "Chamber",
  "溫暖、緊湊，密集反射讓歌聲較厚實。": "Warm, compact, dense reflections for fuller vocals.",
  "教堂": "Church",
  "柔暗、緩慢鋪開的長尾，適合拉長音與莊嚴感。": "Dark, slowly spreading long tail for sustained notes and solemn character.",
  "體育館": "Stadium",
  "開闊、遠距，較晚的反射群帶出大型場地感。": "Open and distant, with late reflection clusters suggesting a large venue.",
  "隧道": "Tunnel",
  "規律的一波波反射，能聽到沿著長通道延伸的尾音。": "Regular waves of reflections extending down a long passage.",
  "洞穴": "Cave",
  "低沉、幽暗，不規則反射帶出深處回應的感覺。": "Deep, dark, irregular reflections suggesting a distant response.",
  "浴室": "Bathroom",
  "明亮、貼近硬牆，短促反射密集，適合聽鮮明的空間效果。": "Bright, close hard-wall reflections with a dense short tail and vivid space.",
  "夢幻空間": "Dream space",
  "尾音慢慢浮起、綿長散開，營造漂浮感；不會改變音高。": "A slow-rising, long, spreading tail creates a floating feel without changing pitch.",
  "無效的殘響空間類型。": "Invalid reverb space type.",
  "殘響尾音長度需介於 0.2 與 10 秒。": "Reverb decay must be 0.2–10 seconds.",
  "殘響預延遲需介於 0 與 500 ms。": "Reverb pre-delay must be 0–500 ms.",
  "錄音取樣資料無效。": "Invalid recording sample data.",
  "貼近耳邊": "Intimate",
  "木吉他": "Acoustic guitar",
  "大廳一般流行": "Hall pop",
  "明亮流行": "Bright pop",
  "大廳慢板抒情": "Hall ballad",
  "演唱會": "Concert",
  "夢幻": "Dreamy",
  "自訂": "Custom",
  "貼近耳邊 · 清楚自然": "Intimate · Clear and natural",
  "木吉他 · 輕聲演唱": "Acoustic guitar · Gentle singing",
  "大廳 · 一般流行（預設）": "Hall · Pop (default)",
  "明亮流行 · 人聲突出": "Bright pop · Prominent vocals",
  "大廳 · 慢板抒情": "Hall · Slow ballad",
  "教堂 · 莊嚴長尾": "Church · Solemn long tail",
  "演唱會 · 寬大舞台": "Concert · Wide stage",
  "夢幻 · 空靈回聲": "Dreamy · Ethereal delay",
  "原音": "Original",
  "不額外調整音色：EQ 歸零、柔化與壓縮關閉；空間效果仍保留。": "No extra tonal adjustment: EQ flat, smoothing and compression off. Space effects remain.",
  "溫柔親密": "Tender and intimate",
  "柔和、貼近耳邊，收斂尖亮感；可搭配「貼近耳邊」情境。": "Soft and close with restrained brightness. Pairs with the intimate space preset.",
  "甜蜜幸福": "Sweet and joyful",
  "輕盈明亮、帶微笑感，輕度壓縮讓輕聲較穩定。": "Light and bright, with gentle compression to steady quiet singing.",
  "深情真摯": "Heartfelt",
  "溫暖厚實，保留較多演唱起伏；可搭配大廳。": "Warm and full while preserving dynamics. Pairs with hall reverb.",
  "思念懷舊": "Nostalgic",
  "柔暗溫暖，收斂高頻，烘托回憶感。": "Soft and warm with restrained highs for a nostalgic feel.",
  "孤單落寞": "Lonely",
  "音色清瘦、稍微退後，保留原有強弱；可搭配寬廣空間。": "Lean, slightly recessed tone with original dynamics. Pairs with a wide space.",
  "悲傷脆弱": "Sad and fragile",
  "保留氣息、細節與大小聲起伏，不加柔化或壓縮。": "Preserves breath, detail, and dynamics without smoothing or compression.",
  "釋懷平靜": "Calm and accepting",
  "自然平順，稍微收斂中高頻，保留演唱動態。": "Natural and smooth, gently reducing upper mids while preserving dynamics.",
  "堅定振奮": "Confident and uplifting",
  "增加清晰度與存在感，用輕度壓縮穩住人聲。": "Adds clarity and presence with light compression for steady vocals.",
  "激昂奔放": "Passionate",
  "突出咬字與明亮度，中度壓縮控制較大的音量落差。": "Emphasizes articulation and brightness, with medium compression for larger dynamic changes.",
  "夢幻迷離": "Dreamlike",
  "柔和、朦朧，降低直接感；可搭配夢幻空間與回聲。": "Soft and hazy, reducing directness. Pairs with dream space and delay.",
  "Key 請選擇 −12～＋12 的整數半音。": "Choose an integer key shift from −12 to +12 semitones.",
  "升": "Up",
  "降": "Down",
  "原調": "Original key",
  "請從原調音軌建立 Key 版本，避免重複變調。": "Build key versions from original-key stems to avoid repeated transposition.",
  "變調音軌長度不足，請重新建立此 Key 版本。": "Transposed stem is too short. Rebuild this key version.",
  "變調音軌尚未就緒，請等待載入完成。": "Transposed stems are not ready. Wait for loading to finish.",
  "請再按播放，允許變調音軌播放。": "Press play again to allow transposed audio playback.",
  "· 未完整結束": "· Ended incompletely",
  "· 診斷未完整保存：": "· Diagnostics not fully saved:",
  "· 診斷已保存": "· Diagnostics saved",
  "沒有已保存的伴樂，請補建音軌或選「純人聲」。": "No saved backing. Rebuild stems or choose vocals only.",
  "正在準備試聽…": "Preparing preview…",
  "無法讀取人聲錄音。": "Cannot read vocal recording.",
  "正在播放原始人聲錄音，不加入伴樂、不套用音量平衡或延時校正。滿意後按「存到錄音後處理」。": "Playing original vocals without backing, volume balance, or timing correction. Save for post-production when satisfied.",
  "伴樂長度不足，請補建完整音軌。": "Backing is too short. Rebuild the full stems.",
  "已存到錄音後處理。": "Saved for post-production.",
  "已刪除此版待確認錄音。": "Pending take deleted.",
  "正在讀取要清除的待確認錄音清單…": "Reading pending takes to clear…",
  "這首歌已沒有待確認錄音。": "This song has no pending takes left.",
  "已取消清除，錄音保留。": "Cleanup canceled. Recordings retained.",
  "未能刪除，請重試": "could not be deleted; retry",
  "因開始錄音而保留": "retained because recording started",
  "清除完成，這首此 Key 的待確認整首錄音已全部清空。": "Cleanup complete. All pending whole-song takes for this song and key are cleared.",
  "已選取待確認錄音，可先試聽。": "Pending take selected. Preview it first.",
  "試聽內容已變更，請按「試聽這一版」。": "Preview content changed. Click “Preview this take”.",
  "請啟動新版本機工具": "Start the updated local tools",
  "診斷未連線：": "Diagnostics offline:",
  "待命：只在演唱錄音時收集。": "Ready: collects only during performance recording.",
  "診斷已關閉，已保存資料仍保留。": "Diagnostics disabled. Saved data retained.",
  "清除所有錄音診斷資料？歌曲、演唱錄音與後處理成品都會保留。": "Clear all recording diagnostics? Songs, recordings, and production results will be kept.",
  "未清除：": "Not cleared:",
  "正在確認診斷可保存…": "Checking whether diagnostics can be saved…",
  "診斷無法準備，尚未開始錄音：": "Cannot prepare diagnostics; recording has not started:",
  "診斷無法保存，尚未開始錄音。請確認已更新並啟動本機工具：": "Cannot save diagnostics; recording has not started. Check that updated local tools are running:",
  "診斷不完整，演唱錄音仍會繼續：": "Diagnostics incomplete; performance recording continues:",
  "本機保存太慢，已停止診斷收集": "Local saving too slow; diagnostic collection stopped",
  "診斷分析節點中斷": "Diagnostic analysis node interrupted",
  "診斷分析節點尾端未確認": "Diagnostic analysis tail not confirmed",
  "直接收音診斷中斷：": "Direct-input diagnostics interrupted:",
  "● 錄音診斷中 · 停止錄音後確認保存": "● Recording diagnostics active · Save confirmed after recording stops",
  "錄音暫停，診斷暫停收集。": "Recording paused; diagnostic collection paused.",
  "錄音準備已取消": "Recording preparation canceled",
  "直接收音診斷尾端未確認": "Direct-input diagnostic tail not confirmed",
  "診斷資料未完整保存": "Diagnostic data not fully saved",
  "診斷不完整：": "Diagnostics incomplete:",
  "診斷已保存 · 待命，不再收集音訊": "Diagnostics saved · Ready, no longer collecting audio",
  "診斷未完整保存：": "Diagnostics not fully saved:",
  "分段錄音支援 30 分鐘內的歌曲。": "Segment recording supports songs up to 30 minutes.",
  "第 1 段": "Segment 1",
  "分段草稿格式無效。": "Invalid segment draft format.",
  "段落需連續且不可重疊，每段至少 0.1 秒。": "Segments must be continuous, non-overlapping, and at least 0.1 seconds each.",
  "段落需涵蓋完整歌曲。": "Segments must cover the full song.",
  "最多保留 200 段。": "Maximum 200 segments.",
  "分界需離相鄰分界至少 0.1 秒。": "Boundaries must be at least 0.1 seconds apart.",
  "（後段）": "(latter part)",
  "請選擇內部分界；歌曲起訖固定。": "Choose an internal boundary; song endpoints are fixed.",
  "分界不能越過相鄰段落，每段至少 0.1 秒。": "A boundary cannot cross neighboring segments; each must be at least 0.1 seconds.",
  "請選擇內部分界。": "Choose an internal boundary.",
  "時間請輸入 mm:ss 或 mm:ss.sss。": "Enter time as mm:ss or mm:ss.sss.",
  "合成校正或交叉淡化設定無效。": "Invalid mix correction or crossfade settings.",
  "試聽無法播放：": "Cannot play preview:",
  "另一分頁已更新這份草稿，請重新整理頁面後繼續；錄音仍保留。": "Another tab updated this draft. Reload before continuing; recordings are retained.",
  "本段尚未選用錄音，請先錄這一段，或在右側挑選演唱版本。": "No take selected for this segment. Record it or choose a take on the right.",
  "加入伴樂需要已保存的伴奏音軌，請先補建音軌，或改選「純人聲」。": "Adding backing requires a saved instrumental stem. Rebuild stems or choose vocals only.",
  "無法讀取本段人聲錄音，請確認歌曲庫。": "Cannot read this segment’s vocals. Check the library.",
  "正在播放本段原始人聲錄音，不加入伴樂、不套用音量平衡或延時校正。": "Playing original segment vocals without backing, balance, or timing correction.",
  "此錄音缺少歌曲時間資訊，請改選「純人聲」。": "This recording lacks song timing. Choose vocals only.",
  "伴樂長度不足，請補建完整音軌，或改選「純人聲」。": "Backing is too short. Rebuild full stems or choose vocals only.",
  "已刪除此版錄音。請重新挑選本段版本或重新錄製；其他錄音與已另存成品保留。": "Take deleted. Choose another take or record again. Other recordings and saved results are kept.",
  "此版錄音已刪除，但草稿或列表更新失敗：": "Take deleted, but draft or list refresh failed:",
  "未能完成刪除：": "Could not finish deletion:",
  "正在讀取要清除的分段錄音清單…": "Reading segment recordings to clear…",
  "此歌曲的分段錄音已清空，目前剩餘 0 筆。": "This song’s segment recordings are cleared. 0 remaining.",
  "分界與版本選擇已保存。原始錄音保留。": "Boundaries and take selections saved. Original recordings retained.",
  "原唱區間已保存，請重新試合完整一版。": "Original vocal regions saved. Assemble the full mix again.",
  "目前選擇純人聲：不加入原唱，也不套用「只用原唱」替換。設定仍保留。": "Vocals-only selected: original vocals are not added and original-only replacement is not applied. Settings are retained.",
  "需先準備並保留歌曲分離音軌，才能加入原唱。": "Prepare and keep separated stems before adding original vocals.",
  "設定隨本歌曲草稿保存；調整後請重新試合。原唱使用歌曲目前的 Key，不套用收音延時校正。": "Regions save with this song’s draft. Assemble again after changes. Original vocals use the current song key without microphone timing correction.",
  "分段模式 · 不計整首分數": "Segment mode · No whole-song score",
  "手動比例＋自動微調：音量可調 0–200%，兩路各自最多修正 ±3 dB，0% 保持靜音。": "Manual levels + automatic fine-tuning: 0–200%, up to ±3 dB correction per track. 0% stays muted.",
  "自動平衡：人聲 75%、伴樂 45% 為基準，各自最多修正 ±6 dB；下方手動數值不參與。": "Automatic balance: baseline vocals 75%, backing 45%, up to ±6 dB correction each. Manual values below are ignored.",
  "已存到錄音後處理": "Saved for post-production",
  "直接播放原始收音": "Playing raw input directly",
  "本段尚未選用錄音；錄完保存後即可試聽，也可在右側挑選已錄版本。": "No take selected. Preview after recording and saving, or choose an existing take on the right.",
  "尚未選用錄音／未錄處留空": "No take selected / Leave unrecorded parts empty",
  "已選版本未找到": "Selected take not found",
  "另保留草稿原先選用的錄音，可改選本段版本。": "The draft’s previously selected take is also retained. You can choose a take from this segment instead.",
  "所有段落都有可用人聲；可試合完整版本。": "All segments have usable vocals. Assemble the full mix.",
  "停止循環練唱": "Stop loop practice",
  "歌曲範圍與草稿不同，請載入原先版本。": "Song range differs from the draft. Load the original version.",
  "復原紀錄歌曲不同。": "Undo history belongs to another song.",
  "已讀取分段草稿。": "Segment draft loaded.",
  "可開啟分段模式，邊播放邊加入分界。": "Enable segment mode and add boundaries during playback.",
  "無法開啟草稿：": "Cannot open draft:",
  "請先結束並結算目前的整首演唱，再使用分段模式。": "Finish and score the current whole-song performance before using segment mode.",
  "分段模式已開啟。播放中按「在此分段」，稍後可拖曳或精確調整時間。": "Segment mode enabled. Click “Split here” during playback, then drag boundaries or edit exact times.",
  "分段操作已取消。": "Segment operation canceled.",
  "播放器尚未確認跳到指定位置，請重試。": "Player has not confirmed seeking to the requested position. Retry.",
  "本段已保存，可按「試聽本段錄音」立即聽這一版，也可切換演唱版本；原先錄音保留。": "Segment saved. Preview it now or switch takes; previous recordings are retained.",
  "本段收音中斷，請查看錄音狀態中的保留片段。": "Segment input interrupted. Check recording status for the retained portion.",
  "沒有完成新的錄音；既有版本保留。": "No new recording completed. Existing takes retained.",
  "錄音已停止；草稿／保存狀態請確認：": "Recording stopped. Check draft / save status:",
  "請先結束整首演唱。": "Finish the whole-song performance first.",
  "提前播放請輸入 0～60 的整數秒數。": "Enter pre-roll as a whole number from 0 to 60 seconds.",
  "原唱＋伴樂": "Original vocals + backing",
  "伴樂": "Backing",
  "只有伴樂帶唱需要已保存的伴奏音軌，請先補建音軌。": "Backing-only guide playback requires saved instrumental stems. Rebuild stems first.",
  "伴樂長度不足，請補建完整試聽音軌。": "Backing is too short. Rebuild full preview stems.",
  "麥克風未就緒，請查看收音設定。": "Microphone not ready. Check input settings.",
  "無法完成本段錄音：": "Cannot complete segment recording:",
  "正在讀取各段乾淨人聲並試合…": "Reading clean vocals for each segment and assembling…",
  "尚未完整涵蓋：": "Incomplete coverage:",
  "。請補唱，或勾選「允許未錄範圍保留靜音」。": ". Record the missing parts or allow silence in unrecorded regions.",
  "找不到採用版本，請確認歌曲庫。": "Selected take not found. Check the library.",
  "乾淨人聲音檔無法讀取。": "Cannot read clean vocal audio.",
  "至少需錄好一段並選用錄音版本。": "Record at least one segment and select a take.",
  "加入伴樂或原唱需要已保存的分離音軌。": "Adding backing or original vocals requires saved stems.",
  "分離音軌長度不足，請補建完整音軌。": "Separated stems are too short. Rebuild full stems.",
  "· 分段合成": "· Segment mix",
  "已復原上一次分界／版本調整。": "Last boundary / take change undone.",
  "合併的兩段使用不同版本，請重新挑選演唱版本。": "Merged segments used different takes. Select a take again.",
  "草稿已保存於目前瀏覽器；各次演唱錄音沿用歌曲庫保存。": "Draft saved in this browser. Individual takes remain saved in the song library.",
  "已移除分界。兩段原先採用的版本不同，合併後請重新挑選版本；原始錄音都保留。": "Boundary removed. The merged segments used different takes; select a take again. All original recordings retained.",
  "音量已記住。純人聲原檔試聽不套用音量，請選「人聲＋伴樂／和音」邊聽邊調整。": "Levels remembered. Raw vocal preview ignores these levels; choose vocals + backing / harmonies to adjust while listening.",
  "音量已記住；試聽會先完成整段混音，再接續目前位置播放。滿意後可保存最新音量到錄音後處理。": "Levels remembered. The complete preview will be rendered before resuming at the current position. Save the latest levels for post-production when satisfied.",
  "下次分段錄音只用伴樂／和音帶唱。": "Next segment take uses backing / harmonies only for guidance.",
  "下次分段錄音播放原唱＋伴樂帶唱。": "Next segment take uses original vocals + backing for guidance.",
  "正在將最新試聽音量合成至成品…": "Rendering the latest preview levels into the result…",
  "已存到錄音後處理，已套用最新音量，可繼續後製與 A/B 比較。分段素材仍保留在分段區。": "Saved for post-production with the latest levels. Continue production and A/B comparison. Segment sources remain in the segment area.",
  "試合設定已變更，請重新試合完整一版。": "Mix settings changed. Assemble the full mix again.",
  "另一分頁已變更草稿，請重新整理後再編輯；現有錄音保留。": "Another tab changed the draft. Reload before editing; existing recordings retained.",
  "分段錄音需使用原速播放。": "Segment recording requires normal playback speed.",
  "保留尾音": "Keeping tail",
  "錄製中": "Recording",
  "缺少原唱音軌，請重新試合。": "Original vocal stem missing. Assemble again.",
  "齒音頻率": "Sibilance frequency",
  "音準修正": "Pitch correction",
  "無效的音準修正設定。": "Invalid pitch correction settings.",
  "分析人聲": "Analyzing vocals",
  "這筆錄音沒有原唱音高基準，請改選「最近半音」。": "This recording has no original pitch reference. Choose nearest semitone.",
  "修正音準": "Correcting pitch",
  "降噪／齒音處理": "Noise reduction / De-essing",
  "無效的人聲音訊。": "Invalid vocal audio.",
  "原始歌聲含有無效取樣，無法處理。": "Original vocals contain invalid samples and cannot be processed.",
  "降低呼吸聲": "Reducing breaths",
  "人聲處理完成": "Vocal processing complete",
  "人聲處理逾時，請先用片段或降低處理強度。": "Vocal processing timed out. Try a clip or lower the processing strength.",
  "人聲處理無法啟動，請重新整理頁面。": "Cannot start vocal processing. Reload the page.",
  "沒有足夠的無人聲底噪片段，降噪略過；其餘效果保留。": "Insufficient unvoiced background noise. Noise reduction skipped; other effects retained.",
  "已完成": "Complete",
  "未完成": "Incomplete",
  "處理中": "Processing",
  "（預設）": "(default)",
  "我的錄音": "My recording",
  "整首": "Full song",
  "片段": "Clip",
  "其他歌曲": "Other song",
  "未載入歌曲": "No song loaded",
  "目前歌曲": "Current song",
  "自動分析": "Auto-detect",
  "未完成：": "Incomplete:",
  "準備試聽…": "Preparing preview…",
  "配樂": "Backing",
  "抒情": "Ballad",
  "流行": "Pop",
  "溫暖": "Warm",
  "明亮": "Bright",
  "主歌": "Verse",
  "副歌": "Chorus",
  "前奏": "Intro",
  "間奏": "Interlude",
  "請先啟動本機唱錄工具，再製作 MV。": "Start local recording tools before creating a music video.",
  "請更新並重新啟動本機工具，才能製作 MV。": "Update and restart local tools to create music videos.",
  "MV 請求失敗。": "Music video request failed.",
  "目前 MV 正在製作，請先完成或取消，再更換來源。": "A music video is being created. Finish or cancel it before changing sources.",
  "沒有可用的翻唱音檔。": "No usable cover audio.",
  "翻唱來源：": "Cover source:",
  "填寫歌名與翻唱者，再按「開始製作翻唱 MV」。": "Enter song title and cover singer, then create the music video.",
  "請填寫歌名與翻唱者。": "Enter the song title and cover singer.",
  "正在將選取音檔交給本機製作…": "Sending selected audio to local video processing…",
  "MV 已保存，正在載入預覽…": "Music video saved. Loading preview…",
  "MV 已完成。保存位置：": "Music video complete. Saved at:",
  "已取消 MV 製作。": "Music video creation canceled.",
  "這份 MV 已從本機刪除，可使用音檔重新製作。": "This video was deleted locally. Recreate it from the audio if needed.",
  "本機音檔 · 預設聲波畫面": "Local audio · Waveform view",
  "本機 MV · 影片留在本機": "Local video · Files stay on your computer",
  "選擇本機音檔": "Choose local audio",
  "已匯入的音檔": "Imported audio files",
  "載入音檔": "Load audio",
  "MP3／WAV 音檔，使用預設聲波畫面。": "MP3 / WAV audio with a waveform view.",
  "MP4／MOV／MKV／WebM 影片。": "MP4 / MOV / MKV / WebM video.",
  "最多 2 GB、15 分鐘。工作副本保存在歌曲庫的 .local-mv 資料夾，原檔保留，不上傳雲端。": "Up to 2 GB and 15 minutes. A working copy is stored in the library’s .local-mv folder. Original retained; no cloud upload.",
  "本機工具未連線。": "Local tools offline.",
  "請更新並重新啟動本機工具，才能匯入 MP3／WAV 音檔。": "Update and restart local tools to import MP3 / WAV audio.",
  "請更新並重新啟動本機工具，才能匯入本機 MV。": "Update and restart local tools to import local videos.",
  "本機 MV 處理失敗。": "Local video processing failed.",
  "選擇已匯入的音檔": "Choose imported audio",
  "正在讀取…": "Reading…",
  "請先選擇已匯入的檔案。": "Choose an imported file first.",
  "正在取消匯入…": "Canceling import…",
  "檔案格式與所選來源不符，請重新選擇。": "File format does not match the selected source. Choose again.",
  "檔案上限 2 GB。": "Maximum file size is 2 GB.",
  "正在將檔案傳到這台電腦的歌曲庫，請稍候；不會上傳雲端…": "Copying the file to this computer’s library. Please wait; nothing is uploaded to the cloud…",
  "已取消匯入。": "Import canceled.",
  "已取消匯入；原檔保留。": "Import canceled. Original file retained.",
  "本機媒體無法播放，請重新載入；若已手動刪除檔案，請重新匯入。": "Cannot play local media. Reload it, or import again if the file was deleted manually.",
  "請按播放器的播放按鈕：": "Press the player’s play button:",
  "播放": "Play",
  "錄音診斷本機工具未連線，請啟動本機工具。": "Recording diagnostics are offline. Start the local tools.",
  "原音（預設，不額外調整音色）": "Original (default, no extra tone adjustment)",
  "直接載入本機基準，可試聽分離結果": "Loaded local reference directly, separated stems available for preview",
  "直接載入本機基準，音檔已清除": "Loaded local reference directly, audio files cleared",
  "已保存到本機，可試聽分離結果": "Saved locally, separated stems available for preview",
  "已保存到本機，音檔已清除": "Saved locally, audio files cleared",
  "🎬 已保存 MV": "🎬 Saved music videos",
  "搜尋 · 播放 · 下載 · 刪除": "Search · Play · Download · Delete",
  "列出歌曲庫「vedio」資料夾裡本工具做的 MV，最新的在最上面。可搜尋、播放、下載，或勾選後刪除；刪除 MV 不會刪掉錄音與原始音檔。": "Lists the music videos this tool made in the library’s “vedio” folder, newest first. Search, play, download, or tick and delete; deleting a video doesn’t delete recordings or original audio.",
  "用歌名或翻唱者搜尋": "Search by song or singer",
  "搜尋已保存 MV": "Search saved music videos",
  "刪除選取的 MV": "Delete selected videos",
  "展開後讀取清單。": "The list loads when you expand this section.",
  "請先啟動本機唱錄工具。": "Start local recording tools first.",
  "MV 清單讀取失敗。": "Couldn’t read the music video list.",
  "正在讀取 MV 清單…": "Loading the music video list…",
  "目前沒有已保存的 MV。": "No saved music videos yet.",
  "正在確認目前歌曲庫的 MV 數量與容量…": "Checking music video count and size in the current library…",
  "清理完成：目前沒有可清理的 MV。": "Cleanup complete. No removable music videos.",
  "已取消清理，MV 保留。": "Cleanup canceled. Videos retained."
};

export const templates = [
  ["錄製第 {0} 段", "Record segment {0}", [0]],
  ["顯示 {0}／{1} 個歌曲基準。", "Showing {0} of {1} song references."],
  [
    "本機回應 {0}",
    "Local response {0}",
    [
      0
    ]
  ],
  [
    "播放追蹤已連線 · 本機已收到 {0}（不錄音）",
    "Playback tracking connected · Received locally: {0} (no audio recorded)",
    [
      0
    ]
  ],
  [
    "播放追蹤未送達：{0}。這次紀錄尚未收到。",
    "Playback tracking not delivered: {0}. This log has not been received.",
    [
      0
    ]
  ],
  [
    "歌聲輸出中斷：{0}",
    "Vocal monitoring interrupted: {0}",
    [
      0
    ]
  ],
  [
    "本機歌聲直送喇叭中 · {0}",
    "Native direct vocal monitoring · {0}",
    [
      0
    ]
  ],
  [
    "低延遲歌聲輸出中 · {0}",
    "Low-latency vocal monitoring · {0}",
    [
      0
    ]
  ],
  [
    "歌聲輸出失敗：{0}",
    "Vocal monitoring failed: {0}",
    [
      0
    ]
  ],
  [
    "喇叭 {0}{1}",
    "Speaker {0}{1}",
    [
      0,
      1
    ]
  ],
  [
    "影片無法播放（{0}）。可能禁止嵌入、已移除或需登入；請換影片。",
    "Cannot play this video ({0}). It may block embedding, be removed, or require sign-in. Try another video.",
    [
      0
    ]
  ],
  [
    "已載入{0}：{1}。請按播放，或準備歌曲基準。",
    "Loaded {0}: {1}. Press play or prepare the song reference.",
    [
      0
    ]
  ],
  [
    "讀取成功：{0} bytes，只在本機記憶體中，未保存。",
    "Read {0} bytes into local memory only; not saved.",
    [
      0
    ]
  ],
  [
    "{0}測試未通過：{1}",
    "{0} test failed: {1}",
    [
      0,
      1
    ]
  ],
  [
    "{0} ms（估計）",
    "{0} ms (estimated)",
    [
      0
    ]
  ],
  [
    "輸入：{0}{1}\n取樣率：{2} Hz\n輸入延遲：{3}\nWeb Audio 輸出延遲：{4}\n分析輸出：{5}\n回音消除：{6}\n\n輸出估計屬於本頁 AudioContext，不代表 YouTube 的延遲；不會自動填入補償值。",
    "Input: {0}{1}\nSample rate: {2} Hz\nInput latency: {3}\nWeb Audio output latency: {4}\nAnalysis output: {5}\nEcho cancellation: {6}\n\nOutput estimates belong to this page’s AudioContext, not YouTube. Compensation is not filled in automatically.",
    [
      1,
      2,
      3,
      4,
      5,
      6
    ]
  ],
  [
    "收音失敗：{0}",
    "Input failed: {0}",
    [
      0
    ]
  ],
  [
    "{0}{1} cents · 相對最近音名，非歌曲分數",
    "{0}{1} cents · Relative to the nearest note, not a song score",
    [
      0,
      1
    ]
  ],
  [
    "麥克風 {0}",
    "Microphone {0}",
    [
      0
    ]
  ],
  [
    "缺少或無法使用：{0}。請參考下方安裝指引。",
    "Missing or unavailable: {0}. See the installation guide below.",
    [
      0
    ]
  ],
  [
    "下一步 {0}／8 · {1}",
    "Next {0}/8 · {1}",
    [
      0,
      1
    ]
  ],
  [
    "前往{0}",
    "Go to {0}",
    [
      0
    ]
  ],
  [
    "{0}：音高誤差 {1} 音分內、進拍誤差 {2} 毫秒內給滿分，超過逐步扣分。100 音分＝1 個半音；難度與八度、評分範圍分開設定。",
    "{0}: full marks within {1} cents of pitch and {2} ms of timing; larger errors reduce scores. 100 cents = 1 semitone. Difficulty, octave matching, and scoring range are separate settings.",
    [
      0,
      1,
      2
    ]
  ],
  [
    "本輪評分難度：{0}（本輪固定）",
    "This round’s difficulty: {0} (fixed for this round)",
    [
      0
    ]
  ],
  [
    "{0} 本機工具未回覆清除結果；閒置工作會於約 15 分鐘後自動清理。",
    "{0} Local tools did not confirm cleanup. Idle work is automatically cleared after about 15 minutes.",
    [
      0
    ]
  ],
  [
    "歌曲庫位置：{0}。已記住這台電腦的設定。",
    "Library location: {0}. Saved for this computer.",
    []
  ],
  [
    "無法設定歌曲庫：{0}",
    "Cannot set library location: {0}",
    [
      0
    ]
  ],
  [
    "分離模式已變更，尚未套用。請按「準備歌曲基準」載入或建立所選模式；目前仍是{0}",
    "Separation mode changed but not applied. Prepare the reference to load or create that mode. Currently still using {0}",
    [
      0
    ]
  ],
  [
    "分離模型已變更，尚未套用。請按「準備歌曲基準」載入或建立所選模型；目前仍是 {0}。",
    "Separation model changed but not applied. Prepare the reference to load or create that model. Currently still using {0}.",
    [
      0
    ]
  ],
  [
    "目前已載入：{0} · {1} · {2} · {3}",
    "Loaded: {0} · {1} · {2} · {3}",
    [
      1,
      2,
      3
    ]
  ],
  [
    "這首歌只有評分基準，未保留人聲／伴奏音檔。{0}",
    "This song has a scoring reference only, without saved vocal / instrumental audio. {0}",
    [
      0
    ]
  ],
  [
    "{0}試聽 · {1} · {2} · 本機音檔",
    "{0} preview · {1} · {2} · Local audio",
    [
      0,
      1,
      2
    ]
  ],
  [
    "{0} · {1} · {2} · {3} 音高 · {4} · {5} · {6} MB · {7}",
    "{0} · {1} · {2} · {3} pitch · {4} · {5} · {6} MB · {7}",
    [
      0,
      1,
      2,
      3,
      4,
      5,
      6,
      7
    ]
  ],
  [
    "前 {0} 秒",
    "First {0} seconds",
    [
      0
    ]
  ],
  [
    "載入 {0}",
    "Load {0}",
    []
  ],
  [
    "已就緒：{0} · {1} · {2} · {3} 音高。",
    "Ready: {0} · {1} · {2} · {3} pitch.",
    [
      1,
      2,
      3
    ]
  ],
  [
    "已刪除：{0}（基準與試聽音軌）。",
    "Deleted: {0} (reference and preview stems).",
    []
  ],
  [
    "刪除失敗：{0}",
    "Delete failed: {0}",
    [
      0
    ]
  ],
  [
    "這台電腦已保存 {0} 個歌曲基準。金色標記表示有整首待確認或分段錄音。",
    "{0} song references saved on this computer. Gold markers indicate pending whole-song or segment recordings.",
    [
      0
    ]
  ],
  [
    "無法讀取歌曲庫：{0}",
    "Cannot read library: {0}",
    [
      0
    ]
  ],
  [
    "選取 {0} {1} 分",
    "Select {0}, score {1}",
    [
      1
    ]
  ],
  [
    "{0} 分",
    "{0} points",
    [
      0
    ]
  ],
  [
    "已清除 {0} 筆分數紀錄；演唱錄音與歌曲仍保留。",
    "Cleared {0} score entries. Recordings and songs are preserved.",
    [
      0
    ]
  ],
  [
    "本輪已結算 · 評分難度：{0}",
    "Round scored · Difficulty: {0}",
    [
      0
    ]
  ],
  [
    "已就緒：{0} · 基準已保留，直接按「從頭開始唱」即可再唱。",
    "Ready: {0} · Reference retained. Click “Sing from the start” to sing again.",
    []
  ],
  [
    "{0}推論 100%；正在完成音軌，尚未就緒。",
    "{0} inference 100%; finalizing stems, not ready yet.",
    [
      0
    ]
  ],
  [
    "{0}分離 {1}%（本階段）",
    "{0} separation {1}% (this stage)",
    [
      0,
      1
    ]
  ],
  [
    "{0} {1}%（尚需驗證及保存）",
    "{0} {1}% (validation and saving still required)",
    [
      0,
      1
    ]
  ],
  [
    "{0} · 已隨歌曲版本保存。",
    "{0} · Saved with this song version.",
    [
      0
    ]
  ],
  [
    "已就緒：{0} · {1} · {2} · {3} 音高 · {4} · {5} 秒 · {6}{7}。",
    "Ready: {0} · {1} · {2} · {3} pitch · {4} · {5} seconds · {6}{7}.",
    [
      1,
      2,
      3,
      4,
      5,
      6,
      7
    ]
  ],
  [
    "自動估計約 {0} BPM；播放時顯示拍點，可能出現半速／倍速誤差。",
    "Estimated tempo about {0} BPM. Beats display during playback; half / double tempo errors are possible.",
    [
      0
    ]
  ],
  [
    "準備失敗：{0}",
    "Preparation failed: {0}",
    [
      0
    ]
  ],
  [
    "正在準備 {0}，完成後會保存到歌曲庫…",
    "Preparing {0}; it will be saved to the library when ready…",
    []
  ],
  [
    "播放器未就緒：{0}",
    "Player not ready: {0}",
    [
      0
    ]
  ],
  [
    "無法準備歌曲：{0}",
    "Cannot prepare song: {0}",
    [
      0
    ]
  ],
  [
    "已選 {0}，尚未套用。{1}",
    "Selected {0}, not applied yet. {1}",
    [
      0,
      1
    ]
  ],
  [
    "目前播放 {0}；請按「建立／載入此 Key」。",
    "Playing {0}; click “Create / Load this key”.",
    [
      0
    ]
  ],
  [
    "未開始演唱：{0}{1}",
    "Not started: {0}{1}",
    [
      0,
      1
    ]
  ],
  [
    "{0} 本次演唱資料仍保留，可先結算。",
    "{0} Performance data retained. You can score it first.",
    [
      0
    ]
  ],
  [
    "辨識 {0}/5 音，建議補償 {1}{2} ms，時間差散布 {3} ms。{4}與 YouTube 播放路徑可能不同，套用後可再手動微調。",
    "Detected {0}/5 notes. Suggested compensation {1}{2} ms; timing spread {3} ms. {4}The playback path may differ from YouTube; fine-tune manually after applying.",
    [
      0,
      1,
      2,
      3,
      4
    ]
  ],
  [
    "{0} · {1} · {2} · {3} · 基準長度 {4}",
    "{0} · {1} · {2} · {3} · Reference length {4}",
    [
      1,
      2,
      3,
      4
    ]
  ],
  [
    "已保存 {0} 段不計分區間。",
    "Saved {0} unscored regions.",
    [
      0
    ]
  ],
  [
    "未保存：{0}",
    "Not saved: {0}",
    [
      0
    ]
  ],
  [
    "{0} · 只影響錄音，不影響評分；每輪開始前設定。",
    "{0} · Affects recording only, not scoring. Set before each round.",
    [
      0
    ]
  ],
  [
    "{0} · {1}{2} · {3} · {4} 秒{5}{6}",
    "{0} · {1}{2} · {3} · {4} seconds{5}{6}",
    [
      0,
      1,
      2,
      3,
      4,
      5,
      6
    ]
  ],
  [
    "· 歌聲校正 {0} ms",
    "· Vocal correction {0} ms",
    [
      0
    ]
  ],
  [
    "乾淨歌聲保存失敗：{0}",
    "Failed to save clean vocals: {0}",
    [
      0
    ]
  ],
  [
    "自動保存失敗，停止後請下載備份：{0}",
    "Autosave failed. Download a backup after stopping: {0}",
    [
      0
    ]
  ],
  [
    "錄音已就緒{0}，影片開始播放時同步錄製。",
    "Recording ready{0}. Starts in sync with video playback.",
    [
      0
    ]
  ],
  [
    "● 錄音中 · {0}（錄製中暫存，停止後存入歌曲庫）",
    "● Recording · {0} (temporary storage during recording; saved to library after stopping)",
    [
      0
    ]
  ],
  [
    "正在將錄音歌聲校正 {0} ms 並保存…",
    "Applying {0} ms vocal correction and saving…",
    [
      0
    ]
  ],
  [
    "診斷未完整保存：{0}。",
    "Diagnostics not fully saved: {0}.",
    [
      0
    ]
  ],
  [
    "延時校正未完成，已保留待確認錄音：{0}",
    "Timing correction incomplete; pending take retained: {0}",
    [
      0
    ]
  ],
  [
    "錄音已保留為待確認版本 · 歌聲校正 {0} ms。請先試聽，滿意再存到錄音後處理。",
    "Recording kept as a pending take · Vocal correction {0} ms. Preview it, then save for post-production when satisfied.",
    [
      0
    ]
  ],
  [
    "收音中斷，已保留錄音片段，可下載備份：{0}",
    "Input interrupted; recorded portion retained. Download a backup: {0}",
    [
      0
    ]
  ],
  [
    "錄音未完整保存，請先按「下載未保存錄音」備份：{0}",
    "Recording not fully saved. Download the unsaved recording as a backup first: {0}",
    [
      0
    ]
  ],
  [
    "無法讀取錄音清單：{0}",
    "Cannot read recording list: {0}",
    [
      0
    ]
  ],
  [
    "{0} · 人聲修正 {1} dB{2} · 輸出峰值保護開啟",
    "{0} · Vocal adjustment {1} dB{2} · Peak protection enabled",
    [
      0,
      1,
      2
    ]
  ],
  [
    "· 配樂／和音修正 {0} dB",
    "· Backing / harmony adjustment {0} dB",
    [
      0
    ]
  ],
  [
    "正在清除後處理錄音：{0}／{1} 筆…",
    "Clearing production recordings: {0}/{1}…",
    [
      0,
      1
    ]
  ],
  [
    "已刪除 {0} 筆錄音及其後處理資料；待確認錄音與分段素材保留。",
    "Deleted {0} recordings and their production data. Pending takes and segment sources are preserved.",
    [
      0
    ]
  ],
  [
    "未全部刪除：{0}",
    "Some items were not deleted: {0}",
    [
      0
    ]
  ],
  [
    "瀏覽器錄音儲存不可用：{0}",
    "Browser recording storage unavailable: {0}",
    [
      0
    ]
  ],
  [
    "已保存至 {0}。",
    "Saved to {0}.",
    []
  ],
  [
    "暫存在此瀏覽器，尚未搬存：{0}",
    "Temporarily stored in this browser, not migrated: {0}",
    [
      0
    ]
  ],
  [
    "本機錄音目錄未連線；瀏覽器待搬存資料仍保留。{0}",
    "Local recording folder disconnected. Browser copies awaiting migration are retained. {0}",
    [
      0
    ]
  ],
  [
    "正在搬存錄音 {0}：{1}…",
    "Migrating recording {0}: {1}…",
    [
      0
    ]
  ],
  [
    "錄音位置：{0}。{1}{2}",
    "Recording location: {0}. {1}{2}",
    [
      1,
      2
    ]
  ],
  [
    "已搬存 {0} 筆，瀏覽器舊副本已清除。",
    "Migrated {0} recordings; old browser copies removed.",
    [
      0
    ]
  ],
  [
    "部分錄音仍留在瀏覽器：{0}",
    "Some recordings remain in the browser: {0}",
    [
      0
    ]
  ],
  [
    "{0} 秒",
    "{0} seconds",
    [
      0
    ]
  ],
  [
    "{0} · 殘響 {1}% · {2} · 尾音 {3} 秒 · 預延遲 {4} ms · 明亮 {5} · 寬度 {6}% · 回聲 {7}%{8}。",
    "{0} · Reverb {1}% · {2} · Decay {3} sec · Pre-delay {4} ms · Brightness {5} · Width {6}% · Delay {7}%{8}.",
    [
      0,
      1,
      2,
      3,
      4,
      5,
      6,
      7,
      8
    ]
  ],
  [
    "／{0} ms／{1} 次／每次保留 {2}%／{3}",
    "/ {0} ms / {1} repeats / {2}% retained / {3}",
    [
      0,
      1,
      2,
      3
    ]
  ],
  [
    "{0} EQ 低／中／高：{1} dB · 柔化：{2} · 壓縮：{3}。",
    "{0} EQ low / mid / high: {1} dB · Smoothing: {2} · Compression: {3}.",
    [
      0,
      1,
      2,
      3
    ]
  ],
  [
    "{0} · {1} · {2} · {3} · {4} 秒",
    "{0} · {1} · {2} · {3} · {4} seconds",
    [
      0,
      1,
      2,
      3,
      4
    ]
  ],
  [
    "錄音原始基準：{0}。目前已載入：{1}。{2}",
    "Original reference: {0}. Currently loaded: {1}. {2}",
    [
      0,
      1,
      2
    ]
  ],
  [
    "原始錄音約 {0} 秒；目前成品 {1} 秒。剪輯秒數以套用延時後、尚未裁切的完整錄音為準。{2}",
    "Original recording about {0} seconds; current result {1} seconds. Trim times refer to the full recording after timing correction and before cropping. {2}",
    [
      0,
      1,
      2
    ]
  ],
  [
    "目前播放器 0 秒對應原始錄音 {0} 秒。",
    "Player time 0 corresponds to {0} seconds in the original recording.",
    [
      0
    ]
  ],
  [
    "{0} · {1} {2} · {3} · 校正 {4} ms · 總分 {5} · 音準 {6} · 進拍 {7} · 完整度 {8} · 可計分旋律 {9} 秒{10}",
    "{0} · {1} {2} · {3} · Correction {4} ms · Total {5} · Pitch {6} · Timing {7} · Completeness {8} · Scorable melody {9} seconds{10}",
    [
      0,
      1,
      2,
      3,
      4,
      5,
      6,
      7,
      8,
      9,
      10
    ]
  ],
  [
    "· 同音檔 0 ms 進拍 {0}",
    "· Same audio timing score at 0 ms: {0}",
    [
      0
    ]
  ],
  [
    "正在試聽：{0}{1}{2}{3}",
    "Previewing: {0}{1}{2}{3}",
    [
      1,
      2,
      3
    ]
  ],
  [
    "只聽人聲：{0}{1}{2}{3}（已保存的效果）",
    "Vocals only: {0}{1}{2}{3} (saved effects)",
    [
      1,
      2,
      3
    ]
  ],
  [
    "{0} · 已保存後處理成品 · {1}",
    "{0} · Saved production result · {1}",
    [
      1
    ]
  ],
  [
    "刪除這筆錄音、原始歌聲及其後處理資料？此操作無法復原。\n{0} · {1}",
    "Delete this recording, original vocals, and production data? This cannot be undone.\n{0} · {1}",
    [
      1
    ]
  ],
  [
    "清除錄音後處理清單的全部 {0} 筆？包含所有歌曲的已保存錄音與後製成品，以及各筆附帶的人聲和後處理資料。\n待確認錄音、分段素材及歌曲庫保留。此操作無法復原。",
    "Clear all {0} entries in the production list? This includes saved recordings and production results for all songs, with their vocals and production data.\nPending takes, segment sources, and the song library are kept. This cannot be undone.",
    [
      0
    ]
  ],
  [
    "正在清除：0／{0} 筆…",
    "Clearing: 0/{0}…",
    [
      0
    ]
  ],
  [
    "正在清除：{0}／{1} 筆，已刪除 {2} 筆{3}…",
    "Clearing: {0}/{1}, deleted {2}{3}…",
    [
      0,
      1,
      2,
      3
    ]
  ],
  [
    "，失敗 {0} 筆",
    ", {0} failed",
    [
      0
    ]
  ],
  [
    "已刪除 {0} 筆；後處理清單剩餘 {1} 筆。{2}",
    "Deleted {0}; {1} entries remain in the production list. {2}",
    [
      0,
      1,
      2
    ]
  ],
  [
    "{0} 筆未刪除，可重試：{1}",
    "{0} not deleted. Retry: {1}",
    [
      0,
      1
    ]
  ],
  [
    "已刪除 {0} 筆；清單更新失敗，請重新整理確認：{1}",
    "Deleted {0}; list refresh failed. Refresh to check: {1}",
    [
      0,
      1
    ]
  ],
  [
    "已套用 {0} 組「{1}」音色，空間設定保留；按試聽聽取新效果，滿意後重新合成另存。",
    "Applied “{1}” tone to set {0}. Space settings retained. Preview the effect, then render a copy when satisfied.",
    [
      0,
      1
    ]
  ],
  [
    "已套用{0} 組「{1}」，按試聽聽取新效果；滿意後重新合成另存。",
    "Applied “{1}” to set {0}. Preview the effect, then render a copy when satisfied.",
    [
      0,
      1
    ]
  ],
  [
    "正在以 {0} 重新評分…",
    "Rescoring with {0}…",
    [
      0
    ]
  ],
  [
    "正在分析乾淨歌聲 {0}%…",
    "Analyzing clean vocals {0}%…",
    [
      0
    ]
  ],
  [
    "正在套用{0}歌聲柔化並合成…",
    "Applying {0} vocal smoothing and rendering…",
    [
      0
    ]
  ],
  [
    "已另存校正後錄音{0} · 歌唱者 {1}%{2}，請按播放器試聽；可轉 MP3。原錄音保留，這筆成品也可繼續後製。",
    "Saved a corrected copy{0} · Singer {1}%{2}. Preview in the player or convert to MP3. Original retained; this result is also editable.",
    [
      0,
      1,
      2
    ]
  ],
  [
    "（歌聲柔化：{0}）",
    "(vocal smoothing: {0})",
    [
      0
    ]
  ],
  [
    "· 配樂／和音 {0}%",
    "· Backing / harmonies {0}%",
    [
      0
    ]
  ],
  [
    "MP3 已轉換並開始下載，同時保存至 {0}。",
    "MP3 converted; download started and saved to {0}.",
    []
  ],
  [
    "MP3 已轉換並開始下載，但尚未存入錄音目錄：{0}",
    "MP3 converted and downloading, but not yet saved in the recording folder: {0}",
    [
      0
    ]
  ],
  [
    "正在調整 {0} 組",
    "Editing {0}",
    []
  ],
  [
    "片段試聽目前 {0} 設定",
    "Preview current {0} settings on a clip",
    []
  ],
  [
    "重新合成 {0}（音量／延時／音色／剪輯）",
    "Render {0} again (levels / timing / tone / trim)",
    []
  ],
  [
    "保存至 {0}",
    "Saved to {0}",
    [
      0
    ]
  ],
  [
    "{0} 第 {1} 段 · {2}",
    "{0} region {1} · {2}",
    [
      0,
      1,
      2
    ]
  ],
  [
    "還原 {0} 預設設定",
    "Reset {0} to defaults",
    []
  ],
  [
    "{0} 項不同",
    "{0} differences",
    [
      0
    ]
  ],
  [
    "{0} 組欄位尚未完成：{1} 補齊後會繼續顯示差異。",
    "Set {0} has incomplete fields: {1} Differences resume when these are completed.",
    [
      0,
      1
    ]
  ],
  [
    "正在調整 {0}，兩組設定各自保留；按試聽才會播放新效果。",
    "Editing {0}. Each set keeps its own settings; preview again to hear changes.",
    []
  ],
  [
    "準備 {0}…",
    "Preparing {0}…",
    []
  ],
  [
    "● 正在聽 {0}",
    "● Listening to {0}",
    []
  ],
  [
    "▶ 試聽 {0}",
    "▶ Preview {0}",
    []
  ],
  [
    "情緒 {0} · 殘響 {1}% · 明亮 {2} · 寬度 {3}% · 回聲 {4}% · {5} 段局部效果 · 校正 {6} ms",
    "Mood {0} · Reverb {1}% · Brightness {2} · Width {3}% · Delay {4}% · {5} effect regions · Correction {6} ms",
    [
      0,
      1,
      2,
      3,
      4,
      5,
      6
    ]
  ],
  [
    "已還原 {0} 系統預設：原音、大廳殘響 20%、回聲 10%、音量 100%、校正 {1} ms，清理與音準修正關閉；另一組保留。按試聽即可重新比較。",
    "Restored {0} defaults: original tone, hall reverb 20%, delay 10%, volume 100%, correction {1} ms, cleanup and pitch correction off. Other set retained. Preview to compare again.",
    [
      0,
      1
    ]
  ],
  [
    "正在準備 {0} 片段…",
    "Preparing clip {0}…",
    []
  ],
  [
    "{0} · 原始錄音 {1} 秒 · 循環試聽中",
    "{0} · Original recording position {1} seconds · Looping preview",
    [
      0,
      1
    ]
  ],
  [
    "正在比較 {0}：{1}～{2} 秒{3}。試聽不另存錄音。",
    "Comparing {0}: {1}–{2} seconds{3}. Preview does not save another recording.",
    [
      1,
      2,
      3
    ]
  ],
  [
    "已選 {0}～{1} 秒，可按 A／B 試聽。",
    "Selected {0}–{1} seconds. Preview A or B.",
    [
      0,
      1
    ]
  ],
  [
    "錄音取樣不連續（{0} 個取樣），已保留錄音，請重新開啟收音。",
    "Recording samples are discontinuous ({0} samples). Recording retained; enable input again.",
    [
      0
    ]
  ],
  [
    "_柔化{0}",
    "_Smoothing{0}",
    [
      0
    ]
  ],
  [
    "人聲{0}%",
    "Vocals{0}%",
    [
      0
    ]
  ],
  [
    "配樂{0}%",
    "Backing{0}%",
    [
      0
    ]
  ],
  [
    "局部音量{0}段",
    "VolumeRegions{0}",
    [
      0
    ]
  ],
  [
    "壓縮{0}",
    "Compression{0}",
    [
      0
    ]
  ],
  [
    "音準修正{0}%_{1}",
    "PitchCorrection{0}%_{1}",
    [
      0,
      1
    ]
  ],
  [
    "殘響{0}%",
    "Reverb{0}%",
    [
      0
    ]
  ],
  [
    "預延遲{0}ms",
    "PreDelay{0}ms",
    [
      0
    ]
  ],
  [
    "殘響明亮{0}",
    "ReverbBrightness{0}",
    [
      0
    ]
  ],
  [
    "殘響寬度{0}%",
    "ReverbWidth{0}%",
    [
      0
    ]
  ],
  [
    "回聲{0}%_{1}ms_{2}次{3}",
    "Delay{0}%_{1}ms_{2}repeats{3}",
    [
      0,
      1,
      2,
      3
    ]
  ],
  [
    "局部效果{0}段",
    "EffectRegions{0}",
    [
      0
    ]
  ],
  [
    "剪輯{0}-{1}秒",
    "Trim{0}-{1}sec",
    [
      0,
      1
    ]
  ],
  [
    "淡入{0}秒",
    "FadeIn{0}sec",
    [
      0
    ]
  ],
  [
    "淡出{0}秒",
    "FadeOut{0}sec",
    [
      0
    ]
  ],
  [
    "_人聲後製{0}",
    "_VocalProduction{0}",
    [
      0
    ]
  ],
  [
    "{0}需介於 {1} 與 {2}。",
    "{0} must be between {1} and {2}.",
    [
      0,
      1,
      2
    ]
  ],
  [
    "情境_{0}",
    "Space_{0}",
    [
      0
    ]
  ],
  [
    "情緒_{0}",
    "Mood_{0}",
    [
      0
    ]
  ],
  [
    "{0} · 影片原聲靜音，播放同步變調音軌。",
    "{0} · Video audio muted; synchronized transposed stems playing.",
    [
      0
    ]
  ],
  [
    "{0} · {1} · {2} 秒{3}{4}",
    "{0} · {1} · {2} seconds{3}{4}",
    [
      1,
      2,
      3,
      4
    ]
  ],
  [
    "· 診斷未完整保存：{0}",
    "· Diagnostics not fully saved: {0}",
    [
      0
    ]
  ],
  [
    "正在試聽{0} · 校正 {1} ms。滿意後按「存到錄音後處理」。",
    "Previewing {0} · Correction {1} ms. Save for post-production when satisfied.",
    [
      0,
      1
    ]
  ],
  [
    "刪除待確認錄音「{0} · {1}」？此版錄音與人聲將刪除，無法復原。",
    "Delete pending take “{0} · {1}”? This recording and its vocals will be permanently deleted.",
    [
      1
    ]
  ],
  [
    "刪除「{0}」同一 Key 的全部 {1} 筆待確認錄音？\n\n只刪除這首的待確認整首錄音與人聲；其他歌曲、其他 Key、分段錄音及已存到錄音後處理的成品都保留。\n刪除後無法復原。",
    "Delete all {1} pending takes for “{0}” in this key?\n\nOnly this song’s pending whole-song recordings and vocals will be deleted. Other songs, keys, segments, and approved production results are kept.\nThis cannot be undone.",
    [
      1
    ]
  ],
  [
    "正在清除這首的 {0} 筆待確認錄音…",
    "Clearing {0} pending takes for this song…",
    [
      0
    ]
  ],
  [
    "正在清除待確認錄音：{0}／{1} 筆，已刪除 {2} 筆{3}…",
    "Clearing pending takes: {0}/{1}, deleted {2}{3}…",
    [
      0,
      1,
      2,
      3
    ]
  ],
  [
    "，{0} 筆失敗",
    ", {0} failed",
    [
      0
    ]
  ],
  [
    "已處理 {0}／{1} 筆，正在更新錄音清單…",
    "Processed {0}/{1}. Refreshing recording list…",
    [
      0,
      1
    ]
  ],
  [
    "已刪除這首的 {0} 筆待確認錄音。{1}",
    "Deleted {0} pending takes for this song. {1}",
    [
      0,
      1
    ]
  ],
  [
    "尚有 {0} 筆{1}。",
    "{0} remaining{1}.",
    [
      0,
      1
    ]
  ],
  [
    "診斷服務回應 {0}",
    "Diagnostic service response {0}",
    [
      0
    ]
  ],
  [
    "本機保留 {0} 次 · {1} MB · {2}",
    "Stored locally: {0} sessions · {1} MB · {2}",
    [
      0,
      1
    ]
  ],
  [
    "診斷未連線：{0}",
    "Diagnostics offline: {0}",
    [
      0
    ]
  ],
  [
    "已清除 {0} 次診斷；錄音與歌曲保留。",
    "Cleared {0} diagnostic sessions. Recordings and songs retained.",
    [
      0
    ]
  ],
  [
    "未清除：{0}",
    "Not cleared: {0}",
    [
      0
    ]
  ],
  [
    "診斷無法準備，尚未開始錄音：{0}",
    "Cannot prepare diagnostics; recording has not started: {0}",
    [
      0
    ]
  ],
  [
    "診斷無法保存，尚未開始錄音。請確認已更新並啟動本機工具：{0}",
    "Cannot save diagnostics; recording has not started. Check that updated local tools are running: {0}",
    [
      0
    ]
  ],
  [
    "診斷不完整，演唱錄音仍會繼續：{0}",
    "Diagnostics incomplete; performance recording continues: {0}",
    [
      0
    ]
  ],
  [
    "直接收音診斷中斷：{0}",
    "Direct-input diagnostics interrupted: {0}",
    [
      0
    ]
  ],
  [
    "診斷不完整：{0}",
    "Diagnostics incomplete: {0}",
    [
      0
    ]
  ],
  [
    "診斷未完整保存：{0}",
    "Diagnostics not fully saved: {0}",
    [
      0
    ]
  ],
  [
    "整首待確認 {0} 筆",
    "{0} pending whole-song takes",
    [
      0
    ]
  ],
  [
    "分段錄音 {0} 筆",
    "{0} segment recordings",
    [
      0
    ]
  ],
  [
    "載入 {0}{1}",
    "Load {0}{1}",
    [
      0,
      1
    ]
  ],
  [
    "第 {0} 段",
    "Segment {0}",
    [
      0
    ]
  ],
  [
    "{0}（後段）",
    "{0} (latter part)",
    [],
    [
      0
    ]
  ],
  [
    "試聽無法播放：{0}",
    "Cannot play preview: {0}",
    [
      0
    ]
  ],
  [
    "正在準備本段試聽：{0}…",
    "Preparing segment preview: {0}…",
    [],
    [
      0
    ]
  ],
  [
    "正在試聽本段錄音：{0} · 歌聲校正 {1} ms。可邊聽邊調人聲與伴樂音量，不必重錄。",
    "Previewing segment take: {0} · Vocal correction {1} ms. Adjust vocal and backing levels while listening without recording again.",
    [
      1
    ],
    [
      0
    ]
  ],
  [
    "刪除「{0} · {1} · {2} 秒」這一版錄音？\n目前有 {3} 段選用此版本，刪除後需重新挑選。\n此版人聲及錄音檔會刪除，無法復原；其他版本與已另存成品保留。",
    "Delete take “{0} · {1} · {2} seconds”?\nCurrently selected by {3} segments, which will need new take selections.\nThis take and its vocals will be permanently deleted. Other takes and saved results are kept.",
    [
      1,
      2,
      3
    ],
    [
      0
    ]
  ],
  [
    "清除「{0}」的全部 {1} 筆分段錄音？\n包含各段所有演唱版本，刪除後無法復原。\n段落分界、其他歌曲、整首錄音及錄音後處理中的已存成品都會保留。",
    "Clear all {1} segment recordings for “{0}”?\nIncludes every take for all segments. This cannot be undone.\nBoundaries, other songs, whole-song recordings, and saved production results are kept.",
    [
      1
    ]
  ],
  [
    "正在清除 {0} 筆分段錄音…",
    "Clearing {0} segment recordings…",
    [
      0
    ]
  ],
  [
    "正在清除分段錄音：{0}／{1} 筆{2}…",
    "Clearing segment recordings: {0}/{1}{2}…",
    [
      0,
      1,
      2
    ]
  ],
  [
    "已清除 {0} 筆分段錄音，{1} 筆未能清除，可重試。{2}",
    "Cleared {0} segment recordings; {1} could not be cleared. Retry. {2}",
    [
      0,
      1,
      2
    ]
  ],
  [
    "已清除此歌曲的 {0} 筆分段錄音。清除完成，目前剩餘 0 筆。段落分界保留，可重新錄製；其他歌曲、整首錄音與後處理成品都保留。",
    "Cleared {0} segment recordings for this song. 0 remaining. Boundaries retained for new takes. Other songs, whole-song recordings, and production results kept.",
    [
      0
    ]
  ],
  [
    "已清除 {0} 筆分段錄音；未能完成清除或列表更新：{1}",
    "Cleared {0} segment recordings; cleanup or list refresh incomplete: {1}",
    [
      0,
      1
    ]
  ],
  [
    "（{0} 段）",
    "({0} regions)",
    [
      0
    ]
  ],
  [
    "第 {0} 個原唱區間的播放方式",
    "Playback mode for original vocal region {0}",
    [
      0
    ]
  ],
  [
    "刪除第 {0} 個原唱區間",
    "Delete original vocal region {0}",
    [
      0
    ]
  ],
  [
    "本段錄音：{0} · {1} · {2} · {3}{4}",
    "Segment take: {0} · {1} · {2} · {3}{4}",
    [
      1,
      2,
      3,
      4
    ],
    [
      0
    ]
  ],
  [
    "歌聲校正 {0} ms（含起唱與尾音餘量）",
    "Vocal correction {0} ms (including pre-roll and tail)",
    [
      0
    ]
  ],
  [
    "拖曳分界 {0}，{1}",
    "Drag boundary {0}, {1}",
    [
      0,
      1
    ]
  ],
  [
    "{0} · {1} · {2} 秒",
    "{0} · {1} · {2} seconds",
    [
      1,
      2
    ],
    [
      0
    ]
  ],
  [
    "沿用已選錄音 · {0} · {1}",
    "Keep selected take · {0} · {1}",
    [
      1
    ],
    [
      0
    ]
  ],
  [
    "本段共有 {0} 個錄音版本，全部列出；可重錄多次，沒有三次上限。{1}",
    "All {0} takes for this segment are listed. Record as many as needed; there is no three-take limit. {1}",
    [
      0,
      1
    ]
  ],
  [
    "待補錄或涵蓋不足：{0}。可改選本段版本，或明確勾選保留靜音。",
    "Missing or insufficient coverage: {0}. Choose another take or explicitly allow silence.",
    [],
    [
      0
    ]
  ],
  [
    "無法開啟草稿：{0}",
    "Cannot open draft: {0}",
    [
      0
    ]
  ],
  [
    "本段錄音已保留，但診斷未完整保存：{0}。",
    "Segment recording retained, but diagnostics not fully saved: {0}.",
    [
      0
    ]
  ],
  [
    "本段已保存，可按「試聽本段錄音」立即聽這一版，也可切換演唱版本；原先錄音保留。{0}",
    "Segment saved. Preview it now or switch takes; previous recordings are retained. {0}",
    [
      0
    ]
  ],
  [
    "錄音已停止；草稿／保存狀態請確認：{0}",
    "Recording stopped. Check draft / save status: {0}",
    [
      0
    ]
  ],
  [
    "正在準備本段{0}帶唱與收音…",
    "Preparing segment {0} guide playback and input…",
    [
      0
    ]
  ],
  [
    "準備起唱：{0}，{1}–{2} · {3}帶唱；到尾音餘量後自動保存。",
    "Ready to sing: {0}, {1}–{2} · {3} guide playback. Saves automatically after the tail allowance.",
    [
      1,
      2,
      3
    ],
    [
      0
    ]
  ],
  [
    "無法完成本段錄音：{0}",
    "Cannot complete segment recording: {0}",
    [
      0
    ]
  ],
  [
    "尚未完整涵蓋：{0}。請補唱，或勾選「允許未錄範圍保留靜音」。",
    "Incomplete coverage: {0}. Record the missing parts or allow silence in unrecorded regions.",
    [],
    [
      0
    ]
  ],
  [
    "{0} · 分段合成",
    "{0} · Segment mix",
    []
  ],
  [
    "已試合完整 {0} · {1} · 歌聲校正 {2} ms{3}。目前為暫存試聽；滿意後按「存到錄音後處理」。",
    "Full mix assembled: {0} · {1} · Vocal correction {2} ms{3}. Temporary preview only; save for post-production when satisfied.",
    [
      0,
      1,
      2,
      3
    ]
  ],
  [
    "· 原唱加入 {0} 個區間",
    "· Original vocals in {0} regions",
    [
      0
    ]
  ],
  [
    "已移除最後一道分界，剩 {0} 段。原始錄音保留。{1}",
    "Last boundary removed; {0} segments remain. Original recordings retained. {1}",
    [
      0,
      1
    ]
  ],
  [
    "已切換為{0}，請按「試聽本段錄音」。",
    "Switched to {0}. Preview the segment recording again.",
    [
      0
    ]
  ],
  [
    "準備起唱 · 還有 {0} 秒",
    "Ready to sing · {0} seconds remaining",
    [
      0
    ]
  ],
  [
    "片段{0}-{1}秒",
    "Clip{0}-{1}sec",
    [
      0,
      1
    ]
  ],
  [
    "未完成：{0}",
    "Incomplete: {0}",
    [
      0
    ]
  ],
  [
    "來源：{0} · {1} 秒",
    "Source: {0} · {1} seconds",
    [
      1
    ]
  ],
  [
    "翻唱來源：{0}",
    "Cover source: {0}",
    []
  ],
  [
    "MV 已完成。保存位置：{0}",
    "Music video complete. Saved at: {0}",
    []
  ],
  [
    "{0}最多 2 GB、15 分鐘。工作副本保存在歌曲庫的 .local-mv 資料夾，原檔保留，不上傳雲端。",
    "{0}Up to 2 GB and 15 minutes. A working copy is stored in the library’s .local-mv folder. Original retained; no cloud upload.",
    [
      0
    ]
  ],
  [
    "已匯入「{0}」。可直接播放，或按「準備歌曲基準」使用錄音、評分與分段。",
    "Imported “{0}”. Play it directly, or prepare the reference for recording, scoring, and segments.",
    []
  ],
  [
    "請按播放器的播放按鈕：{0}",
    "Press the player’s play button: {0}",
    [
      0
    ]
  ],
  [
    "· {0} 秒",
    "· {0} seconds",
    [
      0
    ]
  ],
  [
    "{0}共 {1} 項，{2}。{3}",
    "{0}{1} items, {2}. {3}",
    [
      0,
      1,
      2,
      3
    ]
  ],
  [
    "【{0}】{1}",
    "[{0}] {1}",
    [
      0
    ]
  ],
  [
    "{0}（預設）",
    "{0} (default)",
    []
  ],
  [
    "{0} Key",
    "{0} Key",
    [
      0
    ]
  ],
  [
    "升{0} Key",
    "Up {0} semitones",
    []
  ],
  [
    "降{0} Key",
    "Down {0} semitones",
    []
  ],
  [
    "EQ {0}",
    "EQ {0}",
    [
      0
    ]
  ],
  [
    "{0} 次",
    "{0} repeats",
    []
  ],
  [
    "升 {0} Key",
    "Up {0} semitones",
    []
  ],
  [
    "降 {0} Key",
    "Down {0} semitones",
    []
  ],
  [
    "{0} · {1} · {2} · {3} · {4} · 保留音軌",
    "{0} · {1} · {2} · {3} · {4} · Keep stems",
    [
      0,
      1,
      2,
      3,
      4
    ]
  ],
  [
    "{0} · {1} · {2} · {3} · {4} · 不保留音軌",
    "{0} · {1} · {2} · {3} · {4} · Discard stems",
    [
      0,
      1,
      2,
      3,
      4
    ]
  ],
  [
    "第 {0} 段 · {1}–{2}",
    "Segment {0} · {1}–{2}",
    []
  ],
  [
    "第 {0} 段 {1}–{2}",
    "Segment {0} {1}–{2}",
    []
  ],
  [
    "{0} · 開始",
    "{0} · Start",
    []
  ],
  [
    "{0} · 結束",
    "{0} · End",
    []
  ],
  ["正在載入影片：{0}", "Loading video: {0}", []],
  ["正在播放：{0}", "Playing: {0}", []],
  ["正在準備下載：{0}", "Preparing download: {0}", []],
  ["已開始下載：{0}", "Download started: {0}", []],
  ["位置：{0}", "Location: {0}", []],
  ["符合「{0}」的有 {1} 部（全部 {2} 部，{3}）。", "{1} match “{0}” ({2} in total, {3}).", [1, 2, 3]],
  ["共 {0} 部，{1}。", "{0} videos, {1}.", [0, 1]],
  ["刪除 {0} 部 MV（{1}）？\n位置：{2}\n{3}\n\n會永久刪除選取的 MP4，無法復原。原始音檔與已保存錄音保留。", "Delete {0} music videos ({1})?\nLocation: {2}\n{3}\n\nThe selected MP4 files are permanently deleted and can’t be recovered. Original audio and saved recordings are kept.", [0, 1, 2]],
  ["已刪除 {0} 部，釋出 {1}。", "Deleted {0} videos, freed {1}.", [0, 1]],
  ["刪除未全部完成：{0}", "Deletion incomplete: {0}", [0]],
  ["清除全部 {0} 部 MV（{1}）？\n位置：{2}\n\n包含目前歌曲庫內所有歌曲由本工具產生的 MV 成品，永久刪除後無法復原。原始影片、歌曲與錄音都保留。", "Clear all {0} music videos ({1})?\nLocation: {2}\n\nPermanently deletes videos created by this tool for all songs in the current library. Original videos, songs, and recordings are kept.", [0, 1, 2]],
  ["正在清理 MV：{0}／{1} 部…", "Cleaning up videos: {0}/{1}…", [0, 1]],
  ["清理完成：已刪除 {0} 部 MV，釋出 {1}。原始影片、歌曲與錄音保留。", "Cleanup complete: deleted {0} videos, freed {1}. Original videos, songs, and recordings kept.", [0, 1]],
  ["清理未全部完成{0}：{1} 請查看重新整理後的清單。", "Cleanup incomplete{0}: {1} Check the refreshed list.", [0, 1]],
  ["（已確認刪除 {0} 部，釋出 {1}）", "(confirmed {0} videos deleted, {1} freed)", [0, 1]]
];
