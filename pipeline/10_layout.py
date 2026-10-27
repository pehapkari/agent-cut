"""Step 10 – lecture layout ("program" video) for the edit → work/layout/program.mp4.

Composites, on the main-audio timeline (same time base as audio_clean.wav, so
the FCPXML cuts apply 1:1):
  * background: work/brand/video-background@2x.png (11_brand.py), else lecture.json "background_png"
  * the screen recording (black OBS bars cropped) in the left slot with a frame
  * the speaker's head, face-tracked from the camera, in a circle (or sharp-edged square framed like the screen,
    lecture.json "head_shape") in the top-right corner
The screen and the head fade in at the start of the first kept range of the
approved edit plan, so the cut from the intro onto the background is clean.

Face detection runs on the camera proxy (all faces cached in work/layout/head_dets.npz,\nthe followed speaker in work/layout/head_track.npz);
the render reads the original camera.

  10_layout.py            track (if needed) + render
  10_layout.py preview    a few still frames → work/layout/preview_*.jpg
"""
import subprocess
import time
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter1d

from common import LECTURE, TOOLS, WORK, config, ffmpeg_bin, load_json, log, src, tc

FPS = 30
W, H = 1920, 1080
BAR_TOP, BAR_BOTTOM = 117, 963          # bands of the event template
MARGIN = 24
HEAD = 330                              # bubble size (px)
RING = 7                                # ring width (px)
BRAND = (0x4F, 0x5B, 0x93)
LAYOUT = WORK / "layout"


# ------------------------------------------------------------------ geometry
def geometry(screen_crop) -> dict:
    sw, sh = screen_crop[0], screen_crop[1]
    scr_h = BAR_BOTTOM - BAR_TOP - 2 * MARGIN
    scr_w = int(round(scr_h * sw / sh / 2) * 2)
    scr_x, scr_y = MARGIN, BAR_TOP + MARGIN
    col_x = scr_x + scr_w                  # right column starts here
    head_x = col_x + (W - col_x - HEAD) // 2
    head_y = BAR_TOP + MARGIN + 6
    return {"scr": (scr_x, scr_y, scr_w, scr_h), "head": (head_x, head_y, HEAD)}


# ------------------------------------------------------------- face tracking
def detect_faces() -> dict:
    """All face detections on the camera proxy at 10 Hz (cached, the slow part)."""
    cache = LAYOUT / "head_dets.npz"
    if cache.exists():
        d = np.load(cache)
        return {k: d[k] for k in d.files}
    proxy = WORK / "proxy" / "camera.mp4"
    cap = cv2.VideoCapture(str(proxy))
    pw, ph = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    det = cv2.FaceDetectorYN.create(str(TOOLS / "models" / "face_detection_yunet_2023mar.onnx"), "", (pw, ph), 0.6)
    every = 3                                    # detect at 10 Hz
    rows = []                                    # frame, cx, cy, h, score
    i = 0
    log("detecting faces in the camera proxy (10 Hz)")
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % every == 0:
            _, f = cap.retrieve()
            _, faces = det.detect(f)
            for x, y, w, h, *_, score in (faces if faces is not None else []):
                rows.append((i, x + w / 2, y + h / 2, h, score))
        if i % (FPS * 300) == 0:
            log(f"  {tc(i / FPS)}")
        i += 1
    cap.release()
    out = {"dets": np.array(rows, np.float32).reshape(-1, 5), "n": np.int64(i),
           "proxy_w": np.float32(pw), "proxy_h": np.float32(ph)}
    LAYOUT.mkdir(parents=True, exist_ok=True)
    np.savez(cache, **out)
    return out


