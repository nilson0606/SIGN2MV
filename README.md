# SIGN2MV

[中文說明](README.zh-TW.md)

Sing & record, AI cover and lyric music videos in one local Windows program.

- **Library** — import a song once (YouTube or file); separated stems are cached and shared.
- **Sing & record** — pitch-guided singing, scoring, whole-song and segment recording, post-production.
- **AI cover** — RVC voice conversion (Applio), versions, quick remix, vocal sections, duet, training.
- **MV** — 1080p 60 fps lyric videos with Whisper alignment and karaoke colouring.

Everything runs locally; nothing is uploaded.

## Quick start (Windows 10/11)

1. **Code → Download ZIP** on this page. Before extracting, right-click the ZIP → *Properties*; if there is an
   *Unblock* box at the bottom, tick it and press *OK*. Then extract it to a folder whose path has only English letters
   and digits, e.g. `D:\SIGN2MV` (rename `SIGN2MV-main`). Nothing needs to be installed first.
   Double-click `MANUAL.html` in that folder to read the full manual before installing.
2. Double-click `install.bat`. It downloads Python, the AI programs and models (about 10 GB the first
   time) into the folder; run it again if it stops. If Windows shows *Windows protected your PC*, press
   *More info* → *Run anyway*.
3. Double-click `start.bat`. The app opens in its own window at `http://127.0.0.1:9700`.
4. In the app: **Library** → add a song → import it from YouTube or a file, then sing it, make an AI
   cover or a video.

No songs and no voice models are included: you import your own songs, and train a voice model with your
own voice or import one you have the right to use.

Everything (Python, models, caches, temp files) is installed inside the folder, not on C:.

The full manual, with a step-by-step getting-started chapter, is in `web/manual/` (English master,
Traditional Chinese translation). Open it with `MANUAL.html` in the folder, even before installing, or
with **Manual ↗** in the app. Problems and questions:
[GitHub Issues](https://github.com/nilson0606/SIGN2MV/issues).

## Updating

To update, copy the new files **over** the old folder; your songs, recordings, voice models and settings are not
touched.

1. Press **Shut down** at the top right of SIGN2MV and wait until the window closes.
2. **Code → Download ZIP** on this page; right-click the ZIP → *Properties* → tick *Unblock* → *OK* (skip if there is
   no such box).
3. Extract it anywhere; you get a `SIGN2MV-main` folder.
4. Open `SIGN2MV-main`, select everything (Ctrl + A), copy, and paste it into your SIGN2MV folder (the one with
   `start.bat`); when asked, choose *Replace the files in the destination*.
5. Double-click `start.bat`. **Code date** under *System status* on the home page ends with a 7-character code
   (e.g. `2026-11-08 · 0f0d724`). When it matches the 7-character code at the top right of the file list on this page,
   you are up to date. Compare the code, not just the date: there can be several changes on one day.

To find out whether there is a new version, you can also press **Check for updates** under *System status* on the
home page: it says whether you are up to date and how many newer changes GitHub has (it only asks; nothing is
downloaded or replaced).

`library`, `models`, `runtime` and `config` are not in the ZIP and are never overwritten. Run `install.bat` again
only when the [CHANGELOG](CHANGELOG.md) says so; running it when unsure does no harm, finished parts are skipped.
Every change is listed in the [CHANGELOG](CHANGELOG.md).

## Requirements and limits

- Windows 10 or 11 (64-bit). macOS and Linux are not supported yet.
- About 10 GB of downloads for the first install, kept inside the folder.
- AI work (separation, voice conversion, training, Whisper) uses an NVIDIA graphics card through CUDA
  when present, otherwise the CPU (much slower). Developed on an RTX 4060 Laptop GPU (8 GB).
- MV video encoding tries the graphics card encoders in turn — NVIDIA (NVENC, driver 570 or newer),
  AMD (AMF), Intel (Quick Sync) — then the CPU. The installer reports which one works.
- A microphone for sing & record.

## Use responsibly

Import only songs and recordings you have the right to use. YouTube import uses yt-dlp; check
YouTube's terms where you live. Use voice models only for voices you have the right to use, and do not
present a converted voice as someone else's real performance.

## Layout

| Path | Contents |
|---|---|
| `app/` | FastAPI server, job queue, library, workspace APIs |
| `workers/` | job worker programs (separation, Whisper, MV render, cover, training) |
| `web/` | the web app (shell, `sing/`, `mv/`, manuals) |
| `installer/` | installer, pinned requirements, model manifest |
| `tests/` | pytest suite |

## Tests

```
python -m pytest tests
```
Engine, Applio and voice-model tests run only when these are set:
`SIGN2MV_TEST_ENGINE_PYTHON`, `SIGN2MV_TEST_MODELS`, `SIGN2MV_TEST_APPLIO_PYTHON`,
`SIGN2MV_TEST_APPLIO_DIR`, `SIGN2MV_TEST_VOICE`.

## Licences

This project: MIT (see `LICENSE`). Third-party programs and models are downloaded by the installer and
keep their own licences: see `THIRD_PARTY.md`.
