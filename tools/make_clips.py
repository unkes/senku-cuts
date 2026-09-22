# -*- coding: utf-8 -*-
"""Сборка вертикальных роликов 1080×1920 из cuts.json.

  python make_clips.py                     — собрать все части
  python make_clips.py 5                   — только пятую
  python make_clips.py 5 --styles          — пятую во всех вариантах кадра
  python make_clips.py 5 --seconds=15      — короткий кусок для проверки
"""
import json, subprocess, sys, pathlib

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "final.mp4"
OUT = ROOT / "clips"
FONTS = ROOT / "fonts"
W, H = 1080, 1920

STYLE = "B2"          # выбранный кадр: боковины срезаны, геймплей крупный
SUB_SIZE = 70         # кегль субтитров
SUB_OUTLINE = 7
SUB_MAXW = 780        # шире — перенос или обрезка по краям
SUB_FUDGE = 1.14      # libass рисует шире, чем меряет PIL — берём запас
SUB_MAXWORDS = 5
SUB_Y = 1570          # строка всегда стоит здесь


def vf_chain(style):
    """B — весь кадр; B2/B3 — кроп боковин; C — полный кроп 9:16."""
    if style == "C":
        return "[0:v]crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=%d:%d[v]" % (W, H)
    crop = {"B": None, "B2": 1.20, "B3": 1.45}.get(style)
    fg = "[fg]"
    if crop:
        fg += "crop=ih*%.3f:ih:(iw-ih*%.3f)/2:0," % (crop, crop)
    fg += "scale=%d:-2[fgs];" % W
    gy = int(H * 0.26)
    return ("[0:v]split=2[bg][fg];"
            "[bg]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
            "gblur=sigma=34,eq=brightness=-0.12:saturation=1.12[bgb];" % (W, H, W, H)
            + fg + "[bgb][fgs]overlay=(W-w)/2:%d[v]" % gy)


def esc(t):
    return t.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def ass_header():
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: " + str(W) + "\n"
        "PlayResY: " + str(H) + "\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: sub,Montserrat Black," + str(SUB_SIZE) + ",&H00FFFFFF,&H000000FF,&H00101010,"
        "&H00000000,0,0,0,0,100,100,0,0,1," + str(SUB_OUTLINE) + ",4,5,40,40,40,204\n"
        "Style: part,Montserrat Black,66,&H00FFFFFF,&H000000FF,&H001A1A1A,"
        "&H00000000,0,0,0,0,100,100,2,0,1,5,3,8,60,60,110,204\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")


def tc(t):
    t = max(0.0, t)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return "%d:%02d:%05.2f" % (h, m, s)


_font = None


def text_width(t):
    """ширина строки в пикселях — по ней набираем группу, чтобы не было переноса"""
    global _font
    if _font is None:
        from PIL import ImageFont
        _font = ImageFont.truetype(str(FONTS / "Montserrat-Black.ttf"), SUB_SIZE)
    return _font.getlength(t) * SUB_FUDGE + 2 * SUB_OUTLINE


def group_words(ws):
    """слова бьём на строки, которые заведомо влезают в одну строку"""
    lines, cur = [], []
    for w in ws:
        trial = cur + [w]
        if cur and text_width(" ".join(x["w"].strip() for x in trial)) > SUB_MAXW:
            lines.append(cur)
            cur = [w]
        else:
            cur = trial
        if len(cur) >= SUB_MAXWORDS:
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    return lines


def build_ass(words, t0, t1, part_no, total, path):
    """Строка стоит на месте: показываем группу целиком, подсвечивая текущее слово.
       Кончилась группа — гаснет целиком, следующая появляется там же."""
    ev = ["Dialogue: 0,%s,%s,part,,0,0,0,,ЧАСТЬ %d / %d"
          % (tc(0), tc(min(6.0, t1 - t0)), part_no, total)]
    ws = [w for w in words if w["e"] > t0 and w["s"] < t1 and w["w"].strip()]
    pos = "{\\pos(%d,%d)\\q2}" % (W // 2, SUB_Y)
    hot, back = "{\\c&H43E0FF&}", "{\\c&HFFFFFF&}"
    lines = group_words(ws)
    for li, line in enumerate(lines):
        # следующая строка появится тут — до неё текущая должна погаснуть
        nxt = lines[li + 1][0]["s"] - t0 if li + 1 < len(lines) else t1 - t0
        for k, cur in enumerate(line):
            parts = []
            for j, w in enumerate(line):
                txt = esc(w["w"].strip())
                parts.append(hot + txt + back if j == k else txt)
            full = " ".join(x["w"].strip() for x in line)
            wpx = text_width(full)
            fit = ""
            if wpx > SUB_MAXW:                       # длинная строка — ужимаем, а не режем
                kk = max(62, int(100 * SUB_MAXW / wpx))
                fit = "{\\fscx%d\\fscy%d}" % (kk, kk)
            start = cur["s"] - t0
            if k + 1 < len(line):
                end = line[k + 1]["s"] - t0          # до следующего слова этой же строки
            else:
                end = min(cur["e"] - t0 + 0.5, nxt, t1 - t0)   # гаснет до прихода следующей
            if end <= start:
                end = start + 0.10
            ev.append("Dialogue: 0,%s,%s,sub,,0,0,0,,%s%s%s"
                      % (tc(start), tc(end), pos, fit, " ".join(parts)))
    path.write_text(ass_header() + "\n".join(ev) + "\n", encoding="utf-8")


def run(cut, part_no, total, words, style=STYLE, suffix=""):
    OUT.mkdir(exist_ok=True)
    t0, t1 = cut["start"], cut["end"]
    ass = ROOT / ("_sub_%02d%s.ass" % (part_no, suffix))
    build_ass(words, t0, t1, part_no, total, ass)
    dst = OUT / ("часть_%02d%s.mp4" % (part_no, suffix))
    assf = str(ass).replace("\\", "/").replace(":", "\\:")
    fdir = str(FONTS).replace("\\", "/").replace(":", "\\:")
    vf = vf_chain(style) + ";[v]subtitles='%s':fontsdir='%s'[vo]" % (assf, fdir)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", str(t0), "-to", str(t1), "-i", str(SRC),
         "-filter_complex", vf, "-map", "[vo]", "-map", "0:a",
         "-c:v", "libx264", "-preset", "medium", "-crf", "19",
         "-pix_fmt", "yuv420p", "-profile:v", "high", "-r", "60",
         "-c:a", "aac", "-b:a", "192k", "-ac", "2",
         "-movflags", "+faststart", str(dst)], check=True)
    ass.unlink(missing_ok=True)
    return dst


if __name__ == "__main__":
    cuts = json.load(open(ROOT / "cuts.json", encoding="utf-8"))
    data = json.load(open(ROOT / "transcript.json", encoding="utf-8"))
    words = [w for s in data["segments"] for w in s["words"]]

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    styles_mode = "--styles" in sys.argv
    secs = None
    for a in sys.argv[1:]:
        if a.startswith("--seconds="):
            secs = float(a.split("=")[1])
    idx = [int(args[0])] if args else range(1, len(cuts) + 1)

    for n in idx:
        c = dict(cuts[n - 1])
        if secs:
            c["end"] = round(c["start"] + secs, 2)
        if styles_mode:
            for st in ("B", "B2", "B3", "C"):
                print("готово:", run(c, n, len(cuts), words, style=st, suffix="_вариант" + st).name)
        else:
            p = run(c, n, len(cuts), words)
            print("готово: %s  (%.0f с)" % (p.name, c["end"] - c["start"]), flush=True)
