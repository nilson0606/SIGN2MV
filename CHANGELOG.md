# Changelog

## Unreleased

- Library, 「音軌平移」: a song not shifted yet opens at +1.00 (lyrics 1 s ahead); a shifted one at its value.
  「套用」 lights up yellow when it can be used.
- Library, 「音軌平移」: a highlighted line says what it is for (lyrics in the video a little before the singing, for
  singing along and recording; + makes them earlier), in the box and both manuals. The box asks the server again
  before previewing and when the window comes back to the front: a song separated after the box was drawn still
  showed it as usable (applying was already refused by the server).
- Library, 「音軌平移」: the value is now the total against the originally imported audio (the box opens at the
  current value; 0 goes back), and `POST …/audio-shift` takes `{"target": s}`. 「試播音量」 sets the preview's
  loudness; the video stays muted while previewing (its own volume control unmuted it and added the video's sound
  on top). A refused apply gives the players their files back and shows the reason. The temporary diagnosis no
  longer reports a covered window's once-a-second timer as a stall. Checked with 31 browser cases.
- Library, 「音軌平移」 preview: the audio device is closed when the preview stops or the song is left (it was kept
  open, with the decoded song, each time the page was drawn again). TEMPORARY: `web/js/diag.js` + `POST /api/diag`
  write `diag:` lines to `server.log` when the page stops for over a second during the preview or apply, to find a
  freeze seen only in the SIGN2MV (Edge) window.
- Library, 「音軌平移」 preview: pops while previewing. The preview kept nudging the audio's playback speed (logged:
  1.00 ↔ 1.10 every 0.1–0.2 s) to chase a coarse position, and each change was audible. It now plays the song
  audio with Web Audio, scheduled once at the offset (allowing for the output latency), and only starts again
  after a pause, a seek or a new value, with 5 ms fades. The applied file was never affected.
- Library: 「音軌平移」 / *Audio shift* in 「原曲」 moves the song audio −2.00 to +2.00 s against the picture
  (+ = later: silence at the start, the end cut; the length stays). Only for a song nothing has been made from
  yet: any other folder in the song (stems, keys, sing, cover, MV, renders, ...) or a sing & record take blocks it.
  「試播」 plays the muted video with the shifted audio live; 「套用」 is offered only for the previewed value, asks,
  then rebuilds `source/` like a re-import: the audio is shifted sample-exact with ffmpeg, the picture is copied
  into the new video.mp4 (not encoded again), the old audio, video and upload copy are deleted. `source.json`
  records `audio_offset_s` and gets a new `source_hash` (`…#shift+300ms`) so caches never take the old audio.
  About 3 s for a 228 s song on the PC (measured on a copy).
- Docs (both manuals, both languages): the three guide choices, the trial mix without backing vocals, the
  automatic draft save, the backing-vocal filter for lead references and their one-time rebuild, 「重新匯入（換來源）」
  and the rebuilt references after it, and the 「保留原唱音色（舊做法）」 versions.
- Library: 「下載 MP3」 / *Download MP3* under the video in 「原曲」 saves the song's original audio as a 192 kbps
  MP3, made for that click from the lossless `source/audio.wav` (the video's AAC is itself encoded from it, so this
  compresses once, not twice). Nothing is added to the library; the temporary file is removed after sending.
- Home: 「檢查更新」 / *Check for updates* under the system status asks GitHub whether this copy is the latest and
  how many newer changes there are, with links to the update steps and to GitHub. It only asks: nothing is
  downloaded or replaced.
- Sing & record, segment recording: the 「重新讀取錄音版本」 and 「保存草稿」 buttons are gone. Every change already
  saved the draft; the take list is now read again whenever the sing page is shown or gets focus.
- Sing & record: the guide choice (「演唱時帶唱」 and, for segments, 「錄音時帶唱」) has 「原唱＋伴樂（不含和音）」 for
  versions with separate lead and backing vocals: the lead singer and the accompaniment, played from the separated
  tracks. The default now reads 「原唱＋和音＋伴樂」 there (it always included the backing vocals); a plain version
  keeps 「原唱＋伴樂」 and does not offer the new choice.
- Sing & record, lead/backing versions: backing vocals that leaked into the lead track are no longer scored as
  the melody. When the reference is made, a run of melody where the backing-vocal track is clearly louder
  (by 6 dB or more, median over the run) or the lead track is nearly silent (below -45 dBFS) becomes a rest.
  On 〈心所愛的人〉 this removes the intro harmony (10.9–15.9 s) that showed as an E5 melody line. Existing
  lead/backing references are made again the next time they are loaded (pitch analysis only, about a minute).
