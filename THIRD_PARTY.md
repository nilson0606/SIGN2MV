# Third-party components

SIGN2MV downloads these components during `install.bat` into the application
folder. They are not part of this repository. Each keeps its own licence; where
a model page states no licence, check the linked source before any use beyond
personal use.

## Programs and libraries

| Component | Use | Licence |
|---|---|---|
| uv (astral-sh) | Python and environment manager | MIT / Apache-2.0 |
| CPython 3.12 | runtime | PSF |
| FFmpeg (BtbN GPL build, with Rubber Band) | audio/video conversion, key change, MV encoding | GPL |
| Deno | yt-dlp JavaScript runtime | MIT |
| PyTorch, torchaudio, torchvision | AI runtime | BSD-3-Clause |
| FastAPI, Uvicorn, python-multipart | local web server | MIT / BSD |
| NumPy, Pillow | MV frames | BSD / MIT-CMU |
| Demucs | vocal separation | MIT |
| audio-separator | RoFormer separation | MIT |
| faster-whisper, CTranslate2 | lyric alignment | MIT |
| yt-dlp | YouTube import | Unlicense |
| librosa, soundfile, SciPy | audio processing | ISC / BSD |
| Applio 3.7.1 | RVC voice conversion and training | MIT |
| basic-pitch 0.4.0 (ONNX model, installed without TensorFlow) | melody transcription | Apache-2.0 |
| pretty_midi, mir_eval | MIDI | MIT |
| tinysoundfont | sound-font synthesis | MIT |

## Models and sounds

| Model | Use | Licence / source |
|---|---|---|
| htdemucs | separation | MIT (Demucs) |
| BS-RoFormer ep317 (viperx) | separation | licence not verified; UVR public model, downloaded by audio-separator from [TRvlvr/model_repo](https://github.com/TRvlvr/model_repo/releases/tag/all_public_uvr_models) |
| Mel-RoFormer vocals (Kimberley Jensen) | separation | licence not verified; [KimberleyJSN/melbandroformer](https://huggingface.co/KimberleyJSN/melbandroformer) |
| Mel-RoFormer karaoke (aufr33, viperx) | lead / backing split | licence not verified; UVR public model, [TRvlvr/model_repo](https://github.com/TRvlvr/model_repo/releases/tag/all_public_uvr_models) |
| BS-RoFormer male/female (aufr33) | duet split | licence not verified; [python-audio-separator model-configs](https://github.com/nomadkaraoke/python-audio-separator/releases/tag/model-configs) |
| Sucial male/female (chorus BS-RoFormer ep267) | duet split, optional | CC BY-NC-SA 4.0 (non-commercial); installed only after accepting it; [python-audio-separator model-configs](https://github.com/nomadkaraoke/python-audio-separator/releases/tag/model-configs) |
| Mel-RoFormer karaoke (becruily) | lead / backing split, optional | licence not verified; downloaded by hand from [python-audio-separator model-configs](https://github.com/nomadkaraoke/python-audio-separator/releases/tag/model-configs) |

"Licence not verified" means the model's own page has not been checked for terms yet. These community
separation models are widely used with audio-separator and UVR, but before any use beyond personal use,
check the model page. File sizes and SHA-256 hashes are in `installer/manifest.json`.
| RMVPE (`rmvpe.pt`) | pitch | from huggingface.co/lj1995/VoiceConversionWebUI (MIT) |
| ContentVec, HiFi-GAN pretrained G/D | Applio conversion and training | downloaded by Applio (see Applio) |
| chinese-hubert-base (TencentGameMate, via Applio's model repository) | optional feature model for training | MIT |
| faster-whisper medium / small (Systran) | lyric alignment | MIT (OpenAI Whisper weights) |
| GeneralUser GS 2.0.3 (S. Christian Collins) | steel guitar / yangqin sounds | GeneralUser GS License v2.0: free use and redistribution |

Guzheng and dizi samples are not downloaded; users can import their own .ogg
samples (a folder with guzheng / dizi subfolders) on the AI cover page.

## Code carried over

Both projects are by the same author as SIGN2MV and are covered by this project's licence (MIT):

- The sing & record front end (`web/sing/`) and its recording modules come from the author's
  [sign_record](https://github.com/nilson0606/sign_record) project.
- The MV page (`web/mv/index.html`) and the MV, mixing, melody, training and alignment logic are
  ported from the author's earlier private project (AI_COVER_MV).

## Data included in this repository

- `app/t2s_chars.txt`: Traditional → Simplified Chinese, one character each, taken from
  [OpenCC](https://github.com/BYVoid/OpenCC)'s `TSCharacters.txt` (Apache-2.0). It is used only to compare
  pasted lyrics with recognized words (Whisper mixes both scripts); no text shown to the user is converted.

## FFmpeg (GPL)

This repository contains no FFmpeg binaries: `install.bat` downloads the BtbN GPL build (pinned
release and SHA-256 in `installer/manifest.json`) and SIGN2MV runs it as a separate program. Anyone who
redistributes a package that includes `ffmpeg.exe` must ship it under the GPL (licence text and a way to
get the corresponding source), as for any GPL program.
