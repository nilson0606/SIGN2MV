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
| BS-RoFormer ep317 (viperx), Mel-RoFormer Kim, karaoke aufr33/viperx, male/female aufr33 | separation | see the model pages listed by audio-separator |
| Sucial male/female (chorus BS-RoFormer ep267) | duet split, optional | CC BY-NC-SA 4.0 (non-commercial); installed only after accepting it |
| RMVPE (`rmvpe.pt`) | pitch | from huggingface.co/lj1995/VoiceConversionWebUI (MIT) |
| ContentVec, HiFi-GAN pretrained G/D | Applio conversion and training | downloaded by Applio (see Applio) |
| faster-whisper medium / small (Systran) | lyric alignment | MIT (OpenAI Whisper weights) |
| GeneralUser GS 2.0.3 (S. Christian Collins) | steel guitar / yangqin sounds | GeneralUser GS License v2.0: free use and redistribution |

Guzheng and dizi samples are not downloaded; the user can import their own
copies (for example from the old AI cover folder) on the AI cover page.

## Code carried over

- The sing & record front end (`web/sing/`) and its recording/diagnostics
  modules come from the author's sign_record project.
- The MV page (`web/mv/index.html`) and the MV, mixing, melody, training and
  alignment logic are ported from the author's AI_COVER_MV project.