- Sing & record, segment recording: 「試合內容」 has 「人聲＋伴樂（不加和音）」 for versions with separate lead and
  backing vocals: the backing-vocal track is left out of the trial mix and of the saved recording, so
  post-processing leaves it out too. In a plain version the choice reads 「人聲＋伴樂」: its backing vocals are
  part of the vocal track, so the accompaniment never had them.
Three outside reviews (Claude, Gemini, Astro) on 11-08, merged and checked against the code:

- Sing & record: key versions made with the old "keep the singer's timbre" method (R2, 11-07) were no longer
  recognised after the switch to R3, so recordings made on them could not read their reference or backing in
  post-processing. They are recognised again, listed as 「保留原唱音色（舊做法）」, and load as they are; they
  are never made again.
- Library: 「重新匯入（換來源）」 deleted the old source before the new one was in place, so a failure at that
  moment left the song without audio. The old one is now kept until the new one is in place, put back if that
  fails, and put back at the next start if the program was stopped in between.
- Sing & record: after replacing a song's source, its sing references kept the old pitch, beats and backing,
  and the "first N seconds" clip kept the old audio. References remember the source they were made from; an
  outdated one is made again (marked 「來源已更換，載入時會重新建立」 in the list), and clips follow the source.
- Sing & record: a local-microphone capture whose page was reloaded or closed while it was opening kept the
  microphone; every later request said it was used by another tab until SIGN2MV was restarted. Fixed.
- Jobs: cancel and the time limit did not reach a worker that was still loading its libraries when its input
  was large. Fixed.
- Live pitch (RMVPE scoring): a worker stuck while loading is stopped after 3 minutes.
- `server.log`: the harmless "[WinError 10054]" tracebacks (a browser closing a connection) are no longer logged.
- AI cover: the trained model's info names the feature model actually used; a temporary index copy is removed
  when a conversion fails; versions record the key copies they use; less memory for the room effect.
- YouTube link lookup ends yt-dlp's helper processes on a timeout; the library-folder picker waits for its
  process after closing it.
- `start.bat` returns Python's exit code (it always returned 0).
- Sing & record: 「保留原唱音色」 is dimmed at the original key, where it does nothing.
- Docs: check for updates by the 7-character code after the code date, not only the date.
- Installer: also downloads the feature model chinese-hubert-base (about 360 MB, MIT), offered when training a
  voice, so it works without the internet. Before, Applio downloaded it the first time it was used. An earlier
  install can get it by running `install.bat` again (optional; only this step runs).

- Home, system status: new row 「程式日期」 / *Code date*: the date and short commit of the code
  (`app/BUILD.txt`, filled in by GitHub's Download ZIP), to compare with the latest change on GitHub. The version
  number alone did not change between updates.
- Docs: README (both languages) and the manual have an 「更新到新版」 / *Updating* section, step by step: shut down,
  download, unblock, extract, copy over the old folder, start, check the code date; when `install.bat` is needed.
- Sing & record, 「人聲保留原唱音色」: now made with Rubber Band's newer R3 engine (already inside SIGN2MV's ffmpeg)
  instead of R2. Measured on a vocal lowered 4 semitones, the spectral centroid moves −3% from the original
  instead of −11% (without the option: −16%), so the voice keeps much more of the singer's timbre. Key versions
  made with the old method (2026-11-07) are not reused: the new ones are separate (`_t`), and the old vocal copies
  are marked 「舊做法，已不使用，可刪」 in 「已存的分軌」. Without the option nothing changes.
- Sing & record: 「送出音量」 meters next to the ear switches show what the page really sends to each ear. When
  Windows 「單聲道音訊」 / *Mono audio* is on (read from the registry, never changed), a note under the switches says
  that Windows mixes left and right after SIGN2MV, so the ear switches and headphone mono cannot work. Shutting
  SIGN2MV down reminds you to switch Mono audio back if it differs from when SIGN2MV started.
- Sing & record: 「耳機單聲道」 / *Headphone mono*, off by default (stereo as before). When on, everything you hear
  while singing (the song, backing only, key versions, the segment monitor) plays as the same sound in both ears,
  for singing with one earcup off. The headphone hint says so. The choice is remembered on this computer.
- Sing & record: 「耳機聲音：左耳／右耳」 / *Headphone sound: Left ear / Right ear*, both on by default. Untick one to
  mute that ear (for the same audio as above), e.g. the earcup you took off, so nothing leaks into the microphone.
  Not remembered: both ears are on again when the page opens.
