# Tutorial film tools (work in progress, not part of the app)

`film.js` drives the real sing page in a demo environment and captures frames; `assemble.py` turns them
into an MP4 (one file per scene, joined with `-c copy`). First film: segment recording, shortest flow (zh-TW).

Demo environment used on 2026-11-12 (Linux container, no GPU):
- server: `SIGN2MV_ROOT=/tmp/tut SIGN2MV_NO_BROWSER=1 SIGN2MV_NO_WARMUP=1 SIGN2MV_FORCE_CPU=1
  SIGN2MV_ENGINE_PYTHON=<wrapper> python3 -m app --port 9713 --no-browser`, `config/settings.json` with
  `"language": "zh-TW"`.
- `<wrapper>` runs the system python with empty `yt_dlp`, `demucs`, `torchaudio` packages and a `torch` stub
  that raises ImportError on use, so the page's tools check passes.
- song "Morning Light": 64 s from `tests/synth_song.py` (voice and backing written with one common gain),
  a 960x540 gradient video with lyric lines, `source/source.json` written by hand; the voice and backing
  are placed as `stems/<key>/vocals.wav|instrumental.wav` (key from `app.stems.plan`), then
  `POST /sr/jobs` with `pitchMethod: "yin"` builds the reference without the real engine.
- browser: Chromium with `--force-device-scale-factor=2 --window-size=960,540` and `viewport: null`
  (the screencast then gives 1920x1080 frames; an emulated deviceScaleFactor gives 960x540), a fake
  microphone, and "律動" turned off to lower the load.
- On a 2-core machine the page sometimes reports a capture break while recording; `film.js` records that
  take again and marks the broken one so `assemble.py` leaves it out.

Run: `RECORD=1 DSF=2 node film.js` (about 5 min), then `python3 assemble.py`.
