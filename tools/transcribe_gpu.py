# -*- coding: utf-8 -*-
"""Расшифровка с пословными таймингами на GPU."""
import os, sys, glob, json, time, site
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for sp in site.getsitepackages():
    for d in glob.glob(os.path.join(sp, "nvidia", "*", "bin")):
        os.add_dll_directory(d)
        os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
from faster_whisper import WhisperModel

src = sys.argv[1]
dst = sys.argv[2]
MODEL = os.environ.get("WHISPER_MODEL", "large-v3")   # путь к локальной модели или её имя
m = WhisperModel(MODEL, device="cuda", compute_type="float16")
t0 = time.time()
segs, info = m.transcribe(src, language="ru", word_timestamps=True, beam_size=5,
                          vad_filter=True, vad_parameters=dict(min_silence_duration_ms=350),
                          condition_on_previous_text=True)
out = []
for s in segs:
    out.append({
        "s": round(s.start, 3), "e": round(s.end, 3), "text": s.text.strip(),
        "words": [{"w": w.word, "s": round(w.start, 3), "e": round(w.end, 3)} for w in (s.words or [])]
    })
    if len(out) % 40 == 0:
        print("  %5.1f%%  %6.1f с  %s" % (100 * s.end / info.duration, s.end, s.text.strip()[:60]), flush=True)
json.dump({"duration": info.duration, "segments": out}, open(dst, "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("готово: %d сегментов за %.0f с (аудио %.0f с)" % (len(out), time.time() - t0, info.duration))