- Sing & record: new option under the key, 「人聲保留原唱音色」 / *Keep the singer's timbre in the vocals*, off by
  default. When on, a key version shifts the original vocals (and lead / backing vocals) with Rubber Band's
  formant preservation, so they sound more like the singer in that key instead of higher / lower-voiced; the
  accompaniment is shifted as before. It can add some artefacts, which is why it is off by default. On and off are
  separate key versions (their own vocal copies under `keys/`, marked in 「已存的分軌」), so switching never
  reuses the other kind. Also: the 「正在準備 …」 message now shows the key in English too.
- Home: 「開始」 shows a card for each page (Library, Sing & Record, MV, AI Cover) with a small screenshot and one
  line on what it does; a click opens the page. The screenshots follow the interface language. They were taken
  with an invented demo song (「Morning Light」, generated for this), not with real songs.
- Home, system status: a SIGN2MV banner at the top, and the component checks shown as one group of small tags
  instead of one row each, so the panel is about as tall as 「開始」.
- Docs: the installer asks about the optional Sucial model at the very start, before anything is downloaded (the
  manual said it asks partway through). After an import the original player is inside the folded 「▸ 原曲」
  section; the manual now says so.
- Cover, warm-up fix: the Applio warm-up failed every time with `AssertionError: Invalid device id`. It imported
  Applio's own inference code, which checks the graphics card on import, while the warm-up hides the card. It now
  loads only the libraries Applio uses (PyTorch, librosa, faiss, transformers and the rest), one by one, and names
  any that fail in `logs\jobs.log`. The separation warm-up loads its libraries the same way.
- Job queue: writing `logs\jobs.log` can no longer stop the queue. A song title with a broken character (for
  example half of an emoji) made the write fail inside the queue: the job stayed 「執行中」 and every later
  graphics-card job waited until SIGN2MV was restarted. Any error there is now ignored, and such characters are
  written as escape codes.
- Cover and separation, warm-up: right after start-up and then every 15 minutes, SIGN2MV loads the Applio and
  separation libraries in a background process at low priority, without the graphics card and without models.
  When those files (several GB) have left the Windows file cache, the first cover afterwards spent 89–165 s
  loading Applio instead of a few seconds. The warm-up reads them back while nobody is waiting, skips while a
  graphics-card job runs, and logs how long it took to `logs\jobs.log`. Set `SIGN2MV_NO_WARMUP=1` to turn it off.
- Separation progress: a cover that first separated and then split lead and backing vocals logged 「lead」 and
  「separate」 in turn for every chunk of the second split. The first split's progress reporter leaked into the
  second one. Display only; the separation itself was not affected.
- Cover: the Applio load is timed in parts (PyTorch, librosa, Applio's code, the converter) in the job log, and a
  load that runs past 30 s writes where it is waiting every 30 s, so a slow load can be explained afterwards.
- Long graphics-card jobs show every step. Steps without a percentage (reading the audio, loading the model,
  writing the stems; for the sing reference, loading the pitch model and finding the beat) are named and the bar
  moves; before, nothing moved for a long time and the job looked hung. A queued job says which job it is waiting
  for (job boxes, the jobs page and the sing page). The jobs page shows the step and running time of a running
  job. A cancelled job box shows only 「已取消」.
- New `logs\jobs.log`: when each job was queued, started, changed step, was cancelled and ended, with the
  seconds. It is kept after SIGN2MV is closed (about 2 MB, then the older part moves to `jobs.previous.log`).
- Sing & record: the backup link for an unsaved recording has a 「✕ 不需要了」 button; it could only be removed by
  reloading the page.
- Cover training: the feature model can be chosen: contentvec (default) or chinese-hubert-base (trained on
  Chinese speech, about 361 MB, downloaded the first time). Conversion now uses the feature model the voice model
  was trained with; Applio stores it in the `.pth`. Before, conversion always used contentvec, so a model trained
  with another one sounded wrong without any error. A model that needs a feature model Applio cannot load stops
  with a message. Models that do not use contentvec are labelled in the model list and menus. In one A/B test,
  chinese-hubert-base did not articulate more clearly; it is kept as an option.
- README: tick 「解除封鎖」 / *Unblock* in the ZIP's Properties before extracting.
- Cover training: the curve panel follows deleted models and epochs (it kept showing them). The manual says up to
  four saved epochs are kept.
- Cover: the per-song clean-up button is named 「🧹 清理這首歌的中間檔」 / *Clean up this song's unused files*, so it
  is not taken for the training clean-up.
- Cover training: the uploaded training files are listed by name (the file box only showed how many).
- Docs: notes that pitch 0 and Key 0 are left out of version names, and that only Traditional Chinese Windows
  opens SIGN2MV in Chinese. The record-button hint reads 「完成後再按一次錄音按鈕」.
- MV, render lock follow-up (outside review of the previous change, Gemini): the project tabs at the top left can no
  longer be clicked during a render (they switched project, and the finished MV then showed on the wrong project).
  After a reload, the end of a render is taken from the job queue: success, failure (with the error), cancel,
  time-out, or 「渲染已中斷（伺服器已重新啟動）」; it used to report 「✔ 已結束」 at 100% in some of these cases. A
  refresh held during the render no longer switches the player back to a single frame when the MV finishes.
  Reloading during a render no longer shows the 「完成前不會切換專案」 note when 「製作 MV」 was not pressed. A
  render request that breaks (server unreachable) now stops the progress polling.
- MV: the page stays locked for the whole render. Reloading it (F5) during a render used to unlock every button
  while the render went on, so Whisper could be started and the render dropped off the page's progress and stop
  button (outside review, Gemini P5). The page now asks the server when it opens: a running render locks it
  again, shows the progress and the stop button, and when the render ends the page unlocks and reopens the
  project with the new MV. During a render, 「製作 MV」 from another page no longer switches project (a note
  says so; the finished MV used to show on the wrong project), and a refresh from the other pages waits until
  the render has ended.
- MV: 「🎬 播放成品 MV (.mp4)」 can only be pressed once the project has a finished MV (greyed out, with
  「尚未渲染成品 MV」 on hover, until then). It used to switch to an empty player. It follows the same rule as
  the download and open-folder buttons, so it turns on when a project with an MV is opened or a render ends.
- Docs: `MANUAL.html` next to `install.bat` opens the manual in the browser's language (Chinese or English,
  with links to both), so the manual can be read right after extracting the ZIP, before installing.
