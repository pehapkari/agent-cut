"""Step 9 – automatic QA of rendered reels → work/check/.

For every reel:
  * 3 frames (start, middle, end) + a contact sheet NN_sheet.jpg for eyeballing
  * face detected inside the camera box and not touching its edges
  * subtitles: ≤ 2 lines per cue, no line wider than the frame
  * lip sync: the camera's own microphone (original MOV) is cross-correlated
    with the audio used in the reel; the residual must stay within ±1 frame
Writes work/check/report.md with what needs a human look.
"""
import json
import re
import subprocess

import cv2
import numpy as np
from scipy import signal

from common import LECTURE, TOOLS, WORK, load_json, log, src, tc

SR = 16000
W, H, TOP_H = 1080, 1920, 960
CHECK = WORK / "check"


def pcm(path, start, dur, stream="0:a:0"):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
                          "-i", str(path), "-map", stream, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).astype(np.float64)
    x = signal.sosfiltfilt(signal.butter(4, [200, 4000], "band", fs=SR, output="sos"), x)
    return x / (x.std() + 1e-9)


def lip_sync_ms(h: dict, offs: dict) -> float:
    """Residual between the camera's own audio and the reel audio (ms, + = camera late)."""
    cam_t0 = h["start"] - h["render"]["camera_offset"]
    dur = h["end"] - h["start"]
    reel = pcm(LECTURE / h["render"]["file"], 0, dur)
    cam = pcm(src("camera"), cam_t0 - 0.5, dur + 1.0)
    c = signal.correlate(cam, reel, mode="valid", method="fft")
    return (int(np.argmax(np.abs(c))) / SR - 0.5) * 1000


def grab(video, t, dst):
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{t:.3f}", "-i", str(video),
                    "-frames:v", "1", "-q:v", "3", str(dst)], check=True)
    return cv2.imread(str(dst))


def check_face(img, layout: str) -> str | None:
    det = cv2.FaceDetectorYN.create(str(TOOLS / "models" / "face_detection_yunet_2023mar.onnx"), "",
                                    (img.shape[1], img.shape[0]), 0.6)
    _, faces = det.detect(img)
    box_h = TOP_H if layout == "split" else H
    if faces is None:
        return "face not detected"
    x, y, w, h = max(faces, key=lambda r: r[2] * r[3])[:4]
    if y + h > box_h or y < 0 or x < 0 or x + w > W:
        return f"face outside camera box ({int(x)},{int(y)} {int(w)}×{int(h)})"
    if y < box_h * 0.08 or x < W * 0.08 or x + w > W * 0.92:
        return f"face close to the edge ({int(x)},{int(y)})"
    return None


def check_subs(ass_path) -> list[str]:
    from PIL import ImageFont
    font = ImageFont.truetype(str(TOOLS / "fonts" / "Montserrat-ExtraBold.ttf"), 76)
    issues = []
    for line in ass_path.read_text().splitlines():
        if not line.startswith("Dialogue: 1,"):
            continue
        text = re.sub(r"\{[^}]*\}", "", line.split(",,", 1)[1].split(",,", 1)[-1])
        rows = text.split("\\N")
        if len(rows) > 2:
            issues.append(f"{len(rows)} lines: {text}")
        for r in rows:
            if font.getlength(r) > W - 2 * 60:
                issues.append(f"line too wide ({font.getlength(r):.0f}px): {r}")
    return issues


def main():
    offs = load_json("offsets.json")
    hl = [h for h in load_json("highlights.json") if h.get("selected") and h.get("render")]
    CHECK.mkdir(exist_ok=True)
    report, rows = [], ["# Kontrola reels", ""]
    for n, h in enumerate(hl, 1):
        r = h["render"]
        video = LECTURE / r["file"]
        dur = h["end"] - h["start"]
        stem = video.stem
        frames, problems = [], []
        for tag, t in (("a_start", 0.6), ("b_mid", dur / 2), ("c_end", dur - 0.6)):
            img = grab(video, t, CHECK / f"{stem}_{tag}.jpg")
            frames.append(cv2.resize(img, (360, 640)))
            p = check_face(img, r["layout"])
            if p:
                if "edge" in p and r.get("crop_at_edge", 0) > 0:
                    p += f" – ořez je na hraně záběru kamery ({r['crop_at_edge']:.0%} snímků), limit záběru"
                problems.append(f"{tag}: {p}")
        cv2.imwrite(str(CHECK / f"{stem}_sheet.jpg"), np.hstack(frames))
        problems += [f"subs: {s}" for s in check_subs(WORK / "reels" / f"{stem}.ass")]
        lip = lip_sync_ms(h, offs)
        if abs(lip) > 1000 / 30:
            problems.append(f"lip sync off by {lip:+.0f} ms")
        report.append({"reel": stem, "layout": r["layout"], "lip_sync_ms": round(lip, 1), "problems": problems})
        log(f"{stem}: lip-sync {lip:+.1f} ms, {len(problems)} problem(s)")
        rows += [f"## {stem}", "", f"- layout: {r['layout']} ({r['layout_reason']})",
                 f"- lip-sync residual: {lip:+.1f} ms", f"- čas v přednášce: {tc(h['start'])}–{tc(h['end'])}",
                 f"- náhled: `work/check/{stem}_sheet.jpg`"]
        rows += [f"- ⚠️ {p}" for p in problems] or ["- ✅ bez automaticky zjištěných problémů"]
        rows.append("")
    (CHECK / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    (CHECK / "report.md").write_text("\n".join(rows))
    log("wrote work/check/report.md")


if __name__ == "__main__":
    main()
