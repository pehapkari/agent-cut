"""Step 8 – render selected highlights as 1080×1920 reels → out/reels/NN_slug.mp4.

Reads work/highlights.json; renders items with "selected": true.
Per reel:
  * layout "split": camera (face-tracked crop) on top 1080×960, screen below,
    brand band at the bottom; "full": camera crop over the whole frame.
    Default "auto" = split unless the screen is blank/static or unavailable.
  * burned-in ASS subtitles (max 2 lines, keywords highlighted)
  * audio from work/audio_clean.wav
Analysis (face tracking, screen check) runs on proxies; render on originals.

  08_reels.py            render all selected
  08_reels.py 2 5        render only reels number 2 and 5
"""
import json
import re
import subprocess
import sys

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d

from common import LECTURE, OUT, TOOLS, WORK, config, load_json, log, run, src

W, H, FPS = 1080, 1920, 30
TOP_H = 960                       # camera box height in split layout (screen goes below)
BRAND_BG = "4F5B93"               # from the event graphics
ACCENT = "&H003BD4FF"             # ASS BGR: #FFD43B yellow
FONT = "Montserrat ExtraBold"     # tools/fonts/Montserrat-ExtraBold.ttf


# -------------------------------------------------------------------- timing
def offset_at(o: dict, main_t: float) -> float:
    """Source offset at a given main-audio time, including clock drift."""
    ref = o.get("query_start", 0) + o.get("query_len", 0) / 2
    src_t = main_t - o["offset"]
    return o["offset"] + o.get("drift_ppm", 0) * 1e-6 * (src_t - ref)


# ------------------------------------------------------------- face tracking
def track_face(cam_t0: float, dur: float, crop_w: int, crop_h: int, face_y: float,
               src_w: int, src_h: int) -> np.ndarray:
    """Per-frame crop x/y (in original camera pixels) following the speaker's face."""
    proxy = WORK / "proxy" / "camera.mp4"
    cap = cv2.VideoCapture(str(proxy))
    pw, ph = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    sx, sy = src_w / pw, src_h / ph
    det = cv2.FaceDetectorYN.create(str(TOOLS / "models" / "face_detection_yunet_2023mar.onnx"), "", (pw, ph), 0.6)
    step = 0.2
    ts, xs, ys = [], [], []
    for t in np.arange(0, dur + step, step):
        cap.set(cv2.CAP_PROP_POS_MSEC, (cam_t0 + t) * 1000)
        ok, f = cap.read()
        if not ok:
            continue
        _, faces = det.detect(f)
        if faces is None:
            continue
        # biggest confident face
        x, y, w, h = max(faces, key=lambda r: r[2] * r[3] * r[-1])[:4]
        ts.append(t)
        xs.append((x + w / 2) * sx)
        ys.append((y + h / 2) * sy)
    cap.release()
    n = int(round(dur * FPS)) + 1
    tt = np.arange(n) / FPS
    if len(ts) < 3:
        log("WARNING: face not found – centered crop")
        cx = np.full(n, src_w / 2)
        cy = np.full(n, src_h / 2)
    else:
        # robust: drop outliers (other faces, false hits) vs. running median
        xs, ys, ts = np.array(xs), np.array(ys), np.array(ts)
        med = np.array([np.median(xs[max(0, i - 7): i + 8]) for i in range(len(xs))])
        keep = np.abs(xs - med) < crop_w * 0.25
        cx = np.interp(tt, ts[keep], xs[keep])
        cy = np.interp(tt, ts[keep], ys[keep])
        # slow, smooth camera move
        cx = gaussian_filter1d(cx, sigma=FPS * 0.8, mode="nearest")
        cy = gaussian_filter1d(cy, sigma=FPS * 2.0, mode="nearest")
    x = np.clip(cx - crop_w / 2, 0, src_w - crop_w)
    y = np.clip(cy - crop_h * face_y, 0, src_h - crop_h)
    # if the speaker stays inside a static window, don't move at all
    if x.max() - x.min() < crop_w * 0.12:
        x[:] = np.median(x)
    if y.max() - y.min() < crop_h * 0.12:
        y[:] = np.median(y)
    return np.stack([x, y], axis=1).round().astype(int)