def track_head(cam_dur: float) -> dict:
    """Follow the speaker: each sample takes the face closest to where the speaker
    was, of similar size; faces elsewhere (photos on the projected slide, the
    audience) are ignored. Lost for long → re-acquire on a face of the usual size."""
    cache = LAYOUT / "head_track.npz"
    if cache.exists():
        d = np.load(cache)
        return {k: d[k] for k in d.files}
    D = detect_faces()
    dets, n = D["dets"], int(D["n"])
    frames = np.unique(dets[:, 0]).astype(int)
    by_frame = {f: dets[dets[:, 0] == f] for f in frames}
    ref_h = float(np.median([by_frame[f][np.argmax(by_frame[f][:, 3]), 3] for f in frames]))
    speed = 6.0 * ref_h                          # max plausible head motion per second (px)
    ts, xs, ys, hs = [], [], [], []
    last = None                                  # (frame, x, y, h)
    for f in frames:
        c = by_frame[f]
        if last is None or (f - last[0]) / FPS > 3.0:
            # re-acquire on the face closest to the speaker's usual size (people
            # walking past the camera are much larger, faces on slides smaller)
            c = c[(c[:, 3] > 0.6 * ref_h) & (c[:, 3] < 1.5 * ref_h) & (c[:, 4] > 0.8)]
            if not len(c):
                continue
            best = c[np.argmin(np.abs(np.log(c[:, 3] / ref_h)))]
        else:
            dt = (f - last[0]) / FPS
            dist = np.hypot(c[:, 1] - last[1], c[:, 2] - last[2])
            ok = (dist < last[3] + speed * dt) & (c[:, 3] > 0.6 * last[3]) & (c[:, 3] < 1.6 * last[3])
            if not ok.any():
                continue
            best = c[ok][np.argmin(dist[ok])]
        last = (f, best[1], best[2], best[3])
        ts.append(f / FPS)
        xs.append(best[1])
        ys.append(best[2])
        hs.append(best[3])
    ts, xs, ys, hs = map(np.array, (ts, xs, ys, hs))
    tt = np.arange(n) / FPS
    cx = gaussian_filter1d(np.interp(tt, ts, xs), sigma=FPS * 0.5, mode="nearest")
    cy = gaussian_filter1d(np.interp(tt, ts, ys), sigma=FPS * 1.0, mode="nearest")
    out = {"cx": cx.astype(np.float32), "cy": cy.astype(np.float32), "face_h": np.float32(np.median(hs)),
           "proxy_w": D["proxy_w"], "proxy_h": D["proxy_h"], "hit_rate": np.float32(len(ts) / max(1, len(np.arange(0, n, 3))))}
    np.savez(cache, **out)
    log(f"speaker followed in {out['hit_rate']:.0%} of samples, median face height {out['face_h']:.0f}px")
    return out


# ------------------------------------------------------------ static overlay
def overlay_png(geo: dict, shape: str) -> tuple:
    """Frame around the screen + ring around the head (RGBA) and the head mask (L)."""
    ss = 4                                        # supersampling for smooth edges
    ov = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    def frame(x, y, w, h):                        # 3 px sharp-edged frame, as in the design
        d.rectangle([(x - 3) * ss, (y - 3) * ss, (x + w + 3) * ss, (y + h + 3) * ss], outline=BRAND + (255,), width=3 * ss)
    frame(*geo["scr"])
    hx, hy, hs = geo["head"]
    if shape == "circle":
        box = [(hx - RING) * ss, (hy - RING) * ss, (hx + hs + RING) * ss, (hy + hs + RING) * ss]
        d.ellipse(box, outline=BRAND + (255,), width=RING * ss)
    else:
        frame(hx, hy, hs, hs)
    ov = ov.resize((W, H), Image.LANCZOS)
    mask = Image.new("L", (HEAD * ss, HEAD * ss), 0)
    md = ImageDraw.Draw(mask)
    if shape == "circle":
        md.ellipse([0, 0, HEAD * ss - 1, HEAD * ss - 1], fill=255)
    else:
        md.rectangle([0, 0, HEAD * ss - 1, HEAD * ss - 1], fill=255)
    mask = mask.resize((HEAD, HEAD), Image.LANCZOS)
    LAYOUT.mkdir(parents=True, exist_ok=True)
    ov.save(LAYOUT / "overlay.png")
    mask.save(LAYOUT / "head_mask.png")
    return LAYOUT / "overlay.png", LAYOUT / "head_mask.png"


