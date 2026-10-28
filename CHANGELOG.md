# Changelog

## Unreleased

Parity with the three old programs (every small tuning, preview and check they had):

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
  first), optional quick MV right after a cover, a warning naming the MV projects that use a
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