# ------------------------------------------------------------- screen borders
def screen_crop(dur: float) -> tuple[int, int, int, int]:
    """Black bars of the screen recording (OBS canvas ≠ display) via cropdetect
    on 4 windows of the original; the union of the results wins. Cached."""
    cache = WORK / "screen_crop.json"
    if cache.exists():
        return tuple(load_json("screen_crop.json")["crop"])
    found = []
    for f in (0.2, 0.4, 0.6, 0.8):
        res = subprocess.run(["ffmpeg", "-v", "info", "-nostdin", "-ss", f"{dur * f:.1f}", "-i", str(src("screen")),
                              "-t", "3", "-vf", "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
        m = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", res)
        if m:
            found.append(tuple(int(v) for v in m[-1]))
    # union of the samples: bars never hold content, but a dark slide can fool one sample
    x0, y0 = min(f[2] for f in found), min(f[3] for f in found)
    x1, y1 = max(f[2] + f[0] for f in found), max(f[3] + f[1] for f in found)
    crop = (x1 - x0, y1 - y0, x0, y0)
    cache.write_text(json.dumps({"crop": crop, "samples": found}) + "\n")
    log(f"screen crop {crop}")
    return crop


# --------------------------------------------------------------- screen check
def screen_layout(scr_t0: float, dur: float, scr_dur: float) -> tuple[str, str]:
    if scr_t0 < 0 or scr_t0 + dur > scr_dur:
        return "full", "screen not recorded for this passage"
    cap = cv2.VideoCapture(str(WORK / "proxy" / "screen.mp4"))
    stds, edges = [], []
    for t in np.linspace(0.5, dur - 0.5, 8):
        cap.set(cv2.CAP_PROP_POS_MSEC, (scr_t0 + t) * 1000)
        ok, f = cap.read()
        if not ok:
            continue
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        stds.append(float(g.std()))
        edges.append(float((cv2.Canny(g, 60, 160) > 0).mean()))
    cap.release()
    if not stds or np.median(stds) < 12 or np.median(edges) < 0.012:
        return "full", f"screen looks empty (std {np.median(stds):.0f}, edges {np.median(edges):.3f})"
    return "split", f"screen has content (std {np.median(stds):.0f}, edges {np.median(edges):.3f})"


# ----------------------------------------------------------------- subtitles
FONT_SIZE = 76
MAX_LINE_PX = W - 2 * 70     # line width incl. outline must stay inside the safe margins
_font = None


def text_px(text: str) -> float:
    global _font
    if _font is None:
        from PIL import ImageFont
        _font = ImageFont.truetype(str(TOOLS / "fonts" / "Montserrat-ExtraBold.ttf"), FONT_SIZE)
    return _font.getlength(text) + 12          # + outline on both sides


def join(ws: list[dict]) -> str:
    return " ".join(w["w"] for w in ws)


def fits(ws: list[dict]) -> bool:
    """Does this run of words fit into ≤ 2 lines?"""
    return len(two_lines(ws)) <= 2 and all(text_px(join(ln)) <= MAX_LINE_PX for ln in two_lines(ws))


def ass_time(t: float) -> str:
    t = max(0.0, t)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def is_key(word: str, keys: set[str]) -> bool:
    w = re.sub(r"[^\w]", "", word.lower())
    return bool(w) and (w in keys or any(ch.isdigit() for ch in w))


def cues(words: list[dict]) -> list[list[dict]]:
    """Group words into cues: ≤ 2 lines that fit, ≤ 3.2 s, break on pauses and sentence ends."""
    out, cur = [], []
    for w in words:
        if cur and (not fits(cur + [w]) or w["s"] - cur[-1]["e"] > 0.6 or w["e"] - cur[0]["s"] > 3.2):
            out.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.?!…]$", w["w"]) or (re.search(r"[,:;]$", w["w"]) and text_px(join(cur)) > MAX_LINE_PX):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def two_lines(ws: list[dict]) -> list[list[dict]]:
    """One line if it fits, else the most balanced split into two lines."""
    if text_px(join(ws)) <= MAX_LINE_PX or len(ws) < 2:
        return [ws]
    best = min(range(1, len(ws)), key=lambda i: max(text_px(join(ws[:i])), text_px(join(ws[i:]))))
    return [ws[:best], ws[best:]]


def write_ass(path, words: list[dict], t0: float, dur: float, keys: set[str], y_center: int, brand: str):
    keys = {k.lower() for k in keys}
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{FONT},{FONT_SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,6,3,5,60,60,0,1
Style: Brand,{FONT},40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,0,0,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    if brand:
        ev.append(f"Dialogue: 0,{ass_time(0)},{ass_time(dur)},Brand,,0,0,0,,{{\\pos({W // 2},{H - 300})}}{brand}")
    cs = cues([w for w in words if w["e"] > t0 and w["s"] < t0 + dur])
    for i, c in enumerate(cs):
        start = c[0]["s"] - t0
        end = (cs[i + 1][0]["s"] - t0) if i + 1 < len(cs) else c[-1]["e"] - t0 + 0.4
        end = min(end, c[-1]["e"] - t0 + 0.8, dur)
        lines = []
        for ln in two_lines(c):
            parts = []
            for w in ln:
                t = w["w"].replace("{", "").replace("}", "")
                parts.append(f"{{\\c{ACCENT}}}{t}{{\\c&H00FFFFFF&}}" if is_key(t, keys) else t)
            lines.append(" ".join(parts))
        ev.append(f"Dialogue: 1,{ass_time(start)},{ass_time(end)},Cap,,0,0,0,,"
                  f"{{\\pos({W // 2},{y_center})\\fad(60,60)}}" + "\\N".join(lines))
    path.write_text(head + "\n".join(ev) + "\n")


# -------------------------------------------------------------------- render
def render(n: int, h: dict, cfg: dict, offs: dict, probe: dict, words: list[dict]):
    a0, a1 = h["start"], h["end"]
    dur = a1 - a0
    cam_off = offset_at(offs["camera"], a0 + dur / 2)
    cam_t0 = a0 - cam_off
    scr_t0 = a0 - offs["screen"]["offset"]
    cam_v = probe["camera"]["video"][0]
    cw, ch = cam_v["width"], cam_v["height"]

    layout = h.get("layout", "auto")
    reason = "set in highlights.json"
    if layout == "auto":
        layout, reason = screen_layout(scr_t0, dur, probe["screen"]["duration"])
    log(f"#{n:02d} {h['slug']}: {dur:.1f}s layout={layout} ({reason})")

    if layout == "split":
        box_w, box_h = W, TOP_H
        crop_h = int(ch * h.get("zoom", 0.62))
        face_y, cap_y = 0.36, TOP_H - 120
    else:
        box_w, box_h = W, H
        crop_h = int(ch * h.get("zoom", 0.8))
        face_y, cap_y = 0.30, int(H * 0.68)
    crop_w = int(round(crop_h * box_w / box_h / 2) * 2)
    crop_h -= crop_h % 2

    xy = track_face(cam_t0, dur, crop_w, crop_h, face_y, cw, ch)
    rdir = WORK / "reels"
    rdir.mkdir(exist_ok=True)
    stem = f"{n:02d}_{h['slug']}"
    cmd_file = rdir / f"{stem}.crop.txt"
    with cmd_file.open("w") as f:
        prev = None
        for i, (x, y) in enumerate(xy):
            if (x, y) != prev:
                f.write(f"{i / FPS:.4f} crop@c x {x}, crop@c y {y};\n")
                prev = (x, y)
    ass = rdir / f"{stem}.ass"
    brand = f"{cfg.get('speaker', '')}  ·  pražský sraz přátel PHP" if layout == "split" else ""
    write_ass(ass, words, a0, dur, set(h.get("keywords", [])), cap_y, brand)

    x0, y0 = xy[0]
    cam_chain = (f"[0:v]fps={FPS},sendcmd=f='{cmd_file}',crop@c=w={crop_w}:h={crop_h}:x={x0}:y={y0},"
                 f"scale={box_w}:{box_h}:flags=lanczos,unsharp=5:5:0.6,setsar=1[cam]")
    if layout == "split":
        sw, sh, sx, sy = screen_crop(probe["screen"]["duration"])
        scr_h = int(round(W * sh / sw / 2) * 2)
        fc = (f"{cam_chain};"
              f"[1:v]fps={FPS},crop={sw}:{sh}:{sx}:{sy},scale={W}:{scr_h}:flags=lanczos,setsar=1[scr];"
              f"color=c=0x{BRAND_BG}:s={W}x{H}:r={FPS}:d={dur:.3f}[bg];"
              f"[bg][cam]overlay=0:0:shortest=1[t1];[t1][scr]overlay=0:{TOP_H}:shortest=1[t2];"
              f"[t2]ass='{ass}':fontsdir='{TOOLS / 'fonts'}'[v]")
        inputs = ["-ss", f"{cam_t0:.3f}", "-t", f"{dur:.3f}", "-i", str(src("camera")),
                  "-ss", f"{scr_t0:.3f}", "-t", f"{dur:.3f}", "-i", str(src("screen"))]
        a_idx = 2
    else:
        fc = f"{cam_chain};[cam]ass='{ass}':fontsdir='{TOOLS / 'fonts'}'[v]"
        inputs = ["-ss", f"{cam_t0:.3f}", "-t", f"{dur:.3f}", "-i", str(src("camera"))]
        a_idx = 1
    fc += f";[{a_idx}:a]afade=t=in:d=0.08,afade=t=out:st={dur - 0.3:.3f}:d=0.3[a]"
    inputs += ["-ss", f"{a0:.3f}", "-t", f"{dur:.3f}", "-i", str(WORK / "audio_clean.wav")]

    OUT.joinpath("reels").mkdir(parents=True, exist_ok=True)
    dst = OUT / "reels" / f"{stem}.mp4"
    run(["ffmpeg", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-t", f"{dur:.3f}", "-r", str(FPS),
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(dst)])
    h["render"] = {"file": str(dst.relative_to(LECTURE)), "layout": layout, "layout_reason": reason,
                   "camera_offset": round(cam_off, 4), "crop": [crop_w, crop_h],
                   "crop_moves": int((np.diff(xy, axis=0) != 0).any(axis=1).sum()),
                   # share of frames where the crop is pinned to the camera frame edge
                   # (speaker walked out of the croppable area – a limit of the shot)
                   "crop_at_edge": round(float(((xy[:, 0] == 0) | (xy[:, 0] == cw - crop_w)).mean()), 2)}
    log(f"wrote {dst.relative_to(LECTURE)}")


def subtitle_words(tr: dict) -> list[dict]:
    """Transcript words with manual fixes (work/subs_fixes.json) and re-joined
    Whisper sub-tokens ("e" + "-shop" → "e-shop")."""
    fixes = {}
    if (WORK / "subs_fixes.json").exists():
        fixes = {k: v for k, v in load_json("subs_fixes.json").items() if not k.startswith("_")}
    out = []
    for s in tr["segments"]:
        for w in s["words"]:
            w = dict(w)
            key = f"{w['s']:.2f}"
            if key in fixes:
                w["w"] = fixes[key]
            if not w["w"].strip():
                continue
            if w["w"].startswith("-") and out and not out[-1]["w"][-1:] in ".,?!":
                out[-1]["w"] += w["w"]
                out[-1]["e"] = w["e"]
                continue
            out.append(w)
    return out


def main():
    cfg = config()
    offs, probe = load_json("offsets.json"), load_json("probe.json")
    hl = load_json("highlights.json")
    words = subtitle_words(load_json("transcript.json"))
    only = {int(a) for a in sys.argv[1:] if a.isdigit()}
    sel = [h for h in hl if h.get("selected")]
    if not sel:
        raise SystemExit("no highlight has \"selected\": true in work/highlights.json")
    for n, h in enumerate(sel, 1):
        if only and n not in only:
            continue
        render(n, h, cfg, offs, probe, words)
    import json
    (WORK / "highlights.json").write_text(json.dumps(hl, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