# --------------------------------------------------------------------- render
def offset_at(o: dict, main_t: np.ndarray) -> np.ndarray:
    ref = o.get("query_start", 0) + o.get("query_len", 0) / 2
    return o["offset"] + o.get("drift_ppm", 0) * 1e-6 * (main_t - o["offset"] - ref)


def head_crops(track: dict, cam_w: int, cam_h: int, n_main: int, cam_off: dict):
    """Per main-timeline frame: camera frame index and crop box (x, y, side)."""
    sx = cam_w / float(track["proxy_w"])
    side = int(round(float(track["face_h"]) * sx * 4.0))       # head + shoulders
    side = min(side, cam_h)
    t = np.arange(n_main) / FPS
    k = np.round((t - offset_at(cam_off, t)) * FPS).astype(int)  # camera frame for each main frame
    kk = np.clip(k, 0, len(track["cx"]) - 1)
    cx = track["cx"][kk] * sx
    cy = track["cy"][kk] * sx
    x = np.clip(cx - side / 2, 0, cam_w - side).round().astype(int)
    y = np.clip(cy - side * 0.45, 0, cam_h - side).round().astype(int)
    return k, x, y, side


def render(preview_times=None):
    cfg = config()
    offs, probe = load_json("offsets.json"), load_json("probe.json")
    plan = load_json("edit_plan.json")
    crop = __import__("08_reels").screen_crop(probe["screen"]["duration"])
    shape = cfg.get("head_shape", "circle")
    geo = geometry(crop)
    overlay, mask = overlay_png(geo, shape)
    track = track_head(probe["camera"]["duration"])

    approved = sorted((c for c in plan["cuts"] if c["status"] == "approved"), key=lambda c: c["start"])
    t_in = approved[0]["end"] if approved and approved[0]["start"] <= 0.5 else 0.0
    dur = offs["main_duration"]
    n_main = int(dur * FPS)
    cam_v = probe["camera"]["video"][0]
    cw, ch = cam_v["width"], cam_v["height"]
    k, hx, hy, side = head_crops(track, cw, ch, n_main, offs["camera"])
    sx, sy, sw, sh = geo["scr"]
    px, py, ps = geo["head"]
    bg = WORK / "brand" / "video-background@2x.png"     # 11_brand.py
    if not bg.exists():
        bg = LECTURE / cfg["background_png"]
    scr_off = offs["screen"]["offset"]
    c = crop

    frames = range(n_main)
    if preview_times:
        frames = [int(t * FPS) for t in preview_times]

    # stills are decoded and scaled ONCE, then repeated by the loop filter
    fc = (f"[0:v]scale={W}:{H}:flags=lanczos,format=rgb24,loop=-1:1,setpts=N/{FPS}/TB[bg];"
          f"[1:v]fps={FPS},crop={c[0]}:{c[1]}:{c[2]}:{c[3]},scale={sw}:{sh}:flags=lanczos,format=rgba,"
          f"setpts=PTS+{scr_off:.4f}/TB,fade=in:st={t_in:.3f}:d=0.6:alpha=1[scr];"
          f"[2:v]format=rgb24,setpts=N/{FPS}/TB[headrgb];[3:v]format=gray,loop=-1:1,setpts=N/{FPS}/TB[m];"
          f"[headrgb][m]alphamerge,fade=in:st={t_in:.3f}:d=0.6:alpha=1[head];"
          f"[bg][scr]overlay={sx}:{sy}:eof_action=pass[a];"
          f"[a][head]overlay={px}:{py}:eof_action=pass[b];"
          f"[4:v]format=rgba,loop=-1:1,setpts=N/{FPS}/TB,fade=in:st={t_in:.3f}:d=0.6:alpha=1[ov];"
          f"[b][ov]overlay=0:0[v]")
    LAYOUT.mkdir(parents=True, exist_ok=True)
    if preview_times:
        return preview(preview_times, k, hx, hy, side, geo, overlay, mask, bg, crop, scr_off, t_in)

    dst = LAYOUT / "program.mp4"
    tmp = LAYOUT / "program.part.mp4"
    cmd = [ffmpeg_bin(), "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
           "-i", str(bg),
           "-i", str(src("screen")),
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ps}x{ps}", "-r", str(FPS), "-i", "-",
           "-i", str(mask),
           "-i", str(overlay),
           "-filter_complex", fc, "-map", "[v]", "-t", f"{dur:.3f}", "-r", str(FPS),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(tmp)]
    log(f"rendering program {tc(dur)} (head {shape}, screen+head fade in at {tc(t_in)}) – ~10–15 min")
    comp = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    reader = subprocess.Popen([ffmpeg_bin(), "-v", "error", "-nostdin", "-i", str(src("camera")),
                               "-map", "0:v:0", "-vf", f"fps={FPS}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                              stdout=subprocess.PIPE)
    fsize = cw * ch * 3
    cur_idx, cur = -1, np.zeros((ch, cw, 3), np.uint8)
    blank = np.zeros((ps, ps, 3), np.uint8).tobytes()
    t0 = time.time()
    for i in range(n_main):
        if i and i % (FPS * 120) == 0:            # progress every 2 min of material
            el = time.time() - t0
            log(f"  {i / n_main:5.1%}  {tc(i / FPS)} / {tc(dur)}  speed {i / FPS / el:.1f}×  "
                f"ETA {tc(el / i * (n_main - i))}")
        want = k[i]
        if want < 0:
            comp.stdin.write(blank)
            continue
        while cur_idx < want:
            buf = reader.stdout.read(fsize)
            if len(buf) < fsize:
                break
            cur = np.frombuffer(buf, np.uint8).reshape(ch, cw, 3)
            cur_idx += 1
        if cur_idx < want:            # camera ended
            comp.stdin.write(blank)
            continue
        roi = cur[hy[i]:hy[i] + side, hx[i]:hx[i] + side]
        comp.stdin.write(cv2.resize(roi, (ps, ps), interpolation=cv2.INTER_LANCZOS4).tobytes())
    comp.stdin.close()
    reader.stdout.close()
    reader.terminate()
    if comp.wait() != 0:
        raise SystemExit("program render failed")
    tmp.rename(dst)
    log(f"wrote {dst.relative_to(LECTURE)}")


def preview(times, k, hx, hy, side, geo, overlay, mask, bg, crop, scr_off, t_in):
    """Compose single frames in Python (fast) to judge the layout."""
    base = Image.open(bg).convert("RGB").resize((W, H), Image.LANCZOS)
    ov = Image.open(overlay)
    m = Image.open(mask)
    sx, sy, sw, sh = geo["scr"]
    px, py, ps = geo["head"]
    for t in times:
        i = int(t * FPS)
        img = base.copy()
        scr = subprocess.run([ffmpeg_bin(), "-v", "error", "-nostdin", "-ss", f"{t - scr_off:.3f}", "-i", str(src("screen")),
                              "-frames:v", "1", "-vf", f"crop={crop[0]}:{crop[1]}:{crop[2]}:{crop[3]},scale={sw}:{sh}",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        if len(scr) == sw * sh * 3:
            img.paste(Image.frombytes("RGB", (sw, sh), scr), (sx, sy))
        cam = subprocess.run([ffmpeg_bin(), "-v", "error", "-nostdin", "-ss", f"{k[i] / FPS:.3f}", "-i", str(src("camera")),
                              "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        probe = load_json("probe.json")["camera"]["video"][0]
        cw, ch = probe["width"], probe["height"]
        if len(cam) == cw * ch * 3:
            fr = np.frombuffer(cam, np.uint8).reshape(ch, cw, 3)
            roi = cv2.resize(fr[hy[i]:hy[i] + side, hx[i]:hx[i] + side], (ps, ps), interpolation=cv2.INTER_LANCZOS4)
            img.paste(Image.fromarray(roi), (px, py), m)
        img.paste(ov, (0, 0), ov)
        out = LAYOUT / f"preview_{int(t)}.jpg"
        img.save(out, quality=90)
        log(f"wrote {out.relative_to(LECTURE)}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        render([float(a) for a in sys.argv[2:]] or [400.0, 1200.0, 2000.0])
    else:
        render()