- Sing & record: the RMVPE scoring worker is stopped when one piece gets no answer within 120 s (the page
  has given up by then). Before, a worker that stopped answering kept the lock: every later scoring
  request waited behind it and the idle clean-up never ran, until SIGN2MV was closed. The next piece now
  starts a new worker. Found by an outside review (Gemini, P2); no such hang had been seen.
- MV: photos 37 to 99 are counted again when lyrics are pasted and when a render builds its own timeline.
  The photo count still stopped at the old limit of 36 (`count_existing_scene_images`), so a project with
  more photos was treated as having 36 there. Found by an outside review (Gemini, P1).
- Docs, for open-sourcing: the manual (English and Chinese) has a new step-by-step getting-started chapter
  (download, extract to an English path, install, start, import a song, sing, get a voice model, first
  cover, first video, shut down), button names that match the screen, rescoring, the original-vocal test
  and segment takes closing the input, and a section on reporting problems through GitHub Issues. Wording
  about the older programs this replaced is gone. The Sing & Record guide (「說明 ↗」) no longer describes
  the stand-alone sign_record (local tools, GitHub Pages, YouTube player, library folder, diagnostics,
  the 「vedio」 folder) and no longer says "non-commercial use only", which contradicted the MIT licence.
  New README.zh-TW.md; the README has a quick start. Three interface hints no longer mention the old
  AI cover program.
- Sing & record, segment mode: a saved 分段合成 rescored far too low (for example total 14, pitch 0, rhythm 0)
  because it was saved without the scoring choices, so 「允許高／低八度」 was off and an octave-down voice
  scored as off-key. A segment mix now stores 音域比對, 評分範圍 and 評分難度 like a whole-song take; segment
  mixes saved earlier take the octave choice from the 音域比對 setting shown when they are rescored (both
  「重新評分」 on the sing page and 錄音重新評分 in post-production). Checked on a real 哭沙 segment mix: 14 → 81.
- Sing & record, segment mode: 「試合完整一版」 no longer gets stuck on 「正在讀取各段乾淨人聲並試合…」. The input
  stayed open after a segment was recorded; when it stopped during the trial (native capture interrupted while
  the trial loaded the computer, or 「停止收音」) the running trial was dropped without a message. Each segment
  now closes the input once it is saved, like a whole-song take (「錄這一段」 opens it again), and the input
  stopping no longer cancels a trial.
