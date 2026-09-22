# -*- coding: utf-8 -*-
"""Разбивка ролика на части по границам фраз.

Часть не короче MIN_LEN, цель — TARGET_LEN. Граница ставится только там,
где между словами есть пауза; предпочтение — паузе подлиннее и концу предложения,
чтобы не рвать на полуслове. Вступление и реклама вырезаются.
"""
import json, sys, pathlib

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = pathlib.Path(__file__).parent

MIN_LEN = 62.0
TARGET_LEN = 95.0
MAX_LEN = 135.0
MIN_GAP = 0.30

# размечено по транскрипту вручную — надёжнее эвристики
INTRO_END = 70.95                 # «…на титанах в пати» — конец вступления
ADS = [(177.95, 201.45)]          # блок GG Sell

data = json.load(open(ROOT / "transcript.json", encoding="utf-8"))
DUR = data["duration"]
words = []
for s in data["segments"]:
    for w in s["words"]:
        words.append({"w": w["w"].strip(), "s": w["s"], "e": w["e"]})
words.sort(key=lambda w: w["s"])
for i, w in enumerate(words[:-1]):
    w["gap"] = max(0.0, words[i + 1]["s"] - w["e"])
words[-1]["gap"] = 9.9


def in_ads(t):
    return any(a <= t <= b for a, b in ADS)


def score(w, length):
    """чем лучше граница: длинная пауза, конец предложения, близость к цели"""
    s = min(w["gap"], 1.4) * 2.0
    if w["w"].endswith((".", "!", "?", "…")):
        s += 1.6
    elif w["w"].endswith(","):
        s += 0.3
    s -= abs(length - TARGET_LEN) / 55.0
    return s


def text_of(a, b):
    return " ".join(w["w"] for w in words if w["s"] >= a - 0.01 and w["e"] <= b + 0.01)


cuts = []
i = 0
while i < len(words) and (words[i]["s"] < INTRO_END or in_ads(words[i]["s"])):
    i += 1

prev_end = None          # части идут встык, иначе паузы с геймплеем выпадают
while i < len(words):
    start = prev_end if prev_end is not None else words[i]["s"]
    if in_ads(start):
        start = words[i]["s"]
    best = None
    j = i
    while j < len(words):
        w = words[j]
        length = w["e"] - start
        if in_ads(w["s"]):                      # упёрлись в рекламу — заканчиваем до неё
            if j > i and words[j - 1]["e"] - start >= 30:
                best = (999, j - 1)
            break
        if length >= MIN_LEN and w["gap"] >= MIN_GAP:
            sc = score(w, length)
            if best is None or sc > best[0]:
                best = (sc, j)
        if length >= MAX_LEN:
            if best is None:
                best = (0, j)
            break
        j += 1
    if best is None:
        best = (0, min(j, len(words) - 1))
    k = best[1]
    end = min(DUR, words[k]["e"] + 0.45)
    if end - start >= 25:
        cuts.append({"start": round(max(0, start), 2), "end": round(end, 2),
                     "text": text_of(start, end)})
    i = k + 1
    prev_end = end
    if i < len(words) and in_ads(words[i]["s"]):   # дальше реклама — рвём встык
        while i < len(words) and in_ads(words[i]["s"]):
            i += 1
        prev_end = None

# подрезаем тишину по краям: ролик не должен начинаться с молчания
for c in cuts:
    inside = [w for w in words if w["s"] >= c["start"] - 0.01 and w["e"] <= c["end"] + 0.01]
    if not inside:
        continue
    lead = inside[0]["s"] - c["start"]
    if lead > 2.5:
        c["start"] = round(inside[0]["s"] - 1.0, 2)
    tail = c["end"] - inside[-1]["e"]
    if tail > 3.0:
        c["end"] = round(inside[-1]["e"] + 1.6, 2)
    c["text"] = text_of(c["start"], c["end"])

# после подрезки часть могла стать короче минуты — дотягиваем до следующей паузы
for n, c in enumerate(cuts):
    if c["end"] - c["start"] >= MIN_LEN:
        continue
    limit = cuts[n + 1]["start"] if n + 1 < len(cuts) else DUR
    for w in words:
        if w["e"] <= c["end"]:
            continue
        if w["e"] >= limit:
            break
        if w["e"] - c["start"] >= MIN_LEN and w["gap"] >= MIN_GAP:
            c["end"] = round(min(w["e"] + 0.45, limit), 2)
            c["text"] = text_of(c["start"], c["end"])
            break
    if c["end"] - c["start"] < MIN_LEN:      # слов дальше нет — добираем геймплеем
        c["end"] = round(min(c["start"] + MIN_LEN + 2.0, limit), 2)

# хвост короче минуты приклеиваем к предыдущей части
if len(cuts) > 1 and cuts[-1]["end"] - cuts[-1]["start"] < MIN_LEN:
    tail = cuts.pop()
    cuts[-1]["end"] = tail["end"]
    cuts[-1]["text"] = text_of(cuts[-1]["start"], tail["end"])

print("вступление: 0 – %.1f  |  реклама: %s" %
      (INTRO_END, ", ".join("%.1f–%.1f" % a for a in ADS)))
print("\n=== частей: %d ===" % len(cuts))
total = 0
for n, c in enumerate(cuts, 1):
    ln = c["end"] - c["start"]
    total += ln
    print("%2d. %5.1f–%6.1f (%3.0f с)  …%s" % (n, c["start"], c["end"], ln, c["text"][-58:]))
print("\nсуммарно %.0f мин из %.0f мин исходника" % (total / 60, DUR / 60))

json.dump(cuts, open(ROOT / "cuts.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("сохранено: cuts.json")
