# Senku Cuts

Desktop tooling that turns a long gameplay recording into short vertical clips,
ready to be uploaded to the creator's own TikTok drafts.

Built for a single channel, not offered as a service to other people.

## What it does

1. **Transcribes** the narration with word-level timing (faster-whisper, GPU).
2. **Splits** the recording into parts at natural sentence boundaries — no cuts
   mid-word, each part at least a minute, intro and sponsor block removed.
3. **Renders** each part as a 1080×1920 vertical clip: gameplay framed over a
   blurred backdrop, part number on top, word-by-word subtitles that stay on a
   fixed line so the viewer's eyes don't jump.
4. **Uploads** the finished clips to the owner's TikTok drafts. Nothing is ever
   published automatically — every post is reviewed and published by hand.

## Layout

```
tools/transcribe_gpu.py   расшифровка с пословными таймингами
tools/plan_cuts.py        разметка частей по границам фраз
tools/make_clips.py       сборка вертикальных роликов с субтитрами
docs/                     страницы для TikTok Developer Portal (GitHub Pages)
```

## Usage

```bash
ffmpeg -i final.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le audio.wav
python tools/transcribe_gpu.py audio.wav transcript.json
python tools/plan_cuts.py                 # печатает разметку, пишет cuts.json
python tools/make_clips.py                # собирает все части
python tools/make_clips.py 5 --styles     # пятая часть во всех вариантах кадра
```

Set `WHISPER_MODEL` to a local model directory if the model is not downloaded
through Hugging Face.

## TikTok permissions

| Scope | Why |
|---|---|
| `user.info.basic` | confirm which account is connected |
| `video.upload` | place finished clips into that account's drafts |

Neither publishing nor reading other users' data is requested.

[Terms of Service](https://unkes.github.io/senku-cuts/tos.html) ·
[Privacy Policy](https://unkes.github.io/senku-cuts/privacy.html)