- Sing & record: capture is no longer stopped when the window is covered, minimised or in the background
  while a take starts, runs or is being finished (recording and RMVPE scoring do not need the page in front);
  an idle microphone is released after a minute in the background, and leaving the page still stops
  everything. A device change elsewhere (Bluetooth headset, HDMI monitor waking, a new Windows default) no
  longer stops capture: browser capture stops only when the microphone in use is gone, native capture
  ignores it (the capture process and the page's reserve report real failures).
- Sing & record 「重新評分」 of a saved recording no longer writes back the whole record it read when the
  button was pressed. Only the RMVPE analysis is stored, merged with the record as it is at that moment
  (new POST /sr/recordings/{id}/patch, merged under the archive lock; browser-held takes in one IndexedDB
  transaction). Before, saving the take to post-production while it was being analysed was undone and the
  take went back to 「待確認」. Needs the local tools restarted.
- Sing & record: a whole-song take that did not end normally (page reloaded or closed, capture cut off) no
  longer stays stuck in the browser where it could only be previewed or deleted. The next time the page lists
  recordings it writes the WAV headers from the audio actually stored, marks the take complete and 「中斷後救回」
  and moves it to the library as a pending take. A take still being recorded or saved (this tab or another one)
  holds a Web Lock and is never touched. The pending-take panel gets 「下載這一版」, the page asks the browser for
  persistent storage, and leaving the page while a take is being finished and saved asks first.
- Sing & record: 「從頭開始唱且評分」 can no longer stay greyed out. It works at any time, also during a take
  or while a start is in progress: the running take is ended first (its recording kept as a pending take, not
  scored), then a new take starts. A start that loses the microphone, or a step that takes too long (each step
  has its own limit: microphone 120 s, recording 90 s, sing-along track 60 s, seek 45 s), ends with a message
  naming the step. A failed start goes back to ready instead of a paused state without a take.
- Sing & record: 「結束並結算」 can no longer hang in 「結算中」. The video pauses at once; every RMVPE request
  has its own time limit (30 s live, 120 s for saved recordings and AI covers) and the final RMVPE settle stops
  after 20 s even if the server never answers, falling back to the browser estimate. An error while scoring
  ends the take instead of leaving the page in 「結算中」.
- Sing & record 「評分對象」 also lists the AI cover versions of the loaded song and key: the converted vocal
  (cover/rvc, on the song's own timeline, scoring delay starts at 0 and does not change the input latency) is
  RMVPE-analysed once per page (nothing written into the cover) and scored as a whole-song take, with the
  version's own pitch (e.g. -12) taken out. 童話 cover #1 (pitch 0): standard 95 at 0 ms, 96 at -20 ms.
- Sing & record 「重新評分」: new 「評分對象」 menu. Besides the take just sung it lists the saved whole-song
  recordings of the loaded song and key (pending or saved to post-production), so after a reload a take can be
  rescored at another delay or difficulty without singing again. The first rescore of a saved recording runs
  RMVPE on its clean vocal and keeps the result with the recording (as post-production does); it is scored on
  the loaded reference with the difficulty chosen now. Rescoring is off while a take runs.
- Sing & record rhythm score: note starts are no longer cut separately in the reference and in the take
  (two independent cuts at the 0.75-semitone line flipped on a few cents, so even the original vocal of
  the song lost up to 10 rhythm points). For every note start of the reference, the cell where the voice
  arrives on that note is found the same way in both, and the two are compared. Original-vocal test
  (童話, standard): rhythm 97 -> 100 in the original key, 90 -> 98 four keys down; rhythm now moves by
  1-4 points instead of 10-20 when the delay is 10-30 ms off. A take sung on time but up to 150 cents
  off still gets its rhythm marks; the pitch score marks the pitch.
- Standard and strict pitch limits +5 cents (standard 30 / 105, strict 20 / 55): the measurement margin
  at which the original vocal of 童話 (original key, at its own delay) reaches pitch 100. Rhythm limits
  and relaxed unchanged. Manuals updated.
- Manuals (Chinese and English) brought up to date: Windows 10/11 only; NVENC needs driver 570+ and the
  installer logs the working encoder; FFmpeg pinned and checksum-checked; Shut down closes the console;
  segment takes are saved before the next part; converted backing vocals get the key in their conversion;
  job log names each conversion and hides harmless separator notices; new troubleshooting rows (CPU MV
  encoding, capture broke off, console left open); MIT licence and use-responsibly note. The sing &
  record guide's SIGN2MV note says the install step is skipped and which features were removed.
- AI cover job line and log name each conversion: 「1/2 主唱 · CUDA」, 「2/2 和聲 · CUDA」, 「✔ 已轉換主唱（28.1 秒）」
  (also 人聲, 和聲 2, 男聲, 女聲, 分段 a–b 秒, 外部音檔 …; English in the English UI). They used to show the
  internal keys (main, backing).
- AI cover: 「原唱和聲混進成品」 is now 「和聲混進成品」 (the backing may be the converted one); its note says
  which backing goes in, and the volume sections say 「和聲」.
- AI cover: new option 「和聲也轉成我的聲音」 (off by default) under 「原唱和聲混進成品」. With the lead split
  off, the backing vocals are converted too, with the lead's model and pitch (+ key), and replace the
  original backing in the mix; quick remix reuses the converted backing. Versions made with it are named
  "… · Backing VC". New feature (the old AI cover had no such option).
- Job log: audio-separator's 「CUDAExecutionProvider not available in ONNXruntime」 and 「Using soundfile for
  writing」 are no longer shown. They are not problems: the separation models are PyTorch files and run on
  CUDA through PyTorch, ONNX Runtime is not used for them.
- Open-source groundwork: MIT licence (`LICENSE`); README gains requirements and limits (Windows only,
  NVIDIA CUDA for AI work, NVIDIA/AMD/Intel/CPU for MV encoding) and a "use responsibly" note;
  THIRD_PARTY lists each separation model with its download page (licence marked "not verified" where
  the author's terms were not checked), where the carried-over code comes from, and the FFmpeg GPL note.
- Installer: FFmpeg is pinned to the BtbN build `autobuild-2026-10-31-12-59` (8.1.3, NVENC needs driver
  570+) and checked by size and SHA-256, instead of the moving "latest" file. The male/female separation
  models (aufr33, Sucial) and the becruily karaoke model now have size and SHA-256 too (computed from the
  downloaded files). The next install.bat run fetches FFmpeg again and re-checks the models.
- Personal names and paths of the author's older setup removed from hints, comments, tests and the
  manual (model import example is now `D:\voice-models`; guzheng/dizi hint describes the folder layout).
- Cover: the spectrum bars of a playing version froze after switching to another page and back (the
  animation stopped while the page was hidden and nothing started it again).
- 全部關閉 now closes the black window: the server waited forever for connections the open page keeps
  (a paused video, the microphone stream). It now gives them 3 seconds and then ends, also when a worker
  thread is stuck.
- Segment recording: pressing 錄製 while the last take was still being saved did nothing (the button was
  disabled without a word until the save ended). The panel now says 「正在保存本段錄音…」 as soon as a
  take ends, and a press during that time says to wait instead of being ignored.
- Sing & record: loading a song that is already in the player no longer leaves 「正在載入本機媒體…」 on screen
  (it says the song is loaded); 「已有歌唱基準…，正在載入…」 changes to 「已載入歌唱基準（…）。」 when it is in.
- Finished folder (review of 2026-11-01): shortcuts are recorded before they are made, so one made just
  before closing is never taken for the user's file; a file in the way of a song folder no longer stops
  the folder for every other song; failing shortcuts wait before the next try (30 s, doubling, up to an
  hour) instead of starting PowerShell on every click; PowerShell errors are readable (UTF-8 from the
  first line, exit code checked); two songs can swap names; a same-title song without an import time
  gets (2) instead of "（ 匯入）"; sing & record requests made while recording no longer trigger it (only
  a saved version does).
- Whisper: reading the audio stops after 10 minutes instead of waiting forever on a stuck ffmpeg.
- Library: a Finished folder (成品資料夾; the folder name is English in every UI language) inside the library, kept in step with the songs: one
  folder per song named by its title, with shortcuts to every cover version, saved sing & record version,
  quick MV and full MV (the song folders themselves are named by id). Same titles get the import date
  (and time); renaming a song renames its folder; deleting work deletes its shortcuts. Only shortcuts
  SIGN2MV made are removed, never the user's own files. Buttons: 📂 成品資料夾 (library), 📂 成品 (song).
- Cover: 「原唱和聲混進成品」 moved from the folded 「分離與和聲」 block to the mix block (under the accompaniment
  volume), like the old 🎶 混入原唱和聲: it is a mix option that quick remix switches.
- Cover: a song covered for the first time starts from the default settings; only the last cover's voice model
  is kept. It used to take everything from the last song, including its accompaniment key (a new song got
  the previous song's −4 key).
- Cover speed: Python no longer recompiles torch, transformers, librosa… on every job. Child processes ran with
  PYTHONDONTWRITEBYTECODE=1 and the installer never compiled the environments, so Applio took 89–100 s to
  start (5.8 s when the files happened to be in memory) and covers were slow off and on; the old programs keep
  the compiled files. The setting is gone and the installer compiles every environment once (new step).
- Cover: the finished box keeps a Log button with the whole run (it disappeared with the progress box).
- Sing & record: the segment mode button is bright pink-orange; 「歌聲輸出到喇叭」 (live voice to the speakers)
  and recording diagnostics are removed (diagnostics was on by default and could affect recording timing).
- Settings: the library note no longer widens the label column and pushes the inputs past the panel.
- Sing & record: the song menu lists every Key version that already has a singing reference
  (「童話 · 降 4 Key」). Loading a song or Key version with a reference loads it right away (with the
  settings it was built with, nothing is rebuilt); without one, the song loads, the Key is selected and a
  note asks to press 「準備歌曲基準」.
- MV encoding (full and quick) tries the graphics card encoders in turn, NVIDIA (NVENC), AMD (AMF), Intel
  (Quick Sync), then the CPU, so PCs without an NVIDIA card also encode on their graphics card. Every
  failure's reason is shown and kept (encoder_errors.log next to the MV, the quick MV list); the installer
  reports which one works. Windows only for now (no macOS build).
- ffmpeg: the installer now takes the BtbN build of the 8.1 release (NVENC API 13.0, NVIDIA driver 570+)
  instead of the master build. Master needed NVENC API 13.1 (driver 610+, newer than the current 592), so
  the graphics card never encoded: every full MV and quick MV fell back to the CPU. The installer now tries
  NVENC once and writes the result to the install log. When NVENC fails, the full MV shows ffmpeg's reason
  (and keeps it in nvenc_error.log next to the MV); the quick MV says so on its job line and in the list.
- Full MV: the lyric list on each card names a line by its Scene number (「[Scene 22 02:09.14] …」) instead of
  its line number (「[第22段 …]」), which stopped matching the cards once photos were inserted.
- Full MV: 「＋ 插入照片」 on each card inserts as many cards as photos chosen (or dropped on the button) in
  front of it, in file-name order; the cards behind move back with their lyrics. 「＋ 前面插一張」 is now
  「＋ 空白」 (one empty card).
- Full MV: up to 99 photo cards (was 36, the old MV studio's number), so long lyrics can get more
  "insert before" slots; drag a photo onto another card to move it there (the photos in between shift
  by one, lyrics and timing stay with their positions), besides ◀ / ▶.
- Whisper (full MV timing and quick MV lyrics) failed on every song with "open() got an unexpected keyword
  argument 'metadata_errors'": the installed faster-whisper 1.2.1 decodes files with an option PyAV 19
  removed. The audio is now decoded by SIGN2MV's FFmpeg and handed to Whisper as samples. The test double
  for faster-whisper refuses file paths the same way, so the tests would catch this again.
- English UI: switching the language while the app is open now also switches the sing & record page
  (it waited for a reload that was skipped whenever a take was pending), the library location and
  storage line, the job log buttons and the dates. Server and worker messages of the sing & record and
  MV parts (errors, queue and progress lines, job logs) are shown in English; the MV transition names
  and the lyrics placeholder too.
- Segment recording: when the audio capture breaks off (the old timeline check stops the take so it
  cannot drift), the segment panel says why and asks to record the part again; it said "no new recording".
- Full MV: after a render the line under the player shows the finished MV (size, resolution, fps); it
  kept saying "no MP4 rendered yet" until the project was opened again.
- Cover: separation runs in its own process that ends before the voice conversion, so Applio gets all
  the graphics memory back. Measured on an RTX 4060 Laptop (8 GB): conversion after a separation took
  82.6 s instead of 19.2 s (the card fell back to system memory). The old AI cover program also
  separated in its own script.
- Sing & record: a clear notice while the browser asks for microphone permission (recording and
  playback wait for it) and when the microphone is blocked; messages of the version / trial panel
  of segment recording also appear under the button that was pressed.
- Sing & record: listening to a take of the last part failed with "backing too short" when the
  recording ran a fraction of a second past the end of the song; only the song has to be covered.
- New start (start.bat) opens on Home; the MV page no longer opens the new-project dialog by itself.

Parity with the three old programs (every small tuning, preview and check they had):

- Quick MV studio look: optional lyric subtitles (old AI cover lyric MV): LRC times, Whisper timing once per
  song (covers and takes reuse it), even spread, per-line timing panel (play, ±0.5 s, start = player time,
  edit, delete, add), saved per audio.
- Look switcher in the top bar: console / classic (old AI cover green) / day (light), remembered.
- Cover voice pitch back to the old −12..+12 (re-converted sections keep −24..+24).
- Sing & record: first 15 / 30 / 60 s trial (separated on its own), keep-separated-tracks
  option, deleting a prepared song frees its unused stems, real environment check, playback
  trace, mask rules exactly as sign_record, MP3 export stops when the page leaves, one render
  per sent take, the sing manual is reachable, shutdown asks about the native microphone.
- Jobs: a log viewer (the old terminal) on every job box and on the Jobs page, a cancel
  button everywhere, elapsed time; MV renders run on their own lane.
- Cover training: 6-step dashboard with status light and epoch / step / best-loss cards,
  convergence panel (5-epoch average, grid values, hover, verdict, live badge, kept epochs
  with size, use / delete), presets 30 / 100 / 200, default name, this song's vocals as
  training material, cleanup shows free disk space, new or imported models are selected.
- Cover form: "this run uses" summary with back-to-original-key, key badge, same-second
  A/B key preview, pitch and volume presets, restore-defaults buttons, separate-again switch,
  separation and rubberband availability, duet status and warnings, per-section preview and
  edit, autotune / denoise per re-converted section, clip end from its length, full-width
  colon in times, lead split model aufr33 or becruily (optional hand download).
- Cover versions: select all / delete selected, format and size, show in Explorer, watch the
  quick or full MV made from a version, now-playing text, busy note, tab title on finish,
  live spectrum bars, every song's versions in one list, 🧹 clean up unused files (listed
  first), a warning naming the MV projects that use a
  version before it is deleted.
- Quick MV: every song's list with search, select, delete; the old AI cover look ("studio":
  subtitle, badge, credits line, 60 fps) as a second style; 720p for both styles; open folder.
- MV workspace: project import copies photos, Whisper result, finished MV and outside audio
  and asks before replacing a project of the same name; any audio format can be dropped in
  (converted to FLAC when the browser cannot play it); open folder; paste lyrics from the
  clipboard; new projects start with the old picture style; a project whose audio was deleted
  says so.
- Library: link preview before importing (thumbnail, title, length, page link, player), paste
  button, drop a file to upload with a progress bar, clickable source link; library location
  picked with a folder dialog and checked.

- Quick MV (sing_record's audio-reactive title card, same filter and layout): MV page tabs
  "Quick MV" / "Full MV"; Quick MV / Full MV buttons on cover versions and sing & record takes;
  any of the song's audio as source; NVENC with libx264 fallback; stored in songs/<id>/quickmv/.
- Library: stem / key copy delete routes are explicit (/stems/{name}, /keys/{name}).
- Engine environment moves to PyTorch 2.11 (CUDA 12.8), the same build as Applio: both
  environments now share one copy of the PyTorch files (uv hard links), so Windows keeps one
  set warm instead of loading two 4 GB sets in turn. Re-run install.bat to update.
- Cover: PyTorch is loaded only when a cover actually has to separate; progress shows while
  programs and models load and the elapsed time during voice conversion; the finished line
  splits voice conversion into start-up and conversion, with the mix steps on hover.
- Library: *Saved stems* lists every separation layer and key copy of a song as a
  tree, with size, date and the cover versions / sing references that use it; each
  can be deleted (with everything made from it). Users separate again when needed.
- Library: storage overview per song (original, stems, covers, cover cache, sing &
  record, MV, other), song sizes in the list, library total and free disk space.
- Key copies are shared: one folder per track and key (`keys/<track hash>_p2/`), made
  by whichever of library, sing & record or AI cover needs it first and reused by the
  others. Each records the stem it was made from. Older key folders are still listed
  and can be deleted; they are no longer reused.
- Manual: how originals, caches and your work relate.
- Library song page: sections fold (remembered), with one-line summaries; saved-stem rows
  fold their children; long "used by" lists are shortened.

## 0.1.0 — first complete version

- One program and one song library for sing & record, AI cover and lyric MV.
- Installer that keeps everything inside the application folder (uv, Python
  3.12, three environments: server / engine / Applio), resumable, with checksums.
- Job queue: one GPU job at a time, two general jobs; cancel, timeouts,
  process-tree kill.
- Library: YouTube and file import, layered stem cache shared by every workspace,
  key versions.
- Sing & record: the sign_record app embedded, with the library as its source.
- MV: the MV studio embedded; projects per song; Whisper and rendering as GPU
  jobs; covers and recordings as MV audio; English page translation.
- AI cover: Applio 3.7.1 conversion; versions as song renders; quick remix in
  place or as a new version; vocal sections (mute, original, re-convert with
  own separation, external clip with optional conversion); volume sections;
  male/female duet; key change; melody instrument (GeneralUser GS, imported
  guzheng/dizi); voice model import (including whole old model folders),
  upload, epochs, loss curves; training with Applio.
- Interface in Traditional Chinese and English (follows Windows), manuals in
  both languages (English is the master).
