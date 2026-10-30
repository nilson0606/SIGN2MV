# Changelog

## Unreleased

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
