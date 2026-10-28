# Changelog

## Unreleased

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
